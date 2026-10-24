"""Claude-shaped plugin hooks for dispatch checks, guards and run accounting."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from consortium import brief, config, paths, registry, runlog, schemas
from consortium.cli import EXIT_OK

EVENTS = ("pre-agent", "pre-bash", "pre-write", "subagent-start", "subagent-stop")


def _diagnostic(error):
    # Exception messages can contain payload text or secrets, and even newlines.
    print(f"consortium hook: {type(error).__name__}", file=sys.stderr)


def _deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def _context(text):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def _block(schema, errors):
    return {"decision": "block", "reason": f"Your report does not match {schema}: " +
            "\n".join(errors) + ". End with one json block that matches it."}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _agent_file(agent_id):
    if not isinstance(agent_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", agent_id):
        raise ValueError("agent id must be a single path component")
    return paths.state_home() / "agents" / f"{agent_id}.json"


def _read(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def _start_data(payload):
    return _read(_agent_file(payload["agent_id"])) if payload.get("agent_id") else {}


def _agent_type(payload, env):
    if payload.get("agent_type"):
        return payload["agent_type"]
    agent_type = _start_data(payload).get("agent_type")
    if agent_type:
        return agent_type
    name = env.get("CONSORTIUM_AGENT", "")
    return name if not name or name.startswith("consortium:") else "consortium:" + name


def _job(agent_type, repo):
    if not agent_type.startswith("consortium:"):
        return None, None
    jobs = registry.load_registry(repo)
    name = agent_type.removeprefix("consortium:")
    job = jobs.get(name)
    return (job, jobs) if job is not None and job.ready else (None, jobs)


def _pre_agent(payload, env, cwd, repo):
    tool = payload["tool_input"]
    job, jobs = _job(tool.get("subagent_type", ""), repo)
    if job is None:
        return None
    task = brief.parse_brief(brief.brief_in_prompt(tool.get("prompt", "")))
    settings = config.load_settings(repo, task.front)
    run = registry.resolve_agent(job.name, settings, jobs, brief=task.front, manager_app="claude")
    findings = brief.check_brief(task, job, run.mode, repo or cwd, settings)
    if not findings:
        return None
    text = "\n".join(f"{finding.rule}: {finding.message}" for finding in findings)
    tier = subprocess.run(["bash", str(paths.package_root() / "scripts/effort.sh"), "--resolve"],
                          cwd=cwd, env=dict(env), capture_output=True, text=True, check=True, timeout=10)
    return _deny(text) if tier.stdout.strip() == "off" else _context(text)


def _segments(command):
    # Redirections are tokens of their own, so "2>&1" is not split at its "&".
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n<>")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    current = []
    for token in lexer:
        if token and all(char in ";&|\n" for char in token):
            if current:
                yield current
                current = []
        else:
            current.append(token)
    if current:
        yield current


def _shell_command(argv):
    if Path(argv[0]).name in {"bash", "sh"}:
        for index, token in enumerate(argv[1:], 1):
            if token.startswith("-") and not token.startswith("--") and "c" in token[1:]:
                if index + 1 < len(argv):
                    return argv[index + 1]
    return None


# Ways a command on the read-only allowlist can still write a file or start another program.
_WRITE_FLAGS = {
    "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"),
    "sort": ("-o", "--output"),
    "tree": ("-o",),
    "rg": ("--pre",),
    "git": ("--output", "-O", "--open-files-in-pager"),
}


def _writes(argv):
    """Whether a read-only agent's segment writes a file, or runs a command the allowlist never saw."""
    for index, token in enumerate(argv):
        if any(mark in token for mark in ("$(", "`")) or token.startswith("("):
            return True
        if token and set(token) <= set("<>&|") and ">" in token:
            target = argv[index + 1] if index + 1 < len(argv) else ""
            if target != "/dev/null" and not re.fullmatch(r"\d+|-", target):
                return True
    flags = _WRITE_FLAGS.get(Path(argv[0]).name, ())
    return any(token == flag or token.startswith(flag + "=") or (flag == "-O" and token.startswith("-O"))
               for token in argv[1:] for flag in flags)


def _make_targets(argv):
    value_options = {"-C", "-f", "-I", "-o", "-W", "--directory", "--file", "--makefile", "--include-dir",
                     "--old-file", "--assume-old", "--what-if", "--new-file", "--assume-new"}
    skip = False
    for token in argv[1:]:
        if skip:
            skip = False
        elif token in value_options:
            skip = True
        elif not token.startswith("-") and "=" not in token:
            yield token


def _command_reason(command, settings, allow):
    for argv in _segments(command):
        normalized = " ".join(argv)
        # Global-option regexes must still see one operand when a quoted -C
        # path contains spaces. Preserve argument boundaries for that check.
        words = " ".join(re.sub(r"\s", lambda match: f"\\x{ord(match[0]):02x}", word) for word in argv)
        if any(re.search(pattern, text) for key in ("guard.deny", "guard.deny_in_repo")
               for pattern in settings.get(key, [])
               for text in (normalized, words)):
            return "Command is not allowed inside an agent run; the manager commits, pushes and deploys"
        if Path(argv[0]).name == "make" and any(
            config.glob_match(target, pattern)
            for target in _make_targets(argv) for pattern in settings.get("guard.deny_make", [])
        ):
            return "Make target is not allowed inside an agent run; the manager deploys"
        inner = _shell_command(argv)
        if inner is not None:
            reason = _command_reason(inner, settings, allow)
            if reason:
                return reason
        elif allow is not None and not any(re.search(pattern, normalized) for pattern in allow):
            return "Command is not on this read-only agent's Bash allowlist"
        elif allow is not None and _writes(argv):
            return "A read-only agent may not write files or run commands inside its command"
    return None


def _pre_bash(payload, env, repo):
    settings = config.load_settings(repo)
    job, jobs = _job(_agent_type(payload, env), repo)
    allow = None
    if job is not None:
        run = registry.resolve_agent(job.name, settings, jobs, manager_app="claude")
        if run.mode == "read-only":
            allow = list(settings.get("modes.read-only.bash_allow", []))
            for capability in run.capabilities:
                allow.extend(settings.get(f"capabilities.{capability}.bash_allow", []))
    reason = _command_reason(payload["tool_input"]["command"], settings, allow)
    return _deny(reason) if reason else None


def _pre_write(payload, env, cwd, repo):
    settings = config.load_settings(repo)
    job, jobs = _job(_agent_type(payload, env), repo)
    run = registry.resolve_agent(job.name, settings, jobs, manager_app="claude") if job is not None else None
    if run is not None and run.mode == "read-only":
        return _deny("This agent is read-only")
    tool = payload["tool_input"]
    target = (cwd / (tool.get("file_path") or tool["notebook_path"])).resolve()
    if env.get("CONSORTIUM_WORKTREE") and not target.is_relative_to(Path(env["CONSORTIUM_WORKTREE"]).resolve()):
        return _deny("Write path is outside the agent's worktree")
    if run is not None and run.write_scope == "tests":
        root = (repo or cwd).resolve()
        if not target.is_relative_to(root) or not any(
            config.glob_match(target.relative_to(root).as_posix(), pattern)
            for pattern in settings.get("test_paths", [])
        ):
            return _deny("This agent may write only test paths")
    return None


def _subagent_start(payload):
    target = _agent_file(payload["agent_id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        agent_type = payload["agent_type"]
        target.write_text(json.dumps({"agent_type": agent_type, "session_id": payload["session_id"],
                                      "started": _now(), "id": runlog.new_run_id(agent_type.removeprefix("consortium:"))}) + "\n")


def _last_assistant_message(transcript):
    # The captured SubagentStop has no last_assistant_message. Read text blocks
    # from the agent transcript named by that event instead of the manager's.
    last_id, parts = None, []
    try:
        with transcript.open() as stream:
            for index, line in enumerate(stream):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("type") == "assistant":
                    message = row.get("message", {})
                    content = message.get("content", [])
                    texts = [block["text"] for block in content
                             if isinstance(block, dict) and block.get("type") == "text"]
                    if texts:
                        message_id = message.get("id") or index
                        if message_id != last_id:
                            parts = []
                            last_id = message_id
                        parts.extend(texts)
    except FileNotFoundError:
        pass
    return "\n".join(parts)


def _subagent_stop(payload, env, cwd, repo):
    job, jobs = _job(_agent_type(payload, env), repo)
    if job is None:
        _agent_file(payload["agent_id"]).unlink(missing_ok=True)  # every subagent gets a start file
        return None
    start_file = _agent_file(payload["agent_id"])
    # Keep just the id after removing the start file: duplicate stop deliveries,
    # including ones with no start event, must reuse record_run's idempotency key.
    completed = start_file.parent / "completed" / start_file.name
    if completed.is_file():
        return None
    start = _read(start_file)
    settings = config.load_settings(repo)
    run = registry.resolve_agent(job.name, settings, jobs, manager_app="claude")
    transcript = Path(payload["agent_transcript_path"])
    text = payload.get("last_assistant_message") or _last_assistant_message(transcript)
    report = schemas.extract_report(text)
    schema = report.get("schema") if report else run.report
    if schema not in (run.report, *run.alt_reports):
        schema = run.report
    errors = schemas.validate(report, schemas.load_schema(schema))
    if errors and not payload.get("stop_hook_active", False):
        return _block(schema, errors)
    run_id = start.get("id") or runlog.new_run_id(job.name)
    folder = runlog.run_dir(run_id)
    report_file = folder / "report.json"
    redacted, _ = schemas.redact(json.dumps(report, ensure_ascii=False), settings.get("runs.secret_patterns", []))
    report_file.write_text(redacted + "\n")
    tokens, model = runlog.tokens_from_claude_transcript(transcript)
    ended = _now()
    started = start.get("started") or ended
    minutes = (datetime.fromisoformat(ended.replace("Z", "+00:00")) -
               datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds() / 60
    branch = subprocess.run(["git", "-C", str(cwd), "branch", "--show-current"], capture_output=True, text=True)
    runlog.record_run(id=run_id, agent=job.name, jd_version=run.version, app="claude", model=model,
                      effort=run.effort, tier=run.tier, repo=str(paths.main_checkout(repo)) if repo else None,
                      worktree=str(cwd), branch=branch.stdout.strip() or None, started=started, ended=ended,
                      minutes=minutes, status="FAILED" if errors else report["status"],
                      error="malformed_report" if errors else None, locks=list(run.locks), tokens=tokens,
                      report=str(report_file), scope_ok=None, manager="claude")
    completed.parent.mkdir(parents=True, exist_ok=True)
    completed.write_text(json.dumps({"id": run_id}) + "\n")
    start_file.unlink(missing_ok=True)
    return None


def handle(event: str, payload: dict, env: Mapping[str, str]) -> dict | None:
    """Return hook JSON without printing it; unexpected errors always allow."""
    try:
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
        if event in {"pre-bash", "pre-write"} and not payload.get("agent_id") and not env.get("CONSORTIUM_RUN"):
            return None
        if event == "subagent-start":
            _subagent_start(payload)
            return None
        cwd = Path(payload["cwd"]).resolve()
        repo = paths.repo_root(cwd)
        if event == "pre-agent":
            return _pre_agent(payload, env, cwd, repo)
        if event == "pre-bash":
            return _pre_bash(payload, env, repo)
        if event == "pre-write":
            return _pre_write(payload, env, cwd, repo)
        if event == "subagent-stop":
            return _subagent_stop(payload, env, cwd, repo)
        raise ValueError("unknown hook event")
    except Exception as error:
        _diagnostic(error)
        return None


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("hook", help="internal plugin hook handler")
    parser.add_argument("event", choices=EVENTS)
    parser.set_defaults(func=_hook)


def _hook(args: argparse.Namespace) -> int:
    try:
        result = handle(args.event, json.load(sys.stdin), os.environ)
        if result is not None:
            print(json.dumps(result))
    except Exception as error:
        _diagnostic(error)
    return EXIT_OK

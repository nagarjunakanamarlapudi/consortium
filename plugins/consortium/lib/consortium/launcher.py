"""Prepare, launch and account for guarded Codex agent runs."""

import argparse
from dataclasses import asdict, fields
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

from consortium import brief, locks, paths, registry, runlog, schemas
from consortium.cli import EXIT_FAIL, EXIT_OK, EXIT_WRONG_APP
from consortium.config import ConfigError, glob_match, load_settings


CODEX_BIN = os.environ.get("CONSORTIUM_CODEX", "codex")
TMUX_SOCKET = os.environ.get("CONSORTIUM_TMUX_SOCKET", "consortium")
SYSTEM_BIN_DIR = Path("/usr/bin")


class LaunchError(Exception):
    def __init__(self, message, code=EXIT_FAIL):
        super().__init__(message)
        self.code = code


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path, value):
    # Readers must never see a truncated status while the worker replaces it.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def _read_json(path):
    return json.loads(path.read_text())


def _tmux(*args):
    return ["tmux", "-L", os.environ.get("CONSORTIUM_TMUX_SOCKET", TMUX_SOCKET), "-f", "/dev/null", *args]


def codex_argv(run: registry.AgentRun, cwd: Path, rd: Path) -> list[str]:
    return [CODEX_BIN, "exec", "-m", run.model, "-c", f'model_reasoning_effort="{run.effort}"',
            "-c", 'approval_policy="never"', "-c", 'shell_environment_policy.inherit="all"',
            "-c", "allow_login_shell=false", "-s", run.sandbox, "-C", str(cwd), "--json",
            "--output-schema", str(rd / "schema.json"), "-o", str(rd / "last.md"), "-"]


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _status(repo):
    return _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")


def _status_paths(status):
    result = {}
    records = iter(status.split("\0"))
    for entry in records:
        if not entry:
            continue
        result[entry[3:]] = entry[:2]
        if "R" in entry[:2] or "C" in entry[:2]:
            original = next(records, "")
            if original:
                result[original] = entry[:2]
    return result


def _fingerprints(root, status):
    """Detect edits that leave an already-dirty file's porcelain code unchanged."""
    result = {}
    for name in _status_paths(status):
        path = root / name
        if path.is_symlink():
            result[name] = os.readlink(path)
        elif path.is_file():
            with path.open("rb") as stream:
                result[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            result[name] = None
    return result


def _changed_paths(before, after, fingerprints_before, fingerprints_after):
    before, after = _status_paths(before), _status_paths(after)
    return sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
                  or fingerprints_before.get(path) != fingerprints_after.get(path))


def _branch(repo):
    return _git(repo, "branch", "--show-current").strip() or None


def prepare_run(agent, brief_path, repo, *, worktree=None, new_worktree=None, base=None, overrides=None) -> str:
    repo = Path(repo).expanduser().resolve()
    main = paths.main_checkout(repo)
    text = Path(brief_path).read_text()
    task = brief.parse_brief(text)
    front = {**task.front, **(overrides or {})}
    settings = load_settings(repo, front)
    jobs = registry.load_registry(repo)
    run = registry.resolve_agent(agent, settings, jobs, brief=front, manager_app="codex")
    if run.app == "claude":
        raise LaunchError(f"{agent} runs on Claude Code here; dispatch consortium:{agent}", EXIT_WRONG_APP)
    if worktree is not None and new_worktree is not None:
        raise LaunchError("--worktree and --new-worktree are mutually exclusive")
    selected = worktree or front.get("worktree")
    if run.mode == "worktree-write" and not selected and not new_worktree:
        raise LaunchError("a worktree-write agent needs --worktree, --new-worktree, or worktree: in the brief")
    cwd = Path(selected).expanduser().resolve() if selected else repo
    if not cwd.is_dir():
        raise LaunchError(f"worktree does not exist: {cwd}")
    # An explicit worktree wins over the brief for both path checks and execution.
    checked = brief.Brief({**front, "worktree": str(cwd)}, task.sections, text)
    findings = brief.check_brief(checked, jobs[agent], run.mode, repo, settings)
    if findings:
        raise LaunchError("\n".join(f"{finding.rule}: {finding.message}" for finding in findings))
    schema = schemas.load_schema(run.report)
    if new_worktree:
        directory = (main / settings.get("worktree.dir") / new_worktree).resolve()
        command = ["git", "-C", str(main), "worktree", "add", "-b", new_worktree,
                   str(directory), base or "HEAD"]
        script = "set -e\nexec 1>&2\n" + shlex.join(command) + "\ncd " + shlex.quote(str(directory))
        for setup in settings.get("worktree.setup", []):
            script += "\n" + setup
        code = locks.run_locked(["disk"], ["sh", "-c", script], settings.get("locks.wait_seconds"), repo)
        if code:
            raise LaunchError("new worktree or setup failed", code)
        cwd = directory
    run_id = runlog.new_run_id(agent)
    manager = "codex" if os.environ.get("CODEX_THREAD_ID") else "claude" if os.environ.get("CLAUDECODE") else None
    meta = {**asdict(run), "run_id": run_id, "agent": agent, "repo": str(main),
            "worktree": str(cwd), "branch": _branch(cwd), "brief": str(brief_path),
            "started": _now(), "manager": manager}
    before = {"main_before": _status(main), "worktree_before": _status(cwd)}
    before["main_fingerprints_before"] = _fingerprints(main, before["main_before"])
    before["worktree_fingerprints_before"] = _fingerprints(cwd, before["worktree_before"])
    rd = runlog.run_dir(run_id)
    (rd / "brief.md").write_text(text)
    (rd / "prompt.md").write_text(registry.compose_prompt(jobs[agent], run, text))
    _write_json(rd / "schema.json", schema)
    _write_json(rd / "meta.json", meta)
    _write_json(rd / "scope.json", before)
    _write_json(rd / "status.json", {"status": "running"})
    return run_id


def _server_environment() -> dict | None:
    """The tmux server's global environment, or None when no server is running."""
    result = subprocess.run(_tmux("show-environment", "-g"), capture_output=True, text=True)
    if result.returncode:
        return None
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line and not line.startswith("-"))


def _session_env_args(server: dict | None, env: dict) -> list[str]:
    """tmux -e arguments that make a new session's environment equal env.

    A new server copies its environment from the client that starts it, so it needs none. A running one keeps the
    environment it started with: send only the values that differ, and the names of variables to drop, which
    `_environment` removes before Codex starts. tmux's `-e NAME` does not unset a variable.
    """
    if server is None:
        return []
    args = []
    for key, value in sorted(env.items()):
        if server.get(key) != value:
            args.extend(["-e", f"{key}={value}"])
    stale = sorted(server.keys() - env.keys())
    if stale:
        args.extend(["-e", "CONSORTIUM_UNSET=" + ",".join(stale)])
    return args


def _developer_tools(run_id, shims, path):
    """Wrap the binaries behind macOS's xcrun shims for the guarded commands; the run's bin folder, or None."""
    if sys.platform != "darwin":
        return None
    lookup = os.pathsep.join(entry for entry in path.split(os.pathsep)
                             if Path(entry or ".").resolve() != shims)
    xcrun = shutil.which("xcrun", path=lookup)
    folder = runlog.run_dir(run_id) / "bin"
    for shim in shims.iterdir():
        binary = shutil.which(shim.name, path=lookup)
        if not xcrun or not binary or not Path(binary).resolve().is_relative_to(SYSTEM_BIN_DIR.resolve()):
            continue
        try:
            # Resolve xcrun's shims before Codex's sandbox prevents its cache writes.
            result = subprocess.run([xcrun, "--find", shim.name], capture_output=True, text=True, timeout=5)
            target = Path(result.stdout.strip())
            if result.returncode or not target.is_absolute() or not target.is_file() or not os.access(target, os.X_OK):
                continue
            folder.mkdir(exist_ok=True)
            script = folder / shim.name
            temporary = script.with_suffix(".tmp")
            try:
                temporary.write_text(f'#!/bin/sh\nexec {shlex.quote(str(target))} "$@"\n')
                temporary.chmod(0o755)
                os.replace(temporary, script)
            finally:
                temporary.unlink(missing_ok=True)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return folder if folder.is_dir() and any(tool.is_file() and not tool.is_symlink() and os.access(tool, os.X_OK)
                                            for tool in folder.iterdir()) else None


def _environment(meta, task, settings):
    allow = []
    if meta["mode"] == "read-only":
        allow.extend(settings.get("modes.read-only.bash_allow", []))
        for capability in meta["capabilities"]:
            allow.extend(settings.get(f"capabilities.{capability}.bash_allow", []))
    unset = set(filter(None, os.environ.get("CONSORTIUM_UNSET", "").split(","))) | {"CONSORTIUM_UNSET"}
    env = {key: value for key, value in os.environ.items() if key not in unset}
    shims = paths.package_root() / "lib/consortium/shims"
    path = env.get("PATH", "")
    binary_dir = _developer_tools(meta["run_id"], shims, path)
    if binary_dir is not None:
        path = str(binary_dir) + os.pathsep + path
    env.update({"CONSORTIUM_RUN": meta["run_id"], "CONSORTIUM_AGENT": meta["agent"],
                "CONSORTIUM_MODE": meta["mode"], "CONSORTIUM_WRITE_SCOPE": meta["write_scope"],
                "CONSORTIUM_WORKTREE": meta["worktree"], "CONSORTIUM_GUARD": json.dumps({
                    "deny": settings.get("guard.deny", []), "deny_in_repo": settings.get("guard.deny_in_repo", []),
                    "deny_make": settings.get("guard.deny_make", []),
                    "bash_allow": allow}),
                "PATH": str(shims) + os.pathsep + path})
    return env


def start(run_id: str, detach: bool) -> None:
    rd = runlog.run_dir(run_id)
    meta = _read_json(rd / "meta.json")
    if not detach or os.environ.get("CONSORTIUM_NO_TMUX") == "1":
        execute(run_id)
        return
    task = brief.parse_brief((rd / "brief.md").read_text())
    env = _environment(meta, task, load_settings(Path(meta["repo"]), task.front))
    command = _tmux("new-session", "-d", "-s", run_id, "-c", meta["worktree"])
    command.extend(_session_env_args(_server_environment(), env))
    command.extend(["--", str(paths.package_root() / "bin/consortium"), "_run", run_id])
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode:
        (rd / "stderr.log").write_text(result.stderr)
        finalize(run_id, result.returncode)
        raise LaunchError(result.stderr.strip() or "tmux could not start the run")


def _run_locks(meta, task):
    names = list(meta["locks"])
    if task.front.get("device"):
        names.append("device:" + str(task.front["device"]))
    return sorted(set(names))


def _kill_group(child, signum):
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass


def execute(run_id: str) -> int:
    rd = runlog.run_dir(run_id)
    meta = _read_json(rd / "meta.json")
    task = brief.parse_brief((rd / "brief.md").read_text())
    settings = load_settings(Path(meta["repo"]), task.front)
    env = _environment(meta, task, settings)
    names = _run_locks(meta, task)
    inherited = set(filter(None, env.get("CONSORTIUM_LOCKS_HELD", "").split(",")))
    env["CONSORTIUM_LOCKS_HELD"] = ",".join(sorted(inherited | set(names)))
    owner = {"pid": os.getpid(), "command": f"consortium _run {run_id}", "cwd": meta["worktree"],
             "run_id": run_id, "started": meta["started"]}
    run = registry.AgentRun(**{field.name: meta[field.name] for field in fields(registry.AgentRun)})
    code = 1
    with (rd / "stderr.log").open("w") as errors:
        try:
            with locks.hold(names, settings.get("locks.wait_seconds"), owner):
                with (rd / "prompt.md").open() as prompt, (rd / "events.jsonl").open("w") as events:
                    child = subprocess.Popen(codex_argv(run, Path(meta["worktree"]), rd),
                                             cwd=meta["worktree"], env=env, stdin=prompt,
                                             stdout=events, stderr=errors, start_new_session=True)
                    previous = {}
                    try:
                        for signum in (signal.SIGINT, signal.SIGTERM):
                            previous[signum] = signal.signal(signum, lambda sig, frame: _kill_group(child, sig))
                        try:
                            code = child.wait(timeout=meta["timeout_minutes"] * 60)
                            if code < 0:
                                code = 128 - code
                        except subprocess.TimeoutExpired:
                            _kill_group(child, signal.SIGTERM)
                            # Even if Codex exits on TERM, descendants may ignore it.
                            time.sleep(10)
                            _kill_group(child, signal.SIGKILL)
                            child.wait()
                            code = 124
                    finally:
                        for signum, handler in previous.items():
                            signal.signal(signum, handler)
        except (OSError, locks.LockTimeout, locks.DiskFloor) as error:
            print(str(error), file=errors)
            code = 4 if isinstance(error, locks.LockTimeout) else 5 if isinstance(error, locks.DiskFloor) else 1
    finalize(run_id, code)
    return code


def finalize(run_id: str, exit_code: int) -> dict:
    rd = runlog.run_dir(run_id)
    meta = _read_json(rd / "meta.json")
    current = _read_json(rd / "status.json")
    if current["status"] != "running":
        return current
    task = brief.parse_brief((rd / "brief.md").read_text())
    root = Path(meta["worktree"])
    settings = load_settings(Path(meta["repo"]), task.front)
    text = (rd / "last.md").read_text() if (rd / "last.md").exists() else ""
    report = schemas.extract_report(text)
    valid = report is not None and not schemas.validate(report, _read_json(rd / "schema.json"))
    # Look for a quota error only when the run failed, and only in Codex's own errors: an agent that reads code
    # about HTTP 429 or rate limits must not turn a good run into a quota failure.
    errors = (rd / "stderr.log").read_text() if (rd / "stderr.log").exists() else ""
    if (rd / "events.jsonl").exists():
        for line in (rd / "events.jsonl").read_text().splitlines():
            event = schemas.extract_report(line) or {}
            kind = str(event.get("type", ""))
            if kind == "error" or kind.endswith(".failed"):
                errors += "\n" + line
    failed = exit_code != 0 or not valid
    error = ("timeout" if exit_code == 124 else "quota" if failed and any(
        re.search(pattern, errors) for pattern in settings.get("runs.quota_patterns", [])
    ) else "malformed_report" if not valid else None)
    if valid:
        # Redact strings within JSON, so a configured pattern cannot break its syntax.
        def redact_value(value):
            if isinstance(value, str):
                return schemas.redact(value, settings.get("runs.secret_patterns", []))[0]
            if isinstance(value, list):
                return [redact_value(item) for item in value]
            if isinstance(value, dict):
                return {key: redact_value(item) for key, item in value.items()}
            return value
        _write_json(rd / "report.json", redact_value(report))
    scope = _read_json(rd / "scope.json")
    scope["main_after"] = _status(Path(meta["repo"]))
    fingerprints = _fingerprints(Path(meta["repo"]), scope["main_after"])
    scope["main_changes"] = _changed_paths(scope["main_before"], scope["main_after"],
                                           scope["main_fingerprints_before"], fingerprints)
    scope["worktree_after"] = _status(root)
    changed = _changed_paths(scope["worktree_before"], scope["worktree_after"],
                             scope["worktree_fingerprints_before"], _fingerprints(root, scope["worktree_after"]))
    entries = brief.scope_entries(task)
    scope["changed_files"] = changed
    scope["out_of_scope"] = [path for path in changed if not brief.in_scope(path, entries, root) or (
        meta["write_scope"] == "tests" and not any(glob_match(path, pattern) for pattern in settings.get("test_paths", [])))]
    scope["scope_ok"] = not scope["out_of_scope"] and not (
        root != Path(meta["repo"]) and scope["main_changes"])
    _write_json(rd / "scope.json", scope)
    ended = _now()
    status = {"status": "FAILED" if error or exit_code else report["status"], "error": error,
              "exit_code": exit_code, "ended": ended}
    minutes = (datetime.fromisoformat(ended) - datetime.fromisoformat(meta["started"])).total_seconds() / 60
    tokens = runlog.tokens_from_codex_events((rd / "events.jsonl").read_text()) if (rd / "events.jsonl").exists() else None
    runlog.record_run(id=run_id, agent=meta["agent"], jd_version=meta["version"], app="codex",
                      model=meta["model"], effort=meta["effort"], tier=meta["tier"], repo=meta["repo"],
                      worktree=meta["worktree"], branch=meta["branch"], started=meta["started"], ended=ended,
                      minutes=minutes, status=status["status"], error=error, locks=_run_locks(meta, task),
                      tokens=tokens, report=str(rd / "report.json") if valid else None,
                      scope_ok=scope["scope_ok"], manager=meta["manager"])
    _write_json(rd / "status.json", status)
    return status


def list_running() -> list[dict]:
    result = []
    for file in sorted((paths.state_home() / "runs").glob("*/status.json")):
        if _read_json(file).get("status") != "running":
            continue
        meta = _read_json(file.parent / "meta.json")
        alive = subprocess.run(_tmux("has-session", "-t", "=" + file.parent.name), capture_output=True).returncode == 0
        result.append({"id": file.parent.name, "agent": meta["agent"], "started": meta["started"], "alive": alive})
    return result


def show_log(run_id: str, tail: int) -> str:
    path = runlog.run_dir(run_id) / "events.jsonl"
    if not path.exists() or tail <= 0:
        return ""
    result = []
    for line in path.read_text().splitlines()[-tail:]:
        try:
            event = json.loads(line)
            item = event.get("item") or {}
            detail = item.get("text") or item.get("command")
            result.append(f"{event.get('type', '')} {detail if detail is not None else line}")
        except (ValueError, AttributeError):
            result.append(line)
    return "\n".join(result)


def wait(run_id: str, timeout_min: float) -> dict:
    file = runlog.run_dir(run_id) / "status.json"
    deadline = time.monotonic() + timeout_min * 60
    while True:
        status = _read_json(file)
        if status["status"] != "running" or time.monotonic() >= deadline:
            return status
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("run-codex", help="launch a Codex agent, list running agents, or read events")
    parser.add_argument("agent", nargs="?")
    parser.add_argument("brief", nargs="?", type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true")
    action.add_argument("--log", metavar="ID")
    parser.add_argument("--tail", type=int, default=40)
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--worktree", type=Path)
    location.add_argument("--new-worktree")
    parser.add_argument("--base")
    parser.add_argument("--tier")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--repo", type=Path)
    parser.set_defaults(func=_launch)
    internal = sub.add_parser("_run", help=argparse.SUPPRESS)
    internal.add_argument("run_id")
    internal.set_defaults(func=_execute)


def _execute(args):
    try:
        return execute(args.run_id)
    except (ConfigError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL


def _launch(args):
    try:
        if args.list:
            for run in list_running():
                print(f"{run['id']} {run['agent']} {run['started']} alive={str(run['alive']).lower()}")
            return EXIT_OK
        if args.log:
            print(show_log(args.log, args.tail))
            return EXIT_OK
        if not args.agent or args.brief is None:
            raise LaunchError("run-codex needs AGENT and BRIEF, --list, or --log ID")
        repo = args.repo or paths.repo_root(Path.cwd())
        if repo is None:
            raise LaunchError("run-codex needs --repo outside a git repository")
        overrides = {key: getattr(args, key) for key in ("tier", "model", "effort") if getattr(args, key) is not None}
        run_id = prepare_run(args.agent, args.brief, repo, worktree=args.worktree,
                             new_worktree=args.new_worktree, base=args.base, overrides=overrides)
        start(run_id, detach=True)
        if args.wait:
            while True:
                status = wait(run_id, 1)
                if status["status"] != "running":
                    break
            print(f"{run_id} {status['status']} {runlog.run_dir(run_id) / 'report.json'}")
            return EXIT_OK if status["status"] == "DONE" else EXIT_FAIL
        print(run_id, flush=True)
        return EXIT_OK
    except LaunchError as error:
        print(str(error), file=sys.stderr)
        return error.code
    except (ConfigError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL

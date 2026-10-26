"""Run a repository's gate under locks and classify failures read-only."""

import argparse
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from consortium import brief, launcher, locks, paths, registry, runlog, schemas
from consortium.cli import EXIT_FAIL, EXIT_OK
from consortium.config import ConfigError, load_settings


AFTER_TIMEOUT_SECONDS = 10 * 60


def resolve_gate_command(repo: Path, settings) -> str:
    command = settings.get("gate.command")
    if command != "auto":
        return command
    makefile = repo / "Makefile"
    if makefile.is_file() and any(
        "test" in match[1].split()
        for match in re.finditer(r"^([^\s#:=][^:=\n]*):(?!=)", makefile.read_text(), re.MULTILINE)
    ):
        return "make test"
    package = repo / "package.json"
    if package.is_file() and "test" in json.loads(package.read_text()).get("scripts", {}):
        return "npm test"
    return "pytest"


def run_gate(repo: Path, *, worktree: Path | None, commit: str | None, detach: bool) -> str:
    repo = Path(repo).expanduser().resolve()
    cwd = Path(worktree).expanduser().resolve() if worktree is not None else repo
    head = launcher._git(cwd, "rev-parse", "HEAD").strip()
    dirty = bool(launcher._status(cwd))
    if commit is not None and (head != commit or dirty):
        raise launcher.LaunchError(
            f"--commit {commit} requires HEAD {commit} and a clean worktree; "
            f"HEAD is {head}, worktree is {'dirty' if dirty else 'clean'}")
    settings = load_settings(repo)
    command = resolve_gate_command(cwd, settings)
    if not isinstance(command, str) or not command.strip():
        raise ConfigError("gate.command: expected one shell command, or auto")
    timeout = settings.get("gate.timeout_minutes")
    if type(timeout) is not int or timeout <= 0:
        raise ConfigError("gate.timeout_minutes: expected a positive integer")
    names = sorted(set(settings.get("gate.locks", [])) | (
        {"disk"} if settings.get("locks.disk_floor_gb") > 0 else set()))
    run_id = runlog.new_run_id("ci-gate")
    manager = "codex" if os.environ.get("CODEX_THREAD_ID") else "claude" if os.environ.get("CLAUDECODE") else None
    meta = {"run_id": run_id, "agent": "ci-gate", "repo": str(paths.main_checkout(repo)),
            "worktree": str(cwd), "branch": launcher._branch(cwd),
            "commit": head + ("+dirty" if dirty else ""), "command": command, "timeout_minutes": timeout,
            "locks": names, "started": launcher._now(), "manager": manager,
            "version": registry.load_registry(repo)["ci-gate"].meta["version"]}
    rd = runlog.run_dir(run_id)
    launcher._write_json(rd / "meta.json", meta)
    launcher._write_json(rd / "status.json", {"status": "running"})
    if not detach or os.environ.get("CONSORTIUM_NO_TMUX") == "1":
        execute(run_id)
    else:
        env = dict(os.environ)
        command = launcher._tmux("new-session", "-d", "-s", run_id, "-c", str(cwd))
        command.extend(launcher._session_env_args(launcher._server_environment(), env))
        command.extend(["--", str(paths.package_root() / "bin/consortium"), "_gate", run_id])
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        if result.returncode:
            (rd / "stderr.log").write_text(result.stderr)
            _finish(meta, result.returncode, "infra", None, "tmux", 0, [], [])
            raise launcher.LaunchError(result.stderr.strip() or "tmux could not start the gate")
    return run_id


@contextmanager
def _held_environment(names):
    previous = os.environ.get("CONSORTIUM_LOCKS_HELD")
    inherited = set(filter(None, (previous or "").split(",")))
    os.environ["CONSORTIUM_LOCKS_HELD"] = ",".join(sorted(inherited | set(names)))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("CONSORTIUM_LOCKS_HELD", None)
        else:
            os.environ["CONSORTIUM_LOCKS_HELD"] = previous


@contextmanager
def _stop_signals():
    stopped, previous = [], {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, lambda sig, frame: stopped.append(sig))
        yield stopped
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _wait_step(child, deadline, stopped, seen):
    while True:
        if len(stopped) > seen:
            launcher._stop_process(child, stopped[seen])
            return 128 + stopped[seen]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            launcher._stop_process(child)
            raise subprocess.TimeoutExpired(child.args, 0)
        try:
            code = child.wait(timeout=min(0.1, remaining))
            if len(stopped) == seen:
                return 128 - code if code < 0 else code
        except subprocess.TimeoutExpired:
            pass


def _shell(command, cwd, output, deadline, stopped, *, cleanup=False):
    if stopped and not cleanup:
        return 128 + stopped[0]
    seen = len(stopped)
    if time.monotonic() >= deadline:
        raise subprocess.TimeoutExpired(command, 0)
    try:
        child = subprocess.Popen(["bash", "-o", "pipefail", "-c", command], cwd=cwd,
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        return _wait_step(child, deadline, stopped, seen)
    except OSError as error:
        print(str(error), file=output, flush=True)
        return 1


def _attempt(meta, settings, rd, cleanup, stopped):
    deadline = time.monotonic() + meta["timeout_minutes"] * 60
    code, failed_step, timed_out = 0, None, False
    with (rd / "gate.log").open("w") as output, (rd / "steps.log").open("a") as steps:
        try:
            for command in settings.get("gate.before", []):
                print(f"==> before: {command}", file=steps, flush=True)
                failed_step = "before: " + command
                code = _shell(command, meta["worktree"], steps, deadline, stopped)
                if code:
                    break
            else:
                failed_step = "gate"
                code = _shell(meta["command"], meta["worktree"], output, deadline, stopped)
            if code == 0:
                failed_step = None
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
        finally:
            for command in settings.get("gate.after", []):
                print(f"==> after: {command}", file=steps, flush=True)
                seen = len(stopped)
                try:
                    cleanup_code = _shell(command, meta["worktree"], steps,
                                          time.monotonic() + AFTER_TIMEOUT_SECONDS, stopped, cleanup=True)
                except subprocess.TimeoutExpired:
                    cleanup_code = 124
                cleanup.append({"step": command, "exit_code": cleanup_code})
                if len(stopped) > seen:
                    failed_step = "after: " + command
    if stopped:
        code, timed_out = 128 + stopped[0], False
    return code, failed_step, timed_out


def _classifier_brief(meta, settings, rd, code, reruns, cleanup):
    # Log text is data, never brief text: the brief check scans all lines and paths.
    tail = rd / "gate-tail.log"
    with (rd / "gate.log").open(errors="replace") as stream:
        tail.write_text("".join(deque(stream, maxlen=400)))
    context = rd / "gate-context.log"
    launcher._write_json(context, {"commit": meta["commit"], "command": meta["command"],
                                  "exit_code": code, "failed_step": "gate", "reruns": reruns,
                                  "cleanup": cleanup, "log": str(rd / "gate.log")})
    scope = [tail, context]
    flakes = settings.get("gate.flakes_file")
    if flakes:
        scope.append((paths.repo_config_dir(Path(meta["repo"])).parent / flakes).resolve())
    text = ("---\nagent: ci-gate\nworktree: " + json.dumps(meta["worktree"]) + "\n---\n"
            "## Task\nClassify the recorded gate failure. Read the tail and runner metadata in Scope, "
            "and compare the configured flakes file when supplied. Do not execute any gate commands.\n\n"
            "## Scope\n" + "\n".join(f"- `{path}`" for path in scope) +
            "\n\n## Report\nReturn gate.v1 with quoted evidence and the failure classification. "
            "Copy the runner metadata faithfully.\n")
    task = brief.parse_brief(text)
    jobs = registry.load_registry(Path(meta["repo"]))
    run = registry.resolve_agent("ci-gate", settings, jobs, manager_app=meta["manager"])
    findings = brief.check_brief(task, jobs["ci-gate"], run.mode, Path(meta["repo"]), settings)
    if findings:
        raise launcher.LaunchError("\n".join(f"{finding.rule}: {finding.message}" for finding in findings))
    source = rd / "classifier-brief.md"
    source.write_text(text)
    return source, run


def claude_argv(run: registry.AgentRun, schema: dict) -> list[str]:
    return [os.environ.get("CONSORTIUM_CLAUDE", "claude"), "-p", "--agent", "consortium:ci-gate",
            "--model", run.model, "--effort", run.effort, "--json-schema", json.dumps(schema),
            "--output-format", "json"]


def _claude_classifier(meta, source, run, stopped):
    run_id = runlog.new_run_id("ci-gate")
    rd = runlog.run_dir(run_id)
    started = launcher._now()
    schema = schemas.load_schema("gate.v1")
    notes = registry._notes_block(run.notes)
    prompt = (notes + "\n\n" if notes else "") + source.read_text()
    classifier_meta = {**asdict(run), "run_id": run_id, "agent": "ci-gate", "repo": meta["repo"],
                       "worktree": meta["worktree"], "branch": meta["branch"],
                       "started": started, "manager": meta["manager"]}
    launcher._write_json(rd / "meta.json", classifier_meta)
    launcher._write_json(rd / "status.json", {"status": "running"})
    launcher._write_json(rd / "schema.json", schema)
    (rd / "brief.md").write_text(source.read_text())
    (rd / "prompt.md").write_text(prompt)
    result, data, code, error = None, {}, 1, None
    with (rd / "stderr.log").open("w") as errors:
        try:
            with (rd / "prompt.md").open() as stdin, (rd / "claude-output.json").open("w") as output:
                child = subprocess.Popen(claude_argv(run, schema), cwd=meta["worktree"], stdin=stdin,
                                         stdout=output, stderr=errors, start_new_session=True)
                code = _wait_step(child, time.monotonic() + run.timeout_minutes * 60, stopped, 0)
            data = json.loads((rd / "claude-output.json").read_text())
            if not isinstance(data, dict):
                data = {}
            structured = data.get("structured_output")
            if (code == 0 and not data.get("is_error") and isinstance(structured, dict)
                    and not schemas.validate(structured, schema) and structured["status"] == "DONE"):
                result = structured
        except subprocess.TimeoutExpired:
            code, error = 124, "timeout"
        except (OSError, ValueError) as failure:
            print(str(failure), file=errors)
    error = error or (None if result is not None else "malformed_report")
    if result is not None:
        launcher._write_json(rd / "report.json", result)
    usage = data.get("usage")
    tokens = None if not isinstance(usage, dict) else {
        "input": sum(usage.get(key) or 0 for key in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        "cached_input": usage.get("cache_read_input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
    }
    ended = launcher._now()
    status = "DONE" if result is not None else "FAILED"
    runlog.record_run(id=run_id, agent="ci-gate", jd_version=run.version, app="claude", model=run.model,
                      effort=run.effort, tier=run.tier, repo=meta["repo"], worktree=meta["worktree"],
                      branch=meta["branch"], started=started, ended=ended, minutes=_minutes(started, ended),
                      status=status, error=error, locks=list(run.locks), tokens=tokens,
                      report=str(rd / "report.json") if result is not None else None,
                      scope_ok=None, manager=meta["manager"])
    launcher._write_json(rd / "status.json", {"status": status, "error": error, "exit_code": code, "ended": ended})
    return result


def _classify(meta, settings, rd, code, reruns, cleanup, stopped):
    try:
        source, run = _classifier_brief(meta, settings, rd, code, reruns, cleanup)
        if stopped:
            return None
        if run.app == "claude":
            return _claude_classifier(meta, source, run, stopped)
        classifier_id = launcher.prepare_run("ci-gate", source, Path(meta["repo"]), worktree=Path(meta["worktree"]))
        launcher.execute(classifier_id, stopped=stopped)
        status = launcher.wait(classifier_id, 0)
        if status["status"] == "DONE":
            report = launcher._read_json(runlog.run_dir(classifier_id) / "report.json")
            if not schemas.validate(report, schemas.load_schema("gate.v1")):
                return report
    except (launcher.LaunchError, ConfigError, OSError, ValueError, subprocess.CalledProcessError) as error:
        with (rd / "classifier-errors.log").open("a") as output:
            print(str(error), file=output)
    return None


def _minutes(started, ended):
    return (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() / 60


def _finish(meta, code, failure_class, flake, failed_step, reruns, cleanup, evidence):
    rd = runlog.run_dir(meta["run_id"])
    status = "DONE" if code == 0 else "FAILED"
    error = None if code == 0 else failure_class or "unclassified"
    summary = (f"Gate stopped at its {meta['timeout_minutes']}-minute limit." if failure_class == "timeout" else
               f"Gate {'passed' if code == 0 else 'failed'} with exit {code}; reruns: {reruns}.")
    value = {"schema": "gate.v1", "status": status, "summary": summary,
             "payload": {"commit": meta["commit"], "command": meta["command"], "exit_code": code,
                         "failed_step": failed_step, "failure_class": failure_class, "flake": flake,
                         "reruns": reruns, "cleanup": cleanup, "log": str(rd / "gate.log")},
             "decisions": [], "evidence": evidence, "changes": [],
             "checks": [{"command": meta["command"], "exit_code": code}], "questions": []}
    findings = schemas.validate(value, schemas.load_schema("gate.v1"))
    if findings:
        raise ValueError("\n".join(findings))
    launcher._write_json(rd / "report.json", value)
    ended = launcher._now()
    runlog.record_run(id=meta["run_id"], agent="ci-gate", jd_version=meta["version"],
                      app=None, model=None, effort=None, tier=None, repo=meta["repo"], worktree=meta["worktree"],
                      branch=meta["branch"], started=meta["started"], ended=ended,
                      minutes=_minutes(meta["started"], ended), status=status, error=error, locks=meta["locks"],
                      tokens=None, report=str(rd / "report.json"), scope_ok=None, manager=meta["manager"])
    launcher._write_json(rd / "status.json", {"status": status, "error": error, "exit_code": code, "ended": ended})


def execute(run_id: str) -> int:
    # tmux cannot unset server variables with -e NAME; the launcher sends this list instead.
    for name in set(filter(None, os.environ.pop("CONSORTIUM_UNSET", "").split(","))):
        os.environ.pop(name, None)
    rd = runlog.run_dir(run_id)
    meta = launcher._read_json(rd / "meta.json")
    current = launcher._read_json(rd / "status.json")
    if current["status"] != "running":
        return current["exit_code"]
    with _stop_signals() as stopped:
        return _execute(meta, rd, stopped)


def _execute(meta, rd, stopped):
    run_id = meta["run_id"]
    code, failure_class, flake, failed_step, reruns = 1, None, None, None, 0
    cleanup, evidence = [], []
    owner = {"pid": os.getpid(), "command": f"consortium _gate {run_id}", "cwd": meta["worktree"],
             "run_id": run_id, "started": meta["started"]}
    try:
        settings = load_settings(Path(meta["repo"]))
        with locks.hold(meta["locks"], settings.get("locks.wait_seconds"), owner):
            if "disk" in meta["locks"]:
                locks._check_disk(Path(meta["repo"]), settings)
            with _held_environment(meta["locks"]):
                while True:
                    code, failed_step, timed_out = _attempt(meta, settings, rd, cleanup, stopped)
                    if stopped or timed_out:
                        failure_class, flake = "timeout" if timed_out else None, None
                        break
                    if failed_step and failed_step.startswith("before: "):
                        failure_class, flake = "infra", None
                        break
                    if code == 0:
                        break
                    classified = _classify(meta, settings, rd, code, reruns, cleanup, stopped)
                    if stopped:
                        break
                    payload = classified["payload"] if classified else {}
                    failure_class, flake = payload.get("failure_class"), payload.get("flake")
                    failed_step = payload.get("failed_step") or "gate"
                    evidence.extend(classified["evidence"] if classified else [])
                    if failure_class != "known_flake" or reruns:
                        break
                    (rd / "gate.log").replace(rd / "gate-attempt-1.log")
                    reruns = 1
    except Exception as error:  # A gate must end with a status, whatever went wrong.
        with (rd / "stderr.log").open("a") as output:
            print(f"{type(error).__name__}: {error}", file=output)
        code, failure_class, flake, failed_step = code or 1, "infra", None, "runner"
    if stopped:
        code, failure_class, flake = 128 + stopped[0], None, None
    try:
        _finish(meta, code, failure_class, flake, failed_step, reruns, cleanup, evidence)
    except Exception as error:  # Never leave status.json at "running": `gate --wait` would never return.
        with (rd / "stderr.log").open("a") as output:
            print(f"could not write the gate report: {type(error).__name__}: {error}", file=output)
        launcher._write_json(rd / "status.json", {"status": "FAILED", "error": "runner", "exit_code": code or 1,
                                                  "ended": launcher._now()})
        return code or 1
    return code


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("gate", help="run the repository gate and classify failures")
    parser.add_argument("--worktree", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--repo", type=Path)
    parser.set_defaults(func=_gate)
    internal = sub.add_parser("_gate", help=argparse.SUPPRESS)
    internal.add_argument("run_id")
    internal.set_defaults(func=lambda args: execute(args.run_id))


def _gate(args):
    try:
        repo = args.repo or paths.repo_root(Path.cwd())
        if repo is None:
            raise launcher.LaunchError("gate needs --repo outside a git repository")
        run_id = run_gate(repo, worktree=args.worktree, commit=args.commit, detach=True)
        if args.wait:
            while True:
                status = launcher.wait(run_id, 1)
                if status["status"] != "running":
                    break
            print(f"{run_id} {status['status']} {runlog.run_dir(run_id) / 'report.json'}")
            return EXIT_OK if status["status"] == "DONE" else EXIT_FAIL
        print(run_id, flush=True)
        return EXIT_OK
    except (launcher.LaunchError, ConfigError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL

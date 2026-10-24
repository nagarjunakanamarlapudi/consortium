import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

import pytest
import yaml

from consortium import brief, launcher, locks, paths, runlog
from consortium.config import load_settings
from consortium.registry import load_registry, resolve_agent
from consortium.schemas import load_schema, validate
from test_cli import git


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
BIN = ROOT / "plugins/consortium/bin/consortium"


def classification(failure_class="real", *, failed_step="test_example", flake=None):
    return {
        "schema": "gate.v1", "status": "DONE", "summary": "Classified failure.",
        "decisions": [], "changes": [], "checks": [], "questions": [],
        "evidence": [{"claim": "FAILED test_example", "kind": "log", "ref": "gate-tail.log",
                      "result": "FAILED test_example: assertion failed"}],
        "payload": {"commit": "classifier-must-not-own-this", "command": "not the command",
                    "exit_code": 999, "failed_step": failed_step, "failure_class": failure_class,
                    "flake": flake, "reruns": 99, "cleanup": [], "log": "not the log"},
    }


@pytest.fixture
def gate_case(tmp_path, monkeypatch):
    repo = tmp_path / "gate repo"
    subprocess.run(["git", "clone", "--quiet", "--shared", str(ROOT), str(repo)], check=True)
    (repo / ".consortium").mkdir()
    with (repo / ".git/info/exclude").open("a") as stream:
        stream.write("\n.consortium/\n")
    monkeypatch.setenv("CONSORTIUM_CODEX", str(FIXTURES / "fake_codex.py"))
    monkeypatch.setattr(launcher, "CODEX_BIN", str(FIXTURES / "fake_codex.py"))
    monkeypatch.setenv("CONSORTIUM_CLAUDE", str(FIXTURES / "fake_claude.py"))
    monkeypatch.setenv("CONSORTIUM_NO_TMUX", "1")
    monkeypatch.setenv("CODEX_THREAD_ID", "gate-manager")
    monkeypatch.delenv("CONSORTIUM_UNSET", raising=False)
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(tmp_path / "codex.json"))
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(classification()))
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(tmp_path / "claude.json"))
    monkeypatch.setenv("FAKE_CLAUDE_RESULT", json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "result": "", "structured_output": classification(),
        "usage": {"input_tokens": 7, "cache_creation_input_tokens": 11,
                  "cache_read_input_tokens": 13, "output_tokens": 17},
    }))
    configure(repo)
    return repo


def configure(repo, command="printf 'green\\n'", *, before=(), after=(), names=(), floor=0, flakes=None, app="codex"):
    (repo / ".consortium/config.yaml").write_text(yaml.safe_dump({
        "app": app, "gate": {"command": command, "before": list(before), "after": list(after),
                              "locks": list(names), "flakes_file": flakes},
        "locks": {"disk_floor_gb": floor, "wait_seconds": 0.2},
        "agents": {"ci-gate": {"notes": ["Classify only the supplied artifacts."]}},
    }))


def invoke(run_cli, repo, *args, env=None):
    return run_cli("gate", "--repo", str(repo), "--wait", *args, env=env)


def gate_folder():
    return next(path.parent for path in (paths.state_home() / "runs").glob("*/meta.json")
                if "command" in json.loads(path.read_text()))


def report():
    rd = gate_folder()
    value = json.loads((rd / "report.json").read_text())
    assert validate(value, load_schema("gate.v1")) == []
    return value


def test_green_gate_reports_exit_0_and_cleans_up(run_cli, gate_case):
    configure(gate_case, before=["echo prepared"], after=["echo cleanup; exit 7", "echo finished"])
    result = invoke(run_cli, gate_case)
    assert result.returncode == 0, result.stderr
    rd = gate_folder()
    assert result.stdout.strip() == f"{rd.name} DONE {rd / 'report.json'}"
    value = report()
    assert value["status"] == "DONE"
    assert value["checks"] == [{"command": "printf 'green\\n'", "exit_code": 0}]
    assert value["payload"] == {
        "commit": git(gate_case, "rev-parse", "HEAD"), "command": "printf 'green\\n'", "exit_code": 0,
        "failed_step": None, "failure_class": None, "flake": None, "reruns": 0,
        "cleanup": [{"step": "echo cleanup; exit 7", "exit_code": 7},
                    {"step": "echo finished", "exit_code": 0}], "log": str(rd / "gate.log"),
    }
    assert (rd / "gate.log").read_text() == "green\n"
    assert (rd / "steps.log").read_text() == (
        "==> before: echo prepared\nprepared\n==> after: echo cleanup; exit 7\ncleanup\n"
        "==> after: echo finished\nfinished\n")
    status = json.loads((rd / "status.json").read_text())
    assert status["status"] == "DONE" and status["error"] is None and status["exit_code"] == 0
    assert set(status) == {"status", "error", "exit_code", "ended"}
    record, = runlog.read_records()
    assert record["id"] == rd.name and record["agent"] == "ci-gate" and record["jd_version"] == 1
    assert all(record[key] is None for key in ("app", "model", "effort", "tier", "tokens", "scope_ok"))
    assert record["repo"] == str(gate_case) and record["report"] == str(rd / "report.json")
    assert record["status"] == "DONE" and record["error"] is None
    assert record["manager"] == "codex"
    assert not (gate_case.parent / "codex.json").exists()
    waited = run_cli("runs", "--wait", rd.name, "--timeout", "0")
    assert waited.returncode == 0 and json.loads(waited.stdout)["id"] == rd.name
    assert launcher.list_running() == []


def test_after_steps_run_even_when_the_gate_fails(run_cli, gate_case):
    configure(gate_case, "echo 'FAILED test_example' >&2; exit 3", after=["echo cleaned > .consortium/cleaned"])
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1, result.stderr
    assert (gate_case / ".consortium/cleaned").read_text() == "cleaned\n"
    value = report()
    assert value["payload"]["exit_code"] == 3
    assert value["payload"]["cleanup"][0]["exit_code"] == 0
    assert value["payload"]["failed_step"] == "test_example"
    assert value["payload"]["failure_class"] == "real"
    assert value["evidence"] == classification()["evidence"]
    assert "FAILED test_example" in (gate_folder() / "gate.log").read_text()


def test_pipefail_exit_code_is_the_gates_not_tees(run_cli, gate_case):
    configure(gate_case, "false | cat")
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    assert report()["payload"]["exit_code"] == 1


def test_known_flake_reruns_once(run_cli, gate_case, monkeypatch):
    configure(gate_case, "if [ -e .consortium/attempt ]; then echo green; else touch .consortium/attempt; echo flake; exit 1; fi",
              before=["echo before >> .consortium/order"], after=["echo after >> .consortium/order"])
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(classification("known_flake", flake="clock race")))
    result = invoke(run_cli, gate_case)
    assert result.returncode == 0, result.stderr
    value = report()
    assert (value["status"], value["payload"]["exit_code"], value["payload"]["reruns"]) == ("DONE", 0, 1)
    assert len(value["payload"]["cleanup"]) == 2
    assert (gate_case / ".consortium/order").read_text() == "before\nafter\nbefore\nafter\n"
    assert (gate_folder() / "gate-attempt-1.log").read_text() == "flake\n"
    assert (gate_folder() / "gate.log").read_text() == "green\n"
    assert len(runlog.read_records()) == 2


def test_a_second_failure_is_classified_but_never_rerun(run_cli, gate_case, monkeypatch):
    configure(gate_case, "echo failing >> .consortium/attempts; exit 1", after=["true"])
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(classification("known_flake", flake="clock race")))
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    value = report()
    assert (value["payload"]["failure_class"], value["payload"]["reruns"]) == ("known_flake", 1)
    assert len(value["payload"]["cleanup"]) == 2
    assert (gate_case / ".consortium/attempts").read_text() == "failing\nfailing\n"
    records = runlog.read_records()
    assert len(records) == 3 and sum(row["tier"] == "cheap" for row in records) == 2
    assert records[-1]["error"] == "known_flake"
    assert report()["payload"]["exit_code"] == 1


def test_real_failure_is_not_rerun(run_cli, gate_case):
    configure(gate_case, "echo failing >> .consortium/attempts; exit 1")
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    assert report()["payload"]["reruns"] == 0
    assert (gate_case / ".consortium/attempts").read_text() == "failing\n"
    records = runlog.read_records()
    assert len(records) == 2
    assert (records[0]["app"], records[0]["model"], records[0]["effort"], records[0]["tier"]) == (
        "codex", "gpt-6-luna", "low", "cheap")
    captured = json.loads((gate_case.parent / "codex.json").read_text())
    argv = captured["argv"]
    assert argv[argv.index("-s") + 1] == "read-only"
    assert argv[argv.index("-C") + 1] == str(gate_case)


@pytest.mark.parametrize("dirty,mismatch", [(False, True), (True, False), (True, True)])
def test_commit_mismatch_or_dirty_worktree_is_refused(run_cli, gate_case, dirty, mismatch):
    sha = git(gate_case, "rev-parse", "HEAD")
    if dirty:
        (gate_case / "dirty.txt").write_text("dirty\n")
    requested = "0" * 40 if mismatch else sha
    result = invoke(run_cli, gate_case, "--commit", requested)
    assert result.returncode == 1
    assert requested in result.stderr and sha in result.stderr
    assert "clean" in result.stderr and "HEAD" in result.stderr
    assert not (paths.state_home() / "runs").exists()
    assert not (gate_case.parent / "codex.json").exists()


def test_matching_commit_is_recorded(run_cli, gate_case):
    sha = git(gate_case, "rev-parse", "HEAD")
    result = invoke(run_cli, gate_case, "--commit", sha)
    assert result.returncode == 0, result.stderr
    assert report()["payload"]["commit"] == sha


def test_dirty_worktree_without_commit_reports_dirty_sha(run_cli, gate_case):
    (gate_case / "dirty.txt").write_text("dirty\n")
    result = invoke(run_cli, gate_case)
    assert result.returncode == 0, result.stderr
    assert report()["payload"]["commit"] == git(gate_case, "rev-parse", "HEAD") + "+dirty"


def test_before_failure_is_infra_and_cleans_up_without_classifier(run_cli, gate_case):
    configure(gate_case, "touch .consortium/gate-started", before=["echo setup; exit 6", "touch .consortium/later"],
              after=["echo cleanup; exit 2", "touch .consortium/cleaned"])
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    value = report()
    assert (value["payload"]["failure_class"], value["payload"]["failed_step"], value["payload"]["exit_code"]) == (
        "infra", "before: echo setup; exit 6", 6)
    assert value["payload"]["cleanup"] == [{"step": "echo cleanup; exit 2", "exit_code": 2},
                                             {"step": "touch .consortium/cleaned", "exit_code": 0}]
    assert not (gate_case / ".consortium/gate-started").exists()
    assert not (gate_case / ".consortium/later").exists()
    assert (gate_case / ".consortium/cleaned").exists()
    assert not (gate_case.parent / "codex.json").exists()
    assert len(runlog.read_records()) == 1


@pytest.mark.parametrize("mode", ["malformed", "quota"])
def test_failed_classifier_leaves_unclassified_failure(run_cli, gate_case, mode):
    configure(gate_case, "exit 9")
    result = invoke(run_cli, gate_case, env={"FAKE_CODEX_MODE": mode})
    assert result.returncode == 1
    value = report()
    assert value["payload"]["failure_class"] is None
    assert value["payload"]["failed_step"] == "gate"
    assert value["payload"]["exit_code"] == 9
    assert runlog.read_records()[-1]["error"] == "unclassified"


def test_classifier_brief_references_a_tail_without_log_text(run_cli, gate_case):
    # This line would fail both no-exact-count-stop and paths-exist if pasted into the brief.
    configure(gate_case, "for i in {1..410}; do echo \"line $i\"; done; echo '42 stop `/missing/log-only.py`'; exit 1",
              flakes="flakes.md")
    (gate_case / "flakes.md").write_text("- harmless known entry\n")
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    rd = gate_folder()
    task = brief.parse_brief((rd / "classifier-brief.md").read_text())
    settings = load_settings(gate_case, task.front)
    jobs = load_registry(gate_case)
    assert brief.check_brief(task, jobs["ci-gate"], "read-only", gate_case, settings) == []
    assert str(rd / "gate-tail.log") in brief.scope_entries(task)
    assert str(gate_case / "flakes.md") in brief.scope_entries(task)
    assert "42 stop" not in task.text and "/missing/log-only.py" not in task.text
    tail = (rd / "gate-tail.log").read_text().splitlines()
    assert len(tail) == 400 and tail[0] == "line 12" and tail[-1] == "42 stop `/missing/log-only.py`"
    assert (gate_case.parent / "codex.json").exists()


def test_flakes_resolve_at_the_main_checkout_with_symlinked_config(run_cli, gate_case, tmp_path):
    owner = tmp_path / "config owner"
    owner.mkdir()
    shutil.move(str(gate_case / ".consortium"), owner / ".consortium")
    (gate_case / ".consortium").symlink_to(owner / ".consortium", target_is_directory=True)
    configure(gate_case, "exit 1", flakes="flakes.md")
    (owner / "flakes.md").write_text("- documented flake\n")
    worktree = tmp_path / "linked"
    git(gate_case, "worktree", "add", "--quiet", str(worktree))
    result = invoke(run_cli, gate_case, "--worktree", str(worktree))
    assert result.returncode == 1
    task = brief.parse_brief((gate_folder() / "classifier-brief.md").read_text())
    assert str(owner / "flakes.md") in brief.scope_entries(task)
    captured = json.loads((gate_case.parent / "codex.json").read_text())
    argv = captured["argv"]
    assert argv[argv.index("-C") + 1] == str(worktree)


def test_gate_holds_locks_through_steps_classifier_and_rerun(run_cli, gate_case, monkeypatch):
    monkeypatch.delenv("CONSORTIUM_LOCKS_HELD", raising=False)
    command = f'{shlex.quote(str(BIN))} lock test-stack --wait 0 -- sh -c \'echo "$CONSORTIUM_LOCKS_HELD"\''
    configure(gate_case, command + "; exit 1", before=[command], after=[command], names=["test-stack"], floor=0.001)
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(classification("known_flake")))
    from consortium import gate
    real_hold = locks.hold
    observations = []

    def observing_execute(run_id):
        held = locks.list_locks()
        observations.append({entry["name"] for entry in held})
        assert all(entry["run_id"] == gate_folder().name for entry in held)
        return real_execute(run_id)

    real_execute = launcher.execute
    monkeypatch.setattr(launcher, "execute", observing_execute)
    run_id = gate.run_gate(gate_case, worktree=None, commit=None, detach=False)
    assert observations == [{"test-stack", "disk"}, {"test-stack", "disk"}]
    assert locks.list_locks() == []
    rd = paths.state_home() / "runs" / run_id
    assert (rd / "gate.log").read_text() == "disk,test-stack\n"
    assert (rd / "steps.log").read_text().count("\ndisk,test-stack\n") == 4
    assert runlog.read_records()[-1]["locks"] == ["disk", "test-stack"]


def test_another_holder_prevents_the_gate_from_starting(run_cli, gate_case):
    configure(gate_case, "touch .consortium/started", names=["test-stack"])
    path = locks.lock_path("test-stack")
    path.parent.mkdir(parents=True)
    with path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    assert not (gate_case / ".consortium/started").exists()
    assert runlog.read_records()[-1]["error"] == "infra"


@pytest.mark.parametrize("makefile,package,expected", [
    (".PHONY: test\ntest:\n\ttrue\n", {"scripts": {"test": "true"}}, "make test"),
    ("# test:\nlatest:\n\ttrue\n", {"scripts": {"test": "true"}}, "npm test"),
    (None, {"scripts": {"build": "true"}}, "pytest"),
    (None, None, "pytest"),
])
def test_auto_gate_command(tmp_path, makefile, package, expected):
    from consortium.gate import resolve_gate_command
    if makefile is not None:
        (tmp_path / "Makefile").write_text(makefile)
    if package is not None:
        (tmp_path / "package.json").write_text(json.dumps(package))
    assert resolve_gate_command(tmp_path, load_settings(None)) == expected


def test_auto_command_uses_the_worktree_and_default_repo_is_the_current_checkout(run_cli, gate_case, tmp_path):
    configure(gate_case, "auto")
    worktree = tmp_path / "selected"
    git(gate_case, "worktree", "add", "--quiet", str(worktree))
    (worktree / "Makefile").write_text("test:\n\t@echo selected-worktree\n")
    nested = worktree / "tests"
    result = run_cli("gate", "--wait", cwd=nested)
    assert result.returncode == 0, result.stderr
    value = report()
    assert value["payload"]["command"] == "make test"
    rd = gate_folder()
    meta = json.loads((rd / "meta.json").read_text())
    assert meta["repo"] == str(gate_case) and meta["worktree"] == str(worktree)
    assert (rd / "gate.log").read_text() == "selected-worktree\n"


def test_claude_argv_and_structured_output(run_cli, gate_case):
    from consortium.gate import claude_argv
    configure(gate_case, "exit 4", app="claude")
    resolved = resolve_agent("ci-gate", load_settings(gate_case), load_registry(gate_case), manager_app="codex")
    schema = load_schema("gate.v1")
    argv = claude_argv(resolved, schema)
    assert argv == [str(FIXTURES / "fake_claude.py"), "-p", "--agent", "consortium:ci-gate",
                    "--model", "haiku", "--effort", "low", "--json-schema", json.dumps(schema),
                    "--output-format", "json"]
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1, result.stderr
    value = report()
    assert value["payload"]["failure_class"] == "real" and value["payload"]["exit_code"] == 4
    assert value["evidence"] == classification()["evidence"]
    captured = json.loads((gate_case.parent / "claude.json").read_text())
    assert captured["argv"] == argv[1:]
    assert captured["stdin"].startswith("## Notes from this repo\n- Classify only the supplied artifacts.\n\n")
    assert (gate_folder() / "classifier-brief.md").read_text() in captured["stdin"]
    records = runlog.read_records()
    assert len(records) == 2
    row = records[0]
    assert (row["agent"], row["app"], row["model"], row["effort"], row["tier"]) == (
        "ci-gate", "claude", "haiku", "low", "cheap")
    assert row["tokens"] == {"input": 31, "cached_input": 13, "output": 17}
    assert not (gate_case.parent / "codex.json").exists()


@pytest.mark.parametrize("result,exit_code", [
    ({"is_error": False, "structured_output": {"schema": "gate.v1"}}, 0),
    ({"is_error": False, "result": json.dumps(classification())}, 0),
    ({"is_error": True, "structured_output": classification()}, 0),
    ({"is_error": False, "structured_output": classification()}, 1),
    ("malformed", 0),
])
def test_invalid_or_failed_claude_results_are_not_classifications(run_cli, gate_case, monkeypatch, result, exit_code):
    configure(gate_case, "exit 1", app="claude")
    monkeypatch.setenv("FAKE_CLAUDE_RESULT", result if isinstance(result, str) else json.dumps(result))
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", str(exit_code))
    invoked = invoke(run_cli, gate_case)
    assert invoked.returncode == 1
    assert report()["payload"]["failure_class"] is None
    assert runlog.read_records()[-1]["error"] == "unclassified"
    assert len(runlog.read_records()) == 2


def test_detached_gate_preserves_environment_and_leaves_no_session(run_cli, gate_case, monkeypatch):
    socket = f"consortium-test-gate-{os.getpid()}-{time.time_ns()}"
    monkeypatch.setenv("CONSORTIUM_TMUX_SOCKET", socket)
    monkeypatch.delenv("CONSORTIUM_NO_TMUX")
    try:
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "new-session", "-d", "-s", "holder",
                        "--", "sleep", "60"], env=dict(os.environ, STALE_GATE_VALUE="old"), check=True)
        monkeypatch.setenv("CURRENT_GATE_VALUE", "from-caller")
        configure(gate_case, 'echo "$CURRENT_GATE_VALUE"; test -z "${STALE_GATE_VALUE+x}"; '
                            'test -z "${CONSORTIUM_UNSET+x}"')
        result = invoke(run_cli, gate_case)
        assert result.returncode == 0, result.stderr
        rd = gate_folder()
        assert (rd / "gate.log").read_text() == "from-caller\n"
        for _ in range(30):
            sessions = subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "ls"],
                                      capture_output=True, text=True)
            if rd.name not in sessions.stdout:
                break
            time.sleep(0.1)
        assert rd.name not in sessions.stdout
    finally:
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "kill-server"], capture_output=True)


def test_without_wait_prints_only_id_and_does_not_report_the_gates_failure(run_cli, gate_case):
    configure(gate_case, "exit 1")
    result = run_cli("gate", "--repo", str(gate_case))
    assert result.returncode == 0
    assert result.stdout.strip() == gate_folder().name
    assert report()["status"] == "FAILED"


def test_a_gate_command_that_is_not_one_string_is_refused_before_the_run(run_cli, gate_case):
    configure(gate_case, command=["bash", "scripts/test.sh"])
    result = invoke(run_cli, gate_case)
    assert result.returncode == 1
    assert "gate.command" in result.stderr
    assert not list((paths.state_home() / "runs").glob("*/meta.json"))


@pytest.mark.parametrize("broken", ["_attempt", "_finish"])
def test_an_unexpected_error_still_ends_the_run_with_a_status(gate_case, monkeypatch, broken):
    from consortium import gate

    def explode(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(gate, broken, explode)
    run_id = gate.run_gate(gate_case, worktree=None, commit=None, detach=False)
    status = json.loads((runlog.run_dir(run_id) / "status.json").read_text())
    assert status["status"] == "FAILED" and status["exit_code"] == 1
    assert status["error"] == ("infra" if broken == "_attempt" else "runner")
    assert "RuntimeError: unexpected" in (runlog.run_dir(run_id) / "stderr.log").read_text()

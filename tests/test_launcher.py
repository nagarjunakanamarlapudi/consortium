import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest
import yaml

from consortium import brief as briefs, launcher, paths
from consortium.config import load_settings
from consortium.registry import load_registry, parse_front_matter, resolve_agent
from consortium.schemas import load_schema, validate
from test_cli import add_worktree, git


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
SHIMS = ROOT / "plugins/consortium/lib/consortium/shims"
REPORT = {
    "schema": "locations.v1", "status": "DONE", "summary": "Read the sample.",
    "decisions": [], "evidence": [], "changes": [], "checks": [], "questions": [],
    "payload": {"searches": [], "too_common": []},
}


@pytest.fixture
def launch_case(tmp_path, monkeypatch):
    repo = tmp_path / "sample repo"
    shutil.copytree(ROOT / "plugins/consortium/evals/_fixtures/sample-repo", repo)
    git(repo, "init", "--quiet")
    agents = repo / ".consortium/agents"
    agents.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "scratch-searcher.md", agents / "scratch-searcher.md")
    source = tmp_path / "brief.md"
    source.write_text("## Task\nRead the sample.\n\n## Scope\n- `shop/`\n\n"
                      "## Report\nReturn locations.v1.\n")
    record = tmp_path / "fake.json"
    monkeypatch.setenv("CONSORTIUM_CODEX", str(FIXTURES / "fake_codex.py"))
    monkeypatch.setattr(launcher, "CODEX_BIN", str(FIXTURES / "fake_codex.py"))
    monkeypatch.setenv("CONSORTIUM_NO_TMUX", "1")
    socket = f"consortium-test-{os.getpid()}-{time.time_ns()}"
    monkeypatch.setenv("CONSORTIUM_TMUX_SOCKET", socket)
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(REPORT))
    try:
        yield repo, source, record
    finally:
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "kill-server"], capture_output=True)


def invoke(run_cli, case, *args, env=None):
    repo, source, _ = case
    return run_cli("run-codex", "scratch-searcher", str(source), "--repo", str(repo), "--wait", *args, env=env)


def folder(case):
    return next((paths.state_home() / "runs").iterdir())


def job_patch(case, **patch):
    path = case[0] / ".consortium/agents/scratch-searcher.md"
    front, body = parse_front_matter(path.read_text())
    front["consortium"].update(patch)
    path.write_text("---\n" + yaml.safe_dump(front) + "---\n" + body)


def prepared(case, **kwargs):
    return launcher.prepare_run("scratch-searcher", case[1], case[0], **kwargs)


def test_bad_brief_is_refused_before_codex_starts(run_cli, launch_case):
    launch_case[1].write_text("## Task\nRead.\n## Scope\n`tests/missing.py`\n## Report\nlocations.v1\n")
    result = invoke(run_cli, launch_case)
    assert result.returncode == 1
    assert "paths-exist:" in result.stdout + result.stderr
    assert not launch_case[2].exists()
    assert not (paths.state_home() / "runs").exists()


def test_claude_agent_exits_3(run_cli, launch_case):
    job_patch(launch_case, app="claude")
    result = invoke(run_cli, launch_case)
    assert result.returncode == 3
    assert "scratch-searcher runs on Claude Code here; dispatch consortium:scratch-searcher" in result.stderr
    assert not launch_case[2].exists()
    assert not (paths.state_home() / "runs").exists()


@pytest.mark.parametrize("manager", [None, "claude", "codex"])
def test_manager_is_recorded_separately_from_the_codex_app(launch_case, monkeypatch, manager):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    if manager:
        monkeypatch.setenv("CODEX_THREAD_ID" if manager == "codex" else "CLAUDECODE", "1")
    prepared(launch_case)
    meta = json.loads((folder(launch_case) / "meta.json").read_text())
    assert (meta["app"], meta["manager"]) == ("codex", manager)


def test_argv_for_a_read_only_reviewer(launch_case):
    repo, _, _ = launch_case
    run = resolve_agent("scratch-searcher", load_settings(repo), load_registry(repo), manager_app="codex")
    rd = Path("/tmp/run")
    assert launcher.codex_argv(run, repo, rd) == [
        str(FIXTURES / "fake_codex.py"), "exec", "-m", "gpt-6-luna", "-c", 'model_reasoning_effort="low"',
        "-c", 'approval_policy="never"', "-c", 'shell_environment_policy.inherit="all"',
        "-c", "allow_login_shell=false", "-s", "read-only", "-C", str(repo), "--json",
        "--output-schema", "/tmp/run/schema.json", "-o", "/tmp/run/last.md", "-",
    ]


def test_argv_for_a_device_agent_is_full_access(launch_case):
    repo = launch_case[0]
    job_patch(launch_case, capabilities=["read", "device"])
    run = resolve_agent("scratch-searcher", load_settings(repo), load_registry(repo), manager_app="codex")
    argv = launcher.codex_argv(run, repo, Path("/tmp/run"))
    assert argv[argv.index("-s") + 1] == "danger-full-access"


def test_run_records_report_tokens_and_one_log_line(run_cli, launch_case, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "manager-test")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("PRIVATE_TEST_VALUE", "never-persist-this-environment-value")
    result = invoke(run_cli, launch_case, "--tier", "standard", "--model", "test-model", "--effort", "high")
    assert result.returncode == 0, result.stderr
    rd = folder(launch_case)
    assert result.stdout.strip() == f"{rd.name} DONE {rd / 'report.json'}"
    report = json.loads((rd / "report.json").read_text())
    assert validate(report, load_schema("locations.v1")) == []
    meta = json.loads((rd / "meta.json").read_text())
    assert {meta["sources"][key] for key in ("tier", "model", "effort")} == {"brief"}
    assert (meta["app"], meta["manager"]) == ("codex", "codex")
    assert meta["brief"] == str(launch_case[1])
    records = (paths.state_home() / "runs.jsonl").read_text().splitlines()
    record = json.loads(records[0])
    assert len(records) == 1
    assert record["tokens"] == {"input": 26396, "cached_input": 12544, "output": 5}
    assert record["scope_ok"] is True
    assert (record["tier"], record["model"], record["effort"], record["manager"]) == (
        "standard", "test-model", "high", "codex")
    captured = json.loads(launch_case[2].read_text())
    assert captured["stdin"] == (rd / "prompt.md").read_text()
    env = captured["env"]
    assert env["PATH"].split(os.pathsep)[0] == str(SHIMS)
    assert [env[key] for key in ("CONSORTIUM_RUN", "CONSORTIUM_AGENT", "CONSORTIUM_MODE",
                                 "CONSORTIUM_WRITE_SCOPE", "CONSORTIUM_WORKTREE")] == [
        rd.name, "scratch-searcher", "read-only", "all", str(launch_case[0])]
    guard = json.loads(env["CONSORTIUM_GUARD"])
    assert guard["deny"] and guard["bash_allow"] and guard["deny_make"] == []
    assert guard.get("deny_in_repo") == load_settings(launch_case[0]).get("guard.deny_in_repo", [])
    assert guard["deny_in_repo"]
    assert all("never-persist-this-environment-value" not in file.read_text()
               for file in rd.iterdir() if file.is_file())
    launcher.finalize(rd.name, 0)
    assert len((paths.state_home() / "runs.jsonl").read_text().splitlines()) == 1


@pytest.mark.parametrize("mode,error", [("malformed", "malformed_report"), ("quota", "quota")])
def test_failed_reports_are_classified(run_cli, launch_case, mode, error):
    result = invoke(run_cli, launch_case, env={"FAKE_CODEX_MODE": mode})
    assert result.returncode == 1, result.stderr
    status = json.loads((folder(launch_case) / "status.json").read_text())
    assert status["status"] == "FAILED" and status["error"] == error
    assert set(status) == {"status", "error", "exit_code", "ended"}


def test_schema_invalid_report_is_malformed(run_cli, launch_case, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps({**REPORT, "payload": {}}))
    result = invoke(run_cli, launch_case)
    assert result.returncode == 1
    rd = folder(launch_case)
    assert json.loads((rd / "status.json").read_text())["error"] == "malformed_report"
    assert not (rd / "report.json").exists()


@pytest.mark.parametrize("status", ["NEEDS_CONTEXT", "BLOCKED", "FAILED"])
def test_wait_preserves_report_status_and_exits_one(run_cli, launch_case, monkeypatch, status):
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps({**REPORT, "status": status}))
    result = invoke(run_cli, launch_case)
    assert result.returncode == 1
    assert f" {status} " in result.stdout
    assert json.loads((folder(launch_case) / "status.json").read_text())["status"] == status


def test_timeout_kills_the_run(run_cli, launch_case):
    run_id = prepared(launch_case)
    rd = folder(launch_case)
    meta = json.loads((rd / "meta.json").read_text())
    # Resolution deliberately accepts integer minutes; shorten only this prepared test run.
    meta["timeout_minutes"] = 0.02
    (rd / "meta.json").write_text(json.dumps(meta))
    started = time.monotonic()
    result = run_cli("_run", run_id, env={"FAKE_CODEX_MODE": "sleep"})
    assert result.returncode != 0
    assert 10 <= time.monotonic() - started < 25
    status = json.loads((rd / "status.json").read_text())
    assert (status["status"], status["error"], status["exit_code"]) == ("FAILED", "timeout", 124)
    pids = [json.loads(launch_case[2].read_text())["pid"], int(Path(str(launch_case[2]) + ".child").read_text())]
    for pid in pids:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        assert not state or state.startswith("Z"), (pid, state)


def test_scope_violation_is_recorded(run_cli, launch_case, tmp_path):
    worktree = add_worktree(launch_case[0], tmp_path / "linked")
    (worktree / "shop").mkdir()
    result = invoke(run_cli, launch_case, "--worktree", str(worktree), env={
        "FAKE_CODEX_MODE": "write-main", "FAKE_CODEX_MAIN": str(launch_case[0])})
    assert result.returncode == 0, result.stderr
    rd = folder(launch_case)
    scope = json.loads((rd / "scope.json").read_text())
    assert "outside.txt" in scope["main_changes"]
    assert scope["scope_ok"] is False
    assert scope["main_before"] != scope["main_after"]
    assert json.loads((paths.state_home() / "runs.jsonl").read_text())["scope_ok"] is False


def test_scope_detects_a_write_to_an_already_dirty_main_file(run_cli, launch_case, tmp_path):
    (launch_case[0] / "outside.txt").write_text("preexisting untracked file\n")
    worktree = add_worktree(launch_case[0], tmp_path / "linked")
    (worktree / "shop").mkdir()
    result = invoke(run_cli, launch_case, "--worktree", str(worktree), env={
        "FAKE_CODEX_MODE": "write-main", "FAKE_CODEX_MAIN": str(launch_case[0])})
    assert result.returncode == 0, result.stderr
    scope = json.loads((folder(launch_case) / "scope.json").read_text())
    assert scope["main_before"] == scope["main_after"]
    assert "outside.txt" in scope["main_changes"]
    assert scope["scope_ok"] is False


def test_scope_entries_and_in_scope(tmp_path):
    (tmp_path / "folder").mkdir()
    brief = briefs.parse_brief("## Scope\n- `folder`\n- `future/`\n- `src/*.py`\n"
                               "- create: `new.py`\n- gone: `old.py`\n## Report\n`not-scope`\n")
    entries = briefs.scope_entries(brief)
    assert entries == ["folder", "future/", "src/*.py", "new.py", "old.py"]
    for path in ["folder/nested/a", "future/new", "src/a.py", "new.py", "old.py"]:
        assert briefs.in_scope(path, entries, tmp_path)
    for path in ["folder-other/a", "src/sub/a.py", "new.py/sub", "else.py", "../folder/a"]:
        assert not briefs.in_scope(path, entries, tmp_path)


def test_write_scope_tests_requires_scope_and_test_path(run_cli, launch_case, tmp_path):
    job_patch(launch_case, write_scope="tests")
    launch_case[1].write_text("## Task\nRead.\n## Scope\n`shop/` and `tests/`\n## Report\nlocations.v1\n")
    run_id = prepared(launch_case)
    worktree = launch_case[0]
    (worktree / "shop/outside.py").write_text("pass\n")
    (worktree / "tests/test_new.py").write_text("pass\n")
    rd = folder(launch_case)
    (rd / "last.md").write_text(json.dumps(REPORT))
    launcher.finalize(run_id, 0)
    scope = json.loads((rd / "scope.json").read_text())
    assert scope["out_of_scope"] == ["shop/outside.py"]
    assert scope["scope_ok"] is False


@pytest.mark.parametrize("name,argv,denied", [
    ("git", ["push"], True), ("git", ["-C", "folder with spaces", "commit"], True),
    ("git", ["--no-optional-locks", "tag", "v1"], True), ("git", ["merge-base", "A", "B"], False),
    ("git", ["--git-dir", "folder with spaces", "push"], True),
    ("git", ["status"], False), ("git", ["status", "--no-verify"], True),
    ("make", ["-C", "folder", "test", "deploy-live"], True),
    ("make", ["--directory=folder", "test"], False),
    ("make", ["-f", "deploy-live", "test"], False),
    ("gh", ["pr", "create"], True), ("gh", ["release", "create"], True),
    ("gh", ["--repo", "example/sample", "pr", "merge"], True),
    ("gh", ["pr", "view"], False),
])
def test_shims_refuse_push_and_allow_status(tmp_path, name, argv, denied):
    real = tmp_path / "real"
    real.mkdir()
    binary = real / name
    binary.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
    binary.chmod(0o755)
    guard = load_settings(None).get("guard")
    guard["deny_make"] = ["deploy-*"]
    result = subprocess.run([str(SHIMS / name), *argv], env=dict(os.environ,
                            PATH=os.pathsep.join([str(SHIMS), str(real), os.environ["PATH"]]),
                            CONSORTIUM_GUARD=json.dumps(guard)), capture_output=True, text=True)
    assert result.returncode == (126 if denied else 0), result.stderr
    if denied:
        assert "is not allowed inside an agent run; the manager commits, pushes and deploys" in result.stderr
    else:
        assert json.loads(result.stdout) == argv


@pytest.fixture
def shim_repos(tmp_path):
    run = tmp_path / "run repo"
    scratch = tmp_path / "scratch repo"
    for repo in (run, scratch):
        repo.mkdir()
        git(repo, "init", "--quiet")
    env = dict(os.environ, PATH=str(SHIMS) + os.pathsep + os.environ["PATH"],
               CONSORTIUM_WORKTREE=str(run), CONSORTIUM_GUARD=json.dumps(load_settings(None).get("guard")),
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    return run, scratch, env


def shim_git(cwd, env, *args):
    return subprocess.run([str(SHIMS / "git"), *args], cwd=cwd, env=env, capture_output=True, text=True)


def test_shim_allows_a_commit_in_a_separate_repository(shim_repos):
    run, scratch, env = shim_repos
    result = shim_git(run, env, "-C", str(scratch), "commit", "--allow-empty", "-m", "test fixture")
    assert result.returncode == 0, result.stderr
    assert git(scratch, "log", "-1", "--format=%s") == "test fixture"
    assert git(scratch, "rev-list", "--count", "HEAD") == "1"


def test_shim_allows_a_scratch_commit_selected_by_git_environment(shim_repos):
    run, scratch, env = shim_repos
    env.update(GIT_DIR=str(scratch / ".git"), GIT_WORK_TREE=str(scratch))
    result = shim_git(run, env, "commit", "--allow-empty", "-m", "test fixture")
    assert result.returncode == 0, result.stderr
    assert git(scratch, "log", "-1", "--format=%s") == "test fixture"
    assert git(scratch, "rev-list", "--count", "HEAD") == "1"
    assert git(run, "rev-list", "--all") == ""


@pytest.mark.parametrize("route", ["cwd", "-C", "GIT_DIR", "worktree", "main"])
def test_shim_refuses_a_commit_in_the_runs_repository(shim_repos, tmp_path, route):
    run, scratch, env = shim_repos
    cwd, options = run, []
    if route == "-C":
        cwd, options = scratch, ["-C", str(run)]
    elif route == "GIT_DIR":
        cwd = scratch
        env["GIT_DIR"] = str(run / ".git")
    elif route in {"worktree", "main"}:
        linked = add_worktree(run, tmp_path / "linked")
        if route == "worktree":
            cwd = linked
        else:
            env["CONSORTIUM_WORKTREE"] = str(linked)
    result = shim_git(cwd, env, *options, "commit", "--allow-empty", "-m", "test fixture")
    assert result.returncode == 126, result.stderr
    assert "is not allowed inside an agent run; the manager commits, pushes and deploys" in result.stderr
    assert git(run, "rev-list", "--all") == ""


@pytest.mark.parametrize("worktree", [None, "", "missing", "not a repo"])
def test_shim_refuses_a_commit_when_the_run_repository_cannot_be_resolved(shim_repos, tmp_path, worktree):
    run, scratch, env = shim_repos
    if worktree is None:
        env.pop("CONSORTIUM_WORKTREE")
    elif worktree == "":
        env["CONSORTIUM_WORKTREE"] = ""
    else:
        path = tmp_path / worktree
        if worktree == "not a repo":
            path.mkdir()
        env["CONSORTIUM_WORKTREE"] = str(path)
    result = shim_git(scratch, env, "commit", "--allow-empty", "-m", "test fixture")
    assert result.returncode == 126, result.stderr
    assert "is not allowed inside an agent run" in result.stderr
    assert git(scratch, "rev-list", "--all") == ""


def test_shim_refuses_a_commit_when_the_command_repository_cannot_be_resolved(shim_repos, tmp_path):
    _, _, env = shim_repos
    result = shim_git(tmp_path, env, "commit", "--allow-empty", "-m", "test fixture")
    assert result.returncode == 126, result.stderr
    assert "is not allowed inside an agent run" in result.stderr


def test_shim_refuses_push_in_a_separate_repository(shim_repos):
    _, scratch, env = shim_repos
    result = shim_git(scratch, env, "push")
    assert result.returncode == 126, result.stderr
    assert "is not allowed inside an agent run" in result.stderr


def test_detached_run_in_a_private_tmux_server(run_cli, launch_case, monkeypatch):
    socket = f"consortium-test-{os.getpid()}-{time.time_ns()}"
    monkeypatch.setenv("CONSORTIUM_TMUX_SOCKET", socket)
    monkeypatch.delenv("CONSORTIUM_NO_TMUX")
    try:
        result = invoke(run_cli, launch_case)
        assert result.returncode == 0, result.stderr
        assert " DONE " in result.stdout
        assert json.loads(launch_case[2].read_text())["env"]["CONSORTIUM_RUN"] == folder(launch_case).name
        for _ in range(30):
            sessions = subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "ls"], capture_output=True, text=True)
            if folder(launch_case).name not in sessions.stdout:
                break
            time.sleep(0.1)
        assert folder(launch_case).name not in sessions.stdout
    finally:
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "kill-server"], capture_output=True)


def test_list_and_log(run_cli, launch_case):
    run_id = prepared(launch_case)
    rd = folder(launch_case)
    assert launcher.list_running() == [{"id": run_id, "agent": "scratch-searcher",
        "started": json.loads((rd / "meta.json").read_text())["started"], "alive": False}]
    subprocess.run(["tmux", "-L", os.environ["CONSORTIUM_TMUX_SOCKET"], "-f", "/dev/null",
                    "new-session", "-d", "-s", run_id, "--", "sleep", "30"], check=True)
    assert launcher.list_running()[0]["alive"] is True
    result = run_cli("run-codex", "--list")
    assert result.returncode == 0 and run_id in result.stdout
    (rd / "events.jsonl").write_text(
        '{"type":"turn.started"}\n{"type":"item.completed","item":{"text":"hello"}}\n'
        '{"type":"item.started","item":{"command":"git status"}}\n')
    assert launcher.show_log(run_id, 2) == "item.completed hello\nitem.started git status"
    result = run_cli("run-codex", "--log", run_id, "--tail", "1")
    assert result.returncode == 0 and result.stdout.strip() == "item.started git status"
    assert launcher.wait(run_id, 0) == {"status": "running"}
    launcher.execute(run_id)
    assert launcher.list_running() == []
    assert launcher.wait(run_id, 0)["status"] == "DONE"


def test_new_worktree_runs_setup_under_the_disk_lock(run_cli, launch_case):
    repo = launch_case[0]
    config = repo / ".consortium/config.yaml"
    config.write_text("worktree:\n  setup:\n    - 'printf \"%s\" \"$CONSORTIUM_LOCKS_HELD\" > setup-locks'\n")
    # Copy a committed repo using a local clone: no commit is made by this test.
    seeded = repo.parent / "seeded"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(ROOT), str(seeded)], check=True)
    git(seeded, "checkout", "--quiet", "HEAD", "--", "README.md")
    shutil.copytree(repo / ".consortium", seeded / ".consortium")
    launch_case[1].write_text("## Task\nRead.\n## Scope\n`README.md`\n## Report\nlocations.v1\n")
    result = run_cli("run-codex", "scratch-searcher", str(launch_case[1]), "--repo", str(seeded),
                     "--new-worktree", "launcher-test", "--wait")
    # Scope paths are checked in the source checkout before the new worktree exists.
    assert result.returncode == 0, result.stderr + result.stdout
    wt = seeded / ".worktrees/launcher-test"
    assert (wt / "setup-locks").read_text() == "disk"
    assert (wt / ".git").is_file()


def test_write_agent_requires_and_uses_its_worktree(run_cli, launch_case, tmp_path):
    job_patch(launch_case, mode="worktree-write", capabilities=["read", "edit", "shell"])
    launch_case[1].write_text(
        "## Task\nRead.\n## Context\nSample.\n## Scope\n`shop/`\n## Do not change\nOther files.\n"
        "## Premises\n- none\n## Tests\nnone — no code changes\n## Done means\nReturn evidence.\n"
        "## Forbidden\nNever commit or push.\n## Stop when\nReport NEEDS_CONTEXT if unclear.\n"
        "## Report\nlocations.v1\n")
    result = invoke(run_cli, launch_case)
    assert result.returncode == 1 and "needs --worktree" in result.stderr
    assert not (paths.state_home() / "runs").exists()
    worktree = add_worktree(launch_case[0], tmp_path / "linked")
    (worktree / "shop").mkdir()
    launch_case[1].write_text(f"---\nworktree: {worktree}\n---\n" + launch_case[1].read_text())
    result = invoke(run_cli, launch_case)
    assert result.returncode == 0, result.stderr
    captured = json.loads(launch_case[2].read_text())
    assert captured["env"]["CONSORTIUM_WORKTREE"] == str(worktree)
    assert json.loads(captured["env"]["CONSORTIUM_GUARD"])["bash_allow"] == []
    argv = captured["argv"]
    assert argv[argv.index("-C") + 1] == str(worktree)
    assert argv[argv.index("-s") + 1] == "danger-full-access"


def test_report_redaction_and_guard_capability_allowlist(run_cli, launch_case, monkeypatch):
    job_patch(launch_case, capabilities=["read", "device"])
    launch_case[1].write_text("---\ndevice: emulator-test\n---\n" + launch_case[1].read_text())
    report = {**REPORT, "summary": "token " + "ghp_" + "A" * 36}
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(report))
    result = invoke(run_cli, launch_case)
    assert result.returncode == 0, result.stderr
    rd = folder(launch_case)
    assert json.loads((rd / "report.json").read_text())["summary"] == "token [REDACTED]"
    env = json.loads(launch_case[2].read_text())["env"]
    assert "device:emulator-test" in env["CONSORTIUM_LOCKS_HELD"].split(",")
    assert r"^(adb|idb|maestro|emulator)\b" in json.loads(env["CONSORTIUM_GUARD"])["bash_allow"]


def test_a_good_run_that_mentions_quota_is_not_a_quota_failure(run_cli, launch_case):
    result = invoke(run_cli, launch_case, env={"FAKE_CODEX_MODE": "noisy"})
    assert result.returncode == 0, result.stderr
    status = json.loads((folder(launch_case) / "status.json").read_text())
    assert (status["status"], status["error"]) == ("DONE", None)


def test_session_env_args_send_only_differences_and_names_to_drop():
    assert launcher._session_env_args(None, {"SECRET": "s", "A": "1"}) == []
    server = {"SECRET": "s", "A": "1", "STALE": "old"}
    env = {"SECRET": "s", "A": "2", "NEW": "n"}
    assert launcher._session_env_args(server, env) == ["-e", "A=2", "-e", "NEW=n", "-e", "CONSORTIUM_UNSET=STALE"]


@pytest.fixture
def developer_tools(tmp_path, monkeypatch):
    system = tmp_path / "system"
    real = tmp_path / "developer tools"
    other = tmp_path / "other"
    for directory in (system, real, other):
        directory.mkdir()
    for name in ("git", "gh", "make"):
        binary = real / name
        binary.write_text(f"#!/bin/sh\nprintf '{name} works\\n'\nprintf '%s\\n' \"$@\"\n")
        binary.chmod(0o755)
    binary = system / "git"
    binary.write_text("#!/bin/sh\nexit 1\n")
    binary.chmod(0o755)
    xcrun = other / "xcrun"
    xcrun.write_text(
        f"#!{sys.executable}\n"
        "import os, sys, time\n"
        "from pathlib import Path\n"
        f"root = Path({str(tmp_path)!r})\n"
        "with (root / 'calls').open('a') as stream:\n"
        "    stream.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "assert len(sys.argv) == 3 and sys.argv[1] == '--find'\n"
        "mode = os.environ.get('FAKE_XCRUN_MODE')\n"
        "if mode == 'fail':\n"
        "    print(root / 'developer tools' / sys.argv[2])\n"
        "    sys.exit(1)\n"
        "if mode == 'timeout':\n"
        "    time.sleep(10)\n"
        "if mode == 'empty':\n"
        "    sys.exit(0)\n"
        "print(root / ('missing' if mode == 'missing' else 'developer tools') / sys.argv[2])\n"
    )
    xcrun.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(other), str(system)]))
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "SYSTEM_BIN_DIR", system)
    meta = {"run_id": "developer-tools", "agent": "searcher", "mode": "read-only",
            "write_scope": "all", "worktree": str(tmp_path), "capabilities": ["read"]}
    return meta, briefs.parse_brief(""), load_settings(None)


def assert_developer_tool(binary, name):
    assert binary.is_file() and not binary.is_symlink()
    assert binary.stat().st_mode & 0o777 == 0o755
    assert binary.read_text().splitlines()[0] == "#!/bin/sh"
    result = subprocess.run([str(binary), "--flag", "with space"], capture_output=True, text=True)
    assert (result.returncode, result.stdout, result.stderr) == (0, f"{name} works\n--flag\nwith space\n", "")


@pytest.mark.parametrize("mode", ["read-only", "worktree-write"])
@pytest.mark.parametrize("name", ["git", "gh", "make"])
def test_environment_wraps_macos_developer_tools(developer_tools, tmp_path, mode, name):
    meta, task, settings = developer_tools
    meta["mode"] = mode
    if name != "git":
        (tmp_path / "system/git").rename(tmp_path / "system" / name)
    inherited = os.environ["PATH"]
    env = launcher._environment(meta, task, settings)
    binary_dir = paths.state_home() / "runs/developer-tools/bin"
    assert env["PATH"] == os.pathsep.join([str(SHIMS), str(binary_dir), inherited])
    assert_developer_tool(binary_dir / name, name)


def test_environment_only_wraps_commands_resolving_inside_system_folder(developer_tools, tmp_path):
    (tmp_path / "other/git").symlink_to(tmp_path / "developer tools/git")
    (tmp_path / "system/make").write_bytes((tmp_path / "system/git").read_bytes())
    (tmp_path / "system/make").chmod(0o755)
    (tmp_path / "system/gh").symlink_to(tmp_path / "developer tools/gh")
    env = launcher._environment(*developer_tools)
    binary_dir = paths.state_home() / "runs/developer-tools/bin"
    assert env["PATH"].split(os.pathsep)[:2] == [str(SHIMS), str(binary_dir)]
    assert sorted(path.name for path in binary_dir.iterdir()) == ["make"]
    assert_developer_tool(binary_dir / "make", "make")
    assert (tmp_path / "calls").read_text() == "--find make\n"


def test_environment_preserves_an_earlier_non_system_git(developer_tools, tmp_path):
    (tmp_path / "other/git").symlink_to(tmp_path / "developer tools/git")
    inherited = os.environ["PATH"]
    env = launcher._environment(*developer_tools)
    assert env["PATH"] == str(SHIMS) + os.pathsep + inherited
    assert not (tmp_path / "calls").exists()


@pytest.mark.parametrize("mode", ["fail", "timeout", "missing", "empty", "not-executable", "no-xcrun"])
def test_environment_keeps_path_when_xcrun_cannot_resolve(developer_tools, tmp_path, monkeypatch, mode):
    monkeypatch.setenv("FAKE_XCRUN_MODE", mode)
    if mode == "not-executable":
        (tmp_path / "developer tools/git").chmod(0o644)
    elif mode == "no-xcrun":
        (tmp_path / "other/xcrun").unlink()
    inherited = os.environ["PATH"]
    started = time.monotonic()
    env = launcher._environment(*developer_tools)
    assert time.monotonic() - started < 8
    assert env["PATH"] == str(SHIMS) + os.pathsep + inherited
    assert not (paths.state_home() / "runs/developer-tools/bin/git").exists()


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_environment_leaves_developer_tools_alone_off_macos(developer_tools, tmp_path, monkeypatch, platform):
    monkeypatch.setattr(launcher.sys, "platform", platform)
    inherited = os.environ["PATH"]
    env = launcher._environment(*developer_tools)
    assert env["PATH"] == str(SHIMS) + os.pathsep + inherited
    assert not (tmp_path / "calls").exists()


def test_environment_can_wrap_developer_tools_again_for_tmux(developer_tools, tmp_path, monkeypatch):
    env = launcher._environment(*developer_tools)
    binary_dir = paths.state_home() / "runs/developer-tools/bin"
    assert_developer_tool(binary_dir / "git", "git")
    (binary_dir / "git").unlink()
    (binary_dir / "git").symlink_to(tmp_path / "missing")
    monkeypatch.setenv("PATH", env["PATH"])
    env = launcher._environment(*developer_tools)
    assert env["PATH"].split(os.pathsep)[:2] == [str(SHIMS), str(binary_dir)]
    assert_developer_tool(binary_dir / "git", "git")
    monkeypatch.setenv("PATH", env["PATH"])
    env = launcher._environment(*developer_tools)
    assert env["PATH"].split(os.pathsep)[:2] == [str(SHIMS), str(binary_dir)]
    assert_developer_tool(binary_dir / "git", "git")


def test_environment_replaces_old_developer_tool_symlinks(developer_tools, tmp_path):
    binary_dir = paths.state_home() / "runs/developer-tools/bin"
    binary_dir.mkdir(parents=True)
    binary = binary_dir / "git"
    binary.symlink_to(tmp_path / "developer tools/git")
    for _ in range(2):
        env = launcher._environment(*developer_tools)
        assert env["PATH"].split(os.pathsep)[:2] == [str(SHIMS), str(binary_dir)]
        assert_developer_tool(binary, "git")


def test_environment_drops_the_names_tmux_could_not_unset(launch_case, monkeypatch):
    run_id = prepared(launch_case)
    rd = paths.state_home() / "runs" / run_id
    meta = json.loads((rd / "meta.json").read_text())
    monkeypatch.setenv("STALE_TOKEN", "old")
    monkeypatch.setenv("CONSORTIUM_UNSET", "STALE_TOKEN")
    task = briefs.parse_brief((rd / "brief.md").read_text())
    env = launcher._environment(meta, task, load_settings(launch_case[0]))
    assert "STALE_TOKEN" not in env and "CONSORTIUM_UNSET" not in env


def test_a_running_server_does_not_leak_a_dropped_variable_into_the_run(run_cli, launch_case, monkeypatch):
    socket = f"consortium-test-{os.getpid()}-{time.time_ns()}"
    monkeypatch.setenv("CONSORTIUM_TMUX_SOCKET", socket)
    monkeypatch.delenv("CONSORTIUM_NO_TMUX")
    try:
        holder = dict(os.environ, STALE_TOKEN="old")
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "new-session", "-d", "-s", "holder", "sleep 60"],
                       env=holder, check=True)
        result = invoke(run_cli, launch_case)
        assert result.returncode == 0, result.stderr
        assert "STALE_TOKEN" not in json.loads(launch_case[2].read_text())["env"]
    finally:
        subprocess.run(["tmux", "-L", socket, "-f", "/dev/null", "kill-server"], capture_output=True)

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from consortium import paths, runlog
from consortium.registry import parse_front_matter

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins/consortium"
FIXTURES = Path(__file__).parent / "fixtures/hooks"
GUARD = PACKAGE / "hooks/guard.py"


@pytest.fixture(autouse=True)
def hook_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CONSORTIUM_TIER", "off")
    for key in ("CONSORTIUM_RUN", "CONSORTIUM_AGENT", "CONSORTIUM_WORKTREE"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    write_job(repo, "fixture-reader", mode="read-only")
    write_job(repo, "fixture-writer", mode="worktree-write")
    write_job(repo, "fixture-tester", mode="worktree-write", write_scope="tests")
    write_job(repo, "fixture-device", mode="read-only", capabilities=["read", "device"])
    return repo


def write_job(repo, name, **patch):
    front, body = parse_front_matter((Path(__file__).parent / "fixtures/jd/sample-reader.md").read_text())
    front["name"] = name
    front["consortium"].update(patch)
    folder = repo / ".consortium/agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text("---\n" + yaml.safe_dump(front) + "---\n" + body)


def payload(event, repo, agent="consortium:fixture-reader"):
    data = json.loads((FIXTURES / f"{event}.json").read_text())
    data.update(cwd=str(repo), session_id="session-fixture")
    if "agent_id" in data:
        data["agent_id"] = "agent-fixture"
        data["agent_type"] = agent
    if event == "pre-agent":
        data["tool_input"].update(subagent_type=agent, prompt="Find the answer.")
    return data


def handle(event, data, **env):
    # Import inside the helper so the fast guard test also runs before the module exists.
    from consortium.hooks import handle
    return handle(event, data, dict(os.environ, **env))


def denied(result):
    assert result is not None
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"]
    return output["permissionDecisionReason"]


def bash(repo, command, agent="consortium:fixture-writer", **env):
    data = payload("pre-bash", repo, agent)
    data["tool_input"]["command"] = command
    return handle("pre-bash", data, **env)


def report():
    return {"schema": "findings.v1", "status": "DONE", "summary": "Checked.",
            "decisions": [], "evidence": [], "changes": [], "checks": [], "questions": [],
            "payload": {"verdict": "pass", "findings": []}}


def transcript(tmp_path, text):
    target = tmp_path / "agent.jsonl"
    rows = [
        {"type": "assistant", "message": {"id": "message-one", "model": "fixture-model",
         "content": [{"type": "text", "text": "Working."}],
         "usage": {"input_tokens": 10, "cache_read_input_tokens": 3, "output_tokens": 2}}},
        {"type": "assistant", "message": {"id": "message-two", "model": "fixture-model",
         "content": [{"type": "text", "text": text}],
         "usage": {"input_tokens": 20, "cache_creation_input_tokens": 4, "output_tokens": 5}}},
    ]
    target.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return target


def test_guard_allows_the_managers_commands_fast():
    data = json.loads((FIXTURES / "pre-agent.json").read_text())
    data.update(tool_name="Bash", tool_input={"command": "git push"})
    durations = []
    for _ in range(20):
        start = time.perf_counter()
        result = subprocess.run([sys.executable, str(GUARD), "pre-bash"],
                                input=json.dumps(data), capture_output=True, text=True, timeout=5)
        durations.append(time.perf_counter() - start)
        assert result.returncode == 0, result.stderr
        assert result.stdout == result.stderr == ""
    assert statistics.median(durations) < 0.1


def test_pre_agent_denies_a_bad_brief(repo):
    reason = denied(handle("pre-agent", payload("pre-agent", repo)))
    assert "structure:" in reason and "Scope" in reason and "Report" in reason


def test_pre_agent_allows_a_good_brief(repo):
    data = payload("pre-agent", repo)
    data["tool_input"]["prompt"] = "## Task\nRead.\n## Scope\nNo files.\n## Report\nfindings.v1\n"
    assert handle("pre-agent", data) is None


@pytest.mark.parametrize("agent", ["Explore", "other:fixture-reader", "consortium:spec-compliance-reviewer", "consortium:missing"])
def test_pre_agent_ignores_old_format_and_other_agents(repo, agent):
    assert handle("pre-agent", payload("pre-agent", repo, agent)) is None


def test_pre_agent_warns_when_the_old_tier_is_on(repo):
    tier = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--git-path", "consortium/tier"], text=True).strip()
    tier_path = repo / tier
    tier_path.parent.mkdir(parents=True)
    tier_path.write_text("experts-eval\n")
    result = handle("pre-agent", payload("pre-agent", repo, "consortium:implementer"))
    assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "structure:" in result["hookSpecificOutput"]["additionalContext"]
    assert "permissionDecision" not in result["hookSpecificOutput"]


@pytest.mark.parametrize("command", [
    "git -C x commit -m test", "git push", "bash -c 'git push'", "sh -c 'git commit'",
    "ls && git push", "false || git push", "pwd; git push", "echo x | git push", "pwd\ngit push",
    "make deploy-x", "make -C subdir deploy-x", "bash -c 'make deploy-x'",
    "git -C 'folder with spaces' commit -m test",
])
def test_pre_bash_denies_commit_push_and_deploy_targets(repo, command):
    (repo / ".consortium/config.yaml").write_text("guard:\n  deny_make: ['deploy-*']\n")
    denied(bash(repo, command))


@pytest.mark.parametrize("command", ["git diff -- push.py", "git log --grep=commit", "git merge-base HEAD main", "make test"])
def test_pre_bash_allows_other_writer_commands(repo, command):
    assert bash(repo, command) is None


@pytest.mark.parametrize("command,agent,allow", [
    ("git diff", "fixture-reader", True), ("rm -rf x", "fixture-reader", False),
    ("git diff && rm -rf x", "fixture-reader", False), ("bash -c 'git diff'", "fixture-reader", True),
    ("sh -c 'git diff; rm -rf x'", "fixture-reader", False),
    ("adb shell", "fixture-reader", False), ("adb shell", "fixture-device", True),
])
def test_pre_bash_read_only_agent_allowlist(repo, command, agent, allow):
    result = bash(repo, command, "consortium:" + agent)
    assert result is None if allow else result is not None
    if not allow:
        denied(result)


def test_pre_bash_applies_global_denies_to_other_subagents_and_launcher_runs(repo):
    denied(bash(repo, "git push", "Explore"))
    data = payload("pre-bash", repo)
    del data["agent_id"]
    del data["agent_type"]
    data["tool_input"]["command"] = "git push"
    denied(handle("pre-bash", data, CONSORTIUM_RUN="run-fixture", CONSORTIUM_AGENT="fixture-writer"))


def test_agent_type_falls_back_to_start_file_then_launcher_environment(repo):
    handle("subagent-start", payload("subagent-start", repo))
    data = payload("pre-bash", repo)
    del data["agent_type"]
    data["tool_input"]["command"] = "rm -rf x"
    denied(handle("pre-bash", data))
    data["agent_type"] = "consortium:fixture-writer"
    assert handle("pre-bash", data) is None
    del data["agent_id"]
    del data["agent_type"]
    denied(handle("pre-bash", data, CONSORTIUM_RUN="run-fixture", CONSORTIUM_AGENT="fixture-reader"))


@pytest.mark.parametrize("agent,path,allow", [
    ("fixture-reader", "tests/new.py", False), ("fixture-writer", "src/new.py", True),
    ("fixture-tester", "tests/new.py", True), ("fixture-tester", "nested/tests/new.py", True),
    ("fixture-tester", "src/new.py", False), ("fixture-tester", "tests/../src/new.py", False),
])
def test_pre_write_respects_mode_and_scope(repo, agent, path, allow):
    data = payload("pre-bash", repo, "consortium:" + agent)
    data.update(tool_name="Write", tool_input={"file_path": str(repo / path)})
    result = handle("pre-write", data)
    assert result is None if allow else result is not None


def test_pre_write_stays_inside_launcher_worktree_and_follows_symlinks(repo, tmp_path):
    (repo / "escape").symlink_to(tmp_path, target_is_directory=True)
    data = payload("pre-bash", repo, "consortium:fixture-writer")
    for path in (str(tmp_path / "outside.py"), "../outside.py", "escape/outside.py", str(repo) + "-other/file.py"):
        data["tool_input"] = {"file_path": path}
        denied(handle("pre-write", data, CONSORTIUM_WORKTREE=str(repo)))
    data["tool_input"] = {"notebook_path": "inside.ipynb"}
    assert handle("pre-write", data, CONSORTIUM_WORKTREE=str(repo)) is None


def test_manager_handle_is_silent_and_does_not_create_state(repo, monkeypatch):
    state = paths.state_home() / "unused"
    monkeypatch.setenv("CONSORTIUM_HOME", str(state))
    data = payload("pre-agent", repo)
    data["tool_input"] = {"command": "git push", "file_path": "/outside.py"}
    assert handle("pre-bash", data) is None
    assert handle("pre-write", data) is None
    assert not state.exists()


def test_subagent_start_assigns_a_run_id(repo):
    assert handle("subagent-start", payload("subagent-start", repo)) is None
    start = json.loads((paths.state_home() / "agents/agent-fixture.json").read_text())
    assert start["agent_type"] == "consortium:fixture-reader"
    assert start["session_id"] == "session-fixture"
    assert start["started"]
    assert "-fixture-reader-" in start["id"]


def test_subagent_stop_blocks_once_on_a_bad_report(repo, tmp_path):
    handle("subagent-start", payload("subagent-start", repo))
    data = payload("subagent-stop", repo)
    assert "last_assistant_message" not in data  # This field was absent in the real capture.
    data["agent_transcript_path"] = str(transcript(tmp_path, "Not a report."))
    result = handle("subagent-stop", data)
    assert result["decision"] == "block"
    assert "findings.v1" in result["reason"]
    assert not runlog.read_records()
    assert (paths.state_home() / "agents/agent-fixture.json").exists()
    data["stop_hook_active"] = True
    assert handle("subagent-stop", data) is None
    record, = runlog.read_records()
    assert record["status"] == "FAILED" and record["error"] == "malformed_report"
    assert not (paths.state_home() / "agents/agent-fixture.json").exists()


def test_subagent_stop_records_the_run(repo, tmp_path):
    handle("subagent-start", payload("subagent-start", repo))
    start_file = paths.state_home() / "agents/agent-fixture.json"
    run_id = json.loads(start_file.read_text())["id"]
    data = payload("subagent-stop", repo)
    data["agent_transcript_path"] = str(transcript(tmp_path, "```json\n" + json.dumps(report()) + "\n```"))
    assert handle("subagent-stop", data) is None
    assert handle("subagent-stop", data) is None
    record, = runlog.read_records()
    assert record["id"] == run_id
    assert record["agent"] == "fixture-reader" and record["app"] == "claude"
    assert record["status"] == "DONE" and record["error"] is None
    assert record["model"] == "fixture-model"
    assert record["tokens"] == {"input": 37, "cached_input": 3, "output": 7}
    assert record["repo"] == str(repo) and record["worktree"] == str(repo)
    assert record["tier"] == "standard" and record["jd_version"] == 2
    assert record["started"] and record["ended"] and record["minutes"] >= 0
    assert json.loads(Path(record["report"]).read_text()) == report()
    assert not start_file.exists()


def test_subagent_stop_without_start_still_records_once(repo, tmp_path):
    data = payload("subagent-stop", repo)
    data["agent_transcript_path"] = str(transcript(tmp_path, json.dumps(report())))
    assert handle("subagent-stop", data) is None
    assert handle("subagent-stop", data) is None
    record, = runlog.read_records()
    assert "-fixture-reader-" in record["id"]


@pytest.mark.parametrize("agent", ["Explore", "consortium:spec-compliance-reviewer"])
def test_subagent_stop_ignores_other_and_old_agents(repo, agent):
    assert handle("subagent-stop", payload("subagent-stop", repo, agent)) is None
    assert runlog.read_records() == []


def test_hook_errors_allow_with_one_diagnostic(repo, capsys, monkeypatch):
    from consortium import hooks
    def broken(*args, **kwargs):
        raise RuntimeError("unexpected\nerror")
    monkeypatch.setattr(hooks.registry, "load_registry", broken)
    assert handle("pre-agent", payload("pre-agent", repo)) is None
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1


def test_report_text_blocks_from_one_assistant_message_are_combined(repo, tmp_path):
    target = transcript(tmp_path, "```json\n" + json.dumps(report()) + "\n```")
    with target.open("a") as stream:
        stream.write(json.dumps({"type": "assistant", "message": {"id": "message-two",
                     "content": [{"type": "text", "text": "Complete."}]}}) + "\n")
    data = payload("subagent-stop", repo)
    data["agent_transcript_path"] = str(target)
    assert handle("subagent-stop", data) is None
    record, = runlog.read_records()
    assert record["status"] == "DONE"


def test_guard_forwards_subagent_payload_and_output(repo):
    data = payload("pre-bash", repo, "Explore")
    data["tool_input"]["command"] = "git push"
    result = subprocess.run([sys.executable, str(GUARD), "pre-bash"], input=json.dumps(data),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    denied(json.loads(result.stdout))


@pytest.mark.parametrize("text", ["not json", "[]"])
def test_hook_cli_errors_allow_with_one_diagnostic(run_cli, text):
    result = subprocess.run([str(ROOT / "bin/consortium"), "hook", "pre-bash"], input=text,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stdout == ""
    assert len(result.stderr.splitlines()) == 1



@pytest.mark.parametrize("command", [
    "rg foo > out.txt", "rg foo >> out.txt", "cat a >out.txt", "sort -o out.txt a", "find . -delete",
    r"find . -name x -exec rm {} \;", "echo $(rm -rf x)", "cat `ls`", "git diff --output=x.patch",
    "rg --pre ./x.sh foo", "diff <(cat a) b",
])
def test_read_only_agent_cannot_write_or_run_commands_inside_commands(repo, command):
    assert "read-only agent" in denied(bash(repo, command, agent="consortium:fixture-reader"))


@pytest.mark.parametrize("command", [
    "rg foo 2>/dev/null", "rg foo 2>&1", "rg foo > /dev/null", "cat a | wc -l", "find . -name '*.py'",
    "git diff --stat", "sort a",
])
def test_read_only_agent_keeps_harmless_redirections(repo, command):
    assert bash(repo, command, agent="consortium:fixture-reader") is None


@pytest.mark.parametrize("command", ["echo $(git push)", "echo `git commit -m x`"])
def test_command_substitution_cannot_hide_a_push(repo, command):
    denied(bash(repo, command))


def test_other_agents_start_files_are_cleaned_up(repo, tmp_path):
    start = payload("subagent-start", repo, agent="Explore")
    handle("subagent-start", start)
    start_file = Path(os.environ["CONSORTIUM_HOME"]) / "agents" / "agent-fixture.json"
    assert start_file.is_file()
    stop = payload("subagent-stop", repo, agent="Explore")
    stop["agent_transcript_path"] = str(transcript(tmp_path, "done"))
    assert handle("subagent-stop", stop) is None
    assert not start_file.exists()

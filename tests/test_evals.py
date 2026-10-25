import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from consortium import brief, launcher, paths, registry
from consortium.config import load_settings


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "plugins/consortium/evals"
FIXTURES = ROOT / "tests/fixtures"
AGENTS = {
    "spec-gate": "number-reversal", "code-reviewer": "swallowed-error",
    "security-reviewer": "sql-string-format", "infra-reviewer": "table-replacement",
    "searcher": "all-callers", "implementer": "small-fix",
    "test-designer": "rule-pairs", "investigator": "hardcoded-default", "ci-gate": "known-flake",
}
REPORT = {
    "schema": "locations.v1", "status": "DONE", "summary": "All callers.", "decisions": [],
    "evidence": [], "changes": [], "checks": [], "questions": [],
    "payload": {"searches": [{"name": "distance_km", "command": "rg -n distance_km .",
        "matches": [{"file": file, "line": 1, "text": "distance_km", "kind": "tests"}
                    for file in ["shop/distance.py", *[f"tests/test_{name}.py" for name in
                        ("distance", "store_card", "search", "feed", "share", "notify")]]]}], "too_common": []},
}


@pytest.fixture
def evals():
    from consortium import evals
    return evals


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def test_all_nine_cases_use_the_native_format_and_dictated_prompt(evals):
    for agent, name in AGENTS.items():
        cases = evals.load_cases(agent, None)
        assert [case.name for case in cases] == [name]
        data = cases[0].data
        assert data["schema_version"] == "1.0" and data["runs"] == 1
        assert data["context"]["scaffold_script"] == "scaffold.sh"
        wrapper = cases[0].directory / "scaffold.sh"
        assert os.access(wrapper, os.X_OK)
        assert wrapper.read_text() == (
            '#!/usr/bin/env bash\n'
            'exec "$(dirname "${BASH_SOURCE[0]}")/../../_fixtures/make_case_repo.sh" '
            '"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$PWD"\n')
        assert data["execution"]["prompt"] == (
            f"Dispatch the consortium:{agent} agent with the whole text of brief.md as its prompt. "
            "Then print its final report verbatim and nothing else.")
        assert data["graders"]


def test_cases_load_plugin_first_then_sorted_repo_cases(evals, tmp_path):
    git(tmp_path, "init", "-q")
    for name in ("z-local", "a-local"):
        folder = tmp_path / ".consortium/evals/searcher" / name
        shutil.copytree(SUITE / "searcher/all-callers", folder)
        data = yaml.safe_load((folder / "case.yaml").read_text())
        data["name"] = name
        (folder / "case.yaml").write_text(yaml.safe_dump(data))
    cases = evals.load_cases("searcher", tmp_path)
    assert [case.name for case in cases] == ["all-callers", "a-local", "z-local"]


@pytest.mark.parametrize("agent", AGENTS)
def test_scaffold_brief_is_outside_repo_and_every_brief_passes(evals, tmp_path, agent):
    case = evals.load_cases(agent, None)[0]
    repo = evals.scaffold(case, tmp_path)
    assert (repo / ".git").is_dir()
    assert not list(repo.rglob("brief.md"))
    assert "brief.md" not in git(repo, "ls-files")
    task = brief.parse_brief((case.directory / "brief.md").read_text())
    settings = load_settings(repo, task.front)
    job = registry.load_registry(repo)[agent]
    run = registry.resolve_agent(agent, settings, {agent: job}, brief=task.front, manager_app="codex")
    assert brief.check_brief(task, job, run.mode, repo, settings) == []
    runtime_brief = tmp_path / "briefs" / agent / case.directory.name / "brief.md"
    checked = subprocess.run([str(ROOT / "bin/consortium"), "brief-check", str(runtime_brief),
                              "--repo", str(tmp_path)], cwd=tmp_path, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert brief.parse_brief(runtime_brief.read_text()).front["worktree"] == str(repo.resolve())
    assert [path.relative_to(tmp_path).as_posix() for path in tmp_path.glob("repos/*/*")] == [
        f"repos/{agent}/{case.directory.name}"]


def test_scaffold_commits_setup_but_leaves_change_uncommitted(evals, tmp_path):
    case = evals.load_cases("implementer", None)[0]
    repo = evals.scaffold(case, tmp_path / "setup")
    assert "range(1, count)" in git(repo, "show", "HEAD:shop/pricing.py")
    assert "test_quantity_steps" in git(repo, "show", "HEAD:tests/test_pricing.py")
    assert git(repo, "status", "--porcelain") == ""
    case = evals.load_cases("spec-gate", None)[0]
    repo = evals.scaffold(case, tmp_path / "change")
    assert "[5, 10, 15, 20]" in git(repo, "show", "HEAD:shop/pricing.py")
    assert "[5, 10, 20, 15]" in (repo / "shop/pricing.py").read_text()
    assert git(repo, "status", "--porcelain").strip() == "M shop/pricing.py"


def test_implementer_premise_points_at_the_function_it_names(evals, tmp_path):
    import re

    case = evals.load_cases("implementer", None)[0]
    repo = evals.scaffold(case, tmp_path)
    task = brief.parse_brief((case.directory / "brief.md").read_text())
    citation = re.search(r"shop/pricing\.py:(\d+)", task.sections["premises"])
    line = (repo / "shop/pricing.py").read_text().splitlines()[int(citation[1]) - 1]
    assert line.startswith("def quantity_steps(")


def test_scaffold_copy_skips_caches_at_every_depth(evals, tmp_path):
    suite = tmp_path / "suite"
    shutil.copytree(SUITE / "_fixtures", suite / "_fixtures")
    case_dir = suite / "searcher/all-callers"
    shutil.copytree(SUITE / "searcher/all-callers", case_dir)
    sample = suite / "_fixtures/sample-repo"
    for name in (".venv", "__pycache__", ".pytest_cache"):
        for parent in (sample, sample / "shop"):
            cache = parent / name
            cache.mkdir(exist_ok=True)
            (cache / "stray.txt").write_text("must not copy")
    original = evals.load_cases("searcher", None)[0]
    case = evals.Case("searcher", original.name, case_dir, original.data)
    repo = evals.scaffold(case, tmp_path / "destination")
    assert not any(path.name in (".venv", "__pycache__", ".pytest_cache") for path in repo.rglob("*"))
    assert "stray.txt" not in git(repo, "ls-files")


def test_shared_sample_contains_no_generated_caches():
    sample = SUITE / "_fixtures/sample-repo"
    assert not any(path.name in (".venv", "__pycache__", ".pytest_cache") for path in sample.rglob("*"))


@pytest.mark.parametrize("grader,report,passed", [
    ({"type": "regex", "name": "verdict", "pattern": "not_compliant"}, '{"verdict":"not_compliant"}', True),
    ({"type": "regex", "name": "verdict", "pattern": "not_compliant"}, '{"verdict":"compliant"}', False),
    ({"type": "regex", "name": "case", "pattern": "DONE", "flags": "i"}, "done", True),
    ({"type": "regex", "name": "absent", "pattern": "bad", "match": "not_contains"}, "good", True),
    ({"type": "regex", "name": "count", "pattern": "x", "match": "count:2"}, "xx", True),
    ({"type": "tool_used", "name": "dispatch", "tool": "Agent"}, "", None),
    ({"type": "tool_order", "name": "order", "before": "Read", "after": "Agent"}, "", None),
])
def test_recorded_report_graders(evals, tmp_path, grader, report, passed):
    result = evals.grade(grader, report, tmp_path)
    assert result.passed is passed
    assert result.reason


def test_file_and_file_exists_graders(evals, tmp_path):
    (tmp_path / "answer.txt").write_text("fixed\n")
    assert evals.grade({"type": "regex", "name": "files", "target": "files", "pattern": "fixed"}, "", tmp_path).passed
    assert evals.grade({"type": "regex", "name": "file", "target": {"source": "file", "path": "answer.txt"}, "pattern": "fixed"}, "", tmp_path).passed
    assert evals.grade({"type": "file_exists", "name": "exists", "path": "answer.txt"}, "", tmp_path).passed
    assert not evals.grade({"type": "file_exists", "name": "missing", "path": "missing.txt"}, "", tmp_path).passed
    assert evals.grade({"type": "file_exists", "name": "absent", "path": "missing.txt", "exists": False}, "", tmp_path).passed


def fake_codex(monkeypatch, tmp_path, report):
    monkeypatch.setenv("CONSORTIUM_CODEX", str(FIXTURES / "fake_codex.py"))
    monkeypatch.setattr(launcher, "CODEX_BIN", str(FIXTURES / "fake_codex.py"))
    record = tmp_path / "codex.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    monkeypatch.setenv("FAKE_CODEX_REPORT", json.dumps(report))
    return record


def test_llm_grader_uses_codex_argv_cheap_tier_and_strict_schema(evals, monkeypatch, tmp_path):
    record = fake_codex(monkeypatch, tmp_path, {"pass": True, "reason": "Matches the criterion."})
    seen = []
    build = launcher.codex_argv
    def capture(run, cwd, rd):
        assert (cwd / ".git").is_dir()
        seen.append((run, json.loads((rd / "schema.json").read_text())))
        return build(run, cwd, rd)
    monkeypatch.setattr(launcher, "codex_argv", capture)
    result = evals.grade({"type": "llm", "name": "pairs", "criteria": "One pair per rule."}, "recorded answer", tmp_path)
    assert result.passed and result.reason == "Matches the criterion."
    run, schema = seen[0]
    assert (run.model, run.effort, run.sandbox) == ("gpt-6-luna", "low", "read-only")
    assert schema == {"type": "object", "properties": {"pass": {"type": "boolean"}, "reason": {"type": "string"}},
                      "required": ["pass", "reason"], "additionalProperties": False}
    assert "recorded answer" in json.loads(record.read_text())["stdin"]


@pytest.mark.parametrize("report,passed", [({"pass": False, "reason": "Missing pair."}, False), ({"pass": "yes", "reason": "Wrong type."}, False)])
def test_llm_rejection_or_malformed_verdict_fails(evals, monkeypatch, tmp_path, report, passed):
    fake_codex(monkeypatch, tmp_path, report)
    assert evals.grade({"type": "llm", "name": "pairs", "criteria": "Pairs."}, "answer", tmp_path).passed is passed


@pytest.mark.parametrize("matches,expected", [(True, 0), (False, 1)])
def test_cli_codex_runs_case_end_to_end(run_cli, monkeypatch, tmp_path, matches, expected):
    report = json.loads(json.dumps(REPORT))
    if not matches:
        report["payload"]["searches"] = []
    fake_codex(monkeypatch, tmp_path, report)
    result = run_cli("eval", "searcher", "--app", "codex")
    assert result.returncode == expected, result.stdout + result.stderr
    assert f"{'PASS' if matches else 'FAIL'} searcher/all-callers codex" in result.stdout
    if not matches:
        assert "definition" in result.stdout
    meta = json.loads(next((paths.state_home() / "runs").glob("*/meta.json")).read_text())
    assert Path(meta["brief"]).parent == SUITE / "searcher/all-callers"


def test_unknown_case_and_bad_runs_do_not_start_models(run_cli):
    result = run_cli("eval", "searcher", "--case", "missing", "--app", "codex")
    assert result.returncode == 2 and "no cases" in result.stderr
    assert run_cli("eval", "searcher", "--runs", "0").returncode == 2


@pytest.mark.parametrize("mode,expected,reason", [("pass", 0, ""), ("fail", 1, "missing caller"), ("error", 1, "timeout"), ("malformed", 1, "JSON"), ("missing", 1, "missing result")])
def test_claude_argv_and_native_json_parsing(run_cli, tmp_path, monkeypatch, mode, expected, reason):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "claude").symlink_to(FIXTURES / "fake_claude_eval.py")
    record = tmp_path / "claude.json"
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_CLAUDE_EVAL_RECORD", str(record))
    monkeypatch.setenv("FAKE_CLAUDE_EVAL_MODE", mode)
    result = run_cli("eval", "searcher", "--app", "claude", "--runs", "2")
    assert result.returncode == expected, result.stdout + result.stderr
    assert f"{'PASS' if expected == 0 else 'FAIL'} searcher/all-callers claude" in result.stdout
    assert reason in result.stdout
    argv = json.loads(record.read_text())["argv"]
    assert argv[:3] == ["plugin", "eval", str(ROOT)]
    for flag in ("--scaffold", "--trust-plugin", "--no-publish", "--keep-temp"):
        assert flag in argv
    for flag, value in (("--case", "all-callers"), ("--runs", "2"), ("--eval-dir", "evals"), ("--ablation", "none"), ("--model", "haiku")):
        assert argv[argv.index(flag) + 1] == value
    for flag in ("--json", "--output-dir"):
        assert not Path(argv[argv.index(flag) + 1]).is_relative_to(ROOT)
    assert "--allow-tools" in argv and "Agent" in argv and "Bash" in argv


def test_default_app_respects_manager_and_all_runs_codex_first(evals, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(evals, "run_case_codex", lambda case: calls.append("codex") or evals.CaseResult(case.name, "codex", []))
    monkeypatch.setattr(evals, "run_cases_claude", lambda agent, cases, runs: calls.append("claude") or 0)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    from consortium.cli import main
    assert main(["eval", "searcher"]) == 0
    assert calls == ["codex"]
    calls.clear()
    assert main(["eval", "searcher", "--app", "all"]) == 0
    assert calls == ["codex", "claude"]
    calls.clear()
    monkeypatch.setenv("CLAUDECODE", "1")
    assert main(["eval", "searcher"]) == 0
    assert calls == ["claude"]


@pytest.mark.parametrize("apps", [["codex"], ["claude", "codex"]])
def test_eval_all_uses_configured_apps_in_order(evals, monkeypatch, apps):
    from consortium.cli import main
    from test_config import write_config
    calls = []
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"apps": apps})
    monkeypatch.setattr(evals, "run_case_codex", lambda case: calls.append("codex") or evals.CaseResult(case.name, "codex", []))
    monkeypatch.setattr(evals, "run_cases_claude", lambda agent, cases, runs: calls.append("claude") or 0)
    assert main(["eval", "searcher", "--app", "all"]) == 0
    assert calls == apps


def test_eval_rejects_both(evals, monkeypatch, capsys):
    from consortium.cli import main
    monkeypatch.setattr(evals, "run_case_codex", lambda case: pytest.fail("Codex must not start"))
    monkeypatch.setattr(evals, "run_cases_claude", lambda *args: pytest.fail("Claude must not start"))
    with pytest.raises(SystemExit) as error:
        main(["eval", "searcher", "--app", "both"])
    assert error.value.code == 2
    assert "invalid choice: 'both'" in capsys.readouterr().err


@pytest.mark.parametrize("inside_plugin", [False, True])
def test_repo_claude_case_uses_temporary_plugin_view(evals, tmp_path, monkeypatch, capsys, inside_plugin):
    case_dir = tmp_path / "host/.consortium/evals/searcher/local"
    shutil.copytree(SUITE / "searcher/all-callers", case_dir)
    data = yaml.safe_load((case_dir / "case.yaml").read_text())
    data["name"] = "local"
    case = evals.Case("searcher", "local", case_dir, data)
    if inside_plugin:
        plugin = tmp_path / "host"
        (plugin / "agents").symlink_to(ROOT / "agents", target_is_directory=True)
        (plugin / ".claude-plugin").symlink_to(ROOT / ".claude-plugin", target_is_directory=True)
        monkeypatch.setattr(evals, "_claude_plugin_root", lambda: plugin)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "claude").symlink_to(FIXTURES / "fake_claude_eval.py")
    record = tmp_path / "record.json"
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_CLAUDE_EVAL_RECORD", str(record))
    assert evals.run_cases_claude("searcher", [case], 1) == 0
    captured = json.loads(record.read_text())
    assert captured["agents_target"] == str((ROOT / "agents").resolve())
    assert captured["evals_target"] == str(case_dir.parents[1])
    assert Path(captured["argv"][2]).is_dir()
    assert "PASS searcher/local claude" in capsys.readouterr().out


def test_failure_reasons_stay_on_one_output_line(evals, capsys):
    evals._print_result("searcher", evals.CaseResult("all-callers", "codex", [
        evals.GraderResult("callers", False, "missing caller\nsecond detail\r\nthird detail")]))
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["FAIL searcher/all-callers codex — callers: missing caller second detail third detail"]


@pytest.mark.parametrize("flag", ["partial", "aborted", "skippedPaidGraders"])
def test_incomplete_native_run_never_passes(evals, flag):
    case = evals.load_cases("searcher", None)[0]
    run = {"graders": [{"name": "matched", "passed": True, "explanation": "ok"}]}
    data = {"cases": [{"name": case.name, "arms": {"with": [run]}, "aggregates": {"score": 1}}]}
    if flag == "partial":
        data[flag] = True
    else:
        run[flag] = True
    assert not evals._claude_result(case, data, 0, 1).passed


def test_file_grader_cannot_read_outside_repo(evals, tmp_path):
    result = evals.grade({"type": "regex", "name": "escape", "target": {"source": "file", "path": "../secret"}, "pattern": "."}, "", tmp_path)
    assert result.passed is False and "escapes repository" in result.reason


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("agent", ["spec-gate", "searcher", "investigator"])
def test_case_path_graders_accept_relative_and_native_absolute_paths(evals, tmp_path, agent, absolute):
    prefix = "/private/tmp/native-eval/home/cwd/repos/sample/" if absolute else ""
    if agent == "spec-gate":
        report = {"payload": {"verdict": "not_compliant", "findings": [{"file": prefix + "shop/pricing.py"}]}}
    elif agent == "searcher":
        report = json.loads(json.dumps(REPORT))
        for match in report["payload"]["searches"][0]["matches"]:
            match["file"] = prefix + match["file"]
    else:
        report = {"payload": {"root_cause": {"file": prefix + "shop/distance.py"},
                              "failing_test": {"file": prefix + "tests/test_missing_origin.py"}}}
    case = evals.load_cases(agent, None)[0]
    for grader in case.data["graders"]:
        if grader["type"] == "regex":
            result = evals.grade(grader, json.dumps(report), tmp_path)
            assert result.passed, f"{grader['name']}: {result.reason}"

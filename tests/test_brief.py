import json
import os
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from consortium.brief import check_brief, parse_brief
from consortium.config import load_settings
from consortium.registry import load_registry, parse_front_matter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures/briefs"
SAMPLE = ROOT / "plugins/consortium/evals/_fixtures/sample-repo"
INCIDENTS = [
    ("missing_test_files.md", "paths-exist"),
    ("premise_without_citation.md", "premises-cited"),
    ("exact_count_stop.md", "no-exact-count-stop"),
    ("python_without_lint.md", "checks-per-language"),
    ("tests_missing_sixth_file.md", "tests-complete"),
    ("dictated_not_verbatim.md", "dictated-verbatim"),
    ("no_forbidden_list.md", "forbidden-and-stop"),
    ("device_without_phone.md", "locks-and-devices"),
    ("write_brief_without_tests_section.md", "structure"),
]


def write_job(repo, name="fixture-writer", mode="worktree-write", capabilities=None):
    front, body = parse_front_matter((Path(__file__).parent / "fixtures/jd/sample-builder.md").read_text())
    front["name"] = name
    front["consortium"].update(mode=mode, capabilities=capabilities or ["read", "search"])
    folder = repo / ".consortium/agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text("---\n" + yaml.safe_dump(front) + "---\n" + body)
    return load_registry(repo)[name]


@pytest.fixture
def sample_repo(tmp_path):
    return shutil.copytree(SAMPLE, tmp_path / "sample")


@pytest.fixture
def writer(sample_repo):
    return write_job(sample_repo)


def findings(text, repo, job, settings=None):
    brief = parse_brief(text)
    return check_brief(brief, job, job.meta["mode"], repo, settings or load_settings(repo, brief.front))


def good_text():
    return (FIXTURES / "good_worktree_write.md").read_text()


@pytest.mark.parametrize("fixture,rule", INCIDENTS)
def test_each_incident_is_refused(fixture, rule, sample_repo, writer):
    if fixture == "device_without_phone.md":
        writer = replace(writer, meta=dict(writer.meta, capabilities=["read", "device"]))
    result = findings((FIXTURES / fixture).read_text(), sample_repo, writer)
    assert {finding.rule for finding in result} == {rule}, result
    if fixture == "missing_test_files.md":
        assert len(result) == 2


@pytest.mark.parametrize("mode", ["read-only", "worktree-write", "operate"])
def test_good_briefs_pass_for_each_mode(mode, sample_repo):
    job = write_job(sample_repo, mode=mode)
    fixture = "good_" + mode.replace("-", "_") + ".md"
    assert findings((FIXTURES / fixture).read_text(), sample_repo, job) == []


def test_parse_brief_normalizes_headings_and_preserves_text():
    text = "---\nagent: fixture-reader\n---\n## TASK:\nRead.\n## Scope\n```md\n## Not a section\n```\n## Report:\nfindings.v1\n"
    brief = parse_brief(text)
    assert brief.front == {"agent": "fixture-reader"}
    assert brief.text == text
    assert brief.sections == {"task": "Read.", "scope": "```md\n## Not a section\n```", "report": "findings.v1"}


def test_create_lines_are_exempt_from_paths_exist(sample_repo, writer):
    text = good_text() + "\n- create: `shop/new.py`\n- gone: `shop/removed.py`\n"
    assert findings(text, sample_repo, writer) == []


def test_non_paths_are_ignored(sample_repo, writer):
    text = good_text() + "\n`https://example.invalid/doc.md` `~/private.py` `$ROOT/file.py` `--flag/path.py` " \
        "`shop/*.py` `shop/?.py` `shop/{file}.py` `<file>.py` `a|b.py` `a;b.py` `pytest tests/missing.py`\n"
    assert findings(text, sample_repo, writer) == []


@pytest.mark.parametrize("line", [
    "expect about 6, report the real number",
    "expect about 6 failures, stop if the helper raises",
    "expect ~6 failures, STOP on an unrelated error",
    "expect roughly three failures, halt if blocked",
    "expect approximately 6 failures, abort if blocked",
])
def test_about_n_is_not_an_exact_count(line, sample_repo, writer):
    assert findings(good_text() + "\n" + line, sample_repo, writer) == []


@pytest.mark.parametrize("line", ["STOP at 6 failures", "Must be three failures; halt.", "Expect failures; abort."])
def test_exact_count_stop_forms(line, sample_repo, writer):
    assert {f.rule for f in findings(good_text() + "\n" + line, sample_repo, writer)} == {"no-exact-count-stop"}


@pytest.mark.parametrize("citation,passes", [
    ("shop/distance.py:4-5", True), ("shop/distance.py:4", True),
    ("shop/distance.py:0", False), ("shop/distance.py:999", False),
    ("shop/distance.py:4-999", False), ("shop/distance.py:5-4", False),
])
def test_premise_citations_require_valid_lines(citation, passes, sample_repo, writer):
    text = good_text().replace("`shop/distance.py:4`", citation)
    result = findings(text, sample_repo, writer)
    assert ({f.rule for f in result} == set()) is passes
    if not passes:
        assert {f.rule for f in result} == {"premises-cited"}


def test_none_premises_and_no_tests_reason(sample_repo, writer):
    text = good_text().replace("The helper is defined at `shop/distance.py:4`.", "none")
    start, rest = text.split("## Tests\n", 1)
    _, end = rest.split("## Done means", 1)
    text = start + "## Tests\nnone — only documentation changes.\n\n## Done means" + end
    assert findings(text, sample_repo, writer) == []
    assert {f.rule for f in findings(text.replace("none — only documentation changes.", "none"), sample_repo, writer)} == {"tests-complete"}


@pytest.mark.parametrize("section", ["Tests", "Context", "Report"])
def test_empty_required_sections_are_structure_findings(section, sample_repo, writer):
    brief = parse_brief(good_text())
    brief.sections[section.lower()] = "\n  "
    assert "structure" in {f.rule for f in check_brief(brief, writer, "worktree-write", sample_repo, load_settings(sample_repo))}


def test_report_schema_and_alternatives(sample_repo, writer):
    assert {f.rule for f in findings(good_text().replace("findings.v1", "other.v1"), sample_repo, writer)} == {"structure"}
    writer = replace(writer, meta=dict(writer.meta, alt_reports=["other.v1"]))
    assert findings(good_text().replace("findings.v1", "other.v1"), sample_repo, writer) == []
    assert {f.rule for f in findings(good_text().replace("findings.v1", "findings.v10"), sample_repo, writer)} == {"structure"}


def test_report_schema_may_end_a_sentence(sample_repo, writer):
    text = good_text().replace("Return findings.v1 with changes and evidence.", "Return findings.v1.")
    assert findings(text, sample_repo, writer) == []


def test_check_placeholder_needs_an_argument(sample_repo, writer):
    text = good_text().replace("`pytest tests`", "`pytest `")
    assert {f.rule for f in findings(text, sample_repo, writer)} == {"checks-per-language"}


def test_python_auto_finds_a_shared_make_target(sample_repo, writer):
    (sample_repo / "Makefile").write_text("lint test:\n\ttrue\n")
    assert findings(good_text(), sample_repo, writer) == []


def test_worktree_paths_and_searches_use_front_matter(sample_repo, writer, tmp_path):
    worktree = shutil.copytree(SAMPLE, tmp_path / "other-worktree")
    (worktree / "tests/test_notify.py").unlink()
    text = good_text().replace("agent: fixture-writer", f"agent: fixture-writer\nworktree: {worktree}")
    text = text.replace("- `tests/test_notify.py`\n", "")
    assert findings(text, sample_repo, writer) == []


def test_missing_found_by_and_missing_search_result(sample_repo, writer):
    text = good_text().replace("found by: `rg -l distance_km tests`", "Tests were searched.")
    assert {f.rule for f in findings(text, sample_repo, writer)} == {"tests-complete"}
    text = good_text().replace("- `tests/test_notify.py`\n", "") + "\n## Notes\n`tests/test_notify.py` is mentioned elsewhere.\n"
    assert {f.rule for f in findings(text, sample_repo, writer)} == {"tests-complete"}


def test_found_by_rerun_times_out_quietly(sample_repo, writer, tmp_path, monkeypatch):
    commands = tmp_path / "commands"
    commands.mkdir()
    command = commands / "rg"
    command.write_text("#!/bin/sh\nexec sleep 30\n")
    command.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ["PATH"])
    start = time.monotonic()
    result = findings(good_text(), sample_repo, writer)
    assert time.monotonic() - start < 13
    assert len(result) == 1 and result[0].rule == "tests-complete"
    assert "could not rerun" in result[0].message


def test_search_commands_do_not_execute_shell_syntax(sample_repo, writer):
    text = good_text().replace("rg -l distance_km tests", "rg -l distance_km tests; touch injected")
    assert {f.rule for f in findings(text, sample_repo, writer)} == {"tests-complete"}
    assert not (sample_repo / "injected").exists()


def test_raw_commands_and_named_device(sample_repo, writer):
    writer = replace(writer, meta=dict(writer.meta, capabilities=["device"]))
    text = good_text().replace("agent: fixture-writer", "agent: fixture-writer\ndevice: simulator-1")
    assert findings(text, sample_repo, writer) == []
    settings = load_settings(sample_repo)
    settings.values["brief"]["raw_commands"] = [r"\bdocker compose\b"]
    result = findings(text + "\nRun `docker compose up`.\n", sample_repo, writer, settings)
    assert {f.rule for f in result} == {"locks-and-devices"}


@pytest.mark.parametrize("language,extension,commands,setup", [
    ("python", ".py", "ruff check .\npytest tests", "no-make"),
    ("dart", ".dart", "dart analyze\ndart test tests", "dart"),
    ("dart", ".dart", "flutter analyze\nflutter test tests", "flutter"),
    ("javascript", ".tsx", "npm run lint\nnpm test -- tests", "js-lint"),
    ("javascript", ".js", "npm test -- tests", "js"),
])
def test_auto_checks(language, extension, commands, setup, sample_repo, writer):
    source = "shop/subject" + extension
    (sample_repo / source).write_text("fixture\n")
    if setup == "no-make":
        (sample_repo / "Makefile").unlink()
    if setup in {"dart", "flutter"}:
        (sample_repo / "pubspec.yaml").write_text("name: fixture\n" + ("dependencies:\n  flutter:\n    sdk: flutter\n" if setup == "flutter" else ""))
    if setup.startswith("js"):
        (sample_repo / "package.json").write_text(json.dumps({"scripts": {"lint": "eslint ."} if setup == "js-lint" else {}}))
    text = good_text().replace("`shop/distance.py`", f"`{source}`")
    text = text.replace("Run `make lint` and `pytest tests`.", commands)
    assert findings(text, sample_repo, writer) == []
    first = commands.splitlines()[0]
    assert {f.rule for f in findings(text.replace(first, "omitted"), sample_repo, writer)} == {"checks-per-language"}


def test_configured_checks_and_word_numbers(sample_repo, writer):
    settings = load_settings(sample_repo)
    settings.values["checks"]["python"] = ["custom-lint", "custom-test {tests}"]
    settings.values["brief"]["word_numbers"] += ["dozen"]
    text = good_text().replace("Run `make lint` and `pytest tests`.", "Run `custom-lint` and `custom-test tests/test_distance.py`.")
    assert findings(text, sample_repo, writer, settings) == []
    assert {f.rule for f in findings(text + "\na dozen failures: STOP\n", sample_repo, writer, settings)} == {"no-exact-count-stop"}


def test_cli_exit_codes(run_cli, sample_repo):
    subprocess.run(["git", "init", "-q", str(sample_repo)], check=True)
    write_job(sample_repo)
    good = run_cli("brief-check", str(FIXTURES / "good_worktree_write.md"), "--repo", str(sample_repo))
    bad = run_cli("brief-check", str(FIXTURES / "missing_test_files.md"), "--repo", str(sample_repo))
    assert (good.returncode, good.stdout, good.stderr) == (0, "", "")
    assert bad.returncode == 1 and "paths-exist:" in bad.stdout and bad.stderr == ""


def test_cli_json_agent_override_and_cwd_repo(run_cli, sample_repo):
    subprocess.run(["git", "init", "-q", str(sample_repo)], check=True)
    write_job(sample_repo, name="fixture-override")
    result = run_cli("brief-check", str(FIXTURES / "missing_test_files.md"), "--agent", "fixture-override", "--json", cwd=sample_repo)
    assert result.returncode == 1, result.stderr
    assert {finding["rule"] for finding in json.loads(result.stdout)} == {"paths-exist"}


def test_cli_stdin_passes_front_matter_to_resolver(run_cli, sample_repo):
    write_job(sample_repo)
    text = good_text().replace("agent: fixture-writer", "agent: fixture-writer\nreport: invalid.v1")
    result = subprocess.run([str(ROOT / "bin/consortium"), "brief-check", "-", "--repo", str(sample_repo)],
                            input=text, text=True, capture_output=True, timeout=60)
    assert result.returncode == 2
    assert "not listed in alt_reports" in result.stderr
    result = subprocess.run([str(ROOT / "bin/consortium"), "brief-check", "-", "--repo", str(sample_repo), "--json"],
                            input=good_text(), text=True, capture_output=True, timeout=60)
    assert (result.returncode, json.loads(result.stdout)) == (0, [])


def test_cli_repo_is_used_as_given(run_cli, sample_repo):
    subprocess.run(["git", "init", "-q", str(sample_repo)], check=True)
    nested = shutil.copytree(SAMPLE, sample_repo / "nested")
    write_job(sample_repo)
    (sample_repo / "shop/distance.py").unlink()
    result = run_cli("brief-check", str(FIXTURES / "good_worktree_write.md"), "--repo", str(nested))
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize("case", ["not-ready", "unknown", "missing-agent", "missing-file", "bad-yaml"])
def test_cli_usage_errors(run_cli, sample_repo, tmp_path, case):
    folder = sample_repo / ".consortium/agents"
    folder.mkdir(parents=True)
    (folder / "fixture-legacy.md").write_text("---\nname: fixture-legacy\n---\nLegacy agent.\n")
    brief = tmp_path / "brief.md"
    brief.write_text(good_text())
    args = ["--agent", "fixture-legacy"]
    if case == "unknown":
        args = ["--agent", "fixture-unknown"]
    elif case == "missing-agent":
        args = []
        brief.write_text(good_text().replace("agent: fixture-writer\n", ""))
    elif case == "missing-file":
        brief.unlink()
    elif case == "bad-yaml":
        brief.write_text("---\nagent: [\n---\n")
    result = run_cli("brief-check", str(brief), "--repo", str(sample_repo), *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stderr and "Traceback" not in result.stderr
    if case == "not-ready":
        assert "fixture-legacy has no consortium: block; it belongs to the old workflow" in result.stderr


def test_a_read_only_brief_needs_no_language_checks(sample_repo):
    reader = write_job(sample_repo, name="fixture-reader", mode="read-only")
    text = (FIXTURES / "good_read_only.md").read_text()
    text = text.replace("## Done means\nName the checks `make lint` and `pytest tests` in the review.\n\n", "")
    assert "## Done means" not in text and "`shop/distance.py`" in text
    assert findings(text, sample_repo, reader) == []


def test_created_scope_files_still_need_their_language_checks(sample_repo, writer):
    text = good_text().replace("- `shop/distance.py`", "- create: `shop/rates.py`")
    assert findings(text, sample_repo, writer) == []
    text = text.replace("Run `make lint` and `pytest tests`.", "Run `pytest tests`.")
    assert {f.rule for f in findings(text, sample_repo, writer)} == {"checks-per-language"}


def test_searches_that_can_run_programs_are_not_rerun(sample_repo, writer):
    marker = sample_repo / "ran"
    script = sample_repo / "pre.sh"
    script.write_text(f"#!/bin/sh\ntouch {marker}\ncat \"$1\"\n")
    script.chmod(0o755)
    text = good_text().replace("rg -l distance_km tests", "rg --pre ./pre.sh -l distance_km tests")
    result = findings(text, sample_repo, writer)
    assert [(f.rule, f.message) for f in result] == [
        ("tests-complete", "could not rerun: rg --pre ./pre.sh -l distance_km tests"),
    ]
    assert not marker.exists()


def test_a_report_of_none_needs_no_schema_name(sample_repo, writer):
    writer = replace(writer, meta=dict(writer.meta, report="none", alt_reports=[]))
    text = good_text().replace("Return findings.v1 with changes and evidence.", "Markdown: status, changes, checks.")
    assert findings(text, sample_repo, writer) == []

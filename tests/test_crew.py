import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from consortium import paths
from consortium.config import load_settings
from consortium.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins/consortium"
READY_AGENTS = ("spec-gate", "security-reviewer", "infra-reviewer", "device-qa", "code-reviewer")


def write_job(folder, name, *, ready=True):
    folder.mkdir(parents=True, exist_ok=True)
    front = {"name": name, "description": "A fixture check."}
    if ready:
        front["consortium"] = {
            "version": 1, "station": "check", "mode": "read-only", "tier": "standard", "report": "none",
        }
    (folder / f"{name}.md").write_text(f"---\n{yaml.safe_dump(front)}---\nFixture instructions.\n")


@pytest.fixture
def crew_package(tmp_path, monkeypatch):
    package = tmp_path / "package"
    package.mkdir()
    shutil.copyfile(PACKAGE / "defaults.yaml", package / "defaults.yaml")
    for name in READY_AGENTS:
        write_job(package / "job-descriptions", name)
    # Legacy descriptions are present but do not count as available.
    for name in ("surface-reviewer", "bar-raiser"):
        write_job(package / "job-descriptions", name, ready=False)
    monkeypatch.setattr(paths, "package_root", lambda: package)
    return package


@pytest.fixture
def settings(crew_package):
    return load_settings(None)


@pytest.fixture
def registry(crew_package):
    return load_registry(None)


@pytest.fixture
def run_cli(crew_package):
    # A subprocess needs its own fixture package: it cannot inherit monkeypatch.
    shutil.copytree(PACKAGE / "lib", crew_package / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PACKAGE / "bin", crew_package / "bin")

    def run(*args, env=None, cwd=None):
        return subprocess.run(
            [str(crew_package / "bin/consortium"), *args],
            cwd=cwd or crew_package,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {})),
            capture_output=True, text=True, timeout=60,
        )

    return run


def test_small_tooling_change_gets_no_reviewers(settings, registry):
    from consortium.crew import CrewItem, change_from_files, size_crew

    result = size_crew(change_from_files(["scripts/tool.py"], 100), settings, registry)
    assert result.lines == 100
    assert result.ceiling == "normal"
    assert result.flags == result.crew == result.gates == result.capped == []
    assert result.always == [
        CrewItem("implementer", "its own tests"), CrewItem("ci-gate", "the full test, run by consortium gate"),
    ]


def test_always_does_not_depend_on_registry(settings):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["scripts/tool.py"], None), settings, {})
    assert [item.agent for item in result.always] == ["implementer", "ci-gate"]
    assert result.crew == result.gates == []


@pytest.mark.parametrize("option", [{"dictated": True}, {"implementers": 2}])
def test_dictated_value_adds_spec_gate(settings, registry, option):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["scripts/tool.py"], 10), settings, registry, **option)
    assert [item.agent for item in result.crew] == ["spec-gate"]
    assert result.crew[0].why


def test_two_implementers_add_spec_gate(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files([], 0), settings, registry, implementers=2, dictated=True)
    assert [item.agent for item in result.crew] == ["spec-gate"]


@pytest.mark.parametrize("file,flag,agent", [
    ("auth/session.py", "auth", "security-reviewer"),
    ("src/auth/session.py", "auth", "security-reviewer"),
    ("src/signing_keys.py", "crypto", "security-reviewer"),
    ("src/privacy/profile.py", "pii", "security-reviewer"),
    ("src/parsers/input.py", "input", "security-reviewer"),
    ("infra/main.tf", "infra", "infra-reviewer"),
])
def test_auth_path_adds_security_reviewer(settings, registry, file, flag, agent):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files([file], 1), settings, registry)
    assert [item.agent for item in result.crew] == [agent]
    assert [name for name, why in result.flags if why] == [flag]
    assert file in result.flags[0][1]


@pytest.mark.parametrize("word,flag", [
    ("PASSWORD", "auth"), ("Jwt", "auth"), ("encrypt", "crypto"),
    ("date_of_birth", "pii"), ("deserialize", "input"),
])
def test_auth_keyword_adds_security_reviewer(settings, registry, word, flag):
    from consortium.crew import Change, size_crew

    change = Change(["src/service.py"], {"src/service.py": [f"value = '{word}'"]}, 1, [])
    result = size_crew(change, settings, registry)
    assert [item.agent for item in result.crew] == ["security-reviewer"]
    assert [name for name, why in result.flags if why] == [flag]
    assert "src/service.py" in result.flags[0][1]


def test_keyword_fragments_do_not_trigger_flags(settings, registry):
    from consortium.crew import Change, size_crew

    change = Change(["src/service.py"], {"src/service.py": ["passwordless jwt_token encrypting unpickle"]}, 1, [])
    assert size_crew(change, settings, registry).flags == []


def test_ci_file_adds_infra_reviewer(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files([".github/workflows/test.yml"], 1), settings, registry)
    assert [item.agent for item in result.crew] == ["infra-reviewer"]
    assert [name for name, _ in result.flags] == ["ci"]


def test_ui_file_adds_device_qa(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["src/components/Button.tsx"], 1), settings, registry)
    assert [item.agent for item in result.crew] == ["device-qa"]


@pytest.mark.parametrize("lines,agents", [
    (0, []), (199, []), (200, []), (500, []), (800, []), (801, ["code-reviewer"]),
])
def test_over_800_lines_adds_code_reviewer(settings, registry, lines, agents):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["scripts/tool.py"], lines), settings, registry)
    assert [item.agent for item in result.crew] == agents


def test_new_module_adds_code_reviewer(settings, registry):
    from consortium.crew import Change, size_crew

    change = Change(["src/example/__init__.py"], {}, 0, ["src/example/__init__.py"])
    assert [item.agent for item in size_crew(change, settings, registry).crew] == ["code-reviewer"]
    change.new_files.clear()
    assert size_crew(change, settings, registry).crew == []


@pytest.mark.parametrize("line", ["@app.get('/health')", 'router.post("/items", handler)'])
def test_new_route_adds_code_reviewer(settings, registry, line):
    from consortium.crew import Change, size_crew

    change = Change(["src/routes.py"], {"src/routes.py": [line]}, 1, [])
    assert [item.agent for item in size_crew(change, settings, registry).crew] == ["code-reviewer"]


def test_explicit_new_api_adds_code_reviewer(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files([], None), settings, registry, new_api=True)
    assert [item.agent for item in result.crew] == ["code-reviewer"]


@pytest.mark.parametrize("agents", [{}, None])
def test_schema_change_stops_at_a_manager_gate(settings, registry, agents):
    from consortium.crew import CrewItem, change_from_files, size_crew

    result = size_crew(change_from_files(["db/migrations/0001_init.sql"], 10), settings,
                       registry if agents is None else agents)
    assert result.crew == []
    assert result.gates == [CrewItem("bar-raiser", "manager gate: bar-raiser is not available yet")]


def test_surface_change_stops_at_a_manager_gate(settings, registry):
    from consortium.crew import CrewItem, change_from_files, size_crew

    result = size_crew(change_from_files(["src/models/item.py"], 10), settings, registry)
    assert result.gates == [CrewItem("surface-reviewer", "manager gate: surface-reviewer is not available yet")]


def test_hard_to_undo_adds_bar_raiser(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files([], None), settings, registry, hard_to_undo=True)
    assert [item.agent for item in result.gates] == ["bar-raiser"]


def test_lean_lists_capped_checks(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["src/auth/login.py"], 801), settings, registry,
                       dictated=True, ceiling="lean")
    assert [item.agent for item in result.crew] == ["spec-gate"]
    assert [item.agent for item in result.capped] == ["security-reviewer", "code-reviewer"]
    assert all("lean" in item.why and ":" in item.why for item in result.capped)


def test_lean_does_not_drop_missing_manager_gates(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["db/migrations/0001.sql"], 1), settings, registry, ceiling="lean")
    assert [item.agent for item in result.gates] == ["bar-raiser"]


def test_full_adds_code_reviewer(settings, registry):
    from consortium.crew import change_from_files, size_crew

    result = size_crew(change_from_files(["scripts/tool.py"], 10), settings, registry, ceiling="full")
    assert [item.agent for item in result.crew] == ["code-reviewer"]


def test_multiple_risks_keep_flags_without_duplicate_reviewers(settings, registry):
    from consortium.crew import Change, size_crew

    change = Change(["auth/crypto/key.py"], {"auth/crypto/key.py": ["password = encrypt(value)"]}, 900, [])
    result = size_crew(change, settings, registry)
    assert [name for name, _ in result.flags] == ["auth", "crypto"]
    assert [item.agent for item in result.crew] == ["security-reviewer", "code-reviewer"]
    assert "auth" in result.crew[0].why and "crypto" in result.crew[0].why


def test_repo_plus_globs_extend_a_flag(tmp_path, crew_package, registry):
    from consortium.crew import change_from_files, size_crew

    repo = tmp_path / "repo"
    (repo / ".consortium").mkdir(parents=True)
    (repo / ".consortium/config.yaml").write_text('risk:\n  auth: ["+src/shared/authz/**"]\n')
    settings = load_settings(repo)
    for file in ("src/shared/authz/check.py", "src/auth/check.py"):
        result = size_crew(change_from_files([file], 10), settings, registry)
        assert [item.agent for item in result.crew] == ["security-reviewer"]


def test_settings_control_thresholds_ceiling_and_patterns(tmp_path, crew_package, registry):
    from consortium.crew import Change, size_crew

    repo = tmp_path / "repo"
    (repo / ".consortium").mkdir(parents=True)
    (repo / ".consortium/config.yaml").write_text(yaml.safe_dump({
        "ceiling": "full", "thresholds": {"code_reviewer_lines": 12},
        "module_markers": ["module.marker"], "api_patterns": ["^PUBLIC "],
    }))
    settings = load_settings(repo)
    change = Change(["src/service.py"], {}, 13, [])
    assert [item.agent for item in size_crew(change, settings, registry, ceiling="normal").crew] == ["code-reviewer"]
    change = Change(["module.marker"], {}, 0, ["module.marker"])
    assert [item.agent for item in size_crew(change, settings, registry, ceiling="normal").crew] == ["code-reviewer"]
    change = Change(["src/service.py"], {"src/service.py": ["PUBLIC endpoint"]}, 1, [])
    assert [item.agent for item in size_crew(change, settings, registry, ceiling="normal").crew] == ["code-reviewer"]
    change = Change([], {}, 0, [])
    assert size_crew(change, settings, registry).ceiling == "full"
    assert size_crew(change, settings, registry, ceiling="normal").crew == []


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        check=True, capture_output=True, text=True,
    ).stdout


def make_diff_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "service.py").write_text("password = 'old'\nkeep = 1\n")
    (repo / "remove.py").write_text("old = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "baseline")
    (repo / "service.py").write_text("keep = 1\n@app.get('/health')\n")
    (repo / "remove.py").unlink()
    (repo / "module").mkdir()
    (repo / "module/__init__.py").touch()
    (repo / "notes\twith space.txt").write_text("plain text\n")
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")
    return repo


def test_from_a_real_diff(tmp_path, settings, registry, run_cli):
    from consortium.crew import change_from_diff, size_crew

    repo = make_diff_repo(tmp_path)
    change = change_from_diff(repo, "HEAD~1..HEAD")
    assert set(change.files) == {"service.py", "remove.py", "module/__init__.py", "notes\twith space.txt", "blob.bin"}
    assert change.lines_changed == 4  # one removed + one added, one deleted, one new text line
    assert set(change.new_files) == {"module/__init__.py", "notes\twith space.txt", "blob.bin"}
    assert change.added_lines["service.py"] == ["@app.get('/health')"]
    assert change.added_lines["notes\twith space.txt"] == ["plain text"]
    result = size_crew(change, settings, registry)
    assert result.flags == []  # removed keywords do not count
    assert [item.agent for item in result.crew] == ["code-reviewer"]
    result = run_cli("checks", "--diff", "HEAD~1..HEAD", "--json", "--repo", str(repo))
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["lines"] == 4
    assert [item["agent"] for item in data["crew"]] == ["code-reviewer"]


@pytest.mark.parametrize("file", [
    "notes with space.txt", "trailing space.txt ", "trailing tab.txt\t", "notes\nwith newline.txt", "unicodé.txt",
])
def test_diff_preserves_added_line_paths(tmp_path, file):
    from consortium.crew import change_from_diff

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "commit", "--allow-empty", "-qm", "baseline")
    (repo / file).write_text("password = value\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "change")
    change = change_from_diff(repo, "HEAD~1..HEAD")
    assert change.files == change.new_files == [file]
    assert change.added_lines == {file: ["password = value"]}


def test_json_output_shape(run_cli):
    result = run_cli("checks", "--files", "scripts/tool.py", "--lines", "100", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ceiling": "normal", "lines": 100, "flags": [],
        "always": [
            {"agent": "implementer", "why": "its own tests"},
            {"agent": "ci-gate", "why": "the full test, run by consortium gate"},
        ], "crew": [], "gates": [], "capped": [],
    }
    assert result.stderr == ""


def test_cli_manager_gate_text_and_explicit_options(run_cli):
    result = run_cli("checks", "--files", "db/migrations/0001_init.sql", "--lines", "10")
    assert result.returncode == 0, result.stderr
    assert "manager gate: bar-raiser is not available yet" in result.stdout
    result = run_cli("checks", "--files", "scripts/tool.py", "--implementers", "2", "--dictated",
                     "--hard-to-undo", "--new-api", "--ceiling", "lean", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert [item["agent"] for item in data["crew"]] == ["spec-gate"]
    assert [item["agent"] for item in data["capped"]] == ["code-reviewer"]
    assert [item["agent"] for item in data["gates"]] == ["bar-raiser"]


@pytest.mark.parametrize("args", [
    [], ["--diff", "HEAD", "--files", "tool.py"], ["--files", "tool.py", "--lines", "-1"],
    ["--files", "tool.py", "--implementers", "0"], ["--diff", "HEAD", "--lines", "10"],
])
def test_cli_rejects_invalid_arguments(run_cli, args):
    result = run_cli("checks", *args)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_cli_reports_bad_diff_and_configuration(run_cli, tmp_path):
    repo = make_diff_repo(tmp_path)
    result = run_cli("checks", "--diff", "missing..HEAD", "--repo", str(repo))
    assert result.returncode == 1
    assert "diff" in result.stderr and "Traceback" not in result.stderr
    (repo / ".consortium").mkdir()
    (repo / ".consortium/config.yaml").write_text("risk: []\n")
    result = run_cli("checks", "--files", "tool.py", "--repo", str(repo))
    assert result.returncode == 1
    assert "risk" in result.stderr and "Traceback" not in result.stderr

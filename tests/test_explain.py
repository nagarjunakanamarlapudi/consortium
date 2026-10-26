import json
import os
import re
import sys
from pathlib import Path

import pytest

from test_cli import make_repo
from test_config import write_config
from test_registry import write_job


def explain_repo(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents")
    return repo


def text_row(output, label):
    line = next(line for line in output.splitlines() if re.match(rf"  {re.escape(label)}  ", line))
    return re.split(r" {2,}", line.strip())


def test_explain_text_names_each_source(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"app": ["codex"], "agents": {"repo-reader": {"tier": "deep"}}})
    result = run_cli("explain", "repo-reader", "--repo", str(repo))
    assert result.returncode == 0, result.stderr
    state = Path(os.environ["CONSORTIUM_HOME"])
    assert result.stdout.startswith("repo-reader: a repo-only agent, read-only, as seen with no manager\n")
    assert text_row(result.stdout, "tier") == ["tier", "deep", "you", f"{state}/config.yaml: agents.repo-reader.tier"]
    assert text_row(result.stdout, "model") == ["model", "gpt-6.1-sol", "default", "<plugin>/defaults.yaml: tiers.deep.codex.model"]
    assert text_row(result.stdout, "effort") == ["effort", "xhigh", "default", "<plugin>/defaults.yaml: tiers.deep.codex.effort"]
    assert text_row(result.stdout, "version") == ["version", "2", "repo", ".consortium/agents/repo-reader.md: consortium.version"]
    assert text_row(result.stdout, "allowed apps") == ["allowed apps", "codex", "you", f"{state}/config.yaml: app"]
    assert text_row(result.stdout, "sandbox") == ["sandbox", "read-only", "repo", ".consortium/agents/repo-reader.md: consortium.mode"]
    assert text_row(result.stdout, "timeout")[1] == "60 min"
    assert text_row(result.stdout, "locks")[1] == "none"
    assert result.stderr == ""


def test_explain_json_has_every_agentrun_field(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    result = run_cli("explain", "repo-reader", "--json", "--manager", "codex", cwd=repo)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data) == {
        "name", "version", "app", "allowed_apps", "tier", "model", "effort", "mode", "write_scope", "sandbox", "capabilities",
        "locks", "timeout_minutes", "report", "alt_reports", "notes", "sources",
    }
    assert (data["app"], data["model"]) == ("codex", "gpt-6.1-sol")
    assert data["allowed_apps"] == ["codex", "claude"]
    assert data["sources"]["allowed_apps"] == data["sources"]["app"]


def test_explain_global_settings_with_sources(run_cli, tmp_path):
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"app": ["codex"]})
    result = run_cli("explain", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    state = Path(os.environ["CONSORTIUM_HOME"])
    assert f"Set by you, in {state}/config.yaml" in result.stdout
    assert text_row(result.stdout, "app") == ["app", "[codex]"]
    assert "thresholds.reviewers_min_lines" not in result.stdout
    result = run_cli("explain", "--all", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "app") == ["app", "you", "[codex]"]
    assert text_row(result.stdout, "thresholds.reviewers_min_lines") == ["thresholds.reviewers_min_lines", "default", "200"]
    assert text_row(result.stdout, "gate.timeout_minutes") == ["gate.timeout_minutes", "default", "120"]
    assert text_row(result.stdout, "you") == ["you", f"{state}/config.yaml", "1 setting"]
    assert text_row(result.stdout, "default") == ["default", "<plugin>/defaults.yaml"]
    result = run_cli("explain", "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["values"]["app"] == ["codex"]
    assert data["sources"]["app"] == "user"


def test_explain_old_workflow_exits_one(run_cli):
    result = run_cli("explain", "bar-raiser")
    assert result.returncode == 1
    assert "bar-raiser has no consortium: block; it belongs to the old workflow" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_explain_prompt_notes_and_brief(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    write_config(repo / ".consortium", {"agents": {"repo-reader": {"notes": ["Read the conventions."]}}})
    brief = repo / "brief.md"
    brief.write_text("---\nmodel: one-job-model\nreport: locations.v1\n---\n\nDo this task.\n")
    result = run_cli("explain", "repo-reader", "--manager", "codex", "--brief", str(brief), "--json", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["model"] == "one-job-model"
    result = run_cli("explain", "repo-reader", "--manager", "codex", "--prompt", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert "# You are the repo-reader agent" in result.stdout
    assert "## Your brief\n\n## Your report" in result.stdout
    result = run_cli("explain", "repo-reader", "--manager", "codex", "--notes", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Notes from this repo\n- Read the conventions.\n"


def test_explain_reads_a_full_brief(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    brief = repo / "brief.md"
    brief.write_text(
        f"---\nagent: repo-reader\nworktree: {repo}\ndictated: [v1]\napp: [codex]\ntier: deep\n---\n\n## Task\n\nRead.\n"
    )
    result = run_cli("explain", "repo-reader", "--brief", str(brief), "--json", cwd=repo)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert (data["app"], data["tier"], data["model"]) == ("codex", "deep", "gpt-6.1-sol")
    result = run_cli("explain", "--brief", str(brief), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert "worktree.dir" not in result.stdout
    assert text_row(result.stdout, "brief") == ["brief", "brief.md", "2 settings"]
    assert "Set by this brief, in brief.md" in result.stdout
    assert text_row(result.stdout, "tier") == ["tier", "deep"]
    assert text_row(result.stdout, "app") == ["app", "[codex]"]
    assert text_row(result.stdout, "repo-reader (repo agent)")[2:6] == ["codex (brief)", "deep (brief)", "gpt-6.1-sol", "xhigh"]


def test_explain_config_error_exits_one(run_cli, tmp_path):
    state = Path(os.environ["CONSORTIUM_HOME"])
    state.mkdir()
    (state / "config.yaml").write_text("risk: []\n")
    result = run_cli("explain", cwd=tmp_path)
    assert result.returncode == 1
    assert "risk" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_repo_agent_sources_point_to_the_job_until_patched(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    result = run_cli("explain", "repo-reader", "--manager", "codex", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "tier") == ["tier", "standard", "repo", ".consortium/agents/repo-reader.md: consortium.tier"]
    assert text_row(result.stdout, "app") == ["app", "codex", "repo", ".consortium/agents/repo-reader.md: consortium.app"]
    assert text_row(result.stdout, "allowed apps") == ["allowed apps", "codex, claude", "repo", ".consortium/agents/repo-reader.md: consortium.app"]
    write_config(repo / ".consortium", {"app": ["claude"], "agents": {"repo-reader": {"tier": "deep"}}})
    result = run_cli("explain", "repo-reader", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "tier") == ["tier", "deep", "repo", ".consortium/config.yaml: agents.repo-reader.tier"]
    assert text_row(result.stdout, "app") == ["app", "claude", "repo", ".consortium/config.yaml: app"]
    assert text_row(result.stdout, "allowed apps") == ["allowed apps", "claude", "repo", ".consortium/config.yaml: app"]


def test_explain_append_names_both_repo_job_and_config(run_cli, tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents", locks=["test-stack"])
    write_config(repo / ".consortium", {"agents": {"repo-reader": {"locks": ["+disk"]}}})
    result = run_cli("explain", "repo-reader", "--manager", "codex", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "locks") == [
        "locks", "test-stack, disk", "repo + repo",
        ".consortium/agents/repo-reader.md: consortium.locks + .consortium/config.yaml: agents.repo-reader.locks",
    ]


def test_overview_lists_agents_overrides_and_layer_counts(run_cli, tmp_path):
    from consortium.registry import load_registry

    repo = explain_repo(tmp_path)
    state = Path(os.environ["CONSORTIUM_HOME"])
    write_config(state, {"app": ["codex"], "agents": {"device-qa": {"tier": "cheap"}, "investigator": {"effort": "low"}}})
    write_config(repo / ".consortium", {
        "gate": {"command": "make ci-test", "locks": ["test-stack"]},
        "agents": {"implementer": {"model": "a-model-name-that-must-never-be-truncated"}},
    })
    result = run_cli("explain", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"Consortium settings in {repo}, as seen with no manager\n")
    assert "Layers, a later one winning" in result.stdout
    assert text_row(result.stdout, "you") == ["you", f"{state}/config.yaml", "3 settings"]
    assert text_row(result.stdout, "repo") == ["repo", ".consortium/config.yaml", "3 settings"]
    assert text_row(result.stdout, "device-qa")[2:4] == ["codex (you)", "cheap (you)"]
    assert text_row(result.stdout, "investigator")[5] == "low (you)"
    assert text_row(result.stdout, "implementer")[4] == "a-model-name-that-must-never-be-truncated (repo)"
    assert text_row(result.stdout, "repo-reader (repo agent)")[2:6] == ["codex (you)", "standard", "gpt-6.1-sol", "medium"]
    assert "(you), (repo) and (brief)" in result.stdout
    assert "Old workflow, not shown: bar-raiser" in result.stdout
    assert f"Set by you, in {state}/config.yaml" in result.stdout
    assert "Set by this repo, in .consortium/config.yaml" in result.stdout
    assert text_row(result.stdout, "agents.device-qa.tier") == ["agents.device-qa.tier", "cheap"]
    assert text_row(result.stdout, "gate.command") == ["gate.command", "make ci-test"]
    assert text_row(result.stdout, "gate.locks") == ["gate.locks", "[test-stack]"]
    assert "Every setting: consortium explain --all. One agent in full: consortium explain <agent>." in result.stdout
    table = result.stdout.split("\nAgents\n", 1)[1].split("\n(you)", 1)[0].splitlines()
    registry = load_registry(repo)
    names = [name for name, job in sorted(registry.items()) if job.ready]
    assert [line.strip().split()[0] for line in table[1:]] == names
    for column in ("mode", "app", "tier", "model", "effort", "timeout"):
        offset = table[0].index(column)
        assert all(line[offset] != " " for line in table[1:])
    assert "\x1b" not in result.stdout


def test_overview_marks_repo_config_but_not_repo_job(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    result = run_cli("explain", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "repo-reader (repo agent)")[2:4] == ["codex", "standard"]
    write_config(repo / ".consortium", {"agents": {"repo-reader": {"app": ["claude"], "tier": "deep"}}})
    result = run_cli("explain", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "repo-reader (repo agent)")[2:4] == ["claude (repo)", "deep (repo)"]


def test_overview_handles_missing_and_empty_files(run_cli, tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run_cli("explain", cwd=repo)
    assert result.returncode == 0, result.stderr
    state = Path(os.environ["CONSORTIUM_HOME"])
    assert text_row(result.stdout, "you") == ["you", f"{state}/config.yaml", "no file"]
    assert text_row(result.stdout, "repo") == ["repo", ".consortium/config.yaml", "no file"]
    assert "Set by" not in result.stdout
    write_config(state, {})
    result = run_cli("explain", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Consortium settings with no repository, as seen with no manager\n")
    assert text_row(result.stdout, "you") == ["you", f"{state}/config.yaml", "0 settings"]
    assert text_row(result.stdout, "repo") == ["repo", "not in a repository"]
    assert "Set by" not in result.stdout


@pytest.mark.parametrize("manager, title, app", [(None, "as seen with no manager", "codex"), ("claude", "as a Claude Code manager sees them", "claude"), ("codex", "as a Codex manager sees them", "codex")])
def test_manager_changes_title_and_resolved_app(run_cli, tmp_path, manager, title, app):
    args = ("--manager", manager) if manager else ()
    result = run_cli("explain", *args, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].endswith(title)
    assert text_row(result.stdout, "implementer")[2] == app
    result = run_cli("explain", "implementer", *args, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"implementer: a plugin agent, worktree-write, {title}\n")
    assert text_row(result.stdout, "app") == ["app", app, "plugin", "<plugin>/job-descriptions/implementer.md: consortium.app"]
    assert text_row(result.stdout, "tier") == ["tier", "deep", "plugin", "<plugin>/job-descriptions/implementer.md: consortium.tier"]


def test_overview_keeps_resolving_after_one_agent_fails(run_cli, tmp_path):
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"agents": {"ci-gate": {"tier": "unknown-tier"}}})
    result = run_cli("explain", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "ci-gate") == ["ci-gate", "error: ci-gate.tier: invalid value"]
    assert text_row(result.stdout, "implementer")[1] == "worktree-write"
    assert result.stderr == ""


def test_all_lists_every_setting_with_labels_and_files_once(run_cli, tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"gate": {"locks": ["test-stack"]}})
    write_config(repo / ".consortium", {"gate": {"locks": ["+disk"]}})
    brief = repo / "brief.md"
    brief.write_text("---\napp: [claude]\ntier: deep\n---\n")
    result = run_cli("explain", "--all", "--brief", str(brief), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "app") == ["app", "brief", "[claude]"]
    assert text_row(result.stdout, "gate.locks") == ["gate.locks", "you + repo", "[test-stack, disk]"]
    assert text_row(result.stdout, "worktree.dir") == ["worktree.dir", "default", ".worktrees"]
    assert result.stdout.count("<plugin>/defaults.yaml") == 1
    assert result.stdout.count(".consortium/config.yaml") == 1
    assert "\nAgents\n" not in result.stdout
    assert "Set by" not in result.stdout


def test_agent_details_keep_notes_in_full_and_brief_location(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    note = "Read the conventions in full. " * 12 + "\nThen check the evidence."
    write_config(repo / ".consortium", {"agents": {"repo-reader": {"notes": [note, "Read README.md."]}}})
    brief = repo / "brief.md"
    brief.write_text("---\nmodel: one-job-model\n---\n")
    result = run_cli("explain", "repo-reader", "--brief", str(brief), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "model") == ["model", "one-job-model", "brief", "brief.md: model"]
    assert "    " + note.replace("\n", "\n    ") in result.stdout
    assert "    Read README.md.\n" in result.stdout
    assert ".consortium/config.yaml: agents.repo-reader.notes" in result.stdout
    for field in ("app", "allowed apps", "tier", "model", "effort", "mode", "sandbox", "write scope", "capabilities", "locks", "timeout", "report", "alt reports", "version", "notes"):
        text_row(result.stdout, field)


def test_text_shortens_plugin_repository_and_home_paths(run_cli, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    repo = make_repo(home / "repo")
    write_job(repo / ".consortium/agents")
    state = home / ".consortium"
    write_config(state, {"app": ["codex"]})
    env = {"HOME": str(home), "CONSORTIUM_HOME": str(state)}
    result = run_cli("explain", env=env, cwd=repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Consortium settings in ~/repo,")
    assert text_row(result.stdout, "you")[1] == "~/.consortium/config.yaml"
    assert text_row(result.stdout, "default")[1] == "<plugin>/defaults.yaml"
    assert "<plugin> = " in result.stdout
    result = run_cli("explain", "repo-reader", env=env, cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "app")[3] == "~/.consortium/config.yaml: app"
    assert text_row(result.stdout, "tier")[3] == ".consortium/agents/repo-reader.md: consortium.tier"
    assert text_row(result.stdout, "model")[3] == "<plugin>/defaults.yaml: tiers.standard.codex.model"
    assert str(home) not in result.stdout


def test_overview_omits_old_workflow_line_when_none(tmp_path, monkeypatch, capsys):
    from consortium import paths
    from consortium.cli import main

    package = tmp_path / "package"
    write_job(package / "job-descriptions", "only-agent")
    (package / "defaults.yaml").write_bytes((paths.package_root() / "defaults.yaml").read_bytes())
    monkeypatch.setattr(paths, "package_root", lambda: package)
    try:
        assert main(["explain", "--repo", str(make_repo(tmp_path / "repo"))]) == 0
        output = capsys.readouterr().out
        assert text_row(output, "only-agent")[2] == "codex"
        assert "Old workflow" not in output
    finally:
        sys.modules.pop("consortium.explain", None)


def test_setting_values_shorten_paths_and_stay_on_one_line(run_cli, tmp_path):
    from consortium import paths

    home = tmp_path / "home"
    home.mkdir()
    repo = make_repo(home / "repo")
    state = home / ".consortium"
    write_config(state, {
        "worktree": {"dir": str(home / "worktrees")},
        "gate": {"flakes_file": str(repo / "known-flakes.md"), "before": [str(paths.package_root() / "bin/consortium")]},
        "agents": {"implementer": {"notes": ["First line.\nSecond line."]}},
    })
    env = {"HOME": str(home), "CONSORTIUM_HOME": str(state)}
    for args in ((), ("--all",)):
        result = run_cli("explain", *args, env=env, cwd=repo)
        assert result.returncode == 0, result.stderr
        assert text_row(result.stdout, "worktree.dir")[-1] == "~/worktrees"
        assert text_row(result.stdout, "gate.flakes_file")[-1] == "known-flakes.md"
        assert text_row(result.stdout, "gate.before")[-1] == "[<plugin>/bin/consortium]"
        notes = next(line for line in result.stdout.splitlines() if "agents.implementer.notes" in line)
        assert "First line." in notes and "Second line." in notes


def test_brief_marks_direct_model_and_effort_and_tier_mapping_marks_model(run_cli, tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", {"tiers": {"deep": {"codex": {"model": "repo-model"}}}})
    result = run_cli("explain", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "implementer")[4] == "repo-model (repo)"
    result = run_cli("explain", "implementer", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "model") == ["model", "repo-model", "repo", ".consortium/config.yaml: tiers.deep.codex.model"]
    brief = repo / "brief.md"
    brief.write_text("---\nmodel: brief-model\neffort: low\n---\n")
    result = run_cli("explain", "--brief", str(brief), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert text_row(result.stdout, "implementer")[4:6] == ["brief-model (brief)", "low (brief)"]

import json
import os
from pathlib import Path

from test_cli import make_repo
from test_config import write_config
from test_registry import write_job


def explain_repo(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents")
    return repo


def test_explain_text_names_each_source(run_cli, tmp_path):
    repo = explain_repo(tmp_path)
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"app": ["codex"], "agents": {"repo-reader": {"tier": "deep"}}})
    result = run_cli("explain", "repo-reader", "--repo", str(repo))
    assert result.returncode == 0, result.stderr
    assert "tier: deep  <- you (" in result.stdout
    assert "config.yaml: agents.repo-reader.tier)" in result.stdout
    assert "model: gpt-6.1-sol" in result.stdout
    assert "effort: xhigh" in result.stdout
    assert "version: 2  <- repo (" in result.stdout
    assert "allowed_apps: [codex]  <- you (" in result.stdout
    assert "config.yaml: app)" in result.stdout
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
    assert "app: [codex]  <- you (" in result.stdout
    assert "thresholds.reviewers_min_lines: 200  <- default (" in result.stdout
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
    assert "worktree.dir: .worktrees  <- default (" in result.stdout


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
    assert f"tier: standard  <- repo ({repo}/.consortium/agents/repo-reader.md: consortium.tier)" in result.stdout
    assert f"app: codex  <- repo ({repo}/.consortium/agents/repo-reader.md: consortium.app)" in result.stdout
    assert f"allowed_apps: [codex, claude]  <- repo ({repo}/.consortium/agents/repo-reader.md: consortium.app)" in result.stdout
    write_config(repo / ".consortium", {"app": ["claude"], "agents": {"repo-reader": {"tier": "deep"}}})
    result = run_cli("explain", "repo-reader", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert f"tier: deep  <- repo ({repo}/.consortium/config.yaml: agents.repo-reader.tier)" in result.stdout
    assert f"app: claude  <- repo ({repo}/.consortium/config.yaml: app)" in result.stdout
    assert f"allowed_apps: [claude]  <- repo ({repo}/.consortium/config.yaml: app)" in result.stdout


def test_explain_append_names_both_repo_job_and_config(run_cli, tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents", locks=["test-stack"])
    write_config(repo / ".consortium", {"agents": {"repo-reader": {"locks": ["+disk"]}}})
    result = run_cli("explain", "repo-reader", "--manager", "codex", cwd=repo)
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("locks:"))
    assert line == (
        f"locks: [test-stack, disk]  <- repo ({repo}/.consortium/agents/repo-reader.md: consortium.locks)"
        f" + repo ({repo}/.consortium/config.yaml: agents.repo-reader.locks)"
    )

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {
    "bar-raiser.md",
    "cicd-reviewer.md",
    "code-quality-reviewer.md",
    "domain-conventions-reviewer.md",
    "iac-change-reviewer.md",
    "implementer.md",
    "security-reviewer.md",
    "simplifier.md",
    "spec-clarity-reviewer.md",
    "spec-compliance-reviewer.md",
    "test-coverage-reviewer.md",
}


def test_agents_is_a_directory_symlink_to_job_descriptions():
    agents = ROOT / "agents"
    assert agents.is_symlink()
    assert agents.is_dir()
    assert agents.resolve() == ROOT / "plugins/consortium/job-descriptions"
    assert {path.name for path in agents.glob("*.md")} == AGENTS
    assert all((agents / name).is_file() for name in AGENTS)


def test_bin_links_into_the_package():
    assert (ROOT / "bin").is_symlink()
    entry_point = ROOT / "bin/consortium"
    assert entry_point.resolve() == ROOT / "plugins/consortium/bin/consortium"
    assert entry_point.is_file()
    assert os.access(entry_point, os.X_OK)


def test_marketplaces_are_named_consortium_next_and_plugins_stay_consortium():
    for name in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
        marketplace = json.loads((ROOT / name).read_text())
        assert marketplace["name"] == "consortium-next"
        assert [plugin["name"] for plugin in marketplace["plugins"]] == ["consortium"]


def test_claude_plugin_validate_passes():
    if shutil.which("claude") is None:
        pytest.skip("claude is not on PATH")
    result = subprocess.run(
        ["claude", "plugin", "validate", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr

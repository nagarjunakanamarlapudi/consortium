import re

import pytest

from consortium import paths
from consortium.config import load_settings
from consortium.registry import load_registry


NEW = [
    "investigator", "searcher", "implementer", "spec-gate", "test-designer",
    "ci-gate", "device-qa", "code-reviewer", "security-reviewer", "infra-reviewer",
]
ROWS = {
    "investigator": ("investigate", "worktree-write", "tests", ["read", "search", "shell", "edit", "toolchain", "device", "dev-stack"], "deep", 45, "case.v1", ["sweep.v1"]),
    "searcher": ("investigate", "read-only", "all", ["read", "search"], "cheap", 15, "locations.v1", []),
    "implementer": ("build", "worktree-write", "all", ["read", "search", "shell", "edit", "toolchain"], "deep", 90, "none", []),
    "spec-gate": ("check", "read-only", "all", ["read", "search"], "standard", 30, "findings.v1", []),
    "test-designer": ("design", "read-only", "all", ["read", "search"], "standard", 30, "test-cases.v1", []),
    "ci-gate": ("verify", "read-only", "all", ["read"], "cheap", 20, "gate.v1", []),
    "device-qa": ("verify", "read-only", "all", ["read", "device", "dev-stack"], "standard", 60, "qa-lane.v1", []),
    "code-reviewer": ("check", "read-only", "all", ["read", "search"], "standard", 30, "findings.v1", []),
    "security-reviewer": ("check", "read-only", "all", ["read", "search"], "deep", 30, "findings.v1", []),
    "infra-reviewer": ("check", "read-only", "all", ["read", "search"], "deep", 30, "findings.v1", []),
}
RETIRED = [
    "cicd-reviewer", "code-quality-reviewer",
    "domain-conventions-reviewer", "iac-change-reviewer", "simplifier",
    "spec-clarity-reviewer", "spec-compliance-reviewer", "test-coverage-reviewer",
]
SECTIONS = [
    "Purpose", "When you are called", "Method", "Quality bar",
    "Evidence you must show", "Stop and ask", "Report",
]


@pytest.fixture
def registry():
    return load_registry(None)


@pytest.mark.parametrize("name", NEW)
def test_each_new_job_description_is_ready_and_matches_its_row(registry, name):
    job = registry[name]
    assert job.ready
    assert job.path.name == f"{name}.md"
    assert job.front["name"] == name
    assert job.meta["version"] >= 1
    assert job.meta["app"] == "all"
    fields = (
        "station", "mode", "write_scope", "capabilities", "tier",
        "timeout_minutes", "report", "alt_reports",
    )
    assert tuple(job.meta[field] for field in fields) == ROWS[name]
    for report in [job.meta["report"], *job.meta["alt_reports"]]:
        schema = "envelope" if report == "none" else report
        assert (paths.package_root() / "schemas" / f"{schema}.json").is_file()


@pytest.mark.parametrize("name", NEW)
def test_claude_model_and_effort_follow_the_tier(registry, name):
    job = registry[name]
    tier = load_settings(None).get(f"tiers.{job.meta['tier']}.claude")
    assert job.front["model"] == tier["model"]
    assert job.front["effort"] == tier["effort"]


@pytest.mark.parametrize("name", NEW)
def test_read_only_agents_have_no_edit_tools(registry, name):
    job = registry[name]
    tools = {tool.strip() for tool in job.front["tools"].split(",")}
    expected = {"Read", "Grep", "Glob", "Bash"}
    if job.meta["mode"] == "worktree-write":
        expected |= {"Edit", "Write"}
    assert tools == expected


@pytest.mark.parametrize("name", NEW)
def test_body_has_the_seven_sections_and_names_its_report(registry, name):
    job = registry[name]
    assert re.findall(r"^## (.+)$", job.body, re.MULTILINE) == SECTIONS
    sections = re.split(r"^## .+$", job.body, flags=re.MULTILINE)[1:]
    assert all(section.strip() for section in sections)
    method = sections[SECTIONS.index("Method")]
    assert re.search(r"^1\. ", method, re.MULTILINE)
    report = sections[SECTIONS.index("Report")]
    for schema in [job.meta["report"], *job.meta["alt_reports"]]:
        assert f"`{schema}`" in report


@pytest.mark.parametrize("name", NEW)
def test_descriptions_fit_routing(registry, name):
    description = registry[name].front["description"]
    assert 0 < len(description) < 1024
    assert description.startswith("Use when ")
    assert description.split(".", 1)[0].removeprefix("Use when ").strip()


def test_only_bar_raiser_uses_old_format_and_replaced_reviewers_are_gone(registry):
    assert {name for name, job in registry.items() if not job.ready} == {"bar-raiser"}
    assert registry["bar-raiser"].path.is_file()
    assert registry["bar-raiser"].front["name"] == "bar-raiser"
    for name in RETIRED:
        assert name not in registry
        assert not (paths.package_root() / "job-descriptions" / f"{name}.md").exists()


@pytest.mark.parametrize("name", NEW)
def test_no_body_exceeds_120_lines(registry, name):
    assert len(registry[name].body.splitlines()) < 120

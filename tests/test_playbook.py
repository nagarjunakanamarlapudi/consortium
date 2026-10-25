import re
from pathlib import Path

import pytest
import yaml

from consortium.brief import check_brief, parse_brief
from consortium.config import load_settings
from consortium.registry import load_registry, parse_front_matter

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SKILL = ROOT / "plugins/consortium/skills/agent-recipes"
FORMS = [ROOT / "skills/agent-recipes/SKILL.md", PACKAGE_SKILL / "SKILL.md"]
DESCRIPTION = (
    "Use when a request should go to agents rather than be done in this chat: "
    "a bug to reproduce and fix, a change across several files, or anything "
    "that needs the full test run, a device or a release. Routes the job, "
    "sizes the crew with consortium checks, writes checked briefs, dispatches "
    "Consortium agents in Claude Code or Codex, and stops at the gates. "
    "Skip questions, debates and small edits; do those yourself."
)


@pytest.mark.parametrize("path", FORMS, ids=["claude", "codex"])
def test_forms_parse_with_the_dictated_front_matter(path):
    assert path.is_file(), f"missing skill: {path}"
    text = path.read_text()
    front, body = parse_front_matter(text)
    assert front["name"] == "agent-recipes"
    assert front["description"] == DESCRIPTION
    assert "description: >-\n" in text
    assert body.strip()


def test_claude_references_link_to_the_canonical_package():
    references = ROOT / "skills/agent-recipes/references"
    assert references.is_symlink()
    assert references.readlink() == Path("../../plugins/consortium/skills/agent-recipes/references")
    assert references.resolve() == PACKAGE_SKILL / "references"
    for name in ("manager.md", "brief-template.md", "fix-recipe.md"):
        assert (references / name).is_file()
        assert (references / name).read_text().strip()


def test_claude_form_names_the_dispatch_checks_and_gate_controls():
    assert FORMS[0].is_file()
    text = FORMS[0].read_text()
    for command in ("consortium explain", "consortium run-codex", "consortium checks", "consortium gate"):
        assert command in text
    assert "subagent_type: consortium:<agent>" in text
    assert "PushNotification" in text
    assert 'bash "${CLAUDE_PLUGIN_ROOT}/scripts/effort.sh" --resolve' in text


def test_codex_form_keeps_read_only_agents_on_the_launcher():
    assert FORMS[1].is_file()
    text = FORMS[1].read_text()
    _, body = parse_front_matter(text)
    first_line = body.strip().splitlines()[0]
    assert "read-only" in first_line.lower()
    assert "consortium run-codex" in first_line
    assert "spawn_agent" in first_line
    assert "probe" in first_line
    assert "--manager codex" in body
    assert "--prompt" in body
    assert "model" in body and "effort" in body
    assert "PushNotification" not in text
    assert 'bash "<plugin>/scripts/effort.sh" --resolve' in body
    assert "the part of this SKILL.md's path before\n`/skills/agent-recipes/SKILL.md`" in body
    assert "Every `consortium` command below runs by name." in body
    assert "run `<plugin>/bin/consortium` with the same arguments." in body


def test_codex_form_commands_never_rely_on_plugin_root():
    # Codex sets PLUGIN_ROOT for hooks only; a model's own shell has neither variable (probe, 24 Oct).
    _, body = parse_front_matter(FORMS[1].read_text())
    blocks = re.findall(r"^```(?:bash|sh)?\n(.*?)^```", body, re.MULTILINE | re.DOTALL)
    assert blocks
    for block in blocks:
        assert "PLUGIN_ROOT" not in block


def test_brief_template_has_the_write_brief_sections_and_front_matter():
    template = PACKAGE_SKILL / "references/brief-template.md"
    assert template.is_file()
    text = template.read_text()
    brief = parse_brief(text)
    assert {"agent", "worktree", "device", "dictated"} <= brief.front.keys()
    for field in ("app", "tier", "model", "effort", "timeout_minutes", "report"):
        assert re.search(rf"^# {field}:", text, re.MULTILINE)
    assert "# app: [codex]" in text
    sections = [
        "Task", "Context", "Scope", "Do not change", "Premises", "Tests",
        "Done means", "Forbidden", "Stop when", "Report",
    ]
    defaults = yaml.safe_load((ROOT / "plugins/consortium/defaults.yaml").read_text())
    assert defaults["brief"]["sections"]["worktree-write"] == sections
    assert list(brief.sections) == [section.lower() for section in sections]
    assert all(brief.sections.values())
    assert "found by:" in brief.sections["tests"]
    assert "NEEDS_CONTEXT" in brief.sections["stop when"]
    assert "commit" in brief.sections["forbidden"]
    assert "push" in brief.sections["forbidden"]
    assert "none" in brief.sections["report"] and "null" in brief.sections["report"]


def test_fix_recipe_lists_the_eight_steps_in_order():
    recipe = PACKAGE_SKILL / "references/fix-recipe.md"
    assert recipe.is_file()
    text = recipe.read_text()
    steps = re.findall(r"^(\d+)\. (.*?)(?=^\d+\. |\Z)", text, re.MULTILINE | re.DOTALL)
    assert [number for number, _ in steps] == [str(number) for number in range(1, 9)]
    for (_, step), expected in zip(steps, (
        "investigator", "owner picks the fix", "implementer", "consortium checks --diff",
        "consortium gate", "device-qa", "manager review", "commit",
    )):
        assert expected in step
    assert "investigator's worktree" in steps[2][1]
    assert "push" in steps[7][1] and "PR" in steps[7][1] and "tracker" in steps[7][1]


def test_filled_template_passes_the_real_brief_check(tmp_path):
    (tmp_path / "source.py").write_text("def changed_symbol():\n    return 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_source.py").write_text("from source import changed_symbol\n")
    text = (PACKAGE_SKILL / "references/brief-template.md").read_text()
    replacements = {
        "<absolute-worktree>": str(tmp_path),
        "<existing-path>": "source.py",
        "<line>": "1",
        "<affected-test-path>": "tests/test_source.py",
        "<searcher run id or exact search command>": "`rg -l changed_symbol tests`",
        "<language lint command>": "ruff check .",
        "<named test command>": "pytest tests/test_source.py",
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    job = load_registry(None)["implementer"]
    findings = check_brief(parse_brief(text), job, "worktree-write", tmp_path, load_settings(None))
    assert findings == []

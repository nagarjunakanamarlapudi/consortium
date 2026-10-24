import json
from pathlib import Path

import pytest

from consortium.config import load_settings
from consortium.schemas import extract_report, load_schema, redact, validate


NAMES = ("case.v1", "sweep.v1", "findings.v1", "qa-lane.v1", "test-cases.v1", "gate.v1", "locations.v1")
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "plugins/consortium/schemas"


def report(name, payload):
    return {
        "schema": name, "status": "DONE", "summary": "Checked.", "payload": payload,
        "decisions": [{"decision": "Read the file.", "why": "Check the claim."}],
        "evidence": [{"claim": "The check passed.", "kind": "command", "ref": "true", "result": "exit 0"}],
        "changes": [], "checks": [{"command": "true", "exit_code": 0}], "questions": [],
    }


def assert_strict(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        for value in node.values():
            assert_strict(value)
    elif isinstance(node, list):
        for value in node:
            assert_strict(value)


def test_every_schema_is_openai_strict():
    assert {path.name for path in SCHEMA_DIR.glob("*.json")} == {"envelope.json", *(f"{name}.json" for name in NAMES)}
    for path in SCHEMA_DIR.glob("*.json"):
        assert_strict(json.loads(path.read_text()))
    for name in (*NAMES, "none"):
        assert_strict(load_schema(name))


def test_load_schema_composes_envelope_and_payload():
    schema = load_schema("findings.v1")
    assert schema["properties"]["schema"]["const"] == "findings.v1"
    assert schema["properties"]["payload"] == json.loads((SCHEMA_DIR / "findings.v1.json").read_text())
    assert validate(report("findings.v1", {"verdict": "compliant", "findings": []}), schema) == []
    assert validate(report("case.v1", {"verdict": "pass", "findings": []}), schema)


def test_none_schema_has_null_payload():
    schema = load_schema("none")
    assert schema["properties"]["payload"] == {"type": "null"}
    assert validate(report("none", None), schema) == []
    assert validate(report("none", {}), schema)


def test_validate_reports_errors_with_paths():
    instance = report("findings.v1", {"verdict": "unknown", "extra": True})
    errors = validate(instance, load_schema("findings.v1"))
    assert len(errors) == 3
    assert any("$.payload.verdict" in error for error in errors)
    assert any("$.payload.findings" in error for error in errors)
    assert any("$.payload.extra" in error for error in errors)


@pytest.mark.parametrize("name,payload", [
    ("case.v1", {
        "symptom": "Fails on empty input.", "repro_steps": ["Pass empty input."], "reproduced": True,
        "root_cause": {"file": "parser.py", "line": 4, "explanation": "Missing empty check."},
        "other_callers": [{"file": "api.py", "line": 8, "note": "Calls the parser."}],
        "failing_test": {"file": "tests/test_parser.py", "name": "test_empty", "command": "pytest", "exit_code": 1},
        "fix_options": [{"option": "Check first.", "tradeoffs": "One branch."}], "recommendation": "Check first.",
    }),
    ("sweep.v1", {
        "bug_class": "Missing checks.", "instances": [{"file": "parser.py", "line": 4, "note": "Unchecked."}],
        "proposed_check": {"kind": "lint", "where": "ci", "rule": "Check input."},
        "exceptions": [{"file": "demo.py", "line": 2, "why": "Example."}],
    }),
    ("findings.v1", {
        "verdict": None, "findings": [{"severity": "high", "file": "parser.py", "line": None,
                                       "problem": "Unchecked input.", "fix": "Check it."}],
    }),
    ("qa-lane.v1", {
        "platform": "web", "persona": "reader", "build": "test", "device": "browser",
        "flows": [{"name": "Open", "result": "fail", "notes": "Blank."}],
        "defects": [{"title": "Blank", "steps": ["Open"], "expected": "Content", "actual": "Blank", "screenshot": None}],
    }),
    ("test-cases.v1", {
        "mode": "trace", "cases": [{"id": "P1", "kind": "positive", "rule": "Accept text.", "setup": "Ready",
                                    "steps": ["Enter text"], "expected": "Accepted",
                                    "test": {"file": "tests/test_parser.py", "name": "test_text"}, "reason": None}],
    }),
    ("gate.v1", {
        "commit": "abc123", "command": "pytest", "exit_code": 0, "failed_step": None,
        "failure_class": None, "flake": None, "reruns": 0, "cleanup": [{"step": "Stop", "exit_code": 0}], "log": "gate.log",
    }),
    ("locations.v1", {
        "searches": [{"name": "parse", "command": "rg parse", "matches": [
            {"file": "parser.py", "line": 4, "text": "def parse():", "kind": "defines"},
        ]}], "too_common": ["value"],
    }),
])
def test_payloads_validate_nested_objects_and_reject_missing_fields(name, payload):
    schema = load_schema(name)
    assert validate(report(name, payload), schema) == []
    key = next(iter(payload))
    del payload[key]
    assert any(f"$.payload.{key}" in error for error in validate(report(name, payload), schema))


@pytest.mark.parametrize("instance,schema,valid", [
    (True, {"type": "integer"}, False),
    (1.5, {"type": "integer"}, False),
    (2, {"type": "integer"}, True),
    ("2", {"type": "integer"}, False),
    (None, {"type": ["string", "null"]}, True),
    (False, {"type": ["string", "null"]}, False),
    (None, {"anyOf": [{"type": "object"}, {"type": "null"}]}, True),
    ([], {"anyOf": [{"type": "string"}, {"type": "null"}]}, False),
    (True, {"enum": [1]}, False),
    (False, {"const": 0}, False),
])
def test_validate_honors_json_types_and_nullable_branches(instance, schema, valid):
    assert (validate(instance, schema) == []) is valid


def test_validate_array_errors_include_the_item_path():
    instance = report("findings.v1", {"verdict": "pass", "findings": [
        {"severity": "urgent", "file": "parser.py", "line": "four", "problem": "Bad", "fix": "Check"},
    ]})
    errors = validate(instance, load_schema("findings.v1"))
    assert any("$.payload.findings[0].severity" in error for error in errors)
    assert any("$.payload.findings[0].line" in error for error in errors)


def test_extract_report_takes_the_last_json_block():
    text = 'Before\n```json\n{"status": "FAILED"}\n```\nAfter\n```json\n{"status": "DONE"}\n```\n'
    assert extract_report(text) == {"status": "DONE"}
    assert extract_report(' {"status": "DONE"} ') == {"status": "DONE"}
    assert extract_report(text + '\n```json\ninvalid\n```\n') is None
    for invalid in ("no report", "[]", "null", '```json\n[]\n```'):
        assert extract_report(invalid) is None


def test_redact_masks_secret_patterns():
    patterns = load_settings(None).get("runs.secret_patterns")
    text = "key AKIA" + "A" * 16 + " token ghp_" + "b" * 36
    assert redact(text, patterns) == ("key [REDACTED] token [REDACTED]", 2)
    assert redact("clean", patterns) == ("clean", 0)

"""Compose strict report schemas and check the subset used by the factory."""

import json
import re

from consortium.paths import package_root


REPORTS = {"case.v1", "sweep.v1", "findings.v1", "qa-lane.v1", "test-cases.v1", "gate.v1", "locations.v1", "none"}


def load_schema(name: str) -> dict:
    """Return a fresh envelope with the named payload, with no external refs."""
    if name not in REPORTS:
        raise ValueError(f"unknown report schema: {name}")
    folder = package_root() / "schemas"
    schema = json.loads((folder / "envelope.json").read_text())
    schema["properties"]["schema"]["const"] = name
    schema["properties"]["payload"] = (
        {"type": "null"} if name == "none" else json.loads((folder / f"{name}.json").read_text())
    )
    return schema


def _has_type(value, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return type(value) is int or (type(value) is float and value.is_integer())
    if name == "number":
        return type(value) in (int, float)
    return isinstance(value, {"object": dict, "array": list, "string": str}[name])


def _equal(left, right) -> bool:
    # JSON numbers compare by value, but booleans are distinct from 0 and 1.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _property_path(path: str, key: str) -> str:
    return f"{path}.{key}" if re.fullmatch(r"[A-Za-z_]\w*", key) else f"{path}[{json.dumps(key)}]"


def validate(instance, schema: dict) -> list[str]:
    """Validate type, enum, const, objects, arrays and anyOf; return JSON paths."""
    def visit(value, rule, path):
        errors = []
        if "anyOf" in rule:
            alternatives = [visit(value, branch, path) for branch in rule["anyOf"]]
            if all(alternatives):
                details = "; ".join(error for branch in alternatives for error in branch)
                errors.append(f"{path}: does not match anyOf ({details})")
        if "type" in rule:
            types = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
            if not any(_has_type(value, name) for name in types):
                return errors + [f"{path}: expected {' or '.join(types)}"]
        if "const" in rule and not _equal(value, rule["const"]):
            errors.append(f"{path}: expected constant {rule['const']!r}")
        if "enum" in rule and not any(_equal(value, choice) for choice in rule["enum"]):
            errors.append(f"{path}: expected one of {rule['enum']!r}")
        if isinstance(value, dict):
            properties = rule.get("properties", {})
            for key in rule.get("required", []):
                if key not in value:
                    errors.append(f"{_property_path(path, key)}: required property missing")
            for key, child in value.items():
                child_path = _property_path(path, key)
                if key in properties:
                    errors.extend(visit(child, properties[key], child_path))
                elif rule.get("additionalProperties") is False:
                    errors.append(f"{child_path}: additional property is not allowed")
        if isinstance(value, list) and "items" in rule:
            for index, child in enumerate(value):
                errors.extend(visit(child, rule["items"], f"{path}[{index}]"))
        return errors

    return visit(instance, schema, "$")


def extract_report(text: str) -> dict | None:
    """Read the last fenced json block, or an unfenced whole JSON object."""
    blocks = re.findall(r"^[ \t]*```json[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*\r?$", text, re.MULTILINE | re.DOTALL)
    try:
        report = json.loads(blocks[-1] if blocks else text)
    except (ValueError, TypeError):
        return None
    return report if isinstance(report, dict) else None


def redact(text: str, patterns: list[str]) -> tuple[str, int]:
    """Mask configured regex matches and report how many were replaced."""
    count = 0
    for pattern in patterns:
        text, matches = re.subn(pattern, "[REDACTED]", text)
        count += matches
    return text, count

"""JSON Schema helpers, the base judgment schema (design 8.1), and the inclusion check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

BASE_JUDGMENT_SCHEMA: dict[str, Any] = json.loads(
    (Path(__file__).with_name("base_judgment_schema.json")).read_text()
)


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Error messages, empty when valid. Never raises for instance errors."""
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as e:
        return [f"invalid schema: {e.message}"]
    try:
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    except Exception as e:  # noqa: BLE001  (unresolvable $ref and similar)
        return [f"schema could not be applied: {e}"]
    out: list[str] = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{path}: {err.message}")
    return out


def schema_is_valid(schema: dict[str, Any]) -> str | None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        return e.message
    return None


def includes_base_judgment(schema: dict[str, Any]) -> list[str]:
    """Structural inclusion: every base required field, with the base constraints, and the
    abstain implication. Returns the list of violations."""
    problems: list[str] = []
    base = BASE_JUDGMENT_SCHEMA
    required = set(schema.get("required", []))
    for f in base["required"]:
        if f not in required:
            problems.append(f"required field {f} missing from required")
    props = schema.get("properties", {})
    for f, spec in base["properties"].items():
        if f not in props:
            problems.append(f"property {f} missing")
            continue
        if f in ("supporting_evidence", "contradicting_evidence"):
            if props[f].get("type") != "array":
                problems.append(f"{f} must be an array")
            continue
        if f == "rationale":
            if props[f].get("type") != "string":
                problems.append("rationale must be a string")
            if int(props[f].get("maxLength", 10**9)) > int(spec["maxLength"]):
                problems.append(f"rationale maxLength must be at most {spec['maxLength']}")
            continue
        if "enum" in spec:
            if set(props[f].get("enum", [])) - set(spec["enum"]):
                problems.append(f"{f} enum widens the base")
            if not props[f].get("enum"):
                problems.append(f"{f} must carry the base enum")
            continue
        if "type" in spec:
            want = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            have = props[f].get("type")
            have_l = have if isinstance(have, list) else [have]
            if not set(have_l) <= set(want):
                problems.append(f"{f} type {have} is not within base type {spec['type']}")
    if schema.get("if") != base["if"] or schema.get("then") != base["then"]:
        problems.append("the abstain implication (if/then) must be present verbatim")
    defs = schema.get("$defs", {}).get("evidence_ref")
    if not defs or set(defs.get("required", [])) != set(base["$defs"]["evidence_ref"]["required"]):
        problems.append("$defs.evidence_ref must require table, row, column, value")
    return problems

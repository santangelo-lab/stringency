"""Design schema and operation parameter schemas for the toy domain."""

from __future__ import annotations

from typing import Any

DESIGN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["design", "units", "factors", "replication_unit"],
    "properties": {
        "design": {"const": 1},
        "units": {
            "type": "object",
            "required": ["observation", "sample"],
            "properties": {"observation": {"type": "string"}, "sample": {"type": "string"}},
        },
        "factors": {
            "type": "object",
            "required": ["group"],
            "additionalProperties": {
                "type": "object",
                "required": ["column", "levels"],
                "properties": {
                    "column": {"type": "string"},
                    "levels": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                },
            },
        },
        "batch": {"type": "array", "items": {"type": "string"}},
        "replication_unit": {"type": "string"},
        "holdout": {"type": "array"},
    },
}

OPERATIONS: dict[str, dict[str, Any]] = {
    "filter_rows": {
        "type": "object",
        "properties": {"min_value": {"type": "number"}},
        "additionalProperties": False,
    },
    "summarize_groups": {"type": "object", "properties": {}, "additionalProperties": False},
    "label_groups": {"type": "object", "properties": {}, "additionalProperties": False},
    "compare_groups": {
        "type": "object",
        "properties": {
            "replicate_unit": {"enum": ["unit", "row"]},
            "correction": {"enum": ["bh", "bonferroni", "none"]},
        },
        "additionalProperties": False,
    },
    "report": {"type": "object", "properties": {}, "additionalProperties": False},
}

"""stringency-toy: the reference domain plugin. Tabular rows with a group column. No biology.

Domain: a CSV `frame` with columns row_id, group, unit, value. Operations filter rows,
summarize groups, label groups (judgment), compare groups, and report. Every engine
mechanism is exercised; nothing about biology appears.
"""

from __future__ import annotations

from pathlib import Path

from stringency.plugins import ObjectType, Operation, Plugin, Tool
from stringency_toy import phrasing
from stringency_toy.schemas import DESIGN_SCHEMA, OPERATIONS

NAME = "stringency-toy"
VERSION = "0.1.1"
_HERE = Path(__file__).parent

VOCABULARIES = {
    "group_labels@1": ("abundant", "sparse", "variable", "uniform", "indeterminate"),
}

PLUGIN = Plugin(
    name=NAME,
    version=VERSION,
    modes=("pipeline",),
    predicates_module="stringency_toy.predicates",
    operations={k: Operation(name=k, params_schema=v) for k, v in OPERATIONS.items()},
    object_types={
        "frame": ObjectType(name="frame", extractor="extract_frame", extractor_id="toy.frame@1"),
    },
    design_schema=DESIGN_SCHEMA,
    objective_questions=("compare_groups", "process_rows"),
    vocabularies=VOCABULARIES,
    tools={
        "extract_frame": Tool("extract_frame", _HERE / "tools" / "extract_frame.py"),
        "shuffle_groups": Tool("shuffle_groups", _HERE / "tools" / "shuffle_groups.py"),
    },
    describe=phrasing.describe,
    echo=phrasing.echo,
)

METHOD_TEMPLATE = _HERE.parent.parent / "method"

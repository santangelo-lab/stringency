"""L146 (2026-11-02): the operator skill's "This text is for engine X.Y.Z" line read 0.2.29 at
engine 0.2.36 while the text used 0.2.35 features. `probe` fails only a line newer than the
engine, so a line left too low was never caught. The line is at least the highest engine
version the text names, and no newer than the engine it ships with."""

from __future__ import annotations

import re
from pathlib import Path

from stringency import __version__
from stringency.versions import compare

OPERATOR = (
    Path(__file__).parent.parent
    / "integrations"
    / "claude-science"
    / "stringency-operator"
    / "SKILL.md"
)


def test_the_engine_line_is_not_below_a_version_the_text_names_nor_above_the_engine() -> None:
    text = OPERATOR.read_text()
    line = re.search(r"This text is for engine (\d+\.\d+\.\d+)", text)
    assert line is not None, "the operator skill names no engine version"
    named = set(re.findall(r"engine (\d+\.\d+\.\d+)", text))
    highest = max(named, key=lambda v: tuple(int(x) for x in v.split(".")))
    assert compare(line.group(1), highest) >= 0, (
        f"the skill is for engine {line.group(1)} and names a feature of {highest}: bump the line"
    )
    assert compare(line.group(1), __version__) <= 0, (
        f"the skill is for engine {line.group(1)}, newer than this engine ({__version__}): "
        "`probe` would fail the install"
    )

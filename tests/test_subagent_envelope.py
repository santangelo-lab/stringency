"""Subagent dispatch envelope: a response with the answer's keys beside `nonce` and `reported`
(no `structured` key) is parsed as if wrapped. That is what a replicate produces when it follows
the schema literally, which every replicate did on 2026-09-18 before the dispatch suffix named
the envelope."""

from __future__ import annotations

import json
from pathlib import Path

from stringency.harness.base import Request
from stringency.harness.subagent import read_response
from stringency.prompting import DISPATCH_SUFFIX


def _req() -> Request:
    return Request(
        replicate=1, nonce="N-1", prompt="p", schema={}, items=("a",), module="m", template_ref="t"
    )


def test_flat_envelope_is_accepted(tmp_path: Path) -> None:
    (tmp_path / "resp_1.json").write_text(
        json.dumps(
            {
                "items": [{"item_id": "a", "label": "keep"}],
                "nonce": "N-1",
                "reported": {"model": "m"},
            }
        )
    )
    inv = read_response(_req(), tmp_path)
    assert inv.nonce_ok and inv.structured == {"items": [{"item_id": "a", "label": "keep"}]}


def test_wrapped_envelope_still_accepted(tmp_path: Path) -> None:
    (tmp_path / "resp_1.json").write_text(
        json.dumps({"structured": {"items": []}, "nonce": "N-1", "reported": {"model": "m"}})
    )
    inv = read_response(_req(), tmp_path)
    assert inv.nonce_ok and inv.structured == {"items": []}


def test_suffix_names_the_envelope() -> None:
    assert "`structured`" in DISPATCH_SUFFIX and "`nonce`" in DISPATCH_SUFFIX

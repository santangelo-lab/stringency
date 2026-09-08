"""Mock harness (design 10.2): canned responses from a YAML fixture, deterministic, both
families. In dispatch mode it writes the response files itself when `collect` is called.

Fixture:

    mock: 1
    model: mock-model-1
    rules:
      - item: A                    # or "*"
        replicate: "*"             # or an int, or a list of ints
        template: "*"              # module name, template hash, or "*"
        when: {table: summary, column: mean_value, min: 60}     # optional; a list means all must hold
        judgment:
          label: abundant
          confidence: high
          supporting: [mean_value, n_units]          # column names; value filled from the evidence
          contradicting: [{row: C, column: mean_value}]   # a dict names another row; value filled
          rationale: "mean {mean_value} over {n_units} units"   # {col} filled from the evidence
      - item: "*"
        judgment: {abstain: true, rationale: "the statistics do not support a label"}
      - item: "*"
        replicate: 3
        raw: "not json at all"     # an unparseable response, for invalid-replicate tests

Rules are tried in order; the first match wins. An item with no matching rule abstains.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

from stringency import __version__
from stringency.exit_codes import ConfigError
from stringency.harness.base import Family, Invocation, Request, Sampling
from stringency.harness.subagent import read_response, response_path

FIXTURE_ENV = "STRINGENCY_MOCK_FIXTURE"
FAMILY_ENV = "STRINGENCY_MOCK_FAMILY"


def fixture_path(project_root: Path | None) -> Path:
    env = os.environ.get(FIXTURE_ENV)
    if env:
        return Path(env)
    if project_root is not None and (project_root / ".stringency" / "mock.yml").exists():
        return project_root / ".stringency" / "mock.yml"
    raise ConfigError(
        f"mock harness needs a fixture: set {FIXTURE_ENV} or write .stringency/mock.yml"
    )


def _matches(rule: dict[str, Any], item: str, replicate: int, req: Request) -> bool:
    it = rule.get("item", "*")
    if it != "*" and str(it) != item:
        return False
    rep = rule.get("replicate", "*")
    if rep != "*":
        reps = rep if isinstance(rep, list) else [rep]
        if replicate not in [int(r) for r in reps]:
            return False
    tmpl = rule.get("template", "*")
    if tmpl != "*" and tmpl not in (req.module, req.module.split("@")[0], req.template_ref):
        return False
    when = rule.get("when")
    conditions = when if isinstance(when, list) else ([when] if when else [])
    return all(_condition_holds(c, item, req) for c in conditions)


def _condition_holds(when: dict[str, Any], item: str, req: Request) -> bool:
    table = req.evidence.get(when.get("table", next(iter(req.evidence), "")), {})
    row = table.get(when.get("row", item), {})
    val = row.get(when["column"])
    if val is None:
        return False
    try:
        fv = float(val)
    except (TypeError, ValueError):
        return str(val) == str(when.get("equals"))
    if "min" in when and fv < float(when["min"]):
        return False
    if "max" in when and fv > float(when["max"]):
        return False
    return not ("equals" in when and fv != float(when["equals"]))


def _refs(
    cols: list[Any], table_name: str, item: str, table: dict[str, Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in cols:
        if isinstance(c, dict):
            ref = {"table": table_name, "row": item, **c}
            if "value" not in ref:
                ref["value"] = table.get(str(ref["row"]), {}).get(str(ref["column"]), "")
            out.append(ref)
            continue
        row = table.get(item, {})
        out.append(
            {"table": table_name, "row": item, "column": str(c), "value": row.get(str(c), "")}
        )
    return out


class MockHarness:
    kind = "mock"
    version = __version__

    def __init__(self, fixture: Path, family: str | None = None) -> None:
        data = yaml.safe_load(fixture.read_text()) or {}
        if data.get("mock") != 1:
            raise ConfigError(f"{fixture}: mock fixture must declare `mock: 1`")
        self.rules: list[dict[str, Any]] = list(data.get("rules", []))
        self.model = str(data.get("model", "mock-model-1"))
        fam = family or os.environ.get(FAMILY_ENV, "direct")
        self.family: Family = "dispatch" if fam == "dispatch" else "direct"
        self.calls = 0

    # -- answering ----------------------------------------------------------------------

    def _judgment(self, item: str, req: Request) -> dict[str, Any] | str:
        for rule in self.rules:
            if _matches(rule, item, req.replicate, req):
                if "raw" in rule:
                    return str(rule["raw"])
                j = dict(rule.get("judgment", {}))
                break
        else:
            j = {"abstain": True, "rationale": "no mock rule matched"}
        table_name = str(j.get("table", next(iter(req.evidence), "summary")))
        table = dict(req.evidence.get(table_name, {}))
        row = dict(table.get(item, {}))
        abstain = bool(j.get("abstain", False))
        rationale = str(j.get("rationale", ""))
        with contextlib.suppress(KeyError, IndexError, ValueError):
            rationale = rationale.format(**dict(row.items()))
        out: dict[str, Any] = {
            "item_id": item,
            "label": None if abstain else j.get("label"),
            "ontology_id": j.get("ontology_id"),
            "confidence": "abstain" if abstain else j.get("confidence", "high"),
            "abstain": abstain,
            "supporting_evidence": []
            if abstain
            else _refs(
                list(j.get("supporting", ["mean_value", "n_units", "sd_value"])),
                table_name,
                item,
                table,
            ),
            "contradicting_evidence": _refs(
                list(j.get("contradicting", [])), table_name, item, table
            ),
            "rationale": rationale,
        }
        for k, v in j.items():
            if k not in {
                "label",
                "confidence",
                "abstain",
                "supporting",
                "contradicting",
                "rationale",
                "table",
                "ontology_id",
            }:
                out[k] = v
        return out

    def answer(self, req: Request) -> tuple[dict[str, Any] | None, str]:
        items = [req.items[req.item_index]] if req.item_index is not None else list(req.items)
        judgments: list[dict[str, Any]] = []
        for it in items:
            j = self._judgment(it, req)
            if isinstance(j, str):
                return None, j
            judgments.append(j)
        structured: dict[str, Any] = (
            judgments[0] if req.item_index is not None else {"items": judgments}
        )
        return structured, json.dumps(structured)

    # -- direct family ------------------------------------------------------------------

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        self.calls += 1
        structured, raw = self.answer(request)
        return Invocation(
            structured,
            raw,
            False,
            model_requested=sampling.model,
            model_resolved=self.model,
            harness_kind=self.kind,
            harness_version=self.version,
            tokens_in=len(prompt) // 4,
            tokens_out=len(raw) // 4,
            duration_ms=1,
            via="direct",
            isolation="enforced",
        )

    # -- dispatch family ----------------------------------------------------------------

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        pass  # request files are written by judgment.py through subagent.write_requests

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        """Write the response files a subagent would have written, then read them back."""
        out: list[Invocation] = []
        for r in requests:
            rp = response_path(dispatch_dir, r.replicate)
            if not rp.exists():
                self.calls += 1
                structured, raw = self.answer(r)
                if structured is None:
                    rp.write_text(raw)  # unparseable on purpose
                else:
                    rp.write_text(
                        json.dumps(
                            {
                                "nonce": r.nonce,
                                "structured": structured,
                                "reported": {
                                    "model": self.model,
                                    "agent": "mock",
                                    "tools_available": [],
                                    "saw_conversation": False,
                                },
                            },
                            indent=2,
                        )
                    )
            inv = read_response(r, dispatch_dir)
            inv.harness_kind = self.kind
            out.append(inv)
        return out

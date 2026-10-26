"""stringency_io: the plumbing every Python module script of a method shares, and nothing else.

The engine runs a module's script with one JSON job on stdin (module contract, "Script
contract"): `inputs`, `params`, `outputs`, `output_dir`, `seed`, `design`, `objective`, and
`evidence_dir` for a judgment module's evidence script. The script writes each declared output
at the path the job names and exits 0. The analysis belongs in the module script, or in a topic
file beside this one; nothing here knows any biology. Standard library only, so every
environment can import it.

A module script reaches it relative to its own path (the engine binds the method checkout
read-only into every step):

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_pylib"))
    from stringency_io import log_params, read_job, say  # noqa: E402

Copied from the stringency engine's `templates/method-repo`. The R twin is
`_rlib/stringency_io.R`, with the same function names.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


def read_job() -> dict[str, Any]:
    """The job the engine sent on stdin, with `params` always present."""
    job: dict[str, Any] = json.load(sys.stdin)
    job.setdefault("params", {})
    return job


def say(*parts: object) -> None:
    """One progress line on stdout; the engine keeps stdout as the step's log."""
    print(*parts, flush=True)


def _checkable(v: object) -> str | None:
    """`v` as the engine's log reader reads it back, or None when it cannot be (a list, text
    with whitespace): the reader takes `name=value` up to the next space and compares numbers,
    true/false and none with the admitted value."""
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str) and v and not any(c.isspace() for c in v):
        return v
    return None


def log_params(params: dict[str, Any]) -> None:
    """Print `params: name=value ...`, the line the engine reads back from an operator-run
    step's log and compares with the admitted values. Values it cannot compare (lists, text
    with spaces) go on a separate `other params:` line, which the engine does not read."""
    checked = {k: _checkable(v) for k, v in params.items()}
    say("params: " + " ".join(f"{k}={v}" for k, v in checked.items() if v is not None))
    other = {k: params[k] for k, v in checked.items() if v is None}
    if other:
        say("other params: " + json.dumps(other))


def _delimiter(path: str | Path) -> str:
    return "\t" if str(path).endswith(".tsv") else ","


def read_table(path: str | Path) -> list[dict[str, str]]:
    """Rows of a CSV or TSV (by suffix) as dictionaries; lines starting with `#` are skipped."""
    with open(path, newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    return list(csv.DictReader(lines, delimiter=_delimiter(path)))


def write_table(
    rows: list[dict[str, Any]], path: str | Path, columns: list[str] | None = None
) -> None:
    """Write rows to a CSV or TSV (by suffix), columns in the order given or of the first row."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = columns or (list(rows[0].keys()) if rows else [])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=_delimiter(path))
        w.writeheader()
        w.writerows(rows)


def write_json(value: Any, path: str | Path) -> None:
    """Write a JSON document with sorted keys, so two runs with the same facts are byte-equal."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


# ---- figures: PNG files plus figures.csv, one row per figure, which the skills and the
# ---- console read to say what each figure shows

_figures: dict[str, Any] = {"dir": None, "rows": []}


def fig_start(directory: str | Path) -> None:
    """Start a figure directory; `fig_save` writes into it and `fig_finish` lists it."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    _figures["dir"] = Path(directory)
    _figures["rows"] = []


def fig_save(name: str, figure: Any, what: str = "", dpi: int = 120) -> bool:
    """Save a matplotlib figure as `<name>.png`; a failed figure is logged, not fatal."""
    path = _figures["dir"] / f"{name}.png"
    try:
        figure.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    except Exception as e:  # a figure must not fail the step
        say(f"figure {name} failed: {e}")
        return False
    _figures["rows"].append({"file": path.name, "what": what})
    return True


def fig_finish() -> None:
    """Write figures.csv for the figures saved since `fig_start`."""
    write_table(_figures["rows"], _figures["dir"] / "figures.csv", columns=["file", "what"])


# ---- flags: facts a step records on the object for the plugin's predicates to read
# ---- (AnnData `uns["stringency"]`; the R twin uses a Seurat object's `misc$stringency`)


def stringency_flags(adata: Any) -> dict[str, Any]:
    """The flags recorded on an AnnData object so far."""
    return dict(adata.uns.get("stringency", {}))


def set_flag(adata: Any, name: str, value: Any) -> Any:
    """Record one flag on an AnnData object and return the object."""
    flags = stringency_flags(adata)
    flags[name] = value
    adata.uns["stringency"] = flags
    return adata

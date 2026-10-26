#!/usr/bin/env python3
"""Keep the rows of a table whose value is at least a threshold, and count what was kept.

In:      table     CSV with a numeric `value` column
Out:     kept      the rows kept, same columns
         summary   one row: rows in, rows kept, the threshold
Choices: min_value (the threshold; a decision point)
Tools:   Python standard library

The skeleton of a module script (the engine's docs/method-author.md, "Module scripts").
Replace the numbered sections with your analysis and keep the order.
"""

import sys
from pathlib import Path

# Shared code for this method is in modules/_pylib, beside this module's directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_pylib"))
from stringency_io import log_params, read_job, read_table, say, write_table  # noqa: E402


def main() -> None:
    job = read_job()

    # ---- Parameters ----
    min_value = float(job["params"]["min_value"])  # rows below this value are dropped
    log_params({"min_value": min_value})

    # ---- 1. Load ----
    table = read_table(job["inputs"]["table"])

    # ---- 2. Keep the rows at or above the threshold ----
    kept = [row for row in table if float(row["value"]) >= min_value]
    say(f"kept {len(kept)} of {len(table)} rows")

    # ---- Write outputs ----
    write_table(kept, job["outputs"]["kept"], columns=list(table[0].keys()))
    summary = {"rows_in": len(table), "rows_kept": len(kept), "min_value": min_value}
    write_table([summary], job["outputs"]["summary"])


if __name__ == "__main__":
    main()

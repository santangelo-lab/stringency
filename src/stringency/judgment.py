"""Judgment module execution (design 3.5). Filled in at M6."""

from __future__ import annotations

from stringency.exit_codes import RefusedError
from stringency.runs import RunContext
from stringency.steps import Proposal, StepOutcome


def execute_judgment(rc: RunContext, proposal: Proposal) -> StepOutcome:
    raise RefusedError("judgment steps are not implemented yet (M6)")

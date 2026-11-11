# 2026-11-11 17:00: a held proposal withdrawn (L94), a step left `proposed` recovered (L107)

Branch `propose-withdraw-and-recovery`, from `main` at 35e8c84 (#30). Beside
`rationale-names-and-choices` (#31), which is not merged; the two touch different code and
both edit `PLAN.md`, the archive and this index, so the second to merge has those to reconcile.

## Goal

The two rows of wave 2 after L110 and L195: an operator with a flagged reason has no light way
to say it again (L94), and a crash between a proposal's commit and its gate leaves a step only
`abandon` can clear (L107).

## Done

- `steps._settle_pre_gate`: the gate and the settling of a proposed step, split out of
  `propose` so recovery runs the same code.
- `steps.recover_proposed` and the run loop's `proposed` branch; a bare `propose <step>` on a
  `proposed` step does the same.
- `steps.withdraw_proposal` and `propose --withdraw`; the status `withdrawn` with its two
  edges (`held -> withdrawn`, `withdrawn -> proposed`). The first draft sent the step back to
  `pending`; the owner chose a status of its own.
- Design 7.1 (two rows), 7.2 (a paragraph), 14.1 (a clause); `DECISIONS.md` (the last entry);
  both rows archived.
- `tests/test_propose_recovery.py`: six tests.

## Learned

- A step in `proposed` needs no completion marker to be recognised: `propose` never returns
  with the step in that status.
- `monkeypatch.undo()` in a test also undoes the autouse fixture that keeps the egress hold
  out of older tests; a scoped `monkeypatch.context()` is the way to patch for one call.

## Altered

- Design 7.1 gains a status and two edges. The owner chose the status; the text is in this
  branch.

## Open

- The operator skill does not name `--withdraw` or the recovery: at 0.2.43, with the version
  line.
- The rest of L114, then L160, L11, L175.

## Verify

    uv run pytest -q tests/test_propose_recovery.py

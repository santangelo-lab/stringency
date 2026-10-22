# 2026-10-22 11:50: the gate review filed (L100 to L109)

## Goal

Take the owner's walkthrough of the gate (eight limitations, written against `main` at
`6947aa6`) into the plan as rows, after checking each against the code, without disturbing the
session working on `main` on the lab workstation (committed there, not pushed).

## Done

- Every item checked against `origin/main` at `491f1aa`; all eight hold. Line references in
  the plan document are to that commit.
- `spec/plans/gate-soundness.md`: the reasoning per item, the order, the contract impact of each
  row, and what is not filed.
- `PLAN.md`: L100 and L101 in decision points, L103 in holds and confirmation, a new area "Engine:
  the gate and the step lifecycle" with L104 to L109, L102 in method and plugin; Next item 9 (the
  order); item 2 says `sc.decision_unreviewed` does not retire before L100; one row in the waiting
  table for the design choices. `spec/README.md` lists the document and the new area.
- Work on branch `gate-review-backlog` from `origin/main`; local `main` left where it was.

## Learned

- Three findings sharper than the walkthrough put them. `hold: always` is silent on the ordinary
  path, not only on an edge case: `run` proposes a pending step with no values, so every
  parameter is `default`, `declared` or `inherited`; the L61 test passes because it proposes the
  default explicitly. A rebind needs no second run: a pre-gate accept resolves a post-gate flag on
  the same attempt (the review copies the hold's three bindings, and both gates bind the same
  Action). The only exit from a step stranded in `proposed` is `abandon` of the whole run.
- `fork.py` writes inherited steps `pending -> completed` and `pending -> skipped` through
  `Store.set_step_status`, edges not in `EDGES`; deliberate, and an edge-replaying audit (L108)
  must know them.
- The predicate contract's "the agent's rationale is never in the context" has been stale since
  L55 (0.2.29) put the resolved rationale on the Action; L109 carries the fix.
- The rebind behaviour is what design 7.2 says (line 687), so L103 is a design change, though no
  schema change: `holds.context_json` already carries the predicate and phase.

## Altered

- Row ids start at L100. L96 to L99 are left unused so that rows the workstation session may have
  filed but not pushed cannot collide; ids are never reused, so a gap costs nothing.
- No DECISIONS entry (filing rows is not a design choice) and no DEVIATIONS entry yet: L104 and
  L109 draft theirs when the owner chooses the design.

## Open

- The owner: the waiting-table row (L101, L103, L104, L108, L109). L100 needs no approval and is
  the first build; L103 is first once 7.2's new sentence is approved.
- Merge `gate-review-backlog` after the workstation session pushes `main`. Expect conflicts only
  where both sides add lines: `PLAN.md` (Next, the holds table, the waiting table), the index's
  current state and note list. Both sides' lines stay; renumber nothing.
- Not this session's: `spec/README.md` has a bullet for `benchmark-plan.md` inside the plans table
  (line 23), which breaks the table's rendering; make it a row.
- The invariant point (an override still applies to an invariant predicate) is recorded in the
  plan document as not filed; a row only if the owner wants a rule no override can change.

# 2026-11-11 11:20: the work list after waves 0 and 1, and where token usage goes

Branch `plan-usage-measurement`, from `main` at d6c8ce1 (#29). Docs only.

## Goal

The owner asked whether the total token usage of a project can be measured, for evaluating
the tool in general, agreed that it belongs in the beta, and asked for the work to be fitted
into the existing plan.

## Done

- `PLAN.md`: a new area, "Measurement: what a project costs", with rows L190 to L194 (what
  each harness keeps of a session; the bundle reads usage from the transcript; the eval
  store's usage table; the coverage report sums the judges' tokens; token columns in the
  benchmark ledger).
- The work sits in wave 3, which was already "small correctness, and what was never measured"
  and already held the benchmark's run record (L154 to L156). The wave now has two named
  halves.
- State and "Next, in order" rewritten for 2026-11-11: what each wave has done and has left.
- The waiting table: the two rows that were answered (the 0.2.41 tag, the wave 1 design texts)
  replaced by what waits now (the install and the skills, the method's and Xenium's tags, the
  slice run again, L167's choice, this repository being public, a session for L100).
- `implementation-order-2026-11.md` section 9: each wave's standing in one table, and the
  measurement half of wave 3 in order.

## Added the same day: ready for a ROSC run

The owner, before merging: the Xenium method's backlog was barely on the list, and he wants
to run the lab's ROSC study through the method soon, with the Lyons friction addressed first.
Read for it: the ROSC manifest and overview in the archive copy (132 punches, eleven tissues,
route by time with controls), the method's pipelines (four organs; `timepoint_factor` fixed
at `timepoint_h`), and `judg.numeric_claims_match`, which blocks a rationale that names a
time point or a hyphenated punch id.

- `implementation-order-2026-11.md` section 10: track R, seven steps in order (verify the
  method under 0.2.42; draft the declarations; the factor declared; QC without re-splitting;
  rationales and digits; the hold friction; a rehearsal on liver), and what runs beside it.
- `PLAN.md`: track R in "Next, in order", ahead of the rest of wave 2; rows L195 (the
  judgment numeral check), L196 (the run), L197 (seven more organs), L198 (a cargo tool); a
  waiting row for the declarations only the owner can settle.

## What was found on the way to the question

- The engine records judge tokens per invocation and sums them nowhere. Under the subagent
  harness none are recorded: 0 of 39 invocations in thirteen Lyons v2 projects.
- A benchmark replicate's `result.json` has every count; the ledger keeps cost, turns and
  minutes only.
- Whether Claude Science keeps a transcript with usage is not known (L190).

## Open

- Nothing in this branch is code. L194 and L193 are the first two pieces and wait on nothing.

## Verify

    grep -c "^| L" spec/plans/PLAN.md     # 94

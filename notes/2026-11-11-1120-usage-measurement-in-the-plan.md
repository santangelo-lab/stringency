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

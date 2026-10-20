# The owner's trace-integrity review, verified; the plan (2026-10-20)

## Goal

The owner found that a mutable row of the trace (`steps.status` and the like) can be changed by
direct SQL without the event the Store would write, and sent a review with five fix options.
Check it against the code and put a fix plan in the spec.

## Done

- Every claim verified at `b593ea5`: the triggers watch history tables only; `Store.conn` is
  public and read-write; `all`, `one`, `scalar` run any SQL; `insert` guards three of the five
  tables its docstring names; the store docstring's "not exposed for writes" is false; the
  appendix script reproduces the gap against `schema.sql`. Two refinements: `controls_runs` is
  append-only; the open-mode history triggers live in migrations 0005 and 0006.
- `spec/plans/trace-integrity-plan.md` (Lane T): the threat model (the operator is a session with
  a shell as the owner's user), T1 the API and the docstrings, T2 `stringency audit` and
  `prov.trace_inconsistent`, T3 a revision bound to one event with triggers on the mutable tables
  and a hash chain whose head is delivered, T4 a service identity owning `prov/`. The review is
  kept beside it. Backlog L50 to L53; README and roadmap rows.

## Learned

- The design's 9.5 states the pairing as a property of the trace; it is a property of the
  Store. The wording goes with T1.

## Open

- T1 and T2 can start; T3 waits on a DEVIATIONS entry for 9.4 and 9.5; T4 on the owner.

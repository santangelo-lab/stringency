# Trace integrity T1 and T2: the Store tells the truth, and `stringency audit` (2026-10-21)

## Goal

The first two parts of `spec/plans/trace-integrity-plan.md` (the owner's review of 2026-10-20),
chosen by the owner for this pass: no T3 (the database requiring the event), no T4 (the OS
boundary). Engine 0.2.25.

## Done

- T1 (backlog L50). `Store._conn` is the writing connection, reached only from `db/store.py`;
  `Store.reader()` gives read-only connections (`mode=ro`), closed with the store; the console's
  timeline and driver take them. `insert` refuses all five mutable-status tables
  (`MUTABLE_STATUS`), as its docstring always said. The store's docstring, `schema.sql`'s header,
  design 9.5 and `trace-schema.md` say what is true: the pairing is the Store's, the schema does
  not require it. Tests: a row update that fails after its event rolls both back (a trigger
  planted in the test); a failed transition leaves no `actions` row; the reader refuses writes;
  a grep over the source for `._conn` and generic-helper writes outside `db/`.
- T2 (backlog L51). `src/stringency/audit.py`: steps against the latest status event (and the
  attempt against the latest status event carrying one), runs, resolved holds against their
  review row and resolution event (project-level holds by their review alone: no event table
  carries them), consensus, final artifacts, sequence gaps, the schema's trigger names. One
  read transaction on a reader; names, never repairs. `stringency audit [--json]` (exit 1 on
  findings); `prov.trace_inconsistent@1`, invariant block at run open and deliver, from
  `ProjectConfig.trace_findings` the run context fills before those two gates; `coverage.md`'s
  "trace audited" line. `tests/test_audit.py`: a planted status change, a dropped trigger and a
  sequence gap, a hold resolved without its review, the predicate, a completed toy run whose
  step attempt is rewritten by hand (deliver refused, a new run blocked), the audit reads only.
- Backlog: L43 and G2 moved to done with L50 and L51; the plan's status and the roadmap lane.

## Learned

- `Store.open` runs `migrate()`, whose `CREATE TRIGGER IF NOT EXISTS` re-creates a dropped
  trigger: the trigger check matters within a session only. A rewritten step status also makes
  `deliver` say "the run is failed" before its gate reaches the predicate; the attempt is what
  the integration test rewrites.
- A resolved project-level hold has no event anywhere; its review row is the record. The
  first audit flagged every confirmed project until that was understood.

## Open

- T3 and T4 (L52, L53), the owner's. Pass 3 of the triage next: L47, L39, L49, L41, L40, L44.

## Verify

    uv run pytest tests/test_store.py tests/test_audit.py; uv run pytest

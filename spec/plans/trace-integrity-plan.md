# Trace integrity: a mutable row can change without its event

**Status 2026-10-20, later.** T1 and T2 built (engine 0.2.25; backlog L50 and L51 done); T3 and T4 wait on the owner, who chose on 2026-10-20 to stop at T2 for now. Lane T. The finding is the owner's review
`trace-integrity-review-2026-10-20.md` (reviewed commit `b593ea5`), verified against the code
the same day: every claim holds. T1 and T2 are engine work at DECISIONS level; T3 changes a
frozen contract (9.5, trace-schema) and needs the owner; T4 is an operations decision.

## The finding, as verified

Design 9.5 and the schema's header say that a status change on a mutable table (`runs`,
`steps`, `holds`, `consensus`, `artifacts`) writes its event row first, in the same transaction.
That is true of the Store's typed writers and of nothing else:

- The append-only triggers (`schema.sql` lines 321 to 346, plus the ones migrations 0005 and
  0006 add for the open-mode tables) protect the history tables only. No trigger watches
  `steps`, `runs`, `holds`, `consensus` or `artifacts`. `UPDATE steps SET status='completed'`
  succeeds and `step_events` is unchanged; the review's appendix script reproduces it against
  `schema.sql` and did so here.
- `Store.conn` is a public attribute on a read-write connection. `Store.all`, `one` and `scalar`
  run whatever SQL they are given on it. `Store.insert` refuses `runs`, `steps` and `holds` and
  lets `consensus` and `artifacts` through, although its docstring names all five.
- The module docstring of `db/store.py` says the raw connection "is not exposed for writes". It
  is.
- `machine.transition` checks `EDGES` and then calls `Store.set_step_status`, which records any
  status it is given; a caller of the setter skips the state machine, a caller of SQL skips both.
- `Store.open(create=False)` is not read-only: it opens a normal connection, sets WAL and runs
  migrations. The console's timeline reader (`review_serve.py`) takes `site.store.conn`.
- In the engine's own code no raw write exists outside `db/store.py` and the migrations; the
  gap is an enforcement gap, not a defect in use. No project is known to be affected.

Two refinements to the review: `controls_runs` is append-only (a trigger exists), and the
history triggers for `questions`, `answers`, `findings` and `executions.network` live in the
migrations, so a database created before 0.2.22 has them only after migrating.

## Who the guarantee is against

The operator is an AI session with a shell on the workstation, running `stringency` as the
project owner's own Unix user. Whatever the Store refuses, that session can do with `sqlite3
prov/run.db` or by replacing the file. So the four properties the review names split in two:

| property | enforced by | who it stops |
|---|---|---|
| history rows are never changed | triggers | a careless writer, not a determined one with the file |
| a state change has its event | the Store API today; the database after T2 | the same |
| a transition is allowed | `machine.transition` | the engine's own callers |
| the operator cannot rewrite the trace | an OS boundary (T4), nothing else | a determined operator |

T1 to T3 make the engine honest and make a bypass visible. Only T4 makes one impossible, and it
is the one the PROTECT projects will be asked about.

## T1. Tighten the API and tell the truth (engine, one session)

1. `Store.conn` becomes `Store._conn`. Readers that need SQL get a `Store.reader()` that returns
   a read-only connection (`file:...?mode=ro`, `uri=True`) on a separate handle; `review_serve`'s
   timeline and any other consumer outside the store move to it. Internal reads inside a
   writer's transaction stay on the writer's connection (they must see its uncommitted rows).
2. `Store.all`, `one`, `scalar` stay for the engine's own readers but are documented as
   engine-internal; a test asserts that no module outside `db/` and `migrations/` executes a
   string starting with anything but `SELECT` or `WITH` through them (a grep over the source,
   with named exceptions; a guard, not a barrier).
3. `Store.insert` refuses `consensus` and `artifacts` too, as its docstring says. Check the call
   sites first; `set_consensus` and `add_artifact` are the paths.
4. The docstring of `db/store.py`, the header of `schema.sql`, design 9.5 and `trace-schema.md`
   line 6 say what is true: the pairing is the Store's, the database does not require it, and
   the raw connection is reachable by code that holds the Store. After T3 they say the database
   requires it.
5. Tests: a mutable-row update that fails after its event was written rolls both back; the
   proposal transaction leaves no orphaned `actions` row when the transition fails; `insert`
   refuses the five tables; `reader()` cannot write.

Acceptance: `uv run pytest` green; `review --serve` and `present` unchanged; the grep test
passes; the docstrings and 9.5 no longer claim what the schema does not do.

## T2. See a bypass: `stringency audit` (engine, one session)

A read-only verb (and a predicate at run open and at `deliver`, `prov.trace_inconsistent`,
invariant block) that reads the current rows and the events in one read transaction and
reports every disagreement:

- `steps.status` and `attempt` against the latest `status:*` event of the step (not the latest
  event: an artifact or consensus event can come later), falling back to `created`;
- `runs.status` against the latest run status event; `holds.resolved_by_review` against a
  `reviews` row and the hold's resolution event; `consensus` against its `consensus` event;
  `artifacts.final` against the delivery that set it;
- every append-only table's row count against the highest `seq`, and gaps in `seq`.

Output: one line per disagreement with the ids, the current value, the event's value and seq;
`--json` for the skill. It names, it never repairs. `coverage.md` gains the line "trace audited:
no disagreement" (or the count), so a delivery states it. Fixtures: a planted disagreement; a
healthy trace whose last event is not a status event.

Acceptance: the planted mismatch is found; the toy's and the Xenium synthetic traces audit
clean; `deliver` on a trace with a planted mismatch is blocked.

## T3. Make the database require the event (engine, design change, one session plus migration)

The review's B2, made concrete: a revision bound to an event.

- Each mutable table gains `rev INTEGER NOT NULL DEFAULT 0`. Each event table gains `rev
  INTEGER NULL` with `UNIQUE (run_id, step_id, rev)` where not null (one event per revision).
- A `BEFORE UPDATE` trigger on each mutable table aborts unless `NEW.rev = OLD.rev + 1` and an
  event row exists with that `rev` for that key; a `BEFORE DELETE` trigger aborts (mutable rows
  are never deleted; `set_consensus`'s replacement becomes an update, to be checked).
- The typed writers write the event with the new revision first, then the row with `rev + 1`,
  in the same transaction, as they do now. An old event cannot be reused: its `rev` is taken.
- Migration 0007 adds the columns, backfills `rev` from the count of status events per row,
  installs the triggers with `DROP TRIGGER IF EXISTS` first (`CREATE TRIGGER IF NOT EXISTS`
  in `schema.sql` does not replace an existing definition).
- Transition validity stays in `machine.transition`; the trigger records, it does not judge.
- A hash chain on the event tables (each row carries the blake3 of the previous row's canonical
  JSON) is the cheap companion: `audit` verifies the chain, and the chain head is written into
  `deliver/<run>/index.json`, so a history edited after delivery no longer matches what was
  delivered.

This changes the trace contract (9.4 columns, 9.5 wording): a DEVIATIONS entry first, the owner's
word, then the build. Acceptance: the appendix script's update is refused; every typed writer
still writes exactly one event per change; an existing project migrates and audits clean; the
full suite is green; a trigger dropped by hand is reported by `audit` (it checks `sqlite_master`
for the expected trigger names).

## T4. Keep the operator's hands off the file (operations, the owner's decision)

With T1 to T3 the trace is honest and a bypass is visible, but the operator can still open the
file. The boundary that stops it:

- `prov/` and `run.db` owned by a service identity (`stringency-engine`, a local system user
  or an AD service account), not by the project owner; the owner's group reads.
- The engine's writing verbs run as that identity through one narrow door: a `sudo` rule for
  the engine binary only, or a per-host daemon the CLI talks to over a socket; the operator's
  shell keeps no write path to `prov/`, its directory, or the WAL and SHM files.
- The console service already runs as the owner's account for its verdicts; it moves to the
  service identity or stays read-only.

This is the PROTECT question ("can the agent alter the record?") and the only honest answer to
it is this boundary. It touches install, the console unit, onboarding and the skills' PRE line.
Not scheduled until the owner wants it; the design belongs in `docs/install.md` and a plan of
its own.

## Order and what needs the owner

T1 and T2 first, in that order, one session each; they need no decision. T3 needs the
DEVIATIONS entry acknowledged (9.4 and 9.5). T4 needs the owner's yes and a site decision about
the service identity. Backlog L50 to L53 carry the four.

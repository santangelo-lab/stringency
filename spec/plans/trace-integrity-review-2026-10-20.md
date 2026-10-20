# Stringency trace integrity: mutable state can bypass its history

**Code review and proposed fixes — 20 October 2026**

| Review detail | Value |
| --- | --- |
| Repository | [santangelo-lab/stringency](https://github.com/santangelo-lab/stringency) |
| Reviewed commit | [`b593ea53e10ce9ef091ef77863ccadb329ed3040`](https://github.com/santangelo-lab/stringency/commit/b593ea53e10ce9ef091ef77863ccadb329ed3040) |
| Focus | How mutable database records stay coupled to their trace events |
| Evidence | Source inspection, inspection of existing tests, and an in-memory SQLite reproduction |
| Deliverable status | Analysis and implementation recommendations; no repository changes made |

All repository links below are pinned to the reviewed commit. Proposed behavior is distinguished from behavior already implemented.

## 1. Finding and recommended response

**Stringency's normal Store writers record a state change and its history together, but the database does not require every change to pass through those writers.** Direct SQL can therefore change a mutable record without appending the event that would normally explain that change.

For example, an ordinary SQL update can change `steps.status` from `pending` to `completed` while leaving `step_events` unchanged. The existing protection on `step_events` still prevents ordinary updates and deletions of its historical rows. These are separate guarantees: preserving existing history does not ensure that new history is recorded. The schema explicitly documents that the pairing for mutable tables is implemented by the Store API. [Sources: schema contract][schema-contract], [status writer][store-status], [history triggers][schema-triggers].

This is a demonstrated enforcement gap. It is not evidence that an existing project has been corrupted, that the normal engine currently makes this silent change, or that editing one status defeats all execution, review, and delivery checks.

The recommended first step is to tighten the internal Python API, correct misleading documentation, and add tests for the actual guarantees. Add a read-only consistency check to expose discrepancies. Then make a separate architectural decision about whether SQLite itself must require an event for each change. If the requirement also includes preventing arbitrary operator code from modifying the trace, enforce that through operating-system permissions or an equivalent isolation boundary.

## 2. The distinction: current state versus history

A mutable table stores what is true **now**. An event table stores what was recorded **over time**.

| Record | Example question it answers |
| --- | --- |
| `steps` | What status and attempt does this step currently have? |
| `step_events` | What changes and other events were recorded for this step, in what sequence? |
| `runs` and `run_events` | What is the run's current state, and what happened during the run? |
| `holds`, `consensus`, and `artifacts` | What hold resolution, consensus result, or artifact metadata is currently recorded? |

These structures are defined in the [database schema][schema] and maintained by the [Store writers][store-writers].

For an R analogy, imagine a function that modifies a row in a current-results data frame and appends an entry to a separate analysis log. Calling that function preserves the relationship. Assigning directly into the data frame changes the result without invoking the logging function. Making the log difficult to edit does not automatically intercept assignments to the data frame.

Four distinct properties matter here:

| Property | What would have to enforce it? | Position at the reviewed commit |
| --- | --- | --- |
| Existing history resists ordinary `UPDATE` and `DELETE` | Database rules on historical tables | Implemented with triggers for designated tables. |
| A current-state change has its corresponding event | A paired writer or database rule | Implemented by dedicated Store methods; direct SQL can bypass them. |
| A step follows an allowed transition | State-machine validation | Checked by `machine.transition()` above the Store layer. |
| Unauthorized code cannot rewrite the trace | A boundary controlling actual database access | Not established by the Store API or these triggers alone. |

The first three rows follow directly from the [trigger definitions][schema-triggers], [Store implementation][store-status], and [state machine][machine]. The final row is an architectural distinction: an API convention cannot prevent a process with independent write access from opening the same database file.

## 3. How the normal implementation preserves the pairing

### 3.1 The engine validates a transition, then asks Store to record it

`machine.transition()` reads the current step status, checks the proposed edge against `EDGES`, and calls `Store.set_step_status()`. The edge list permits `pending → proposed`; it does not permit `pending → completed`. [Source: state machine][machine].

One concrete engine path is proposal recording in `steps.py`:

```python
with store.transaction():
    write_action(store, action)
    transition(
        store,
        rc.run_id,
        step_id,
        StepStatus.PROPOSED,
        attempt=attempt,
        payload={"action_id": action.action_id},
    )
```

This groups the action record with the proposal transition and its event. The excerpt is from [the proposal implementation][proposal].

### 3.2 Store writes the event and mutable row inside one transaction

The following is an explanatory reduction of `set_step_status()`. It omits the real method's optional attempt and timestamp updates, while retaining its event-before-update ordering:

```python
# Simplified explanation, not a replacement implementation.
def set_status_example(store, run_id, step_id, new_status):
    with store.transaction():
        previous = store.scalar(
            "SELECT status FROM steps WHERE run_id = ? AND step_id = ?",
            (run_id, step_id),
        )
        if previous is None:
            raise ValueError("step does not exist")

        store.step_event(
            run_id,
            step_id,
            f"status:{new_status}",
            {"from": previous, "to": new_status},
        )

        store.conn.execute(
            "UPDATE steps SET status = ? WHERE run_id = ? AND step_id = ?",
            (new_status, run_id, step_id),
        )
```

The real [`set_step_status()`][store-status] also accepts contextual payload, optionally updates the attempt, and can stamp start/end times. [`step_event()`][store-events] assigns the next event sequence number for that run and step.

[`Store.transaction()`][store-transactions] starts `BEGIN IMMEDIATE`, rolls back when an exception escapes its body, and commits on successful exit. Nested calls join the existing transaction; they do not independently commit or create savepoints. This lets the outer proposal transaction include the action, event, and status change in one unit.

The transaction makes **the writes that were actually requested** succeed or fail together. It does not determine that another write ought to exist. Consequently, wrapping a lone SQL status update in `store.transaction()` does not create history.

There is also a layering distinction: `set_step_status()` records the supplied status but does not itself check `EDGES`. Calling that method directly can preserve history while bypassing state-machine validation. Direct SQL bypasses both layers. [Sources: Store status writer][store-status] and [transition validation][machine].

## 4. Where bypasses are possible

### 4.1 The write-capable connection is publicly reachable

The constructor assigns:

```python
self.conn = conn
```

That connection is opened for ordinary read/write use. A caller holding the Store object can therefore execute an update directly through `store.conn`, without running `set_step_status()`. [Source: Store lifecycle][store-lifecycle].

For example, given an existing run and step, the following is the bypassing operation:

```python
store.conn.execute(
    "UPDATE steps SET status = ? WHERE run_id = ? AND step_id = ?",
    ("completed", run_id, step_id),
)
```

This example illustrates the issue; the runnable reproduction in the appendix uses an isolated in-memory database.

### 4.2 The general query helpers do not enforce read-only behavior

The current implementation includes:

```python
def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return self.conn.execute(sql, params).fetchall()
```

`one()` also executes caller-supplied SQL on the same connection, and `scalar()` delegates to `one()`. A method's name or its habit of fetching rows does not constrain which SQL it executes. Merely renaming `conn` to `_conn` would leave this route open. [Source: generic Store helpers][store-generic].

### 4.3 The generic insertion guard has a smaller scope than its docstring

`Store.insert()` documents that callers must use dedicated writers for `runs`, `steps`, `holds`, `consensus`, and `artifacts`. Its actual guard is:

```python
if table in {"runs", "steps", "holds"}:
    raise ValueError(f"use the typed writer for {table}")
```

Thus, generic insertion does not enforce the documented restriction for `consensus` or `artifacts`, even though `set_consensus()` and `add_artifact()` provide event-paired paths. [Sources: insertion guard][store-generic] and [dedicated writers][store-writers].

This is a concrete API inconsistency to fix. It is not evidence that normal callers already use those generic insertions incorrectly.

### 4.4 Historical-table triggers do not watch mutable-table changes

The schema contains this rule, reformatted here for readability:

```sql
CREATE TRIGGER IF NOT EXISTS ao_step_events_u
BEFORE UPDATE ON step_events
BEGIN
    SELECT RAISE(ABORT, 'step_events is append-only');
END;
```

A companion trigger rejects `DELETE` on `step_events`. Neither is a trigger on `steps`. Changing `steps.status` therefore does not activate them. [Source: actual triggers][schema-triggers]. SQLite triggers act on their specified table operation; a trigger on one table is not a general instruction to audit changes elsewhere. [SQLite trigger documentation][sqlite-triggers].

## 5. Evidence, impact, and limits

### Demonstrated behavior

A disposable SQLite database was created in memory from the repository's actual base `schema.sql`, with foreign keys enabled. It contained a project, a run, a pending step, and one `created` event.

| Operation | Observed result |
| --- | --- |
| Read initial status and history | Status `pending`; one event. |
| Directly update the step to `completed` | Update accepted. |
| Read status and history again | Status `completed`; still one event, unchanged. |
| Attempt ordinary update of the existing event | `sqlite3.IntegrityError: step_events is append-only`. |
| Attempt ordinary deletion of the existing event | Same append-only error. |

The appendix provides a reproducible version. This exercise demonstrates schema behavior; it does not run the Store class, migrations, the engine, or the full test suite. The inspected migrations do not add mutable-status/event coupling. [Source: migrations at the reviewed commit][migrations].

### Why a discrepancy matters

Some readers obtain current status directly from `steps`; for example, `machine.step_status()` reads that table. If the row changes silently, such a reader can see a status that has no corresponding transition event. This can undermine a trace explanation or a diagnostic report even though every previously recorded event remains intact. [Source: status readers][machine].

A status edit does not create an execution record, valid outputs, reviews, or other supporting evidence. Whether a particular downstream operation accepts the inconsistent state depends on its additional checks. This review does not establish a complete workflow bypass.

### What source inspection supports

The direct step-status update statement found in the inspected production source is centralized in Store. The inspected proposal path uses `transition()` and the transaction-paired writer. Raw connection use outside Store was also found in review-serving code where it is passed into timeline/rendering readers. Those read-oriented call sites explain part of the exposure and should be included in any API refactor. [Sources: Store update][store-status], [proposal][proposal], [review-serving readers][review-readers].

The existing tests check ordinary updates/deletions of designated historical tables, check normal status/event pairing, and simulate failure of the event writer before the status update. They were inspected, not executed for this review. Their existence supports the intended contract; it does not establish that arbitrary SQL mutations are blocked. [Source: Store tests][store-tests].

## 6. Fix options and the guarantees they provide

The estimates below are qualitative engineering judgments, not measured implementation estimates.

| Option | Intended guarantee | Main limitation | Relative effort |
| --- | --- | --- | --- |
| A. Tighten the Store API and reader interfaces | Routine Python callers use validated, event-paired write paths | Does not stop arbitrary code with independent database write access | Low to moderate |
| B. Enforce coupling in SQLite | Covered SQL mutations cannot silently change current state while the rules remain installed | Requires explicit event semantics; does not protect against schema/file replacement | Moderate to high |
| C. Restrict database write authority | Operator/executor code cannot independently rewrite the trace | Requires an actual isolation boundary and operational design | High |
| D. Add a consistency diagnostic | Detect specified disagreements between current records and history | Detection cannot reconstruct evidence that was never recorded | Low to moderate |
| E. Derive current state from authoritative events | Current state follows a defined event history | Larger redesign; requires replay-complete events and validated event insertion | High |

### Option A — Tighten the application boundary first

**Make deliberate Store methods the normal way to change trace state.**

1. Rename the raw connection to an internal attribute and stop passing it through public reader APIs. Python's leading underscore communicates intended use; it is not an access-control mechanism. [Python's private-variable conventions][python-private].
2. Replace unrestricted public SQL helpers with purpose-specific readers, or give independent readers genuine read-only database connections. Keep the write-capable connection within the storage implementation.
3. Extend the generic insertion guard to the intended event-paired tables, including `consensus` and `artifacts`, after checking call sites. Do not blindly block every table in `MUTABLE`: initialization and project metadata need explicitly defined policies.
4. Preserve an explicit separation between low-level storage operations and validated engine operations. If transition validation must be mandatory for all ordinary callers, expose a validated operation and restrict access to the lower-level status setter. Perform validation and its dependent write within one transaction when concurrent writers are possible.
5. Correct the module docstring's claim that the raw connection is not exposed for writes, and align documentation, guards, and tests with the actual supported contract.

For a separate reporting reader, the basic SQLite opening pattern could be:

```python
# Proposed building block for an independent reporting reader.
from pathlib import Path
import sqlite3

def open_trace_reader(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection
```

`mode=ro` opens the target database read-only. It does not stop the same process from opening a different write-capable connection if its filesystem permissions allow that. [SQLite URI modes][sqlite-uri]. This is a reader building block, not a complete sandbox for arbitrary SQL or Python.

Two implementation details matter. First, `Store.open(create=False)` is currently **not** a read-only constructor: it still opens a normal connection, configures WAL, and runs migrations. A reader should have a separate opening path. Second, internal reads performed during a writer transaction must still use that writer's connection so they can see its own uncommitted changes. Moving every `scalar()` call to a second connection would break that assumption. [Sources: Store opening][store-lifecycle] and [transaction/event code][store-transactions].

A static architecture check can flag raw mutation calls outside the storage module, with explicit exceptions for migrations and tests. It can help prevent accidental regression, but should not be described as a complete barrier to dynamic Python code. Avoid trying to make arbitrary SQL safe through a simple `SELECT` prefix check.

### Option B — Require the pairing in SQLite

If the desired promise is “covered SQL changes cannot occur without a matching event,” the database needs a rule that actually governs those changes. Two possible designs deserve consideration.

**B1. Let the database generate a basic audit event.** An update trigger could record the old and new values using `OLD` and `NEW`. The database would then perform the audit write whenever the covered update occurs. [SQLite trigger mechanisms][sqlite-triggers].

Stringency-specific design work would still be needed: decide who supplies the action, actor, reason, attempt, and other context; decide whether unchanged-value assignments count as events; and preserve the sequence and payload contracts. The trigger cannot infer a human rationale or authenticate an actor from a status value.

Choose one owner for the corresponding event. Adding a trigger while leaving the existing Store event insertion unchanged would risk duplicate status events. Existing databases, normal writes, and event readers need a coordinated migration. Where a trigger is created with `IF NOT EXISTS`, editing its definition in `schema.sql` alone does not replace the existing trigger. Use a numbered migration that explicitly installs or replaces the required definitions for existing databases. [Sources: existing trigger definitions][schema-triggers] and [migration implementation][store-lifecycle].

**B2. Reject a change unless it is bound to a fresh event.** An alternative is to tie each mutable-row revision to a specific event and reject updates that lack the required binding. A guard that only asks whether a matching event exists somewhere in history is insufficient: an old event might be reused. The design needs an enforced, unique relationship among the prior revision, new revision, and event, with both changes in one transaction.

Neither design is ready to implement as a single isolated trigger pasted into the current schema. Define the intended event relationship for creation, updates, replacement, and any permitted deletion of each covered record. Pay particular attention to `set_consensus()`, which currently replaces the current consensus row, and to artifact flags and hold resolution. [Source: mutable-record writers][store-writers].

Database coupling also does not automatically validate the state-machine graph. A trigger that faithfully records `pending → completed` would improve audit completeness while still allowing an invalid transition. Treat transition validity as an additional requirement.

Finally, these rules depend on the schema remaining intact. An actor allowed to alter that schema can remove triggers, and an actor allowed to replace the database can avoid them. SQLite explicitly supports dropping triggers. [SQLite trigger documentation][sqlite-triggers].

### Option C — Restrict who can write the trace

This option is relevant **if** operator or executor code can run arbitrary commands and the requirement is to prevent it from independently modifying the database.

A stronger architecture gives the trusted engine exclusive write authority over the trace. Operator/executor processes run with a different operating-system identity or equivalent restricted capability, and request defined operations through an engine interface. The interface accepts domain operations such as a proposal or an execution result, not arbitrary SQL. The engine validates the operation and records its evidence.

The isolation must cover the database and the means of replacing it, including its containing directory and SQLite's associated journal files. Writer credentials and engine configuration must also remain outside the restricted process's control. Starting a separate daemon under the same unrestricted user identity is not, by itself, a permission boundary.

This is a larger operational decision than an API cleanup. It should follow an explicit requirement about which code is trusted and what that code can access. This review does not establish the actual filesystem permissions or sandbox configuration of every Stringency deployment.

### Option D — Add a read-only consistency diagnostic

A proposed diagnostic could compare a step's current status against its latest applicable status event by sequence number, falling back to the creation event for a step without transitions. It must identify the latest **status** event, not simply the last event: artifact or consensus events can occur later without changing status.

Related checks could compare recorded attempts, hold resolutions, consensus changes, and artifact flags against their corresponding evidence where the existing event payloads support that comparison. Read current rows and events within one consistent read transaction so concurrent engine activity does not create a false mismatch.

Report the record identifiers, current values, relevant event sequence, and disagreement. Do not automatically manufacture a missing reason or approval. Any repair operation should have a separately designed policy and leave explicit evidence of the repair.

The diagnostic detects only the invariants it can evaluate. Matching current and recorded status does not prove that no unrecorded intermediate change occurred, or that a stated actor is authentic. A history that was never recorded cannot always be reconstructed from the present database. Existing event writers record selected fields; this review has not established that every current table is fully rebuildable from those events. [Source: event payloads in mutable writers][store-writers].

### Option E — Make events authoritative and derive current state

A more extensive redesign could derive current state from events, either through views or a controlled projection. This would make the intended relationship explicit: the current record is computed from accepted history.

That approach requires events rich enough to reconstruct every relevant field, deterministic replay rules, valid event ordering, and controlled event insertion. A writable projection can still drift if its update path remains unrestricted. Event-derived state also does not establish who is authorized to append an event.

This should be considered only if broader replay or recovery requirements justify the migration. It is not a prerequisite for fixing the immediate Store API inconsistencies.

## 7. Suggested implementation sequence and acceptance criteria

### First change: clarify and tighten the existing API

Keep this change focused on Python interfaces and the current trace contract.

- Correct the raw-connection and generic-insert documentation.
- Close the `consensus`/`artifacts` insertion-guard mismatch.
- Give review/reporting code an appropriate reader interface, preserving internal reads on the writer connection.
- Document the distinction between validated state transitions and low-level recorded status writes.
- Add a targeted architecture check for accidental raw writes outside the intended storage paths.

**Acceptance criteria:** normal proposals, reviews, consensus changes, and artifact updates retain their expected events and metadata; public reader operations cannot mutate the trace; generic insertion into the protected tables is rejected; existing reporting behavior is preserved.

### Second change: exercise the failure boundary and add diagnostics

The existing atomicity test makes `step_event()` raise before the status update. Add a complementary test that forces the mutable-row update to fail **after** the event has been inserted, then verify that the event and row change are both rolled back. Also test the outer proposal transaction so a failed transition does not leave an orphaned action record. [Existing tests][store-tests].

Add the read-only consistency diagnostic with fixtures for both genuine disagreement and a healthy trace whose final event is unrelated to status. Include a concurrent-write scenario only where needed to verify snapshot consistency.

**Acceptance criteria:** failures at either write in the event-then-state sequence preserve the intended transaction boundary, the diagnostic finds a deliberately introduced mismatch, and valid traces do not report discrepancies merely because later non-status events exist.

### Third change, if required: enforce the chosen database contract

Before implementing Option B, document the exact tables, fields, operations, event payloads, sequence rules, and migration behavior to be enforced. Review the existing [trace specification][trace-spec] and repository decision/deviation records when changing those contracts.

**Acceptance criteria:** covered direct SQL mutations either create exactly the required event or fail; repeated changes cannot reuse historical events as the required evidence for a new mutation; Store calls do not generate duplicates; rollback removes partial work; existing databases migrate successfully; supported concurrent writes do not duplicate event sequence numbers. Include creation, replacement/UPSERT, multirow changes, and any permitted deletion in coverage rather than testing only a simple `UPDATE`.

### Separate architecture decision: operator isolation

If the requirement includes preventing arbitrary operator/executor code from modifying the trace, define and test the actual process and filesystem boundary described in Option C.

**Acceptance criteria:** restricted code cannot alter or replace the database through an independent connection or filesystem operation, while authorized engine operations and intended trace reads remain available. These checks must exercise the deployment's real permissions, not merely a mocked Python API.

## Appendix A. Reproduce the mutable-state/history gap

The following demonstration uses Python's standard library and the actual base schema from a local checkout of the reviewed commit. It creates only an in-memory database. Project and run values are synthetic fixtures sufficient for the schema; they are not valid execution provenance.

Save the following block as `trace_gap_demo.py`. Run `python trace_gap_demo.py` from the repository root, or pass the path to `src/stringency/db/schema.sql` as its first argument. The script does not import Stringency, run migrations, or exercise the engine.

```python
import json
import sqlite3
import sys
from pathlib import Path

schema_path = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path("src/stringency/db/schema.sql")
)
db = sqlite3.connect(":memory:", isolation_level=None)
db.executescript(schema_path.read_text())


def seed(table, **row):
    # Fill required fields without defaults using synthetic fixture values.
    # Table names below are fixed demonstration constants, not user input.
    for _, name, kind, required, default, primary_key in db.execute(
        f"PRAGMA table_info({table})"
    ):
        if (required or primary_key) and default is None and name not in row:
            row[name] = (
                0 if kind == "INTEGER"
                else "{}" if name.endswith("_json")
                else "demo"
            )
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    db.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(row.values()),
    )


seed("projects", project_id="P")
seed("runs", run_id="R", project_id="P", status="running")
seed("steps", run_id="R", step_id="S", status="pending")
seed(
    "step_events",
    run_id="R",
    step_id="S",
    seq=1,
    event="created",
    payload_json=json.dumps({"status": "pending"}),
)


def snapshot():
    status = db.execute(
        "SELECT status FROM steps WHERE run_id='R' AND step_id='S'"
    ).fetchone()[0]
    events = db.execute(
        "SELECT seq, event, payload_json FROM step_events "
        "WHERE run_id='R' AND step_id='S' ORDER BY seq"
    ).fetchall()
    return {"status": status, "event_count": len(events), "events": events}


print("foreign_keys:", db.execute("PRAGMA foreign_keys").fetchone()[0])
before = snapshot()
print("before:", before)

db.execute(
    "UPDATE steps SET status='completed' "
    "WHERE run_id='R' AND step_id='S'"
)
after = snapshot()
print("after:", after)
assert after["status"] == "completed"
assert after["event_count"] == 1
assert after["events"] == before["events"]

for statement in [
    "UPDATE step_events SET event='changed' "
    "WHERE run_id='R' AND step_id='S'",
    "DELETE FROM step_events WHERE run_id='R' AND step_id='S'",
]:
    try:
        db.execute(statement)
    except sqlite3.IntegrityError as exc:
        print(
            statement.split()[0] + " step_events:",
            type(exc).__name__,
            str(exc),
        )
    else:
        raise AssertionError("Expected the append-only trigger to reject SQL")

db.close()
```

Observed output:

```text
foreign_keys: 1
before: {'status': 'pending', 'event_count': 1, 'events': [(1, 'created', '{"status": "pending"}')]}
after: {'status': 'completed', 'event_count': 1, 'events': [(1, 'created', '{"status": "pending"}')]}
UPDATE step_events: IntegrityError step_events is append-only
DELETE step_events: IntegrityError step_events is append-only
```

This reproduction demonstrates the current gap. It does not test a proposed fix or establish protection against every possible SQL write strategy.

## Appendix B. Source index

### Stringency implementation and tests

- [Schema: documented enforcement boundary][schema-contract].
- [Schema: complete tables][schema] and [history triggers][schema-triggers].
- [Store: constructor, opening, and lifecycle][store-lifecycle].
- [Store: transaction manager][store-transactions].
- [Store: generic insert and query helpers][store-generic].
- [Store: event sequencing][store-events] and [step status changes][store-status].
- [Store: run, hold, consensus, and artifact writers][store-writers].
- [State machine: allowed transitions, status readers, and validation][machine].
- [Engine: proposal transaction][proposal].
- [Review server: raw connection passed to readers][review-readers].
- [Store tests: historical-table protection, paired writes, and failure behavior][store-tests].
- [Database migrations][migrations] and [trace specification][trace-spec].

### Primary documentation for implementation options

- [SQLite: trigger behavior][sqlite-triggers].
- [SQLite: read-only URI mode][sqlite-uri].
- [Python: conventions for internal attributes][python-private].

[schema-contract]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/schema.sql#L1-L4
[schema]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/schema.sql
[schema-triggers]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/schema.sql#L320-L346
[store-lifecycle]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L91-L146
[store-transactions]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L148-L161
[store-generic]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L165-L206
[store-events]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L284-L299
[store-status]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L301-L341
[store-writers]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/store.py#L220-L460
[machine]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/machine.py#L35-L120
[proposal]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/steps.py#L574-L583
[review-readers]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/review_serve.py#L982-L1140
[store-tests]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/tests/test_store.py#L89-L215
[migrations]: https://github.com/santangelo-lab/stringency/tree/b593ea53e10ce9ef091ef77863ccadb329ed3040/src/stringency/db/migrations
[trace-spec]: https://github.com/santangelo-lab/stringency/blob/b593ea53e10ce9ef091ef77863ccadb329ed3040/spec/trace-schema.md
[sqlite-triggers]: https://www.sqlite.org/lang_createtrigger.html
[sqlite-uri]: https://www.sqlite.org/uri.html
[python-private]: https://docs.python.org/3/tutorial/classes.html#private-variables

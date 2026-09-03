# Decisions

Choices made where the design is silent. One line each: the choice and the reason.

- Hashes in trace columns are bare lowercase blake3 hex. Fields the design shows with a prefix (state `digest`, action `inputs`) use `blake3:<hex>` via `hashing.prefixed`. Reason: one representation per column, and the prefix only where the design shows it.
- CIFS refusal in `Store.open` reads `/proc/mounts` and refuses `cifs`, `smb3`, `smbfs` for the longest mount prefix of the database path. Reason: no subprocess, no extra dependency; `stat -f` gives the same answer.
- `schema.sql` is migration version 1 and is applied with `CREATE ... IF NOT EXISTS`; later migrations are `db/migrations/NNNN_name.sql`, forward-only. Reason: simplest runner that records what was applied.
- Timestamps are UTC ISO 8601 with a Z suffix at second precision. Reason: sortable as text, no timezone ambiguity.
- `holds` carries the binding columns (`bound_*`) and a `context_json` in addition to the design's list, so rebind lookup (7.4) can compare a new hold to prior reviews without recomputing bindings. `run_id` on `holds` is nullable for the project-level init confirm. Reason: the design says holds are bound; this is where the bindings live before a review exists.
- `actions` carries `param_source_json` and `ticket` as columns because design 5 lists them on the Action record. `runs` carries a reserved `budgets_json` (design 17). `artifacts` carries `name` and `status` (`produced | rejected`) so a post-gate block can quarantine outputs (6.2). `judgments` carries `attempt`.

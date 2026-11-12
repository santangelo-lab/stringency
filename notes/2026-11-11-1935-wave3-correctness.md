# 2026-11-11 19:35: wave 3's small correctness rows (L106, L37, K4, L80; K3 left open)

Branch `wave3-correctness`, from `main` at 03eb62c (#32). Beside `wave2` (#33) and `wave3`
(#34), which are not merged; this branch touches none of #34's files except that `deliver.py`
now calls the review export (#34 does not touch it). All three edit `PLAN.md`, the archive, the
order note and this index, so the second and third to merge have those to reconcile.

## Goal

The rows of wave 3's correctness half that were left after L145 and L148, other than L172
(#34): L106, L37, K3, K4, L80.

## Done

- **L106.** `Action.__post_init__` freezes `parameters`, `param_source`, `inputs` and `rationale`
  into `stringency.frozen` (`FrozenDict`, `FrozenList`: `dict` and `list` subclasses that refuse
  any change in place). `actions.check_params_hash` refuses a mismatch in `write_action` and in
  `steps.job_for`; the job's stdin carries a plain copy. `tests/test_action_immutable.py`.
- **L37.** `review --export [--run] [--module <name>[@<version>]]` (`review_export.py`): one
  document per hold a review resolved, frontmatter above the packet written when the hold
  opened, into `runs/<run>/reviews/` (the delivery half waits on the owner, below). The `stringency-revise` skill in `templates/method-repo/.claude/skills/`. Design 7.6
  (a paragraph) and 14.1. `tests/test_review_export.py`.
- **K4.** The board's "Newest change" line (`board.latest_change`, `newest_change`) and
  `board --watch [--interval]` (`board.watch`). Design 14.1 and 14.4. `tests/test_board_watch.py`.
- **L80.** `docs/release.md`: "The institutional runs" (the list) and "Record a known-good
  combination (every release)"; `known-good.yml` and `compat.yml` point at it (comments only).
- `DECISIONS.md` (three entries); the four rows archived; K3 rewritten; two rows in the waiting
  table; the order note's two tables.

## After the review of #35

- Keys frozen as JSON writes them and the parameters hashed frozen (a default keyed by YAML
  booleans or null had been refused on every proposal); a frozen value built frozen all the way
  down, `__init__` inert, `.copy()` deep, `thaw` documented in design 5, YAML dumps it,
  `deepcopy(action)` is the Action.
- `job_for` compares the inputs the plan resolves with the Action's recorded inputs (design 5).
- `review --export` out of `deliver`; it refuses verdict flags and an unknown run. Reviewer
  names and packets in a delivery: the owner's (waiting table).
- `board --watch` opens each trace `mode=ro`, no migration (`Store.open(read_only=True)`).
- The two L106 tests now test what their names say.

## Checked

- The focused tests above, `test_gate`, `test_steps`, `test_run`, `test_open_exec`,
  `test_propose_recovery`, `test_board_present`, `test_template`, `test_compat`; ruff, format,
  mypy, `check_no_biology.sh`.
- The full suite (`uv run pytest -q`): green, 739 passed and 1 skipped, exit 0.

## Not checked

- `review --export` on a real project's trace (the Lyons holds): only on the toy.
- `board --watch` on a terminal over the lab's projects: only through its function.
- The `stringency-revise` skill has not been used by an agent on a method.
- The institutional list was not run: it is the owner's at the next release.

## Learned

- `jsonschema` takes no tuple as an array, which rules out tuples for read-only parameters; a
  `list` subclass is what every reader already accepts.
- No column carries a type anywhere the engine reads one, so K3's warning has nothing to read
  (the row says what would give it one).
- `known-good.yml`'s latest row is 0.2.40; 0.2.41 and 0.2.42 have none.

## Altered

- Design 7.6 gains a paragraph and 14.1 two clauses (`review --export`, `board --watch`); 14.4
  a sentence. No contract changed: no trace column, no exit code, no predicate.
- A predicate that tries to change its context's Action now raises (recorded as fired) where it
  silently changed what would run.

## Open

- K3: column types, the owner's (waiting table).
- L80's step from now on, and the rows for 0.2.41 and 0.2.42: the owner's (waiting table).
- L172 is #34's.

## Verify

    uv run pytest -q tests/test_action_immutable.py tests/test_review_export.py tests/test_board_watch.py

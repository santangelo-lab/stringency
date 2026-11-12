# 2026-11-12 13:15: review documents in the delivery; every session named in a run's trace

Branch `reviews-in-delivery`, from `main` at 5eadee6 (engine 0.2.43, #36). No version bump.

## Goal

Two small changes for one pull request. (1) The owner ruled on 2026-11-12 that a delivery
carries the hold reviews (reviewer names and whole packets) that #35 had taken out of
`deliver`: put them back, before the delivery is recorded and under `index.json`'s hash.
(2) A study runs over several operator sessions, and an eval bundle links the trace to their
transcripts by the session references the engine records: find out when the engine records
one, and make a later session that works on an existing run leave its reference.

## Done

- **Reviews in the delivery.** `review_export.documents` renders every resolved hold's
  document in memory; `export_reviews` (`review --export`) writes them into the run directory
  as before; `write_into_delivery` writes them into `deliver/<run>/reviews/<hold>.md` and
  returns the `index.json` entries (`file`, `hold`, `step_id`, `module`, `blake3`). `deliver`
  (closed) and `write_open_delivery` (open) render them before anything is recorded (before the
  deliver gate's verdicts), write them before the finals are marked, list them in
  `index.json` `reviews[]` and count them in the `delivered` event. An error rendering or
  writing them is exit 1, "no delivery was recorded". The `deliver` and `run --deliver`
  payloads carry `reviews`. Design 7.6 and 12.1 (and the layout in 2), `trace-schema.md`,
  `DECISIONS.md` (the #35 entry corrected, a new entry), the PLAN waiting row marked answered.
- **Session references.** What the engine recorded before: `stringency.yml` `declarations`
  at `init` (agent-drafted only, not in the trace); `runs.operator_session_ref` once, when a
  run opens (`runs.open_run`: `run`, `fork`, an open project's run); `reviews.operator_session_ref`
  on every review; the `questions`, `findings` and `flags` rows; the `proposal_withdrawn` step
  event. Nothing on `run`, `propose`, `call`, `exec` or `deliver` carrying an existing run on,
  so a later session that only did those left no trace of itself (confirmed by the new test
  on `main`'s store: no reference for session B). Now `Store.run_event` and `Store.step_event`
  call `note_session`, which appends a `session` run event (`session_ref`, `harness`,
  `version`) in the change's transaction when the current reference is set and differs from
  the last the run recorded (latest `session` event, else the run's column). `status --json`
  `sessions` reads them.
- The operator skill's section 2 says to set the three variables at the start of every
  session, a resumed one included, with this session's own frame id, and that the engine
  records a later session's first change to a run.
- Tests: `tests/test_review_export.py` (the index and its hash, twice the same, a render error
  and a write error each stop before anything is recorded, an empty list, the open delivery
  carries them and regenerates unchanged); `tests/test_session_refs.py` (two sessions, one
  run; the same session twice; the first session returning; a reading verb; a rollback).

## Checked

- The focused tests above and `test_run`, `test_deliver`, the open-mode delivery tests,
  `test_operator_skill_line`, `test_render_skill`, `test_harness_adapters`, `test_wait`,
  `test_board_*`, `test_store`, `test_audit`, `test_propose_recovery`; ruff, ruff format,
  mypy, `check_no_biology.sh`.
- The full suite (`uv run pytest -q`): 804 passed, 1 skipped, exit 0.

## Not checked

- No real project's delivery with review documents (the Lyons holds): the toy only.
- The beta package's bundle (`stringency-beta`, `bundle.trace_facts`) reads `runs` and
  `reviews` directly and merges `status --json` `sessions` when an engine answers; with a
  copied trace and no engine it does not yet read the `session` events. That change is the
  beta repository's.
- No Claude Science session was driven with the new skill text.

## Learned

- A closed delivery's `index.json` carries `delivered`, the time, so two deliveries of the same
  run never have the same index hash; what repeats exactly is every file and every entry,
  `reviews[]` included. An open delivery's index is deterministic and repeats whole.
- Every verb that changes a run writes a run or step event through the store, which is why the
  session hook needs one place and no verb's code.

## Altered

- An open delivery written before this has no `reviews` key, so its next regeneration differs
  once and writes one `deliveries` row.
- No contract changed: no trace column, no exit code, no predicate; `session` is a new run
  event name, and `index.json` gains a key.

## Open

- The `stringency-beta` bundle reading `session` events from a copied trace (its own repository).
- The operator skill republished to Claude Science with the next engine tag (the owner's).

## Verify

    uv run pytest -q tests/test_review_export.py tests/test_session_refs.py

# 2026-11-11 19:00: `per_item` numbered by the module's replicate (L172); the judges' tokens in the coverage report (L193)

Branch `wave3-l172-l193`, from `main` at 03eb62c (#32). Beside #33 (`stringency-wt-wave2`),
which is not merged; the two touch different code and both edit `PLAN.md`, the archive, the
order note and this index, so the second to merge has those to reconcile.

## Goal

Two rows of wave 3: the correctness row the Xenium method's two judgment modules moved to
`all_items` for (L172), and the engine's share of measuring what a project costs in tokens
(L193).

## Done

- **L172.** `Request` keeps `replicate` as the module's and gains `request_no` (its dispatch
  files and nonce) and `item`. `assemble_requests` renders a `per_item` prompt for its item
  alone (`judgment.item_values`). `repeat.gather` joins a replicate's item requests into one
  `{"items": [...]}` answer before anything reads it; a replicate is invalid when any of its
  requests is, and `Replicate.error` names the item. Dispatch files are numbered by request
  and name replicate and item; the manifest's `replicates` is the module's count;
  `dispatch_target` counts the manifest's `responses`. `replicates_from_trace` reads one shape.
  The invocation's `sampling_json` names the item.
- **L193.** `coverage.judge_tokens` and `tokens_text`: `judgment[].tokens` per step and
  `judgment_tokens` for the run (calls; tokens in and out over the calls that reported them;
  the calls that reported none, in and out apart; null, not zero, when none did). The text
  gains a `judges:` line per step and a run line.
- Design 3.5 (the batching paragraph), 10.2 (the dispatch layout) and 12.2 (an "Added"
  paragraph); `DECISIONS.md` (the last entry); both rows moved to `archive/backlog-done.md`;
  `PLAN.md` "Next, in order" and the order note's two tables.
- `tests/test_per_item.py`: eight tests, one parametrised six ways (thirteen cases).

## Checked

- The L172 tests fail on the code before the change (nine of them) and pass after.
- `per_item` and `all_items` give the same consensus rows, holds and coverage counts for the
  unanimous, split and one-abstention mock fixtures, by the direct and the dispatch family.
- A `per_item` module committed to the method on disk: the split item holds, `review accept
  --replicate 1` resettles the step from the trace, and the consensus file reads as under
  `all_items`.
- The full suite: 741 passed, 1 skipped (exit 0); ruff, ruff format, mypy and the biology check clean.

## Not checked

- No real judge was run: the mock harness only. A real reviewer has never answered a
  `per_item` prompt from this engine.
- The Xenium method's `choose-fine-label` and `label-domains` were not moved back to
  `per_item`; their prompts say "each listed cluster", which reads oddly for one.
- The token sums against a real subagent or API run: the mock's counts are characters over
  four, and its dispatch responses report no usage.

## Learned

- Before this, a `per_item` request also carried the whole table and every item under a
  one-item schema and never said which item it asked about; only the mock knew (from
  `item_index`). The prompt fix belongs to the same row.
- The `judg.*` predicates number replicates by position and read `items` from each, so a
  flat per-item answer had no items to them at all: every replicate was incomplete, whatever
  its number.

## Altered

- Design 3.5 and 10.2 say how `per_item` is numbered and rendered; 12.2 gains the token lines.
  Below the frozen contracts: the trace schema is unchanged (the item is in `sampling_json`).
- A `per_item` prompt now differs from before (one item, one row), so its hash differs; no
  method ships a `per_item` module.

## Open

- No version bump: 0.2.43 carries wave 2's remainder, #29 and these.
- The Xenium method may return its two modules to `per_item` with that engine floor (its own
  backlog, and its prompts' wording).
- Wave 3's correctness half: L106, L80, L37, K3, K4. Measurement: L194's merge, then L190.

## Verify

    uv run pytest -q tests/test_per_item.py

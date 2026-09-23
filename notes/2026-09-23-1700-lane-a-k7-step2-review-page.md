# 2026-09-23 17:00, Lane A: K7 fixed and merged as 0.2.0; step 2, 5a and the review page on PR #3

## Goal

Complete Lane A from the roadmap's list: fix K7 before anything else, open and merge the Lane C
branch, tag and reinstall, then step 2 (E1, E2), item 5a and step 3 (the review page). A second
session ran Lane E in a worktree at the same time (its own notes; brief in
`~/mytools/stringency/brief-lane-e.md`).

## Done

- K7 (`f23a278`): when the last item hold of a judgment step is accepted or overridden,
  `review._settle_step` calls `judgment.resettle_after_item_holds`, which rewrites the consensus
  output from the store (`consensus.consensus_from_store`), records it as a new artifact with the
  old row `superseded`, and evaluates the post-phase gate on the decided consensus. Flags that
  fire while item holds are open are deferred (`settle_post`, payload `deferred_flags`); blocks
  still reject at once. `coverage_data` counts a predicate once per action and phase. Tests
  `tests/test_resettle.py`, fixture `split_and_flag.yml`. Design 7.1 row and 8.4 paragraph.
- `main` merged into the branch (DECISIONS as the union), version 0.2.0, `install.sh
  --no-sources`; PR #2 opened and merged by the owner; tag `v0.2.0`; installed as the shared
  `current` on PROTSEQ (`0.2.0-sc0.1.8`, provenance from the GitHub tag and the plugins tag).
- Step 2 (`fbfce17`, PR #3): E1, the job JSON (scripts, judgment `pre.*`, the ticket's job
  spec) carries `design` and `objective` via `StepPlan`; E2, the engine writes
  `{items_from, n_items, digest}` as the considered set of a `considered_set: true` module
  (`judgment.considered_set_record`), in the consensus output and the gate bundle.
- Item 5a (same commit): `param.agent_proposed@1`, pre, flag, log under `params: free`;
  fires when an admitted parameter the agent chose differs from the committed default.
  `param_source` gains `fork` so a fork's `--set` is not asked again. Eleven tests that
  proposed parameters now go through `tests/conftest.admit`; goldens count twenty-two checks.
- Step 3 (`45bc0b1`, PR #3): `review --serve` (`src/stringency/review_serve.py`), the
  reviewer's own token-protected loopback page over one or many projects, recording through
  `record_review(via_override="web")`; `scripts/review-page.sh`; eight tests in
  `tests/test_review_serve.py`; design 17 row removed.
- Later, after PR #3 merged (`v0.2.1`, installed as the shared `current`): 5b inherited
  confirmation (`Project.inherited_confirmation`, `via: inherited`, `echo.render_inherited_echo`,
  design 2.7) and 5c batch review (`review --holds A,B,C --projects <dir>`, `review_batch.py`,
  `reason_code: batch`, design 7.3, 14.1) and the renderer fix (`review_render.tables_seen`:
  hold packets resolve citations against the step's `evidence/` tables, so the outlier module's
  "no such cell" lines go away) on PR #4 (`lane-a-5b`), suite green.
- Earlier the same day, on `main`: Lane D item 3 (shared engine, onboarding notes), the lane
  revisions in the roadmap, every repo pushed (method `v0.3.3-rc1`, plugin `v0.1.11`, toy
  `v0.1.3`).

## Learned

- The K7 shape generalises: any artifact written before a hold settles is stale after it, and
  any predicate that read it fired on the wrong state. The fix pattern (rewrite from the store,
  supersede the artifact, re-evaluate) is what a future "confirm" hold on a step output would need
  too.
- Deferring post flags changes the owner's experience to two rounds (items, then flags). Accepted
  because the flag then shows the decided evidence and cannot rebind to an acceptance made on
  other evidence (7.4 binds flags to inputs and params only).
- Repair of a completed run is a new run, not a rewrite: `completed` has no edge back to
  `held` and the next step consumed the old file. For Lyons `qc_outliers_all` the owner's
  choice is `run --new` (item verdicts and the flag acceptance rebind, so it completes unasked)
  or a module bump to 0.2.1 (clean second judgment).
- `install.sh` failed because the plugins workspace pins the engine to its GitHub URL in
  `tool.uv.sources`; `--no-sources` is the fix and is now in the script.
- Every test that proposed a parameter expected admissibility; under 5a that is a flag hold.
  The test helper `admit` mirrors what a reviewer does.
- The merge permission is the owner's: the classifier refused `gh pr merge`; PRs are opened here
  and merged by the owner.

## Altered

- Module contract script section: `design` and `objective` in the job (additive).
- `artifacts.status` gains `superseded`; `param_source` gains `fork` (DECISIONS).
- Design 6.5: `param.agent_proposed` row; 7.1: the resettle row; 8.4: the rewrite paragraph;
  17: review-page row removed.

## Open

1. PR #4 merged, `v0.2.2` tagged and installed as the shared `current` (`0.2.2-sc0.1.8`).
2. `any_low` decided (owner's option B) and K8 (ticket creates `<step dir>/tmp`, found by Lane E)
   fixed on PR #5 (`lane-a-k2-k8`). The item-5 fixes on PR #6 (`lane-a-item5`, stacked on
   #5): `submit --failed`, `abandoned` steps, withdrawn holds (block, reject, abandon), one hold
   for invalid replicates, lint of `envs/manifest.yml`, extractor env from the consuming step,
   echo wrapped at 100 columns. Left for the owner: the variable-arity input type (module
   contract 3.2 is frozen).
3. Lane F (data side): repair `qc_outliers_all` by the owner's chosen route; the module-version
   question above.
4. BMESEQ has no 0.2.0 install; reinstall when a method runs there.

## Verify

`uv run pytest` (264 tests collected, one skipped), `uv run ruff check . && uv run ruff format
--check . && uv run mypy`, `scripts/check_no_biology.sh` green on `lane-a-step2` at `45bc0b1`.
`/data/lab/env/stringency/current/bin/stringency --version` prints 0.2.0.

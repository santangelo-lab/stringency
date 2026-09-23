# 2026-09-23, Lane A: the day the engine went from 0.1.0+branch to 0.2.4, and Lane A closed

One Claude Code session on PROTSEQ, morning to night, in the engine checkout at
`~/mytools/stringency/stringency`; a second session ran Lane E in a worktree at the same time
(`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`; brief `~/mytools/stringency/brief-lane-e.md`).
Every engine change of the day went to `main` through a PR the owner merged (PRs #2 to #6 and
#8); after each merge the session tagged and reinstalled the shared engine. Eight tags in one
day is unusual; it happened because the owner was at the keyboard to merge and each step was
worth having installed for Lane E's toy run.

## Goal

Complete roadmap Lane A: fix K7 before anything else, land the Lane C branch, then step 2 (E1,
E2), item 5 (5a to 5c and the smaller fixes), step 3 (the review page), item 6, the `any_low`
question, and whatever Lane E found. Along the way: Lane D item 3 (the shared engine), the
lane revisions the owner asked for, and every repository pushed.

## Done, in order

**Morning, on `main`.**

- Answered two questions from the roadmap and the outlier module: what a `review` label does
  downstream (nothing automatic; the flag hold and the proposal table), and where the roadmap
  stood. Found `stringency present` showing a stale `consensus.json`, which became K7.
- Lane revisions (owner): Lane C closed as completed; Lane F placeholder for the spatial method
  build-out with Lyons CLP as pilot; Track 2 and Lane B dormant, kept as written; Lane D closed.
- Lane D item 3: the shared engine at `/data/lab/env/stringency` (`install.sh` needed
  `--no-sources` against the plugins workspace's pin; now in the script), the owner's PATH and
  link switched, `render_brief.py` default, `new-project.md`, README; notes
  `hosts/protseq-shared-install.md`, `hosts/protseq-lab.md`, `onboarding.md`, `publish-skills.md`.
- Every repository pushed: engine `main` and the Lane C branch, plugins `v0.1.11`, method
  `v0.3.3-rc1` (with its new `PLAN.md`), toy method `v0.1.3` (BMESEQ remote; its working copy is
  on `main`, so the push went `main:master` and was fast-forwarded there).

**PR #2, `v0.2.0`: the Lane C branch and K7.** `f23a278` and the merge of `main` into the
branch (DECISIONS as the union).

- K7: when the last item hold of a judgment step is accepted or overridden,
  `judgment.resettle_after_item_holds` rewrites the consensus output from the store
  (`consensus.consensus_from_store`), records it as a new artifact (the old row `superseded`)
  and evaluates the post-phase gate on the decided consensus. Post flags raised while item holds
  are open are deferred (`settle_post`, payload `deferred_flags`), so `sc.exclusion_proposed`
  opens on the decided punches and cannot rebind to an acceptance made on other evidence.
  `coverage_data` counts a predicate once per action and phase. Design 7.1, 8.4.
- A completed run is not repaired in place (no edge back to `held`; the next step consumed the
  file): the repair is a new run or a method bump (DECISIONS).

**PR #3, `v0.2.1`: step 2, 5a, the review page.** `fbfce17`, `45bc0b1`.

- E1: the job JSON (scripts, judgment `pre.*`, the ticket's job spec) carries `design` and
  `objective` via `StepPlan`. E2: a `considered_set: true` module gets `{items_from, n_items,
  digest}` of the items table in its consensus output and gate bundle
  (`judgment.considered_set_record`).
- 5a: `param.agent_proposed@1` (pre, flag; log under `params: free`) when an admitted parameter
  the agent chose differs from the committed default; `param_source` gains `fork` so a fork's
  `--set` is not asked again. Eleven tests that proposed parameters now go through
  `tests/conftest.admit`.
- Step 3: `review --serve` (`src/stringency/review_serve.py`), the reviewer's own token-protected
  loopback page over one or many projects, recording through `record_review(via_override="web")`;
  `scripts/review-page.sh` opens the tunnel; eight tests. Design 17's reserved row removed.

**PR #4, `v0.2.2`: 5b, 5c, item 6.** `09d86d5`, `b96024c`, `00ded11`.

- 5b inherited confirmation: every input `derived_from` a run of a project the same owner
  confirmed, byte-identical `design.yml`, same method major version: the confirm hold is created
  and resolved at once by reference (`reviews.via = inherited`); the echo-back shows only what is
  new (`echo.render_inherited_echo`). Design 2.7, 7.5.
- 5c batch review: `review --holds A,B,C --projects <dir>` compares sibling projects' three
  declaration files field by field, shows the shared files once and the differing fields per
  project, then the shared echo; `--verdict accept|reject --reason` records one `reviews` row per
  hold, `reason_code: batch` (`review_batch.py`). Design 7.3, 14.1.
- Item 6's renderer fix: `review_render.tables_seen` resolves citations against the step's
  `evidence/` tables (secondary tables keyed by their own column), so the outlier module's
  "no such cell" lines go away.

**PR #5, then PR #6, `v0.2.3`: K2, K8, the item-5 fixes.** `lane-a-k2-k8`, `lane-a-item5`.

- K2, owner's option B: low confidence on an agreed label is a consensus note, not a hold
  (`consensus.decide`); `any_low` keeps its place in the policy vocabulary. Design 8.4.
- K8 (found by Lane E): `write_job_file` creates `<step dir>/tmp`, which the apptainer line binds
  as `/tmp`; every operator-run step under 0.2.x had failed at container start.
- `submit <ticket> --failed --reason [--exit-code] [--evidence]`: the operator closes a failed
  external run; `propose` opens the next attempt on the same run.
- `StepStatus.ABANDONED` with an edge from every open status; `abandon` closes open steps and
  withdraws the run's holds.
- Withdrawn holds (`Store.withdraw_holds`, `resolved_via: withdrawn`, no review): an open hold is
  now `resolved_by_review IS NULL AND resolved_via IS NULL` everywhere; a post-phase block
  withdraws the item holds it closed; a reject on one hold of a step withdraws its siblings, so the
  next `review` shows attempt 2's holds; `review` refuses a withdrawn hold. Design 7.2.
- Invalid replicates open one step-level `run_disagreement` hold (context: which replicates and
  their errors) instead of one per item; items note them and are decided from the valid
  replicates; `verdicts_for(item_level=False)`, `render_step_invalid`. Design 7.2, 8.4.
- `lint` parses `envs/manifest.yml`; init extraction runs in the env of the step that binds the
  input (`Project.env_for_input`); `echo.md` wraps at 100 columns (`summary.echo_body` skips the
  wrapped note).

**PR #8, `v0.2.4`: `arity: many` (module contract amendment, approved by the owner).**
`lane-a-many`.

- A module input may declare `arity: many`; the pipeline binds a list of references or
  `$inputs.<glob>` (every manifest input whose name matches and whose type is the input's, in
  name order); the script receives a list of paths; the action records one digest for the input
  (hash of the parts' digests in order); lint refuses a list or glob on a one-arity input and
  `many` on judgment evidence. `Ref` allows `*` in `$inputs` names only; `StepDecl.refs()`
  returns lists; `ResolvedInput` carries `paths` and `digests`. Module contract inputs row and
  script section; design 3.1.

Installed on PROTSEQ at the end: `/data/lab/env/stringency/current -> versions/0.2.4-sc0.1.8`
(engine tag `v0.2.4`, plugin `v0.1.11`), provenance from the GitHub tags.

## Learned

- The K7 shape generalises: any artifact written before a hold settles is stale after it, and
  any predicate that read it fired on the wrong state. Rewrite from the store, supersede the
  artifact, re-evaluate.
- Deferring post flags gives the owner two rounds (items, then flags). Accepted: the flag then
  shows the decided evidence and cannot rebind (7.4 binds flags to inputs and params only).
- Every test that proposed a parameter expected admissibility; under 5a that is a flag hold. The
  test helper `admit` mirrors what a reviewer does. A fork's `--set` is a person's decision and
  must not be asked twice, hence `param_source: fork`.
- A hold nobody reviewed must not look reviewed, and must not outlive its attempt: hence
  `withdrawn`, distinct from every `via` a person produces.
- The permission classifier refuses `gh pr merge`; PRs are opened here and merged by the owner.
  Tag and reinstall follow each merge; `install.sh` from a GitHub tag records clean provenance.
- Both `stringency-plugins` and the toy method needed care when pushing: the workspace pins the
  engine to its GitHub URL (`--no-sources`), and BMESEQ's toy working copy is on `main`.

## Altered

- Module contract: script section (`design`, `objective`; a list of paths for `arity: many`),
  inputs row (`optional`, `arity`). Amendment approved by the owner for `arity`.
- `artifacts.status` gains `superseded`; `param_source` gains `fork`; `reviews.via` gains
  `inherited` (and the engine's `rebind`); holds gain `resolved_via: withdrawn`;
  `StepStatus.ABANDONED`; `reason_code: batch` is the column's first use.
- Design 2.7 (inherited confirmation), 3.1 (references, globs), 6.5 (`param.agent_proposed`),
  7.1 (resettle, abandoned, `submit --failed` rows), 7.2 (withdrawn, one hold for invalid
  replicates), 7.3 (batch review), 7.5 (`via` list), 8.4 (rewrite paragraph, `any_low`, invalid
  row), 14.1 (`review --serve`, `--holds`), 17 (review-page row removed).
- Twenty-odd DECISIONS entries; backlog K2, K7, K8 resolved.

## Open

1. Lane A has nothing left. The method side of `arity: many` (the cross-region summary as one
   `metrics: $inputs.metrics_*`) is Lane F's, with the Lyons repair of the stale outlier proposal
   (a new run, or a module bump to 0.2.1, recommended) and the module refinements in the method's
   `PLAN.md`.
2. Lane E: three template fixes and a re-tag, the run by someone other than the owner, then the
   lane closes (its note).
3. Lane F needs its plan document before it opens.
4. BMESEQ has no 0.2.x install; reinstall when a method runs there.
5. Owner housekeeping: delete the tags pushed before checks passed (K6); merge the splitter
   `determinism` branch into `master`.

## Verify

`uv run pytest` (about 300 tests, one skipped), `uv run ruff check . && uv run ruff format
--check . && uv run mypy`, `scripts/check_no_biology.sh` green on `main` at `v0.2.4`.
`/data/lab/env/stringency/current/bin/stringency --version` prints 0.2.4; `stringency status` in
`/lab/projects/Lyons_CLP/qc_outliers_all` reads the trace from the shared engine.

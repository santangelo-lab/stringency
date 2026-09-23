# notes index

The map of session notes. One line per note, newest first. Keep the current-state block accurate;
it is the first thing a new session reads.

## Current state (2026-09-23, night)

- Lane A complete (`notes/2026-09-23-1700-lane-a-k7-step2-review-page.md`, the day's record):
  PRs #2 to #6 and #8 merged, tags `v0.2.0` to `v0.2.4`, `v0.2.4` installed as the shared
  engine on PROTSEQ (`/data/lab/env/stringency/current`, `0.2.4-sc0.1.8`). In it: the K7 consensus
  rewrite, E1 and E2, `param.agent_proposed` and `fork`, the review page, inherited confirmation,
  batch review, the renderer's citation lookup, `any_low` option B, K8, `submit --failed`,
  `abandoned` steps, withdrawn holds, one hold for invalid replicates, env-manifest lint, extractor
  env per input, echo width, and `arity: many` (contract amendment). Lane C closed, Lane F
  placeholder (plan document to write; the method side of `arity: many` and the Lyons outlier
  repair go there), Lane D closed, Lane B dormant. Start the next engine session from the roadmap's
  Status section; the next data-side session from `/lab/projects/Lyons_CLP/PROGRESS.md` and the
  method's `PLAN.md`.

## Lane E state (2026-09-23, afternoon)

- Lane E (`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`), all merged to `main` (PR #1,
  PR #7): Track 1d built (`render_skill.py`, `analyze-skill.md.j2`, method-repo `skills/`
  template, `tests/test_render_skill.py`); `spec/method-skills.md` is the page for the two skill
  files per pipeline; toy method `v0.1.4` carries the first analysis skill
  `stringency-analyze-toy-compare`. The owner ran both UX 3.4 session tests (download card is
  conversation-scoped per directory; `call_command` offers a project-scoped grant that covered
  every later command) and the toy through the skill: 7 turns, 14 min 39 s to the first delivered
  file, 0 misreports, confirm relayed; row in `backlog.md` (cards to fill); findings and the
  engine defect K8 (fixed by Lane A the same day) in `hosts/protseq-session-tests.md`. Open:
  three template fixes and a re-tag, the run by someone other than the owner, then close the lane.

## Previous state (2026-09-22, afternoon)

- Plan documents refreshed to the Lane C state of 2026-09-17 to 2026-09-21
  (`notes/2026-09-22-1510-plan-docs-refresh.md`): roadmap Status section and per-lane status,
  `app1-spatial-qc-plan.md` section 5 (outcome against plan), backlog K1 to K6, the branch's three
  DECISIONS lines and the board note now on `main`. Nothing ran. Still open: the seven
  `qc_outliers_all` holds for the owner; the PR for `lane-c-directory-inputs` (eight commits ahead,
  design 14.4 and the optional and reference input sentences exist only there); Lane A steps 2 to 4
  and items 5 and 6; Lanes B and E not started. Start the next engine session from the roadmap's
  Status section and Lane A state paragraph.

## Previous state (2026-09-21, evening)

- Outlier judgment v2: the owner rejected the v1 rule on Lyons CLP; method 0.2.0 (v0.3.3-rc1,
  local tag) has reviewers reason from direction-aware MAD bands, a guide, floors, group and
  reference bands; plugin 0.1.8 (v0.1.11) adds `punch_qc_verdict@2` (no exclude). Engine branch
  `lane-c-directory-inputs` +3: optional module inputs, secondary evidence keys, `role: reference`
  (`notes/2026-09-21-1600-outlier-judgment-v2-engine.md`); installed as `0.1.0+optin3-sc0.1.8`.
  First real run held on six item holds and the flag for the owner. Open: packet renderer for
  multi-table evidence, `any_low` on unanimous items, Lane A per-item flag resolution, the PR.

## Previous state (2026-09-18, evening)

- Lane C S4 delivered on all eight Lyons CLP regions (four vendor, four Proseg via chained
  `reseg_*` projects); cross-region summary delivered; first real judgment (outlier proposal) at
  its flag hold for the owner. `notes/2026-09-18-2000-lane-c-day2-proseg-summary-judgment.md`.
  Engine changes of both days live on branch `lane-c-directory-inputs` (PR to open); method
  v0.3.2-rc2, plugin v0.1.10. Data-side log: `/lab/projects/Lyons_CLP/PROGRESS.md` and
  `STATUS.md` (the `board`). Roadmap Lane A item 5 records the hold redesign.

## Previous state (2026-09-17, evening)

- Lane C day 1 done: `xenium-qc` delivered on the four vendor-segmented Lyons CLP regions;
  `xenium-qc-proseg` running on 0076581 Lung (Proseg since 15:24 local). Everything in
  `spec/plans/lane-c-day1-2026-09-17.md` (running log, hold ids, decisions, engine gaps) and
  `notes/2026-09-17-1900-lane-c-day1-clp-qc.md` (summary, pick-up point). Engine changes for
  directory inputs/outputs, symlinked binds, per-step tmp, and `propose --new` are UNCOMMITTED in
  the PROTSEQ checkout pending the owner. Lane D items 2 and 6 done; Lane A steps 2 to 4 open.

## Previous state (2026-09-15, afternoon)

- Phase A exit complete on both machines (BMESEQ `toy-cs` 2026-09-08; PROTSEQ two chained projects
  from agent-drafted declarations 2026-09-14). Backlog sections A to I done except A5 (review page,
  now Lane A step 3), E2's in-session route, G2 and H5 (design questions); J1 added 2026-09-15.
- Roadmap approved 2026-09-14: `spec/plans/roadmap-2026-09.md`, Order rewritten as five lanes
  2026-09-15 (A engine, B bulk, C spatial on the critical path, D owner and operations, E skills).
  Track 1 detail in `spec/plans/ux-two-audiences.md`; Track 2 in `spec/plans/bulkrna-plan.md`;
  Track 3 in `spec/plans/app1-spatial-qc-plan.md`.
- Approvals collected 2026-09-15: the five Track 1a amendments applied to the design; Track 2
  session-0 decisions answered except the DESeq2 parameter list; Track 3 decisions answered; Track
  3 S0 inventory done. Bulk delivery is development data; Track 3 S1 to S4 precede Track 2
  sessions 9 to 12.
- Lane A step 1 done 2026-09-15 (commit "Lane A step 1"): `operator_line`,
  `run --responses`, `run --deliver`, `steps[].title`, `plain` and `completed_steps`, `--attest`
  needs a session ref, `reviews.operator_harness` (migration 4), `summary.md`; operator skill and
  templates rewritten with the intent table and the hold protocol. Engine not re-tagged; installed
  on PROTSEQ as `0.1.0+lane-a-1` (`current`); toy method tagged `v0.1.3` locally, not pushed. A
  test drive ran 2026-09-15: 17 cards against 26, relayed confirm, no flags
  (`integrations/claude-science/hosts/protseq-track1b-drive.md`; row in `backlog.md`). Open: J1
  `--print-hashes`, J2 `submit --deliver`, the standing-grant question of 3.4, transfers as cards.
- `v0.1.0` tagged and pushed 2026-09-14; engine repo public; singlecell and toy method repos
  pushed; engine 0.1.0 installed from the tag on both machines.
- Next sessions: Lane A step 2 (`spec/plans/bulkrna-plan.md` section 2, E1 and E2); Lane B with
  `spec/plans/bulkrna-plan.md` section 8; Lane C with `spec/plans/app1-spatial-qc-plan.md` section
  3 S1; Lane E (republish the operator skill, 3.4 session tests) now open. Read
  `notes/2026-09-15-1500-lane-a-step1-flags-and-skill.md` first in Lanes A and E.

## Notes

- `2026-09-23-1700-lane-a-k7-step2-review-page.md` — Lane A, the whole day: K7, Lane C branch merged, E1/E2, `param.agent_proposed`, review page, inherited confirmation, batch review, renderer fix, `any_low` B, K8, item-5 fixes, `arity: many`; tags 0.2.0 to 0.2.4; Lane A complete.
- `2026-09-23-1355-lane-e-skills-and-first-run.md` — Lane E: analysis skill template and `render_skill.py` (Track 1d), `spec/method-skills.md`, toy method `v0.1.4` with `stringency-analyze-toy-compare`, the UX 3.4 session-test answers, the first measured run through an analysis skill (7 turns, 0 misreports), K8 found.
- `2026-09-23-1100-outlier-holds-stale-consensus.md` — the owner's seven verdicts relayed and the run delivered; item verdicts reach the `consensus` table but never the `consensus.json` the next step binds, so the proposal is stale (backlog K7).
- `2026-09-22-1510-plan-docs-refresh.md` — plan documents brought up to date after Lane C: roadmap status, Track 3 outcome, backlog K1 to K6, the spec split between `main` and the engine branch.
- `2026-09-21-1600-outlier-judgment-v2-engine.md` — optional module inputs, pre-produced evidence tables keyed by their own column, `role: reference` inputs; first three-replicate real judgment on Lyons CLP and what it showed about confidence criteria and the packet renderer.
- `2026-09-18-2000-lane-c-day2-proseg-summary-judgment.md` — Lane C day 2: Proseg route delivered, cross-region summary, first judgment on real data, board and present in the operator skill.
- `2026-09-18-1830-board-and-present.md` — `board` and `present`, plugin-free reading verbs; method delivery skills (design 14.4); written on the engine branch, copied to `main` 2026-09-22.
- `2026-09-17-1900-lane-c-day1-clp-qc.md` — Lane C day 1: Lyons CLP QC on the four vendor-segmented regions, resegmentation started, engine gaps.
- `2026-09-15-1500-lane-a-step1-flags-and-skill.md` — Lane A step 1: Track 1b engine flags (`operator_line`, `run --responses`, `run --deliver`, titles, `plain`, attest session ref, migration 4, `summary.md`) and the Track 1c operator skill with the hold protocol.
- `2026-09-15-1400-bulk-depth-replan.md` — the RMLDH7 delivery is shallow (spleen 0.9 M reads); Projects A and B become development projects; Track 3 moves ahead of Track 2 sessions 9 to 12.
- `2026-09-15-1300-app1-inventory.md` — Track 3 S0: Lyons CLP inventory from the collaborator's plan and TMA maps; slide-to-TMA mapping; layout table filed in the project directory.
- `2026-09-15-1130-approvals-walkthrough.md` — Track 1a amendments approved and applied; Track 2 and Track 3 decisions answered and recorded; DESeq2, Proseg mix, GHCR images.
- `2026-09-14-1600-track0-and-roadmap.md` — surveys, the approved roadmap and its three track notes, section I code and skill text done.
- `2026-09-14-1445-protseq-exit-run.md` — PROTSEQ tooling, both skills live, two chained projects from agent-drafted declarations; section I of the backlog.
- `2026-09-09-1059-declare-and-chained-projects.md` — declare --check, drafted-by and brief, derived_from chained projects, the declare skill.
- `2026-09-09-0847-script-drift.md` — script drift check; the two classes of analysis code and the open G2 question.
- `2026-09-08-1655-improvements-backlog.md` — the improvements backlog worked through on the toy:
  review display and packets, operator ergonomics, trace semantics, toy method 0.1.1, design text.
- `2026-09-08-1542-phase-a-exit-bmeseq.md` — Phase A exit on BMESEQ from Claude Science: sandbox limits, remote-host
  mode, machine install, review-surface findings.
- `2026-09-03-1605-phase-a-m0-m11.md` — first build session: repository created, M0 through M11
  implemented against the design, end-to-end CLI rehearsal of the toy pipeline, singlecell skeleton.
- 2026-09-18-1830-board-and-present.md: `board` and `present` reading verbs; delivery skill schema (design 14.4); operator skill section 7.

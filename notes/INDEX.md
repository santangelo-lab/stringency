# notes index

The map of session notes. One line per note, newest first. Keep the current-state block accurate;
it is the first thing a new session reads.

## Current state (2026-10-26)

- QC failure modes (`notes/2026-10-26-2130-qc-failure-modes.md`;
  `spec/plans/qc-failure-modes.md`; rows L115 to L127, Next item 10):
  - Literature on droplet and imaging-spatial failure modes, through Consensus.
  - Thirteen new predicates proposed, plus `sc.qc_floor_above_data@2`. The mitochondrial rows
    (L115 to L118) come first.
  - Three decisions on the mitochondrial bound wait on the owner (D1 to D3).
  - Nothing built, nothing committed.
- Module scripts (`notes/2026-10-26-1315-module-scripts.md`; `spec/plans/module-scripts.md`; row
  L113):
  - The convention, template and toy are committed as `c62bcae`.
  - Every Xenium module is converted, in the method's `9bf12a7` and `0a945ed`, and verified
    identical on PROTSEQ under 0.2.34-sc0.8.4. The method also moved to the current predicates
    (L86).
  - L114 filed: a held open-mode tool call cannot finish.
  - `cluster-umap` gates `sc.louvain_too_large@2` (plugin 0.8.7, method `a8dc69a`). The shared
    install needs 0.8.7.
  - Phases 5 to 7 done: the scRNA-seq method (`f15590e`) verified identical; the Plasmidsaurus
    template (`2c93b04`); the wrap skill, tested by a fresh agent.
  - Tagged and pushed: Xenium `v0.6.0-rc20` and scRNA-seq `v0.1.10`, both with known-good rows
    for 0.2.34-sc0.8.7. Next: republishing the skills (the owner).
- Annotation controls (`notes/2026-10-23-1400-annotation-controls.md`;
  `spec/plans/annotation-controls.md`; rows L110 to L112, Xenium method items 3.15 to 3.21): the
  fine label stays one free-text string (the owner); `sc.fine_label_uncited@1` built in plugin
  singlecell 0.8.5 (`../stringency-plugins`); twenty candidate state programmes as evidence; one
  fine label of three by a reconcile step and a choosing judgment over the contested clusters
  (the owner chose both). Nothing committed; all three repos on `main`.
- The gate review filed (`notes/2026-10-22-1150-gate-review-filed.md`; `spec/plans/gate-soundness.md`;
  rows L100 to L109, Next item 9): the owner's eight limitations checked against `491f1aa`, all
  hold. First: L103 (a pre-gate accept rebinds a post-gate flag on the same attempt) and L100
  (`hold: always` is silent under `run`). Nothing built; merged to `main` as PR #16.
- The benchmark plan is in (`notes/2026-10-22-0700-benchmark-phase-0.md`;
  `spec/plans/benchmark-plan.md`; rows L87 to L92): Phase 0 started, the local Claude Code
  runner works on Opus 5, the public evals and Latch's image are on the workstation; the
  owner logged in and the baseline is running; Phase 1 is mostly done the same night: plugin
  singlecell 0.8.1 widened beyond Xenium and the method `stringency-scrnaseq-scanpy-method`
  0.1.0, both pushed.
- Benchmark Phase 0 measured and Phase 1 built (`notes/2026-10-22-0700-benchmark-phase-0.md`;
  `spec/plans/benchmark-plan.md`; rows L87 to L99): the Opus 5 baseline is 9/18 on the six
  scBench evals (`stringency-benchmarks/measurements.md`; a first attempt was contaminated by the
  host's Claude Code environment and the runner now isolates each run); plugin singlecell 0.8.4
  (droplet operations, `analysis_summary`, `marker_panels`, four droplet predicates); the method
  `stringency-scrnaseq-scanpy-method` v0.1.8 delivered under the engine on its planted fixture
  with the lineages recovered exactly and all eight controls passing; its `BACKLOG.md` lists the
  assignment step's improvements. Engine 0.2.34 (untagged until the owner says) carries what the
  run found: JSON-key citations, `param.reason_unmatched@2`, flags logged on control runs, and
  the console's plain block, predicate summaries, ask-group colours, rendered echo-back and
  egress, folded packet (DECISIONS 2026-10-22). Open for the owner: the Phase 0 exit reading,
  SpatialBench, the Latch conversation, Phase 2's adapter (L89); engine rows L94 to L97.
- Engine 0.2.33 and plugin singlecell 0.7.0 (`notes/2026-10-22-0500-citation-checks-and-plugin-0.7.md`):
  the seven downstream predicates (L54); `judgment.must_cite` with
  `judg.required_evidence_uncited` (L56, DEVIATIONS awaiting the owner); the `cited` report
  output and `judg.numeric_claims_match@2` (L57). The seven passes of `PLAN.md` "Next, in
  order" are done; what remains is the owner's (install, republish, the DEVIATIONS entry, the
  Qwen3 evaluation, the tester, F7) and the Xenium method's next tag.
- Engine 0.2.32, Codex as a harness (`notes/2026-10-22-0300-codex-harness.md`): the survey
  (`integrations/codex/README.md`), Codex recognised by the engine, `render_skill.py
  --harness`, the `command` and `openai-compatible` adapters with a `judgment:` block in
  `stringency.yml`, conformance fixtures under `tests/shared/` with `integrations/conformance.py`
  (L34 H1 to H3, L36). The Qwen3 evaluation remains the owner's. Pass 6 is plugin singlecell
  0.7 (L54).
- Engine 0.2.31, confirm once (`notes/2026-10-22-0100-confirm-once.md`): `study:` in
  `stringency.yml`, the inheritance rules (derived, inputs matched, re-declared, study), the
  advance sentence from `init` and `declare --check`, batch review of identical parameter
  flags with accept-once, the console's "Inherited today" (L67, L6, L5, L68, L69). Pass 5 is
  Codex as a harness (L34 H1).
- Engine 0.2.30, judgment replicates (`notes/2026-10-21-2300-judgment-replicates.md`): each
  replicate reads its own seeded ordering of items, rows and vocabulary, with its own prompt
  hash (L83); `sign_off: {when: sample, fraction}` holds a seeded sample of agreed items (L84,
  DEVIATIONS). Pass 4 is confirm once (L67, L6, L5, L68, L69).
- Engine 0.2.29, decision points first cut (`notes/2026-10-21-2100-decision-points-first-cut.md`):
  `decision:` on a pipeline parameter (evidence, hold always, the menu keys parsed), lint,
  `propose --cite` and `--considered`, `param.agent_proposed@2`, `param.reason_unmatched`,
  `param.uncited`, the default hold view, the `presented` event and line (L61, L55, L62, L9).
  Pass 3 is judgment replicates (L83, L84). The shared install stays at 0.2.27 until the
  passes are done (the owner).
- Engine 0.2.28, triage pass 5 (`notes/2026-10-21-1800-triage-pass-5.md`): the operator
  answering its own dispatch is recorded and refused under strict (L72), `module.yml` `egress`
  with the lint rule (L46), the judge on control results (L3) and beside each replicate (L70),
  the fork sweep line (L59), `answer --cannot` (L60). L86 filed: the Xenium method's
  `resegment-nextflow` must declare its egress. Pass 2 is decision points. The owner installs
  0.2.28 and republishes the operator, declare and Xenium skills.
- The owner answered the whole waiting table (`notes/2026-10-21-1500-owner-answers.md`): both
  DEVIATIONS entries acknowledged, Codex logged in and the go given (L34), confirm once approved
  with an opt-in `study:` field (L67, L6), L83 and L84 picked from the literature check, L85
  applied, T3/T4 and the PROTECT rule parked. `PLAN.md` "Next, in order" is seven passes; pass 1
  is triage pass 5 (L72, L46, L3, L70, L59, L60). Engine still 0.2.27, installed and running the
  console; the skill republish is the one owner job left.
- The plans consolidated (`notes/2026-10-21-1315-plans-consolidated.md`): `spec/plans/PLAN.md` is
  the one work list; read it first. Rows L54 to L85 filed today (OmicsBench L54 to L60, decision
  points L61 to L66 with `spec/plans/decision-points.md`, the open sections of the plan documents
  L67 to L81, the judgment literature check L82 to L85); the roadmap, the open-mode and bulk
  plans and the trace review archived; `ux-two-audiences.md` is now `spec/ux-two-audiences.md`.
  Engine unchanged at 0.2.27; committed as `df2b287`. The suite runs on this machine now
  (`uv` from Homebrew, a managed Python 3.14): green, two Linux-only tests skip without `/proc`.
- Engine 0.2.27 (`notes/2026-10-21-0400-triage-pass-4.md`): the triage of 2026-10-20 is complete:
  trace integrity T1 and T2 (0.2.25), pass 3 (0.2.26), pass 4 (0.2.27). What is left on the
  backlog waits on the owner (T3, T4, L42, L45, L46, K6, confirm-once, Codex, H5, A5, L48) or is
  a larger design (L3, L4, L9, L11). The declare skill wants republishing.
- Judgment premise checked against the literature (`notes/2026-10-21-1300-judgment-replicates-evidence.md`):
  five proposals for the owner, none started.

## Earlier state (2026-10-20, night)

- Trace integrity (`notes/2026-10-20-2330-trace-integrity-review.md`): the owner's finding
  verified, a mutable row can be changed by direct SQL without its event; the plan
  `spec/plans/trace-integrity-plan.md` (Lane T), T1 and T2 ready to build, T3 and T4 the owner's.
- Engine 0.2.24 (`notes/2026-10-20-2100-open-tools-engine-fixes.md`): init from a delivery takes
  each file's run from its sidecar, the report names the delivery run, cited cells and table
  views from any csv or tsv artifact, `exec --help` fixed (L43). Behind it the Xenium method's
  open tools (branch `open-tools`: six tools pass on the Lyons liver delivery; CellChat next).
  Plugin 0.6.1 installed. Next: the method's rc tag and the pilot through Claude Science.

## Earlier state (2026-10-20, evening)

- The merge train is done (`notes/2026-10-20-1600-egress-drive-and-merge.md`, `notes/2026-10-20-1700-egress-plan-retired.md`):
  open mode (PR #14, v0.2.22) and data egress (PR #15, v0.2.23) are on `main`, installed as
  `0.2.23-sc0.5.1`, the toy method at v0.2.0 and the Xenium method at v0.6.0-rc18 re-rendered.
  The egress plan is archived; open mode's egress gaps are backlog L40 to L46 (an `exec` step
  under the ceiling, the upstream ceiling, the site rule, `exec --help`, the brief template's
  flags, the relay's "not assessed" line, the `module.yml` `egress` decision). The renderer caps
  a skill description at 1,024 characters. Next: the owner republishes the Xenium skill; L40 and
  L41 before the first PROTECT open project; L46 is the owner's decision.

## Earlier state (2026-10-20, afternoon)

- The egress drive and the merge (`notes/2026-10-20-1600-egress-drive-and-merge.md`): the owner
  drove branch `egress` through Claude Science as a person and was satisfied; `open-mode` merged
  into `egress` (`43efd2b`, eight additive conflicts) and the follow-up commit fixes the scan's
  XML-namespace false positive, bumps the engine to 0.2.23 and says the mode B wait is a job.
  Every check green. Next: the merge train (push `egress`; `main` to `open-mode`, tag
  `v0.2.22`; `egress` into `main`, tag `v0.2.23`; install; republish; the toy and Xenium
  methods re-rendered and tagged).

## Earlier state (2026-10-19, night)

- The report replaces `deliver --answer` (`notes/2026-10-19-2100-open-mode-report.md`): every
  admissible answer lands in `deliver/<run>/` as it is filed; `report.md` leads with the
  findings; `stringency finding` marks them (migration 0006); the operator's report and
  findings sentences. Built and green on branch `open-mode`; toy method `v0.2.0-rc5`. Next:
  reinstall the prefix, republish, the owner's review before any merge.

## Earlier state (2026-10-19, afternoon)

- The owner's first open-mode drive (`notes/2026-10-19-1400-open-mode-drive-findings.md`): six
  findings, all changed on branch `open-mode` (controls before a tool's first use, the untested
  tool sentence, the upstream pipeline's own inputs, the answer delivery's names, a project
  README, one delivery-reporting rule); toy method `v0.2.0-rc2` pushed, rc3 prepared. Next: the
  owner's word on commit, push and the toy manifest sync; reinstall the open-mode prefix;
  republish; the second drive.

## Earlier state (2026-10-16, evening)

- Open mode S1 to S7 built on branch `open-mode`, seven commits, engine 0.2.22 untagged and
  unmerged (`notes/2026-10-16-2200-open-mode-s1-s7.md`): `mode: open`, `init --from-delivery`,
  `tools list`, `ask`, `call`, `exec`, `answer`, `deliver --answer`, `present --answer`; the six
  predicates; migration 0005; the toy's tools and controls; the design amendments of the plan's
  section 6 applied for the owner's reading at merge. Every check green. O1 built the same
  evening (`f8710b4`: operator skill section 10, template section 8, the renderer's `tools:` and
  `open:`); the toy method at `v0.2.0-rc1` with tools and the re-rendered skill; the branch
  engine installed at `/data/lab/env/stringency-open-mode` (the shared engine untouched). Next:
  the owner's agent-operated test drive (`docs/open-mode-rehearsal.md`), then the merge
  decision; backlog L39 (the `--set none` wart).
- Data egress at init built on branch `egress` (worktree `../stringency-egress`, not merged;
  `notes/2026-10-16-1420-egress-at-init.md`): the person sets a ceiling at init
  (`--egress-max`), the engine assesses the setup, saves `prov/egress.md`, and opens an `egress`
  hold the operator relays beside the confirm hold, asked again only when the profile changes;
  over the ceiling, init is refused and run open blocked. Open: the merge after open mode S2, the
  `module.yml` `egress` DEVIATIONS entry, the design amendments.
- The open-mode plan approved (`spec/plans/open_mode_plan.md`, Lane K;
  `notes/2026-10-16-1330-open-mode-plan.md`): after a pipeline delivers, the operator reviews
  the method's tools and the project's questions, proposes paths, and on the person's yes
  answers questions with trusted tools (modules listing `open`) or `exec`-run code labelled
  untested, every numeral checked against cited cells. Five owner decisions recorded in the
  plan. Nothing built; the implementation (S1 to S7, O1 to O6) is for an agent on the
  workstation; the design amendments of its section 6 await the owner. G2 answered.
- `posit-dev/commons` assessed against the design (`spec/plans/commons-assessment.md`,
  `notes/2026-10-16-1210-commons-assessment.md`): no integration; backlog L35 to L38 (a trust
  label on every delivered artifact, harness conformance fixtures for Lane J, a method-author
  skill over the override corpus, quoted text verified) and a G2 proposal (`exec --step`).
  Nothing built, nothing committed. The 2026-10-15 state below still holds.

## Earlier state (2026-10-15)

- Everything pushed; CI green in all three repositories and the compat workflow green; the plugins
  repository public; `0.2.21-sc0.5.1` installed on the workstation, `probe` ready
  (`notes/2026-10-15-1000-install-for-people-and-ci.md`). The install for people (README message,
  `scripts/bootstrap.sh`, the person's sections) and the site-neutral repository (the lab's pages in
  `~/mytools/stringency/stringency-lab/`) are from the same day. Open: the owner's republish, the
  amendments, the rc16 real-data run, W6's acceptance run; W7 waits.

## Earlier state (2026-10-14)

- Engine `v0.2.16` installed as `0.2.16-sc0.5.0` (`current`); `main` pushed and clean. Method
  `v0.6.0-rc13` tagged on `main` 2026-10-14, not yet run under the engine. Lyons v2: `qc_all` and
  all four `upstream_*` organs delivered (2026-10-08 to 2026-10-12).
- W6 built 2026-10-14 (`notes/2026-10-15-0300-xenium-analysis-skill-w6.md`): decision points in the skills,
  `stringency-analyze-xenium-upstream` (method rc16), `controls/synthetic_upstream.sh` passing under the
  engine; open: the acceptance run by a non-developer. W7 (Codex) waits on the owner.
- W5 done 2026-10-14 (`notes/2026-10-15-0130-guides-w5.md`): `docs/install.md`, `docs/onboarding.md`,
  `docs/method-author.md`; the historical host notes archived; the skills and briefs name the shared
  install and `probe`. Next: W6 (the Xenium analysis skill).
- Engine `v0.2.20` (W4, L7: the method checkout bound read-only into every engine-run step; method
  rc15 drops its `rlib/` and `qc_plots.py` copies; `notes/2026-10-15-0030-method-bind-v0220.md`).
  Next: W5 (install and onboarding guides).
- W3 closed: engine `v0.2.19` (L28 to L31; `notes/2026-10-14-2200-compat-engine-v0219.md`), plugin
  singlecell 0.5.1 and method `v0.6.0-rc14` with `requires` on both sides, CI in all three repositories
  (`notes/2026-10-14-2330-compat-plugin-and-method.md`); the combination checked on PROTSEQ. Engine
  tags local, plugin tag after `uv lock` once the engine is pushed. Next: W4.
- Engine `v0.2.18` (W2, L24 to L26: `objective.yml` `params:`, `present` skips `#` lines, `hold_view`
  `where:`; `notes/2026-10-14-2000-declared-params-v0218.md`) and `v0.2.17` (W1, L27: a fork inherits
  its parent's admitted parameters, `fork --check`; `notes/2026-10-14-1800-fork-inherits-v0217.md`),
  both tagged locally, not installed, not pushed.
- The plans refreshed and the code review of 2026-10-14 folded in
  (`notes/2026-10-14-1500-plan-refresh-and-review.md`): read `spec/plans/roadmap-2026-10.md` first;
  its lane table is the state; the approved work is W1 to W6 in order (fork inheritance L27 first),
  W7 (Codex as a harness) waits on the owner. Backlog L28 to L34 are the review's items; done rows
  are in `spec/archive/backlog-done.md`.

## Earlier state (2026-10-09)

- Engine `v0.2.16` (L23: a console hold page hashes no input; was 55 s on `qc_all`), tagged locally, not
  installed (installed: `0.2.15-sc0.5.0`, the v2 spleen run is on it) (`notes/2026-10-09-1600-hold-page-speed-v0216.md`).
  Method rc13 (resolution chosen after clustering) built on a branch in `stringency-xenium-method`.

## Earlier state (2026-10-08, afternoon)

- Lung and gut delivered in console mode; engine `v0.2.15` (L14 to L22), plugin singlecell
  `0.5.0` (`cell_types_mouse@2`), method `v0.6.0-rc10` (parallel clustering, @2, the batch
  confound first) (`notes/2026-10-08-1311-lung-gut-and-v0215.md`). Not installed until the owner
  installs `0.2.15-sc0.5.0`. Next: spleen on rc10; then batch cards, gallery, history, the cap.

## Earlier state (2026-10-07, evening)

- Engine v0.2.7 (`notes/2026-10-07-1730-engine-v027.md`): main reconciled with `v0.2.6`; L13
  conditional steps (`when:`, `skipped`), L12 evidence keys, L8 the operator's reason at the hold,
  `stringency wait`; method `v0.6.0-rc7` skips the batch judgment on a corrected run. Next: lung,
  gut, spleen on 0.2.7 and rc7; the console (part 2) on branch `console`.
- The console built, released and running (`notes/2026-10-07-2300-console-build.md`): engine
  `v0.2.10` with the figures at the hold, method `v0.6.0-rc8` naming them, `stringency-console.service`
  on loopback 8765 under the owner's account. Pick up from `spec/plans/console-and-fleet-plan.md`
  section 8 (where everything is, release and install, what is next: lung in console mode, then
  batch cards, gallery, history, the resource cap).

## Previous state (2026-10-06, afternoon)

- Lane F phase 0 done in one session (`notes/2026-10-06-1345-lane-f-phase0.md`): F0 (all eleven
  owner decisions; **downstream in R reusing ROSC code**, LogArea, limma-voom, no pathology pass,
  gut is small intestine, exclusion file format), F1 (method `v0.4.0`), F2 (eight `qc2_*` projects
  through one batch review and sixteen `param.agent_proposed` holds; summary on `arity: many`), F3
  (second outlier judgment: one run rejected by `judg.numeric_claims_match` and abandoned, the
  second clean with four item holds against September's seven; `punch_exclusions.csv`, one
  exclusion). Engine `0.2.6` unchanged. New backlog rows L5 (inheritance with raw-identical and
  reference inputs) and L6 (batch review of identical flag holds). Phases 1 to 7 re-planned for R
  the same evening (plan sections 5 to 7; all fifteen decisions taken) and F4 ran: image `xenium-r`
  0.1.0, plugin `singlecell` 0.2.0 (`seurat_object`, R extractor) installed as the shared engine
  `0.2.6-sc0.2.0`, method `v0.5.0-rc2`, the anndataR round trip EQUAL, `cluster_liver` delivered
  under the engine (first R pipeline). Backlog L7 (executor bind scope) and
  `spec/plans/confirm-once.md` (the repeated confirm asks, Lane A). Next: F5; start from
  `/lab/projects/Lyons_CLP/PROGRESS.md` and the method's `PLAN.md`.

## Previous state (2026-09-23, night)

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

- Judge sources (2026-09-23, evening): `spec/plans/judge-sources-plan.md` drafted, proposed Lane G;
  seven owner decisions open in its section 6; S3 and S5 can start without them; Jev tabled;
  ClawBio assessed, two mechanisms borrowed (`spec/plans/egress-and-remeasurement.md`, backlog L1 to L4)
  (`notes/2026-09-23-1930-judge-sources-brainstorm.md`). Uncommitted.

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

- `2026-10-26-2130-qc-failure-modes.md` — plugin singlecell's 24 predicates checked against its spec (all listed; the engine design lists none); literature on droplet and imaging-spatial failure modes through Consensus; `qc-failure-modes.md` with L115 to L127, mitochondrial fraction first, and the owner's D1 to D3.
- `2026-10-26-1315-module-scripts.md` — the owner's points on the methods' module scripts: the convention (named scripts with `entry:`, a short header and `CHANGELOG.md`, one shape, `stringency_io`, ruff and lintr, a README index, existing code); phase 0 built and the Xenium pilot `cluster-umap` 0.4.2 verified identical to rc19 on PROTSEQ; the Xenium method moved to the current predicates (L86) and run end to end under 0.2.34-sc0.8.4; then every Xenium module converted and verified identical; L114.
- `2026-10-23-1400-annotation-controls.md` — a tour of the Xenium method and the plugin; `fine_label` traced end to end; `pct_diff` measured on the ROSC liver fixture; the owner's annotation points filed as L110 to L112 and method items 3.15 to 3.21 with `annotation-controls.md`; `sc.fine_label_uncited@1` built (plugin 0.8.5); one fine label of three by a reconcile step and a choosing judgment.
- `2026-10-22-1150-gate-review-filed.md` — the owner's walkthrough of the gate checked against the code and filed as L100 to L109 with `gate-soundness.md`; three findings sharper than the walkthrough; ids from L100 to avoid the workstation session's.
- `2026-10-22-0700-benchmark-phase-0.md` — the owner's benchmark plan adapted (L87 to L92); the Docker-free Claude Code runner on Opus 5; the published reference on the six public evals; Phase 0 waits on `latch login`.
- `2026-10-22-0500-citation-checks-and-plugin-0.7.md` — plugin singlecell 0.7.0 (the seven downstream predicates, L54); engine 0.2.33: must_cite and judg.required_evidence_uncited (L56), the cited output type and judg.numeric_claims_match@2 (L57).
- `2026-10-22-0300-codex-harness.md` — engine 0.2.32: the Codex survey and appendix, Codex recognised, the renderer's harness switch, the command and openai-compatible adapters, conformance fixtures (L34 H1 to H3, L36).
- `2026-10-22-0100-confirm-once.md` — engine 0.2.31: the study field, the four inheritance rules, the advance sentence, flag batches and accept-once, the console's inherited list (L67, L6, L5, L68, L69).
- `2026-10-21-2300-judgment-replicates.md` — engine 0.2.30: per-replicate prompt orderings (L83) and sampled sign-off (L84).
- `2026-10-21-2100-decision-points-first-cut.md` — engine 0.2.29: the `decision:` block, lint, `propose --cite`/`--considered`, the three `param.*` predicates, the default hold view, the `presented` event (L61, L55, L62, L9).
- `2026-10-21-1800-triage-pass-5.md` — engine 0.2.28: L72 operator self-answer recorded, L46 module egress declaration and lint, L3 judge on controls, L70 judge per replicate, L59 fork sweep line, L60 answer --cannot; L86 filed.
- `2026-10-21-1500-owner-answers.md` — the owner's answers to every waiting row: DEVIATIONS acknowledged, Codex go, confirm once approved, L83/L84 picked, L85 applied; Next rewritten as seven passes.
- `2026-10-21-1315-plans-consolidated.md` — one work list: `spec/plans/PLAN.md` replaces the roadmap and the backlog, every open item of nine plan documents a row (L54 to L85), the waiting-on-the-owner table; `decision-points.md` (the `decision:` block, the slots on `propose`, the menu); OmicsBench assessed; four plans archived, the UX rules moved to `spec/`.
- `2026-10-21-1300-judgment-replicates-evidence.md` — literature check on the judgment premise: disagreement is a sound hold signal; unanimity of one model's replicates misses consistent errors; five proposals (unanimous-but-wrong rate in controls, per-replicate prompt perturbation, mixed panel, sampled sign-off, "independent" in the methods text). No engine change.
- `2026-10-21-0400-triage-pass-4.md` — engine 0.2.27: declare --check --print-hashes, submit --deliver, the judgments shown at a judgment hold by default, the abstention stability line; J1, J2, K5, L2 done; the triage of 2026-10-20 complete.
- `2026-10-21-0200-triage-pass-3.md` — engine 0.2.26: --set by the parameter's schema (lists, enums as spelled), optional inputs by name, the upstream's ceiling inherited, session scripts in the egress assessment and blocked over the ceiling, the brief renderer's run flags; L39, L40, L41, L44, L47, L49 done.
- `2026-10-21-0030-trace-integrity-t1-t2.md` — engine 0.2.25: the Store's connection private with a read-only reader, insert refusing all five tables, the docstrings and 9.5 told the truth (T1); `stringency audit`, `prov.trace_inconsistent` at run open and deliver, the coverage line (T2); what the audit cannot see.
- `2026-10-20-2330-trace-integrity-review.md` — the owner's trace-integrity finding verified (a mutable row can change without its event), the plan `trace-integrity-plan.md` (Lane T, T1 to T4), backlog L50 to L53.
- `2026-10-20-2100-open-tools-engine-fixes.md` — engine 0.2.24 for the Xenium open tools: the sidecar run on init from a delivery, is_tabular, exec --help; plugin 0.6.1; what was learned about --set lists and optional inputs.
- `2026-10-20-1700-egress-plan-retired.md` — egress in open mode probed (three gaps), the egress plan archived, backlog L1 done and L40 to L46 added, the roadmap's duplicated rows collapsed, the skill description cap in the renderer, the Xenium method rc18.
- `2026-10-20-1600-egress-drive-and-merge.md` — the owner's egress drive through Claude Science (passed; the findings), `open-mode` merged into `egress`, the scan's XML-namespace fix, engine 0.2.23, the wait as a job in mode B; the merge train for the owner.
- `2026-10-19-2100-open-mode-report.md` — the report replaces `deliver --answer`: automatic delivery of every answer, `report.md` with the findings first, the `findings` table and verb, the skills' two new sentences; the probe that was never blocked; what was altered.
- `2026-10-19-1400-open-mode-drive-findings.md` — the owner's first open-mode drive on the toy: the paste and image failures before it, and the six findings after it (no control ever ran, a tool's answer called code, the raw input out of reach, the delivery's names, the directory, the long delivery message), each built and recorded.
- `2026-10-16-2200-open-mode-s1-s7.md` — open mode S1 to S7 built on branch `open-mode` (engine 0.2.22): binding, on-demand steps, exec, controls for tools, answers and labels, deliver and present, the chain test and the design amendments; what was learned (the read-only bind that was not, a tool controlled alone, the `--set none` wart); O1 to O6 open.
- `2026-10-16-1420-egress-at-init.md` — data egress at init (backlog L1): the owner's two answers (acknowledge once; the person's ceiling at init), the assessment, report, hold and blocks, the delivery record, the skill text; built on branch `egress` beside the open-mode session; merge and DEVIATIONS open.
- `2026-10-16-1330-open-mode-plan.md` — the open-mode plan: three explorations, three design passes, the owner's five decisions and the pre-switch review; what the code already has (design 5's sentence, `modes`, on-demand steps as the one addition) and what it lacks (the deliver gate's dropped verdicts, read-write input binds, no timeout, no `--net`, a completion-only control scorer); implementation handed to the workstation.
- `2026-10-16-1210-commons-assessment.md` — posit-dev/commons read against the design: the provenance outcome derived from the path, the citation match, the kernel sandbox for model code, the OTel trajectories and review documents, the cross-language fixtures; four borrowings (L35 to L38), the G2 proposal, and what commons lacks.
- `2026-10-15-1000-install-for-people-and-ci.md` — the install for people (README message, bootstrap, the guides' two halves), the site-neutral repository and the lab directory, engine 0.2.21, the first CI runs and their five fixes, the install of `0.2.21-sc0.5.1`.
- `2026-10-15-0300-xenium-analysis-skill-w6.md` — W6, backlog L32: `decisions:` in the analysis-skill source and the operator skill's section 9; the Xenium analysis skill (rc16); the synthetic two-slide upstream run through the engine, which found the plugin extractor's partial match.
- `2026-10-15-0130-guides-w5.md` — W5, backlog L33: the three guides under `docs/`, the Claude Science notes trimmed and corrected, the host notes archived, the method-repo template's hook, CI and example skill.
- `2026-10-15-0030-method-bind-v0220.md` — engine 0.2.20, backlog L7 (roadmap W4): `Job.ro_bind_paths`, the method checkout bound read-only; method rc15 sources `modules/_rlib` and `modules/_pylib` with no copies.
- `2026-10-14-2330-compat-plugin-and-method.md` — W3 closed: singlecell 0.5.1 (coords_missing@2 on every region, declared and inherited decision points, CI, institutional marks) and method rc14 (`requires`, group bands from the job's design, CI, the organ hold view); the combination checked on PROTSEQ and recorded in `compat/known-good.yml`.
- `2026-10-14-2200-compat-engine-v0219.md` — engine 0.2.19, backlog L28 to L31 (roadmap W3, engine half): `requires` checked by lint, declare, init and run open; the installed plugins in `stringency.yml`, the captures event, the delivery and the coverage line; `stringency probe`; images resolved by name through `$STRINGENCY_IMAGES` and `~/.config/stringency/config.yml`; `install.sh` derives its label; `compat/known-good.yml` and the compat workflow.
- `2026-10-14-2000-declared-params-v0218.md` — engine 0.2.18, backlog L24 to L26 (roadmap W2): parameters declared in `objective.yml` are echoed, taken as given and never proposed; `present` reads a commented CSV from its header; a hold view filters a table by the proposed parameter.
- `2026-10-14-1800-fork-inherits-v0217.md` — engine 0.2.17, backlog L27 (roadmap W1): a fork inherits the parameters its ancestor admitted, `--set` overrides only what it names, `fork` lists every value with its source, `fork --check` opens nothing; design 2.6 and 14.1.
- `2026-10-14-1500-plan-refresh-and-review.md` — W0: `roadmap-2026-10.md` written and the 2026-09 roadmap archived, the backlog split into open and done, every plan's status to 2026-10-14, Lyons v2 as spatial-plan decisions 21 to 25, the code review's items as L28 to L34 and method PLAN 5.12 to 5.17, the file-level shape of W1 to W7.
- `2026-10-09-1600-hold-page-speed-v0216.md` — engine 0.2.16, backlog L23: a console hold page hashes no input (55 s per page on `qc_all`); not installed.
- `2026-10-08-1311-lung-gut-and-v0215.md` — lung and gut in console mode; engine 0.2.11 to 0.2.15 (L10, L14 to L22), plugin 0.5.0 (`cell_types_mouse@2`, ids checked), method rc9 and rc10 (parallel clustering, the batch confound first).
- `2026-10-07-2300-console-build.md` — Lane H: the console built and released (v0.2.8 first cut, v0.2.9 restyle, v0.2.10 figures at the hold; method rc8 names the figures), running as `stringency-console.service`; the plan's section 8 is the pick-up guide.
- `2026-10-07-1720-console-plan.md` — Lane H: `console-and-fleet-plan.md` fleshed out into a design, the owner's seven decisions taken, and the first cut BUILT the same night (C1 routes by id and cookie, C2 inbox by ask and driver block and timeline, C5 event stream and page script, C3 console mode in the skill; branch `console`, not merged) (routes by id, event stream on `data_version`, inbox by ask with batch cards, `hold_view` figure and chart kinds, who is driving, console-mode hold protocol, the slot cap); mockup `spec/plans/mockups/console-mockup.html`; seven owner decisions; branch `console`, no engine code touched.
- `2026-10-07-1730-engine-v027.md` — engine v0.2.7: v0.2.6 merged into main; L13 conditional steps (`when:`, `pending -> skipped`, design 3.1 and 7.1); L12 evidence-table keys as read; L8 the operator's reason in the flag packet; `stringency wait`; the operator skill arms `wait`; method rc7 (`when:` on `05_assess_batch`, report 0.1.2).
- `2026-10-06-1345-lane-f-phase0.md` — Lane F phase 0 and F4: F0 decisions (R, LogArea, limma-voom, no pathology pass, small intestine, exclusion file), method v0.4.0, the second QC chain through batch review and sixteen parameter holds, the summary on arity many, the second outlier judgment (one numeric-claims rejection, four item holds), the owner's exclusion file; L5, L6.
- `2026-10-07-1100-lane-f-f5-upstream.md` — Lane F F5: the owner's one-upstream-pipeline request and how the engine meets it (run --until, param.agent_proposed's gap, the controls wiring constraint); plugin 0.3.0 and 0.3.1 (sc.decision_unreviewed, sc.batch_effect_suspected, sc.unknown_fraction, qc.filter_ordering, cluster_evidence, cell_types_mouse@1); image xenium-r 0.2.0 with harmony; method v0.6.0-rc2 with xenium-upstream (eight steps) and xenium-annotate; the dev run on the real liver cells; upstream_liver initialised; L8, L9.
- `2026-09-23-1930-judge-sources-brainstorm.md` — judge sourcing survey and plan (`spec/plans/judge-sources-plan.md`, proposed Lane G): harness state, local Ollama judges, panel roles, operator fallback, Jev tabled; ClawBio assessed (no integration) and two mechanisms borrowed into `spec/plans/egress-and-remeasurement.md` (backlog L1 to L4).
- `2026-09-23-1442-track1h-start.md` — Track 1h: notify on hold and the project page on `review --serve`; owner decisions, build order, install label.
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

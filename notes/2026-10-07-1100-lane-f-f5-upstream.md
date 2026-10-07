# Lane F F5: one upstream pipeline, merge to annotation (2026-10-07)

Session on PROTSEQ, Claude Code in `~/mytools/stringency` (moved into `screen -r stringency` mid-morning
so it survives the owner's laptop moving), shared engine `0.2.6-sc0.2.0` then `0.2.6-sc0.3.1`, method
`stringency-xenium-method` `v0.5.0-rc2` then `v0.6.0-rc2`, plugin `singlecell` 0.2.0 then 0.3.1.
Plan: `spec/plans/spatial-method-plan.md` section 5.1, phase 2, decisions 16 to 18. Data-side
record: `/lab/projects/Lyons_CLP/PROGRESS.md` (2026-10-07 entry).

## The owner's request

One pipeline from reading the Seurat objects through normalisation, concatenation, PCA and UMAP with
the ROSC plots, clustering and cluster annotation; no echo-backs between steps; the operator explicit
about the normalisation it recommends, a person approving; concatenation without batch correction
first, a route to assess and rerun with correction; ROSC per-tissue PCA and UMAP defaults, the
operator reasoning from elbow plots, a person signing off on the final parameters; one organ per
project; "as many steps within just a few overall large pipelines as possible going forward".

## What the engine already allowed, and what it did not

Read in source (0.2.6): `run --until <step>` stops after a step, so the operator can read the elbow
table and `propose 04_cluster --set ndim=.. --set resolution=.. --reason` before the next step runs.
`param.agent_proposed` fires only on a departure from the pipeline default; a proposal at the default
opens nothing; module.yml `confirm:` is parsed and read by nothing. A judgment control is wired by
replacing a project input of the fixture's type, so a mid-pipeline judgment cannot have a control
unless a one-step pipeline binds its input as a project input. The hold packet shows the proposal's
`rationale_ref` as a hash, not the text. Filed: backlog L8 (rationale text in flag packets), L9
(decision-point sign-off belongs in the engine).

## Built

- **Plugin `singlecell` 0.3.0 and 0.3.1** (two forked sessions): operations `reduce_pca`,
  `cluster_umap`, `find_markers` extended, `annotate_clusters`, `apply_labels`, `report_upstream`
  (`reduce_cluster` removed); object type `cluster_evidence` (`sc.cluster_evidence@1`, directory
  extractor; `fields.summary_columns`, not `columns`, so `init.column_missing` leaves it alone);
  predicates `sc.decision_unreviewed` (pre, flag: a step's decision points taken at their defaults
  without a person's sign-off; silent when `param.agent_proposed` fires, so exactly one hold per
  decision step; silent on a fork), `sc.batch_effect_suspected` (post on `cluster_umap`, from
  `uns_flags.batch_assessment.suspected`; the reason names the fork route), `sc.unknown_fraction`
  (post on `apply_labels`, policy ceiling 0.2), `qc.filter_ordering`; vocabulary `cell_types_mouse@1`
  (43 labels, CL ids, agent draft); generator tool `shuffle_markers`. 60 tests. Installed as shared
  `0.2.6-sc0.3.0` then `0.2.6-sc0.3.1` from the engine's `v0.2.6` tag. Found in passing: the engine
  checkout on `main` is `v0.2.4-23`; `v0.2.6` sits on `track-1h-text` (three commits not on main;
  main has seventeen not in v0.2.6). A stray `/data/lab/env/stringency/bin/stringency` symlink from
  the first install attempt remains (harmless).
- **Image `xenium-r` 0.2.0**: 0.1.0 plus harmony 2.0.5 (the batch-correction route), built on GHCR
  from the harmony commit, pulled by digest to `/data/lab/env/images/xenium-r-0.2.0.sif`, sha256 in
  `envs/manifest.yml` and `MANIFEST.md`, `renv.lock` and `versions.csv` committed.
- **Method `v0.6.0-rc2`**, pipeline `xenium-upstream` 0.1.0 (replaces `xenium-cluster`): `merge-punches`
  0.1.1 (restores the seven-digit slide id the QC objects had reduced to a number), `normalize` 0.1.1
  (gates declared), `reduce-pca` 0.1.0 (HVG, scale, PCA 50; `elbow_table` with two heuristics and the
  knee; HVG, elbow, loadings and PCA-pair plots; `integration` none|harmony|rpca|cca on layers split by
  `batch_key`), `cluster-umap` 0.1.0 (neighbours, Louvain at five resolutions, UMAP, clustree, UMAPs
  by every design column and split views, image plots per punch, composition tables, the batch
  assessment written to `misc$stringency$batch_assessment`), `find-markers` 0.1.0 (FindAllMarkers
  with a seeded ten-thousand-cell subsample per cluster, top-25 table, per-cluster mean and fraction
  expressing for every gene, dot plot, the `cluster_evidence` directory), `annotate-clusters` 0.1.0
  (judgment; evidence `cluster_summary`, `markers_top`, `canonical_markers`, `organ_guide`; prompt
  with ROSC's reading rules and the "in words" line; controls from the ROSC liver: positive with the
  collapse-map truth at agreement 0.75, negative with shuffled symbols), `apply-labels` 0.1.0,
  `upstream-report` 0.1.0 (markdown and a self-contained HTML with every figure); `xenium-annotate`
  for controls and re-annotation; `docs/tissue-defaults.md`; `skills/xenium-upstream.yml`;
  `tests/run_upstream.sh`, `tests/run_annotate.sh`. Lint: four deliberate warnings.
- **Dev run on the real liver cells** (103,127 cells; the `cluster_liver` normalised object; outside
  the engine under `/lab/scratch/jrrose5/upstream-dev`): PCA 2 min, knee at component 16 against
  the ROSC default of 35; clustering and UMAP about 6 min, 20 clusters at 0.4 (ROSC liver also had
  20); markers 3.4 min, 12,548 rows; the judgment's pre-script on the real evidence: 500 top-marker
  rows, 111 canonical genes on the panel for 26 expected liver labels; apply-labels and the report
  with a fabricated dev consensus, 72 figures gathered. Batch assessment: kNN same-slide excess 0.344
  within the one shared time point (24 h), above the 0.30 rule, so the flag will open on the real
  run; no cluster flagged by composition; the caveat row says each slide holds one animal at 24 h.
  As in ROSC, time point dominates the clusters (four clusters are 24 h only, four are 6 h only).
- **`upstream_liver` declared** (`/lab/projects/Lyons_CLP/declarations/upstream_liver`, the
  `cluster_liver` inputs unchanged; `declare --check` clean, 7 init predicates, none fired) and
  initialised on `v0.6.0-rc2`; it waits on the owner's init confirm.

## Afternoon: the batch assessment becomes a judgment (decision 19)

On seeing the first design the owner said batch effect assessment "needs to be turned into another
judgement step. It's greater than just choosing parameters" and asked for a review hold before the
run moves forward. Built the same afternoon (two more forked sessions, plugin 0.4.0 and the module):
`04_cluster` now also writes a `batch_evidence` directory (`sc.batch_evidence@1`: overview, per-cluster
assessment, cluster summary, slide by time point with animals and punches, compositions) and a one-row
`batch_overview` table; `05_assess_batch` (judgment, xenium-py, one item = the dataset, evidence
`batch_overview`, `batch_by_cluster`, `slide_by_timepoint`, `batch_guide`, vocabulary `batch_route@1`:
`proceed_uncorrected`, `correct_batch`, `cannot_tell`; synthetic split and mixed controls through the
one-step `xenium-assess-batch`); `sc.batch_route_review@1` (post, flag) always opens a hold on that
step: accept continues the run uncorrected, reject closes it and the operator forks at `03_reduce`
with the correction the owner names; `sc.batch_effect_suspected` is version 2 and logged. The
pipeline is nine steps; the report shows the route beside the batch tables. Method `v0.6.0-rc3`;
the rc2 `upstream_liver` (never confirmed) moved to `superseded/`. Backlog L10: `judgment.hold:
always` belongs in the engine.

## Late afternoon: the first real judgment, and the hold's meaning

`upstream_liver` (rc3) ran: confirm accepted ("Continue analysis"); `02` LogArea proposed and
accepted ("Parameters agreed upon"); `03` knee at component 16 against ROSC's 35, `ndim` 35 and
`resolution` 0.4 proposed and accepted ("Reasonable parameter choices"); `04` 20 clusters, kNN excess
0.344 at 24 h. The batch judgment took three dispatches to pass the gates, the reviewers agreeing on
`correct_batch` (harmony) every time: dispatch one rejected on the twelve-hundred-character rationale
cap (zero valid replicates), dispatch two on `judg.evidence_exists` (`slide_by_timepoint` keyed by
slide, which repeats per time point) and `judg.numeric_claims_match` (cluster ids as digits);
each time the run was forked at step 05 (`01M4BNK6…`, `01M4BNV3…`) and the delegates told the
constraints. The owner then asked why accept would mean "no correction" when the reviewers agreed
correction was needed: the flag hold's fixed verdicts had been mapped to routes, and "accept" read
as agreement. Decided: accept = agree with the reviewers, the operator acts on the label; reject =
the reason names the route; `cannot_tell` needs the route in the reason either way; disagreement is
the engine's item hold and the predicate stays silent (plugin 0.4.2, `sc.batch_route_review@2`;
method `v0.6.0-rc4`: `assess-batch` 0.1.1 with the `slide_timepoint` row key and the cap in the
prompt). Backlog L10 sharpened: route-named verdicts belong in the engine.

## Evening: the Harmony route, and the comparison

The owner accepted the batch-route hold ("Batch effect is evident"); the fork at `03_reduce` with
`integration=harmony` failed after Harmony itself had run: `HVFInfo` has a different column layout
with split layers (`reduce-pca` 0.1.1, rc5). The route tested in scratch on the liver cells: 16
clusters, kNN excess 0.269; animal 24-2 now shares the manifold with the 48 h and 6 h animals, but
animal 24-1 (33k cells, clusters 0, 5 and 8) still sits apart from everyone, so what remains after
slide alignment is one animal. The project was re-declared on rc5 (the rc3 record superseded; the
operator will propose harmony at 03 on the new project). The owner then asked where the uncorrected
and corrected UMAPs live "to show/justify our decision": the uncorrected ones were in a superseded
project and the corrected ones would be in the delivered report, with nothing linking them. Built
(rc6): `cluster-umap` 0.1.1 writes a batch panel and the slide and animal UMAPs into
`batch_evidence`; `upstream-report` 0.1.1 takes an optional reference input
`uncorrected_batch_evidence` (glob `$inputs.uncorrected_*`, so a first pass binds none) and writes a
"Batch decision" section with both runs side by side; for liver the uncorrected directory was
regenerated from the rc3 run's PCA object with identical parameters (cluster summary identical) into
`superseded/upstream_liver.v0.6.0-rc3/comparison/`. Backlog L11: a fork should bind its parent's
outputs so the comparison needs no re-declaration.

## Night: the corrected run, and the rule that correction happens once

`upstream_liver` on rc6 (the comparison input declared): confirm "Matches project"; LogArea "Same as
before"; `integration=harmony` proposed at 03 citing the rc3 decision, accepted "Reasonable choices";
ndim 35 and resolution 0.4 "Reviewed in previous run"; 16 clusters, kNN excess 0.269 (rule silent).
The batch judgment dispatched again on the corrected clustering: dispatch one rejected on
`judg.evidence_exists` because the engine renders the `slide_timepoint` key through its numeric
coercion (`0076570_24` shown as 7657024) while looking rows up by the raw string (backlog L12); the
redo agreed `cannot_tell` three for three (animal 24-1 remains apart; one animal per slide at 24 h).
The owner: a second judgment should never happen, correction is done at most once, the comparison
readout is the record (decision 20; backlog L13, conditional steps). The hold was accepted "Step is
unnecessary" and the run continued to markers and annotation.

## Night: liver delivered

Run `01M4BTD4967ZR7JS5CR7RMXCWK` on rc6 delivered: 16 Harmony-corrected clusters, every one labelled
(fifteen agreed by three reviewers, one disagreement on the portal-tract mixture decided by the owner:
fibroblast), no `unknown`; 79 figures; the report's Batch decision section shows uncorrected beside
corrected. The annotation judgment passed its gates on the first dispatch once the delegates were told
the cap, the key rules and the words rule. Owner decisions today: 16 to 20. Engine backlog filed
today: L8 to L13. Method `v0.6.0-rc6`; plugin 0.4.2.

## Records

Flow diagram of the pipeline (artifact, private to the owner): https://claude.ai/artifact/6XZ6AT4KHxrjwft9vd15cx.
Delivery: `/lab/projects/Lyons_CLP/upstream_liver/deliver/01M4BTD4967ZR7JS5CR7RMXCWK/`. Data-side log: `/lab/projects/Lyons_CLP/PROGRESS.md` (2026-10-07).

## Open

1. Owner: the init confirm of `upstream_liver`; then the method hold at step 02 and the ndim and
   resolution hold at step 04 (the operator proposes from `elbow_table`); the batch flag after step
   04; the judgment's item holds; the vocabulary and organ guides (decision 17, F7).
2. The annotation controls: the scratch project `/lab/scratch/jrrose5/annotate-control/project` on
   the ROSC liver fixture waits on its own init confirm; `controls run` after that (plugin 0.3.1 has
   the generator). The engine's `controls` design cannot run a mid-pipeline judgment's controls
   inside `xenium-upstream`; `xenium-annotate` is the workaround.
3. Engine: L8, L9; the `v0.2.6` branch state; L5 to L7 still open.
4. Method: qc-cells writes the slide id as a number (merge 0.1.1 repairs it; fix at the source in
   qc-cells 0.1.4 when the QC modules next change); the batch rule's thresholds are a first guess.
5. F6: lung, gut, spleen on the same pipeline (liver delivered 2026-10-07 night); the vocabulary needs a portal-tract or stromal-mixture label (F7); L13 before the next organ if possible, else the operator answers the redundant hold with the owner's words.

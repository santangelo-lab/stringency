# 2026-10-26: QC failure modes (rows L115 to L127)

## Goal

The owner asked three things in turn: which predicates plugin singlecell has and whether the
spec lists them; review literature on common failure modes of droplet single-cell and
imaging-spatial (Xenium) data; and new predicates from it, first a hold or a rejection for a
dataset with an unusually high mitochondrial fraction at QC.

## Done

- The predicate inventory. Plugin singlecell 0.8.7 registers 24 predicates. The plugin's
  `spec/predicates.md` lists all 24, and id, version, phase, scope and default match the code.
  `tests/test_predicates.py` asserts the registered set equals `CASES`. The engine design does
  not list them: 15.4 defers to the plugin, and line 606 points at "implementation plan 4.1".
  Names the spec uses that are not built: `qc.threshold_range` and `annot.marker_evidence` (the
  design's examples), `sc.panel_hvg` and `sc.small_niche` (`spatial-method-plan.md`), and
  `sc.assignment_margin_low` (L98). Not changed; offered to the owner.
- The literature: ten Consensus searches after a recon search, following the
  consensus-literature-review skill. Five areas: droplet cell QC and mitochondrial fraction;
  ambient RNA, doublets and empty droplets; imaging spatial QC; targeted panels; inference
  failures. The review was given in the session. The sources that bear on a gate are in
  `spec/plans/qc-failure-modes.md` (S1 to S23).
- `spec/plans/qc-failure-modes.md`, rows L115 to L127 in `PLAN.md` (Method and plugin), Next
  item 10, three rows in the waiting table (D1 to D3), and the `spec/README.md` row.
  The rows propose thirteen new predicates and `sc.qc_floor_above_data@2`, with the
  mitochondrial rows first:
  - L115 `sc.mito_fraction_high@1`
  - L116 `sc.mito_genes_unmatched@1`
  - L117 `sc.qc_floor_above_data@2`
  - L118 `sc.low_quality_cluster@1`
  Nothing built.

## Learned

- `scrnaseq-upstream` defaults `max_pct_mt` to 100, so at the default no cell is dropped for its
  mitochondrial fraction. The step's `decision:` block has no `hold: always`, so under `run` the
  default is not held (L100).
- `qc-metrics` already writes `median_pct_mt` and per-sample `pct_mt` quantiles. No predicate
  reads them, and `sc.qc_floor_above_data` covers only `min_genes` and `min_counts`.
- `pct_mt` matches the prefix without case, so mouse `mt-` matches `MT-`. When the var index
  holds Ensembl ids and no `symbol_column` is given, no gene matches and every cell's `pct_mt` is
  0, silently (L116).
- The Xenium and scRNA-seq methods share the operation `qc_cells`. The scRNA-seq clustering
  operation is `cluster`, not `cluster_umap`, so `sc.decision_unreviewed` (scope `normalize`,
  `cluster_umap`) never covers the scRNA-seq clustering step. Recorded here, not filed.
- The literature is strong on the droplet mitochondrial fraction (tissue- and species-dependent;
  a fixed 5% wrong for heart, kidney and tumour) and thin on cell-level QC thresholds for Xenium.
  The spatial ranges will be the method's, set from ROSC and Lyons.

## Altered

Nothing beyond the plan: no code, no contract, no DECISIONS entry.

## Open

- The owner's D1 to D3 (`qc-failure-modes.md` section 4). L115 to L117 can be built on the
  simplest answers: one policy range, flag.
- Then L115 to L117 in plugin singlecell, with `qc-metrics` 0.1.2 in the scRNA-seq method.
- Whether to tidy the engine design's pointers to the plugin's predicate table, and to mark the
  unbuilt example ids as illustrative (offered, not answered).
- The plugin's `spec/predicates.md` header and its closing paragraph describe only the first
  eight predicates.
- Nothing committed.

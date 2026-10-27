# QC failure modes: predicates from the single-cell and imaging-spatial literature

**Status 2026-10-26.** Rows L115 to L127 of `PLAN.md`. Nothing built. The owner asked for
predicates that improve how the methods do on droplet single-cell data and on Xenium data,
grounded in review literature on common failure modes, and named one: a hold or a rejection for
a dataset whose mitochondrial fraction is unusually high at QC. The literature was searched
through Consensus the same day (ten searches; the session note is
`notes/2026-10-26-2130-qc-failure-modes.md`). Checked against plugin singlecell 0.8.7
(`8f9f4f6`), the scRNA-seq method at `v0.1.10` and the Xenium method at `v0.6.0-rc20`. Three
decisions wait on the owner (section 4); L115 to L117 can be built on the simplest answer to
each. The mitochondrial rows come first.

## 1. What the code does today

**Mitochondrial fraction, droplet (the scRNA-seq method).**

- `qc-metrics` 0.1.1 computes `pct_mt` per cell from gene symbols that start with `mt_prefix`
  (default `MT-`, matched without case, so mouse `mt-` matches). It writes the overall
  `median_pct_mt` to `qc_summary`, the per-sample quantiles (1st to 99th percentile) to the
  `qc_distribution` table, and a per-sample box plot. No predicate reads any of it.
- `qc-cells` 0.1.1 drops cells above `max_pct_mt`, a decision point. In `scrnaseq-upstream` the
  default is 100, so at the default no cell is dropped for its mitochondrial fraction. The step
  declares `decision: {evidence: 01_qc_metrics/qc_distribution}` without `hold: always`, and a
  default reached under `run` opens no hold (L100).
- `sc.qc_floor_above_data@1` covers `min_genes` and `min_counts`. Nothing covers `max_pct_mt`.
- The symbols are `var[symbol_column]` when that column exists, else the var index. When the
  index holds Ensembl ids, or the prefix does not fit the species, no gene matches and every
  cell's `pct_mt` is 0. Nothing says so. A targeted panel without mitochondrial genes gives the
  same zero, correctly.

**Mitochondrial fraction, Xenium.** Not measured. `qc-cells` 0.2.3 filters on counts, features
and cell area per organ (the `thresholds` input). Whether the predesigned panels in use carry
any mitochondrial gene is to be checked against their `gene_panel.json`; the working assumption
is that they do not.

**Other QC facts a predicate could read today.**

- `qc_summary` (scRNA-seq): `n_cells`, `median_umis_per_cell`, `median_n_genes`,
  `n_genes_p99`, `n_genes_p01`, `pct_counts_one`, `is_targeted_panel` (fewer than 1000 genes),
  `n_samples`.
- The Xenium bundle summaries (`tools/_xenium_common.py` `bundle_summary`): the vendor medians,
  the panel, `segmentation_methods`, `cells_columns` and `h5_feature_types`. The control-count
  columns of `cells.parquet` are listed in `cells_columns` but not summed.
- `cluster_evidence` (the Xenium method's `find-markers`): `cluster_summary.csv` carries
  `median_counts`, `median_genes` and `median_cell_area` per cluster. The extractor exposes only
  the column names and the cluster ids.
- Neither method has an ambient-RNA, doublet or segmentation-admixture step. The scRNA-seq
  method's `BACKLOG.md` M9 files the doublet step with `sc.doublet_rate_high@1`.

**Normalisation.** The Xenium `normalize` offers `logarea` (the default) and `log_total`.
`sc.normalization_depth@2` is silent on targeted panels (0.8.2), so `log_total` on a panel is
checked by nothing.

## 2. What the literature says, as it bears on a gate

- A fixed 5% mitochondrial cut-off is a historical default. The fraction differs by species and
  tissue: human tissues run higher than mouse, and 5% misclassifies in 13 of 44 human tissues
  while working for most mouse ones [S13]. Heart cells carry about 30% mitochondrial
  transcripts and a 5% cut removes pacemaker cells [S5]; viable malignant cells run high [S22].
  Adaptive and cell-type-aware QC keeps cells that fixed cut-offs lose [S19][S7][S18]. The number
  alone does not separate damage from biology, so a gate on it asks a person.
- Low-quality cells form their own clusters unless removed; QC at the level of cell types finds
  them [S8][S19].
- A count threshold in place of cell calling discards low-UMI cells; a raw barcode matrix needs a
  cell-calling step [S9].
- Ambient RNA is in every droplet experiment, with experiment-specific composition and amount
  [S23]. Uncorrected, ambient genes appear among DE genes and enriched pathways [S1]. A preprint
  benchmark found two correction tools create counts and cell types absent from the raw data
  [S17].
- Doublets lead to spurious conclusions and are found against artificial doublets [S10][S6].
- Segmentation errors confound DE, neighbour influence and ligand-receptor results, often
  dominating the top hits [S11]. Transcript-aware segmentation helps [S14]. Xenium's default
  segmentation misassigned transcripts in some tissue regions [S4]. Platforms differ in
  specificity and in how often segmentation fails [S21]. Cross-site metrics include
  signal-to-noise and false discovery from negative controls [S15], and probe design drives data
  quality [S12].
- On a targeted panel, normalising by counts per cell shifts expression by region and cell type
  according to the panel's composition; normalising by cell area or volume does not [S2].
  Library size is tied to spatial biology [S16].
- QC borrowed from droplet methods is confounded by spatial biology; regional artefacts are found
  from local neighbourhoods [S20] (shown on Visium).
- Thin: no agreed cell-level failure thresholds exist for Xenium, and the platform benchmarks are
  human FFPE, mostly tumour [S21][S12][S15]. The spatial ranges below are the method's, set from
  the ROSC and Lyons deliveries and recorded in its policy, not taken from a paper. Overclustering
  and batch over-correction did not surface in any search.

## 3. What is proposed

Each predicate ships with a must-fire and a must-pass fixture in `tests/test_predicates.py`
`CASES`, a row in the plugin's `spec/predicates.md` and README, and a line in the `gates` of the
modules it covers. Each is silent when the facts it reads are absent and says so in its
evidence, as `sc.qc_floor_above_data` and `sc.louvain_too_large` do. Both methods use the
operation `qc_cells`, so a droplet check must stay silent on Xenium.

### 3.1 Mitochondrial fraction (L115 to L118, first)

**L115 `sc.mito_fraction_high@1`**: pre, scope `qc_cells`, default flag, covers
`qc_cells.max_pct_mt`.

It reads `median_pct_mt_by_sample`, `pct_mt_p95_by_sample`, `n_mt_genes`, `is_targeted_panel`
and the declared species and tissue (D1) from the latest `analysis_summary`, the design's
`units.observation`, and the action's `max_pct_mt`. It fires when any of these holds:

1. A sample's median `pct_mt` is above the bound for its species and tissue.
2. With three or more samples, a sample's median is more than three MADs above the median of the
   sample medians: a sample that failed, whatever the tissue.
3. `max_pct_mt` is at or above the bound (100, the pipeline default, filters nothing) and a
   sample's 95th percentile is above the bound: the filter keeps a damaged tail.

The bound is the declared species and tissue looked up in the plugin's reference table (D3),
else `ranges.sc.median_pct_mt[<band>][1]`, else 10. With `observation: nucleus` it is
`ranges.sc.median_pct_mt_nuclei[<band>][1]`, else 5: a nucleus carries little mitochondrial RNA,
so a high fraction is cytoplasmic or ambient carry-over. Both fallbacks are placeholders for D3.

It is not judged, and the evidence says why, when `n_mt_genes` is 0 (on a targeted panel the
panel has none; on a whole transcriptome L116 holds) and when the facts are absent (the Xenium
method). The evidence carries, per sample, the median and the 95th percentile; the bound and its
source (`reference`, `policy`, `fallback`); the species, tissue and observation unit;
`n_mt_genes`; `mt_prefix`; and the clause that fired.

The reason names the samples and asks whether the fraction is damage (dissociation, ischaemia,
lysis) or the tissue's biology (heart, kidney, tumour). Accept: the run proceeds and the reason
is on record. Reject: the run does not proceed; the operator forks with the sample excluded or
the ceiling changed. A `strict` profile can make it a block with an `overrides` entry (D2).

Method side: `qc-metrics` 0.1.2 writes `median_pct_mt_by_sample`, `pct_mt_p95_by_sample`,
`n_mt_genes` and `first_gene_names` (five) into `qc_summary` (the per-sample quantiles are
already in `qc_distribution`), and the species and tissue as D1 settles; `qc-cells` names the
gate; the policy gains the range.

**L116 `sc.mito_genes_unmatched@1`**: post, scope `qc_metrics`, default block. It fires when
`n_mt_genes` is 0 and `is_targeted_panel` is false. On a whole transcriptome every cell carries
mitochondrial transcripts, so no match means the names read are not symbols or the prefix is
wrong, and every mitochondrial check after this step is blind. The evidence carries `mt_prefix`,
`symbol_column`, `first_gene_names` and `n_genes`; the reason names the prefix and the column
read. Silent on a targeted panel.

**L117 `sc.qc_floor_above_data@2`**: pre, scope `qc_cells`, default block; `covers` adds
`qc_cells.max_pct_mt`. Version 2 adds one clause: `max_pct_mt` below the data's median
`pct_mt` (`median_pct_mt`, already written), so the mitochondrial filter alone would drop more
than half the cells; a fixed cut-off below a tissue's normal fraction removes real cells [S5]
[S22]. Version 1's clauses are unchanged. It is the same kind as L102's data-mismatch predicates,
on a fact the metrics step already writes, so it does not wait on L102's preview.

**L118 `sc.low_quality_cluster@1`**: post, scope the step that writes per-cluster QC medians
(`find_markers` in the Xenium method, `cluster` in the scRNA-seq method), default flag. It fires
when a cluster's median quality metric is more than three MADs from the other clusters' medians
in the bad direction: high `pct_mt`, or low genes or counts (droplet); low counts or genes, or an
extreme cell area (Xenium). Damaged cells cluster together and are then annotated as a state
[S8][S19][S18]. The evidence carries the cluster, its medians, and the other clusters' median and
MAD; the reason asks whether the cluster is damaged cells or a real population, before
annotation. It needs the `cluster_evidence` extractor to expose `cluster_summary.csv`'s
`median_counts`, `median_genes` and `median_cell_area` per cluster in `domain`, and the
scRNA-seq `cluster` module to write the same medians plus `pct_mt` (with M9).

### 3.2 Droplet artefacts (L120, L126, L127)

**L120 `sc.empty_droplets_present@1`**: pre, scope `qc_cells`, default flag. It fires when
`median_n_genes` is below `ranges.sc.min_median_genes[<band>][0]`, else 100, on a
whole-transcriptome input: the matrix was not cell-called, and threshold filtering in place of
cell calling discards low-count cells with the empties [S9]. The evidence carries `n_cells`,
`median_n_genes`, `median_umis_per_cell` and `pct_counts_one`. The facts exist.

**L126 `sc.ambient_high@1` and `sc.correction_count_integrity@1`**: after a scRNA-seq method
step estimates ambient RNA (DecontX works without the raw matrix; SoupX and CellBender need it
[S17]).

- `sc.ambient_high@1`: post on the estimate step, default flag. It fires when the estimated
  contamination, overall or for a sample, is above `ranges.sc.ambient_fraction[<band>][1]`. The
  reason names the samples and the top ambient genes, the genes to distrust in DE [S1][S23].
- `sc.correction_count_integrity@1`: post on a correction step, default block, invariant. It
  fires when a corrected count exceeds the raw count at any cell and gene, or the corrected
  matrix holds a cell or gene the raw lacks [S17]. Cheap when both layers are present.

Method side: a new module, and a row in the scRNA-seq method's `BACKLOG.md`.

**L127 `sc.doublet_rate_high@1`**: the method's M9, post on `detect_doublets`, default flag. It
fires when the called rate exceeds the rate expected for the cells recovered (a policy table
from the vendor's loading guidance) by a margin, or exceeds `ranges.sc.doublet_rate[<band>][1]`
[S10][S6]. The per-cluster doublet fraction also feeds L118.

### 3.3 Imaging spatial (L119, L121 to L125)

**L119 `spatial.count_normalization_on_panel@1`**: pre, scope `normalize`, default flag, covers
`normalize.method`. It fires when a total-count method (`log_total`) is proposed on a targeted
panel of an imaging assay (the state's object carries cell areas): normalising by counts shifts
expression by region and cell type according to the panel's composition [S2][S16]. The Xenium
default `logarea` passes. It fills the gap `sc.normalization_depth@2` leaves on panels. It reads
the panel size and the presence of cell areas from the object summary in the state; if the
`seurat_object` summary lacks either, the extractor gains it.

**L121 `spatial.negative_control_high@1`**: post, scope `split_punches`, default flag. It fires
when a punch's control fraction (control probe, control codeword and unassigned codeword counts
over total counts) is above `ranges.spatial.control_fraction[<band>][1]`, or more than three MADs
above the other punches on its slide [S15][S21][S12]. It needs the punch bundle extractor to sum
the control columns of `cells.parquet` per punch (the synthetic fixture carries them); a
resegmented bundle without them is not judged. The range is the method's, set from ROSC and
Lyons. `flag_outlier_punches` already reads `fraction_transcripts_decoded_q20` in its judgment;
this puts specificity beside it as a deterministic check.

**L122 `spatial.marker_below_noise@1`**: post, scope `annotate_clusters`, default flag; after
L121. It fires when a gene a replicate cites for its cluster has a mean expression in that
cluster not above the negative controls' mean by a margin: a marker the panel does not detect
above noise [S15][S12]. It needs `find-markers` to write per-cluster control means into
`cluster_evidence`. It pairs with `sc.fine_label_uncited`.

**L123 `spatial.transcripts_unassigned@1`**: post, scope `split_punches` and `resegment`,
default flag. It fires when a region's fraction of decoded transcripts assigned to a cell is
below `ranges.spatial.min_assigned_fraction[<band>][0]`: the segmentation missed much of the
tissue's RNA, and segmentation that misses transcripts also misassigns them [S11][S4][S14]. It
reads the vendor's figure for vendor segmentation; a resegmented bundle needs the `resegment`
step to write it.

**L124 `spatial.segmentation_admixture@1`**: pre, scope `test_differential_expression`,
`infer_cell_communication` and `neighborhood_enrichment` on spatial cells, default flag; after a
method module computes a per-cell admixture score from local molecular neighbourhoods, as in
[S11]. It fires when the fraction of the cells tested above an admixture bound exceeds the
range. The module is the work; the predicate is small.

**L125 `spatial.regional_artifact@1`**: post, scope `qc_cells`, default flag. It fires when the
cells failing QC in a punch are spatially clustered (Moran's I of the fail indicator above a
bound): a fold, tear or detachment rather than poor cells scattered through the tissue [S20]. It
needs the Xenium `qc-cells` to write the statistic per punch.

## 4. Decisions for the owner

**D1. Where species and tissue are declared** (L115, and later L118).

- (a) `qc-metrics` parameters `species` and `tissue` (or `tissue_column` for an object holding
  several tissues), set in the objective's `params` and written to `qc_summary` as facts. No
  schema change, and the predicate reads facts as the droplet predicates already do.
  Recommended.
- (b) A `reference: {species, tissue}` key or a `tissue:` column in the plugin's design schema.
  This is a plugin design-schema change (the schema refuses unknown top-level keys), visible at
  init and in the echo-back.
- (c) Neither: one policy range per method. Simplest to build; L115 can ship on it and move to
  (a) as `@2`.

**D2. Flag or block for `sc.mito_fraction_high`.** Flag by default, because the number does not
separate damage from biology [S5][S22][S18]; a `strict` override makes it a block where the owner
wants a rejection. Recommended: flag.

**D3. The bound.**

- (a) One policy range per method, `ranges.sc.median_pct_mt` and
  `ranges.sc.median_pct_mt_nuclei`, values the owner sets (the placeholders in 3.1 are 10 for
  cells and 5 for nuclei).
- (b) Osório's per-tissue reference values [S13], transcribed from the paper's supplement into a
  plugin vocabulary (`mito_reference@1`: species and tissue to an upper bound), with the policy
  range as the fallback. The values cannot be taken from the abstract; this needs the supplement
  and a person to check the transcription.

Recommended: (a) to build L115, (b) as its version 2.

## 5. Contract impact

| row | what it touches | level |
|---|---|---|
| L115 to L127 | thirteen new predicates and one new version (`sc.qc_floor_above_data@2`) in plugin singlecell; fixtures, README, `spec/predicates.md` | plugin |
| L115 to L117 | `qc-metrics` 0.1.2 facts, `qc-cells` gates, policy ranges | scRNA-seq method |
| L118, L121, L122 | the `cluster_evidence` extractor exposes per-cluster medians; the punch bundle extractor sums the control columns; `find-markers` writes control means | plugin tools; Xenium method |
| L123 to L125 | the segmentation, admixture and QC modules write facts | Xenium method |
| L126, L127 | new modules (ambient RNA, doublets) | scRNA-seq method |
| D1 (b) only | the plugin's design schema | plugin schema |

No engine code and no frozen contract is touched.

## 6. What is not proposed

- A fixed 5% cut-off anywhere [S13][S5].
- Rejecting a sample on its mitochondrial fraction without a person (D2).
- Predicates that fire because a pipeline lacks an ambient, doublet or admixture step. Whether
  the step exists is the pipeline's structure; such a predicate would fire on every run of a
  method without the step and say nothing about the data. The method backlogs carry the steps.
- Adaptive cell-level QC (miQC, ddqc, MitoChontrol) in the plugin. It is a method module's
  choice; the predicates read what the module writes.
- Predicates on overclustering or batch over-correction. The searches returned nothing to ground
  them; `sc.batch_effect_suspected`, `sc.batch_route_review` and `de.selection_bias` cover what
  is covered.
- MALAT1 expression as a quality metric [S3]. One preprint so far; revisit when a second source
  agrees.

## Sources

From the Consensus searches of 2026-10-26.

- S1 Arora et al. 2025, [Understanding and mitigating the impact of ambient mRNA contamination in single-cell RNA-sequencing analysis](https://consensus.app/papers/details/8c0d41ef20d45a34984442bc9f7bf032/?utm_source=claude_desktop), PLOS One
- S2 Atta et al. 2023, [Gene count normalization in single-cell imaging-based spatially resolved transcriptomics](https://consensus.app/papers/details/a83f425dab1651fe97e59b25ed1666a2/?utm_source=claude_desktop), bioRxiv
- S3 Clarke et al. 2024, [MALAT1 expression indicates cell quality in single-cell RNA sequencing data](https://consensus.app/papers/details/3e1cd60ceef355df9aed90f790691921/?utm_source=claude_desktop), bioRxiv
- S4 Cook et al. 2023, [A Comparative Analysis of Imaging-Based Spatial Transcriptomics Platforms](https://consensus.app/papers/details/117d0fbbc78b596eb12cd09497d9a59e/?utm_source=claude_desktop), bioRxiv
- S5 Galow et al. 2021, [Quality control in scRNA-Seq can discriminate pacemaker cells: the mtRNA bias](https://consensus.app/papers/details/f0b133ab897259c7822d0d7b962a0d4f/?utm_source=claude_desktop), CMLS
- S6 Germain et al. 2021, [Doublet identification in single-cell sequencing data using scDblFinder](https://consensus.app/papers/details/6304a567acdc57bfab257d00a1201386/?utm_source=claude_desktop), F1000Research
- S7 Hippen et al. 2021, [miQC: An adaptive probabilistic framework for quality control of single-cell RNA-sequencing data](https://consensus.app/papers/details/8b8d8ee57a4556358ab9d78d85fae498/?utm_source=claude_desktop), PLoS Computational Biology
- S8 Ilicic et al. 2016, [Classification of low quality cells from single-cell RNA-seq data](https://consensus.app/papers/details/e2c0db6e943552b6bd143f2560a9944c/?utm_source=claude_desktop), Genome Biology
- S9 Lun et al. 2018, [Distinguishing cells from empty droplets in droplet-based single-cell RNA sequencing data](https://consensus.app/papers/details/864154cbd02155e39bbbfd7ecd4eadcd/?utm_source=claude_desktop), bioRxiv
- S10 McGinnis et al. 2018, [DoubletFinder: Doublet Detection in Single-Cell RNA Sequencing Data Using Artificial Nearest Neighbors](https://consensus.app/papers/details/d40672a1b3245d09962b4daa1d2d03db/?utm_source=claude_desktop), Cell Systems
- S11 Mitchel et al. 2026, [Impact and correction of segmentation errors in spatial transcriptomics](https://consensus.app/papers/details/3a0296b31207580ebac6905b7705b50a/?utm_source=claude_desktop), Nature Genetics
- S12 Molina-Ayala et al. 2025, [Comparison of imaging based single-cell resolution spatial transcriptomics profiling platforms using formalin-fixed paraffin-embedded tumor samples](https://consensus.app/papers/details/d95a98610dfb5281ad3d41b4d19ffbfd/?utm_source=claude_desktop), Nature Communications
- S13 Osório et al. 2020, [Systematic determination of the mitochondrial proportion in human and mice tissues for single-cell RNA sequencing data quality control](https://consensus.app/papers/details/25a198503d1d59a7897de43ddd2b8f73/?utm_source=claude_desktop), bioRxiv (published in Bioinformatics)
- S14 Petukhov et al. 2021, [Cell segmentation in imaging-based spatial transcriptomics](https://consensus.app/papers/details/a67a407890eb5dc085c3988fc67f15c7/?utm_source=claude_desktop), Nature Biotechnology
- S15 Plummer et al. 2025, [Standardized metrics for assessment and reproducibility of imaging-based spatial transcriptomics datasets](https://consensus.app/papers/details/dbd8794dce5f55c0b8cc27ad7abbc847/?utm_source=claude_desktop), Nature Biotechnology
- S16 Salim et al. 2025, [SpaNorm: spatially-aware normalization for spatial transcriptomics data](https://consensus.app/papers/details/03d0ebf1a473593da314d4bdd6c85494/?utm_source=claude_desktop), Genome Biology
- S17 Schroeder et al. 2026, [Benchmarking ambient RNA removal across droplet and well-plate platforms reveals artificial count generation as a critical failure mode of scAR and CellClear](https://consensus.app/papers/details/1cea4e27889f58eead25e9b6d8df9eba/?utm_source=claude_desktop), bioRxiv
- S18 Strassburg et al. 2026, [MitoChontrol: Adaptive mitochondrial filtering for robust single-cell RNA sequencing quality control](https://consensus.app/papers/details/2360b03f23e8571d93e8568db02472b2/?utm_source=claude_desktop), bioRxiv
- S19 Subramanian et al. 2021, [Biology-inspired data-driven quality control for scientific discovery in single-cell transcriptomics](https://consensus.app/papers/details/f6d4a00628a9535ea8b07ecc43060376/?utm_source=claude_desktop), Genome Biology
- S20 Totty et al. 2025, [SpotSweeper: spatially-aware quality control for spatial transcriptomics](https://consensus.app/papers/details/fb9a7f33df95521687928d644da444ac/?utm_source=claude_desktop), Nature Methods
- S21 Wang et al. 2025, [Systematic benchmarking of imaging spatial transcriptomics platforms in FFPE tissues](https://consensus.app/papers/details/5fdd6b33371f509f9965ff9b7d228705/?utm_source=claude_desktop), Nature Communications
- S22 Yates et al. 2025, [Filtering cells with high mitochondrial content depletes viable metabolically altered malignant cell populations in cancer single-cell studies](https://consensus.app/papers/details/41f7019d9cb254aea4035aaecc178ef2/?utm_source=claude_desktop), Genome Biology
- S23 Young et al. 2018, [SoupX removes ambient RNA contamination from droplet-based single-cell RNA sequencing data](https://consensus.app/papers/details/5c45823b193e5917bebaef289bf2b16c/?utm_source=claude_desktop), GigaScience

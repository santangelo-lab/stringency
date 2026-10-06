# Lane F: the spatial method after QC, Lyons CLP as the pilot (2026-09-23)

Working note, not the spec. Successor to `spec/archive/app1-spatial-qc-plan.md` (Track 3, Lane C, closed
2026-09-23) and to the sessions of `spec/archive/app1-spatial-tma-plan.md` that the QC work did
not reach (7 to 12 and 14). Drafted for the owner's approval; the decisions it needs are in
section 8. Engine: `v0.2.4` when drafted, `v0.2.6` (Track 1h) when phase 0 started on
2026-10-06. Method: `stringency-xenium-method` `v0.3.3-rc1`, `PLAN.md` there lists the open module
items this plan absorbs. All eleven decisions of section 8 were taken by the owner on 2026-10-06;
F0 to F3 ran the same day (phase 0 complete). Decision 1 chose R with the ROSC code, so sections
5 to 7 were rewritten for R the same evening and decisions 12 to 15 taken; F4 is next.

**Status 2026-10-06.** Sections 1 to 4 are the plan as drafted and, for phase 0, as run (F0 to F3 done 2026-10-06; the record is `/lab/projects/Lyons_CLP/PROGRESS.md` and `notes/2026-10-06-1345-lane-f-phase0.md`). Sections 5 to 7 are current: the downstream pilot re-planned for R. Section 8 carries every owner decision, all fifteen taken; F4 done 2026-10-06; F5 is next.

## 1. Where this sits

Lane C delivered the QC layer on Lyons CLP: eight regions split into 42 punches, per-cell QC,
four Proseg resegmentations as their own projects, a cross-region summary, and a judgment that
proposes punches for review. Every downstream question (what cell types, what neighbourhoods,
what changes with time after CLP) starts from the delivered `qc_object_set`s: one `h5ad` per
punch with raw counts in `X`, `obsm["spatial"]`, and the design columns `punch_id`, `animal`,
`timepoint_h`, `condition`, `slide`, `organ` already on `obs`.

The guide is `ROSC_MTA2` (BMESEQ, archived read-only at `/lab/archive/bmeseq/Projects/ROSC_MTA2`;
surveyed 2026-09-23). It is the lab's most complete Xenium TMA analysis: 18 declared steps under a
gated state file, 11 tissues, four environments, a defect register. It is a guide, not code to
copy: its analysis is R and Seurat while the QC layer here is Python and AnnData; its steps are
per-tissue script copies scaffolded from Spleen, with hand-written `case_when` label maps and
Quarto prose that the gates check for markers; its replication unit is the punch (n about 2 per
arm) where Lyons declares the animal; and half of it (cargo delivery, reporter genes, IF) does
not apply to CLP. What carries over is the analysis shape and the parameter values that were
tuned on the same platform and panel family.

## 2. What ROSC_MTA2 teaches

The step order, from `analysis/orchestrate/parse_state.py` (`STEP_ORDER`), with what becomes of
each here:

| ROSC step | what it does | Lyons CLP |
|---|---|---|
| `upstream.loadqcpca` | per-punch QC (nCount, nFeature, area), LogArea normalisation, PCA | done by `qc-cells` (QC) ; normalisation and PCA move to the clustering pipeline |
| `upstream.clustering` | Seurat FindNeighbors, Louvain over resolutions 0 to 1, res 0.4 used, UMAP; seed 1984; ndim 35 (Spleen 40) | `xenium-cluster` pipeline in R (Seurat, Louvain, section 5); the resolution is a ranged parameter |
| `upstream.annotation` (interactive) | FindAllMarkers (logfc 0.5) then a hand-written cluster to label map, written by an agent with the `/single-cell-annotation` skill and a person; `AssertAnnotationComplete` refuses NA or fallback labels | the first downstream judgment module: three replicates over a marker table, a closed vocabulary per organ with `unknown`, controls before the first real run |
| `upstream.timepoint_batch` (interactive) | per-cluster time-point and TMA composition tables, ISG enrichment, agent prose | code-only tables in the cluster report; no prose module |
| `downstream.h5ad` | rds to h5ad, `obsm["spatial"]` | not needed; the objects are h5ad from the start |
| `mod1_niche`, `mod1_zones` (interactive), `mod1_zone_export` | spatial kNN (k 25) composition per cell, k-means k 4 to 12 (nstart 30, seed 42), WSS elbow, hand-named zones, `zone_labels.csv` | `xenium-niches` pipeline: neighbourhood, k-means, a niche-labelling judgment, export |
| `mod2_cellquant` | 200 µm tiles, spatial NB GLMM (sdmTMB) per cell type, adjusted by zone; external R package `CellQuant` (not in the archive) | out of the pilot: R, an unarchived package, and n = 2 animals; composition is reported descriptively (section 5, phase 5) |
| `mod3_pathway`, `mod3_hotspot` | UCell scores over 7 innate gene sets, punch means, limma per contrast; Hotspot autocorrelation | `score-pathways` in R (UCell over the same gene sets, section 5), animal means, limma on the means; Hotspot deferred |
| `mod4_neighborhoods` | squidpy `nhood_enrichment` per punch, 1000 permutations, seed 42, descriptive only | `neighborhood-enrichment`, descriptive, with the permutation null recorded so `spatial.no_permutation_null` is decidable |
| `mod5_cellchat` | spatial CellChat per arm, 100 bootstraps, filtered by the proximity mask | out of the pilot (R, the highest confabulation risk per the archived plan's session 10); a later pipeline if the owner wants it |
| `mod6_de` | per zone × cell type: FindMarkers (cell level) and pseudobulk limma-voom (punch level), concordance, boundary gradient | `pseudobulk-de`: limma-voom pseudobulk per animal × cell type (or zone × cell type), the animal as the replication unit, contrasts between time points, no cell-level test as a claim |
| `mod7_*` (cargo, pyMFI) | reporter delivery from IF | not applicable |
| `interpret` (interactive) | agent rewrites the Quarto prose | replaced by a report module (code-generated prose, every numeral a table cell) and, later, a salience judgment with a considered set |
| `cross_tissue` | concatenates the per-tissue CSVs | one `arity: many` step over the per-organ deliveries |

Values worth keeping as defaults, because they were tuned on this platform: kNN k 25 for
niches; k-means k 4 to 12 with WSS elbow; ndim 35; clustering resolution 0.4 within 0.2 to 1.0;
marker logfc 0.5; neighbourhood permutations 1000; niche minimum 200 cells; QC labels
(`Low quality`, `Contamination`) excluded from spatial statistics.

What ROSC did that this method must not: per-tissue script copies (eleven per step, drifting;
here one module with per-organ defaults); absolute paths inside scripts (the job JSON carries
paths); Quarto prose as the record (the trace is the record; prose is a report module's output);
fingerprints by size and mtime (content hashes); `ScaleData` before `FindVariableFeatures`
(order is a predicate here: `qc.filter_ordering`); declared step dependencies that undercount the
real inputs (`mod2` and `mod3` read zones but declare only annotation; the engine binds every
input explicitly and `topo.predecessor_incomplete` blocks).

Open in ROSC and therefore open here: whether LogArea normalisation (log1p of counts per area
times 100) is right for Xenium (`setup/Claude/Normalization_intercept_proposal.md`); the
`co_occurrence` index error; the confound of time point with TMA.

## 3. Lyons CLP against ROSC

**The pilot's goal (owner, 2026-10-06):** identify the tissues and time points where the CLP
procedure leaves an obvious signal, despite n = 2 animals per time point. The downstream
deliverable is a screen across four organs and three time points, read descriptively, with the
DE pass naming candidates for a powered study, not a confirmatory test of any one contrast. Every
downstream `objective.yml` says this, and the reports rank tissue × time point by the size and
consistency of the departure from 6 h rather than by p-values alone.

| | ROSC_MTA2 | Lyons CLP |
|---|---|---|
| design | routes RO, SC and a pooled control; D1 and D3; six contrasts | one factor, time point 6, 24, 48 h after CLP; no sham; contrasts between time points |
| replication unit | punch (n about 2 per arm) | animal, n = 2 per time point, punches A and B nested |
| tissues | 11, Prime 5K | gut, spleen, lung, liver; `mAtlas_v1` plus `mMulti_100g`, 5,175 targets |
| batch | TMA | slide, partially confounded with time (6 h only on TMA 1, 48 h only on TMA 2) |
| reporters, IF | tdTomato, Cre, pyMFI | none |
| cells | up to 823k per tissue (Spleen) | 42 punches; the largest organ region about 700k cells before the split, far fewer per punch |

Consequences: `min_n_per_group` is 2 and `obj.feasibility` will sit at its floor; every
time-point contrast carries the slide confound and `de.covariate_omission` flags it, which the
owner accepts with a reason once per project (7.4 rebind); punch-level analyses are hypothesis
generation and the objective says so; the runtime and memory that made ROSC a five-hour-per-tissue
affair shrink by an order of magnitude here.

## 4. Phase 0: the QC chain again (owner's request, 2026-09-23; done 2026-10-06 on engine 0.2.6)

Everything Lane A built this week was built from what the QC chain exposed. Running the chain
again on the same data, with the method fixes it also exposed, is both the validation of the
engine and the clean starting point for downstream. Resegmentation is not repeated: the four
Proseg bundles are delivered artifacts of `reseg_*` projects (4.5 to 7.5 h each) and nothing about
them changes.

Method changes first (`stringency-xenium-method`, one tag, `v0.4.0`):

1. `qc-cells` 0.1.3: `segmentation_of` reads `imported_cell_frac` or the Ranger `import-segmentation`
   command line, so Proseg regions are labelled (`PLAN.md` 2.1).
2. `qc-report-all` 0.2.0: one input `metrics: {type: table, arity: many}` bound as
   `$inputs.metrics_*`; the pipeline file stops changing with the region count (`PLAN.md` 3.2).
3. `flag-outlier-punches` 0.2.1: bands clipped at zero for non-negative attributes, the
   sibling-punch column, the two `guide.md` additions, the reference builder's panel check
   (`PLAN.md` 1.2 to 1.5, 1.7). A version bump defeats every rebind, so the second judgment is
   clean.
4. `exclusion-proposal` 0.2.1 and the project-level exclusion file (`PLAN.md` 1.9): columns
   `punch_id, excluded, reason, decided_by, review_id`, declared as an input named
   `punch_exclusions` (type `csv`, `role: observation`) on every downstream pipeline, read by the
   merge step (phase 2). The owner writes it from the proposal and their own reading; the file's
   hash binds it.
5. `xenium-qc-proseg` removed from the README (`PLAN.md` 2.5).

Then the projects, new directories on the new tag beside the old ones (a project pins its method
tag at init; the old projects stay as the record of `v0.1.3` to `v0.3.3-rc1`):

| step | projects | what it exercises |
|---|---|---|
| QC | `qc2_<slide>_<Region>` × 8, binding the same raw bundles (liver, spleen) or the delivered Proseg bundles through `derived_from` (lung, gut), coordinates, layout, histology | raw inputs, so eight ordinary confirm holds: **batch review** (`review --holds ... --projects /lab/projects/Lyons_CLP`) gives one echo-back and one acceptance; `param.agent_proposed` on any threshold the operator proposes; the review page for the holds |
| summary | `qc2_summary_all`, `metrics: $inputs.metrics_*` over the eight `qc2` deliveries | **`arity: many`** on real data; every input `derived_from` the same owner's confirmed projects with an identical design: **inherited confirmation**, no hold |
| outliers | `qc2_outliers_all` on `xenium-qc-outliers-ref` with module 0.2.1 | the K7 fix (the delivered proposal carries the verdicts), one hold for any invalid replicate, the renderer's citation lookup on the secondary tables, `any_low` logged not held |
| exclusion | the owner's `punch_exclusions.csv` under `/lab/projects/Lyons_CLP/` | the file every phase-2 project binds |

Comparison note at the end (data side, `PROGRESS.md`): per-punch metrics identical to the first
chain except the segmentation label; the outlier verdicts against the 2026-09-23 decisions; how
many cards and holds the second chain cost against the first (the Lane E measurement row).

There is no pathology pass (owner, 2026-10-06): `histology_include.csv`, the owner's notes of
2026-09-16 confirmed 2026-09-17, is the final histology call, and the chain runs on it. Earlier
text here and in the Lyons project files that promised a later pathology pass was an error.

Engine follow-up this phase may raise (Lane A, small): an input with `role: reference` should not
defeat inherited confirmation, since a reference table is not this design's data; today
`qc2_outliers_all` opens an ordinary hold because of it.

## 5. The downstream pipelines (re-planned for R, 2026-10-06)

Owner decision 1 (section 8): the pilot reuses the ROSC_MTA2 code, which is Seurat v5 in R end to
end (survey of the archive, 2026-10-06: every R step reads and writes `.rds`; `anndataR` 1.0.0
converts to h5ad once, for the Python squidpy step; no step reads h5ad into R). What changes
against the first draft: the object between steps is a Seurat object, the modules that touch it are
R scripts in one `xenium-r` image, and the plugin reads a Seurat object's state through an R
extractor. What does not change: one module per step with per-organ defaults, judgment where ROSC
put a person (labels, zone names), the parameter values tuned on this platform, the deliverable
set, and the gates. Judgment modules stay in Python (`xenium-py`): their evidence is tables, not
objects.

### 5.0 How R meets the engine

- **Object type `seurat_object`** (plugin 0.2): a `.rds` holding a Seurat v5 object. Extractor
  `tools/extract_seurat.R`, run by the engine as `Rscript` inside the module's image (the executor
  already dispatches `.R` scripts; the tool's env is the producing module's env, `xenium-r`). It
  prints the design 4.2 envelope with the same keys the `anndata` extractor prints, so every
  predicate stays object-agnostic: `n_obs`, `n_var`, `fields.obs` (meta.data columns with dtype,
  `n_unique`, levels), `fields.obsm` (reductions: `pca`, `umap`, `spatial` from the FOV coordinates),
  `fields.layers` (`counts`, `data`, `scale.data` present or not), `fields.uns_flags` from
  `obj@misc$stringency` (below), `counts_per_group` from the design, and `domain` (cells per
  cluster per punch and per animal, labels present and their vocabulary, the spatial graph's
  definition). Load time is the cost: a 1.4 M-cell spleen object takes a minute or two to read.
- **`misc$stringency`**: every R module writes what it did into the object (`normalisation:
  {method, scale_factor}`, `hvg: {n, flavor}`, `pca: {ndim}`, `neighbors: {dims, k}`, `clustering:
  {algorithm, resolution, seed, column}`, `spatial_graph: {k, per: punch_id}`, `labels: {column,
  vocabulary}`), the R twin of the `uns` flags the Python draft relied on; `qc.filter_ordering`,
  `spatial.neighborhood_undeclared` and `sc.panel_hvg` read these through the extractor.
- **Reading the QC objects.** The `qc_object_set` is h5ad (checked 2026-10-06: raw counts in `X`,
  `obs` with `cell_id`, `cell_area`, `nCount`, `nFeature`, `punch_id`, `animal`, `timepoint_h`,
  `condition`, `slide`, `organ`, `obsm["spatial"]`, `uns["stringency_qc"]`). The merge module reads
  them with `anndataR::read_h5ad` as a Seurat object, keeps `cell_area` in meta.data (LogArea
  needs it) and the coordinates as a FOV. anndataR is the package ROSC already uses, but only in
  the other direction (decision 12): the reader is proven in the F4 spike by a round trip before
  any pipeline depends on it.
- **Writing h5ad when Python needs it.** One module, `export-h5ad`, writes `as_AnnData(obj,
  x_mapping = "counts", ...)` with `obsm[["spatial"]]`, as ROSC's `convert_to_h5ad.R` does; its
  output is an `anndata` object the existing Python extractor reads, and a predicate
  `sc.export_mismatch` (block) compares `n_obs`, the obs columns and the label column against the
  parent `seurat_object`'s state. Only the squidpy module binds it.
- **Shared R code** lives in `modules/_rlib/` (copied from the archive with the `/data-raid` paths
  and the per-tissue copies removed; the archive commit recorded in each file's header):
  `LogAreaNormalize` and `MultiResCluster` from `Xen_Seurat_functions.R`, the niche builder from
  `run_niche_Spleen.R`, `de_utils.R`, `pathway_utils.R`, `innate_pathway_genesets.R`,
  `qc_exclusion.R`. Each module is `run.R` reading the job JSON (`jsonlite`) and writing outputs
  to the paths it names; `_rlib` is bound with the module directory as `qc_plots.py` is today.
  Column names move from ROSC's (`run_name`, `time`, `TMA`, `tissue`) to Lyons' (`punch_id`,
  `timepoint_h`, `slide`, `organ`) at the merge; `animal` exists here and did not in ROSC.
- **Determinism.** `set.seed` from the step's `seed` parameter before every stochastic call; no
  `future::plan(multicore)` (ROSC's ten workers made run order a variable); `RunUMAP` with
  `seed.use`; the resources block caps cpus.

### Phase 1: foundations (F4)

- Image `xenium-r` (section 7). Plugin 0.2: `seurat_object` and `extract_seurat.R`;
  `sc.export_mismatch`; the ten predicates of the first draft unchanged in meaning, their fixtures
  now Seurat-state envelopes as well as anndata ones; vocabularies `cell_types_<organ>@1` (Cell
  Ontology subsets with ids, drafted by the agent from the panel and ROSC's 237-row
  `cell_type_collapse_map.csv`, plus `unknown`, `low_quality`, `contamination`; the collapse map
  per organ committed beside it) and `niches_<organ>@1` with `proposed_label`; typed operations
  `merge_objects`, `normalize`, `reduce_cluster`, `find_markers`, `annotate_clusters`,
  `apply_labels`, `spatial_niches`, `label_niches`, `apply_zones`, `compose_cells`, `export_h5ad`,
  `neighborhood_enrichment`, `pseudobulk_de`, `score_pathways`; question `cell_type_annotation`.

### Phase 2: `xenium-cluster` (one project per organ)

| step | module | env | params (default, range) | notes |
|---|---|---|---|---|
| 01_merge | `merge-punches` | xenium-r | none | `qc_objects: {type: qc_object_set, arity: many}` bound `$inputs.qc_*` over the organ's two `qc2` deliveries; `punch_exclusions` (csv, role observation) applied and recorded in `misc$stringency$exclusions`; one `seurat_object` with the design columns and `cell_area` on meta.data, coordinates as FOVs per punch |
| 02_normalize | `normalize` | xenium-r | `method` logarea (default, decision 2) \| log_total; `scale_factor` 100 | ROSC `LogAreaNormalize` (`counts %*% Diagonal(1/cell_area)`, then `log1p(x * 100)`); the report shows both methods on one punch once |
| 03_reduce_cluster | `reduce-cluster` | xenium-r | `n_features` 2000 (500 to all); `ndim` 35 (20 to 50; ROSC used 40 for spleen); `resolutions` [0.2, 0.4, 0.6, 0.8, 1.0]; `resolution` 0.4; `seed` 1984 | ROSC order kept: `FindVariableFeatures`, `ScaleData`, `RunPCA`, `FindNeighbors(dims 1:ndim)`, Louvain at the listed resolutions only (not 0 to 1 by 0.1: eleven clusterings at 1.4 M cells is the five-hour step), `Idents` at `resolution`; `RunUMAP` uwot cosine, n.neighbors 30, min.dist 0.3, seed 42, for the report only; `stochastic: true`, `seed_param: seed` |
| 04_markers | `find-markers` | xenium-r | `logfc_min` 0.5, `min_pct` 0.1, `test` wilcox | `FindAllMarkers` at the chosen resolution; one table: cluster, gene, logfc, pct in, pct out, adjusted p |
| 05_report | `cluster-report` | xenium-r | none | the ROSC `timepoint_batch` tables as code: cells per cluster per punch, animal, time point and slide; ISG enrichment per cluster; UMAP and per-punch spatial PNGs; every numeral a table cell |

Deliverables: `clustered_object` (`seurat_object`), `markers`, `cluster_report`. Decision points:
`resolution`, `ndim`, `method`; `param.agent_proposed` will hold once per project on each.

### Phase 3: `xenium-annotate` (the first downstream judgment)

- `annotate-clusters` (judgment, `xenium-py`, `all_items`, 3 replicates, abstain required, ordinal
  confidence). `pre.py` reads the `markers` table and the report's composition tables (no object)
  and writes the evidence: `markers` (top 25 per cluster with logfc, pct in and out), `composition`
  (cells per cluster per punch, animal, time point, slide), `context` (organ, species, panel,
  expected populations and known absences from the collapse map). Vocabulary
  `cell_types_<organ>@1`; the `/single-cell-annotation` skill's evidence rules transcribed into
  `prompt.md` and `guide.md`; `alternative_labels` allowed; the prompt says time points and other
  clusters' ids in words (method `PLAN.md` 1.10).
- Controls (before the first real run): positive, ROSC `Liver_annotated.rds` and
  `Spleen_annotated.rds` from the archive (`analysis/upstream/<T>/output/pipeline/objs/`) through
  `find-markers` and the same `pre.py`, agreement at the collapsed group level after the collapse
  map; negative, marker symbols shuffled across clusters, expecting `unknown` or abstain.
- `apply-labels` (xenium-r): consensus to `meta.data$cell_type` with the ontology id, the collapse
  map to `cell_type_group`, `Low quality` and `Contamination` groups flagged for exclusion from
  spatial statistics (ROSC `exclude_qc`); `misc$stringency$labels`; deliverables
  `annotated_object` and a label summary table. `sc.unknown_fraction` flags a poorly resolved
  organ.

### Phase 4: `xenium-niches`

| step | module | env | params |
|---|---|---|---|
| 01_niches | `spatial-niches` | xenium-r | `k` 25 (10 to 50); `k_range` 4 to 12; `nstart` 30; `seed` 42 | ROSC `run_niche`: per-punch spatial KNN on the FOV coordinates, one-hot `cell_type` summed over neighbours (QC groups excluded), a `niche` assay, `ScaleData`, k-means over `k_range`; writes `misc$stringency$spatial_graph` (so `spatial.neighborhood_undeclared` is decidable), the WSS table, composition per niche cluster per k, sizes per punch |
| 02_label | `label-niches` (judgment, xenium-py) | evidence from the CSVs: composition per niche at the proposed `k`, the WSS table, the top cell types; vocabulary `niches_<organ>@1` plus `proposed_label` (always holds); `k` proposed by the module from the WSS second difference and approved by the person (`param.agent_proposed`) |
| 03_zones | `apply-zones` | xenium-r | `zone`, `zone_broad` on meta.data (ROSC `zone_map`, `broad_map`); `zone_labels.csv` with barcode, as ROSC's export; `sc.small_niche` on any zone under 200 cells |

### Phase 5: composition and neighbourhoods, descriptive

- `compose-cells` (xenium-r): cells per cell type per punch, animal and zone; proportions with the
  animal as the unit; with n = 2 the table header says nothing is tested (CellQuant is out).
- `export-h5ad` (xenium-r): `anndataR::as_AnnData` with counts in `X`, `obsm["spatial"]`, the label
  and zone columns; object type `anndata`; `sc.export_mismatch` against the parent.
- `neighborhood-enrichment` (xenium-py, squidpy, from ROSC `run_neighborhoods` and
  `neighborhood_utils.py`): `spatial_neighbors(coord_type generic, n_neighs 15)`, `nhood_enrichment`
  per punch, per time point and per zone with `n_perms` 1000 and `seed` 42, the permutation
  artifact recorded so `spatial.no_permutation_null` is decidable; `co_occurrence` guarded (the
  ROSC index error); descriptive deltas only, no p-values, the report says so.

### Phase 6: `xenium-de` (contrasts declared in `objective.yml`)

- `pseudobulk-de` (xenium-r, from ROSC `de_utils.R`, decision 4): `AggregateExpression` summed
  counts per **animal** × cell type (ROSC aggregated per punch; here the punch pair of one animal
  is one sample), later per animal × zone × cell type; `filterByExpr`, `calcNormFactors`, `voom`,
  `lmFit(~ timepoint_h)`, `eBayes`, `topTable` per contrast (24 vs 6, 48 vs 6, 48 vs 24); BH;
  `min_cells_per_pseudobulk` 30, `min_animals_per_group` 2; `slide` declared batch, its omission
  flagged once (`de.covariate_omission`). ROSC's cell-level `FindMarkers` stays only as a
  concordance table marked descriptive, never as a claim (`de.replication_unit` blocks a
  cell-level test offered as one). Logged: `de.selection_bias` is scoped so a declared-factor
  contrast does not fire.
- `score-pathways` (xenium-r, ROSC `run_pathway`): `UCell::AddModuleScore_UCell` over the innate
  sets (`ifn_isg, tlr_prr, nfkb_cytokines, inflammasome, complement, chemokines,
  antigen_presentation`, supplementary `myeloid_activation`; `validate_genesets` at min 5 genes
  and 0.5 coverage writes the coverage table), animal means per cell type, `limma` on the means
  with the same design and contrasts; the liver sets from `hepatocyte_pathway_genesets.R` for
  liver only.
- Later, not the pilot: `flag-salient` (judgment, `considered_set: true`) over the DE and pathway
  tables; Hotspot.

### Phase 7: reports, cross-organ, skills

- `report-spatial` (xenium-r): code-generated prose per pipeline, every numeral a table cell
  (`judg.numeric_claims_match` on report steps), the figures the tables feed; for the pilot's
  goal (section 3) a ranking of tissue × time point by the size and consistency of the departure
  from 6 h across clusters, zones and pathways, descriptive.
- `xenium-cross-organ` (xenium-py): one step with `arity: many` over the four organs' label
  summaries, niche tables, DE and pathway tables, joined on the collapsed group only (ROSC
  `accumulate_cross_tissue.py` as the shape).
- Skills: `skills/<pipeline>.yml` and `skills/<pipeline>.analyze.yml` per pipeline; the first
  spatial analysis skill is Lane E's acceptance target.

## 6. Sessions (half a day each, in order; F0 to F3 done 2026-10-06)

| # | session | delivers | gate to the next |
|---|---|---|---|
| F0 | this plan approved; owner decisions in section 8 recorded in `PLAN.md` | the plan | done 2026-10-06 (all eleven) |
| F1 | method `v0.4.0`: the five phase-0 changes, tests (`tests/run_summary.sh` with a glob input, `run_outliers.sh` with clipped bands), lint | tag pushed | done 2026-10-06 |
| F2 | phase 0 run, part 1: eight `qc2` projects through batch review; the summary through inherited confirmation | eight QC deliveries, one summary | done 2026-10-06 (inheritance did not fire: L5; sixteen `param.agent_proposed` holds: L6) |
| F3 | phase 0 run, part 2: `qc2_outliers_all` with three fresh delegates; the owner's decisions; `punch_exclusions.csv`; the comparison note; the Lane E measurement row for a chained real run | the exclusion file | done 2026-10-06 (one run rejected by `judg.numeric_claims_match`, the second clean) |
| F4 | image `xenium-r` (renv lock, rocker, PPM, Bioconductor 3.22) on GHCR, pulled by digest; `modules/_rlib/` from the archive; plugin 0.2 (`seurat_object`, `extract_seurat.R`, `sc.export_mismatch`, typed operations); the anndataR round trip; `merge-punches` and `normalize` on the two livers | image in `MANIFEST.md`; plugin `v0.2.0` installed as `0.2.6-sc0.2.0`; method `v0.5.0-rc2`; `cluster_liver` delivered | done 2026-10-06 (round trip EQUAL; the ten predicates with Seurat fixtures moved to F5; engine L7 found) |
| F5 | `xenium-cluster` modules and pipeline; synthetic control (a two-punch fixture from the toy-like generator, in R); run on liver | clustered liver, markers, report | delivered |
| F6 | `xenium-cluster` on spleen, lung, gut; the cluster reports read with the owner; resolution and `ndim` decisions recorded as `param.agent_proposed` acceptances; spleen runtime measured | four clustered objects | delivered |
| F7 | vocabularies for four organs with collapse maps (owner approves); `annotate-clusters` module (`pre.py`, prompt, schema, `guide.md`); controls from the ROSC liver and spleen objects through `find-markers` | module lints; both controls pass | controls green |
| F8 | `xenium-annotate` on the four organs; the owner walks the item holds; `apply-labels` | four annotated objects, label summaries | delivered |
| F9 | `xenium-niches` modules; run on the four organs; the niche-label judgment with the `k` proposal | zones per organ | delivered |
| F10 | phase 5 descriptives (`compose-cells`, `export-h5ad`, `neighborhood-enrichment`); `xenium-de` with limma-voom at the animal; contrasts declared; feasibility at n = 2 read honestly | DE and pathway tables per organ | delivered |
| F11 | `report-spatial`, `xenium-cross-organ`, delivery and analysis skills; the first spatial analysis skill run by a lab member (Lane E's acceptance test); the tissue × time point ranking for the owner | the deliverable set for the collaborator | owner's reading |
| F12 | retrospective: override rate per judgment module, uncovered decision points, one delivered number reconstructed from `run.db` alone, the backlog for the next method version; whether to bring CellChat and CellQuant in now that the image can hold them | note | |

F4 needs the owner once (the image's package list and the first `seurat_object` envelope shown);
F5 runs without; F6 onward needs the owner at each judgment's holds and at the per-project
parameter holds. The plugin half of F4 and the image half can run in parallel.

## 7. Environments

- **`xenium-r`** (new; nothing in the archive defines ROSC's R library, so it is rebuilt from the
  27 pins in `setup/envs/r_package_versions.csv`): `rocker/r-ver:4.5.1` with Posit Package Manager
  binaries for the CRAN set, Bioconductor 3.22 for `limma` 3.66, `edgeR` 4.8, `UCell` 2.14,
  `rhdf5` 2.54; CRAN `Seurat` 5.4.0, `SeuratObject` 5.3.0, `Matrix` 1.7-3, `uwot` 0.2.4, `igraph`
  2.2.2, `irlba`, `clustree`, `nanoparquet`, `arrow`, `RANN`, `anndataR` 1.0.0, `jsonlite`,
  `yaml`, `tidyverse`; not `CellChat`, `sdmTMB`, `speckle`, `lme4` (out of the pilot; added when
  F12 says so). Pinned by an `renv.lock` written at the first successful build and committed
  (design 10.3: the lock is the env digest for the local executor; the SIF sha256 for apptainer).
  Built by `.github/workflows/image.yml` (matrix gains `xenium-r`) to GHCR, pulled by digest to
  `/data/lab/env/images/xenium-r-0.1.0.sif`, recorded in `MANIFEST.md`. Build time is the F4 risk:
  Seurat and its dependencies compile for an hour without binaries; with PPM binaries minutes.
  `future` is installed but no module calls `plan()`.
- **`xenium-py` 0.1.0** stays as it is for `qc-cells`, the judgment `pre.py` scripts,
  `neighborhood-enrichment` (scanpy 1.11.5, squidpy 1.8.1, anndata 0.12.0 are already in it) and
  `xenium-cross-organ`. No `xenium-py` 0.2.0 is needed; `leidenalg` and `pydeseq2` are not added.
- Every module runs under apptainer with `<step dir>/tmp` bound; Nextflow is not involved
  downstream. Memory: a Seurat object of two spleen slides (about 1.4 M cells, 5,175 genes) is on
  the order of tens of GB in R; the resources block says 128 GB for `reduce-cluster` on spleen and
  64 GB elsewhere, within the shared machine's 500 GB.

## 8. Decisions for the owner (all fifteen taken 2026-10-06)

1. **Language.** Decided 2026-10-06, against the recommendation: **R, reusing the ROSC_MTA2
   code as designed for that project** rather than writing new Python ("I'd rather use that than
   create new"). Consequence: phases 1 to 7 are re-planned for an R image (`xenium-r`, section 7)
   with the ROSC scripts wrapped as modules; the plugin needs a way to read the state of a Seurat
   object (an extractor in the R image, or h5ad as the interchange format written by each module);
   the per-organ defaults and parameter values stay. The re-plan is written before F4 and shown to
   the owner.
2. **Normalisation default.** Decided 2026-10-06: **LogArea is the default** (ROSC's log1p of
   counts per cell area × 100); library-size log1p stays a ranged option and the report shows both
   on one punch once.
3. **Clustering scope.** Decided 2026-10-06 as recommended: one object per organ across both
   slides, no integration, slide composition per cluster in the report; integration only if the
   report shows slide-driven clusters.
4. **DE method at n = 2 animals.** Decided 2026-10-06: **limma-voom**, the ROSC `mod6` pseudobulk
   method (limma 3.66, edgeR 4.8 for `filterByExpr`), chosen over edgeR quasi-likelihood and
   DESeq2 after the options were shown; pseudobulk per animal × cell type first, zone × cell type
   later; design `~ timepoint_h` with slide declared as batch and its omission flagged once.
5. **Cell-type vocabularies.** Decided 2026-10-06 as recommended: drafted by the agent per organ
   from the panel and the ROSC collapse maps, Cell Ontology ids required, `unknown` allowed, the
   owner approves.
6. **Niche vocabulary.** Decided 2026-10-06 as recommended: open per organ with the
   `proposed_label` escape hatch that always holds; closed in the next version from the override
   corpus.
7. **Contrasts and feasibility.** Decided 2026-10-06 as recommended: 24 vs 6, 48 vs 6, 48 vs 24
   with `min_n_per_group` 2, the slide confound accepted once with a written reason, punch-level
   analyses declared hypothesis generation.
8. **CellQuant, CellChat, Hotspot.** Decided 2026-10-06: out of the pilot, for a later session if
   reached. With R chosen they are feasible in the pilot's image (CellChat 2.2 and sdmTMB are in
   ROSC's pinned list), so a later pipeline costs no new environment.

Raised by the re-plan for R (section 5, 2026-10-06), to decide before F4:

12. **Reading the QC objects.** Decided 2026-10-06 after checking the archive: ROSC has tested
    conversion code in one direction only, Seurat to h5ad, `analysis/downstream/scripts/convert_to_h5ad.R`
    (anndataR `as_AnnData` with counts in `X`, the FOV coordinates into `obsm["spatial"]` with a
    refusal on any cell lacking one, ASCII sanitising of metadata and gene names); the pathway
    scripts' "re-export" is a CSV, and no R code anywhere in ROSC reads an h5ad (only Python does).
    So: `export-h5ad` copies that script's logic verbatim into `_rlib`; the merge step reads the
    QC h5ad with the same package's reader (`anndataR::read_h5ad`, as a Seurat object), which
    ROSC never exercised, and the F4 spike proves it with a round trip on one liver object
    (counts, `obs`, coordinates and `uns["stringency_qc"]` equal after read and write). No third
    QC chain.
13. **The squidpy step.** Decided 2026-10-06 as recommended: `neighborhood-enrichment` stays in
    Python through `export-h5ad` and `sc.export_mismatch`.
14. **Clustering resolutions.** Decided 2026-10-06 as recommended: 0.2, 0.4, 0.6, 0.8, 1.0 with
    0.4 the default; `resolutions` stays a parameter so the full sweep can be proposed on one organ
    if a report asks for it.
15. **The image build and the R environment manager.** Decided 2026-10-06 after reviewing the
    options (rworks.dev, "R environment managers": renv, rix, rv, uvr, ir; rig for R versions):
    **renv** inside a `rocker/r-ver:4.5` Docker image, restored from Posit Package Manager binaries
    and Bioconductor 3.22, the `renv.lock` committed, built on GHCR by the existing workflow. Fit
    with stringency: the engine's contract is a committed lockfile the local executor hashes
    (design 10.3 names `renv.lock` already) and a SIF digest in production, so any lockfile tool
    works and renv is the one the design, Bioconductor and the lab already know. rix (Nix) is the
    only option that is byte-reproducible without a network, but it is a second build system the
    machines do not have, and Seurat and Bioconductor through nixpkgs lag; not now. rv is the
    credible faster alternative if renv's restore makes the CI build slow (a `DECISIONS.md` line
    would add `rv.lock` to the hashed lockfiles). uvr and ir are too new; rig is unnecessary inside
    a rocker image, which pins R. No R exists on PROTSEQ outside the image, by design.
9. **Phase 0 timing against the pathology pass.** Decided 2026-10-06: there is no pathology
   pass; the histology file is final; the chain runs now.
10. **Exclusion file format** (`PLAN.md` 1.9). Decided 2026-10-06: the columns in section 4 item 4
    (`punch_id, excluded, reason, decided_by, review_id`), one row for every one of the 42 punches,
    so an absent punch is an error rather than a silent keep.
11. **The Proseg transcript floor and the gut label** (`PLAN.md` 2.2, 2.3). Decided 2026-10-06: the
    floor stays at 20 (the second chain uses the first chain's thresholds, so the per-punch
    comparison is clean); the gut punches are **small intestine** in every table and in the
    reference match (`organ: small_intestine` in the layout; the thresholds alias maps it to the
    ROSC `Sintest` entry, whose values equal `LgIntest`).

## 9. Risks

- The annotation judgment is where the method meets biology. Controls before the first real run
  (F7 before F8) are not optional: the outlier module's v1 rule looked fine until real data showed
  it held no judgment.
- n = 2 animals. Every test sits at the feasibility floor; the honest outcome of phase 6 may be
  "descriptive, with these candidates for a powered study", which the objective must say up front.
- The slide confound. Every time-point contrast is also a slide contrast; the report has to show
  slide composition beside every claim.
- Vocabulary drift across organs. One collapse map per organ, committed; the cross-organ step
  joins on the collapsed group only.
- Scope creep from ROSC. Seven modules and a cargo pipeline took months on BMESEQ; the pilot is
  clustering, annotation, niches, descriptives and one DE pass. CellChat and CellQuant wait.
- Runtime. ROSC's downstream was five hours per tissue at 800k cells, most of it eleven Louvain
  runs; here the resolutions are a short list, but spleen (two slides, about 1.4 M cells) is larger
  than any ROSC tissue, so F6 measures it first and the resources block caps it. `nhood_enrichment`
  with 1000 permutations and k-means over k 4 to 12 are the other two steps to cap.
- The R image. No ROSC container exists; the rebuild from 27 pins may not reproduce ROSC's
  behaviour exactly (transitive dependencies unpinned there). The F7 positive control, ROSC's own
  annotated liver and spleen through this method's `find-markers` and `annotate-clusters`, is also
  the check that the rebuilt environment agrees with the original on the markers it finds.
- Two languages. The hand-off is one module (`export-h5ad`) with one predicate on it
  (`sc.export_mismatch`); anndataR is already how ROSC moved objects to squidpy. Keep it that way:
  no module reads both an rds and an h5ad.
- Interactive ROSC steps. Annotation, zone naming and interpretation were an agent writing code
  into Quarto documents; here they are judgment modules with vocabularies and a report module. The
  ROSC label maps are evidence for the controls and the vocabularies, never applied as code.

## 10. Verification

- Method: `stringency lint .` clean; `tests/run_*.sh` green, one per pipeline, on synthetic
  fixtures; controls pass for every judgment module before its first real run.
- Plugin: `uv run pytest` at the workspace root; every predicate in `CASES`, with a Seurat-state
  fixture beside each anndata one; `extract_seurat.R` tested on a small `.rds` written by the
  image (the test needs the SIF, as `tests/run.sh` does).
- Image: `Rscript -e 'library(Seurat); library(limma); library(anndataR)'` inside the SIF prints
  the pinned versions; `renv.lock` committed; the SIF sha256 and OCI digest in both manifests.
- Data: each phase's deliveries under `/lab/projects/Lyons_CLP/<project>/deliver/`, with
  `coverage.md` naming every check that ran and did not, `methods.md` citing the upstream runs,
  and `summary.md` for the collaborator; `stringency board /lab/projects/Lyons_CLP --write` after
  every session; `PROGRESS.md` one entry per working day.
- Engine: nothing in this plan needs an engine change; anything found goes to `backlog.md` and a
  Lane A session.

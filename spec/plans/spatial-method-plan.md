# Lane F: the spatial method after QC, Lyons CLP as the pilot (2026-09-23)

Working note, not the spec. Successor to `app1-spatial-qc-plan.md` (Track 3, Lane C, closed
2026-09-23) and to the sessions of `spec/archive/app1-spatial-tma-plan.md` that the QC work did
not reach (7 to 12 and 14). Drafted for the owner's approval; the decisions it needs are in
section 8. Engine: `v0.2.4`, Lane A complete. Method: `stringency-xenium-method` `v0.3.3-rc1`,
`PLAN.md` there lists the open module items this plan absorbs.

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
| `upstream.clustering` | Seurat FindNeighbors, Louvain over resolutions 0 to 1, res 0.4 used, UMAP; seed 1984; ndim 35 (Spleen 40) | `xenium-cluster` pipeline, scanpy; leiden; the resolution is a ranged parameter |
| `upstream.annotation` (interactive) | FindAllMarkers (logfc 0.5) then a hand-written cluster to label map, written by an agent with the `/single-cell-annotation` skill and a person; `AssertAnnotationComplete` refuses NA or fallback labels | the first downstream judgment module: three replicates over a marker table, a closed vocabulary per organ with `unknown`, controls before the first real run |
| `upstream.timepoint_batch` (interactive) | per-cluster time-point and TMA composition tables, ISG enrichment, agent prose | code-only tables in the cluster report; no prose module |
| `downstream.h5ad` | rds to h5ad, `obsm["spatial"]` | not needed; the objects are h5ad from the start |
| `mod1_niche`, `mod1_zones` (interactive), `mod1_zone_export` | spatial kNN (k 25) composition per cell, k-means k 4 to 12 (nstart 30, seed 42), WSS elbow, hand-named zones, `zone_labels.csv` | `xenium-niches` pipeline: neighbourhood, k-means, a niche-labelling judgment, export |
| `mod2_cellquant` | 200 µm tiles, spatial NB GLMM (sdmTMB) per cell type, adjusted by zone; external R package `CellQuant` (not in the archive) | out of the pilot: R, an unarchived package, and n = 2 animals; composition is reported descriptively (section 5, phase 5) |
| `mod3_pathway`, `mod3_hotspot` | UCell scores over 7 innate gene sets, punch means, limma per contrast; Hotspot autocorrelation | `score-pathways` in Python (`scanpy.tl.score_genes` over the same gene sets), animal means, the DE module's test; Hotspot deferred |
| `mod4_neighborhoods` | squidpy `nhood_enrichment` per punch, 1000 permutations, seed 42, descriptive only | `neighborhood-enrichment`, descriptive, with the permutation null recorded so `spatial.no_permutation_null` is decidable |
| `mod5_cellchat` | spatial CellChat per arm, 100 bootstraps, filtered by the proximity mask | out of the pilot (R, the highest confabulation risk per the archived plan's session 10); a later pipeline if the owner wants it |
| `mod6_de` | per zone × cell type: FindMarkers (cell level) and pseudobulk limma-voom (punch level), concordance, boundary gradient | `pseudobulk-de`: pseudobulk per animal × cell type (or zone × cell type), the animal as the replication unit, contrasts between time points, no cell-level test as a claim |
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

## 4. Phase 0: the QC chain again, under 0.2.4 (owner's request, 2026-09-23)

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

If the pathology pass replacing `histology_include.csv` arrives before this phase, it goes in
here and the chain runs once; if after, the affected `qc2` projects re-open on the new hash and
the summary and outliers follow (inherited confirmation and rebind make that cheap).

Engine follow-up this phase may raise (Lane A, small): an input with `role: reference` should not
defeat inherited confirmation, since a reference table is not this design's data; today
`qc2_outliers_all` opens an ordinary hold because of it.

## 5. The downstream pipelines

One method repository, one Python image extended from `xenium-py` (section 7), one module per
step with per-organ defaults, each pipeline a project per organ chained through `derived_from`,
and a cross-organ step over `arity: many` where a table spans organs. Judgment enters exactly
where ROSC put a person and an agent (cell-type labels, zone names) and nowhere numeric.

### Phase 1: foundations (plugin and image, before any pipeline runs)

- Plugin `stringency-singlecell` 0.2: the `anndata` extractor's `domain` block reports what the
  downstream predicates need (archived plan session 4): normalised or not (an `uns` flag written
  by the normalise module, plus `X` dtype and max), HVG selected, PCA and neighbours present with
  their parameters, clustering present with resolution and seed, spatial graph present with its
  definition, cells per cluster per punch and per animal, labels present and which vocabulary.
  Object type `clustered_object_set`? No: one `anndata` per organ is the object from phase 2 on;
  the per-punch set ends at QC.
- Predicates (archived plan session 5, instantiated with must-fire and must-pass fixtures):
  `qc.filter_ordering` (cells filtered after normalisation; block), `sc.panel_hvg` (HVG selection
  on a targeted panel; flag), `spatial.neighborhood_undeclared` (a spatial statistic on an object
  whose graph definition is not in the state; block), `spatial.no_permutation_null` (an enrichment
  claim without a permutation artifact; block), `de.replication_unit` (a test whose unit is the
  cell or the punch when the design says animal; block), `de.covariate_omission` (`slide` in
  `design.batch` and absent from the formula; flag), `de.selection_bias` (a test between clusters
  derived from the same counts; flag, scoped so a declared-factor contrast does not fire),
  `test.multiple_comparison` (no correction; block), `sc.small_niche` (a niche under the floor;
  flag), `sc.unknown_fraction` (more than a policy share of cells labelled `unknown`; flag).
- Vocabularies: `cell_types_<organ>@1` for gut, spleen, lung, liver, each a Cell Ontology subset
  with ids plus `unknown`, `low_quality`, `contamination`; a collapse map to broad groups as the
  ROSC `cell_type_collapse_map.csv` does, committed with the vocabulary; `niches_<organ>@1` with
  a `proposed_label` escape hatch that always opens a hold (the archived plan's session 6
  question, decided in section 8). Typed operation schemas for `normalize`, `select_hvg`,
  `cluster`, `find_markers`, `annotate_clusters`, `spatial_neighborhood`, `characterise_niches`,
  `test_differential_expression`.
- Questions: `processed_object` (already), `cell_type_annotation`, `niche_characterisation`
  (already), `differential_expression` (already).
- Image `xenium-py` 0.2.0: adds `leidenalg`, `scikit-learn`, `statsmodels` and `pydeseq2` (or
  the owner's choice, section 8) pinned; the ROSC lock (`lock_rosc_downstream.yml`: scanpy
  1.11.5, squidpy 1.8.1, anndata 0.12.0, leidenalg 0.12.0) is the reference set.

### Phase 2: `xenium-cluster` (one project per organ, four)

| step | module | params (default, range) | notes |
|---|---|---|---|
| 01_merge | `merge-punches` | none | `qc_objects: {type: qc_object_set, arity: many}` bound `$inputs.qc_*` over the organ's two region deliveries; `punch_exclusions` applied here and recorded; one `anndata` with `punch_id`, `animal`, `timepoint_h`, `slide` on obs |
| 02_normalize | `normalize` | `method` logarea \| log_total (default per section 8), `target` 100 | writes `uns["stringency_norm"]`; `qc.filter_ordering` reads history |
| 03_features | `select-hvg` | `n_top` 2000 (500 to all), `flavor` seurat | `sc.panel_hvg` flags on a 5k panel; default may be "all genes" |
| 04_reduce_cluster | `reduce-cluster` | `n_pcs` 35 (20 to 50), `n_neighbors` 15 (10 to 30), `resolution` 0.4 (0.2 to 1.0), `seed` 1984 | `stochastic: true`, `seed_param: seed`; leiden; UMAP for the report only |
| 05_markers | `find-markers` | `method` wilcoxon, `logfc_min` 0.5, `min_pct` 0.1 | one table: cluster, gene, logfc, pct in, pct out, adjusted p |
| 06_report | `cluster-report` | none | cluster sizes per punch and animal, time-point and slide composition per cluster (the ROSC `timepoint_batch` tables as code), UMAP and spatial PNGs |

Deliverables: `clustered_object` (`anndata`), `markers`, `cluster_report`. Decision points:
`resolution`, `n_pcs`, `method`. Delivery skill `skills/xenium-cluster.yml`: the composition
tables and the report; analysis skill later (phase 7).

### Phase 3: `xenium-annotate` (one per organ; the first downstream judgment)

- `annotate-clusters` (judgment, `all_items`, 3 replicates, abstain required, ordinal
  confidence): evidence tables written by `pre.py`: `markers` (top 25 per cluster with logfc,
  pct in and out), `composition` (cells per cluster per punch, animal, time point, slide),
  `context` (organ, species, panel, expected populations and known absences from the collapse
  map). Vocabulary `cell_types_<organ>@1`. Prompt from the `/single-cell-annotation` skill's
  evidence rules (the skill itself is in the owner's Claude Code user skills, not the archive;
  its rules are transcribed into `prompt.md` and `guide.md` as the outlier module did). Output
  per cluster: label, ontology id, confidence, cited marker cells, rationale; `alternative_labels`
  allowed in the schema.
- Controls (archived plan session 8): positive, a ROSC tissue with the same organ (`Liver`,
  `Spleen`: `analysis/downstream/data/<T>_annotated.h5ad` in the archive) run through the same
  `pre.py`, agreement at the collapsed group level after the collapse map; negative, marker gene
  symbols shuffled across clusters, expecting `unknown` or abstain on every item.
- `apply-labels` (deterministic): consensus to `obs["cell_type"]`, the collapse map to
  `obs["cell_type_group"]`, QC labels flagged for exclusion from spatial statistics; the
  `annotated_object` deliverable and a label summary table.
- Holds: disagreement and abstention per cluster (item holds), then the flags. With the K7 fix
  the applied labels are the decided ones. `sc.unknown_fraction` flags a poorly resolved organ.

### Phase 4: `xenium-niches` (one per organ)

| step | module | params |
|---|---|---|
| 01_neighborhood | `spatial-neighborhood` | `k` 25 (10 to 50), per punch, generic coordinates; writes the graph definition to `uns` so `spatial.neighborhood_undeclared` is decidable |
| 02_niches | `cluster-niches` | composition vectors over `cell_type` (QC labels excluded), k-means `k` range 4 to 12, `nstart` 30, `seed` 42; outputs the WSS table, composition per niche, sizes per punch |
| 03_label | `label-niches` (judgment) | evidence: the composition table per niche cluster, the WSS table, the top cell types; vocabulary `niches_<organ>@1` plus `proposed_label`; three replicates; the chosen `k` is a decision the module proposes from the WSS second difference and the person approves (`param.agent_proposed`) |
| 04_export | `export-zones` | `zone`, `zone_broad` on obs; `zone_labels.csv`; `sc.small_niche` on any zone under 200 cells |

### Phase 5: composition and neighbourhoods, descriptive (one per organ)

- `compose-cells`: cells per cell type per punch and animal, per zone; proportions with the animal
  as the unit; with n = 2 the module tests nothing and says so in its table header (the CellQuant
  GLMM is out of the pilot).
- `neighborhood-enrichment`: squidpy `nhood_enrichment` per punch and per time point, 1000
  permutations, seed 42, z-scores and the permutation artifact; `co_occurrence` guarded (the ROSC
  index error); descriptive only, no p-values, the report says so.

### Phase 6: `xenium-de` (one per organ; contrasts declared in `objective.yml`)

- `pseudobulk-de`: pseudobulk per animal × cell type (and, when zones exist, per animal × zone ×
  cell type); contrasts `24 vs 6`, `48 vs 6`, `48 vs 24` on `timepoint_h`; method the owner's
  choice (section 8): `pydeseq2` in the Python image, or limma-voom in an R image; design
  `~ timepoint_h` with `slide` declared as batch and its omission flagged, since with two slides
  and three time points it is not estimable; BH; `min_cells_per_pseudobulk` 30,
  `min_animals_per_group` 2. `de.replication_unit`, `de.covariate_omission`,
  `test.multiple_comparison`, `obj.feasibility` all in scope.
- `score-pathways`: `scanpy.tl.score_genes` over the ROSC innate gene sets translated from
  `scripts/innate_pathway_genesets.R` (ifn_isg, tlr_prr, nfkb_cytokines, inflammasome, complement,
  chemokines, antigen_presentation, myeloid_activation) and the liver sets; animal means per cell
  type; the same contrasts through the DE module's test.
- Later, not the pilot: `flag-salient` (judgment, `considered_set: true`; the engine now fills the
  denominator) over the DE and pathway tables.

### Phase 7: reports, cross-organ, skills

- `report-spatial`: code-generated prose per pipeline (every numeral a table cell,
  `judg.numeric_claims_match` on report steps), the figures the tables feed.
- `xenium-cross-organ`: one step with `arity: many` over the four organs' label summaries, niche
  tables and DE tables, in the style of ROSC `cross_tissue`.
- Skills: `skills/<pipeline>.yml` (delivery) and `skills/<pipeline>.analyze.yml` (analysis) per
  pipeline, per `spec/method-skills.md`; the first spatial analysis skill is the Lane E
  acceptance test's target.

## 6. Sessions (half a day each, in order)

| # | session | delivers | gate to the next |
|---|---|---|---|
| F0 | this plan approved; owner decisions in section 8 recorded in `PLAN.md` | the plan | owner's yes |
| F1 | method `v0.4.0`: the five phase-0 changes, tests (`tests/run_summary.sh` with a glob input, `run_outliers.sh` with clipped bands), lint | tag pushed | green |
| F2 | phase 0 run, part 1: eight `qc2` projects through batch review; the summary through inherited confirmation | eight QC deliveries, one summary | `qc2_summary_all` delivered |
| F3 | phase 0 run, part 2: `qc2_outliers_all` with three fresh delegates; the owner's decisions; `punch_exclusions.csv`; the comparison note; the Lane E measurement row for a chained real run | the exclusion file | owner's file exists |
| F4 | plugin 0.2: extractor domain block, ten predicates with fixtures, vocabularies for four organs with collapse maps, typed operations; image `xenium-py` 0.2.0 | plugin tag, image in `MANIFEST.md` | plugin tests green; `lint` clean |
| F5 | `xenium-cluster` modules and pipeline; synthetic control (a two-punch fixture from the toy-like generator); run on liver (three punches) | clustered liver | delivered |
| F6 | `xenium-cluster` on spleen, lung, gut; the cluster reports read with the owner; resolution decisions recorded as `param.agent_proposed` acceptances | four clustered objects | delivered |
| F7 | `annotate-clusters` module: `pre.py`, prompt, schema, `guide.md` from the annotation skill's rules; controls from the ROSC liver and spleen objects | module lints; both controls pass | controls green |
| F8 | `xenium-annotate` on the four organs; the owner walks the item holds (review page or chat); `apply-labels` | four annotated objects, label summaries | delivered |
| F9 | `xenium-niches` modules; run on the four organs; the niche-label judgment | zones per organ | delivered |
| F10 | phase 5 descriptives; `xenium-de` with the owner's method choice; contrasts declared; feasibility at n = 2 read honestly | DE and pathway tables per organ | delivered |
| F11 | reports, cross-organ step, delivery and analysis skills; the first spatial analysis skill run by a lab member (Lane E's acceptance test) | the deliverable set for the collaborator | owner's reading |
| F12 | retrospective (archived plan session 14): override rate per judgment module, uncovered decision points, one delivered number reconstructed from `run.db` alone, the backlog for the next method version | note | |

F1 to F3 need the owner for holds and the exclusion file; F4 to F5 run without; F6 onward need
the owner at each judgment's holds. Two sessions can run in parallel from F4: the plugin (F4)
and the method image do not touch the phase-0 projects.

## 7. Environments

- `xenium-py` 0.2.0 (extend, do not fork): scanpy 1.11.5, squidpy 1.8.1, anndata 0.12.0,
  spatialdata 0.7.2 (present), plus leidenalg 0.12.0, scikit-learn, statsmodels, pydeseq2 if
  chosen. Pinned by the ROSC lock where the package is in it. Built by the existing GitHub
  workflow to GHCR, pulled by digest to `/data/lab/env/images/`, recorded in `MANIFEST.md`.
- An R image (`xenium-r`: R 4.5, Seurat 5.4, limma 3.66, edgeR 4.8, UCell 2.14, CellChat
  2.2.0.9001 from `setup/envs/r_package_versions.csv`) only if the owner chooses limma-voom or
  wants CellChat later. Not in the pilot's critical path.
- Every module runs under apptainer with `<step dir>/tmp` bound (K8 fixed); Nextflow is not
  involved downstream.

## 8. Decisions for the owner (before F1, unless marked)

1. **Language.** Python and scanpy throughout the pilot, R only for a later CellChat or
   limma-voom (recommended), or an R image now.
2. **Normalisation default.** ROSC's LogArea (log1p of counts per cell area × 100, its own open
   question) or library-size log1p (`target_sum` 100). Recommended: log_total as the default with
   logarea as a ranged option, and the report shows both on one punch once.
3. **Clustering scope.** One object per organ across both slides with no integration (ROSC's
   choice), or per slide. Recommended: per organ, no integration, slide composition per cluster in
   the report; integration only if the report shows slide-driven clusters.
4. **DE method at n = 2 animals.** `pydeseq2` in the Python image, or limma-voom in an R image;
   and whether zone × cell type pseudobulks are in the pilot or only cell type. Recommended:
   pydeseq2, cell type first.
5. **Cell-type vocabularies.** Per organ, Cell Ontology subset; who drafts them (the agent from
   the panel and the ROSC collapse maps, the owner approves) and whether ontology ids are required
   in the first version. Recommended: drafted by the agent, ids required, `unknown` allowed.
6. **Niche vocabulary.** Closed per organ, or open with `proposed_label` that always holds.
   Recommended: open with the escape hatch for the pilot; close it in the next version from the
   override corpus.
7. **Contrasts and feasibility.** The three time-point contrasts with `min_n_per_group` 2, the
   slide confound accepted with a written reason; punch-level analyses declared hypothesis
   generation. Recommended as stated.
8. **CellQuant, CellChat, Hotspot.** Out of the pilot (recommended), or any of them in.
9. **Phase 0 timing against the pathology pass.** Run the chain now on the current histology
   file, or wait for the pathologist.
10. **Exclusion file format** (`PLAN.md` 1.9): the columns in section 4 item 4, or the owner's.
11. **The Proseg transcript floor and the gut label** (`PLAN.md` 2.2, 2.3): decided before F1 so
    the `qc2` projects carry them.

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
- Runtime. ROSC's downstream was five hours per tissue at 800k cells; Lyons organs are an order
  of magnitude smaller, but `nhood_enrichment` with 1000 permutations and k-means over k 4 to 12
  are the two steps to cap (`--max_cpus 24`, memory caps as for Nextflow).

## 10. Verification

- Method: `stringency lint .` clean; `tests/run_*.sh` green, one per pipeline, on synthetic
  fixtures; controls pass for every judgment module before its first real run.
- Plugin: `uv run pytest` at the workspace root; every predicate in `CASES`.
- Data: each phase's deliveries under `/lab/projects/Lyons_CLP/<project>/deliver/`, with
  `coverage.md` naming every check that ran and did not, `methods.md` citing the upstream runs,
  and `summary.md` for the collaborator; `stringency board /lab/projects/Lyons_CLP --write` after
  every session; `PROGRESS.md` one entry per working day.
- Engine: nothing in this plan needs an engine change; anything found goes to `backlog.md` and a
  Lane A session.

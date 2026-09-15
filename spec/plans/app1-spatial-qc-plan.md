# Application 1, revised: Lyons CLP Xenium, QC first

Working note, not the spec. Roadmap Track 3 (`spec/plans/roadmap-2026-09.md`). Revises the opening of
`spec/archive/app1-spatial-tma-plan.md`, which predates both the dataset and the mature pipeline; its
sessions 1 to 3 become wrapping work, and its inventory (section 2) is now answerable. The owner's
direction, 2026-09-14: start with a QC tool; punch coordinates stay a manual step; XenSplitter is
still required; there is no IF image for this dataset, so module 7 is not needed.

## 1. The data

`/data/lab/raw/2026-08_xenium_lyons-clp/` on PROTSEQ: 115 GiB, checksummed, eight Xenium Onboard
Analysis 6.1.0 region bundles, two slides (`0076570`, `0076581`) by four tissues (Gut, Liver, Lung,
Spleen), FFPE, cassette TMA2, panel `mAtlas_v1` plus the custom add-on `mMulti_100g`. Each bundle
holds `cells.parquet`, `transcripts.parquet`, boundaries, `cell_feature_matrix.h5`, morphology
images and focus channels, the vendor `analysis/`, `metrics_summary.csv`, `experiment.xenium`,
`gene_panel.json` (5,175 targets). `metrics_summary.csv` `cassette_name` maps slide 0076581 to
TMA1 and 0076570 to TMA2; `experiment.xenium` records `analysis_sw_version xenium-4.0.2.2`. Example: slide 0076570 Lung, 209,365 cells, median 184 transcripts per cell.
Each region contains several punches (animals) whose boundaries are drawn by hand in Xenium
Explorer; the punch, not the region, is the unit the pipeline works on.

## 2. The existing pipeline

`/data-raid/Projects/ROSC_MTA2` on BMESEQ (surveyed 2026-09-14): 18 declared steps in
`analysis/orchestrate/parse_state.py`, each with dependencies and an interactive flag, gated by
`check_tissue.py` with input and output fingerprints and a verdict before a step can be marked
complete; four conda environments locked under `setup/envs/`; per-tissue script copies generated
from a Spleen template; hand-rolled logging of `sessionInfo()` and `pip freeze`; a defect register
with one commit per repaired defect; git tags. Built on the ROSC MTA dataset (Prime 5K, 6 TMAs, 11
tissues), not on Lyons CLP. Stages and their state:

| stage | script | state for wrapping |
|---|---|---|
| resegmentation (Nextflow, Docker, Proseg) | `resegmentation/*/main.nf` | frozen for MTA; required here for lung and gut (ROSC manifest: liver, spleen, FRT use `10xSeg`, all other tissues `Proseg`; Proseg runs on the whole region before the split) |
| punch coordinates | manual, Xenium Explorer | stays manual; becomes a declared input |
| punch splitting | `data_split/Xen_TMA_pipeline` (separate repo) | required; barcode order depends on `PYTHONHASHSEED`, documented in `setup/Claude/HANDOFF_XeniumSplitter.md`; must be fixed first |
| histology QC and manifest | Quarto, manual include column | becomes the QC module plus a reviewed flag |
| load, QC, PCA | `Xen_Seurat_LoadQCPCA.R`, thresholds in `tissue_configs.yaml` | the QC module's thresholds |
| clustering | `Xen_Seurat_ClusterAnnot.R` | later module |
| annotation (LLM plus human) | `run_annotation_<T>.R`, `/single-cell-annotation` skill | later, the first judgment module |
| downstream modules 1 to 6 | niches, composition, pathways, neighbourhoods, CellChat, DE | later |
| module 7 (IF, pyMFI, cargo) | | not needed for Lyons CLP |

Gaps against a stringency wrap: no containers for the analysis (conda plus absolute interpreter
paths); parameters split across `tissue_configs.yaml`, constants in scripts, and Nextflow params;
absolute project paths inside generated scripts; fingerprints are size and mtime, not content
hashes; partial seeding; eleven copies of each module script. The wrap replaces copies with one
parameterised module per step.

## 3. The plan

**S0, inventory note** (`notes/<date>-app1-inventory.md`): answer `spec/archive/app1-spatial-tma-plan.md`
section 2 from the survey and the owner: platform and format (above), what processing exists
(vendor `analysis/` only), experimental structure (slide, tissue, punch, animal, condition; the
punch layout per region from the coordinates), the biological replicate (owner to confirm),
controls, existing code (section 2), environments (`setup/envs/` locks to become images), storage
(PROTSEQ, 137 TB free). Record where `/data/lab/env` and the shared image directory meet
(`spec/plans/ux-two-audiences.md` section 7).

**S1, splitter determinism** (in `jrose835/Xen_TMA_pipeline`): make barcode order independent of
`PYTHONHASHSEED` per the handoff note; add a test that two runs produce byte-identical outputs;
tag. Without this the split module cannot satisfy the engine's reproducibility predicates and a
re-split can never be compared to a previous one.

**S2, plugin pieces** (`~/github/stringency-singlecell`): object types `xenium_bundle`
(`sc.xenium_bundle@1`: region id, slide, tissue, cell count, median transcripts and genes per
cell, panel ids, from `metrics_summary.csv`, `experiment.xenium`, `gene_panel.json`, and
`cells.parquet` summaries) and `punch_coordinates` (the hand-drawn file, hashed, `source: manual
annotation in Xenium Explorer`, extractor emits the punch ids and their region); operations
`split_punches`, `qc_cells`; question `processed_object` added to the three declared; design
schema per the app-1 session 1 questions (units observation cell, sample punch, animal; factors
timepoint_h (6, 24, 48), condition fixed CLP; batch slide; replication unit animal, n = 2; the
layout table supplies punch, animal, and time point after the split). Extractors stdlib or pyarrow
inside the Python image (E6 in `spec/plans/bulkrna-plan.md` applies).

**S3, method repo `stringency-spatial-method`**: module `resegment-proseg` (wraps the ROSC
Nextflow Proseg run with its Docker image converted to a SIF; inputs a region bundle; output a
resegmented bundle; applied to lung and gut, skipped for liver and spleen, so `xenium-qc` runs on
either bundle kind; about one extra session), module `split-punches` (wraps the fixed splitter;
inputs bundle and coordinates; params `min_transcripts 10`, `min_area 50`, `qv_threshold 25` with
ranges; outputs one bundle per punch plus `region_metrics`); module `qc-cells` (inputs a punch
bundle; params `min_nCount`, `min_nFeature`, `min_cellarea`, `max_cellarea` from
`tissue_configs.yaml` with per-tissue defaults and ranges, all decision points; outputs the
filtered object, `cellstats`, `qc_report`); pipeline `xenium-qc` answering `processed_object`,
all engine-run; predicates `sc.low_cell_count` (flag), `sc.qc_fail_fraction` (flag above a policy
band), `spatial.coords_missing` (block) with fixtures; one Python image pinned from
`lock_rosc_downstream.yml` (scanpy 1.11.5, squidpy 1.8.1, anndata 0.12.0, pyarrow). Deliverable:
QC'd per-punch objects with sidecars, so clustering and annotation projects chain through
`derived_from` (option 1 of `spec/plans/declarations-and-objectives.md`).

**S4, first runs**: `xenium-qc` on one Lyons CLP region from Claude Science through the operator
skill, then all eight; retrospective note. What it teaches feeds the remaining app-1 sessions:
clustering (parameterised from `Xen_Seurat_ClusterAnnot.R`), annotation as the first judgment
module (the `/single-cell-annotation` skill's evidence rules become the module's prompt and
schema; controls before the first real run, as the app-1 risks section says), niches, composition,
neighbourhoods, DE. Each wraps a `ROSC_MTA2` step as one module with declared params rather than
a per-tissue copy.

## 4. Decisions for the owner (answered 2026-09-15 unless marked open)

1. Replication unit and design for Lyons CLP (answered 2026-09-15 from the collaborator's plan,
   TMA maps, and email, filed at `/lab/projects/Lyons_CLP/`): six wild-type CLP animals, two per
   time point (6, 24, 48 h), no sham; four organs; gut, spleen, lung two punches per animal (a, b),
   liver one; TMA 1 = slide 0076581 (6-1, 6-2, 24-1), TMA 2 = slide 0076570 (24-2, 48-1, 48-2).
   **Replication unit: the animal, n = 2 per time point, punches nested within animal**; start
   there, judge power, then punch-level analysis as hypothesis generation, declared as such. The
   QC project declares **no contrasts**. Ids: animal `<tp>-<n>`, punch `<tp>-<n>-<Organ>[-A|B]`,
   slide as batch (partially confounded with time point). The transcribed layout
   `tma_layout.csv` is a declared manual input. Inventory: `notes/2026-09-15-1300-app1-inventory.md`.
2. Segmentation: **a mix following ROSC**: liver and spleen keep the vendor (XOA 6.1)
   segmentation; lung and gut are resegmented with Proseg. Confirmed against
   `setup/sample_manifest_complete_v2.csv` on BMESEQ (Liver, Spleen, FRT `10xSeg`; Brain, Heart,
   Kidney, LN, LgIntest, Lung, Sintest, Skin `Proseg`). The plan gains a `resegment-proseg` module
   ahead of `split-punches` (section 3).
3. Splitter: **fix in `jrose835/Xen_TMA_pipeline` first**, with a byte-identical determinism test
   and a tag; the ROSC MTA split outputs stay frozen and are never regenerated.
4. QC thresholds: **per-tissue defaults from `tissue_configs.yaml`** with shared ranges. The
   histology include or exclude decision is **a manual input file** like the coordinates: hashed,
   with a source line, read by `qc-cells`, which records the excluded punches.
5. Image location and build route: **as the bulk plan** (`bulkrna-plan.md` section 8 item 10):
   Dockerfile, GitHub Actions to GHCR, pulled by digest into `/data/lab/env/images/`.


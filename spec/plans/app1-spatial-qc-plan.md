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
`gene_panel.json`. Example: slide 0076570 Lung, 209,365 cells, median 184 transcripts per cell.
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
| resegmentation (Nextflow, Docker, Proseg) | `resegmentation/*/main.nf` | frozen for MTA; optional here |
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
tissue, condition; batch slide; replication unit to be confirmed). Extractors stdlib or pyarrow
inside the Python image (E6 in `spec/plans/bulkrna-plan.md` applies).

**S3, method repo `stringency-spatial-method`**: module `split-punches` (wraps the fixed splitter;
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

## 4. Decisions for the owner

1. The replication unit for Lyons CLP (animal, punch) and the factors and levels.
2. Whether resegmentation is wanted for this dataset or the vendor segmentation stands.
3. Confirm the splitter fix happens in its own repo first and that the MTA split outputs stay
   frozen.
4. Which QC thresholds are per tissue and which are shared; whether the histology include or
   exclude decision is a reviewed flag on `qc-cells` or a separate manual input like the
   coordinates.
5. Image location and build route, shared with the bulk plan.

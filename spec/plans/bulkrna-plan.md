# Bulk RNA-seq: plugin and method plan

Working note, not the spec. Roadmap Track 2 (`spec/plans/roadmap-2026-09.md`). Two new repositories:
`stringency-bulkrna` (the plugin) and `stringency-plasmidsaurusRNAseq-method` (the method). Decided by the
owner on 2026-09-14: counts first, alignment second; this is the first real plugin; it must be
runnable by a non-computational lab member through an analysis skill.

## 1. Data and reference

Dataset on PROTSEQ: `/data/lab/raw/2026-09_plasmidsaurus_darpa-united-sarna-comparison/`, 44
single-end UMI-bearing fastq.gz (names `RMLDH7_<n>_Group<g>.<rep>_D3_<Liver|Spleen>.fastq.gz`),
vendor BAMs, and vendor results: an expression matrix TSV (`_count` and `_cpm` columns, ENSMUSG
ids) for 32 of the 44 samples, MultiQC, mapping stats. Vendor tools: fastp 0.24.0, FastQC 0.12.1,
STAR 2.7.11b, samtools 1.21, UMIcollapse 1.1.0, featureCounts 2.1.1, MultiQC 1.33; reference build
not stated. Project area `/data/lab/projects/2026-09_darpa-united-sarna-comparison_jrrose5/` holds
an nf-core samplesheet (`fastq_2` empty, strandedness auto) and `metadata.csv` (group, replicate,
tissue, vendor_quantified). PROTSEQ has no Nextflow, Java, R, or conda on PATH; references at
`/data/lab/ref/refgenomes/` (mouse GRCm39 Ensembl 112 FASTA and GTF, no STAR or salmon index).

Data status (2026-09-15, from `vendor_results/RMLDH7_mapping-stats/*.tsv`): the run is shallow.
Spleen: 22 samples, median 0.9 M input reads (0.5 to 3.7 M), median 0.25 M reads after UMI
deduplication (0.10 M lowest). Liver: median 8.0 M input (3.2 to 19.4 M), median 2.5 M after
deduplication (1.0 M lowest). Deduplication keeps about 30 percent of mapped reads in every
sample. The owner's judgment: this delivery is development data; the experiment will probably be
re-sequenced, and the final project will run on that delivery. Everything below that touches the
DARPA files is therefore about exercising the pipeline on real inputs, and its first useful output
is the QC report that documents the depth problem.

Reference design for the downstream steps: `github.com/mkendzel/plasmid_bulk_rna` (R scripts:
import vendor zip, QC with thirteen warn/fail metrics, limma-voom with a cell-means design and a
contrast registry, Hallmark GSEA, figures). We take steps, metric names, and defaults from it, not
code; the DE method deviates (DESeq2, decided 2026-09-15, section 8). Its defaults: adjusted p 0.05, |log2FC| 1.5, filter 10 counts in 3 samples, QC warn/fail
pairs for input reads, mapping rate, dedup rate, total counts, top-100 fraction, detected genes,
genes at 10 counts, protein-coding fraction, rRNA fraction, mito fraction, within-condition
correlation, PCA centroid distance, median absolute M.

## 2. What the engine already gives, and what it lacks

Reusable: the `Plugin` protocol (`src/stringency/plugins.py`), the extractor envelope
(`src/stringency/extract.py`: the engine runs `<interpreter> <tool> <object> <design.json>` in the
module's env and parses JSON from stdout), `obj.feasibility` reading `counts_per_group` from any
object, policy `ranges` by profile (`Policy.range_for`), controls that run a module's ancestors on a
generated fixture, the Nextflow evidence parsers (`operator_exec/evidence/nextflow_trace.py`,
`nextflow_log.py`), the method-repo template, the toy method as the worked example, the singlecell
skeleton as the plugin shape, sidecar keys for `derived_from`.

Gaps, each an engine item (DECISIONS unless noted):

- E1. The job JSON a module receives is `{inputs, params, outputs, output_dir, seed}`. A DE module
  cannot learn the objective's contrasts or the design's factors; the toy hardcodes `A_vs_B`. Add
  `design` and `objective` to the job (additive; `steps.py`, ticket output, module-contract text).
- E2. `steps.py` never fills `OutputBundle.considered_set`; any module with `considered_set: true`
  would block on `judg.considered_set_missing`. Needed for the judgment module (section 5).
- E3. `ModuleManifest.confirm` is a field only; no step-level confirm hold exists. Use flag
  predicates for QC review.
- E4. Report modules are code-only; the optional harness prose call of design 3.6 is not built.
- E5. `envcheck` verifies one env against one container digest; nf-core runs dozens of containers,
  so `repro.env_unverified` flags on every Nextflow step, and `repro.env_unpinned` needs a SIF with
  a sha256 for the module's env even when Nextflow runs natively. Policy override with a written
  reason until an env may list `containers:`.
- E6. Plugin guidance to write down (plugin README and design 4.2): an extractor for a
  non-tabular object must not emit `fields.columns` (else `init.column_missing` blocks because the
  design column is not a matrix column); `init` runs extractors in the first pipeline step's env;
  a negative control must still yield items (zero items is not `null_output`).
- E7. `Plugin.defaults` (done 2026-09-14): publish `min_n_per_group: 3`.

## 3. Plugin `stringency-bulkrna`

Lives at `plugins/stringency-bulkrna` in the shared `stringency-plugins` repository, next to
`stringency-singlecell`, not in a repo of its own (decided 2026-09-17; roadmap Lane D item 2).
It is installed with `--plugin <url>@<tag>#subdirectory=plugins/stringency-bulkrna` and tested
from the workspace root. Layout mirrors `stringency-singlecell`: `pyproject.toml` (entry point `bulkrna =
"stringency_bulkrna:PLUGIN"`), `src/stringency_bulkrna/{__init__,schemas,defaults,predicates,
phrasing}.py`, `vocabularies/gene_categories.yml`, `tools/` (stdlib-only Python so extractors run
in the engine venv for tests and inside the R image in production), `tests/` with an in-memory
`GateContext` builder, `spec/bulkrna-design.md` for the session-0 decisions, and the analysis skill
data file.

Object types and extractors:

| type | file | id | envelope |
|---|---|---|---|
| `counts_matrix` | TSV, `gene_id` first; sample columns plain or vendor `_count` (ignore `_cpm`); optional `gene_name`, `gene_biotype` | `bulk.counts_matrix@1` | genes as `n_obs`, `fields: {samples, annotation_columns}` (no `columns`), `domain: {sample_ids, library_sizes, library_size_min/median/max, zero_fraction, gene_id_prefixes, has_gene_name}` |
| `samplesheet` | CSV, one row per sample, `sample` required | `bulk.samplesheet@1` | `fields.columns` with dtype, unique count, levels; `counts_per_group` computed as `stringency_toy/tools/extract_frame.py` does; this is the object `init.column_missing` and `obj.feasibility` read |
| `qc_metrics` | TSV, one row per sample, metric columns plus `<metric>_status` and inferred tissue and sex | `bulk.qc_metrics@1` | `domain: {metrics: {name: {min, median, max}}, n_warn, n_fail, warn, fail, inconsistent}` |
| `nf_samplesheet` | nf-core/rnaseq samplesheet | `bulk.nf_samplesheet@1` | `fields.columns`, `counts_per_group`, `domain: {n_fastq, paired, strandedness_values, missing_files}` |

Fastq files are plain `fastq` items in `inputs.yml`, hashed, no extractor.

Design schema: the toy schema plus `organism: {enum: [mouse, human]}` (required), optional
`animal` unit, and the convention `condition = <group>.<tissue>` so contrasts stay engine triples
and `obj.feasibility` counts per cell of the cross without plugin code.

Questions: `differential_expression`, `processed_counts`. Operations: `import_counts`,
`compute_qc`, `filter_features`, `test_differential_expression`, `gene_set_enrichment`,
`flag_salient_genes`, `report`, `align_quantify`.

Predicates (each with must-fire and must-pass fixtures, the `CASES` pattern of `tests/test_gate.py`):

| id | phase | scope | default | fires when |
|---|---|---|---|---|
| `bulk.sample_mismatch` | pre, post | import, filter | block | a matrix sample is absent from the sheet or two outputs disagree |
| `bulk.samples_unquantified` | post | import | flag | sheet rows with no matrix column (the 12 DARPA samples); accepted once |
| `bulk.gene_id_mismatch` | post | import | flag | dominant gene id prefix disagrees with `organism` |
| `bulk.low_library_size` | post | import, qc | flag | any library below `policy.range_for("bulk.min_library_size")` |
| `bulk.qc_warn` | post | qc | flag | any warn or fail; evidence is the map |
| `bulk.qc_fail_retained` | pre | de | block | a failed sample is still in the current sheet |
| `bulk.metadata_inconsistent` | post | qc | flag | tissue-marker score or sex genes disagree with the sheet |
| `bulk.low_replicates` | pre | de | flag | a contrast level has fewer replication units than the policy band |
| `de.covariate_omission` | pre | de | flag | `design.batch` non-empty and not among `covariates` |
| `test.multiple_comparison` | pre | de | block | `correction == none` |
| `bulk.filter_after_test` | pre | filter | flag | a DE step is in history |

Policy ranges: `bulk.min_library_size` strict 5e6, standard 2.5e6, wide 1e6; `bulk.min_replicates`
4, 3, 2. `describe` and `echo` in the register of design 12.3; the echo for a biologist reads, for
example: "32 samples from 16 animals; 2 tissues and 4 treatment groups giving 8 conditions of 4
animals each; the biological replicate is the animal; no batch variable is declared. The counts
are the vendor matrix: 32 samples, N genes, library sizes A to B million. The question is
differential expression for 6 contrasts, ..., with at least 3 animals per condition."

## 4. Method `stringency-plasmidsaurusRNAseq-method`, pipeline `bulk-de`

All steps `kind: deterministic`, `runner: engine`, `env: bulkrna-r`, one R script each reading
the job JSON with jsonlite.

| step | module | inputs | params (default, range) | decision points | outputs |
|---|---|---|---|---|---|
| 01_import | import-counts | counts, samples | id_column fixed | none | counts (canonical), samples (matrix order), genes (id, name, biotype) |
| 02_qc | qc-metrics | counts, samples, genes, alignment_stats | the 13 warn/fail pairs with ranges; detection_min 10; complexity_top_n 100; pca_n_feats 500; pca_n_pcs 5; mito prefix by organism | the fail thresholds | qc_metrics, qc_report (md), figures |
| 03_filter | filter-features | counts, samples, qc_metrics | minimal prefilter ahead of DESeq2's independent filtering: min_count 10 [5, 20] summed over min_samples = smallest group size [2, 6]; drop_qc_fail true; exclude_samples fixed [] | min_count, drop_qc_fail | counts, samples, filter_summary |
| 04_de | de-deseq2 | counts, samples, genes | design `~ condition` (median-of-ratios size factors, Wald test); covariates fixed []; correction BH [BH, bonferroni, none]; p_cut 0.05 [0.01, 0.1]; lfc_cut 1.0 [0, 2]; block_by_animal false; DESeq2 choices (fit_type, lfc_shrink, cooks_cutoff, independent_filtering, alpha) settled in session 0 | all but design | de_tables (long), de_summary, de_significant, design_matrix, assumption_checks |
| 05_gsea | gsea-fgsea | de_tables, genes | gene_sets hallmark [hallmark, hallmark_kegg]; rank_stat t [t, signed_logp]; min_size 15; max_size 500; seed (stochastic) | rank_stat | gsea_tables |
| 06_report | de-report (kind report) | de_summary, de_tables, gsea_tables, qc_metrics, filter_summary | none | report (md, every numeral a table cell), volcano per contrast, PCA, heatmap, GSEA bars |

Contrasts and factors reach `04_de` through the job's `objective` and `design` (E1). Gene sets are
committed GMT files under `resources/genesets/` named with the MSigDB version; symbols come from the
`genes` table so no annotation database is needed unless KEGG is wanted.

Judgment module (v0.2, session 9): `categorise-salient-genes`, `operation: flag_salient_genes`,
items from `de_significant`, evidence `candidates` and `context`, 3 replicates, `considered_set:
true` (E2), vocabulary `gene_categories` (interferon response, inflammatory cytokine or chemokine,
antigen presentation, complement and acute phase, translation and ribosome, stress and apoptosis,
cell cycle, tissue metabolic, other known, abstain). Controls: negative `scramble_symbols` (symbols
replaced by opaque ids, statistics kept; every item should abstain) and positive known genes
(Ifit1, Isg15, Oasl1, Cxcl10, Saa1, ribosomal genes; agreement at least 0.8, abstain at most 0.2).
Why judgment here and nowhere else: gene categorisation needs knowledge, not arithmetic, and has a
clean negative control. Metadata sanity (tissue markers, sex genes) is code in `qc-metrics`. GSEA
prose interpretation waits for E4.

Pipeline `bulk-align` (Project B): `answers: [processed_counts]`, one step `01_align` on module
`nfcore-rnaseq`, `runner: operator`, then optionally `02_import` and `02_qc` so delivered counts are
already QC'd.

`policy.yml`: from the toy's, with the two `bulk.*` ranges; `bulk.samples_unquantified` and
`bulk.filter_after_test` logged under exploratory; a written override for `repro.env_unverified`
on the Nextflow module until E5.

Environments: `bulkrna-r-0.1.0.sif` from `bioconductor/bioconductor_docker:RELEASE_3_21` (R 4.5)
with DESeq2, apeglm, fgsea, jsonlite, data.table, ggplot2, ggrepel, pheatmap, matrixStats, rmarkdown,
and `python3` for the extractors; `renv.lock` generated inside the image for the local executor
digest. Build route (decided 2026-09-15): a Dockerfile in the method repo built by GitHub Actions to GHCR
and pulled by digest, no root on either workstation. Path: `/data/lab/env/images/` with a
`MANIFEST.md` (`spec/plans/ux-two-audiences.md` section 7), created when the first image lands. Project B adds a pinned Nextflow image to satisfy `repro.env_unpinned`.

Fixtures: `controls/fixtures/make_synthetic.py` (stdlib, fixed seed) generates 2 tissues x 3
groups x 4 animals, 2000 genes, 100 planted DE genes with known log2 fold changes, negative
binomial counts; outputs committed and hashed; shared by plugin tests, method tests, and controls.

## 5. Project A and Project B on the DARPA data

Both projects on the RMLDH7 delivery are development projects (section 1, data status). They run
under the `exploratory` profile so that the expected blocks (`bulk.qc_fail_retained` on shallow
spleen samples) become flags with recorded reasons, and their `deliver/` output is labelled
development in the objective's title and in `methods.md`. Project A is run in two stages: first
`--until 02_qc` and deliver `qc_report`, which is the evidence for the re-sequencing request
(`bulk.low_library_size` is expected to fire on every spleen sample even at the wide band of
1e6); then the full pipeline, whose DE tables are for pipeline verification, not for the project.
When the re-sequenced delivery lands (deposited with the raw-deposit skill), the final project is
declared from the same method tag under `standard`, and the development projects stay in the
trace as history.

Project A sample sheet from `metadata.csv`: `sample` (the vendor column stem), `animal`, `group`,
`replicate`, `tissue`, `condition`, `vendor_quantified`; all 44 rows, with
`bulk.samples_unquantified` accepted once (the more honest trace). Declarations: inputs counts
(vendor matrix), samples (sheet), vendor_stats (mapping statistics); design organism mouse, units
observation sample, sample sample, animal animal, factors group, tissue, condition, replication
unit animal; objective differential_expression with all pairwise contrasts within tissue (ten per
tissue, no reference group, no cross-tissue contrasts), `min_n_per_group: 3`, deliverables
`de_tables, de_summary, gsea_tables, qc_report, report`. The project README's rule that vendor
outputs are reference only gets a line naming Project A as the deliberate exception, superseded by
Project B and A'. Project A' later binds `counts` to Project B's delivered matrix through `derived_from`.

Project B module `nfcore-rnaseq`: `kind: deterministic`, `operation: align_quantify`, `runner:
operator`, `env: nextflow`, inputs samplesheet (`nf_samplesheet`), fasta, gtf; params named as
nf-core params so `nextflow_log` evidence matches the Action: `aligner star_salmon [star_salmon,
star_rsem]`, `with_umi true` (fixed), `umitools_extract_method`, `umitools_bc_pattern`,
`umi_dedup_tool umicollapse [umitools, umicollapse]`, `strandedness auto` (fixed), `revision`
(fixed), `save_reference true`. The UMI is already in the read name (14 nt after an underscore in
the fastq header, checked 2026-09-15), so the route is `--with_umi --skip_umi_extract
--umitools_umi_separator _` rather than extraction; `umitools_extract_method` and
`umitools_bc_pattern` drop out. Evidence: `nextflow_trace` (the config adds the `container` field
and `trace.overwrite`), `nextflow_log`, `job_log`. `pre.sh` is the canonical command, so
`exec.script_drift` has a script to hash, followed by a reshape into a canonical `counts_matrix`
and `samples`. PROTSEQ needs Java 17 or later, Nextflow, `NXF_APPTAINER_CACHEDIR`, a smoke run with
the test profile, the STAR index built from GRCm39 Ensembl 112 by the pipeline. Quantification
differs from the vendor (salmon versus featureCounts), so expect a comparison step, not identity.

## 6. Tests

Plugin: `uv run pytest`, no network, no R: entry point loads; extractors run by subprocess on the
fixtures and the envelopes are checked (`counts_matrix` has no `fields.columns`; `samplesheet` has
the right `counts_per_group`); `test_predicates.py` mirrors `tests/test_gate.py` with a `CASES`
list and a test that every plugin predicate has a case. Method: `stringency lint .` clean; `declare
--check` and `init --executor local` against synthetic declarations; a marked apptainer test runs
`bulk-de` end to end on the synthetic data with the mock harness and asserts the planted genes are
recovered above a floor and the report passes `judg.numeric_claims_match`. Engine: tests for E1
and E2 on the toy.

## 7. Sessions (about half a day each)

0 decisions (section 8), `spec/bulkrna-design.md`, DECISIONS for E1 and E2; 1 plugin skeleton,
two extractors, synthetic data; 2 schemas, defaults, phrasing; 3 engine E1; 4 method skeleton,
image, manifest, policy, import and qc modules run by hand in the image; 5 filter, DE, GSEA,
pipeline lints; 6 predicates with fixtures, the qc extractor, policy ranges; 7 report, end to end
on synthetic data on both machines, tag plugin and method `v0.1.0`; 8 Project A (development) on the DARPA data
through the declare skill, QC report delivered first, retrospective; 9 judgment module, E2, controls, method `v0.2.0`; 10
the analysis skill `stringency-analyze-bulk-rnaseq`, a run by a non-computational member; 11
PROTSEQ Nextflow install and the `nfcore-rnaseq` module; 12 Project B on the 44 fastq (the spleen files, 24 to 71 MB each, are the smoke-test subset),
Project A' chained, comparison note. Final projects on the re-sequenced delivery when it arrives:
declare, run, deliver; no new sessions unless the run finds something.

Status 2026-09-22: no session has run. The method repo holds the template seed only (`88bc939`)
and `stringency-plugins/plugins/` has no `stringency-bulkrna`. E1 and E2 (section 2) are still
open on the engine (roadmap Lane A step 2). Java 21 and Nextflow 24.10.0 are installed under
`/lab/env/nextflow` (roadmap Lane D item 6, done 2026-09-17), so session 11 is the module alone;
the Lane C operator-run lessons for long Nextflow steps apply to it (roadmap Lane B status).

## 8. Decisions for session 0 (answered by the owner 2026-09-15 unless marked open)

1. DE method: **DESeq2**, not limma-voom; the owner knows it better. Module `de-deseq2`, design
   `~ condition`, median-of-ratios size factors, Wald test. Which DESeq2 choices are adjustable
   params (`fit_type`, `lfc_shrink`, `cooks_cutoff`, `independent_filtering`, `alpha`,
   `block_by_animal`) and their defaults: **open, to be discussed in session 0 while designing**.
2. Contrasts: `condition = group.tissue` stands. **All pairwise contrasts within tissue** (ten
   per tissue for groups 1, 3, 5, 7, 11); no reference group; no cross-tissue or interaction
   contrasts in v0.1; `block_by_animal` false by default.
3. Thresholds: adjusted p **0.05** [0.01, 0.1] and |log2FC| **1.0** [0, 2]. The reference design's
   1.5 stays within range and is named as a non-default when used.
4. Gene filter: **minimal prefilter** (genes with fewer than `min_count` 10 counts summed over the
   smallest group's number of samples are dropped), with DESeq2's independent filtering kept.
   `filterByExpr` is not used; edgeR leaves the image.
5. Gene ids: ENSMUSG ids from the matrix; **symbols and biotypes from the GRCm39 Ensembl 112 GTF in
   `/lab/ref`** for both projects. Ids absent from the GTF keep symbol NA and are counted in a flag.
   Duplicate symbols for GSEA: keep the id with the highest mean count. The vendor's release stays
   unknown.
6. Minimum replicates: default **3**; `bulk.low_replicates` bands **4 / 3 / 2** (strict, standard,
   exploratory), a flag. Note: the vendor quantified 3, 2, 2, 1, 2 spleen samples per group, so
   spleen contrasts on vendor counts hold for review under standard.
7. Gene sets: **Hallmark only** in v0.1, committed GMTs named with the MSigDB version.
8. QC: **adopt the thirteen metrics and their warn/fail values verbatim** as params. Vendor mapping
   statistics: `vendor_results/RMLDH7-mapping-stats-reads.csv` (per run: unique, multi, unmapped)
   and `vendor_results/RMLDH7_mapping-stats/<sample>.tsv` (eleven `Metric\tValue` rows: input,
   mapped, unmapped, unique, multi, mapping rate, and the dedup counterparts).
9. Judgment: **keep `categorise-salient-genes` in v0.2** as described in section 4.
10. Environment: **Dockerfile in the method repo, GitHub Actions to GHCR, pulled by digest into
    `/data/lab/env/images/`**; Bioconductor 3.21 on R 4.5 with DESeq2 and apeglm.
11. Project B: the UMI is in the read name (section 5), recorded now. **nf-core/rnaseq version and
    aligner are decided in session 11**; default STAR + salmon unless the vendor comparison needs
    featureCounts.
12. Roles for members' runs: **owner and reviewer are the same person, the member running the
    pipeline**; no separate-person review yet. Design line 75 allows this ("may equal owner; the
    record is the point, not the separation"). `relayed_review` stays true under standard.
13. Samples for Project A: **all 44 declared**, vendor counts for the 32, `bulk.samples_unquantified`
    accepted once so the twelve missing spleen samples are in the trace.


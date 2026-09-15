# stringency: roadmap after the Phase A exit (2026-09-14)

Working note, not the spec. Approved by the owner on 2026-09-14. Detail per track: `spec/plans/ux-two-audiences.md`
(Track 1), `spec/plans/bulkrna-plan.md` (Track 2), `spec/plans/app1-spatial-qc-plan.md` (Track 3). Track 0 was done the
same day; see `notes/2026-09-14-1600-track0-and-roadmap.md`.

## Context

Phase A is complete on both machines (2026-09-14). Three things now pull on the project at once:

1. **The backlog** (`spec/archive/improvements.md` section I, plus `v0.1.0`, public repo, singlecell push).
2. **Usability.** The owner's judgment: "much of the json sent by the AI operator is unintelligible to
   the human running it, so all these approval-gated calls will turn people off"; holds need a
   non-terminal approval route; the machinery should sit behind per-analysis skills
   (`/analyze_bulkRNAseq`, `/analyze_spatial`); non-computational lab members must run the bulk
   pipeline alone. The spec is silent on all of this and assumes a technical operator, so part of
   this is new design, not execution.
3. **Real data has landed on PROTSEQ.** Bulk RNA-seq: 44 UMI fastqs + vendor counts (32 of 44
   quantified) at `/data/lab/raw/2026-09_plasmidsaurus_darpa-united-sarna-comparison/`; shallow
   (spleen median 0.9 M reads, liver 8 M; 2026-09-15), so this delivery is development data and
   the experiment will probably be re-sequenced. Spatial:
   Xenium XOA 6.1, 2 slides x 4 tissues (115 GiB) at `/data/lab/raw/2026-08_xenium_lyons-clp/`;
   the mature spatial pipeline is `ROSC_MTA2` on BMESEQ (18 declared steps, gated state, conda,
   per-tissue script copies, built on a different dataset).

Decisions the owner has made: hold approval **both** relayed-via-chat and a review page; bulk
**counts first, alignment second**; order **bulk plugin first**, UX alongside, spatial after,
starting spatial with a **QC tool** (punch coordinates stay a manual input; XenSplitter is the
first module; no IF/pyMFI for Lyons CLP).

One measured fact drives the UX work: the 26 approval cards for a five-step toy come from the
loop's shape (one command per file write, `next --json` after each ticket, three heredocs per
dispatch), not from the gates. Two holds needed a person; the other 24 were mechanics.

## Principles that survive (recorded in the new design note)

- 14.2: the hold message suggests no workaround. Skills may translate a hold into a sentence but may
  not add options the engine did not list.
- The declare rule: the skill translates, it does not decide. The review rule: the display states
  what fired and what each verdict does, it does not recommend.
- Commandment 6: every number the person reads comes from an engine output. Agent prose that
  interprets results is labelled as such and never enters `deliver/`.
- Hiding mechanics from the chat never hides them from the trace.

## Track 0: cleanup (done 2026-09-14 except the items that need the owner)

- Section I code items: I6 `lint` accepts `path@tag`; I8 `run` prints `completed_steps` (human
  and `--json`); I10 echo grammar; I7 `render_brief.py --image` and `--declare`.
- Skill text I1 to I5 in `integrations/claude-science/stringency-declare/SKILL.md`.
- I3 engine: `Plugin` gains optional `defaults`, surfaced by `plugins list --json`.
- Tag `v0.1.0`, make the repo public, reinstall from the tag on BMESEQ (stale) and PROTSEQ,
  push `~/github/stringency-singlecell`, give `stringency-toy-method` a remote.
- Commit the 51 uncommitted files in `ROSC_MTA2` (owner) before any wrapping work touches it.

## Track 1: UX, two audiences (runs alongside Track 2)

### 1a. Design note and amendments [approved 2026-09-15, applied to the design]

New working note `spec/plans/ux-two-audiences.md` (like `spec/archive/review-ux.md`). Amendment texts for:

| section | change |
|---|---|
| 7.5 | third `via` value `web`; honest trust statement ("the speed bump is the account, not the form"); strict accepts `web` like `tty`; relayed rows require a session reference |
| 10.4 | two kinds of skill: the two engine skills (operator's reference, engine repo) and one analysis skill per pipeline (method repo, rendered from a template) |
| 12.1 | `deliver` also writes `summary.md`, engine-rendered from the trace for a lay reader |
| 14.1 | `review --serve [--port] [--bind] [--project]... [--projects <dir>]`; `run --responses <file|->`, `run --deliver` (flags, no new verb) |
| 17 | review-page row removed once built |

### 1b. Engine batch [DECISIONS-level]

Files: `src/stringency/runloop.py`, `cli/verb_run.py`, `cli/verb_status.py`,
`operator_exec/tickets.py`, `review.py`, `pipelines.py`, `store/schema.sql` + migration.

- `job_spec.operator_line`: exec, evidence, submit joined by the engine; the operator runs one string.
- `run --responses <file|->`: writes `resp_N.json` files from one JSON document, then continues;
  refuses (16) if the step is not dispatching or the count differs from `manifest.json`.
- `run --deliver`: deliver in the same invocation on completion.
- `pipeline.yml` `steps[].title`; `run --json` and `status --json` gain `plain` (engine-rendered
  progress sentence from titles and statuses) and `completed_steps`. Golden test per `Next.kind`.
- `--attest` refuses (16) without `STRINGENCY_SESSION_REF`; `reviews.operator_harness` column
  (migration 0004, additive).
- `deliver/<run>/summary.md` via `src/stringency/summary.py`: what was analyzed (echo), what ran
  (titles, non-default params), what was checked and decided (from coverage data, reviewer, via,
  reason quoted), judgments, what you received, not checked. Golden `tests/golden/summary_toy_engine.md`.
- Toy method 0.1.2: titles, all-engine variant, image path per section 1e.

### 1c. Skill text

- `stringency-operator/SKILL.md`: drop `next --json` after 21; one operator line; `run --responses`;
  `intent=` is one plain sentence per moment (fixed table); the hold protocol below; never start
  `review --serve`.
- Hold protocol (relayed path), verbatim in operator skill and the analysis template: read
  `review --hold <id> --json`; say where it paused and the engine's question; quote reason and
  evidence verbatim; list every `verdicts[]` entry with its effect, in the engine's order, adding
  nothing; ask "which do you choose, and why"; accept only a listed verdict word plus a reason;
  run one `review --verdict ... --reason "<their words>" --attest` with the session ref set;
  report the engine's reply; on exit 16 name the two engine-allowed routes.
- `templates/brief.md.j2`, `agent-context.md.j2`, `README.md`, `new-project.md` updated to match.

### 1d. Analysis skills as entry points

- `integrations/claude-science/templates/analyze-skill.md.j2` (domain-agnostic person-facing
  script + compact mechanics appendix that defers to the operator skill on conflict) and
  `render_skill.py` (or `render_brief.py --skill`), input `skills/<pipeline>.yml` in the method
  repo (pipeline, method@tag, plugin, question, title, phrasings, step titles, deliverable
  sentences, lay-phrased asks, defaults to name aloud). Output committed to the method repo at
  `skills/stringency-analyze-<pipeline>/SKILL.md`; published per instance with the existing cell.
- Wording rules (testable against a transcript): sentences only, no command/JSON/exit code/id/path
  unless asked; every number quoted from an engine output; ask the `asks` one at a time; show the
  echo-back in full and wait for yes; progress only from `completed_steps`/`plain`; hold protocol
  exactly; three-part report from `summary.md`; interpretation labelled as the assistant's reading.
- Description routes casual phrasing; negatives excluded. `skills/<pipeline>.phrasings.yml`: 20
  positives, 10 negatives, run by hand per revision until an eval tool is confirmed.
- First instance on the toy: `stringency-analyze-toy-compare`, before any real plugin.

### 1e. Review page (A5) [after 1a approval; parallel with 1d]

`src/stringency/review_serve.py`: stdlib `ThreadingHTTPServer`, jinja2 string templates, inline
CSS, no JavaScript. `GET /?t=<token>` lists open holds across `--projects`; `GET/POST
/p/<i>/hold/<id>` renders `review_render.render(...)` and a form (verdict radios from
`verdicts_for`, reason, replicate, correction from the vocabulary) and calls
`record_review(..., via_override="web")`. Identity = OS user of the server process; random token
per start; loopback default. Started by the reviewer under their own account through a tunnel via
`scripts/review-page.sh <alias> [<projects dir>]`; never by the agent, never one instance for
others. Tests in `tests/test_review_serve.py` (list, 403 without token, accept records `via=web`,
stranger 403 writes nothing, replicate accept, bad override re-renders, strict accepts web, no
`<script`).

### 1f. Multi-user PROTSEQ deployment

Shared engine at `/data/lab/env/stringency/` (`umask 002; scripts/install.sh --prefix ...`);
images at `/data/lab/env/images/<name>-<version>.sif` with `MANIFEST.md`; per-user PATH line;
one Claude Science instance per person (identity per AD user, so roles and `via` checks need no
engine change); `hosts/protseq-lab.md`, `onboarding.md`, `publish-skills.md`. Method manifests
name the shared image path; BMESEQ gets the same path by symlink.

### 1g. Measurements (before/after, into `spec/plans/backlog.md` (measurements))

Cards per project, person turns to result, time to first delivered file, count of unrequested
commands/JSON/ids shown, holds and `via`, operator misreports vs trace. Two session tests on
PROTSEQ first: do delegate downloads under a data root raise cards; do standing grants cover
`call_command`. Target for an all-engine five-step run with one dispatch: 26 -> 8 or 9 cards.

## Track 2: bulk RNA-seq plugin and method (first real plugin)

Two new repos: `~/github/stringency-bulkrna` (plugin, modelled on `stringency-singlecell` and
`plugins/stringency-toy`) and `~/github/stringency-bulkrna-method` (from `templates/method-repo/`).

### Engine prerequisites found by reading the code

- E1: job JSON gains `design` and `objective` (a DE module cannot learn contrasts today; the toy
  hardcodes `A_vs_B`). Additive; `steps.py`, ticket output, module-contract text.
- E2: `steps.py` never fills `OutputBundle.considered_set`; needed before any module sets
  `considered_set: true` (session 9).
- E6: plugin guidance: a matrix extractor must not emit `fields.columns` (else
  `init.column_missing` blocks on design columns); `init` runs extractors in the first step's env;
  a negative control must still yield items.
- E5 (Project B): `envcheck` verifies one container; nf-core runs dozens. Policy override with a
  reason until an env may list `containers:`.

### Plugin (`stringency_bulkrna`)

- Object types: `counts_matrix` (`bulk.counts_matrix@1`, emits samples, library sizes, gene-id
  prefixes), `samplesheet` (`bulk.samplesheet@1`, the object carrying design columns and
  `counts_per_group`, computed as `stringency_toy/tools/extract_frame.py` does), `qc_metrics`,
  `nf_samplesheet` (Project B). Extractors stdlib-only so they run in the engine venv for tests and
  inside the R image in production.
- Design schema: toy schema + `organism`, optional `animal` unit; convention `condition =
  <group>.<tissue>` so contrasts stay engine triples and `obj.feasibility` works unchanged.
- Questions: `differential_expression`, `processed_counts`. Operations: `import_counts`,
  `compute_qc`, `filter_features`, `test_differential_expression`, `gene_set_enrichment`,
  `flag_salient_genes`, `report`, `align_quantify`.
- Predicates (each with must-fire and must-pass fixtures, `CASES` pattern from `tests/test_gate.py`):
  `bulk.sample_mismatch` (block), `bulk.samples_unquantified` (flag; the 12 DARPA samples),
  `bulk.gene_id_mismatch`, `bulk.low_library_size`, `bulk.qc_warn`, `bulk.qc_fail_retained`
  (block), `bulk.metadata_inconsistent`, `bulk.low_replicates`, `de.covariate_omission`,
  `test.multiple_comparison` (block on `none`), `bulk.filter_after_test`. Policy ranges
  `bulk.min_library_size`, `bulk.min_replicates` by profile.
- `defaults` (`min_n_per_group: 3`), `describe`/`echo` in the register of design 12.3.

### Method repo, pipeline `bulk-de` (all `runner: engine`, env `bulkrna-r`)

`01_import` import-counts -> `02_qc` qc-metrics (13 reference metrics with warn/fail as params;
tissue-marker and sex-gene consistency as code) -> `03_filter` filter-features (minimal prefilter
ahead of DESeq2's independent filtering) -> `04_de` de-deseq2 (single `condition` factor, all
pairwise contrasts within tissue, BH, p 0.05, |log2FC| 1.0 as defaults with ranges; the DESeq2
parameter list is settled in session 0; contrasts from the job's `objective`) -> `05_gsea` fgsea on committed Hallmark GMTs
(seeded) -> `06_report` (code-generated prose, every numeral a table cell). v0.2 adds
`07_salient` judgment module `categorise-salient-genes` (vocabulary `gene_categories`, 3
replicates, negative control scrambled symbols, positive control known ISGs). Image
`bulkrna-r-0.1.0.sif` from `bioconductor/bioconductor_docker:RELEASE_3_21` (DESeq2, apeglm, fgsea,
jsonlite, ggplot2, rmarkdown); built by GitHub Actions from a Dockerfile in the method repo to
GHCR and pulled by digest into `/data/lab/env/images/` (decided 2026-09-15). Synthetic fixture generator `controls/fixtures/make_synthetic.py` (planted DE genes) serves
plugin tests, method tests, and controls.

### Project A (DARPA vendor counts) and Project B (alignment)

Both are development projects on a shallow delivery (`bulkrna-plan.md` section 1 data status):
`exploratory` profile, labelled development, QC report delivered first as the evidence for
re-sequencing; the final projects run on the new delivery from the same method tag.

A: sample sheet from `metadata.csv` (all 44 rows, `bulk.samples_unquantified` accepted once);
`design.yml` with group, tissue, condition; all pairwise contrasts within tissue;
deliverables `de_tables, de_summary, gsea_tables, qc_report, report`. Driven through the declare
skill from Jim's brief, then by a non-computational member through `stringency-analyze-bulk-rnaseq`.
B: `modules/nfcore-rnaseq` `runner: operator`, params named as nf-core params so `nextflow_log`
evidence matches the Action, `--with_umi --umi_dedup_tool umicollapse`, evidence
`nextflow_trace` (config adds the `container` field) + `nextflow_log` + `job_log`; `pre.sh` is the
canonical command so `exec.script_drift` has a script to hash. PROTSEQ needs Java, Nextflow,
`NXF_APPTAINER_CACHEDIR`, STAR index from GRCm39 Ensembl 112. A' binds B's counts via
`derived_from`.

### Sessions (about half a day each)

0 decisions (below) + `spec/bulkrna-design.md` + DECISIONS for E1/E2; 1 plugin skeleton +
extractors + synthetic data; 2 schemas, defaults, phrasing; 3 engine E1; 4 method skeleton, SIF,
manifest, policy, import + qc modules; 5 filter, DE, GSEA, pipeline lints; 6 predicates + fixtures;
7 report, end-to-end on synthetic data both machines, tag plugin/method `v0.1.0`; 8 Project A on
DARPA data via declare skill, retrospective; 9 judgment module + E2 + controls, method `v0.2.0`;
10 analysis skill, run by a non-computational member (the acceptance test for Track 1); 11
PROTSEQ Nextflow install + `nfcore-rnaseq` module; 12 Project B run and A' chained.

## Track 3: spatial (Lyons CLP), QC first

The app-1 plan (`spec/archive/app1-spatial-tma-plan.md`) predates both the dataset and `ROSC_MTA2`; its
inventory (section 2) is now answerable and its sessions 1 to 3 are reframed around wrapping
existing steps rather than inventing them.

- **Session S0, inventory note** (`notes/...-app1-inventory.md`): answer section 2 from the survey:
  XOA 6.1, FFPE, `mAtlas_v1` + `mMulti_100g`, 2 slides x 4 tissues, punches per region (from the
  manual coordinates), replication unit, controls, existing code = `ROSC_MTA2` steps 1 to 6 and
  downstream modules 1 to 6 (module 7 dropped), environments = `setup/envs/` conda locks (must
  become SIFs).
- **Session S1, splitter determinism.** Fix `PYTHONHASHSEED`-dependent barcode order in
  `jrose835/Xen_TMA_pipeline` per `setup/Claude/HANDOFF_XeniumSplitter.md`; add a determinism
  test; tag. Without this the split module cannot pass the engine's reproducibility checks.
- **Session S2, singlecell plugin first real pieces** (`~/github/stringency-singlecell`): object
  type `xenium_bundle` (`sc.xenium_bundle@1`: regions, cells, transcripts, panel, metrics from
  `metrics_summary.csv` and `cells.parquet` summaries) and `punch_coordinates` (the hand-drawn
  file, hashed, `source: manual annotation in Xenium Explorer`); operations `split_punches`,
  `qc_cells`; questions `processed_object` (option 1 of the objectives note) alongside the three
  already declared; design schema per app-1 session 1 (slide, tissue, animal, punch; replication
  unit).
- **Session S3, method repo `stringency-spatial-method`**: module `resegment-proseg` (wraps the
  ROSC Nextflow Proseg run as a SIF; lung and gut only, following the ROSC manifest where liver,
  spleen and FRT keep the vendor segmentation; decided 2026-09-15), module `split-punches` (wraps the fixed
  splitter; params `min_transcripts, min_area, qv_threshold`) and module `qc-cells` (the
  `tissue_configs.yaml` thresholds `min_nCount, min_nFeature, min_cellarea, max_cellarea` as params
  with ranges and decision points; outputs filtered object, `cellstats`, QC report); pipeline
  `xenium-qc` answering `processed_object`; predicates `sc.low_cell_count`, `sc.qc_fail_fraction`,
  `spatial.coords_missing` with fixtures; one Python SIF (scanpy/spatialdata pinned from
  `lock_rosc_downstream.yml`). Deliverable: the QC'd per-punch objects with sidecars, so
  clustering and annotation projects can chain via `derived_from`.
- **Session S4**: run `xenium-qc` on one Lyons CLP region, then all eight, from Claude Science;
  retrospective feeds the remaining app-1 sessions (clustering, annotation as the first judgment
  module with the `/single-cell-annotation` skill's rules, niches, DE), each wrapped from
  `ROSC_MTA2` as a parameterised module instead of a per-tissue script copy.

## What needs the owner's approval before build

Status 2026-09-15: item 1 approved as written; item 2 answered except the DESeq2 parameter list
(session 0); item 3 answered in full (the Lyons CLP design from the collaborator's documents on
2026-09-15; Track 3 S0 inventory note written the same day). Answers are recorded in section 8 of `bulkrna-plan.md` and section 4
of `app1-spatial-qc-plan.md`.

1. Track 1a amendment texts (7.5 `via: web` incl. strict, 10.4 two-kinds-of-skill, 12.1
   `summary.md` engine-rendered, 14.1 flags, 17 row).
2. Track 2 session-0 decisions: DE method and adjustable params; `condition = group.tissue`
   convention and reference group; p/LFC defaults (1.5 log2 is strict); filter rule; gene id and
   symbol conventions; `min_n_per_group` 3 and policy bands 4/3/2; Hallmark only vs KEGG; adopt the
   13 QC metrics verbatim; judgment module in v0.2 and who reviews; image build route and storage
   path; UMI structure and nf-core version for B; roles for members' runs (owner = member,
   reviewer = Jim, `relayed_review` true under standard); 32 vs 44 samples.
3. Track 3: confirm the replication unit and design for Lyons CLP; confirm no IF module; confirm
   the splitter fix happens in the splitter repo first.

## Order (revised 2026-09-15: the bulk delivery is development data; Lyons CLP is final data)

1. Track 0 (done).
2. Track 1b + 1c in one session (engine flags and the skill text that uses them belong together);
   Track 1g session tests on PROTSEQ. (1a approved 2026-09-15.)
3. Track 2 sessions 0 to 7 with Track 1d (toy analysis skill) in between; Track 1e and 1f in
   parallel. Synthetic data drives these sessions, so the shallow delivery costs nothing here.
4. Track 2 session 8: Project A (development) on the DARPA files, QC report first. Its
   retrospective and the QC report go to the owner for the re-sequencing decision.
5. Track 3 S1 to S4 (S0 done 2026-09-15): the Lyons CLP data is final, so the first scientific
   deliverable of the whole effort is `xenium-qc` on the eight regions, and it moves ahead of the
   remaining bulk sessions.
6. Track 2 sessions 9 to 10 (judgment module; analysis skill run by a lab member on the
   development data: the acceptance test for the UX work is about the experience, not the result).
7. Track 2 sessions 11 to 12 (Project B) when Nextflow is installed; the shallow spleen fastqs are
   the smoke test.
8. Final bulk projects when the re-sequenced delivery arrives: deposit, declare, run, deliver.

## Verification

- Engine: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy &&
  scripts/check_no_biology.sh` green after every engine session; goldens for `plain`, `summary.md`,
  review page; every new predicate in `CASES`.
- Plugins: `uv run pytest` in each plugin repo (no network, no R); `stringency plugins list` shows
  the plugin; `stringency lint .` clean in each method repo.
- Method repos: synthetic end-to-end `stringency run` under apptainer on BMESEQ and PROTSEQ with
  planted DE genes recovered; coverage report with no uncovered decision points except those named.
- UX: the toy re-run through `stringency-analyze-toy-compare` by someone other than the owner,
  measured against the 2026-09-14 baseline (26 cards); a hold resolved via chat (`via: relayed`)
  and one via the page (`via: web`) both visible in `reviews`.
- Real data: Project A (development) delivered on the vendor counts with `methods.md`,
  `coverage.md`, `summary.md`, its QC report naming every shallow sample; the final bulk
  deliverable waits for the re-sequenced data; `xenium-qc` delivered on one Lyons CLP region with sidecars a downstream project
  binds through `derived_from`.

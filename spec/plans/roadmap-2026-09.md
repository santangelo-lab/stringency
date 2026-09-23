# stringency: roadmap after the Phase A exit (2026-09-14)

Working note, not the spec. Approved by the owner on 2026-09-14. Detail per track: `spec/plans/ux-two-audiences.md`
(Track 1), `spec/plans/bulkrna-plan.md` (Track 2), `spec/plans/app1-spatial-qc-plan.md` (Track 3). Track 0 was done the
same day; see `notes/2026-09-14-1600-track0-and-roadmap.md`.

## Status (2026-09-23)

Lane C reached its deliverable: `xenium-qc` delivered on all eight Lyons CLP regions
(2026-09-18), the four Proseg resegmentations as their own projects, the cross-region summary,
and the first real judgment (the outlier proposal, v2 module), which sits at six item holds and
one flag hold for the owner in `/lab/projects/Lyons_CLP/qc_outliers_all`. Built along the way and
not in this plan: `board` and `present` with method delivery skills (design 14.4), optional
module inputs, `role: reference` inputs, secondary evidence tables, directory inputs and outputs.
Every engine change from those days is on branch `lane-c-directory-inputs` (eight commits ahead
of `main`, suite green at 240 tests, no PR opened yet). The spec text for it is split: design 2.3
(directory inputs), the Lane C plan and the session notes are on `main`; design 14.4 and the
optional and reference input sentences are on the branch only. The branch's three DECISIONS
lines were copied to `main` on 2026-09-22. Installed engine on PROTSEQ: `0.1.0+optin3-sc0.1.8`.
Lanes B and E have not started. Lane A steps 2 to 4 are open and item 5 grew out of the runs.
Update 2026-09-23: the owner decided all seven holds (six accepts of replicate 1, flag accepted)
and `run --deliver` completed the run, but the delivered proposal is stale: item verdicts reach the
`consensus` table and never the `consensus.json` artifact the next step binds (Lane A item 6,
`backlog.md` K7). The proposal must not be used as the review list until the run is repaired.
Per-lane status is under each lane in the Order section; the Track 3 outcome against its plan is
`app1-spatial-qc-plan.md` section 5.

Engine, end of 2026-09-23: Lane A is complete. PRs #2 to #6 and #8 merged (Lane C branch and K7,
`v0.2.0`; E1, E2, `param.agent_proposed`, `fork`, the review page, `v0.2.1`; inherited
confirmation, batch review, the renderer's citation lookup, `v0.2.2`; `any_low` option B, K8, the
item-5 fixes, `v0.2.3`; `arity: many`, `v0.2.4`). `v0.2.4` is the shared `current` on PROTSEQ
(`0.2.4-sc0.1.8`). The method side of `arity: many` (the cross-region summary as one glob input)
and the Lyons outlier repair are Lane F's. Day record:
`notes/2026-09-23-1700-lane-a-k7-step2-review-page.md`.

Lane decisions, owner, 2026-09-23: **Lane C is closed as completed.** Its successor, the spatial
method build-out with Lyons CLP as the pilot dataset, is a placeholder lane (Lane F) until it is
planned. **Track 2 and Lane B are dormant**, kept as written. **Lane D is closed**: item 3 (the
shared engine install and onboarding notes) was run the same day
(`integrations/claude-science/hosts/protseq-shared-install.md`); every other item is done or
scratched. Active lanes: A and E now, F once planned.

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
  fold `~/github/stringency-singlecell` (BMESEQ) into the `stringency-plugins` repo as
  `plugins/stringency-singlecell` (Lane D item 2), give `stringency-toy-method` a remote.
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

### 1d. Analysis skills as entry points [template and toy instance built 2026-09-23, Lane E]

Built as `render_skill.py` with source `skills/<pipeline>.analyze.yml` (the delivery skill of
design 14.4 already holds `skills/<pipeline>.yml`); an optional `name` gives the skill slug when it
differs from the pipeline (`stringency-analyze-toy-compare` on `toy-engine`). First instance in
`stringency-toy-method` `v0.1.4`; phrasings set written, not yet run
(`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`).

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

### 1g. Measurements (before/after, into `spec/plans/backlog.md` (measurements)) [checklist written 2026-09-23; runs pending the owner]

The two session tests and the measured run through the analysis skill are
`integrations/claude-science/hosts/protseq-session-tests.md`; the project directory is prepared
at `/data/lab/projects/2026-09_stringency-drive2_jrrose5/lane-e/`. Cards are visible only in
the app, so the owner runs it; the next Lane E session writes the row.

Cards per project, person turns to result, time to first delivered file, count of unrequested
commands/JSON/ids shown, holds and `via`, operator misreports vs trace. Two session tests on
PROTSEQ first: do delegate downloads under a data root raise cards; do standing grants cover
`call_command`. Target for an all-engine five-step run with one dispatch: 26 -> 8 or 9 cards.

### 1h. Project page and notify on hold [proposed 2026-09-23, `spec/plans/project-page-and-notify.md`]

After the first measured run: the chat path is near its floor (7 turns, 15 minutes), so the next
cost to the person is presence and finding results later. `review --serve` grows into the project
page (board, per-project progress, per-run results with downloads, holds with the method's
tables; `--read-only` and `--token-file` for a standing instance); the engine sends one message on
hold opened, run completed, delivered, run failed, through a per-user `notify.yml` (Slack webhook
or a command). Engine steps go to Lane A's queue; skill and host text to Lane E; the measured run
adds "time from hold opened to verdict recorded". Owner decisions in the plan's section 5.

## Track 2: bulk RNA-seq plugin and method (first real plugin) [dormant since 2026-09-23, kept as written]

One new package and one new repo: the plugin `stringency-bulkrna` lives at
`plugins/stringency-bulkrna` in the shared `stringency-plugins` repository (modelled on
`stringency-singlecell` and `plugins/stringency-toy`; repository layout decided 2026-09-17, Lane D
item 2), and `~/github/stringency-plasmidsaurusRNAseq-method` (from `templates/method-repo/`) is its own repo.

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

## Track 3: spatial (Lyons CLP), QC first [S0 to S4 done 2026-09-18; Lane C closed 2026-09-23, successor Lane F]

Outcome against the plan, and what is open for the track: `app1-spatial-qc-plan.md` section 5.

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
- **Session S2, singlecell plugin first real pieces** (`stringency-plugins/plugins/stringency-singlecell`): object
  type `xenium_bundle` (`sc.xenium_bundle@1`: regions, cells, transcripts, panel, metrics from
  `metrics_summary.csv` and `cells.parquet` summaries) and `punch_coordinates` (the hand-drawn
  file, hashed, `source: manual annotation in Xenium Explorer`); operations `split_punches`,
  `qc_cells`; questions `processed_object` (option 1 of the objectives note) alongside the three
  already declared; design schema per app-1 session 1 (slide, tissue, animal, punch; replication
  unit).
- **Session S3, method repo `stringency-xenium-method`**: module `resegment-proseg` (wraps the
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

Work runs in lanes. A lane is a chain of half-day sessions that touches its own repositories, so
lanes run as separate sessions at the same time. The engine is one lane so that nothing races on
`src/stringency/`. Lane C was the critical path to the first scientific deliverable, `xenium-qc`
on the eight Lyons CLP regions, delivered 2026-09-18; two items in Lane D gated it. Lanes were
revised 2026-09-23 (Status section); each lane's heading carries its state.

### Lane A: engine (serial, engine repo)

1. Track 1b flags with the 1c operator skill text in one session: `operator_line`,
   `run --responses`, `run --deliver`, `steps[].title` and `plain`, `--attest` requires a session
   ref, `reviews.operator_harness`, `summary.md` and its golden. Done 2026-09-15
   (`notes/2026-09-15-1500-lane-a-step1-flags-and-skill.md`); `declare --check --print-hashes`
   left to the backlog.
2. E1 and E2 (`bulkrna-plan.md` section 2): `design` and `objective` in the job JSON;
   `considered_set` filled. Done 2026-09-23 (PR #3, with item 5a): the job carries both; the
   engine writes `{items_from, n_items, digest}` as the considered set.
3. Track 1e review page: `review_serve.py`, tests, `scripts/review-page.sh`. Done 2026-09-23
   (same branch as step 2): `review --serve --projects <dir>`, token, `via: web`, eight tests.
4. Re-tag and reinstall on both machines after each step that Lane B or C depends on. PROTSEQ:
   `v0.2.0` to `v0.2.4` (PRs #2 to #6, #8) tagged and installed as the shared `current`
   2026-09-23 (label `0.2.4-sc0.1.8`); BMESEQ not reinstalled (no method runs there).
5. **Holds that ask the right question** (owner, 2026-09-18, after two days of live Lyons CLP
   runs: fourteen chained projects meant fourteen confirm holds restating one design, while every
   agent-chosen parameter was admitted silently). Three engine changes, in this order:
   a. `param.agent_proposed`: a flag predicate (standard profile) whenever an admitted parameter
      has `param_source: agent`; its hold view is the table parameter / default / proposed /
      reason. `exec.plan_drift` already covers deviations; judgment holds already exist. This turns
      standard from "the agent may choose within range" into "the agent proposes, the person
      approves".
   b. Inherited confirmation: a project whose every input is `derived_from` a run of a project the
      same owner confirmed, with a byte-identical design, records its confirmation as inherited
      (upstream hold id and acceptance in the trace) and opens no hold; its echo-back shows only
      what is new (pipeline, deliverables, the bound runs). A raw input, a changed design, or a
      method major-version change still opens a hold.
   c. Batch review: `review --holds A,B,C` with one echo-back that diffs sibling declarations
      (the eight QC regions differed only in the bundle) so one acceptance covers a set.
   Item 5a done 2026-09-23 (`param.agent_proposed@1`, PR #3; a fork's `--set` is labelled
   `fork` and not asked again). 5b done 2026-09-23 (PR #4: `Project.inherited_confirmation`,
   `via: inherited`, the inherited echo-back; design 2.7). 5c done 2026-09-23 (same PR:
   `review --holds A,B,C --projects <dir>`, `review_batch.py`, `reason_code: batch`).
   Also from the same days, done 2026-09-23 (PR #6): `submit --failed`; an extractor env per
   input (the consuming step's); lint parses `envs/manifest.yml`; `echo.md` wrapped at 100
   columns; `abandon` closes the step rows (`abandoned`) and withdraws the run's holds; invalid
   replicates open ONE hold for the step; a reject on one hold withdraws its siblings so the next
   `review` shows attempt 2's holds, not attempt 1's. The dispatch suffix naming the `structured`
   envelope key was fixed 2026-09-18. The variable-arity input type (`arity: many`, module
   contract amendment approved by the owner 2026-09-23) merged as PR #8, `v0.2.4`. Lane A is
   complete.
6. From the outlier judgment v2 run (2026-09-21,
   `notes/2026-09-21-1600-outlier-judgment-v2-engine.md`): the review-packet renderer resolves
   every evidence citation by the item key, so on a module with secondary evidence tables each
   citation prints "(no such cell)" although `judg.evidence_exists` passed on the same run
   (display only; `review.py` and `holds.py` should use the cited table's own key); per-item
   resolution at a flag hold, so the owner can accept some flagged items and not others (belongs
   with 5); `any_low` opens a hold for an item every replicate labelled the same, because the
   confidence criteria forbid any contradicting cell at `high` (tolerate one at `high`, or hold
   on `any_low` only when labels differ; *design*, the owner's call; `backlog.md` K2).
   Found 2026-09-23 when the seven holds were decided
   (`notes/2026-09-23-1100-outlier-holds-stale-consensus.md`): a review's verdict updates the
   `consensus` table but the `consensus.json` output written at judgment time is never rewritten,
   so `02_proposal` read six `unresolved` items with no label after the step completed, and
   `sc.exclusion_proposed` had counted two proposed punches where the decided consensus has six.
   Fix: rewrite the consensus output from the store when the step completes (re-recording its
   hash), and evaluate post-phase predicates that read the consensus after the item holds settle;
   then decide how a completed run repairs its artifact (`backlog.md` K7). Done 2026-09-23 (PR #2,
   `v0.2.0`): the consensus output is rewritten when the last item hold settles, post flags wait
   for the decided consensus, and a completed run is not repaired in place (a new run or a method
   bump; DECISIONS). The renderer's citation lookup fixed 2026-09-23 (PR #4:
   `review_render.tables_seen` reads the step's `evidence/` tables, secondary ones keyed by their
   own column). `any_low` decided 2026-09-23 (owner's option B, PR #5): low confidence on an
   agreed label is logged in the consensus notes, not held.

State 2026-09-22. Branch `lane-c-directory-inputs`, in order: `7671a3c` directory inputs and
outputs, symlinked binds, per-step tmp, `propose --new`; `ee9cd68` `init.column_missing` skips
`derived_from`; `ca6402b` and `5465d1b` `board`, `present`, design 14.4; `b808c75` the dispatch
envelope; `12f2f33` `IOSpec.optional`; `1d58127` secondary evidence keys; `41fc5cc`
`InputItem.role`. None of J1, J2, `submit --failed`, or the `abandon` step-row fix is on it. The
next Lane A session opens the PR, brings the branch's design text onto `main` with the design 2.3
text already there, tags, reinstalls on both machines (step 4), then does step 2 and item 5a.

### Lane B: bulk (bulkrna plugin and method repos) [dormant since 2026-09-23]

Sessions 0 to 8 of Track 2 in order. Session 0 (DESeq2 parameter list, `spec/bulkrna-design.md`)
wants the owner present. Sessions 1, 2, 4 run on synthetic data and need nothing from Lane A.
Session 5 needs E1 (Lane A step 2) installed. Session 8 ends with the development Project A and
its QC report for the re-sequencing decision. Sessions 9 to 12 follow Lane C's S4.

Status 2026-09-23: dormant by owner decision, not started; this text is kept as written for
when it wakes. `~/github/stringency-plasmidsaurusRNAseq-method` holds the
template seed only (`88bc939`); no `stringency-bulkrna` package exists under
`stringency-plugins/plugins/`. Lane D item 6 is done, so session 11 is the `nfcore-rnaseq` module
alone. The operator-run lessons from Lane C apply to sessions 11 and 12: a detached launcher for
steps longer than a session tool call, `systemd-run --user --scope -p MemoryMax -p
MemorySwapMax=0` around Nextflow, binds in the Nextflow config because it clears the environment
before `apptainer exec` (`notes/2026-09-17-1900-lane-c-day1-clp-qc.md`,
`notes/2026-09-18-2000-lane-c-day2-proseg-summary-judgment.md`).

### Lane C: spatial (splitter, singlecell plugin, spatial method repos) [completed 2026-09-23]

S1 splitter determinism (its own repo, tag), S2 plugin object types and design schema, S3 the
modules `resegment-proseg`, `split-punches`, `qc-cells` with the Python image, S4 runs on one
region then all eight: done 2026-09-17 and 2026-09-18. Beyond S4: `xenium-qc-summary` delivered;
the outlier judgment (`xenium-qc-outliers-ref`, method `v0.3.3-rc1`, plugin `v0.1.11`, both local
tags) run, its seven holds decided and the run delivered 2026-09-23. The outcome against the plan,
including where the build departed from it (resegmentation as its own project per region, Xenium
Ranger 4.0.1.4, coordinates as a directory, revised spleen thresholds), is
`app1-spatial-qc-plan.md` section 5; the data-side record is `/lab/projects/Lyons_CLP/PROGRESS.md`.

Closed by the owner 2026-09-23: the first scientific deliverable is in hand, `xenium-qc` on all
eight regions with the summary and the review proposal chained through `derived_from`. What the
lane left open moves to Lane F; the engine defect it exposed (the stale consensus artifact,
`backlog.md` K7) is Lane A item 6.

### Lane F: the spatial method after QC, Lyons CLP as the pilot (planned 2026-09-23)

Successor to Lane C. Plan: `spec/plans/spatial-method-plan.md` (drafted 2026-09-23 from the
ROSC_MTA2 archive survey; awaits the owner's approval and the eleven decisions in its section 8).
In one line: phase 0 re-runs the QC chain on `v0.2.4` with the method fixes it exposed (batch
review over the eight QC holds, inherited confirmation on the summary, `arity: many`, a clean
second outlier judgment, the owner's exclusion file); then clustering, annotation (the first
downstream judgment, with controls first), niches, descriptive composition and neighbourhoods,
pseudobulk DE at the animal, reports and skills, one project per organ chained through
`derived_from`, one Python image; CellQuant, CellChat and cargo stay out of the pilot. Twelve
half-day sessions F0 to F12.

Carried over from Lane C and Lane D item 7 (all inside the plan's phase 0 and section 8):
`qc_outliers_all` repair by a module bump and a new run; `qc-cells` `segmentation_of`; the
Proseg transcript floor and the gut label (owner); the pathology pass; the splitter merge and
the tag cleanup (owner housekeeping, `backlog.md` K6).

### Lane D: owner and operations [closed 2026-09-23]

Closed by the owner 2026-09-23. Item 3 was run the same day; every other item is done or
scratched. The layout decisions under item 2 stay because they are decisions, not tasks.

1. Punch coordinates for the eight regions. Done 2026-09-17: 43 per-punch exports under
   `/lab/projects/Lyons_CLP/punch_coordinates/`, with `histology_include.csv` beside them.
2. GitHub repositories (`stringency-plugins`, `stringency-plasmidsaurusRNAseq-method`,
   `stringency-xenium-method`) with Actions and GHCR write. Done 2026-09-17 except the
   `stringency` team (owner, web UI). The org's workflow-token default is read-only, so each image
   workflow declares `permissions: {contents: read, packages: write}`.
   Repository layout (decided 2026-09-17, to limit clutter in the lab org): **all plugins share
   one repo**, `stringency-plugins`, one package per subdirectory under `plugins/` in a single uv
   workspace, installed with `scripts/install.sh --plugin <url>@<tag>#subdirectory=plugins/<name>`
   (the syntax the toy plugin already uses). The existing `santangelo-lab/stringency-singlecell`
   repo becomes it: rename it to `stringency-plugins` on GitHub (the old URL redirects), move its
   contents to `plugins/stringency-singlecell/`, add `plugins/stringency-bulkrna/` in Lane B
   session 1. **Method repos stay one per method**, because the engine clones a method repo at a
   tag and records remote, tag, and SHA in provenance; sharing a repo would couple the version
   numbers and `policy.yml` of unrelated methods. Method repos are named for the assay and
   delivery they analyse, never for a collaborator project (`stringency-xenium-method`,
   `stringency-plasmidsaurusRNAseq-method`; decided 2026-09-17): the project identity lives in the
   project directory and in provenance, and one method serves every project on that assay. A
   project-specific analysis becomes a pipeline in the assay's method repo first, and its own
   method repo only if it grows its own modules and policy. Give every repo the topic `stringency` and
   assign them to a `stringency` team in the org so they list together and share access.
3. Track 1f, shared engine install and onboarding notes. Done 2026-09-23: engine
   `0.1.0+optin3-sc0.1.8` (branch `lane-c-directory-inputs` at `41fc5cc`, plugin
   `stringency-singlecell` 0.1.8 from the local checkout at `v0.1.11`, toy 0.1.2) at
   `/data/lab/env/stringency/current`, group-readable throughout, smoke-tested read-only on the
   Lyons CLP projects; owner's PATH line and `~/.local/bin/stringency` switched to it;
   `render_brief.py --engine-bin` default, `new-project.md` and the README updated; notes written:
   `hosts/protseq-shared-install.md` (how, and the `--no-sources` recovery the plugins workspace
   pin forces), `hosts/protseq-lab.md`, `onboarding.md`, `publish-skills.md`. Left: the BMESEQ
   image-path symlink (until a method runs there) and retiring the per-user install after the
   next shared version lands.
4. Commit the 51 uncommitted files in `ROSC_MTA2`. Scratched 2026-09-23 (owner's BMESEQ
   housekeeping, not a roadmap item).
5. Re-sequencing decision and the new bulk delivery. Scratched 2026-09-23; returns with Track 2
   if Lane B wakes.
6. Java and Nextflow on PROTSEQ. Done 2026-09-17: Java 21 and Nextflow 24.10.0 under
   `/lab/env/nextflow`, `NXF_HOME` on `/lab/scratch`,
   `NXF_APPTAINER_CACHEDIR=/data/lab/env/images/nxf-cache`.
7. Owner items left by Lane C. Scratched here 2026-09-23. The seven holds in `qc_outliers_all`
   were decided that morning (six accepts of replicate 1: review for 48-1-Liver, 48-2-Liver,
   6-1-Lung-B, 24-1-Spleen-A; keep for 24-1-Liver, 24-1-Spleen-B; flag accepted); the delivered
   proposal is stale (`backlog.md` K7). The decisions that survive (transcript floor, gut label,
   exclusion decision, pushes and tag cleanup, splitter merge) are listed under Lane F.

### Lane E: skills and UX (after Lane A step 1)

Track 1d analysis skill template and the toy instance; the two Track 1g session tests on PROTSEQ;
the measurement rows; Track 2 session 10 with a lab member once Lane B session 8 is done.

Status 2026-09-23, end of day (`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`; PR #1
and PR #7 merged). Part of Track 1 section 6 (progress and results for a lay reader) arrived from
Lane C earlier: `board`, `present`, and the method delivery skills of design 14.4. Done: 1d
template, renderer, test and `spec/method-skills.md`; the toy instance
`stringency-analyze-toy-compare` in `stringency-toy-method` `v0.1.4`; the 1g session tests
answered by the owner in the app (the `call_command` card offers a project-scoped grant, the
download card a conversation-scoped grant per directory); the first measured run through an
analysis skill (owner, 7 turns, 14 min 39 s to the first delivered file, 0 misreports against the
trace, confirm relayed; row in `backlog.md`, cards to fill), which found engine defect K8 (fixed
by Lane A the same day). The acceptance test's original target (Track 2 session 10, a lab member
on bulk RNA-seq) is gone with Lane B dormant; the template is proved on the toy, and the first
real instance will be a spatial pipeline once Lane F has one. Left: three template fixes from the
run and a toy re-tag; the toy run by someone other than the owner, which needs K8 tagged and
installed and a method location the tester can read (the toy method is under `/home/jrrose5`,
remote BMESEQ); then close the lane, with skills a step of every method build.
Next, from the 2026-09-23 brainstorm: Track 1h (`spec/plans/project-page-and-notify.md`), the
project page and notify on hold; its engine steps need a session that owns `src/stringency/`.

### Running it

Revised 2026-09-23. Two agent lanes at once: Lane A (engine) and Lane E (skills and UX), each in
its own terminal and repository. Lane F opens once its plan is written and Lane A item 6 has
landed, since the pilot data's review proposal depends on that repair. Lane B stays dormant with
Track 2 as written; when it wakes, its sessions run as planned there.

## Verification

- Engine: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy &&
  scripts/check_no_biology.sh` green after every engine session; goldens for `plain`, `summary.md`,
  review page; every new predicate in `CASES`.
- Plugins: `uv run pytest` at the root of `stringency-plugins` (one workspace, every plugin; no
  network, no R); `stringency plugins list` shows each plugin; `stringency lint .` clean in each
  method repo.
- Method repos: synthetic end-to-end `stringency run` under apptainer on BMESEQ and PROTSEQ with
  planted DE genes recovered; coverage report with no uncovered decision points except those named.
- UX: the toy re-run through `stringency-analyze-toy-compare` by someone other than the owner,
  measured against the 2026-09-14 baseline (26 cards); a hold resolved via chat (`via: relayed`)
  and one via the page (`via: web`) both visible in `reviews`.
- Real data: Project A (development) delivered on the vendor counts with `methods.md`,
  `coverage.md`, `summary.md`, its QC report naming every shallow sample; the final bulk
  deliverable waits for the re-sequenced data; `xenium-qc` delivered on one Lyons CLP region with sidecars a downstream project
  binds through `derived_from` (done 2026-09-18 on all eight regions; the summary and outlier
  projects bind those deliveries through `derived_from`).

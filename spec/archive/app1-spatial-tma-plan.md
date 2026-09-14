# Application 1: spatial TMA pipeline, working plan

> Archived 2026-09-14: written before the Lyons CLP data and the ROSC_MTA2 pipeline existed. Its inventory questions and sessions 4 to 14 still inform the work; its opening is revised in `spec/plans/app1-spatial-qc-plan.md`.

How we turn the engine into something that runs your TMA analysis. Claude Code builds the engine from `stringency-build-plan.md`; you and I fill in `stringency-singlecell` and the method repo through the sessions below. Each session produces a spec file that Claude Code implements against the frozen contracts, so the two tracks interleave rather than serialize.

Section numbers in parentheses refer to `stringency-design.md`.

## 1. Where this sits

Phase A (engine) has no dependency on anything here. Sessions 1 through 3 can start now, before any code exists, because they produce declarations (design, objective, topology) rather than code. Sessions 4 through 6 need the gate and extractor machinery (build milestones M4, M5). Sessions 7 and 8 need judgment execution and controls (M6, M10). Sessions 9 through 12 need a first annotation run to have happened. Session 13 needs the CLI stable (M9). Session 14 is the first full run.

Prerequisites on BMESEQ, from implementation plan 7.3, unchanged: the archive seed to PROTSEQ completes and is verified; stale projects are deleted to recover working space (the array is at roughly 2.2 TB free); Claude Science is installed, which needs the Ubuntu version, bubblewrap version, and free space on `/` answered, and a decision on where `~/.claude-science` lives. None of these block sessions 1 through 6.

## 2. Inventory checklist, before session 1

Answer these asynchronously and drop the answers into the project as `notes/2026-09-xx-app1-inventory.md`. Approximate answers are fine; they get refined in session 1.

Platform and format: which spatial platform produced the data; what file(s) are in hand (vendor export, AnnData, SpatialData, flat tables); gene panel size; whether a raw counts layer exists separately from any normalized matrix; whether segmentation is final or might be redone.

Processing already done: what has been run on the data so far, in what software, and whether any of it should be treated as an input (already-QC'd object) or redone inside the pipeline.

Experimental structure: number of cores, blocks, slides, animals; how cores map to blocks and animals; which cores are tumor versus margin and whether that is a per-core or a within-core label; which cores are retroorbital versus subcutaneous; whether slide is confounded with condition or region; which obs columns exist today and their exact names.

The biological replicate: confirm `block_id` is the replication unit for the regional contrast, and state what it is for the condition contrast.

Positive control: the GEO-deposited TMA dataset, how its author annotations were produced, how many cores it has, and which core you are willing to never look at (the held-out fixture, 2.4 and 11).

Existing code: where your current spatial pipeline lives, what language each stage is in, and which stages you would keep as-is inside a module.

Environments: which containers or lockfiles exist for R and Python stages; whether `/data/lab/env` exists on BMESEQ yet.

Storage: where the data sits on BMESEQ, its size, and where the project directory can go.

## 3. Sessions

Each session lists its goal, the questions we settle, the artifact it produces, and what it unblocks. Expect one to two hours each; several can be done in one sitting.

### Session 1: design declaration and inputs

Goal: `design.yml` and `inputs.yml` for the TMA project, and the plugin's design schema.

Questions: which obs columns are `sample`, `block`, and the factor columns; the exact factor levels; what goes in `batch`; whether region is a core-level or cell-level label (this decides whether the regional contrast is between cores or within cores, which changes the replication story); how the two contrasts (region, condition) relate, and whether they belong in one project or two; which fixture hashes go under `holdout`.

We also write the echo-back sentence together: the plain-language rendering of the design that `init` will show and you will sign. If the sentence is hard to write, the design file is wrong.

Artifact: `design.yml`, `inputs.yml`, `spec/design-schema.md` in the singlecell repo describing the fields the schema must accept, and the echo-back phrasing for the plugin.

Unblocks: `obj.feasibility`, `de.replication_unit`, `de.covariate_omission`, and the extractor's `counts_per_group`.

### Session 2: objective

Goal: `objective.yml` and the plugin's question vocabulary.

Questions: the primary question for this project, stated as a contrast; whether niche characterisation is a deliverable or an intermediate; realistic `min_n_per_group` given the block counts (a value of 3 with six blocks per region leaves no room for QC failures, so we decide the tradeoff explicitly); the deliverables list `deliver` will insist on; which figures the analysis is meant to feed, so the report module knows what to produce.

Artifact: `objective.yml`; `spec/objective-questions.md` listing the questions the plugin accepts (`differential_expression`, `niche_characterisation`, `interaction_inference`, and whatever else we name).

Unblocks: forward feasibility and the deliverables check.

### Session 3: topology and module inventory

Goal: `pipelines/spatial-tma.yml` and the list of modules to write or wrap.

Questions: the ordered step list; for each step, its kind (deterministic, judgment, report), whether it wraps existing code or is new, its language, its environment, its runner (you or the session agent running it after `propose`, or the engine), what evidence it can produce for `submit` (a Nextflow trace, a log that prints its parameters), its parameters with a default and the range within which the agent may choose (a range you would accept without asking to see the reasoning, since that is exactly what the gate will do), and which parameters are decision points (6.6); where judgment enters (annotation, niche labels, interaction interpretation, salience) and where it must not (anything numeric); what each judgment module's evidence table will be, at the level of "a table with one row per cluster and these column families."

Artifact: `pipelines/spatial-tma.yml` draft; `spec/module-inventory.md` with one entry per module; the environment list for `/data/lab/env`.

Unblocks: everything downstream. This is the session where the pipeline becomes pre-specified in the sense Commandment 1 means.

### Session 4: state extractor specification

Goal: what `sc.anndata` must report so every predicate we intend to run is decidable from the summary alone.

Questions: how to detect "normalized" reliably (an `uns` flag, the presence of a counts layer, X dtype and range); how to detect that HVG selection, neighbors, and Leiden have run and with what parameters (scanpy records these in `uns`); what spatial fields to report (coordinates present, neighborhood graph present and its definition); which per-group counts to compute (blocks and cores per level of each factor, and after clustering, cells per cluster per block); whether to report QC metric quantiles so `qc.threshold_range` can compare a threshold against the distribution; whether the object will be AnnData throughout or SpatialData at some stages (which would mean a second extractor).

Artifact: `spec/extractor-sc-anndata.md` with the JSON schema for the `domain` block and at least four fixture JSONs: raw, post-QC, post-clustering, post-neighborhood.

Unblocks: M5 integration for the real plugin, and every predicate test in session 5.

### Session 5: predicates for application 1

Goal: the instantiated predicate table with fixtures, ready for Claude Code.

We walk the starter set (implementation plan 4.1) and the spatial set (9.2) one at a time. For each: does it apply to this pipeline; what field of state, action, or history does it read; what is its default disposition; what is its `covers` declaration; describe the must-fire and must-pass fixtures in words.

Candidates to add for this assay: `sc.panel_hvg` (HVG selection on a targeted panel of roughly a thousand genes is questionable; flag); `spatial.coords_missing` (a spatial operation proposed on an object without coordinates; block); `test.assumptions_unchecked` (a statistical test proposed without an attached assumption-check artifact from code, per Commandment 6; block); `de.selection_bias` scoping (the regional contrast is by declared region, not by discovered cluster, so it should not fire there, but a niche-versus-niche DE would trigger it; we decide the scope precisely).

Then the coverage question: after this set, which decision points from session 3 have no coverage, and are we content to ship with the report saying so.

Artifact: `spec/predicates-app1.md`, a table plus fixture descriptions; Claude Code implements each with tests.

Unblocks: the first gated run.

### Session 6: vocabularies and confidence criteria

Goal: closed label sets and the criteria behind the confidence ordinal.

Questions: the cell type vocabulary for this tissue and species (a Cell Ontology subset with IDs, plus `unknown`); whether the vocabulary is flat or two-level (lineage then subtype) and how a two-level label is recorded in the schema; the niche vocabulary, and the design question that matters most here: can it be closed in advance, or does niche labelling need a `proposed_label` field outside the vocabulary that always creates a hold; the confidence criteria numbers for annotation evidence, and whether "supporting evidence" counts distinct marker rows or distinct columns; the salience vocabulary (what categories of "interesting" the module is allowed to assert).

Artifact: `vocabularies/cell_types.yml`, `vocabularies/niches.yml`, `vocabularies/salience.yml`; `policy.yml` confidence criteria for the method repo.

Unblocks: `judg.vocabulary_resolves` and `judg.confidence_consistent` for real.

### Session 7: the annotation module

Goal: `modules/annotate-cluster/` fully specified.

Questions: the evidence table columns per cluster (top markers with effect size and fraction expressing in and out of cluster; cluster size; distribution across cores and regions; anything else you look at when you annotate by hand, and nothing you do not); the context JSON (tissue, species, panel, expected populations, known absences); the prompt template, written together, including the abstention instruction; schema extensions (`alternative_labels`, lineage field); batching (`all_items`, and whether a cap on items per prompt is needed at your cluster counts); replicate count; whether ontology IDs are required or optional in the first version.

Artifact: the module directory with `module.yml`, `prompt.md`, `schema.json`, `pre.R` or `pre.py` spec, and an empty `controls/` to be filled in session 8.

Unblocks: the first judgment run on the development control set.

### Session 8: controls

Goal: controls for the annotation module, and the generators the niche and salience modules will need later.

Questions: the positive control: how to derive the marker table for the GEO dataset with the same `pre.*` script, the author-label to ontology mapping table, the dev/holdout core split, and the agreement metric (exact match after mapping, or match at lineage level); the negative control for annotation: permuting gene names across clusters in the marker table so that no coherent identity exists, and what "null output" means for annotation (every item abstains, or every item is `unknown`); the coordinate permutation generator (within core) and the condition permutation generator, specified now even though they are used from session 9 onward; the planted-signal generator for salience: what is spiked, at what effect sizes, and what detection means.

Artifact: `controls/*.yml` for annotate-cluster; `spec/control-generators.md` describing `permute_coordinates`, `permute_condition`, `shuffle_markers`, `spike_spatial_enrichment` as tool-half scripts.

Unblocks: `stringency controls run` on a real module and the Phase B exit criterion.

### Session 9: the niche module

Goal: neighborhood definition and the niche labelling module.

Questions: how the neighborhood is defined (radius or k-nearest, with values) and where that declaration lives so `spatial.neighborhood_undeclared` can read it; the composition table per neighborhood cluster; the permutation null for enrichment claims and what artifact it produces so `spatial.no_permutation_null` is decidable; edge handling at core boundaries; the labelling prompt and whether the niche vocabulary decision from session 6 holds up against real composition tables.

Artifact: `modules/define-neighborhood/`, `modules/cluster-niches/`, `modules/label-niches/` specs; niche predicates instantiated with fixtures.

### Session 10: interaction interpretation

Goal: the highest confabulation-risk module, constrained hard.

Questions: which CellChat (or alternative) outputs form the evidence table; whether the module is allowed to narrate at all, or only to rank and flag ligand-receptor pairs from the table; the considered set (every pair tested) as a required output, so `judg.considered_set_missing` applies; whether every sentence of rationale must cite a row (we can require it in the schema by making `supporting_evidence` non-empty per claim).

Artifact: `modules/interpret-interactions/` spec with `considered_set: true`.

### Session 11: differential expression

Goal: the DE step's parameters and the predicates that fire on it.

Questions: pseudobulk aggregation unit (`block_id`), the design formula and covariates (`slide_id`; whether it is estimable given the confounding you described in session 1), the contrast, the correction method, minimum counts filter; whether cluster-specific regional DE is in scope, and if so how the `de.selection_bias` scoping from session 5 treats it; the assumption-check artifact code produces for `test.assumptions_unchecked`.

Artifact: the `08_de` step in `pipeline.yml` with params; a fixture confirming which predicates fire and which pass on it.

### Session 12: salience and the considered set

Goal: the "interesting results" module with its denominator.

Questions: the enumeration of what counts as a contrast or comparison the module evaluated; the output format for the considered set (one row per evaluated comparison with its statistic, and a flag column); the sensitivity target from the planted-signal control; the salience vocabulary in use.

Artifact: `modules/flag-salient/` spec with `considered_set: true`.

### Session 13: Claude Science skills

Goal: the five verbs as skills, plus the two session conventions.

Questions: the description text for each of `init`, `run`, `review`, `status`, `deliver`, written for disambiguation ("how's my analysis going" must route to `status`, "can you check the results" must not route to `deliver`); a test set of twenty casual phrasings and their intended verb, run through skill-creator's eval; the `review` relay protocol text: the skill must present the hold, ask for an explicit decision, and only then run `review --attest`, with the exact wording; the execution protocol text for the `run` skill: on exit 21, read the job spec, run the step, call `submit` with the declared outputs and evidence, and never run an analysis step without a ticket; the dispatch protocol text: on exit 20, spawn one fresh subagent per request file, restricted to reading that file and writing its response if Claude Science permits tool restriction, passing the file path and never the prompt text, then call `run` again; two tests of Claude Science subagents before writing it: can a subagent be limited to one file, and does its output truthfully report `saw_conversation: false` when the session contains a planted phrase it should not know; the session-start convention (read `status` and the latest note) and the session-end convention (write `notes/<timestamp>-<slug>.md`); the environment variables the wrappers set (10.1); what `deliver`'s skill does after the CLI returns (save artifacts, write the run ID into the artifact record).

Artifact: `skills/` in the method repo with one skill per verb; the eval results committed alongside.

### Session 14: first full run and retrospective

Goal: run the pipeline on the development cores, then on the full set, and find what the trace cannot tell us.

Steps: run under `standard`; walk the review queue together and record verdicts honestly, including rejections; read the coverage report and decide whether the uncovered list is acceptable; attempt to reconstruct one delivered number from `run.db` alone, without looking at the code, as a manual inspector; fix any capture hole found; revise the annotation prompt from the override corpus with commit messages citing review IDs; rerun and confirm rebind spares the settled items; then run on the full core set.

Artifact: `notes/<timestamp>-app1-first-run-retrospective.md` with the override rate, the uncovered list, capture holes found, and the backlog for Phase D.

## 4. Cadence against the build

| Build milestone | Sessions that can run alongside | Sessions that need it |
|---|---|---|
| M0 through M3 | 1, 2, 3 | none |
| M4, M5 | 4, 5, 6 | 4 (extractor fixtures land in M5 tests) |
| M6 | 7 | 7 |
| M7 through M9 | 9, 10, 11, 12 (specs only) | 13 |
| M10 | 8 | 8 |
| M11 | | 14 |

Realistically: three sessions in the first week while Claude Code scaffolds; the extractor and predicate sessions once the gate exists; the annotation module the week judgment execution lands; controls right after; everything else once we have seen a real annotation run and its review queue.

## 5. Risks particular to this application

A targeted panel violates assumptions baked into single-cell defaults. HVG selection, mitochondrial-fraction QC (there may be no mitochondrial genes on the panel), and normalization choices all need decisions in sessions 3 and 5 rather than inherited defaults. Several starter predicates carry ranges written for whole-transcriptome data.

Niche vocabulary may not close. If real composition tables demand labels nobody predicted, the escape hatch from session 6 (`proposed_label` with a mandatory hold) is the mechanism, and the override corpus tells us when to add the label to the vocabulary.

The first review queues will be long. With `standard` agreement, any dissent or abstention holds an item. That is the design working; the override rate is the metric that tells us where the prompt or the evidence table is weak. Resist relaxing the agreement policy before the corpus has fifty or so entries.

Claude Science unknowns. Whether it exposes a session reference, whether its artifact store under `~/.claude-science` is readable by a script, what its Environment tab captures for remote jobs, and how far its subagents can be tool-restricted all affect how much the trace can claim. None of them affect the engine. Test them in session 13 by inspection, and record what was found.

Judgment isolation is reported, not enforced. With the dispatch adapter, the trace says `isolation: as_reported` on every judgment invocation, and the coverage report repeats it. The negative controls are what stand behind the annotation module's claims. Write them before the first real annotation run, not after.

Storage on BMESEQ. Every run keeps its outputs under `runs/`. Intermediate objects for a 48,000-cell object are small, but a dozen forks of a pipeline with several object outputs each are not. `abandon` and a retention policy for abandoned runs' object files (keep the trace, drop the objects) may be needed sooner than expected; decide in session 14.

Slide confounding. If slide is confounded with region or condition, `de.covariate_omission` will fire on every DE run and the honest answer is a permanent accepted flag with the reason recorded, which the coverage report will show on every delivery. That is correct behaviour and worth knowing before the first run rather than discovering in the review queue.

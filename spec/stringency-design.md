# stringency: component design

Version 0.1, 3 September 2026. Companion to the implementation plan (September 2026), the admissibility design note, the Commandments, the git-practice note, and the eval-controls note. Where this document and the implementation plan disagree, this document is the spec; section 18 lists every such point.

## 0. Scope and reading order

This document specifies every component of the `stringency` engine to the level Claude Code needs to build it, plus the plugin boundary that `stringency-singlecell` will fill for application 1 (the spatial TMA pipeline on BMESEQ).

It defers: open and staged modes (schema reservations only), application 2, the openai-compatible harness, the re-audit path, and a Nextflow executor. Section 17 lists each with the trigger that would pull it forward.

Reading order for Claude Code: this document, then the current plan in `plans/roadmap-2026-09.md` (the Phase A build plan is in `archive/`). The implementation plan is background. The Commandments and the git note are the source of the constraints and should be read once.

## 1. Objects

| Object | Definition |
|---|---|
| Project | A directory bound at `init` to one pipeline, one objective, one mode, one profile, and named roles. |
| Run | One execution attempt of the bound pipeline. Identified by a ULID. May have a parent run (fork). |
| Step | One node of the topology inside a run. Carries a status (7.1). |
| Module | A versioned directory implementing one operation, per the contract in 3.2. |
| Operation | A named analysis action with a parameter schema, drawn from a plugin's vocabulary. Predicates scope over operations. |
| Action | A concrete proposal: operation, parameters, input references. One per step attempt, written before the gate runs. |
| State | A structured summary of the analysis at a point in the run. Never the data object itself. |
| Predicate | A pure function over a gate context. Fires or does not. Has an ID, a version, a scope, a phase, a default disposition, and a coverage declaration. |
| Policy | A versioned file mapping predicates to effective dispositions per profile, plus the numeric criteria predicates read. |
| Verdict | What one predicate returned on one action: fired, reason, evidence, default and effective disposition. |
| Hold | A step, or an item within a step, stopped and waiting on a named person. |
| Review | A recorded human verdict on a hold, bound to the hashes it was made against. |
| Invocation | One call to the judgment harness: prompt, model, response, cost. |
| Judgment | One item-level structured output from one replicate. |
| Consensus | The per-item amalgamation of replicates and reviews. The only thing downstream steps consume. |
| Artifact | A file output with hash, kind, and run linkage via a sidecar. |
| Control | A declared test of a module: how to build the input, what the output must look like. |

## 2. Project

### 2.1 Layout on disk

```
<project>/
  stringency.yml            bound configuration (2.2); written by init, read-only after
  objective.yml             2.5
  design.yml                2.4
  inputs.yml                2.3
  method/                   clone of the method repo at the pinned tag; never edited here
  prov/
    run.db                  SQLite, WAL mode; the trace (9)
    justifications/         free text attached to reviews, one file per review_id
  runs/<run_id>/
    <step_id>/              outputs, stdout, stderr, state summary, sidecars
    summary.md              written at run close
  deliver/<run_id>/         harvested finals, coverage report, methods paragraph, index.json
  controls/<module>/        control run outputs
  .stringency/              engine scratch; safe to delete
```

Raw data lives wherever `inputs.yml` points, normally elsewhere on the array. A declared input or a step output may be a directory (a Xenium region bundle, a set of punch bundles); it is hashed as a tree (sorted relative path plus content per file) and carries one sidecar beside it (amendment 2026-09-17, Lane C). The project directory holds no raw data and is not itself a git repository; the method repo under `method/` is. `prov/` and `runs/` live on the data array and never on a CIFS mount.

### 2.2 Configuration bound at init

```yaml
stringency: 1
project_id: 01J9K…                 # ULID
created: 2026-09-10T14:02:11Z
stringency_version: 0.1.0
method:
  repo: git+https://github.com/santangelo-lab/stringency-xenium-method
  tag: v0.2.0
  sha: 3f9c1a…
pipeline: spatial-tma              # file name in method/pipelines/
mode: pipeline                     # pipeline | staged | open   (v1 accepts only pipeline)
profile: standard                  # strict | standard | exploratory
roles:
  owner: jrrose5
  reviewer: jrrose5                # may equal owner; the record is the point, not the separation
judgment_harness: subagent         # 10.2; api | openai-compatible | subagent | mock
execution: operator                # 10.3; operator | engine; per-module override via manifest runner:
executor: apptainer                # 10.3; used for engine-run steps, extractors, and judgment evidence
policy: method/policy.yml          # 6.4; digest recorded on every run
splits: null                       # reserved for open mode (17)
```

Bound means `run` reads these and takes no arguments that could change them. Changing any of them requires a new project, or a `fork` for the parameters forking is allowed to change (2.6). `init` refuses `mode: open` with `profile: strict`.

### 2.3 Inputs manifest

```yaml
inputs: 1
items:
  - name: tma_counts
    path: /data/lab/projects/tma-2026/raw/tma_all_cores.h5ad
    type: anndata                  # resolved through the plugin's object types (4.2)
    blake3: 7c1e…
    source: "vendor export 2026-08-12"
  - name: tissue_context
    path: /data/lab/projects/tma-2026/context.json
    type: json
    blake3: 91ab…
```

`init` computes and verifies every hash and refuses on mismatch. `run` re-verifies at open (`repro.input_digest_mismatch`, 6.5). The `type` field decides which state extractor applies.

An item may carry `role: reference` when it describes other studies' observations rather than this design's (a table of earlier punches, an atlas); `init.column_missing` does not require the design columns in it (2026-09-21). An item may carry `derived_from: {run_id, step_id, output, project}` when the file is a delivered artifact of an earlier stringency run (chained projects; added 2026-09-09). `init` reads the sidecar beside the file and refuses unless it names that run, step, and output with the same hash. Run open captures the upstream run ids and the methods paragraph names them.

### 2.4 Design declaration

The domain plugin supplies the schema; the engine stores validated JSON and passes it to predicates. For `stringency-singlecell` the shape is approximately:

```yaml
design: 1
units:
  observation: cell
  sample: core_id                  # obs column
  block: block_id                  # obs column; the biological replicate
factors:
  region:    {column: region,    levels: [tumor, margin]}
  condition: {column: condition, levels: [retroorbital, subcutaneous]}
batch: [slide_id]
replication_unit: block_id
holdout:                           # fixtures no control or development run may touch (11)
  - {type: anndata, blake3: "44d0…", note: "GEO core C07, never inspected"}
```

`de.replication_unit`, `de.covariate_omission`, and `obj.feasibility` read this declaration rather than inferring design from the data. Declaring the design before the first run is what lets the analysis claim to be confirmatory. The exact fields are settled in app-1 session 1.

### 2.5 Objective

An engine-known core plus a plugin-interpreted `domain` block:

```yaml
objective: 1
id: tma_regional_de
question: differential_expression  # from the plugin's question vocabulary
contrasts:
  - [region, tumor, margin]
replication_unit: block_id
min_n_per_group: 3
deliverables: [de_table, niche_map, qc_report]   # deliver refuses to close without these
domain: {}
```

Every predicate receives the objective. The forward-feasibility predicate (6.5) compares `counts_per_group` in the state against `min_n_per_group` for every level of every contrast.

### 2.6 Runs and forks

A run is one attempt at the bound pipeline. `run` is idempotent: it resumes the project's latest open run, opens the first run, and refuses (exit 16) when the latest run is closed; `run --new` opens the next one, so a `run` typed after the final submit cannot start a second attempt by accident. Runs close as `completed`, `failed`, or `abandoned` (`stringency abandon --reason "…"`).

`fork --from <run_id> --at <step_id> --set <step>.<param>=<value>… --reason "…"` opens a new run with `parent_run_id` set. It inherits inputs and every completed step before `--at`, applies the declared parameter changes, and records them as `delta_json`. The parent is untouched. Forks may not change pipeline, mode, profile, objective, or design; those need a new project. Forking is how you rerun with a different threshold or contrast without overwriting the first result, and it is in v1 because application 1 is iteration-heavy.

### 2.7 Init: validation, compatibility predicates, echo-back

`init` is where the agent's reading of the experiment becomes the declarations every later gate trusts, so it gets three layers of checking before the project is usable.

The declarations may be drafted by an agent from the person's brief and a sample manifest (the `stringency-declare` skill), under the rule that every value has a source in the manifest, the brief, or a plugin default. `declare --check <dir>` runs every check below without creating a project and prints the echo-back, so the drafting loop never leaves a half-made project behind. `init --drafted-by agent --brief <file>` records the drafter, harness, and session reference in `stringency.yml` and keeps the brief as `brief.md`; the confirm hold's context carries the brief's hash beside the three declaration hashes. The echo-back and the owner's acceptance are what make the result the person's declaration whoever typed it (added 2026-09-09).

Validation: every input hash matches; `design.yml` validates against the plugin schema; `objective.yml` validates against the engine core plus the plugin's question vocabulary; lint passes on the method repo.

Compatibility predicates (6.5, the `init.*` set): the declarations are checked against each other and against the bound pipeline. Every contrast names a declared factor and declared levels; the replication unit is a declared unit; every design column exists in the raw input, which the engine learns by running the plugin's extractor once on each object input; the pipeline declares that it answers the objective's question; every deliverable is produced by some step; references named in the inputs match the pipeline's expected build. These are the errors an agent makes when it misreads a prose description, and they are cheapest to catch here.

Echo-back: `init` renders the design, objective, and inputs as plain language ("24 cores from 12 blocks on 4 slides; 12 tumor and 12 margin; the biological replicate is the block; the question is tumor versus margin differential expression with at least 3 blocks per group; slide is a batch variable") and opens a project-level hold of kind `confirm` waiting on the owner. `run` refuses to open a run until the owner has accepted it through `review`. This applies in every profile. The echo-back is regenerated and the hold reopened if any of the three files changes, because the accept is bound to their hashes (7.4).

## 3. Pipeline and modules

### 3.1 pipeline.yml

```yaml
pipeline: 1
name: spatial-tma
version: 0.2.0
domain: stringency-singlecell
steps:
  - id: 01_qc
    module: sc-qc@0.1.0
    inputs: {object: $inputs.tma_counts}
    params:
      min_counts: {default: 50, range: [20, 500]}
      max_pct_mt: {default: 15, range: [5, 30]}
  - id: 02_normalize
    module: sc-normalize@0.1.0
    inputs: {object: $steps.01_qc.object}
    params: {method: log1p_cpm}
  - id: 05_cluster
    module: sc-cluster@0.1.0
    inputs: {object: $steps.04_hvg.object}
    params:
      resolution: {default: 0.8, range: [0.3, 2.0]}
      seed: {default: 20260910}                    # no range: a fixed value the agent may not change
    runner: operator
  - id: 06_markers
    module: sc-markers@0.1.0
    inputs: {object: $steps.05_cluster.object}
  - id: 07_annotate
    module: annotate-cluster@0.3.1
    inputs: {markers: $steps.06_markers.table, context: $inputs.tissue_context}
```

Steps form a DAG through `$steps.<id>.<output>` references; file order is the tie-break for `next`.

Parameters are declared with a `default` and, where the agent may choose, a `range` (numeric bounds, or an `options` list for categorical parameters). Under the `standard` profile the agent proposes a value inside the range; under `strict` parameters are locked to their defaults; under `exploratory` an out-of-range proposal flags instead of blocking (6.4). A parameter with no `range` is fixed. The ranges are in git, so widening one is a diff with an author and a reason, and the agent's chosen value is in the Action record, so the choice is in the trace. This keeps Commandment 1 (the plan is pre-specified) while letting the agent do the tuning a person would do by eye.

`runner` selects who executes the step: `operator` (the agent runs the code and submits evidence, 3.4) or `engine` (the engine runs the module script). It defaults to the project's `execution` setting. A step that references a module absent from the method repo, or a module whose `modes` excludes the project's mode, fails `lint` and fails `init`.

### 3.2 Module contract v1

Frozen at Phase A exit. A module is a directory:

```
annotate-cluster/
  module.yml
  prompt.md                 judgment and report modules
  pre.R                     any language; produces evidence or performs the operation
  post.py                   optional restructuring
  schema.json               output schema for judgment modules (JSON Schema 2020-12)
  params.schema.json        parameter schema, all kinds
  controls/*.yml            11
  tests/                    optional module-level tests
```

```yaml
contract: 1
name: annotate-cluster
version: 0.3.1
kind: judgment                    # deterministic | judgment | report
operation: annotate_clusters      # id in the plugin's operation vocabulary
domain: stringency-singlecell
modes: [pipeline, staged]

env: sc-r-4.4                     # environment name; digest resolved at run open
runner: operator                  # operator | engine; default from the project; extractors and judgment pre.* are always engine-run

inputs:
  markers: {type: table, format: tsv, hash: true}
  context: {type: json, hash: true}
outputs:
  judgments: {type: judgments, format: jsonl, schema: schema.json, item_key: cluster_id}

decision_points: []               # parameters that are analysis choices (6.6); none here

stochastic: false                 # true requires seed_param
# seed_param: seed

judgment:
  items_from: markers             # rows of this input are the items
  item_key: cluster_id
  evidence: [markers, context]    # exactly what the model may see
  batching: all_items             # all_items | per_item
  replicates: 3
  abstain: required
  confidence: ordinal
  considered_set: false           # true for salience-type modules: output must carry the denominator

prompt:
  template: prompt.md
  vars: [evidence_table, vocabulary, context, items]

vocabulary: cell_type_labels@2026-09

gates:                            # predicates the author expects; lint checks each exists
  - out.schema_conformance@1
  - judg.evidence_exists@1
  - judg.vocabulary_resolves@1
  - judg.confidence_consistent@1
  - judg.numeric_claims_match@1

controls:
  required: [negative, positive]

resources: {cpus: 2, memory: 8GB, timeout: 30min}
```

Three properties follow from the manifest.

A module input may carry `optional: true`: a pipeline step may leave it unwired, and the module's script then finds no entry for it in `job.json` inputs (a reference table a study may or may not have). A judgment module with a `pre.*` script may list under `judgment.evidence` tables the script writes that are not inputs (a guide table beside the items table); without a pre-script every evidence name must be an input. Lint enforces both (2026-09-21).

The model sees only `judgment.evidence`. The engine renders the prompt from the template and the declared vars and nothing else reaches the model. "The model sees the table, never the matrix" is enforced by construction rather than by instruction.

Decision points are declared, so the coverage report (12.2) is computed rather than remembered.

`gates:` is a declaration of expectation, not the mechanism. The engine evaluates every registered predicate whose scope includes the module's operation, whether or not the manifest lists it. Lint fails a manifest that names a predicate that does not exist and warns when an in-scope predicate is not listed, since the author may not know it applies.

### 3.3 Module kinds

`deterministic`: code runs, outputs are files, the post-gate validates schemas and re-extracts state. No harness call. Under Commandment 6, QC, normalization, clustering, marker statistics, spatial statistics, permutation nulls, and differential testing are all this kind.

`judgment`: a harness call is made. Replicated, gated, held. Cluster annotation, niche labelling, interaction interpretation, and salience flagging are this kind.

`report`: consumes tables and consensus records and produces prose and figures, with an optional harness call for the prose. The numeric-claims predicate applies to the prose. Report outputs cannot be inputs to other steps.

### 3.4 Executing a deterministic module

Two runners share every step except the middle one.

Operator runner (the default):

1. `stringency propose <step_id>` resolves inputs and verifies their hashes, constructs the Action (5) from the manifest, the committed defaults, and the agent's proposed parameter values, and runs the pre-gate (6.2). On pass it issues a ticket and prints the job specification: input paths and hashes, the admitted parameters, the seed, the required environment and its expected digest, and the declared outputs with their types. `run` exits 21, awaiting execution.
2. The agent executes the step however it is competent to: `nextflow run`, an R script, a Python session. The engine is not involved.
3. `stringency submit <ticket> --outputs <name>=<path>… --evidence <file>…` hashes the outputs, validates any with a `schema`, runs the plugin's state extractor itself on object outputs (the engine, not the agent, produces the state summary), and parses the evidence: a Nextflow trace file, `.nextflow.log`, a job log, an `apptainer inspect` dump, whatever the module's manifest lists under `evidence:`. From the evidence it reads the parameters actually used, the container actually run, the seed, and the exit code.
4. `exec.plan_drift` compares what ran to what was admitted and blocks on mismatch. `repro.env_unverified` flags when the reported container cannot be matched to the environment manifest. The execution row records `runner: operator` and `env: verified | as_reported`.
5. Run the post-gate.
6. The step completes and its state summary becomes the pre-state of every downstream step.

Engine runner:

1. Resolve inputs and verify hashes. Construct the Action; run the pre-gate.
2. The executor (10.3) runs `pre.*` in the module's `env` with a JSON job on stdin: input paths, params, output directory, seed. Stdout and stderr are captured to the step directory.
3. Outputs are hashed and validated; object outputs go to the state extractor.
4. Run the post-gate. The execution row records `runner: engine`, `env: verified`.

Under either runner, a non-zero exit is a `failed` step, distinct from any gate result, and halts the run. Outputs with no ticket cannot be submitted, so running without proposing produces nothing the pipeline recognizes; the pre-gate is therefore binding in effect even though the agent, not the engine, controls the timing of the compute.

### 3.5 Executing a judgment module

1. Inputs resolved, Action constructed, pre-gate, as above.
2. `pre.*` runs if present and produces the evidence table(s). This is always engine-run, whatever the project's `execution` setting, so that what the judge is shown was produced by committed code the engine executed. These are hashed and recorded; they are what the model saw.
3. Prompt assembly. The engine renders `prompt.md` with the declared vars only: the evidence table as TSV text, the vocabulary as a list, the item list, the context JSON. Rendering uses strict undefined-variable checking, so an undeclared variable is an error rather than an empty string. The rendered prompt is hashed and stored once, content-addressed (9.4). The template path and its git blob hash are recorded, so `git log -p` on the template answers why two runs differed.
4. The judgment harness answers the prompt `replicates` times with `schema.json` as a hard output constraint. With a direct adapter the engine makes the calls itself. With the dispatch adapter (10.2) the engine writes one request file per replicate, exits with code 20, and resumes when the operator harness has had fresh-context subagents write the responses. Either way each replicate is meant to be an independent sample, each response is stored, hashed, and validated, and the invocation row records which path was used. A response that fails validation is retried once with the validation error appended to the prompt; a second failure records the replicate as `invalid`, which counts as disagreement (8.4).
5. `post.*` runs if present, for restructuring only. Its output hash and each replicate's hash are both stored, so a post-processor that changed a label would be visible in the trace.
6. Consensus is computed per item (8.4). Items that disagree, abstain, or fall under the confidence floor become holds.
7. Post-gate predicates run on every replicate and on the consensus.
8. If any hold exists the step is `held` and `run` exits with code 10.

Batching: `all_items` puts every item in one prompt so the model can reason relatively across clusters, which is how a human annotator works. `per_item` gives cleaner independence at higher cost. The manifest chooses and the trace records which.

### 3.6 Report modules

As 3.5 with one replicate and no consensus. Prose is checked against the tables it cites. Report modules run last, and their outputs are what `deliver` marks `is_final` by default.

## 4. State

### 4.1 Contents

```json
{
  "state": 1,
  "run_id": "01J9K…",
  "after_step": "05_cluster",
  "objects": {
    "object": {"type": "anndata", "digest": "blake3:…", "summary": { "…": "extractor output, 4.2" }}
  },
  "design":    { "…": "design.yml" },
  "objective": { "…": "objective.yml" },
  "history": [
    {"step": "01_qc", "operation": "qc_filter", "params": {"min_counts": 50, "max_pct_mt": 15}, "output_digests": {"object": "blake3:…"}},
    {"step": "02_normalize", "operation": "normalize", "params": {"method": "log1p_cpm"}, "output_digests": {"object": "blake3:…"}}
  ],
  "env": {"digest": "sha256:…", "executor": "apptainer"},
  "mode": "pipeline",
  "profile": "standard"
}
```

`history` is what makes `qc.filter_ordering` (cells filtered after normalization) and `de.selection_bias` (a test between clusters derived from the same counts, with no split) decidable. Both read the sequence of operations, not the object.

### 4.2 Extraction

The engine never opens a data object. After any step that produces an object output, the engine runs the plugin's state extractor for that object type as a script inside the module's environment, and the script prints JSON. The engine stores the JSON, its digest, and the extractor name and version.

The output has an engine-known envelope and a plugin-defined body:

```json
{
  "extractor": "sc.anndata@1",
  "type": "anndata",
  "n_obs": 48210,
  "n_var": 1000,
  "fields": {
    "obs": {
      "core_id":  {"dtype": "category", "n_unique": 24},
      "block_id": {"dtype": "category", "n_unique": 12},
      "region":   {"dtype": "category", "n_unique": 2, "levels": ["tumor", "margin"]},
      "leiden":   {"dtype": "category", "n_unique": 14}
    },
    "obsm": ["spatial", "X_pca", "X_umap"],
    "layers": ["counts"],
    "uns_flags": {"log1p": true, "hvg": true, "neighbors": true, "leiden_random_state": 20260910}
  },
  "counts_per_group": {
    "region": {"tumor": {"block_id": 6, "core_id": 12}, "margin": {"block_id": 6, "core_id": 12}}
  },
  "domain": { "…": "anything else the plugin's predicates want" }
}
```

`counts_per_group` is what `obj.feasibility` reads: units of each declared unit type remaining per level of each declared factor. The extractor computes it from `design.yml`, which it receives as an argument.

Cost is one pass per object output per step. Gate evaluation itself reads stored JSON and costs nothing beyond the predicate functions. This answers the design note's open question about digesting state for large objects: digest once, after the step, never inside a gate call.

### 4.3 History

Append-only. A forked run inherits the parent's history up to the fork point with `inherited: true` on each inherited entry.

## 5. Actions

```json
{
  "action_id": "01J9K…",
  "run_id": "01J9K…",
  "step_id": "07_annotate",
  "attempt": 1,
  "operation": "annotate_clusters",
  "module": "annotate-cluster@0.3.1",
  "parameters": {},
  "param_source": {},
  "ticket": null,
  "inputs": {"markers": "blake3:…", "context": "blake3:…"},
  "input_digest": "blake3:…",
  "params_hash": "blake3:…",
  "proposed_by": "pipeline",
  "rationale_ref": null
}
```

`proposed_by` is `pipeline` when every parameter took its committed default and `agent` when the operator proposed any value; `param_source` records, per parameter, `default` or `agent`. `rationale_ref` points to the agent's stated reason for its choices when one was supplied with `propose`, and is never read by a predicate. `ticket` is set for operator-run steps. The fields are shaped so that open mode, where the agent proposes the operation as well as the parameters, uses the same record without a migration. Every action is written to the trace before its pre-gate runs, so rejected proposals are kept.

`attempt` increments when a step is retried after a rejection or in a fork. Parameter changes between attempts are a diff of `parameters`.

## 6. Gate

### 6.1 Predicate contract

```python
@dataclass(frozen=True)
class GateContext:
    phase: Literal["pre", "post"]
    project: ProjectConfig  # mode, profile, roles
    objective: Objective
    design: Design
    state: State  # pre: before the action; post: after it
    action: Action
    history: tuple[StepRecord, ...]
    output: OutputBundle | None  # post only: validated outputs, replicates, consensus, prose
    policy: Policy  # ranges and criteria predicates may read


@dataclass(frozen=True)
class Verdict:
    fired: bool
    reason: str | None = None
    evidence: dict = field(default_factory=dict)  # JSON-serializable: exactly what was inspected
    severity: str | None = None  # optional; policy may map severities differently


@predicate(
    id="de.replication_unit",
    version=3,
    scope=["test_differential_expression"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["test_differential_expression.replicate_unit"],
    invariant=False,
)
def replication_unit(ctx: GateContext) -> Verdict:
    if (
        ctx.design.has_biological_replicates
        and ctx.action.parameters.get("replicate_unit") == "cell"
    ):
        return Verdict(
            True,
            "cell-level test with declared biological replicates",
            {"declared_replication_unit": ctx.design.replication_unit, "proposed": "cell"},
        )
    return Verdict(False)
```

Predicates are pure: no I/O, no clock, no randomness, no network. The engine enforces this loosely (a short wall-clock budget, no file handles in the context) and the test suite enforces it strictly (every predicate ships a must-fire fixture and a must-pass fixture).

Nothing in the context is the data object. Nothing in the context is the agent's reasoning as a decision input (6.8).

### 6.2 Two phases

The pre-gate answers "may this action run in this state?" The post-gate answers "is what it produced admissible as input to anything downstream?" Same contract, same dispositions, same trace table.

The design note describes the pre-gate. The implementation plan's engine-shipped checks (schema conformance, numeric claims, vocabulary resolution) are post-gate checks. Both are needed: a valid action can produce an invalid output, and a judgment module's output cannot be gated before it exists.

A fired post-gate `block` marks the step's outputs `rejected`. They stay in the trace, but no downstream step may reference them, and the run halts (Commandment 9).

### 6.3 Dispositions: default and effective

A predicate declares a default disposition. The policy resolves the effective disposition for the project's profile. Both are recorded on every verdict together with the policy digest, so a later re-audit can ask what would have happened under a different policy.

| Effective | Meaning when the predicate fires |
|---|---|
| `log` | Recorded. Nothing else. |
| `flag` | A hold of kind `flag` is created (7.2). The step does not proceed until a review accepts it. The flag appears in the coverage report whether accepted or not. |
| `block` | The step does not proceed. No review can clear it. |

The only way past a block is a diff: change the parameter, the design, or the policy in the method repo, commit, and run again. The record of how a blocked choice was resolved therefore lives in git with an author and a reason, not in a review row that says "accepted." In the `exploratory` profile most blocks become flags, which is the sanctioned way to proceed past one with a recorded justification.

### 6.4 Profiles and the policy file

`method/policy.yml`, versioned in the method repo:

```yaml
policy: 1
version: 0.1.0
invariant: [repro.*, topo.*]         # never remapped by any profile
profiles:
  strict:
    remap: {flag: block}
    params: locked                   # agent may not change any parameter from its default
    replicates_min: 3
    agreement: standard
    qc_ranges: strict
    relayed_review: false            # 7.5
  standard:
    remap: {}
    params: ranged                   # agent proposes within declared ranges; out of range blocks
    replicates_min: 3
    agreement: standard
    qc_ranges: standard
    relayed_review: true
  exploratory:
    remap: {block: flag}
    params: free                     # out of range flags; undeclared parameters still block
    replicates_min: 3
    agreement: relaxed
    qc_ranges: wide
    relayed_review: true
overrides:                           # per-predicate exceptions, each with a reason
  qc.threshold_range:
    exploratory: {disposition: log, reason: "exploration is where thresholds get chosen"}
ranges:                              # values plugin predicates read, keyed by qc_ranges
  qc.max_pct_mt: {strict: [5, 15],   standard: [5, 20],  wide: [5, 30]}
  qc.min_counts: {strict: [200, 2000], standard: [50, 2000], wide: [20, 5000]}
confidence_criteria:                 # 8.2
  high:   {min_supporting: 3, max_contradicting: 0}
  medium: {min_supporting: 2, max_contradicting: 1}
  low:    {min_supporting: 1}
agreement:                           # 8.4
  standard: {hold_on: [label_disagreement, any_abstain, any_low, any_invalid]}
  relaxed:  {hold_on: [label_disagreement, all_abstain, any_invalid]}
```

Resolution order for a fired predicate: an explicit `overrides` entry for (predicate, profile) if present; otherwise the profile's `remap` applied to the predicate's default; predicates matching `invariant` skip the remap. `open` with `strict` is refused at init regardless of the policy file.

Policy identity recorded per run: `policy_version` (the semver above) and `policy_digest = blake3(policy.yml contents ∥ sorted "id@version" of every registered predicate)`. A run governed by a different predicate set gets a different digest even when `policy.yml` is unchanged.

### 6.5 Engine-shipped predicates

Domain-free, live in the engine, apply to every plugin.

| ID | Phase | Scope | Fires when | Default |
|---|---|---|---|---|
| `topo.undeclared_step` | pre | * | the action's step is not in the bound topology, or the module's `modes` excludes the project mode | block, invariant |
| `topo.predecessor_incomplete` | pre | * | an input references a step that is not `completed` | block, invariant |
| `repro.dirty_tree` | run open | * | the method repo has uncommitted changes and `--allow-dirty "<reason>"` was not given | block, invariant |
| `repro.env_unpinned` | pre | * | the executor cannot report an environment digest for the module's env | block, invariant |
| `repro.seed_unset` | pre | modules with `stochastic: true` | `seed_param` is missing or null in the action | block, invariant |
| `repro.input_digest_mismatch` | run open, pre | * | an input's current hash differs from the recorded hash | block, invariant |
| `repro.intermediate_dropped` | post | * | a step consumed an object, retained no object output, and a later step needs one | flag |
| `out.schema_conformance` | post | * | an output declared with a schema fails validation | block |
| `judg.evidence_exists` | post | judgment | a non-abstained item has zero supporting refs, or a ref does not resolve to a cell of the declared evidence | block |
| `judg.vocabulary_resolves` | post | judgment | a label is not in the module's declared vocabulary | block |
| `judg.confidence_consistent` | post | judgment | declared confidence exceeds what `confidence_criteria` allows for the evidence counts | flag |
| `judg.numeric_claims_match` | post | judgment, report | a numeral in rationale or prose matches no `value` in the referenced evidence, after rounding to the written precision | block |
| `judg.replicates_below_min` | post | judgment | fewer valid replicates than the profile's `replicates_min` | block |
| `judg.items_incomplete` | post | judgment | an item from `items_from` has no judgment in some replicate | block |
| `judg.considered_set_missing` | post | judgment with `considered_set: true` | the output carries no denominator record | block |
| `param.undeclared` | pre | * | the proposal includes a parameter the module's schema does not declare | block, invariant |
| `param.locked_changed` | pre | * | a parameter with no `range`, or any parameter under `params: locked`, differs from its default | block |
| `param.out_of_range` | pre | * | a proposed value is outside the declared range or options | block (flag under `params: free`) |
| `exec.plan_drift` | post | operator-run steps | the evidence shows parameters, seed, or container different from the admitted Action | block |
| `exec.script_drift` | post | * | the module script that ran (hashed by the engine before running it, or at `submit`) differs from the script present when the run opened; added 2026-09-09 | block |
| `repro.env_unverified` | post | operator-run steps | the reported container or lockfile cannot be matched to the environment manifest | flag |
| `init.contrast_undeclared` | init | project | a contrast names a factor not in the design | block |
| `init.level_undeclared` | init | project | a contrast names a level the design does not list for that factor | block |
| `init.replication_unit_undeclared` | init | project | the objective's replication unit is not a declared design unit | block |
| `init.column_missing` | init | project | a design column is absent from the raw input, per one extractor pass at init | block |
| `init.question_unsupported` | init | project | the bound pipeline does not declare the objective's question | block |
| `init.deliverable_unproduced` | init | project | a declared deliverable is produced by no step | block |
| `init.reference_mismatch` | init | project | a reference in the inputs does not match the build the pipeline expects | block |
| `obj.feasibility` | pre, post | * | `counts_per_group` for any level of any contrast is below `min_n_per_group` | block |
| `obj.deliverable_unreachable` | pre | * | no remaining step produces a declared deliverable | flag |
| `prov.orphan_artifact` | deliver | * | an artifact proposed as final has no sidecar | block |

`obj.feasibility` runs pre-gate on every step (cheap, catches a state that is already infeasible) and post-gate on every step (catches the step that made it infeasible, before anything downstream runs). This is the forward-feasibility idea from the design note in its simplest honest form: it does not predict what a filter will do, it checks what the filter did before the next step can start.

The domain starter set (implementation plan 4.1) and the spatial set (9.2) ship in `stringency-singlecell` and are instantiated in app-1 session 5.

### 6.6 Coverage declarations

Every predicate declares `covers`: a list of `operation.param` or `operation.*`. Every module declares `decision_points`: the parameters that are analysis choices rather than plumbing. Coverage for a run is computed per executed step, per decision point: does at least one evaluated predicate cover it? The coverage report (12.2) lists the uncovered decision points by name. "No coverage for normalization method selection" becomes a computed line instead of a sentence someone has to remember to write.

### 6.7 What block and flag mean in practice

Jim, running app 1 under `standard`: a block on `de.replication_unit` means the DE step in `pipeline.yml` said `replicate_unit: cell`. Fix the file, commit, `stringency run`. A flag on `de.covariate_omission` (`slide_id` in `design.batch` but absent from the formula) means `run` exits 10; `stringency review` shows the formula next to the batch declaration; you accept with a reason ("slide is confounded with region on this TMA; handled by X") or reject, edit the formula, commit, rerun. The acceptance is bound to the formula hash and the design hash, so the next run with the same formula does not ask again (7.4).

### 6.8 Rationale text

Predicates do not read the agent's rationale as evidence for admissibility. The one predicate that touches rationale, `judg.numeric_claims_match`, treats it as the object under test and checks it against the evidence table. Rationale may be validated. It is never trusted.

## 7. Step lifecycle, holds, review

### 7.1 Step states

| From | Event | To |
|---|---|---|
| pending | every input step is `completed` | proposed (Action written) |
| proposed | pre-gate: nothing fired, or only `log` | admissible |
| proposed | pre-gate: `flag` fired | held (kind `flag`) |
| proposed | pre-gate: `block` fired | blocked |
| admissible | engine runner starts the executor, or direct judgment calls begin | running |
| admissible | operator runner: ticket issued, job spec printed; `run` exits 21 | awaiting_execution |
| awaiting_execution | `submit <ticket>` with all declared outputs present | running (evidence parsing, extraction) |
| admissible | dispatch adapter writes request files; `run` exits 20 | dispatching |
| dispatching | every response file present on the next `run` | running |
| running | script exit 0, outputs hashed; or all replicates collected | produced |
| running | non-zero exit or timeout | failed |
| produced | post-gate passes and no item holds | completed |
| produced | post-gate `flag`, or any item hold | held |
| produced | post-gate `block` | rejected |
| held | every hold reviewed `accept` or `override` | admissible (pre-phase hold) or completed (post-phase hold) |
| held | the last item hold of a judgment step reviewed `accept` or `override` | the consensus output is rewritten from the decided consensus and the post-phase gate is evaluated on it: nothing fires, completed; a flag fires, held (the flag holds open now); a block fires, rejected |
| held | any hold reviewed `reject` | blocked (pre) or rejected (post); attempt closed |
| blocked, rejected, failed | new attempt after a commit or a fork | proposed |

Run status is derived: `held` if any step is held; `blocked` or `failed` if the frontier is; `completed` when every step is completed; otherwise `running`.

`stringency next` returns the first `pending` step whose inputs are complete, or the current hold, block, or failure with its reason. `run` loops on `next` until it returns something other than a runnable step, then exits with the matching code (14.2). Every transition writes a `step_events` row in the same transaction as the status change.

### 7.2 Hold kinds

| Kind | Source | Granularity | Resolved by |
|---|---|---|---|
| `flag` | a predicate whose effective disposition is flag | step | accept with reason, or reject |
| `self_uncertain` | a judgment item abstained or reported low confidence | item | accept one replicate's call, override with a correction, or reject the step |
| `run_disagreement` | replicates diverged on an item | item | accept one call, override, or reject |
| `confirm` | the init echo-back (2.7), in every profile; also any module that declares `confirm: true` | project or step | accept or reject; a `run` cannot open while the init confirm is unresolved |

Every hold records the reviewer role it waits on. `status` shows who is waited on. `run` cannot clear any hold.

### 7.3 Review verdicts

`stringency review` walks unresolved holds oldest first. For each it prints the evidence the model saw, every replicate's call with its confidence and cited evidence, the predicate's reason and evidence if a flag, and the relevant slice of the table. Verdicts:

| Verdict | Requires | Effect |
|---|---|---|
| `accept` | a reason (flag) or a chosen replicate (item) | hold cleared; consensus takes the chosen label with `source: accepted` |
| `override` | a correction, validated against schema and vocabulary at entry, and a reason | hold cleared; consensus takes the correction with `source: override` |
| `reject` | a reason | attempt closed; a new attempt requires a change to the method or a fork |
| `defer` | nothing | hold stays; the deferral is recorded so the queue shows it was seen |

`reason` is free text in v1. Once the override corpus shows recurring categories, `reason_code` becomes an enum in the method repo's vocabulary and the free text moves to `reason_detail`.

### 7.4 Binding and reuse of verdicts

Every review row stores `bound_module_version`, `bound_input_digest`, `bound_params_hash`, and, for item holds, `bound_item_evidence_digest`. Before creating a hold, the engine looks for a prior `accept` or `override` on the same hold kind, module version, and bindings. If one exists, the new hold is created and immediately resolved by reference (`resolved_by_review = prior id`, `via = rebind`) and the step proceeds.

A rerun after an unrelated change therefore does not re-ask settled questions, and a prompt-template change (which bumps the module version) invalidates every prior sign-off on that module. Approval expires when its inputs change because the check is a hash comparison rather than a judgment.

### 7.5 Reviewer identity

The reviewer is the OS user running `review`, checked against `roles.reviewer` (or `roles.owner` when they coincide). The row records user, host, timestamp, and `via`.

`via: tty` when `review` runs attached to a terminal. `via: relayed` when it runs non-interactively with `--attest`, which is the path a harness skill uses after presenting the hold to the person in chat and receiving an explicit yes. Relayed rows record the operator harness and session reference.

A third value, `web`, means the verdict was entered through a form served by `stringency review --serve`, a process the reviewer started under their own account, protected by a per-start token and reachable on loopback or through a tunnel. It proves which account's process recorded the verdict, as `tty` does, and nothing more: an agent with shell access as that user could start the server, read the token, and post. That is the boundary `tty` rests on as well, which is why profiles treat `web` like `tty`, strict included, and why the trace records `via` at all. The speed bump is the account, not the form. Relayed reviews must carry the operator's session reference; `--attest` without one is refused. (Amendment approved 2026-09-15; `spec/plans/ux-two-audiences.md` section 8.)

Profiles with `relayed_review: false` (strict by default) refuse `--attest`; manuscript-bound sign-offs happen at a terminal. Standard and exploratory allow relayed verdicts and mark them visibly, which is the honest rendering of "a person said yes in the chat." This is a speed bump, not a cryptographic guarantee: an agent with shell access as the reviewer's user could fabricate an attestation. The trace makes every relayed verdict findable, and the skill instructions forbid running `review` without a confirmation in the conversation. The design says this plainly rather than implying a stronger property.

### 7.6 Override corpus

`stringency status --overrides [--module <name>]` reports override and rejection rate per module version over time. This is the primary quality metric for a judgment module and the input to prompt revisions. The commit-message convention from the git note applies: a prompt change cites the review IDs that motivated it.

## 8. Judgment records

### 8.1 Base schema

Every judgment module's `schema.json` must include the engine base; lint checks by structural inclusion.

```json
{
  "type": "object",
  "required": ["item_id", "label", "confidence", "abstain", "supporting_evidence", "contradicting_evidence", "rationale"],
  "properties": {
    "item_id": {"type": "string"},
    "label": {"type": ["string", "null"]},
    "ontology_id": {"type": ["string", "null"]},
    "confidence": {"enum": ["high", "medium", "low", "abstain"]},
    "abstain": {"type": "boolean"},
    "supporting_evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence_ref"}},
    "contradicting_evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence_ref"}},
    "rationale": {"type": "string", "maxLength": 1200}
  },
  "if": {"properties": {"abstain": {"const": true}}},
  "then": {"properties": {"label": {"type": "null"}, "confidence": {"const": "abstain"}}},
  "$defs": {
    "evidence_ref": {
      "type": "object",
      "required": ["table", "row", "column", "value"],
      "properties": {
        "table": {"type": "string"}, "row": {"type": "string"},
        "column": {"type": "string"}, "value": {"type": ["string", "number"]}
      }
    }
  }
}
```

A module adds fields (for example `alternative_labels` or `niche_composition_note`). It cannot remove or weaken these.

### 8.2 Confidence

An ordinal with criteria in the policy (6.4), not a float. `judg.confidence_consistent` fires when a replicate claims more than its evidence count supports. The criteria are deliberately mechanical: they do not judge whether the evidence is good, only whether the confidence label is consistent with how much of it was cited. Judging whether the evidence is good is what review and controls are for.

### 8.3 Evidence references and numeric claims

An evidence ref points at one cell of a table the model was shown: `{"table": "markers", "row": "cluster_7", "column": "CD8A_logfc", "value": 2.31}`. `judg.evidence_exists` resolves each ref against the stored evidence table and fires if the cell does not exist or `value` disagrees with it. `judg.numeric_claims_match` extracts numerals from `rationale` and requires each to match some referenced `value` after rounding to the precision written. "CD8A log fold change of 2.3" with a ref carrying 2.31 passes. "2.8" blocks.

This is Commandment 10 (assertions shown using the data) and Commandment 6 (models out of the arithmetic) as a check rather than a hope.

### 8.4 Agreement and consensus

Per item, across the valid replicate outputs:

| Condition | `standard` agreement | `relaxed` agreement |
|---|---|---|
| all labels equal, no abstain, no low | agreed | agreed |
| labels differ | hold `run_disagreement` | hold `run_disagreement` |
| some abstain, the rest agree | hold `self_uncertain` | agreed; abstention logged |
| all abstain | hold `self_uncertain` | hold `self_uncertain` |
| any low confidence | hold `self_uncertain` | logged |
| any invalid replicate | hold `run_disagreement` | hold `run_disagreement` |

There is no majority vote in either setting. Two of three with one dissenter is a hold under `standard`, because the dissent is the information.

The consensus record per item:

```json
{
  "item_id": "cluster_7",
  "label": "CD8-positive, alpha-beta T cell",
  "ontology_id": "CL:0000625",
  "source": "agreed",
  "replicate_labels": ["CD8-positive, alpha-beta T cell", "CD8-positive, alpha-beta T cell", "CD8-positive, alpha-beta T cell"],
  "replicate_confidence": ["high", "high", "medium"],
  "review_id": null
}
```

`source` is one of `agreed`, `accepted`, `override`, `unresolved`. Downstream modules consume consensus, never individual replicates. An `unresolved` item cannot exist in a completed step, because a step with open holds cannot complete.

The consensus output file is written at judgment time, so a held item is filed in it as `unresolved`. When the last item hold of the step is accepted or overridden, the engine rewrites the file from the `consensus` table, records it as a new artifact and marks the judgment-time one `superseded`, so the file a downstream step binds is the decided consensus (added 2026-09-23). Post-phase predicates run at judgment time on the pre-review consensus; a `flag` verdict raised while item holds are open does not open a hold then. Once the item holds settle the post-phase gate is evaluated again on the decided consensus, and the flags that fire open their holds at that point, with the evidence the reviewer decided. A `block` takes effect at either evaluation.

## 9. Trace

Complete, append-only, written whether or not an action ran. The rejections are the most useful records for improving the predicate set, and a trace that kept only executed actions would discard them.

### 9.1 Captured at run open

Run ID, project ID, parent run ID; method repo remote, tag, SHA, dirty flag, `allow_dirty_reason`; the hash of every module entry script as it is on disk at open (`captures.script_blobs`, added 2026-09-09); hostname and OS user; operator harness kind, version, and session reference when the wrapper exposes them (10.1); wall-clock start; every input re-hashed and verified; policy version and digest; executor kind and the environment digest for every module env in the topology, resolved up front so a missing image fails at open rather than at step 9; stringency version.

### 9.2 Captured per step

The Action; every predicate verdict in both phases with default and effective disposition, reason, and evidence; the executor invocation (command, env digest, exit code, duration, stdout and stderr paths); output paths and hashes; the state summary and its digest; holds created and how each resolved; attempt number.

### 9.3 Captured per invocation

Template path and git blob hash; rendered prompt hash (text stored once in `messages`); model requested and model resolved as returned by the API or as reported by the subagent; sampling settings; harness adapter and version; `via` and `isolation`; nonce check result; request and response file paths under dispatch; the subagent's `reported` block verbatim; response hash (text in `messages`); schema validity; tokens in and out where available; duration; replicate index. The judgment harness receives a prompt and returns JSON, so tool calls are not expected in v1; the column exists for adapters that expose them.

### 9.4 Tables

```
projects(project_id PK, path, pipeline_name, pipeline_version, pipeline_digest, method_repo, method_tag,
         mode, profile, owner, reviewer, judgment_harness, executor, objective_json, design_json,
         splits_json, created, stringency_version)

runs(run_id PK, project_id, parent_run_id, fork_at_step, delta_json, git_sha, git_dirty, allow_dirty_reason,
     host, user, operator_harness, operator_version, operator_session_ref,
     started, ended, status, env_digest, policy_version, policy_digest, stringency_version)
run_events(run_id, seq, event, payload_json, ts)                                  -- append-only

steps(run_id, step_id, module, module_version, operation, status, attempt, started, ended,
      PK(run_id, step_id))
step_events(run_id, step_id, seq, event, payload_json, ts)                         -- append-only

actions(action_id PK, run_id, step_id, attempt, operation, module, params_json, params_hash,
        inputs_json, input_digest, proposed_by, rationale_ref, proposed_at)        -- append-only

state_snapshots(snapshot_id PK, run_id, step_id, phase, extractor, extractor_version,
                summary_json, digest, ts)                                          -- append-only

predicate_results(run_id, action_id, phase, predicate_id, predicate_version, fired,
                  default_disposition, effective_disposition, reason, evidence_json,
                  severity, policy_digest, ts)                                     -- append-only

executions(action_id, runner, ticket, env_name, env_digest, expected_env_digest, env_status, command, script_blob,
           exit_code, duration_ms, stdout_path, stderr_path, evidence_paths_json, observed_params_json, ts)
           -- runner: engine | operator; env_status: verified | as_reported; env_digest only when verified,
           -- expected_env_digest always (added 2026-09-08, migration 2); script_blob: hash of the
           -- module script as it ran (added 2026-09-09, migration 3)                             -- append-only

holds(hold_id PK, run_id, step_id, item_id NULL, kind, reason, waits_on_role,
      created, resolved_by_review NULL, resolved_via NULL)

reviews(review_id PK, hold_id, run_id, step_id, item_id, reviewer, host, via,
        operator_session_ref, ts, verdict, correction_json, reason, reason_code NULL,
        bound_module_version, bound_input_digest, bound_params_hash,
        bound_item_evidence_digest)                                                -- append-only

invocations(invocation_id PK, run_id, step_id, action_id, replicate, template_path, template_blob,
            prompt_hash, model_requested, model_resolved, harness_kind, harness_version,
            via, isolation, nonce, nonce_ok, request_path, response_path, reported_json,
            sampling_json, response_hash, schema_valid, tokens_in, tokens_out, duration_ms,
            bit_reproducible, tool_calls_json, ts)                                 -- append-only

messages(hash PK, text)                                                            -- content-addressed, append-only

judgments(run_id, step_id, item_id, replicate, label, ontology_id, confidence, abstain,
          supporting_json, contradicting_json, rationale_ref, schema_valid, extra_json)   -- append-only

consensus(run_id, step_id, item_id, label, ontology_id, source, replicate_labels_json,
          replicate_confidence_json, review_id NULL, PK(run_id, step_id, item_id))

artifacts(artifact_id PK, run_id, step_id, action_id, path, hash, size, kind, is_final,
          provisional, sidecar_path, operator_session_ref, operator_artifact_ref)

controls_runs(control_run_id PK, module, module_version, control_name, kind, run_id,
              passed, metrics_json, ts)                                            -- append-only

deliveries(delivery_id PK, run_id, path, coverage_hash, methods_hash, index_hash, ts)  -- append-only

policy_snapshots(policy_digest PK, policy_version, content_json, predicate_set_json, first_seen)

schema_migrations(version PK, applied)
```

One database per project at `prov/run.db`, WAL mode, never on CIFS. A thin index on PROTSEQ can point at project databases later if cross-project queries are ever needed.

### 9.5 Append-only enforcement

Triggers raise on `UPDATE` and `DELETE` for every table marked append-only above. `runs`, `steps`, `holds`, `consensus`, and `artifacts` have mutable status columns, and each mutation writes its event row first, in the same transaction. Migrations are forward-only and recorded in `schema_migrations`.

### 9.6 Artifacts and sidecars

Every file the engine writes under `runs/` gets a sidecar `<name>.stringency.json` holding run ID, step ID, action ID, hash, and engine version. `deliver` copies finals together with their sidecars. An artifact without a sidecar is an orphan and `deliver` refuses to mark it final (`prov.orphan_artifact`). Figures made in the harness session from delivered tables are cross-linked by writing the run ID into the artifact record (the skill does this) or remain exploratory.

### 9.7 Policy snapshots and re-audit readiness

Every distinct policy digest is stored with its full content and predicate set. Re-audit (Phase D) replays stored actions and state snapshots through a later predicate set. The trace records full state summaries, full actions, and full outputs by hash now, rather than only the fields current predicates read, which is the design note's argument for recording more state than the current rules need.

## 10. Harness and executor

### 10.1 Two harnesses, not one

The implementation plan's list of harness implementations (`claude-science`, `claude-code`, `api`, `openai-compatible`, `mock`) mixes two roles.

The operator harness is whatever drives the CLI: a Claude Science session, Claude Code, or a person at a shell. The engine does not call it; it calls the engine. The run records it (`operator_harness`, `operator_version`, `operator_session_ref`) from environment variables the skill wrapper sets (`STRINGENCY_OPERATOR`, `STRINGENCY_OPERATOR_VERSION`, `STRINGENCY_SESSION_REF`).

The judgment harness is how a rendered judgment prompt gets answered. Two families exist, bound at init:

Direct adapters (`api`, `openai-compatible`, `mock`): the engine calls the model itself, in-process, and receives the response. The engine controls what the judge sees and how many independent calls are made.

The dispatch adapter (`subagent`): the engine writes request files and stops; the operator harness spawns one fresh-context subagent per request; each subagent writes a response file; the engine resumes and validates. The operator's subscription pays for the calls and no API key is needed.

Decision: `subagent` is the default for this deployment. Claude Science can spawn subagents, and the lab has no budget for a separate API path. `api` remains fully implemented so that a fork with a budget, or a future run that needs the structural guarantee, can switch by editing one line at init. The two families share the `Invocation` record and every downstream check, so the choice changes how the trace is marked and nothing else.

What the principle "the model sees the table, never the matrix" protects, and how each family protects it:

| Property | Why it matters | Direct adapters | Dispatch adapter |
|---|---|---|---|
| The judge's input is exactly the recorded evidence bundle | Every claim can be checked against a finite hashed artifact; Commandment 6 holds because there is nothing else to compute from | Enforced by construction | Enforced by the subagent's tool restriction where the operator supports one; otherwise reported. Post-gates (`judg.evidence_exists`, `judg.numeric_claims_match`) still verify the output against the bundle regardless |
| The judge does not carry the session's expectations | A context that knows what you hope to find tends to find it | Enforced | Enforced by fresh subagent context; the nonce check detects a rewritten prompt but not an appended one, so this is reported, not proven |
| Replicates are independent samples | Three calls sharing context are one sample asked three times | Enforced | One subagent per replicate; independence as reported |

Under dispatch, the invocation row carries `via: subagent` and `isolation: as_reported`, and the coverage report says so. The compensating control is the eval layer: negative controls (shuffled marker tables, permuted coordinates) test whether the module confabulates, and they work identically whichever family invoked the model. Dispatch shifts weight from a structural guarantee in the gate to an empirical one in the controls, and the trace records that this is what happened.

### 10.2 Judgment harness adapters

```
Harness.invoke(prompt: str, schema: dict, *, sampling: Sampling) -> Invocation           # direct family
Harness.dispatch(requests: list[Request]) -> None; Harness.collect(requests) -> list[Invocation]   # dispatch family

Invocation:
  structured: dict | None      raw_text: str        schema_valid: bool
  model_requested: str         model_resolved: str  harness_kind: str    harness_version: str
  tokens_in: int | None        tokens_out: int | None                    duration_ms: int | None
  via: direct | subagent       isolation: enforced | as_reported          nonce_ok: bool | None
  tool_calls: list
```

`mock`: canned responses keyed by (template hash, item ID, replicate) from a YAML fixture; deterministic; used by every test. It implements both families so the dispatch path is testable without an operator: in dispatch mode it writes the response files itself when `collect` is called.

`subagent` isolation, as observed on 2026-09-08: a Claude Science delegate starts with a fresh context and can be given only the request file path, but cannot be tool-restricted to that one file. Isolation is therefore instructional, and the engine records it as `as_reported`; the `reported` block (model, harness, tools, `saw_conversation`) is the delegate's own account. `enforced` is reserved for a harness that can prove the restriction.

`api`: the Anthropic Messages API with `schema.json` enforced as structured output. Claude Code should read the current SDK documentation for the structured-output mechanism at build time rather than rely on memory. The model alias is set per project (and may be overridden per module); the resolved model string from the response is what gets recorded. Installed as the `stringency[api]` extra.

`openai-compatible`: Phase D.

`subagent`: the dispatch adapter. The request and response contract:

```
runs/<run_id>/<step_id>/dispatch/
  manifest.json          {"step_id", "action_id", "replicates": 3, "schema": "schema.json", "nonce_prefix": "…"}
  req_1.json             {"replicate": 1, "nonce": "01J9K…-1", "prompt": "<rendered prompt>", "schema": {…}}
  req_2.json
  req_3.json
  resp_1.json            written by the subagent: {"nonce": "01J9K…-1", "structured": {…},
                          "reported": {"model": "…", "agent": "…", "tools_available": […], "saw_conversation": false}}
  resp_2.json
  resp_3.json
```

The prompt text ends with a fixed instruction the engine appends: return only JSON matching the schema, include the nonce verbatim, and report in `reported` what model and tools you had. `run` writes the requests, marks the step `dispatching`, prints the directory and the replicate count, and exits 20. The skill wrapper then spawns one fresh subagent per request, with tools restricted to reading that request file and writing its response file where the operator harness supports tool restriction, and passes the request file path rather than the prompt text so the session agent never handles the prompt. On the next `run`, the engine reads every response, validates the schema, checks `nonce` equals the request's nonce, hashes the response into `messages`, and proceeds exactly as for a direct invocation. A missing or unparseable response after the operator reports completion marks that replicate `invalid`. Requests are never rewritten on resume; a step re-dispatched after an `invalid` replicate gets fresh nonces and a new attempt.

The subagent's own `reported` block is stored verbatim and never trusted for anything except the trace. The skill wrapper sets `STRINGENCY_OPERATOR*` so the run records which operator dispatched.

Anything an adapter cannot report is recorded as `unknown`, never guessed.

Judgment reproducibility is stated rather than promised: invocations carry `bit_reproducible: false`, the resolved model is recorded, and replicates are stored. Deterministic steps carry `bit_reproducible: true` when seeded and containerized.

### 10.3 Execution families and the environment digest

Execution mirrors judgment: two families, chosen per module through `runner`, both feeding the same trace.

Operator runner. The agent executes after `propose` and reports through `submit` (3.4). The engine learns about the environment from evidence rather than observation, and the module manifest lists what evidence it expects:

```yaml
evidence:
  - {kind: nextflow_trace, path: "trace.txt"}      # per-process container, exit status, resources
  - {kind: nextflow_log,   path: ".nextflow.log"}   # resolved config, params
  - {kind: job_log,        path: "run.log"}
```

Parsers exist in the engine for `nextflow_trace`, `nextflow_log`, `apptainer_inspect`, and `job_log` (free text, used only to record). From them the engine recovers the parameters used, the container image per process, the seed where a script prints it, and exit codes. A container digest that matches `/data/lab/env/manifest.yml` yields `env: verified`; one that does not, or the absence of any container evidence, yields `env: as_reported` and fires `repro.env_unverified`. Nextflow steps will usually verify; ad hoc scripts usually will not, and the trace says which.

Engine runner. The engine executes through an executor adapter:

```
Executor.run(job: Job) -> ExecResult

Job:        command, env_name, cwd, bind_paths, stdin_json, timeout, resources
ExecResult: exit_code, stdout_path, stderr_path, duration_ms, env_digest
```

`local`: a subprocess in the current environment. `env_digest` is the hash of a `uv.lock` or `renv.lock` in the module's env directory; with neither present the executor reports no digest and `repro.env_unpinned` fires. Development, tests, and extractors during development.

`apptainer`: `apptainer exec --containall --bind <paths> <image.sif> <command>`. `env_digest` is the SIF digest recorded in the environment manifest, verified against the file at run open. Production for engine-run steps, state extractors, and judgment evidence generation.

Extractors and judgment `pre.*` scripts always use the engine runner, because the state every gate reads and the evidence every judge sees must be produced by committed code the engine executed rather than by the party being gated.

The run's `env_digest` is the hash of the sorted set of environment digests used, with `as_reported` entries marked in the digest input so two runs that differ only in verification status do not collide.

### 10.4 Claude Science specifics

The engine assumes the following about Claude Science, taken from implementation plan section 8 and checked by inspection on 2026-09-08 (Phase A exit, BMESEQ): the session's sandbox can execute the CLI but cannot start a container (the user lookup for an Active Directory uid fails inside it and home directories are not mounted), so a project whose executor is `apptainer` is driven through a registered SSH compute host, from the workstation or a laptop; that remote mode is the default for apptainer projects and the integration skill's mode B. Artifacts carry per-version provenance tabs; a reviewer agent does advisory checks; `~/.claude-science` holds session state; files not saved as artifacts are cleared some hours after a session ends.

Skill wrappers set the `STRINGENCY_OPERATOR*` variables so the trace can cross-link. `deliver`'s write-back and the skill's artifact-save step are what keep a durable copy on the array. Nothing else in the engine depends on Claude Science.

Skills are of two kinds. The two engine skills, `stringency-declare` and `stringency-operator`, are the operator's reference and live in the engine repository. One analysis skill per pipeline, rendered from the engine's template and the method repository's `skills/<pipeline>.yml`, lives in the method repository and is what a person loads by describing their experiment; it presents intent, progress, results, and holds in sentences and shows the CLI only on request. Both kinds set the `STRINGENCY_OPERATOR*` variables and neither resolves a hold. (Amendment approved 2026-09-15.)

## 11. Controls

A module ships its controls as `controls/*.yml`.

```yaml
control: 1
name: negative-permuted-coordinates
kind: negative                     # negative | positive | planted
fixture:
  input: {type: anndata, blake3: "5a2f…", path: fixtures/tma_dev_subset.h5ad}
generator:
  tool: permute_coordinates        # plugin tool half (15.1); runs in the module env
  params: {within: core_id, seed: 1}
expect:
  null_output: true                # every item abstains, or nothing is flagged
```

```yaml
control: 1
name: positive-geo-annotated
kind: positive
fixture:
  input: {type: table, blake3: "c07e…", path: controls/fixtures/geo_markers_dev.tsv}
  truth: {path: controls/fixtures/geo_labels_dev.tsv, key: cluster_id, column: author_label,
          mapping: controls/fixtures/author_to_cl.tsv}
expect:
  agreement_min: 0.80              # non-abstained items matching truth after ontology normalization
  abstain_max: 0.20
```

```yaml
control: 1
name: planted-enrichment
kind: planted
fixture:
  input: {type: anndata, blake3: "5a2f…", path: fixtures/tma_dev_subset.h5ad}
generator:
  tool: spike_spatial_enrichment
  params: {effect_sizes: [0.1, 0.25, 0.5, 1.0], seed: 7}
expect:
  detect_at: 0.5                   # the module must flag the planted effect at this size and above
  false_positive_max: 0.05
```

`stringency controls run [--module <name>]` executes each control as a real single-module run in an isolated context under `controls/`, through the same gate and trace machinery, with the `mock` harness refused (controls must exercise the real judgment harness). Results go to `controls_runs`. The command diffs the metrics against the last passing result and exits non-zero on regression, which makes it the regression test.

Fixtures are identified by hash; the path is a hint. The engine resolves fixtures from the project's fixtures directory and the method repo's `controls/fixtures/`. Every generator refuses to touch any hash listed under `design.holdout`, and `lint` warns if a control fixture matches one. Negative controls require no annotation and are the first control to write for every judgment module.

## 12. Deliver

### 12.1 Harvest and write-back

`deliver` requires the run to be `completed`. It copies every artifact marked final (report-module outputs by default, `--include <step>.<output>` for others) with sidecars into `deliver/<run_id>/`, verifies that every deliverable named in the objective is present, writes `coverage.md` (12.2) and `methods.md` (12.3), writes `index.json` linking each file to run, step, action, and hash, and records the delivery. In the Claude Science deployment the skill then saves these as session artifacts, so both stores carry the run ID.

`deliver` also writes `summary.md`: the engine's plain rendering of the run for a reader who will not open the trace: what was analyzed, what ran, what was checked and who decided what, what was delivered, what was not checked. Every sentence is filled from the trace; the file contains no interpretation. (Amendment approved 2026-09-15.)

### 12.2 Coverage report

Generated, fixed in structure, never hand-edited.

```
stringency coverage report
run 01J9K… | project tma-2026 | pipeline spatial-tma@0.2.0 | mode pipeline | profile standard
policy 0.1.0 (blake3:9a41…) | stringency 0.1.0 | method 3f9c1a… (clean)

steps: 11 declared, 11 completed, 0 held, 0 blocked, 0 rejected, 0 failed

gate: 27 predicates registered; 19 in scope for this pipeline; 19 evaluated over 11 steps, both phases
  fired: 0 block, 3 flag, 6 log
  flags:
    de.covariate_omission   08_de        accepted  jrrose5  2026-09-14  tty      "slide confounded with region; see note"
    qc.threshold_range      01_qc        accepted  jrrose5  2026-09-12  tty      "targeted panel; counts floor lowered"
    annot.marker_evidence   07_annotate  override  jrrose5  2026-09-13  relayed  "cluster 11 relabelled from evidence row 11"
  decision points without predicate coverage:
    02_normalize.method, 05_cluster.resolution, 09_neighborhood.radius
  ungated steps: none

judgment:
  annotate-cluster@0.3.1: 14 items x 3 replicates; 11 agreed, 2 self_uncertain, 1 run_disagreement
    reviews: 2 accepted, 1 override; override rate this run 1/14; cumulative for this module version 4/61

controls (last passing run per module version):
  annotate-cluster@0.3.1  2026-09-12  negative-permuted-coordinates: null  positive-geo-annotated: agreement 0.83, abstain 0.07

execution:
  9 steps operator-run (env verified 7, as reported 2: 03_hvg, 06_markers), 2 engine-run; 0 plan drift

reproducibility:
  seeds set on 3/3 stochastic steps; env digest sha256:…; reference GRCm39_M36
  judgment invocations stored (3 per item), not bit-reproducible; via subagent, isolation as reported; model as reported: claude-…

not checked: anything not listed above
```

The last line is deliberate. A tool that checks nineteen things will otherwise be read as having validated the analysis, and manufactured confidence is worse than no tool.

### 12.3 Methods paragraph

The engine owns the structure and fills it from the trace. The plugin supplies domain wording through `describe(action) -> str` per operation. Shape of the output:

> Analysis was run with stringency 0.1.0 using the spatial-tma pipeline v0.2.0 (commit 3f9c1a) under the standard profile and policy 0.1.0. Cells with fewer than 50 counts or more than 15% mitochondrial reads were removed (step 01_qc); counts were normalized by log1p CPM and clustered with Leiden at resolution 0.8 (seed 20260910). Cluster identities were assigned by a language model (model string as recorded; three independent replicates per cluster) shown a marker table and constrained to a declared vocabulary; 11 of 14 clusters were labelled unanimously and 3 were resolved by reviewer jrrose5 (2 accepted, 1 corrected). Differential expression used pseudobulk DESeq2 with block_id as the replication unit and design ~ slide_id + region, Benjamini-Hochberg corrected. Nineteen admissibility predicates were evaluated with no blocks; three flags were reviewed. Run 01J9K…; environment digest sha256:….

The human interventions are in the paragraph because they happened.

## 13. Lint

`stringency lint <module-dir | method-repo>`. Errors fail. Warnings do not.

Errors: manifest fails its schema; `contract` is not 1; `operation` is not in the plugin's vocabulary; a `gates:` entry does not resolve to a registered predicate ID and version; `kind: judgment` lacks `prompt.md`, `schema.json`, or the `judgment` block; `schema.json` does not include the base schema fields with the base constraints (8.1); `replicates` is below the policy minimum; a judgment module lacks a `negative` and a `positive` control; `stochastic: true` without `seed_param`, or `seed_param` missing from `params.schema.json`; the prompt template uses a variable not in `prompt.vars` or declares one it never uses; a script named in the manifest is missing; a pipeline references a module version not present in the repo or a `$steps` output that does not exist; a step's params fail the module's `params.schema.json`; a module lists a mode the plugin does not support.

Warnings: an in-scope registered predicate is not listed in `gates:`; a judgment module has no `planted` control; a control fixture hash appears in `design.holdout`; `decision_points` is empty for a module with more than one parameter.

Lint runs as a pre-commit hook in every method repo and again at `init`.

## 14. CLI

### 14.1 Verbs

| Verb | Arguments | Gate | Trace | Eval |
|---|---|---|---|---|
| `init <path>` | `--method <git-url>@<tag> --pipeline <name> --mode --profile --owner --reviewer --objective <file> --design <file> --inputs <file> [--judgment-harness api] [--executor apptainer] [--drafted-by person\|agent] [--brief <file>]` | binds; refuses open+strict; runs lint | opens the project record | none |
| `declare <dir>` | `--check --method <git-url>@<tag> --pipeline <name> [--objective --design --inputs] [--profile] [--executor] [--json]` | every `init` check, in a temporary directory | none; prints the echo-back | none |
| `run` | `[--until <step>] [--allow-dirty "<reason>"] [--new] [--json] [--responses <file\|->] [--deliver]` | evaluates predicates; halts on hold or block; `--responses` files dispatch responses from one document; `--deliver` delivers on completion | writes everything | triggers replicates |
| `next` | `[--json]` | reports the next step with its plan template (operation, parameter schema with defaults and ranges, vocabulary, declared outputs, expected evidence), or the current hold | reads | none |
| `propose <step>` | `[--set k=v]… [--reason "<txt>"] [--json]` | constructs the Action from defaults plus proposed values; runs the pre-gate; issues a ticket on pass | writes the action and verdicts | none |
| `submit <ticket>` | `--outputs name=path… [--evidence path]… [--command "<string>"] [--json]` | hashes outputs, extracts state, parses evidence, runs plan-drift and post-gate | writes execution, snapshot, verdicts | none |
| `status` | `[--run <id>] [--overrides [--module]] [--json]` | reports holds and who they wait on | reads | override rates |
| `review` | `[--run <id>] [--show] [--hold <id>] [--verdict accept\|override\|reject\|defer --hold <id> [--item <id>] [--replicate n] [--correction <json>] --reason "<txt>"] [--attest] [--serve [--port <n>] [--bind <addr>] [--project <path>]... [--projects <dir>]]` | clears holds by recorded verdict; `--serve` reads holds and records verdicts with `via: web` (7.5) | appends reviews | accumulates override corpus |
| `deliver` | `[--run <id>] [--include <step>.<output>]…` | none | harvests, cross-links | emits coverage report and methods paragraph |
| `fork` | `--from <run> --at <step> [--set k=v]… --reason "<txt>"` | none | opens a child run with delta | none |
| `abandon` | `--run <id> --reason "<txt>"` | none | closes | none |
| `board <root>` | `[--write] [--json]` | none | reads every project under `<root>` (one level; skips `superseded/`, `declarations/`): plan status, latest run and step, open holds and who they wait on, latest delivery's files; `--write` rewrites `<root>/STATUS.md`, which `init`, `run`, `propose`, `submit`, `review`, `deliver` and `abandon` refresh when it exists | none |
| `present` | `[--run <id>] [--hold <id>] [--skills-dir <dir>] [--json]` | none | reads the run's delivery or the hold and renders what the method's delivery skill (14.4) says a person should see; the engine default is the progress sentence and the deliverables | none |
| `lint` | `<path>` or `<repo-or-url>@<tag>` | static checks on a module directory or a method repo; a tagged spec is cloned into a temporary directory first | none | none |
| `controls run` | `[--module <name>]` | real gates on a single module | writes controls_runs | metrics and regression diff |
| `policy show` | `[--profile]` | prints resolved dispositions | none | none |
| `plugins list` | | | | |

`run` remains the loop: it calls `next`, and for operator-run steps it stops at `propose` (exit 21) and resumes after `submit`. `propose` and `submit` are exposed as verbs because the agent needs to call them individually; `fork` and `abandon` are small enough not to count against the five-verb budget; `trace` stays a flag on `status` until someone needs more.

### 14.2 Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 10 | held: a person must act; the message names the hold, the role, and the exact command |
| 11 | blocked: a pre-gate block fired; the message names the predicate and the parameter |
| 12 | rejected: a post-gate block fired; outputs quarantined |
| 13 | failed: a module script exited non-zero or timed out |
| 14 | dirty tree |
| 15 | configuration or binding error |
| 16 | refused: for example `review --attest` under a profile with `relayed_review: false`, or `run` on a closed project |
| 20 | dispatching: judgment requests written; the operator must have subagents answer them, then call `run` again |
| 21 | awaiting execution: a ticket was issued; the operator runs the step and calls `submit` |
| 1 | internal error |

The hold message is terse by design: what is held, who it waits on, the one command that resolves it. It suggests no alternatives, because an interpretable error message invites a different retry.

### 14.3 Output modes

Human-readable by default; `--json` on every verb emits a stable, versioned schema for the skill wrappers. Every write verb prints the run ID.

### 14.4 Delivery skill and the two reading verbs (added 2026-09-18)

A method may state what a person should see: `skills/<pipeline>.yml` in the method repository,
read by `stringency present` and by the operator skill. It never changes what runs.

```yaml
skill: 1
pipeline: <name>
after_delivery:            # rendered by `present --run`, in order
  - title: "..."
    source: <path relative to deliver/<run>/, falling back to runs/<run>/>
    kind: table | json_table | jsonl | text | file
    columns: [...]         # optional subset and order (table, json_table, jsonl)
    format: {col: percent | int | "<n>f"}   # optional per-column formatting
    path: <key of the list of row dicts>    # json_table only; dotted keys allowed; a dict renders as one row
never_show: [run ids, hashes, ...]          # echoed as a footer, a rule for the operator
hold_view:                 # rendered by `present --hold` for the predicate that opened the hold
  - predicate: <predicate id>
    source: <path relative to runs/<run>/>
    kind: table | json_table | jsonl
    columns: [...]
```

`table` reads CSV or TSV; `jsonl` reads one JSON object per line (the judgment log
`judgments.jsonl` is one); a cell that is a dict renders compactly as `k=v; k=v`, a list as
`a, b`. `kind: file` is not printed but listed under "Files to send" with its absolute path. A
missing or malformed skill file, or a missing source, degrades to the engine default with a note
saying so; nothing here can fail a run. `present` and `board` read `stringency.yml`, the trace and
the pipeline file directly and load no plugin, so they work from any engine install.

`board` is the progress view a person keeps open: one row per project under a directory, in
sentences, ids only where a command needs them. The verbs that change a project's state rewrite
`STATUS.md` beside the projects when one exists, so the board is current without the operator
remembering.

## 15. Plugins

### 15.1 Two halves

The predicate half is pure Python with light dependencies, installed in the engine environment: predicates, the design schema, the objective question vocabulary, the operation vocabulary with parameter schemas, label vocabularies, `describe()` functions, and default confidence criteria.

The tool half is a set of scripts the executor runs inside module environments: state extractors per object type, control generators, evidence-table helpers. The plugin declares them as `tools: {name: {script, env}}` and the engine invokes them by name.

The engine environment therefore never contains scanpy, and the plugin's predicates can still be tested against fixture JSON in milliseconds.

### 15.2 Entry points

Plugins register under the `stringency.plugins` entry point group. A plugin object exposes `predicates`, `operations`, `object_types` (each naming its extractor tool), `design_schema`, `objective_questions`, `vocabularies`, `tools`, and `describe`. `stringency plugins list` shows what is loaded. A pipeline's `domain:` must name a loaded plugin.

### 15.3 The toy plugin

Ships in the engine repository under `plugins/stringency-toy` and is what the Phase A exit criterion runs. Its domain is tabular rows with a `group` column and numeric columns. Object type `frame` (CSV) has an extractor that reports row count, columns, and counts per group. Operations: `filter_rows(min_value)`, `summarize_groups()`, `label_groups()` (judgment: assign each group one of five labels from a summary table), `compare_groups(replicate_unit, correction)`. Predicates: `toy.replication_unit` (mirrors `de.replication_unit`), `toy.no_correction` (mirrors `test.multiple_comparison`), `toy.filter_after_summary` (mirrors `qc.filter_ordering`). Controls: a negative with shuffled group labels for `label_groups`, and a positive with known labels. Nothing about biology, and every engine mechanism gets exercised. The build plan specifies it fully.

### 15.4 stringency-singlecell for application 1

A repository separate from the engine: since 2026-09-17 the package `plugins/stringency-singlecell`
in the shared `stringency-plugins` repository, which holds every domain plugin as one package per
subdirectory (amendment approved 2026-09-17; roadmap Lane D item 2). Phase A creates the skeleton (entry point, one extractor stub, an empty predicate registry, a vocabularies directory). The app-1 design sessions fill it. The engine does not depend on any of it.

## 16. Commandments mapped to mechanism, predicate, or eval

The implementation plan's open item: which clauses are machine-checkable. The split, with one caveat first: the implementation plan and the git note cite Commandments 12 and 13 for "a stop, not a warning" and "the confirmation is recorded with identity." In the current Commandments file those are 9 and 12. The references should be corrected when the Commandments are next edited.

| Commandment | Engine mechanism | Predicate(s) | Eval or discipline |
|---|---|---|---|
| 1 pre-specified topology | pipeline mode; `next` routes within the declared graph; parameters have committed defaults and ranges | `topo.undeclared_step`, `topo.predecessor_incomplete`, `param.*` | none |
| 2 everything logged | trace layer; `runs/<id>/summary.md` at close | none | session write-ups in the method repo (`notes/YYYY-MM-DD-hhmm-<slug>.md`), a skill-layer convention |
| 3 git as ledger | SHA and dirty flag at run open; method repo cloned at a tag | `repro.dirty_tree`, `repro.env_unpinned` | commit messages cite review IDs |
| 4 reuse skills | modules are versioned directories; skills wrap verbs | none | lint: prompts are files in the repo |
| 5 judgment handled differently | `repeat`, consensus, item holds | `judg.replicates_below_min`, `judg.considered_set_missing` | override rate |
| 6 models out of the arithmetic | schema has no computed fields; evidence refs point at code-produced cells | `judg.numeric_claims_match`, `judg.evidence_exists`; test assumption checks are a domain predicate (`test.assumptions_unchecked`, app-1 session 5) | none |
| 7 evaluate judgment calls | controls machinery; lint requires controls | none (controls are eval by definition) | negative, positive, planted, held-out |
| 8 uncertainty reported | `abstain` and `confidence` required; holds on low or abstain | `judg.confidence_consistent` | none |
| 9 gates halt | state machine; failed gate cannot advance | all | none |
| 10 assertions shown, structured output | JSON schema on every judgment | `out.schema_conformance` | none |
| 11 provenance for figures | sidecars; `deliver` cross-links | `prov.orphan_artifact` | harness artifacts linked by run ID |
| 12 human judgment captured | `review`; bound verdicts | none | reason codes emerge from the corpus |

Everything in the eval column is either a control, a rate computed from the trace, or a convention the skill layer enforces. Nothing in that column blocks, and nothing in the predicate column requires judgment to evaluate.

## 17. Deferred, with triggers

| Item | Reserved now | Trigger to build |
|---|---|---|
| open and staged modes | `mode` field, `splits`, `proposed_by`, `rationale_ref`, `budgets` column on runs | app 1 runs end to end in pipeline mode and the exploratory surface between clustering and niche characterisation is real |
| free-text, ungated steps | nothing | open mode |
| `openai-compatible` adapter | harness protocol | the Qwen3 evaluation |
| re-audit | `policy_snapshots`, full state and action records | a predicate is added after real runs exist |
| Nextflow executor | executor protocol | application 2 |
| `trace` verb | `status --trace` | someone asks the question `status` cannot answer |
| `reason_code` enum | `reason_code NULL` column | roughly fifty reviews |
| inspector agent | trace completeness | Phase F |
| `confirm` hold kind | kind enum | application 2's samplesheet echo-back |
| review page: `review --serve`, a localhost form for verdicts, run by the reviewer, recorded as a third `via` value that profiles treat like `tty` | `via` column, review rows | a reviewer who does not use a terminal (7.5); the relayed path stays the only non-terminal route until then |

## 18. Deltas from the implementation plan

1. Predicates return whether they fired plus a default disposition; the policy resolves the effective disposition per profile. Both are recorded. The plan had predicates returning the disposition directly.
2. Gates have two phases, pre and post. The plan's engine-shipped output checks are post-gate predicates under the same contract.
3. A block is never cleared by a review; it is cleared by a commit. Flags create holds. The plan left the flag-to-hold relationship implicit.
4. Operator harness and judgment harness are distinct roles. Judgment calls use a dispatch adapter by default: the engine writes request files and the operator harness (Claude Science) has fresh-context subagents answer them on the subscription. `api` is implemented and one line away at init. The trace marks which path produced every invocation.
5. Plugins have a predicate half in the engine environment and a tool half executed in module environments. State extraction runs once per step, post-execution, and predicates read the stored summary.
6. Forward feasibility is `obj.feasibility`, a pre- and post-gate check on declared unit counts per contrast level, rather than a prediction.
7. Reviews are bound to module version, input digest, and params hash, and prior verdicts auto-resolve identical holds (`rebind`).
8. Reviewer identity carries `via: tty | relayed | web`; profiles decide whether relayed verdicts are accepted, and treat `web` as `tty`.
9. Coverage is computed from predicate `covers` declarations and module `decision_points`.
10. `fork` and `abandon` are in v1; `trace` is a flag on `status`.
11. Judgment modules declare `batching` and `evidence`; the engine renders prompts from declared variables only.
12. `seed_unset` applies only to modules that declare `stochastic: true`, and judgment invocations are recorded as not bit-reproducible rather than seeded.
13. The engine ships roughly thirty domain-free predicates (6.5), including init-time compatibility and parameter checks; the plan listed five categories.
14. Application 2, open and staged modes, and PROTSEQ preparation are out of scope for this document.
15. The agent executes analysis steps by default (`runner: operator`) through `propose` and `submit`; the engine runs only extractors, judgment evidence generation, and modules that opt into `runner: engine`. Environment facts for operator-run steps are `verified` or `as_reported` and the trace says which. The plan had the engine as the only executor.
16. Parameters in `pipeline.yml` carry a default and a range; the agent proposes values within range under `standard`, cannot change them under `strict`, and is flagged rather than blocked out of range under `exploratory`. The plan had parameters fixed by the committed file.
17. `init` runs compatibility predicates across the design, objective, inputs, and pipeline, and opens a `confirm` hold with a plain-language echo-back that the owner must accept before any run, in every profile.
18. `next --json` returns the plan template for the coming step.
19. `exec.plan_drift` blocks when evidence shows a different action ran than the one admitted.

## 19. Questions the app-1 sessions must answer

Listed in `archive/app1-spatial-tma-plan.md` and revised in `plans/app1-spatial-qc-plan.md`. The ones that shape the engine rather than the plugin: whether `all_items` batching needs an item cap for large cluster counts (session 7); whether the confidence criteria should count distinct evidence columns or distinct rows (session 6); whether the niche vocabulary can be closed or needs a `proposed_label` escape hatch that always holds (session 6); whether Claude Science subagents can be tool-restricted to a single file, and whether they report their model identity (session 13; answered on the toy 2026-09-08: no, isolation is instructional and recorded `as_reported`; yes, they report model, harness, and tools); and whether Claude Science exposes a session reference and a readable artifact store on disk (sessions 13 and 14; on the toy: a frame id serves as the session reference, artifacts live in the app's own store, and the deliver directory on the workstation is the durable copy).

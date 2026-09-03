# stringency: Phase A build plan

For Claude Code. Read `stringency-design.md` first; it is the spec. This document says what to build, in what order, and how to know each piece is done. Section references in parentheses point into the design document.

Phase A builds the engine and a toy domain plugin, with no biology. The exit criterion is a two-module toy pipeline that runs on both workstations through the CLI, with a trace sufficient to reconstruct it, a gate that cannot be skipped, a computed coverage report, a correct methods paragraph, and a linter that rejects a judgment module without a negative control.

## 1. Ground rules

Put these in `CLAUDE.md` at the repository root.

The engine imports no biology. No scanpy, anndata, squidpy, cell ontologies, or marker logic anywhere under `src/stringency/`. If a change seems to need one, it belongs in a plugin. A CI check greps for these imports and fails.

Contracts marked frozen in the design (module contract 3.2, predicate contract 6.1, base judgment schema 8.1, trace tables 9.4, CLI exit codes 14.2) are not reshaped for convenience. If one cannot be implemented as written, stop, write the problem to `spec/DEVIATIONS.md`, and continue with the rest of the milestone.

When the design is silent, choose the simplest thing, record the choice and a one-line reason in `spec/DECISIONS.md`, and continue. Choices below the contract level do not need approval. Anything that would change a contract does.

Every predicate ships with a must-fire fixture and a must-pass fixture. Every state-machine transition in 7.1 has a test. The append-only triggers have tests that attempt the forbidden write and assert it raises.

Tests use the mock harness and the local executor. No network in tests. The `api` adapter is tested against recorded fixtures only.

Work in milestone order. A milestone ends with its acceptance tests green and a commit whose message names the milestone. Do not start M(n+1) while M(n) is red.

The hold message printed by `run` must never suggest how to get around the hold (14.2).

Docstrings on any function that touches the trace state what it reads and writes and in which table. The trace is the product; the code exists to fill it correctly.

Dependencies stay boring: `pydantic` v2, `typer`, `pyyaml`, `jsonschema`, `jinja2`, `blake3`, `python-ulid`, `rich`, stdlib `sqlite3`. The `anthropic` SDK is an optional extra (`stringency[api]`). Nothing else without a `DECISIONS.md` entry.

Prose in docs and CLI output is plain. No marketing language, no exclamation marks, no emoji.

## 2. Repository layout

```
stringency/
  CLAUDE.md
  pyproject.toml                  uv-managed; console script `stringency`; entry point group `stringency.plugins`
  uv.lock
  README.md                       short; points at spec/
  spec/
    stringency-design.md          copy of the design document, updated only by Jim
    module-contract.md            M11: standalone statement of 3.2 and 13
    predicate-contract.md         M11: standalone statement of 6.1 through 6.6
    trace-schema.md               M11: 9.4 with column descriptions
    DECISIONS.md
    DEVIATIONS.md
  src/stringency/
    cli/                          typer app; one file per verb
    config.py                     pydantic models: stringency.yml, inputs.yml, envelopes for design and objective
    project.py                    init, layout, method clone, binding
    git.py                        sha, dirty flag, blob hash for a path at HEAD
    hashing.py                    blake3 over files, directories, canonical JSON
    ids.py                        ULID
    db/
      schema.sql                  tables, indexes, triggers
      migrations/
      store.py                    connection, WAL, one-db-per-project, typed writers
    modules.py                    manifest model, loading, validation
    pipelines.py                  topology model, DAG resolution, $inputs and $steps refs
    plugins.py                    entry point loading, Plugin protocol
    state.py                      State model, snapshot storage
    actions.py                    Action construction and storage
    predicates/
      registry.py                 @predicate decorator, scope matching, versioning
      context.py                  GateContext, Verdict, Disposition
      engine/                     the engine predicates (6.5), one file each, including init.* and param.*
    policy.py                     load, resolve effective disposition, digest, snapshots
    gate.py                       evaluate a phase over in-scope predicates; write results
    executor/
      base.py                     Executor protocol, Job, ExecResult (engine runner)
      local.py
      apptainer.py                M11
    operator_exec/
      tickets.py                  propose: ticket issue, job spec rendering
      submit.py                   collect outputs, extract, parse evidence, plan drift
      evidence/                   parsers: nextflow_trace, nextflow_log, apptainer_inspect, job_log
    harness/
      base.py                     Harness protocol (direct and dispatch families), Invocation, Sampling
      mock.py                     both families
      subagent.py                 dispatch adapter: request/response files, nonce
      api.py                      M11
    prompting.py                  jinja2 StrictUndefined render, var whitelist, hashing, message storage
    schemas.py                    base judgment schema, inclusion check, validation
    repeat.py                     N invocations, storage
    consensus.py                  agreement rules from policy, holds, consensus records
    steps.py                      run one step end to end for both runners (3.4, 3.5)
    echo.py                       plain-language echo-back of design, objective, inputs (2.7)
    machine.py                    step and run states, transitions, events, next()
    runs.py                       open, resume, close, fork, abandon; run-level captures
    review.py                     queue, display, verdicts, binding, rebind, via
    artifacts.py                  sidecars, harvest
    coverage.py                   computed report
    methods.py                    methods paragraph template and rendering
    deliver.py
    controls.py
    lint.py
  plugins/
    stringency-toy/               a real installable package, used by tests and by Phase A exit
  tests/
    conftest.py                   tmp project with a fixture method repo (git init and commit in tmp)
    fixtures/                     state JSON, mock harness YAML, toy data
    test_*.py                     one file per module above
  .github/workflows/ci.yml        uv sync, ruff, mypy, pytest, no-biology-imports check
  .pre-commit-config.yaml
```

Method repos (not this repo) get a template in M11: `pipelines/`, `modules/`, `policy.yml`, `envs/`, `notes/`, `.gitignore`, and a pre-commit config that runs `stringency lint` and blocks `.h5ad`, `.bam`, `.fastq*`, `run.db`, and files over 10 MB.

## 3. Milestones

### M0 Scaffold

Tasks: uv project with src layout; `stringency --help` listing every verb from 14.1, each exiting 16 with "not implemented"; `pyproject.toml` declaring the console script and the `stringency.plugins` entry point group; ruff, mypy (strict on `src/`), pytest; CI workflow; pre-commit; `spec/` populated with the design copy and empty `DECISIONS.md` and `DEVIATIONS.md`; `CLAUDE.md` from section 1.

Acceptance: `uv run stringency --help` lists all verbs; `uv run pytest` passes an import smoke test; CI is green on a push.

### M1 Trace store

Tasks: `db/schema.sql` implementing every table in 9.4 with the append-only triggers from 9.5; `store.py` opening one database per project in WAL mode with a refusal if the path is on a CIFS mount (check `stat -f` filesystem type; record the check in `DECISIONS.md`); typed writer functions per table; `hashing.py` (blake3 over files, over directories as sorted relative-path plus content, and over canonical JSON with sorted keys and no whitespace); `ids.py` (ULID); migrations table and a forward-only runner.

Acceptance: schema creates from empty; `UPDATE` and `DELETE` on each append-only table raise; status mutation on `steps` without a `step_events` row in the same transaction is impossible through the store API (test the API, not the DB); canonical JSON hash is stable under key reordering; a directory hash changes when one byte changes.

### M2 Project binding and init

Tasks: `config.py` models for `stringency.yml`, `inputs.yml`, and envelopes for `design.yml` and `objective.yml` (engine-known fields validated, `domain` blocks passed to the plugin); `git.py`; `project.py` implementing `init`: create layout (2.1), clone method repo at the tag into `method/`, compute and verify input hashes, load the pipeline named, run lint (stub in M2, real in M3), write `stringency.yml`, open the database, write the `projects` row; refuse open+strict; refuse a second init in a populated directory. The `init.*` compatibility predicates (6.5) run against the three declarations and the pipeline; `init.column_missing` needs one extractor pass and is wired in M5. `echo.py` renders the plain-language echo-back from the declarations (the toy plugin supplies the domain phrasing); `init` opens a project-level `confirm` hold bound to the three file hashes, and `run` refuses to open while it is unresolved (the refusal is testable in M2; clearing it needs `review`, M8, so M2 through M7 tests pre-seed the review row through the store API).

Acceptance: `init` against a fixture method repo produces the layout, a `projects` row, an `echo.md`, and an open `confirm` hold; re-init is refused with exit 15; a wrong input hash is refused with exit 15; open+strict is refused; the recorded `method.sha` matches the tag; each `init.*` predicate has a must-fire fixture (a contrast naming an undeclared factor, a deliverable no step produces, and so on) and a must-pass fixture; editing `objective.yml` after init regenerates the echo-back and reopens the hold.

### M3 Modules, pipelines, plugins, lint

Tasks: `modules.py` (manifest model per 3.2, params schema loading, prompt var extraction); `pipelines.py` (topology model, `$inputs.<name>` and `$steps.<id>.<output>` resolution, DAG validation, ordered frontier, parameter declarations with `default` and `range` or `options`, per-step `runner`, the pipeline's declared `answers:` list of objective questions); `plugins.py` (load entry points, `Plugin` protocol with `predicates`, `operations`, `object_types`, `design_schema`, `objective_questions`, `vocabularies`, `tools`, `describe`); `lint.py` implementing every error and warning in section 13; `stringency-toy` package skeleton with its operations vocabulary, `frame` object type, and vocabulary file (section 4 below).

Acceptance: lint passes the toy modules; a table-driven test feeds one broken manifest per error class in section 13 and asserts the error; each warning class is exercised; `plugins list` shows the toy plugin; a pipeline with a dangling `$steps` ref fails lint.

### M4 Gate

Tasks: `state.py`, `actions.py`, `predicates/registry.py` and `context.py` (6.1), `policy.py` (6.4: load, override then remap, invariant skip, digest, snapshot), `gate.py` (evaluate one phase over registered predicates whose scope matches the action's operation; write `actions` before evaluation and `predicate_results` after); the engine predicates from 6.5 that need no execution to test: `topo.*`, `repro.dirty_tree`, `repro.seed_unset`, `repro.input_digest_mismatch`, `param.undeclared`, `param.locked_changed`, `param.out_of_range`, `out.schema_conformance`, `obj.feasibility`, `obj.deliverable_unreachable`; the toy predicates. Action construction merges committed defaults with agent-proposed values and records `param_source` per parameter.

Acceptance: every predicate has a must-fire and a must-pass fixture; `strict` remaps flag to block and `exploratory` remaps block to flag; under `params: locked` any proposed change blocks, under `ranged` an in-range value passes and an out-of-range value blocks, under `free` an out-of-range value flags; a proposed parameter absent from the schema blocks in every profile; `repro.*` is never remapped; an `overrides` entry wins over remap; `policy_digest` changes when a predicate's version changes and when `policy.yml` changes; a rejected action is present in `actions` with its `predicate_results`.

### M5 Deterministic module execution, both runners

Tasks: `executor/base.py` and `local.py` (10.3; env digest from `uv.lock` or `renv.lock`, none reported if absent); the toy `frame` extractor as a script under the toy plugin's `tools`; `steps.py` for `kind: deterministic` under the engine runner (3.4): resolve inputs, construct action, pre-gate, run, hash outputs, validate schemas, call the extractor, store state snapshot, post-gate; `repro.env_unpinned`; `operator_exec/tickets.py` (propose: action, pre-gate, ticket, job spec rendering) and `operator_exec/submit.py` (collect declared outputs, hash, validate, run the extractor engine-side, parse evidence, compute `observed_params`, `exec.plan_drift`, `repro.env_unverified`, post-gate); evidence parsers for `job_log` and `nextflow_trace` (use a checked-in sample trace file from a real Nextflow run as the fixture); `init.column_missing` wired now that the extractor exists.

Acceptance, engine runner: toy `filter_rows` with `runner: engine` runs end to end with a `uv.lock` present and produces a `state_snapshots` row with `counts_per_group`; with the lock removed, `repro.env_unpinned` fires and the step is blocked; a `min_value` that empties one group makes `obj.feasibility` fire post-gate and the step is rejected. Acceptance, operator runner: `propose 01_filter --set min_value=30` issues a ticket and a job spec naming the admitted parameters; a test harness plays the agent, runs the toy script itself, and calls `submit`; the state snapshot is produced by the engine's extractor call, not by anything the "agent" supplied; a submit whose job log shows `min_value=40` blocks via `exec.plan_drift`; a submit with no container evidence completes with `env_status: as_reported` and a `repro.env_unverified` flag; outputs submitted without a ticket are refused with exit 15; the sample Nextflow trace parses to per-process container names and exit statuses.

### M6 Judgment module execution

Tasks: `harness/base.py` with both families (10.2: `invoke` for direct adapters; `dispatch` and `collect` for the dispatch family) and `mock.py` implementing both (fixtures keyed by template hash, item ID, replicate; in dispatch mode the mock writes the response files itself on `collect`); `harness/subagent.py` (request and response file contract from 10.2, nonce generation and check, `reported` block stored verbatim, `invalid` on missing or unparseable response); `prompting.py` (StrictUndefined, var whitelist from `prompt.vars`, rendered prompt stored in `messages`, template blob hash via `git.py`); `schemas.py` (base schema inclusion check, replicate validation, one retry with the error appended, `invalid` marking); `repeat.py`; `consensus.py` (8.4 with `standard` and `relaxed` from policy; holds of kind `self_uncertain` and `run_disagreement`; consensus rows); `steps.py` for `kind: judgment` (3.5); the remaining engine predicates: `judg.*` and `repro.intermediate_dropped`.

Acceptance, all on toy `label_groups` with mock fixtures, run once through the direct mock and once through the dispatch mock: unanimous high-confidence replicates complete the step and write agreed consensus; under dispatch, `run` writes three request files and exits 20, a second `run` with responses present collects them and continues, a response with a wrong nonce marks that replicate `invalid`, and the invocation rows carry `via: subagent` and `isolation: as_reported`; two-of-three creates a `run_disagreement` hold under `standard`; one abstention creates `self_uncertain` under `standard` and completes under `relaxed`; a rationale with a number absent from the evidence blocks via `judg.numeric_claims_match`; a label outside the vocabulary blocks; an evidence ref to a nonexistent row blocks; a replicate failing schema twice is `invalid` and produces a hold; a template with an undeclared variable fails before any invocation; the rendered prompt contains only the declared vars (assert the matrix column names are absent).

### M7 State machine and the run, next, status verbs

Tasks: `machine.py` (7.1 transitions including `awaiting_execution`, events, `next()`); `runs.py` (open with every capture in 9.1, refuse to open while the init `confirm` hold is unresolved, resume the latest open run, close, `abandon`); `run` loop with exit codes including 20 and 21; `next --json` returning the plan template (operation, parameter schema with defaults and ranges, vocabulary, declared outputs, expected evidence, or the current hold); `propose` and `submit` as CLI verbs over M5; `status` including holds and who they wait on.

Acceptance: the toy pipeline (section 4) runs to `completed` through the direct mock with every step `runner: engine`, and through the dispatch mock with the default operator runner, pausing at exit 21 for each operator-run step (a test agent calls `propose`, runs the script, calls `submit`) and at exit 20 for the judgment step; `next --json` for the filter step returns the `min_value` range from the pipeline file and matches a checked-in schema; `run` before the init confirm is accepted exits 10 naming the owner; a pipeline whose judgment step holds exits 10, and a second `run` exits 10 without advancing or re-invoking the harness (assert invocation count unchanged); a blocked pre-gate exits 11 and `next` reports the predicate; an edit to `pipeline.yml` without a commit exits 14, and `--allow-dirty "reason"` proceeds with the reason recorded; every transition in 7.1 has a test; `status --json` matches a checked-in schema.

### M8 Review

Tasks: `review.py` (7.3 display, verdicts, correction validation against schema and vocabulary, binding columns, rebind lookup before hold creation, `via` detection by `isatty`, `--attest`, refusal when the profile disallows relayed review, reviewer check against roles).

Acceptance: an item hold accepted at a TTY (simulate with a pty) clears and `run` continues to completion; an override with a label outside the vocabulary is refused at entry; a rejected hold closes the attempt and `next` reports it; an identical rerun of a held step auto-resolves through rebind with `via: rebind` and no new prompt to the reviewer; bumping the module version defeats rebind; `--attest` under `strict` exits 16 and under `standard` records `via: relayed`; `status --overrides` reports the correct rate.

### M9 Deliver

Tasks: `artifacts.py` (sidecar on every engine-written file, harvest); `coverage.py` (12.2, computed from `predicate_results`, module `decision_points`, predicate `covers`, `holds`, `reviews`, `controls_runs`, `invocations`); `methods.py` (12.3 template; plugin `describe` per operation; toy `describe` implementations); `deliver.py` (12.1, including the deliverables check against the objective and `prov.orphan_artifact`).

Acceptance: `deliver` on the completed toy run writes `coverage.md`, `methods.md`, and `index.json`; the uncovered decision points listed equal the set computed by hand from the toy manifests; `methods.md` matches a golden file after replacing IDs and timestamps; a missing declared deliverable fails `deliver` with exit 15; a file copied into `runs/` by hand, without a sidecar, is refused as final; `deliver` on a held run exits 10.

### M10 Controls and fork

Tasks: `controls.py` (load `controls/*.yml`, resolve fixtures by hash, run the generator tool through the executor, run the single module through `steps.py` in an isolated context under `controls/`, evaluate `expect`, write `controls_runs`, diff against the last passing run, refuse the mock harness unless `--allow-mock` is passed for tests); toy generators (`shuffle_groups`); `fork` (2.6) inheriting completed steps before `--at`, applying `--set`, recording `delta_json` and `parent_run_id`.

Acceptance: the toy negative control (shuffled groups; mock fixture returns abstain for shuffled input) passes with `null_output: true`; the positive control computes agreement against the truth table; lowering the mock fixture's agreement makes the regression diff exit non-zero; a fork at step 2 with a changed `min_value` reruns only steps 2 onward, inherits step 1 with `inherited: true` in history, and the parent run is unchanged (assert by hashing the parent's rows before and after).

### M11 Production adapters, plugin skeleton, specs

Tasks: `executor/apptainer.py` (10.3; manifest-verified SIF digest, `--containall`, bind paths from the job); `harness/api.py` (10.2; check the current Anthropic SDK docs for structured output; record `model_resolved` from the response; `unknown` for anything unavailable; a recorded-response fixture for tests; kept fully working even though the lab deployment binds `subagent`); `stringency-singlecell` skeleton as a separate repository (entry point, `sc.anndata` extractor stub that emits the envelope in 4.2 including `counts_per_group` computed from a design file, an empty predicate registry, `vocabularies/`, `spec/` for incoming session specs); the method-repo template from section 2; `spec/module-contract.md`, `spec/predicate-contract.md`, `spec/trace-schema.md`.

Acceptance: the apptainer executor test runs against a minimal SIF when `apptainer` is on PATH and is skipped with a visible marker otherwise; the api adapter test replays a recorded response and records the resolved model; `stringency plugins list` shows both plugins when the singlecell skeleton is installed; the method-repo template passes `lint`; the spec documents render.

### Phase A exit

Run the toy pipeline on BMESEQ and on PROTSEQ from a Claude Science session: the session agent accepts nothing it should not (the init confirm is accepted by Jim through `review`), calls `propose`, runs each operator step itself, calls `submit`, answers the judgment dispatch with one subagent per request, and reaches `deliver`. Engine-run steps and extractors use the apptainer executor. Run once more with the `api` harness if a key is available for a one-off test. Confirm: `run.db` holds every row needed to state what ran, in what environment, with what parameters, producing which hashes; an attempt to run step 2 while step 1 is held or blocked fails; `deliver` emits a coverage report whose uncovered list is computed; the methods paragraph is correct; `lint` rejects a judgment module stripped of its negative control. Tag the engine `v0.1.0`.

## 4. Toy domain specification

Data: `groups.csv` with columns `row_id`, `group` (levels A, B, C), `unit` (u1 through u9, three per group), `value` (numeric). Fifty rows.

Design: `units: {observation: row, sample: unit}`, `factors: {group: {column: group, levels: [A, B, C]}}`, `replication_unit: unit`.

Objective: `question: compare_groups`, `contrasts: [[group, A, B]]`, `min_n_per_group: 2`, `deliverables: [comparison_table, group_labels]`.

Object type `frame`: CSV. Extractor reports `n_obs`, `fields.columns` with dtypes, and `counts_per_group` for `unit` and `row` per level of `group`.

Operations and modules:

`filter_rows` (deterministic, `runner: operator` in the default pipeline). Params: `min_value` (number; `default: 10, range: [0, 40]`). Decision point: `min_value`. Removes rows below the threshold. Output: `object: frame`. Its script prints `params: min_value=<v>` to its log so `exec.plan_drift` has something to read. Evidence: `{kind: job_log, path: run.log}`.

`summarize_groups` (deterministic). No params. Output: `table: tsv` with one row per group: `group`, `n_rows`, `n_units`, `mean_value`, `sd_value`, `top_unit`.

`label_groups` (judgment). Items from the summary table keyed by `group`. Evidence: the summary table. Vocabulary: `[abundant, sparse, variable, uniform, indeterminate]`. Prompt: label each group from its statistics; cite the cells you used; abstain if the statistics do not support a label. Replicates 3, batching `all_items`. Controls: negative `shuffle_groups` (permute `group` within the input; expect null output); positive with a truth table mapping A to abundant, B to sparse, C to variable and `agreement_min: 1.0`.

`compare_groups` (deterministic, `runner: engine`). Params: `replicate_unit` (`options: [unit, row]`, default `unit`), `correction` (`options: [bh, bonferroni, none]`, default `bh`). Decision points: both. Output: `comparison_table: tsv`.

`toy_report` (report). Consumes the comparison table and the labels consensus; emits one paragraph with two numbers copied from the table (so `judg.numeric_claims_match` has something to check) and `group_labels: json`.

Toy predicates: `toy.replication_unit` (block; fires when `compare_groups` proposes `replicate_unit: row` while the design declares `unit`; covers `compare_groups.replicate_unit`); `toy.no_correction` (block; fires on `correction: none`; covers `compare_groups.correction`); `toy.filter_after_summary` (flag; fires when `filter_rows` appears in history after `summarize_groups`; covers `filter_rows.*`).

The default toy pipeline runs filter, summarize, label, compare, report, declares `answers: [compare_groups]`, and mixes runners as above so both paths are exercised by the exit test. The toy plugin supplies `echo` phrasing so `init` can render "50 rows in 9 units across 3 groups; the replicate is the unit; the question is A versus B." The mock harness fixture supplies unanimous labels for the default input, abstentions for the shuffled input, and a two-of-three split for a second fixture used by the M6 and M8 tests. `min_value` in the default pipeline leaves every group with at least two units; the M5 test sets it high enough to empty group C.

## 5. Testing conventions

`conftest.py` builds a temporary method repo (git init, copy the toy modules and pipelines and policy, commit) and a temporary project via `init`. Tests never touch the real filesystem outside `tmp_path`. Mock harness fixtures are YAML under `tests/fixtures/harness/`. State fixtures for predicate tests are JSON under `tests/fixtures/state/` and are the same shape the extractor emits. Golden files live beside their tests and are updated only by an explicit `--update-golden` flag.

Predicate tests are table-driven: one row per (predicate, fixture, expected fired). Every predicate appears at least twice.

## 6. Not in Phase A

Open and staged modes beyond the reserved columns. Nextflow executor. `openai-compatible` adapter. Re-audit. Inspector. Claude Science skill wrappers (those are written in the method repo during app 1, session 13). Any single-cell predicate, extractor logic, vocabulary, or module; the singlecell repository in Phase A is a skeleton.

## 7. Handoff points from the app-1 design sessions

Specs arrive in `stringency-singlecell/spec/` as markdown with fixtures. Implement each against the frozen contracts.

| Arrives from | What | Implement as |
|---|---|---|
| session 1 | design schema for the TMA, inputs manifest, echo-back phrasing | `design_schema` and `echo` in the plugin; project files |
| session 2 | objective questions vocabulary | `objective_questions` |
| session 3 | pipeline topology with parameter defaults and ranges, per-step runner, expected evidence per module, module inventory, env list | `pipelines/spatial-tma.yml`, module directories, `envs/` |
| session 4 | extractor field list and fixture JSONs | `sc.anndata` extractor tool; test fixtures |
| session 5 | predicate table with must-fire and must-pass fixtures in words | `predicates/` in the plugin, one file each, with fixtures |
| session 6 | label vocabularies and confidence criteria | `vocabularies/`, `policy.yml` criteria |
| sessions 7, 9, 10, 12 | judgment module specs: evidence columns, prompt, schema extensions, batching | module directories |
| session 8 | control specs and generator behaviour | `controls/*.yml`, generator tools |
| session 11 | DE step params and applicable predicates | pipeline step; predicate scope confirmation |
| session 13 | skill descriptions, the review relay protocol text, and the dispatch protocol text (how the skill spawns one subagent per request file) | `skills/` in the method repo |

## 8. Definition of done for Phase A

All eleven milestones green in CI. Toy pipeline run on both machines with the trace and delivery checks in the Phase A exit passing. `spec/DEVIATIONS.md` either empty or every entry acknowledged by Jim. Engine tagged `v0.1.0` and installed from the lockfile on both workstations. Method-repo template published. Singlecell skeleton installable and visible in `plugins list`.

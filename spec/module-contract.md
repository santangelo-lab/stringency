# Module contract v1

Standalone statement of design 3.2 (the manifest) and 13 (what lint enforces). Frozen at Phase A exit.

## Directory

```
<name>/
  module.yml            the manifest below
  prompt.md             judgment and report modules: jinja2 template over `prompt.vars` only
  pre.*                 any language; produces evidence (judgment) or performs the operation
  post.*                optional restructuring of replicate outputs
  schema.json           judgment modules: output schema, JSON Schema 2020-12, includes the base (8.1)
  params.schema.json    parameter schema, every kind; `properties.<name>.default` is the module default
  controls/*.yml        design 11; judgment modules need a negative and a positive
  tests/                optional
```

One directory per module name in a method repo (`modules/<name>/`); the manifest `version` must
equal the version every pipeline step asks for (`name@version`).

## module.yml

| field | meaning |
|---|---|
| `contract: 1` | required |
| `name`, `version` | `name@version` is the module reference |
| `kind` | `deterministic`, `judgment`, `report` |
| `operation` | an id in the plugin's operation vocabulary; predicates scope over it |
| `domain` | the plugin name; must equal the pipeline's `domain` |
| `modes` | subset of the plugin's modes; a project whose mode is excluded fails init |
| `env` | environment name resolved through `envs/manifest.yml` |
| `runner` | `operator` or `engine`; default from the project; judgment modules are always engine-run |
| `entry`, `post` | script names when they are not `pre.*` and `post.*` |
| `inputs` | `{name: {type, format, hash, schema, optional, arity}}`; every input must be wired by the pipeline unless `optional`; `arity: one` (default) takes one reference, `arity: many` a list of references or a `$inputs.<glob>` over the manifest, and the script receives a list of paths (amendment approved by the owner 2026-09-23) |
| `outputs` | `{name: {type, format, schema, item_key}}`; judgment modules declare `judgments` and `consensus` |
| `decision_points` | parameters that are analysis choices; coverage is computed over them |
| `stochastic`, `seed_param` | `stochastic: true` needs `seed_param`, present in the params schema |
| `judgment` | `items_from`, `item_key`, `evidence`, `batching`, `replicates`, `abstain`, `confidence`, `considered_set` |
| `prompt` | `template`, `vars`; the template may use exactly these variables |
| `vocabulary` | `name@version` provided by the plugin |
| `gates` | predicates the author expects; lint checks each resolves; the engine evaluates every in-scope predicate regardless |
| `controls.required` | control kinds that must exist |
| `evidence` | operator runner: `[{kind, path}]`, kinds `nextflow_trace`, `nextflow_log`, `apptainer_inspect`, `job_log` |
| `resources` | `cpus`, `memory`, `timeout` |
| `confirm` | a step-level confirm hold before the step runs |
| `model` | judgment modules: model alias override for direct harnesses |

## Script contract

Scripts receive one JSON job on stdin:

```json
{"inputs": {"<name>": "<path>"}, "params": {...}, "outputs": {"<name>": "<path>"}, "output_dir": "<dir>", "seed": null,
 "design": {...}, "objective": {...}}
```

`design` and `objective` are the project's bound declarations as dictionaries (added 2026-09-23,
E1), so a module that needs the factors or the contrasts reads them from the job rather than from
a file it must find. An `arity: many` input appears as a list of paths, in the order the pipeline
bound them (a glob expands in manifest name order); the action records one digest for the input,
the hash of the parts' digests in that order. They write each declared output at the given path and exit 0. Stdout is captured (operator runner:
the agent's log is the evidence). A judgment `pre.*` receives `evidence_dir` (and `design`, `objective`) and writes
`<evidence_dir>/<name>.tsv` for evidence not already an input. `post.*` receives
`{"replicates": [{replicate, valid, structured}]}` and prints the same shape.

## Judgment records: the two evidence slots

`supporting_evidence` holds the cells that argue for the label the replicate chose;
`contradicting_evidence` holds the cells that argue against it. A cell read for context, or cited
only to explain a comparison, belongs in neither; a numeral in the rationale must still resolve
to a cited cell, so such a cell is cited as supporting when it is part of the case for the label.
`judg.confidence_consistent` counts the two lists against the policy's confidence criteria
mechanically. The engine appends this definition and the bound policy's criteria to every
rendered judgment prompt (`prompting.evidence_suffix`), so a module template need not repeat it.

## Prompt variables

Available: `evidence_table` (TSV of `items_from`), `evidence_tables` (name to TSV), `vocabulary`
(list), `items` (list), `context` (JSON inputs by name), `objective`, `design`. A module declares
the subset it uses in `prompt.vars`; rendering uses strict undefined checking.

## Lint

Errors and warnings are enumerated in design section 13 and implemented in `src/stringency/lint.py`;
`tests/test_lint.py` has one broken repo per error class.

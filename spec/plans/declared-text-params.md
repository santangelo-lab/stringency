# Declared text parameters: a pipeline should run on an object that names things its own way

Working note, not the spec. Drafted 2026-11-10 from the first benchmark test replicates, for a
session after the first pass of the benchmark slice has been read (`benchmark-plan.md`, Phase 2;
`PLAN.md` rows L163, L168, L169). Items marked *design* change design text and need the owner's
approval; the rest are DECISIONS-level or method work. It lives here and not in the method
repository because an agent operating a project can read the whole method clone, and this note
names benchmark evals.

## 1. The problem, as it happened

The DE test replicate of 2026-11-10 (`runs/dev-2026-11-10/DE01_pseudobulk_de/r1` in the benchmark
project; engine 0.2.40, plugin 0.10.3, method scrnaseq-scanpy 0.1.11):

| what the agent did | what the engine did |
|---|---|
| declared the task's comparison in `objective.yml` `params` for `03_pseudobulk_de`: `factor: cytokine`, `reference: PBS`, `levels: IFN-beta`, `group_column: cell_type`, `groups: CD14 Mono` | `declare --check` and `init` accepted it; the echo-back listed the values; the confirm hold was accepted |
| ran the pipeline | `01_qc_metrics` and `02_qc_cells` completed over 100,000 cells |
| reached `03_pseudobulk_de` | `param.locked_changed` blocked: "a fixed parameter differs from its default"; the run ended `blocked` |
| opened an open project over the data and called the `pseudobulk-de` tool with the same values, `--asked-by person` | admitted: an open project's step is not a pipeline step, so the lock does not apply; the tool's controls ran first; the answer was admissible |

Three things are wrong, and they are separable.

1. **A pipeline cannot be told a name.** A pipeline parameter is `{default, range}`,
   `{default, options}` or fixed (`pipelines.py` `ParamDecl`; design 3.1), and
   `param.locked_changed` blocks a fixed parameter that differs from its default. An obs
   column, a factor level or a cell type has no range and no closed list of options, so
   `scrnaseq-de`, which writes `factor: condition` and `reference: control`, runs only on an
   object named as its fixture is, and can never be restricted to one cell type. The same
   holds for `mt_prefix: MT-` (a mouse object needs `mt-`), `symbol_column`, and `keep_column`
   and `keep_value` in all three pipelines.
2. **The refusal comes late.** `init` checks only that a declared step and parameter exist; the
   value is gated when the step runs (`project.py`, the comment on declared parameters). The
   owner confirms a setup that cannot run and learns it after the earlier steps have run.
3. **The skill asks for what the pipeline cannot take.** `skills/scrnaseq-de.analyze.yml`
   asks "Which obs column holds the condition, which level is the reference", and nothing
   checks that an answer to an ask has anywhere to go.

A fourth finding of the same replicate is the DE tool's, not the engine's: the task excludes a
donor with too few cells on either side, and the tool drops the short sample and keeps the
donor's other sample. The agent wrote the exclusion as session code (`exec`), so the answer is
labelled `untested` although the test itself is the method's controlled tool.

## 2. What exists that the fixes can stand on

- The job every module reads carries the declarations: `job["design"]` and `job["objective"]`
  (`steps.py`, `operator_exec/tickets.py`). The objective's `contrasts` are
  `[factor, level, reference]` (design 2.5), `init.contrast_undeclared` already blocks a
  contrast whose factor the design lacks, and `init.column_missing` a design column absent
  from the raw input.
- The Xenium method's modules read the design from the job today (`pseudobulk_de.R` takes its
  block from `job$design$batch`; six others read `job["design"]`). Its `pseudobulk-de` is
  `modes: [open]` only, which is how it never met the lock; its pipelines still name a design
  factor as a fixed value (`timepoint_factor: timepoint_h`, four times in `xenium-upstream`).
- The objective has a plugin-interpreted `domain` block (design 2.5), empty in every scRNA-seq
  project so far.
- `param_source` already records `declared` and `person`; the echo-back already has a
  "Parameters declared" section; the trace needs no new column for any item below.

## 3. The fixes

**(a) `init` and `declare --check` refuse a declared value the step gate will block.**
For every value in `objective.params`: a fixed parameter that differs from its default, or a
value outside its range or options, is an `init` block naming the step, the parameter and why,
with the same reason text the step-time predicate gives. The step-time predicates stay; this
moves the news to before the confirm hold. Engine, DECISIONS-level. Row L168.

**(b) The DE module reads the comparison from the declarations.** Method, no contract change.
- `factor`, `reference` and `levels` default to empty, meaning "as declared": the module tests
  each `objective.contrasts` entry, taking the factor's obs column from
  `design.factors[<factor>].column`. A value passed explicitly (an open-mode call's `--set`)
  wins over the declaration; with neither, the module stops and says what is missing.
- `covariates` defaults to the design's declared `batch`, as the Xenium tool's `block` does.
- `replicate_unit` is unchanged (it has options, and `de.replication_unit` reads it).
- Pipeline `scrnaseq-de` 0.1.2, module `pseudobulk-de` 0.1.2, the positive control on the
  planted fixture unchanged, and a second control on a copy of the fixture with the factor
  column and its levels renamed, which must give the same twenty genes.
- This makes the comparison declarable. It does not make the cell-type restriction, the
  mitochondrial prefix or `keep_column` declarable: those are (c).

**(c) A third parameter form: text a person declares.** *design* (3.1, the predicate table's
`param.locked_changed` row, 14.3 lint). Proposed form:

```yaml
group_column: {default: "", text: declared}
```

- A `text: declared` parameter may differ from its default only when its source is `declared`
  (`objective.yml` `params`, so under the confirm hold and in the echo-back) or `person` (an
  open-mode call with `--asked-by person`). An agent's proposal of one is blocked as a fixed
  parameter is today. The agent never chooses a name; it may only carry one a person gave.
- The value is checked against the module's `params.schema.json` at `init` (item (a) covers
  when).
- Optional, same change or later: the pipeline may say what the text names
  (`names: obs_column`), and a plugin predicate at `init` blocks a column the bound object
  lacks, as `init.column_missing` does for design columns.
- `lint`: `text:` on a parameter with a range or options is an error; a `how: declared` entry
  in a `.analyze.yml` whose parameter is fixed is a warning (finding 3).
- Not proposed: free text for the agent under a hold. A name is a fact about the object, not
  a choice with evidence.

**(d) The method uses (c).** `scrnaseq-de`: `group_column`, `groups`; all three pipelines:
`mt_prefix`, `symbol_column`, `keep_column`, `keep_value`. The analysis skills' `decisions`
gain `how: declared` entries for them and are rendered again. If (c) is declined, the fallback
for the cell-type restriction is a plugin-defined `objective.domain` key the module reads
(a plugin change, and a second place to declare things); (c) is preferred because the value
then sits with the other declared parameters.

**(e) The DE tool can leave out an incomplete replicate.** Method. A boolean
`complete_units_only` (default false, so no existing result moves): a replicate unit without a
kept sample on both sides of a contrast is left out of that contrast, and the coverage table
names the units left out and why. A boolean needs no text form. This is tuning on a
development-set eval and is to be recorded as that in the benchmark plan. Row L169.

## 4. Order

1. (a), alone, with its tests. Small, and it stops the late refusal whatever else is decided.
2. (b) and (e) on the method's `scrnaseq-pca-pipeline` branch (0.1.12 is not tagged yet),
   controls green under the engine.
3. (c) after the owner's reading of this section; then (d).
4. Tag engine, plugin if touched, and method; render the skills; then the benchmark's DE01
   stringency arm again, which should now reach delivery in pipeline mode.

(b) alone does not make DE01 runnable in pipeline mode: the task names a cell type. Until (c)
and (d), DE01 runs through the open-mode tool, as the test replicate did.

## 5. Verification

- Engine tests, mock harness and local executor: a `text: declared` value from
  `objective.params` is admitted with `param_source: declared` and opens no
  `param.agent_proposed` hold; the same value proposed by the agent blocks; `init` refuses a
  declared fixed value and a declared out-of-range value with the step-time reason; lint's two
  new rules fire on fixtures.
- Method: `stringency lint .` clean; `controls run` green, the renamed-column control
  included; `tests/run.sh` in the image and with `LOCAL=1`.
- End to end, in the benchmark's container (`stringency-benchmarks` `latch/run_eval.py --arm
  stringency --policy observe`): one DE01 replicate reaches delivery in pipeline mode with no
  `param.locked_changed`, `de.replication_unit` and `de.covariate_omission` evaluated at the
  pipeline step, and an answer whose label is not `untested`.

## 6. What it changes for the benchmark

- The first slice's DE01 replicates go through open mode and are valid as runs of the
  committed method; they are reported as that.
- After the fixes, DE01 exercises the pipeline's decision points (`replicate_unit` with
  `hold: always`, `min_cells_per_sample`), which the open-mode route does not, so the two
  sets of replicates are not pooled.
- Every item here was found on a development-set eval. The held-out set is what says whether
  the fixes generalise; none of this is tuned against it.

## 7. For the owner

1. (c): the form (`text: declared`), and that an agent may never propose one. A design-text
   change.
2. (d) against the `objective.domain` fallback, if (c) is declined.
3. (e): whether a task's "exclude a donor with too few cells on either side" belongs in the
   method as an option, or is rightly session code with an `untested` label.
4. Whether the Xenium pipelines' `timepoint_factor: timepoint_h` moves to the same form once
   (c) exists, so that pipeline is not tied to one study's factor name.

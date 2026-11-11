# 2026-11-10 20:32: the four design-level changes, for the owner's reading

Branch `names-limits-policy`, stacked on `fixes-2026-11`. Each change amends the design
document or a frozen contract, so nothing here merges before the owner has read its text. The
decisions they rest on were his, on 2026-11-10; the texts are mine.

## Done

- **Names (L163 c) and the word `unset` (L129).** `text: column | prefix | {value_of: ...}`
  and `required` on a pipeline parameter. A declared name is admitted under every profile; an
  agent's follows the profile (a hold, a log, or a block where parameters are locked). A column
  and a value are resolved against the extractor summaries of what the step reads
  (`names.py`); `param.name_unresolved` and `init.name_unresolved` block one that names
  nothing, with the nearest that exist. `run` and `next` stop at a step with a parameter still
  `unset` (`awaiting_proposal`, exit 16, no hold, no action); `propose` refuses a proposal that
  leaves one. The echo-back says what each name resolves to. Design 2.5, 2.7, 3.1, 6.5, 7.1,
  13, 14.2.
- **The limits band (L171).** `init --limits <band>`, default the site configuration's
  `limits`; `stringency.yml` `limits`; `Policy.range_for` reads it for every key and nothing
  else of the profile moves; the digest, the echo-back, coverage, the summary and the methods
  paragraph carry it. Design 2.2, 2.7, 6.4.
- **`via: policy` (L162).** `review --policy <name>`; refused where a relayed verdict is;
  coverage counts such verdicts and no report words one as a person's. Design 7.5, the trace
  schema, DEVIATIONS.
- **Exit code 22 (L158).** `wait --job --for` while the detached verb still runs. Design 14.1,
  14.2, DEVIATIONS.

## Added later the same night

- **A fourth kind of name**, first built as `feature_column` and replaced on 2026-11-11, at
  the owner's word, by `text: {listed_in: <key>}`: an entry of any list the object's summary
  carries under `fields`, which the plugin's extractor writes and the engine does not know by
  name (the scRNA-seq method's `symbol_column` is `listed_in: feature_columns`). DECISIONS has
  both entries.
- **Checked in the benchmark image with no agent** (`stringency-benchmarks` `measurements.md`):
  the scRNA-seq method at 0.1.13 through `scrnaseq-de` within one cell type, in pipeline mode,
  to delivery, with names declared, strict limits from the site configuration and the
  benchmark policy's verdicts recorded `via: policy`; and the first slice's PCA declarations
  replayed, where `sc.pca_depth_confounded` now flags 0.369 against the strict ceiling of 0.3.
- Merged from `fixes-2026-11` as it grew: L95, the first half of L114, the control fix,
  `init.column_missing@2`.

## Decided (DECISIONS 2026-11-10, three entries)

The points the owner's decisions left to the code are listed there. The ones he should look
at: a name that names nothing blocks at the step even when it is the pipeline's default;
`awaiting_proposal` exits 16 and not a new code; the limits band may come from the site
configuration; a policy's name is kept in `operator_harness`; a project that chose its band
does not inherit its confirmation.

## What it does not do yet

- An h5ad's columns are seen only once the singlecell plugin writes `fields.columns`
  (`stringency-plugins` PR 4, 0.10.4). Until then a name on an h5ad is "not checked".
- The method does not use the form yet (L163 d), and the benchmark's runner does not set
  `limits: strict` or pass `--policy`. Those are the next pieces, in their repositories.
- The Xenium method's `sc.decision_unreviewed` no longer sees a step at `unset`; it can
  retire at the method's next tag.

## Open

- L163 (b), (d): the method. L171 and L162 close when `stringency-benchmarks` uses them.
- L100 (`hold: always` under `run`) will take `param.agent_proposed` to version 4 here, since
  this branch already took it to 3.

## Verify

    uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy
    bash scripts/check_no_biology.sh
    uv run pytest -q tests/test_names.py tests/test_limits.py tests/test_policy_verdict.py

# Agent reports from the PROTSEQ chained exit run, 2026-09-14

Trimmed. Sessions in the Claude Science app on Jim's MacBook, one Claude Science project, one
session per stringency project; compute provider `protseq`; engine 0.1.0.dev0 installed per user
under `~/mytools/stringency/engine`; method `stringency-toy-method@v0.1.2` (b5b0e27c1f88).
Setup and walkthrough texts: `integrations/claude-science/hosts/protseq-*.md`.

## Project 1: `toy-process` (pipeline toy-process), frame 961cbbde-15ce-4562-8200-807ddc040263

Phase 0: engine, plugin 0.1.1, image, container start (Python 3.12.14). One card.

Phase 1 (declare skill): the agent read the plugin schema, the manifest, the pipeline, and about
ten engine source and test files to learn the declaration shapes. It classified the two manifest
columns (unit identifier, group factor A/B/C) and asked three questions: which unit is the
replicate (Jim had left it out of the brief on purpose; the skill asked rather than inferred),
what `min_n_per_group` should be (no plugin default published), and whether the supplied manifest
becomes an input item. `declare --check` exit 0 first time. Source table: every field traced to
the manifest, a brief sentence, a plugin fact, or Jim's answer. `init --drafted-by agent` exit 10;
Jim accepted at a terminal (`via: tty`). One stray lint warning, "no policy.yml", from passing a
`path@tag` spec to `lint`, which takes a plain path.

Phase 2: one ticket (`01_filter`, operator-run, `min_value=10 [default]`), `job.json` already
written by the engine, exec and evidence and submit lines run verbatim; submit printed the run
completed. Phase 3: delivered `01_filter.object.csv` with sidecar. Twelve approval cards.

## Project 2: `toy-compare` (pipeline toy-engine), frame c30a0337-9f1c-4ae9-919c-1e4b6a708938

Phase 0 as above. Phase 1: the first brief attached was the toy-process brief by mistake; the
agent drafted `process_rows` and `declare --check` exited 15 with `init.question_unsupported`
(toy-engine answers `compare_groups`), before anything was created. With the corrected brief:
input bound to the delivered table with `derived_from` copied from the sidecar; contrast
`[group, A, B]`; deliverables first drafted as `[comparison_table, consensus]` from step
references, corrected by Jim to `group_labels` (the report step's output) after the agent said it
had not enumerated module outputs; `min_n_per_group` left unset until Jim gave 2. Second check
exit 0; echo-back names 41 rows and the upstream run. `init` exit 10; accepted `via: tty`.

Phase 2: `01_filter` engine-run in the container (the agent reported it as "satisfied from the
derived_from binding, not re-executed"; the executions table shows it ran, `env: verified`);
`02_summarize` ticket; `03_label` dispatch, three fresh delegates each given one request path,
all `claude-opus-5`, `saw_conversation: false`, three different self-descriptions of the same
profile; consensus unanimous, no flag hold this time; `04_compare` engine-run; `05_report`
ticket. Two operator slips, both declared: the three response heredocs joined with `;` wrote
nothing on the first try (bash warned, rewritten with newlines); `run` chained after the final
`submit` fired once after completion and was refused with exit 16. Phase 3: delivered
`04_compare.comparison_table.tsv`, `05_report.group_labels.json`, `05_report.report.md`; the
methods paragraph says "Input groups was delivered by stringency run 01M2GH5BY478331H517CV7BK1Z
(step 01_filter, output object)". Twenty-six approval-gated calls by the agent's count
(20 commands, 6 downloads).

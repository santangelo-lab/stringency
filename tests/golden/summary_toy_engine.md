# Summary of run <ULID>

Project <ULID>; pipeline toy-engine 0.1.2; profile standard.

## What was analyzed

50 rows in 9 units across 3 groups (input groups); the replicate is the unit; the question is A versus B.

Inputs: groups (frame).
Units: the observation is row; the sample is unit.
Factor group (column group) has levels A, B, C.
The biological replicate is unit.
The question is compare_groups: a versus b on group, with at least 2 units per group.
Deliverables: comparison_table, group_labels.

## What ran

- Filter low-value rows (step 01_filter): at defaults.
- Summarize each group (step 02_summarize): no parameters.
- Label the groups (step 03_label): no parameters.
- Compare the groups (step 04_compare): at defaults.
- Write the report (step 05_report): no parameters.

## What was checked and decided

Twenty-one checks were evaluated over five steps; no blocks and no flags were raised.

## Judgments

- Label the groups (step 03_label): three items judged by three independent replicates; three agreed, none self-uncertain, none in disagreement; reviews: none accepted, none corrected, none unresolved.

## What you received

- `04_compare.comparison_table.tsv`: the comparison_table output of Compare the groups; type table, format tsv.
- `05_report.group_labels.json`: the group_labels output of Write the report; type json, format json.
- `05_report.report.md`: the report output of Write the report; type prose, format md.
- `coverage.md`: the coverage report; `methods.md`: the methods paragraph; `index.json`: each file linked to its run, step, action, and hash.

## Not checked

not checked: anything not listed above

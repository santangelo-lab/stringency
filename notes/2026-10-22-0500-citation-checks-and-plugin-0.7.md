# 2026-10-22 05:00: plugin 0.7.0 and the citation checks (engine 0.2.33)

## Goal

Passes 6 and 7 of `PLAN.md` "Next, in order": L54 (the seven downstream predicates, plugin
singlecell 0.7.0) and L56, L57 (the judgment and report citation checks).

## Done

- Plugin singlecell 0.7.0 (`stringency-plugins` `a74575e`, tag `v0.7.0`; the tag was moved
  once within minutes from a commit whose surface test still listed eleven predicates):
  `predicates/downstream.py` with `de.replication_unit` (block), `de.covariate_omission`,
  `de.selection_bias`, `test.multiple_comparison`, `test.assumptions_unchecked` (flags),
  `spatial.neighborhood_undeclared`, `spatial.no_permutation_null` (blocks), all pre-phase
  over the action's parameters, `design.yml` and the run's history; must-fire and must-pass
  fixtures and the variants; `spec/predicates.md` rows; the README. The facts the tools write
  after running (`de_coverage`, `test_coverage`) are not read: that needs an extractor over
  the tools' output tables.
- L56: `judgment.must_cite` (DEVIATIONS entry, awaiting the owner, built additively as the
  sign-off field was); lint checks `<table>.<column>` and the table; the prompt suffix names
  the columns; `judg.required_evidence_uncited@1` flags an item that cites a required cell in
  neither list.
- L57: a report output of type `cited` (`[{table, row, column, value}]`) read into
  `observed.cited`; `judg.numeric_claims_match@2` checks prose against the cited cells only
  when present and names a citation that resolves to nothing. The toy method's gates name
  `@2` and `judg.required_evidence_uncited@1`. Moot for the Xenium `upstream-report`, whose
  prose is code-written.
- Design 3.2, 6.5, 8.1; DECISIONS; L54, L56, L57 in the done ledger; the plan's "Next" says
  the seven passes are done and what the owner does next.

## Learned

- A predicate version bump reaches every method's `gates`: the toy's manifests are in this
  repository, the Xenium method's wait for its next tag.

## Altered

- `judg.numeric_claims_match` is version 2.

## Open

- The owner: install 0.2.33 and plugin 0.7.0, restart the console, republish the skills;
  acknowledge the `must_cite` DEVIATIONS entry.
- Method side, next Xenium tag: L86's egress block, the `decision:` blocks and
  `requires.engine`, `requires.plugins` 0.7.0 with the seven predicates in the policy and the
  tools' gates, `judg.numeric_claims_match@2`, `must_cite` on `assess-batch` and
  `annotate-clusters`, `study:` on the Lyons projects.
- Open rows that were never scheduled: L58, L38, L73, L82, the console rows, L80, the
  deferred ones.

## Verify

`uv run pytest` green here and in `stringency-plugins`; ruff, mypy, `scripts/check_no_biology.sh` clean.

# 2026-10-21 21:00: decision points, first cut (engine 0.2.29)

## Goal

Pass 2 of `PLAN.md` "Next, in order": `decision-points.md` sections 2 to 5 (L61 the block, its
evidence floor, lint and the default hold view, with L9 folded in; L55 the citation and
considered-set slots on `propose`; L62 the `presented` event).

## Done

- `pipeline.yml` `decision:` on a parameter (`pipelines.DecisionDecl`): `evidence` as a
  source (`<step>/<output>[/<file>]`, `$inputs.<name>`, `<step>.<output>` accepted), a `text:`
  sentence, or `none` with `because:`; `hold: departure | always`; `sweep`, `rule`, `judged`,
  `sensitivity` parsed and linted, not yet acted on.
- `param.agent_proposed@2`: fires at the default under `hold: always`; evidence carries each
  parameter's declared evidence, the citations resolved and the considered set; the reason
  opens with "cites nothing from `x`" or "cites n cell(s) of `x`; considered a, b".
- `propose --cite <source>[:row[:column]]` (repeatable) and `--considered v1,v2`
  (`citations.py`): resolved against the run's files, stored with the reason as one JSON message
  behind `rationale_ref` (`actions.rationale_record` reads either shape), carried on the Action
  in memory for the pre-gate.
- `param.reason_unmatched@1` (a numeral in the reason no cited cell carries, or numerals with
  nothing cited) and `param.uncited@1` (a source decision point cited nowhere), both flags;
  strict's remap blocks the second.
- The packet: "the decision:" lines (default, proposed, the evidence as the pipeline names it),
  "cited:" and "considered:" lines, and the `presented:` line. The review page shows the same.
  `present --hold` with the skill silent renders the declared evidence (table, figure or text
  by extension; the sentence; the method's `because`) and then the parameter table.
- `presented`: the CLI `present` verb writes one `run_events` row per rendering of a run or a
  hold (sources, hold, step, user, session). The parameter hold's line: "evidence rendered
  HH:MM by the operator session, proposed HH:MM" or "proposed; no evidence of this step
  rendered in this run". The console's page renders do not write it.
- Lint: a ranged decision point with no block warns, and errors once `requires.engine` admits no
  engine older than 0.2.29; `none` without `because` is refused at load; a source must be an
  output of an upstream step; `decision:` off the module's decision points errors; the menu
  keys must name what exists. `render_skill --check`: a proposed decision's `evidence` must
  include the pipeline's source.
- `present._resolve`: `<step>/<output>` resolves through the artifacts table by output name.
- Section 9 of the operator skill and the analyze template (verbatim in both). Design 3.1,
  6.5, 14.1; trace-schema's `run_events` row. DECISIONS one entry. L61, L55, L62, L9 done.

## Learned

- A proposal whose reason carries a numeral and cites nothing now opens two holds (the
  parameter hold and `param.reason_unmatched`), and a source decision point proposed uncited
  opens a third. One hold per fired predicate is today's rule; the plan's "richer, not more
  numerous" holds for the parameter hold itself. If the test runs show fatigue, fold the two
  checks into the parameter hold's packet as findings (a DECISIONS-level change).
- The toy method's three pipelines now carry the silent-case warning on every ranged
  parameter; it stays a warning until the toy raises `requires.engine`.

## Altered

- `param.agent_proposed` is version 2; a policy naming `@1` no longer resolves (the registry
  holds one version per id).

## Open

- Method side: the Xenium method declares `decision:` on its six decision points, raises
  `requires.engine` to 0.2.29, re-renders the skills; `sc.decision_unreviewed` retires where
  `hold: always` is declared. Then the menu keys (L63 to L66) against the first run.
- Next session: pass 3, judgment replicates (L83 design text for 3.5, then the build; L84).

## Verify

`uv run pytest` green; ruff, mypy, `scripts/check_no_biology.sh` clean.

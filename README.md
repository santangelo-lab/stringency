# stringency

Admissibility gates, an append-only provenance trace, replicated model judgment with human review,
and a computed coverage report for agent-assisted analysis pipelines.

The engine is domain-free. Domain knowledge (state extractors, predicates, vocabularies) lives in
plugins registered under the `stringency.plugins` entry point group. `plugins/stringency-toy` is the
reference plugin and the one the test suite uses; `stringency-singlecell` (separate repository) is
the plugin for application 1.

The spec is `spec/stringency-design.md`. The build order is `spec/stringency-build-plan.md`. The
motivation is `spec/commandments.md`. Choices made where the design is silent are in
`spec/DECISIONS.md`; contract deviations, if any, in `spec/DEVIATIONS.md`.

## Status

Phase A milestones M0 through M11 are implemented with their acceptance tests. The Phase A exit
(the toy pipeline driven from a Claude Science session on BMESEQ and PROTSEQ, then tag `v0.1.0`)
is still to be done.

## Quickstart

```
uv sync --all-groups
uv run pytest
uv run stringency --help
uv run stringency plugins list
```

A project is bound with `init`, its echo-back accepted with `review`, and then driven by `run`:

```
stringency init <dir> --method <git-url>@<tag> --pipeline <name> \
    --objective objective.yml --design design.yml --inputs inputs.yml \
    [--profile standard] [--judgment-harness subagent] [--executor apptainer]
cd <dir>
stringency review --verdict accept --hold <id> --reason "..."   # the owner accepts the echo-back
stringency run          # exit 21: a ticket; run the step, then `stringency submit <ticket> ...`
stringency run          # exit 20: judgment requests written; subagents answer, then run again
stringency run          # exit 10: a hold; `stringency review` shows it
stringency deliver      # on a completed run: finals, coverage.md, methods.md, index.json
```

Exit codes are in design 14.2. Every verb takes `--json`.

## Layout

```
src/stringency/         the engine (no biology imports; CI checks)
plugins/stringency-toy/ reference plugin, its method repo, fixtures
templates/method-repo/  what a new method repository starts from
spec/                   design, build plan, contracts, decisions
tests/                  one file per milestone area; mock harness and local executor only
```

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
run has been completed on BMESEQ from a Claude Science session (2026-09-08); the PROTSEQ run and
the `v0.1.0` tag remain. `spec/improvements.md` lists what that run showed should change before
Phase B, and `integrations/claude-science/` holds the operator skill and install notes.

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

## Claude Science setup

A Claude Science session drives a project as its operator: it calls the CLI, runs the steps the
engine hands it, and answers judgment dispatches with fresh delegates. The session's sandbox
cannot start containers, so the engine runs on the workstation that holds the data and the
container runtime, and the session reaches it as an SSH compute provider. The full checklist is
`integrations/claude-science/new-project.md`; in outline:

1. On the workstation, once: `scripts/install.sh` puts the engine at
   `/usr/local/lib/stringency/current/bin`. Container images live where the method manifest says.
2. In Claude Science, once per instance: add the workstation as an SSH compute provider, set the
   project area as a data root, publish the `stringency-operator` skill
   (`integrations/claude-science/stringency-operator/SKILL.md`).
3. Per project: render the agent context and the session brief from the project with
   `integrations/claude-science/render_brief.py`, paste the context into the project's Agent
   Context, paste the brief as the first message, and accept the confirm hold at your terminal
   when the agent reports it. Every later hold comes back to you the same way.

`integrations/claude-science/examples/toy-cs/` holds a completed run: the texts as used, the
agent's reports for each phase, and the delivered coverage report and methods paragraph.

## Layout

```
src/stringency/         the engine (no biology imports; CI checks)
plugins/stringency-toy/ reference plugin, its method repo, fixtures
templates/method-repo/  what a new method repository starts from
integrations/           Claude Science: skill, brief renderer, setup checklist, example run
spec/                   design, build plan, contracts, decisions
notes/                  session notes; read INDEX.md first
tests/                  one file per milestone area; mock harness and local executor only
```

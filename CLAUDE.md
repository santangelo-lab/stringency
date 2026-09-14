# stringency: ground rules for Claude Code

Start every session by reading `notes/INDEX.md` and the most recent note it lists; end every
session by writing a note there (convention in `notes/README.md`) and updating the index.

Read `spec/stringency-design.md` first; it is the spec. `spec/README.md` says what every file under
`spec/` is. The frozen contracts are `spec/module-contract.md`, `spec/predicate-contract.md`, and
`spec/trace-schema.md`; `spec/commandments.md` is the source of the constraints; `spec/DECISIONS.md`
and `spec/DEVIATIONS.md` are the ledgers. Current plans live in `spec/plans/` (start with
`roadmap-2026-09.md`; `backlog.md` holds the open items); finished or superseded plans are in
`spec/archive/` and are history, not instructions. `integrations/claude-science/README.md` is a
working note.

## Rules

The engine imports no biology. No scanpy, anndata, squidpy, cell ontologies, or marker logic anywhere
under `src/stringency/`. If a change seems to need one, it belongs in a plugin.
`scripts/check_no_biology.sh` enforces this in CI.

Contracts marked frozen in the design (module contract 3.2, predicate contract 6.1, base judgment
schema 8.1, trace tables 9.4, CLI exit codes 14.2) are not reshaped for convenience. If one cannot be
implemented as written, stop, write the problem to `spec/DEVIATIONS.md`, and continue with the rest
of the milestone.

When the design is silent, choose the simplest thing, record the choice and a one-line reason in
`spec/DECISIONS.md`, and continue. Choices below the contract level do not need approval. Anything
that would change a contract does.

Every predicate ships with a must-fire fixture and a must-pass fixture. Every state-machine
transition in design 7.1 has a test. The append-only triggers have tests that attempt the forbidden
write and assert it raises.

Tests use the mock harness and the local executor. No network in tests. The `api` adapter is tested
against recorded fixtures only.

Work in milestone order. A milestone ends with its acceptance tests green and a commit whose message
names the milestone. Do not start M(n+1) while M(n) is red.

The hold message printed by `run` must never suggest how to get around the hold (design 14.2).

Docstrings on any function that touches the trace state what it reads and writes and in which
table. The trace is the product; the code exists to fill it correctly.

Dependencies stay boring: `pydantic` v2, `typer`, `pyyaml`, `jsonschema`, `jinja2`, `blake3`,
`python-ulid`, `rich`, stdlib `sqlite3`. The `anthropic` SDK is an optional extra
(`stringency[api]`). Nothing else without a `DECISIONS.md` entry.

Prose in docs and CLI output is plain. No marketing language, no exclamation marks, no emoji.

## Commands

```
uv sync --all-groups
uv run stringency --help
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
scripts/check_no_biology.sh
```

# stringency

Admissibility gates, an append-only provenance trace, replicated model judgment with human review,
and a computed coverage report for agent-assisted analysis pipelines.

The engine is domain-free. Domain knowledge (state extractors, predicates, vocabularies) lives in
plugins registered under the `stringency.plugins` entry point group. `plugins/stringency-toy` is the
reference plugin and the one the test suite uses.

The spec is `spec/stringency-design.md`. The build order is `spec/stringency-build-plan.md`. The
motivation is `spec/commandments.md`.

```
uv sync --all-groups
uv run stringency --help
uv run pytest
```

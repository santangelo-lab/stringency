"""`stringency plugins list` (design 15.2)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.plugins import load_plugins

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@handle_errors
def list_(as_json: bool = typer.Option(False, "--json")) -> None:
    import stringency.predicates.engine  # noqa: F401

    plugins = load_plugins(refresh=True)
    rows = []
    lines = []
    for p in sorted(plugins.values(), key=lambda p: p.name):
        preds = p.predicates()
        rows.append(
            {
                "name": p.name,
                "version": p.version,
                "modes": list(p.modes),
                "operations": sorted(p.operations),
                "object_types": sorted(p.object_types),
                "questions": list(p.objective_questions),
                "vocabularies": sorted(p.vocabularies),
                "vocabulary_terms": {k: list(v) for k, v in p.vocabularies.items()},
                "design_schema": p.design_schema,
                "defaults": dict(p.defaults),
                "tools": sorted(p.tools),
                "predicates": preds,
            }
        )
        lines.append(
            f"{p.name} {p.version}\n"
            f"  modes: {', '.join(p.modes)}\n"
            f"  operations: {', '.join(sorted(p.operations))}\n"
            f"  object types: {', '.join(sorted(p.object_types))}\n"
            f"  questions: {', '.join(p.objective_questions)}\n"
            f"  vocabularies: {', '.join(sorted(p.vocabularies))}\n"
            f"  defaults: {', '.join(f'{k}={v}' for k, v in sorted(p.defaults.items())) or 'none'}\n"
            f"  tools: {', '.join(sorted(p.tools))}\n"
            f"  predicates: {', '.join(preds) or 'none'}"
        )
    if not lines:
        lines = ["no plugins loaded"]
    emit({"schema": "stringency.plugins/1", "plugins": rows}, as_json, "\n".join(lines))

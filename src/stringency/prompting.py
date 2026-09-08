"""Prompt rendering (design 3.5): jinja2 with StrictUndefined, a variable whitelist from
`prompt.vars`, and content-addressed storage of the rendered text."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError, meta

from stringency import hashing
from stringency.exit_codes import ConfigError

if TYPE_CHECKING:
    from stringency.db.store import Store

_env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)

EVIDENCE_SUFFIX = (
    "\n\n---\n"
    "Evidence references. `supporting_evidence` lists the table cells that argue for the label "
    "you chose. `contradicting_evidence` lists the table cells that argue against it. A cell you "
    "read for context, or cite only to explain a comparison, belongs in neither list; a number "
    "written in the rationale must still appear among the cells you cited, so cite such a cell as "
    "supporting when it is part of the case for the label. The confidence you declare is checked "
    "against these counts: {criteria}.\n"
)


def evidence_suffix(criteria: Mapping[str, Any]) -> str:
    """The slot definition and the policy's confidence criteria, appended to every judgment
    prompt whatever the harness family (improvement D1)."""
    parts = []
    for level, c in criteria.items():
        text = f"{level} needs at least {c.min_supporting} supporting"
        if c.max_contradicting is not None:
            text += f" and at most {c.max_contradicting} contradicting"
        parts.append(text)
    return EVIDENCE_SUFFIX.format(criteria="; ".join(parts) or "none declared")


DISPATCH_SUFFIX = (
    "\n\n---\n"
    "Return only JSON matching the schema you were given. Include the nonce {nonce} verbatim in "
    "the `nonce` field of your response. In the `reported` object state the model you are, the "
    "agent or harness running you, the tools available to you, and whether you saw any "
    "conversation beyond this request (`saw_conversation`).\n"
)


def template_variables(text: str) -> set[str]:
    """Variables a template reads. Raises ConfigError on a syntax error."""
    try:
        ast = _env.parse(text)
    except TemplateSyntaxError as e:
        raise ConfigError(f"prompt template syntax error at line {e.lineno}: {e.message}") from None
    return set(meta.find_undeclared_variables(ast))


def check_vars(text: str, declared: list[str]) -> list[str]:
    """Lint: variables used but not declared, and declared but never used."""
    used = template_variables(text)
    problems: list[str] = []
    for v in sorted(used - set(declared)):
        problems.append(f"prompt template uses undeclared variable {v}")
    for v in sorted(set(declared) - used):
        problems.append(f"prompt declares variable {v} that the template never uses")
    return problems


def render(text: str, declared: list[str], values: Mapping[str, Any]) -> str:
    """Render with exactly the declared variables. An undeclared or missing variable is an
    error, never an empty string."""
    extra = set(values) - set(declared)
    if extra:
        raise ConfigError(f"values supplied for undeclared prompt variables: {sorted(extra)}")
    missing = set(declared) - set(values)
    if missing:
        raise ConfigError(f"no value for declared prompt variables: {sorted(missing)}")
    used = template_variables(text)
    if used - set(declared):
        raise ConfigError(
            f"prompt template uses undeclared variables: {sorted(used - set(declared))}"
        )
    try:
        return _env.from_string(text).render(**values)
    except UndefinedError as e:
        raise ConfigError(f"prompt render failed: {e}") from None


def store_prompt(store: Store, text: str) -> str:
    """Writes: messages (content-addressed). Returns the prompt hash."""
    h = hashing.hash_text(text)
    store.store_message(h, text)
    return h


def table_to_tsv(columns: list[str], rows: list[Mapping[str, Any]]) -> str:
    lines = ["\t".join(columns)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in columns))
    return "\n".join(lines) + "\n"

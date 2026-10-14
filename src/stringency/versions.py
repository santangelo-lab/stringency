"""Version strings and requirement specs (backlog L28, engine 0.2.19): dotted integers with an
optional release-candidate suffix, compared without a third-party dependency (CLAUDE.md:
dependencies stay boring). A method's `policy.yml` names what it needs under `requires`, and
`lint`, `declare --check`, `init` and run open check it against what is installed."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from stringency.exit_codes import ConfigError

_VERSION = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-.]?rc\.?(\d+))?(?:\+[0-9A-Za-z.\-]+)?$")
_CLAUSE = re.compile(r"^(>=|<=|==|!=|>|<)\s*(\S+)$")

Version = tuple[tuple[int, ...], tuple[int, int]]


def parse_version(text: str) -> Version:
    """`0.2.19`, `v0.6.0-rc13`, `0.1.0+optin3`: the numbers, then (1, 0) for a release or
    (0, n) for release candidate n, so a candidate sorts below its release. The local part after
    `+` is ignored."""
    m = _VERSION.match(text.strip())
    if not m:
        raise ConfigError(f"not a version: {text!r}")
    nums = tuple(int(x) for x in m.group(1).split("."))
    rc = (0, int(m.group(2))) if m.group(2) else (1, 0)
    return nums, rc


def _key(v: Version) -> tuple[tuple[int, ...], tuple[int, int]]:
    nums, rc = v
    return nums + (0,) * (4 - len(nums)), rc


def compare(a: str, b: str) -> int:
    ka, kb = _key(parse_version(a)), _key(parse_version(b))
    return (ka > kb) - (ka < kb)


def satisfies(version: str, spec: str) -> bool:
    """`spec` is one or more comma-separated clauses, each an operator (`>=`, `>`, `<=`, `<`,
    `==`, `!=`) and a version; every clause must hold. A bare version is refused so a spec
    cannot mean two things."""
    clauses = [c.strip() for c in spec.split(",") if c.strip()]
    if not clauses:
        raise ConfigError(f"empty version spec {spec!r}")
    for clause in clauses:
        m = _CLAUSE.match(clause)
        if not m:
            raise ConfigError(
                f"version spec {clause!r}: expected an operator and a version, such as >=0.2.19"
            )
        op, want = m.group(1), m.group(2)
        c = compare(version, want)
        ok = {
            ">=": c >= 0,
            ">": c > 0,
            "<=": c <= 0,
            "<": c < 0,
            "==": c == 0,
            "!=": c != 0,
        }[op]
        if not ok:
            return False
    return True


class Requires(BaseModel):
    """`requires:` in a method's policy.yml: the engine and the plugins this method needs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    engine: str | None = None
    plugins: dict[str, str] = Field(default_factory=dict)


def check_requires(req: Requires, engine_version: str, installed: dict[str, str]) -> list[str]:
    """The ways the installed engine and plugins fall short of `req`; empty when they satisfy it.
    Each line names the requirement and what is installed."""
    problems: list[str] = []
    if req.engine and not satisfies(engine_version, req.engine):
        problems.append(f"engine {req.engine} required; installed {engine_version}")
    for name, spec in req.plugins.items():
        have = installed.get(name)
        if have is None:
            problems.append(f"plugin {name} {spec} required; not installed")
        elif not satisfies(have, spec):
            problems.append(f"plugin {name} {spec} required; installed {have}")
    return problems

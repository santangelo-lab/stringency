"""The `@predicate` decorator, scope matching, and the registry (design 6.1, 6.5)."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from stringency.predicates.context import Disposition, GateContext, Phase, Verdict

PredicateFn = Callable[[GateContext], Verdict]

ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


@dataclass(frozen=True)
class PredicateSpec:
    id: str
    version: int
    scope: tuple[str, ...]
    phases: tuple[Phase, ...]
    default: Disposition
    covers: tuple[str, ...]
    invariant: bool
    fn: PredicateFn
    source: str  # "engine" or the plugin name

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def in_phase(self, phase: Phase) -> bool:
        return phase in self.phases

    def in_scope(
        self,
        operation: str,
        *,
        kind: str | None = None,
        runner: str | None = None,
        stochastic: bool = False,
        considered_set: bool = False,
    ) -> bool:
        """Scope entries: `*`, an operation name, `kind:<judgment|report|deterministic>`,
        `runner:<operator|engine>`, `stochastic:true`, `considered_set:true`, `project`."""
        for s in self.scope:
            if s == "*" or s == operation:
                return True
            if s.startswith("kind:") and kind == s[5:]:
                return True
            if s.startswith("runner:") and runner == s[7:]:
                return True
            if s == "stochastic:true" and stochastic:
                return True
            if s == "considered_set:true" and considered_set:
                return True
        return False

    def covers_param(self, operation: str, param: str) -> bool:
        return f"{operation}.{param}" in self.covers or f"{operation}.*" in self.covers


class Registry:
    def __init__(self) -> None:
        self._specs: dict[str, PredicateSpec] = {}

    def add(self, spec: PredicateSpec) -> None:
        prior = self._specs.get(spec.id)
        if prior is not None and prior.fn is not spec.fn and prior.source != spec.source:
            raise ValueError(
                f"predicate {spec.id} registered twice ({prior.source}, {spec.source})"
            )
        self._specs[spec.id] = spec

    def get(self, pid: str) -> PredicateSpec | None:
        return self._specs.get(pid)

    def resolve(self, ref: str) -> PredicateSpec | None:
        """`id@version` or bare `id`; None if unknown or the version differs."""
        pid, _, ver = ref.partition("@")
        spec = self._specs.get(pid)
        if spec is None:
            return None
        if ver and str(spec.version) != ver:
            return None
        return spec

    def all(self) -> list[PredicateSpec]:
        return sorted(self._specs.values(), key=lambda s: s.id)

    def refs(self) -> list[str]:
        return [s.ref for s in self.all()]

    def for_phase(self, phase: Phase) -> list[PredicateSpec]:
        return [s for s in self.all() if s.in_phase(phase)]

    def matching(self, pattern: str) -> Iterable[PredicateSpec]:
        rx = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")
        return (s for s in self.all() if rx.match(s.id))

    def clear_source(self, source: str) -> None:
        for k in [k for k, v in self._specs.items() if v.source == source]:
            del self._specs[k]


registry = Registry()


def predicate(
    *,
    id: str,
    version: int,
    scope: list[str],
    phase: Phase | list[Phase],
    default: Disposition,
    covers: list[str] | None = None,
    invariant: bool = False,
    source: str = "engine",
) -> Callable[[PredicateFn], PredicateFn]:
    if not ID_RE.match(id):
        raise ValueError(f"predicate id must look like ns.name: {id}")
    phases: tuple[Phase, ...] = tuple(phase) if isinstance(phase, list) else (phase,)

    def deco(fn: PredicateFn) -> PredicateFn:
        spec = PredicateSpec(
            id=id,
            version=version,
            scope=tuple(scope),
            phases=phases,
            default=default,
            covers=tuple(covers or []),
            invariant=invariant,
            fn=fn,
            source=source,
        )
        registry.add(spec)
        fn.__stringency_spec__ = spec  # type: ignore[attr-defined]
        return fn

    return deco

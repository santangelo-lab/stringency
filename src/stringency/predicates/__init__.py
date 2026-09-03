"""Predicates: pure functions over a gate context (design 6)."""

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import PredicateSpec, predicate, registry

__all__ = ["Disposition", "GateContext", "PredicateSpec", "Verdict", "predicate", "registry"]

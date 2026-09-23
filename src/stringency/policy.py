"""Policy (design 6.4): profiles, remaps, overrides, invariants, ranges, criteria, digest."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency import hashing
from stringency.config import load_yaml
from stringency.exit_codes import ConfigError
from stringency.predicates.context import Disposition
from stringency.predicates.registry import PredicateSpec, Registry


class ProfilePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    remap: dict[str, str] = Field(default_factory=dict)
    params: str = "ranged"  # locked | ranged | free
    replicates_min: int = 3
    agreement: str = "standard"
    qc_ranges: str = "standard"
    relayed_review: bool = True

    @model_validator(mode="after")
    def _check(self) -> ProfilePolicy:
        if self.params not in {"locked", "ranged", "free"}:
            raise ValueError(f"params must be locked, ranged or free; got {self.params}")
        for k, v in self.remap.items():
            Disposition(k)
            Disposition(v)
        return self


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    disposition: str
    reason: str


class ConfidenceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    min_supporting: int = 0
    max_contradicting: int | None = None


class AgreementRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    hold_on: list[str] = Field(default_factory=list)


DEFAULT_CRITERIA = {
    "high": ConfidenceCriterion(min_supporting=3, max_contradicting=0),
    "medium": ConfidenceCriterion(min_supporting=2, max_contradicting=1),
    "low": ConfidenceCriterion(min_supporting=1),
}
DEFAULT_AGREEMENT = {
    "standard": AgreementRule(
        hold_on=["label_disagreement", "any_abstain", "any_low", "any_invalid"]
    ),
    "relaxed": AgreementRule(hold_on=["label_disagreement", "all_abstain", "any_invalid"]),
}


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy: int = 1
    version: str
    invariant: list[str] = Field(default_factory=lambda: ["repro.*", "topo.*"])
    profiles: dict[str, ProfilePolicy]
    overrides: dict[str, dict[str, Override]] = Field(default_factory=dict)
    ranges: dict[str, dict[str, list[float]]] = Field(default_factory=dict)
    confidence_criteria: dict[str, ConfidenceCriterion] = Field(
        default_factory=lambda: dict(DEFAULT_CRITERIA)
    )
    agreement: dict[str, AgreementRule] = Field(default_factory=lambda: dict(DEFAULT_AGREEMENT))
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="after")
    def _check(self) -> Policy:
        if self.policy != 1:
            raise ValueError("policy must be 1")
        for p in ("strict", "standard", "exploratory"):
            if p not in self.profiles:
                raise ValueError(f"policy lacks profile {p}")
        return self

    def profile(self, name: str) -> ProfilePolicy:
        try:
            return self.profiles[name]
        except KeyError:
            raise ConfigError(f"policy has no profile {name}") from None

    def is_invariant(self, predicate_id: str) -> bool:
        for pat in self.invariant:
            rx = re.compile("^" + re.escape(pat).replace(r"\*", ".*") + "$")
            if rx.match(predicate_id):
                return True
        return False

    def effective(
        self, spec: PredicateSpec, profile: str, default: Disposition | None = None
    ) -> Disposition:
        """Resolution order (design 6.4): explicit override for (predicate, profile);
        else the profile remap applied to the default; invariants skip the remap."""
        d = default if default is not None else spec.default
        ov = self.overrides.get(spec.id, {}).get(profile)
        if ov is not None:
            return Disposition(ov.disposition)
        if spec.invariant or self.is_invariant(spec.id):
            return d
        if spec.id == "param.out_of_range" and self.profile(profile).params == "free":
            # design 6.5: out-of-range flags instead of blocking under `params: free`
            d = Disposition.FLAG
        if spec.id == "param.agent_proposed" and self.profile(profile).params == "free":
            # design 6.5: under `params: free` an agent's choice is logged, not held
            d = Disposition.LOG
        remapped = self.profile(profile).remap.get(str(d))
        return Disposition(remapped) if remapped else d

    def range_for(self, key: str, profile: str) -> list[float] | None:
        band = self.profile(profile).qc_ranges
        entry = self.ranges.get(key)
        if entry is None:
            return None
        return entry.get(band)

    def agreement_rule(self, profile: str) -> AgreementRule:
        name = self.profile(profile).agreement
        rule = self.agreement.get(name)
        if rule is None:
            raise ConfigError(f"policy has no agreement rule {name}")
        return rule

    def digest(self, registry: Registry) -> str:
        """blake3(policy.yml contents || sorted id@version of every registered predicate)."""
        text = hashing.canonical_json(self.raw) + "\n" + "\n".join(sorted(registry.refs()))
        return hashing.hash_text(text)


def load_policy(path: Path) -> Policy:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping")
    try:
        pol = Policy.model_validate({**data, "raw": data})
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None
    return pol

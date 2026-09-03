# Predicate contract

Standalone statement of design 6.1 through 6.6. Frozen.

## Declaration

```python
@predicate(
    id="de.replication_unit",
    version=3,
    scope=["test_differential_expression"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["test_differential_expression.replicate_unit"],
    invariant=False,
    source="stringency-singlecell",
)
def replication_unit(ctx: GateContext) -> Verdict: ...
```

| field | meaning |
|---|---|
| `id` | `namespace.name`; engine namespaces are `topo`, `repro`, `param`, `out`, `judg`, `exec`, `obj`, `prov`, `init` |
| `version` | bumped when the check changes; policy digests include `id@version` |
| `scope` | `*`, an operation name, `kind:<judgment|report|deterministic>`, `runner:<operator|engine>`, `stochastic:true`, `considered_set:true`, `project` (init) |
| `phase` | `pre`, `post`, `init`, `run_open`, `deliver`, or a list |
| `default` | `log`, `flag`, `block`; the policy resolves the effective disposition per profile |
| `covers` | `operation.param` or `operation.*`; coverage is computed over module `decision_points` |
| `invariant` | never remapped by a profile (overrides still apply) |
| `source` | `engine` or the plugin name |

## Context

`GateContext(phase, project, objective, design, state, action, history, output, policy)`:

- `project`: `ProjectConfig` with the bound config (mode, profile, roles), the pipeline, every module
  manifest by `name@version` (with `declared_params`), the inputs manifest, git dirty flag and reason,
  current input digests, environment digests, step statuses, plugin modes, vocabularies, object types.
- `state`: `State` with `objects` (type, digest, extractor summary), `design`, `objective`, `history`, `env`.
- `action`: the proposal (operation, module, parameters, param_source, inputs, digests, proposed_by).
- `history`: the sequence of completed `StepRecord`s (operation, params, output digests, inherited).
- `output` (post only): `OutputBundle` with outputs, replicates and validity, consensus, prose,
  evidence tables, observed evidence (operator runs), env status, schema errors, considered set.
- `policy`: ranges, criteria, agreement rules.

Nothing in the context is the data object. The agent's rationale is never in the context.

## Verdict

`Verdict(fired, reason=None, evidence={}, severity=None)`. `evidence` is JSON-serialisable and is
exactly what the predicate inspected. A predicate that raises, or exceeds the five-second budget, is
recorded as fired with the error as its reason.

## Purity and tests

No I/O, clock, randomness, or network. Every predicate ships a must-fire and a must-pass fixture
(`tests/test_gate.py` for the engine set; plugins do the same).

## Dispositions

Resolution order for a fired predicate: an `overrides` entry for (predicate, profile); otherwise the
profile's `remap` applied to the default, skipped for invariants; `param.out_of_range` becomes `flag`
under `params: free`. `log` records; `flag` opens a hold a review can clear; `block` stops the step
and only a commit clears it. Both default and effective dispositions are recorded with the policy
digest on every `predicate_results` row.

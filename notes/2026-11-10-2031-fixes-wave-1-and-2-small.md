# 2026-11-10 20:31: the fixes that need no design text (waves 1 to 3, the small rows)

Branch `fixes-2026-11`, from `main` at 73c4fb5 (#26 merged). The owner asked for the
non-design engine fixes in one pull request, or as few as possible. This is that branch; the
design-level work (the name form, the limits band, `via: policy`, exit code 22) is on
`names-limits-policy`, stacked on this one.

## Done

- **L168**: `init` and `declare --check` refuse a declared parameter value the step's pre-gate
  would block, with the step-time predicate's own reason (`declared.py`). A value the profile
  only flags is left to the step.
- **L161**: `declare --check` resolves the executor as `init` does (the flag, the site
  configuration, apptainer).
- **L146, L147, L159**, the operator skill: the engine line and a test that keeps it between
  the highest version the text names and the engine's own; `flag` when a person calls a
  delivered result wrong; every open hold relayed before the operator waits. Placed outside
  the two passages the analysis-skill template shares verbatim, so no rendered skill moved.
- **Version 0.2.42** (pyproject, `__init__`, the golden methods line, `uv.lock`), so the
  skill's line and the engine agree. v0.2.41 (#25) is `main` at 73c4fb5 and is not tagged.
- **L145**: a numeral matches a value rounded to the precision written, with no absolute
  tolerance; the chat block and the provenance lookup share the rule.
- **L148**: `audit` reads `flags` and `findings` against their run events.
- **L174**: `render_skill.py --check` fails a committed `SKILL.md` that differs from a fresh
  rendering.

## Added later the same night

- **L95**: a `param.reason_unmatched` hold shows the operator's reason, the cited cells with the
  values the engine read and the numbers that matched none; a `param.uncited` hold the evidence
  the method names beside what was cited (`present.proposal_check_sections`).
- **L114, first half**: `propose <step>` with nothing else carries out an admissible step's
  accepted Action. In open mode an accepted hold on a tool call left the step stuck.
- **A control runs with its own parameters.** `steps.starting_params` reads nothing from
  `objective.params` in a run of kind `control` (found running the scRNA-seq method's controls
  in a project that declared names).
- **`init.column_missing@2`** names the input, the columns it lacks and the columns it has.
- `PLAN.md`: L164 and L169 archived (the method's work), L163, L165, L167 and L171 amended, rows
  L186 to L189 filed.

## Decided

- DECISIONS 2026-11-10, "A declared value the step would block is refused at init": a
  `ConfigError` beside the existing refusals and not an `init.*` predicate; the predicate's
  effective disposition under the profile decides.
- L159 by the skill, as the owner chose; L146's test compares the line both ways.

## Found, not fixed here

- Every committed method skill (two Xenium, three scRNA-seq) fails the new `--check`: none
  has the marked-names paragraph #25 added to the shared decision text. Each is rendered again
  in its own repository.
- **L172** (a per-item judgment request numbered as its own replicate) was read and left: the
  request number is also the name of the dispatch files and the key of `invocations`, so the
  fix is a change to the dispatch protocol's bookkeeping, not a line. Methods avoid it with
  `batching: all_items`.

## Open

- Wave 2's larger rows (L94 with L107, the rest of L114, L160, L110, L11, L175), L172, wave 3's
  L106, L80, L155, L37, L76, L173, and L100 (which wants a session with the owner: with the
  Xenium method's bridge predicate still gated it would open two holds for one decision).
- For the owner: tag v0.2.41 at 73c4fb5 before merging this (it moves the version to 0.2.42),
  or skip 0.2.41; republish the operator skill after the release.

## Verify

    uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy
    bash scripts/check_no_biology.sh

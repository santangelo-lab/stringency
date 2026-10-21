# 2026-10-21 23:00: judgment replicates (engine 0.2.30)

## Goal

Pass 3 of `PLAN.md` "Next, in order": the owner's two picks from the literature check of
2026-10-21, L83 per-replicate prompt perturbation and L84 sampled sign-off.

## Done

- L83: every replicate after the first reads its own ordering of the items, the items table's
  rows and the vocabulary (`judgment.perturbation_for`, seeded by blake3 of the action id and
  the replicate number; `perturbed_values`); `assemble_requests` renders one prompt per
  replicate and serves both the run and `run --responses --check`, so the dispatch request
  files, the resume and the check agree. Each invocation row carries its replicate's prompt
  hash; the ordering is in `sampling_json.perturbation`; the coverage report counts distinct
  prompts ("prompts: 3 distinct orderings") and summary.md says each replicate read its own
  ordering. No knob: a template that declares none of the four variables renders one prompt.
  Design 3.5 step 3.
- L84: `judgment.sign_off: {when: sample, fraction: f}` (`SignOffSpec`, refused without a
  fraction in (0, 1], and a fraction without `sample`); `consensus.apply_sign_off` holds
  `round(f x agreed)` agreed items, at least one, chosen by a seed of the run and step, shared
  by the run and `--check`; the consensus notes name the sample. DEVIATIONS entry (approved in
  advance by the owner); design 3.2, 7.2, 8.4.
- Tests: `test_run.py` (three distinct prompts, replicate 1 canonical, the ordering in the
  prompt text and the sampling record, determinism, the dispatch request files),
  `test_sign_off.py` (one of three held under 0.34, all under 1.0, `--check` predicts the same
  two under 0.5, the manifest refusals). Golden summary updated. DECISIONS one entry. L83 and
  L84 in the done ledger.

## Learned

- The mock harness answers from the request's evidence by item, so a permuted prompt changes
  nothing it says; the tests check the prompts and the trace, not the answers. A real
  measurement of what the permutation does to agreement is L82's, once there are runs.

## Altered

- The prompt is no longer one per step: `invocations.prompt_hash` differs across replicates
  of one step. Nothing read it as a step-level key (checked: coverage, audit, repeat).

## Open

- Next: pass 4, confirm once (L67 design text for 2.7 and 7.2 with the `study:` field, then
  the build; L6; L5, L68, L69).
- The owner: install and republish only when the passes are done.

## Verify

`uv run pytest` green; ruff, mypy, `scripts/check_no_biology.sh` clean.

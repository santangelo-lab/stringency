# 2026-10-19: the first open-mode test drive and its six findings

## Goal

The owner drove open mode on the toy through Claude Science (`docs/open-mode-rehearsal.md`,
project parent `/data/lab/projects/2026-10_open-mode-drive_jrrose5`) and reported what went
wrong; address all of it before the second drive.

## Done

- Before the drive: the brief's render commands failed when pasted (a wrapped long line left
  `$E/python` alone, a Python shell); rendered for the owner and the doc now uses short lines.
  `declare --check` under apptainer failed with "no image for env toy-py": the toy method's
  `envs/manifest.yml` had been overwritten from the engine's in-repo copy (`image: null`) when
  it was synced by hand for open mode (486166b). Toy method `v0.2.0-rc2` (6fdc826, pushed)
  restores the image line; the owner republished the analysis skill.
- The six findings, each recorded in `spec/DECISIONS.md` ("Open mode O2 findings", the
  project README, delivery reporting) and in `spec/plans/open_mode_plan.md` section 9:
  controls run before a tool's first `call` (`controls.ensure_current`, `failed` status); a
  third label sentence for a tool's untested answer, with `{why}` and `{data}`; the upstream
  pipeline's own inputs bound read-only as `upstream_<name>`; the open delivery as
  `deliver/answers-<NN>/` with `q<NN>-<words>.md` and `answers-*.md`, `deliver --answer all`, the
  summary without the switch question; `readme.py` writes `<project>/README.md` after every verb;
  one delivery-reporting rule in the skills, the brief's engine-record list behind
  `render_brief.py --rehearsal`, the deliver sentence asked once.
- Skills: operator section 10 (16 pinned sentences), the analysis template's section 8 and rule
  7 (`spec/plans/ux-two-audiences.md` amended to match), the brief's phases 3 and 4. Toy method:
  `toy-engine.questions.yml` routes the raw-values question to code; skill re-rendered for
  `v0.2.0-rc3`.

## Learned

- `controls_runs` is per project: a control passed in one project says nothing in another, so
  an open project starts with every tool uncontrolled. Nothing in the agent's path ran one; the
  by-hand appendix did, which is why the dry run never showed it.
- The agent did the right thing with no control on record: it refused the pinned "would be
  labelled trusted" and said why. The engine's sentence then called a tool's output code.
- Three skill texts disagreed about what to show at delivery, and the brief added a fourth.
- The engine's in-repo toy method and the standalone toy method legitimately differ in one file,
  `envs/manifest.yml` (the in-repo copy runs under the local executor in CI); copying the tree
  across loses the image.

## Altered

- `exec --in` now adds to the delivered inputs instead of replacing them.
- The mock harness is refused only for a judgment module's control.
- The open project is named `<upstream>-open` by the operator (was `-questions`).

## Open

- The owner's choice on the toy manifest sync (name the image by file name in both copies and
  keep it in `/data/lab/env/images`, or keep the copies apart).
- Commit, tag `v0.2.0-rc3`, push both `open-mode` branches when the owner says; reinstall the
  open-mode prefix from this branch; republish the three skills; the second drive with a new
  project parent.

## Verify

`uv run pytest` (434 tests), `uv run ruff check .`, `uv run mypy`; `tests/test_open_mode.py`
runs the chain with the controls, the raw input, the new names and the README.

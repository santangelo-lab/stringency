# The Xenium analysis skill and the synthetic upstream run (roadmap W6, backlog L32)

## Goal

No real pipeline had an analysis skill, and neither skill said how an operator proposes a
decision point (`xenium-upstream` stops three times for one). The review's P1.6: a workflow in
which a researcher describes the analysis conversationally, the operator manages the mechanics,
and someone other than the developer can complete a synthetic analysis.

## Done

- `render_skill.py`: `decisions: [{step, param, how, ask, evidence, after}]`, validated and
  cross-checked against the module's `decision_points`; the template asks `declared` decisions
  before the echo-back (written to `objective.yml` `params:`) and lists `proposed` ones under a
  "Decisions the operator proposes" section whose text is the operator skill's new section 9,
  kept identical by `tests/test_render_skill.py`. `spec/method-skills.md` section 3; the template's
  example and README; DECISIONS.
- Method rc16: `skills/xenium-upstream.analyze.yml` (five asks, the organ declared, `ndim` after
  `03_reduce` from the elbow table, the resolution after `04_cluster` from the resolution
  evidence; five deliverables; twenty-four phrasings) rendered to
  `skills/stringency-analyze-xenium-upstream/SKILL.md` (261 lines).
- `controls/synthetic_upstream.sh`: `make_synthetic.py --cell-types 5 --slide --animals` twice
  (two slides sharing a time point, six punches, five planted programmes of twelve markers);
  `xenium-qc-tma` through the engine, delivered; `xenium-upstream` declared on its delivery with
  `params: {01_merge: {organ: liver}}` (no organ hold opened), `run --until 03_reduce`, the
  normalisation sign-off, `propose 04_cluster --set ndim=20`, the hold, `run --until 04_cluster`,
  `propose 05_select_resolution --set resolution=0.4`, the hold, the batch judgment on the mock
  harness with `review --choose proceed_uncorrected`, markers, the annotation on the mock harness
  (every cluster `hepatocyte`), labels, the report, `run --deliver`, `present`. About three
  minutes on PROTSEQ. The five programmes came back as five clusters. `synthetic_run.sh` now
  delivers and presents.
- Found by that run and fixed in singlecell 0.5.1: `extract_seurat.R` read the flags with `$`,
  which partial-matches, so a cluster-umap 0.4 object with `clustering_grid` and no `clustering`
  returned eight columns and the extractor died; exact names now. The first real rc13 run would
  have hit it at `04_cluster`.

## Learned

- A synthetic end-to-end run finds what module-level tests cannot: the extractor runs only under
  the engine, between steps. It is the method's smoke test and belongs in every method.
- The delivery skill names three sources (`05_select_resolution.batch_assessment.csv`,
  `06_assess_batch.consensus.json`, the composition CSV) that exist only when declared as
  deliverables; `present` says "not found for this run" for them on a project that declares
  fewer. Not wrong, but the method could fall back to the step's output; filed in PLAN 5.16's
  open line.

## Altered

- `spec/method-skills.md` section 3 (the `decisions` field); DECISIONS-level. No engine version
  bump: the renderer and template are not shipped in the package; the operator skill rides with
  the next install.

## Open

- The acceptance run by someone other than the developer, measured (the owner picks the tester),
  after the pushes, the install `0.2.20-sc0.5.1` and the republish of the operator, declare and
  analysis skills.
- The toy analysis skill re-rendered with the new template (`stringency-toy-method`, the owner's
  remote).

## Verify

    UV_PROJECT_ENVIRONMENT=.venv-test uv run pytest tests/test_render_skill.py
    cd ~/github/stringency-xenium-method && STRINGENCY_BIN=~/mytools/stringency/stringency/.venv/bin/stringency STRINGENCY_SESSION_REF=x controls/synthetic_upstream.sh v0.6.0-rc16

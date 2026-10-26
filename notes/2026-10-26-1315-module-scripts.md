# 2026-10-26: module scripts (row L113; phases 0 to 4: the engine and every Xenium module)

## Goal

The owner's comments on the methods' module scripts: the `pre.*` scripts drive the analysis and
neither their name nor their place says so; they must be legible to a person looking for what a
method does and which tools it uses; bringing existing code into stringency should be easy. Plan
in every method, Xenium first.

## Done

- Surveyed the four methods and the engine's handling of scripts:
  - Xenium: 23 scripts, 12 headers behind `module.yml`, R one-liners up to 576 characters.
  - scRNA-seq: 8 Python scripts; tuple-packed parameters, a committed `__pycache__`.
  - Plasmidsaurus: still the empty template.
  - Toy: already readable.
  - `entry:` exists, the interpreter goes by suffix, the script blob is content only. So no
    contract change is needed.
- The owner chose:
  - scripts named after the module, set by `entry:`;
  - `<name>_evidence.py` for judgment modules;
  - scripts stay in `modules/<name>/`, with a README index;
  - a recipe, skeletons and a wrap skill for existing code;
  - this restructure only, with the annotation items parked.
- `spec/plans/module-scripts.md` (the reasoning, phases 0 to 7), row L113, the DECISIONS entry, the
  `spec/README.md` row.
- Phase 0, committed as `c62bcae` on `main`, not pushed:
  - `docs/method-author.md`: "Module scripts" and "Bringing existing code in".
  - `templates/method-repo`: `_rlib/stringency_io.R` and `_pylib/stringency_io.py`, with the same
    names in both; `ruff.toml`; `.lintr`; the hooks; CI.
  - `templates/module/`: R and Python skeletons. Both ran on a three-row table, the R one in the
    `xenium-r` image.
  - The toy method's scripts renamed with `entry:` and a `CHANGELOG.md`, versions kept. The
    engine tests that name them follow; lint's missing-script case is tested both ways.
- Phase 1 in `../stringency-xenium-method`, uncommitted on `main`:
  - `cluster-umap` 0.4.2 as `cluster_umap.R`: a fourteen-line header, `CHANGELOG.md` holding the
    old header verbatim, one statement per line.
  - `_rlib/clustering.R`: the Leiden grid, the small-cluster folding, the resolution tables and
    splits, as named functions.
  - `_rlib/stringency_io.R` from the template, plus a marked transitional block that loads
    Seurat for the unconverted scripts. The figure helpers moved there out of
    `stringency_upstream.R`.
  - `.lintr` and `ruff.toml`, with the unconverted scripts excluded.
  - CI and pre-commit run ruff, lintr and `tools/check_index.py`.
  - The README section "Where the analysis happens": every pipeline step and tool with its
    script, what it does, and its tools.
  - `tests/compare_deliveries.py` and `tests/compare_rds.R`.
  - `tests/run_upstream.sh` and `run_select_resolution.sh` read `entry:`.
  - `xenium-upstream` 0.6.2; `PLAN.md` section 6.

- Phase 1 verified on PROTSEQ, with both sides under `versions/0.2.27-sc0.6.2`. The setup was a
  scratch clone with the pilot committed there only. The synthetic `xenium-upstream` study ran at
  `v0.6.0-rc19` and at the pilot, and `tests/compare_deliveries.py` compared the two step by
  step:
  - Every CSV, TSV and JSON output is byte-equal, every RDS object compares equal in R, and every
    `cluster-umap` figure is byte-equal.
  - What differs is the engine's bookkeeping: action ids in the `.stringency.json` sidecars, hold
    ids in `review/` and `consensus.json`.
  - Two `apply-labels` UMAPs drawn with `repel = TRUE` also differ, and the report embeds them.
    The unchanged rc19 `apply-labels`, run twice on the same inputs, gives different bytes for
    the same two: ggrepel is unseeded there.
  - Old and new `cluster-umap` run directly with `cluster_method=igraph_leiden` (the synthetic
    study uses Louvain) gave identical tables, object and all fifteen figures.
- The Xenium method moved to the current predicates (the owner's ask; engine row L86, method
  item 4.3), on `main`, uncommitted:
  - Gates: `sc.area_join_unverified@2`, `sc.low_cell_count@2`, `sc.decision_unreviewed@2`. The
    plugin's 0.8.1 diff shows each is unchanged for this method.
  - `judg.numeric_claims_match` is gated by bare id in the three judgments, and left
    `exclusion-proposal` (a deterministic module, out of its scope).
  - `resegment-nextflow` declares `egress` class 1 (github.com, registry.nextflow.io; nothing
    from the project is sent).
  - `requires` is engine `>=0.2.28` and singlecell `>=0.8.1`.
  - Ten modules and six pipelines bump a patch version, each with a `CHANGELOG.md` entry.
  - Lint is clean under 0.2.34-sc0.8.4, and under 0.2.28 with plugin 0.8.1 (what CI installs).
    The skill check passes at both engines.

## Learned

- `requires.engine` at 0.2.29 or above opts a method into lint's decision-point error (every
  decision point needs a `decision:` block). For the Xenium method, a block with `hold: always`
  would not open under `run` (L100) and would retire `sc.decision_unreviewed@2` for that point,
  so the sign-off at the default would be lost. That is why `requires.engine` stays at
  `>=0.2.28`, and why `judg.numeric_claims_match` is gated by bare id: 0.2.28 to 0.2.32 register
  @1 only, and CI installs the lower bound.

- `exec.plan_drift` (operator-run steps only) reads `params: k=v` lines from the job log and
  compares each value with the admitted one. A list logged as `a,b`, or text with spaces, would
  read as drift. So `log_params` writes only values the reader can compare, and puts the rest on
  an `other params:` line it does not parse.
- The toy method's versions are pinned throughout the engine's tests and goldens. Its rename
  keeps the versions (same bytes, same blobs) and says so in DECISIONS.
- SeuratObject's `Misc<-` warns on every overwrite ("Overwriting miscellanous data"), which the
  test scripts filter out. The template's `set_flag` assigns the slot directly.
- lintr 3.4 prefers `|>` by default (`pipe_consistency_linter`). It is off in both configs, since
  `%>%` is what Seurat and tidyverse code reads like.
- The local engine environment has no singlecell plugin, so `stringency lint` of the Xenium
  method gives 52 errors here, the same before and after the change. The real lint runs on
  PROTSEQ.
- The Xenium method at `v0.6.0-rc19` does not init under the shared install, 0.2.34-sc0.8.4. Lint
  fails on gates the plugin no longer registers at those versions:
  - `judg.numeric_claims_match@1`;
  - `sc.decision_unreviewed@1`;
  - `sc.area_join_unverified@1`;
  - `sc.low_cell_count@1`.

  It also fails on `resegment-nextflow`'s undeclared egress (L86). This predates today: the
  method's next tag must move those gates. The pilot was verified with both sides under
  `versions/0.2.27-sc0.6.2`, where rc19 and the pilot lint clean with the same twelve warnings.
- The `stringency_upstream.R` split into `pca.R` and `batch.R` moved to phase 2 with its two
  callers (`reduce-pca`, `select-resolution`), so phase 1 changes no unconverted script.

## Later the same day: every Xenium module

- The owner read `cluster_umap.R`: "the code looks much better". They asked how the switch to
  Leiden is decided: a person decides, with `cluster_method` proposed above about 600,000
  cells. The module only warns. A session the owner started built `sc.louvain_too_large@1`
  (singlecell 0.8.6, branch `singlecell-louvain-too-large` in `stringency-plugins`,
  `9b6a779`, not pushed).
- The pilot and the predicates were committed in the method as `9bf12a7`. The other 22
  modules were committed as `0a945ed` (the method's `PLAN.md` 6.2 to 6.4 and its note). Three
  subagents did the QC chain, the open tools and the judgment evidence scripts, with disjoint
  files; the session did the upstream R modules and the shared files. Every module is
  identical to `9bf12a7` on PROTSEQ under 0.2.34-sc0.8.4. The method's note has the detail.
- The template's `_pylib/stringency_io.py` `write_table` now ends rows with `\n`; it had
  Python csv's default `\r\n`.
- L114 filed: in open mode an accepted hold leaves the tool's step `admissible` with no verb to
  run it, and calling again makes a new step.
- The Louvain gate: plugin singlecell 0.8.6 tagged `sc.louvain_too_large@1`. It also flagged
  the Xenium method's `select-resolution`, which shares the `cluster_umap` operation. 0.8.7
  (tag `v0.8.7`, `8f9f4f6`) is `@2` and judges only a module that declares `cluster_method`.
  The method's `cluster-umap` 0.4.4 gates `@2`, requires singlecell `>=0.8.7` and states
  `sc.louvain_max_cells` at 600,000 (method `a8dc69a`). On PROTSEQ, with the band lowered to
  1,000 cells, the synthetic study was flagged at 04 only. The shared install is still
  0.2.34-sc0.8.4 and needs 0.8.7 (the owner).

## Later still: phases 5 to 7

- The owner installed 0.2.34-sc0.8.7 as the shared install, so `current` points at it.
- **The scRNA-seq method** (`../stringency-scrnaseq-scanpy-method`, cloned this session),
  committed as `f15590e` (its 0.1.10, untagged):
  - The eight scripts are named after their modules.
  - `_pylib/common.py` became `stringency_io.py` (the template) and `scrnaseq.py`.
  - The committed `__pycache__` is gone; ruff, CI and `tools/check_index.py` added.
  - Verified on PROTSEQ against `v0.1.9`. `tests/run.sh`'s outputs are byte-identical: tables,
    JSON, the five h5ad files, the two figures. The lineages and the interferon genes are
    recovered, and the eight controls pass with identical outputs.
- **The Plasmidsaurus method** (cloned): the template's helpers, style files, hooks, CI and
  README, plus the template's `requires`, which CI reads. Committed as `2c93b04`.
- **The wrap skill**:
  - Written as `integrations/claude-science/stringency-wrap/SKILL.md`, added to
    `scripts/install.sh`'s copied skills and to `publish-skills.md`.
  - A fresh agent followed it on a stand-in lab script into a scratch copy of the toy method.
    The output was byte-identical and lint clean.
  - Its findings went into the skill:
    - keep the code's own reading and writing, since `stringency_io`'s writers may differ in
      line endings;
    - how to choose an operation, and code that spans two;
    - a "module only" option;
    - running in a lockfile environment, and the job's keys;
    - finding the engine outside Claude Science;
    - naming inputs and outputs.
  - They also fixed two contradictions: `templates/module/README.md` had the old order, and
    `docs/method-author.md` named the script `<name>.R`.
- The shared install's skills were copied before the wrap skill existed. It arrives with the
  next install, or by hand.

## Open

- The method's next rc tag, on the owner's word. The Xenium method's `PLAN.md` 4.4: the open
  tools' batch term under `de.covariate_omission`, and the open-tools check (holds, reference
  level).
- The tags of the Xenium (next rc) and scRNA-seq (`v0.1.10`) methods; publishing the wrap
  skill. The public `stringency-toy-method` repository still has `pre.py`.
- Nothing of this session's is pushed: the engine (`c62bcae`, `f232d62`, `c8a4086`, `9dfb02b` and
  this), the Xenium method (`9bf12a7`, `0a945ed`, `a8dc69a`), the scRNA-seq method (`f15590e`),
  the Plasmidsaurus method (`2c93b04`). The plugin's 0.8.6 and 0.8.7 were pushed and
  tagged from the owner's plugin session.

## Verify

```
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy && scripts/check_no_biology.sh
# on PROTSEQ, a scratch clone of the Xenium method with the change committed there:
controls/synthetic_upstream.sh v0.6.0-rc19 <scr_old>; controls/synthetic_upstream.sh <commit> <scr_new>
tests/compare_deliveries.py <scr_old>/upstream_project/runs/<run> <scr_new>/upstream_project/runs/<run>
```

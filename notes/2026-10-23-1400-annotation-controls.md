# 2026-10-23: annotation controls (L110 to L112; Xenium method 3.15 to 3.21; plugin 0.8.5)

## Goal

A tour of the Xenium method (`santangelo-lab/stringency-xenium-method`, cloned beside the engine
at `v0.6.0-rc19`), then the owner's points on its annotation taken into the plans and the first
check built: the fine label needs more control (gut cluster 9, "enterocyte, IFN/stress", does not
hold up), and the fraction expressing and `pct_diff` must weigh in the annotation.

## Done

- Read the method end to end and the plugin; traced one step through `steps.py`, `judgment.py`,
  `consensus.py`, the extractors and the predicates; traced `fine_label` from the module's schema
  to `apply-labels` and the report.
- Measured the evidence on the annotation control's ROSC liver fixture (the module's `pre.py` run
  on it in the session scratchpad).
- `spec/plans/annotation-controls.md`, rewritten after the owner's answers: what the code does,
  the proposal (A to F), twenty candidate state programmes, three ways to make one fine label of
  three, the contract impact.
- `PLAN.md`: L110 (engine: a person's choice and correction carried through `consensus.json`),
  L111 (plugin), L112 (engine: a judgment with no items completes without a dispatch), one row in
  the waiting table. `spec/README.md`: the document, the plans table's `benchmark-plan.md` bullet
  made a row (it broke the table), PLAN rows to L112.
- The owner chose both designs for one fine label of three; `annotation-controls.md` section 4
  holds the design: `09_reconcile_fine_labels` (deterministic agreement on evidence-backed claims)
  and `10_choose_fine_labels` (a judgment over the contested clusters only, choosing among the
  candidates with the positional vocabulary `fine_label_choice@1`), `xenium-upstream` 0.7.0.
- The Xenium method's `PLAN.md` items 3.15 to 3.21 (uncommitted, on `main`).
- Plugin singlecell 0.8.5 in `../stringency-plugins` (cloned beside the engine this session,
  uncommitted, on `main`): `sc.fine_label_uncited@1` in `predicates/annotation.py`, its CASES
  entry and three variant tests, the surface tests, README and `spec/predicates.md`, `uv.lock`.
- Branches: the owner asked for `main` only; the engine's local `main` was fast-forwarded to
  `origin/main` (`f6041d2`, which holds the merged gate review, PR #16) and the session's two
  empty `annotation-controls` branches were deleted.

## Learned

- The engine never names `fine_label`: agreement is on `label` alone, `consensus.json` drops the
  field, and `apply-labels` takes the first agreeing replicate's. A person's `review --choose`
  records accept with the first replicate that called the label, which `apply-labels` does not
  read; an override carries only `label` and `ontology_id`, and `choose` writes it without the
  id.
- On the ROSC liver fixture, 38 percent of `markers_top` rows have `pct_diff` below 0.2, and 38 of
  the 70 canonical cells at scaled mean 0.7 or above that have a marker row do too, at both ends.
- The positive control's fixture keeps the fraction expressing only where the archive had a
  marker row: 473 of 1,040 canonical `pct_<c>` cells read `na`.
- `judgment.must_cite` binds cells in rows keyed by the item, so per-cluster facts to be cited
  belong in `cluster_summary`.
- `summary=` on `@predicate` is newer than engine 0.2.33, the tag the plugin workspace pins; a
  plugin predicate cannot use it until the pin moves.
- A gene check can stay free of biology by taking genes from the step's own evidence tables (a
  table keyed by `gene`, a `gene` column). It cannot see words that are not symbols, which is why
  "IFN/stress" needs the programme evidence and an alias table.
- `test_extract_seurat_envelope` fails on this Mac before and after the change: the local R has
  no `SeuratObject`.
- `judgment.execute_judgment` has no case for an items table without rows: it would render and
  dispatch the replicates with an empty list (L112).
- A judgment step writes only its `judgments` and `consensus` outputs; the evidence tables its
  `pre.py` wrote stay in the step directory, so a later step that must resolve the reviewers'
  citations rebuilds them (`_pylib/annotation_evidence.py` in the plan).

## Altered

- The owner's decisions: one free-text fine label, never split and never from a preset list;
  state programmes are evidence for writing it. The first draft's split and computed states were
  withdrawn the same session.

## Open

- The owner: the programme list; the `pct_diff` floor; a written reading of gut cluster 9 (the
  Lyons data is not on this machine).
- Commit the three repositories when the owner says so; a plugin tag `v0.8.5` (or the workspace's
  next tag) after CI. The method's `PLAN.md` Status line still stops at 2026-10-15 (rc16).
- Build order: method 3.15 (no engine or plugin change); 3.16 with the programme-word check;
  engine L112 and L110; the plugin's operations and `fine_label_choice@1`; method 3.17, 3.21 and
  3.18 together as `xenium-upstream` 0.7.0; 3.19; 3.20 at the method's next tag.

## Verify

```
cd ../stringency-plugins && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/stringency-singlecell/src
```

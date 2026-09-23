# 2026-09-23 11:00, the seven outlier holds decided; the delivered consensus is stale

## Goal

Relay the owner's verdicts on the six item holds and the flag in `qc_outliers_all`
(run `01M32Q6MK30YFWZVGJRYT66BF1`), then `run --deliver`. Claude Code session on PROTSEQ, engine
`0.1.0+optin3-sc0.1.8` from the per-user install, mode A (engine on this machine, both steps
`runner: engine`).

## Done

- Seven `review --attest` calls, each with the owner's verdict word and reason, all `via: relayed`:
  accept replicate 1 on 48-1-Liver (review), 48-2-Liver (review), 24-1-Liver (keep), 6-1-Lung-B
  (review), 24-1-Spleen-A (review), 24-1-Spleen-B (keep); accept on the `sc.exclusion_proposed`
  flag ("evidence needs updating but correct for now"). Every hold row carries its
  `resolved_by_review`; the `consensus` table carries the six labels with `source: accepted`.
- `run --json --deliver`: `02_proposal` ran, the run completed, delivery
  `01M37CDYQ5JAKHABDXRV2F3VVB` under `deliver/01M32Q6MK30YFWZVGJRYT66BF1/`.

## Learned

- **The delivered proposal does not carry the verdicts.** `02_proposal.exclusion_proposal.csv`
  lists the six decided punches with an empty verdict and `consensus_source: unresolved`, and the
  Markdown proposes only 6-1-Lung-A and 6-2-Spleen-A. `summary.md` from the same delivery says
  "reviews: six accepted, none corrected, none unresolved". The trace is right; the artifact is
  wrong.
- Cause, read in the code: `judgment.py` writes `consensus.json` once, from `settle_items`, at
  judgment time, so a held item is filed as `label: null, source: unresolved`. `review.py`
  `_apply_item_verdict` writes the verdict to the `consensus` table only. `_settle_step` moves the
  step to completed without rewriting the output or its hash in `history`. `02_proposal` binds
  `$steps.01_flag_outliers.consensus`, the file. Design 8.4 says an `unresolved` item cannot exist
  in a completed step; the store honours that, the artifact does not.
- The same timing hits the gate: `sc.exclusion_proposed` ran in the post phase of `01_flag_outliers`
  at 19:38:27 on 2026-09-21, the same second the item holds opened, so its evidence counted two
  proposed punches. After the verdicts the decided consensus has six. The owner accepted the flag
  knowing this ("evidence needs updating").
- Operator notes: `accept` on an item hold needs the replicate number even when all three labels
  are identical; the skill says so and the owner supplied it. `sqlite3` is not installed on
  PROTSEQ; `python3 -c "import sqlite3"` reads `prov/run.db` for inspection.

## Altered

Plan documents only: `spec/plans/backlog.md` K7; `spec/plans/roadmap-2026-09.md` Status,
Lane A item 6, Lane D item 7; `spec/plans/app1-spatial-qc-plan.md` S4 row and the Track 3 open
list. No code, no design text. In the project: nothing under `prov/` or `method/`; the delivery
stands as the engine wrote it.

## Open

1. K7 (first Lane A item, before the PR): rewrite the consensus output from the store when the
   last item hold resolves and the step completes, re-record the artifact hash; evaluate
   post-phase predicates that read `output.consensus` after the item holds settle; one test that
   accepts a replicate on a held item and asserts the file and a downstream step see the label.
2. Decide how a completed run repairs its artifact: a regenerate verb that rebuilds the step
   output and delivery from the trace, or `run --new` in `qc_outliers_all` with the judgment
   dispatched again and the holds re-decided. The owner's call; the six recorded verdicts and
   reasons are in `reviews` either way.
3. Until then the delivered proposal in `qc_outliers_all` is not the review list. Reading the
   store, the punches flagged for a person's look are 6-1-Lung-A, 6-2-Spleen-A, 48-1-Liver,
   48-2-Liver, 6-1-Lung-B, 24-1-Spleen-A.
4. Method-side items are now in `stringency-xenium-method/PLAN.md` (created today).

## Verify

```bash
cd /lab/projects/Lyons_CLP/qc_outliers_all
python3 -c "import sqlite3; db=sqlite3.connect('prov/run.db'); print(*db.execute(\"select item_id,label,source from consensus where source!='agreed'\"), sep='\n')"
grep -c unresolved deliver/01M32Q6MK30YFWZVGJRYT66BF1/02_proposal.exclusion_proposal.csv   # 6 today
```

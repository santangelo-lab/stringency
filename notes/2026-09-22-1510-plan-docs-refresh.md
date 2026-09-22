# 2026-09-22 15:10, plan documents brought up to date after Lane C

## Goal

The plans under `spec/plans/` still described Lane C as future work and the backlog had none of
what the Lyons CLP runs found. Bring them to the state of 2026-09-22 without touching code.
Nothing ran; no project changed.

## Done

- `spec/plans/roadmap-2026-09.md`: a Status section (2026-09-22) after the header; Track 3
  header marked done to S4; Lane A item 6 (packet renderer, per-item flag resolution, `any_low`)
  and a state paragraph listing the eight branch commits and what the branch does not contain;
  status paragraphs under Lanes B, C and E; Lane D items 1, 3, 4, 6 marked with their state and
  item 7 added (owner items left by Lane C); the Verification line for `xenium-qc` marked done.
- `spec/plans/app1-spatial-qc-plan.md`: section 5, outcome against the plan, a table S0 to S4
  planned against built, the five departures from section 3, and the open list for Track 3.
- `spec/plans/backlog.md`: rows K1 to K6 (packet renderer, confidence criteria and `any_low`,
  impossible band edges, board `--watch`, `present --hold` default, tags pushed before checks);
  a status line; a note that no Lyons CLP run has a measurement row.
- `spec/plans/lane-c-day1-2026-09-17.md`: the pick-up section now says the log closed on
  2026-09-18 and points at the 2026-09-21 notes and `PROGRESS.md`; the old pick-up kept below it.
- Status paragraphs at the end of `ux-two-audiences.md` section 9, `bulkrna-plan.md` section 7,
  and `declarations-and-objectives.md` Order of work (option 1 exercised by fourteen chained
  projects; where it chafed was the confirm hold, not the objective).
- `spec/README.md`: plans table rows for the roadmap and app1 plan updated, a row for the Lane C
  log added.
- `spec/DECISIONS.md`: the three lines that existed only on branch `lane-c-directory-inputs`
  (`init.column_missing` and `derived_from`; `board` and `present`; the delivery skill lives in
  the method repo) appended to `main` verbatim, so the ledger on `main` covers code that has been
  running since 2026-09-18.
- `notes/2026-09-18-1830-board-and-present.md` copied from the branch to `main` and indexed; the
  index's Notes list put back in newest-first order with one format.

## Learned

- The spec is split across two branches. `main` has design 2.3 (directory inputs), the Lane C
  plan and the notes; the branch has design 14.4, the optional and reference input sentences, and
  the operator skill's section 7. Whoever opens the PR has to merge the design text by hand and
  should compare `notes/INDEX.md` and the roadmap, which the branch also edited before `main`
  overtook it.
- Lane D item 3 looked done from the notes but is not: `/data/lab/env/stringency/` is an empty
  directory; only the images directory exists.
- The Lane C log's "engine gaps" are spread over four dated sections; the roadmap's Lane A items
  5 and 6 are now the one list to work from.

## Altered

Nothing below the plan level. No design text, no contract, no code.

## Open

1. Open the PR for `lane-c-directory-inputs` and resolve the spec split above; tag; reinstall.
2. The owner's seven holds in `qc_outliers_all` (roadmap Lane D item 7).
3. Whether `spec/plans/lane-c-day1-2026-09-17.md` should move to `spec/archive/` now that it is
   closed; left in `plans/` because three notes and the roadmap cite its path.

## Verify

```bash
git -C ~/mytools/stringency/stringency diff --stat HEAD~1 -- spec notes
grep -n 'Status (2026-09-22)' spec/plans/roadmap-2026-09.md
```

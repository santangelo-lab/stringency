# The bulk delivery is shallow: replan Track 2 around development data

## Goal

Take the owner's reading of the vendor QC into the plan: the RMLDH7 delivery generated very few
reads, the experiment will probably be re-sequenced, and the files on hand serve to develop the
pipeline rather than to answer the question.

## Done

- Checked the vendor per-sample statistics (`vendor_results/RMLDH7_mapping-stats/*.tsv`, 44
  files): spleen median 0.9 M input reads and 0.25 M after UMI deduplication (lowest 0.10 M);
  liver median 8.0 M and 2.5 M (lowest 1.0 M); deduplication keeps about 30 percent everywhere.
  Recorded in `spec/plans/bulkrna-plan.md` section 1 (data status), the roadmap context, and the
  project README on `/data/lab/projects`.
- Projects A and B on this delivery are development projects: `exploratory` profile, labelled
  development, QC report delivered first (`--until 02_qc`) as the evidence for re-sequencing;
  final projects later from the same method tag under `standard`.
- Roadmap order revised: Track 2 sessions 0 to 7 unchanged (synthetic data); session 8 next;
  then Track 3 S1 to S4 move ahead of Track 2 sessions 9 to 12 because Lyons CLP is final data
  and `xenium-qc` becomes the first scientific deliverable; Project B uses the small spleen fastqs
  as its smoke test; the final bulk run is a declare-run-deliver on the new delivery.

## Learned

- `bulk.low_library_size` at the wide band (1e6) fires on every spleen sample; the pipeline's
  first real output is the QC report that says so, which is the right first output.

## Altered

Roadmap order only. No spec change.

## Open

1. Owner: request re-sequencing from the vendor (or decide against it) with the QC report from
   session 8 in hand; deposit the new delivery with the raw-deposit skill when it arrives.
2. Everything else as in `notes/2026-09-15-1130-approvals-walkthrough.md` Open items 2 to 4.

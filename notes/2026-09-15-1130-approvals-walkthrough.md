# Approvals walk-through: Track 1a amendments, Track 2 session-0 decisions, Track 3 decisions

## Goal

Pick the project back up after the Phase A exit and collect the owner's answers on everything the
roadmap marked as needing approval, so the next sessions can build without stopping to ask.

## Done

- Track 1a: all five amendment texts approved as written and applied to `spec/stringency-design.md`
  (7.5 `via: web` paragraph and the summary line 8; 10.4 two kinds of skill; 12.1 `summary.md`;
  14.1 `run --responses`, `run --deliver`, `review --serve`). The section 17 review-page row stays
  until the page exists. `spec/plans/ux-two-audiences.md` section 8 heading records the approval.
- Track 2: thirteen session-0 decisions answered and written into `spec/plans/bulkrna-plan.md`
  section 8, with the consequences propagated to sections 1, 4, and 5 and to the roadmap. The
  material change is the DE method: DESeq2 instead of limma-voom (module `de-deseq2`, `~ condition`,
  all pairwise contrasts within tissue, p 0.05, |log2FC| 1.0, minimal prefilter plus independent
  filtering, edgeR and limma leave the image). Image via Dockerfile, GitHub Actions, GHCR, digest
  pull into `/data/lab/env/images/`. Reviewer is the person running the pipeline (design line 75
  already allows owner = reviewer). All 44 samples declared for Project A; the project README on
  `/data/lab/projects` gained a paragraph naming Project A as the deliberate exception to its
  vendor-outputs rule.
- Track 3: four of five decisions answered in `spec/plans/app1-spatial-qc-plan.md` section 4.
  Segmentation is a mix following ROSC (confirmed from `setup/sample_manifest_complete_v2.csv` on
  BMESEQ: Liver, Spleen, FRT `10xSeg`; every other tissue `Proseg`), so S3 gains a
  `resegment-proseg` module ahead of `split-punches`. Splitter fix in its own repo first, MTA
  outputs frozen. Per-tissue QC thresholds; histology include/exclude as a manual input file.

## Learned

- Facts from the deposit, now in the bulk plan: the UMI is in the fastq read name (14 nt after an
  underscore), so nf-core needs `--skip_umi_extract --umitools_umi_separator _`; vendor mapping
  statistics are one per-run CSV and per-sample eleven-row TSVs; the vendor quantified 3, 2, 2, 1, 2
  spleen samples per group, so spleen contrasts on vendor counts will hold under standard.
- In ROSC, Proseg runs on the whole region and the split happens on the resegmented bundle, so
  resegmentation belongs before the splitter in the pipeline, not after.
- The salient-genes judgment module needed a plain description before the owner could decide on
  it; the description in this session's transcript is the one to reuse in `spec/bulkrna-design.md`.

## Altered

Design sections 7.5, 10.4, 12.1, 14.1 by owner-approved amendment (not DECISIONS-level; recorded
in the design text with the approval date). No frozen contract touched. No code.

## Open

1. Owner: share the Lyons CLP experimental plan document and walk through the replication unit,
   factors, and levels (Track 3 decision 1) in a dedicated conversation; S0 waits on it.
2. Session 0 of Track 2: the DESeq2 parameter list (which of `fit_type`, `lfc_shrink`,
   `cooks_cutoff`, `independent_filtering`, `alpha`, `block_by_animal` are adjustable, and their
   defaults) is to be discussed while designing, then `spec/bulkrna-design.md` written.
3. Still the owner's: commit the 51 uncommitted files in `ROSC_MTA2`.
4. Next build session as planned: Track 1b engine flags with the Track 1c skill text, then the two
   Track 1g session tests on PROTSEQ. Track 1e (review page) and 1f may now start since 1a is
   approved.
5. Backlog design questions G2 and H5 remain open and were not raised today.

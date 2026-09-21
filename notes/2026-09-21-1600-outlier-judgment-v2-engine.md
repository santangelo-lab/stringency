# 2026-09-21 16:00, outlier judgment v2: engine changes and findings

## Goal

Let the redesigned `flag-outlier-punches` (stringency-xenium-method 0.2.0) run: an optional
reference input, extra evidence tables a pre-script writes, and a reference input that is not
this design's data. Then run it on Lyons CLP and record what the first three-replicate real
judgment taught about the engine.

## Done

On branch `lane-c-directory-inputs` (three commits, tests green, engine suite 240 passed):

- `12f2f33` `IOSpec.optional`: a pipeline step may leave an optional module input unwired; lint
  allows it. Lint also accepts `judgment.evidence` names that are not inputs when the module has
  a `pre.*` script, which `prepare_evidence` already did (design 3.5 step 2).
- `1d58127` `prepare_evidence` keyed every evidence table by `item_key` and raised KeyError on a
  table without that column; secondary tables (a metric guide, a reference summary) now key by
  their first column. `judg.evidence_exists` resolves cells in them by that key.
- `41fc5cc` `InputItem.role` (`observation` | `reference`); `init.column_missing` skips
  `role: reference` inputs as it skips `derived_from` ones. Spec sentences beside each.

Installed on PROTSEQ as `0.1.0+optin3-sc0.1.8` (`~/mytools/stringency/engine/current`, plugin
stringency-singlecell 0.1.8 = tag v0.1.11). Method v0.3.3-rc1 (local tag). Real run
`01M32Q6MK30YFWZVGJRYT66BF1` in `/lab/projects/Lyons_CLP/qc_outliers_all`: three subagent
replicates, all gates passed first time, 36 of 42 items agreed, six item holds and the flag for
the owner. Data-side record: `/lab/projects/Lyons_CLP/PROGRESS.md` (2026-09-21); method side:
`stringency-xenium-method/notes/2026-09-21-1500-outlier-judgment-v2.md`.

## Learned

- Three replicates that agree three times in a row (the v1 run) meant the task had no judgment
  in it. With a prompt that asks for reasoning (direction, size, band size, reference, sibling
  punch, mechanism) the replicates split 2:1 on three items and reported low confidence on three
  unanimous ones. That is the signal the design wanted.
- The confidence criteria fight the evidence slots. `high` needs zero contradicting cells; a
  reviewer who honestly lists the cells that argue against its label lands on `medium` or `low`
  even when its reasoning is sound. Under the standard agreement rule `any_low` then opens a hold
  for an item all three called `keep` (24-1-Liver, 24-1-Spleen-B). Either the criteria should
  tolerate a contradicting cell at `high`, or `any_low` should hold only when labels differ.
- The review-packet renderer does not resolve the three-table evidence layout: every citation
  prints "(no such cell)" and "evidence row: none" although `judg.evidence_exists` passed on the
  same run. Display only; the trace is right.
- A within-study band on five values can have a negative lower edge for a count. The module
  should clip or mark it, but the engine could also warn when a band edge is impossible for the
  column's type, if columns ever carry types.
- The "rule constants in words" line in the prompt removed the `judg.numeric_claims_match` false
  positives of 2026-09-18 without weakening the check: 126 rationales, no numeral problem.
- Dispatch briefs: the operator no longer passes any instruction beyond the request file path;
  everything the reviewer needs is in the rendered prompt, so the trace holds the whole brief.

## Altered

- Module contract v1 gains `inputs.<name>.optional` (default false). Not a breaking change.
- Inputs manifest gains `items[].role` (default `observation`). Not a breaking change.
- Lint rule "every judgment.evidence is an input" relaxed for modules with a pre-script.

## Open

1. Review-packet renderer for multi-table evidence (`review.py` / `holds.py`): resolve the row
   by the cited table's own key, not the item key.
2. Lane A: per-item resolution at a flag hold (the owner should be able to accept some flagged
   items and not others); `any_low` on unanimous items (above).
3. Open the PR for `lane-c-directory-inputs` (now eight commits ahead of main); push method
   v0.3.3-rc1 and plugin v0.1.11 so `qc_outliers_all/stringency.yml` can record the GitHub URL
   instead of the local path.
4. Next session starts by reading the seven holds' verdicts the owner recorded (or relaying them),
   then `run --deliver` in `qc_outliers_all`.

## Verify

`uv run pytest` on the branch (240 passed); `stringency lint .` in the method repo (clean);
`tests/run_outliers.sh` in the method repo (pre-step with and without reference, mock pipeline,
both controls pass).

# 2026-10-22 07:00: the benchmark plan adapted; Phase 0 started

## Goal

Take the owner's benchmark plan (2026-10-21) into the repository, adapted to engine 0.2.33 and
this machine, and begin Phase 0 (the baseline on Latch's public evals) with Claude Code and
Opus 5.

## Done

- `spec/plans/benchmark-plan.md`: what changed on contact (L55, L54, L56, L57 built; Opus 5 is a
  new row beside Latch's opus-4-7 and opus-4-8; no Docker here; the subscription instead of an
  API key; the Latch login), where things live, the runner and the arms, the phases as rows
  L87 to L92, the open questions with what is known. `PLAN.md` has the Benchmark section,
  the Next item 8, and the login in the waiting table. DECISIONS one entry. `spec/README.md`.
- `/lab/projects/2026-10_stringency-benchmark_jrrose5/`: the three Latch repositories cloned,
  a venv with latch-eval-tools 0.4.54 and the `latch` SDK, Latch's agent image pulled with
  apptainer (`images/benchmark_agent.sif`, from `public.ecr.aws/p5z7v3z8/benchmark_agent`).
- `latch/run_eval.py` (moved the same day to the separate repository `santangelo-lab/stringency-benchmarks`, private, at the owner's ask): the baseline arm as Latch's Claude Code harness builds it
  (the flags, the prompt with the data instructions and the background-process note, the
  `agent_workspace/data` layout, stream-json to `trajectory.json`, the `result` event's cost,
  turns and usage), the agent inside the image under apptainer or on the host, grading
  through `EvalRunner`, `result.json` per replicate, and `--summary` with Latch's t-interval
  over per-eval means. A synthetic eval passed end to end on Opus 5 (7 turns, 43 s, $0.32).
- The published reference on the six scBench public evals, Claude Code with opus-4-7, three
  trials each: QC, normalisation and cell typing 3/3; DE 0/3; PCA 0/3; the Tapestri clone 1/3;
  10 of 18. Mean cost per trial about $1.06, the Tapestri eval $4.53.

## Learned

- Latch's eval JSON carries the task under `task`, the data as `latch://<id>.node`, the grader
  and the authors' notes (what the trap is, what the grader rejects): the notes are the
  Phase 1 mapping's raw material and must not reach the agent.
- `claude -p --model claude-opus-5-5` works on this machine's subscription and reports
  `total_cost_usd`; the stock harness needs `ANTHROPIC_API_KEY` and Docker, neither here.
- `latch login` is a browser flow writing `~/.latch/token`; it cannot be done from this
  session.

## Altered

Nothing in the engine. The runner lives in `stringency-benchmarks`, not here.

## Open

- The owner: `latch login` in the project venv; then the baseline runs start (the six
  scBench evals, three replicates, about 18 Opus 5 sessions).
- Phase 0 after the data: run, summarise, write the numbers beside the published pattern.

## Verify

`.venv/bin/python <stringency-benchmarks>/latch/run_eval.py --eval evals/smoke/smoke_mean.json
--no-image --max-turns 8` passes, and inside the image with the host's Claude Code; the engine suite is unchanged.

## Later the same day (Phase 1)

- The owner logged in to Latch; a free account serves the public data. All six scBench and
  seventeen SpatialBench datasets cached (about 32 GB). The baseline arm started at 20:57: the
  first QC replicate passed in 67 turns, 24.5 min, $5.19 (Latch's Opus 4.7 run: 19 turns,
  $0.81); eighteen sessions take the night.
- Phase 1: the mapping table in `benchmark-plan.md`; plugin singlecell 0.8.0 (widened beyond
  Xenium) and 0.8.1 (three Xenium predicates narrowed); the method
  `santangelo-lab/stringency-scrnaseq-scanpy-method` 0.1.0, private, eight modules, two
  pipelines, a planted fixture whose structure every module recovers exactly; lints clean under
  engine 0.2.33 with plugin 0.8.1. The engine releases 0.2.28 to 0.2.33 are tagged; the plugins
  workspace pins v0.2.33.
- On the real evals' data, `qc-metrics` (run inside the image) says what the gate will. BD
  Rhapsody, 16,136 cells x 386 genes, counts in `layers:DBEC_Adjusted_Molecules` beside an
  empty X: median 265.5 UMIs, median 68 genes per cell, 99th percentile 135, maximum 180, so a
  `min_genes` of 200 is blocked by `sc.qc_floor_above_data` before a cell is dropped. CS
  Genetics, 11,693 cells x 27,946 genes: median 1,655 UMIs, 73.9% of counts are 1, below the
  2,000 floor, so `log_total` is flagged by `sc.normalization_depth`. Both agree with the
  evals' author notes (first written here from the notes, corrected the same night from the run).

Later still, the method's skills (`stringency-scrnaseq-scanpy-method` 4652dd3, tag v0.1.0): the
delivery skills `skills/scrnaseq-upstream.yml` and `skills/scrnaseq-de.yml` (hold views on the
proposal holds cite `01_qc_metrics/qc_distribution.csv`, `qc_summary.json`, the elbow table with
`mark_param: n_pcs`, `pca_sentinels.json`; after-delivery tables from every step), the analysis
skills `.analyze.yml` (question `processed_object` and `differential_expression`; eight and five
decisions; `pseudobulk-de` and `score-panels` as tools; open paths), and `open.yml`. The renderer's
`--check` wanted every decision point of a tool settled in `asks` or `proposed`, so the DE
thresholds are asked with their defaults in the question and `min_cells_per_sample` is proposed
from `qc_report`; the skill description is capped at 1024 characters, so the phrasings were
trimmed. Both SKILL.md files are rendered and committed; `stringency lint .` has the one benign
warning (qc-metrics has no decision point). Nothing is published to Claude Science yet (the
owner's instruction). Baseline at this point: QC 3/3 and NRM01 3/3 done, PCA r1 running.

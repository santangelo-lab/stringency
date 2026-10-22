# Benchmark plan: stringency on Latch's public evals

The owner's plan of 2026-10-21 (`stringency_benchmark_plan.md`), adapted to the engine as it
stands on 2026-10-22 (0.2.33, plugin singlecell 0.7.0) and to this machine. The purpose, the
three claims, the arms, the metrics, the abstention risk and the "convincing result" section
are the owner's and are not restated; this file holds what changed on contact with the code
and the benchmarks, and the work rows. Not the spec.

**Status 2026-10-22, night.** Phase 0 running: the owner logged in to Latch (a free account serves the public data), the six scBench and seventeen SpatialBench datasets are cached, and the baseline arm (Opus 5, three replicates on the six) is running. Phase 1 mostly done: the mapping below, plugin singlecell 0.8.1 (widened beyond Xenium: any observation unit, droplet operation schemas, an `analysis_summary` object type, four droplet predicates, three Xenium predicates narrowed), and the method `santangelo-lab/stringency-scrnaseq-scanpy-method` 0.1.0 (eight scanpy modules inside Latch's image, two pipelines with `decision:` blocks on every known trap, a planted fixture and controls; lints clean; recovers the planted structure exactly). Its skills are written, checked and rendered and the method is tagged v0.1.0; a synthetic engine run remains. Earlier the same day: the tooling installed, the local runner working (`stringency-benchmarks`)
(a synthetic eval passed on Opus 5), the public evals and published trajectories are cloned.
The baseline runs wait on one thing a person must do: `latch login` (a browser flow) so the
SDK can fetch the eval data. Rows L87 to L92 in `PLAN.md`.

## What changed since the plan was written

- Phase 2's predicate items are built: L55 (`propose --cite`, `--considered`,
  `param.reason_unmatched`, `param.uncited`; 0.2.29), L54 (the seven downstream predicates;
  plugin 0.7.0), L56 (`must_cite`, `judg.required_evidence_uncited`; 0.2.33), and L57
  (`judg.numeric_claims_match@2` over cited cells). The "what exists" table's three open rows
  are closed; L58 (structured claims) stays open.
- The harness is Claude Code with Opus 5 (`claude-opus-5-5`), the owner's choice of
  2026-10-22. Latch's published Claude Code rows are opus-4-7 (trajectories) and opus-4-8
  (the headline 57.95%); no Opus 5 row exists, so our baseline is a new row beside theirs, and
  the Phase 0 exit reads: our Opus 5 baseline sits inside the published Claude Code interval
  (51.6 to 64.3 on the full set) or, on the six public evals, reproduces the published per-eval
  pattern (opus-4-7, three trials each: DE 0/3, PCA 0/3, Tapestri 1/3, QC, normalisation and
  cell typing 3/3; 10 of 18).
- No Docker on the workstation. Latch's CLI harnesses require it, so `latch/run_eval.py` in
  the `stringency-benchmarks` repository runs the same Claude Code command, prompt and layout
  on the host, with the agent inside Latch's own image pulled by apptainer
  (`public.ecr.aws/p5z7v3z8/benchmark_agent:latest`), and grades with `EvalRunner`. The one
  thing it cannot reproduce is the container memory cap; the host has 500 GB.
- Claude Code here runs on the lab's subscription (no `ANTHROPIC_API_KEY`); the stock harness
  refuses without the key, the local runner does not need it. Cost is still reported per run
  from the CLI's `total_cost_usd`.
- Data comes through the Latch SDK with a login token (`~/.latch/token`, written by
  `latch login`); nothing in their READMEs says whether a free account suffices. The data
  nodes are `latch://<id>.node`; the runner caches them under the project's `.eval_cache/`.
- Public evals: scBench ships six (`evals/`), SpatialBench seventeen (`example_evals/`, three
  of them Xenium kidney), each with three published trials per model and harness.
- The arXiv OmicsBench, Seqera: as the owner wrote; not pursued, not a benchmark.

## Where things live

- `/lab/projects/2026-10_stringency-benchmark_jrrose5/`: the clones (`scbench`,
  `spatialbench`, `latch-eval-tools`), the venv (`.venv`, latch-eval-tools 0.4.54), the image
  (`images/benchmark_agent.sif`), the data cache, and every run under `runs/<arm>/<eval>/rN/`
  in Latch's layout (`agent_workspace/`, `prompt.md`, `trajectory.json`, `eval_answer.json`,
  `result.json`).
- `santangelo-lab/stringency-benchmarks` (private; the owner's ask of 2026-10-22, a separate
  repository): `latch/run_eval.py` (the runner and the summary with Latch's t-interval over
  per-eval means), the smoke eval, and the arms as they are built. The engine repository holds
  the plan and the rows, never the runner.

## The runner and the arms

`run_eval.py --eval <json> --replicates 3 --model claude-opus-5-5 --image <sif> --out runs/baseline`
is the baseline arm: no system prompt, the task plus Latch's data instructions plus the
background-process note, `--effort max`, no turn cap, the 6000 s timeout. `--arm` labels the
run; `--system-prompt-file` is the method-as-prompt arm; the stringency and sham arms are
agent functions to add beside it (Phase 2). `run_eval.py --summary runs/...` writes one CSV
and the per-eval and overall numbers.

## Phases, as rows

| phase | row | what | exit |
|---|---|---|---|
| 0 | L87 | the owner's `latch login`; pull the six scBench and seventeen SpatialBench public evals; the baseline arm, three replicates, on the scBench six first, the SpatialBench seventeen next; tokens, cost, wall-clock per run | our Opus 5 baseline beside the published pattern |
| 1 | L88 | the six public evals mapped to decision points and predicates (the owner's table is the first cut), marked built, row, or not addressable; the scRNA-seq method as a committed pipeline with `decision:` blocks on QC thresholds, normalisation and HVG count; the Latch conversation opened | one table over both taxonomies; the method lints |
| 2 | L89 | the adapter: prompt to declarations (`declare --check`, `init --drafted-by agent`, a fixed confirm policy), pipeline mode with a fixed hold policy, `answer --cite` from the delivery, open mode for interpretation, `answer --cannot` as abstention; the method-as-prompt and sham-gate arms; tags frozen | all five arms end to end on the DE and cell-typing evals, `coverage.md` per run |
| 3 | L90 | public-set runs, three replicates, the metrics, a note and a `measurements.md` row before any private data | Claim A and Claim B numbers with intervals, the sham comparison |
| 4 | L91 | the reviewer arm, the owner at `stringency review`, answer key unseen | a Claim C number, a per-predicate override table |
| 5 | L92 | Latch: the withheld evals, OmicsBench v1, their judge; the arXiv authors, one email; one run on the frozen tags | private-set numbers, or why not |

## Phase 1, first cut (2026-10-22): the six public evals against the engine at 0.2.33

From the evals' author notes (which name the trap and what the grader rejects; they never
reach the agent) and the graders. "Built" means the engine or plugin mechanism exists today;
"method" means the scRNA-seq method must produce the evidence or the step; "row" means a new
predicate to file; "not addressable" means the gate has nothing to say and the arm abstains.

| eval | the trap (authors) | what the gate does today | status |
|---|---|---|---|
| QC, BD Rhapsody targeted panel (`n_pbmcs_retained`, `median_genes_per_pbmc`, `n_monocytes_pbmc`) | whole-transcriptome thresholds on a 386-gene panel retain zero cells, or 15% at a "safer" floor | the QC thresholds are a `decision:` whose evidence is the step's own distribution table (n_genes, total_counts per cell); `param.uncited` flags a proposal that cites nothing in it, `param.reason_unmatched` a reason with numbers the table does not hold; `sc.low_cell_count` flags too few cells retained (plugin) | built; method: a QC step that writes the distribution table and takes panel-aware floors |
| Normalisation, CS Genetics (`median_umis_per_cell`, `pct_counts_one`, `median_hvg_prevalence`) | log-normalisation at 1,655 median UMIs picks low-prevalence noise genes as HVGs | normalisation method and HVG flavour as decision points with `evidence: <qc>/depth_summary` (median UMI, singleton fraction); the hold shows the depth before the number | decision built; row: a plugin flag when the method is log-normalisation and the median UMI is below a floor (`sc.normalization_depth`); method: `pearson_residuals` and `seurat_v3` as options |
| PCA, Chromium 4T1 (`pc1_top_abs_load`, `max_top5_depth_corr`) | skipping per-gene scaling and depth regression; both sentinels must pass | `scale` and `regress_out` as decision points with `hold: always`; the step writes the two sentinels as a table; `exec.plan_drift` keeps the declared method's output | decision built; row: two post-phase plugin flags over the sentinel table (`sc.pc1_single_gene`, `sc.pca_depth_confounded`); method: the sentinel table |
| DE, Parse Bio, 12 donors (`n_degs`) | `rank_genes_groups` at cell level: 3,194 DEGs (t-test) or 625 (Wilcoxon); pass is pseudobulk by donor with donor in the model, 800 to 1,500 | `pseudobulk-de` with `replicate_unit` a decision point; `de.replication_unit` blocks a unit finer than the design's donor; `de.covariate_omission` flags donor absent from the model; `obj.feasibility` the cells-per-donor floor | built (plugin 0.7.0); method: the Xenium tool's `replicate_unit` enum (`animal`, `punch`) generalised to the design's units, donor as the replication unit in `design.yml` |
| Cell typing, Illumina snRNA DRG (`mural_nuclei`, `interpretation`) | overriding panel scoring with a per-gene look (211, rejected); picking a sophisticated wrong explanation without checking the cells | the panel-scoring step is the declared method and `exec.plan_drift` keeps its output (0); the "why" is a judgment over the per-gene detection table with `must_cite: [detection.pct_detected]`, so the replicates cite Rgs5 against the other three panel genes; `judg.required_evidence_uncited`, `judg.numeric_claims_match@2` | built (0.2.33); method: a panel-scoring step with a per-gene detection table as judgment evidence; pipeline then open |
| Clustering, Tapestri scDNA + protein (`largest_clone_pct`, `interpretation`) | protein clustering instead of genotype; the double mutant instead of the largest clone | outside the single-cell plugin (DNA genotype calls, a 181-variant panel): no method step, no extractor | not addressable: `answer --cannot`, counted as abstention |

Two rows to file for Phase 1 beside L88 (the method): the depth-aware normalisation flag and
the two PCA sentinel flags, each a plugin predicate with must-fire and must-pass fixtures over
a table the method writes. Both read a computed diagnostic, as the owner's plan says: a
sentinel on a computed diagnostic is a gate.

What the baseline cannot show and the gate can: in every one of the five addressable evals the
failing choice is made and not tested (a threshold, a normalisation, a preprocessing step, a
replicate unit, an override of the declared method), and in every one the engine's answer is
the same shape: the choice is a decision point with its evidence beside it, and the hold or
the block lands before the number is written.

## Open questions, with what is known now

- Latch account tier for the public data: unknown until the owner logs in.
- Harness: Claude Code with Opus 5 first (the owner, 2026-10-22); Codex is logged in for the
  harness-shift comparison later (L34).
- Where runs execute: this machine, one at a time by default (the agent's own scripts are
  CPU work; the GPU is not involved); parallel replicates once the baseline's memory footprint
  is seen.
- The unattended declaration and confirm policy (Phase 2): the agent declares from the task,
  `init.*` checks the declarations, and the confirm hold is accepted by a recorded policy row
  (`via: policy`, the arm's name as reviewer); whether that arm is still stringency is the
  owner's question to answer in the write-up.
- Budget: the published Claude Code runs cost $0.14 to $4.53 per trial on the six (mean about
  $1.06); Opus 5 on the subscription reports cost but does not bill per call.
- The pre-registration of the two numbers (accuracy among submitted, abstention rate) goes in
  this file before the first stringency-arm run.

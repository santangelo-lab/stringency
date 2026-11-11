<!-- The owner's benchmark plan of 2026-10-21, copied here unchanged on 2026-11-10 from the
upload it had lived in (it was in no repository, and `benchmark-plan.md` says it does not
restate it). It is the plan of record for the purpose, the three claims, the arms, the metrics,
the abstention risk and what a convincing result looks like. `benchmark-plan.md` holds what
changed on contact with the code and the benchmarks, the pre-registration and its amendments.
Its open-questions list repeats several items and gives two counts of public evals (30 and 57);
both are as he wrote them. -->

# stringency benchmark plan

Oct 21, 2026 · @Jim

## Purpose

Show, on a public benchmark with answer keys, that wrapping an agent in stringency's gate catches the failures that cost agents the most points, and that its holds land where a reviewer's attention is needed. The audience is three groups: the lab and Emory colleagues deciding whether to route analyses through it, LatchBio as a potential collaborator, and reviewers of an eventual write-up.

The obstacle this plan is built around: stringency is a human-in-the-loop system and benchmarks run unattended. The answer is to split the claim so that the two expensive parts (a human's time, a private test set) come last and are small.

## The claim, split into three pieces

Only the third piece needs a person in the loop. The first two run unattended against the benchmark's own graders.

| Claim | What it tests | Human needed? | Primary metric |
| --- | --- | --- | --- |
| A. Gate alone | Same model, same harness, with and without the gate; holds resolved by a fixed policy (hold becomes a block, agent receives the hold record, bounded retries) | No | Change in benchmark score, paired per task |
| B. Holds localize failures | Whether holds are raised on the subtasks the grader marks wrong | No (the answer key stands in for the reviewer) | Hold precision and recall against grader failures |
| C. Reviewer lift | What a real reviewer adds on top of A, on the public tasks only | Yes, Jim | Score lift per intervention; override rate |

Claim B is the one that matters most. Stringency's purpose is to direct scarce human attention, and the lab has never had an answer key to measure that against. The benchmark supplies one.

Why A and B are plausible, and which matters more. Latch's OmicsBench v1 report judged 4,556 failing runs into 17 failure modes. The four largest (arbitrary ambiguity resolution 19.6%, ad hoc classification pipeline 15.3%, disregarding the agent's own contradicting evidence 13.9%, silent statistical choice 11.9%) are one act: a choice made and not tested. The repo's `spec/plans/omicsbench-assessment.md` already maps each mode to an engine mechanism at 0.2.27 and finds the gaps cluster in free text, reasons and claims shown to a person and checked by nothing (rows L55 to L58), plus the downstream predicates designed in September and never built (L54).

Latch also found that harness choice barely moved pass rates but shifted how often undesirable behaviours occurred. Stringency is a harness change. So the primary claim is a behaviour-rate shift, which Latch measures with a judge over trajectories, and a pass-rate delta is secondary. That is a more defensible position than it sounds: it is their finding, stated in their instrument.

## Benchmarks

Latch's OmicsBench v1 carries the pitch; scBench, one of its eight components, is the public slice we can run today. A same-named arXiv benchmark from Michigan and AfterQuery was considered and set aside (below).

| Benchmark | Shape | Public | Why it fits |
| --- | --- | --- | --- |
| OmicsBench v1 (LatchBio, Oct 2026) | Meta-benchmark of 784 tasks from eight Latch suites; auto-graded containers; 31 model-harness configurations; an LLM judge read every failing run into 17 modes and counted undesirable behaviours on passing runs too | Private; a harness submission is a conversation with Latch | The taxonomy is already mapped against the engine in the repo; the behaviour judge is the instrument Claim B needs |
| [scBench](https://github.com/latchbio/scbench) | 195 evals (the paper said 394) across six platforms; six task categories that are the upstream pipeline step for step | 6, with trajectories | The singlecell plugin and the Xenium method's upstream steps cover most of what each asks |
| [scBench-Long](https://github.com/latchbio/scbench-long) | Longer-horizon single-cell tasks | 9, with trajectories | Multi-step; closer to a full pipeline run |
| [SpatialBench](https://github.com/latchbio/spatialbench) | 159 evals, five platforms, seven categories including spatial analysis | 17 (of 159), with trajectories; includes Xenium kidney niche-composition and niche-emergence tasks | Sits directly on `xenium-upstream`; Latch's own `xenium-devkit` skill is an independent method-as-prompt arm |
| [SpatialBench-Long](https://github.com/latchbio/spatialbench-long) | Longer-horizon spatial tasks | 25, with trajectories | Same |

All five share [`latch-eval-tools`](https://github.com/latchbio/latch-eval-tools): `EvalRunner.run(agent_function)` takes any `(task_prompt, work_dir)` callable or reads `eval_answer.json` from the work dir, so the stringency adapter is one function. Built-in harnesses are mini-swe-agent, Claude Code (Docker, with a `system_prompt` parameter), Codex, pi and grokbuild. Run summaries record tokens, cost and an LLM refusal diagnostic. Data is fetched through the `latch` SDK's `LPath`, so a Latch login is required even for the public evals; nothing in the READMEs says whether a free account suffices. About 57 public evals in total, enough to debug the adapter and get a first precision-and-recall estimate, not enough to settle it.

Order: the six scBench evals first because they are the smallest and map to the method cleanly; the 17 SpatialBench evals next because the Xenium tasks and the `xenium-devkit` comparator are there, gated on the `spatial.*` predicates in L54; the Long variants once the short ones run; the withheld sets and OmicsBench v1 through Latch. The Latch conversation belongs in Phase 1. The Latch assessment in the repo was written against their report, not against a run; nothing has executed yet.

**Not pursued: the arXiv OmicsBench** ([2610.21074](https://arxiv.org/abs/2610.21074), U Michigan and AfterQuery). Three of 97 tasks are public, too few to estimate hold precision or recall without the authors running the rest. Its subtasks prescribe the method (test, threshold, correction), so its failures are mostly spec-following and the engine's judgment machinery barely engages. And a second benchmark with the same name muddies the write-up. Two things from it stay useful without a run: its finding that scores fall on subtasks that depend on earlier ones is a citation for the forward-feasibility argument, and its authors' stated open problem, feedback that points at the faulty step without revealing a passing answer, describes a hold record; that is a short email once there is a scBench result to point to.

**Adjacent, not a benchmark: Seqera.** Platform 26.2 (Oct 14, 2026) ships Co-Scientist, autonomous [Co-Scientist Agents](https://seqera.io/blog/from-data-to-analysis-faster-what-s-new-in-seqera-platform/) under service-account identities, event-driven Actions that hand a failed run to an agent to debug and relaunch, per-user credentials, Lineage Search over Nextflow provenance, and an MCP server for Claude and Codex; earlier, Gradient (closed-loop parameter optimization against held-out truth) and rewrites.bio. They publish no agent benchmark. Their [guardrails](https://seqera.io/blog/copilot-to-co-scientist/) are access control: least-privilege credentials and roles answer "may this agent touch this resource"; stringency answers "may this analysis choice run in this state." Those are orthogonal, and that sentence is the positioning when someone asks whether Seqera already does this. Their autonomous fix-and-relaunch loop is the self-correcting behaviour design 3.3 keeps out of the gate, which makes it the clearest illustration of why a hold is unresolvable by the agent. As substrate and venue they fit: a deterministic module can shell out to Platform with the trace cross-linked on run ID, their MCP is a third harness route, and Nextflow Summit or nf-core is a more natural first audience for the Commandments than a benchmark paper. A short assessment in the pattern of `omicsbench-assessment.md` is cheap and not yet written.

## Experimental design

A paired comparison: one model, one base harness, every task run in each arm, three replicates per arm, the benchmark's own confidence-interval method so our numbers sit next to theirs.

**Arms**

| Arm | What runs | Purpose |
| --- | --- | --- |
| Baseline | Model + harness as the benchmark paper ran it | Reproduce their published number before touching anything |
| Method as prompt | Baseline + the method's steps, ranges and decision points injected through the harness's `system_prompt`, no engine. For SpatialBench, Latch's own `xenium-devkit` skill; for scBench, our method text | Separates the method's contribution from the gate's; the Latch-authored skill removes the objection that we wrote the comparison prompt to lose |
| Stringency | Pipeline mode under the engine with the committed method; decision points gated; fixed hold policy; open mode for the interpretation tail | Claim A and Claim B |
| Sham gate | Method as prompt + holds raised at the same rate as the stringency arm but at random, same retry budget | Rules out "extra retries did it" |
| Stringency + reviewer | Stringency arm, holds resolved by Jim, public tasks only | Claim C |

**Metrics**

| Metric | Definition | Supports |
| --- | --- | --- |
| Paired score delta | Stringency score minus baseline score, per task, averaged with 95% CI | A |
| Accuracy among submitted | Score counting only subtasks where an answer was committed | A (see Known risk) |
| Abstention rate | Share of subtasks where the gate declined to submit | A |
| Hold precision | Of holds raised, the fraction on subtasks that scored below threshold | B |
| Hold recall | Of subtasks below threshold, the fraction that raised a hold | B |
| Failure-mode shift | Change in frequency of each OmicsBench failure mode between arms | A, explains the mechanism |
| Cost | Tokens, wall-clock, tool calls per task, each arm | Honesty about overhead |
| Override rate and lift per intervention | From the reviewer arm | C |

**Discipline.** Predicates are developed and tuned on the public tasks only. The private sets are run once, by the authors or with their cooperation, after the predicate set is frozen and tagged. Tuning on the test set is the forking-paths error the Commandments exist to prevent, and anyone reading them will check.

## The integration: pipeline mode first, open mode for the tail

scBench's six task categories (QC, normalization, dimensionality reduction, clustering, cell typing, DE) are the upstream topology of the Xenium method, step for step, and the traps its authors describe are decision points. So the adapter runs the committed method in pipeline mode and answers from the delivery; open mode handles interpretation questions over the delivered tables and tasks the method does not cover.

The six public evals, by shape:

| Eval | Asks | Trap (authors' notes) | Engine mechanism | Shape |
| --- | --- | --- | --- | --- |
| QC, BD Rhapsody targeted panel | Cells retained, median genes, monocyte count | Whole-transcriptome thresholds on a 386-gene panel retain zero cells | QC thresholds as a `decision:` with evidence from the data's own distribution (L61); `qc.threshold_range` | Pipeline |
| Normalization, CS Genetics | HVG prevalence on shallow data | Standard log-normalization at 1,655 median UMIs | Normalization as a decision point with median UMI as evidence | Pipeline |
| PCA, Chromium 4T1 | PC1 top loading, depth correlation of top PCs | Skipping preprocessing sentinels | A sentinel on a computed diagnostic is a gate | Pipeline |
| DE, Parse Bio, 12 donors | DEG count, IFN-β vs PBS in CD14 monocytes | `rank_genes_groups` at cell level: 3,194 DEGs; pass band 800–1,500 is pseudobulk by donor with donor in the design | `pseudobulk-de` with `replicate_unit` as a decision point; `de.replication_unit`, `de.covariate_omission` (L54) | Pipeline |
| Cell typing, Illumina snRNA mouse DRG | Mural nucleus count from a prescribed workflow, then why the count is what it is (five options) | Overriding the declared panel method with a per-gene look (reports 211, graded wrong); picking a plausible explanation without checking the cells | `exec.plan_drift` keeps the declared method's output (0); the why is a judgment citing cluster 21's Rgs5 detection against the other three panel genes | Pipeline, then open |
| Clustering, Tapestri scDNA + protein | Largest mutant clone percentage and an interpretation | Protein clustering instead of genotype | Outside the singlecell plugin; open mode or abstain | Open |

**What the adapter does.**

1. Declare: map the task prompt to `inputs.yml`, `design.yml` (donor as replicate unit, condition factors, stated exclusions) and `objective.yml`, with the agent as operator. The `init.*` predicates check the declarations against each other and the method. The confirm hold takes a fixed policy, since no person is present.
2. Run the committed scRNA-seq method in pipeline mode. Decision points are proposed with `--cite` and `--considered` (L55) and gated; holds follow the fixed policy.
3. Answer the eval's fields from the delivery through `answer --cite`; `ans.*` predicates apply. An interpretation question is answered in open mode over the delivered tables.
4. A task the method cannot run, or a question the delivery cannot answer, is `answer --cannot`, which scores zero and is counted as abstention.

**The confound to design for.** Pipeline mode is method plus gate, and a skeptic will credit the method. The arms separate them: an unrestricted agent; the same agent handed the method as a skill with no engine; pipeline mode under stringency; a sham gate. If the gated arm beats method-as-prompt, the gate earned the difference; if it does not, the method did, which is still a result about the Commandments.

What exists at 0.2.28 against the Latch failure modes, and what is new:

| Latch failure mode | Engine mechanism | Status |
| --- | --- | --- |
| Untraceable output; final answer overrides own computed result | `ans.numeral_unmatched`, `ans.cited_missing`, `judg.numeric_claims_match`, `judg.evidence_exists` | Built |
| Output schema or vocabulary non-compliance | `out.schema_conformance`, `judg.vocabulary_resolves` | Built |
| Reimplementation of a missing tool | `exec` with read-only inputs, network isolation recorded, the pinned untested sentence; `ans.label_authored`; `exec.plan_drift`, `exec.script_drift` | Built |
| Arbitrary ambiguity resolution; invented task specification | declare and echo-back, the confirm hold, seven `init.*` predicates, `param.undeclared`, `param.agent_proposed` | Built; the reason at a hold is unchecked |
| A proposed parameter with an uncited reason | `propose --cite`, `--considered`, `param.reason_unmatched` | L55, next to build |
| Silent statistical choice | `de.replication_unit`, `de.covariate_omission`, `de.selection_bias`, `test.multiple_comparison`, `test.assumptions_unchecked` | L54, unbuilt; the Xenium tools now emit the facts they read |
| Disregard of own contradicting evidence | `judg.confidence_consistent`; `must_cite` and `judg.required_evidence_uncited` | Built; L56 |
| Direction or comparison claims in prose | `judg.claim_unsupported` over structured claims | L58, design |
| Abandonment; gave up and returned null | `abandon --reason`, `deliver` refuses an incomplete run, `answer --cannot` | Built (0.2.28) |

## Known risk: abstention is penalized

The headline score may go down, and we need to decide now how to report that so it does not read as a negative result.

Auto-graded benchmarks score the answer file; an abstention is an empty or missing field and scores zero, and agent system prompts in this family instruct the model to commit to a best answer. Commandment 8 says abstention is always available and a module that cannot support a call must say so. A stringency-wrapped agent that files `answer --cannot` loses that subtask.

The plan:

- Report two numbers in place of one: accuracy among submitted answers, and abstention rate. Pre-register this in the repo before the first stringency-arm run.
- Test whether abstentions fall on subtasks the baseline also got wrong. If they do, the gate declined to guess on things the model could not do, which is the intended behavior and a finding about the benchmark's single-number metric.
- Keep the fixed hold policy's retry budget equal to the benchmark's own, so the abstention is a real last resort and not a shortcut.

If abstentions fall mostly on subtasks the baseline got right, the gate is miscalibrated and that is a result too. It tells us which predicates are too tight, which is exactly what the override log is for in the lab setting.

## Concrete steps

Each phase has an exit criterion. Phase 1 is mostly done already; Phase 2 is ordered the way `PLAN.md` already orders it, with the adapter after the predicates it needs.

**Phase 0: baseline reproduction** (1 week)

- [ ] `pip install latch-eval-tools`, `latch login`; pull the six scBench and 17 SpatialBench public evals; confirm the account tier that works.
- [ ] Pick the harness from configurations Latch ran. Claude Code is one; Codex CLI is now logged in on PROTSEQ (L34), so a second harness is available for the harness-shift comparison Latch reports.
- [ ] Run the public evals, 3 replicates, against the published trajectories and results; record tokens and wall-clock per eval from the run summaries.

Exit: our baseline is inside the published confidence interval on the public tasks.

**Phase 1: failure modes to predicates** (days, not a week)

- [ ] Done for Latch's 17 modes: `spec/plans/omicsbench-assessment.md` section 3.
- [ ] For each of the six public evals, name the decision point or predicate the trap maps to (the table in the integration section is the first cut), and which the method already covers.
- [ ] Open the Latch conversation now: access to the withheld 189 scBench evals for a harness submission, and whether their behaviour judge can run over outside trajectories. If not, reproduce their judge prompt locally and validate it on the published trajectories.
- [ ] Write the scRNA-seq method as a committed pipeline (the Xenium method's upstream steps, generalised to droplet and combinatorial kits), with ranges and `decision:` blocks on QC thresholds, normalization and HVG count.

Exit: one table covering both taxonomies, each mode marked built, backlog row, or not addressable.

**Phase 2: predicates, then the adapter** (3 weeks)

- [ ] L55: `propose --cite`, `--considered`, `param.reason_unmatched`. First in `PLAN.md`'s order and the most generalisable.
- [ ] L54: singlecell plugin 0.7 with the downstream predicates, the four whose facts the tools already emit first (`de.replication_unit`, `de.covariate_omission`, `test.multiple_comparison`, `spatial.neighborhood_undeclared`), each with must-fire and must-pass fixtures. The DE eval is this row.
- [ ] The adapter: prompt to declaration, pipeline-mode run with the fixed hold and confirm policies, `answer --cite` from the delivery, open mode for interpretation questions, `answer --cannot` as abstention.
- [ ] The method-as-prompt arm and the sham-gate arm.
- [ ] Tag the engine, plugin, method and adapter; freeze. Every run records the tags.

Exit: all five arms run end to end on the DE eval and the cell-typing eval, the two that exercise pipeline mode and the pipeline-then-open shape, and `coverage.md` for each run reconstructs what was checked.

**Phase 3: public-set runs and analysis** (1 week)

- [ ] Baseline, stringency and sham arms on all public tasks, 3 replicates, both harnesses if time allows.
- [ ] Compute paired deltas, accuracy among submitted, abstention rate, hold precision and recall, behaviour-rate shift, cost.
- [ ] Results as a note in `notes/` and a row in `spec/plans/measurements.md`, before any private-set data is seen.

Exit: Claim A and Claim B numbers with intervals, and the sham comparison.

**Phase 4: reviewer arm** (Jim's evenings)

- [ ] Stringency arm on the public tasks with holds routed to `stringency review`; resolve from the evidence shown, answer key unseen; verdict and reason recorded.
- [ ] Lift per intervention, override rate per predicate, time per hold.

Exit: a Claim C number and a per-predicate override table.

**Phase 5: private sets and outreach**

- [ ] Latch: send the Phase 3 note with the assessment's section 8 paragraph as the opening; ask for a run on the withheld scBench evals, on OmicsBench v1, and for their judge over our trajectories.
- [ ] Optional, one email: the hold-record format to the arXiv OmicsBench authors against their stated open problem.
- [ ] Run once with the frozen tags. No changes after seeing results.

Exit: private-set numbers, or a documented reason they are not available.

The internal acceptance runs already queued (L77 open-mode acceptance, L79 the Xenium skill by a non-developer) are the lab-side counterpart of this plan. The benchmark should not displace them; a tool that scores well externally and that no colleague has run is not the argument.

## What a convincing result looks like

The strongest version has four parts, and the plan is built so that three of them do not depend on the score moving.

1. Hold precision well above the base failure rate, and recall covering a named share of failures. "Of the subtasks the grader marked wrong, the gate had raised a hold on X%; of holds raised, Y% were on failing subtasks." This is the number no other tool reports.
2. A failure-mode shift: the frequency of uncorrected p-values, memory-derived answers, and criterion substitution drops between arms, while modes the gate does not cover stay flat. This shows the mechanism and demonstrates the coverage report in practice.
3. The sham gate does not reproduce the effect. Placement of holds mattered, retries alone did not.
4. A paired score delta, with its confidence interval, reported alongside abstention rate and cost.

If the score delta is null or negative but 1 through 3 hold, the result is still worth writing up: the gate found the failures and the benchmark's scoring did not reward declining to guess. That is an argument about how agent benchmarks should score, made with data, and it is a stronger position for the collaboration email than a small accuracy gain would be.

If 1 fails, holds are not landing on failures, and the predicate set needs rethinking before any of the rest matters. Better to learn that on 30 public evals than in a colleague's analysis.

For non-computational audiences, the belay framing already in use carries over: the benchmark shows how often the belayer caught a real fall versus locked off on a non-event.

## Open questions

- [ ] Can an outside group get a harness scored on Latch's withheld scBench evals and OmicsBench v1, and judged by their behaviour pipeline? If not, the external claim rests on the 30 public evals plus a local judge, and the rest is a collaboration ask.
- [ ] Harness: Claude Code, Codex, or both? Both gives the harness-shift comparison Latch reports and exercises L34.
- [ ] Where runs execute: scBench's container requirements, and PROTSEQ parallelism against the GPU-sharing arrangement.
- [ ] Can an outside group get a harness scored on Latch's withheld evals and OmicsBench v1, and judged by their behaviour pipeline? If not, the external claim rests on the 57 public evals plus a local judge, and the rest is a collaboration ask.
- [ ] Does a free Latch account pull the public eval data through `LPath`? Not stated anywhere in their READMEs.
- [ ] Harness: Claude Code, Codex, or both? Both gives the harness-shift comparison Latch reports and exercises L34.
- [ ] Where runs execute: the harnesses run the agent in Docker; PROTSEQ parallelism against the GPU-sharing arrangement.
- [ ] Unattended declaration: the declare skill asks one question at a time and never infers a value. In a benchmark the agent is declarer and operator at once, and no one confirms. What the confirm policy is, and whether that arm is still stringency.
- [ ] Budget: Latch reports roughly $0.60 to $1.10 per eval for leading configurations. 57 evals by five arms by three replicates is about 850 runs, low thousands of dollars before the engine's own overhead. Cost it before Phase 3.
- [ ] Ordering against `PLAN.md`: the owner's waiting table, then L61, L55, L54 are already ahead of this. Is the benchmark the reason to pull L54 forward, or does it wait its turn?
- [ ] Their grader vocabulary (`predicate` with `role: gate` or `hard_fail`, `all_of`, a `rubric` judge) overlaps ours. Worth a glossary line before the conversation so the words do not collide.
- [ ] Unattended declaration: the declare skill asks one question at a time and never infers a value. In a benchmark the agent is declarer and operator at once, and no one confirms. What the confirm policy is, and whether that arm is still stringency.
- [ ] Budget: cost the public-set runs, three arms by three replicates by 30 evals, before Phase 3.
- [ ] Ordering against `PLAN.md`: the owner's waiting table, then L61, L55, L54 are already ahead of this. Is the benchmark the reason to pull L54 forward, or does it wait its turn?

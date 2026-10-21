# OmicsBench, assessed

A plan note, written 2026-10-21 after reading LatchBio's OmicsBench v1 (the blog post
`blog.latch.bio/p/omicsbench-v1-a-latch-meta-benchmark`, 2026-10-19, and the report at
`latch.bio/omicsbench`, 42 pages; its failure-mode section 4.2, appendix tables A1 to A6 and the
judge prompts in appendix E). Not the spec. The method is the one used for ClawBio and commons
(`judge-sources-plan.md` section 9, `commons-assessment.md`): say what the other work is, put it
beside the engine, name what is worth taking and where it lands, and record what is not. The
owner's question: the benchmark names two classes of failure, biological and agent-behaviour;
the engine was built against the second; where does it address each, and where not. Items marked
*design* change design text and need the owner; the rest are DECISIONS-level or plugin-level.
`PLAN.md` rows L54 to L60 point here; the parameter-choice gap of 4.2 grew into
`decision-points.md` (L61 to L66) after the owner's reading on 2026-10-21.

**Status 2026-10-21.** Assessed against engine 0.2.27, plugin singlecell 0.6.2 and the Xenium
method at v0.6.0-rc19; no integration lane. Seven borrowings recorded as backlog rows (L54 to
L60), a list of smaller practices with no row, and candidate words for the README (section 8).
Nothing built. 2026-10-21: the owner read it; 4.2 is now the first cut of `decision-points.md`.

## 1. What OmicsBench is

A meta-benchmark of 784 bioinformatics tasks (741 short-horizon, 43 long-horizon) drawn from
eight LatchBio benchmarks across six domains: spatial omics, single cell, epigenomics, variant
calling, microbial surveillance and protein function. Each task is a container holding a data
snapshot, a prompt, a time limit and an automatic grader; experts reproduced a published analysis
and split it into one long task or several short ones, then reviewed the tasks for scientific
validity, durability under defensible alternative approaches, and anti-shortcut structure.
Thirty-one model-harness configurations were run (Claude Code, Codex, Grok Build and Pi as
harnesses). No configuration passed half of the short tasks (best 49.4%) or a third of the long
ones (best 32.8%), and the ceiling has not moved since July 2026.

The part that matters here is section 4.2. An LLM judge (claude-sonnet-5 through Docent) read
all 4,556 failing trajectories of four models with no taxonomy supplied, wrote one decisive error
per run with a quotation as evidence, and a second model tried to overturn each; the free-text
labels were clustered into seventeen failure modes (table A3). A second pass over passing and
failing runs looked for behaviour that is wrong whether or not the answer was right (table A2).
Section 4.3 adds one representative failure per domain from the field's own experts (table A1).

## 2. The taxonomy, counted

Failure modes, as a share of the 4,556 failing runs (table A3; the body text's 49.7 / 21.5 /
8.9 / 4.7 split counts a larger set of 6,347 runs and groups the same modes):

| failure mode | % | the owner's class |
|---|---|---|
| unresolved ambiguity settled by an arbitrary or outcome-driven pick | 19.6 | agent |
| unvalidated ad hoc classification or clustering pipeline | 15.3 | agent |
| disregard of own contradicting diagnostic evidence, or a misidentified target | 13.9 | agent |
| silent unvalidated statistical or data-handling choice | 11.9 | agent |
| unvalidated from-scratch reimplementation of a missing tool | 8.3 | agent |
| task or sub-task abandonment without genuine necessity | 6.0 | agent |
| ungrounded categorical or mechanistic assertion | 3.6 | both |
| unverified sample or data assignment, or scope selection | 3.4 | agent |
| gave up on a missing tool or resource, returned null | 2.9 | agent |
| output not traceable to, or inconsistent with, own computation | 2.2 | agent |
| incomplete or truncated run with unverified final output | 2.2 | agent |
| fabricated or hallucinated reference content | 2.1 | agent |
| invented the task specification where instructions were missing | 2.1 | agent |
| final answer overrides the agent's own favoured computed result | 2.0 | agent |
| naive or unvalidated genomic coordinate or reference anchor | 2.0 | both |
| confounded or fragile ranking metric drives a wrong selection | 1.3 | biological |
| output schema or vocabulary non-compliance | 0.8 | agent |

Undesirable behaviours, from 9,721 judged runs, passing and failing (table A2; 7.4% of failing
and 5.0% of passing runs were flagged): invented references 108, overstated confidence 101,
false completion 91, fabricated answer 88, post-hoc parameter sweep 87, grader gaming 63,
hardcoded conclusion 49, silent method switch 7, circular validation 4.

The domain failures of section 4.3 and table A1: the wrong size scale for cellular
neighbourhoods and no account of local abundance (spatial); weak programs discounted as noise
when not every member gene moves or a strong alternative signal is present (single cell);
array-era effect-size cutoffs applied to whole-genome bisulfite data, or significance by FDR
alone (epigenomics); a base-quality artifact identified and then not acted on, so a benign
repeat was called pathogenic (long-read variants); ordinary gut background tagged as engineered
(microbial); monovalent and multivalent assays treated as interchangeable (protein function).

Two readings of the taxonomy matter for the engine. First, the authors' own summary: "most
failures reflected lapses in scientific judgment", and the first four modes, half of all failures,
are one act, a choice made and not tested. Second, harness choice barely moved pass rates but
shifted how often the undesirable behaviours occurred; the measure that separates harnesses is
behaviour, not score.

## 3. Side by side: the agent-behaviour modes against the engine

What the engine does today (0.2.27) for each mode, and what it lacks. "Pipeline" is a declared
topology run under `run`; "open" is a question of a delivered dataset (open mode, 0.2.22).

| mode | how it arises | what the engine does | what it lacks |
|---|---|---|---|
| arbitrary ambiguity resolution (19.6) | the task leaves a choice open and the agent picks, often the option that gives an answer | the ambiguity is settled before the run: the declare skill asks one question at a time and never infers a value the person did not give; `declare --check` and the echo-back; the confirm hold no run can open past; seven `init.*` predicates on the declarations against each other and the pipeline. A parameter is a committed default inside a committed range; a departure is a `param.agent_proposed` hold showing default, proposal and the operator's reason; a decision point taken at its default is `sc.decision_unreviewed` (L9 moves it into the engine); a value the person settles is `objective.yml` `params:` or `--asked-by person`. Open: the paths forward are filed with `origin: suggested` and counted apart | the operator's reason at a hold is shown and never checked, so the numbers it cites can be invented (L55) |
| ad hoc classification or clustering pipeline (15.3) | the agent assembles a clustering, picks resolutions and subsets by eye, and reports from it | the topology, the modules, the resolution grid and the selection step are committed to git at a tag; `repro.dirty_tree`, `topo.undeclared_step`, `exec.script_drift`; the grid is the declared sweep and the pick is a person's sign-off (`05_select_resolution`, default `unset`); judgment modules ship controls; `sc.unknown_fraction` bands. Open: clustering by `exec` is labelled untested in a pinned sentence | nothing at the engine level; the method author decides the grid |
| disregard of own contradicting evidence (13.9) | a diagnostic says one thing, the conclusion says another | the base judgment schema requires `contradicting_evidence`; `judg.confidence_consistent` refuses `high` with any contradicting cell cited; three independent replicates and a split is a hold, not a vote; a route label needs a person's sign-off; a deterministic rule is logged beside the judgment (`sc.batch_effect_suspected` at the batch hold); the hold shows the reviewer the tables the method names | a judge that leaves the contradicting cell uncited keeps `high` (L56); a direction claim in prose is unchecked (L58) |
| silent statistical choice (11.9) | a test without donor aggregation, an uncorrected covariate, a cutoff nobody declared | every parameter is declared or blocked (`param.undeclared`); `replicate_unit` and `tests` are decision points of `compose-cells` and `pseudobulk-de`; `obj.feasibility` pre and post on every step; the tools write `underpowered` and `pseudoreplication` columns | the predicates the design names for exactly this (`de.replication_unit`, `de.covariate_omission`, `de.selection_bias`, `test.multiple_comparison`, `test.assumptions_unchecked`) are unbuilt, and the tools they would read now ship (L54) |
| reimplementation of a missing tool (8.3) | the package is absent, so the agent writes its own and uses the output | pipeline: not possible by construction; the operator runs the ticket's `operator_line` and nothing else (rule 3), outputs without a ticket cannot be submitted, `exec.plan_drift` and `exec.script_drift` block a different script or parameters. Open: `exec` is the sanctioned form; the script is in `messages`, inputs are read-only, timeout, seed and network isolation are recorded, the answer carries the pinned `untested` sentence, and `ans.label_authored` blocks the operator writing the mark; `prov.controls_stale`; `coverage.md` lists the scripts | the rule "a tool before code" is skill text; the count of exec answers is reported, not gated |
| task abandonment (6.0) and gave up, returned null (2.9) | the agent stops short and reports what it has, or nothing | pipeline: a run closes only as completed, failed or `abandon --reason`; `run` resumes the open run; `obj.deliverable_unreachable`; `deliver` refuses without every declared deliverable; `submit --failed --reason`; the hold message never suggests a way around; skill rule 5 forbids reporting a step done otherwise | open: a question the operator cannot answer leaves a `questions` row and no record of why (L60) |
| ungrounded assertion (3.6) | a label or mechanism asserted with nothing behind it | a non-abstained judgment with zero supporting refs blocks (`judg.evidence_exists`); labels must resolve in a declared vocabulary; abstention is always allowed and holds | prose claims beyond numerals (L58); quoted text (L38) |
| unverified scope selection (3.4) | a subset of samples or cells chosen without saying so | inputs are hashed with a `source` sentence; `design.holdout`; an exclusion file is a declared input the confirm covers; reviewers never exclude a punch (`sc.exclusion_proposed`; the owner decides); `obj.feasibility`; `sc.low_cell_count` and `sc.qc_fail_fraction` bands per profile. Open: a subset made by `exec` is untested | none at the engine level |
| untraceable output (2.2) and overrides computed result (2.0) | the reported number is not the computed one | `judg.evidence_exists` checks the cited value against the stored cell; `judg.numeric_claims_match` on rationale and report prose; `ans.cited_missing` and `ans.numeral_unmatched` on open answers; sidecars and `prov.orphan_artifact`; delivery is regenerated from the trace; the operator may say no number its filed text does not hold | report prose is checked against every cell of every evidence table, so on a large table any numeral matches (L57) |
| incomplete run, unverified output (2.2); false completion (91 runs) | a step reported done that did not run | the step state machine; `deliver` requires `completed`; `plain` sentences are built from the trace; `stringency audit` and `prov.trace_inconsistent` read the rows back against their events; the measurement table's column "misreports vs trace" (zero in every counted run) | T3 and T4 of the trace-integrity plan, the owner's |
| fabricated reference (2.1); naive coordinate anchor (2.0); invented references (108 runs) | a gene set or a coordinate from memory | references are declared inputs with hashes and a source; `init.reference_mismatch`; vocabularies are versioned in the method (`cell_types_mouse@2`); a judge sees the declared evidence only, with no network; `exec` runs with its network isolated where the host allows and recorded otherwise | a reference list embedded in an `exec` script is auditable, not named (section 6; L48 is the route) |
| invented task specification (2.1) | instructions missing, so the agent decides what the task is | the declare rule; `declare --check`; the echo-back; the confirm hold; `init.question_unsupported`, `init.deliverable_unproduced` | none |
| schema non-compliance (0.8) | the output is not in the asked form | `out.schema_conformance`; `judg.vocabulary_resolves`; one retry with the errors, then `invalid`, which counts as disagreement | none |
| post-hoc sweep (87 runs); hardcoded conclusion (49) | parameters tried until the answer fits, or the answer decided first | the objective is declared and confirmed before the first run; every attempt and fork is in the trace with a reason; a fork inherits its parent's admitted parameters; open mode counts reruns of a tool on the same data per answer. A judge starts with a fresh context and reports `saw_conversation`; the operator never writes a label | sibling forks are invisible at delivery (L59); `obj.declared_after_result` (H5) waits |
| grader gaming (63) | the evaluation treated as the oracle | not applicable; there is no grader. The analogue, a judge that knows what the session hopes to find, is what dispatch isolation and the nonce are for | the isolation is `as_reported` under the subagent adapter; the controls are the compensating measure (design 10.1) |
| silent method switch (7); circular validation (4) | the approach changed after an inconvenient result; a check that reads its own output | `exec.plan_drift`; a fork needs `--reason`; `when:` conditions are in the trace; controls run outside the run on declared fixtures; `prov.controls_stale` | L4 (ill-formed controls) |

Read down the last column: the engine's coverage of the agent-behaviour class is close to complete
at the level of mechanism, and the gaps cluster in one place, text. Numbers in text are checked;
the words around them (a reason for a parameter, a direction, a comparison, which evidence was
weighed) are shown to a person and not checked. The seven rows below are mostly that.

## 4. Worth building

### 4.1 The predicates designed for the downstream tools (L54)

Design 6.5 and 16, `bulkrna-plan.md` and `spatial-method-plan.md` name `de.replication_unit`,
`de.covariate_omission`, `de.selection_bias`, `test.multiple_comparison`,
`test.assumptions_unchecked`, `spatial.neighborhood_undeclared` and `spatial.no_permutation_null`.
None is implemented (plugin 0.6.2 ships eleven predicates, all upstream of differential testing).
Until 2026-10-20 nothing ran that they would scope over; the Xenium method's rc19 ships
`pseudobulk-de`, `compose-cells` and `neighborhood-enrichment` as open tools, with
`replicate_unit` and `tests` as decision points, so the trigger is met. OmicsBench's canonical
"silent statistical choice" is a test run on cells without donor aggregation; `de.replication_unit`
is that check, written in 2026-09 and never built.

Mechanism, plugin side: singlecell 0.7 with the seven predicates, each with a must-fire and a
must-pass fixture over the tools' state envelopes. The facts are already written by the tools
(`de_coverage.underpowered`, `test_coverage.pseudoreplication` and `replicate_unit`, the
neighbourhood parameters and the permutation count); the extractor carries them into the summary
and the predicates compare them with `design.yml` (`replication_unit`, `batch`, the factors).
`de.replication_unit` blocks a unit finer than the design's; `de.covariate_omission` flags a
declared batch absent from the model; `test.multiple_comparison` flags a per-gene test with no
correction; `spatial.neighborhood_undeclared` blocks a neighbourhood whose scale is not a declared
parameter of the step. Level: plugin, DECISIONS-level; the plugin's `spec/predicates.md`.

### 4.2 A cited reason for a proposed parameter (L55)

`propose --reason` is stored as `rationale_ref`, printed at the hold under the parameters (L8), and
read by no predicate (design 6.8: rationale is never trusted). That is right for admissibility and
wrong for the person reading it: the operator's "ndim 35: cumulative variance 0.82 at component
35" is what they approve, and nothing says whether the elbow table holds 0.82 at row 35. Open
mode's `answer` solved the same problem with `--cite` and `ans.numeral_unmatched`.

Mechanism: `propose --cite <artifact>[:row[:column]]` as `answer` has, and `--considered
<v1,v2>` for the candidates weighed; the reason, its citations and the considered set stored as
one message (`{text, cited, considered}`, no table change) and resolved into
`param.agent_proposed@2`'s evidence, whose reason sentence opens with what kind of proposal this
is ("cites nothing from `elbow.csv`"); `param.reason_unmatched@1` (pre, `*`, flag): a numeral in
the reason matches no cited cell by `judg._numeral_problems`, or the reason carries numerals and
cites nothing. Section 9 of the operator skill requires both. Level: engine, DECISIONS-level;
14.1 additive.

The owner's reading (2026-10-21): this is the most generalisable of the mechanisms and the one to
build first, with the caveat that it proves the agent opened the right rows, not that it
understood them. The rest of the answer to "picking a threshold without testing it", the
`decision:` block with its evidence floor, lint, and the menu of sweep, rule, judged and
sensitivity controls a method author chooses per step, is `decision-points.md` (L61 to L66).

### 4.3 Evidence the judge must weigh (L56)

`judg.confidence_consistent` counts the cells a replicate cited; a replicate that cites no
contradicting cell can claim `high` whatever the table holds. The module author knows which column
decides the question (`knn_same_batch_excess` for the batch route, the top negative marker for an
annotation), and today can only put it in the prompt.

Mechanism: `judgment.must_cite: [<table>.<column>, ...]` in the manifest (additive to the frozen
`judgment` block; a `DEVIATIONS.md` entry as `sign_off` was); `judg.required_evidence_uncited@1`
(post, judgment, flag): for a replicate and an item, a declared cell is in neither
`supporting_evidence` nor `contradicting_evidence`; the prompt suffix names the columns so the
judge is told, not trapped. First users `assess-batch` and `annotate-clusters`. Level: engine,
DECISIONS-level; module contract 3.2 via `DEVIATIONS.md`.

### 4.4 Report prose checked against cited cells (L57)

A DECISIONS entry of 2026-09 checks report prose against every cell of the module's evidence
tables, because a report cites nothing. On `upstream-report`, whose evidence includes the marker
table, any numeral matches something. Open mode fixed this for answers by requiring citations.

Mechanism: a report module's schema may carry `cited: [{table, row, column, value}]` beside the
prose (the base evidence ref of 8.1); `judg.numeric_claims_match@2` takes the cited cells as the
denominator when the output carries them and every cell otherwise, and the coverage report says
which applied. `upstream-report` first. Level: engine, DECISIONS-level; 8.1 additive.

### 4.5 Structured claims (L58, *design*)

A claim of direction or comparison ("higher in tumour", "no batch structure at this resolution")
is unchecked in any output. The open-mode plan deferred structured claims (`compare`, `threshold`)
"later with a trigger"; 13.9% of OmicsBench failures disregarding a contradicting result, and 3.6%
asserting without ground, are the trigger.

Mechanism: an optional `claims` list in a report's or judgment's output, each `{kind: compare |
threshold, table, row (or row_a, row_b), column, relation, value}`; `judg.claim_unsupported@1`
(post, block) evaluates each against the stored cells. A claim the output does not structure stays
unchecked, and the coverage report counts structured against free claims so the reader knows the
ratio. Level: *design* (8.1 additive, a 6.5 row); after L57, which gives the citation form.

### 4.6 The fork sweep at delivery (L59)

`runs.parent_run_id` and `delta_json` record every fork and its reason, and a run's `coverage.md`
says nothing about sibling forks that ran the same decision point at other values. A person who
forked three times at the resolution and delivered one has done nothing wrong, and the record
should say so where the delivery is read; the design's answer, `obj.declared_after_result` (H5),
waits on staged mode.

Mechanism: one line per decision point in the coverage report and `summary.md`: "forks of this
project at `05_select_resolution.resolution`: 3 (0.4, 0.6, 0.8); this run 0.6, delivered", the
pipeline-mode form of open mode's rerun counts. Level: engine, low, DECISIONS-level.

### 4.7 An unanswerable question recorded (L60)

`ask` writes the `questions` row; when no route fits, the operator says the pinned cannot sentence
and nothing is written; the report lists answers, and the coverage report counts questions asked
by origin. A question given up on is the one record open mode does not keep, and giving up is 9%
of OmicsBench's failures.

Mechanism: `answer --cannot --question <id> --reason "<the cannot sentence's cause>"`: an
`answers` row with `status: unanswerable`, no label, the cause in `messages`; the report's short
list names it; `coverage.md` "questions: n asked, m answered, k unanswerable" with the reasons;
the skill says the sentence and files it. Level: engine, DECISIONS-level.

## 5. The biological modes: what the engine can and cannot do

The owner's framing holds: the engine does not know that a neighbourhood of 50 µm is wrong for
this tissue, that a 0.1 delta-beta cutoff belongs to arrays, or that a His-tag motif is ordinary
in a gut. A wrong analysis the method declared passes every gate, and the coverage report's last
line says so. What the engine offers is a place to put that knowledge once, where it is checked
every run instead of remembered:

- A threshold belongs in `policy.yml` `ranges`, keyed by profile band, in the method for the assay.
  The array cutoff on bisulfite data is a band in the wrong method; the diff that put it there
  has an author and a reason. `qc.threshold_range` (named in the design, unbuilt) is the predicate
  that reads it.
- A scale belongs in a declared parameter with a range (`spatial-niches` `k` 10 to 50) and a
  predicate that refuses the step without one (`spatial.neighborhood_undeclared`, L54). The engine
  cannot say the scale is right; it can say it was chosen, by whom, and that it was in range.
- A background belongs in a declared input (`role: reference`) or a required negative control
  (`controls.required`, 11): a module that must look for engineered sequence ships a control on
  clean gut data and the coverage report shows whether it passed.
- A weak program discounted as noise, an artifact seen and not acted on: these are judgment
  failures, and the engine's answer is replication, the required `contradicting_evidence`, the
  confidence criteria, abstention, and a hold a person answers with the evidence the method names
  beside it. Lane F's batch route is the pattern: a deterministic rule logged, three reviewers,
  the person signs the route.

So the engine's contribution to the biological class is the plugin and the method, which is to
say the lab's own knowledge written as predicates, bands and controls, and the hold for what no
rule can decide. That is less than solving the failure and more than a prompt.

## 6. Smaller, no row

- The benchmark's finding that harness choice shifts behaviour and not pass rate supports Lane J's
  measure: the measurement table's "misreports vs trace" and "holds and `via`" columns count
  behaviour per harness; keep them when Codex arrives.
- A reference list embedded in an `exec` script (the Hallmark EMT set from memory, table A5) is in
  `messages` and labelled untested; a warning when a script carries more than some number of
  literal identifiers would name it. Low; L48, a person's file declared with a source, is the route.
- The judge prompt's rubric ("constructing a criterion, threshold or definition after the fact so
  that it guarantees the result") is the sentence `obj.declared_after_result` was written against
  (`archive/declarations-and-objectives.md`); H5 stays where it is.
- The override corpus is the lab's own trajectory analysis. L37's `review --export` would give
  each resolved hold a packet a Docent-style judge could read; nothing to add here.
- OmicsBench's "durability" criterion (a task must tolerate a reasonable range of defensible
  approaches) is the benchmark's form of a declared range on a parameter.

## 7. Not borrowed

- A grader. The engine has no ground truth and does not pretend to; controls with declared
  fixtures are the measurement, per module version.
- A trajectory judge in the engine. Judging the operator's reasoning is what 6.8 refuses; the
  engine checks outputs and records reasons.
- Refusal counted as failure. Abstention is a structured answer here and a hold, which is the
  opposite accounting.

## 8. Words for the README, for the owner

A candidate paragraph, in the README's register, to place after "What agents are bad at":

> OmicsBench (LatchBio, October 2026) classified 4,556 failing agent runs on bioinformatics
> tasks. About half failed because the agent picked a threshold, a method or a subset of the data
> without testing it; most of the rest because it disregarded its own contradicting result,
> reimplemented a tool it did not have, or gave up. Each of those is a thing the engine was built
> to stop or to record. A parameter is a declared default inside a declared range, and a departure
> is a hold a person answers. A method is a committed module; code written in the session runs
> under the engine and is labelled untested. A judgment cites the cells it rests on and the cells
> against it, and every number in prose is checked against a cell. A run that stops is abandoned
> with a reason or it is not closed. What the engine does not do is know the biology: the wrong
> neighbourhood scale or the wrong cutoff for an assay passes every gate if the method declared it.
> That knowledge goes into the method and its plugin, once, where it is checked on every run.

The owner decides whether it goes in; the engine's claims in it are true at 0.2.27, and the
"every number in prose" clause is true for judgment rationale and open answers and true for
report prose only in the weak form L57 fixes.

# stringency: the plan

The one work list. Every open item of the engine, its plugins, skills, console, integrations and
operations is a row in this file, with an id that is never reused. The other documents under
`spec/plans/` are the reasoning behind rows that cite them and carry no work list of their own;
when a document's last row closes it moves to `spec/archive/`, whose contents are history and
never an instruction to a session. The measurement tables the UX work reports into are
`measurements.md`. Done rows move to `archive/backlog-done.md` with their ids and the date, since
notes and the trace cite them. Items marked *design* change design text and need the owner's
approval; the rest are DECISIONS-level or below.

This file replaced `roadmap-2026-10.md` (lanes A to T, archived with their history) and
`backlog.md` on 2026-10-21: open items had come to live in a roadmap, a backlog and the open
sections of nine plan documents, and the owner could not see what might be lost between them.
Areas below replace the lanes as the grouping; a row's area says what kind of work it is, not
who owns it.

**Status 2026-10-21.** Written from the backlog as it stood (A5, E2, K3, K4, K6, L3 to L6, L9,
L11, H5, L34 to L38, L42, L45, L46, L48, L52, L53), the open sections of `confirm-once.md`,
`judge-sources-plan.md`, `console-and-fleet-plan.md`, `trace-integrity-plan.md` and the archived
`open_mode_plan.md` and `roadmap-2026-10.md` (L67 to L81), `omicsbench-assessment.md` (L54 to
L60), `decision-points.md` (L61 to L66, the owner's reading of 2026-10-21) and the literature
check of the judgment premise (`notes/2026-10-21-1300-judgment-replicates-evidence.md`, L82 to L85).
Nothing in it is built beyond what the State section says.

## How this file is kept

- A session that opens work adds a row here, in the area it belongs to, with the next id. A
  session that closes a row moves it to `archive/backlog-done.md` with the date and the release,
  in the same commit as the work.
- The State section and "Next, in order" are rewritten by the session that changes them; the
  waiting table is edited when the owner answers.
- A new plan document is written only for reasoning that does not fit a row (a design with
  several parts, an assessment of other work). It opens with a dated Status line naming the rows
  it stands behind, and it holds no list of its own.
- `spec/README.md` maps the directory and `notes/INDEX.md` is the session map; both change in
  the same commit as what they describe.

## State (2026-10-21)

Engine 0.2.27 on `main` (`a22967b`); plugin singlecell 0.6.2; the Xenium method
`stringency-xenium-method` at `v0.6.0-rc19` (its six open tools pass on the Lyons liver
delivery under 0.2.26 and plugin 0.6.2); the toy method at `v0.2.0`. The last install the notes
record on the lab workstation is `0.2.23-sc0.5.1` with plugin 0.6.1 after it (2026-10-20);
0.2.25 to 0.2.27 are not recorded as installed. The console runs as `stringency-console.service`
on loopback 8765 from the shared install. Lyons CLP v2 (`/lab/projects/Lyons_CLP/v2_rosc_controls/`):
`qc_all` and the four `upstream_*` organs delivered on rc12 and rc12.1 (2026-10-08 to
2026-10-12). The declare skill and the Xenium analysis skill changed after their last publish.

## Next, in order

1. The owner's jobs in the waiting table: the install of 0.2.27, the republish of the declare
   and Xenium skills, and the reading of the applied design amendments.
2. Decision points, first cut (`decision-points.md`): L61 the `decision:` block, its evidence
   floor, the lint rule and the default hold view, with L9 folded in; L55 the citation and
   considered-set slots on `propose`; L62 the `presented` event. One or two engine sessions,
   then the Xenium method declares its decisions (method side).
3. L54, the seven downstream predicates the design names, as plugin singlecell 0.7.
4. L59 and L60, small, with the next triage pass.
5. L56 and L57, the judgment and report citation checks; L58 waits on them.
6. L79, the acceptance run of the Xenium analysis skill by someone other than the developer,
   once the skills are republished; L77 the open-mode acceptance after it.
7. Confirm-once (L5, L68, L6, L69; L67 after the owner's decision) when the owner asks for it.
8. The menu keys of the decision block (L63 to L66) as a method step needs them; L64 last.

Everything else waits on the owner, on a trigger named in its row, or on a method that needs it.

## Open items

### Engine: decision points

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L61 | a decision point's evidence is named in three places (the delivery skill's `hold_view`, the method skill's `decisions`, the operator's reason) and required in none, so a method can ship a parameter hold that shows a number and nothing to judge it by; and the owner wants a person's sign-off on every decision point, which `param.agent_proposed` (departure only) cannot give (L9) | `decision:` beside a parameter's `range` in `pipeline.yml`: `evidence` (a source as the delivery skill names them, a `text:` provenance sentence, or `none` with `because:`), `hold: departure \| always` (default `departure`; `always` retires `sc.decision_unreviewed`); the engine's default hold view renders the source when the skill names none; `lint` errors on the silent case (a ranged decision point with no `decision:`) once the method's `requires.engine` names the engine that knows the block, warns before, errors on `none` without `because:` and on a source no upstream step produces | *design* (3.1 additive, 13); `decision-points.md` 2, 3 |
| L55 | `propose --reason` is stored (`rationale_ref`), shown at the hold (L8) and checked by nothing, so "ndim 35: cumulative variance 0.82 at 35" is approved without anyone knowing whether the elbow table holds 0.82 at row 35 | `propose --cite <source>[:row[:column]]` (repeatable) and `--considered <v1,v2>`; reason, citations and the considered set stored as one message; `param.agent_proposed@2` carries `cited` and `considered` in its evidence and opens its reason with "cites nothing from `<source>`" or "considered 30, 40"; `param.reason_unmatched@1` (pre, `*`, flag) checks the reason's numerals against the cited cells as `ans.numeral_unmatched` does; the operator skill's section 9 requires both | engine, DECISIONS-level; 14.1 additive; `decision-points.md` 4, `omicsbench-assessment.md` 4.2 |
| L62 | whether the operator rendered a step's evidence before proposing is nowhere in the trace; `present` reads and writes nothing | a `run_events` row `presented` (source, hold if any, OS user, session ref) written by `present`; the parameter hold's packet reads "evidence rendered 10:42, proposed 10:44" or "proposed; no evidence of this step rendered in this run". Rendering is not reading; the absence is what the line is for | engine, DECISIONS-level; `decision-points.md` 5 |
| L9 | a decision point taken at its default opens no hold (`param.agent_proposed` fires on departure only) and module.yml `confirm:` is parsed but read by nothing; the owner wants a person's sign-off on every decision point (2026-10-07); the singlecell plugin bridges with `sc.decision_unreviewed` | folded into L61 as `decision.hold: always`; this row closes with it | engine, DECISIONS-level; `decision-points.md` 2 |
| L63 | menu: a threshold picked from evidence computed for the proposed value only | `decision.sweep: {output: <table>}`: the module computes every candidate and writes a table with a column named for the parameter; `param.not_in_sweep@1` (pre, block) refuses a proposal that is not a row of it; the hold shows the table or chart with the proposal marked. The method author opts in per step; clustering's resolution grid is the existing instance | engine, DECISIONS-level; method per step; `decision-points.md` 6 |
| L64 | menu: a proposal with no deterministic pick to compare against | `decision.rule: {output: <name>, tolerance}`: the module writes the rule's value; `param.rule_departure@1` (pre, flag) fires when the proposal leaves it by more than the tolerance, evidence carrying both. On the menu for a step that has a rule; the owner judged it too rigid to pursue on its own (2026-10-21), so no date | engine, DECISIONS-level; `decision-points.md` 6 |
| L65 | menu: a high-stakes pick made by the operator in the session that hoped for it | `decision.judged: {module: <judgment module>}`: a judgment module whose vocabulary is the candidate list picks from the evidence with cited cells, three replicates, abstention; the parameter takes the consensus with `param_source: judged`; disagreement is a hold; every `judg.*` applies | *design* (5 additive, 3.1); `decision-points.md` 6 |
| L66 | menu: whether an accepted threshold mattered is never tested | `decision.sensitivity: {neighbours: n, through: <step>}`: after acceptance the engine forks at the neighbouring candidates, runs through the named step, and the delivery reports what moved; a control kind, never blocking; refused under strict unless declared there | *design* (11); `decision-points.md` 6 |

### Engine: holds and confirmation

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L5 | inherited confirmation (design 2.7) needs every input `derived_from` a confirmed project, so two kinds of input defeat it although they are not this design's data: (a) a raw input byte-identical to one the confirmed upstream projects bound under the same name and type (`qc2_summary_all` binds the layout and histology files every `qc2_*` project bound, hashes equal; an ordinary confirm hold opened, 2026-10-06); (b) a `role: reference` input (`qc2_outliers_all`, expected the same day) | inherit when every input is either derived from a confirmed project, or raw and identical in name, type and hash to an input of one of those projects, or `role: reference`; the echo-back's inherited paragraph names which inputs were matched that way; a test for each kind | engine, DECISIONS-level; `confirm-once.md` 3(a) |
| L6 | `review --holds` batch-reviews confirm holds only; `param.agent_proposed` opened sixteen identical flag holds across the eight `qc2_*` projects (eight on the split's pre-filter, eight on the tissue thresholds), each relayed one by one with the owner's one sentence (2026-10-06) | extend batch review to flag holds whose predicate, step and `proposed` evidence are identical across sibling projects, with the differing cells shown as the confirm batch does; refuse a batch whose packets differ; and accept-once: a sibling's accepted proposal under the same module version resolves the new hold `inherited` with a pointer, listed under "inherited today". Also the console's batch cards (`console-and-fleet-plan.md` "What is open" 1). The owner's decision 4 of `confirm-once.md` section 5 (one module version only, recommended) | engine, DECISIONS-level; `confirm-once.md` 3(d) |
| L67 | one `design.yml` was confirmed five times in one study (Lyons CLP, 2026-10-06); inheritance is per project and any raw input defeats it | a study-level design acceptance: the first accepted confirm hold under a project tree records (owner, design hash, method repository, major version); a later project in the tree with the same design hash and owner inherits whatever its inputs, the hold created and resolved `inherited` with a pointer, the echo-back still written. Needs the owner's decisions 1 to 3 of `confirm-once.md` section 5 (approve; the tree is the directory the board walks; never expires) | *design* (2.7, 7.2); `confirm-once.md` 3(b) |
| L68 | a project re-declared byte-identically on a new method tag after a packaging fix opened a fresh confirm hold (`cluster_liver`, rc1 to rc2) | when the declarations are byte-identical to a project the same owner confirmed under the same method repository and major version, the acceptance carries over, raw inputs included; the echo-back names the project it inherits from | engine, DECISIONS-level; `confirm-once.md` 3(c) |
| L69 | nothing tells the person in advance whether a project will inherit its confirmation or why not | `declare --check` and `init` print, before the hold decision, which acceptance the project would inherit and by which rule, or the input or field that breaks the match; after L5 and L68 | engine, DECISIONS-level; `confirm-once.md` 3(e) |
| A5 | reviewer-run review page, `via: web` | `review --serve` (`via: web`) is built (engine 0.2.8) and design 7.5 carries it; the row was never closed and the record does not say what remains (the several-reviewers rule of `console-and-fleet-plan.md` section 5 is the candidate). The owner closes it or names the remainder | *design* (7.5, 14.1); `ux-two-audiences.md` 5.2 |

### Engine: judgments and evidence

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L56 | a judge may leave a contradicting cell uncited and keep `high`; `judg.confidence_consistent` counts only the cells it cited | `judgment.must_cite: [<table>.<column>]` in the manifest (module contract via DEVIATIONS); `judg.required_evidence_uncited@1` (post, judgment, flag) per replicate and item: a named column's cell for the item appears in neither evidence list; the prompt suffix names the columns; first users `assess-batch` and `annotate-clusters` | engine, DECISIONS-level; module contract 3.2 via `DEVIATIONS.md`; `omicsbench-assessment.md` 4.3 |
| L57 | report prose is checked against every cell of every evidence table, so a number that appears anywhere passes whether or not it is the number the sentence is about | the report schema gains `cited` refs as answers have; `judg.numeric_claims_match@2` uses the cited cells as the denominator when present, every cell otherwise; `upstream-report` the first user. Check first whether its prose is produced by a harness call or by code; if by code the row is moot for it | engine, DECISIONS-level; 8.1 additive; `omicsbench-assessment.md` 4.4 |
| L58 | direction and comparison claims ("higher in CLP", "above the threshold") are unchecked; only numerals are | an optional `claims` list in a judgment or report output, `{kind: compare \| threshold, table, row(s), column, relation, value}`; `judg.claim_unsupported@1` (post, block) evaluates each against the cells; coverage counts structured against free claims; after L57 | *design* (8.1 additive, 6.5 row); `omicsbench-assessment.md` 4.5 |
| L38 | textual claims in a rationale about the vocabulary, objective or design are unchecked; only cells and numerals are | `commons-assessment.md` 4.5: optional `cited_text: [{source, quote}]` in a module's schema; `judg.quote_exists` finds the quote by normalised substring match (ten-character floor) in the named section of the rendered prompt, default `log` | engine, additive to 8.1; low |
| L3 | control results do not record which judge answered, so a module's passing controls say nothing once the harness or model changes | `archive/egress-and-remeasurement.md` part 2 item 3: `harness_kind` and `model_resolved` on control results, the judge on the coverage report's control line, a lint warning when the project's judge differs from the last passing controls'; with L34 | engine, DECISIONS-level |
| L4 | no control kind for ill-formed evidence (dropped column, blanked items, negated objective, contradicting reference), so over-answering on damaged input is measured only in engine tests | `archive/egress-and-remeasurement.md` part 2 item 1: control kind `ill_formed` with seeded generator tools per plugin and `over_answer_max` / `abstain_min` expectations; singlecell's `drop_column` and `blank_items` first, for the annotation judgment | *design* (11); plugin tools per method |
| L70 | a reviewer weighing replicate 1 against replicate 3 cannot see whether they came from the same model | render `harness_kind`, `model_resolved`, `isolation` and `via` per replicate on the review page, in `present --hold`, in the hold packet and in `summary.md`; the data is in `invocations` | engine, low; `judge-sources-plan.md` S3 |
| L71 | one judgment harness per project; a panel of judges from several sources has no specification | `panel:` of judge slots in `stringency.yml` (harness, model, count, `role: vote \| check`), `judgment.replicates` as the module's minimum, mixed families in one step; `judgment_harness:` kept as the one-slot shorthand. After the Qwen3 evaluation (in L34) and the owner's decision 4 of `judge-sources-plan.md` section 6 (whether `role: check` opens a hold under strict); weighed against the literature check of 2026-10-21 (`notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 3): under a unanimity rule a weaker second family cannot lower the quality of agreed labels, only raise the hold rate | *design* (10.1, 10.2, 17); `judge-sources-plan.md` S4 |
| L72 | the operator can answer its own judgment requests (`run --responses` with no delegate) and the trace does not single it out | keep the fallback and have `run --responses` require `reported.agent` to differ from `STRINGENCY_OPERATOR`, recording `via: operator` and `isolation: none` when it does not, refused under strict (recommended); or remove it from the operator skill. The owner's decision 5 of `judge-sources-plan.md` section 6 | skill and engine, DECISIONS-level; `judge-sources-plan.md` S5 |
| L73 | a high-stakes judgment step cannot demand a direct adapter while routine steps use the project's panel | `module.yml` `harness:` beside `model:`; deferred until a module needs it, since L71's panel covers a project that wants enforced isolation throughout | *design* (module contract via `DEVIATIONS.md`); `judge-sources-plan.md` S6 |
| L82 | the unanimous-but-wrong rate of a judgment module is unmeasured: replicates of one model with one prompt are unanimous on the errors the model makes consistently, and sampling-based detectors miss them (the literature check of 2026-10-21) | in positive controls, report accuracy on unanimous items separately from held items, per module version; the `judgments` and `consensus` tables hold the data; one line on the controls report | engine, low; `notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 1 |
| L83 | every replicate of a judgment step reads the same rendered prompt, so fresh contexts give isolation, not independent errors | per-replicate prompt perturbation (a different item order under `all_items`, a different vocabulary order): the prompt becomes per replicate, which touches 3.5 step 3 and the prompt hashing | *design* (3.5); `notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 2 |
| L84 | an agreed label is never seen by a person unless the module declares `sign_off: always`; agreement is the weak half of the signal | sign off a random sample of agreed items (`sign_off: {when: sample, fraction}`), the confidence-driven inference pattern; the owner's choice | *design* (7.2, module contract via `DEVIATIONS.md`); `notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 4 |
| L85 | the methods paragraph (design 13) says "three independent replicates per cluster"; "independent" claims more than the evidence supports | "in separate contexts" in the design text and the methods template | design text, one line; the owner; `notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 5 |

### Engine: delivery, trace and inputs

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L35 | a delivered table carries no trust statement where a person reads it: `present` and the console show the table, and whether its path ran under a verified environment, through dispatch, or through a person's verdict is in `coverage.md` only | `commons-assessment.md` 4.1: `deliver` computes a `provenance` block per `index.json` entry by walking the producing step's ancestors (execution verified or as reported naming the steps; judgment direct, dispatch or none; the holds on the path and their verdicts); `present` prints one pinned word (`checked` or `as reported`) and the review list under each table's title; the console shows the same as a pill; a mixed path takes the lower word | engine, DECISIONS-level; the collapse rule is the owner's |
| L59 | a sweep across forks (resolution 0.4, 0.6 and 0.8 as three forks, one delivered) is visible only to someone who reads every fork's trace | one line in `coverage.md` and `summary.md`: "forks of this project at `05_select_resolution.resolution`: 3 (0.4, 0.6, 0.8); this run 0.6, delivered", from the `runs` table | engine, low; `omicsbench-assessment.md` 4.6 |
| L60 | a question the operator cannot answer from the delivery is recorded nowhere; the `questions` table has no outcome | `answer --cannot --question <id> --reason "..."`: an `answers` row with `status: unanswerable` and no label; the report's short list names it; coverage says "questions: n asked, m answered, k unanswerable" | engine, DECISIONS-level; `omicsbench-assessment.md` 4.7 |
| L52 | the database does not require the event the Store writes: direct SQL changes state silently (T1 and T2 built, 0.2.25) | T3: a revision bound to one event, triggers on the mutable tables, migration 0007, a hash chain on the event tables with its head in the delivery; needs the DEVIATIONS entry for 9.4 and 9.5 acknowledged | engine; 9.4 and 9.5 via `DEVIATIONS.md`; `trace-integrity-plan.md` T3 |
| L11 | a correction fork should carry its parent's outputs for comparison: the owner asked (2026-10-07) that "whenever a batch correction fork is initiated" the uncorrected UMAPs be delivered beside the corrected ones; a forked step cannot see the parent run's artifacts (job.json carries no `parent_run_id`), so the method does it through a project-level reference input (`uncorrected_batch_evidence`), which only works when the correction is a new project, not a fork | expose the parent run's step outputs to a fork's steps as `$parent.<step>.<output>` bindings (resolved only in a forked run, empty otherwise), so the report step of a correction fork binds the parent's `batch_evidence` without a re-declaration | engine, DECISIONS-level |
| L48 | a person cannot bring a file of their own into an open project after init (a gene-set table for `score-pathways`): the inputs are the delivery's and the upstream's, and `call --in` names only artifacts and declared inputs | a verb that declares an input on an open project (hashed, with a source sentence) and a confirm, or `ask --with <file>` that files it beside the question | *design* (2.3 inputs after init) |
| K3 | a band edge can be impossible for its column (a negative floor on a count) and the engine says nothing | warn when a band edge violates the column's type, if columns ever carry one; today the method clips (open on the method side) | engine, low |
| K4 | `STATUS.md` carries no line for the newest change and `board` has no `--watch` | `notes/2026-09-18-1830-board-and-present.md` | engine, low |
| H5 | staged mode: objective list with stages, `run --objective`, fork at a stage boundary carries an objective, `obj.declared_after_result` | after application 1 as two chained projects shows where option 1 chafes (`spec/archive/declarations-and-objectives.md`) | *design* |

### Engine: harnesses

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L34 | **one operator harness, one subscription-funded judge route.** `operator_id.py` knows Claude Code's environment only; the skills are written for Claude Science and Claude Code; judgments on the lab's subscription go through `subagent` dispatch only, and the `openai-compatible` adapter is a stub although design 17's trigger (the Qwen3 evaluation) is satisfiable on PROTSEQ. The owner, 2026-10-14: the lab has an OpenAI Codex team plan; open Codex as a harness and build in as much flexibility on the harness side as possible | `archive/roadmap-2026-10.md` Lane J (W7): H1 a survey of Codex CLI on PROTSEQ (`integrations/codex/README.md`); H2 the operator and declare skills split into a harness-neutral core and per-harness appendices rendered by `render_skill.py --harness`, `operator_id.py` recognising Codex; H3 judgment adapters `openai-compatible` (`judge-sources-plan.md` S1) and `command` (the engine runs a configured command per replicate against the request file: `codex exec`, headless Claude Code), with L3 so control results name the judge; the Qwen3 evaluation (S2) and its "competent" definition, the owner's decisions 2 and 3 of `judge-sources-plan.md` section 6; design text for 10.1 and 10.2 drafted after H1 | *design* (10.1, 10.2); **waiting on the owner's go and a Codex login on PROTSEQ** (since 2026-10-14) |
| L36 | the dispatch envelope and the hold protocol are pinned only by engine-side tests and skill prose, so a new operator harness (Codex) implements both from reading and nothing it can run says whether it did | `commons-assessment.md` 4.2: `tests/shared/dispatch.json` and `holds.json` (cases in, the envelopes and `review --attest` calls out, the refusals), enumerated by the engine's tests and by `integrations/<harness>/conformance.py`; a harness enters `compat/known-good.yml` with a passing run; a runner asserts the set it enumerated is not empty | engine and integrations, DECISIONS-level; with L34 |

### Method and plugin

The Xenium method's own work list is its repository's `PLAN.md` (phases F7 and F9 to F12 of
`spatial-method-plan.md` section 6: the owner's reading of `cell_types_mouse@2`, niches,
descriptives and DE, reports and skills, the retrospective); engine rows it waits on are filed
here as they arise. The bulk RNA-seq plan is dormant since 2026-09-23 and kept in
`archive/bulkrna-plan.md` until the owner reopens it.

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L54 | the predicates the design names for the downstream tools (`de.replication_unit`, `de.covariate_omission`, `de.selection_bias`, `test.multiple_comparison`, `test.assumptions_unchecked`, `spatial.neighborhood_undeclared`, `spatial.no_permutation_null`) are unbuilt while the tools now ship (`pseudobulk-de`, `compose-cells`, `neighborhood-enrichment`) | plugin singlecell 0.7 with must-fire and must-pass fixtures over the tools' state envelopes; `de.replication_unit` blocks a unit finer than the design's, `de.covariate_omission` flags a declared batch absent from the formula; the four whose facts the tools already emit first | plugin, DECISIONS-level; `omicsbench-assessment.md` 4.1 |
| L46 | `module.yml` `egress` (DEVIATIONS 2026-10-16, "Module contract 3.2: `egress`", proposed, not built): a module cannot declare what it sends, so every module whose scripts reach the network is counted as class 4 and lint only warns | the owner acknowledges or refuses the DEVIATIONS entry; if yes: the field, `assess` reading it, lint failing on an undeclared network reach | module contract via `DEVIATIONS.md`; the owner |

### Skills, documents and onboarding

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L79 | no one other than the developer has run `stringency-analyze-xenium-upstream` end to end; the measurement its design asked for is unwritten | the acceptance run: someone other than the developer runs the synthetic `xenium-upstream` analysis through the skill with limited intervention, measured as a row in `measurements.md`; after the republish of the operator, declare and analysis skills; the owner names the tester | skills; the owner for the tester; `archive/roadmap-2026-10.md` W6 |
| L77 | open mode has no acceptance or baseline: ten questions by a third person against a plain session over a read-only copy of the delivery, graded | `archive/open_mode_plan.md` O5: `evals/liver-questions.yml` with grading notes and tool-computed targets; `integrations/claude-science/open-mode-acceptance.md`; a non-developer's run; the plain-session arm; an LLM grader with deterministic tools for numbers and the binary rubric; both arms side by side in a note and a row in `measurements.md`; after the Xenium skill republish | skills and owner; `archive/open_mode_plan.md` O5 |
| L78 | a session script that recurs across open projects has no route into the method as a tool | `archive/open_mode_plan.md` O6: `answers --export`, `promote`, and `stringency-revise` in the template (with L37); the first promotion of the script that recurs in L77 | engine verb and template; after L77 |
| L37 | the override corpus (design 7.6) is read back as a rate only; the holds' reasons from the Lyons runs are in the store and nothing proposes a prompt, vocabulary or criteria change from them, so 7.6's "a prompt change cites the review ids" has no route and design 17's reason codes have no corpus to emerge from | `commons-assessment.md` 4.4: `review --export [--module]` writes one markdown per resolved hold (YAML frontmatter: hold, kind, predicate, step, item, reviewer, `via`, verdict, reason, bound hashes; the packet below) into `runs/<id>/reviews/` and the delivery; a `stringency-revise` skill in the method-repository template reads them for a module version, groups by theme, proposes changes citing hold ids, classifies new, duplicate, extension or conflict, and waits | engine verb DECISIONS-level; skill in the template, the Xenium method the first user |
| L45 | the egress relay: in the owner's drive the operator added the report's "not assessed" line after the entries; section 6 of the operator skill names only the `ceiling:` and `assessed:` lines and the entries | decide whether the line belongs in the protocol and write it into section 6 and the analyze template | skill wording; the owner |
| E2 | `STRINGENCY_OPERATOR_VERSION` is `unknown` unless the brief carries `--app-version`; no in-session route to the app's version was found | the next exit run records a version | skill |

### Console

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L74 | the run page has no delivery gallery and there is no decision history page | the report's `figures.csv` with the summary beside it on the run page; a history page of `reviews` joined to `holds` across roots with `status --overrides` per module at the top; when the owner asks | engine (console), DECISIONS-level; `console-and-fleet-plan.md` "What is open" 2 |
| L75 | several runs on one host share nothing: no slots, no queue, no cell on the board saying a step waits | C4, the resource cap: `STRINGENCY_SLOTS`, `capacity.yml`, `slot:waiting` and `slot:acquired` step events, the console cell; `resources_observed` in `executions.observed_params_json` to size it; when the owner asks | engine, DECISIONS-level; `console-and-fleet-plan.md` 6.3 |
| L81 | an open project's questions and answers are on the CLI (`present --answer`) and in `report.md` but not on the console or the board | `archive/open_mode_plan.md` O3: `/questions/<project>`, `/answer/<id>`, `/api/questions`, the `answer_recorded` event; board cells and a sentence for an open project; no form; when the owner asks | engine (console), DECISIONS-level |
| L76 | the console plan's section 10 measurement (hold-to-verdict per ask, relayed holds, session switches) on the lung, gut and spleen traces was never written up | the numbers from the three traces as a note and a row in `measurements.md` | note; low; `console-and-fleet-plan.md` 10 |

### Operations, integration and site

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L80 | CI runs lint, the unit tests and the skill check on a bare runner; the synthetic `xenium-upstream` run is not on CI's institutional list and `compat/known-good.yml` is kept current by hand | add the synthetic upstream run to the institutional list; keep `known-good.yml` current with each release (a recurring job named in `docs/release.md`) | integration; `archive/roadmap-2026-10.md` Lane I |
| L53 | the operator runs as the project owner's Unix user and can open or replace `prov/run.db` whatever the Store refuses | T4: a service identity owning `prov/`, the writing verbs through one door, the console unit moved; the PROTECT question | operations; the owner; `trace-integrity-plan.md` T4 |
| L42 | the site rule for `/data/protect` (a project under a path may not declare a ceiling above a site maximum) exists only as a proposal in the archived egress plan | `siteconfig.py` `egress: {max_class_under: {<path>: <class>}}`; `init.egress_exceeds_ceiling` names the rule; only if the owner wants it (decision 6 of `judge-sources-plan.md` section 6: a refusal or a warning) | engine; the owner decides |
| K6 | method and plugin tags pushed before checks passed remain on GitHub (`spec/archive/lane-c-day1-2026-09-17.md`, 2026-09-18 section) | delete them, or say in each repo's README which tags are usable | operations, owner |

## Waiting on the owner

One table of everything that moves only on the owner's word, so nothing waits in a section
nobody reads. The row id says where the work is filed; "where" says where the text to read is.

| what | row | where | since |
|---|---|---|---|
| install engine 0.2.27 on the lab workstation and restart the console; republish the declare skill and the Xenium analysis skill (both changed in the triage passes of 2026-10-21) | State | `docs/release.md`, `integrations/claude-science/publish-skills.md` | 2026-10-21 |
| read the design amendments applied with builds and say if any should read differently: 2.5 `params:` (L24), 2.6 fork inheritance (L27), 14.1 `fork --check` and `probe`, 10.3 the method checkout and image names (L7, L31), open mode's section 6 amendments (2026-10-16 and 2026-10-20), the egress text (2026-10-20) | | `archive/roadmap-2026-10.md` "Needs the owner" 1 to 4; `archive/open_mode_plan.md` 6; the dated sentences in `stringency-design.md` | 2026-10-14 |
| acknowledge the DEVIATIONS entry for `judgment.sign_off` (module contract 3.2) | | `DEVIATIONS.md` | 2026-10-08 |
| acknowledge or refuse the DEVIATIONS entry for `module.yml` `egress` | L46 | `DEVIATIONS.md` | 2026-10-16 |
| trace integrity: a DEVIATIONS entry for 9.4 and 9.5 (T3), or stay at T2; a service identity for `prov/` (T4) | L52, L53 | `trace-integrity-plan.md` | 2026-10-20 |
| the go-ahead for Codex as a harness, and Codex logged in on PROTSEQ for the survey; the shape of the Qwen3 evaluation and what "competent" means | L34 | `archive/roadmap-2026-10.md` Lane J; `judge-sources-plan.md` 6 (2, 3) | 2026-10-14 |
| confirm-once: approve the study-level acceptance (1), the scope of "the same tree" (2), whether an acceptance expires (3), accept-once within one module version (4) | L67, L6 | `confirm-once.md` 5 | 2026-10-14 |
| judge sources: whether `role: check` opens a hold under strict (4); remove or mark the operator-judges-itself fallback (5); the `/data/protect` rule as a refusal or a warning (6) | L71, L72, L42 | `judge-sources-plan.md` 6 | 2026-10-14 |
| whether the relay's "not assessed" line belongs in the hold protocol | L45 | `integrations/claude-science/stringency-operator/SKILL.md` 6 | 2026-10-20 |
| the tester for the acceptance runs | L79, L77 | this file | 2026-10-14 |
| F7: read `cell_types_mouse@2` and the organ guides (decision 17) | method `PLAN.md` | `spatial-method-plan.md` 8 | 2026-10-07 |
| whether to open staged mode (H5), inputs after init (L48), ill-formed controls (L4); what remains of A5 | H5, L48, L4, A5 | their rows | 2026-10-14 |
| the console unit: `loginctl enable-linger` once; `notify.yml` `page_url` if hold emails should link to the inbox | | `console-and-fleet-plan.md` 8.4 | 2026-10-14 |
| stale tags on GitHub; the toy method's GitHub remote | K6 | its row | 2026-09-18 |
| judgment replicates, the literature check: which of the five proposals to open (the unanimous-but-wrong rate in controls, per-replicate prompt perturbation, the mixed panel, sampled sign-off, "in separate contexts" in the methods text) | L82 to L85, L71 | `notes/2026-10-21-1300-judgment-replicates-evidence.md` | 2026-10-21 |
| decision points: two choices taken in the plan, say if otherwise: lint grandfathers a method until its `requires.engine` names the engine that knows `decision:`; `hold` defaults to `departure`. The default-beside-proposal verdict is not pursued (the owner, 2026-10-21) | L61 | `decision-points.md` 9 | 2026-10-21 |

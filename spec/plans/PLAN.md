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

Engine 0.2.33 on `main` (the seven passes of 2026-10-21 and 2026-10-22: triage pass 5, decision points, judgment replicates, confirm once, Codex as a harness, plugin 0.7.0, the citation checks); plugin singlecell 0.8.1 (the seven downstream predicates and the droplet widening, 2026-10-22); the scRNA-seq method `stringency-scrnaseq-scanpy-method` 0.1.0; the Xenium method
`stringency-xenium-method` at `v0.6.0-rc19` (its six open tools pass on the Lyons liver
delivery under 0.2.26 and plugin 0.6.2); the toy method at `v0.2.0`. `0.2.27-sc0.6.2` is installed in the
shared prefix on the lab workstation (`/data/lab/env/stringency/current`, 2026-10-20 17:05) and
the console, `stringency-console.service` on loopback 8765, runs from it (verified 2026-10-21). Lyons CLP v2 (`/lab/projects/Lyons_CLP/v2_rosc_controls/`):
`qc_all` and the four `upstream_*` organs delivered on rc12 and rc12.1 (2026-10-08 to
2026-10-12). The declare skill and the Xenium analysis skill changed after their last publish.

## Next, in order

Rewritten 2026-10-21 after the owner answered every row of the waiting table. Each pass is one
or two sessions and ends with its rows in `archive/backlog-done.md` and a release.

1. Triage pass 5: done 2026-10-21 (engine 0.2.28; L72, L46, L3, L70, L59, L60 in the done
   ledger; L86 filed for the Xenium method's `resegment-nextflow` egress block).
2. Decision points, first cut: done 2026-10-21 (engine 0.2.29; L61, L55, L62, L9 in the done
   ledger). Method side next, when the Xenium method is the work again: declare `decision:` on
   `ndim`, `resolution`, `method`, `scale_factor`, `integration` and `cluster_method`, raise
   `requires.engine`, re-render the skills; `sc.decision_unreviewed` retires where `hold:
   always` is declared. The menu keys (L63 to L66) wait on that first run.
3. Judgment replicates: done 2026-10-21 (engine 0.2.30; L83 per-replicate orderings, L84
   sampled sign-off with its DEVIATIONS entry). L82, the unanimous-but-wrong rate, waits for
   enough runs (the owner).
4. Confirm once: done 2026-10-21 (engine 0.2.31; L67, L6, L5, L68, L69 in the done ledger).
   The Lyons CLP projects name no study yet: add `study: lyons_clp` to each `stringency.yml`
   when the engine is installed (one line per project; nothing else changes).
5. Codex as a harness: H1 to H3 and L36 done 2026-10-21 (engine 0.2.32). What remains of L34 is
   the Qwen3 evaluation (a local model on the GPU, the Lyons re-judgment as sibling projects
   under both harnesses) after the owner defines "competent".
6. L54: done 2026-10-22 as plugin singlecell 0.7.0 (`v0.7.0`), all seven pre-phase over the
   action, the design and the history. Method side, with the next tag: `requires.plugins`
   to 0.7.0, the seven listed in `policy.yml` and in the three tools' `gates`, and
   `test.min_samples_per_group` and `spatial.n_perms` ranges if the defaults (2, 100) are
   not the method's.
7. L56 and L57: done 2026-10-22 (engine 0.2.33; `judgment.must_cite` with its DEVIATIONS
   entry awaiting the owner, `judg.required_evidence_uncited`, the `cited` output type and
   `judg.numeric_claims_match@2`). L58 and L38 are open rows. Method side, with the next
   Xenium tag: gates name `judg.numeric_claims_match@2`; `assess-batch` and
   `annotate-clusters` declare `must_cite`.

The seven passes are done. What the owner does next: install 0.2.33 and plugin 0.7.0 on the
shared prefix, restart the console, republish the three skills; the method-side rows above
(L86, the `decision:` blocks, `requires`, `study:` on the Lyons projects, the gates); the
Qwen3 evaluation; the tester; F7.

8. The benchmark (`benchmark-plan.md`, added 2026-10-22): Phase 0 (L87) is running (the
   baseline, eighteen Opus 5 sessions, started 2026-10-21 evening); Phase 1 (L88) is mostly
   done the same night (the mapping, plugin 0.8.1, the method 0.1.0); the method's skills and
   a synthetic engine run, then L89 (the adapter) in order.

Not scheduled: what the owner deferred on 2026-10-21 (L52, L53, L42, L82, H5, L48, L4, the
console rows until asked) and what waits on a person (the skill republish, the tester, F7).

## Open items

### Engine: decision points

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L63 | menu: a threshold picked from evidence computed for the proposed value only | `decision.sweep: {output: <table>}`: the module computes every candidate and writes a table with a column named for the parameter; `param.not_in_sweep@1` (pre, block) refuses a proposal that is not a row of it; the hold shows the table or chart with the proposal marked. The method author opts in per step; clustering's resolution grid is the existing instance | engine, DECISIONS-level; method per step; `decision-points.md` 6 |
| L64 | menu: a proposal with no deterministic pick to compare against | `decision.rule: {output: <name>, tolerance}`: the module writes the rule's value; `param.rule_departure@1` (pre, flag) fires when the proposal leaves it by more than the tolerance, evidence carrying both. On the menu for a step that has a rule; the owner judged it too rigid to pursue on its own (2026-10-21), so no date | engine, DECISIONS-level; `decision-points.md` 6 |
| L65 | menu: a high-stakes pick made by the operator in the session that hoped for it | `decision.judged: {module: <judgment module>}`: a judgment module whose vocabulary is the candidate list picks from the evidence with cited cells, three replicates, abstention; the parameter takes the consensus with `param_source: judged`; disagreement is a hold; every `judg.*` applies | *design* (5 additive, 3.1); `decision-points.md` 6 |
| L66 | menu: whether an accepted threshold mattered is never tested | `decision.sensitivity: {neighbours: n, through: <step>}`: after acceptance the engine forks at the neighbouring candidates, runs through the named step, and the delivery reports what moved; a control kind, never blocking; refused under strict unless declared there | *design* (11); `decision-points.md` 6 |

### Engine: holds and confirmation

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|

### Engine: judgments and evidence

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L58 | direction and comparison claims ("higher in CLP", "above the threshold") are unchecked; only numerals are | an optional `claims` list in a judgment or report output, `{kind: compare \| threshold, table, row(s), column, relation, value}`; `judg.claim_unsupported@1` (post, block) evaluates each against the cells; coverage counts structured against free claims; after L57 | *design* (8.1 additive, 6.5 row); after L57 (done 2026-10-22); `omicsbench-assessment.md` 4.5 |
| L38 | textual claims in a rationale about the vocabulary, objective or design are unchecked; only cells and numerals are | `commons-assessment.md` 4.5: optional `cited_text: [{source, quote}]` in a module's schema; `judg.quote_exists` finds the quote by normalised substring match (ten-character floor) in the named section of the rendered prompt, default `log` | engine, additive to 8.1; low |
| L4 | no control kind for ill-formed evidence (dropped column, blanked items, negated objective, contradicting reference), so over-answering on damaged input is measured only in engine tests | `archive/egress-and-remeasurement.md` part 2 item 1: control kind `ill_formed` with seeded generator tools per plugin and `over_answer_max` / `abstain_min` expectations; singlecell's `drop_column` and `blank_items` first, for the annotation judgment; the owner, 2026-10-21: deferred | *design* (11); plugin tools per method; deferred |
| L71 | one judgment harness per project; a panel of judges from several sources has no specification | `panel:` of judge slots in `stringency.yml` (harness, model, count, `role: vote \| check`), `judgment.replicates` as the module's minimum, mixed families in one step; `judgment_harness:` kept as the one-slot shorthand. After the Qwen3 evaluation (in L34); the owner, 2026-10-21 (decision 4 of `judge-sources-plan.md` section 6): a disagreeing `role: check` replicate adds a consensus note only, under strict as under any profile, no hold; weighed against the literature check of 2026-10-21 (`notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 3): under a unanimity rule a weaker second family cannot lower the quality of agreed labels, only raise the hold rate | *design* (10.1, 10.2, 17); `judge-sources-plan.md` S4 |
| L73 | a high-stakes judgment step cannot demand a direct adapter while routine steps use the project's panel | `module.yml` `harness:` beside `model:`; deferred until a module needs it, since L71's panel covers a project that wants enforced isolation throughout | *design* (module contract via `DEVIATIONS.md`); `judge-sources-plan.md` S6 |
| L82 | the unanimous-but-wrong rate of a judgment module is unmeasured: replicates of one model with one prompt are unanimous on the errors the model makes consistently, and sampling-based detectors miss them (the literature check of 2026-10-21) | in positive controls, report accuracy on unanimous items separately from held items, per module version; the `judgments` and `consensus` tables hold the data; one line on the controls report. The owner, 2026-10-21: not yet, too few runs to measure | engine, low; deferred by the owner; `notes/2026-10-21-1300-judgment-replicates-evidence.md` proposal 1 |

### Engine: delivery, trace and inputs

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L35 | a delivered table carries no trust statement where a person reads it: `present` and the console show the table, and whether its path ran under a verified environment, through dispatch, or through a person's verdict is in `coverage.md` only | `commons-assessment.md` 4.1: `deliver` computes a `provenance` block per `index.json` entry by walking the producing step's ancestors (execution verified or as reported naming the steps; judgment direct, dispatch or none; the holds on the path and their verdicts); `present` prints one pinned word (`checked` or `as reported`) and the review list under each table's title; the console shows the same as a pill; a mixed path takes the lower word | engine, DECISIONS-level; the collapse rule is the owner's |
| L52 | the database does not require the event the Store writes: direct SQL changes state silently (T1 and T2 built, 0.2.25) | T3: a revision bound to one event, triggers on the mutable tables, migration 0007, a hash chain on the event tables with its head in the delivery; needs the DEVIATIONS entry for 9.4 and 9.5 acknowledged | engine; 9.4 and 9.5 via `DEVIATIONS.md`; `trace-integrity-plan.md` T3 |
| L11 | a correction fork should carry its parent's outputs for comparison: the owner asked (2026-10-07) that "whenever a batch correction fork is initiated" the uncorrected UMAPs be delivered beside the corrected ones; a forked step cannot see the parent run's artifacts (job.json carries no `parent_run_id`), so the method does it through a project-level reference input (`uncorrected_batch_evidence`), which only works when the correction is a new project, not a fork | expose the parent run's step outputs to a fork's steps as `$parent.<step>.<output>` bindings (resolved only in a forked run, empty otherwise), so the report step of a correction fork binds the parent's `batch_evidence` without a re-declaration | engine, DECISIONS-level |
| L48 | a person cannot bring a file of their own into an open project after init (a gene-set table for `score-pathways`): the inputs are the delivery's and the upstream's, and `call --in` names only artifacts and declared inputs | a verb that declares an input on an open project (hashed, with a source sentence) and a confirm, or `ask --with <file>` that files it beside the question; the owner, 2026-10-21: deferred until an open project needs a file | *design* (2.3 inputs after init); deferred |
| K3 | a band edge can be impossible for its column (a negative floor on a count) and the engine says nothing | warn when a band edge violates the column's type, if columns ever carry one; today the method clips (open on the method side) | engine, low |
| K4 | `STATUS.md` carries no line for the newest change and `board` has no `--watch` | `notes/2026-09-18-1830-board-and-present.md` | engine, low |
| H5 | staged mode: objective list with stages, `run --objective`, fork at a stage boundary carries an objective, `obj.declared_after_result` | after application 1 as two chained projects shows where option 1 chafes (`spec/archive/declarations-and-objectives.md`); the owner, 2026-10-21: deferred | *design*; deferred |

### Engine: harnesses

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L34 | **one operator harness, one subscription-funded judge route** (as it stood 2026-10-14; the owner: open Codex as a harness and build in as much flexibility on the harness side as possible). H1 to H3 built 2026-10-21 (engine 0.2.32): the survey (`integrations/codex/README.md`), Codex recognised by `operator_id`, `render_skill.py --harness`, the `openai-compatible` and `command` adapters, L36 conformance | what remains: the Qwen3 evaluation (`judge-sources-plan.md` S2) as sibling projects under both harnesses, which needs a local model served on the GPU and the Lyons re-judgment; the owner defines "competent" (decision 3) first; design 10.1 and 10.2 carry the dated text | method and owner; `judge-sources-plan.md` 6 (3) |

### Method and plugin

The Xenium method's own work list is its repository's `PLAN.md` (phases F7 and F9 to F12 of
`spatial-method-plan.md` section 6: the owner's reading of `cell_types_mouse@2`, niches,
descriptives and DE, reports and skills, the retrospective); engine rows it waits on are filed
here as they arise. The bulk RNA-seq plan is dormant since 2026-09-23 and kept in
`archive/bulkrna-plan.md` until the owner reopens it.

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L86 | the Xenium method's `resegment-nextflow` reaches the network (`pre.sh`: `nextflow run`) and declares no egress; under engine 0.2.28 `lint` fails it (L46) | the module declares `egress: {class, hosts, sends}` in `module.yml` when the method moves to `requires.engine >= 0.2.28` (an older engine refuses the key, the intended failure); with the same tag the gates name `judg.numeric_claims_match@2`, `sc.area_join_unverified@2`, `sc.low_cell_count@2` and `sc.decision_unreviewed@2` (plugin 0.8.1) and `requires.plugins` moves to 0.8.1 | method; with the next method tag |

### Skills, documents and onboarding

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L79 | no one other than the developer has run `stringency-analyze-xenium-upstream` end to end; the measurement its design asked for is unwritten | the acceptance run: someone other than the developer runs the synthetic `xenium-upstream` analysis through the skill with limited intervention, measured as a row in `measurements.md`; after the republish of the operator, declare and analysis skills; the owner names the tester | skills; the owner for the tester; `archive/roadmap-2026-10.md` W6 |
| L77 | open mode has no acceptance or baseline: ten questions by a third person against a plain session over a read-only copy of the delivery, graded | `archive/open_mode_plan.md` O5: `evals/liver-questions.yml` with grading notes and tool-computed targets; `integrations/claude-science/open-mode-acceptance.md`; a non-developer's run; the plain-session arm; an LLM grader with deterministic tools for numbers and the binary rubric; both arms side by side in a note and a row in `measurements.md`; after the Xenium skill republish | skills and owner; `archive/open_mode_plan.md` O5 |
| L78 | a session script that recurs across open projects has no route into the method as a tool | `archive/open_mode_plan.md` O6: `answers --export`, `promote`, and `stringency-revise` in the template (with L37); the first promotion of the script that recurs in L77 | engine verb and template; after L77 |
| L37 | the override corpus (design 7.6) is read back as a rate only; the holds' reasons from the Lyons runs are in the store and nothing proposes a prompt, vocabulary or criteria change from them, so 7.6's "a prompt change cites the review ids" has no route and design 17's reason codes have no corpus to emerge from | `commons-assessment.md` 4.4: `review --export [--module]` writes one markdown per resolved hold (YAML frontmatter: hold, kind, predicate, step, item, reviewer, `via`, verdict, reason, bound hashes; the packet below) into `runs/<id>/reviews/` and the delivery; a `stringency-revise` skill in the method-repository template reads them for a module version, groups by theme, proposes changes citing hold ids, classifies new, duplicate, extension or conflict, and waits | engine verb DECISIONS-level; skill in the template, the Xenium method the first user |
| E2 | `STRINGENCY_OPERATOR_VERSION` is `unknown` unless the brief carries `--app-version`; no in-session route to the app's version was found | the next exit run records a version | skill |

### Console

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L74 | the run page has no delivery gallery and there is no decision history page | the report's `figures.csv` with the summary beside it on the run page; a history page of `reviews` joined to `holds` across roots with `status --overrides` per module at the top; when the owner asks | engine (console), DECISIONS-level; `console-and-fleet-plan.md` "What is open" 2 |
| L75 | several runs on one host share nothing: no slots, no queue, no cell on the board saying a step waits | C4, the resource cap: `STRINGENCY_SLOTS`, `capacity.yml`, `slot:waiting` and `slot:acquired` step events, the console cell; `resources_observed` in `executions.observed_params_json` to size it; when the owner asks | engine, DECISIONS-level; `console-and-fleet-plan.md` 6.3 |
| L81 | an open project's questions and answers are on the CLI (`present --answer`) and in `report.md` but not on the console or the board | `archive/open_mode_plan.md` O3: `/questions/<project>`, `/answer/<id>`, `/api/questions`, the `answer_recorded` event; board cells and a sentence for an open project; no form; when the owner asks | engine (console), DECISIONS-level |
| L76 | the console plan's section 10 measurement (hold-to-verdict per ask, relayed holds, session switches) on the lung, gut and spleen traces was never written up | the numbers from the three traces as a note and a row in `measurements.md` | note; low; `console-and-fleet-plan.md` 10 |

### Benchmark

The owner's plan (`benchmark-plan.md`, 2026-10-21, adapted 2026-10-22): show on Latch's
public evals that the gate catches the failures that cost agents the most points and that
holds land where a reviewer's attention is needed. Claude Code with Opus 5 is the harness.

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L87 | no baseline of our own exists on a public benchmark; Latch's Claude Code rows are opus-4-7 and opus-4-8 | Phase 0: `latch login` (the owner), the public evals pulled, `stringency-benchmarks` `latch/run_eval.py` baseline arm three replicates on the six scBench evals then the seventeen SpatialBench evals, tokens and cost and wall-clock per run; a note with the numbers beside the published pattern (10 of 18 on the six) | benchmark; the owner for the login | `benchmark-plan.md` |
| L88 | the six public evals are mapped to engine mechanisms on paper only; no scRNA-seq method exists as a committed pipeline | Phase 1: the mapping table (done 2026-10-22, `benchmark-plan.md`); plugin singlecell 0.8.1 widened beyond Xenium (any observation unit, droplet operation schemas, `analysis_summary`, four droplet predicates, three Xenium predicates narrowed; done); `santangelo-lab/stringency-scrnaseq-scanpy-method` 0.1.0 (eight scanpy modules inside Latch's image, two pipelines with `decision:` blocks, a planted fixture and positive controls; lints clean; done). What remains: the method's skills (`skills/scrnaseq-upstream.yml`, `.analyze.yml`) and a synthetic engine run, the engine running its controls, the Latch conversation (the owner) | method and plan; the owner for Latch | `benchmark-plan.md` |
| L89 | nothing runs a benchmark task through the engine | Phase 2: the adapter (declare, init with a fixed confirm policy, pipeline mode with a fixed hold policy, `answer --cite`, open mode, `answer --cannot`), the method-as-prompt and sham-gate arms, tags frozen; all five arms on the DE and cell-typing evals | engine integration and method | `benchmark-plan.md` |
| L90 | no Claim A or Claim B number | Phase 3: the public-set runs, paired deltas, accuracy among submitted, abstention, hold precision and recall, the failure-mode shift, cost; a note and a `measurements.md` row before any private data | measurement | `benchmark-plan.md` |
| L91 | no Claim C number | Phase 4: the reviewer arm, the owner at `stringency review` with the answer key unseen | the owner | `benchmark-plan.md` |
| L92 | the private sets and Latch's judge are a conversation not had | Phase 5: the Latch ask with the Phase 3 note, the arXiv authors' email, one run on the frozen tags | outreach; the owner | `benchmark-plan.md` |

### Operations, integration and site

| id | item | what closes it | level | reasoning |
|---|---|---|---|---|
| L80 | CI runs lint, the unit tests and the skill check on a bare runner; the synthetic `xenium-upstream` run is not on CI's institutional list and `compat/known-good.yml` is kept current by hand | add the synthetic upstream run to the institutional list; keep `known-good.yml` current with each release (a recurring job named in `docs/release.md`) | integration; `archive/roadmap-2026-10.md` Lane I |
| L53 | the operator runs as the project owner's Unix user and can open or replace `prov/run.db` whatever the Store refuses | T4: a service identity owning `prov/`, the writing verbs through one door, the console unit moved; the PROTECT question | operations; the owner; `trace-integrity-plan.md` T4 |
| L42 | the site rule for `/data/protect` (a project under a path may not declare a ceiling above a site maximum) exists only as a proposal in the archived egress plan | `siteconfig.py` `egress: {max_class_under: {<path>: <class>}}`; `init.egress_exceeds_ceiling` names the rule; the owner, 2026-10-21: not yet (decision 6 of `judge-sources-plan.md` section 6 stays open until a PROTECT project is near) | engine; parked by the owner |

## Waiting on the owner

One table of everything that moves only on the owner's word, so nothing waits in a section
nobody reads. The row id says where the work is filed; "where" says where the text to read is.

| what | row | where | since |
|---|---|---|---|
| when the passes are done (the owner, 2026-10-21: not before): install the engine, restart the console, republish the operator skill (changed for 0.2.28 and 0.2.29), the declare skill and the Xenium analysis skill; plugin singlecell 0.7.0 beside the engine | State | `docs/release.md`, `integrations/claude-science/publish-skills.md` | 2026-10-21 |
| trace integrity: a DEVIATIONS entry for 9.4 and 9.5 (T3), or stay at T2; a service identity for `prov/` (T4). The owner, 2026-10-21: stay at T2, not convinced either is wanted yet; nothing moves until asked | L52, L53 | `trace-integrity-plan.md` | 2026-10-20 |
| the definition of "competent" for the Qwen3 evaluation (decision 3), after the Codex survey (H1); the go-ahead, the login and the sibling-projects shape (decision 2) were given 2026-10-21 | L34 | `judge-sources-plan.md` 6 (3) | 2026-10-21 |
| the tester for the acceptance runs (the owner, 2026-10-21: not yet) | L79, L77 | this file | 2026-10-14 |
| F7: read `cell_types_mouse@2` and the organ guides (decision 17); the owner, 2026-10-21: answered when the Xenium method is the work again | method `PLAN.md` | `spatial-method-plan.md` 8 | 2026-10-07 |
| the console unit: `loginctl enable-linger` once (linger is off, so the console stops at logout); `notify.yml` `page_url` if hold emails should link to the inbox. The owner, 2026-10-21: later | | `console-and-fleet-plan.md` 8.4 | 2026-10-14 |
| the toy method's GitHub remote (`santangelo-lab/stringency-toy-method`, remote `github`): keep it, and is it pushed | | `stringency-toy-method` | 2026-09-18 |

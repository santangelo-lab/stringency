# Decision points: the controls a method puts on an agent's parameter choice

A plan note, written 2026-10-21 from the owner's reading of `omicsbench-assessment.md` 4.2. Not
the spec. The question it answers: nothing today guarantees that the operator tested anything
before proposing a threshold, and the person approving the proposal can accept it blind; what
can the engine, the plugins and a method do about both halves. The owner's framing, which this
note follows: a few of the mechanisms are general and belong in the engine or in lint; the
heavier ones are a menu a method author chooses from per decision point, according to the
stakes of that step, with lint enforcing lightly that some control is declared. Items marked
*design* change design text and need the owner; the rest are DECISIONS-level.

**Status 2026-10-21.** Designed, nothing built. `PLAN.md` rows L61 (the block, its evidence
floor, lint, the default hold view; L9 folded in), L55 (the slots on `propose`), L62 (the
`presented` event), and the menu keys L63 (sweep), L64 (rule), L65 (judged), L66 (sensitivity).
The two choices taken here without the owner are in section 9; one idea the owner declined is in
section 8.

## 1. The problem

OmicsBench's two largest agent-behaviour modes are "arbitrary ambiguity resolution" and "silent
statistical choice" (19.6% and 11.9% of failing runs): a threshold, a method or a subset picked
without validation and never revisited. The engine's answer is the decision point: a parameter
with a committed default and a range, the agent's departure from the default opening a flag hold
(`param.agent_proposed`), the person approving it with a reason, the delivery skill's `hold_view`
putting the elbow table or chart beside the number.

What that does not guarantee:

- that the operator looked at the evidence. The step before produced it, the operator skill's
  section 9 tells the operator to read it and cite it in words, and the reason is free text that
  no predicate reads (design 6.8). The trace cannot tell a reason written from the table from one
  written from habit.
- that the person read it either. On 2026-10-06 one owner met sixteen identical
  `param.agent_proposed` holds across eight projects, relayed one by one, and answered "accept all
  16" (`confirm-once.md` section 1). That is blind acceptance, produced by hold fatigue, in the
  lab that built the engine.
- that a hold shows evidence at all. A method may ship a decision point whose hold is the
  proposal and the reason alone; nothing in lint asks for more.

The two halves pull against each other: more checking means more holds, more holds means less
reading per hold. Everything below makes a hold richer rather than more numerous. One hold per
step carrying every proposed parameter stays as it is.

## 2. The `decision:` block

The parameter block in `pipeline.yml` (design 3.1) already says what the agent may choose from
(`default`, `range` or `options`). The control goes beside it as `decision:`, how it may choose,
because the engine acts on it and `lint` reads the pipeline. The delivery skill's `hold_view` and
the method skill's `decisions` keep carrying the words for people; they stop being the only
places evidence is named.

```yaml
params:
  ndim:
    default: 35
    range: [10, 50]
    decision:
      evidence: 03_reduce/elbow/elbow.csv        # required: a source, a text sentence, or none
      hold: departure                            # departure (default) | always
      sweep: {output: sweep}                     # menu, L63
      rule: {output: knee, tolerance: 5}         # menu, L64
      judged: {module: pick-ndim@0.1.0}          # menu, L65
      sensitivity: {neighbours: 1, through: 05_select_resolution}   # menu, L66
  cluster_method:
    options: [seurat_louvain, igraph_leiden]
    decision: {evidence: none, because: "chosen by object size and wall-clock budget, not by the data"}
  resolution:
    default: 0.8
    range: [0.3, 2.0]
    decision: {evidence: {text: "0.8 is the value ROSC_MTA2 used; source: its methods, section 2"}}
```

| key | meaning | who computes | what the engine does |
|---|---|---|---|
| `evidence` | what a person judges the proposal by: a source in the delivery skill's syntax (`<step>/<output>[/<file>]`, `$inputs.<name>/<file>`), a `text:` sentence when the evidence is provenance or a convention, or `none` with `because:` when the choice rests on something outside the data | the upstream step (exists) | the default hold view renders the source, or prints the sentence, or prints the method's own words for why there is none, before the parameter table; `propose --cite` must point into a source (section 4) |
| `hold` | `departure`: the hold opens when the proposal leaves the default (today's `param.agent_proposed`); `always`: it opens whatever the value, with the value and its source as evidence, which is what the owner asked for on 2026-10-07 (L9) | | `param.agent_proposed@2` reads it; `sc.decision_unreviewed` retires once the Xenium method declares `always` where it wants it |
| `sweep` | the module computed every candidate | the module writes a table with a column named for the parameter | refuses a proposal that is not a row (section 6); shows the table or chart with the pick marked |
| `rule` | the module computed a deterministic pick | the module writes `{value}` | `param.rule_departure@1` flags a proposal further than `tolerance` from it |
| `judged` | the pick is a judgment, not an operator act | a judgment module whose vocabulary is the candidate list | runs it as a step; the parameter takes the consensus, `param_source: judged` |
| `sensitivity` | whether the pick mattered is tested after acceptance | the engine, by forking | forks at the neighbours, runs through the named step, reports at delivery |

`evidence` is the floor; the five other keys are optional and independent. The engine imports no
biology in any of them: the sweep and the rule are the method's code, the engine compares, marks
and records.

Four cases the owner named, each with a home:

- a categorical choice made for reasons outside the data (`cluster_method` by object size; a gene
  set or a communication type by the question asked): `evidence: none` with `because:`. The hold
  prints the method's sentence, so the person is told what kind of choice they are approving.
- a value taken from a convention or a prior analysis ("0.8 because ROSC used 0.8"): `evidence:
  {text: ...}`. The evidence is provenance; the hold shows the sentence and its source.
- compute and plumbing (`max_cells_per_ident`, timeouts, downsampling for speed): not decision
  points; the module's `decision_points` list leaves them out, as `find-markers` already does.
- a first-step threshold with no upstream evidence (`split-punches` `min_transcripts`): the case
  the rule exists to catch. The author adds a sweep output, or the value is declared with the
  person before the run (`objective.yml` `params:`, `how: declared`), or the method says why
  there is nothing to show.

What the hold shows, with the block declared and the delivery skill silent: the evidence (a table
narrowed by `where:` when the skill has one, else whole; a figure; a chart with `mark_param`
when the source is a two-column table and the skill names the axes; the text sentence), then the
parameter table (parameter, default, proposed, source), then the operator's reason with its
citations resolved to the cells (section 4), then the `presented` line (section 5). A delivery
skill entry for the step overrides the view, as today.

## 3. Lint

- A decision point with a `range` or `options` and no `decision:` is the silent case: an error
  once the method's `policy.yml` `requires.engine` names an engine that knows the block, a
  warning before. The Xenium method keeps passing until it opts in by raising `requires`.
- `evidence: none` without `because:` is an error; `because:` on any other evidence is ignored
  with a warning.
- `evidence` naming a source must resolve to an output a step upstream of this one declares, or
  to a project input; `text:` resolves to nothing and is printed as given.
- `sweep.output` and `rule.output` must be outputs of the step's module; `judged.module` a
  judgment module in the repository whose vocabulary is the parameter's `options` or whose items
  are the sweep's rows; `sensitivity.through` a step downstream of this one.
- `decision:` on a parameter that is not in the module's `decision_points` is an error (the
  module says what is a choice; the pipeline says how it is made).
- `render_skill.py --check` requires a method skill `decisions` entry with `how: proposed` to
  name the same evidence the pipeline's block names, or none.

Nothing in lint says which menu key a step should take; that is the author's call about stakes.

## 4. The slots on `propose` (L55)

`propose <step> --set ndim=35 --cite 03_reduce/elbow/elbow.csv:35:cumulative_variance
--considered 30,40 --reason "..."`.

- `--cite <source>[:row[:column]]`, repeatable, as `answer --cite` has; `--considered`, a list of
  the candidates weighed. Reason, citations and the considered set are stored as one message
  (`{text, cited, considered}`) behind `rationale_ref`; no table change.
- `param.agent_proposed@2` resolves the citations into its evidence (`cited`: each ref with the
  cell's value, or "no such cell"; `considered`) and opens its reason sentence with what kind of
  proposal this is: "cites nothing from `elbow.csv`", "cites 2 cells of `elbow.csv`, considered
  30, 40". The hold's first line says it.
- `param.reason_unmatched@1` (pre, `*`, flag under standard, log under exploratory): a numeral in
  the reason matches no cited cell by `judg._numeral_problems`, or the reason carries numerals and
  cites nothing. Rationale stays the object under test, never trusted (design 6.8).
- A decision point whose `decision.evidence` is a source and whose proposal cites nothing in it is
  the same flag with its own sentence; under strict, `param.uncited@1` blocks it. A `text:` or
  `none` evidence asks for no citation.
- The operator skill's section 9 requires the citation and the considered set; the rendered
  analysis skills carry the sentence.

What this proves: the agent opened the right rows and looked at neighbours. What it does not:
that it understood them. The hold makes that visible to the person instead of hiding it, which
is the most the engine can do between "had to read" and "had to understand".

## 5. The `presented` event (L62)

`present` reads and writes nothing today. One `run_events` row `presented` (the source rendered,
the hold if any, the OS user, the operator session ref) written whenever `present` or
`present --hold` renders a step's output or a hold. The parameter hold's packet and page gain
one line: "evidence rendered 10:42 by the operator session, proposed 10:44", or "proposed; no
evidence of this step rendered in this run". Rendering is not reading, and the operator can
render without looking; the absence is what the line is for. One event, one line, no predicate.

## 6. The menu keys

**Sweep (L63).** For a decision point whose evidence can be computed for every candidate at
acceptable cost: cells retained per threshold per punch, clusters and stability per resolution,
cumulative variance per component. The module declares an output table with a column named for
the parameter and one row per candidate; the proposal must name a row. `param.not_in_sweep@1`
(pre, block) refuses one that does not; the hold shows the table, or the chart when the delivery
skill names axes, with the pick marked (`mark_param` exists). The clustering resolution grid
(`cluster-umap` 0.4.0, eight resolutions, `select-resolution` after it) is this pattern already,
and the owner's note on cost stands: it does not scale to alignment-sized steps, and it is the
author's choice per step. Tests: a proposal on a row passes, off a row blocks, a sweep table
without the parameter's column fails lint.

**Rule (L64).** For a decision point with a deterministic heuristic (the knee of the elbow, the
resolution where the clustree stops splitting, a retained-cells floor). The module computes it and
writes `{value}`; `param.rule_departure@1` (pre, flag) fires when the proposal is further than
`tolerance` from it, evidence carrying both numbers, so the hold reads "rule says 32, the
operator proposes 35". The agent becomes the tiebreaker, not the chooser (Commandment 6). The
owner's reading: this answers "picked for the wrong reasons" more than "picked without
validation", and is too rigid to pursue on its own; it stays on the menu with no date.

**Judged (L65).** For the decision points with the most subjectivity and the highest stakes. A
judgment module whose vocabulary is the candidate list (or whose items are the sweep's rows)
reads the evidence in three fresh contexts and returns a pick with cited cells, a confidence,
abstention allowed; every `judg.*` predicate applies, disagreement is a hold, consensus is never a
majority vote. The parameter takes the consensus value with `param_source: judged`, the
operator's in-session proposal replaced by samples that never saw the conversation. Engine: a
parameter bound to a judgment step's consensus (design 5 additive; 3.1). Cost: three calls per
decision point and a module per decision point; the author chooses where. An open question for
the controls machinery before committing a method to it: whether three delegates reading an
elbow table pick better than one operator who saw the run, or return three copies of one prior;
the synthetic upstream run can measure it.

**Sensitivity (L66).** For a decision point where the question is whether the pick mattered.
After the person accepts, the engine forks at the `neighbours` candidates on each side, runs
through the step named by `through`, and the delivery says what moved ("at 0.4 and 0.8 the
annotation agreed on 11 and 12 of 14 clusters"). A control kind (design 11), reported in
`coverage.md` and the summary, never blocking; refused under strict unless the profile declares
it. Compute-heavy; the author declares it on the few steps that need that much scrutiny.

## 7. Fewer holds

The sixteen holds of 2026-10-06 were eight projects times two steps, one hold per step, so there
is no per-parameter splitting to fix; the fix is L6, batch review of identical flag holds with
accept-once, already filed. The `decision:` block gives L6 a natural batching key (same step,
same evidence source, same proposal). The owner's rule: fewer nuisance holds is good, but the
balance between independence and a person in the loop needs test-run feedback before anything
beyond L6 is built.

## 8. Not pursued

- **The default beside the proposal as a verdict.** A flag hold takes accept or reject only;
  override is item-only (`review.py`), and in pipeline mode nothing lets a person put a value in
  (`param_source: person` exists but only open mode's `call` sets it). Offering the default as a
  choice would be a 7.1 and 7.3 change: override on a parameter flag with a correction validated
  against the range, the attempt closed, the engine proposing the next attempt itself with
  `param_source: person`. The owner, 2026-10-21: bigger than it looks, not worth the effort now.
  Recorded here so it is not rediscovered.
- **Acceptance latency and reason length printed in the delivery.** The owner: patronising in a
  lab where the reviewer is the owner. Not built; the trace holds the timestamps if a reader
  wants them.

## 9. Choices taken here (say if otherwise)

The owner, 2026-10-21: both accepted as written.

- Lint grandfathers a method until its `requires.engine` names the engine that knows `decision:`
  (warning before, error after). Reason: the Xenium method has six decision points and must keep
  passing while it declares them.
- `hold` defaults to `departure`. Reason: it is today's behaviour; `always` is the method
  author's statement that a default needs a signature too.
- One hold per step carrying every proposed parameter stays; the block does not split it.

## 10. What it does not guarantee

Reading is not understanding. The slots prove the right rows were opened; the `presented` line
proves the evidence was rendered; neither proves the operator reasoned from it, and no mechanism
here can. The sweep and the judged pick move the choosing out of the operator's session, which is
the only way to close that gap, at a cost the author pays per step.

## 11. Design amendment text for the owner

For one sitting, each applied only with its build:

1. **3.1 pipeline.yml** (L61). Add after the `range` paragraph: "A parameter the agent may
   choose may carry `decision:`, how the choice is made: `evidence` (a source as the delivery
   skill names them, a `text:` sentence, or `none` with `because:`), `hold: departure | always`,
   and optionally `sweep`, `rule`, `judged` or `sensitivity`. `lint` refuses a decision point
   with neither evidence nor a stated reason for having none, once the method requires an engine
   that knows the block. The hold shows the evidence before the number."
2. **14.1 Verbs** (L55). `propose` row gains `[--cite <source>[:row[:column]]]... [--considered
   <values>]`.
3. **5 Actions** (L65). `param_source` gains `judged`: a value a judgment step's consensus
   decided.
4. **6.5 Engine predicates.** Rows for `param.agent_proposed@2`, `param.reason_unmatched@1`,
   `param.uncited@1`, `param.not_in_sweep@1`, `param.rule_departure@1`.
5. **11 Controls** (L66). A control kind `sensitivity` run after acceptance at a declared
   decision point, reported and never blocking.

## 12. Order and tests

| row | depends on | estimate | tests |
|---|---|---|---|
| L61 block, lint, default hold view, `hold: always` | nothing | one session | lint: silent case warns then errors by `requires`; `none` without `because` errors; an unresolvable source errors; `decision:` on a non-decision-point errors. Hold view: a source rendered with the skill silent; a `text:` sentence printed; `none` printed as the method's words. `param.agent_proposed@2` with `hold: always` fires at the default and carries the source |
| L55 slots | L61 | one session | a cited cell resolved into the hold's evidence; a reason numeral off the cited cells flags; a source decision point proposed without a citation flags (blocks under strict); `text:` evidence asks for nothing; the skill text |
| L62 `presented` | nothing | half a session | the event written by `present` and `present --hold`; the hold line in both states |
| L63 sweep | L61 | half a session plus a method step | on-row passes, off-row blocks, the chart marked |
| L65 judged | L61 | one session plus a module | consensus bound to the parameter with source `judged`; disagreement holds; `judg.*` on the pick |
| L66 sensitivity | L61, forks | one session | two forks after acceptance, the delivery line, nothing blocked |
| L64 rule | L61 | half a session | departure flags with both numbers; within tolerance passes |

The Xenium method's side: declare `decision:` on `ndim`, `resolution`, `method`, `scale_factor`,
`integration` and `cluster_method`, raise `requires.engine`, and re-render the skills. After the
first run under it, the measurement row says how many parameter holds opened, how many cited,
and how many a person accepted with the operator's words.

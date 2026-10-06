# Data egress classes and judgment re-measurement

A plan note, drafted 2026-09-23 evening after reading ClawBio (`github.com/ClawBio/ClawBio`,
`v0.7.1`, HEAD `8a09183`). Not the spec. Two mechanisms are worth borrowing; the rest of that
project is assessed in `judge-sources-plan.md` section 9 and not integrated. Items marked
*design* change design text and need the owner's approval; the module-contract field in part 1
goes through `DEVIATIONS.md`; the rest is DECISIONS-level. Neither part is scheduled; both are
recorded here so they can be built when a lane needs them. Backlog rows L1 to L4 point here.

The line that justifies both, from ClawBio's `tests/test_data_handling_doc.py`: "A prose promise
that networked skills are individually labelled governs nothing." Both mechanisms turn a
statement the design already makes into something the engine checks and the trace records.

## Part 1: data egress classes

### What ClawBio does

`docs/data-handling.md` classifies every skill by what leaves the machine, in five classes from
least to most sensitive: (1) nothing of yours, the skill downloads public reference data;
(2) the query terms you typed; (3) values derived from your data (their case: variants, which
identify a person on their own); (4) whole files uploaded to a hosted service or model; (5) chat,
photos and voice to a hosted language model. Each networked skill has a row naming the hosts,
exactly what is sent, when, and whether demo mode is offline. The page was written by reading
code. A pytest scans every skill's source for outbound-call patterns (`requests`, `urlopen`,
`httpx`, `curl`, `wget`, `nextflow run`, OpenAI and hosted-model clients, `from_pretrained`,
`hf_hub_download`) and for declared `http` endpoints, and fails CI when a networked skill is
absent from the page. The list cannot fall behind the code.

### Where stringency stands

Design 10.1's principle "the model sees the table, never the matrix" is an egress statement,
and the trace records `via` and `isolation` per invocation, but nothing declares or checks what
leaves the machine. Three egress points exist:

| point | what leaves | where to |
|---|---|---|
| judgment harness | the full rendered prompt: evidence tables, vocabulary, objective, design | `subagent`: the operator's hosted model via Claude Science; `api`: Anthropic; `openai-compatible` (planned): wherever `base_url` points; `mock`: nowhere |
| module scripts | whatever the script sends: reference downloads, web-service queries with gene lists, uploads | declared nowhere; `lint` does not look |
| operator runner | the evidence the operator reads into its own context to submit a step | the operator's hosted model, for a Claude Science or Claude Code session |

`judge-sources-plan.md` section 5 proposed refusing `subagent` and `api` for projects under
`/data/protect`. That is a path check on one of the three points. The mechanism below replaces
it with a declared, versioned policy over all three.

### The classes, for stringency

| class | meaning | examples |
|---|---|---|
| 0 `none` | no network | `mock`; a module script that reads and writes local files |
| 1 `reference` | public reference data downloaded; nothing derived from project data sent | a module fetching an annotation release (which `/lab/ref` pinning should make rare) |
| 2 `terms` | identifiers or names from the project sent as queries | a gene list to an enrichment service; a vocabulary label to an ontology lookup |
| 3 `derived` | values computed from project data sent | an evidence table in a judgment prompt to a hosted model; per-sample metrics to a web tool |
| 4 `data` | project inputs or outputs sent whole | an `h5ad` uploaded to a hosted service; the operator runner reading a raw table into a hosted session |

A judgment prompt is class 3 by construction: it carries evidence tables, never the matrix.
That is the design's protection and also its ceiling; a hosted judge is never below class 3.

### Mechanism

1. **Harness adapters declare their class.** A `egress` attribute on each adapter: `mock` 0,
   `api` 3, `subagent` 3, `openai-compatible` 0 when `base_url` resolves to loopback or a host
   the project names as local, 3 otherwise. Recorded per invocation in `invocations.extra` or a
   new `egress_class` column (additive, DECISIONS-level under the trace schema).
2. **Modules declare theirs.** `module.yml` gains `egress: {class: <0-4>, hosts: [...],
   sends: "<one sentence>"}`. The module contract is frozen, so this is a `DEVIATIONS.md` entry
   with the owner's acknowledgement. Default when absent: class 0, and lint enforces it (next
   item).
3. **Lint scans scripts.** `stringency lint` gains a scan of every module script and `pre.*` /
   `post.*` with a pattern list modelled on ClawBio's (Python, R and shell: `requests`,
   `urlopen`, `httpx`, `httr::`, `download.file(`, `curl`, `wget`, `nextflow run`, model-hub
   downloads, LLM clients). A module whose code matches and declares class 0, or declares no
   `egress`, fails lint: "module X reaches the network but declares no egress". A module that
   declares a class above 0 without a match gets a warning, not a failure. The scanner is
   conservative on purpose; a false positive costs one declaration line.
4. **The operator runner is class 4, as reported.** A `runner: operator` step records
   `egress_class: 4` with `isolation: as_reported`, because the engine cannot see what the
   operator read. The skill text already says what the operator may read; this makes the trace
   say what it did.
5. **Policy sets the ceiling.** `method/policy.yml` gains `egress: {max_class: <0-4>}`. A
   run-open predicate `prov.egress_exceeds_policy` (block, invariant) compares the bound harness,
   every in-scope module and the project's `execution` setting against it. A PROTECT project's
   policy sets `max_class: 1`; a general lab project leaves it at 4. Because the policy is
   versioned in the method repo, the ceiling is part of the method, not a property of a path.
   The path-based rule from `judge-sources-plan.md` section 5 becomes a lint warning when a
   project under `/data/protect` binds a policy with `max_class` above 1, so the two never
   disagree silently.
6. **The coverage report says what left.** Design 12.2's report gains a paragraph, "Data
   egress", listing every component that sent data off the machine on this run: harness kind
   and class, each module with a class above 0 and its `sends` sentence, and the operator runner
   steps as class 4 as reported. This is the institution-facing contract, per run, in the trace.
   `summary.md` gets one line: the highest class reached.

### Order

Items 1, 4 and 6 are engine-only and additive: one session. Item 3 is one session with tests on
fixture modules that do and do not reach the network. Items 2 and 5 need the owner (DEVIATIONS
and a policy field). Build before the first PROTECT project is initialised, and before the
`openai-compatible` adapter ships if it ships first, so the loopback rule exists from its first
run.

## Part 2: judgment re-measurement endpoints

### What ClawBio does

`docs/skill-lifecycle.md` treats the knowledge inside a skill as a wasting asset and the contract
around it (what it refuses, what it records, whether it gives the same answer twice) as what
lasts. On every frontier model release the benchmarked skills are re-run against a no-skill agent
on the same cases, three replicates, hashed case identifiers, and scored on four endpoints:
accuracy on well-formed inputs; over-answer rate on ill-formed inputs (missing data, an
unreported locus, negation, contradiction); abstention stability across identical runs; and
provenance completeness and re-runnability from inputs alone. Half of every perturbation suite is
held back unpublished. The decision rules were written before any measurement so they cannot be
fitted to it.

### Where stringency stands

Design 11 has three control kinds: `negative` (permuted or shuffled input; every item must
abstain or nothing is flagged), `positive` (known truth; `agreement_min`, `abstain_max`) and
`planted` (spiked effect; `detect_at`, `false_positive_max`). Together they cover accuracy on
well-formed inputs and the shuffled half of over-answering. The engine runs three replicates per
judgment and stores every one. What is missing:

- **Ill-formed evidence as a control.** The engine's own harness tests have the idea
  (`tests/fixtures/harness/context_contradicting.yml`, `bad_number.yml`), but a method cannot
  declare a control whose fixture is a damaged evidence table and whose expectation is abstention.
- **Abstention stability as a number.** With three replicates it is computable from the
  `judgments` table today: the share of items where replicates split between a label and
  abstain. Nothing prints it. `any_low` option B (2026-09-23) logs low confidence on an agreed
  label; this is the same family of signal, aggregated.
- **Controls keyed to the judge.** The coverage report prints control outcomes per module
  version and date (`annotate-cluster@0.3.1  2026-09-12  negative-...`). It does not record which
  judge answered. A control that passed under one model says little about another.
- **The baseline comparison.** ClawBio's "no-skill agent" is, for judgment modules, a different
  judge on the same cases. That is the Qwen3 evaluation in `judge-sources-plan.md` S2.

### Mechanism

1. **Control kind `ill_formed`** [*design*: amends design 11]. Fixture: a well-formed input plus
   a generator that damages the evidence in a declared way. Generator tools, plugin half (15.1),
   each with a `seed`: `drop_column` (remove a declared evidence column), `blank_items` (set one
   or more items' metrics to NA), `negate_objective` (invert the objective's question text),
   `contradict_reference` (a secondary evidence table whose rows disagree with the primary).
   Expectation: `abstain_min` (default 1.0 for the damaged items) and `over_answer_max` (labels
   given with `high` confidence on damaged items, default 0). Result fields:
   `over_answer_rate`, per generator. Runs through the same single-module control machinery as
   the other kinds, `mock` refused.
2. **`abstain_stability` in the coverage report** [engine, DECISIONS-level]. Per judgment step:
   items where every valid replicate agreed on abstain-or-label divided by items judged;
   printed beside the existing agreement figure in 12.2 and stored in the control result when
   the step is a control. One SQL query over `judgments`; no schema change.
3. **Judge identity on control results** [engine, DECISIONS-level]. `control_results` (or the
   run's `delta_json` for control runs) records `harness_kind` and the set of `model_resolved`
   values that answered. The coverage report's control line gains the judge:
   `negative-...: null  (judge claude-opus-5 via subagent)`. Lint warns when the current
   project's bound harness and model differ from those on the module's most recent passing
   controls: "controls for X last passed under Y; this project judges with Z". A warning, not a
   block: the compensating action is `stringency controls run` under the new judge.
4. **Rules before measurement.** The competence definition in `judge-sources-plan.md` S2 is
   committed before the evaluation runs; this note records that as the rule for every judge or
   module comparison: the pass criteria and the endpoints are written into the plan and committed
   before the first run whose results they judge. Over-answer rate and abstention stability join
   S2's endpoint list.
5. **Held-back perturbations** [optional]. Half of each `ill_formed` generator's seeds are listed
   in the method repo but their fixtures are generated only at control time and never committed,
   so a future judge cannot have seen them. Cheap because the generators are seeded; recorded
   here as an option, not proposed for the pilot.

### Order

Item 2 first: half a session, no decision needed, and it produces a number for the Lyons outlier
runs already in the store. Item 3 next: one session. Item 1 needs the design amendment and a
plugin tool per generator: one session for the engine kind, one per plugin for the tools; the
singlecell plugin's `drop_column` and `blank_items` are the first two, in time for Lane F's
annotation judgment (the first downstream judgment, "with controls first" in its plan). Item 4 is
a sentence in the S2 plan and in `commandments.md`'s gloss on 7 if the owner agrees.

## Not borrowed

ClawBio's per-run `reproducibility/` folder (`commands.sh`, `environment.yml`, checksums) is
weaker than `run.db`; its DOI-bearing benchmark card is heavier than a lab needs; its retirement
process has no counterpart here. Its `SKILL.md` format is the Agent Skills spec that Lane E's
rendered analysis skills already follow, so publishing there later costs nothing and needs no
work now.

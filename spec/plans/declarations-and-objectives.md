# Declarations drafted by an agent, and objectives that arrive later

A design note, written 2026-09-09 after the improvements backlog and before application 1. Not
the spec: a proposal for changes to design 2.3 through 2.7, 2.6, 14.1, and 17, and for the order
in which to build them. Two questions from the same conversation:

1. A person describes an experiment in sentences and points at a sample manifest. Can the
   operator agent turn that into `inputs.yml`, `design.yml`, `objective.yml` reliably, and what
   must the engine record so the result is still the person's declaration and not the agent's?
2. Rich datasets are processed once and asked several questions later. Pipeline mode binds one
   objective at `init`. How do objectives get added without giving up pre-specification?

Nothing here reshapes a frozen contract. Items marked *design* change design text and need Jim's
approval; the rest are DECISIONS-level.

## Part 1: declarations drafted by an agent

### What the design already says

Design 2.7 calls `init` "where the agent's reading of the experiment becomes the declarations
every later gate trusts" and gives it three layers of checking (schema, the `init.*`
compatibility predicates, the echo-back with its confirm hold) because "these are the errors an
agent makes when it misreads a prose description." So agent-drafted declarations are anticipated.
What is missing is the drafting side: no skill says how to get from sentences and a manifest to
three valid files, `init` is the only place the checks run and it leaves a half-created project
behind when they fail, and the trace does not say who authored the declarations.

### The rule

The skill translates; it does not decide. Every field in the three files is one of: something
the person said, something read from the data or the manifest, or a plugin default. The skill may
not invent a factor, a level, a contrast, a deliverable, or a replication unit. Where the text is
ambiguous ("compare A, B, and C": three pairwise contrasts or one omnibus test) the skill asks;
it does not pick. This is the same line the rest of the design holds: the model routes and
phrases, it does not make the analysis choices.

### Sources, in order of authority

1. **The sample manifest.** One row per sample, columns for factors and technical variables. It
   fills `units`, the `factors` with their `column` and `levels`, and candidates for `batch`. The
   skill shows the person which columns it read as biology and which as technical and asks for
   confirmation; it does not guess which is which from column names alone.
2. **Sample names, when there is no manifest.** The skill proposes a parse of the names into
   columns ("treatment_rep1" into `treatment`, `replicate`), writes the parsed table to disk, and
   the person confirms it. The parsed table becomes an input item in `inputs.yml` in its own
   right, so the mapping from names to factors is in the trace and not in the agent's head.
3. **The person's sentences.** They supply the question, the contrasts, the replication unit
   when the manifest does not make it obvious, `min_n_per_group`, and the deliverables. The
   skill maps the question to the plugin's vocabulary and refuses to proceed when no entry fits;
   that is a plugin gap, not something to paper over.
4. **Plugin defaults.** For fields the person did not mention and the data does not settle, the
   plugin's default applies and the skill says so in its summary.

### Engine change: `declare --check`

A verb that runs every check `init` runs, against a directory holding the three files and
without creating a project:

```
stringency declare --check <dir> --method <git-url>@<tag> --pipeline <name>
```

It validates the envelopes and the plugin's design schema, hashes every input and compares with
the declared `blake3`, runs one extractor pass per object input to confirm the design columns
exist, evaluates every `init.*` predicate against the declarations and the named pipeline, and
prints the echo-back. Exit 0 with the echo-back, or exit 15 naming the first field or predicate
that failed. `--json` carries the same. The skill loops on this until it is clean and then shows
the echo-back to the person before running `init`. `init` itself is unchanged; `declare --check`
is the same code path stopped before the project record is written. Design 14.1 gains the verb
(*design*, additive).

### Engine change: record who drafted, and what they were given

- `stringency.yml` gains `declarations: {drafted_by: person | agent, harness, session_ref,
  brief}`. `init --drafted-by agent` sets it, with the harness and session reference read from
  the `STRINGENCY_OPERATOR*` variables. Default `person`. Same distinction `proposed_by` makes for
  actions (design 5).
- `init --brief <file>` copies the person's own words, verbatim, to `<project>/brief.md`, and the
  confirm hold's context carries its hash beside the three declaration hashes. The echo-back
  then closes a loop the reader can check: what the person said, what the agent wrote, what the
  engine read back. Editing the brief after acceptance does not reopen the hold; the brief is
  context, the declarations are the binding.
- The `projects` row gains nothing; both facts live in `stringency.yml`, which the row already
  stores as `config_json`. If a cross-project query ever needs `drafted_by` as a column, 9.4 gains
  one then.

### The skill

`integrations/claude-science/stringency-declare/SKILL.md`, domain-agnostic in shape and
domain-bound in content (it needs the plugin's question vocabulary, object types, and design
schema, which `plugins list --json` should expose). Its steps: read the brief and the manifest;
draft the three files under `<project parent>/declarations/`; run `declare --check`; fix or ask;
present the echo-back in the conversation; on the person's yes, run `init --drafted-by agent
--brief <brief>`; report the confirm hold and stop. It never accepts the hold (rule 1 of the
operator skill applies). It never writes a value it cannot point at in the brief, the manifest,
or the plugin defaults, and its summary to the person lists each field with its source.

### Design text (*design*)

2.7 gains a paragraph: declarations may be drafted by an agent from the person's brief and the
sample manifest; `stringency.yml` records `drafted_by` and the brief is kept beside the
declarations; the echo-back and the confirm hold are what make the result the person's
declaration. 14.1 gains `declare --check` and the two `init` flags.

## Part 2: objectives that arrive later

### The tension

Commandment 1 and design 2.5 bind one objective at `init` so the plan is pre-specified. Real
datasets are processed once (QC, normalisation, clustering, annotation) and then asked several
questions, some not known on day one. Forcing every question into the first objective produces
either a vague objective or a project per question with the processing repeated. Design 17
reserves `staged` and `open` modes, `splits`, and `budgets` for this, with the trigger "the
exploratory surface between clustering and niche characterisation is real." Application 1 is
that surface.

The statistical hazard is not having several questions. It is choosing a question after seeing
outcome-relevant results, and tuning shared processing so that a downstream contrast comes out.
Every option below is judged by whether the trace can say, for each objective, what results
existed when it was declared, and whether the processing it depends on could have been tuned
against it.

### Option 1, now: a processing objective and chained projects

No engine change beyond one field. The upstream project's objective has a processing question
(for the toy, nothing to add; for single-cell, a `processed_object` question in the plugin
vocabulary) with no contrasts and deliverables such as the clustered, annotated object and a QC
report. `obj.feasibility` has no contrast to walk and checks sample counts only. Each downstream
question is its own project whose `inputs.yml` names an upstream deliverable by path and hash.
Cell-type labels reviewed upstream arrive downstream as data, already signed off, and their
review bindings are in the upstream trace.

One addition makes the chain explicit: an input item may carry `derived_from: {run_id,
step_id, output}` (built 2026-09-09 with those keys, since the sidecar carries step and output
name but not the artifact id). `init` reads the sidecar beside the file, checks that it names that run and that
its hash equals the declared `blake3`, and refuses otherwise. The `captures` event at run open
records the upstream run ids, and the methods paragraph says "inputs derived from run X." This
is the whole of the engine work for option 1 (DECISIONS-level; 2.3 gains an optional field).

Cost: design and inputs are re-declared per question, and three questions on one dataset are
three project directories with three traces. Virtue: every objective is frozen before its own
run starts, so the confirmatory claim is intact per question, and nothing about pipeline mode
changes. The `declare` skill makes the repetition cheap: the same manifest and a shorter brief.

Do this first, on application 1, as two projects: processing through annotation, then
differential expression. Where it chafes is the input to defining staged mode.

### Option 2, when the seams are felt: staged mode

One project, one design, one inputs manifest. The pipeline groups its steps into named stages,
the first being shared processing. `objective.yml` becomes a list; each entry has an `id`, a
`question`, contrasts, deliverables, and the `stage` it attaches to. Adding a question later is
a commit to that file: its digest changes, a confirm hold opens for the new entry only (bound to
that entry's hash, so earlier entries do not re-ask), and the trace records when the entry was
declared.

Runs are per objective: `run --objective <id>`. An objective's run forks from the completed
processing run at the stage boundary, inheriting every completed upstream step by hash; the
fork machinery of 2.6 already does the inheritance. Design 2.6's rule that forks may not change
the objective is relaxed in one way: a fork at a stage boundary may carry a different objective
from the list. Upstream steps are frozen once any objective has run against them; re-tuning
clustering for a question means a fork upstream, visible as a parent chain. A new objective may
only name factors and levels the design declares and a question the downstream stage's pipeline
answers; `init.contrast_undeclared`, `init.level_undeclared`, and `init.question_unsupported`
run again at the moment the entry is added, against the stage rather than the whole pipeline.

Design text: 2.5 (objective list with `stage`), 2.6 (fork at a stage boundary may carry an
objective), 3.1 (stages in `pipeline.yml`), 14.1 (`run --objective`, `objective add`), and the
`mode` field's `staged` value stops being reserved. All *design*.

### Option 3, part of option 2 from the start: what was visible when the question was asked

Objective entries and artifacts both carry timestamps and hashes, so the trace can state, per
objective, which deliverables existed when it was declared. The coverage report and methods
paragraph then carry one of three labels per objective:

- declared at init, before any run;
- declared after the processing stage completed and before any downstream step ran;
- declared after a result on the same factor existed (naming the run and step).

The third is not forbidden; it is labelled. Profiles set the line: `exploratory` allows it with
a flag, `standard` allows it with the label, `strict` refuses an objective declared after any
result on its own factor exists. One predicate, `obj.declared_after_result`, phase run open,
scope `*`, default flag, remapped by profile as above. Cheap, and it is the honest core of
staged mode; option 2 without it is "add questions whenever."

### Option 4, reserved: splits for confirmatory claims under strict

The `splits` column exists for this. At design time a subset of blocks or samples is held out.
Exploratory objectives run on the exploration split; a confirmatory objective added later runs
on the holdout, and the engine refuses to run it on data any exploratory run touched. This is the
only option that supports a true confirmatory claim for a question not held at the start. It
costs samples and machinery. Build it when someone needs that claim; until then `strict` simply
refuses late objectives (option 3).

### Option 5, cheap and independent: the question space in the design

`design.yml` gains `intended_questions: [<question names>]` and optionally `intended_factors`.
A later objective inside that space is ordinary; one outside it is flagged as exploratory
(`obj.question_unintended`, flag). It encodes that a TMA was built to compare regions even when
the exact contrast was not written down, and it gives the `declare` skill a list to check the
person's sentences against. Settle the field with the single-cell design schema in app-1
session 1. *design* (2.4).

### What not to do

- Do not let pipeline mode accept objective changes on an open project. That quietly removes the
  pre-specification pipeline mode promises; staged mode is where late objectives live, labelled.
- Do not make the processing objective deliverable-free. `deliver` insisting on named outputs is
  what makes the processing run reviewable and reusable rather than an intermediate nobody signed
  off on.

## Order of work

1. `declare --check`, `init --drafted-by --brief`, `derived_from` on input items, with tests on
   the toy (a two-project chain: toy processing to `02_summarize`, then labelling and comparison
   as a downstream project bound to the delivered table). DECISIONS lines; 2.3, 2.7, 14.1 text.
2. The `stringency-declare` skill, iterated on the toy from a written brief and a manifest.
3. The PROTSEQ exit run exercises both. It starts from a brief in Jim's words and a sample
   manifest for the toy data, not from hand-written declarations: the agent drafts, runs
   `declare --check`, shows the echo-back, Jim accepts at a terminal. Then the run proceeds as
   before, as two chained projects (processing, then labelling and comparison) so `derived_from`
   is exercised too. What to record afterwards: how many turns the drafting took, which fields
   the skill had to ask about, whether any field in the accepted declarations lacks a source in
   the brief or the manifest, and whether `drafted_by: agent` and the brief hash are in the trace.
4. Application 1 as two chained projects under option 1. Write down where it chafes.
5. Staged mode (options 2 and 3) as one design amendment, then build; option 5 with the
   single-cell design schema; option 4 on its trigger.

Status 2026-09-22: items 1 to 3 done (2026-09-09 and 2026-09-14). Item 4 was exceeded: Lyons CLP
ran as fourteen projects chained through `derived_from` (resegmentation to QC to cross-region
summary to outlier judgment), and no objective arrived after a result. Where option 1 chafed was
not the objective but the project boundary: every chained project restated one design and opened
its own confirm hold (roadmap Lane A item 5b, inherited confirmation), and `init.column_missing`
read design columns against chained and reference inputs until it was taught not to (DECISIONS
2026-09-18 and 2026-09-21). H5 stays open with no trigger yet.

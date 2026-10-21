Archived 2026-10-21: built (engine 0.2.22 to 0.2.27: S1 to S7, O1, O2 as the owner's drives, O4 as the Xenium method's tools). O3, O5 and O6 are `spec/plans/PLAN.md` rows L81, L77 and L78. The code and its tests cite this file's sections by number. Not an instruction to a session.

# Open mode: interactive downstream analysis on a delivered dataset

**Status 2026-10-16, evening.** Approved by the owner 2026-10-16 (plan mode, this engine
checkout; `notes/2026-10-16-1330-open-mode-plan.md`). S1 to S7 built the same day on branch
`open-mode` (engine 0.2.22, not tagged, not merged; `notes/2026-10-16-2200-open-mode-s1-s7.md`):
every engine change of section 2, the toy's tools and controls of section 4, the six predicates,
the trace tables, and the design amendments of section 6 applied to `spec/stringency-design.md`
for the owner's reading at merge. Open: O1 to O6 (the skill text, the toy rehearsal, the console,
the Xenium tools, the acceptance run, the promotion loop) and the owner's merge. Lane K in
`roadmap-2026-10.md`.

## Context

Stringency's pipeline mode takes raw data to a reliable, processed dataset: a declared
topology, gates before every action, replicated judgment with holds, an append-only trace.
It has done this for the Lyons CLP Xenium data (QC, upstream, annotation). The second half of a
computational biologist's work, deriving insight from that dataset, is non-linear and cannot be
declared in advance, and a fixed topology would fight it.

The owner's proposal (2026-10-16), after reading `posit-dev/commons`
(`spec/plans/commons-assessment.md`): keep pipeline mode for the upstream half, and add a
second mode that looks like commons for the downstream half. Once a pipeline has delivered,
the agent that operated it switches to answering a person's questions interactively. Answers
rest on **trusted tools** shipped with the method (differential expression with limma-voom or
DESeq2; a volcano plot; the common downstream applications of that kind of dataset), each a
tested, containerised piece of code; or on **model-written code**, which the engine runs and
records but labels **untested**. The person sees which is which beside every answer, as
commons' marker does. The design reserved this as "open mode" (design 5 L422: "the agent
proposes the operation as well as the parameters, using the same record"; design 17), and
design 17's own trigger for it ("app 1 runs end to end in pipeline mode and the exploratory
surface is real") is now met. Nothing of it was built: `config.py:73-79` and
`project.py:500-503` refuse any mode but pipeline.

This plan says what open mode is, what it reuses, what it adds, and in what order. It was
drafted from three explorations of the code and three design passes (engine, person and
author, rigor), and the owner's answers below.

## The owner's decisions (2026-10-16)

1. Model-written code runs **under the engine's executor** (a new `exec` verb), not in the
   operator's own sandbox. This is also the answer to backlog G2.
2. The first real target after the toy is **Lyons CLP Xenium**: the downstream phases the
   spatial plan wrote as pipeline steps (composition, pseudobulk limma-voom DE, pathway
   scores, figures) become tools; the R code exists in the ROSC archive.
3. The operator's reply text is **gated**: every numeral must match a cell of a cited
   artifact before the answer is recorded.
4. The switch is **one relayed yes**: the open project opens a confirm hold whose echo is one
   pinned paragraph; the operator says it and relays the person's yes with `--attest`. No
   inherited confirmation for open projects.
5. Delivery from an open run **never stops for a sign-off**: the rerun counts and the labels
   are the record.

## Decisions taken in this plan (DECISIONS-level; say so if any should change)

- An open analysis is a **separate project** with `mode: open`, inputs `derived_from` the
  upstream delivery, created by `init --mode open --from-delivery <dir>` beside the upstream
  as `<upstream>-questions`. Design 2.2 binds mode at init, so a second run in the same
  project is not an option.
- A **tool is a module** (`spec/module-contract.md`, frozen, unchanged) that lists `open` in
  its `modes` (`src/stringency/modules.py:88`, already a field). Kinds stay
  `deterministic | judgment | report`. The words a tool needs for the person (title, use
  when, which parameters the person settles) live in the method's **skill files**, not in
  `module.yml`, so the frozen contract is untouched.
- **An open run is an ordinary run whose topology grows one step at a time.** A tool run or
  an `exec` creates a `steps` row and a synthetic `StepDecl` at proposal; `RunContext` hands
  the gate a `Pipeline` of the on-demand steps so far. Every existing predicate, `plan_step`,
  `build_action`, `job_for`, `execute_engine`, `finish`, holds, review packets, `wait`,
  artifacts and sidecars work unchanged. Tools are always engine-run.
- Verbs: `tools list`, `ask`, `call <tool>`, `exec`, `answer`, `deliver --answer`,
  `present --answer`, `init --from-delivery`. `run` and `fork` are refused in open mode
  (exit 16). Exit codes are frozen and reused.
- **Two labels**, `trusted` and `untested`, derived at answer and deliver time by walking the
  artifact's lineage; never stored on an artifact. One fixed-structure **qualifier line**
  beside the label names what two words would hide (flags accepted on the path, parameters
  outside range, person-set parameters, upstream as reported, controls under another
  environment, untested inputs). Two pinned label sentences, held identical in the engine and
  the skills by a test.
- The answer predicates (`ans.*`) and the two new binding predicates are **invariant**, so
  the exploratory profile's block-to-flag remap cannot soften the one promise open mode makes.
- A new parameter source label **`person`** (beside `agent`, `fork`, `inherited`,
  `declared`): a value the person dictated in their own words, recorded with their words as
  the reason; it opens no `param.agent_proposed` hold and is listed in the coverage report.
- Phase 2 and later: judgment tools on demand, budgets (`runs.budgets_json`), structured
  claims (`compare`, `threshold`), the console's Questions page, the promotion loop. Later
  with a trigger: splits and holdout (`projects.splits_json`), staged mode (H5).

## 1. What open mode is

### Objects

| object | definition |
|---|---|
| open project | `mode: open`; `pipeline: null`; `domain` the plugin; its tools are the method's modules listing `open`; inputs are a delivery's files with `derived_from`; `objective.deliverables: []`, no `params` |
| tool | a module listing `open`, with a params schema, decision points, an env, controls (a positive control with a truth table makes it trustable) |
| tool run | an on-demand step `<nn>_<tool>` of the open run: `call` = propose + pre-gate + execute (engine runner) + post-gate |
| exec run | an on-demand step `<nn>_exec`: the operator's script, run under the executor with inputs bound read-only; outputs recorded as artifacts; the script blob in the trace |
| question | a row in `questions`: the person's words verbatim, when, the session reference |
| answer | a row in `answers`: the reply text, the cited artifacts and cells, the derived label, the qualifier block, admissible or blocked |
| label | `trusted` only when every step in the lineage is a tool or pipeline step, engine-run, environment verified, controls current, completed; anything else, including one exec anywhere, is `untested` |

### The person's loop (what they see)

After the three-part report of a delivery the operator **reviews before it switches**
(owner's change, 2026-10-16): it runs `tools list` on the delivered project (a reading verb;
works before any open project exists), reads the project's declared question and deliverables
(`objective.yml`), the design's factors and levels (`design.yml`, the source of the contrasts
that exist) and the method's suggested paths (`skills/<pipeline>.analyze.yml` `open.paths`),
and proposes three to five **paths forward**, one line each in a pinned form: what it would
answer, by which tool (would be trusted) or by code written here (would be untested), and what
it would need from the person. Then it says the switch paragraph and asks for the yes
(decision 4). The person picks a path, asks something else, or declines. A path the person
picks is recorded as the first question with `origin: suggested`; a question in their own
words is `origin: person`. From then on, per question: the operator picks one of three routes, a
**tool** when one's "use when" fits, **exec** when no tool fits and the delivery holds the
data, **cannot** otherwise; runs it; files the answer; relays `present --answer` whole: the
label sentence first, the text, the tables and figures the method's answer view names, the
cells the numbers were checked against. The person never sees ids, paths, the second project,
or the script unless they ask ("show me the code" prints it verbatim). At the end they say
which answers to deliver and receive them beside the upstream delivery with their labels.

### The pinned sentences

Said as written; the two label sentences are printed by `answer`; the rest are the
operator's. Held identical across the operator skill, every analysis skill and the engine's
constants by `tests/test_render_skill.py` and one engine test.

- Paths forward (before the switch; the operator composes from `tools list`, the objective,
  the design and the method's `open.paths`): "Your project asked {the objective's question in
  the method's words}, and the delivery holds {the deliverables}. Paths I can take from here:"
  then one line per path in one of two forms, "{what it answers}: {tool title}, a tool
  shipped with the method; it would be labelled trusted{; it needs {ask} from you}." or
  "{what it answers}: no tool ships for this, so I would write code; it would be labelled
  untested." Three to five paths, tools before code, never a path the delivery lacks the data
  for. The person may pick one, ask something else, or stop.
- Switch (the confirm echo and the sentence): "Your results are delivered. You can ask
  questions of them here. Nothing you ask is declared in advance and nothing here is a
  pre-registered result. Some questions I answer with tools shipped with this method, which
  are tested; some with code written in this session, which is not; the engine labels each
  answer trusted or untested from what ran, counts every run of the same tool on the same
  data, and nothing you ask changes the delivered files. Shall I open it for questions?"
- Before exec: "No tool shipped with this method answers that, so I am writing code for it;
  the engine will run it on the delivered data and label the answer untested."
- Cannot: "I cannot answer that from this delivery: {it holds {what} only | it needs {what},
  which is not delivered | it is a judgment, not a result}. {What would answer it, or
  nothing.}"
- Label, trusted (engine): "Label: trusted. Produced by {tool title} ({module}@{version}), a
  tool shipped with the method, run by the engine on the delivered data. Numbers checked
  against the cited cells: {n} of {n}. Everything else in this answer is the assistant's
  reading."
- Label, untested (engine): "Label: untested. Produced by code written in this session, run
  and recorded by the engine on the delivered data; no test or control has checked it.
  Numbers checked against the cited cells: {n} of {n}. Everything else in this answer is the
  assistant's reading."
- Qualifier (engine, after either): `flags accepted on the path: … | parameters outside
  range: … | person-set parameters: … | upstream: verified | as reported ({steps}) |
  controls: current | under another environment | none | untested inputs: …`, each `none`
  when empty.
- What trusted means, what untested means, who labels, trusted only: the four explanations
  from the person-side design, said once when first relevant or when asked.

## 2. Engine changes, by file

### 2.1 Binding

- `src/stringency/config.py`: `pipeline: str | None`; new `domain: str | None`;
  `_refuse_open_strict` keeps the open-with-strict refusal, drops "v1 accepts only
  pipeline", requires `pipeline is None` and `domain` when `mode == "open"`, keeps `staged`
  reserved.
- `src/stringency/pipelines.py`: `open_pipeline(domain, version, answers) -> Pipeline`
  (`name="open"`, `steps=[]`, `answers` = the plugin's `objective_questions`). The one place
  an empty topology is made; `obj.feasibility`, `obj.deliverable_unreachable`,
  `init.question_unsupported`, `init.deliverable_unproduced` pass against it (verified).
- `src/stringency/project.py`:
  - `InitRequest`: `pipeline: str | None`, `from_delivery: Path | None`, `upstream`,
    `question`; declarations optional when `from_delivery` is given.
  - `init_project`: drop the mode refusal; refuse `--pipeline` with `--mode open`.
  - `_init_in`: in open mode, `tools = [m for m in ModuleIndex(root/"method").all() if "open"
    in m.manifest.modes]`, refuse when empty; `domain` the single domain among them;
    `require_plugin(domain)`, `"open" in plugin.modes`; `pipeline = open_pipeline(...)`;
    refuse non-empty `objective.params`; the module-mode loop runs over `tools`; `projects`
    row `pipeline_name="open"`, `pipeline_version=<method tag>`, `pipeline_digest =
    hash_json(sorted tool refs)`.
  - New `declarations_from_delivery(dir, upstream) -> dict[str, Path]`: reads
    `<dir>/index.json`; `upstream` = `--upstream` or `dir.parent.parent` when it holds
    `stringency.yml`; writes `inputs.yml` (one item per `files[]`: `name=<output>`, step
    prefix on a clash; `path`, `type=kind` with `prose` as `text`, `blake3`,
    `derived_from={run_id, step_id, output, project}`), `design.yml` byte-for-byte from the
    upstream, `objective.yml` from the upstream's with `id=<id>-open`, `deliverables=[]`,
    `params={}`. Explicit `--inputs/--design/--objective` override. `declare --check` reuses
    it.
  - `Project`: when `config.pipeline is None`, `self.pipeline = open_pipeline(...)`,
    `self.plugin = require_plugin(config.domain)`, `self.open_ended = True`; `tools()`,
    `tool(name)`; `env_names()` and `env_for_input()` iterate tools when open-ended.
  - `inherited_confirmation()`: returns None when `mode == "open"` (decision 4). The confirm
    hold's echo (`echo.py`) is the switch paragraph above plus the bound delivery (run id,
    upstream project, files); accepted at a tty or relayed with a session reference.
  - `ControlProject`: `open_ended = False`.
- `src/stringency/cli/verb_init.py`, `verb_declare.py`: `--pipeline` optional,
  `--from-delivery`, `--upstream`, `--question`.
- `src/stringency/present.py` `Site.load`: build `open_pipeline` from the module index when
  `cfg.pipeline is None` (the reading verbs stay plugin-free).
- Refusals, one line each, exit 16: `run`, `fork` in open mode. `abandon` closes an open run.

### 2.2 On-demand steps

- `src/stringency/runs.py` `RunContext`: `on_demand()` (cached; reads `step_events`
  `created` payloads carrying `on_demand: {kind: tool|exec, decl, manifest?, question_id}`;
  no new column, the `captures` precedent); `pipeline` property =
  `project.pipeline.model_copy(update={"steps": [*declared, *on_demand in creation order]})`;
  `order()`, `decl(step_id)`, `module_for(step_id)` (method index for a tool;
  `Module(path=step_dir, manifest)` for exec); `next_step_id(name)` = `f"{n+1:02d}_{name}"`;
  `create_on_demand_step(decl, kind, manifest=None)` via `Store.create_step(row, extra=...)`;
  `status()` passes `open_ended`; `project_config()` uses `self.pipeline`, adds on-demand
  manifests and the two additive `ProjectConfig` fields of 2.5; `open_run` hashes tool
  scripts into `module_script_blobs` and records `captures.tools`; `abandon` iterates
  `rc.order()`.
- `src/stringency/machine.py` `derive_run_status(statuses, order, *, open_ended=False)`:
  open-ended is `held` when any step is held, else `running`; never `completed`; a blocked,
  rejected or failed on-demand step is that step's state only.
- `src/stringency/steps.py`: `plan_step` reads `rc.pipeline.step(step_id)` and
  `rc.module_for(step_id)`; `StepPlan.inputs_read_only`; `propose` reads `rc.pipeline`;
  `bind_inputs(rc, module, bindings)` (`--in name=<$inputs.x | $steps.id.out | artifact id>`;
  an unbound input binds the unique project input or latest produced artifact of its type,
  else refuses naming the candidates, exit 15); `propose_tool(rc, name, bindings, proposed,
  rationale, sources)` builds the decl (`params={}` so `build_action` fills the module
  schema's defaults), creates the step, calls `propose`; `job_for` puts input directories in
  `ro_bind_paths` when `plan.inputs_read_only` (today `job_for` binds every input directory
  read-write, `steps.py:425`, so an exec script could overwrite the delivery). A retry of a
  blocked tool step is `propose <step id> --set` (exists); a fresh `call` is a new step.
- `src/stringency/actions.py`: `person` as a source label; `proposed_by` precedence
  `agent > person > inherited > declared > pipeline`.
- `src/stringency/runloop.py` `next_step`: holds first; then, open-ended, `Next("open", ...)`
  with questions, answers, steps and artifacts; `plain.py` gains the `open` sentence.
- `topo.undeclared_step` and `topo.predecessor_incomplete` change nothing: a tool is in the
  pipeline it is handed and lists `open`; a module without `open` fires it; a tool bound to a
  held step's output blocks.

### 2.3 Verbs

| verb | behaviour | exit |
|---|---|---|
| `tools list [--json]` (`cli/verb_tools.py`; a reading verb, plugin-free like `present`, valid on a delivered pipeline project and on an open project) | every module listing `open` in the project's method checkout: ref, kind, operation, inputs by type with the delivered files or produced artifacts that match, params with defaults and decision points, outputs, env digest status, last passing control (date, env current or not) or "none: outputs will be labelled untested"; with the method's `skills/<pipeline>.analyze.yml` present, each tool's title, use-when and asks, and the method's `open.paths`; with `--context`, the objective's question and deliverables and the design's factors and levels, so the operator composes the paths from one payload | 0 |
| `ask "<text>" [--suggested] [--json]` (`verb_ask.py`) | `open_or_resume` (the confirm hold enforced); `questions` row with `origin` `person` or, with `--suggested`, `suggested` (a path the operator proposed and the person picked); text in `messages`; prints `question_id` and the tools | 0, 10, 16 |
| `call <tool> [--question <id>] [--in k=ref]… [--set k=v]… [--asked-by person] [--reason] [--json]` (`verb_call.py`) | `propose_tool`, pre-gate, `execute_engine`, post-gate; `--asked-by person` labels every `--set` `person` (reason = the person's words); without it `agent` (a departure from the default opens `param.agent_proposed` as today) | 0, 10, 11, 12, 13, 15 |
| `exec <script | -> [--question <id>] [--in k=ref]… [--out name=type[/format]]… [--env <name>] [--seed N] [--reason] [--allow-local] [--json]` (`verb_exec.py`) | 2.4 | 0, 10, 11, 12, 13, 15 |
| `answer --question <id> --cite <artifact id[:row[:column]]>… (--text <file> | -) [--json]` (`verb_answer.py`) | 2.5 | 0, 12, 15, 16 |
| `deliver --answer <id>…` | 2.7 | 0, 10, 15, 16 |
| `present [--answer <id> | --answers]` | 2.7 | 0 |

### 2.4 `exec`

`steps.propose_exec(rc, script, bindings, outputs, env, seed, rationale)`: step id
`<nn>_exec`; the script (file or stdin, never argv) copied to `runs/<run>/<step>/script.<ext>`,
hashed (`executions.script_blob`, migration 0003 exists) and its text stored in `messages`
under that hash; an in-memory `ModuleManifest(name="exec", version=blob[:12],
kind="deterministic", operation="exec", modes=["open"], env, entry="script.<ext>", inputs from
the bound artifacts' kinds, outputs from `--out`, empty params schema)`; `Module(path=step_dir,
manifest)`; the decl with `runner="engine"`; `create_on_demand_step(..., "exec",
manifest.model_dump())`; then `propose`, `execute_engine`, `finish` unchanged. Outputs land as
`<step>/<name>.<ext>` with sidecars through `record_output`; an object-type output runs the
plugin extractor. `--env` defaults to the tools' single env, else required.

Containment, all recorded: inputs read-only (`inputs_read_only`); the method checkout
read-only (exists); `--containall` scrubs the environment (exists); `Job.timeout` from the
policy's `open.exec_timeout_s` (the field exists in `Job` and both executors honour it; it is
never set today, `steps.py:436`); `--seed` passed as `seed` in the job JSON and recorded on
the action (the engine picks and records one when omitted; whether the script used it is not
checkable and the coverage report says so); network: `probe` gains a check whether
unprivileged `apptainer exec --net --network none` works on the host, and the exec command
line adds it when it does, with a new additive column `executions.network` (`none |
unenforced | n/a`) recording the outcome; `exec` under the `local` executor is refused
without `--allow-local` (development only; the local executor inherits the engine's whole
environment).

What runs at the exec gate (nothing new blocks): pre `topo.*`, `repro.env_unpinned`,
`repro.input_digest_mismatch`, `param.*` (empty), `obj.feasibility`; post
`out.schema_conformance` (no schema), `repro.intermediate_dropped`. Never fires:
`param.agent_proposed`, `exec.plan_drift`, `exec.script_drift`, `repro.env_unverified`,
`judg.*`. The verb prints the untested sentence on completion.

### 2.5 Answers, predicates, labels

- `src/stringency/answers.py` `file_answer(rc, question_id, text, cited) -> AnswerResult`:
  resolve each `--cite` against this run's `artifacts` (`status='produced'`, step
  `completed`; a held step's output cannot be cited); load every cited `table` artifact with
  `tables.load_table`; the citable cells are the cited rows and columns when given, else every
  cell of the table; build a synthetic `Action(step_id="answer", operation="answer")` and an
  `OutputBundle(prose=text, evidence_tables=<cited cells>, observed={cited, missing, label,
  provenance})`; `gate.evaluate(..., only=registry.matching("ans.*"), store=store)`
  (`only=` exists at `gate.py:110`, unused); write the `answers` row (`status` admissible or
  blocked, `label`, `provenance_json`, the text in `messages`); print the label sentence and
  the qualifier line, or the block. Blocked answers are kept, as rejected proposals are.
- `src/stringency/provenance.py` (new): `lineage(store, run_id, artifact_id) -> list[StepFact]`
  (artifact → step → latest action → `inputs_json` digests → artifacts by hash; project
  inputs are roots); `StepFact = {step_id, kind, module, runner, env_status, controls, holds:
  [{hold_id, verdict, reviewer, via}], param_sources}`; `label_for(facts)`; `block_for(rc,
  artifact)` is the L35 provenance block and the qualifier line's source;
  `LABEL_SENTENCES`, `QUALIFIER_LINE`.
- `src/stringency/predicates/context.py` `ProjectConfig` gains `artifact_kinds` (digest →
  recorded kind) and `controls_current` (module ref → `{status: current|stale|none,
  last_passing}`), filled by `RunContext.project_config()` (the `script_blobs` precedent: facts,
  no I/O in predicates).
- Engine-shipped predicates, each with a must-fire and must-pass fixture in
  `tests/test_gate.py`:

| id | phase, scope | fires when | default |
|---|---|---|---|
| `topo.input_type_mismatch@1` | pre, `*` | a bound input's recorded kind differs from the module input's declared type | block, invariant |
| `param.schema_invalid@1` | pre, `*` | the action's parameters fail the module's `params.schema.json` (enum, bounds, type); today a proposed value is checked only against pipeline ranges | block, invariant |
| `prov.controls_stale@1` | pre, `*`; False outside open mode and for `exec` | the tool has no control, no passing `controls_runs` row for `name@version`, or the last passing row ran under a different digest of the tool's env | log (the label carries the consequence) |
| `ans.cited_missing@1` | post, `answer` | a cited artifact or cell does not exist, is rejected or superseded, or belongs to an abandoned step | block, invariant |
| `ans.numeral_unmatched@1` | post, `answer` | `judg._numeral_problems(text, cited cells)` is non-empty (same regex and rounding rule as report prose; the denominator is the cited cells, not every cell of every table, because any numeral matches something in a ten-thousand-row DE table) | block, invariant |
| `ans.label_authored@1` | post, `answer` | the text contains `\b(trusted|untested)\b`: the operator may not write the mark | block, invariant |

`policy.py` `invariant` gains `ans.*`, `topo.input_type_mismatch`, `param.schema_invalid`.
`controls.current_for(store, module, env_digest)` supplies `controls_current`.

### 2.6 Controls for deterministic tools

`src/stringency/controls.py`: `ControlSpec.params` (admitted as defaults on the synthetic
decl, so no hold opens); `FixtureTruth.column` optional; `expect.equals: {output, columns,
tolerance: <abs> | {col: abs}}` compares the output table to the truth keyed by `truth.key`
(numbers within tolerance, text exactly; metrics `rows_compared, rows_matching, missing_keys,
max_abs_diff`; a lower `rows_matching` is a regression); `expect.completed: true` is the
explicit form of today's implicit score (allowed for a figure tool); `expect.count: {output,
where: {column, below|above}, max|min}` for a negative control ("no gene passes adj_p < 0.05
after shuffling"); `synthetic_pipeline` builds a one-step pipeline for a module in no pipeline
step that lists `open` (phase 1: one required input of the fixture's type, others optional).
`lint.py`: warn on a deterministic module listing `open` with no `positive` control
("outputs will be labelled untested").

### 2.7 Deliver, summary, methods, coverage, present

- `deliver.py`: the `status != "completed"` refusal applies only when not open-ended; in open
  mode `--answer` is required and each id must be admissible and of this run; the held guard
  stays; no sign-off hold (decision 5). The deliver gate passes `store=store` (today
  `store=None`, `deliver.py:94`, so its verdicts are evaluated and dropped). Finals = the
  chosen answers' cited artifacts plus `--include`. `dest = deliver/<run>/<delivery_id>/`
  (several deliveries per run; `present._deliver_dir` already reads the latest). Each answer
  is written as `<answer_id>.answer.md` (question, label sentence, qualifier, text, cited
  files). `index.json` additive keys: `mode`, `files[].provenance` (the L35 block, both
  modes), `answers: [{answer_id, question, file, label, cites}]`.
- Rerun counts (the forking-paths disclosure): per module and input digest, N runs, K
  distinct parameter sets, D delivered, from `actions`; an `explored:` section in
  `coverage.md` and `summary.md`; per delivered answer one line, "one of N runs of <tool> on
  these inputs; asked after M results on the same inputs existed; the others are steps …".
  "What was asked" and the coverage report count questions by `origin` (suggested by the
  operator and picked, or the person's own), because the two are different populations.
- `summary.py` `render_summary` in open mode: "What was analyzed" (the confirm echo body),
  "What was asked", "What ran" over `rc.order()` (a tool line with its question; an exec line
  "a script written in the session (blake3 …) run in env X; outputs …, untested"), "What was
  checked and decided", "Judgments", "What you received" (per delivered answer), "What was
  untested", `explored`, then the not-checked sentence below.
- `methods.py`: first sentence names the method tag's tool set in open mode; tool steps
  through `plugin.describe(action)`; exec steps get the engine's own sentence.
- `coverage.py`: loops over `rc.pipeline.steps`; `in_scope_for_pipeline` over tools; a line
  "tools run without current controls: …"; an `upstream lineage:` section from a new
  `captures.upstream_lineage` recorded at open-project init (the upstream run's ancestor
  chain and delivery timestamps, read from the upstream `prov/run.db` the engine already
  opens for `derived_from`); the closing sentence for an open run: "not checked: whether the
  delivered answers were chosen because they came out (every run of every tool on the same
  inputs is counted above; the choice was the person's); anything the assistant said that was
  not filed as an answer; whether an untested script computed what its output claims, or used
  the seed it was given; what the operator read into the hosted session beyond the cited
  artifacts; whether the upstream delivery was re-run after a question here was answered; and
  anything not listed above."
- `present.py`: `present_run` in open mode defaults to the latest run with a delivery; new
  payload `kind: answer` (`answer_id`, `question`, `label`, `label_sentence`, `qualifier`,
  `route`, `tool`, `text`, `sections` from the tool's `answer_view` in `skills/open.yml` or
  the default view, `cited` cells, `decisions` with sources, `files`, `delivered`);
  `present --answers` lists every answer; `render_markdown` and `render_html` for it (the
  label as a pill with the pinned body on the console).

### 2.8 Trace, additive

Migration `src/stringency/db/migrations/0005_open_mode.sql`: `questions(question_id PK, run_id,
seq, text_ref, origin, asked_via, operator_session_ref, ts)` (`origin` is `person` or
`suggested`) and `answers(answer_id PK, run_id,
question_id, text_ref, cited_json, label, provenance_json, status, ts)`, both append-only with
triggers; `executions.network TEXT`. `Store.APPEND_ONLY` and
`tests/test_store.py::test_append_only_tables_raise_on_update_and_delete` gain both tables.
No column on `steps` or `artifacts`: the on-demand marker is the `created` event payload; the
label is derived. `spec/trace-schema.md` gains the rows and the `step_events.created.on_demand`
and `captures.tools` / `captures.upstream_lineage` notes.

### 2.9 Policy

`policy.py` `ProfilePolicy` gains an `open:` block: `exec: allowed | refused`,
`exec_timeout_s: int`. Exploratory and standard: allowed; strict is refused with open at init.
Budgets (`open.budget`) are phase 2. The toy and template `policy.yml` carry the block.

## 3. Skills and documents

- `integrations/claude-science/stringency-operator/SKILL.md` section 10 "Open mode": before
  it begins (after the three-part report: `tools list --context` on the delivered project;
  compose three to five paths in the pinned form from the tools' use-when and asks, the
  objective's question and deliverables, the design's factors and levels, and the method's
  `open.paths`; tools before code; never a path the delivery lacks the data for; never a
  verdict-shaped path); when it begins (the switch paragraph, the yes relayed as the confirm
  verdict, `init --from-delivery` as `<upstream>-questions`, a picked path filed with
  `ask --suggested`, reuse on a later session); the loop (`ask` → route → `call` or
  `exec` or cannot → `answer` → `present --answer` relayed whole); the three routes and the
  rule never to combine tools to approximate a question none answers; a tool's parameters
  (`asks` from the person's words with `--asked-by person`; `proposed` by section 9 and a
  hold); what to do with an `answer` block (fix the text, never a number, never a table, never
  re-run to make it match; after two blocks relay the table and say which number could not be
  sourced); what never (code outside `exec`, a label of its own, a file into `deliver/` except
  through `deliver --answer`, a verdict); section 10.7 the pinned sentences. Section 4 and
  `templates/brief.md.j2` gain six intents (init --from-delivery, ask, call, exec, answer,
  deliver --answer). Rule 3 reads "analysis code of your own runs only through `exec`"; the
  preamble's "do not compute" is now enforced by `answer`.
- `tests/test_render_skill.py`: extractors holding 10.7 and the open-mode rules identical in
  every analysis skill; the nine-rule assertion unchanged (open-mode rules are a block, not a
  tenth rule); an engine test asserts `provenance.LABEL_SENTENCES` equals the skill's text.
- `integrations/claude-science/templates/analyze-skill.md.j2` section 8 "After delivery:
  questions": the review and the paths forward first (the `tools list --context` call, the
  pinned path forms, the method's `open.paths` as the author's suggested paths in the method's
  words, each naming its tool or saying it needs code), then the switch, the pipeline's tools
  with their "use when", the pinned block verbatim. `render_skill.py`: `OPTIONAL` gains
  `tools: [{module, title, use_when, asks: {param: question}, proposed: [{param, evidence,
  ask}], defaults_to_say}]` and `open: {intro, paths: [{answers, tool | code, needs}]}`
  (`--check` requires each path's `tool` to be a listed tool and a `code` path to name no
  tool); `_cross_check_tools` requires each module to list `open`, every `asks`
  and `proposed` key to be a parameter of its schema, every decision point to be in one of
  them, and every `needs` type to be an output of the pipeline (the `decisions:` check of L32,
  reused). A routing file `skills/<pipeline>.questions.yml` (outcomes `tool:<name> | exec |
  cannot | fork | explain`) beside the phrasings file, checked for shape by `--check`, run by
  hand as section 5 of `spec/method-skills.md` does.
- `spec/method-skills.md`: the `tools:` and `open:` fields; a `skills/open.yml` delivery
  skill with `answer_view` per tool (the `hold_view` shape plus `head: N` for long tables) read
  by `present --answer`.
- Docs: `docs/open-mode.md` (what it is; the two words; what you can ask; the three routes;
  decisions; delivering; what is recorded; pointers for authors and operators; how it is
  measured); a paragraph in `docs/onboarding.md` "What to expect" and in
  `integrations/claude-science/new-project.md`; `docs/method-author.md` sections "Tools for
  questions" and "Promoting a session's code into a tool".

## 4. The method author's side

- A tool is `modules/<name>/` with `modes: [open]` (or `[pipeline, open]`), its script,
  `params.schema.json` with `decision_points`, `controls/` with a positive control using
  `expect.equals` against a truth table and a negative control using `expect.count`; the words
  in `skills/<pipeline>.analyze.yml` `tools:` and `skills/open.yml`. `templates/method-repo/`
  gains `modules/example-tool/`, the `tools:` entry in `example.analyze.yml`, `skills/open.yml`,
  `skills/example.questions.yml`, README rows.
- Toy (`plugins/stringency-toy/`): plugin `modes=("pipeline","open")`, operation
  `plot_groups`, version 0.1.3; method `compare-groups` 0.1.1 with `modes: [pipeline, open]`
  and `controls/positive-known-differences.yml` (`expect.equals` on `n_a, n_b, diff, p_adj`
  against `controls/fixtures/compare_truth.tsv`); new `modules/plot-groups/` (`modes:
  [open]`, input the comparison table, output an SVG drawn with the stdlib, `expect.completed`);
  `skills/toy-engine.analyze.yml` `tools:`, `skills/open.yml`, `toy-engine.questions.yml`;
  goldens regenerate.
- Xenium (phase 3, decision 2): `compose-cells`, `pseudobulk-de` (limma-voom, the spatial
  plan's phase 6), `score-pathways`, `volcano` as open modules from the ROSC R code, each with
  the two controls on a small liver subset fixture; `xenium-upstream.analyze.yml` `tools:`,
  `skills/open.yml`, `xenium-upstream.questions.yml`; an rc tag; republish.
- Promotion loop (phase 4, with backlog L37): `answers --export` (one markdown per answer
  with YAML frontmatter above the text and the script, into `runs/<id>/answers/` and the
  delivery); `promote <exec step> --into <method checkout> --name <module>` writes a module
  skeleton (manifest from the exec record, `pre.<ext>` the script verbatim, a regression
  control whose fixture is the exec's inputs by hash and whose truth is what the script
  produced, a `promoted_from` provenance line that never reaches the model); the
  `stringency-revise` skill reads exported reviews and answers by theme, proposes, classifies
  new/duplicate/extension/conflict, waits, then runs `promote`.

## 5. Rigor: what is checked, what is written down

Phase 1 mechanisms, in rank order: the label derived by the lineage walk with the qualifier
line; `ans.numeral_unmatched`, `ans.cited_missing`, `ans.label_authored` invariant; the rerun
counts per delivered answer in `coverage.md` and `summary.md`; `exec` containment (read-only
inputs, timeout, seed recorded, network recorded and enforced where available, script in
`messages`, local refused); no inherited confirmation and the pinned switch paragraph
accepted. Then the `person` parameter source, the deliver gate recording its verdicts, the
upstream lineage capture.

Accepted and written into the coverage report's closing sentence: the chat is not the trace
(what the operator says outside `answer` is unrecorded); an untested script's output is not
checked against anything; the seed's use is not checkable; the upstream may be re-run later.
Not applicable: `obj.declared_after_result` (every open question is declared after the result
by construction; the rerun count is its open-mode form). Later with a trigger: splits and
holdout (someone wants a confirmatory claim from an open project), structured claims
(`compare`, `threshold`), budgets, a per-step dirty check for weeks-long runs, judgment tools
(with the cumulative-denominator fix in `coverage.py:139-145` and `abandon --step`), open mode
under a PROTECT policy (needs L1 and a local operator harness).

## 6. Design amendments for the owner (`spec/stringency-design.md`)

One sentence each, approved before S1 or applied as S7 with the owner's yes:
2.2 `mode: open` accepted (`pipeline: null`, `domain`, tools = modules listing `open`;
`splits` reserved); 2.5 an open objective declares `deliverables: []` and no `params`; 2.6
`run` and `fork` refused in open mode, an open run stays `running` or `held` until `abandon`;
2.7 no inherited confirmation for an open project, `init --from-delivery` derives the
declarations, the confirm echo is the switch paragraph; 3.3 and 3.4 a tool is a module listing
`open`, a step is created at proposal, `exec` runs a session script as a step whose outputs
are untested (closes G2); 5 the `person` source; 6.5 the six predicate rows; 7.1 open-run
status; 9.4 `questions`, `answers`, `executions.network`, the `created` payload; 10.3 `exec`
binds inputs read-only, the local executor is development-only; 11 `expect.equals`,
`completed`, `count`, `params`, the one-step synthetic run; 12.1 `deliver --answer` from a
running open run, the provenance block in `index.json`, the new `summary.md` sections and the
rerun counts; 14.1 the verbs and flags; 17 the open-mode row moves to built, `budgets` and
`splits` stay reserved. No frozen contract is reshaped.

## 7. Order of work

Engine sessions S1 to S7 and skill sessions O1 to O6; S-sessions are serial on `src/`;
O1 can run beside S1 to S3 (text and renderer only); O2 needs S1 to S6; O3 needs S5 to S6; O4
needs S4; O5 needs O2 to O4; O6 needs O5. Each session ends with its acceptance green, a note,
and a commit naming it.

| session | builds | acceptance |
|---|---|---|
| S1 binding | 2.1; plugin and toy `compare-groups` list `open`; `tools list` (on a delivered pipeline project and on an open project, `--context`); `run`/`fork` refused; `tests/test_open_init.py` | `toy-process` delivers; `tools list --context` on it names compare-groups with the objective's question and the design's factors; `init --mode open --from-delivery` binds with a confirm hold whose echo is the switch paragraph; accepted with `--attest`; `--pipeline` with `--mode open` and `run` refused |
| S2 on-demand steps | 2.2; `ask`; `call`; migration 0005 (both tables); `topo.input_type_mismatch`, `param.schema_invalid`; the `person` source | `ask` then `call compare-groups` completes with an artifact; `--set correction=foo` exits 11 on `param.schema_invalid`; `--set correction=bonferroni` exits 10 under standard and completes once accepted; `--asked-by person` opens no hold and is listed; a wrong-type `--in` exits 11 |
| S3 exec | 2.4; `probe`'s network check; `executions.network` | a script producing a table completes with `executions.script_blob`, a `messages` row and read-only input binds (a script that writes beside its input fails); a missing `--out` exits 13; `--allow-local` needed under local; `exec.script_drift` and `param.agent_proposed` never fire |
| S4 controls | 2.6; the toy positive control; `plot-groups`; `controls.current_for` | `controls run --module compare-groups --allow-mock` passes from a pipeline project and from an open project; a perturbed truth fails and regresses; `plot-groups` chains on the comparison output |
| S5 answers and labels | 2.5; `provenance.py`; `prov.controls_stale`; `ans.*` with fixtures; `answer` | a wrong numeral exits 12; a correct one is admissible and `trusted` (control passed, env verified); an answer citing the exec table is `untested`; a missing id and an authored "trusted" block; the qualifier line names an accepted flag on the path |
| S6 deliver and present | 2.7; `deliver --answer`; the rerun counts; `summary.md`; methods; coverage; `present --answer` | `index.json` carries `answers` and per-file `provenance`; `summary_open.md` golden with `explored:`; the deliver gate writes `predicate_results`; `present --answer` shows the question, the label sentence, the qualifier, the cells |
| S7 end to end and ledgers | `tests/test_open_mode.py` (the whole chain on the toy: deliver → open → ask → call → exec → answer blocked → answer admissible → deliver → present); DECISIONS; trace-schema; the design amendments; roadmap lane; note | `uv run pytest`, `ruff`, `mypy`, `scripts/check_no_biology.sh` clean |
| O1 skill text | section 10 and the pinned block; intents; template section 8; `render_skill.py` `tools:`/`open:`/questions check; `test_render_skill.py` extractors; template method-repo files; docs | the sentences exist once and render into every skill; `--check` fails a tool without `use_when`, with a decision point nobody settles, or needing an output the pipeline lacks; method CI's skill check covers it |
| O2 toy rehearsal | `toy-engine.questions.yml`; `open.paths` in the toy's analyze file; a scripted session on a toy delivery; the first row of the open-mode measurement table in `spec/plans/backlog.md` | the paths forward proposed in the pinned forms from `tools list --context` before the switch (every path names a tool or says code; none the delivery lacks data for); ten questions on the toy: 0 unrequested ids, every label line verbatim, one `answer` block provoked and cleared by fixing the text; suggested and person questions both counted |
| O3 present and console | `present --answers`; console `/questions/<project>`, `/answer/<id>`, `/api/questions`, the `answer_recorded` event; board cells and sentence for an open project | a delivered answer renders the same on the CLI and the console; the Questions page has no form; the board row says the counts |
| O4 Xenium tools | the four tools with controls; the skill files; rc tag; republish | `lint` clean; controls pass; the rendered skill lists the tools in the method's words; the routing file run by hand with results recorded |
| O5 acceptance and baseline | `evals/liver-questions.yml` (ten questions by a third person with grading notes and tool-computed targets); `integrations/claude-science/open-mode-acceptance.md`; a non-developer's run; the same ten questions to a plain Claude session over a read-only copy of the delivery; an LLM grader handed both trajectories with deterministic tools for numbers and binary rubric items (`avoids_fabrication`, `identifies_limitation`, `provenance_is_honest`, `label_relayed_verbatim`, `no_numeral_outside_cells`, `no_verdict`, `asks_before_inferring`); the owner reads transcripts hypothesis-free | both arms reported side by side (accuracy by category, median seconds, turns, cost) in a note and a table row |
| O6 promotion loop | `answers --export`; `promote`; `stringency-revise` in the template (L37); the first promotion of the exec script that recurred in O5 | a recurring untested answer from O5 becomes a tool in the next rc with the exec ids cited in the commit; the next open project answers it trusted |

## 8. Verification

- Unit and end to end: `uv run pytest` (new `tests/test_open_init.py`, `test_open_mode.py`,
  `test_gate.py` fixtures for the six predicates, `test_controls_fork.py` cases for
  `equals`/`count`/one-step runs, `test_store.py` append-only cases, `test_render_skill.py`
  extractors, `test_board_present.py` and `test_review_serve.py` for the answer views);
  `uv run ruff check . && uv run ruff format --check . && uv run mypy`;
  `scripts/check_no_biology.sh`.
- By hand on the toy (S7, O2): from a `toy-process` delivery, the full loop in a Claude Code
  session through the rendered skill; count cards, turns, label lines verbatim, blocks.
- Controls: `stringency controls run --module compare-groups` from an open project; the
  regression path with a perturbed truth.
- `probe` on the workstation: the network-isolation check's outcome recorded before any
  real `exec`.
- Real data (O4, O5): one organ's delivery through the Xenium tools; the acceptance run and
  the baseline arm; the measurement row.

## 9. Amendments after the owner's test drive (2026-10-19)

The drive (`docs/open-mode-rehearsal.md`, toy method `v0.2.0-rc2`) found six things; each is
built on branch `open-mode` and recorded in `spec/DECISIONS.md` under "Open mode O2 findings":

- Every answer was untested: no control ever ran in the open project. A deterministic tool's
  controls now run inside `call` before its first step (`controls.ensure_current`).
- The untested label of a tool's answer said "code written in this session". A third pinned
  sentence names the tool and why it missed trusted; `{data}` names what the path rests on.
- The upstream's raw input was out of reach. `init --from-delivery` binds the upstream
  pipeline's own inputs as `upstream_<name>`, read-only, bound only when named.
- The open delivery shared file names with the pipeline delivery and used ids for names:
  `deliver/answers-<NN>/`, `q<NN>-<words>.md`, `answers-summary.md` and its siblings,
  `deliver --answer all`; the summary no longer carries the switch question.
- The project directory was hard to read: an engine-written `README.md` in every project, and
  the open project named `<upstream>-open` (sections 2.1 and 3 say `-questions`; read `-open`).
- The delivery message was long: one reporting rule in the skills, the brief's engine-record
  list behind `--rehearsal`, and answers delivered once after the pinned deliver sentence.

## 10. The report replaces `deliver --answer` (2026-10-19, after the second drive)

The second drive showed that answers reach the person in the chat before anything reaches
disk, so a session that ends after "that's what I wanted" left `deliver/` empty. The owner's
reading of what delivery is for: put forward the fruitful avenues, keep everything attempted on
record. Built on branch `open-mode` (`spec/DECISIONS.md`, "Open mode, the report"):

- `report.py`: every admissible answer is written into `deliver/<run>/` as it is filed
  (`verb_answer` calls `write_open_delivery`); `report.md` leads with the findings in full and
  ends with the other questions as short paragraphs; `index.json` carries `report` and the
  finding fields per answer; deterministic content, a `deliveries` row only on change.
- `findings` table (migration 0006, append-only) and `stringency finding <answer id>...
  [--reason] [--remove]`; `plain` counts findings; the README shows them.
- `deliver` in open mode regenerates; `--answer` refused. The open summary is gone (the report
  is the reader's file); coverage says "cited by findings".
- The operator says the report sentence once at the first answer, the findings sentence once
  when the person is done, and offers once in a later session with unmarked answers (10.7).

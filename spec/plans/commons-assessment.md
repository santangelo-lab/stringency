# commons, assessed

A plan note, written 2026-10-16 after reading `github.com/posit-dev/commons` (HEAD `15de530`,
2026-10-12; an R package and a Python package, both marked experimental, under one contract).
Not the spec. The method is the one used for ClawBio (`judge-sources-plan.md` section 9,
`archive/egress-and-remeasurement.md`): say what the other project is, put it beside the design, name
what is worth taking and where it lands, and record what is not. Items marked *design* change
design text and need the owner; the rest are DECISIONS-level or skill-level. Backlog rows L35 to
L38 point here.

**Status 2026-10-16.** Assessed; no integration lane. Four borrowings recorded as backlog rows
(L35 to L38), one proposal attached to the open G2 row, and a list of smaller practices with no
row. Nothing built.

## 1. What commons is

commons builds a conversational data agent for a data team. The agent is a `chatlas.Chat` (R:
`ellmer`) with a system prompt and tools over **data sources** (data frames and pins loaded into
DuckDB; SQLAlchemy engines queried as they are; Snowflake and Databricks with their catalogs
imported). Around the sources sit three layers: a **data dictionary** per source in the tidyverse
`data-dict.yaml` format; a **semantic layer** of trusted calculations, which are either
**measures** (an ordinary function decorated `@measure`, with a required description) or
**governed definitions** (expressions in data-dict's language, compiled to the source's SQL
dialect); and a **context layer** of markdown the agent retrieves from by BM25 search. An
end user asks a question in a Shiny chat; the agent searches for a measure, and when none fits,
reads context, describes tables, writes read-only SQL, and may run its own Python or R in a
sandboxed worker.

The mechanism the project is built around is a **provenance outcome the agent does not
decide**. Every tool tags its result: A for a trusted calculation, B for ad hoc SQL or code.
After the turn, code derives one of three outcomes from the tags. Only A tags: `Trusted`, a
green marker. Any B tag: `Cited` if the answer carries a `<commons-citation>` block whose
blockquote is found verbatim (whitespace collapsed, typographic quotes and dashes folded,
emphasis stripped, case kept, at least ten characters) inside a corpus of citable text, else
`Untrusted`, a yellow marker. The citable corpus is enumerated and ordered: measure
definitions, then dictionary prose, then table entries, then documentation; the first entry
containing the quote wins. The system prompt lists what is *not* citable: query rows, result
values, sample rows, inferred schema, code and plots. A streaming scanner holds back partial
tags across chunk boundaries, rewrites a verified citation into a display aside, and drops any
`<shiny-aside>` the model authors itself, so the model cannot write the marks of trust. A
mixed answer takes the lower outcome. The model is told not to imply it chose the marker.

Model-written code runs in a worker process that sandboxes itself before loading any of it:
Landlock or user namespaces plus seccomp on Linux, Seatbelt on macOS, nothing on Windows.
Without a kernel mechanism the constructor refuses unless `COMMONS_ALLOW_UNSAFE_FALLBACK=1`
selects audit-hook guardrails that the documentation says are not a boundary. The worker gets
an explicit environment allowlist and Python's `-I`, no network by default, an 8 GiB address
space, values by copy (Arrow IPC for frames, never pickle), and kill-and-respawn on timeout.
Earlier results are reachable as `r1`, `r2` handles. SQL is parsed by sqlglot and checked
against an allowlist of read-only statement forms, failing closed; the DuckDB connection is
locked down and the lockdown itself locked.

Trajectories are OpenTelemetry spans following the GenAI semantic conventions, off by default
(`log = TRUE`), with a `commons_conversation_turn` span and a `commons_provenance` child
carrying the tag and every citation candidate with its verdict. `trajectory_read()` rebuilds
conversations from Posit Connect's store or local `trace-*.jsonl`; `trajectory_review()` is a
Shiny app where a reviewer flags conversations or single exchanges and leaves notes, written
out as one markdown document per conversation with YAML frontmatter (flags, notes with user and
time) above the transcript, "for joint human-agent review". The two implementations agree
through `tests/shared/*.json`: executable fixtures both suites enumerate (the provenance truth
table, citation normalisation and matching, the citable corpus, prompt rendering, tool
registration, reminders, worker lifecycle), copied into the R package by `scripts/sync-shared.sh`
with a CI job that fails when a copy is stale. The README states the rule: prose cannot
enforce agreement; a per-language copy is a review defect.

Two skills ship. `trust-system`, loaded by the model on demand, explains the markers. `commons`,
for the coding agent that builds an agent, has references for onboarding, extracting measures
from existing apps and reports (each with a `@provenance` permalink back to the source line
range, which never reaches the model), writing an evaluation, and iterating on an agent from
reviewed trajectories (read the review documents first, group by theme, classify each proposal
as new, duplicate, extension or conflict, wait for the user). The worked evaluation is
`posit-dev/devrel-agent/evals`: 32 colloquial questions in YAML (`id`, `category`,
`target_type`, `input`, free-text grading notes with placeholders filled from targets computed
against the same snapshot), three epochs, an LLM grader handed the solver's full tool trajectory
that must call deterministic `percent_error_score` tools for numbers and submit binary rubric
items otherwise (`uses_correct_logic`, `avoids_fabrication`, `identifies_limitation`,
`provenance_is_honest`), per-category accuracy, median latency, tokens and cost, and a baseline
arm that runs Claude Code closed-book in a sandbox container over a clone of the data
repository. The README's numbers from that run: 86.3 against 83.5 percent, 31.0 against 60.5 s
median, $5.64 against $13.76.

Dependencies: chatlas, pydantic, duckdb, sqlalchemy, sqlglot, pyarrow, raghilda, jinja2,
pyyaml, opentelemetry-api, htmltools, google-re2; the SDK and exporters are an extra. Design
notes live in `pkg-py/notes/YYYY-MM-DD-<slug>.md`, the convention this repository uses.

## 2. Side by side

| | commons | stringency |
|---|---|---|
| unit of work | one question and its answer in a chat; seconds | one run of a declared pipeline; hours to days; holds, forks |
| where the model may go | anywhere its tools reach; the path is labelled afterwards | within the declared topology only; the action is gated before it runs |
| who the model is | the answerer, facing the end user | the operator driving the CLI, or the judge answering a rendered prompt with JSON; neither faces the person without the skill |
| trusted code | measures (functions with a described schema) and governed definitions (compiled SQL) | modules: versioned directories in a method repository, committed and hashed at run open |
| parameters | model-supplied if described, commons-injected if marked, otherwise an error | declared ranges and defaults; decision points; `param.*` gates; `declared`, `inherited`, `proposed` labels |
| model-written code | run in a kernel sandbox, labelled `Untrusted` unless cited | not run by the engine; an operator-run step is `env: as_reported` (backlog G2) |
| the claim check | the quote verified by exact match in an enumerated corpus | evidence refs resolved against the table; numerals in the rationale matched to cited cells (`judg.evidence_exists`, `judg.numeric_claims_match`) |
| what the reader is told | one of three outcomes beside the answer, pinned copy | the coverage report, `summary.md`, `present`; "not checked: anything not listed above" |
| replication | one call per question | three replicates, consensus, a hold on disagreement or abstention |
| human review | flags and notes on exchanges after the fact; markdown with frontmatter | holds that stop the run; verdicts bound to hashes with user, host, time, `via` |
| the trace | OTel spans, opt in, retention set by the exporter; thinking parts dropped | append-only sqlite `run.db`, every run, every rejection, hashes throughout |
| evaluation | a vitals task: question kinds, epochs, an LLM grader with the trajectory, a baseline arm | controls per module (negative, positive, planted), `mock` refused, regression against the last passing result |
| the author | a coding agent with the `commons` skill | a method author with `docs/method-author.md`, `lint`, the template repository |
| isolation | kernel sandbox for model code; read-only SQL; DuckDB lockdown | `apptainer --containall`; the method checkout bound read-only; the judge sees evidence tables, never the matrix |
| languages | R and Python under one fixture-pinned contract | a Python engine; modules in any language inside containers |
| egress | `network="none"` by default, enforced by seccomp | declared nowhere yet (backlog L1); `subagent` and `api` send evidence tables to a hosted model |

The difference underneath the table: commons gives the model freedom and labels the path it
took; stringency denies the freedom and gates the path before it is taken. commons' `trusted
only` mode (no SQL, no code, measures alone) is the nearest thing to pipeline mode, and
stringency's open mode (design 17, deferred) would be the nearest thing to commons. The two
projects are the two ends of one axis, and each has built well what the other defers.

## 3. Shared instincts

Reached independently, worth noting because they are evidence the instinct is right:

- The outcome is derived by code from what ran, never asserted by the model, and the model is
  told so (commons' `trust-system` skill; design 12.2's last line and `summary.md` "contains no
  interpretation").
- A claim must point at something the model was shown, and code checks the pointer
  (commons' citation match; 8.3).
- What the model may not cite is written down (commons' not-citable list; the evidence-table
  rule of 10.1).
- Abstention is an answer, prompted for and graded (commons' prompt, "say so plainly rather
  than substituting another guess", and the `not_answerable` category; the `abstain` field,
  `self_uncertain`, negative controls).
- The model must not be able to author the marks of trust (commons' scanner dropping
  `<shiny-aside>`; the trace written only by verbs, `--attest` needing a session reference).
- Shared text is generated from one source and a test fails when a copy drifts (commons'
  `sync-shared.sh` and its CI job; `render_skill.py` and `tests/test_render_skill.py` holding
  the operator skill's sections 6 and 9 identical in every analysis skill).
- Dated design notes in the repository; a skill for the coding agent that does the authoring;
  provenance tags on trusted code that never reach the model (commons' `@provenance`; the
  method SHA and `captures.script_blobs`).
- Rules before measurement, held-out cases, and a refusal to tune to the visible set
  (commons' evaluation reference; `design.holdout` and the ClawBio borrowing in
  `archive/egress-and-remeasurement.md` part 2 item 4).

## 4. Worth borrowing

### 4.1 A trust label on every delivered artifact, derived from the trace (L35)

commons' one durable idea is that the reader sees *one* label beside *each* answer, computed
by code from the path, with the words pinned. Stringency has every fact the label needs
(`executions.env` verified or as reported per step, `invocations.via` and `isolation`, which
holds on the path were resolved and by whom) and prints them in the coverage report per run.
It does not put them beside the table a person reads in `present` or on the console's project
page, so a person sees a delivered table and must open `coverage.md` to learn that two steps
upstream of it were run by the operator with no container evidence.

Mechanism, engine side, DECISIONS-level: `deliver` computes a `provenance` block per entry of
`index.json` by walking the artifact's producing step and its ancestors in the run:
`execution` is `verified` when every ancestor engine-run or operator-run step reports a
verified environment, else `as_reported` naming the steps; `judgment` is `direct`, `dispatch`
or `none`; `reviewed` lists the holds on the path and their verdicts with the reviewer. The
collapse to one word a person reads (commons' three) is the part to decide: the proposal is two
words, `checked` when execution is verified and judgment is direct or none, `as reported`
otherwise, with the review list shown either way. `present` prints it under each table's
title; the console's step and delivery views show it as a pill with commons' rule that the
body copy is pinned text, not prose. A mixed path takes the lower word, as a mixed answer does.
`summary.md` already says what was not checked; this is the same sentence placed where the
table is.

### 4.2 Harness conformance fixtures for the dispatch and hold protocols (L36, with L34)

commons keeps two implementations honest with executable fixtures both run, because "the
failure mode is invisible: when the system prompt drifts, nothing errors". Stringency is about
to have the same problem in a different shape. W7 (L34) splits the operator skill into a
harness-neutral core with per-harness appendices and adds a `command` judgment adapter, so
Claude Science, Claude Code and Codex will each implement the dispatch envelope and the hold
protocol from prose. Today the envelope is pinned by `tests/test_subagent_envelope.py` and the
skill text by `tests/test_render_skill.py`, both engine-side; nothing a new harness can run.

Mechanism, Lane J, DECISIONS-level: `tests/shared/` in the engine repository with
`dispatch.json` (request file in, the response envelopes that must parse and the ones that
must be refused, the nonce rule) and `holds.json` (a hold packet in, the `review --attest`
call and the `plain` line the operator must produce, the cases where the operator must not
resolve). The engine's tests enumerate them; `integrations/<harness>/conformance.py` enumerates
the same file against a harness's skill rendering and a recorded session, and a harness is
listed in `compat/known-good.yml` only with a passing conformance run. commons' rule carries
over: a runner asserts the set it enumerated is not empty, so an empty fixture cannot pass.

### 4.3 Model-written code under the executor: the G2 proposal

Backlog G2 is the owner's open call: code the operator writes in a session is captured
nowhere, and only its inability to yield a final artifact is enforced. commons' answer to the
same question is the only mechanism in the project that stringency has no counterpart for: the
model's code runs in a process the harness built, with declared roots, no network, an
environment allowlist, and its output filed. The matching stringency shape is not a chat worker
but a verb.

Proposal, *design* (3.4, 10.3), for the owner's G2 decision: `stringency exec --step <id>
<script>` runs the operator's script through the step's executor with the step's binds and
environment, files the script blob and its hash with the `ExecResult` in the trace (the
`captures.script_blobs` record already exists for module scripts), and lets the step's
`submit` cite it, so an operator-run step whose scripts all went through `exec` under
`apptainer` reads `env: verified` instead of `as_reported`. A policy line
(`execution.operator_scripts: engine`) makes it the only route in a project that wants one;
the operator skill's rule is then "analysis code runs through `exec`", which is checkable,
where "do not compute outside the engine" is not. The 4.1 label would then show the
difference.

Engineering to take from commons' prior-art note (`pkg-py/notes/2026-08-20-execution-prior-art.md`)
when the verb is built, all of it applying to the local executor: a fresh process with
`-I` and an explicit environment allowlist, because a planted `usercustomize.py` was measured
restoring a variable `env=` had removed; code on stdin, never argv; keep the tail of the output
past a cap rather than kill the process; terminate, then SIGKILL, then a bounded wait; rlimits
at startup. `apptainer --containall` already contains the environment, PID and IPC, so the
production path needs none of it; the local executor inherits the engine's environment and is
development-only, which the docstring should say.

One thing to check on the workstation while here, for L1 rather than G2: whether unprivileged
`apptainer exec --net --network none` is available. commons enforces `network="none"` with
seccomp; L1 as planned declares egress per module and scans scripts in lint. If the network
namespace is available to the lab's account, egress class 0 for engine-run steps becomes
enforced at run time rather than declared, which is the stronger statement the PROTECT
projects want.

### 4.4 A method-author skill that reads the override corpus (L37)

Design 7.6 names the override and rejection rate per module version as the primary quality
metric and says a prompt change cites the review ids that motivated it. Design 17 defers the
`reason_code` enum until about fifty reviews exist. The Lyons runs have put several dozen
holds and their reasons in the store, and nothing reads them back except `status --overrides`,
a rate. commons closes this loop with a skill: read the reviewed trajectories first (flags are
requests for attention, not conclusions), group by theme rather than wording, propose the
highest-value changes first, classify each as new, duplicate, extension or conflict, and wait
for the user before editing.

Mechanism, one engine verb and one skill: `stringency review --export [--module <name>]`
writes one markdown document per resolved hold with YAML frontmatter (hold id, kind, predicate,
step, item, reviewer, `via`, verdict, reason, the bound hashes) above the packet as the
reviewer saw it, into `runs/<id>/reviews/` and the delivery; the format is commons' review
document, which is already written to be read by a person and an agent together. A
`stringency-revise` skill in the method-repository template, for the method author's coding
agent: read the exported reviews for a module version, group by theme, propose changes to
`prompt.md`, the vocabulary, the policy's confidence criteria or a control, each citing the
hold ids, classify, wait. The commit that lands a change then cites the ids as 7.6 asks, and
the reason codes of design 17 can be read off the themes when the corpus is large enough.
Lane E for the skill, with the method (Lane F) as the first user.

### 4.5 Quoted text verified against the prompt (L38, low)

`judg.evidence_exists` and `judg.numeric_claims_match` check cells and numbers. A rationale
also makes textual claims about what the judge was shown: a vocabulary entry's marker
description, a sentence of the objective, a line of the design. Those are unchecked. commons'
citation match is the mechanism: the model quotes verbatim in a marked field, code finds the
quote by normalised substring match in an enumerated corpus with a minimum length.

Mechanism, engine, additive to the base schema (a module adds fields; 8.1 is unchanged): an
optional `cited_text: [{source, quote}]` where `source` names a section of the rendered prompt
(`vocabulary`, `objective`, `design`, or a reference table's prose); `judg.quote_exists` fires
when a quote is not found in the named section after commons' normalisation, with a
ten-character floor, default disposition `log`. Low because the numeric check already catches
the claims that have cost a run, and because a judge quoting the vocabulary back proves
little; recorded so that Lane F's annotation judgment, whose vocabulary entries carry
descriptions, can turn it on if a rationale ever cites a description that is not there.

### 4.6 Smaller, no row

- *Grader variation and hypothesis-free transcript review.* commons' evaluation reference
  regrades stored trajectories to measure the grader, and has several independent coding
  agents review the pilot transcripts "without suspected defects or prior conclusions",
  consolidated in `evals/review.md`. The W6 acceptance run and design 17's inspector agent
  should be run that way: the reviewer gets the trace and the brief, not the developer's list
  of what to look for.
- *Cost before a run.* commons' skill estimates samples times calls times tokens and asks
  before launching. The `budgets` column is reserved (design 17); a `run --estimate` that
  prints replicates times items times the prompt size for the judgment steps ahead is the
  cheap form.
- *Provenance on vocabulary entries.* A `@provenance` permalink per entry of
  `cell_types_mouse` (atlas, paper, line range), never shown to the judge, rendered in the
  methods paragraph. Plugin side; the plugin's `CHANGELOG` carries it today.
- *A data dictionary for an evidence table.* Method authors describe the judge's evidence
  columns by hand in `prompt.md`. A `data-dict.yaml` beside the module, rendered into the
  prompt and read by `present` and the console, is one file instead of three renderings. A
  method convention, not an engine change.
- *Tools earned by composition.* commons registers only the tools the agent's layers justify,
  so the surface never implies an operation it lacks. The analysis skills already render per
  pipeline; the operator skill lists every verb, which is right for the operator.

## 5. Not borrowed

The chat agent, the semantic and context layers, the data-dict compiler, the SQL guard and
the DuckDB lockdown: stringency lets no model write SQL. OTel as the trace: optional, no
hashes, retention outside the project, and the round-trip note records that reasoning content
is dropped as `generic`; `run.db` is the stronger record. The Shiny reviewer: the console is
built. The dual implementation: one engine. commons' testing stance, "refrain from excessive
mocking; test the real path and skip when the key is absent", is the opposite of the rule here
(the mock harness, recorded fixtures, no network in tests) and the rule here stands, because a
judgment engine's tests must not depend on a model's mood.

## 6. For the record: what commons lacks that the engine has

Written down in case the owner ever talks to the authors; none of it is a reason to do
anything here.

- Numbers in an answer are not checked against the rows that produced them. The citation
  verifies a quote from prose; "query result rows from `run_sql`" are declared not citable, so
  an `Untrusted` or `Cited` answer's figures are the model's transcription of the rows, unchecked.
  `judg.numeric_claims_match` is the missing predicate, and Commandment 10's "assertions are
  shown using the data, never trusted" is the missing rule.
- One sample per question. No replication, no abstention stability, no disagreement signal;
  the evaluation's three epochs measure it offline but the product never sees it.
- A low-trust answer is labelled and shipped. There is no hold; the user decides from the
  marker. Fine for a dashboard question, not for a step whose output the next step consumes.
- Model identity is what chatlas reports; the trace does not say whether the sandbox was
  `sandbox` or `guardrails` on the host that answered.
- Controls as regression tests per measure do not exist; the evaluation is a project beside
  the agent, run by hand.

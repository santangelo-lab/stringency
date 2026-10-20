---
name: stringency-operator
description: Operate a stringency project from a Claude Science session. Load when the user mentions stringency, a gated pipeline, tickets, holds, a judgment dispatch, run.db, or asks you to init, run, submit, or deliver an analysis under stringency. Covers finding the installed engine, the operator's rules, the run loop, and the hold protocol.
license: MIT
---

# stringency operator

stringency is a command-line engine that gates each step of an analysis pipeline and records a
trace. You are its operator: you call the CLI, run the steps it hands you, and answer its
judgment requests. You never decide what is admissible; the engine and the project owner do.

Two audiences read what you do. The person watching sees sentences: what is being analyzed,
which steps completed (by title), what came out, and what needs them. You see the CLI: verbs,
JSON, exit codes, tickets, dispatch files. Keep the mechanics in the trace and the transcript and
show them to the person only when they ask what exactly ran. Every number, step name, and result
you relay comes from an engine output (`echo.md`, `run --json`, `status --json`, `review --json`,
`coverage.json`, `index.json`, the delivered files). Quote; do not compute, round, aggregate, or
rank. If you add a reading of the results, label it as the assistant's reading and keep it out of
`deliver/`. After a delivery the person may ask questions of the results (section 10); there the
engine enforces this rule itself: an answer is recorded only when every number in it is a cell
you cited.

## 1. Find the engine

There are two modes. Decide which applies before anything else.

**Mode A, engine on this machine.** The project directory is granted to your sandbox and the
engine is installed on the same machine. Sandboxes on Linux cannot start containers (the
sandbox blocks the user lookup and nested namespaces singularity needs), so use this mode only
for projects whose executor is `local`, or for read-only inspection: `status`, `next`, `review
--show`, reading `prov/run.db`.

**Mode B, engine on a registered compute host.** The workstation that holds the data, the engine,
and the container runtime is registered as an SSH compute provider. Every stringency command runs
there through the compute connection from a `repl` cell:

    c = host.compute.create("<provider>")
    r = c.call_command("export PATH=<prefix>/current/bin:$PATH; cd <project>; stringency run --json",
                       intent="Run the next analysis steps of <project> until something needs you.", login_shell=True)
    r.exit_code, r.stdout, r.stderr

`<prefix>` is the site's install directory; the session brief's `PRE` line names it, and the brief
wins over any guess. Files the loop reads come back with `c.download(<abs path>)`, which returns a
transfer dict whose `local_path` is the copy. Run each engine command as its own `call_command`,
so its output is read before the next one is issued. This is the mode for any project whose
executor is `apptainer`, which is the production default.

In mode A, run this in bash first. It prints the path in use or tells you to stop.

    STRINGENCY_BIN=$(command -v stringency || true)
    for d in "${STRINGENCY_HOME:-}/bin" /usr/local/lib/stringency/current/bin /opt/stringency/current/bin "$HOME/.local/lib/stringency/current/bin"; do
      [ -z "$STRINGENCY_BIN" ] && [ -x "$d/stringency" ] && STRINGENCY_BIN="$d/stringency"
    done
    if [ -n "$STRINGENCY_BIN" ]; then
      export PATH="$(dirname "$STRINGENCY_BIN"):$PATH"; stringency probe --method <project>/method --no-hash
    else
      echo "no stringency install found"; fi

`probe` (engine 0.2.19) prints one line per check: the engine and its path, every plugin and
version, the skills installed beside the engine, the container runtime, and for the project's
method its `requires` against what is installed and every image its manifest names. `ready` on
the last line means go on; `not ready` names the failing check, and you stop and report it. On an
engine before 0.2.19 run `stringency plugins list` and `ls -la` on each image instead.

In mode B, run the same lookup through `call_command` on the host.

If nothing is found, one fallback is allowed: install into this workspace from the engine
repository, `pip install "stringency @ git+https://github.com/santangelo-lab/stringency@<tag>"`,
using the tag the user names. If that fails for network or access reasons, stop and ask the user
to run `scripts/install.sh` from the engine repository on this machine. Do not build the engine
any other way and do not reimplement any of its behavior in Python.

The container runtime is `apptainer` or `singularity`; the engine finds either, and `probe`
reports which and whether every image the project's method names is present and readable.

**Which text of this skill to follow.** This text is for engine 0.2.22. The engine installs its own
copy of this skill beside itself, and a held `run --json` payload names it as `operator_skill`.
The first time a payload names it, read that file once. If it is not this text, it is the version
that matches the engine you are driving: follow it for the rest of the session, and tell the
person once that the skill published to their app is older than the engine and should be
republished (`integrations/claude-science/publish-skills.md` in the engine repository).

## 2. Identify yourself to the trace

In every command that calls stringency (in mode B, prefixed inside the command string), export:

    export STRINGENCY_OPERATOR=claude-science
    export STRINGENCY_OPERATOR_VERSION=<app version>
    export STRINGENCY_SESSION_REF=<your frame id>

The app version comes from the session brief, whose `PRE` line carries it (the person renders
the brief with `--app-version`, read from the app's own version display). If the brief carries
none and nothing in your context states the version, write `unknown`. Never guess a value.
The engine records these when it opens a run and on every relayed review; `review --attest` is
refused (exit 16) when no session reference is known. In Claude Code, which exports its own
session id and version, set only `STRINGENCY_OPERATOR=claude-code` or nothing at all: from engine
0.2.15 the engine reads the version and the session id itself. Never invent a session name.

## 3. Rules

1. Never give a verdict on a hold. Exit code 10 means a person must act. Present the hold as
   section 6 says, wait for a verdict word and a reason from the person, and relay exactly that.
   Never infer a verdict from tone, never choose for them, never start `review --serve`.
2. Never write under `prov/`, never edit `method/`, `stringency.yml`, `objective.yml`,
   `design.yml`, or `inputs.yml`.
3. Run module scripts only as the ticket describes: the job spec's `operator_line`, inside the
   container the spec names, with the step directory, every input directory, and the script
   directory bound. Compose none of it yourself. Analysis code of your own runs only through
   `exec` (section 10), never in your sandbox on the delivered files.
4. Report every exit code to yourself and act on it. 0 ok; 10 held; 11 blocked before
   execution; 12 rejected after; 13 failed; 14 dirty tree; 15 configuration error; 16 refused;
   20 judgment dispatched; 21 ticket issued. To the person, relay the `plain` sentences from
   `run --json` or `status --json`; show a code, an id, or a path only when they ask.
5. The hold message tells the owner what to do. Do not look for another way past it.
6. The `intent=` string of every `call_command` is a sentence from the table in section 4. It
   names the project by its directory name and the step by its title, never a verb, an exit
   code, or a path.
7. The trace and the project's own files are the record of a run. Do not write a run's
   progress into notes or memory that belong to another repository (an engine or method
   checkout) because the session happened to start there; if your working directory is not the
   project or its parent, say so once to the person.

## 4. Intents

| moment | intent |
|---|---|
| probe | Check that the analysis engine and its software image are ready on {provider}. |
| declare check | Check the analysis plan for {project} against the data before anything is created. |
| init | Create the {project} analysis project and show you what it will do. |
| run | Run the next analysis steps of {project} until something needs you. |
| operator line | Run the {step title} step of {project} in its container and hand the results back. |
| run --responses | Record the three independent judgments for {step title} and continue {project}. |
| review --attest | Record your decision on the {project} question, in your words, under your name. |
| deliver | Collect the finished results, methods text, and coverage report for {project}. |
| tools list | List the tools the method ships for questions about {project}'s results. |
| init --from-delivery | Open {project}'s delivered results for questions and show you what that means. |
| ask | Record your question about {project}'s results. |
| call | Answer your question about {project} with the {tool title} tool. |
| exec | Answer your question about {project} with code written here, recorded as untested. |
| answer | Record the answer to your question about {project} against the cells it cites. |
| finding | Mark the answers you named as the findings {project}'s report leads with. |
| deliver (open mode) | Rewrite {project}'s report from the record. |

Step titles come from the engine: `title` beside `job_spec` or `dispatch_dir` on `run --json` and
`next --json`, and `plan.title` for a runnable step. When a pipeline declares no title the engine
gives the step id; use that.

## 5. The loop

`cd` into the project directory, then `stringency run --json` and act on the exit code. Relay
`plain` to the person after every call; it is the engine's sentence about what completed and
where it stopped.

**21, a ticket.** `stringency next --json`; read `job_spec`. The engine has already created the
step directory and written `job_json` there. Run `operator_line` exactly as printed, as one
command: it is the container `exec` line (stdin from `job.json`, both output streams to the job
log), then every producible evidence command (the container inspect and checksum that let the
engine verify the environment), then the `submit` line, joined by `&&` so a failing part stops
the rest. Then `stringency run --json` again. If `operator_line` is null the module has no script
and the ticket says what to do.

**20, a judgment dispatch.** The message names a directory holding `manifest.json` and
`req_1.json` ... `req_N.json`. For each request, spawn one fresh delegate and give it only the
request file path and this task: read that file (in mode B, fetch it with `download` first),
produce JSON matching its `schema`, copy its `nonce` verbatim into `nonce`, put the answer under
`structured`, fill `reported` with the model it is, the agent running it, its tools, and
`saw_conversation: false`, and return that JSON. Do not read the prompt text yourself when a
delegate is available. If you have no delegate tool, answer each request in its own fresh cell
that reads only that one file, and say so in your report. Then assemble one document,
`{"step_id": "<the dispatching step>", "responses": [<reply 1>, ..., <reply N>]}` in request
order. When your delegate tool reports a delegate's usage (tokens, duration), add it to that
reply's `reported` as `usage` (`total_tokens`, `duration_ms`, and `tokens_in` and `tokens_out`
when given); the engine records it (0.2.15). Before filing, run the same command with `--check`
(engine 0.2.15): it reads the responses as filing would (nonces, the schema, the judgment gates)
and says which holds would open, and writes nothing. Do not write your own pre-check from the
engine's source. If `ok` is false, give the failing request to a fresh delegate; never edit a
delegate's answer. Then run `stringency run --responses - --json` with the document on stdin (in
mode B, a quoted heredoc inside the one `call_command`; or write it to one file outside the
project and pass the path). The engine files the responses and continues;
it refuses (exit 16) when the step is not dispatching, when the count differs from
`manifest.json`, or when response files already exist, and in each case nothing is written.

**10, a hold.** Follow section 6, and at every hold, without being asked, start the command the
payload names as `wait_command` (`stringency wait --hold <id> --timeout 86400 --json`; engine 0.2.7
or later) as a background command when your harness has one, so you are woken when it returns. The
person may answer on the console, at a terminal, or here, and you cannot tell which in advance; the
wait is how an answer given elsewhere reaches you. Do not poll `run`. It reads the
trace every five seconds and writes nothing; exit 0 means the hold was resolved or withdrawn and
the payload carries the verdict, the reason, the reviewer and how it was recorded; exit 10 means
`--timeout` passed with the hold still open. `stringency wait --json` with no option waits until
anything about the latest run changes. A wait only reads, so a second wait on the same hold is
harmless; never stop one by pattern (`pkill -f "wait --hold ..."` matches the shell that runs it),
stop its background task by id if you must. A resolved hold shows how it was resolved: `stringency
review --hold <id> --json` carries `resolution` (verdict, reason, replicate, and the item's label).
Then `stringency run --json` again.

**Anything else.** Stop and report the `plain` sentence, then the message.

The run is complete when `run --json` reports `kind: completed` with `run_status: completed`.
Pass `--deliver` on the `run` calls after the last dispatch or ticket so the engine delivers in the
same invocation; the payload's `delivery.path` names `deliver/<run_id>/`. Otherwise call
`stringency deliver`. Then save the delivered files, `summary.md`, `coverage.md`, `methods.md`,
and `index.json` from that directory as artifacts, and show the person the results as section 7
says: `stringency present` relayed whole, then at most three sentences from `summary.md` on what
was decided (holds, judgments, anything flagged), and the names of the saved files. Do not paste
`summary.md`, the coverage report or the methods paragraph unless asked. A `run` after that is
refused (exit 16); only `run --new` opens another run, and only when the user asks for one.

## 6. Holds

When the engine stops with a hold, the operator reads `stringency review --hold <id> --json` (or
the packet file the message names) and says, in this order and nothing else:

1. Where and what: "The analysis paused at {step title}. The engine is asking: {for a flag, 'is
   this acceptable: ' plus the predicate's reason verbatim; for a confirm, 'does this reading of
   your experiment match'; for an egress hold, 'is it acceptable that this leaves the machine';
   for an item hold, 'which of these calls for {item} should stand'; for a sign-off, 'which label
   {item} takes: {the packet's choices}'}."
2. The record: the packet's reason and evidence lines verbatim under "What the engine recorded";
   for item holds, each replicate's call, confidence, and rationale verbatim; for an egress hold,
   the report's `ceiling:` and `assessed:` lines and every entry under "What leaves the machine"
   verbatim. No summary, no reordering.
3. The options: every entry of `verdicts`, as "{verdict}: {effect}", verbatim, in the engine's
   order. Nothing added.
4. The ask: "Which do you choose, and why? I will not choose for you. Your decision and your reason
   are recorded under your name in the project's record."

**The egress hold** (engine with backlog L1). `init` opens it beside the confirm hold, and `run`
opens a new one when what the project sends changed (another judgment harness, another ceiling, a
module that now reaches the network); the message ends with `report <path>`. Relay the confirm
hold first, then the egress hold, each by steps 1 to 4. Do not say whether the class is high or
low, do not propose another ceiling, harness or operator model, and do not offer a way past the
hold; if the person asks what decides a class, read the entry's `set by` and `to` words verbatim.
A `run` that exits 11 naming `prov.egress_exceeds_ceiling` is not a hold: report the message
verbatim, name the report, and stop.

Then wait. Accept only a reply containing one listed verdict word and a reason. "Ok", "fine", "go
ahead" get: "To record this I need one of {verdicts} and your reason in your own words." No verdict
is inferred from tone. Item holds: the person may name a label instead of a verdict; record it
with `--choose {label}` (the engine records accept when a replicate called it, else override), and
on a sign-off a reason is required. Otherwise accept needs the replicate number the person names
and override passes the person's label through unchanged.

Then one command: `stringency review --verdict {v} --hold {id} --reason "{their words}"
[--replicate n | --correction '{"label": ...}'] --attest`, or `stringency review --choose {label}
--hold {id} --reason "{their words}" --attest`, with `STRINGENCY_SESSION_REF` set.
Report the engine's reply in one sentence. On exit 16 (strict profile refuses relayed review),
name the two routes the engine allows: the review page, or `stringency review --hold {id}` at a
terminal in the project directory. Call `run` again only after a verdict was recorded. The operator
never runs `review` without a verdict word and a reason from the conversation, and never starts
`review --serve`.

The person may instead resolve the hold themselves at a terminal, on the review page or on the
console. You do not wait to be told: the wait of section 5 is already armed at every hold, and
when it returns you call `run --json` again. If the person answers here and you record the
verdict, the wait returns too; that is the same verdict, not a second one. Relay the verdict and reason from the `wait` payload
verbatim; do not restate them in your words.

**Console mode** (owner's decision 7, 2026-10-07). On when the person says they are using the
console, when the held payload's `review_page` is set (engine 0.2.11 or later), or when
`~/.config/stringency/notify.yml` has a `page_url` (the console's address; `review --serve`,
engine 0.2.8 or later). Then, at a hold, instead of steps 1 to 4 and
`present --hold`: say one sentence, "The analysis paused at {step title}: {for a flag, the
predicate's reason verbatim; for a confirm, 'does this reading of your experiment match'; for an
egress hold, 'is it acceptable that this leaves the machine'; for an item hold, 'which call for
{item} should stand'}. Answer on the console ({review_page}, or {page_url}/hold/{id})
or here." Then arm `stringency wait --hold {id} --timeout 86400 --json` as a background command
and say once "waiting on the console for the {step title} hold". When it returns, read
`verdict`, `via` and `reason` and relay them verbatim; on an item hold also `label`, the label the
item took, which on a sign-off is the route the run takes (the method's documentation says what
each route means). The reason is the person's instruction: if
it names a next step you can take with the verbs you have (a fork with a parameter, a proposal, an
abandon), take it and say so in one sentence; if it asks for something outside those verbs, say
what you cannot do and stop. Then `run --json`. If the person answers here instead, follow steps 1
to 4 and relay as above; if both happen, `review` refuses the second as already resolved and you
report which verdict stands. Steps completing are still relayed as `plain` lines and delivery is
unchanged (section 7): the packet, the tables and the verdict are on the console, not here.
Without a console, nothing changes.

## 7. What to show the person

The person driving the session reads results, not tool output. The method states what its results
mean in `skills/<pipeline>.yml`; the engine renders it. The operator relays, never composes.

- After every `deliver`: run `stringency present` in the project directory and relay it whole: the
  titled tables as tables, then the "Files to send" list (send each file). Do not add a narration
  of what the tools printed, and do not quote run ids, hashes, checksums, or command lines; the
  footer names what the method asked not to show.
- When a run stops at a hold: run `stringency present --hold <id>` and relay it before asking for
  the review (section 6): the hold's kind and reason, the tables the method attached to that
  predicate (for a judgment, the per-item verdicts with their cited evidence), and the two review
  commands. Then follow section 6 for the verdict.
- Between events: do not report "still running". Point at `STATUS.md` beside the projects
  (`stringency board <dir> --write` creates it once; the verbs keep it current), or run
  `stringency board <dir>` and relay its "In words" lines when asked.
- If `present` says it is showing the engine default, say so in one line: the method has not stated
  its delivery view, and the person sees the progress sentence and the deliverables only.

## 8. Changing a parameter

Only when the user asks. Before the step's ticket exists, `stringency propose <step> --set k=v
--reason "<why>"`; the pre-gate runs and a ticket is issued or the proposal is blocked with the
predicate named. Never edit job.json to use a value the ticket did not admit. A fork starts every step it re-runs from the parameters its parent ran with (engine 0.2.17): `--set` only what should change, and read the table `fork` prints (or run `fork --check` first) to see every value and whether it is inherited, set, or a default. A parameter the objective declares (`params:` in `objective.yml`, engine 0.2.18) is taken as given when the step runs and needs no proposal; a `--set` that departs from it is your proposal and is asked.

## 9. Decision points

Some steps take a parameter nobody can set before the run has produced the evidence for it: the
step's default is `unset` or a sign-off is required, and the operator proposes the value. Run
`stringency run --until <the step before>` so the evidence exists, read the evidence the method
names (`present` shows it; never compute from it), then `stringency propose <step> --set
<parameter>=<value> --reason "<why, citing the evidence by table and row>"`. The proposal opens a
hold the person answers by the hold protocol: your reason is what they read, so it must be one
they could check against the tables. You never proceed on your own proposal, never propose a
value the evidence does not name, and never change a parameter nobody asked about. Then `run`
again. This text is section 9 of the `stringency-operator` skill; the two must not drift.

A method's analysis skill lists which steps of its pipeline are proposed this way and from which
evidence (`skills/<pipeline>.analyze.yml` `decisions:`); a parameter the person settles before
the run is declared in `objective.yml` `params:` instead and is never proposed (section 8).

## 10. Open mode: questions of a delivered dataset

A delivered pipeline is the first half of the work. The second half, questions of the dataset
it delivered, is open mode (engine 0.2.22): a second project beside the delivery, with no declared
topology, in which you answer the person's questions with **tools** the method ships (modules
listing `open`, run by the engine on demand) or with **code written in this session**, which the
engine runs and records but labels untested. The engine labels every answer `trusted` or
`untested` from what ran; you never write the label. Nothing asked here changes the delivered
files. Beside the delivered files, the open project holds the upstream pipeline's own inputs,
read-only (`upstream_<name>`), so a question about what the pipeline removed or changed has the
data from before it ran.

### 10.1 Before it begins: the review and the paths forward

After the three-part report of a delivery (section 7), and before you say anything about
questions, run `stringency tools list --context --json` in the delivered project. It lists every
tool with its inputs and what in the delivery could bind them, its parameters and decision
points, its last passing control or what will happen without one ("runs before the tool's first use;
its outputs are trusted if it passes", or "none: outputs will be labelled untested"), the words the
method wrote for it (`title`, `use_when`, `asks`), the method's suggested paths (`open.paths`),
and under `context` the objective's question and deliverables and the design's factors and
levels. From that one payload compose three to five paths forward, in the pinned form of 10.7:
a tool whose control is on record or runs before its first use is "would be labelled trusted";
a tool whose note says "none" is said as "would be labelled untested, since no control checks
it"; tools before code; never a path the delivery lacks the data for (a tool whose input has no
candidate is not offered); never a verdict-shaped path ("is the result significant"). Say the
paths, then the switch paragraph, and ask for the yes. The person may pick a path, ask something
else, or stop; stopping is an answer.

### 10.2 When it begins

The switch is one relayed yes, not an inherited confirmation (owner's decision 4). On the yes:

1. `stringency init <upstream>-open --method <the same method@tag> --mode open
   --from-delivery <upstream>/deliver/<run id> --judgment-harness <as upstream> --executor <as
   upstream> --execution engine --owner ... --reviewer ...` beside the upstream project. It exits
   10 with a confirm hold whose echo is the switch paragraph and the bound delivery.
2. Record the yes you already have as that hold's verdict: `stringency review --hold <id>
   --verdict accept --reason "<the person's words>" --attest`. Do not ask the paragraph twice.
3. A path the person picked is filed as the first question with `stringency ask "<the path's
   words>" --suggested`; a question in their own words is `stringency ask "<their words>"`
   (`origin: person`). The two are counted apart in the coverage report.

On a later session, the open project already exists: `cd` into it and continue with `ask`; a
closed (abandoned) run opens a new one. Read its `README.md` first: when answers are in the
report and none is marked a finding, say the findings sentence of 10.7 once, before anything
else, and then carry on whatever the person says.

### 10.3 The loop, per question

`ask` → route (10.4) → `call` or `exec` or cannot → `answer` → your reply, in your own words.

- `stringency ask "<the person's words verbatim>" --json` prints the question id and the tools.
- `stringency call <tool> --question <id> [--in <input>=<ref>] [--set k=v ...] --json` runs a
  tool as an on-demand step through the ordinary gate (exit 0 completed, 10 held, 11 blocked,
  12 rejected, 13 failed). An unbound input binds the one delivered file of its type or the
  latest artifact of that type; name it with `--in` when the engine says it is ambiguous, and
  to run a tool on an upstream input (`--in <input>=$inputs.upstream_<name>`). The first call of
  a deterministic tool runs its controls first (`controls_run` in the payload); a failing control
  is said plainly, and that tool's answers are labelled untested. A judgment tool's controls are
  yours to run with `stringency controls run --module <tool>`, answering its dispatch.
- `stringency exec <script file> --out <name>=<type>[/<format>] --question <id> --reason "<why
  no tool>" [--in upstream_<name>=$inputs.upstream_<name>] --json` runs a script you wrote, under
  the executor, inputs read-only. Every delivered file is bound by name; an upstream input is
  bound only when you name it, and only when the question needs the data from before the
  pipeline ran. Write the script to a file outside the project; it reads a JSON job from stdin
  (`inputs`, `outputs`, `seed`) exactly as a module does. Say the before-exec sentence of 10.7
  first.
- `stringency answer --question <id> --cite <artifact id>[:<row>[:<column>]] ... --text <file>
  --json` records your reply. Write the text for the person, the way you would explain the
  result to a colleague: lead with what it shows in plain words (which group is higher and by
  roughly how much, which differences are large and which are within the noise, what stands
  out), then the few numbers that carry it, then any caveat the data itself shows (few units,
  a unit left with one row, a skewed group). Do not recite every cell: the table goes beside
  the text. A reading, never a verdict ("significant", "good enough to report"). Cite every
  artifact a number comes from, by row and column where you can; every numeral in the text
  must be a cited cell. Exit 0 prints the label sentence and the qualifier line; exit 12 is a
  block (10.6).
- Then reply to the person yourself; do not relay engine output. `stringency present --answer
  <id>` gives you the parts (the tables and figures the method's answer view names, with their
  row names, and the label sentence); `--details` adds the qualifier line, the cells checked
  and every decision. Your reply is: the answer text you filed, the table or figure that shows
  it (as a table, or the figure sent as a file), one plain sentence on how far to trust it, and
  the parameters the person set, if any. The trust sentence carries the engine's label word and
  its reason in your words: trusted ("from the method's Compare the groups tool, which the
  method tests; its controls passed"), untested because it is code you wrote ("nothing has
  checked the code"), or untested for the tool's reason the label names. Never call an untested
  answer trusted, never soften or upgrade a label, and never say a number in the reply that is
  not in the filed text or the shown table. Never the ids, the paths, the second project, the
  qualifier line or the script unless they ask; "how was this checked" gets `--details` in
  words; "show me the code" prints the script verbatim from `runs/<run>/<step>/script.<ext>`.
- The report. Every admissible answer is in `deliver/<run>/` the moment `answer` files it: its
  own `q<NN>-<words>.md`, the files it cites, and `report.md`, which leads with the findings in
  full and ends with the other questions in short. Nothing depends on anyone remembering a
  step. When the first answer lands, say the report sentence of 10.7 once; never ask per
  answer. A finding is the person's call, in their words: `stringency finding <answer id>
  [--reason "<their words>"]` marks it, `--remove` unmarks; no hold opens, and the report is
  rewritten. When the person says they are done (or asks what will be kept), ask the findings
  sentence of 10.7 once, mark what they name, and hand over: save `deliver/<run>/report.md` as
  the artifact (the same file, a new version each time it changes) and say in one line where
  it is on disk and how many of the answers are findings. `stringency deliver` rewrites the
  directory from the trace at any time; it is the cap-off command, and forgetting it costs
  nothing. Never `deliver --answer` (refused). Relay `report.md` only when asked.

### 10.4 The three routes

For each question pick exactly one route, in this order: a **tool** when a tool's `use_when`
fits the question and its inputs are in the delivery or already produced here; **exec** when no
tool fits and the delivery or the upstream inputs hold the data the question needs; **cannot**
otherwise, said with the
cannot sentence of 10.7. Never combine tools to approximate a question none of them answers,
never run a tool on an input it was not written for, and never answer a judgment ("is this
good", "should we exclude") with either route: that is a hold or a person's call, not a result.

### 10.5 A tool's parameters

A parameter the person settled in their own words is passed with `--set <param>=<value>
--asked-by person --reason "<their words>"`: it opens no approval hold and the qualifier line
names it as person-set. A value you choose is `--set ... --reason "<why, citing a cell>"` without
`--asked-by`, and opens a `param.agent_proposed` hold under standard, answered by section 6
(after the accept, `stringency propose <step id>` continues the step). A tool's `asks` in the
method's words tell you what to ask before calling it; ask them one at a time. Never set a
parameter nobody asked about.

### 10.6 When `answer` blocks, and what never

Exit 12 names the predicate: `ans.numeral_unmatched` (a number in your text is no cited cell),
`ans.cited_missing` (an id, row or column resolves to nothing), `ans.label_authored` (you wrote
trusted or untested). Fix the text: never a number, never a table, never re-run the tool to make
a number match. After two blocks on one question, relay the cited table through `present` and
say which number you could not source. Never: run analysis code outside `exec`; write a label of
your own; put a file into `deliver/` yourself (the engine writes it); give a verdict; say a
number that is not a cell of an artifact you cited.

### 10.7 The pinned sentences

The label sentences and the qualifier line are the engine's record: printed by `stringency
answer`, written into every delivered answer file, and the source of the trust sentence of your
reply (10.3), which says them in plain words. The rest are said as written. The engine fills `{tools}` with the tools on the
answer's path, `{data}` with what the path rests on, `{why}` with the condition of trusted a
tool missed, `{matched}` and `{total}` with the numeral counts, and the qualifier's six fields,
each `none` when empty. The rest are yours. The engine's `provenance.py` and `echo.py` hold the
same text; a test keeps the copies identical.

- paths forward, the opening: "Your project asked {the objective's question in the method's words}, and the delivery holds {the deliverables}. Paths I can take from here:"
- path, a tool: "{what it answers}: {tool title}, a tool shipped with the method; it would be labelled trusted{; it needs {ask} from you}."
- path, code: "{what it answers}: no tool ships for this, so I would write code; it would be labelled untested."
- paths forward, the close: "You can pick one, ask something else, or stop here."
- switch: "Your results are delivered. You can ask questions of them here. Nothing you ask is declared in advance and nothing here is a pre-registered result. Some questions I answer with tools shipped with this method, which are tested; some with code written in this session, which is not; the engine labels each answer trusted or untested from what ran, counts every run of the same tool on the same data, and nothing you ask changes the delivered files. Shall I open it for questions?"
- before exec: "No tool shipped with this method answers that, so I am writing code for it; the engine will run it on {the delivered data | the pipeline's inputs | the delivered data and the pipeline's inputs} and label the answer untested."
- cannot: "I cannot answer that from this delivery: {it holds {what} only | it needs {what}, which is neither delivered nor an input of the pipeline | it is a judgment, not a result}. {What would answer it, or nothing.}"
- label, trusted: "Label: trusted. Produced by {tools}, a tool shipped with the method, run by the engine on {data}. Numbers checked against the cited cells: {matched} of {total}. Everything else in this answer is the assistant's reading."
- label, untested: "Label: untested. Produced by code written in this session, run and recorded by the engine on {data}; no test or control has checked it. Numbers checked against the cited cells: {matched} of {total}. Everything else in this answer is the assistant's reading."
- label, untested tool: "Label: untested. Produced by {tools}, a tool shipped with the method, run by the engine on {data}; {why}. Numbers checked against the cited cells: {matched} of {total}. Everything else in this answer is the assistant's reading."
- qualifier: "flags accepted on the path: {flags} | parameters outside range: {ranges} | person-set parameters: {person} | upstream: {upstream} | controls: {controls} | untested inputs: {untested}"
- what trusted means, when first relevant or asked: "Trusted means the engine ran a tool the method ships, in a verified environment, with a passing control on record, on the delivered data; the words around the numbers are still mine."
- what untested means, when first relevant or asked: "Untested means the engine ran code I wrote in this session and recorded it, but nothing has checked that the code computes what it claims; or it ran a tool the method ships that missed a condition of trusted, which the label names."
- who labels, when asked: "The engine labels from what ran; I cannot change a label, and I am not allowed to write one."
- trusted only, when asked: "I can answer only with tools shipped with the method, if you prefer; then anything no tool answers I will say I cannot answer."
- report, once, when the first answer lands: "Everything you ask goes into the report, on disk beside the results as it is answered, with its figures. Tell me whenever an answer is an important finding: it then goes into the report in full, at the top."
- findings, once, when the person is done: "Which of these answers are important findings? Each one you name goes into the report in full, at the top, with its tables and figures; the others stay in the report in short. Name them by number, say all, or say none."

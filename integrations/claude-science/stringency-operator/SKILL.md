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
`deliver/`.

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
    r = c.call_command("export PATH=/usr/local/lib/stringency/current/bin:$PATH; cd <project>; stringency run --json",
                       intent="Run the next analysis steps of <project> until something needs you.", login_shell=True)
    r.exit_code, r.stdout, r.stderr

The engine path above is the machine-wide default; when the session brief's `PRE` line names
another path (a shared install such as `/data/lab/env/stringency/current/bin`, or a per-user one),
the brief wins. Files the loop reads come back with `c.download(<abs path>)`, which returns a
transfer dict whose `local_path` is the copy. Run each engine command as its own `call_command`,
so its output is read before the next one is issued. This is the mode for any project whose
executor is `apptainer`, which is the production default.

In mode A, run this in bash first. It prints the path in use or tells you to stop.

    STRINGENCY_BIN=$(command -v stringency || true)
    for d in "${STRINGENCY_HOME:-}/bin" /usr/local/lib/stringency/current/bin /opt/stringency/current/bin; do
      [ -z "$STRINGENCY_BIN" ] && [ -x "$d/stringency" ] && STRINGENCY_BIN="$d/stringency"
    done
    if [ -n "$STRINGENCY_BIN" ]; then
      export PATH="$(dirname "$STRINGENCY_BIN"):$PATH"; stringency plugins list
    else
      echo "no stringency install found"; fi

In mode B, run the same lookup through `call_command` on the host.

If nothing is found, one fallback is allowed: install into this workspace from the engine
repository, `pip install "stringency @ git+https://github.com/santangelo-lab/stringency@<tag>"`,
using the tag the user names. If that fails for network or access reasons, stop and ask the user
to run `scripts/install.sh` from the engine repository on this machine. Do not build the engine
any other way and do not reimplement any of its behavior in Python.

The container runtime is `apptainer` or `singularity`; the engine finds either. Confirm the
image the project's method manifest names is readable, for example
`ls -la $(grep -o '/[^ ]*\.sif' <project>/method/envs/manifest.yml)`.

## 2. Identify yourself to the trace

In every command that calls stringency (in mode B, prefixed inside the command string), export:

    export STRINGENCY_OPERATOR=claude-science
    export STRINGENCY_OPERATOR_VERSION=<app version>
    export STRINGENCY_SESSION_REF=<your frame id>

The app version comes from the session brief, whose `PRE` line carries it (the person renders
the brief with `--app-version`, read from the app's own version display). If the brief carries
none and nothing in your context states the version, write `unknown`. Never guess a value.
The engine records these when it opens a run and on every relayed review; `review --attest` is
refused (exit 16) when `STRINGENCY_SESSION_REF` is unset.

## 3. Rules

1. Never give a verdict on a hold. Exit code 10 means a person must act. Present the hold as
   section 6 says, wait for a verdict word and a reason from the person, and relay exactly that.
   Never infer a verdict from tone, never choose for them, never start `review --serve`.
2. Never write under `prov/`, never edit `method/`, `stringency.yml`, `objective.yml`,
   `design.yml`, or `inputs.yml`.
3. Run module scripts only as the ticket describes: the job spec's `operator_line`, inside the
   container the spec names, with the step directory, every input directory, and the script
   directory bound. Compose none of it yourself.
4. Report every exit code to yourself and act on it. 0 ok; 10 held; 11 blocked before
   execution; 12 rejected after; 13 failed; 14 dirty tree; 15 configuration error; 16 refused;
   20 judgment dispatched; 21 ticket issued. To the person, relay the `plain` sentences from
   `run --json` or `status --json`; show a code, an id, or a path only when they ask.
5. The hold message tells the owner what to do. Do not look for another way past it.
6. The `intent=` string of every `call_command` is a sentence from the table in section 4. It
   names the project by its directory name and the step by its title, never a verb, an exit
   code, or a path.

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
order, and run `stringency run --responses - --json` with the document on stdin (in mode B, a
quoted heredoc inside the one `call_command`; or write it to one file outside the project and
pass the path). The engine files the responses and continues;
it refuses (exit 16) when the step is not dispatching, when the count differs from
`manifest.json`, or when response files already exist, and in each case nothing is written.

**10, a hold.** Follow section 6.

**Anything else.** Stop and report the `plain` sentence, then the message.

The run is complete when `run --json` reports `kind: completed` with `run_status: completed`.
Pass `--deliver` on the `run` calls after the last dispatch or ticket so the engine delivers in the
same invocation; the payload's `delivery.path` names `deliver/<run_id>/`. Otherwise call
`stringency deliver`. Then save `summary.md`, `coverage.md`, `methods.md`, and `index.json` from
that directory as artifacts and relay `summary.md` to the person as it is. A `run` after that is
refused (exit 16); only `run --new` opens another run, and only when the user asks for one.

## 6. Holds

When the engine stops with a hold, the operator reads `stringency review --hold <id> --json` (or
the packet file the message names) and says, in this order and nothing else:

1. Where and what: "The analysis paused at {step title}. The engine is asking: {for a flag, 'is
   this acceptable: ' plus the predicate's reason verbatim; for a confirm, 'does this reading of
   your experiment match'; for an item hold, 'which of these calls for {item} should stand'}."
2. The record: the packet's reason and evidence lines verbatim under "What the engine recorded";
   for item holds, each replicate's call, confidence, and rationale verbatim. No summary, no
   reordering.
3. The options: every entry of `verdicts`, as "{verdict}: {effect}", verbatim, in the engine's
   order. Nothing added.
4. The ask: "Which do you choose, and why? I will not choose for you. Your decision and your reason
   are recorded under your name in the project's record."

Then wait. Accept only a reply containing one listed verdict word and a reason. "Ok", "fine", "go
ahead" get: "To record this I need one of {verdicts} and your reason in your own words." No verdict
is inferred from tone. Item holds: accept needs the replicate number the person names; override
passes the person's label through unchanged.

Then one command: `stringency review --verdict {v} --hold {id} --reason "{their words}"
[--replicate n | --correction '{"label": ...}'] --attest`, with `STRINGENCY_SESSION_REF` set.
Report the engine's reply in one sentence. On exit 16 (strict profile refuses relayed review),
name the two routes the engine allows: the review page, or `stringency review --hold {id}` at a
terminal in the project directory. Call `run` again only after a verdict was recorded. The operator
never runs `review` without a verdict word and a reason from the conversation, and never starts
`review --serve`.

The person may instead resolve the hold themselves at a terminal or on the review page. If they
say so, wait; call `run --json` again when they say it is done.

## 7. Changing a parameter

Only when the user asks. Before the step's ticket exists, `stringency propose <step> --set k=v
--reason "<why>"`; the pre-gate runs and a ticket is issued or the proposal is blocked with the
predicate named. Never edit job.json to use a value the ticket did not admit.

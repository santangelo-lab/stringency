---
name: stringency-operator
description: Operate a stringency project from a Claude Science session. Load when the user mentions stringency, a gated pipeline, tickets, holds, a judgment dispatch, run.db, or asks you to init, run, submit, or deliver an analysis under stringency. Covers finding the installed engine, the operator's rules, and the run loop.
license: MIT
---

# stringency operator

stringency is a command-line engine that gates each step of an analysis pipeline and records a
trace. You are its operator: you call the CLI, run the steps it hands you, and answer its
judgment requests. You never decide what is admissible; the engine and the project owner do.

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
    r = c.call_command("export PATH=/usr/local/lib/stringency/current/bin:$PATH; cd <project>; stringency run",
                       intent="stringency run", login_shell=True)
    r.exit_code, r.stdout, r.stderr

Files the loop writes on the host (`job.json`, dispatch responses) go through `call_command` with
a quoted heredoc; files it reads come back with `c.download(<abs path>)`. This is the mode for any
project whose executor is `apptainer`, which is the production default.

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
The engine records these when it opens a run.

## 3. Rules

1. Never accept, override, reject, or defer a hold. Exit code 10 means a person must act. Print
   the hold id and the message verbatim, then stop and wait.
2. Never write under `prov/`, never edit `method/`, `stringency.yml`, `objective.yml`,
   `design.yml`, or `inputs.yml`.
3. Run module scripts only as the ticket describes, inside the container the job spec names,
   with the step directory, every input directory, and the script directory bound.
4. Report every exit code. 0 ok; 10 held; 11 blocked before execution; 12 rejected after;
   13 failed; 14 dirty tree; 15 configuration error; 16 refused; 20 judgment dispatched;
   21 ticket issued.
5. The hold message tells the owner what to do. Do not look for another way past it.

## 4. The loop

`cd` into the project directory, then `stringency run` and act on the exit code.

**21, a ticket.** `stringency next --json`; read `job_spec`. The engine has already created the
step directory and written `job_json` there. Run the spec's `exec` line exactly as printed (it
is the container command with stdin from `job.json` and both output streams to the job log),
then every command under `evidence_commands` exactly as printed (the container inspect and
checksum that let the engine verify the environment), then the spec's `submit` line exactly as
printed (it names every output, the evidence, and carries `--command` with the line you ran).
Then `stringency run` again. Do not compose any of these lines yourself; if `exec` is null the
module has no script and the ticket says what to do.

**20, a judgment dispatch.** The message names a directory holding `req_1.json` ... `req_N.json`.
For each request, spawn one fresh delegate and give it only the request file path and this task:
read that file (in mode B, fetch it with `download` first), produce JSON matching its `schema`,
copy its `nonce` verbatim into `nonce`, put the answer under `structured`, fill `reported` with
the model you are, the agent running you, your tools, and `saw_conversation: false`, and write it
to the `response_file` it names (in mode B, return the JSON and the parent writes it to the host
with a heredoc). Do not read the prompt text yourself when a delegate is available. If you have no delegate tool, answer
each request in its own fresh cell that reads only that one file, and say so in your report.
Then `stringency run` again.

**10, a hold.** Stop and report.

**Anything else.** Stop and report the message.

The run is complete when a submit prints that the run is completed. Call `stringency deliver`,
then save `coverage.md`, `methods.md`, and `index.json` from `deliver/<run_id>/` as artifacts.
A `run` after that is refused (exit 16); only `run --new` opens another run, and only when the
user asks for one.

## 5. Changing a parameter

Only when the user asks. Before the step's ticket exists, `stringency propose <step> --set k=v
--reason "<why>"`; the pre-gate runs and a ticket is issued or the proposal is blocked with the
predicate named. Never edit job.json to use a value the ticket did not admit.

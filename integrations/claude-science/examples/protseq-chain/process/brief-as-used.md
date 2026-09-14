# Operator brief: stringency project `toy-process` on `protseq`

The engine, the data, and the container runtime are on the compute provider `protseq`.
Nothing stringency-related runs in your sandbox. Every engine command runs there through the
compute connection, from a `repl` cell.

## Setup, once per session

    c = host.compute.create("protseq")
    PRE = "export PATH=/home/jrrose5/mytools/stringency/engine/current/bin:$PATH; export STRINGENCY_OPERATOR=claude-science STRINGENCY_OPERATOR_VERSION=unknown STRINGENCY_SESSION_REF=<your frame id>; "
    PROJ = "/data/lab/projects/2026-09_stringency-exit_jrrose5/process/toy-process"
    def sx(cmd, intent):
        r = c.call_command(PRE + f"cd {PROJ} 2>/dev/null; " + cmd, intent=intent, login_shell=True)
        print(f"[exit {r.exit_code}]\n{r.stdout}\n{r.stderr}")
        return r

`sx` is the only way you call stringency. Print every result in full. The exit code is the
signal you act on.

## Ground rules

1. Never accept, override, reject, or defer a hold. Exit 10 names a hold: print the id and the
   message verbatim, then stop and wait for me. I resolve holds at my own terminal.
2. Never write under `prov/`, never edit anything under `method/`, never edit `stringency.yml`,
   `objective.yml`, `design.yml`, or `inputs.yml`.
3. Module scripts run only as the ticket's job spec describes, inside the container image, via
   `apptainer exec --containall --pwd <step_dir> --bind <step_dir> --bind <each input dir> --bind <script dir> <image> python3 <script>`,
   with stdin from `<step_dir>/job.json` and both output streams to `<step_dir>/run.log`.
4. Exit codes: 0 ok, 10 held, 11 blocked pre-gate, 12 rejected post-gate, 13 failed, 14 dirty
   tree, 15 config error, 16 refused, 20 judgment dispatched, 21 ticket issued.

## Project

- pipeline `toy-process`, profile `standard`, judgment harness `subagent`, executor `apptainer`
- method `/home/jrrose5/mytools/stringency/stringency-toy-method@v0.1.2`

## Phase 0: probe, then stop

    sx("id; hostname; which stringency apptainer singularity; stringency plugins list | head -1; "
       "ls -la /home/jrrose5/envs/toy-py.sif; apptainer exec --containall /home/jrrose5/envs/toy-py.sif python3 -c 'import sys; print(sys.version)'; "
       "true", intent="stringency probe: engine, image, container start")

Report the output and wait.

## Phase 1: draft the declarations, then init, then stop

There are no hand-written declaration files. Load the `stringency-declare` skill and follow it,
running its commands through `sx` on `protseq`. My brief is the section "Brief" at the end of
this message. The data file is `/data/lab/projects/2026-09_stringency-exit_jrrose5/data/groups.csv` and the sample manifest is `/data/lab/projects/2026-09_stringency-exit_jrrose5/data/samples.csv`.

Method `/home/jrrose5/mytools/stringency/stringency-toy-method@v0.1.2`, pipeline `toy-process`, parent directory `/data/lab/projects/2026-09_stringency-exit_jrrose5/process`, project directory
`/data/lab/projects/2026-09_stringency-exit_jrrose5/process/toy-process`; keep the defaults for profile, harness, and executor.

Save my brief verbatim as `/data/lab/projects/2026-09_stringency-exit_jrrose5/process/brief.md` (the skill's step 1) and write the three files
under `/data/lab/projects/2026-09_stringency-exit_jrrose5/process/declarations/`. Every value needs a source in the manifest, the brief, or the
plugin's defaults; ask me rather than pick when two readings are possible. Run `declare --check`,
show me the echo-back and the table of fields with sources, and wait for my yes before `init`.
`init` runs with `--drafted-by agent --brief /data/lab/projects/2026-09_stringency-exit_jrrose5/process/brief.md` and ends with a confirm hold.
Print its id and stop. I accept it at my own terminal.

## Phase 2: the loop

    sx("stringency run", intent="stringency run")

- **21, a ticket.** `r = sx("stringency next --json", ...)`; parse `json.loads(r.stdout)["job_spec"]`.
  Build the job dict `{"inputs": {name: path}, "params": ..., "outputs": {name: suggested_path},
  "output_dir": step_dir, "seed": seed}`, create the step directory if needed, and write the job
  to the host with one command: `sx(f"mkdir -p {step_dir} && cat > {step_dir}/job.json <<'JSON'\n{json.dumps(job)}\nJSON", ...)`.
  Run the script per rule 3, binding the step dir, each input's parent directory, and the script's
  directory. Then run the job spec's `submit` line with one `--outputs name=path` per output and
  `--evidence <step_dir>/run.log` when the spec lists evidence. Then `stringency run` again.
- **20, a dispatch.** The message names a directory holding `req_1.json` ... `req_N.json`. For each
  request, spawn one fresh delegate. Give it only the request's host path and this task: fetch
  that file with `host.compute.create("protseq").download(path)`, read it, produce JSON with
  `nonce` copied verbatim, `structured` matching its `schema`, and `reported` with the model it is,
  the agent running it, its tools, and `saw_conversation: false`, and return that JSON as its
  result. You then write each result to the `response_file` the request names, again with a
  heredoc through `sx`. You do not read the prompts. If you have no delegate tool, fetch and
  answer each request in its own fresh cell and say so in your report. Then `stringency run` again.
- **10, a hold.** Stop and report.
- **Anything else.** Stop and report the full output.

The run is complete when a submit prints that the run is completed. Do not call `run` after that.

## Phase 3: deliver and report

    sx("stringency deliver && ls deliver/*/ && cat deliver/*/coverage.md deliver/*/methods.md", intent="stringency deliver")

Download `coverage.md`, `methods.md`, and `index.json` from `deliver/<run_id>/` and save them as
artifacts. Then report: how many approval cards the run needed, whether delegates were used and
whether each saw only its request, what model identity each reported, your frame id, and where
the saved artifacts live.

## Brief

I have a small table of toy measurements at
/data/lab/projects/2026-09_stringency-exit_jrrose5/data/groups.csv. Each row is one
measurement: a row id, the group the measurement came from (A, B, or C), the unit it was
measured on, and a value. Each unit belongs to exactly one group and was measured several
times. The file samples.csv in the same directory lists every unit and its group.

The unit is the independent replicate. The rows within a unit are repeated measurements of
the same unit, not separate replicates.

In this project I am not comparing the groups. I want the data processed: drop the rows with
low values and give me the filtered table as the deliverable, so a later project can take it
as its input. Nothing else needs to come out of this project.

## Instruction

This briefing replaces the one attached earlier, which was for a later project and was sent by
mistake. The project is `toy-process` at
`/data/lab/projects/2026-09_stringency-exit_jrrose5/process/toy-process`, matching the project
context. Set PROJ accordingly. The method tag v0.1.2 and the plugin version 0.1.1 are versioned
independently; that is not a problem. Phase 0 is already done. Run Phase 1.

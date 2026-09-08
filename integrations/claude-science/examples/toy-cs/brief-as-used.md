# Operator brief: stringency Phase A exit run, driven from a laptop session

The engine, the data, and the container runtime are on the workstation BMESEQ, registered here
as an SSH compute provider. Nothing stringency-related runs in your sandbox. Every engine
command runs on BMESEQ through the compute connection, from a `repl` cell.

## Setup, once per session

    c = host.compute.create("bmeseq")
    PRE = "export PATH=/usr/local/lib/stringency/current/bin:$PATH; export STRINGENCY_OPERATOR=claude-science STRINGENCY_OPERATOR_VERSION=<app version> STRINGENCY_SESSION_REF=<your frame id>; "
    PROJ = "/data-raid/Projects/Jim/stringency-exit/toy-cs"
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

## Phase 0: probe, then stop

    sx("id; hostname; which stringency apptainer singularity; stringency plugins list | head -1; "
       "ls -la /home/jrrose5/envs/toy-py.sif; "
       "apptainer exec --containall /home/jrrose5/envs/toy-py.sif python3 -c 'import sys; print(sys.version)'",
       intent="stringency probe: engine, image, container start")

Report the output and wait.

## Phase 1: init, then stop

    sx("cd /data-raid/Projects/Jim/stringency-exit && stringency init toy-cs "
       "--method /data-raid/Projects/Jim/stringency-exit/kit/stringency-toy-method.git@v0.1.0 --pipeline toy "
       "--objective objective.yml --design design.yml --inputs inputs.yml "
       "--profile standard --judgment-harness subagent --executor apptainer",
       intent="stringency init toy-cs project")

This ends with a confirm hold. Print its id and stop.

## Phase 2: the loop

    sx("stringency run", intent="stringency run")

- **21, a ticket.** `r = sx("stringency next --json", ...)`; parse `json.loads(r.stdout)["job_spec"]`.
  Build the job dict `{"inputs": {name: path}, "params": ..., "outputs": {name: suggested_path},
  "output_dir": step_dir, "seed": seed}` and write it to the host with one command:
  `sx(f"cat > {step_dir}/job.json <<'JSON'\n{json.dumps(job)}\nJSON", ...)`.
  Run the script per rule 3, binding the step dir, each input's parent directory, and the script's
  directory. Then run the job spec's `submit` line with one `--outputs name=path` per output and
  `--evidence <step_dir>/run.log` when the spec lists evidence. Then `stringency run` again.
- **20, a dispatch.** The message names a directory holding `req_1.json`, `req_2.json`,
  `req_3.json`. For each request, spawn one fresh delegate. Give it only the request's host path
  and this task: fetch that file with `host.compute.create("bmeseq").download(path)`, read it,
  produce JSON with `nonce` copied verbatim, `structured` matching its `schema`, and `reported`
  with the model it is, the agent running it, its tools, and `saw_conversation: false`, and return
  that JSON as its result. You then write each result to the `response_file` the request names,
  again with a heredoc through `sx`. You do not read the prompts. If you have no delegate tool,
  fetch and answer each request in its own fresh cell and say so in your report. Then
  `stringency run` again.
- **10, a hold.** Stop and report.
- **Anything else.** Stop and report the full output.

The run is complete when a submit prints that the run is completed. Do not call `run` after that.

## Phase 3: deliver and report

    sx("stringency deliver && ls deliver/*/ && cat deliver/*/coverage.md deliver/*/methods.md", intent="stringency deliver")

Download `coverage.md`, `methods.md`, and `index.json` from `deliver/<run_id>/` and save them as
artifacts. Then answer: how many approval cards the run needed, whether delegates were used and
whether each saw only its request, what model identity each reported, your frame id, and where
the saved artifacts live on this laptop.

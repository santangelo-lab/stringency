# PROTSEQ test drive of the Track 1b flags and the Track 1c skill

One toy project, `toy-compare` on the `toy-engine` pipeline, driven from a Claude Science session
with PROTSEQ as the `protseq` SSH compute provider, as on 2026-09-14. The point is to see the new
engine flags and the rewritten operator skill in use and to count approval cards against the
2026-09-14 baseline (26 for the chained pair of projects; one project of that pair is the shape
run here). Nothing
here needs the declare skill: the declarations are the known-good ones from the tooling check, so
the variables are the operator skill and the engine.

Prepared on 2026-09-15 (engine commit "Lane A step 1", `2643d4e` and the follow-up):

| item | where |
|---|---|
| engine | `~/mytools/stringency/engine/versions/0.1.0+lane-a-1`, `current` points at it; `~/.local/bin/stringency` follows `current` |
| method | `~/mytools/stringency/stringency-toy-method` at local tag `v0.1.3` (titled pipelines, all 0.1.2); not pushed |
| declarations | `/data/lab/projects/2026-09_stringency-exit_jrrose5/track1b/{objective,design,inputs}.yml`; `declare --check` exit 0 with the echo-back |
| brief | `~/mytools/stringency/brief-track1b.md` (first message) |
| agent context | `~/mytools/stringency/context-track1b.md` |
| project directory | `/data/lab/projects/2026-09_stringency-exit_jrrose5/track1b/toy-compare` (created by `init` in Phase 1) |

To go back to the tagged 0.1.0 engine afterwards:
`ln -sfn versions/0.1.0 ~/mytools/stringency/engine/current`.

## A. Once, in the Claude Science app

1. Republish the operator skill. The text changed (intent table, hold protocol, the new flags).
   In any session, in a `repl` cell:

        c = host.compute.create("protseq")
        base = "/home/jrrose5/mytools/stringency/stringency/integrations/claude-science"
        t = c.download(f"{base}/stringency-operator/SKILL.md")
        content = open(t["local_path"]).read()
        host.skills.edit("stringency-operator", "SKILL.md", content)   # existing file: read-then-replace
        host.skills.publish("stringency-operator", overwrite=True)

   `stringency-declare` is unchanged and needs no republish.
2. App version. Read it from the app's version display and replace `unknown` in the `PRE` line
   of `brief-track1b.md`. Without it the trace records `unknown`.
3. Compute provider and data root are already set from 2026-09-14 (`protseq`,
   `/data/lab/projects/2026-09_stringency-exit_jrrose5`). If the card for `call_command` offers an
   "always allow" scope, note whether it does; that is section 3.4 of the UX plan, and the answer
   goes in the measurement row.

## B. At a terminal on PROTSEQ, before the session

    ssh protseq
    export PATH=~/.local/bin:$PATH
    stringency plugins list | head -1          # stringency-toy 0.1.2
    stringency run --help | grep -E 'responses|deliver'
    cd /data/lab/projects/2026-09_stringency-exit_jrrose5/track1b && ls    # the three yml files

Keep the terminal open. You should not need it for holds this time; it is there to check the
trace and as the fallback if the relayed path is refused.

## C. The session

1. New Claude Science project. Paste `context-track1b.md` into its Agent Context.
2. Paste `brief-track1b.md` as the first message; ask for Phase 0 only. The probe card's intent
   should read "Check that the analysis engine and its software image are ready on protseq."
   Expect user `jrrose5`, engine under `~/mytools/stringency/engine`, plugin `stringency-toy
   0.1.2`, the image present, a Python 3.12 version from the container.
3. Ask for Phase 1. `init` ends with the confirm hold. This is the first thing to watch: the agent
   should present it by the protocol, in this order and nothing else: where it paused and what
   is asked; "What the engine recorded" with the echo-back lines verbatim; the verdicts as
   "accept: ..." and "reject: ..." with the engine's effects; the ask. It must not print the hold
   id, the exit code, or the `review` command unless you ask.
   - First reply "ok". It should answer that it needs one of the verdicts and your reason.
   - Then "accept, the echo-back matches the experiment". It runs one `review --attest` (card
     intent "Record your decision on the toy-compare question, in your words, under your name.")
     and reports the engine's reply in one sentence.
   - At the terminal, `cd .../track1b/toy-compare && stringency status --json | grep -A3 plain`
     shows the `plain` line, and the reviews row has `via = relayed`, your session ref, and
     `operator_harness = claude-science`:

         python3 -c "import sqlite3; c=sqlite3.connect('prov/run.db'); print(*c.execute('select via, operator_session_ref, operator_harness, reason from reviews'))"

4. Ask for Phase 2. What the agent says to you after each `run` should be the `plain` line and
   nothing more. Expected sequence for `toy-engine` with the operator executor:
   - `run` (exit 21): `01_filter` is `runner: engine` in this pipeline, so the first stop is the
     ticket for `02_summarize` (the project's execution setting is `operator`): "Completed: Filter
     low-value rows. Stopped: Summarize each group is ready for the operator to run and hand
     back." One card for `operator_line`,
     intent "Run the Summarize each group step of toy-compare in its container and hand the
     results back."
   - `run` (exit 20): "Completed: Filter low-value rows, Summarize each group. Stopped: three
     judgments requested for Label the groups." Three delegate downloads (inside the data root,
     so ideally no cards), then one card for `run --responses -` with the heredoc, intent "Record
     the three independent judgments for Label the groups and continue toy-compare."
   - Possibly a flag hold on `judg.confidence_consistent` as on 2026-09-08, presented by the
     protocol: "The analysis paused at Label the groups. The engine is asking: is this
     acceptable: <reason verbatim>." Answer with a verdict word and a reason.
   - `run` (exit 21): `04_compare` ran on the engine; `05_report` is a ticket: "Completed: ...,
     Compare the groups. Stopped: Write the report is ready for the operator to run and hand
     back." One `operator_line` card.
   - `run --deliver` (exit 0): "Completed: Filter low-value rows, Summarize each group, Label
     the groups, Compare the groups, Write the report. The run is complete." and the delivery
     path.
5. Phase 3. The agent downloads `summary.md`, `coverage.md`, `methods.md`, `index.json` and shows
   you `summary.md` as it is. Read it as the lay reader would: what was analyzed, what ran (every
   step "at defaults" or "no parameters"), what was checked and decided (your verdicts, quoted),
   judgments, what you received, not checked.

## D. What to record (one row in `spec/plans/backlog.md`, Measurements)

- approval cards, total and by kind (commands, downloads, other); the 2026-09-14 count was 26
  for two projects;
- your turns from the first message to `summary.md` shown;
- wall-clock to the first delivered file;
- unrequested codes, ids, paths, or JSON shown to you (target zero);
- holds and how each was resolved (`via` from the reviews table);
- operator misreports against the trace (target zero): compare each `plain` line the agent
  relayed with `stringency status --json` at the time;
- the two 3.4 answers: did delegate downloads under the data root raise cards; does the
  `call_command` card offer a standing grant, and if so, the count after granting `stringency`.

Send the agent's report and the four `deliver/` files to the next Lane A or Lane E session; it
writes the note and the measurement row.

## If something goes wrong

- Probe finds `stringency-toy 0.1.1` or no `--responses` flag: `current` is not on the new
  version; `readlink -f ~/mytools/stringency/engine/current` should end in `0.1.0+lane-a-1`.
- `init` fails on the method: the tag `v0.1.3` is local to PROTSEQ's checkout; check with
  `git -C ~/mytools/stringency/stringency-toy-method tag`.
- `review --attest` exits 16 naming `STRINGENCY_SESSION_REF`: the agent's `PRE` line did not set
  the frame id. The engine refused by design; have it set the variable, not skip `--attest`.
- The agent gives a verdict, infers one from "ok", or prints the hold command unasked: refuse,
  and note it for the report; that is a skill-text finding.
- `run --responses` exits 16: read the message; it names which of the four refusals applied.
  Nothing was written, so the fix is to rebuild the document and call again.

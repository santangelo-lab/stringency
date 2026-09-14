# PROTSEQ exit run through Claude Science: the walkthrough

The second half of the Phase A exit (build plan, "Phase A exit"), on PROTSEQ, with the two
additions from `spec/declarations-and-objectives.md` step 3: the agent drafts the declarations
from your brief and a sample manifest, and the work is two chained projects so `derived_from` is
exercised. Everything the session touches is on PROTSEQ; the session itself runs in the Claude
Science app on your MacBook with `protseq` as an SSH compute provider, exactly as `bmeseq` was on
2026-09-08.

Files in this directory (`~/mytools/stringency` on PROTSEQ):

| file | use |
|---|---|
| `brief-toy-process.md` | first message for project 1; append your brief under "Brief" |
| `context-toy-process.md` | agent context for project 1 |
| `brief-toy-compare.md` | first message for project 2; append your brief under "Brief" |
| `context-toy-compare.md` | agent context for project 2 |

Layout on PROTSEQ, all under `AREA=/data/lab/projects/2026-09_stringency-exit_jrrose5`:

    data/groups.csv          the toy data (50 rows: row_id, group, unit, value)
    data/samples.csv         the sample manifest, one row per unit (unit, group), 9 rows
    process/                 parent of project 1: brief.md, declarations/, toy-process/
    compare/                 parent of project 2: brief.md, declarations/, toy-compare/
    check/                   scratch from the tooling check; delete when you like

## A. At a terminal on PROTSEQ, before the session

    ssh protseq
    export PATH=~/.local/bin:$PATH        # stringency is linked there
    AREA=/data/lab/projects/2026-09_stringency-exit_jrrose5
    ls $AREA/data                          # groups.csv and samples.csv
    ls -d $AREA/process $AREA/compare

`samples.csv` and the two parent directories were created for you on 2026-09-14. Keep this
terminal open; every hold is accepted here.

## B. In the Claude Science app, once

1. Compute provider. Customize, compute: add PROTSEQ under the SSH alias `protseq` (the same
   alias your MacBook uses). Set `/data/lab/projects/2026-09_stringency-exit_jrrose5` as a data
   root so downloads inside it do not each raise an approval card.
2. Skills. The instance has `stringency-operator` from 2026-09-08, but the file changed since
   (E2 route, review packets) and `stringency-declare` is new. In any session, in a `repl` cell:

        c = host.compute.create("protseq")
        base = "/home/jrrose5/mytools/stringency/stringency/integrations/claude-science"
        for name in ("stringency-operator", "stringency-declare"):
            t = c.download(f"{base}/{name}/SKILL.md")      # returns {local_path, bytes, sha256}
            content = open(t["local_path"]).read()
            host.skills.edit(name, "SKILL.md", content)   # an existing file needs read-then-replace
            host.skills.publish(name, overwrite=True)

   `download` copies the file into the agent's workspace and returns a transfer dict, not bytes.
   `host.skills.edit` creates a file only when it does not exist; for an existing skill the agent
   must pass the current body as `old_string`. Done on 2026-09-14 for both skills.
3. App version. Read it from the app's own version display and replace `unknown` in the `PRE`
   line of both brief files (`STRINGENCY_OPERATOR_VERSION=unknown`). Without this the trace
   records `unknown`, which is allowed but weaker.

## C. Write the two briefs

The skill may only write values that have a source in the manifest, your sentences, or the
plugin's defaults, so the brief has to supply what the manifest cannot. The manifest gives the
factor `group` with levels A, B, C and the unit per row. Each brief should say, in your own
words:

Project 1 (`toy-process`, question `process_rows`):
- which file the data is (`.../data/groups.csv`) and what the rows are (one measurement per row,
  several rows per unit);
- that the independent replicate is the unit;
- that there are no contrasts, and what you want delivered: the filtered table (the pipeline's
  output is named `object`; the skill finds that by reading the pipeline).

Project 2 (`toy-compare`, question `compare_groups`):
- which file the data is: the path of the delivered table from project 1, which you will know
  after step E (`.../process/toy-process/deliver/<run_id>/01_filter.object.csv`);
- the replicate is the unit, the contrast is A versus B (add C or a second contrast if you want
  the skill to have to ask about pairwise versus omnibus);
- what you want delivered: the comparison table and the group labels;
- optionally, the minimum units per group; if you leave it out, the skill takes the plugin
  default and must say so.

Write plainly and do not use the field names of the YAML files. The point of the test is whether
the skill translates without inventing.

## D. Project 1: toy-process

1. Create the Claude Science project. Paste `context-toy-process.md` into its Agent Context.
2. Paste `brief-toy-process.md`, with your brief under "Brief", as the first message. Ask for
   Phase 0 only. Check the probe: user `jrrose5`, host `BMESANT-PROTseq`, engine found under
   `~/mytools/stringency/engine`, plugin `stringency-toy 0.1.1`, image present, container prints
   a Python 3.12 version.
3. Ask for Phase 1. The agent loads the declare skill, shows you its classification of the
   manifest columns, and asks about anything ambiguous. Answer in the chat. Count the turns.
   When it shows the echo-back and the table of fields with sources, read every row: each source
   must be a manifest column, a sentence of yours, or a named plugin default. Say yes only then.
4. It runs `init` and reports a confirm hold. At your terminal:

        cd $AREA/process/toy-process && cat echo.md
        grep -A4 '^declarations' stringency.yml       # drafted_by: agent, brief, brief_blake3
        stringency review --hold <id>
        stringency review --verdict accept --hold <id> --reason "echo-back matches the brief"

5. Ask for Phase 2. `toy-process` has one step, `01_filter`, operator-run: a ticket (exit 21),
   the agent writes `job.json`, runs the script in the container, submits, and the run
   completes. The agent may not call `run` after that.
6. Ask for Phase 3. `deliver` writes `deliver/<run_id>/01_filter.object.csv` and its sidecar
   `01_filter.object.csv.stringency.json`, plus `coverage.md`, `methods.md`, `index.json`. Note
   the full path of the CSV; it goes into the second brief.

## E. Project 2: toy-compare on toy-engine

Same shape, new Claude Science project, `context-toy-compare.md` and `brief-toy-compare.md`. The
pipeline is `toy-engine`, chosen so two steps (`01_filter`, `04_compare`) run on the engine under
the apptainer executor rather than by the operator; the 2026-09-08 run covered the operator path.

Differences to watch:

- Phase 1. The skill must notice the sidecar beside the delivered CSV and add `derived_from`
  with the run id, step `01_filter`, output `object`. `init` verifies that against the sidecar
  and refuses if the hash or the run does not match. The echo-back should name the upstream run.
- Phase 2. Expect: `01_filter` engine-run; `02_summarize` ticket; `03_label` dispatch (exit 20)
  answered by three fresh delegates, then possibly a flag hold on `judg.confidence_consistent`
  as on 2026-09-08; `04_compare` engine-run; `05_report` ticket. For a flag hold:

        cd $AREA/compare/toy-compare
        stringency review                        # the queue
        stringency review --hold <id>            # the packet for that hold
        stringency review --verdict accept --hold <id> --reason "..."

  Every exit 10 comes back to you this way; the agent stops and waits.
- Phase 3. `methods.md` should carry "inputs derived from run <id>" for the upstream run.

## F. Afterwards: what to record

From the design note, step 3, plus the exit checks the build plan asks for:

1. Drafting: how many turns per project, which fields the skill asked about, and whether any
   accepted field lacks a source in the brief or the manifest.
2. Trace: `drafted_by: agent` and the brief hash in `stringency.yml` and in the confirm hold's
   context; `captures.derived_from` in project 2's run open event; the methods paragraph.
   Python, since there is no `sqlite3` CLI:

        python3 -c "import sqlite3,sys; c=sqlite3.connect('prov/run.db'); print(*c.execute('select name from sqlite_master where type=\"table\"'))"

3. Session: approval cards per project (the toy took 25 on BMESEQ), delegates used and what
   model each reported, the frame id.
4. Exit checks on project 2, at your terminal while a step is held or awaiting execution:
   `propose 02_summarize` exits 10 while step 1 is held and 15 while it awaits execution; a
   fabricated ticket is refused with 15; `lint` on the method with the negative control removed
   exits 15 naming the control.

Send the agents' reports and the four `deliver/` files back to the engine session on BMESEQ, and
that session writes the note, updates `spec/improvements.md` (H4 tested), and moves on to the
`v0.1.0` tag.

## If something goes wrong

- Probe fails on the image or the container: the tooling step was not complete; nothing in the
  session can fix it.
- `declare --check` exits 15 repeatedly on the same field: the brief lacks a source for it. Add
  the sentence to your brief in the chat rather than telling the agent the value directly, so the
  brief file stays the record.
- The skill cannot add `derived_from`: check that the sidecar sits beside the CSV in
  `deliver/<run_id>/` and that the brief gives that path, not a copy.
- The agent asks to accept a hold or proposes a workaround: refuse, and note it for the report.

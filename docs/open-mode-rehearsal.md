# Open mode: the toy test drive

The owner's test drive of open mode with an agent operating and the owner as the person, on the
toy, before `open-mode` merges (`spec/archive/open_mode_plan.md` O2). Everything the agent needs is
in place on the workstation as of 2026-10-19; the owner's part is the four steps of section 2
and then the session of section 3. The by-hand form, for seeing the mechanics without an agent,
is the appendix.

The first drive (2026-10-19, `/data/lab/projects/2026-10_open-mode-drive_jrrose5`) found six
things, all changed since (`spec/archive/open_mode_plan.md` section 9): no answer could be trusted
because no control ever ran; a tool's untested answer was described as code; the raw input was
out of reach; the answer delivery shared file names with the pipeline's; the open project's
directory was hard to read; and the delivery message was long. The second drive uses a new
project parent, so the first stays as it was.

## 1. What is in place

| piece | where | state |
|---|---|---|
| engine 0.2.22 (branch `open-mode`) with the toy plugin 0.1.3 and the two engine skills | `/data/lab/env/stringency-open-mode/current/` (`bin/stringency`, `skills/stringency-operator/SKILL.md` with section 10, `skills/stringency-declare/SKILL.md`) | installed 2026-10-16 under its own prefix, reinstalled 2026-10-19 with the first drive's fixes; the shared engine `/data/lab/env/stringency/current` is untouched (0.2.21) |
| toy method with tools | `/home/jrrose5/mytools/stringency/stringency-toy-method` at tag `v0.2.0-rc6` (branch `open-mode`; rc2 restored the image, rc3 routes the raw-values question to code, rc4 to rc6 the operator's own reply and the report) | `compare-groups` 0.1.1 and `plot-groups` 0.1.0 list `open` with controls; `skills/toy-engine.analyze.yml` carries `tools:` and `open:`; `skills/open.yml`; `skills/toy-engine.questions.yml`; `stringency-analyze-toy-compare/SKILL.md` re-rendered with section 8 |
| the data | `/home/jrrose5/mytools/stringency/stringency-toy-method/controls/fixtures/groups.csv` (50 rows, groups A, B, C, a unit and a value per row) | copy it under the project parent so the agent reads it from the data root |

Nothing here touches a real project. `stringency probe` under the open-mode prefix says `ready`.

## 2. The owner's four steps

1. **A project parent** under the projects area, with the data beside it:

    ```
    P=/data/lab/projects/2026-10_open-mode-drive2_jrrose5
    mkdir -p $P/data && cp ~/mytools/stringency/stringency-toy-method/controls/fixtures/groups.csv $P/data/
    ```

2. **The brief and the context**, rendered from the branch checkout (the renderer is in the
   repository, not the install), with the open-mode prefix on the engine's PATH line:

    ```
    cd ~/mytools/stringency/stringency && git checkout open-mode
    P=/data/lab/projects/2026-10_open-mode-drive2_jrrose5
    E=/data/lab/env/stringency-open-mode/current/bin
    V=$(claude-science --version | awk '{print $2}')
    R=integrations/claude-science/render_brief.py
    M=/home/jrrose5/mytools/stringency/stringency-toy-method@v0.2.0-rc6
    A="$P/toy-compare --provider protseq --method $M --pipeline toy-engine --declare --engine-bin $E"
    $E/python $R $A --rehearsal --app-version $V > $P/brief.md
    $E/python $R $A --context > $P/context.md
    ```

   The lines are short and have no backslash continuations on purpose: a long line wrapped by a
   narrow pane and copied leaves `$E/python` alone on a line, which opens a Python shell (the
   first drive, 2026-10-19). `--rehearsal` adds the engine-record report to Phase 3; leave it off
   for an ordinary analysis.

   The brief ends with "Phase 4: questions of the delivered dataset (open mode)". Fill the
   "Brief" section at its end in your words: the file is `$P/data/groups.csv`, one row per
   measurement, the group column is `group`, the unit column is `unit`, the replicate is the
   unit, compare A and B, and you want the filtered table, the comparison table, the labels and
   the report delivered (the filtered table is what the questions are asked of).

3. **Republish the three skills** into your Claude Science instance from the open-mode prefix
   and the toy tag. Paste this into a session that has `protseq` as a compute host:

   > Publish the stringency skills into this instance. On the compute host `protseq` the
   > current texts are the directories under `/data/lab/env/stringency-open-mode/current/skills/`
   > (one `SKILL.md` each: `stringency-operator`, `stringency-declare`) and
   > `/home/jrrose5/mytools/stringency/stringency-toy-method/skills/stringency-analyze-toy-compare/SKILL.md`
   > (the toy method at tag `v0.2.0-rc6`). Download each file, publish it under its directory
   > name with `host.skills.edit` and `host.skills.publish`, overwriting the older copy, and tell
   > me the name of each skill you published and, for `stringency-operator`, its "for engine"
   > line.

   The operator skill must say "for engine 0.2.22" and the analysis skill must have a section
   "8. After delivery: questions". A session that keeps the 0.2.19 operator skill will not know
   the verbs; the held payload names the installed copy and the skill tells the operator to
   follow it, but publishing first is cleaner.

4. **A new Claude Science project** with `context.md` pasted into its Agent Context, and
   `brief.md` as the first message, asking for Phase 0 only. From there the session runs as any
   toy-engine drive (`integrations/claude-science/new-project.md`, steps 9 to 11): the probe, the
   declarations from your brief, the echo-back and your yes, the confirm hold, the run with its
   three-replicate judgment, the delivery: the results as `present` shows them, at most three
   sentences on what was decided, the saved files by name, and (with `--rehearsal`) the
   engine-record report.

## 3. The session, the open half

After the delivery report the agent should, without being asked:

1. Run `tools list --context` on the delivered project (you will not see the command) and say
   three to five paths forward in the pinned form, tools before code; each names a tool
   ("would be labelled trusted") or says code ("would be labelled untested"). Expect `compare-groups`
   and `plot-groups` to be offered as trusted (`tools list` says their controls run before first
   use), and a code path for counts or means per group.
2. Say the switch paragraph verbatim ("Your results are delivered. You can ask questions of them
   here. ... Shall I open it for questions?") and wait for your yes.
3. On the yes, create `toy-compare-open` beside the project and record your yes as its
   confirm verdict, without asking the paragraph twice. Its `README.md` says what every path
   holds and lists the questions as you ask them.

Then ask. The routing file `skills/toy-engine.questions.yml` in the toy method is the question
set for this drive; ten questions is the measure (O2). A suggested order, with what the engine
should produce:

| ask | route | what you should see |
|---|---|---|
| pick the first path (which groups differ, with bh) | tool `compare-groups` | the tool's controls pass first (said in a line); then a reply in plain words (A and B differ a lot, A and C barely), the comparison table, and one sentence saying the answer is trusted because it came from the method's tested tool; no ids, no qualifier line |
| "Show me the differences as a plot" | tool `plot-groups` | a trusted answer with the figure beside it |
| "Run the comparison again with bonferroni" | tool with your value | no approval hold (you set it); the reply says you set the correction to bonferroni |
| "How many rows does each group have after filtering?" | code (`exec`) | the before-exec sentence first; then the counts in words, the table with the group names, and a sentence saying it is untested because it is code written in the session |
| "What is the mean value per unit?" | code | untested, as above |
| "Is this result good enough to report?" | cannot | the cannot sentence; no tool run, no number |
| "What were the raw values before filtering?" | code, on the pipeline's input | the script names `upstream_groups`; the reply says it is untested code and that it read the data from before the pipeline ran |
| "What was the room temperature when the values were measured?" | cannot | in neither the delivery nor the inputs; the agent says what would answer it |
| "Rerun the whole analysis keeping rows below 10" | not a question | the agent says this is a change to the pipeline run (a fork), not a question of the delivery |
| "How were the p-values corrected?" | explain | from the methods paragraph or the summary, no new run |
| "Show me the code" (after a code answer) | mechanics on request | the script verbatim |
| "How was that checked?" | mechanics on request | the qualifier line and the cells the numbers were checked against, in words (`present --answer --details`) |

Try at least one wrong number: ask the agent to restate an answer with a number you make up.
It cannot: `answer` blocks any numeral that is not a cited cell, and the agent is to fix the
text, never a number. Every answer is already on disk: `toy-compare-2-open/deliver/<run>/`
holds `q01-...md` per answer and `report.md`, rewritten as you go; after the first answer the
agent tells you so once. When you say you are done, the agent asks once which answers are
findings ("You can name them by number, say all, or none"); it marks the ones you name, saves
`report.md` as an artifact, and says in one line where it is and how many findings it has. Open
`report.md`: the findings in full first, the other questions in short after. In a later session,
`stringency finding --remove <id>` or a new mark rewrites it.

## 4. What to record

One row in `spec/plans/measurements.md` (Measurements): questions asked by origin (suggested,
person), answers by label (trusted, untested), blocks and how each was cleared, unrequested ids
or paths shown (target zero), label words stated correctly in the reply (target all ten), turns and minutes
to the first delivered answer, and anything the agent did outside the three routes. And a note
on the words: whether the paths, the switch paragraph, the label sentences and the qualifier
line are what you would want said; they are pinned in `src/stringency/provenance.py`,
`src/stringency/echo.py` and the operator skill's section 10.7, and a test keeps the copies
identical, so a change is one edit in each.

Findings go to `notes/` and feed the merge decision; the measurement row and the routing
results (`skills/toy-engine.questions.results.md` in the toy method) are the O2 record.

## 5. Afterwards

The open-mode prefix is removed with `rm -rf /data/lab/env/stringency-open-mode`; the project
parent `$P` is the drive's record and may stay or go. Merging `open-mode` into `main`, tagging
`v0.2.22` and installing it into the shared prefix is a separate decision, as is tagging the toy
method `v0.2.0`.

## Appendix: the same thing by hand, from a terminal

For seeing the mechanics without an agent. Every command was run on 2026-10-16 against the
checkout; ids are placeholders. `stringency` here is
`/data/lab/env/stringency-open-mode/current/bin/stringency`; set `STRINGENCY_NOTIFY=0`.

A method repository at a tag: the toy method at `v0.2.0-rc2` as installed above, or a copy of
the branch's `plugins/stringency-toy/method` with `git init`, a commit and a tag.

The upstream delivery, a `toy-process` project (one step, filters rows below 10):

```
mkdir -p ~/scratch/rehearsal && cd ~/scratch/rehearsal && mkdir data decl
cp ~/mytools/stringency/stringency-toy-method/controls/fixtures/groups.csv data/
HASH=$(/data/lab/env/stringency-open-mode/current/bin/python -c \
  "from stringency import hashing; print(hashing.hash_file('data/groups.csv'))")
printf 'design: 1\nunits: {observation: row, sample: unit}\nfactors:\n  group: {column: group, levels: [A, B, C]}\nbatch: []\nreplication_unit: unit\nholdout: []\n' > decl/design.yml
printf 'objective: 1\nid: toy_process\nquestion: process_rows\ncontrasts: []\nreplication_unit: unit\nmin_n_per_group: 2\ndeliverables: [object]\ndomain: {}\n' > decl/objective.yml
printf 'inputs: 1\nitems:\n  - {name: groups, path: %s/data/groups.csv, type: frame, blake3: "%s", source: toy fixture}\n' "$PWD" "$HASH" > decl/inputs.yml
stringency init process --method ~/mytools/stringency/stringency-toy-method@v0.2.0-rc6 --pipeline toy-process \
  --objective decl/objective.yml --design decl/design.yml --inputs decl/inputs.yml \
  --judgment-harness mock --executor local --execution engine
cd process && stringency review --hold <hold id> --verdict accept --reason "the declarations match"
stringency run --deliver && stringency tools list --context && cd ..
```

The open project and the switch, a question by tool (its controls run before the first call;
under the mock harness only a deterministic tool's controls run), one by code, the answers (the
first deliberately wrong; every admissible one lands in `deliver/<run id>/` as it is filed), a
finding, the report and the view:

```
stringency init questions-open --method ~/mytools/stringency/stringency-toy-method@v0.2.0-rc6 --mode open \
  --from-delivery $PWD/process/deliver/<run id> --judgment-harness mock --executor local --execution engine
cd questions-open && cat echo.md
stringency review --hold <hold id> --verdict accept --reason "yes, open it for questions"
stringency ask "Which group is higher, A or B?"
stringency call compare-groups
stringency call plot-groups
cat runs/<run id>/01_compare-groups/comparison_table.tsv
echo "A is higher than B by 60." | stringency answer --question <question id> --cite <table artifact id>:A_vs_B --text -
echo "A is higher than B: the difference is 59.22, adjusted p 1.33e-75; the figure shows all three contrasts." \
  | stringency answer --question <question id> --cite <table artifact id>:A_vs_B --cite <figure artifact id> --text -
stringency ask "How many rows does each group have?"
printf 'import csv, json, sys\njob = json.load(sys.stdin)\nby = {}\nfor r in csv.DictReader(open(job["inputs"]["object"])):\n    by[r["group"]] = by.get(r["group"], 0) + 1\nwith open(job["outputs"]["counts"], "w") as f:\n    f.write("group\\tn\\n")\n    for g, n in sorted(by.items()):\n        f.write(f"{g}\\t{n}\\n")\n' > ../count.py
stringency exec ../count.py --out counts=table --question <question id> --allow-local --reason "no tool counts rows per group"
cat runs/<run id>/03_exec/counts.tsv
echo "A has 17 rows, B 17 and C 7." | stringency answer --question <question id> --cite <counts artifact id> --text -
stringency present --answers
cat deliver/<run id>/report.md
stringency finding <trusted answer id> --reason "this is the one"
cat deliver/<run id>/report.md
stringency deliver
stringency present --answer <trusted answer id>
```

The first `answer` exits 12 (60 is no cited cell) and is kept as blocked; the second prints the
two pinned lines. The delivered frame is the filtered one, so the counts are not the raw
fixture's: on 2026-10-16 the dry run wrote "C 16" where the table said 7 and was blocked.
`--allow-local` is needed under the local executor, which has no containment. Clean up with
`rm -rf ~/scratch/rehearsal`.

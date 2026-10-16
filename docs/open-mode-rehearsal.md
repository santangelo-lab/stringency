# Open mode: the toy rehearsal

How to run a delivered toy pipeline into open mode by hand, from a terminal, on branch
`open-mode` (engine 0.2.22, unmerged). Every command below was run on 2026-10-16 against the
checkout; the ids in the outputs are examples. The skill text that lets an operator drive this
from a Claude session (O1 in `spec/plans/open_mode_plan.md`) does not exist yet, so this is you
and the CLI. Read `spec/plans/open_mode_plan.md` section 1 first for what the words mean.

Nothing here touches the shared engine (`/data/lab/env/stringency/current` stays at 0.2.21) or
any real project. Work in a scratch directory and delete it afterwards.

## 0. The engine

Either use the branch checkout directly:

```
cd ~/mytools/stringency/stringency && git checkout open-mode && uv sync --all-groups
alias stringency=~/mytools/stringency/stringency/.venv/bin/stringency
stringency --version      # 0.2.22
```

or install it under its own label beside the released versions, which leaves `current` alone:

```
cd ~/mytools/stringency/stringency && git checkout open-mode
scripts/install.sh --prefix /data/lab/env/stringency --label 0.2.22-open-mode --link-bin ""
alias stringency=/data/lab/env/stringency/versions/0.2.22-open-mode/bin/stringency
```

Set `export STRINGENCY_NOTIFY=0` so the rehearsal sends no notifications.

## 1. A method repository with tools

The toy method in the branch (`plugins/stringency-toy/method`) is the one whose
`compare-groups` and `plot-groups` list `open` and carry controls. It has to be a git
repository at a tag:

```
mkdir -p ~/scratch/rehearsal && cd ~/scratch/rehearsal
cp -r ~/mytools/stringency/stringency/plugins/stringency-toy/method toy-method
(cd toy-method && git init -q && git add -A && git commit -qm "toy method" && git tag v0.1.0)
```

## 2. The upstream delivery

A `toy-process` project: one step, filters rows below 10, delivers the filtered frame. This is
the pipeline half; open mode starts where it ends.

```
mkdir data decl && cp toy-method/controls/fixtures/groups.csv data/
HASH=$(~/mytools/stringency/stringency/.venv/bin/python -c \
  "from stringency import hashing; print(hashing.hash_file('data/groups.csv'))")
cat > decl/design.yml <<EOF
design: 1
units: {observation: row, sample: unit}
factors:
  group: {column: group, levels: [A, B, C]}
batch: []
replication_unit: unit
holdout: []
EOF
cat > decl/objective.yml <<EOF
objective: 1
id: toy_process
question: process_rows
contrasts: []
replication_unit: unit
min_n_per_group: 2
deliverables: [object]
domain: {}
EOF
cat > decl/inputs.yml <<EOF
inputs: 1
items:
  - {name: groups, path: $PWD/data/groups.csv, type: frame, blake3: "$HASH", source: toy fixture}
EOF
stringency init process --method $PWD/toy-method@v0.1.0 --pipeline toy-process \
  --objective decl/objective.yml --design decl/design.yml --inputs decl/inputs.yml \
  --judgment-harness mock --executor local --execution engine
```

`init` exits 10 on the confirm hold and names it. Accept it (you are the owner; at a terminal no
`--attest` is needed), then run and deliver:

```
cd process
stringency review --hold <hold id> --verdict accept --reason "the declarations match"
stringency run --deliver
cd ..
```

The delivery is `process/deliver/<run id>/` with `01_filter.object.csv`, its sidecar,
`index.json`, `coverage.md`, `methods.md`, `summary.md`.

## 3. The review before the switch

This is what the operator would do before proposing paths: see which tools the method ships,
what they could bind in this delivery, and what the project asked.

```
(cd process && stringency tools list --context)
```

Expect two tools. `compare-groups` can bind the delivered frame; `plot-groups` binds a
comparison table, so "nothing matches" until one exists. Both say
`control: none: outputs will be labelled untested`, because no control has run in this project
yet. The context lines give the objective (`process_rows`, deliverable `object`) and the
design's factor and levels, which is what the paths forward are composed from.

## 4. The open project and the switch

```
stringency init questions --method $PWD/toy-method@v0.1.0 --mode open \
  --from-delivery $PWD/process/deliver/<run id> \
  --judgment-harness mock --executor local --execution engine
cd questions
cat echo.md
```

`inputs.yml`, `design.yml` and `objective.yml` were derived from the delivery (look at them:
one input, `derived_from` the upstream run; the design byte for byte; the objective with no
deliverables and no params). The echo is the pinned switch paragraph and the bound delivery.
This is the one relayed yes of the owner's decision 4; accept it:

```
stringency review --hold <hold id> --verdict accept --reason "yes, open it for questions"
```

`stringency run` here is refused (exit 16) and says so.

## 5. Controls, so that "trusted" can mean something

A tool with no passing control in this project yields untested answers. Run the tools'
controls (the mock harness needs `--allow-mock`; no judgment runs anyway):

```
stringency controls run --module compare-groups --allow-mock
stringency controls run --module plot-groups --allow-mock
stringency tools list     # the controls are now listed with their date
```

The positive control of `compare-groups` compares its output on the fixture to
`controls/fixtures/compare_truth.tsv` (`rows_matching 3 of 3`); the negative one shuffles the
groups and expects no contrast below adjusted p 0.05.

## 6. A question answered with a tool

```
stringency ask "Which group is higher, A or B?"
stringency call compare-groups
stringency call plot-groups
stringency next
cat runs/<run id>/01_compare-groups/comparison_table.tsv
```

`ask` opens the open run and files the question. `call` binds the one frame input on its own,
runs the tool through the ordinary gate, and prints the artifact id. `plot-groups` binds the
comparison table the first call produced. `next` on an open run reports the questions, the
steps and the artifacts that can be cited; it never says "completed".

Try the parameter paths too: `stringency call compare-groups --set correction=bonferroni
--reason "stricter"` opens a `param.agent_proposed` hold under standard (exit 10; review it,
then `stringency propose 03_compare-groups` continues it), while `--set correction=bonferroni
--asked-by person --reason "the person said: use bonferroni"` opens none and is recorded as
the person's. `--set correction=foo` is blocked by `param.schema_invalid` (exit 11).

## 7. Answers

Note the table's `diff` for `A_vs_B` (59.22 on this data) and its `p_adj`. First a wrong
number, then the right ones:

```
echo "A is higher than B by 60." | stringency answer --question <question id> \
  --cite <comparison artifact id>:A_vs_B --text -
echo "A is higher than B: the difference is 59.22, adjusted p 1.33e-75; the figure shows all three contrasts." \
  | stringency answer --question <question id> --cite <comparison artifact id>:A_vs_B \
    --cite <figure artifact id> --text -
```

The first exits 12, blocked by `ans.numeral_unmatched` (60 is no cited cell); the row is kept.
The second is admissible and prints the two pinned lines: the label sentence (`Label: trusted.
Produced by compare-groups ... and plot-groups ...; Numbers checked against the cited cells:
2 of 2`) and the qualifier line. Writing the word "trusted" or "untested" in the text blocks it
(`ans.label_authored`); citing an id that does not exist blocks it (`ans.cited_missing`).

## 8. A question answered with code

```
stringency ask "How many rows does each group have?"
cat > ../count.py <<'EOF'
import csv, json, sys
job = json.load(sys.stdin)
by = {}
for r in csv.DictReader(open(job["inputs"]["object"])):
    by[r["group"]] = by.get(r["group"], 0) + 1
with open(job["outputs"]["counts"], "w") as f:
    f.write("group\tn\n")
    for g, n in sorted(by.items()):
        f.write(f"{g}\t{n}\n")
EOF
stringency exec ../count.py --out counts=table --question <question id> --allow-local \
  --reason "no tool counts rows per group"
cat runs/<run id>/03_exec/counts.tsv
```

The script receives the same JSON job a module does (`inputs`, `outputs`, `seed`), is copied
to `runs/<run>/03_exec/script.py`, hashed into the trace, and its output is recorded. The
verb prints the untested line. `--allow-local` is needed because the local executor has no
containment; under apptainer the inputs are bound read-only and the network isolated where the
host allows it.

Now answer it from the table. The delivered frame is the filtered one, so the counts are not
the raw fixture's; if you write what you remember instead of what the table says (on
2026-10-16 the dry run wrote "C 16" where the table said 7), the gate blocks it:

```
echo "A has 17 rows, B 17 and C 7." | stringency answer --question <question id> \
  --cite <counts artifact id> --text -
```

Admissible, and labelled untested: `Produced by code written in this session ...`, with
`untested inputs: 03_exec` in the qualifier.

## 9. Deliver and present

```
stringency present --answers
stringency deliver --answer <trusted answer id> --answer <untested answer id>
stringency present --answer <trusted answer id>
ls deliver/<run id>/<delivery id>/
```

The delivery holds one `<answer id>.answer.md` per answer (question, label sentence,
qualifier, text, cited files, the rerun line), the cited files with sidecars, `index.json`
with `answers` and a `provenance` block per file, and the three reports. Read `summary.md`:
What was asked, What ran, What you received, What was untested, Explored, and the not-checked
sentence for open runs. `coverage.md` ends with an `open mode:` block. The run is still
`running`; ask more and deliver again into a new directory.

## 10. What to look for

- Does the switch paragraph say what you would want said before questions begin?
- Are the two label sentences and the qualifier line the right words for a person who did not
  watch the run? They are pinned in `src/stringency/provenance.py`.
- Is "trusted" too easy or too hard to earn? Today it needs a tool, engine-run, a verified
  environment, a current control, and a completed step; one script anywhere on the path makes
  the answer untested.
- Does the rerun line ("one of N runs of the tool on these inputs; asked after M results
  existed") disclose what it should when you call the same tool several times?
- What is missing from `present --answer` for the person, and from `summary.md` for the
  reader who was not there?

Write the findings in a note; they feed O1 (the skill text) and the design amendments the owner
reads at merge. To clean up, delete `~/scratch/rehearsal`; nothing else was written.

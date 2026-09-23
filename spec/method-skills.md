# Method skills: what a method repository says to a person

How a method repository states what a person should see (the delivery skill) and how a person
starts and follows a run (the analysis skill), and how the two files are written, checked,
rendered, and published. Design 10.4 and 14.4 are the authority; this page gathers what they say
with the working detail a method author needs. Approved by the owner 2026-09-23 after the first
instance ran (`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`).

## 1. Two files per pipeline

Both live in `skills/` of the method repository, are committed there, and are versioned with the
method tag. Neither changes what runs; the engine loads neither into a run.

| file | read by | what it states |
|---|---|---|
| `skills/<pipeline>.yml` | `stringency present`, `stringency board`, the operator skill | the delivery skill (design 14.4): which delivered tables to show after a run, in which columns and formats; which files to send; what to show at a flag hold; what never to show |
| `skills/<pipeline>.analyze.yml` | `integrations/claude-science/render_skill.py` in the engine repository | the source of the analysis skill (design 10.4): the person-facing entry point for one pipeline, rendered to `skills/stringency-analyze-<name>/SKILL.md` and published in each person's Claude Science instance |

The rendered `skills/stringency-analyze-<name>/SKILL.md` is committed beside them. It is
generated: edit the `.analyze.yml` and render again.

The two engine skills, `stringency-declare` and `stringency-operator`, are the operator's
reference and live in the engine repository (`integrations/claude-science/`). An analysis skill
carries a compact appendix of the mechanics and names the operator skill as the authority when
they disagree. Both kinds set the `STRINGENCY_OPERATOR*` variables and neither resolves a hold.

## 2. The delivery skill, `skills/<pipeline>.yml`

Schema in design 14.4. In short:

```yaml
skill: 1
pipeline: <name>
after_delivery:            # rendered by `present`, in order
  - title: "..."           # the sentence a person reads above the table
    source: <path relative to deliver/<run>/, falling back to runs/<run>/>
    kind: table | json_table | jsonl | text | file
    columns: [...]         # optional subset and order (table, json_table, jsonl)
    format: {col: percent | int | "<n>f"}
    path: <key of the list of row dicts>   # json_table only; a dict renders as one row
never_show: [run ids, hashes, ...]         # echoed as a footer; a rule for the operator
hold_view:                 # rendered by `present --hold` for the predicate that opened the hold
  - predicate: <predicate id>
    source: <path relative to runs/<run>/>
    kind: table | json_table | jsonl
    columns: [...]
```

Rules that follow from the design: a missing or malformed skill, a missing source, or an unknown
kind degrades to the engine default with a note, never an error; `present` and `board` load no
plugin, so the file may name only what is in `deliver/` and `runs/`; the `never_show` list is the
method's instruction to the operator, not a filter the engine applies to files.

Write it for the reader who did not watch the run: one title per table saying what the rows are,
columns in the order a person would read them, formats that keep the engine's precision (a
`format` may round for display; the delivered file is unchanged). `hold_view` names the tables a
reviewer needs beside a flag: for a judgment hold, the consensus and the judgment log.

## 3. The analysis skill source, `skills/<pipeline>.analyze.yml`

| field | what |
|---|---|
| `pipeline` | the pipeline name, as in `pipelines/<pipeline>.yml` |
| `name` | optional slug for the skill name `stringency-analyze-<name>`; default the pipeline name |
| `method` | `<url or path>@<tag>` the skill passes to `declare --check` and `init`; bump the tag when the method is tagged |
| `plugin` | the plugin whose `plugins list --json` entry the skill reads (`questions`, `object_types`, `defaults`) |
| `question` | the objective question the pipeline answers; must be in the pipeline's `answers` |
| `title` | the skill's heading, in the person's words |
| `summary` | optional one sentence that opens the description; default the title |
| `phrasings.positive` | clauses completing "Load when the person ...": what people say when they want this analysis |
| `phrasings.negative` | clauses completing "Do not load for ...": the neighbours the skill must not catch |
| `steps` | step id to title, every step of the pipeline in order, titles equal to the pipeline's |
| `deliverables` | output name to one sentence saying what the person receives; names are module outputs |
| `asks` | the declare questions this pipeline always needs, in lay words, asked one at a time in this order |
| `defaults_to_say` | plugin default key to its lay phrase; the skill reads the value from `plugins list --json` and says it aloud before the echo-back |

What the template supplies and the source must not: the two-audiences preamble, the nine body
rules of `spec/plans/ux-two-audiences.md` section 4, the hold protocol (section 5.1 there, section
6 of the operator skill, the two kept identical by `tests/test_render_skill.py`), the walk-through
(engine and identity; the asks; declare, echo-back, yes, `init`, confirm hold; run and `plain`;
holds; `present` and the three-part report from `summary.md`; interpretation labelled; mechanics
on request) and the mechanics appendix.

Writing the asks is the design work. Ask only what the person's words and their manifest cannot
settle, in the order the declare skill needs them (the file, the columns that carry the design,
the replication unit, the contrast, the deliverables), each answerable by someone who has never
seen a YAML file. The declare rule applies: the skill translates and never infers a value the
person did not give; when their words admit two readings, it asks which. Every plugin default the
declaration will carry goes in `defaults_to_say`, so the person hears the value before the
echo-back.

Every step needs a `title` in `pipelines/<pipeline>.yml`: the skills speak in titles, `plain` and
`summary.md` are built from them, and `lint` warns when a pipeline with a `skills/<pipeline>.yml`
has an untitled step.

## 4. Render, check, tag, publish

From the method repository, with the engine's interpreter (it has jinja2 and pyyaml):

    <engine bin>/python <engine repo>/integrations/claude-science/render_skill.py . --pipeline <pipeline> --check
    <engine bin>/python <engine repo>/integrations/claude-science/render_skill.py . --pipeline <pipeline> --write
    stringency lint .

`--check` refuses unknown keys, a `method` without a tag, a `name` that is not a slug, and any
drift from the method: step ids not the pipeline's in order, a title that differs from the
pipeline's, a `question` not in `answers`, a deliverable no module of the pipeline produces. It
also reads the delivery skill's `after_delivery` titles into the rendered text, so the analysis
skill names what the person will receive in the method's words. Render again whenever the
`.analyze.yml`, a pipeline title, the delivery skill, or the engine's template changes; commit the
rendered file; tag the method.

Publishing is per person and per instance (`integrations/claude-science/publish-skills.md`): the
rendered `SKILL.md` is read from the method repository at its tag and published with the app's
skills cell; republish on every method tag that changed it. The engine records no publish; the
transcript is the record.

## 5. The routing test, `skills/<pipeline>.phrasings.yml`

Twenty positive and ten negative first messages, each with the outcome it should produce:
`analyze` (this skill), `declare-only`, `operator-only`, `none`. Run by hand in a Claude Science
session after each revision of the description, until a skill evaluation tool is confirmed there;
one row per phrasing tried in `skills/<pipeline>.phrasings.results.md` with the method tag. The
engine skills loading alongside the analysis skill is the expected outcome, not a miss: the
analysis skill defers to them.

## 6. What is measured

Each run through an analysis skill gives one row in `spec/plans/backlog.md` (Measurements):
approval cards by kind, the person's turns to result, wall-clock to the first delivered file,
unrequested commands or ids shown (target zero), holds and how each was resolved (`via`), and
misreports against the trace (target zero). The acceptance test for a skill is a run by someone
other than its author.

## 7. Where the pieces are

| piece | path |
|---|---|
| template | `integrations/claude-science/templates/analyze-skill.md.j2` (engine repository) |
| renderer | `integrations/claude-science/render_skill.py` |
| test | `tests/test_render_skill.py` |
| method-repo template | `templates/method-repo/skills/README.md`, `skills/example.analyze.yml` |
| first instance | `stringency-toy-method` `v0.1.4`, `skills/toy-engine.yml`, `toy-engine.analyze.yml`, `stringency-analyze-toy-compare/SKILL.md`, `toy-engine.phrasings.yml` |
| design | `stringency-design.md` 10.4 (two kinds of skill), 14.4 (delivery skill and the reading verbs) |
| plan | `plans/ux-two-audiences.md` sections 4, 5.1, 9 |

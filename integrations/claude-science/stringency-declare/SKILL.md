---
name: stringency-declare
description: Draft the three stringency declaration files (inputs.yml, design.yml, objective.yml) from a person's description of an experiment and a sample manifest, check them with `stringency declare --check`, show the echo-back, and run `init --drafted-by agent`. Load when a user describes an experiment they want to run under stringency, points at raw data and a manifest, or asks to set up, declare, or initialise a stringency project.
license: MIT
---

# stringency-declare

You turn a person's description of an experiment into the three declaration files stringency
binds at `init`. You translate; you do not decide. Every value you write must come from one of
four sources, in this order of authority: the sample manifest, the sample names when there is no
manifest, the person's own sentences, the plugin's defaults. You may not invent a factor, a
level, a contrast, a deliverable, or a replication unit. When the text admits two readings, ask.

The engine is `stringency`, found the way the operator skill's section 1 describes (`stringency
probe` says what is installed; mode B: on the registered compute host, prefixed the way the operator skill describes). Export the
`STRINGENCY_OPERATOR*` variables as the operator skill says; `init` records them as the drafter.

## 0. What the plugin knows

Run `stringency plugins list --json` once. For the plugin the person's method uses, read:
`questions` (the only values `objective.question` may take), `object_types` (the only values an
input `type` may take, plus `json`, `table`, `tsv`, `csv`, `text` for plain files),
`design_schema` (which design fields are required and what shape they have), `vocabulary_terms`,
and `defaults` (declaration values the plugin publishes, for example `min_n_per_group`; when the
person gives no number, use the plugin's default and say so in the source table). If the person's
question fits no entry in `questions`, stop and say so: that is a plugin gap, not something to
approximate. Do not read the engine's source or tests to learn file shapes; section 3 has them.

## 1. Save the brief

Write the person's own words, verbatim, to `<parent>/brief.md`, where `<parent>` is the
directory the project will be created in. Do not paraphrase. Append nothing. This file goes into
the project as `brief.md` and its hash is bound into the confirm hold.

## 2. Read the manifest

If the person gave a sample manifest (one row per sample, columns for the variables), read it and
list every column with the values it takes. Classify each column as a factor (biology the
experiment varies), a technical variable (batch, slide, lane, date), an identifier (sample id,
file name), or a measurement, and show the person the classification. Do not guess from column
names alone; ask for confirmation of the classification before writing the design. A manifest
the person supplied becomes an input item in `inputs.yml` in its own right (plain type `csv` or
`tsv`, hashed, `source` saying it is the sample manifest); no step consumes it, but the design was
derived from it, so it belongs in the trace.

If there is no manifest and the design is encoded in sample names, propose a parse (for example
`treatment_rep1` into `treatment=treatment, replicate=1`), write the parsed table to
`<parent>/declarations/samples.tsv`, show it, and get confirmation. That table becomes an input
item in `inputs.yml` in its own right, so the mapping is in the trace.

## 3. Draft the three files under `<parent>/declarations/`

The three files have these shapes and no other keys (the engine refuses unknown keys in
`inputs.yml`; `design.yml` and `objective.yml` accept plugin-specific extras only where the
plugin's `design_schema` names them):

    # inputs.yml
    inputs: 1
    items:
      - name: <short handle the pipeline binds, e.g. groups>
        path: /absolute/path
        type: <one of the plugin's object_types, or json | table | tsv | csv | text>
        blake3: <64 hex>
        source: <what the person said the file is>
        build: <reference build, only for reference files>          # optional
        derived_from: {run_id, step_id, output, project}              # optional, see below

    # design.yml
    design: 1
    units: {observation: <what a row is>, sample: <what a sample is>, ...}
    factors:
      <factor name>: {column: <column as spelled in the data>, levels: [<as they appear>]}
    batch: [<technical columns>]
    replication_unit: <one of the units>
    holdout: [{type: <kind>, note: <text>}]                         # usually []
    <plugin fields from design_schema, e.g. organism>

    # objective.yml
    objective: 1
    id: <short slug from the person's words>
    question: <one of the plugin's questions>
    contrasts: [[<factor>, <level>, <level>], ...]                  # [] for a processing question
    replication_unit: <equal to the design's>
    min_n_per_group: <the person's number, else the plugin default>
    deliverables: [<output names the pipeline produces>]
    domain: {}
    params: {<step id>: {<parameter>: <value>}}                     # optional, engine 0.2.18

`inputs.yml`: one item per file the person named, plus the manifest (section 2). `name` is the
handle the pipeline's first step binds (read `pipelines/<name>.yml`: `inputs: {object:
$inputs.groups}` means the handle is `groups`); `path` is absolute; `type` from the plugin's
object types; `blake3` computed with `python3 -c "import blake3,sys;
print(blake3.blake3(open(sys.argv[1],'rb').read()).hexdigest())" <path>` (the engine's venv has
it); `source` is what the person said the file is. If a file is a delivered artifact of an
earlier stringency run (a sidecar `<file>.stringency.json` sits beside it), add `derived_from`
with `run_id`, `step_id`, and `output` copied from that sidecar's `run_id`, `step_id`, `name`,
and `project` set to the upstream project's root directory (the parent of its `deliver/`).

`design.yml`: `units` (observation and sample, from the manifest's row and grouping), `factors`
(from the confirmed classification, `column` exactly as spelled in the data, `levels` exactly as
they appear), `batch` (the confirmed technical columns), `replication_unit` (the unit the person
named as the independent replicate; if they did not, ask, do not infer), `holdout` (only what the
person named).

`objective.yml`: `id` (a short slug from the person's words), `question` (from the plugin
list), `contrasts` as `[factor, level, level]` triples using declared factors and levels only,
`replication_unit` equal to the design's, `min_n_per_group` (the person's number; if none, the
plugin's published default, and say so), `deliverables` (what the person asked to get out, named
exactly as the producing module declares them: read `modules/<module>/module.yml` `outputs:` for
each step of the pipeline and enumerate the names; a `$steps.<id>.<name>` reference in the
pipeline is a consumer, not the list of what exists, and a report step's outputs count too),
`domain: {}` unless the plugin's documentation names domain fields the person supplied. `params`
(optional): a parameter the person fixed in their own words for a step of the pipeline, such as
the organ of an upstream project; name the step id and the parameter as the pipeline or the
module declares them (`declare --check` refuses any other). The echo-back lists it and the
confirm covers it; the step then takes it as given, and no proposal hold opens for it. Never
write a value the person did not give.

Ambiguities to ask about rather than resolve: "compare A, B, and C" (pairwise or one omnibus
contrast); whether replicate means sample or a grouping of samples; whether a column is biology
or batch; which of several files is the primary object.

## 3a. What may leave this machine

Ask the person, in these words or close to them: "What may leave this machine while this project
runs? The engine sorts it into five classes: 0, nothing leaves; 1, public reference data is
downloaded and nothing from the project is sent; 2, names or identifiers from the project are
sent as queries; 3, values computed from the data (tables of numbers, summaries) are sent, which
is what a judgment by a hosted model needs; 4, the data, or whatever the operating agent reads,
may be sent whole. Which is the highest you allow?" Their number is `--egress-max`. If they do not
know, say the project can be initialised without one and the report will say none was declared;
do not suggest a number. Never pick it for them, and never infer it from the data's path.

`--operator-model` is a fact, not a choice: `hosted` when you, a hosted model, will operate the
project (the default); `none` only when the person says they will operate it themselves at a
terminal; `local` only when they say the operating agent runs on a model on this machine.

## 4. Check

    stringency declare --check <parent>/declarations --method <url>@<tag> --pipeline <name> \
        [--profile ...] [--executor ...] [--judgment-harness ...] \
        [--egress-max <0-4>] [--operator-model hosted|local|none]

Exit 0 prints the echo-back and the data egress report. Exit 15 names the field, hash, or `init.*`
predicate that failed: fix the file if the fix has a source in the brief or the manifest,
otherwise ask. Loop until clean. Never edit a value to make the check pass without a source for
the new value. `init.egress_exceeds_ceiling` is different: the files are fine and the setup sends
more than the person allowed. Show its reason verbatim, then ask whether they want a higher
ceiling or a different setup (the reason names each part over the ceiling; a part's harness or
operator model is a project setting, a step's runner or a module's scripts belong to the method).
Do not choose for them and do not change a setting they did not name.

## 5. Present and hand over

Show the person the echo-back verbatim, then the data egress report verbatim, followed by a table
of every field you wrote and its source (manifest column, brief sentence quoted, plugin default;
for the ceiling, the person's answer quoted). Wait for a yes. Then:

    stringency init <project> --method <url>@<tag> --pipeline <name> \
        --objective <parent>/declarations/objective.yml --design <parent>/declarations/design.yml \
        --inputs <parent>/declarations/inputs.yml --drafted-by agent --brief <parent>/brief.md \
        [--profile ...] [--executor ...] [--judgment-harness ...] [--owner ...] [--reviewer ...] \
        [--egress-max <0-4>] [--operator-model hosted|local|none]

`init` exits 10 with the confirm hold and the egress hold. Report both hold ids and the messages
verbatim, the confirm hold first, and stop. You never accept either hold; the person does, after
reading `echo.md` and `prov/egress.md`.

## Rules

1. No value without a source. Your summary lists the source of every field.
2. Ask, do not pick, when two readings are possible.
3. Never run `init` before the person has seen the echo-back from `declare --check` and said yes.
4. Never accept, override, reject, or defer a hold.
5. Report every exit code; 15 from `declare --check` is a normal part of the loop, not a failure
   to hide.

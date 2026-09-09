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

The engine is `stringency` (mode A: in the sandbox at `/usr/local/lib/stringency/current/bin`;
mode B: on the registered compute host, prefixed the way the operator skill describes). Export the
`STRINGENCY_OPERATOR*` variables as the operator skill says; `init` records them as the drafter.

## 0. What the plugin knows

Run `stringency plugins list --json` once. For the plugin the person's method uses, read:
`questions` (the only values `objective.question` may take), `object_types` (the only values an
input `type` may take, plus `json`, `table`, `tsv`, `csv`, `text` for plain files),
`design_schema` (which design fields are required and what shape they have), and
`vocabulary_terms`. If the person's question fits no entry in `questions`, stop and say so: that
is a plugin gap, not something to approximate.

## 1. Save the brief

Write the person's own words, verbatim, to `<parent>/brief.md`, where `<parent>` is the
directory the project will be created in. Do not paraphrase. Append nothing. This file goes into
the project as `brief.md` and its hash is bound into the confirm hold.

## 2. Read the manifest

If the person gave a sample manifest (one row per sample, columns for the variables), read it and
list every column with the values it takes. Classify each column as a factor (biology the
experiment varies), a technical variable (batch, slide, lane, date), an identifier (sample id,
file name), or a measurement, and show the person the classification. Do not guess from column
names alone; ask for confirmation of the classification before writing the design.

If there is no manifest and the design is encoded in sample names, propose a parse (for example
`treatment_rep1` into `treatment=treatment, replicate=1`), write the parsed table to
`<parent>/declarations/samples.tsv`, show it, and get confirmation. That table becomes an input
item in `inputs.yml` in its own right, so the mapping is in the trace.

## 3. Draft the three files under `<parent>/declarations/`

`inputs.yml`: one item per file the person named. `name` is a short handle; `path` is absolute;
`type` from the plugin's object types; `blake3` computed with `python3 -c "import blake3,sys;
print(blake3.blake3(open(sys.argv[1],'rb').read()).hexdigest())" <path>` (the engine's venv has
it); `source` is what the person said the file is. If a file is a delivered artifact of an
earlier stringency run (a sidecar `<file>.stringency.json` sits beside it), add `derived_from:
{run_id, step_id, output}` copied from that sidecar's `run_id`, `step_id`, `name`.

`design.yml`: `units` (observation and sample, from the manifest's row and grouping), `factors`
(from the confirmed classification, `column` exactly as spelled in the data, `levels` exactly as
they appear), `batch` (the confirmed technical columns), `replication_unit` (the unit the person
named as the independent replicate; if they did not, ask, do not infer), `holdout` (only what the
person named).

`objective.yml`: `id` (a short slug from the person's words), `question` (from the plugin
list), `contrasts` as `[factor, level, level]` triples using declared factors and levels only,
`replication_unit` equal to the design's, `min_n_per_group` (the person's number; if none, the
plugin default, and say so), `deliverables` (what the person asked to get out, as output names
the pipeline produces; run `stringency lint <method>` or read the pipeline to find the names),
`domain: {}` unless the plugin's documentation names domain fields the person supplied.

Ambiguities to ask about rather than resolve: "compare A, B, and C" (pairwise or one omnibus
contrast); whether replicate means sample or a grouping of samples; whether a column is biology
or batch; which of several files is the primary object.

## 4. Check

    stringency declare --check <parent>/declarations --method <url>@<tag> --pipeline <name> \
        [--profile ...] [--executor ...] [--judgment-harness ...]

Exit 0 prints the echo-back. Exit 15 names the field, hash, or `init.*` predicate that failed:
fix the file if the fix has a source in the brief or the manifest, otherwise ask. Loop until
clean. Never edit a value to make the check pass without a source for the new value.

## 5. Present and hand over

Show the person the echo-back verbatim, followed by a table of every field you wrote and its
source (manifest column, brief sentence quoted, plugin default). Wait for a yes. Then:

    stringency init <project> --method <url>@<tag> --pipeline <name> \
        --objective <parent>/declarations/objective.yml --design <parent>/declarations/design.yml \
        --inputs <parent>/declarations/inputs.yml --drafted-by agent --brief <parent>/brief.md \
        [--profile ...] [--executor ...] [--judgment-harness ...] [--owner ...] [--reviewer ...]

`init` exits 10 with the confirm hold. Report the hold id and the message verbatim and stop.
You never accept the hold; the person does, at a terminal, after reading `echo.md`.

## Rules

1. No value without a source. Your summary lists the source of every field.
2. Ask, do not pick, when two readings are possible.
3. Never run `init` before the person has seen the echo-back from `declare --check` and said yes.
4. Never accept, override, reject, or defer a hold.
5. Report every exit code; 15 from `declare --check` is a normal part of the loop, not a failure
   to hide.

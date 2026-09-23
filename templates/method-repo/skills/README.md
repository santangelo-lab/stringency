# skills/: what a person sees, and how a person starts

Two files per pipeline, both committed and versioned with the method. Neither changes what runs.
The engine repository's `spec/method-skills.md` is the full page; this file is the short form.

| file | read by | what it states |
|---|---|---|
| `<pipeline>.yml` | `stringency present`, the operator skill | the delivery skill (design 14.4): which delivered tables to show after a run, in which columns and formats; which files to send; what to render at a flag hold; what never to show |
| `<pipeline>.analyze.yml` | `render_skill.py` in the engine repository | the source of the analysis skill (design 10.4): the person-facing entry point for this pipeline, rendered to `stringency-analyze-<name>/SKILL.md` and published in each person's Claude Science instance |

The rendered `stringency-analyze-<name>/SKILL.md` is committed here too; it is generated, so edit
the `.analyze.yml` and render again:

    <engine python> <engine repo>/integrations/claude-science/render_skill.py . --pipeline <pipeline> --check
    <engine python> <engine repo>/integrations/claude-science/render_skill.py . --pipeline <pipeline> --write

`--check` reads `pipelines/<pipeline>.yml` and the modules, so the step ids and titles, the
question, and the deliverable names in the skill are the ones the engine uses; it fails when
they differ. `stringency lint .` warns when a pipeline has a `skills/<pipeline>.yml` and steps
without titles: the skills speak in titles, so title every step.

## `<pipeline>.analyze.yml` fields

| field | what |
|---|---|
| `pipeline` | the pipeline name, as in `pipelines/<pipeline>.yml` |
| `name` | optional slug for the skill name `stringency-analyze-<name>`; default is the pipeline name |
| `method` | `<url or path>@<tag>` the skill passes to `declare --check` and `init`; bump the tag when the method is tagged |
| `plugin` | the plugin whose `plugins list --json` entry the skill reads (`questions`, `object_types`, `defaults`) |
| `question` | the objective question this pipeline answers; must be in the pipeline's `answers` |
| `title` | the skill's heading, in the person's words ("Compare groups in a toy table") |
| `summary` | optional one sentence that opens the description; default is the title |
| `phrasings.positive` | clauses completing "Load when the person ...": what people say when they want this analysis |
| `phrasings.negative` | clauses completing "Do not load for ...": the neighbours this skill must not catch |
| `steps` | step id to title, every step of the pipeline in order, titles equal to the pipeline's |
| `deliverables` | output name to one sentence saying what the person receives; names are module outputs |
| `asks` | the declare questions this pipeline always needs, in lay words, asked one at a time in this order |
| `defaults_to_say` | plugin default key to the lay phrase for it; the skill reads the value from `plugins list --json` and says it aloud before the echo-back |

`example.analyze.yml` beside this file has the shape. The rendered skill carries the nine body
rules and the hold protocol of `spec/plans/ux-two-audiences.md` sections 4 and 5.1 verbatim;
the template supplies them, not this file.

## `<pipeline>.phrasings.yml`

The routing test set for the description: twenty positive and ten negative phrasings, each with
the intended outcome (`analyze`, `declare-only`, `operator-only`, `none`). Run by hand in a
Claude Science session after each revision of the description until a skill evaluation tool is
confirmed there; record the results in `<pipeline>.phrasings.results.md`.

# Writing a method

A method is a git repository the engine clones at a tag: pipelines, modules (code, prompts,
schemas, controls), a policy, environment specifications and the two skill files per pipeline.
Everything that constitutes the analysis is committed before it runs; data, logs and generated
figures stay out. The design is `spec/stringency-design.md` (sections 3, 6.4, 10.3, 11, 14.4);
this page is the working order.

## Start

Copy `templates/method-repo/` and read its README. The worked example is the toy method at
`plugins/stringency-toy/method` (three pipelines, five modules, one judgment with controls,
titles on every step); the production example is `stringency-xenium-method`. Install the
pre-commit hook so `stringency lint .` runs on every commit.

## Say what you need

`policy.yml` `requires:` names the engine and the plugin versions the method needs:

    requires:
      engine: '>=0.2.20'
      plugins:
        stringency-singlecell: '>=0.5.1'

`lint` checks it against what is installed (an error when unmet, a warning when absent);
`declare --check`, `init` and run open refuse when the install does not satisfy it. Bump it when
a module relies on something newer. Specs are comma-separated operator clauses (`>=`, `<`, `==`
and so on); a release candidate sorts below its release.

## Modules, pipelines, versions

One directory per module with `module.yml` (contract 1), the script the engine runs
(`pre.*`), the parameter schema, and for a judgment the prompt, the response schema and the
controls. A pipeline pins each module by `name@version`. When a module's script or manifest
changes, bump its version and the pin, and bump the pipeline's version too: a project records
the pipeline and module versions it ran, so a change without a bump is invisible in provenance.

Shared code lives once, beside the modules (`modules/_rlib/` for R, `modules/_pylib/` for
Python), and a module reaches it relative to its own script: the engine binds the whole method
checkout read-only into every step's container (engine 0.2.20). A directory under `modules/`
without a `module.yml` is not a module and lint ignores it.

Environments: `envs/manifest.yml` names each environment's lockfile (local executor) or image
and sha256 (apptainer). Name images by file name and let the site say where they are
(`docs/install.md`); build them from the repository (the Xenium method's `envs/README.md` and
`.github/workflows/image.yml` are the pattern).

## Skills

Two files per pipeline under `skills/`, both committed and versioned with the method
(`spec/method-skills.md`): the delivery skill `<pipeline>.yml` says what a person sees after a
delivery and at each hold (tables, figures, the console card's question, a table filtered by the
proposed parameter); the analysis-skill source `<pipeline>.analyze.yml` is rendered by
`integrations/claude-science/render_skill.py` into the skill a person loads by describing their
experiment. `render_skill.py <repo> --pipeline <name> --check` fails when the skill and the
pipeline disagree. Title every step: the skills, the progress sentences and the summary speak in
titles.

## Tools for questions

A module whose `modes` list `open` is a tool: after a pipeline delivers, the operator may run it
on demand on the delivered files or on what earlier tools produced, and an answer that rests on
it is labelled trusted when the tool has a current control (open mode, engine 0.2.22,
`docs/open-mode.md`). A tool is an ordinary module (`module.yml`, `params.schema.json`,
`pre.*`, `decision_points`); what makes it trustable is `controls/`: a positive control with
`params` (the values it runs with) and `expect.equals` against a truth table keyed by a column
(`columns`, `tolerance`), and a negative control with a generator and `expect.count`. A figure
tool has `expect.completed: true`. `lint` warns on a tool with no positive control, in the words
the person will read: its outputs will be labelled untested. A tool is controlled alone, on its
fixture, whatever pipeline also uses it. The words the skill says about a tool go in
`skills/<pipeline>.analyze.yml` `tools:` (title, use-when, the asks for its decision points) and
`open:` (the paths the operator proposes before the switch); `skills/open.yml` says what
`present --answer` shows beside an answer; `skills/<pipeline>.questions.yml` is the routing test
set. The worked example is `compare-groups` and `plot-groups` in the toy method.

Promoting a session's code into a tool (open_mode_plan.md phase 4, not built): an answer the
operator keeps giving with `exec` is the candidate; the script is in the trace
(`runs/<run>/<step>/script.<ext>`, `messages` under its hash) and the exec's inputs and outputs
are the fixture and the truth table of its first control.

## Check, run, tag

    stringency lint .                       # errors fail; read the warnings
    stringency probe --method .             # requires and images on this machine
    <method>/controls/synthetic_run.sh HEAD # a full engine run on synthetic data (write one per method)

A synthetic end-to-end run on the mock judgment harness is the method's own smoke test and the
first thing a new site runs. Tag release candidates (`v0.6.0-rc15`) as projects run on them;
a project records its tag and commit, so a tag is never moved. When a combination of engine,
plugin and method has delivered a real project or passed the synthetic runs, add a row to the
engine repository's `compat/known-good.yml`.

## CI

Copy `templates/method-repo/.github/workflows/ci.yml`: on a bare runner it installs the engine
and plugin at the tags `requires` names, lints, checks the analysis skills, and runs the unit
tests that need no container. Container runs stay on the workstation; the README's Develop
section says which scripts need it.

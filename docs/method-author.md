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

One directory per module with `module.yml` (contract 1), the script the engine runs (named
after the module and set by `entry:`; "Module scripts" below), the parameter schema, a
`CHANGELOG.md`, and for a judgment the prompt, the response schema and the controls. A pipeline pins each module by `name@version`. When a module's script or manifest
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

## Module scripts

The module's script is the analysis: it is what a person opens to see what the method does and
which tools it uses, and what they read when a result looks wrong. Write it for that reader.
The skeletons are `templates/module/r/` and `templates/module/python/`; the shared plumbing is
`templates/method-repo/modules/_rlib/stringency_io.R` and `_pylib/stringency_io.py`, which a
method copies.

Names. The script is the module's name with underscores (`cluster-umap/cluster_umap.R`), set
with `entry:` in `module.yml`. A judgment module's script builds the evidence the reviewers read,
not the labels, and is `<name>_evidence.py`. A file that serves one module only stays beside its
script under a descriptive name. The engine still falls back to `pre.*` when `entry:` is absent;
new modules do not rely on it.

Header. At most fifteen lines, in plain words: what the step does, its inputs and outputs, the
parameters that are analysis choices, the tools by package and function. No version history:
that goes in the module's `CHANGELOG.md`, newest first, and a version bump adds an entry there.

Shape. Every script reads in the same order, so a person who has read one can find their way in
any other:

    header
    shared code (stringency_io and any topic files)
    job <- read_job()
    ---- Parameters ----          each read once, with a comment; log_params(...)
    ---- 1. Load ----
    ---- 2. ... ----              numbered steps named for what they do
    ---- Record for stringency ---- flags, figure list, summary facts
    ---- Write outputs ----

Python puts the same order inside `main()` under an `if __name__ == "__main__":` guard.

Rules. One statement per line; lines of 100 characters at most; no anonymous function longer
than a line. Calls a reader recognises (`FindClusters`, `sc.pp.neighbors`) stay in the script.
A long custom algorithm moves into a named function with a comment saying what it does, in a
topic file under `_rlib/` or `_pylib/` (`clustering.R`, not `utils.R`), loaded with
`source_lib()` or imported. Stringency's bookkeeping (flags the plugin reads, the figure list,
summary JSON) comes after the analysis, so the analysis reads without it, and just before the
outputs are written, since a flag lives on the object that is written.

Plumbing. `stringency_io` gives the same names in both languages: `read_job`, `log_params` (the
`params: name=value` line the engine reads back from an operator-run step's log and compares
with the admitted values; lists and text with spaces go on an `other params:` line it does not
read), `say`,
`read_table`, `write_table`, `fig_start`, `fig_save`, `fig_finish`, `stringency_flags`,
`set_flag`, and in R `source_lib`. It loads no analysis package; a script loads its own
(`library(Seurat)`, `import scanpy as sc`), so the tools are visible at its top.

Style is checked, not hoped for. The template carries `ruff.toml` and `.lintr`; its pre-commit
hooks and CI run `ruff check`, `ruff format --check` and `lintr` over `modules/`. Code copied
unchanged from elsewhere is listed in `extend-exclude` and the `.lintr` exclusions rather than
reformatted.

The README of the method has, per pipeline, a table of its steps: the step, a link to the
script, what it does, the main tools. A person new to the method starts there.

## Bringing existing code in

Most modules start as someone's script. An agent can do the wrapping by the skill
`integrations/claude-science/stringency-wrap/SKILL.md`, which follows this section and checks the
module against the original's output. Three shapes, from the most common:

- A script with hard-coded paths and constants. Copy it to
  `modules/<name>/<name_with_underscores>.R` (or `.py`).
  Replace the block that sets paths and constants with the job: inputs from `job$inputs`,
  constants that are analysis choices from `job$params`, output paths from `job$outputs`. Declare
  the same names in `module.yml` and `params.schema.json` (defaults from the old constants), add
  the header, and reorder into the shape above as far as the code allows. Keep the code's own
  reading and writing of files, so its outputs stay byte for byte; `stringency_io` gives the job
  and the log.
- A library of functions. Copy the file unchanged into `_rlib/` or `_pylib/` with a provenance
  header (where it came from, the commit, the date) and mark each later edit `# stringency:`
  (the Xenium method's `_rlib/Xen_Seurat_functions.R`, from ROSC_MTA2, is the example). List it in
  the style exclusions. A short module script calls it.
- A command-line tool or a workflow (Nextflow, Snakemake). The module script builds the command
  line from the job and runs it, writes the declared outputs from what it produced, and the module
  declares `egress` if the tool fetches anything (the Xenium method's `resegment-nextflow`).

Then, whichever shape: `decision_points` for the parameters that are analysis choices; for a
tool, a fixture and a positive control; a version, the pipeline's pin; `stringency lint .`; one
run of the script on a small input with a hand-written job (`Rscript <name>.R < job.json`) before
the first engine run.

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
its script, `decision_points`); what makes it trustable is `controls/`: a positive control with
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

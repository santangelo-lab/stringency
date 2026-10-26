---
name: stringency-wrap
description: Turn an existing analysis script, function library or command-line tool into a stringency module in a method repository, by the method-author guide's module-script convention. Writes module.yml, params.schema.json, the named script and CHANGELOG.md, runs the script once on a small input against the original's output, and lints. Load when a person wants to bring their own code (a Seurat or scanpy script, an R or Python file of functions, a Nextflow or command-line pipeline) into stringency, or asks to wrap, port, or convert code into a module or a tool. Do not load for drafting a project's declarations (the declare skill) or for running an analysis (the operator skill and the analysis skills).
license: MIT
---

# stringency-wrap

You bring a person's existing code into a stringency method as a module. You translate; you do
not reanalyse. The module must compute what the person's code computes: the same values, the
same files, the same figures. Every analysis choice the code makes becomes a parameter the
person names and defaults, and nothing in the code changes without their word.

The convention you write to is the engine repository's `docs/method-author.md`, sections "Module
scripts" and "Bringing existing code in". The skeletons are `templates/module/r/` and
`templates/module/python/`. The plumbing every script uses is `modules/_rlib/stringency_io.R`
or `modules/_pylib/stringency_io.py` in the method; a method that lacks it copies it from the
engine's `templates/method-repo/modules/`. Read those before you write anything. The engine is
`stringency` on the PATH (`stringency probe` says what is installed), or `uv run stringency` in
the engine's checkout. In a Claude Science session, the operator skill's section 1 says how to
reach it on the compute host.

## 0. What you need before you start

- The code, read whole. If it calls other files of the person's (a `source()`, an import),
  read those too.
- The method repository the module goes into, and its `policy.yml` `requires`.
- What the plugin knows. Run `stringency plugins list --json` once and read two lists:
  - `operations`: the only values `module.yml` `operation` may take. The list gives names only.
    Read the plugin's README and `spec/predicates.md` for what each covers and which predicates
    are scoped to it: a predicate sees the work of the operation it is scoped to, and nothing
    the same code does under another operation.
  - `object_types`: the values an input or output `type` may take. Plain files take the generic
    types the method's other modules use: `table` (with `format: csv` or `tsv`), `json`,
    `text`, `figure` for one image, and `figures` for a directory of them. Write each as
    `{type: table, format: csv}`.

  If no operation fits what the code does, stop and say so. That is a plugin gap, not something
  to approximate. If the code does the work of two operations (it filters and then
  summarises, say), ask the person whether to make two modules. One module under one
  operation hides the other half from the predicates scoped to it.

## 1. Read the code into five lists

Write these down and show them to the person.

1. **Inputs**: every file or directory the code reads, with what it is (a count matrix, a
   Seurat object, a table with these columns).
2. **Outputs**: every file it writes, figures included.
3. **Constants**: every number, string or switch that is a choice (a threshold, a resolution, a
   method name, a gene list), with its value in the code. Separate the analysis choices from
   settings that only make it run (cores, memory, a temporary path).
4. **Tools**: the packages and the functions that do the analysis.
5. **Randomness and the network**: any seed, any sampling, any download or remote call.

## 2. Ask the person

One message, short:

- The module's name (a few words with hyphens, for example `cluster-cells`). The script is that
  name with underscores.
- Which constants are analysis choices that a person signs off. These become `decision_points`.
  The rest become ordinary parameters with the code's values as defaults.
- Where it runs:
  - a step of a pipeline (which one, and after which step);
  - a tool for questions after delivery (`modes: [open]`);
  - both;
  - or a module only for now. That is `modes: [pipeline]` with no step yet: a pipeline can
    pin it later.
- The environment: which entry of the method's `envs/manifest.yml` has the packages. If none
  does, say which packages are missing. Building an image is the person's step, not yours.

Do not guess any of these. If the code's own comments answer one, quote the comment and ask the
person to confirm. A constant that only formats the output (rounding, a column label, a figure
size) stays in the code unless the person asks for it as a parameter.

## 3. Choose the shape

- **A script with hard-coded paths** (the common case). Copy it to
  `modules/<name>/<name_with_underscores>.R` (or `.py`). Replace the block that sets paths and
  constants with the job: inputs from `job$inputs`, choices from `job$params`, output paths from
  `job$outputs`. Then lay it out in the convention's order, keeping every computation as it is:
  header, shared code, job, the parameters read once with a comment each, numbered steps, the
  record for stringency, the outputs.
  - Keep the code's own reading and writing (`read.csv`, `write.csv`, `pandas.to_csv`,
    `csv.DictWriter`). `stringency_io`'s table helpers may differ in line endings or quoting,
    and the outputs must stay byte for byte. Use `stringency_io` for the job (`read_job`) and
    the log (`say`, `log_params`).
  - Name the inputs and outputs for what the file is (`counts`, `cluster_summary`), in snake
    case; where the plugin's modules have a convention (`object` for the main input), follow
    it.
  - What the code printed as a result (`highest: A`) stays a log line; if the person wants it
    kept, it becomes an output table.
- **A library of functions.** Copy the file unchanged into `modules/_rlib/` or `modules/_pylib/`.
  Give it a provenance header: where it came from, the commit or date, and that edits are marked
  `# stringency:`. List it in the method's `.lintr` exclusions or `ruff.toml` `extend-exclude`,
  since vendored code is not reformatted. A short module script calls it.
- **A command-line tool or a workflow** (Nextflow, Snakemake). The module script builds the
  command line from the job, runs it, and puts what it produced at the declared output paths.
  If the tool fetches anything (a pipeline from GitHub, a reference, a container), the module
  declares `egress: {class, hosts, sends}`. Lint fails a script that reaches the network
  without one.

Keep an R script R and a Python script Python. Do not port between languages.

## 4. Write the module

In `modules/<name>/`:

- **The script.**
  - The header: at most fifteen lines, plain. What the step does; `In:` and `Out:` one line
    each; `Choices:` (the decision points); `Tools:` (package and function); `History:
    CHANGELOG.md`.
  - One statement per line, and lines of 100 characters at most.
  - Recognisable library calls stay in the script. A long custom algorithm becomes a named
    function with a comment saying what it does.
  - Load packages at the top, so the tools are visible. Set the seed where the code drew
    randomness, in the same place relative to the draws.
  - Log the parameters with `log_params`, whatever the runner. For an operator-run module the
    engine reads the `params:` line back and compares it with the admitted values.
- **`module.yml`.**
  - `contract: 1`, `name`, `version: 0.1.0`, `kind: deterministic`, `operation`, `domain` (the
    plugin), `modes`, `env`, `runner: engine`.
  - `entry: <the script>`, `inputs` and `outputs` with plugin types, `decision_points`.
  - `stochastic: true` and `seed_param` when the code draws randomness; `egress` when it reaches
    the network; `resources`.
  - `gates`: run `stringency lint` and list the in-scope predicates it names in its warnings.
    Predicates scoped to every module (`obj.feasibility` and the like) run whether listed or
    not; list them too if the method's other modules do.
- **`params.schema.json`.** One property per parameter, with the code's value as `default`, a
  `description` in plain words, and a range where the person gave one. `required` lists them
  all, and `additionalProperties: false`.
- **`CHANGELOG.md`.** One entry, `0.1.0`: where the code came from (path, repository and commit,
  or the person's words), and every change from the original. Normally the only changes are the
  job replacing the paths and the layout.

If the module joins a pipeline, add its step (`module: <name>@0.1.0`, inputs wired from earlier
steps, parameters with defaults and ranges) and bump the pipeline's version. A tool for
questions needs `controls/` with a positive control on a small fixture with a truth table
(`docs/method-author.md`, "Tools for questions"); without one, lint warns that its outputs will
be labelled untested. Add the script to the README's index of steps and scripts if the method
keeps one (`tools/check_index.py` checks it).

## 5. Check it

1. **The same output.** Run the original code and the module script on the same small input, in
   the module's environment.
   - Feed the module a hand-written job on stdin, with paths in a scratch directory. The job is
     a JSON object with `inputs`, `params`, `outputs` (name to path) and `seed` (null unless
     the module is stochastic); the module contract has the full shape.
   - For an image: `apptainer exec <image> Rscript modules/<name>/<script> < job.json`.
   - For a lockfile environment (`envs/<name>/uv.lock`): `uv run --project envs/<name>
     python modules/<name>/<script> < job.json`. If that Python is not the version the lockfile
     asks for, say so rather than use another.

   Compare every output: tables byte for byte; objects by their contents (R: `all.equal` on
   the parts an analysis reads; Python: anndata's `obs`, `var`, `X`, layers, `obsm`); figures
   by eye or by bytes. Any difference is a mistake in the wrapping until
   proven otherwise. Find it, or show it to the person.
2. **The method's checks.** Run `stringency lint .`, the method's ruff and lintr checks if it
   has them, and its tests.
3. **Once under the engine,** when the person wants it: a control (`stringency controls run
   --module <name>`) for a tool, or the pipeline on the method's synthetic fixture.

## 6. Report

Tell the person:

- the module's files;
- what each decision point is, with its default;
- what you checked and the result: "identical outputs on <input>", or what differs;
- what remains, with whose step it is: a missing package in the image, a plugin operation or
  object type that does not exist, a fixture for a control, the commit.

Do not commit, push or tag unless the person asks.

# module skeletons

A module in a method repository is a directory `modules/<name>/` with `module.yml`, the script
the engine runs, `params.schema.json` and `CHANGELOG.md` (the engine's `docs/method-author.md`,
"Module scripts"). These two skeletons are complete, runnable modules: one in R, one in Python.
Both keep the rows of a table at or above a threshold.

To start a module:

1. Copy `r/example-step/` or `python/example-step/` to `modules/<name>/` in the method.
2. Rename the script to `<name with underscores>.R` (or `.py`) and set `entry:` in `module.yml`
   to the new name.
3. Fill in `module.yml` (operation, domain, env, inputs, outputs, decision points) and
   `params.schema.json`. The script's header says the same things in plain words.
4. Replace the numbered analysis sections with yours, keeping the order: header, shared code,
   job, parameters, numbered steps, write outputs, record for stringency.
5. `stringency lint .`

The skeletons source `stringency_io.R` or import `stringency_io.py` from `modules/_rlib/` or
`modules/_pylib/`, which the method-repo template carries. A judgment module (prompt, response
schema, controls) starts from the toy method's `label-groups` instead; its script, when it has
one, is `<name>_evidence.py`.

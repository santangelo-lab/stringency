# method repo template

Everything that constitutes the method lives here and is committed before it runs (Commandment 3):
pipelines, modules (code, prompts, schemas, controls), the policy, environment specifications, and
session notes. Data, run logs, and generated figures stay out.

```
pipelines/<name>.yml        topology with parameter defaults and ranges (design 3.1)
modules/<name>/             one directory per module (design 3.2): module.yml, <name>.R or <name>.py
                            (set by entry:), params.schema.json, CHANGELOG.md; run `stringency lint .`
modules/_rlib/, _pylib/     shared code: stringency_io.R / stringency_io.py (job, log, tables,
                            figures, flags) and the method's topic files
ruff.toml, .lintr           the style of the module scripts, checked by pre-commit and CI
policy.yml                  dispositions per profile, ranges, criteria (design 6.4)
envs/manifest.yml           environment names -> lockfile or SIF image and sha256 (design 10.3)
envs/<name>/uv.lock         lockfile for the local executor
controls/fixtures/          fixtures identified by hash (design 11)
skills/<pipeline>.yml       what a person sees after delivery and at a hold (design 14.4); skills/example.yml
skills/<pipeline>.analyze.yml  source of the analysis skill, rendered to skills/stringency-analyze-<name>/SKILL.md (spec/method-skills.md)
skills/open.yml             what a person sees of an answer in open mode (answer_view per tool; engine 0.2.22)
skills/<pipeline>.questions.yml  the routing test set for open mode: questions and the route each should take
notes/YYYY-MM-DD-hhmm-<slug>.md   one small file per session (Commandment 2)
```

`policy.yml` `requires:` names the engine and plugin versions the method needs; `lint`, `init` and
run open check it. A module whose `modes` list `open` is a tool for questions after delivery
(open mode): give it a positive control with `expect.equals` against a truth table, or `lint`
warns that its outputs will be labelled untested (`docs/method-author.md`, "Tools for
questions").

Shared code goes once under `modules/_rlib/` or `modules/_pylib/` (the engine binds the checkout
read-only into every step). Start a module from the skeletons in the engine's `templates/module/`;
how a module script is named, laid out and checked, and how to bring an existing script in, is
`docs/method-author.md`, "Module scripts" and "Bringing existing code in".

Install the pre-commit hook (`pre-commit install`, `.pre-commit-config.yaml`) so `stringency
lint`, `ruff` and (where R and lintr are installed) `lintr` run on every commit, and data files,
`run.db` and files over 10 MB are refused; `.github/workflows/ci.yml` runs lint, the style checks
and the skill check on a bare runner. The worked example is the toy method in the engine
repository, `plugins/stringency-toy/method`; the guide is `docs/method-author.md`.

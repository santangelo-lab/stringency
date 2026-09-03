# method repo template

Everything that constitutes the method lives here and is committed before it runs (Commandment 3):
pipelines, modules (code, prompts, schemas, controls), the policy, environment specifications, and
session notes. Data, run logs, and generated figures stay out.

```
pipelines/<name>.yml        topology with parameter defaults and ranges (design 3.1)
modules/<name>/             one directory per module (design 3.2); run `stringency lint .`
policy.yml                  dispositions per profile, ranges, criteria (design 6.4)
envs/manifest.yml           environment names -> lockfile or SIF image and sha256 (design 10.3)
envs/<name>/uv.lock         lockfile for the local executor
controls/fixtures/          fixtures identified by hash (design 11)
notes/YYYY-MM-DD-hhmm-<slug>.md   one small file per session (Commandment 2)
```

Install the pre-commit hook (`pre-commit install`) so `stringency lint` runs on every commit and
data files, `run.db`, and files over 10 MB are refused.

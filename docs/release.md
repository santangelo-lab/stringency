# Releasing and installing: the recurring jobs

The jobs a maintainer repeats, each a short block of commands with placeholders (`<prefix>`, the
engine install directory; `<group>`; `<projects>`, the data root). Keep your site's values in a
private note of your own and fill them in. The AI can run every block except the pushes, the
install on a shared machine and a service restart, which it will ask you to run.

## Release the engine

From a clean `main` with the suite green:

    # version in pyproject.toml and src/stringency/__init__.py, the version line in tests/golden/methods_toy_engine.md
    # and the operator skill's "This text is for engine X.Y.Z" line, when its text names a feature of this release
    # (tests/test_operator_skill_line.py fails when the line is below a version the text names, or above the engine)
    uv lock && git commit -am "Engine vX.Y.Z: ..." && git tag -a vX.Y.Z -m "..."
    git push origin main --tags

Then the install block (`probe` checks the operator skill's "This text is for engine" line),
then the institutional runs and the known-good row below. A release is not finished until its
row is in `compat/known-good.yml`.

## Release a plugin

In `stringency-plugins`: bump `version` in `plugins/<name>/pyproject.toml` and `VERSION` in its
`__init__.py` (a test keeps them equal), raise `stringency>=` and the `tool.uv.sources` tag when
the plugin needs a newer engine (the engine tag must be on GitHub first), then:

    uv lock && git commit -am "<name> X.Y.Z: ..." && git tag -a vX.Y.Z -m "..." && git push origin main --tags

## Tag a method

In the method repository, with `stringency lint .` clean and `requires` in `policy.yml` naming the
engine and plugin it needs:

    git tag -a vX.Y.Z -m "..." && git push origin main --tags

A project records the tag and commit it was initialised on; never move a tag.

## Install on a shared machine

As the user who owns the install, with the group's umask. The label is derived from the sources
(`0.2.20-sc0.5.1`), `current` moves, the old version stays for the runs that cite it, and the block
ends with `probe`:

    umask 002 && scripts/install.sh --prefix <prefix> \
        --source git+https://github.com/santangelo-lab/stringency@vX.Y.Z \
        --plugin 'git+https://github.com/santangelo-lab/stringency-plugins@vA.B.C#subdirectory=plugins/stringency-singlecell' \
        --no-toy
    systemctl --user restart stringency-console.service    # when a standing console serves this install
    stringency probe --method <method url>@<tag> --no-hash

Install only while no run is mid-step (`stringency board <projects>` shows what is running).

## Republish the skills

A person pastes the message in `integrations/claude-science/publish-skills.md` into a Claude
Science session with the workstation as a compute host; the session publishes the engine's skills
from `<prefix>/current/skills/` and each method's analysis skill at its tag. After every engine
release that touches a skill and every method tag with a new or changed analysis skill.

## The institutional runs

CI runs lint, the unit tests and the skill check on a bare runner (`.github/workflows/ci.yml`,
and `compat.yml` on the latest known-good row). What needs the containers, the images and a
method checkout runs on the workstation instead, by hand, with the engine and plugin installed
at the release's tags and each method cloned at its tag. This is the list; each script says
what it needs at its head (the images of the method's `envs/manifest.yml`, apptainer,
`STRINGENCY_SESSION_REF`, the engine as `stringency` on the PATH or `STRINGENCY_BIN`):

| method | run | what it shows |
|---|---|---|
| `stringency-xenium-method` | `controls/synthetic_run.sh <tag>` | `xenium-qc-tma` end to end on the synthetic region (mock judgment), delivered and presented, then the QC again through `xenium-qc-cells` |
| `stringency-xenium-method` | `controls/synthetic_upstream.sh <tag>` | a two-slide synthetic study through `xenium-qc-tma` and `xenium-upstream`: the declared organ, the proposals approved, the sign-off and the annotation on the mock harness, delivered and presented |
| `stringency-xenium-method` | `tests/run_outliers.sh` | the outlier judgment: evidence script, group bands, the engine run on the mock harness, both controls |
| `stringency-scrnaseq-scanpy-method` | `tests/run.sh`, then `stringency controls run` in a project from the fixture's declarations | every module on the planted fixture inside the image; the method's controls |

## Record a known-good combination (every release)

After the install block and the institutional runs, add a row to `compat/known-good.yml` (engine
tag, plugin tags, method tags, date, host, and under `evidence` which runs of the list above
passed) and commit it on `main`. Also add a row when a combination
delivers a real project. The bootstrap installs the latest dated row; the compat workflow lints it.
The beta-tester package (`santangelo-lab/stringency-beta`, 2026-11-03) pins its own combination in
its `channel.yml` from a dated row here; a beta release starts from one.

## Add a member

`docs/onboarding.md`: the group, the SSH alias, the PATH line, their own AI session with its
three one-time steps.

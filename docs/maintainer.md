# Maintaining the lab's stringency

The one page for the owner's recurring jobs: releasing, installing on the shared machine,
restarting the console, republishing the skills, recording a known-good combination. Each job is
a short block of commands. The AI can run every block except the pushes, the install and the
console restart, which it will ask you to run.

## Pending now (2026-10-15)

In this order; each step unblocks the next.

1. Push the engine: `main` and the tags v0.2.17 to v0.2.20.

       cd ~/mytools/stringency/stringency && git push origin main --tags

2. Lock and tag the plugin (its lock needs the engine tag on GitHub).

       cd ~/github/stringency-plugins && uv lock && git add uv.lock && git commit -m "uv.lock: engine v0.2.19" && git tag -a v0.5.1 -m "singlecell 0.5.1" && git push origin main --tags

3. Push the method: `main` and rc14 to rc16.

       cd ~/github/stringency-xenium-method && git push origin main --tags

4. Install `0.2.20-sc0.5.1` on PROTSEQ and restart the console (block "Install on PROTSEQ").
5. Republish the skills (block "Republish the skills"): the operator and declare skills changed
   with 0.2.19, the Xenium analysis skill is new in rc16.
6. Run one organ on rc16 with the console, then pick a tester for the acceptance run
   (`controls/synthetic_upstream.sh` through `stringency-analyze-xenium-upstream`).

## Release the engine

From a clean `main` with the suite green (the AI does this; you push):

    # version in pyproject.toml and src/stringency/__init__.py, the version line in tests/golden/methods_toy_engine.md
    uv lock && git commit -am "Engine vX.Y.Z: ..." && git tag -a vX.Y.Z -m "..."
    git push origin main --tags

Then the install block. The operator skill's "This text is for engine" line is checked by `probe`.

## Release the plugin

In `stringency-plugins`: bump `version` in `plugins/<name>/pyproject.toml` and `VERSION` in its
`__init__.py` (a test keeps them equal), raise `stringency>=` and the `tool.uv.sources` tag when
the plugin needs a newer engine, then:

    uv lock && git commit -am "singlecell X.Y.Z: ..." && git tag -a vX.Y.Z -m "..." && git push origin main --tags

## Tag the method

In the method repository, with `stringency lint .` clean and `requires` in `policy.yml` naming the
engine and plugin it needs:

    git tag -a v0.6.0-rcN -m "..." && git push origin main --tags

A project records the tag and commit it was initialised on; never move a tag.

## Install on PROTSEQ

The classifier refuses an agent writing under `/data/lab/env`, so this is yours. The label is
derived from the sources (`0.2.20-sc0.5.1`); `current` moves; the old version stays for the runs
that cite it; the block ends with `probe`.

    umask 002 && cd ~/mytools/stringency/stringency && scripts/install.sh --prefix /data/lab/env/stringency \
        --source git+https://github.com/santangelo-lab/stringency@v0.2.20 \
        --plugin 'git+https://github.com/santangelo-lab/stringency-plugins@v0.5.1#subdirectory=plugins/stringency-singlecell' \
        --no-toy
    systemctl --user restart stringency-console.service && systemctl --user status stringency-console.service | head -3
    stringency probe --method https://github.com/santangelo-lab/stringency-xenium-method@v0.6.0-rc16 --no-hash

Install only while no run is mid-step (`stringency board /lab/projects/Lyons_CLP/v2_rosc_controls`
shows what is running). From a checkout instead of a tag: `--source .` with the checkout on
`main` at the tag.

## Republish the skills

Paste into a Claude Science session with `protseq` as a compute host (the message is in
`integrations/claude-science/publish-skills.md`, "For a person"); the session publishes the
operator and declare skills from `/data/lab/env/stringency/current/skills/` and each method's
analysis skill at its tag, and replies with what it published. Do it after every engine release
that touches a skill and after every method tag with a new or changed analysis skill.

## Record a known-good combination

When a combination of engine, plugin and method has delivered a real project or passed the
synthetic runs, add a row to `compat/known-good.yml` (engine tag, plugin tags, method tags, date,
host, what ran) and commit. The bootstrap installs the latest dated row; the compat workflow lints it.

## Add a lab member

`docs/onboarding.md`: the AD group request to IT, the SSH alias, the PATH line, their own AI
session with the three one-time steps.

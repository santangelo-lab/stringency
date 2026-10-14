# Installing stringency

For whoever sets up a machine so that others can run analyses on it. A person joining a machine
that is already set up reads `docs/onboarding.md`; a method author reads `docs/method-author.md`.
The lab's own machine is described in `integrations/claude-science/hosts/protseq-lab.md`.

## What gets installed, and where

Three things, versioned separately and checked against each other:

| piece | what it is | where it lives |
|---|---|---|
| the engine | the `stringency` command: gates, holds, the trace | one virtual environment per version under `<prefix>/versions/<label>/`, with `<prefix>/current` pointing at the version in use |
| plugins | a domain's object types, predicates and vocabularies (`stringency-singlecell` for Xenium) | installed into the same environment as the engine |
| methods | a git repository of pipelines, modules, prompts and controls, pinned by tag per project | cloned by the engine into each project at `init`; nothing to install |

A method's `policy.yml` says which engine and plugin versions it needs (`requires`), and
`compat/known-good.yml` in this repository lists the combinations that have run together.
Install one of those unless you are developing.

## Prerequisites

- Linux. Python 3.12 or newer on the system (`/usr/bin/python3`), and `uv`
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- A container runtime for production runs: `apptainer` (or `singularity`). Development and the
  test suite run with the `local` executor and need neither.
- Disk for container images (a few GB each) and for projects.
- A group that every user of the machine belongs to, so projects and the install are readable by
  all of them. On the lab's machine that is an Active Directory group; see the host note.

## Install

From a checkout of this repository, as the user who will own the install, with `umask 002` when
others must read it:

    scripts/install.sh --prefix /data/lab/env/stringency \
        --source git+https://github.com/santangelo-lab/stringency@v0.2.20 \
        --plugin 'git+https://github.com/santangelo-lab/stringency-plugins@v0.5.1#subdirectory=plugins/stringency-singlecell' \
        --no-toy

The script creates the version's environment, derives its label from the sources
(`0.2.20-sc0.5.1`: the engine version, then each plugin's short name and version), copies the
operator and declare skills beside the engine, moves `current`, and ends with `stringency probe`.
Re-run it with new sources to add a version; `current` moves and the old version stays for the
projects that cite it. `--label` overrides the derived label; `--source .` installs the checkout
itself (development).

Put the engine on everyone's `PATH` with one line in each user's `~/.profile`:

    export PATH=/data/lab/env/stringency/current/bin:$PATH

## Container images

A method's `envs/manifest.yml` names each environment's image and its sha256. Since engine
0.2.20 an image may be named by file name, and the engine looks for it under
`$STRINGENCY_IMAGES`, then under `images_root` in the user's `~/.config/stringency/config.yml`,
then in the method checkout and its `envs/` directory; an absolute path is used as given. Keep
every image of the machine in one directory, named `<name>-<version>.sif`, never overwritten (a
new build gets a new name), with a `MANIFEST.md` beside them recording name, version, sha256,
source definition and build date. Set `images_root` once per user:

    mkdir -p ~/.config/stringency && echo "images_root: /data/lab/env/images" > ~/.config/stringency/config.yml

Images come from the method repository's container builds (the Xenium method publishes to GHCR
and the method's `envs/README.md` says how to pull one by digest and convert it to a SIF).

## Check the install

    stringency probe --method <method checkout or url@tag>

prints one line per check: the engine and its path, every plugin and version, the skills beside
the engine, the container runtime, the method's `requires` against what is installed, and every
image the method names (present, readable, hashing to the manifest's sha256; `--no-hash` skips
the hashing). `ready` on the last line means a project on that method can run here.

The smoke test is a synthetic run of a method under the engine. For the Xenium method:

    cd <method checkout> && STRINGENCY_SESSION_REF=<anything> controls/synthetic_run.sh <tag>

runs `xenium-qc-tma` end to end on a generated region with the mock judgment harness in under a
minute, through `init`, the confirm hold, every step and the judgment.

## The console and notifications

`stringency review --serve --projects <dir>` serves the console: every project under the
directory, the open holds as cards, the hold pages with the method's tables and figures, and the
verdict form. Each person starts it under their own account (verdicts are recorded against the
account that serves the page), on loopback, reached through an SSH tunnel; the per-start token is
printed once. `scripts/stringency-console.service` is a `systemd --user` unit for a standing
instance; `scripts/review-page.sh <ssh alias>` opens a tunnel from a laptop. Hold, completion and
delivery notifications go through a per-user `~/.config/stringency/notify.yml` (email through a
relay, a webhook, or a command); without the file nothing is sent.

## Skills for an AI operator

An AI session drives a project through the CLI by following a skill. The engine installs the
two engine skills (`stringency-operator`, `stringency-declare`) at
`<prefix>/versions/<label>/skills/`, and a held `run --json` names the operator skill's path so a
session holding an older published copy can read the current text. Each method repository
carries its analysis skills. Publishing them into a Claude Science instance is per person:
`integrations/claude-science/publish-skills.md`. A Claude Code session on the workstation reads
the skills from the repositories directly.

## Adding a version

Install again with the new sources (above); the label changes, `current` moves, nothing is
deleted. Then restart any standing console service so it serves the new engine. Every run
records the engine and plugin versions it ran under, so an older project is reproduced by
installing the versions its `stringency.yml` names and pointing `PATH` at them.

## Where the lab's install is

`integrations/claude-science/hosts/protseq-lab.md`: paths, the group, ports, resource caps.

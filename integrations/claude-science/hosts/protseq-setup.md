# PROTSEQ: tooling for the stringency exit run

Instructions for an agent working on PROTSEQ (`BMESANT-PROTseq`, Ubuntu 24.04, 88 cores,
502 GB RAM, `/data` 137 TB free) as user `jrrose5`. The goal is a machine on which the toy
pipeline can run under the apptainer executor from a Claude Science session, the same way it
already runs on BMESEQ. Nothing here runs the exit project itself; that is a later session.

State found on 2026-09-14: `git` and system `python3` 3.12.3 present; `claude-science`, `claude`,
`gh` in `~/.local/bin`; no `uv`, no `apptainer`, no `singularity`; `/usr/local/lib` and
`/usr/local/bin` are root-owned; `~/mytools/stringency` exists and is empty; `~/envs` does not exist. SSH to GitHub works as
`jrose835` (key `~/.ssh/id_ed25519_github`), and the alias `bmeseq` reaches BMESEQ with
`~/.ssh/id_ed25519_bmeseq`. `apt-cache policy apptainer` shows no candidate, so apptainer is not in
the default repositories.

## Rules for the agent

- You do not have sudo. Step 1 needs it; write the commands out for Jim and wait, or skip it and
  do everything else first. Do not try to work around it with an unprivileged apptainer build
  unless Jim asks (see the note under step 1).
- Everything stringency-related that is not data goes under `~/mytools/stringency`: the two
  checkouts and the engine install. The only exceptions are `uv` (its installer puts it in
  `~/.local/bin`), the `stringency` command link in `~/.local/bin`, and the container image, whose
  path is fixed by the method manifest (step 3). Do not write to `/usr/local`, `/opt`, or `/etc`.
- Under `/data/lab` create only the one directory named in step 6. Do not modify anything else
  there. `umask 002`; the tree is setgid `bme-santangelo-lab`, so leave group ownership alone.
- Copy from BMESEQ only the small items named here (a 42 MB image, two git repositories, one
  CSV). Do not read BMESEQ's array for anything else; the link is 1 GbE.
- Do not touch the GPU, its drivers, Ollama, Docker, or the Claude Science daemon.
- Verify each step with the command given and report the actual output. Report every skip or
  failure as such.

## 1. Apptainer (Jim, sudo)

Ubuntu 24.04 has no apptainer package in its default repositories. The maintained route is the
project's PPA, which also installs the AppArmor profile this kernel needs
(`kernel.apparmor_restrict_unprivileged_userns = 1` is set on this host):

    sudo add-apt-repository -y ppa:apptainer/ppa
    sudo apt update
    sudo apt install -y apptainer

Verify, as `jrrose5`, without sudo:

    apptainer --version
    apptainer exec docker://alpine:3.19 cat /etc/alpine-release

The second command pulls a small image from Docker Hub once; it should print `3.19.x`. If it
fails with a namespace or AppArmor error, report the exact message; do not change kernel or
AppArmor settings. Note: the engine looks for `apptainer` first and falls back to `singularity`;
`STRINGENCY_APPTAINER_BIN` overrides both. On PROTSEQ the command name will be `apptainer`.

Unprivileged fallback, only if Jim says so: apptainer's `tools/install-unprivileged.sh` into
`~/.local/apptainer`. With the AppArmor restriction above it is likely to fail; the PPA route is
the one to use.

## 2. uv (no sudo)

    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv --version

The installer puts `uv` in `~/.local/bin`, which is already on the PATH (`claude-science` lives
there). BMESEQ runs uv 0.8.15; any current release is fine.

## 3. Sources and the image

    mkdir -p ~/mytools/stringency ~/envs
    git clone git@github.com:santangelo-lab/stringency.git ~/mytools/stringency/stringency
    git clone bmeseq:github/stringency-toy-method ~/mytools/stringency/stringency-toy-method
    scp bmeseq:envs/toy-py.sif ~/envs/toy-py.sif

Checks:

    git -C ~/mytools/stringency/stringency log --oneline -1          # expect bf1639b or later
    git -C ~/mytools/stringency/stringency-toy-method tag             # must list v0.1.2
    sha256sum ~/envs/toy-py.sif
    # 03a05256a5f9c3f9414709b7d0a08928289a048c5fd8187c653a30cf848858f7  toy-py.sif

The image path matters: the toy method's `envs/manifest.yml` names
`/home/jrrose5/envs/toy-py.sif` with that sha256, and the same path serves both machines. That
is why the image sits outside `~/mytools`. Do not rename or move it, and do not rebuild it. If the checksum differs, delete the copy and copy again.

The toy method repository has no GitHub remote; BMESEQ's working copy is the source of truth.
If `git clone bmeseq:...` fails on the SSH alias, report that rather than reconstructing the
repository from files.

## 4. Engine install (per user)

    cd ~/mytools/stringency/stringency
    scripts/install.sh --prefix ~/mytools/stringency/engine --link-bin ~/.local/bin
    stringency plugins list

Expected: a venv at `~/mytools/stringency/engine/versions/0.1.0.dev0/`, `current` pointing at it,
`~/.local/bin/stringency` linked, and `plugins list` naming `stringency-toy`. The script picks
`/usr/bin/python3` (3.12.3) on its own. A per-user prefix is correct here: the session reaches
PROTSEQ as an SSH compute host, so the engine runs as the user outside any sandbox and the
machine-wide location in the integration README does not apply.

## 5. Test suite and container smoke test

    cd ~/mytools/stringency/stringency
    uv sync --all-groups
    uv run pytest -q
    uv run ruff check . && uv run ruff format --check . && uv run mypy
    scripts/check_no_biology.sh

With apptainer on the PATH the previously skipped executor test
(`test_apptainer_runs_minimal_sif`) runs and pulls `alpine:3.19` once. Report the pass, fail,
and skip counts. Then the toy image itself:

    apptainer exec ~/envs/toy-py.sif python3 --version    # Python 3.12.x

## 6. Project area and a declare check

Create the area, following the dated naming used under `/data/lab/projects`. Jim may prefer
another name; use this unless told otherwise:

    umask 002
    mkdir -p /data/lab/projects/2026-09_stringency-exit_jrrose5/data
    cd /data/lab/projects/2026-09_stringency-exit_jrrose5
    scp bmeseq:/data-raid/Projects/Jim/stringency-exit/data/groups.csv data/groups.csv

Then a tooling check with known-good declarations. Copy BMESEQ's three files into a scratch
subdirectory, point the input at the PROTSEQ path, and run `declare --check`:

    mkdir -p check
    for f in objective design inputs; do scp bmeseq:/data-raid/Projects/Jim/stringency-exit/$f.yml check/; done
    sed -i 's#/data-raid/Projects/Jim/stringency-exit/data/groups.csv#/data/lab/projects/2026-09_stringency-exit_jrrose5/data/groups.csv#' check/inputs.yml
    stringency declare --check check --method ~/mytools/stringency/stringency-toy-method@v0.1.2 --pipeline toy --executor apptainer

Exit 0 and an echo-back means the engine, the method repository at its tag, the image, and the
input hash all line up on this machine. Exit 15 names the failing field or predicate; report it
verbatim. The `check/` directory is scratch: the exit run will not use these declarations, since
its point is that the agent drafts them from a brief and a manifest. Leave `check/` in place for
Jim to remove.

## 7. Report back

Paste, in this order: `apptainer --version`; `uv --version`; the three checks from step 3; the
tail of `install.sh` output and `stringency plugins list`; the pytest summary line and the
ruff, mypy, and no-biology results; the `apptainer exec` output; the `declare --check`
echo-back or its error. Then list anything skipped and why.

## After this (not the agent's job)

The exit run is driven from a Claude Science session with PROTSEQ registered as an SSH compute
provider (alias `protseq` from the MacBook), the `stringency-operator` and `stringency-declare`
skills published on that instance, and a brief in Jim's words plus a sample manifest in the
project area. `integrations/claude-science/new-project.md` is the checklist; the brief's `PRE`
line puts `~/mytools/stringency/engine/current/bin` on the PATH (`render_brief.py --engine-bin`).

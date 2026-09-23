# PROTSEQ as the lab's stringency host

What a person or an agent needs to know about running stringency on PROTSEQ once the engine is
shared (roadmap Track 1f, Lane D item 3, installed 2026-09-23). Machine context for agents is
`~/.claude/CLAUDE.md` on the host; this note covers only the stringency layer. History:
`protseq-setup.md` (the per-user setup of 2026-09-14), `protseq-shared-install.md` (how the
shared install was made and how a version is added).

## Paths

| what | where | notes |
|---|---|---|
| engine | `/data/lab/env/stringency/current/bin/stringency` | `current` is a symlink into `versions/<label>/`; every run records the engine version |
| engine versions | `/data/lab/env/stringency/versions/<label>/` | one venv per label, never deleted or overwritten; `envs/` beside them is unused |
| container images | `/data/lab/env/images/<name>-<version>.sif` | pinned by sha256 in `MANIFEST.md` there and in each method's `envs/manifest.yml`; never overwrite a file, a new build gets a new name |
| projects | `/data/lab/projects/<project>/` (`/lab/projects/...`) | project directories are engine-managed; `stringency board /lab/projects/<area>` writes the area's `STATUS.md` |
| raw data | `/lab/raw/` | group-readable, not group-writable |
| references | `/lab/ref/` | one canonical set; the outlier reference table lives here |
| scratch | `/lab/scratch/<user>/` | Nextflow work directories and anything safe to wipe |
| Nextflow | `/lab/env/nextflow` (Java 21, Nextflow 24.10.0) | `NXF_HOME` on `/lab/scratch`, `NXF_APPTAINER_CACHEDIR=/data/lab/env/images/nxf-cache` |
| method repos | `~/github/<method>` per user, or a git URL | the engine clones a method at a tag; a local checkout is only for development |

Group: everything under `/data/lab` is group `bme-santangelo-lab` with the setgid bit and a
default ACL granting the group `rwx`, so files are group-writable whatever the umask. Still use
`umask 002` in shells that write under `/data/lab/env`. Membership in the group is an AD request
to IT, not a local change.

## PATH

One line per user in `~/.profile`:

    export PATH=/data/lab/env/stringency/current/bin:$PATH

Login shells read it, and Claude Science's `call_command(..., login_shell=True)` inherits it.
`render_brief.py --engine-bin` defaults to this path. A user who also has a per-user install
should point `~/.local/bin/stringency` at the shared binary or remove it, so both shell kinds
agree.

## Adding an engine version

Only a maintainer does this, from an engine checkout, with `umask 002`:

    scripts/install.sh --prefix /data/lab/env/stringency --source <engine ref> \
      --plugin <plugin ref> --label <label>

`current` moves to the new label; the old version stays for runs that cite it. If a plugin comes
from the `stringency-plugins` workspace and the engine ref is not the GitHub one its
`tool.uv.sources` pins, install with `uv pip install --no-sources` into the venv the script
created (see `protseq-shared-install.md`, step 2, for the exact recovery). Everyone's PATH
follows `current` with no change on their side.

## Claude Science

- One instance per person, reaching PROTSEQ through their own SSH identity, so every command runs
  as their AD user and the engine's `roles`, `via: tty` and `via: web` are per person without any
  engine change.
- Per instance, once: compute provider `protseq` (SSH), data root `/data/lab/projects`, and the
  skill publish cell (`publish-skills.md`).
- Ports: this machine's Claude Science uses 8000 and 8001 (previews). BMESEQ uses 8010 and 8011.
  Keep them as they are so both can be tunnelled at once. 8765 is the personal project page
  (`scripts/review-page.sh`); 8766 is the standing read-only page (below).

## The project page

- Personal, with the verdict form: `scripts/review-page.sh protseq` from a laptop runs
  `stringency review --serve --projects /data/lab/projects` on PROTSEQ as that person and tunnels
  port 8765; the URL with its token is printed once. Never started by an agent, never for others.
- Standing, read-only: `scripts/stringency-page.service`, a `systemd --user` unit under the
  owner's account, loopback `127.0.0.1:8766`, `--read-only --token-file
  ~/.config/stringency/page-token`, projects two levels under `/data/lab/projects` (add
  `--project <path>` lines for deeper ones). Reached by `ssh -N -L 8766:127.0.0.1:8766 protseq`;
  the URL with its token is stable across restarts and is what a member puts in `page_url` of
  their `notify.yml`. Install and linger commands are in the unit's header; it records no verdict.
- Notifications: per user, `~/.config/stringency/notify.yml`; email through the campus relay
  `smtp.service.emory.edu:25` (accepts unauthenticated mail from this host, checked 2026-09-23),
  `smtp.office365.com:587` with a mode-600 credential file as the fallback. The engine writes
  `<project>/.stringency/notify.log`; `STRINGENCY_NOTIFY=0` silences it (batch work, tests).
- Resource caps apply to every pipeline run: default `--max_cpus 24 --max_memory 200.GB` for
  nf-core, `systemd-run --user --scope -p MemoryMax=140G -p MemorySwapMax=0` around Nextflow
  launches (`/lab/projects/Lyons_CLP/run_ticket.sh` is the working example).

## GPU

32 GB, shared on demand with Brian (the owner's experimental LLM project). Check
`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv` before GPU work and
set an explicit memory limit if anything is resident.

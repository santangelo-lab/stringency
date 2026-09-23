# PROTSEQ: shared engine install (roadmap Lane D item 3, Track 1f)

Step-by-step for the owner or an agent working as `jrrose5` on PROTSEQ. Goal: one engine that
every lab member on this machine runs, at `/data/lab/env/stringency`, pinned to the version the
Lyons CLP runs used; a PATH line per user; the onboarding notes. New runs use it in place of the
per-user install under `~/mytools/stringency/engine`. Companion notes: `protseq-setup.md` (the
original per-user setup), `spec/plans/ux-two-audiences.md` section 7 (the design).

State found 2026-09-23:

- `/data/lab/env/stringency/` exists and is empty: owner `jrrose5`, group `bme-santangelo-lab`,
  setgid, default ACL `group:bme-santangelo-lab:rwx`, `other::r-x`. No `sudo` step remains.
- `/data/lab/env/images/` holds seven images pinned by sha256 in `MANIFEST.md`. Method manifests
  name that path; the engine install does not touch it.
- The per-user engine in use is `0.1.0+optin3-sc0.1.8`: engine branch `lane-c-directory-inputs`
  at `41fc5cc`, plugin `stringency-singlecell` 0.1.8 from `~/github/stringency-plugins` at
  `0b22769` (local tag `v0.1.11`, not pushed), toy plugin from the same engine ref. Neither ref
  is on GitHub yet, so the shared install pins the same local refs and the same label; when Lane A
  opens the PR and tags, step 6 installs the tagged version beside it.
- `uv` 0.12.13 is in `~/.local/bin` of `jrrose5`. Only the installer needs it; users run the venv.

Rules: `umask 002` in every shell that writes there. Never delete or overwrite a
`versions/<label>` directory; a new engine gets a new label and `current` moves. Create nothing
else under `/data/lab/env`. Leave group ownership alone (setgid and the ACL handle it).

## 1. Preflight

    umask 002
    ls -la /data/lab/env/stringency                       # empty; drwxrwsr-x+ jrrose5 bme-santangelo-lab
    getfacl /data/lab/env/stringency | grep default:group:bme    # default:group:bme-santangelo-lab:rwx
    git -C ~/mytools/stringency/stringency rev-parse --short lane-c-directory-inputs   # 41fc5cc
    git -C ~/github/stringency-plugins rev-parse --short v0.1.11                        # 0b22769
    uv --version

If either commit differs from the one in the comment, stop: the label in step 2 would then name
a version that is not the one the Lyons CLP runs recorded. Pick a new label instead.

## 2. Install

    umask 002
    cd ~/mytools/stringency/stringency
    scripts/install.sh \
      --prefix /data/lab/env/stringency \
      --source "git+file:///home/jrrose5/mytools/stringency/stringency@lane-c-directory-inputs" \
      --plugin "git+file:///home/jrrose5/github/stringency-plugins@v0.1.11#subdirectory=plugins/stringency-singlecell" \
      --label 0.1.0+optin3-sc0.1.8

What happens: a venv at `versions/0.1.0+optin3-sc0.1.8/` on `/usr/bin/python3` (3.12.3); the
engine and the toy plugin from the branch ref (the script adds the toy itself), the singlecell
plugin from the tag; `current -> versions/0.1.0+optin3-sc0.1.8`; an empty `envs/` the script
always creates (images live in `/data/lab/env/images`; leave `envs/` empty). `/usr/local/bin` is
not writable, so the script links no command and prints the PATH hint; that is expected.

Expected last lines: `installed stringency 0.1.0+optin3-sc0.1.8 at ...`, `current -> ...`, a
plugins list naming `stringency-singlecell 0.1.8` and `stringency-toy 0.1.2`.

**What happened on 2026-09-23.** The `uv pip install` step failed with "Requirements contain
conflicting URLs for package `stringency`": the `stringency-plugins` workspace root pins
`stringency` to `git+https://github.com/santangelo-lab/stringency` in `tool.uv.sources`, and uv
applies that pin to the plugin whether it is installed from the git URL or from the local path,
so it conflicts with the local branch ref. The script had already created the venv, so the
recovery was to finish by hand with `--no-sources`, then set `current`:

    umask 002
    venv=/data/lab/env/stringency/versions/0.1.0+optin3-sc0.1.8
    uv pip install --quiet --no-sources --python $venv/bin/python \
      "git+file:///home/jrrose5/mytools/stringency/stringency@lane-c-directory-inputs" \
      "git+file:///home/jrrose5/mytools/stringency/stringency@lane-c-directory-inputs#subdirectory=plugins/stringency-toy" \
      ~/github/stringency-plugins/plugins/stringency-singlecell
    ln -sfn versions/0.1.0+optin3-sc0.1.8 /data/lab/env/stringency/current

The plugin therefore records the local path (`0b22769`, the `v0.1.11` checkout) rather than the
tag. `install.sh` now passes `--no-sources` itself (same day), so a later run of step 2 as
written succeeds. The script's `set -e` already stops it before `current` moves when the install
fails; the `current` link that briefly pointed at the empty venv on 2026-09-23 came from the
hand-run recovery, whose pipe through `tail` masked the exit code, and was removed and re-set.

## 3. Verify the install

    S=/data/lab/env/stringency/current/bin/stringency
    readlink /data/lab/env/stringency/current
    $S --version
    $S plugins list
    python3 - <<'EOF'
    import glob, json
    for f in sorted(glob.glob('/data/lab/env/stringency/current/lib/python3.12/site-packages/stringency*.dist-info/direct_url.json')):
        print(f.split('/')[-2], json.load(open(f)))
    EOF
    namei -l /data/lab/env/stringency/current/bin/stringency
    find /data/lab/env/stringency/versions ! -perm -g+r | head

Expect `41fc5cc...` for `stringency` and `stringency_toy`, `0b22769...` for
`stringency_singlecell`; every path component traversable by the group (`/data` itself grants
`bme-santangelo-lab` execute through its ACL); the `find` prints nothing.

## 4. Smoke test from the shared binary (read-only)

    cd /lab/projects/Lyons_CLP/qc_outliers_all && $S status
    $S board /lab/projects/Lyons_CLP                    # no --write
    cd ~/github/stringency-xenium-method && $S lint .

Expect the same output the per-user engine gives (run completed, both steps completed; the
board; lint clean).

## 5. Switch your own account

1. Add to `~/.profile` (login shells; `call_command(..., login_shell=True)` inherits it):

       export PATH=/data/lab/env/stringency/current/bin:$PATH

2. Repoint the per-user link so non-login shells agree:

       ln -sfn /data/lab/env/stringency/current/bin/stringency ~/.local/bin/stringency
       hash -r; which stringency; stringency --version

3. Keep `~/mytools/stringency/engine` as the rollback until the next shared version lands, then
   retire it. Nothing in a project directory names the engine path; runs record the version.
4. In the engine repo: `ENGINE_BIN` in `integrations/claude-science/render_brief.py` becomes
   `/data/lab/env/stringency/current/bin`; `new-project.md` step 1 and `README.md` "Claude Science
   setup" step 1 stop saying per-user or `/usr/local/lib/stringency`.

## 6. Adding a version later

Re-run `scripts/install.sh --prefix /data/lab/env/stringency --source <ref> --plugin <ref>
--label <label>`; `current` moves, the old version stays for runs that cite it. Once the branch is
merged and tagged, the refs are GitHub ones:

    --source "git+ssh://git@github.com/santangelo-lab/stringency@v0.2.0" \
    --plugin "git+ssh://git@github.com/santangelo-lab/stringency-plugins@v0.1.11#subdirectory=plugins/stringency-singlecell"

Every user's PATH follows `current` without any change on their side.

## 7. The notes (agent-doable, commit to `main`)

- `integrations/claude-science/hosts/protseq-lab.md`: the shared paths (engine, images and
  `MANIFEST.md`, `/data/lab/projects`, `/lab/scratch`), the PATH line, the port rule (8000/8001
  stay for this machine's Claude Science; BMESEQ uses 8010/8011), how a version is added, the
  `umask 002` rule.
- `integrations/claude-science/onboarding.md`, per `ux-two-audiences.md` section 7: membership
  in `bme-santangelo-lab` is an AD request to IT; a computational member sets up the SSH alias
  `protseq`; the PATH line; in their own Claude Science instance, once: provider `protseq`, data
  root `/data/lab/projects`, the publish cell; optionally `scripts/review-page.sh` on their
  laptop; two paragraphs on what to expect (holds come to them in chat, nothing is excluded or
  decided without them, every number they read comes from an engine output).
- `integrations/claude-science/publish-skills.md`: the publish cell per instance for
  `stringency-operator`, `stringency-declare`, and each method's
  `skills/stringency-analyze-<pipeline>` once those exist.

## 8. Deferred

BMESEQ gets `/data/lab/env/images` by symlink so the same manifest paths resolve there (design
10.3). Not needed until a stringency method runs on BMESEQ.

## Verification, in one line each

- `readlink /data/lab/env/stringency/current` prints `versions/0.1.0+optin3-sc0.1.8`.
- `stringency --version` from a fresh login shell resolves to the shared path (`which`).
- `stringency status` in `qc_outliers_all` matches the per-user engine's output.
- `direct_url.json` commits match the preflight commits.
- `find ... ! -perm -g+r` under `versions/` prints nothing.

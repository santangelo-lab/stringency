# 2026-11-03 14:50: the MacBook spike S1, the engine's side

**Goal.** Spike S1 of the beta-tester package on Jim's MacBook (Apple Silicon, macOS 26, no
container runtime): the engine installed the tester's way, the suite on the Mac, and what the
install scripts assume about a Mac. The beta repository's note
(`stringency-beta/notes/2026-11-03-1450-macbook-s1.md`) has the whole spike.

**Done.**
- The suite at v0.2.37 on the Mac: green, 637 passed and 4 skipped in 4 min 33 s, on Python
  3.14.7 (uv's choice with no `.python-version`).
- `install.sh` from a checkout, branch `beta-mac-s1`:
  - with no system python3 >= 3.12 (macOS ships 3.9) it installs 3.12 with uv and uses it, as
    `bootstrap.sh` does; before, it stopped with "no python3 >= 3.12 found (set
    STRINGENCY_PYTHON)", the snag the handoff predicted;
  - the empty `plugins` array under `set -u` (`--no-toy` with no `--plugin`) stopped macOS's
    bash 3.2 with "plugins[@]: unbound variable"; both expansions are guarded;
  - `uv venv` runs with `UV_VENV_CLEAR=1`: uv 0.8 and later refuse an existing venv, so a
    label installed before ("setup" run twice, the beta's `update` to a version already there)
    failed with "Failed to create virtual environment".
  Checked by a clean-PATH install into a scratch prefix; no test, since the scripts need the
  network and the suite has none.
- PLAN rows L149 (`bootstrap.sh` always passes `--no-toy`; its closing text names apptainer on a
  local site) and L150 (`review --serve`'s default port 8765 is the Claude Science app's).

**Learned.**
- The Claude Science desktop app (`claude-science serve --app`) listens on 127.0.0.1:8765 and
  8766 while it is open. 8765 is `review_serve.DEFAULT_PORT` and the beta channel's console port.
- Under `uv run` of another project, `python3` on PATH is that project's venv interpreter, so
  `bootstrap.sh` skips its own 3.12 install and the engine venv takes that Python (here 3.14);
  the venv's `home` is uv's managed CPython, so nothing breaks, but the version is not the one
  CI pins.
- `install.sh` uses `readlink` without `-f` and links into `/usr/local/bin` only when it is
  writable (root-owned here, so not linked): both fine on a Mac.

**Altered.** Nothing in a contract.

**Open.**
- Merge `beta-mac-s1` and tag; L149 and L150.
- The liveness watch item (`active.py` reads `/proc`; on Darwin the stale-engine logic should
  say "unknown", never "gone") needs a held run on the Mac: the first Mac-local toy run (S1 step
  5), which Jim drives.

**Verify.** `env -u STRINGENCY_PYTHON PATH=/opt/homebrew/bin:/usr/bin:/bin scripts/install.sh
--prefix <scratch> --source . --no-toy --link-bin <scratch>/bin` on a Mac ends with `ok engine`.

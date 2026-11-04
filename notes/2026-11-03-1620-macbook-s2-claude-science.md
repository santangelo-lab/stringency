# 2026-11-03 16:20: the MacBook spike S2, the engine's side

**Goal.** Spike S2 of the beta-tester package: a Claude Science session on Jim's MacBook driving
the local install (v0.2.37, executor local) through the toy run. The beta repository's note
(`stringency-beta/notes/2026-11-03-1600-macbook-s2.md`) has the whole spike.

**Done.**
- Claude Science's shell runs on the Mac as the user under a sandbox scoped to its workspace;
  with host folder grants (`~/.local/lib/stringency` and `~/.local/share/uv/python` read-only,
  `~/stringency/projects` read-write, `~/stringency/data` read-only) `probe` ends `ready`.
- `init` failed inside the sandbox (no path named `.git` may be created; the method clone); Jim
  ran it in Terminal with the session's `STRINGENCY_OPERATOR` and `STRINGENCY_SESSION_REF`, and
  the session drove everything after it: tickets, the label dispatch through three sub-agents,
  the hold (answered on the console), `deliver`, `present`. Run `01M6HJHP` completed and
  delivered the same tables as the Claude Code run; `audit` is clean.
- PLAN rows L151 (`init` in a sandbox that refuses `.git`), L152 (a Claude Science delegate
  names itself as the operator, so its replicates are recorded `isolation: none`) and L153
  (`run --deliver` refused after a final operator ticket, which both Mac runs hit).

**Learned.**
- A read-only grant lets a binary under it run; the engine's venv needs uv's Python directory
  granted as well as the install.
- `operator_env` drops `STRINGENCY_OPERATOR_VERSION=unknown` and then puts it back as the
  fallback, so the run row says `operator_version: unknown` where a Claude Code run says null.
- `siteconfig.load()` sees no file when `config.yml` is unreadable, and `probe` prints the same
  lines either way, so `ready` in a sandbox does not say which executor `init` will choose.

**Altered.** Nothing in a contract.

**Open.** L151 to L153; merge `beta-mac-s1`.

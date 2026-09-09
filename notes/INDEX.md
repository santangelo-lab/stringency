# notes index

The map of session notes. One line per note, newest first. Keep the current-state block accurate;
it is the first thing a new session reads.

## Current state (2026-09-09)

- Phase A M0 through M11 green on `main`. The improvements backlog (`spec/improvements.md`)
  is worked through on the toy except A5 (on its trigger) and the E2 in-session version route:
  review display and packets, hold ids in messages, `review --hold`, `init` exit 10, `job.json`
  and exact exec/submit lines at ticket time, `submit --command`, `expected_env_digest`,
  `status` lists holds, `run --new`, evidence-slot definition on every prompt, inspect evidence
  with checksum on toy operator modules. Toy method 0.1.1 (tagged locally in
  `~/github/stringency-toy-method`, mirror on `/data-raid` not updated).
- Phase A exit run done on BMESEQ (`toy-cs`, run `01M2172HKP6E3RNQNEPP6DSFCE`) on the
  pre-backlog engine. PROTSEQ half not done; BMESEQ machine install is stale.
- 2026-09-09: `exec.script_drift` closes the edited-script gap (G1). `declare --check`,
  `init --drafted-by --brief`, `derived_from` inputs, and the `stringency-declare` skill are
  built (H1 to H4); `spec/declarations-and-objectives.md` holds the design. Toy method at
  `v0.1.2` locally. Open design questions: G2 (session-written code), H5 (staged mode).
- Not done: PROTSEQ run, `v0.1.0` tag, public repo, singlecell push, review page (A5), G2.
- Next session should start with: `notes/2026-09-09-1059-declare-and-chained-projects.md`, then `notes/2026-09-09-0847-script-drift.md` then
  `notes/2026-09-08-1655-improvements-backlog.md`, section **Open**.

## Notes

- `2026-09-09-1059-declare-and-chained-projects.md` — declare --check, drafted-by and brief, derived_from chained projects, the declare skill.
- `2026-09-09-0847-script-drift.md` — script drift check; the two classes of analysis code and the open G2 question.
- `2026-09-08-1655-improvements-backlog.md` — the improvements backlog worked through on the toy:
  review display and packets, operator ergonomics, trace semantics, toy method 0.1.1, design text.
- `2026-09-08-1542-phase-a-exit-bmeseq.md` — Phase A exit on BMESEQ from Claude Science: sandbox limits, remote-host
  mode, machine install, review-surface findings.
- `2026-09-03-1605-phase-a-m0-m11.md` — first build session: repository created, M0 through M11
  implemented against the design, end-to-end CLI rehearsal of the toy pipeline, singlecell skeleton.

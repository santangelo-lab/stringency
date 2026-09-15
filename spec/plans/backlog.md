# Backlog

Open items not covered by a roadmap track, carried from `spec/archive/improvements.md` on
2026-09-14, plus the measurement table the UX work reports into. Items marked *design* change
design text and need the owner's approval.

| id | item | proof | level |
|---|---|---|---|
| A5 | reviewer-run review page, `via: web` | roadmap Track 1e (`ux-two-audiences.md` section 5.2); the trigger, a reviewer without a terminal, is met | *design* (7.5, 14.1) |
| E2 | `STRINGENCY_OPERATOR_VERSION` is `unknown` unless the brief carries `--app-version`; no in-session route to the app's version was found | the next exit run records a version | skill |
| G2 | code the agent writes in a session (notebook cells, plotting scripts) is captured nowhere; only its inability to yield a final artifact is enforced (`prov.orphan_artifact`) | decide: the rule alone (Commandment 5) or a capture verb that files a session script with a sidecar | *design*; the owner's call |
| J1 | `declare --check --print-hashes`: print blake3 for input items lacking one and exit 15 naming the field, so the declare skill fills hashes from engine output rather than its own Python | `ux-two-audiences.md` 3.2, the one row of that table not built in Lane A step 1 (2026-09-15); a test that a manifest without hashes gets them printed | engine, DECISIONS-level |
| H5 | staged mode: objective list with stages, `run --objective`, fork at a stage boundary carries an objective, `obj.declared_after_result` | after application 1 as two chained projects shows where option 1 chafes (`declarations-and-objectives.md`) | *design* |

## Measurements

One row per toy run, before and after each Track 1 step. Baseline from the PROTSEQ chained run.

| date | pipeline | approval cards | person turns to result | time to first delivered file | unrequested commands, JSON, ids shown | holds and `via` | operator misreports vs trace |
|---|---|---|---|---|---|---|---|
| 2026-09-08 | toy (BMESEQ) | 25 | not counted | not counted | not counted | confirm tty, flag tty | 0 |
| 2026-09-14 | toy-process | 12 | 3 drafting turns | not counted | many (raw commands in reports) | confirm tty | 0 |
| 2026-09-14 | toy-engine | 26 | 4 drafting turns, one lost to a wrong brief | not counted | many | confirm tty | 1 (filter step reported as skipped) |

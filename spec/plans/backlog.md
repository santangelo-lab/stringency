# Backlog

Open items not covered by a roadmap track, carried from `spec/archive/improvements.md` on
2026-09-14, plus the measurement table the UX work reports into. Items marked *design* change
design text and need the owner's approval. Status 2026-09-22: A5, E2, G2, J1, J2 and H5 are
unchanged (none was built on the Lane C branch); K1 to K7 come from the Lyons CLP runs and are
not in a roadmap lane (the engine gaps that are, sit under roadmap Lane A items 5 and 6).

| id | item | proof | level |
|---|---|---|---|
| A5 | reviewer-run review page, `via: web` | roadmap Track 1e (`ux-two-audiences.md` section 5.2); the trigger, a reviewer without a terminal, is met | *design* (7.5, 14.1) |
| E2 | `STRINGENCY_OPERATOR_VERSION` is `unknown` unless the brief carries `--app-version`; no in-session route to the app's version was found | the next exit run records a version | skill |
| G2 | code the agent writes in a session (notebook cells, plotting scripts) is captured nowhere; only its inability to yield a final artifact is enforced (`prov.orphan_artifact`) | decide: the rule alone (Commandment 5) or a capture verb that files a session script with a sidecar | *design*; the owner's call |
| J1 | `declare --check --print-hashes`: print blake3 for input items lacking one and exit 15 naming the field, so the declare skill fills hashes from engine output rather than its own Python | `ux-two-audiences.md` 3.2, the one row of that table not built in Lane A step 1 (2026-09-15); a test that a manifest without hashes gets them printed | engine, DECISIONS-level |
| J2 | `submit --deliver`: when the last step is an operator ticket the run completes inside `submit`, so `run --deliver` never applies and delivery costs one more card (seen 2026-09-15, `deliver` was the tenth command) | the same guard as `run --deliver`; one test | engine, DECISIONS-level |
| K1 | the review-packet renderer resolves every evidence citation by the item key, so on a module with secondary evidence tables each citation prints "(no such cell)" and "evidence row: none" although `judg.evidence_exists` passed on the same run (display only; the trace is right) | resolve by the cited table's own key in `review.py` and `holds.py`; a test on a three-table judgment (found 2026-09-21, `notes/2026-09-21-1600-outlier-judgment-v2-engine.md`) | engine, DECISIONS-level |
| K2 | confidence criteria: `high` needs zero contradicting cells, so a reviewer that lists the cells against its label lands on `medium` or `low`, and `any_low` opens a hold for an item every replicate labelled the same (24-1-Liver and 24-1-Spleen-B on the first v2 run) | decide: tolerate one contradicting cell at `high`, or hold on `any_low` only when labels differ | *design* (8.x); the owner's call; roadmap Lane A item 6 |
| K3 | a band edge can be impossible for its column (a negative floor on a count) and the engine says nothing | warn when a band edge violates the column's type, if columns ever carry one; today the method clips (open on the method side) | engine, low |
| K4 | `STATUS.md` carries no line for the newest change and `board` has no `--watch` | `notes/2026-09-18-1830-board-and-present.md` | engine, low |
| K5 | `present --hold` on a judgment hold renders exactly what the skill lists; a default that shows `judgments.jsonl` beside the consensus would save a skill line per method | same note | engine, low |
| K6 | method and plugin tags pushed before checks passed remain on GitHub (`lane-c-day1-2026-09-17.md`, 2026-09-18 section) | delete them, or say in each repo's README which tags are usable | operations, owner |
| K7 | an item hold's verdict reaches the `consensus` table but never the `consensus.json` artifact: `judgment.py` writes the file at judgment time with held items as `source: unresolved`, `review.py::_apply_item_verdict` updates the store only, and `_settle_step` completes the step without rewriting the output. Downstream steps bind `$steps.<id>.consensus` (the file), so on `qc_outliers_all` run `01M32Q6MK30YFWZVGJRYT66BF1` the delivered proposal shows the six owner-decided punches as `unresolved` with no verdict while `summary.md` says "six accepted, none unresolved". Design 8.4 says an `unresolved` item cannot exist in a completed step. `sc.exclusion_proposed` ran on the same pre-review consensus (2 proposed; 6 after the verdicts) | when the last item hold resolves and the step completes, rewrite the consensus output from the store and re-record its hash in `history`; re-evaluate post-phase predicates that read `output.consensus` after the item holds settle (or run them only then); a test that accepts a replicate on a held item and asserts the file and a downstream step see the label; decide how a completed run repairs its artifact (regenerate from the trace, or `run --new` and re-decide) (found 2026-09-23, `notes/2026-09-23-1100-outlier-holds-stale-consensus.md`) | engine, DECISIONS-level; predicate timing *design* (7.1, 8.4) |
| H5 | staged mode: objective list with stages, `run --objective`, fork at a stage boundary carries an objective, `obj.declared_after_result` | after application 1 as two chained projects shows where option 1 chafes (`declarations-and-objectives.md`) | *design* |

## Measurements

One row per toy run, before and after each Track 1 step. Baseline from the PROTSEQ chained run.

| date | pipeline | approval cards | person turns to result | time to first delivered file | unrequested commands, JSON, ids shown | holds and `via` | operator misreports vs trace |
|---|---|---|---|---|---|---|---|
| 2026-09-08 | toy (BMESEQ) | 25 | not counted | not counted | not counted | confirm tty, flag tty | 0 |
| 2026-09-14 | toy-process | 12 | 3 drafting turns | not counted | many (raw commands in reports) | confirm tty | 0 |
| 2026-09-14 | toy-engine | 26 | 4 drafting turns, one lost to a wrong brief | not counted | many | confirm tty | 1 (filter step reported as skipped) |
| 2026-09-15 | toy-engine (Lane A step 1 flags and skill; hand-written declarations, no drafting phase) | 17: 10 commands (probe, init, `review --hold`, `review --attest`, three `run`, two `operator_line`, `deliver`), 7 transfers (3 request files, 4 delivered files) | about 6 (Phase 0, Phase 1, "ok", the verdict, Phase 2, Phase 3) | not counted | final report only, on request | confirm relayed (session ref and `operator_harness` recorded) | 0 in the final report; intermediate turns not audited |

No Lyons CLP run has a row: the fourteen projects were driven from a terminal through the
operator skill, not through an analysis skill, and cards were not counted. The next row comes
from Lane E.

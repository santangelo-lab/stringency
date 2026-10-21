# Measurements

The tables the UX work reports into, moved out of `backlog.md` on 2026-10-21 when `PLAN.md` became the one work list (the rows are as they stood). One row per measured run. The method skills page (`spec/method-skills.md`, "Measurement") and `docs/open-mode.md` say what each run records.


One row per toy run, before and after each Track 1 step. Baseline from the PROTSEQ chained run.
The 2026-09-23 skill row is the toy run through `stringency-analyze-toy-compare` (checklist
`integrations/claude-science/hosts/protseq-session-tests.md` section D and its results). The 3.4 answers (owner, 2026-09-23, app): a download under
`/data/lab/projects` raises a card offering a conversation-scoped grant per directory; the `call_command`
card offers once, this conversation, this project, or global, and a project grant covered every later
`stringency` command with no card (`integrations/claude-science/hosts/protseq-session-tests.md`).

| date | pipeline | approval cards | person turns to result | time to first delivered file | unrequested commands, JSON, ids shown | holds and `via` | operator misreports vs trace |
|---|---|---|---|---|---|---|---|
| 2026-09-08 | toy (BMESEQ) | 25 | not counted | not counted | not counted | confirm tty, flag tty | 0 |
| 2026-09-14 | toy-process | 12 | 3 drafting turns | not counted | many (raw commands in reports) | confirm tty | 0 |
| 2026-09-14 | toy-engine | 26 | 4 drafting turns, one lost to a wrong brief | not counted | many | confirm tty | 1 (filter step reported as skipped) |
| 2026-09-15 | toy-engine (Lane A step 1 flags and skill; hand-written declarations, no drafting phase) | 17: 10 commands (probe, init, `review --hold`, `review --attest`, three `run`, two `operator_line`, `deliver`), 7 transfers (3 request files, 4 delivered files) | about 6 (Phase 0, Phase 1, "ok", the verdict, Phase 2, Phase 3) | not counted | final report only, on request | confirm relayed (session ref and `operator_harness` recorded) | 0 in the final report; intermediate turns not audited |
| 2026-09-23 | toy-engine through `stringency-analyze-toy-compare` (owner, app, engine install `0.2.0-sc0.1.8`, toy method `v0.1.4`; project `lane-e/group-a-vs-b`) | owner to fill: expected 0 command cards under the project-scoped `call_command` grant, one download card per directory read (data, dispatch, deliver) | 7 (first message; "unit"; the deliverables; "yes, that's right" on the column reading; "yes" to the echo-back; the verdict with reason; the K8 instruction). The "ok" refusal was not exercised | 14 min 39 s (brief saved 12:48:20, first delivered file 13:02:59), of which about 4 min at the K8 stop; `init` at 12:53 | 3: the three "Bound to" hashes inside the echo-back (shown twice, at the echo and in the confirm hold's record); `type frame` and `type csv` in the source table; the delivery path with the run id in the final report. The K8 diagnosis quoted the mount error, exit 255 and paths, with cause | confirm relayed (session ref, `operator_harness` claude-science, reason "The reading is correct"); no flags; three delegates `claude-opus-5`, `saw_conversation` false, 9 of 9 labels agreed | 0: every relayed `plain` line, the three-part report and the `present` tables match `status --json`, `summary.md` and `present`. Deviation, on the owner's instruction: two `mkdir` of the step `tmp` for the operator tickets (K8). Trace `stringency_version` reads `0.1.0.dev0` on the 0.2.0 install |

| 2026-10-06 | Lyons CLP second QC chain, Lane F phase 0 (terminal session, Claude Code; engine `0.2.6-sc0.1.8`, method `v0.4.0`; eleven projects: eight `xenium-qc`, one summary, one outlier judgment, plus the exclusion file) | not counted (terminal) | 7 verdict turns (batch confirm; "accept all 16" for the parameter flags; two confirms; four item holds in one turn; one flag) plus 3 decision turns and 3 questions | 81 min from the first `init` to the first `qc2` delivery, about an hour of it the owner's questions at the split holds; whole chain about 2 h 40 min | 0 (the batch echo-back and the `present` tables only; the comparison script's output was summarised) | 31 holds, all relayed: 8 confirm as one batch, 16 `param.agent_proposed` flags, 2 confirm, 4 `run_disagreement` items, 1 flag | 0 known; one judgment run rejected by `judg.numeric_claims_match` and abandoned with the reason |

Before 2026-10-06 no Lyons CLP run had a row: the fourteen projects were driven from a terminal through the
operator skill, not through an analysis skill, and cards were not counted. The next row comes
from Lane E.

## Open mode

One row per open-mode run (`docs/open-mode.md` "How it is measured", `docs/open-mode-rehearsal.md` section 4). No row yet: the owner's two drives of 2026-10-19 on the toy were recorded as findings (`notes/2026-10-19-1400-open-mode-drive-findings.md`), not as a row.

| date | delivery | questions asked (person, suggested) | answers by label (trusted, untested) | blocks and how each was cleared | unrequested ids or paths shown | label words stated correctly | turns and minutes to the first delivered answer | outside the three routes |
|---|---|---|---|---|---|---|---|---|

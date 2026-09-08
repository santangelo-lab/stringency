# Improvements backlog: iterate on the toy before Phase B

What the Phase A exit run on 2026-09-08 showed should change before the engine meets a real
pipeline. Each item says what was observed, what to change, how the toy tests prove it, and
whether it touches a contract. Nothing here reshapes a frozen contract; items marked *design*
change design text and need Jim's approval; the rest are DECISIONS-level.

Work through this list on the toy pipeline, with the `toy-cs` trace at
`/data-raid/Projects/Jim/stringency-exit/toy-cs/prov/run.db` as a fixture where noted, before
starting the single-cell plugin. Cross-reference: `spec/review-ux.md` for the review surface in
depth; `notes/2026-09-08-1542-phase-a-exit-bmeseq.md` for the run itself.

## A. Review surface (highest value)

| # | observed | change | proof | level |
|---|---|---|---|---|
| A1 | `review` prints the hold header and predicate JSON; design 7.3 promises the evidence the model saw, each replicate's call with cited cells, and the table slice | render the 7.3 display per hold kind (`spec/review-ux.md`, layer 1) | golden test per hold kind using the `toy-cs` flag hold; the `unanimous`, `split`, `one_abstain` mock fixtures for the item kinds | decisions; **done 2026-09-08** (`review_render.py`, goldens in `tests/golden/review_*.txt`, `context_contradicting.yml` replays the toy-cs judges) |
| A2 | `run`'s hold message names step and reviewer but not the hold id (14.2 says the message names the hold) | include the hold id | assert on the message in the M7 hold test | decisions; **done 2026-09-08** (message names the hold and `review --hold <id>`, which shows one hold) |
| A3 | `init` exits 0 with an open confirm hold; `run` on the same hold exits 10 | `init` exits 10 when it leaves a hold open | M2 acceptance test | decisions; **done 2026-09-08** |
| A4 | no way to read a hold without a terminal | review packet on disk per hold, HTML and Markdown (`review-ux.md` layer 2) | packet exists after a hold opens; content equals the A1 render | decisions |
| A5 | every verdict path is a terminal or the agent | reviewer-run review page, `via: web` (`review-ux.md` layer 3) | deferred in design 17; build when a non-terminal reviewer exists | *design* (7.5, 14.1) |

## B. Operator ergonomics

| # | observed | change | proof | level |
|---|---|---|---|---|
| B1 | operator created the step directory, assembled job.json, and composed the container command from the job spec | at ticket time the engine creates the step dir, writes `job.json` there, and prints the exact `apptainer exec` line and the submit line; `next --json` carries both | M5 operator test asserts the files and the command; the toy operator helper in `stringency-exit/tools` becomes two lines | decisions |
| B2 | `status --json` does not list the open confirm hold or any hold id | `status --json` includes open holds with id, kind, step, waits_on | schema fixture update; M7 test | decisions |
| B3 | `run` on a project whose latest run is completed silently opens a new run | refuse with exit 16 and a message naming `run --new`; `--new` opens one | M7 test | decisions (14.1 gains a flag) |
| B4 | remote-mode operators pay one approval per command; 25 authorization points for five steps | B1 and B2 remove several; measure again after them | count in the next exit run | none |

## C. Trace semantics

| # | observed | change | proof | level |
|---|---|---|---|---|
| C1 | operator-run executions carry the expected digest in `env_digest` while `env_status` is `as_reported`; readable as verified | keep the expected digest in a separate field (`expected_env_digest`) and leave `env_digest` null when unverified; coverage report unchanged | M5 test on both runners; trace-schema spec updated | decisions (9.4 adds a column, does not reshape) |
| C2 | operator-run executions have no `command`; the operator's exact invocation is lost | `submit --command "<string>"` recorded as reported, or the job-log parser captures a `command:` line the ticket tells the operator to echo | M5 test; `toy-cs` shows the gap | decisions |
| C3 | env verification for operator steps never exercised: toy modules declare only `job_log` evidence | toy operator modules also declare `apptainer_inspect` evidence; the ticket says how to produce it; the exit run then shows `verified` on operator steps | M5 test for the verified operator path | toy method only |

## D. Judgment contract

| # | observed | change | proof | level |
|---|---|---|---|---|
| D1 | all three judges used `contradicting_evidence` for context cells, firing `judg.confidence_consistent` | define the slot in the prompt suffix and in `spec/module-contract.md`: a contradicting ref is a cell that argues against the chosen label; or count only such refs in the criteria. Pick one; the first is simpler and keeps the predicate mechanical | toy prompt updated; the `toy-cs` responses replayed through the gate as a regression fixture | decisions; module-contract text |
| D2 | delegates cannot be tool-restricted to one file; isolation is instructional | none in the engine; record the answer in design 10.2 and 19 | text | *design* (text only) |

## E. Deployment and operator identity

| # | observed | change | proof | level |
|---|---|---|---|---|
| E1 | a Claude Science sandbox on the workstation cannot start containers; runs go through an SSH compute host | design 10.4 text says so; the skill's mode B is the default for apptainer projects | text; integration README already records it | *design* (10.4 text) |
| E2 | `STRINGENCY_OPERATOR_VERSION` recorded as `unknown` because the agent had no sanctioned way to learn the app version | the skill names a route (the app exposes its version to the session; find and cite it) | next exit run records a version | skill only |
| E3 | machine-wide install matters only for mode A; remote mode works from a per-user install | `scripts/install.sh --prefix ~/.local/lib/stringency` documented as the no-sudo route for compute hosts | run it on PROTSEQ | docs |

## F. Small fixes already listed elsewhere

Hold id in message (A2), init exit code (A3), step dir at ticket time (B1). Listed here so the
backlog is complete in one place.

## Order

1. A1, A2, A3 together: one session, golden tests, `toy-cs` as fixture. Done 2026-09-08.
2. B1, B2, B3, C1, C2: one session; re-run the toy exit by hand afterwards and count commands.
3. C3 and D1: toy method edits plus tests; bump the toy module versions.
4. E1, D2 design text; E2 skill; E3 docs.
5. A4 when A1 exists. A5 on its trigger.
6. Then PROTSEQ exit run on the updated engine, `v0.1.0`, Phase B.

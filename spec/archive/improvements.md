# Improvements backlog: iterate on the toy before Phase B

> Archived 2026-09-14: the backlog from the two exit runs, sections A to I, closed. The four open rows (A5, E2, G2, H5) moved to `spec/plans/backlog.md`.

What the Phase A exit run on 2026-09-08 showed should change before the engine meets a real
pipeline. Each item says what was observed, what to change, how the toy tests prove it, and
whether it touches a contract. Nothing here reshapes a frozen contract; items marked *design*
change design text and need Jim's approval; the rest are DECISIONS-level.

Work through this list on the toy pipeline, with the `toy-cs` trace at
`/data-raid/Projects/Jim/stringency-exit/toy-cs/prov/run.db` as a fixture where noted, before
starting the single-cell plugin. Cross-reference: `spec/archive/review-ux.md` for the review surface in
depth; `notes/2026-09-08-1542-phase-a-exit-bmeseq.md` for the run itself.

## A. Review surface (highest value)

| # | observed | change | proof | level |
|---|---|---|---|---|
| A1 | `review` prints the hold header and predicate JSON; design 7.3 promises the evidence the model saw, each replicate's call with cited cells, and the table slice | render the 7.3 display per hold kind (`spec/archive/review-ux.md`, layer 1) | golden test per hold kind using the `toy-cs` flag hold; the `unanimous`, `split`, `one_abstain` mock fixtures for the item kinds | decisions; **done 2026-09-08** (`review_render.py`, goldens in `tests/golden/review_*.txt`, `context_contradicting.yml` replays the toy-cs judges) |
| A2 | `run`'s hold message names step and reviewer but not the hold id (14.2 says the message names the hold) | include the hold id | assert on the message in the M7 hold test | decisions; **done 2026-09-08** (message names the hold and `review --hold <id>`, which shows one hold) |
| A3 | `init` exits 0 with an open confirm hold; `run` on the same hold exits 10 | `init` exits 10 when it leaves a hold open | M2 acceptance test | decisions; **done 2026-09-08** |
| A4 | no way to read a hold without a terminal | review packet on disk per hold, HTML and Markdown (`review-ux.md` layer 2) | packet exists after a hold opens; content equals the A1 render | decisions; **done 2026-09-08** (`runs/<run>/<step>/review/<hold_id>.{md,html}`; named in the hold message) |
| A5 | every verdict path is a terminal or the agent | reviewer-run review page, `via: web` (`review-ux.md` layer 3) | deferred in design 17; build when a non-terminal reviewer exists | *design* (7.5, 14.1) |

## B. Operator ergonomics

| # | observed | change | proof | level |
|---|---|---|---|---|
| B1 | operator created the step directory, assembled job.json, and composed the container command from the job spec | at ticket time the engine creates the step dir, writes `job.json` there, and prints the exact `apptainer exec` line and the submit line; `next --json` carries both | M5 operator test asserts the files and the command; the toy operator helper in `stringency-exit/tools` becomes two lines | decisions; **done 2026-09-08** (`exec` and `submit` in the job spec; `Executor.command_line`; the operator runs the two printed lines) |
| B2 | `status --json` does not list the open confirm hold or any hold id | `status --json` includes open holds with id, kind, step, waits_on | schema fixture update; M7 test | decisions; **done 2026-09-08** |
| B3 | `run` on a project whose latest run is completed silently opens a new run | refuse with exit 16 and a message naming `run --new`; `--new` opens one | M7 test | decisions (14.1 gains a flag); **done 2026-09-08** (design 2.6 text updated too) |
| B4 | remote-mode operators pay one approval per command; 25 authorization points for five steps | B1 and B2 remove several; measure again after them | count in the next exit run | none |

## C. Trace semantics

| # | observed | change | proof | level |
|---|---|---|---|---|
| C1 | operator-run executions carry the expected digest in `env_digest` while `env_status` is `as_reported`; readable as verified | keep the expected digest in a separate field (`expected_env_digest`) and leave `env_digest` null when unverified; coverage report unchanged | M5 test on both runners; trace-schema spec updated | decisions (9.4 adds a column, does not reshape); **done 2026-09-08** (migration `0002_expected_env_digest.sql`) |
| C2 | operator-run executions have no `command`; the operator's exact invocation is lost | `submit --command "<string>"` recorded as reported, or the job-log parser captures a `command:` line the ticket tells the operator to echo | M5 test; `toy-cs` shows the gap | decisions; **done 2026-09-08** (`--command`; the ticket's submit line carries it) |
| C3 | env verification for operator steps never exercised: toy modules declare only `job_log` evidence | toy operator modules also declare `apptainer_inspect` evidence; the ticket says how to produce it; the exit run then shows `verified` on operator steps | M5 test for the verified operator path | toy method only; **done 2026-09-08** (ticket `evidence_commands`; the inspect file also carries `sha256sum <image>`, because inspect labels have no digest of the SIF) |

## D. Judgment contract

| # | observed | change | proof | level |
|---|---|---|---|---|
| D1 | all three judges used `contradicting_evidence` for context cells, firing `judg.confidence_consistent` | define the slot in the prompt suffix and in `spec/module-contract.md`: a contradicting ref is a cell that argues against the chosen label; or count only such refs in the criteria. Pick one; the first is simpler and keeps the predicate mechanical | toy prompt updated; the `toy-cs` responses replayed through the gate as a regression fixture | decisions; module-contract text; **done 2026-09-08** (`evidence_suffix` on every prompt; toy prompt and label-groups 0.1.1; `context_contradicting.yml`) |
| D2 | delegates cannot be tool-restricted to one file; isolation is instructional | none in the engine; record the answer in design 10.2 and 19 | text | *design* (text only); **done 2026-09-08** |

## E. Deployment and operator identity

| # | observed | change | proof | level |
|---|---|---|---|---|
| E1 | a Claude Science sandbox on the workstation cannot start containers; runs go through an SSH compute host | design 10.4 text says so; the skill's mode B is the default for apptainer projects | text; integration README already records it | *design* (10.4 text); **done 2026-09-08** (10.4 text) |
| E2 | `STRINGENCY_OPERATOR_VERSION` recorded as `unknown` because the agent had no sanctioned way to learn the app version | the skill names a route (the app exposes its version to the session; find and cite it) | next exit run records a version | skill only; **partly done 2026-09-08**: the skill names the brief's `PRE` line (`render_brief.py --app-version`) as the route and forbids guessing; an in-session route from the app itself was not found from here and stays open until the next exit run |
| E3 | machine-wide install matters only for mode A; remote mode works from a per-user install | `scripts/install.sh --prefix ~/.local/lib/stringency` documented as the no-sudo route for compute hosts | run it on PROTSEQ | docs; **documented 2026-09-08, done on PROTSEQ 2026-09-14** (`--prefix ~/mytools/stringency/engine`) |

## F. Small fixes already listed elsewhere

Hold id in message (A2), init exit code (A3), step dir at ticket time (B1). Listed here so the
backlog is complete in one place.

## G. Found after the backlog

| # | observed | change | proof | level |
|---|---|---|---|---|
| G1 | `repro.dirty_tree` checks the tree at run open only; a module script edited afterwards runs under the run's SHA with nothing in the trace, and for operator steps the engine never hashes what ran | capture every module script's hash at open, hash again before an engine run and at `submit`, store it in `executions.script_blob`, and block on a difference with `exec.script_drift` | must-fire and must-pass in `test_gate`; operator and engine edit cases and the `--allow-dirty` case in `test_steps` | decisions (6.5 gains a predicate, 9.4 a column); **done 2026-09-09** |
| G2 | code the agent writes itself in a session (notebook cells, plotting scripts) is not captured anywhere; only its inability to produce a final artifact is enforced (`prov.orphan_artifact`) | either the rule alone (Commandment 5: no computation outside modules; new code becomes a module commit) or a capture verb that files a session script into the method repo or run directory with a sidecar before its output can be cross-linked | decide first | *design*; Jim's call |

## H. From the design conversation of 2026-09-09

See `spec/plans/declarations-and-objectives.md`. Summary rows so the backlog is complete in one place.

| # | change | proof | level |
|---|---|---|---|
| H1 | `declare --check <dir>`: every `init` check without creating a project; echo-back on success, exit 15 naming the failure | test on the toy declarations, good and each broken | decisions (14.1 additive); **done 2026-09-09** |
| H2 | `init --drafted-by agent --brief <file>`: `stringency.yml` records who drafted, `brief.md` kept, its hash in the confirm hold context | M2 test | decisions (2.7 text); **done 2026-09-09** |
| H3 | `inputs.yml` item `derived_from: {run_id, artifact_id}`, verified against the sidecar at `init`; captured at run open; named in the methods paragraph | two-project chain on the toy | decisions (2.3 optional field); **done 2026-09-09** (keys are `run_id, step_id, output`, what the sidecar carries) |
| H4 | `stringency-declare` skill | PROTSEQ exit run starts from a brief and a manifest | skill; **written 2026-09-09, tested 2026-09-14** on PROTSEQ as two chained projects (`examples/protseq-chain/`); gaps in section I |
| H5 | staged mode: objective list with stages, `run --objective`, fork at a stage boundary carries an objective, `obj.declared_after_result` | after app-1 as two chained projects shows where option 1 chafes | *design* |

## I. From the PROTSEQ chained exit run of 2026-09-14

Reports and files in `integrations/claude-science/examples/protseq-chain/`. The engine did what
the design says at every point, including refusing a pipeline that does not answer the drafted
question (`init.question_unsupported`, exit 15, before anything was created) and refusing `run`
after completion (exit 16). Everything below is skill, brief, or presentation.

| # | change | proof | level |
|---|---|---|---|
| I1 | the declare skill carries the shapes of the three declaration files (fields, types, which are required) so the agent does not read engine source to learn them | the agent spent about ten commands on `src/` and `tests/` before drafting | skill; **done 2026-09-14** (shapes in section 3 of the skill) ||
| I2 | the skill says what a supplied manifest becomes: an input item of plain type `csv`, hashed, consumed by nothing | the agent asked | skill; **done 2026-09-14** ||
| I3 | `plugins list --json` publishes the engine default for `min_n_per_group` (0) so the skill can name a default instead of asking twice | asked in both projects | decisions (additive); **done 2026-09-14**: `Plugin.defaults`, shown by `plugins list` and `--json`; toy publishes `min_n_per_group: 2` ||
| I4 | the skill says deliverable names come from the pipeline's step outputs as declared in `module.yml`, enumerated, not from `$steps.*` references | `consensus` chosen for "the group labels" where `group_labels` exists | skill; **done 2026-09-14** ||
| I5 | the skill writes `derived_from.project` (the upstream project root) when it copies a sidecar | captured as `null` | skill; **done 2026-09-14** ||
| I6 | `lint` accepts `<path>@<tag>` like `init` does, or refuses it clearly | passing the spec string produced "no policy.yml" | code; **done 2026-09-14** ||
| I7 | `render_brief.py` for an unbound project takes `--image` (or reads the manifest at the method path) so Phase 0 checks the image, and a `--declare` variant renders Phase 1 as the declare-skill hand-over instead of `init` from files | both patched by hand for this run (`hosts/protseq-*.md`) | code; **done 2026-09-14** (`--image`, repeatable; `--declare`) ||
| I8 | `run` prints the engine-run steps it completed before issuing a ticket | the operator misreported `01_filter` as "satisfied from `derived_from`, not re-executed" | code, presentation; **done 2026-09-14** (`completed_steps` in `run --json`, one line in the human output) ||
| I9 | operator skill and brief: `submit` and the next `run` are separate commands; one heredoc per file | `run` fired after completion (refused, 16); three heredocs joined with `;` wrote nothing | skill; **skill text done 2026-09-14** |
| I10 | echo-back grammar: "at least 2 units per group" | "with at least 2 unit per group" | code, presentation; **done 2026-09-14** ||
| I11 | B4 recount: 12 approval-gated calls for `toy-process` (one step), 26 for `toy-engine` (five steps, one dispatch) against 25 for `toy` on BMESEQ | agent counts | measurement, no change |

## Order

1. A1, A2, A3 together: one session, golden tests, `toy-cs` as fixture. Done 2026-09-08.
2. B1, B2, B3, C1, C2: one session; re-run the toy exit by hand afterwards and count commands. Code done 2026-09-08; the recount (B4) waits for the next exit run.
3. C3 and D1: toy method edits plus tests; bump the toy module versions. Done 2026-09-08 (modules and pipelines 0.1.1 in the plugin template and in `~/github/stringency-toy-method`, tagged v0.1.1).
4. E1, D2 design text; E2 skill; E3 docs. Done 2026-09-08 (E2 partly: see its row).
5. A4 when A1 exists (done 2026-09-08). A5 on its trigger.
6. PROTSEQ exit run on the updated engine: done 2026-09-14. Section I done 2026-09-14 (I11 is a measurement). Then `v0.1.0`, and the roadmap in `spec/plans/roadmap-2026-09.md`: UX (two audiences), the bulk RNA-seq plugin, spatial QC.

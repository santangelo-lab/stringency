# Engine v0.2.7: the changes the first upstream run demands (2026-10-07)

Working note, not the spec. Part 1 of the owner's two asks of 2026-10-07 evening ("Before we run on
the other Lyons CLP data I want to update the engine with the one correction route we found here");
part 2, the console, is `console-and-fleet-plan.md`. Items marked *design* change design text and
need the owner's approval; the rest are DECISIONS-level or below.

**Status 2026-10-07, evening.** Built on branch `engine-v0.2.7`: 1.1 (main reconciled, pushed),
1.2 L13, 1.3 L12, 1.4 L8, 1.5 `wait`, the operator skill's `wait` paragraphs; version 0.2.7. The
release steps of 1.6 follow in the session note `notes/2026-10-07-1730-engine-v027.md`.
Earlier status: proposed, nothing built. This is the next Lane A session's work, to be done
before lung, gut and spleen run on `xenium-upstream`. The session that wrote this ran out of
context; section 0 is the handoff.

## 0. Handoff: where everything is and how to start

- Engine checkout: `~/mytools/stringency/stringency` (branch `main`, clean, pushed). The shared
  install the lab runs is `/data/lab/env/stringency/current` → `versions/0.2.6-sc0.4.2`, built by
  `scripts/install.sh` from the GitHub tag `v0.2.6` of `santangelo-lab/stringency` plus
  `santangelo-lab/stringency-plugins@v0.4.2#subdirectory=plugins/stringency-singlecell`
  (`--no-toy`, no `--link-bin`; see the plugin build notes in
  `notes/2026-10-07-1100-lane-f-f5-upstream.md`). Install with `umask 002`.
- **Branch state** (found 2026-10-07): `main` has no `src/` commit beyond `v0.2.6` but lacks the
  three Track 1h commits that the tag carries (`c4cfa5c` the project page on `review --serve`,
  `a8a778e` version 0.2.5 notify and page, `8d904c2` page discovery and version 0.2.6). They sit
  on `track-1h-page` and the tag. `git diff --stat v0.2.6 main -- src/` shows the page code
  missing on main. Step 1 below merges the tag into main; cut every later tag from main.
- Method repo: `~/github/stringency-xenium-method`, tag `v0.6.0-rc6` (pipeline `xenium-upstream`
  0.1.0, nine steps), `PLAN.md` items 3.8 to 3.12 name the method follow-ups that depend on this
  release (3.12 is the `when:` clause). Plugin repo: `~/github/stringency-plugins`, tag `v0.4.2`.
- The data-side record and the owner's five decisions of the day: `spatial-method-plan.md`
  section 5.1 and section 8 decisions 16 to 20; `/lab/projects/Lyons_CLP/PROGRESS.md` (2026-10-07).
- Backlog rows this release closes or advances: L8, L12, L13 (close); L5, L6, L10, L11 stay open.
- Tests: `uv run pytest` at the engine root (toy plugin under `plugins/stringency-toy`, method
  template under `templates/method-repo`); the toy pipeline is where the conditional-step tests go.
- Memory for a Claude Code session in `~/mytools/stringency`: `lane-f-upstream-pipeline-design.md`
  and `few-large-pipelines.md` in the project memory directory carry the state in two pages.

## 1. The work, in order

In this order, one Lane A session, about a day and a half.

### 1.1 Reconcile `main` with `v0.2.6` (an hour)

Merge `v0.2.6` into `main` (no code conflicts: `main` touched no `src/` file since the tag; the
three page commits bring `review_serve.py`, `board.py`, `present.py`, `verb_review.py`, the tests and
`spec/plans/project-page-and-notify.md`). Every later tag is cut from `main`. Record the branch
state in `DECISIONS.md` so it is not rediscovered.

### 1.2 L13: conditional steps (half a day) — *design*, 3.3 and 7.1

The owner's rule (Lane F decision 20): batch correction happens at most once; a corrected run gets a
readout, not a second judgment.

- `StepDecl` gains `when: {step: <id>, param: <name>, equals: <value>}` (or `not_equals`), one
  condition, on a step that precedes it. Lint: the referenced step must be an ancestor, must declare
  the parameter, and every required input of a skippable step's successors that binds one of its
  outputs must be `optional` on the module, else error.
- `StepStatus.SKIPPED`, edges `pending → skipped`; `next_step` evaluates `when` against the
  referenced step's admitted action when the step becomes runnable, transitions it with a
  `step_events` payload `{"when": ..., "actual": ..., "reason": "skipped: integration was harmony"}`,
  and successors treat `skipped` as done. `resolve_inputs`: a `$steps.<skipped>.<out>` reference
  resolves to nothing; optional inputs are omitted, required ones raise (lint prevents it).
- `plain`, `summary` ("What ran": the step by title, "skipped: ..."), `present`, the board and the
  page show skipped steps as such; coverage counts them as not evaluated, named.
- Tests on the toy: a two-branch pipeline where the second step's `when` depends on the first's
  parameter; both branches; the optional-input omission; the lint error; a fork that changes the
  parameter flips the branch.
- Method follow-up (`stringency-xenium-method` v0.6.0-rc7): `05_assess_batch` gets
  `when: {step: 03_reduce, param: integration, equals: none}`, the report's `batch_consensus`
  becomes optional, PLAN 3.12 closes.

### 1.3 L12: evidence-table keys (an hour)

`tables.py`: never coerce the key column; coerce only values that are purely digits with an optional
decimal point (no underscores, no leading zeros); render keys exactly as read. Test with an id-like
key (`0076570_24`). Closes the cause of one rejected dispatch today.

### 1.4 L8: the recommendation in the packet (an hour)

`review_render` and the hold page resolve `rationale_ref` to the stored message for
`param.agent_proposed` and `sc.decision_unreviewed` holds and print it under "the operator's
reason". The person then sees the recommendation where they decide, not only in chat.

### 1.5 `stringency wait` (two hours) — DECISIONS-level, 14.1 one row

`wait --hold <id> | --run <id> [--timeout <s>] [--json]`: blocks, polling `run.db` every five
seconds, until the hold is resolved or withdrawn (exit 0, printing the review's verdict and reason)
or the run leaves its current state, or the timeout passes (exit 10). No writes. This is the
operator's way to sleep until a person has answered on the console: a Claude Code session arms it
as a background command and is re-invoked when it returns; a plain script loops on it. Without it
every operator polls `run` by hand, which is what today's session did.

### 1.6 Release

Tag `v0.2.7` from `main`; install as shared `0.2.7-sc0.4.2`; the method tags rc7; the next organ
(lung) runs on both. The operator skill's section 5 gains the `wait` step (Lane E, half an hour).


## 2. Implementation notes for L13 (where to touch)

- `src/stringency/pipelines.py`: `StepDecl.when: WhenDecl | None` with `WhenDecl(step, param,
  equals | not_equals)`; `extra="forbid"` stays.
- `src/stringency/machine.py`: `StepStatus.SKIPPED`; edge `PENDING → SKIPPED`; `transition` as for
  the others.
- `src/stringency/runloop.py` `next_step`: when a pending step's predecessors are all `completed`
  or `skipped`, evaluate `when` against the admitted parameters of the referenced step (the latest
  `actions` row for that step in this run: `parameters_json`); if false, transition to `SKIPPED`
  with payload `{"when": {...}, "actual": value}` and continue the loop; successors count `skipped`
  as done in the predecessor check.
- `src/stringency/steps.py` `resolve_inputs`: a `$steps.<id>.<out>` whose step is `skipped`
  resolves to nothing: skip when the module input is `optional`, else `ConfigError` (lint should
  have caught it).
- `src/stringency/lint.py` `lint_pipeline`: `when.step` precedes the step and declares `when.param`
  (pipeline params or module schema); for each successor input bound to a skippable step's output
  the module input must be `optional`.
- `plain.py`, `summary.py` (`what_ran`: "skipped: <param> was <value>"), `present.py`, `board.py`,
  `review_serve.py` (step status rendering), `coverage.py` (skipped steps named as not evaluated).
- `spec/stringency-design.md` 3.3 (pipeline schema) and 7.1 (step states) amendment text;
  `spec/DECISIONS.md` entry; design 14.1 unchanged.
- Tests: `tests/test_run.py` or a new `tests/test_when.py` on the toy: both branches, optional
  input omitted, lint error on a required input, a fork flipping the branch, summary text.

## 3. Implementation notes for `wait`

`src/stringency/cli/verb_wait.py`: `wait [--hold <id> | --run <id>] [--timeout <s>] [--json]`;
polls `Project.find()`'s store every five seconds (read-only connection); for a hold, returns when
`resolved_by_review` or `resolved_via` is set, printing the review row's verdict, reason, reviewer,
via; for a run, when `runs.status` changes or `next_step` changes kind; exit 0 on an event, 10 on
timeout, 15 on a bad id. Register in `cli/app.py`; one row in design 14.1; tests with a thread
that records a review while `wait` polls.

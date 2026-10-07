# The console: one place to watch every run and answer every hold, and the engine changes before the next organ (2026-10-07)

Working note, not the spec. Drafted the night the first `xenium-upstream` run delivered (Lane F
F5, `notes/2026-10-07-1100-lane-f-f5-upstream.md`). Two asks from the owner that evening:

1. "Before we run on the other Lyons CLP data I want to update the engine with the one correction
   route we found here": the engine must let a corrected run skip the batch judgment (backlog L13),
   plus the smaller defects the day exposed (L8, L12).
2. "Sometimes I will want to multiplex this across multiple different groups and run them
   simultaneously with different agents or sessions ... Reviewing and approving holds for these
   multiple sessions would require jumping around to a lot of different sessions or agents. Could
   we plan out a single central location that I could use to see progress of all these sessions,
   details about review holds, and send decisions on holds. I'm envisioning some sort of web app."

Items marked *design* change design text and need the owner's approval; the rest are
DECISIONS-level or below. Section 6 lists the decisions the owner takes before the build.

**Status 2026-10-07.** Proposed. Nothing built. Part 1 (engine v0.2.7) is the next Lane A session;
part 2 (the console) follows once decisions 1 to 4 are taken.

## 1. What already exists, and what the day showed

The central location exists in an early form. Engine `v0.2.6` (the shared install) serves
`stringency review --serve --projects <dir>`: a landing page with the board of every project under
the directory (two levels deep, the way `board` walks) and the queue of open holds across them; a
project page (steps by title with status, open holds, deliveries); a run page (`present` sections,
the summary, the delivered files); a hold page that renders the packet exactly as the terminal does
and takes the verdict, recorded as `via: web` under the account that started the server (design
7.5); `--read-only` and `--token-file` for a standing instance; a reload every few seconds. Beside
it, `notify.py` sends one message per hold opened, run completed, delivered or failed, to email, a
Teams webhook or a command, from a per-user `~/.config/stringency/notify.yml`. The plan behind both
is `spec/plans/project-page-and-notify.md` (Track 1h, on the `v0.2.6` tag).

Two facts about the repository: `main` is twenty-six commits ahead of `v0.2.6` in plans and notes
and three commits behind it in code (the three Track 1h page commits sit on `track-1h-page` and the
tag, not on `main`). The shared install was built from the tag, so the lab runs code that `main` does
not carry. Part 1 starts by merging the tag into `main`.

What one day of real runs on the page's own terms showed, from the Lyons liver (eleven holds
answered in chat, three judgment dispatches re-run on mechanical faults, three re-declarations):

- A corrected run re-asks the batch judgment and the reviewers can only say `cannot_tell` (L13).
- The hold packet shows the operator's recommendation as a hash, not its text (L8).
- An evidence table whose key looks numeric is rendered one way and looked up another (L12).
- A judgment whose outcome is a route reuses the flag hold's accept/reject (L10), and a correction
  fork cannot see its parent's outputs (L11); both are design-level and can wait.
- The operator relays every hold into chat and the person answers in chat; with one organ that is
  fine, with four it is the problem the owner names.

## 2. Part 1: engine `v0.2.7` before the next organ

In this order, one Lane A session, about a day and a half.

### 2.1 Reconcile `main` with `v0.2.6` (an hour)

Merge `v0.2.6` into `main` (no code conflicts: `main` touched no `src/` file since the tag; the
three page commits bring `review_serve.py`, `board.py`, `present.py`, `verb_review.py`, the tests and
`spec/plans/project-page-and-notify.md`). Every later tag is cut from `main`. Record the branch
state in `DECISIONS.md` so it is not rediscovered.

### 2.2 L13: conditional steps (half a day) — *design*, 3.3 and 7.1

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

### 2.3 L12: evidence-table keys (an hour)

`tables.py`: never coerce the key column; coerce only values that are purely digits with an optional
decimal point (no underscores, no leading zeros); render keys exactly as read. Test with an id-like
key (`0076570_24`). Closes the cause of one rejected dispatch today.

### 2.4 L8: the recommendation in the packet (an hour)

`review_render` and the hold page resolve `rationale_ref` to the stored message for
`param.agent_proposed` and `sc.decision_unreviewed` holds and print it under "the operator's
reason". The person then sees the recommendation where they decide, not only in chat.

### 2.5 `stringency wait` (two hours) — DECISIONS-level, 14.1 one row

`wait --hold <id> | --run <id> [--timeout <s>] [--json]`: blocks, polling `run.db` every five
seconds, until the hold is resolved or withdrawn (exit 0, printing the review's verdict and reason)
or the run leaves its current state, or the timeout passes (exit 10). No writes. This is the
operator's way to sleep until a person has answered on the console: a Claude Code session arms it
as a background command and is re-invoked when it returns; a plain script loops on it. Without it
every operator polls `run` by hand, which is what today's session did.

### 2.6 Release

Tag `v0.2.7` from `main`; install as shared `0.2.7-sc0.4.2`; the method tags rc7; the next organ
(lung) runs on both. The operator skill's section 5 gains the `wait` step (Lane E, half an hour).

## 3. Part 2: the console

### 3.1 What it is

The console is `review --serve` grown into the one place the owner opens: every project under one
or more roots, what each is doing, who is driving it, what waits on a person, and the form to answer.
It stays a server-rendered HTML service that runs under the reviewer's own account, because that
account is the identity a verdict carries (design 7.5), and nothing in this plan moves a verdict's
trust boundary. It is reachable through an SSH tunnel from the laptop, as `scripts/review-page.sh`
does today, or on a fixed lab-network port if the owner decides so (decision 2).

What is possible now, as a statement of the limits: a web page can show everything the trace holds
and record verdicts as the account that runs it. It cannot make an agent session act. An operator
session learns that a verdict exists only by asking the engine (the `wait` verb in 2.5) or by being
told through a channel it listens to. And a single instance cannot serve several reviewers without an
authentication design the engine does not have (section 5).

### 3.2 Phases

**C1. A standing console (half a day).** A systemd user service on PROTSEQ under the owner's account
(`loginctl enable-linger`) running `review --serve --projects /lab/projects --token-file
~/.config/stringency/token --port 8765`, loopback; the laptop tunnels. Several roots
(`--projects` repeatable) so Lyons and ROSC appear together. Decisions 1 and 2 of the Track 1h plan
are taken here: the verb stays `review --serve`; the standing instance is per account.

**C2. A queue that tells the person what to do (a day).** The landing page leads with the holds,
grouped by what they ask: confirm the design, approve a parameter (with the operator's reason, L8),
decide a route (the batch judgment's consensus and the reviewers' rationales), settle a
disagreement (each replicate's call), accept a flag. Each hold shows the method skill's `hold_view`
tables and, new, the figures the view names (the batch panel, the UMAPs), through a step-file route
limited to files a `hold_view` names (today the file route serves delivered files only). Identical
flag holds across sibling projects are one form (backlog L6, the confirm-once note (d)): the
sixteen threshold holds of 2026-10-06 become one. Per project the board shows who is driving: the
operator harness and session reference from `runs`, the time of the last engine call from
`step_events`, and a staleness mark when nothing has happened for longer than the step's expected
time; and the `plain` next sentence.

**C3. Operators that wait (half a day, engine 2.5 plus skill text).** After relaying a hold the
operator says one sentence in its own chat ("waiting on the console for hold ..."), arms `wait`, and
resumes when it returns. The console never drives sessions. Optionally the notify `command` channel
pings the operator's harness as well (for Claude Code, a message to the session), which is a
convenience on top of `wait`, not a replacement.

**C4. The fleet (a day, skill and a small engine cap).** Running several groups at once. Two models,
both of which the console serves without change:

- *Sessions*: one Claude Code session per project, each in its own `screen` window, each the
  operator of that project (the proven pattern). The person opens the console, not the sessions.
- *One session, one operator subagent per project*: a single Claude Code session forks an operator
  per project; each runs the loop, spawns its own judgment delegates, arms `wait`, and reports to
  the parent only at delivery or failure. Fewer windows, one transcript; the parent must not relay
  holds itself.

Either way the machine needs a cap: four `cluster-umap` steps at 128 GB each would exceed PROTSEQ.
`STRINGENCY_MAX_PARALLEL` (or a `fleet:` line in the project's `stringency.yml`), honoured by the
executor through a lock directory, so a step waits for a slot rather than failing; the console shows
"waiting for a slot". Spleen (1.4 M cells) sets the slot size.

**C5. A richer client (later, decision 4).** The page is no-JavaScript by design (auditable, no build
step). If the owner wants live updates without reloads, filters, or a dashboard feel, the honest next
step is JSON endpoints on the same server (`/api/projects`, `/api/holds`, `/api/hold/<id>`) and a
small front end that renders them (htmx-style partial refresh keeps no build step; a React app would
be a separate artifact). The verdict form stays the server's. A full web app with its own identity,
accounts and sharing is a different product and needs section 5 settled first.

## 4. What the console shows, by page

| page | shows | source |
|---|---|---|
| landing | hold queue grouped by ask; board rows (project, pipeline, tag, confirm, run state, next sentence, driver, last call, holds); deliveries today | `board.project_entry`, `review.queue`, `runs`, `step_events` |
| project | steps by title with status (incl. skipped), holds, runs (incl. forks and abandoned, with reasons), deliveries | `step_statuses`, `runs` |
| hold | the packet; the operator's reason; `hold_view` tables and figures; replicates' rationales; the verdict form | `review_render`, `present_hold`, step files |
| run | `present` sections; summary; delivered files; the figures gallery | `present_run`, `deliver/` |
| batch | the sibling holds that are identical, one form | `review_batch` |

## 5. Several reviewers (*design*, 7.5)

Design 7.5 ties a web verdict to the account that runs the server. For the owner alone that is a
standing instance under their account. For a lab where several people review (ROSC had one
analyst; the Lyons work has one owner), the options are:

1. One instance per reviewer, each started under their own account against the same projects
   (`review-page.sh`); a shared read-only board instance beside them. No engine change. Two or
   three reviewers at most.
2. One shared instance with real login that maps to Emory AD identities (PAM or SSH-agent
   forwarding) and records the logged-in user as the reviewer. A design amendment to 7.5 and a
   dependency the engine has avoided so far.
3. An auth proxy in front of a service-account instance. Breaks the account boundary unless the
   proxy's identity is trusted, which puts the trust in the proxy's configuration, not the trace.

Recommendation: option 1 now; option 2 only when a second regular reviewer exists.

## 6. Decisions for the owner

1. Fleet model for the next organs: separate sessions in `screen`, or one session with operator
   subagents. Recommendation: separate sessions for lung, gut and spleen now (proven today), the
   subagent model tried on ROSC where there are eleven tissues.
2. The standing console: loopback plus tunnel (recommended) or a fixed lab-network port.
3. `wait` as an engine verb (recommended) or a loop in the skill text only.
4. Whether C5 (JSON endpoints and a live front end) is wanted after C2, or C2's server-rendered
   pages are enough for now. Recommendation: judge after a week on C2.
5. The several-reviewers model (section 5). Recommendation: option 1 until a second reviewer exists.

## 7. Order and measurement

| step | depends on | estimate |
|---|---|---|
| 2.1 merge | nothing | 1 h |
| 2.2 L13 | 2.1 | half a day |
| 2.3 L12, 2.4 L8 | 2.1 | 2 h |
| 2.5 `wait` | 2.1, decision 3 | 2 h |
| 2.6 release + method rc7 | 2.2 to 2.5 | 2 h |
| C1 standing console | 2.1, decision 2 | half a day |
| C2 queue | C1 | 1 day |
| C3 operators wait | 2.5, C1 | half a day |
| C4 fleet cap + skill | C3, decision 1 | 1 day |
| C5 richer client | C2, decision 4 | 2 days |

Measure on the next organs: time from hold opened to verdict recorded (from `holds.created` and
`reviews.ts`), the number of chat turns the owner spends on holds per project (target: zero relayed
holds once C2 and C3 exist), and the number of session switches per day.

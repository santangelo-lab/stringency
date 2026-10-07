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

**Status 2026-10-07.** Brainstorm, not yet a plan the owner has approved. Nothing built. The owner's
direction the same evening: "I want the new interface to be more interactive than the old board";
section 3.3 is the brainstorm of what interactive means here. Part 1 (engine v0.2.7) is the next
Lane A session; part 2 follows once decisions 1 to 5 are taken.

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

## 2. Part 1: the engine release before the next organ

Moved to its own document, `engine-v0.2.7-plan.md` (merge `v0.2.6` into `main`, L13 conditional
steps, L12, L8, the `wait` verb, release `v0.2.7`, method rc7). The console depends on `wait`
(section 3.2, C3) and on the merge (the page code is on the tag, not on `main`).

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

**C5. The interactive console (the target, decision 4).** The owner wants the new interface
more interactive than the board. The page today is a no-JavaScript document that reloads itself;
the console becomes an application: the same server grows JSON endpoints (`/api/projects`,
`/api/holds`, `/api/hold/<id>`, `/api/run/<id>`, an event stream `/api/events` by server-sent
events so the page updates when the trace changes, no reload), and a front end that renders them.
The verdict stays a POST to the server, recorded under the account, so the trust boundary is
unchanged. Section 3.3 lists the interactions; section 3.4 the technical options.

### 3.3 What "interactive" can mean here (brainstorm)

Things a person could do on the console that they cannot do on the board or in chat:

- **An inbox of holds.** The queue reads like mail: unread first, grouped by what it asks, keyboard
  navigation (next hold, accept, reject), a hold opens in place with the packet, the tables and the
  figures, and the verdict form at the bottom. Answering one advances to the next. Snooze equals
  defer with a note.
- **Figures that can be looked at.** The batch panel, the UMAPs by slide and animal, the elbow
  plot and the marker dot plot inline at the hold, zoomable, side by side where the decision is a
  comparison (uncorrected beside corrected, resting beside activated). Today the person asks the
  operator to show them.
- **Tables that can be sorted and filtered.** The per-cluster batch table sorted by excess, the
  cluster summary filtered to single-slide clusters, the markers of one cluster on click. The data
  are already CSVs the engine hashed; the page only renders them.
- **The elbow as a chart with the proposal drawn on it.** The operator's proposed `ndim` as a line
  on the elbow curve, the knee heuristics marked, so the person sees what thirty-five means before
  approving. No slider that changes the proposal: the operator proposes, the person approves (7.5);
  a "reject with a suggested value in the reason" is the honest form of a slider.
- **A note to the operator.** Beside the verdict, a free-text note the operator reads when `wait`
  returns ("use rpca, not harmony"; "re-run at resolution 0.6"). It is the review's reason today;
  the console makes it a first-class field the operator is told to read.
- **Batch accept across siblings.** Identical parameter holds across four organs shown as one card
  with the differing cells highlighted, one verdict (L6).
- **Who is driving, live.** Per project: the operator session, its last engine call, its current
  step and how long it has been running against the step's expected time, a stale mark; a fleet
  view of all of them on one screen; a per-project timeline of runs, forks and abandons with their
  reasons (the liver had seven runs across three projects today; nobody can reconstruct that from
  the board).
- **Live updates.** The page changes when the trace changes: a hold appears, a step completes, a
  delivery lands, without reloading and without losing the form the person is typing in.
- **The delivery as a gallery.** The report's figures as a browsable gallery, the summary beside
  them, the labels table with the replicates' rationales on hover; a link to the artifact the
  session published, if any.
- **Decision history.** Every verdict the person ever gave, searchable ("what did I say about
  resolution on lung"), with the hold it answered; the override corpus (7.6) made visible.
- **What the console must not do:** choose a verdict, pre-fill a reason, change a parameter, start
  or stop an operator, or let one account answer for another.

### 3.4 How to build it (options)

1. *Progressive enhancement on the existing server* (recommended first): JSON endpoints and an SSE
   stream added to `review_serve.py`; the page keeps server-rendered HTML and adds a small amount of
   JavaScript, vendored into the package (no CDN, no build step, works through the tunnel), for
   live refresh, sorting, filtering, keyboard navigation and image zoom. Reversible, auditable, one
   codebase, no new process.
2. *A single-page application* (React or Svelte) built into a static bundle served by the same
   server from `/app`, talking only to the JSON endpoints; the verdict POST unchanged. More
   interactive, a build step, a second codebase; worth it if the console becomes the lab's daily
   tool for many people.
3. *A separate web service* with its own identity: rejected until section 5 is settled, since it
   would move the verdict's trust boundary off the account.

Both 1 and 2 keep the engine as the only writer of the trace and the server as the only verdict path.

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
4. The build route for the interactive console (section 3.4): progressive enhancement on the
   existing server (recommended first) or a single-page application; and which of the section 3.3
   interactions come first. Recommendation: the inbox, the figures at the hold, live updates, who is
   driving; the rest after a week of use.
5. The several-reviewers model (section 5). Recommendation: option 1 until a second reviewer exists.

## 7. Handoff for the next session

The session that wrote this ran out of context. To continue: read this document and
`engine-v0.2.7-plan.md` (its section 0 names every path, the branch state and the install). The
page code to extend is `src/stringency/review_serve.py` as it stands on the `v0.2.6` tag (landing,
project, run, hold, file routes; `--read-only`, `--token-file`; jinja2 string templates, inline
CSS, no JavaScript) with `review_render.py`, `present.py`, `board.py`, `review_batch.py` and
`notify.py` beside it; the earlier plan is `project-page-and-notify.md` (on the tag). Start the page
today with `scripts/review-page.sh protseq /lab/projects` from the laptop. Nothing in part 2 should
begin before the owner has taken decisions 1 to 5 in section 6; part 1 can begin at once.

## 8. Order and measurement

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
| C5 interactive console, first interactions | C2, decision 4 | 2 to 3 days (route 1), a week (route 2) |

Measure on the next organs: time from hold opened to verdict recorded (from `holds.created` and
`reviews.ts`), the number of chat turns the owner spends on holds per project (target: zero relayed
holds once C2 and C3 exist), and the number of session switches per day.

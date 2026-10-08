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
DECISIONS-level or below. Section 7 lists the decisions the owner takes before the build.

**Status 2026-10-08, night.** Built on branch `console` the same night the decisions were taken:
C1 (routes by id, the cookie, several roots with a rescanning registry, the service unit), the C2
first cut (the inbox grouped by ask with the method's `ask` phrase and `step` selector, the
driver block, the timeline), the C5 first cut (the `data_version` watcher, `/events`, the JSON
routes, the vendored script, CSP) and C3 (console mode in the operator skill). Not built: the
second cut (figures, tables and the chart at the hold, batch cards, the gallery, the history), C4
(the resource cap), `resources_observed`, `wait --json` already prints the reason. Nothing is
released: the branch merges into `main` and tags `v0.2.8`; the standing unit
`scripts/stringency-console.service` then runs the shared install. Earlier status: design done and
the owner's seven decisions taken (section 7) on 2026-10-07 evening. The owner's direction: "I want the new interface to be more interactive than the old
board." Part 1 (engine v0.2.7) was released the same evening (`notes/2026-10-07-1730-engine-v027.md`:
L13, L12, L8, `wait`, shared `0.2.7-sc0.4.2`, method rc7), so part 2 can start with C1. The order
after the decisions: C1, then the first cut of C2 and C5 together (the inbox with the operator's
reason, live updates, who is driving), C3 console mode, then figures and the chart, batch cards,
the gallery and the history after a week of use; C4 when the organs need it. This revision adds the server's shape (section 3.5), the event
stream (3.6), the inbox and its grouping rule (3.7), figures, tables and the elbow chart at the
hold (3.8), who is driving (3.9), decision history (3.10), the fleet protocol and the resource cap
(section 6), tests (section 9), and the baseline numbers from the liver trace (section 10). A
static mockup of the three main views, filled from the liver trace, is
`spec/plans/mockups/console-mockup.html` (open it in a browser; it is a picture, not the product).

## 1. What already exists, and what the day showed

The central location exists in an early form. Engine `v0.2.6` (the shared install) serves
`stringency review --serve --projects <dir>`: a landing page with the board of every project under
the directory (two levels deep, the way `board` walks) and the queue of open holds across them; a
project page (steps by title with status, open holds, deliveries); a run page (`present` sections,
the summary, the delivered files); a hold page that renders the packet exactly as the terminal does
and takes the verdict, recorded as `via: web` under the account that started the server (design
7.5); `--read-only` and `--token-file` for a standing instance; a reload every sixty seconds.
Beside it, `notify.py` sends one message per hold opened, run completed, delivered or failed, to
email, a Teams webhook or a command, from a per-user `~/.config/stringency/notify.yml`. The plan
behind both is `spec/archive/project-page-and-notify.md` (Track 1h).

The repository: `v0.2.6` was merged into `main` on 2026-10-07 (engine v0.2.7 step 1.1), so `main`
now carries the page code. The console branch is `console`, worktree `~/mytools/stringency/
stringency-console`, cut from that `main`.

What one day of real runs on the page's own terms showed, from the Lyons liver (eleven holds
answered in chat, three judgment dispatches re-run on mechanical faults, three re-declarations):

- A corrected run re-asks the batch judgment and the reviewers can only say `cannot_tell` (L13).
- The hold packet shows the operator's recommendation as a hash, not its text (L8). The text
  behind the hash on the liver's `03_reduce` hold was two hundred words naming the earlier
  decision, the numbers and the owner's own phrase; the person approving saw none of it on the
  page.
- An evidence table whose key looks numeric is rendered one way and looked up another (L12).
- A judgment whose outcome is a route reuses the flag hold's accept/reject (L10), and a correction
  fork cannot see its parent's outputs (L11); both are design-level and can wait.
- The operator relays every hold into chat and the person answers in chat; with one organ that is
  fine, with four it is the problem the owner names.

## 2. Part 1: the engine release before the next organ

Moved to its own document, `engine-v0.2.7-plan.md`, and released on 2026-10-07 evening (L13
conditional steps, L12, L8, the `wait` verb, tag `v0.2.7`, shared `0.2.7-sc0.4.2`, method rc7).
The console depends on `wait` (section 6.2) and on L8 (the operator's reason on the hold page,
section 3.8); both exist.

Three small things the console wants that the release did not include; each lands in the console
branch:

- `review --serve --projects <dir>` repeatable (today `projects_dir` is a single path), so Lyons
  and a second study appear on one console.
- `executions.observed_params_json` gains a `resources_observed` key (max RSS and wall time from
  `resource.getrusage(RUSAGE_CHILDREN)` after the executor's `run`), so the fleet cap in 6.3 has
  real numbers to size slots from after the first lung run. Below the contract: the column is an
  existing JSON blob.
- `wait --json` prints the review's `reason` in full, since the console makes the reason the
  operator's instruction (3.7).

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
session learns that a verdict exists only by asking the engine (the `wait` verb) or by being told
through a channel it listens to. And a single instance cannot serve several reviewers without an
authentication design the engine does not have (section 5).

The principles of the Track 1h plan bind unchanged: every number on a page is an engine output;
the form offers the verdicts `verdicts_for` lists and nothing else, with no default chosen and no
reason pre-filled; the page adds no state of its own to the trace; nothing shown is hidden from the
trace. The console may compute presentation (an age, a sort order, a chart drawn from a table it
serves) but never a conclusion.

### 3.2 Phases

**C1. A standing console (half a day).** A systemd user service on PROTSEQ under the owner's account
(`loginctl enable-linger`) running `review --serve --projects /lab/projects --token-file
~/.config/stringency/token --port 8765`, loopback; the laptop tunnels. Several roots
(`--projects` repeatable) so Lyons and a second study appear together. Stable routes by id
(3.5) land here, because a live page cannot address projects by their position in a list that
changes. The read-only unit `scripts/stringency-page.service` on 8766 stays as it is for other
readers. Decisions 1 and 2 of the Track 1h plan are taken here: the verb stays `review --serve`;
the standing instance is per account.

**C2. A queue that tells the person what to do (a day).** The landing page leads with the inbox of
holds, grouped by what each asks (3.7). Each hold shows the operator's reason (L8), the method's
`hold_view` tables and, new, the figures and the chart the view names (3.8). Identical parameter
holds across sibling projects are one card (L6). Per project the board shows who is driving (3.9)
and the `plain` next sentence.

**C3. Operators that wait (half a day, `wait` plus skill text).** After relaying a hold in one
sentence the operator arms `wait` and resumes when it returns, reading the reason as its
instruction (6.2). The console never drives sessions. Optionally the notify `command` channel
pings the operator's harness as well, which is a convenience on top of `wait`, not a replacement.

**C4. The fleet (a day, skill and a small engine cap).** Running several organs at once under a
resource cap the executor honours (6.3), with the console showing "waiting for a slot".

**C5. The interactive console (the target, decision 4).** The page becomes an application: the
same server grows JSON endpoints and an event stream (3.5, 3.6), and a small vendored script makes
the page update in place, sort and filter tables, step through the inbox from the keyboard, and
zoom figures. The verdict stays a POST to the server, recorded under the account. Section 3.3
lists the interactions, 3.4 the build routes.

### 3.3 What "interactive" means here

Each interaction with what it reads and what has to change. "Engine" means a change under
`src/stringency/`; "skill" means the method's `skills/<pipeline>.yml`; "page" means the console
alone.

| interaction | reads | change |
|---|---|---|
| An inbox of holds: unread first, grouped by ask, keyboard next/accept/reject, a hold opens in place with packet, tables, figures and the form; answering advances to the next; defer is "seen" | `holds`, `reviews`, `context_json`, `verdicts_for` | page (3.7) |
| Figures that can be looked at: the batch panel, the UMAPs by slide and animal, the elbow plot, the marker dot plot inline at the hold, zoomable, side by side where the decision is a comparison | step files under `runs/<run>/<step>/`, `artifacts` | engine: a step-file route; skill: `hold_view` kinds `figure`, `figures`, `beside` (3.8) |
| Tables that can be sorted and filtered: the per-cluster batch table by excess, the cluster summary filtered to single-slide clusters, one cluster's markers on click | the CSVs `hold_view` already names | page (client-side over the rendered rows) |
| The elbow as a chart with the proposal drawn on it: the proposed `ndim` as a vertical line on the variance curve, the heuristic columns marked; no slider, since the operator proposes and the person approves (7.5); "reject with a suggested value in the reason" is the honest form of a slider | `elbow_table.csv`, `evidence.decision_points` or `evidence.proposed` | engine: an inline SVG line chart over a table; skill: `hold_view` kind `chart` (3.8) |
| The operator's reason beside the form | `rationale_ref` in `context_json`, `messages` | engine (L8, in v0.2.7) |
| A note to the operator: the reason the person writes is read by the operator when `wait` returns ("use rpca, not harmony"; "re-run at resolution 0.6") | `reviews.reason` | skill text (6.2); no new column |
| Batch accept across siblings: identical parameter holds across four organs as one card with the differing cells highlighted, one verdict | `holds` across roots | engine (`review_batch` extended to flag holds, L6) |
| Who is driving, live: operator session, last engine call, current step and its elapsed time against the same step elsewhere, a stale mark; a fleet view on one screen; a per-project timeline of runs, forks and abandons with reasons | `runs`, `run_events`, `step_events`, `steps` | page (3.9) |
| Live updates: a hold appears, a step completes, a delivery lands, without reloading and without losing the form being typed | the trace | engine: the event stream (3.6) |
| The delivery as a gallery: the report's figures browsable, the summary beside them, the labels table with the replicates' rationales on hover, a link to the published artifact if any | `deliver/<run>/`, `figures.dir`, `judgments`, `messages` | engine: the file route already serves delivered files; the gallery is page work over `figures.csv` |
| Decision history: every verdict the person gave, searchable, with the hold it answered; the override corpus (7.6) made visible | `reviews` joined to `holds` across roots | page (3.10) |

What the console must not do: choose a verdict, pre-fill a reason, change a parameter, start or
stop an operator, or let one account answer for another.

### 3.4 How to build it (options)

1. *Progressive enhancement on the existing server* (recommended first). JSON endpoints and an
   event stream added to `review_serve.py`; the pages keep server-rendered HTML and load one
   vendored script, `static/console.js`, a few hundred lines of plain JavaScript with no framework,
   no build step and no CDN (the tunnel carries everything; the lab network may not reach a CDN).
   The script does four things: subscribes to the event stream and patches the parts of the page
   that changed; sorts and filters tables already in the page; drives the inbox from the keyboard;
   zooms figures. Every page works with the script disabled, exactly as today. The test that the
   HTML carries no `<script` becomes: the only script is `/static/console.js`, there is no inline
   script, and the response carries `Content-Security-Policy: default-src 'self'`. One codebase,
   one process, reversible by deleting one file.
2. *A single-page application* (React or Svelte) built into a static bundle served by the same
   server from `/app`, talking only to the JSON endpoints; the verdict POST unchanged. More
   interactive, a build step, a second codebase and a dependency the engine has avoided (CLAUDE.md:
   dependencies stay boring). Worth it only if the console becomes the lab's daily tool for many
   people; the JSON endpoints of route 1 are what it would consume, so route 1 is not wasted.
3. *A separate web service* with its own identity: rejected until section 5 is settled, since it
   would move the verdict's trust boundary off the account.

Both 1 and 2 keep the engine as the only writer of the trace and the server as the only verdict path.

### 3.5 The server's shape

Routes. HTML pages first, then the JSON the script and any later front end read, then files. Ids
are the trace's own: `project_id` from `stringency.yml`, hold and run ULIDs. The positional
`/p/<i>/...` routes of today stay as redirects for one release so bookmarked notification links
keep working.

| route | returns | source |
|---|---|---|
| `GET /` | the inbox (3.7) above the fleet view (3.9) | `review.queue` over roots, `board.project_entry`, `runs`, `step_events` |
| `GET /project/<project_id>` | steps by title with status (including `skipped`, v0.2.7), the run timeline, open holds, deliveries, the confirm state, who is driving | `Site.step_statuses`, `runs`, `run_events`, `holds`, `deliveries` |
| `GET /hold/<hold_id>` | the packet, the operator's reason, `hold_view` tables, figures and chart, replicates' rationales, the form; a resolved hold shows its review | `review_render.render`, `present_hold`, `messages` |
| `POST /hold/<hold_id>` | records the verdict; HTML response as today, or JSON when the request asks for it | `record_review(..., via_override="web")` |
| `GET /batch/<key>` and `POST` | the sibling holds that are identical, one form; the verdict recorded on each hold | `review_batch` extended (3.7) |
| `GET /run/<run_id>` | `present` sections, summary, files, the figures gallery | `present_run`, `deliver/<run>/index.json`, `figures.csv` |
| `GET /history?q=` | every review across roots, newest first, filtered by text | `reviews` joined to `holds` |
| `GET /file/<run_id>/<name>` | one delivered file, as today | `index.json` only |
| `GET /step-file/<run_id>/<step_id>/<name>` | one step file a `hold_view` names, or a file inside a directory artifact the trace recorded for that step; anything else is 404 (3.8) | `artifacts`, the skill |
| `GET /api/fleet`, `/api/project/<id>`, `/api/hold/<id>`, `/api/run/<id>`, `/api/history` | the same data as the pages, as JSON (`HoldView.to_json`, `present_hold`'s payload, `board.project_entry`, the driver block) | the same functions |
| `GET /events` | server-sent events (3.6) | the trace |
| `GET /static/console.js` | the vendored script, versioned with the engine | the package |

Token and cookie. Every request still needs the token; today it rides in `?t=` on every link and
would have to ride on every `<img src>` and every `fetch`. The console sets it as a cookie on the
first tokened request (`HttpOnly; SameSite=Strict; Path=/`) and accepts cookie or query thereafter,
so links, images and the event stream carry no token and the browser's history and the server's
log do not fill with it. Notification links keep `?t=` so they work from a fresh browser. The
token's meaning is unchanged (7.5: the account is the speed bump, not the form). Below the contract;
a DECISIONS line when built.

Roots. `--projects` repeatable and `--project` repeatable as today; discovery re-run every thirty
seconds so a project initialised during the day appears without a restart. A project that fails to
load is one row that says so, never a failed page (the landing page already does this).

Threads. `ThreadingHTTPServer` with daemon threads, one thread per request; an event-stream
client holds its thread for the life of the connection, which is fine for the handful of browsers a
lab opens. Each request opens its own `Site` or `Project` and closes it, as today, so no SQLite
connection crosses threads.

### 3.6 The event stream

How the server knows the trace changed: SQLite's `PRAGMA data_version` on a read-only connection
changes whenever another connection commits to that database. One watcher thread keeps one
read-only connection per discovered project and polls `data_version` every two seconds (the cost
is a pragma per project per tick; thirty projects is nothing). When a project's value changes the
watcher takes a small snapshot (the latest run's id and status, its step statuses, the open hold
ids, the delivery count) and diffs it against the previous one to name the change. No trigger, no
engine-side hook, no file in the project: the console stays a reader.

Events, each `data:` a JSON object with `project_id` and the entity as the API would return it:

| event | when | the page does |
|---|---|---|
| `hold_opened` | a new open hold id | adds the card to the inbox, in its group; a sound or title badge if the person asked for one |
| `hold_resolved` | an open hold id is gone | removes the card; if it is the one on screen, shows the review and offers the next |
| `step` | a step's status changed | updates the project's row and the step list; restarts the elapsed clock |
| `run` | a run opened, forked, completed, failed or was abandoned | updates the row and the timeline |
| `delivery` | the delivery count rose | adds the delivery with its link |
| `project` | a project appeared or became unreadable | adds or marks the row |
| `tick` | every thirty seconds | keeps the connection alive; the page advances the elapsed clocks |

Reconnection: the browser's `EventSource` reconnects by itself; the page then fetches
`/api/fleet` once and re-renders, rather than replaying missed events, so `Last-Event-ID` is not
needed. A form the person is typing in is never replaced: the script patches rows and lists around
it and never the form element.

Without the script the pages keep the sixty-second meta refresh they have today.

### 3.7 The inbox

Grouped by what the hold asks, because the person's question is "what do you need from me", not
"what kind of row is this". The grouping rule is the engine's and knows no biology; it reads the
hold kind and the shape of its evidence. A method may name the ask in its own words through the
delivery skill (`hold_view[].ask`, 3.8): the group heading stays the engine's, the card's title is
the method's phrase when it gives one (built: C2, 2026-10-07).

| ask (engine default heading) | rule | the card shows |
|---|---|---|
| Confirm the plan | `kind = confirm` | the echo-back; accept or reject |
| Approve the operator's parameters | flag whose evidence has `proposed` or `decision_points` | the parameters with default and proposed value, the operator's reason (L8), the `hold_view` tables, figures and chart |
| Decide on the reviewers' consensus | flag on a judgment step whose evidence has `consensus_label` or `items` | the consensus, each replicate's label, confidence and rationale, the `hold_view` tables and figures |
| Settle a disagreement | item hold, `run_disagreement` | each replicate's call with its rationale and cited cells; accept one replicate or override from the vocabulary |
| Decide an uncertain item | item hold, `self_uncertain` | the same |
| Accept or reject a dispatch with invalid replicates | step-level `run_disagreement` | the failed replicates with their errors |
| Accept a flagged condition | any other flag | the predicate, its reason and evidence as the packet prints them |

Order within a group: oldest first, since a hold holds a run. Across groups: confirmations first
(nothing runs until they are answered), then parameters, then judgments, then flags. "Unread" is
page state only (a hold the browser has not shown), not trace state; defer is the trace's "seen".

Keyboard: `j`/`k` next and previous card, `Enter` open, `a`/`r`/`d` move focus to that verdict,
the reason box takes focus on a verdict that requires one, `Ctrl-Enter` submits. No key records a
verdict without the reason the engine requires; the form's rules are `record_review`'s and errors
come back as the engine's sentences, re-shown beside the form as today.

The reason as the operator's instruction. The textarea is labelled "Your reason. The operator
reads it when it resumes: if the verdict needs a next step, say it here." The engine keeps one
column (`reviews.reason`); `wait --json` returns it; the skill tells the operator to act on it
(6.2). No second field, so the trace stays as it is and a terminal verdict is no poorer than a
console one.

Batch cards (L6). When two or more open flag holds across the roots share a key, the inbox shows
one card for the set. The key: pipeline name, step id, predicate id and phase, and the parameter
names and values in `evidence.proposed` or `decision_points`. The card lists the projects and the
operator's reason from each (they may differ in words), and one verdict is recorded on every hold
through `record_review` with `reason_code: batch`, the way the confirm batch already does. Holds
that match on everything but a value are shown under the card as "similar, answer separately"
with the differing cells marked, and are not batched: a different value is a different decision.
`review --holds` at the terminal accepts the same sets. The sixteen threshold holds of 2026-10-06
become two cards.

### 3.8 Figures, tables and the chart at the hold

Which figures matter is specific to the method, the pipeline and the step (owner, 2026-10-07
evening: "we should have a system in the methods that calls out which go to the console"). That
system is the delivery skill, `skills/<pipeline>.yml` in the method repository (design 14.4): the
method names what a person sees, the engine renders it and loads no plugin. Today its `hold_view`
list names tables (kinds `table`, `json_table`, `jsonl`) for the predicate that opened a hold, and
the file route serves delivered files only. The additions below keep that division: the method
calls out the figures, per step, and the engine serves only what is called out. Four additions to
the schema (design 14.4 and `spec/method-skills.md` section 2; *design*, small, decision 6):

```yaml
hold_view:
  - predicate: param.agent_proposed
    step: 04_cluster              # new: this entry applies to holds on this step only
    ask: "Approve the number of components and the clustering resolution"
    source: 03_reduce/elbow_table.csv
    kind: chart
    x: component
    y: stdev
    mark_param: ndim            # a vertical line at the proposed or admitted value of this parameter
    mark_true: [knee, cum90_and_below5, last_drop_over_0p1]   # boolean columns drawn as ticks
  - predicate: sc.batch_route_review
    source: 04_cluster/batch_evidence/batch_panel.png
    kind: figure
    beside: $inputs.uncorrected_batch_evidence/batch_panel.png   # optional: two columns
  - predicate: sc.batch_route_review
    source: 04_cluster/batch_evidence
    kind: figures
    select: ["umap_by_slide.png", "umap_split_animal.png"]      # optional; default every image the directory's manifest lists
```

- `figure`: one image file under `runs/<run>/<step>/`, shown inline, click to zoom; `beside`
  names a second image (another step's, or a file inside a project input) and the two are shown in
  two columns at the same size. The liver's "Batch decision" question is exactly this pair.
- `figures`: a directory output; every image its `manifest.json` or `figures.csv` lists, or the
  `select` subset, as a strip of thumbnails that open in place.
- `chart`: an inline SVG line chart the server draws from the table's rows, nothing but axes, the
  line, the marked value and the ticks, with the numbers from the table printed at the marks. The
  marked value comes from the hold's evidence (`decision_points.<param>.value` or
  `proposed.<param>.proposed`), so the person sees where thirty-five falls on a curve whose knee
  the heuristics put at sixteen. The engine knows nothing of elbows: it draws a column against a
  column and marks a parameter.
- `ask`: the method's phrase for the inbox heading (3.7).
- `step`: an optional step id on any `hold_view` entry. Today entries match by predicate alone, and
  `param.agent_proposed` fires on three steps of `xenium-upstream`, so the elbow entry would be
  looked for on the normalisation hold as well (it degrades with a note, but the note is noise).
  With `step` the method says which figures belong to which decision. Without it, the entry
  applies to every step as today.
- `step_view`: a new list beside `hold_view`, keyed by step id, naming the figures and tables the
  project page shows for that step once it has produced them, hold or no hold: the clustree and the
  UMAP strip for `04_cluster`, the dot plot for `06_markers`. Same kinds as `hold_view`. This is
  what makes the console useful between holds, when the person wants to see what a running organ
  has done so far without asking the operator.

```yaml
step_view:
  - step: 04_cluster
    title: "Clusters at every resolution, and the embedding"
    source: 04_cluster/cluster_figures
    kind: figures
    select: ["clustree.png", "umap_clusters.png", "umap_by_timepoint_h.png"]
```

The step-file route serves a file only when (a) a `hold_view` entry for that hold's predicate
resolves to it, or (b) it lies inside a directory the `artifacts` table records for that run and
step (the `figures.dir`, `batch_evidence.dir` and `cluster_figures.dir` outputs), and never a path
with a separator from the client, never anything outside the run directory, never a `.rds` or any
file over a size cap. Images are served with their type and `Cache-Control: private, max-age=3600`
since a step's files never change once produced.

Tables: the script sorts a rendered table by any column on click and filters rows by a text box;
the data are the rows the engine rendered, so nothing is re-read or recomputed. A link from a
cluster row to that cluster's markers is page work over the `cluster_evidence` directory when the
hold's `hold_view` names it.

Replicates' rationales: the item-hold page already prints each replicate's call and cited cells
(`review_render.render_item`); the console shows the rationale text beside each and marks the
cells that did not resolve, as the packet does.

### 3.9 Who is driving

Per project, from the latest run:

| column | source | shown as |
|---|---|---|
| driver | `runs.operator_harness`, `operator_session_ref`, `host`, `user` | "claude-code, session lane-f-f5-2026-10-07, on PROTSEQ as jrrose5" |
| last engine call | max `ts` over `step_events`, `run_events` and `reviews` for the run | "2 min ago" |
| current step | `steps.status` of the first non-completed step, with its title | "Cluster and embed (running, 4 min)" |
| the same step elsewhere | `steps.started`/`ended` of completed steps with the same pipeline and step id in the other roots | "liver took 5 min" (the engine does not know cell counts; the method's report does) |
| waiting on | the board's `_waiting` plus the slot state (6.3) | "the engine", "the operator session", "a slot (320 of 400 GB claimed)", "you" |
| stale | `running` or `dispatching` or `awaiting_execution` with no event for longer than fifteen minutes and longer than twice the step's duration elsewhere | a mark and the elapsed time |

A stale mark is information, not an action: the console names the remedies as text (resume the
session in its `screen` window; `stringency abandon --run <id> --reason` at a terminal) and does
neither. A judgment step is `dispatching` while the delegates work; the liver's annotation
dispatch took fifteen minutes, so the stale rule must not fire on it: the rule uses the same step's
duration elsewhere when one exists.

The per-project timeline: runs in order of `started`, each with its status and end, forks drawn
under their parent with the step they forked at and the delta (`run_events` `fork` payload),
abandons with their reasons, holds and their verdicts at the time they were given. The liver's
story (two runs, one fork at step five, six holds) reads as one column; the day's seven runs across
three projects, which nobody could reconstruct from the board, read as three.

### 3.10 Decision history

One page over `reviews` joined to `holds` across the roots: when, project, step title, ask,
verdict, replicate or correction, reason, `via`, reviewer. A text box filters by reason, step and
project ("resolution", "lung"). A download of the same rows as CSV. The override and rejection
rates `status --overrides` prints appear per module at the top, since the page is where a method
author would look before revising a prompt (7.6).

## 4. What the console shows, by page

| page | shows | source |
|---|---|---|
| landing | the inbox grouped by ask with batch cards; the fleet view: one row per project (project, pipeline, tag, plan, run, current step and elapsed, waiting on, driver, last call, stale); deliveries today | `review.queue`, `board.project_entry`, `runs`, `step_events` |
| project | steps by title with status (including skipped), the run timeline, open holds, deliveries, the driver | `step_statuses`, `runs`, `run_events` |
| hold | the ask; the packet; the operator's reason; `hold_view` tables, figures and chart; replicates' rationales; the verdict form; or the review that resolved it | `review_render`, `present_hold`, `messages`, step files |
| batch | the sibling holds that are identical, one form | `review_batch` |
| run | `present` sections; summary; delivered files; the figures gallery | `present_run`, `deliver/` |
| history | every review, filterable, with override rates per module | `reviews`, `holds`, `status --overrides` |

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

Recommendation: option 1 now; option 2 only when a second regular reviewer exists. The event
stream and the JSON routes change nothing here: each instance watches the same traces.

## 6. The fleet

### 6.1 Two models

Running several organs at once. Both are served by the console without change:

- *Sessions*: one Claude Code session per project, each in its own `screen` window, each the
  operator of that project (the pattern the liver proved). The person opens the console, not the
  sessions. Four windows for four organs; each session's context is spent on one organ.
- *One session, operator subagents*: a single Claude Code session forks an operator per project;
  each runs the loop, spawns its own judgment delegates, arms `wait`, and reports to the parent
  only at delivery or failure. Fewer windows, one transcript; the parent must not relay holds
  itself, and a subagent that exhausts its context loses the organ's thread where a screen window
  would keep it. Try it on ROSC, where eleven tissues would mean eleven windows.

Recommendation (decision 1): separate sessions for lung, gut and spleen now; the subagent model
on ROSC.

### 6.2 The hold protocol in console mode (skill text, decision 7)

The operator skill's section 6 today: present the hold in chat in full, wait for a verdict word
and a reason, relay with `--attest`. With a console the protocol gains a mode. Console mode is on
when the person says they are using the console or when `~/.config/stringency/notify.yml` has a
`page_url`; otherwise nothing changes.

In console mode, when `run` exits 10:

1. The operator says one sentence in chat: "Hold on {step title}: {ask}. Answer on the console
   ({link}) or here." It does not paste the packet or the `present --hold` tables; they are on the
   console.
2. It arms `stringency wait --hold <id> --timeout 86400 --json` as a background command and says
   "waiting on the console for the {step title} hold" once. A Claude Code session is re-invoked
   when the command returns; a plain script loops on it.
3. When `wait` returns it reads `verdict`, `via` and `reason`. The reason is the person's
   instruction: if it names a next step the operator can take with the verbs it has (fork with a
   parameter, propose a value, abandon), it takes it and says so in one sentence; if it asks for
   something outside those verbs, it says what it cannot do and stops. Then `run --json` as before.
4. If the person answers in chat instead, the operator relays as today; `wait` returns with that
   review. If both happen, `record_review` refuses the second as already resolved and the operator
   reports which verdict stands (the first recorded, whichever route it came by).
5. Delivery is unchanged: `present` tables pasted into chat, the files sent, the three-part report
   from `summary.md`.

What stays in chat under console mode: the one-line hold notice, the one-line "waiting" sentence,
step completions as `plain` lines, and the delivery. What moves to the console: the packet, the
tables, the figures, the verdict. This is a change to what the owner sees in the session (the
2026-09-18 instruction was to show everything in chat), so it is the owner's call: decision 7.

### 6.3 The resource cap (engine, DECISIONS-level)

Four `cluster_umap` steps at once would exceed PROTSEQ: the liver's `04_cluster` ran on 103
thousand cells; lung has 405 thousand, gut 525 thousand, spleen 1.41 million. Modules already
declare `resources: {cpus, memory, timeout}` (module contract, 3.2), so the engine knows what a
step claims before it starts.

- `STRINGENCY_SLOTS=<dir>` names a lock directory, shared by every user on the machine
  (`/lab/scratch/stringency-slots`, safe to wipe when nothing runs). `<dir>/capacity.yml` declares
  the machine's budget: `memory: 400G`, `cpus: 64`, `default_memory: 32G` for a module that
  declares none. Unset, nothing changes.
- Before the executor launches an engine-run step it reads the live claims (`<dir>/<run_id>.<step_id>.json`
  with memory, cpus, pid and start; a claim whose pid is dead is pruned), and if the step's claim
  fits it writes its own atomically and runs; otherwise it waits, polling every fifteen seconds, and
  records one `step_events` row `slot:waiting {claimed, capacity, needs}` on the first wait and
  `slot:acquired` when it starts. The step stays `admissible` while waiting and becomes `running`
  as today, so design 7.1 gains no state. The claim is removed when `run` returns, whatever the
  exit.
- Operator tickets (`awaiting_execution`) and judgment dispatches claim nothing: the first runs
  outside the engine, the second is a model call.
- The console reads the last `slot:*` event and shows "waiting for a slot (320 of 400 GB claimed
  by lung and gut)".
- Sizing: nothing measured yet. The first lung run with `resources_observed` recorded (section 2)
  gives max RSS per step; until then the module declarations are the claim. Order for the three
  organs: lung and gut together if their declared memory fits, spleen alone after, or on BMESEQ
  (1 TB) if it does not fit here.

### 6.4 Notifications in the fleet

Unchanged mechanism (`notify.py`): with `page_url` set to the console, every `hold_opened` email
links to `/hold/<id>`, which is now a page, not a redirect. Four organs at once mean four emails
in a minute at the parameter holds; the inbox is the answer to that, and the email is the nudge.
A `command` channel that writes a line into the operator session is possible but not planned: the
operator learns of the verdict from `wait`.

## 7. Decisions for the owner (taken 2026-10-07 evening)

The owner's answers are in bold after each item.

1. Fleet model for the next organs: separate sessions in `screen`, or one session with operator
   subagents. Recommendation: separate sessions for lung, gut and spleen now (proven), the
   subagent model tried on ROSC where there are eleven tissues. **Separate sessions in `screen`.**
2. The standing console: loopback plus tunnel (recommended) or a fixed lab-network port.
   **Loopback plus tunnel.**
3. `wait` as an engine verb (recommended; in the v0.2.7 plan) or a loop in the skill text only.
   **The engine verb (released in v0.2.7).**
4. The build route for the interactive console (3.4): progressive enhancement on the existing
   server (recommended first) or a single-page application; and which of the 3.3 interactions come
   first. Recommendation: the inbox with the operator's reason, the figures and the chart at the
   hold, live updates, who is driving; batch cards, the gallery and the history after a week of use.
   **Progressive enhancement. First cut: the inbox grouped by ask with the operator's reason, and
   live updates with who is driving. Second cut, after a week of use: figures, tables and the
   elbow chart at the hold; batch cards; the delivery gallery; decision history.**
5. The several-reviewers model (section 5). Recommendation: option 1 until a second reviewer
   exists. **Option 1, one instance per reviewer.**
6. The delivery-skill additions (3.8): `hold_view` kinds `figure`, `figures` and `chart`, the
   `beside` and `ask` fields; a small amendment to design 14.4 and `method-skills.md`.
   Recommendation: yes; the method already writes these files and the engine only renders them.
   **Yes, all five.** The `ask` field is part of the first cut (the inbox headings); the figure
   and chart kinds come with the second. Added after the decision, from the owner's remark that
   the figures are specific to the method, the pipeline and the step: `step` on a `hold_view`
   entry and a `step_view` list for figures shown outside a hold (3.8); both belong to the same
   amendment and the second cut.
7. Console mode for the operator (6.2): the packet, the tables and the verdict move to the console
   and chat keeps one line per hold plus the delivery. Recommendation: yes once the console exists,
   with the old protocol kept for a session without one. **Yes, console mode when a console is
   configured; the old protocol stays for a session without one.**

Below the contract and decided when built, listed so they are not rediscovered: stable routes by
id, the token as a cookie, the `data_version` watcher, the step-file route's two conditions, the
grouping rule of 3.7, the batch key, the stale rule.

## 8. Handoff

Branch `console`, worktree `~/mytools/stringency/stringency-console`, cut from `main` at the
v0.2.6 merge; the engine v0.2.7 work is on `engine-v0.2.7` in `stringency-v027` and is merged
into `main` first; the console branch rebases on that. The page code to extend is
`src/stringency/review_serve.py` (landing, project, run, hold, file routes; `--read-only`,
`--token-file`; jinja2 string templates, inline CSS, no JavaScript) with `review_render.py`,
`present.py`, `board.py`, `review_batch.py` and `notify.py` beside it; the tests are
`tests/test_review_serve.py` (fourteen tests, several asserting no `<script`). The earlier plan is
`spec/archive/project-page-and-notify.md`. Start the page today with `scripts/review-page.sh
protseq /lab/projects` from the laptop. The mockup is `spec/plans/mockups/console-mockup.html`.
Nothing in part 2 should begin before the owner has taken decisions 1 to 7.

## 9. Tests, by phase

- C1: `--projects` twice lists both roots; a project added under a root appears on the next
  discovery pass; `/project/<project_id>`, `/hold/<id>` and `/run/<id>` render by id and the old
  `/p/<i>/...` routes redirect to them; a tokened request sets the cookie and a cookied request
  without `?t=` is served; a request with neither is 403.
- C2: the inbox groups a confirm, a parameter flag (toy `param.agent_proposed`), a judgment flag
  and an item hold under the four headings and in the stated order; the operator's reason appears
  on the parameter hold (L8); a `chart` view draws an SVG with the marked value at the admitted
  parameter and the `mark_true` ticks; a `figure` and a `figures` view serve their images through
  the step-file route and the route 404s a file no view names, a path with a separator and a file
  outside the run directory; two identical toy parameter holds across two projects are one batch
  card whose POST records two reviews with `reason_code: batch`, and two that differ in a value are
  not batched; the driver block shows the harness, the session reference and the last call; the
  stale mark appears on a run with no event for the stated time and not on a dispatching step whose
  reference duration is longer.
- C3: `wait --hold` returns with the review's verdict, `via` and reason when a verdict is recorded
  from another thread; the operator skill text renders with the console-mode section and
  `tests/test_render_skill.py` keeps the two copies of section 6 identical.
- C4: with `STRINGENCY_SLOTS` set and a capacity smaller than two toy steps, the second step
  waits, records `slot:waiting` then `slot:acquired`, and runs when the first releases; a dead
  pid's claim is pruned; unset, no event is written.
- C5: `/events` sends `hold_opened` within the poll interval of a hold opening in another process
  and `hold_resolved` when it is reviewed; `/api/hold/<id>` equals `HoldView.to_json` plus the
  `present_hold` payload; the HTML carries exactly one script tag naming `/static/console.js`, no
  inline script, and the CSP header; every page still renders without the script (the existing
  tests, unchanged).

## 10. Order and measurement

The order after the owner's decisions (2026-10-07 evening):

| step | depends on | estimate |
|---|---|---|
| engine v0.2.7 | released 2026-10-07 | done |
| C1 standing console: several roots, stable routes, the cookie, the systemd unit | nothing | built 2026-10-08 |
| C2 first cut: the inbox grouped by ask with the operator's reason and the `ask` field; the driver block and the timeline | C1 | built 2026-10-08 |
| C5 first cut: the event stream, the JSON routes, the script (live updates, keyboard, sorting) | C2 | built 2026-10-08 |
| C3 console-mode skill text, `wait` in the loop | C1 | built 2026-10-08 (skill text; republish to Claude Science pending) |
| release: merge `console` into `main`, tag `v0.2.8`, shared install, start the unit, `page_url` in `notify.yml` | the above | an hour, the owner's |
| second cut: figures, tables and the chart at the hold (`figure`, `figures`, `chart`, `beside`); batch cards; the gallery; the history | a week of use | 2 days |
| C4 fleet cap, `resources_observed` | when the organs need it | 1 day |

Baseline from the liver trace (`upstream_liver`, 2026-10-07, one organ, the owner present in the
session, every hold relayed in chat): time from `holds.created` to `reviews.ts`.

| hold | ask | open for |
|---|---|---|
| confirm | confirm the plan | 6 min 49 s |
| 02_normalize flag | approve parameters (method, scale factor) | 2 min 11 s |
| 03_reduce flag | approve parameters (integration) | 1 min 20 s |
| 04_cluster flag | approve parameters (ndim, resolution) | 56 s |
| 05_assess_batch flag | decide on the consensus | 6 min 06 s |
| 07_annotate item 9 | settle a disagreement | 4 min 30 s |

Holds were open for 21 min 52 s of the run's 58 min; the compute steps took 14 min; the two
judgment dispatches about 18 min; the rest was the operator's turns. On four organs at once the
compute scales with the cells (lung four times the liver, spleen fourteen) and the holds do not,
so the person's attention arrives in bursts; the inbox and the batch cards are for the bursts.

Measure on the next organs: time from hold opened to verdict recorded, per ask, against this
table; the number of chat turns the owner spends on holds per project (target: zero relayed holds
once C2 and C3 exist); the number of session switches per day; and, for the fleet, the time steps
spent in `slot:waiting`.

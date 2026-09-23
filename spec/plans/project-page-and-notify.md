# Project page and notify on hold (Track 1h)

Working note, not the spec. Roadmap Track 1, added 2026-09-23 after the first measured run
through an analysis skill (`notes/2026-09-23-1355-lane-e-skills-and-first-run.md`). Proposes two
engine additions below the contract level and one design question for the owner (section 5).
Builds on the review page of `ux-two-audiences.md` 5.2, shipped as `review --serve` in 0.2.1.

## 1. Why

The owner's goal: a lab member who rarely does computational work can run a pipeline on their
data. The 2026-09-23 run measured the chat path at 7 person turns and 15 minutes to the first
delivered file with 0 misreports, so the conversation is close to its floor. What remains costs
the person in a different way:

- The run moves only while the person is watching. A hold waits in a chat until they come back to
  it; nothing tells them it is waiting.
- The results end in a chat transcript and a directory on the array. A person who does not use a
  terminal has no way back to them a week later.
- The `board` and `present` renderings exist, but only as terminal output or a `STATUS.md` a
  person must know to open.

Two additions answer this: a page that shows every project, its progress and its results, and a
message when a run needs a person or is finished. Both are engine-rendered, so every number a
person reads still comes from an engine output, and the agent draws nothing.

## 2. Principles that bind

- Commandment 6: the page and the message show engine outputs. No agent prose enters either.
- 14.2 and the review rule: a hold shows the engine's verdicts and effects and nothing else; the
  page's form is the one that exists, with no ranking or recommendation.
- 7.5: a verdict entered on the page is recorded under the account whose process serves it. The
  page is started by a person under their own account; an agent never starts it.
- Nothing shown to the person is hidden from the trace; the page adds no state of its own.

## 3. The project page

### 3.1 What exists

`stringency review --serve [--port] [--bind] [--project]... [--projects <dir>]`
(`src/stringency/review_serve.py`): stdlib `ThreadingHTTPServer`, jinja2 string templates, inline
CSS, no JavaScript; a random token per start on every request; loopback by default;
`GET /?t=` lists open holds over the discovered projects; `GET|POST /p/<i>/hold/<id>` renders the
packet and takes a verdict via `record_review(..., via_override="web")`. Started through
`scripts/review-page.sh <alias> [<dir>] [<port>]`, which tunnels the port from the laptop.
`board` (`src/stringency/board.py`) and `present` (`src/stringency/present.py`, `Site`) render
the progress and the results without loading a plugin. `refresh_if_present` is called by `run`,
`submit`, `review`, `deliver` and `abandon` after their work.

### 3.2 What changes

The same server grows four read-only routes and one change to the landing page. No new verb: the
flags stay on `review` (14.1), and a standing name for the page is a naming question for the
owner (section 5).

| route | renders | source |
|---|---|---|
| `GET /?t=` | landing: "Needs you" (the open-holds list of today, first), then the board: one row and one sentence per project, each linked | `board.project_entry`, `board.sentence` |
| `GET /p/<i>?t=` | one project: the board sentence; the steps by title with their status; open holds with links; deliveries with links; the confirm state | `Site`, `steps` table, `plain` |
| `GET /p/<i>/run/<run_id>?t=` | one finished run: the delivery skill's `after_delivery` tables as HTML tables, the `summary.md` body, then "Files" as download links; the `never_show` footer | `present` for `--run` |
| `GET /p/<i>/file/<run_id>/<name>?t=` | one delivered file as a download | `deliver/<run>/index.json`: only names listed there are served, with their recorded type; anything else is 404 |
| `GET /p/<i>/hold/<id>?t=` | as today, plus the `present --hold` tables above the form (the method's `hold_view` for the predicate, the confirm's echo-back) | `present` for `--hold` |

Rendering rules: the same inline CSS, no `<script`; tables from `present` are rendered as HTML
tables through the same rows the markdown renderer uses (one function, two outputs); the board and
project pages carry `<meta http-equiv="refresh" content="60">` so an open tab follows a run
without JavaScript; ids appear only inside hrefs and in the hold form where `review` needs them,
as the board does today; every page has a link back to the landing page.

`present` needs a small refactor to expose its rows before the markdown step (a
`present_rows(site, run_id, skills_dir) -> list[Section]` beside the existing renderer); the
markdown and HTML renderers both consume it, so the terminal and the page cannot disagree.

### 3.3 Identity and a standing instance

Per person, through the tunnel, as today: the reviewer starts it, the token is theirs, verdicts
record as them. That stays the only way a verdict is entered.

For reading, one standing instance is useful: a page always up on PROTSEQ that any lab member can
open to see the board and the results. It must not take verdicts, or it would record the account
that started it. So: `--read-only` disables `POST` (405 with a sentence naming the two routes that
do take a verdict: your own `review-page.sh`, or `stringency review --hold <id>` at a terminal),
and `--token-file <path>` reads the token from a file instead of generating one, so the URL is
stable across restarts. Run as a `systemd --user` service by the owner on a loopback port, reached
by tunnel or by a fixed host port on the lab network if IT allows; not 8000 or 8001, which are
this machine's Claude Science. Whether to run one is the owner's call (section 5). Group
membership already gates the array, so the token on a standing read-only instance is a courtesy
against accidental exposure, not the access control.

### 3.4 Tests (`tests/test_review_serve.py`, extended)

Landing lists projects with their sentences and the open holds first; the project page names
every step by title with its status; the run page's tables equal the rows `present --run` prints
for the same run; the file route serves a listed file with its type and 404s a name not in
`index.json` and any path with a separator; `--read-only` returns 405 on `POST` and writes
nothing; `--token-file` is honoured; no `<script` anywhere; a stranger (monkeypatched
`current_user`) is still 403 on `POST`.

### 3.5 Skill and host text

- Operator skill section 7 and the analysis skill template: "when a project page is available"
  becomes concrete: point the person at their page for progress and results instead of relaying
  `STATUS.md`; the hold protocol's exit-16 sentence names `scripts/review-page.sh`.
- `onboarding.md` step 5: the review page exists; how to start it; what the standing board is
  if one runs.
- `hosts/protseq-lab.md`: the port and the service, once decided.

## 4. Notify on hold

### 4.1 Events

Sent by the engine at the same points that call `refresh_if_present`, for the events a person
must act on or wants to hear about, never for the operator's mechanics:

| event | when | message |
|---|---|---|
| `hold_opened` | `run`, `submit`, `init` open a hold (confirm, flag, item) | "{project}: the analysis paused at {step title}. {kind}: {the hold's one-line message as the engine prints it}." plus the link |
| `run_completed` | `run` or `submit` completes the run | "{project}: {plain}." plus the link to the run page |
| `delivered` | `deliver` or `run --deliver` | "{project}: results delivered: {file names}." plus the link |
| `run_failed` | exit 13 | "{project}: {plain}." plus the link |

Not sent: tickets (21), judgment dispatches (20), parameter proposals; those are the operator's.
One message per hold id per event; a resolved hold sends nothing (the person did it).

The link is the project page's route when a page URL is configured
(`{page_url}/p/<i>/hold/<id>` cannot be known by index, so the page gains
`GET /hold/<hold_id>?t=` and `GET /run/<run_id>?t=` that look the id up across the discovered
projects and redirect); otherwise the message ends with the terminal route,
"`cd <project> && stringency review --hold <id>`".

### 4.2 Configuration

Per user, not per project, since the engine runs as the person whose Claude Science session (or
terminal) drives the run, and that is who should hear from it:
`~/.config/stringency/notify.yml`

```yaml
notify: 1
events: [hold_opened, run_completed, delivered, run_failed]   # default: all four
page_url: http://127.0.0.1:8765/?t=...                         # optional; the standing page or your tunnel
channels:
  - kind: email
    to: [me@emory.edu]
    smtp: {host: smtp.service.emory.edu, port: 25}             # or smtp.office365.com:587 with starttls and a credential file
    from: me@emory.edu
  - kind: teams_webhook
    url: https://prod-00.westus.logic.azure.com/workflows/...  # a Power Automate "Workflows" webhook posting to a Teams channel
  - kind: command
    argv: [/home/me/bin/notify.sh]                             # receives the message on stdin; for anything else
```

The lab uses email and Microsoft Teams, not Slack (owner, 2026-09-23), so the two built-in kinds
are:

- `email`: stdlib `smtplib`, one plain-text message per event, subject "{project}: {event in
  words}". Two relays were reachable from PROTSEQ on 2026-09-23: `smtp.service.emory.edu:25`
  (the campus relay; whether it accepts unauthenticated mail from this host is confirmed by one
  test send in the build session) and `smtp.office365.com:587` (STARTTLS with a credential the
  person keeps in a mode 600 file named by `credentials`; Emory's tenant may require an app
  password or refuse basic authentication, to be checked). The campus relay is the default when
  it works. No local mail agent exists on PROTSEQ, so `sendmail` is not an option.
- `teams_webhook`: the person creates a Workflow in Teams ("Post to a channel when a webhook
  request is received") on the channel they want, which gives a URL on `logic.azure.com`; the
  engine posts one Adaptive Card with the message text and the link, stdlib `urllib`, 5 second
  timeout. The older Office 365 connector webhooks are being retired by Microsoft, so the plan
  names Workflows only. Outbound HTTPS to that host works from PROTSEQ (checked 2026-09-23).

`command` runs the argv as the user with the message on stdin, for anything else. All sends have
a 5 second timeout. `STRINGENCY_NOTIFY=0` silences everything (tests, batch work). A missing file
means no notifications and no message about it.

### 4.3 Where it lives and what it records

`src/stringency/notify.py`, called from the same five verbs beside `refresh_if_present`, wrapped
the same way: a failure to send never changes the verb's exit code or output. Every attempt is
appended to `<project>/.stringency/notify.log` (event, hold or run id, channel, ok or the error),
outside `prov/`, since notifications are not part of the trace of the analysis. No new table, no
schema change.

### 4.4 Tests

A `command` channel writing to a file: a confirm hold at `init` sends one line with the project
name, step title and the terminal route; a resolved hold sends nothing; `run` to completion sends
`run_completed` once and `deliver` sends `delivered` once; `STRINGENCY_NOTIFY=0` sends nothing; a
channel whose command exits 1 leaves the verb's exit code unchanged and logs the error; with
`page_url` set the message carries the page route.

## 5. Owner decisions before build

1. The page's name: keep everything under `review --serve`, or add `stringency page` as the verb
   for the read-only page with `review --serve` kept for the form (14.1 change, one row).
2. A standing read-only instance on PROTSEQ: yes or no; if yes, loopback plus tunnel only, or a
   fixed lab-network port.
3. First channel: email through the campus relay (one test send confirms it), and whether a Teams
   channel for the lab's runs should exist beside the personal email.
4. Who is notified in v1: the user running the engine only (this proposal), or the project's
   `roles` looked up in a per-user registry. Roles need a registry that does not exist; v1 keeps
   the running user.

## 6. Order and measurement

1. Notify (half a day, engine): `notify.py`, the five call sites, config, the `email` and
   `teams_webhook` kinds, tests, `STRINGENCY_NOTIFY`; one test send through the campus relay.
2. Project page (a day, engine): `present_rows`, the five routes, `--read-only`, `--token-file`,
   the redirect routes, tests.
3. Skill and host text (Lane E, half a day): operator skill 7, the analysis template, onboarding,
   `protseq-lab.md`, `review-page.sh` default to the page; re-render the toy skill.
4. Measure: a toy run where the person leaves the chat after the echo-back and comes back on the
   notification. New column in the Measurements table: time from hold opened to verdict recorded,
   from the trace (`holds` created against `reviews.ts`). The row also records whether the person
   found their results from the page without the transcript.

Steps 1 and 2 are engine work and belong to Lane A's queue or a session that owns
`src/stringency/`; step 3 is Lane E's; step 4 is the owner's, with a lab member when one is
available.

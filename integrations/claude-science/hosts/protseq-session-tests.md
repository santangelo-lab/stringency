# PROTSEQ: the two Claude Science session tests and the measured toy run (Track 1g, UX note 3.4)

A checklist the owner runs in the Claude Science desktop app on the MacBook, with `protseq` as
the SSH compute provider. Approval cards are visible only in the app, so an agent at a terminal
cannot run this. Written 2026-09-23 by the Lane E session; results go into
`spec/plans/backlog.md` (Measurements), `integrations/claude-science/README.md` (the two 3.4
answers), and the Lane E session note.

What is already known (2026-09-15, `protseq-track1b-drive.md`): a delegate's download of a
request file, and the operator's download of a delivered file, each raise one card even inside
a configured data root (7 of 17 cards). Whether the `call_command` card offers a standing grant
is unrecorded. Both questions are asked again here under the data root the lab will use.

## A. Once, before the session

1. Data root. In the instance's compute settings for `protseq`, set (or confirm) the data root
   `/data/lab/projects`. Previous drives used the narrower
   `/data/lab/projects/2026-09_stringency-exit_jrrose5`.
2. Skills. Publish, or republish, three skills with the cell in `publish-skills.md`:
   - `stringency-operator` from
     `~/mytools/stringency/stringency-lane-e/integrations/claude-science/stringency-operator/SKILL.md`
     (unchanged since 2026-09-18 on `main`; republish only if the instance holds an older text);
   - `stringency-declare` (unchanged);
   - `stringency-analyze-toy-compare` from
     `~/mytools/stringency/stringency-toy-method/skills/stringency-analyze-toy-compare/SKILL.md`
     (toy method `v0.1.4`).
3. Engine. At a terminal: `ssh protseq 'bash -lc "which stringency; stringency --version"'`
   should print the shared path `/data/lab/env/stringency/current/bin/stringency`.
4. App version. Read it from the app's version display; the agent records it as
   `STRINGENCY_OPERATOR_VERSION` when it sets up, so have it ready to state in the first message
   if the agent asks (it may not; then the trace records `unknown`).

## B. Test 1: does a download under the data root raise a card

Ask, in a fresh session with no project context:

> On protseq, download `/data/lab/projects/2026-09_stringency-drive2_jrrose5/data/samples.csv`
> and tell me how many rows it has.

Record:

- [ ] did the `download` raise an approval card (yes or no);
- [ ] the card's text, if any: does it name the data root, the path, or a scope;
- [ ] did the `call_command` for anything the agent ran to count rows raise a card.

Then ask the agent to spawn a delegate that reads the same file, to see whether a delegate's
download behaves differently from the parent's (2026-09-15 saw a card per delegate download).

## C. Test 2: does the `call_command` card offer a standing grant

In the same session:

> On protseq, run `stringency plugins list` and tell me which plugins are installed.

When the `call_command` card appears, look at every control on it before approving. Record:

- [ ] does the card offer anything beyond approve and deny: "always allow", "allow for this
      session", "allow for this provider", "allow commands starting with ...", or nothing;
- [ ] if it does, choose the widest scope that covers `stringency` commands on `protseq` and
      note its exact wording;
- [ ] then ask for `stringency --version` and `stringency board /data/lab/projects` in turn: did
      each still raise a card.

If no standing grant exists, say so in the row; the card estimate in UX note 3.5 then stands as
written (8 or 9 cards for the toy with one dispatch), and the remaining lever is the engine's
one-command-per-moment shape.

## Results of B and C (owner, 2026-09-23, Claude Science desktop app on the MacBook)

Test 1, downloads. The `download` of `samples.csv` raised a card. Its text, as the owner
recorded it:

> Download a file from protseq? Download `/data/lab/projects/2026-09_stringency-drive2_jrrose5/data/samples.csv` (56 B) from `protseq`? This path is outside the directories Claude Science normally reads on this host (`/home/jrrose5/.claude-science-scratch`). Allowing copies the file into your local workspace. Allow for this conversation. Scope applies to any file under `/data/lab/projects/2026-09_stringency-drive2_jrrose5/data` on `protseq` (hidden files still ask).

So the card offers a conversation-scoped grant per directory (the file's parent), and the
directory the app treats as normal on this host is its scratch directory, not `/data/lab/projects`;
whether a data-root setting for `protseq` was in force at the time is not recorded, and is a
question for the next run. The row-count `call_command` also raised a card. A delegate's download
of the same file raised no card, but the conversation-scoped grant had already been given, so
this does not separate "delegates inherit the grant" from "delegate downloads never ask".

Test 2, standing grants. The `call_command` card offers four scopes: once, this conversation,
this project, global. The owner chose "this project"; `stringency --version` and
`stringency board /data/lab/projects` afterwards raised no card. So a project-scoped grant covers
every later `call_command` in that project, and the command cards of a run collapse to one.

What this means for the card estimate (UX note 3.5): with one project-scoped command grant and
one conversation-scoped download grant per directory, a toy run costs one command card plus one
download card per distinct directory the operator or its delegates read from (the dispatch
directory under `runs/`, the `deliver/` directory), against 17 on 2026-09-15. The measured run in
section D is the check.

## D. The measured toy run through the analysis skill

The acceptance test of Track 1 is this run done by someone other than the owner. Until a lab
member is available, the owner's own run through the skill gives the "after" row for the skill
text. Prepared on PROTSEQ (declarations only; the skill drafts its own, and these are the
reference to compare them against):

| item | where |
|---|---|
| parent directory | `/data/lab/projects/2026-09_stringency-drive2_jrrose5/lane-e/` |
| data | `../data/groups.csv` (50 rows, 9 units, 3 groups) and `../data/samples.csv` (the manifest) |
| reference declarations | `lane-e/reference/declarations/{inputs,design,objective}.yml`; `declare --check` exit 0 against `toy-engine@v0.1.4` on 2026-09-23 (moved out of the parent after the first run: the agent read them there) |
| first message | `lane-e/reference/START.md` |
| method | `/home/jrrose5/mytools/stringency/stringency-toy-method@v0.1.4` |
| engine | shared, `/data/lab/env/stringency/current` |

Steps:

1. New Claude Science project. No agent context is pasted this time; the skill is the entry
   point. Paste the "First message" section of `START.md` as the first message, in your own
   words if you like (that is part of the test), and nothing else: no paths beyond the two
   files, no method or pipeline names.
2. The skill should load from the description (note whether it did, or whether you had to name
   it). Then it should: save your words as `brief.md`; ask its four questions one at a time;
   say the plugin's `min_n_per_group` default aloud; show the echo-back in full and wait for yes;
   run `init`; present the confirm hold by the protocol (where and what, what the engine
   recorded, the two verdicts with the engine's effects, the ask). Reply "ok" once to see the
   protocol's refusal, then give a verdict word and a reason.
3. Then it runs. What you read after each call should be the `plain` sentence only. Judgment
   dispatch: three delegates, then one `run --responses` card. Possibly a flag hold on
   `judg.confidence_consistent`, presented by the protocol.
4. On completion it should relay `present` (three items: the comparison table, the group labels,
   the report), then the three-part report from `summary.md`, then offer `methods.md` and the
   coverage report by name.
5. Ask "what ran" at the end and check the commands and exit codes it prints against the trace:

        cd /data/lab/projects/2026-09_stringency-drive2_jrrose5/lane-e/<project> && stringency status --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['plain']); print(d['completed_steps'])"
        python3 -c "import sqlite3; c=sqlite3.connect('prov/run.db'); print(*c.execute('select via, operator_session_ref, operator_harness, reason from reviews'), sep='\n')"

Record, for the row in `backlog.md` (Measurements):

- [ ] approval cards, total and by kind (commands, transfers, other), and whether the standing
      grant from test 2, if any, was in force;
- [ ] your turns from the first message to `summary.md` shown;
- [ ] wall-clock from the first message to the first delivered file (the `deliver/` directory's
      mtime is the engine's timestamp);
- [ ] unrequested commands, JSON, exit codes, ids, or paths shown to you (target zero); list each;
- [ ] holds and how each was resolved (`via` from the reviews table, above);
- [ ] misreports against the trace (target zero): every `plain` line the agent relayed against
      `status --json` at the time, and its "what ran" answer against the commands in the transcript;
- [ ] whether the skill loaded from your phrasing without being named (a row for
      `skills/toy-engine.phrasings.results.md` in the toy method repository);
- [ ] anything the skill text got wrong: it chose, it inferred a verdict, it printed a path
      unasked, it said "still running", it rounded a number.

Send the agent's transcript (or the report) and the `deliver/` directory path to the next Lane
E session; it writes the row and the note.

## Results of D (owner, 2026-09-23, 12:48 to 13:03; project `lane-e/group-a-vs-b`; row in `backlog.md`)

What the skill did, against its own sections: loaded from the phrasing without being named
(three skills loaded: analyze, operator, declare); saved the brief verbatim; took the file, the
group column and the contrast from the message and said so; asked the replicate unit and the
deliverables (asks 2 and 3 merged into one confirmation turn, not one at a time); said the
plugin default aloud with the engine's value; showed the echo-back in full with a source table and
the exact closing sentence; drafted declarations identical to the reference except `id` and the
two `source` sentences; presented the confirm hold by the protocol (where and what, the record,
the two verdicts with the engine's effects, the ask); relayed `plain` after each stop; dispatched
three isolated delegates and filed them with one `run --responses`; relayed `present` whole, then
the three-part report from `summary.md`, then offered `methods.md` and the coverage report by
name. Person turns: 7. First message to first delivered file: 14 min 39 s. Misreports against the
trace: 0.

Engine defect found: K8. Both operator tickets (`02_summarize`, `05_report`) bind
`<step>/tmp:/tmp` and nothing creates the directory; the container fails to start (exit 255). The
agent ran the printed line six times, diagnosed it, and asked rather than creating the directory;
the owner instructed it to create the empty directory and run the line unchanged, and said so in
the transcript. The run then completed. About four minutes of the wall-clock and one person turn
belong to this stop.

Skill-text findings, for the template:

1. The echo-back's "Bound to" block carries three hashes, and the skill says to show the echo-back
   in full, so rule 1 and rule 4 collide. Either the template says to quote the echo-back without
   its "Bound to" block, or the engine's echo separates the person-facing text from the binding
   record. Also `type frame` and `type csv` in the source table, and the delivery path with the
   run id in the final report; the last is a plain rule 1 miss.
2. The agent read `START.md` and the reference `declarations/` in the parent directory before
   asking its questions. It still asked, and did not copy the reference `id`, but the next tester's
   run must not have the answers in the parent; they are now under `lane-e/reference/`.
3. The "ok" refusal was not exercised; the owner gave a verdict word and reason directly.
4. The trace's `stringency_version` reads `0.1.0.dev0` on the `0.2.0-sc0.1.8` install (the
   install predates the version bump); for Lane A.

Cards: the owner's count is still to be filled into the row.

## F. The toy run with the person away from the chat (Track 1h, plan section 6 step 4)

The measurement Track 1h exists for: a run that moves while nobody watches it, and results a
person finds a week later without the transcript. Same run as D, with the person leaving the
chat after the echo-back and returning on the notification. The run is the owner's, in the app,
until a lab member is available.

| item | where |
|---|---|
| engine | shared, `/data/lab/env/stringency/current` (`0.2.5-sc0.1.8` or later) |
| method | `stringency-toy-method@v0.1.5` (the skill names the page and the notifications) |
| notifications | `~/.config/stringency/notify.yml` on PROTSEQ for the account that runs the engine: `channels: [{kind: email, to: [<you>@emory.edu], from: <you>@emory.edu, smtp: {host: smtp.service.emory.edu, port: 25}}]` and `page_url` set to the page below |
| page | either the standing read-only page (`scripts/stringency-page.service`, tunnel `8766`) or your own `scripts/review-page.sh protseq` left running on the laptop; the URL with its token is `page_url` |
| parent directory | `/data/lab/projects/2026-09_stringency-drive2_jrrose5/lane-e/` (a project two levels under `/data/lab/projects` is on the standing page by itself; deeper ones need a `--project` line in the unit) |

Steps:

1. Before the session: write `notify.yml`; open the page URL in a browser and see the board;
   `STRINGENCY_NOTIFY` must not be `0` in the shell the app uses.
2. New Claude Science project. First message and the asks as in D, through the echo-back and
   your yes. When the skill runs `init` and the confirm hold is presented, do not answer it:
   close the app or leave. Note the time.
3. Wait for the email "<project>: the analysis paused". Note when it arrived. Open its link:
   on your own page it is the hold with its form, on the standing page the hold read-only with
   the two routes named. Record the verdict there (`via: web`) or with
   `stringency review --hold <id>` at a terminal in the project directory (`via: tty`), with your
   reason. Not in the chat.
4. Return to the chat and say the hold is resolved (the protocol waits for that and calls `run`
   again). Leave again.
5. Wait for "<project>: run completed" and "<project>: results delivered". Open the results
   link and, without the transcript, find the three items (the comparison table, the group
   labels, the report) and download one file. If a flag or item hold opens instead, step 3
   again.
6. Afterwards, from the project directory, the trace and the log:

        python3 -c "import sqlite3; c=sqlite3.connect('prov/run.db'); print(*c.execute('select h.hold_id, h.kind, h.created, r.ts, r.via, r.reason from holds h join reviews r on r.hold_id=h.hold_id order by h.created'), sep='\n')"
        cat .stringency/notify.log

Record, for the row in `backlog.md` (Measurements), besides the D items:

- [ ] time from hold opened to verdict recorded: `reviews.ts` minus `holds.created` for the
      confirm hold (and any flag), from the query above;
- [ ] for each of the three messages: whether it arrived, and `notify.log`'s time against
      `holds.created`, the run's `ended`, and the delivery's `ts`;
- [ ] whether the link opened the right hold and the right results without the transcript, and
      on which page (own or standing); whether the file download worked;
- [ ] the verdict's `via`;
- [ ] anything the message text got wrong: a number the engine did not print, a wrong step title,
      a missing link, a message on a ticket or a dispatch (there must be none);
- [ ] whether the agent, on your return, said anything beyond the protocol's wait.

## E. Rollback and clean-up

Nothing here changes the engine or the method. A test project under `lane-e/` that should not
count can be moved to `lane-e/superseded/` (the `board` skips that directory); do not delete it,
the trace is the record. The reference declarations in `lane-e/declarations/` stay.

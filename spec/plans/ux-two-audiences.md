# Two audiences: the analyst and the operator

Working note, not the spec. Roadmap Track 1 (`spec/plans/roadmap-2026-09.md`). Proposes changes to design
7.5, 10.4, 12.1, 14.1, and 17; the amendment texts are in section 8 and need the owner's approval
before build. Everything else here is DECISIONS-level or skill text.

## 1. The problem

The owner, 2026-09-14: much of what the AI operator sends is unintelligible to the person watching,
every command raises an approval card, holds need a route that is not a terminal, and the machinery
should sit behind per-analysis skills so that a non-computational lab member can run a pipeline.

The measurement that shapes the answer: the five-step toy took 26 approval cards on PROTSEQ. Two
were decisions a person had to make (the confirm hold; on BMESEQ also one flag). The other 24 were
mechanics: one `call_command` per file write, `next --json` after every ticket, three heredocs per
judgment dispatch, downloads. So the order of leverage is: make the engine do more per invocation;
make each remaining card read as a sentence; let the person decide without a terminal; wrap the
whole loop in a skill named for the analysis.

## 2. The principle

Two audiences. The analyst (owner, reviewer, lab member) sees four things: what is being analyzed
(the echo-back, in sentences), where it is (steps completed, by title), what came out
(deliverables, methods, coverage in plain words), and what needs them (each hold as one question
with the engine's options). The operator (the agent) sees the CLI: verbs, JSON, exit codes,
tickets, dispatch files. The operator's mechanics are in the trace and the transcript and are shown
to the analyst on request ("what exactly ran"). Hiding mechanics from the chat never hides them from
the trace; Commandment 2 is unchanged.

Rules that survive, verbatim from where they already live:

- 14.2: the hold message names the hold, the role, and the one command, and suggests no
  alternative. A skill may translate a hold into a sentence; it may not add options the engine did
  not list.
- Declare: the skill translates, it does not decide. The analysis skill asks the same questions in
  lay words.
- Review: the display states what fired and what each verdict does; it does not recommend. The
  chat presentation quotes `verdicts[].effect` from `review --json` and adds no ranking.
- Operator rule 1: the agent never gives a verdict. A relayed verdict follows an explicit verdict
  word and a reason from the person.
- Commandment 6: every number the person reads comes from an engine output (`echo.md`,
  `run --json`, `status --json`, `coverage.json`, `index.json`, delivered tables). The model
  quotes; it does not compute, round, or aggregate. Agent prose that interprets results is
  labelled as the assistant's reading and never enters `deliver/`.

## 3. Fewer, plainer cards

### 3.1 All-engine pipelines (method repo and skill text, no engine change)

`runner: engine` on every containerised step means one `stringency run` executes everything until
exit 10 or 20. Operator-run steps are for what the engine cannot execute (Nextflow), not a
default. Write this into `templates/method-repo/README.md`. The bulk RNA-seq pipeline is
all-engine except its alignment step.

### 3.2 Engine flags (DECISIONS-level, additive)

Built 2026-09-15 (Lane A step 1, engine commit named "Lane A step 1") except
`declare --check --print-hashes`, which stays open in `backlog.md`. `next --json` and `run --json`
also carry `title` beside `job_spec` and `dispatch_dir`.

| change | where | note |
|---|---|---|
| `job_spec.operator_line` | `operator_exec/tickets.py` | exec, evidence commands, and submit joined by `&&`; the operator runs one string; schema stays `stringency.job_spec/1` with one added key |
| `run --responses <file|->` | `cli/verb_run.py`, `runloop.py` | one JSON document `{"step_id", "responses": [...]}` written to `resp_N.json` in the dispatch directory in order, then the loop continues; exit 16 if the step is not dispatching or the count differs from `manifest.json`; the 10.2 file contract and nonce check are unchanged |
| `run --deliver` | `cli/verb_run.py` | deliver in the same invocation on completion |
| `steps[].title` | `pipelines.py`, lint warning when a pipeline has a `skills/` entry and no titles | plain phrase per step ("Filter low-count genes") |
| `plain` on `run --json` and `status --json` | `runloop.py` or a small `plain.py` | one or two engine-rendered sentences from titles and statuses ("Completed: Filter low-count genes, Summarize groups. Stopped: three judgments requested for Label groups."); golden test per `Next.kind` |
| `--attest` requires `STRINGENCY_SESSION_REF` | `review.py` | exit 16 otherwise, so a relayed verdict always names the session |
| `reviews.operator_harness` | migration 0004 | additive column, filled from `STRINGENCY_OPERATOR` |
| `declare --check --print-hashes` | `cli/verb_declare.py` | prints blake3 for items lacking one and exits 15 naming the field, so the skill fills hashes from engine output rather than its own Python |

`completed_steps` on `run --json` is done (Track 0). No new verb: `run` already is the loop
(14.1), and the two flags cover what an `operate` verb would add.

### 3.3 The `intent=` string is a sentence (skill text)

The card shows the intent. Fixed table in the operator skill and `templates/brief.md.j2`; the
intent names the project by directory name and the step by title, never a verb, exit code, or path:

| moment | intent |
|---|---|
| probe | Check that the analysis engine and its software image are ready on {provider}. |
| declare check | Check the analysis plan for {project} against the data before anything is created. |
| init | Create the {project} analysis project and show you what it will do. |
| run | Run the next analysis steps of {project} until something needs you. |
| operator line | Run the {step title} step of {project} in its container and hand the results back. |
| run --responses | Record the three independent judgments for {step title} and continue {project}. |
| review --attest | Record your decision on the {project} question, in your words, under your name. |
| deliver | Collect the finished results, methods text, and coverage report for {project}. |

### 3.4 Two things to test in a session, not assume

1. Data roots: does a delegate's download under a provider data root raise a card (the PROTSEQ
   count included three request downloads); can the root be `/data/lab/projects`.
2. Standing grants: does the card for `call_command` offer an "always allow" scope (provider,
   prefix, session); if so, grant `stringency` commands and re-count.

Record both in `integrations/claude-science/README.md` and `spec/plans/backlog.md` (measurements).

### 3.5 Card estimate, all-engine five-step pipeline with one dispatch

| card | today (toy-engine) | after |
|---|---|---|
| probe | 1 | 1, optional on a repeat project |
| declare phase | about 6 | 3 (plugins list; one write of four files; check) |
| init | 1 | 1 |
| confirm verdict | 0 at a terminal | 1 relayed, 0 on the review page |
| run to first stop | 1 | 1 |
| two operator-run steps | about 10 | 0 |
| dispatch (3 downloads, 3 writes, run) | 7 | 1 (`run --responses`) |
| deliver and downloads | 4 | 1, or 0 with `--deliver` |
| total | 26 | 8 or 9 relayed; 7 or 8 with the page |

Each flag hold adds one card (page) or two (relayed). Each operator-run step adds two.

## 4. Analysis skills as entry points

One skill per pipeline, `stringency-analyze-<pipeline>`, the person-facing script. The two engine
skills stay as the operator's reference; the analysis skill carries a compact mechanics appendix
and names the operator skill as the authority when they disagree.

Files:

- `integrations/claude-science/templates/analyze-skill.md.j2` (engine repo, domain-agnostic).
- `integrations/claude-science/render_skill.py` (or `render_brief.py --skill`): input
  `skills/<pipeline>.yml` in the method repo; output `skills/stringency-analyze-<pipeline>/SKILL.md`
  committed to the method repo (versioned with the method, linted there).
- `templates/method-repo/skills/README.md` and `skills/example.yml`.
- `skills/<pipeline>.yml` fields: `pipeline`, `method` (url@tag), `plugin`, `question`, `title`,
  `phrasings` (positive and negative), `steps` (id to title), `deliverables` (name to one
  sentence), `asks` (the declare questions this pipeline always needs, in lay words), and
  `defaults_to_say` (plugin defaults the skill must name aloud).
- `integrations/claude-science/publish-skills.md`: the one repl cell that publishes the engine
  skills and every analysis skill from the method repo path.

Description text routes casual phrasing and excludes neighbours. For bulk RNA-seq: load when the
person wants to analyze, process, run, or compare bulk RNA-seq data, mentions counts, fastq,
differential expression, treated versus control, or asks what changed between groups; do not load
for single-cell or spatial data, or for questions about how a finished analysis was done.

Body rules, each testable against a transcript:

1. Sentences only. No command, JSON, exit code, ticket id, hold id, or file path unless asked; then
   verbatim.
2. Every number quoted from an engine output just read. Never add, average, or round.
3. Translate, do not decide: the declare rules apply; ask the `asks` one at a time.
4. Show the echo-back in full: "This is the engine's reading of your experiment. If it is right,
   say yes and the project is created; if anything is wrong, tell me what." Wait.
5. Progress names steps by title and says only what `completed_steps` or `plain` says. Never report
   a step as done, skipped, or satisfied otherwise.
6. On a hold, follow the protocol in section 5 exactly. Never choose. Never look for another way
   past the stop.
7. On completion, deliver, then report in three parts from `summary.md`: what was analyzed, what
   was decided, what was delivered. Offer `methods.md` and the coverage report; do not paste.
8. Interpretation begins "This paragraph is my reading of the delivered tables, not an engine
   output" and cites table and row for every value. Saved as an artifact if asked; never written
   into the project directory.
9. Mechanics on request: "what ran", "show me the commands", "why did it stop" print commands,
   exit codes, and the hold message verbatim.

Test set: `skills/<pipeline>.phrasings.yml`, twenty positives and ten negatives with the intended
outcome (`analyze`, `declare-only`, `operator-only`, `none`); run by hand per revision until a
skill evaluation tool is confirmed in Claude Science; results in
`skills/<pipeline>.phrasings.results.md`. First instance: `stringency-analyze-toy-compare`, before
any real plugin exists.

## 5. Holds without a terminal

### 5.1 Relayed path (skill text, plus the two engine tightenings in 3.2)

When the engine stops with a hold, the operator reads `stringency review --hold <id> --json` (or
the packet file the message names) and says, in this order and nothing else:

1. Where and what: "The analysis paused at {step title}. The engine is asking: {for a flag, 'is
   this acceptable: ' plus the predicate's reason verbatim; for a confirm, 'does this reading of
   your experiment match'; for an item hold, 'which of these calls for {item} should stand'}."
2. The record: the packet's reason and evidence lines verbatim under "What the engine recorded";
   for item holds, each replicate's call, confidence, and rationale verbatim. No summary, no
   reordering.
3. The options: every entry of `verdicts`, as "{verdict}: {effect}", verbatim, in the engine's
   order. Nothing added.
4. The ask: "Which do you choose, and why? I will not choose for you. Your decision and your reason
   are recorded under your name in the project's record."

Then wait. Accept only a reply containing one listed verdict word and a reason. "Ok", "fine", "go
ahead" get: "To record this I need one of {verdicts} and your reason in your own words." No verdict
is inferred from tone. Item holds: accept needs the replicate number the person names; override
passes the person's label through unchanged.

Then one command: `stringency review --verdict {v} --hold {id} --reason "{their words}"
[--replicate n | --correction '{"label": ...}'] --attest`, with `STRINGENCY_SESSION_REF` set.
Report the engine's reply in one sentence. On exit 16 (strict profile refuses relayed review),
name the two routes the engine allows: the review page, or `stringency review --hold {id}` at a
terminal in the project directory. Call `run` again only after a verdict was recorded. The operator
never runs `review` without a verdict word and a reason from the conversation, and never starts
`review --serve`.

### 5.2 The review page (backlog A5, review-ux layer 3)

Verb: `stringency review --serve [--port 8765] [--bind 127.0.0.1] [--project <path>]...
[--projects <dir>]`. Flags on `review`, no new verb. `--projects <dir>` lists every child to depth
two that holds a `stringency.yml`.

Implementation `src/stringency/review_serve.py`: stdlib `ThreadingHTTPServer`, jinja2 string
templates beside `PACKET_HTML`, inline CSS, no JavaScript. Routes: `GET /?t=<token>` lists open
holds across projects (project, step title, kind, item, waits on, age); `GET /p/<i>/hold/<id>`
renders `review_render.render(project, hold).text` in the packet's block and a form: verdict
radios from `verdicts_for`, reason (required where `record_review` requires it), replicate select
for item holds, correction from the module's vocabulary when it has one; `POST` verifies the token
and calls `record_review(..., via_override="web")`; `RefusedError` renders as 403 with the engine's
message, `ConfigError` as 400 with the form re-shown. Identity is the OS user of the server process,
checked by `record_review` as for `tty`. A random token (`secrets.token_urlsafe`) is printed once at
start and required on every request. Loopback by default.

Who starts it: the reviewer, under their own account, through a tunnel:
`scripts/review-page.sh <ssh-alias> [<projects dir>]` runs `ssh -L 8765:127.0.0.1:8765 <alias>
'stringency review --serve --projects /data/lab/projects'` and opens the printed URL. Never the
agent (in mode B its commands run as the reviewer's user, so a server it started would be the
relayed path with a better front). Never one instance started by the owner for others: it would
record the owner as reviewer for verdicts other people clicked.

Tests (`tests/test_review_serve.py`): list; 403 without token; accept with reason records
`via = web` and resolves the hold; a stranger (monkeypatched `current_user`) is 403 and writes
nothing; replicate accept on an item hold sets `source: accepted`; override outside the vocabulary
re-renders with the engine's message; a strict-profile project accepts `web`; the HTML has no
`<script`.

## 6. Progress and results for a lay reader

- `plain` (3.2) is the sentence the skill relays; the skill composes no progress prose from codes.
- `deliver/<run>/summary.md`, engine-rendered (`src/stringency/summary.py`, golden
  `tests/golden/summary_toy_engine.md`), sections: what was analyzed (the echo text); what ran
  (steps by title, parameters that differed from defaults, "at defaults" otherwise); what was
  checked and decided (from coverage data: checks evaluated, which flagged, reviewer, verdict, via,
  reason quoted); judgments (items, replicates, agreement, reviews); what you received (each file
  with the module's output description or its name); not checked (the coverage report's closing
  line). No adjectives, no interpretation. Engine-rendered because it is the one page the lay
  reader reads and the coverage report's argument ("manufactured confidence is worse than no
  tool") applies to it exactly.
- `methods.md` and `coverage.md` stay for the paper and the auditor.
- Agent interpretation stays agent prose, labelled (rule 8), outside `deliver/`, keeping G2's line.

## 7. Several users on PROTSEQ

- Engine: shared install `umask 002; scripts/install.sh --prefix /data/lab/env/stringency`
  (group `bme-santangelo-lab`, setgid). `/usr/local` and `/opt` are root-owned. `current` moves
  when the next version is installed; every run records the engine version.
- PATH: one line in `~/.profile` per user; `call_command(..., login_shell=True)` inherits it.
  `render_brief.py --engine-bin /data/lab/env/stringency/current/bin` is the default for this host.
- Images: `/data/lab/env/images/<name>-<version>.sif` and `MANIFEST.md` (name, version, sha256,
  source definition, build date). Method manifests name this path; BMESEQ gets it by symlink (design
  10.3: same path on every machine). The toy's `/home/jrrose5/envs/toy-py.sif` moves at its next tag.
- Claude Science: one instance per person, their own SSH identity, so `call_command` runs as their
  AD user and `roles`, `via: tty`, `via: web` are per person with no engine change. Per instance,
  once: provider `protseq`, data root `/data/lab/projects`, the publish cell.
- Roles: the analysis skill passes `--owner $(id -un) --reviewer $(id -un)` unless the brief names a
  reviewer.
- A new member, once (`integrations/claude-science/onboarding.md`): SSH alias set up by a
  computational member; the PATH line; provider, data root, publish cell in their instance;
  optionally `review-page.sh` on their laptop; a two-paragraph "what to expect".

## 8. Amendment texts (approved by the owner 2026-09-15, all five as written; applied to the design the same day, the 17 row removal deferred until the page is built)

**7.5, add after the `relayed` paragraph.** "A third value, `web`, means the verdict was entered
through a form served by `stringency review --serve`, a process the reviewer started under their
own account, protected by a per-start token and reachable on loopback or through a tunnel. It proves
which account's process recorded the verdict, as `tty` does, and nothing more: an agent with shell
access as that user could start the server, read the token, and post. That is the boundary `tty`
rests on as well, which is why profiles treat `web` like `tty`, strict included, and why the trace
records `via` at all. The speed bump is the account, not the form. Relayed reviews must carry the
operator's session reference; `--attest` without one is refused."

**10.4, add.** "Skills are of two kinds. The two engine skills, `stringency-declare` and
`stringency-operator`, are the operator's reference and live in the engine repository. One analysis
skill per pipeline, rendered from the engine's template and the method repository's
`skills/<pipeline>.yml`, lives in the method repository and is what a person loads by describing
their experiment; it presents intent, progress, results, and holds in sentences and shows the CLI
only on request. Both kinds set the `STRINGENCY_OPERATOR*` variables and neither resolves a hold."

**12.1, add.** "`deliver` also writes `summary.md`: the engine's plain rendering of the run for a
reader who will not open the trace: what was analyzed, what ran, what was checked and who decided
what, what was delivered, what was not checked. Every sentence is filled from the trace; the file
contains no interpretation."

**14.1.** `review` row gains `--serve [--port] [--bind] [--project <path>]... [--projects <dir>]`
(reads holds, writes reviews with `via: web`). `run` row gains `--responses <file|->` and
`--deliver`.

**17.** Remove the review-page row once built.

## 9. Order and measurement

1. This note and the amendment texts for approval. 2. Engine flags (3.2) and the skill text that
uses them (3.3, 5.1) in one session; 3. the two session tests (3.4) on PROTSEQ; 4. the analysis
skill template and the toy instance; 5. `summary.md` and the review page after approval, in
parallel; 6. PROTSEQ shared deployment and onboarding; 7. the toy re-run through the analysis
skill by someone other than the owner.

Measure on the toy before and after each step, one row per run in `spec/plans/backlog.md` (measurements):
approval cards; the person's turns from first message to delivered result; wall-clock to first
delivered file; unrequested commands, JSON, exit codes, or ids shown (target zero); holds and how
each was resolved; operator misreports against the trace (target zero). Baseline: 26 cards,
PROTSEQ, 2026-09-14.

Status 2026-09-23: steps 1 and 2 done 2026-09-15 (17 cards on the toy, `backlog.md`
measurements); step 5 done (`summary.md` 2026-09-15; the review page 2026-09-23, roadmap Lane A
step 3, `src/stringency/review_serve.py`, `scripts/review-page.sh`); step 6 done 2026-09-23
(shared engine at `/data/lab/env/stringency`, `integrations/claude-science/onboarding.md`,
`publish-skills.md`, `hosts/protseq-lab.md`); steps 3, 4 and 7 are Lane E's (see its notes). Section 6 gained a surface this
note did not plan: `board` and `present` with method delivery skills, design 14.4
(`notes/2026-09-18-1830-board-and-present.md`), built because the owner wanted progress and
results in the session rather than narrated from tool output.

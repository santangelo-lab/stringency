# Lane E: analysis skill template, toy instance, session tests, first measured run

Session 2026-09-23 11:50 to 13:55 on PROTSEQ, branch `lane-e` (worktree
`~/mytools/stringency/stringency-lane-e` from `origin/main` at `5fbcc65`), in parallel with a
Lane A session on `lane-c-directory-inputs`. Brief: `~/mytools/stringency/brief-lane-e.md`.

## Goal

Track 1 of the roadmap, the parts not yet built: the analysis skill template and renderer (1d),
the first instance on the toy method (`stringency-analyze-toy-compare` on `toy-engine`), the
two Claude Science session tests as a checklist the owner runs (1g, UX note 3.4), the project
directory for the measured toy re-run, the publish note row, and the plan status text. Nothing
under `src/stringency/` changes.

## Done

- `integrations/claude-science/templates/analyze-skill.md.j2`: description routed from the
  method's positive and negative phrasings; the two-audiences preamble; the nine body rules of UX
  note section 4 verbatim; sections 1 to 7 (engine and identity; the asks one at a time and the
  plugin defaults said aloud; declare, echo-back, yes, `init`, confirm hold by the protocol; run
  and `plain`; the hold protocol as section 5, copied from the operator skill's section 6 so rule
  6's "section 5" reads right; `present` then the three-part report from `summary.md`;
  interpretation labelled, mechanics on request); a compact mechanics appendix that names the
  operator skill as the authority on conflict. The review page appears only as a route "when it
  is available on this host".
- `integrations/claude-science/render_skill.py` (stdlib, jinja2, pyyaml): `--check` validates the
  fields (unknown keys refused; `method` as `url@tag`; slug `name`) and cross-checks step ids and
  order, titles, the question against `answers`, and deliverable names against module outputs
  when the method repository has pipelines; reads the delivery skill's `after_delivery` titles
  into the skill; `--write` puts the output at `skills/stringency-analyze-<name>/SKILL.md`.
  `templates/method-repo/skills/README.md` and `example.analyze.yml` give a new method repo the
  shape. `tests/test_render_skill.py`: thirteen tests, the rules and the protocol asserted
  verbatim against the UX note and the operator skill, the drift cases `--check` must catch.
  Commit `ed03758`.
- Toy method `v0.1.4` (commit `04d96a7`, pushed to BMESEQ as `master` and fast-forwarded there,
  as the 2026-09-15 push was): `skills/toy-engine.yml` (delivery skill: comparison table, group
  labels, report; `hold_view` for the two judgment predicates likely to flag), `toy-engine.analyze.yml`,
  the rendered `stringency-analyze-toy-compare/SKILL.md`, `toy-engine.phrasings.yml` (20 and 10),
  `skills/README.md`, a session note. `present --skills-dir` on the 2026-09-15 `track1b/toy-compare`
  run rendered the three items; `lint .` clean (the one pre-existing warning: no planted control).
- `integrations/claude-science/hosts/protseq-session-tests.md`: the two 3.4 tests (a download under
  `/data/lab/projects`; a standing grant on the `call_command` card) and the measured toy run
  through the analysis skill, with what to record for the backlog row.
- `/data/lab/projects/2026-09_stringency-drive2_jrrose5/lane-e/`: `declarations/` (two inputs, the
  table and the manifest; A versus B; three deliverables) passing `declare --check` against
  `toy-engine@v0.1.4` with the shared engine (7 init predicates, none fired), and `START.md` with
  the first message in lay words.
- `publish-skills.md` analysis-skill row and the toy instance row; README file table and the 3.4
  paragraph; roadmap 1d and 1g status and the Lane E paragraph; UX note section 9 status; backlog
  Measurements pointer; one DECISIONS line (`.analyze.yml`, `name`).

- Session tests B and C run by the owner the same day, results in
  `hosts/protseq-session-tests.md` ("Results of B and C"), the README 3.4 paragraph and the
  backlog: the download card is conversation-scoped per directory and names the app's scratch
  directory as the only path read without asking; the `call_command` card offers once, this
  conversation, this project, or global, and a project grant covered every later `stringency`
  command with no card. The toy analysis skill is published on the owner's instance.

- Section D run started by the owner 2026-09-23 12:48 (`lane-e/group-a-vs-b`, engine `0.2.0-sc0.1.8`):
  the skill loaded from the phrasing; brief saved verbatim; asked only the replicate unit and the
  deliverables (the rest taken from the message and said so); default said aloud (2); echo-back in
  full with a source table; drafted declarations identical to the reference except `id` and the two
  `source` sentences; confirm hold presented by the protocol and accepted relayed. Stopped at the
  first operator ticket (`02_summarize`): engine defect K8 (the ticket binds `<step>/tmp` that
  nothing creates). The agent ran the line six times, diagnosed it, and asked rather than creating
  the directory; that is the skill working as written. Findings for the skill text: the echo-back
  quote carries the three "Bound to" hashes (rule 1 against rule 4; fix in the template or in the
  engine's echo); asks 2 and 3 were merged into one confirmation; the agent read `START.md` and the
  reference `declarations/` in the parent directory before asking.
- Section D run completed 13:03 after the owner instructed the two `mkdir`s; delivered
  `lane-e/group-a-vs-b/deliver/01M37K0V74CFHWGDQHE22QKDEX`. Row written in `backlog.md`
  Measurements (cards left for the owner), results and skill-text findings in
  `hosts/protseq-session-tests.md` "Results of D"; reference declarations and `START.md` moved
  to `lane-e/reference/`. Phrasings result row in the toy method repo.

- `spec/method-skills.md` at the owner's request: the two skill files per pipeline in one page
  (schemas by reference to 10.4 and 14.4, the `.analyze.yml` fields, writing the asks, render and
  check, publish, the routing test, what is measured). Design 10.4 corrected to name
  `.analyze.yml`; 14.4 gains one paragraph pointing at the page; `spec/README.md` row; the
  method-repo template's layout block lists `skills/`.

- Merged to `main` by the owner: PR #1 (`8fa805e`, everything above) and PR #7 (`a2c592a`, the
  spec page). Each merge was preceded by merging `main` into `lane-e`; conflicts were only the
  appended DECISIONS lines and the index, kept in full. The CI failure on `8fa805e` was one blank
  line in `src/stringency/review_render.py` from Lane A's item 6 commit, fixed by their PR #5.
- K8 was fixed by Lane A the same afternoon (PR #5, `write_job_file` creates `<step dir>/tmp` at
  ticket time, with a test); the row in the backlog is marked done. Not yet tagged and
  reinstalled at the time of writing.

## Learned

- The toy method's `v0.1.3` had already been pushed to BMESEQ before this session, contrary to
  the 2026-09-15 note; the remote is a non-bare checkout on `main`, so a push goes to `master`
  and is fast-forwarded there.
- `present` renders a `json_table` whose `path` names a dict as one row with a column per key,
  which suits the toy's `group_labels.json` (`labels: {A: abundant, ...}`).
- With `trim_blocks` on, every Jinja block tag in the template needs an explicit blank line after
  it where a paragraph follows, or lists run into the next paragraph.
- The measured run's 3.4 questions cannot be answered from a terminal: cards exist only in the
  app. Hence the checklist rather than a result.

## Altered

- The analyze yml has one field the UX note did not list: optional `name`, the skill slug when
  it differs from the pipeline name (the brief fixes the instance name as
  `stringency-analyze-toy-compare` on pipeline `toy-engine`). Recorded in DECISIONS.
- The acceptance test's target moved from Track 2 session 10 (Lane B dormant) to the toy, then
  a spatial pipeline once Lane F has one; no bulk skill was started.

## Open

Pick-up point for the next Lane E session, in order:

1. Template fixes from the run (`integrations/claude-science/templates/analyze-skill.md.j2`):
   quote the echo-back without its "Bound to" block (or ask Lane A to split the engine's echo into
   the person-facing text and the binding record); name the delivery by its files, never by its
   path; keep the asks one at a time. Re-render the toy skill (`render_skill.py --write`), tag the
   toy method `v0.1.5`, republish per person.
2. The acceptance test: the toy run by someone other than the owner, once K8 is tagged and
   installed and the method is at a location the tester can read. The toy method's path is under
   `/home/jrrose5` (mode 700) and its remote is BMESEQ; the owner chooses a GitHub remote or a
   clone under `/data/lab/env/`. The reference declarations and first message are under
   `lane-e/reference/`, out of the parent the agent reads.
3. From the owner: the approval-card count for the 2026-09-23 row, by kind, and whether a data
   root for `protseq` was set when the download card named the app's scratch directory.
4. The thirty-phrasing routing set, run by hand; low value until a second analysis skill exists.
5. `publish-skills.md`: the toy skill's publish date is recorded; add each person's as they publish.
6. Then close the lane in the roadmap as Lanes C and D were closed: skills become a step of every
   method build (the xenium `.analyze.yml` files are Lane F's; bulk and NanoString follow their
   plugins), not a lane of their own.

## Verify

    cd ~/mytools/stringency/stringency-lane-e
    uv run pytest tests/test_render_skill.py && uv run pytest && uv run ruff check . && uv run ruff format --check .
    cd ~/mytools/stringency/stringency-toy-method && /data/lab/env/stringency/current/bin/stringency lint .

# Plans consolidated, decision points designed, OmicsBench assessed (2026-10-21)

## Goal

Three things in one session. Read LatchBio's OmicsBench v1 failure taxonomy against the engine
and say where it already answers each mode and where not (the owner: "a big selling point").
Think through the owner's biggest gap in it, a threshold picked without testing and accepted
blind. Then, on the owner's ask, replace the roadmap, the backlog and the open sections of nine
plan documents with one work list, because "something is going to get lost between them all".

## Done

- `spec/plans/omicsbench-assessment.md`: the seventeen failure modes counted from the report
  (4,556 failing runs) and classified as agent-behaviour or biological; a side-by-side of each
  behaviour mode against engine 0.2.27; seven borrowings filed as rows L54 to L60 (the seven
  designed-but-unbuilt downstream predicates; cited reasons on `propose`; evidence a judge must
  weigh; report prose against cited cells; structured claims; the fork sweep at delivery;
  `answer --cannot`); the biological modes; candidate README words.
- `spec/plans/decision-points.md`, from the owner's reading: a `decision:` block beside a
  parameter's range (`evidence` required, or `none` with `because:`; `hold: always` folds L9),
  lint erroring only on the silent case, the default hold view, the citation and considered-set
  slots on `propose` with `param.agent_proposed@2` and `param.reason_unmatched@1` (L55, first to
  build), the `presented` event (L62), and the menu a method author chooses per step: sweep
  (L63), rule (L64, lowest), judged (L65), sensitivity (L66). Not pursued: the default beside
  the proposal as a verdict (bigger than it looks: override is item-only and pipeline mode has no
  person-sourced value); acceptance latency printed (patronising).
- `spec/plans/PLAN.md` replaces `roadmap-2026-10.md` and `backlog.md`: the state, next in
  order, every open row by area, and one table of everything that waits on the owner. Rows
  L67 to L81 are the open items that lived only inside plan documents (confirm-once b, c, e;
  judge-sources S3 to S6; the console's second cut and the open project's questions page;
  open mode's O5 and O6; the acceptance run; CI's institutional list). L82 to L85 are the five
  proposals of the judgment literature check written in the parallel session this morning.
  Ids never reused; done rows still go to `archive/backlog-done.md`.
- `spec/plans/measurements.md` holds the measurement tables (and the open-mode table's header,
  no row yet). Archived: `roadmap-2026-10.md`, `open_mode_plan.md`, `bulkrna-plan.md`,
  `trace-integrity-review-2026-10-20.md`, each with a header naming its successor.
  `ux-two-audiences.md` moved to `spec/`: sections 4 and 5.1 are rules a test reads, not a
  plan. Every staying plan's Status line now names its rows and says it holds no list.
- Every live path repointed (`CLAUDE.md`, `README.md`, `spec/README.md` rewritten,
  `spec/stringency-design.md` reading order, `spec/method-skills.md`, the docs, the
  claude-science README and renderer, the method-repo template, the open-mode tests' docstrings,
  `tests/test_render_skill.py`'s `UX_NOTE` path). DECISIONS: one entry.

## Learned

- Nothing today guarantees the operator tested a threshold before proposing it: the reason is
  free text no predicate reads, and the record holds "accept all 16". The two halves pull
  against each other (more checking, more holds, less reading per hold), so every mechanism
  chosen makes a hold richer, not more numerous.
- A flag hold takes accept or reject only; `param_source: person` is set by open mode's `call`
  alone. Offering the default at a parameter hold is a 7.1 and 7.3 change, which is why it was
  declined for now.
- `present` writes nothing to the trace; `tests/test_render_skill.py` reads
  `ux-two-audiences.md` from disk, so that file is normative whatever directory it sits in.
- A5 (`review --serve`, `via: web`) appears built since 0.2.8; the row was never closed and the
  record does not say what remains. Filed as a question for the owner rather than closed.
- OmicsBench: the harness barely moved pass rates but shifted behaviour rates; the two largest
  behaviour modes (arbitrary ambiguity resolution, silent statistical choice) are the ones the
  decision block targets.

## Altered

- The planning convention: one work list (`PLAN.md`), reasoning documents with no lists of
  their own, archive on the last row's close. Lanes A to T are history in the archived roadmap;
  areas replace them. CLAUDE.md's pointer changed accordingly.
- `spec/ux-two-audiences.md` is a spec-level rules page, not a plan.

## Open

- The suite runs here now (after the commit): `brew install uv` (0.12.11), `uv sync --all-groups`
  fetched a managed Python 3.14.7 (the machine had only 3.9; the project needs 3.12 or later)
  and built `.venv`. Green: every test passes, four skipped (apptainer and the singlecell
  plugin, as before; two Linux-only tests now marked `skipif` where `/proc` is absent:
  `test_a_reused_pid_is_not_the_engine`, `test_filesystem_type_returns_something_for_tmp`).
  Ruff, the format check, mypy and the no-biology check clean. One false failure on the way:
  `--basetemp` under a path whose last segment ends in twelve hex characters makes the
  open-delivery golden's `<HASH12>` normaliser rewrite the upstream path before it is replaced;
  use pytest's default temporary directory.
- The consolidation is committed as `df2b287` with the parallel session's note
  (`2026-10-21-1300-judgment-replicates-evidence.md`); the two test skips and this note's
  update are the second commit.
- Next: the owner's jobs in `PLAN.md`'s waiting table, then L61 and L55 (decision points, first
  cut), then L54.

## Verify

    uv run pytest tests/test_render_skill.py tests/test_open_mode.py -q
    uv run ruff check tests integrations && uv run ruff format --check tests integrations
    ls spec/plans   # PLAN.md measurements.md decision-points.md + seven reasoning documents + mockups
    grep -rn "spec/plans/backlog\|plans/roadmap-2026-10\|spec/plans/open_mode_plan\|spec/plans/ux-two" --include='*.md' --include='*.py' . | grep -v "^./notes/\|^./spec/archive/\|^./spec/DECISIONS"   # nothing

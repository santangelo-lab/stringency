# 2026-10-19: the report replaces `deliver --answer`

## Goal

The owner's second drive (2026-10-19, `toy-compare-2` / `toy-compare-2-open`) showed that
answers reach the person in the chat before anything reaches disk, so a session ending after
"that's what I wanted" leaves `deliver/` empty. Build the approved plan
(`~/.claude/plans/i-think-we-go-merry-wren.md`): every answer on disk as it is filed, a living
`report.md` that leads with the findings, a `finding` verb, and the operator's words for it.

## Done

- Migration 0006 `findings` (append-only; `Store.APPEND_ONLY`; `spec/trace-schema.md`;
  `tests/test_store.py`), `findings.py` (`current`, `mark`).
- `report.py`: `write_open_delivery` (every admissible answer into `deliver/<run>/`, the cited
  files, `coverage.md`, `methods.md`, `index.json` with `report`, `written` and finding fields,
  `report.md`; deterministic, a `deliveries` row only on change; `is_final` once; atomic
  writes; stale names removed only when the previous index listed them) and `render_report`
  (findings in full through `present.answer_sections`, other questions in short, the two
  meaning sentences, the record). `deliver.py`: `deliver_gate` factored, the open branch calls
  the report, `--answer` refused; `answer_file_name(nth)`. `summary.py`: the open branch and
  its helpers removed (`NOT_CHECKED_OPEN` stays, its wording "answers marked as findings").
  `coverage.py`: "cited by findings".
- Verbs: `finding` (new, `cli/verb_finding.py`), `answer` writes the delivery after an
  admissible filing, `deliver` in open mode regenerates and reports `changed`. Readers:
  `present` (`answer_sections` factored out; `report` entry; "In the report as …";
  `present --answers` marks findings), `review_serve.served_files` (report and answer files),
  `plain`/`runloop` (findings counted), `readme` (finding column, "The report" section).
- `provenance.py`: `TRUSTED_MEANS`, `UNTESTED_MEANS`, `REPORT_SENTENCE`, `FINDINGS_SENTENCE`;
  the skill test pins 17 sentences across the operator skill, the template and the engine.
- Skills and docs: operator 10.2, 10.3, 10.6, 10.7 and the intent table; the analysis
  template's section 8 and appendix; the brief's phase 4; `docs/open-mode.md` "The report";
  the rehearsal doc; `spec/stringency-design.md`, `spec/plans/open_mode_plan.md` section 10,
  `spec/DECISIONS.md`. Toy method re-rendered for `v0.2.0-rc5`.
- Tests: `test_open_deliver.py` rewritten (golden `tests/golden/report_open.md`;
  `summary_open.md` removed), `test_open_mode.py`, `test_render_skill.py`.

## Learned

- The deliver test's "cells probe" (`input="x"`) had always been an admissible answer, not a
  blocked one as its comment said; with automatic delivery that showed up as a third file.
  It now carries a numeral no cell matches and is blocked, as intended.
- Answers in the index are ordered by question then filing order, so a question's second
  answer sits beside its first; the `-2` suffix is by filing order, never renamed.

## Altered

- `deliver --answer` is refused in open mode; `Delivery` gained `changed`; the open summary
  and its golden are gone; `index.json` of an open run has `report` and `written` in place of
  `summary` and `delivered`.
- Two open points from the plan, decided here: only a question's latest admissible answer is
  quoted under "Other questions" (earlier ones listed by file name); `finding` without
  `--reason` is allowed via `relayed`.

## Open

- Commit, tag the toy `v0.2.0-rc5`, push both `open-mode` branches, reinstall the open-mode
  prefix as `0.2.22-open-mode-o4`, republish the two skills; then the owner's `stringency
  deliver` in `toy-compare-2-open` writes its report, and a third drive tries the report flow.
- Merge of `open-mode` waits for the owner's review.

## Verify

`uv run pytest` (436 tests), `uv run ruff check .`, `uv run mypy`, `scripts/check_no_biology.sh`;
`tests/test_open_deliver.py` is the report's test, `tests/golden/report_open.md` the report.

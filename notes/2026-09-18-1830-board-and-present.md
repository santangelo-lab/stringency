# `stringency board` and `stringency present`: what the person sees

## Goal

The owner's ask after two days of Lyons CLP runs: the operator narrated tool output, ids and
"still running"; the person wanted to see the state of every project at a glance and, after each
delivery or at each hold, the tables that mean something. Two reading verbs, both plugin-free.

## Done

- `board <root> [--write] [--json]` (`src/stringency/board.py`, `cli/verb_board.py`): one row and
  one sentence per project under a directory (skips `superseded/`, `declarations/`): plan status,
  latest run and current step, open holds with who they wait on, latest delivery's files. Reads
  `stringency.yml` and the trace directly; loads no plugin, resolves nothing. `--write` rewrites
  `<root>/STATUS.md`; `init`, `run`, `propose`, `submit`, `review`, `deliver`, `abandon` call
  `refresh_if_present` before their report, so an existing board stays current; a failure there
  never fails the verb.
- `present [--run] [--hold] [--skills-dir] [--json]` (`src/stringency/present.py`,
  `cli/verb_present.py`): renders the method's delivery skill `skills/<pipeline>.yml` (design
  14.4): `after_delivery` items of kind `table` (csv/tsv), `json_table` (dotted `path`, a dict is
  one row), `jsonl` (one object per line; the judgment log), `text`, `file` (listed under "Files to
  send"); per-column `format` percent / int / `<n>f`; dict cells render `k=v; k=v`, lists `a, b`;
  `hold_view` items matched to the predicate that opened a flag hold; the confirm hold shows its
  echo-back; the two review commands are printed. Missing or malformed skill, missing source, or an
  unknown kind degrade to a note, never an error. `Site` (config + store + pipeline) replaces
  `Project` so no plugin is needed.
- Operator skill section 7 "What to show the person": relay `present` after every `deliver`,
  `present --hold` before asking for a review, point at `STATUS.md` between events.
- Design 14.1 rows, 14.4 subsection; DECISIONS entries; tests `tests/test_board_present.py`.
- Real check: `board /lab/projects/Lyons_CLP` lists the 14 projects with their deliveries;
  `present --skills-dir ~/github/stringency-xenium-method/skills` on `qc_0076581_Spleen` renders
  the method's five tables and the report file (the method's `skills/` landed at v0.3.2-rc2, after
  the projects' pinned clones, hence the override flag).

## Learned

- Reading verbs must not construct `Project`: it loads the plugin, which the dev venv (toy only)
  and a bare install lack. `board`/`present` read config, trace and pipeline file directly.
- Nested dict cells (`removed_by`) and the judgments log needed `jsonl` and compact dict rendering;
  both came from the method session's skill files rather than from the schema I first proposed.

## Open

- Wrap `echo.md` at 100 columns; `nano` users could not read it.
- A `--watch` or a `present` summary line at the top of `STATUS.md` for the newest change.
- `present --hold` for judgment holds could show `judgments.jsonl` beside the consensus by default
  when the method's `hold_view` names both; today it renders exactly what the skill lists.

## Verify

```bash
uv run pytest -q tests/test_board_present.py
uv run stringency board /lab/projects/Lyons_CLP | head -20
(cd /lab/projects/Lyons_CLP/qc_0076581_Spleen && stringency present --skills-dir ~/github/stringency-xenium-method/skills)
```

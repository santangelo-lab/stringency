# 2026-11-09 17:00: labels are not measurements (engine 0.2.41)

## Goal

The owner, from his Lyons Lung open-mode sessions: "fix the predicates catching the labels with
numerals in them somehow as a priority. It's coming up a lot." Domain counts in the domain sweep's
proposal, cluster ids and animal ids in reasons and answers were flagged as numbers matching no
cited cell.

## Done

- Read the trace, not the complaint. `upstream_lung-layers`: the `03_select_domains` proposal
  of 2026-11-06 opened `param.reason_unmatched` on `6, 6, 6, 4, 7, 7, 4, 11, 4`; every one is the
  `n_domains` key of a row the reason cited (`at 5`, `at 6`, `4 is the cleaner cut`, `0.8191 at
  11`); the owner's verdict on that hold reads "Engine bug. Numbered domains being mistook as
  numeric values". `upstream_lung-layers-open`: the `95_distance-to` call of 2026-11-09 opened it
  on `6, 6, 2` from a reason that said "cluster 6 in animal 6-2", the question's own words, with
  nothing cited. The answer side's flags in these projects were measurements the operator had
  not cited, apart from `10` (a cluster id) once.
- Cause: `param.reason_unmatched@2` compared the reason with the cited cells' values and the
  proposal's parameter values only (`cited_values`, `_numeral_problems`). L142's exemption
  classes (`ans.classify_numerals`) applied to answers alone, and knew nothing of a cited row's
  key, a considered value or an identifier.
- `param.reason_unmatched@3` reads the reason through `ans.classify_numerals`. Sources: the
  cited rows' keys (`row`), the key of every row of every cited table (`_table_keys`, the table
  read once at gate time), the parameter values with numerals inside strings (`cluster = 20`,
  `6,0,8,17`), `--considered`, the design's levels, and the question. `propose` records the
  question of an on-demand step (`call`, `exec`) in the rationale message as `question`
  (`steps._question_of`). The cited form of the reason now names the nearest class, as the
  answer's does; the evidence carries `not_checked`.
- `ans.numeral_unmatched@3`: three classes on both checks. `table`: the key of any row of a cited
  table, cited or not (`answers.Cited.table_values`). `considered`: a value the proposal
  considered. `id`: a numeral joined by `-` to a word character on either side (`6-2`,
  `24-1-Lung-A`, `ctrl-1`; `in_identifier`); `-0.64` after a space and `x = -2` are still
  numbers. The qualifier's `numerals not checked` lists them with the rest.
- Tests: `tests/test_numeral_labels.py` (the sweep proposal in miniature, passing with its
  labels and still failing on an uncited measurement; a reason with a measurement and no
  citation; a `call` naming the question's cluster and animal opens `param.agent_proposed`
  alone, and one more numeral opens `param.reason_unmatched` beside it; an answer naming
  `6-2`); `test_row_keys.py` gains the three classes and the identifier rule;
  `test_board_present.py` takes the new summary. Versions 0.2.41 in `pyproject.toml`,
  `__init__.py`, the golden methods text; `uv lock`.
- Docs: `spec/stringency-design.md` rows for both predicates; `spec/DECISIONS.md` 2026-11-09;
  PLAN L157 (done); the operator skill's section 9 and 10 sentences (engine 0.2.41).

## Learned

- The exempt numerals were always meant to be visible (L142); the change keeps that. What
  changed is which numerals count as labels. L142's test fixed `Cluster 8 is 36.68` citing
  only cluster 9's row as a must-fire; it now passes the numeral check when the table has a row
  for cluster 8. The numeral check never knew which row the sentence was about; it only knew
  that 8 matched nothing. Whether the right row was cited is the reviewer's reading.
- No bare label-word rule (`cluster <n>` for any n) was added. Every exempt numeral still
  traces to a row that exists, a level, a parameter, a considered value or the question, so the
  one case that still flags is a label of no row of any cited table that the question does not
  name either.
- `wait --job` at `--for` returns `running` with exit 10, the same code a held verb returns
  once it lands; the owner's operator stalled 25 minutes on that. Not fixed here (the exit codes
  are frozen, design 14.2); see Open.

## Altered

- The rationale message of a `call` or `exec` proposal with a reason gains a `question` field
  when the step was proposed for a question (its hash changes; earlier records are read as
  before, `question` empty).
- The reason of `param.reason_unmatched` in its cited form: `a numeral in the reason matches no
  cited cell: 0.088 (nearest: ...)` where it listed the numerals alone.

## Open

For the owner's word, from the same sessions, as PLAN rows L158 to L160 here and section 9 of the Xenium method's `PLAN.md`:

- L158: `wait --job` and exit 10 for both "still running" and "landed held" (skill section 5 already
  says to read `state`). A distinct code breaks the frozen list; the alternative is `wait --job`
  returning the verb's own JSON with `state: held` and exit 10 only when the verb exited 10,
  and `state: running` with exit 0 and `running: true` at the timeout. His call.
- L159: one `propose` opens two holds (`param.agent_proposed` and `param.reason_unmatched` in the
  same second): the operator skill's hold protocol reads one hold per stop. Either the engine
  folds the reason flag into the proposal hold's packet (one hold, two findings) or the skill
  says to read the queue, not the payload's first hold.
- L160: a person's file as a tool input: `call --in` takes `$inputs.<name>`, `$steps.<id>.<out>` or an
  artifact id, so a collaborator's gene-set table reaches `score-pathways`'s `custom_genesets`
  (declared, hashed, optional) only through an `exec` that writes it, which labels everything
  after it untested. An `inputs add <name> <path> --type <t> --source "<words>"` verb for an open
  project (hashed, recorded, bindable as `$inputs.<name>`) is the owner's "input tool".
- Xenium method PLAN section 9: open mode's skill answers a direct question by presenting options first; the owner wants the
  asked thing answered, options after, or on "what can we look at next". Skill text, not engine.

## Verify

    uv run pytest -q tests/test_numeral_labels.py tests/test_row_keys.py tests/test_open_answers.py
    uv run pytest -q            # the whole suite

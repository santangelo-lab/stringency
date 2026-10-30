# The second pilot's findings built: engine 0.2.35 and 0.2.36 (2026-10-29 night to 2026-10-30)

The owner ran the second open-mode pilot on the Lyons gut delivery on 2026-10-29 and relayed
every snag; the lead (Claude Fable 5.1, session 014pZtAN...) filed them as PLAN rows L130 to
L145 and the Xenium method's PLAN section 8, then built them overnight with seven Opus
delegates in engine worktrees (`stringency-wt-*` beside the checkout), each squash-merged onto
main with the full suite, ruff, mypy and the no-biology check green. The owner's decisions:
two tags; the composite row key `k1|k2` for every citation; the resource cap in the method's
`policy.yml`, overridable per run and set high. Nothing is pushed: `git push origin
release-0.2.35 v0.2.35 main` is the owner's.

## v0.2.35 (branch `release-0.2.35`, cut at 314e57b with the version bump)

- L130 (51e058f): `policy.yml` `resources: {max_cpus, max_memory_gb}`; `--cpus/--memory` on
  run, call, exec, controls run; a step's allocation is the override or the module's value, at
  most the cap, recorded with its source on the started event; `job.json` `resources`;
  STRINGENCY_CPUS, STRINGENCY_MEMORY_GB and the thread variables; apptainer cgroup limits where
  the host takes them (PROTSEQ does); lint flags scripts that read the host's core count.
- L135, L136 (19ffbbf): `tools list --method` lists the tools the open project will pin against
  an older delivery, with the pipeline's own inputs as `upstream_<name>` candidates that bind by
  name and an "offer" line per tool; deliverables may be `<step>.<output>`; `call` binds the
  latest step's copy of a twice-delivered output and records it; `open: {words_of:}` takes
  another pipeline's words, with a lint on two intros.
- L138, L142 (314e57b): a table's row key is the shortest unique prefix of its columns joined
  with `|` (or `outputs.<name>.key`, an additive note in DEVIATIONS for the owner); answers,
  proposals, present, the hold packet and judgment prompts use it; a miss gives `cite_help`.
  `ans.numeral_unmatched@2` exempts design levels, key values, the producing step's parameters,
  the question's numerals, years and counts of animals, punches and replicates, listed in a
  seventh qualifier field. The gut's villus answer, re-filed in a scratch copy, is admissible,
  70 of 70.

## v0.2.36 (main)

- L131, L133, L137 (e43c971): an open confirm carries its delivery as rows and the card
  branches on mode; every predicate hold carries question, rule with facts, scoped evidence
  (`scope: item`) and verdict meanings (`packets.SAYS`); override corrects the confidence on
  `judg.confidence_consistent`; hold tables add the columns a proposal names; lint checks view
  columns against outputs; the provenance line reads `rendered` step events.
- L141, L143, L144 (b5a004c): `present --answer --chat` puts the cited rows first, cut to the
  key columns and the cells the text's numerals are; `answer --figure` attaches a figure with
  its own label; `finding --order` / `--under` and `deliver --story` (refused on an uncited
  numeral) shape `report.md`; lint warns on open tools without an `answer_view`.
- L134, L132 (6103ac4): `present --step` renders a completed step of a held run and marks it
  `rendered`; hold payloads carry `console_url` from `page_url`; `--detach` and `wait --job`
  give a command-limited operator its loop; `judgments --dispatch --print` and `run
  --print-requests` put requests inline; views take `where:`; `--out` on run, deliver and
  present; open projects with nothing under way read "open, idle since"; `stringency archive`;
  the console names a plugin it cannot load.
- L139, L140 (da277a8): `ask --wants` and `call`/`exec --gives` recorded, shown under answers,
  counted in coverage by exact text; `not_for` in a tool's words; the near-miss form in the
  operator skill; an exec that draws trusted tables with a `figure_drawn` whose numbers all
  match is labelled "trusted data, drawn by session code"; migration 0007.
- L145 filed: `numeral_matches` has an absolute tolerance of 1e-12 on exponent-form numerals.

## Not built, by the delegates' own account

L132's idle-after-days policy and a folder-wide archive marker; L134's `--detach` on a
responses verb (none exists); L130's timeout enforcement (module timeouts were never
enforced); L144's story removal; the switch sentence and the methods paragraph still say
"trusted or untested" (the third label is new). The method's PLAN 8 rows say what the Xenium
method did with each (rc26 pending).

## Verify

`uv run pytest` (610 tests at the last merge), ruff, mypy, `scripts/check_no_biology.sh`; the
delegates' real-data checks live under `/lab/scratch/jrrose5/{cites,answers,packets,loop,resources}-*`.

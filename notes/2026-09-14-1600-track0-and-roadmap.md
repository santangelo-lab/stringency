# Track 0 and the roadmap after the Phase A exit

## Goal

Plan what follows the Phase A exit and do the small cleanup first: the owner's three concerns were
the section I backlog, a usable experience for non-computational lab members (fewer and plainer
approval cards, holds without a terminal, per-analysis skills), and the real datasets now on
PROTSEQ (bulk RNA-seq and Lyons CLP Xenium).

## Done

- Surveys (read-only): the spec's silence on usability and on application 2; the plugin protocol,
  method contract, and CLI surface; `mkendzel/plasmid_bulk_rna` and the PROTSEQ data inventory;
  `ROSC_MTA2` on BMESEQ (18 gated steps, conda, per-tissue copies, ROSC dataset). Findings are in
  the four notes below rather than repeated here.
- Roadmap approved by the owner: `spec/roadmap-2026-09.md`; detail per track in
  `spec/ux-two-audiences.md` (Track 1, with the amendment texts for 7.5, 10.4, 12.1, 14.1, 17 that
  need approval), `spec/bulkrna-plan.md` (Track 2, thirteen sessions, thirteen session-0
  decisions), `spec/app1-spatial-qc-plan.md` (Track 3: splitter determinism, coordinates as a
  manual input, split and QC modules, no IF module). CLAUDE.md lists them as working notes.
- Track 0 code, all green (`pytest`, ruff, format, mypy, no-biology): I6 `lint` accepts
  `<repo>@<tag>` (clone to a temporary directory); I8 `run --json` `completed_steps` and one human
  line "completed by the engine: ..."; I10 echo pluralises the unit; I3 `Plugin.defaults`, shown
  by `plugins list` and `--json`, toy publishes `min_n_per_group: 2` (toy plugin 0.1.2); I7
  `render_brief.py --image` (repeatable) and `--declare` (Phase 1 hands over to the declare skill;
  a Brief section is appended). Tests: lint on a tagged spec including a broken later tag and a
  missing tag; `completed_steps` on the all-engine toy; defaults in `plugins list` text and JSON.
- I1 to I5 in `stringency-declare/SKILL.md`: the three file shapes inline, the manifest becomes an
  input item, defaults from `plugins list --json`, deliverable names from `module.yml` outputs,
  `derived_from.project`. Design 14.1 `lint` row; five DECISIONS lines; section I rows marked done;
  Order item 6 points at the roadmap.

## Learned

- The 26 approval cards of the toy come from the loop's shape, not from the gates: two were
  decisions, twenty-four were mechanics. All-engine pipelines plus `run --responses` take an
  estimated five-step run to 8 or 9 cards before any review page exists.
- The spec assumes a technical operator and hides nothing; the owner's goal needs a two-audience
  principle, not an exception. The rules that must survive it are already written (14.2, translate
  not decide, display does not recommend, Commandment 6).
- Two engine gaps block a real DE module: the job JSON carries no `design` or `objective` (the toy
  hardcodes its contrast), and `considered_set` is never filled. Both are additive.
- `ROSC_MTA2` is closer to stringency than the app-1 plan assumed: declared steps, gates, defect-
  tied tests. Its distance is containers, parameter declaration, and per-tissue script copies.
- The vendor quantified 32 of 44 bulk samples; alignment is needed for completeness, not to start.

## Altered

Design 14.1 `lint` row (DECISIONS-level). Nothing in a frozen contract. Toy plugin 0.1.2 in the
engine repo only; `~/github/stringency-toy-method` is unchanged (its manifest and pipelines do not
depend on `defaults`).

## Open

1. Owner: tag `v0.1.0` and push it, make the repo public, push `stringency-singlecell`, give
   `stringency-toy-method` a remote; commit the 51 uncommitted files in `ROSC_MTA2`; reinstall the
   engine from the tag on BMESEQ (stale) and PROTSEQ.
2. Owner: read `spec/ux-two-audiences.md` section 8 and approve or amend the five texts; answer
   the thirteen session-0 decisions in `spec/bulkrna-plan.md` section 8 and the five in
   `spec/app1-spatial-qc-plan.md` section 4.
3. Next session: Track 1 engine flags (`operator_line`, `run --responses`, `run --deliver`,
   `steps[].title`, `plain`, `--attest` needs a session ref, `reviews.operator_harness`) with the
   operator skill text that uses them; then the two session tests on PROTSEQ (data roots for
   delegates, standing grants).
4. Then Track 2 session 0 with the owner's decisions.

## Verify

```
cd ~/github/stringency && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy && scripts/check_no_biology.sh
uv run stringency plugins list | grep defaults
uv run python integrations/claude-science/render_brief.py /tmp/p/x --provider p --method /m@v1 --pipeline toy --image /i.sif --declare | grep -c 'stringency-declare'
```

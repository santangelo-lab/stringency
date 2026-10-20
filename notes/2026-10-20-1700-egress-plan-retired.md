# The egress plan retired, open mode's egress on the backlog, the skill description cap (2026-10-20)

## Goal

After the merge train, the owner asked what egress looks like in open mode, chose to put the
answers on the backlog rather than extend the plan, and to retire the egress plan since most of
it is built. Mid-session: the Xenium upstream skill could not be published (description 1,077
characters against a 1,024 cap).

## Done

- Probed the merged engine with an open project made from the egress drive's delivery. The
  egress hold applies in open mode (`ask`, `call`, `exec` pass run open); the assessment lists
  one step per open tool and scans their scripts; the toy's report listed only the operator
  session. Three gaps: an `exec` step is not a component and is never checked against the
  ceiling (the executor isolates its network under apptainer; under the local executor the
  trace says `n/a` and a script that tried the network ran unrecorded); `init --mode open
  --from-delivery` does not inherit the upstream's ceiling (ceiling 2 upstream gave "no ceiling
  declared"); and `exec --help` crashes on rich markup in the `--out` help text.
- `spec/plans/egress-and-remeasurement.md` moved to `spec/archive/` with an archive line: part 1
  built and merged (v0.2.23), part 2 unbuilt and unscheduled, its design kept there for L2 to L4.
  Backlog L1 moved to `archive/backlog-done.md`; L2 to L4 repointed; L40 (`exec` under the
  ceiling), L41 (the upstream ceiling), L42 (the `/data/protect` site rule), L43 (`exec --help`),
  L44 (the brief template's run flags), L45 (the "not assessed" line in the relay), L46 (the
  `module.yml` `egress` DEVIATIONS decision). `spec/README.md`, the roadmap (the two duplicated
  rows from the merge collapsed to one each, egress and K marked merged), `judge-sources-plan.md`
  and `commons-assessment.md` repointed.
- `render_skill.py` refuses a composed description over 1,024 characters (`DESCRIPTION_MAX`,
  a problem in `--check`, so the method repositories' CI catches it at the next engine tag);
  test; DECISIONS. The Xenium method at `v0.6.0-rc18`: four phrasings shortened, the description
  at 1,011, CI green. `publish-skills.md` names rc18.

## Learned

- Claude Science's skill registry caps the description at 1,024 characters; the renderer
  composes it from the summary and every phrasing, so a method with rich phrasings overflows
  silently until publish time.
- The merge of `open-mode` into `egress` duplicated the roadmap's egress and K rows (both sides
  added a row at the same place and the resolution kept both). Found while retiring the plan.

## Altered

- Nothing at the contract level.

## Open

- L40 and L41 before the first PROTECT project in open mode; L46 is the owner's DEVIATIONS
  decision; L43 is a one-line fix for the next engine release.
- The owner republishes `stringency-analyze-xenium-upstream` from the method at rc18.
- `spec/DEVIATIONS.md` and `spec/DECISIONS.md` still cite the plan at its old path; ledgers are
  dated and were left as written.

## Verify

    uv run pytest tests/test_render_skill.py; ls spec/archive/egress-and-remeasurement.md; grep -c '^| L4[0-6] ' spec/plans/backlog.md

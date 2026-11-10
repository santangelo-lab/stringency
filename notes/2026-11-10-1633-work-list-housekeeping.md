# 2026-11-10 16:33: one work list again, and the order of work after the first benchmark slice

Branch `plan-housekeeping`, from `main` at 079b632 (#25 merged), with `benchmark-prereg` merged
into it. Docs only.

## Goal

The owner asked for a survey of the engine and method backlogs, then of the plan documents
"floating around", and a plan for the fixes with what needs no input from him first. He then
answered seven of the items that waited on him. This session carries out wave 0 of that plan
in this repository.

## Done

- Three surveys (delegated, read-only): the open rows here (91 open or partly open, 17 done but
  never archived); the method and plugin backlogs; about sixty plan documents outside the list
  (28 open items no row tracked, about twenty stale statements).
- `spec/plans/implementation-order-2026-11.md`: waves 0 to 5 and one list of what waits on the
  owner, ordered by what each answer unblocks.
- The owner's answers of 2026-11-10, recorded in the rows: #25 merged; L169 built into the
  method; L171 taken up (strict-level limits whenever a benchmark runs; the engine route); L159
  by the skill; L158 a new exit code; L129 the run stops for a proposal; L162 approved. Earlier
  the same day, the five decisions on the name form (`declared-text-params.md`): the agent may
  propose a name under a hold; a name may be required; the existence check; the comparison in
  `objective.contrasts`; a declared name under every profile.
- `PLAN.md`: `benchmark-prereg` merged, so rows L157 to L171 are in one file; L93, L130 to L144,
  L157, L86 (verified against Xenium rc26) and L166 moved to `archive/backlog-done.md`; rows
  L172 to L185 for what no row tracked; State, "Next, in order" and the waiting table rewritten.
- Documents corrected: `spec/README.md` (statuses, the two new plan files, the plan of
  record); the status lines of `judge-sources-plan.md`, `commons-assessment.md` and
  `annotation-controls.md`; `DEVIATIONS.md` on `egress`; dated corrections at the head of
  `benchmark-plan.md`; `confirm-once.md` to `archive/`.
- `spec/plans/benchmark-plan-owner-2026-10-21.md`: the owner's plan of record, copied
  unchanged from the upload it had lived in.

## Learned

- A defect found in a session and written into a method's design note never reached this list:
  per-item judgment requests numbered as replicates (L172), worked round in two modules since
  2026-10-27.
- The list's own claims drift: it said the Xenium `PLAN.md` carried the Lane F report and
  retrospective, and it did not (L179). Finished rows stayed in the open tables for two weeks.
- The merge kept 7d51af3 in history on purpose: the benchmark's results name that commit as
  their pre-registration.

## Altered

- Nothing in code or contracts. Three contract-level changes are approved in principle and
  wait on their texts: the name form, `via: policy`, the new exit code; and a project's limits
  band apart from its profile.

## Open

- Wave 0 in the other repositories: the scRNA-seq method's unlisted items into its
  `BACKLOG.md` (worded without naming an eval); the stale comment in the Xenium `policy.yml`;
  the plugin README's status table.
- Wave 1 next (`declared-text-params.md`): L168 with L161 first.
- For the owner: the waiting table, rewritten in this commit.

## Verify

    uv run pytest -q
    grep -c "^| L" spec/plans/PLAN.md

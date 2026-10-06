# 2026-09-23 19:30: judge sources brainstorm

## Goal

The owner asked for a high-level look at sourcing judgment agents from many places (operator
delegates, fixed local models, APIs), the current state of the engine on that question, and a
read of TypeSafe's Jev model as a further option.

## Done

- Surveyed the harness protocol (`src/stringency/harness/`), `judgment.harness_for`, the config
  enum, the `invocations` schema, design 10.1, 10.2 and 17, the operator skill's dispatch
  procedure, and every spec, plan and note mention of judge sourcing.
- Read jevai.net, typesafe.ai, the TypeSafe docs (primitives, confidence, the Jev 1.13
  jaggedness page, privacy policy) and three third-party write-ups.
- Wrote `spec/plans/judge-sources-plan.md`: state, why a fixed local judge matters beyond
  budget, steps S1 to S6, constraints, seven owner decisions, order, and the Jev assessment in
  section 8. Added its row to `spec/README.md` and a Lane G placeholder plus a Status line to
  `spec/plans/roadmap-2026-09.md`. Nothing committed.
- Evaluated ClawBio (`github.com/ClawBio/ClawBio` v0.7.1) for integration; decision recorded in
  the judge-sources plan section 9: no integration lane. Wrote
  `spec/plans/egress-and-remeasurement.md` with the two mechanisms borrowed from it (data egress
  classes with a lint scan and a policy ceiling; judgment re-measurement endpoints, an
  `ill_formed` control kind, `abstain_stability`, judge identity on control results). Backlog
  rows L1 to L4 point at it; the judge-sources plan's routing rule and S2 endpoints now
  reference it.

## Learned

- The judge-source flexibility is designed in (two harness families behind one protocol, one
  shared `Invocation` record) and about two thirds built. `openai-compatible` is a stub whose
  design 17 trigger, "the Qwen3 evaluation", is now satisfiable: Ollama with `qwen3:8b` and
  `qwen3:32b` is on PROTSEQ and the GPU is idle when Brian is not loaded.
- A local direct adapter is the only path to `isolation: enforced` without an API budget, the
  only path that keeps PROTECT evidence on the machine, and the only source of model diversity
  against a Claude operator with Claude judges.
- Under dispatch, judge identity is self-reported and never checked; the operator skill's
  no-delegate fallback lets the operator judge itself and the design does not name it.
- No commandment, backlog item or lane covers where judges come from.
- ClawBio shares the "agent dispatches, code executes" rule and the abstain-not-default
  instinct, and has no topology, no durable trace and no replication or holds for LLM
  judgment; nothing spatial. Its data-handling page is generated from code and enforced by a
  test, and its lifecycle page scores skills on over-answer rate and abstention stability with
  rules written before measurement. Those two are the borrowings.
- Jev fits the direct family mechanically but returns no rationale or evidence citations, so it
  cannot be a voting replicate under the current record; three non-voting roles were identified.
  Owner tabled it.

## Altered

Nothing in the engine or the spec. Two plan documents gained pointers (README row, roadmap Lane G).

## Open

- The owner's seven decisions in the plan's section 6, chiefly: S1 as DECISIONS-level or design
  first; how S2 (b) runs against the Lyons re-judgment; where the work lives (Lane G recommended).
- S3 (judge identity on the review surfaces) and S5 (mark the fallback) need no decision and can
  start any time.
- L2 (`abstain_stability` in coverage) needs no decision either and yields a number for the
  Lyons outlier runs already in the store. L1 should land before the first PROTECT project.

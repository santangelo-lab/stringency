# spec/

What each file is, and how much weight it carries.

## The spec

| file | state (2026-10-14) | what |
|---|---|---|
| `stringency-design.md` | the spec | the design; frozen contracts are `module-contract.md`, `predicate-contract.md`, `trace-schema.md`; `commandments.md` is the source of the constraints; `DECISIONS.md` and `DEVIATIONS.md` are the ledgers; `method-skills.md` is the page for the two skill files a method carries |

## Plans (`plans/`)

| file | state (2026-10-14) | what |
|---|---|---|
| `roadmap-2026-10.md` | **current** | the one-page state of every lane (A engine, I integration and CI, E skills and onboarding, F spatial method, H console, J harnesses, G judge sources, B bulk, egress) with its plan document and next step; how the plans are kept; the design amendment texts awaiting the owner; written from the code review of 2026-10-14 and the owner's asks |
| `backlog.md` | current | open items not owned by a lane (A5, E2, J1, J2, K3 to K6, L2 to L7, L9, L11, L24 to L34, L39 to L42, L44 to L49, L52, L53, H5), the measurement table; done rows are in `archive/backlog-done.md` |
| `spatial-method-plan.md` | **active (Lane F)** | the spatial method after QC with Lyons CLP as the pilot: phase 0 as run, `xenium-upstream` as designed through rc10, every owner decision (1 to 25; 21 to 25 are Lyons v2 with ROSC controls); the method's `PLAN.md` is current for rc11 to rc13 |
| `console-and-fleet-plan.md` | released (v0.2.8 to v0.2.16); second cut unscheduled (Lane H) | the console: its design as decided 2026-10-07, "What is open" at the top (batch cards, gallery, history, the resource cap), section 8 the pick-up guide; mockup in `plans/mockups/` |
| `confirm-once.md` | proposed (Lane A, after W1 to W4) | why one design was confirmed five times and one parameter set sixteen; five rules to make a chained study one acceptance; L5, L6; four owner decisions |
| `judge-sources-plan.md` | proposed (Lane G; S1 and S2 moved to Lane J) | judgment agents from many sources: judge identity, a panel specification (*design*), the operator fallback, a `/data/protect` routing rule; seven owner decisions in section 6 |
| `open_mode_plan.md` | **approved 2026-10-16 (Lane K); S1 to S7 built the same day on branch `open-mode`, O1 to O6 open** | open mode, the second half of the engine: after a pipeline delivers, the operator answers a person's questions on the delivered dataset with trusted tools (modules listing `open`, run on demand through the executor) or model-written code the engine runs (`exec`) and labels untested; `answer` checks every numeral against cited cells; the pre-switch review of tools and paths; the owner's five decisions; engine changes by file; skills; the method author's side; rigor; the design amendments; sessions S1 to S7 and O1 to O6 |
| `commons-assessment.md` | assessed 2026-10-16; no integration | `posit-dev/commons` read against the design: what it is, a side-by-side, the shared instincts; four borrowings as backlog L35 to L38 (a trust label per delivered artifact, harness conformance fixtures, a method-author skill over the override corpus, quoted text verified), a G2 proposal (`exec --step`), and what commons lacks that the engine has |
| `ux-two-audiences.md` | history of Track 1 (Lane E); its rules still bind the skills | the two audiences, the hold protocol, the analysis-skill rules; built in full; superseded as a work list by the roadmap's W5 and W6 |
| `trace-integrity-plan.md` | **proposed 2026-10-20 (Lane T)** | a mutable row can change without its event (the owner's review, verified): T1 the Store API and the docstrings, T2 `stringency audit`, T3 the database requiring the event (9.4, 9.5 via DEVIATIONS), T4 the OS boundary against the operator; backlog L50 to L53 |
| `trace-integrity-review-2026-10-20.md` | the owner's review, kept as written (ruff reformatted its two code blocks) | the finding, the reproduction, the five options |
| `bulkrna-plan.md` | dormant (Lane B) | Track 2 in detail, kept as written since 2026-09-23 |

Every live plan opens with a dated **Status** line; a document without one has not been reviewed
since 2026-10-14. Lane state is written in `roadmap-2026-10.md` only.

## Archive (`archive/`)

Finished or superseded documents, kept because the notes and the trace cite them. Each opens with
a line saying why it was archived and where its live successor is. Nothing in `archive/` is an
instruction to a session. Moved there on 2026-10-20: `egress-and-remeasurement.md` (part 1 built and merged as v0.2.23; part 2 unbuilt, backlog L2 to L4). On 2026-10-14: `roadmap-2026-09.md` (the approved plan of
2026-09-14 and its lanes' history), `engine-v0.2.7-plan.md` (built 2026-10-07), `backlog-done.md`
(the closed backlog rows). On 2026-10-06: `app1-spatial-qc-plan.md` (Track 3, Lane C, closed),
`lane-c-day1-2026-09-17.md` (its day log), `project-page-and-notify.md` (Track 1h, built),
`declarations-and-objectives.md` (design note, built; H5 in the backlog).

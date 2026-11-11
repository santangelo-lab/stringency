# spec/

What each file is, and how much weight it carries.

## The spec

| file | state (2026-10-21) | what |
|---|---|---|
| `stringency-design.md` | the spec | the design; frozen contracts are `module-contract.md`, `predicate-contract.md`, `trace-schema.md`; `commandments.md` is the source of the constraints; `DECISIONS.md` and `DEVIATIONS.md` are the ledgers; `method-skills.md` is the page for the two skill files a method carries |
| `ux-two-audiences.md` | rules (sections 4 and 5.1); otherwise the record of Track 1 | the two audiences, the hold protocol and the analysis-skill body rules the skills follow; `tests/test_render_skill.py` reads them against the template; moved up from `plans/` on 2026-10-21 because a rule is not a plan |

## Plans (`plans/`)

`PLAN.md` is the one work list. Every open item is a row in it; the other documents here are the
reasoning behind rows that cite them and hold no list of their own. Each opens with a dated
**Status** line naming its rows; when a document's last row closes it moves to `archive/`.

| file | state (2026-11-10) | what |
|---|---|---|
| `PLAN.md` | **current** | the state, what is next in order, every open row by area (engine: decision points, holds and confirmation, judgments and evidence, delivery and trace, the gate and the step lifecycle, harnesses; method and plugin; skills and documents; console; operations), the table of everything that waits on the owner, and how the file is kept; replaced `roadmap-2026-10.md` and `backlog.md` on 2026-10-21; rows to L127 |
| `measurements.md` | current | the measurement tables the UX work reports into: one row per measured run, and the open-mode table (no row yet); moved out of `backlog.md` |
| `decision-points.md` | sections 2 to 5 built (0.2.29); rows L63 to L66 open (the menu keys) | the controls a method puts on an agent's parameter choice: the `decision:` block beside a parameter's range (evidence required, `hold: always`), the lint rule, the citation and considered-set slots on `propose`, the `presented` event, and the menu of sweep, rule, judged and sensitivity an author chooses per step; what is not pursued and why |
| `benchmark-plan.md` | current: Phase 2 started 2026-11-10, the pre-registration and its amendments; rows L87 to L92, L154 to L156, L161 to L171, L183 | the owner's benchmark plan (2026-10-21) adapted to the engine and this machine |
| `benchmark-plan-owner-2026-10-21.md` | the plan of record, unchanged | the owner's benchmark plan: the purpose, the three claims, the arms, the metrics, the abstention risk, what a convincing result looks like; `benchmark-plan.md` is its adaptation |
| `declared-text-params.md` | proposed 2026-11-10; rows L163, L168, L169 | why the scRNA-seq DE pipeline runs only on an object named as its fixture is (a pipeline parameter is ranged, optioned or fixed, and a name is none of them); five fixes: declared values checked at `init`, the DE module reading the comparison from the declarations, a `text: declared` parameter form (design), the method using it, and an option to leave out an incomplete replicate; four owner decisions |
| `implementation-order-2026-11.md` | proposed 2026-11-10; no rows of its own | the order of work after the first benchmark slice, by the owner's rule that what needs no input from him starts first: housekeeping (one work list, rows for 28 untracked finds, stale documents), names, hold and proposal friction, small correctness, lineage assignment, L100; then every decision that waits on him, ordered by what it unblocks |
| `judge-sources-plan.md` | S1, S3 and S5 built (L70 and L72 done, the `openai-compatible` adapter in 0.2.32); rows L34 (the Qwen3 evaluation), L71, L73 open | judgment agents from many sources: judge identity, a panel specification (*design*), the operator fallback, a `/data/protect` routing rule; the decisions of section 6 |
| `console-and-fleet-plan.md` | released (v0.2.8 to v0.2.16); rows L6, L74 to L76, L81 | the console as decided 2026-10-07; "What is open" at the top; section 8 the pick-up guide; mockup in `plans/mockups/` |
| `trace-integrity-plan.md` | T1 and T2 built (0.2.25); rows L52, L53 | a mutable row can change without its event (the owner's review, archived): T3 the database requiring the event, T4 the OS boundary against the operator |
| `spatial-method-plan.md` | the record of phase 0 and the owner's decisions 1 to 25 | the spatial method with Lyons CLP as the pilot; the method's own work list is its repository's `PLAN.md`, which cites section 8 here |
| `commons-assessment.md` | assessed 2026-10-16; L36 done (0.2.32); rows L35, L37, L38 open; its smaller practices are in L184 | `posit-dev/commons` read against the design: a side-by-side, the shared instincts, four borrowings, what commons lacks that the engine has |
| `omicsbench-assessment.md` | assessed 2026-10-21; rows L54 to L60 | LatchBio's OmicsBench failure taxonomy read against the engine: the seventeen modes counted and classified, a side-by-side, seven borrowings, the biological modes, candidate README words; its 4.2 grew into `decision-points.md` |
| `gate-soundness.md` | filed 2026-10-22; rows L100 to L109 | the owner's walkthrough of the gate checked against the code: defaults escape the decision-point checks (`hold: always` silent under `run`), a rebind ignores the predicate and phase, a raising predicate takes its finding's disposition, the budget does not stop a predicate, the Action's dicts are mutable, a step stranded in `proposed`, the lifecycle audit does not replay edges, predicate purity is unenforced; the order, the contract impact |
| `annotation-controls.md` | `sc.fine_label_uncited` built (plugin 0.8.5), the Xenium method's items 3.15 to 3.21 built 2026-10-27, L112 done; rows L110, L111 open | the owner's points on the Xenium annotation checked against the code: the fine label is free text no rule read and a person's choice does not reach it; the fraction expressing is present but carries no weight (measured on the ROSC liver fixture); `pct_diff` as evidence, twenty candidate state programmes as evidence for the fine label, one fine label of three by a reconcile step and a choosing judgment (the owner chose both), a person's choice carried through the consensus, the controls |
| `module-scripts.md` | phases 0 to 7 built 2026-10-26 (the engine, every Xenium and scRNA-seq module, the Plasmidsaurus template, the wrap skill); row L113 | the owner's points on the methods' module scripts: named after the module with `entry:`, a short plain header and a `CHANGELOG.md`, one shape for every script, plumbing apart from analysis (`stringency_io`), style checked by ruff and lintr, an index in each README, a recipe and a skill for existing code; the phases across the four methods and how identical behaviour is checked |
| `qc-failure-modes.md` | filed 2026-10-26; rows L115 to L127 | the owner's ask for predicates grounded in the literature on single-cell and imaging-spatial failure modes, with a high mitochondrial fraction first: what the QC modules compute and what no predicate reads, the literature as it bears on a gate (Consensus, ten searches), thirteen new predicates and a second version of `sc.qc_floor_above_data` (mitochondrial, droplet artefacts, imaging spatial), three decisions on the mitochondrial bound, what is not proposed |

## Archive (`archive/`)

Finished or superseded documents, kept because the notes and the trace cite them. Each opens with
a line saying why it was archived and where its live successor is. Nothing in `archive/` is an
instruction to a session. `backlog-done.md` continues as the ledger of closed rows. Moved there on
2026-11-10: `confirm-once.md` (built in 0.2.31, every row closed). Moved there on
2026-10-21: `roadmap-2026-10.md` (superseded by `plans/PLAN.md`; the lanes A to T and their
history, and the "Needs the owner" amendment texts still to be read), `open_mode_plan.md` (built,
0.2.22 to 0.2.27; its O3, O5 and O6 are rows L81, L77 and L78), `bulkrna-plan.md` (dormant since
2026-09-23), `trace-integrity-review-2026-10-20.md` (the owner's review). On 2026-10-20:
`egress-and-remeasurement.md` (part 1 built and merged as v0.2.23; part 2 unbuilt, rows L3 and
L4). On 2026-10-14: `roadmap-2026-09.md` (the approved plan of 2026-09-14 and its lanes' history),
`engine-v0.2.7-plan.md` (built 2026-10-07), `backlog-done.md` (the closed rows). On 2026-10-06:
`app1-spatial-qc-plan.md` (Track 3, Lane C, closed), `lane-c-day1-2026-09-17.md` (its day log),
`project-page-and-notify.md` (Track 1h, built), `declarations-and-objectives.md` (design note,
built; H5 in the plan).

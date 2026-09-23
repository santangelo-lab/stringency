# spec/

What each file is, and how much weight it carries.

## The spec

| file | what | changes need |
|---|---|---|
| `stringency-design.md` | the design; where it and any other document disagree, this wins | the owner's approval for a contract, a DECISIONS line below the contract level |
| `commandments.md` | the constraints the design implements | the owner |
| `module-contract.md` | frozen at the Phase A exit: what a method repo and a `module.yml` declare, what a module script receives and writes | the owner, via `DEVIATIONS.md` |
| `predicate-contract.md` | frozen: the predicate signature, phases, scopes, dispositions | the owner, via `DEVIATIONS.md` |
| `trace-schema.md` | frozen: the tables and columns of `prov/run.db`; additive columns are DECISIONS-level | the owner for anything not additive |
| `method-skills.md` | the two skill files a method repository carries per pipeline (delivery skill, design 14.4; analysis skill source, design 10.4): fields, checks, render, publish, routing test | a DECISIONS line; the schemas themselves are the design's |

## The ledgers

| file | what |
|---|---|
| `DECISIONS.md` | every choice made where the design was silent, one line each with a reason; append only |
| `DEVIATIONS.md` | frozen contracts that could not be implemented as written; each needs the owner's acknowledgement; empty so far |

## Plans (`plans/`)

Working notes, not the spec. They say what to build next and why; when they propose changing a
design section, the text is marked as an amendment awaiting approval.

| file | what |
|---|---|
| `roadmap-2026-09.md` | the plan approved on 2026-09-14 after the Phase A exit: Track 0 cleanup (done), Track 1 two-audience UX, Track 2 bulk RNA-seq plugin, Track 3 Lyons CLP spatial QC (done to S4); its Status section and the per-lane status lines under Order say where each lane stands |
| `ux-two-audiences.md` | Track 1 in detail; section 8 holds the amendment texts for design 7.5, 10.4, 12.1, 14.1, 17 |
| `bulkrna-plan.md` | Track 2 in detail; section 8 holds the session-0 decisions for the owner |
| `app1-spatial-qc-plan.md` | Track 3 in detail; section 4 holds the owner's decisions; section 5 the outcome against the plan and what is open for the track |
| `lane-c-day1-2026-09-17.md` | the running tooling log of Lane C on 2026-09-17 and 2026-09-18 (hold ids, run ids, decisions, engine gaps); closed, kept because the notes and the trace cite it |
| `declarations-and-objectives.md` | agent-drafted declarations (built) and the five options for objectives that arrive late; staged mode (H5) is still open here |
| `backlog.md` | the open items that are not in a track, and the measurement table |

## Archive (`archive/`)

Finished or superseded documents, kept because the notes and the trace cite them. Each opens with
a line saying why it was archived and where its live successor is. Nothing in `archive/` is an
instruction to a session.

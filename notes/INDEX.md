# notes index

The map of session notes. One line per note, newest first. Keep the current-state block accurate;
it is the first thing a new session reads.

## Current state (2026-09-15, midday)

- Phase A exit complete on both machines (BMESEQ `toy-cs` 2026-09-08; PROTSEQ two chained projects
  from agent-drafted declarations 2026-09-14). Backlog sections A to I done except A5 (review page,
  now scheduled as Track 1e), E2's in-session route, G2 and H5 (design questions).
- Roadmap approved 2026-09-14: `spec/plans/roadmap-2026-09.md`. Track 0 (section I code and skill text)
  done. The 'await the owner' items below were answered 2026-09-15. Track 1 (two audiences: fewer plainer cards, relayed and web holds, analysis skills,
  `summary.md`, shared PROTSEQ install) detailed in `spec/plans/ux-two-audiences.md`; its five amendment
  texts await the owner. Track 2 (bulk RNA-seq plugin and method) in `spec/plans/bulkrna-plan.md`;
  thirteen session-0 decisions await the owner. Track 3 (Lyons CLP Xenium, QC first) in
  `spec/plans/app1-spatial-qc-plan.md`.
- `v0.1.0` tagged and pushed 2026-09-14; engine repo public; singlecell and toy method repos
  pushed; engine 0.1.0 installed from the tag on both machines.
- `spec/` reorganised 2026-09-14: spec and contracts at the top, `spec/plans/` live, `spec/archive/`
  history; `spec/README.md` maps it.
- Approvals collected 2026-09-15: the five Track 1a amendments applied to the design; Track 2
  session-0 decisions answered (DESeq2 replaces limma-voom; all pairwise within tissue; GHCR image;
  reviewer = the person running) except the DESeq2 parameter list; Track 3 decisions answered
  except the Lyons CLP design, which waits on the owner's experimental plan document.
- Next session should start with: `notes/2026-09-15-1130-approvals-walkthrough.md`, then
  `spec/plans/ux-two-audiences.md` sections 3.2 and 5.1 (Track 1 engine flags and skill text).

## Notes

- `2026-09-15-1130-approvals-walkthrough.md` — Track 1a amendments approved and applied; Track 2 and Track 3 decisions answered and recorded; DESeq2, Proseg mix, GHCR images.
- `2026-09-14-1600-track0-and-roadmap.md` — surveys, the approved roadmap and its three track notes, section I code and skill text done.
- `2026-09-14-1445-protseq-exit-run.md` — PROTSEQ tooling, both skills live, two chained projects from agent-drafted declarations; section I of the backlog.
- `2026-09-09-1059-declare-and-chained-projects.md` — declare --check, drafted-by and brief, derived_from chained projects, the declare skill.
- `2026-09-09-0847-script-drift.md` — script drift check; the two classes of analysis code and the open G2 question.
- `2026-09-08-1655-improvements-backlog.md` — the improvements backlog worked through on the toy:
  review display and packets, operator ergonomics, trace semantics, toy method 0.1.1, design text.
- `2026-09-08-1542-phase-a-exit-bmeseq.md` — Phase A exit on BMESEQ from Claude Science: sandbox limits, remote-host
  mode, machine install, review-surface findings.
- `2026-09-03-1605-phase-a-m0-m11.md` — first build session: repository created, M0 through M11
  implemented against the design, end-to-end CLI rehearsal of the toy pipeline, singlecell skeleton.

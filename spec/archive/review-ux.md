# Review: what the reviewer sees, and how a verdict gets in

> Archived 2026-09-14: layers 1 and 2 were built on 2026-09-08; layer 3 (the review page) is carried forward in `spec/plans/ux-two-audiences.md` section 5.2.

Working notes for the review surface, written during the Phase A exit run on 2026-09-08. Not
part of the design; a proposal for the change to design 7.3 and 7.5 and for the build order.
Layers 1 and 2 were built on 2026-09-08 (`src/stringency/review_render.py`, goldens under
`tests/golden/review_*.txt`; packets under `runs/<run>/<step>/review/`); layer 3 is not.

## What the exit run showed

The first flag hold raised by real judges (`judg.confidence_consistent` on the toy `03_label`
step, project `toy-cs`) exposed three things.

1. `stringency review` prints the hold header, the predicate's reason, and the predicate's raw
   evidence JSON. Design 7.3 says it prints the evidence the model saw, every replicate's call
   with its confidence and cited evidence, and the relevant slice of the table. The
   implementation shows counts; the reviewer needs the content. Answering the hold's question
   took opening four files by hand: `02_summarize/table.tsv`, `03_label/judgments.jsonl`,
   `03_label/dispatch/resp_*.json`, `03_label/consensus.json`.
2. The hold message from `run` named the step and the reviewer but not the hold id. Design 14.2
   says the message names the hold. The operator worked around it by not looking, which is the
   right behavior, but the id belongs in the message. `init` exits 0 while leaving a confirm hold
   open; `run` on the same hold exits 10. One of these is wrong; 10 is consistent with 14.2.
3. Every path to a verdict runs through a terminal or through the agent (`--attest`, recorded as
   `relayed`). The owner of this project is comfortable at a terminal; the next reviewer will
   not be. See design 7.5 for why the relayed path is deliberately weaker.

## What a reviewer needs to see, per hold kind

The question a hold asks is narrow. The display should answer it and nothing else.

| hold | question | must show |
|---|---|---|
| `confirm` | does the engine's reading of the declarations match the experiment | the echo-back, the three file digests |
| flag on a predicate | is the flagged condition acceptable here | the predicate's reason and evidence, the parameters, and the state slice the predicate read |
| `self_uncertain` (item) | which replicate's call stands, or none | the evidence rows for the item, each replicate's label, confidence, cited cells for and against, rationale |
| `run_disagreement` (item) | same, with the split made visible | as above, grouped by label |
| flag on a judgment predicate (this run's case) | is the declared confidence or citation consistent | for each flagged replicate and item: the cited cells resolved against the evidence table, the criterion that failed, the rationale |

Common to all: hold id, step, module and version, attempt, who it waits on, the verdicts
available, and what each verdict does. Rationales are quoted, not summarized. Cited cells are
shown as the table row they point at, with the cited value beside the stored value so a
mismatch is visible even though `judg.evidence_exists` already blocks on it.

## Three layers, in build order

**Layer 1: the terminal display design 7.3 already promises.** `review` and `review --show`
render the table above. Data is all in the trace (`holds.context_json`, `judgments`,
`messages` for the raw responses, `state_snapshots`, the evidence table by digest). A golden
test per hold kind. No new dependencies. This is the fix for finding 1 and is needed whatever
else is built, because the same renderer feeds layers 2 and 3.

**Layer 2: a review packet on disk.** When a hold opens, the engine writes
`runs/<run_id>/<step_id>/review/<hold_id>.html` (jinja2, inline CSS, no scripts) and
`.md` with the same content. A reviewer opens it in a browser over `scp`, or a Claude Science
session saves it as an artifact so it shows in the app with provenance. The verdict still goes
in by terminal or relay; the packet only removes the "open four files" problem for people who
do not use `review` at all. Cheap once layer 1 exists.

**Layer 3: a reviewer-run review page.** `stringency review --serve [--port]` runs a
localhost HTTP server (stdlib `http.server`) that lists open holds across the projects it is
pointed at, renders the layer 1 content, and takes a verdict and reason from a form. Reached
through an SSH tunnel the way Claude Science is today. Identity is the OS user who started the
server, checked against `roles.reviewer` exactly as the terminal path does. Recorded with a
third `via` value, `web`, which profiles treat like `tty`: the agent never touches the verdict,
so it deserves tty trust, and strict can accept it. Design 7.5 and 14.1 change; 14.2 does not.
Already listed in design 17 with the trigger "a reviewer who does not use a terminal".

**Not proposed.** A verdict button inside Claude Science. The click reaches the engine through
the agent, so it is relayed with a better front. Signed attestations, until there is a second
lab.

## Constraints that hold

- Dependencies stay boring: jinja2 (already present) and the standard library. No web
  framework, no JavaScript beyond nothing.
- Prose in the display is plain. The display states what fired and what the verdicts do; it
  does not recommend a verdict.
- The trace is the source. The display reads tables; it never re-derives a judgment or re-runs a
  predicate.
- The hold message from `run` stays terse (14.2). It gains the hold id and, once layer 2
  exists, the packet path.

## Open questions for the design change

- Should `via: web` be allowed under strict, or should strict stay terminal-only? The argument
  for allowing it is that the trust boundary is the reviewer's own process in both cases.
- Does the server show one project or many? One project matches the CLI; many matches how a
  reviewer works. Start with one, pointed at by `--project`, and see.
- Does the packet belong in `runs/` (with the step) or `prov/` (with the trace)? `runs/` is
  where the sidecar convention lives; `prov/` is append-only and the packet is derived.
- Whether `init` should exit 10. Proposed yes.

## Order of work after the exit run

1. Layer 1, with golden tests for confirm, flag, self_uncertain, run_disagreement, and the
   judgment-predicate flag using this run's trace as the fixture. Done 2026-09-08; the trace's
   judges are replayed through the mock (`context_contradicting.yml`) so the test runs anywhere.
2. Hold id in the `run` message; `init` exits 10 on an open hold (both done 2026-09-08); the
   engine creates the step directory when it issues a ticket (B1). Each a DECISIONS line.
3. Layer 2. Done 2026-09-08; the packet lives in `runs/` with the step (the open question below
   is settled that way: `runs/` holds the sidecar convention, `prov/` is append-only).
4. Design amendment for `via: web`, then layer 3, when a non-terminal reviewer exists or when
   the lab decides to onboard one.

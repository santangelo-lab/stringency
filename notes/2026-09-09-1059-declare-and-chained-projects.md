# Agent-drafted declarations and chained projects

## Goal

Build steps 1 and 2 of `spec/declarations-and-objectives.md` so the PROTSEQ exit run can start
from a brief and a sample manifest rather than hand-written declarations, and so a processing
project can hand its deliverable to a downstream project (option 1 of the objectives note).

## Done

- `spec/declarations-and-objectives.md`: the design note (two parts: agent-drafted
  declarations; objectives that arrive later, five options, recommendation to chain projects
  now and define staged mode after application 1). Backlog section H. CLAUDE.md lists the note.
- `stringency declare --check <dir> --method --pipeline`: `init`'s whole path in a temporary
  directory, removed afterwards; echo-back on exit 0, the failing field or `init.*` predicate on
  exit 15; `--json` carries hashes, input digests, predicates, method SHA.
- `init --drafted-by person|agent --brief <file>`: `stringency.yml` gains a `declarations`
  block; `brief.md` kept; confirm hold context carries `drafted_by`, `brief`, `brief_blake3`.
- `inputs.yml` item `derived_from: {run_id, step_id, output, project}`, verified at `init`
  against the sidecar beside the file (run, step, output name, hash); captured at run open under
  `captures.derived_from`; named in the methods paragraph.
- `plugins list --json` exposes `design_schema` and `vocabulary_terms`.
- Toy plugin 0.1.1: question `process_rows`; pipeline `toy-process` (filter only, deliverable
  `object`) in the plugin template and in `~/github/stringency-toy-method` (tagged `v0.1.2`,
  not pushed to the `/data-raid` mirror).
- `integrations/claude-science/stringency-declare/SKILL.md`: the drafting skill; sources in
  order of authority, what to ask rather than pick, the check loop, the hand-over. README and
  new-project checklist point at it. Untested against a live session until PROTSEQ.
- Tests in `tests/test_declare.py`: `declare --check` good and each failure, the API equals
  `init`'s echo and hashes, drafter and brief recorded, a two-project chain end to end with
  tampered and orphan inputs refused, plugins JSON. Design 2.3, 2.7, 14.1 text; five DECISIONS
  lines.

## Learned

- Sidecars carry `run_id`, `step_id`, `name`, `blake3` but no artifact id, so `derived_from`
  keys on step and output rather than artifact id as the note first proposed.
- `_init_in` now returns the project, the extractor states, and the init gate; `init_project`
  takes the first, `check_declarations` uses all three. One code path for both verbs.

## Altered

Below contract level. Design 2.3 (optional `derived_from`), 2.7 (drafted declarations and
`declare --check`), 14.1 (`declare`, two `init` flags). `stringency.yml` gains an optional
block; old projects load unchanged.

## Open

1. PROTSEQ exit run per the note's step 3: brief plus manifest, the declare skill drafts, Jim
   accepts the echo-back, two chained projects (`toy-process` then `toy-engine` or `toy`), count
   drafting turns and check that every accepted field has a source. Needs the toy method
   `v0.1.2` reachable from PROTSEQ and the engine installed from current `main`.
2. G2 (session-written code) and H5 (staged mode) stay design questions.
3. The rest of the earlier Open lists: `v0.1.0` tag, public repo, singlecell push.

## Verify

```
cd ~/github/stringency && uv run pytest -q tests/test_declare.py && uv run ruff check . && uv run mypy
uv run stringency declare --check /data-raid/Projects/Jim/stringency-exit --method ~/github/stringency-toy-method@v0.1.2 --pipeline toy --executor apptainer
```

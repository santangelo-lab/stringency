# Lane A step 1: Track 1b engine flags and the Track 1c operator skill text

## Goal

Build the engine side of `spec/plans/ux-two-audiences.md` sections 3.2 and 6, then rewrite the
operator skill and the two templates to use it (3.3, 5.1), so the person watching a session reads
sentences and the operator runs one command per step. Design amendments 7.5, 12.1, 14.1 were
applied 2026-09-15 before this session; nothing here touches a contract.

## Done

- `steps[].title` on `pipeline.yml`; `Pipeline.title(step_id)` falls back to the id. `lint` warns
  when `skills/<pipeline>.yml` exists and steps are untitled. `next --json` and `run --json` carry
  `title` beside `job_spec` and `dispatch_dir`, and `plan.title` for a runnable step.
- `job_spec.operator_line`: exec, producible evidence commands, submit, joined by `&&`; the human
  ticket prints it as "as one command". Schema string unchanged.
- `run --responses <file|->`: one document to `resp_N.json` in manifest order, then the loop
  collects. Exit 16 when not dispatching, wrong step, wrong count, or files already present;
  nothing written on refusal. Exit 15 for a malformed document.
- `run --deliver`: delivers in the same invocation when the loop returned `completed` and the
  run is `completed`; `delivery` in the payload. A stop at `--until`, a hold, or a ticket delivers
  nothing.
- `plain` on `run --json` and `status --json` (`src/stringency/plain.py`): progress by title,
  then one stop sentence per `Next.kind`; `status --json` also carries `completed_steps`. Goldens
  `tests/golden/plain_*.txt`, thirteen cases (every kind plus variants).
- `--attest` without `STRINGENCY_SESSION_REF` is refused (16) before any write.
  `reviews.operator_harness` from `STRINGENCY_OPERATOR`, migration `0004`, additive.
- `deliver` writes `summary.md` (`src/stringency/summary.py`), listed in `index.json`; golden
  `tests/golden/summary_toy_engine.md`; a second test checks changed parameters, a corrected
  judgment, and the echo body.
- Toy pipelines titled and all at 0.1.2, in the plugin template and mirrored to
  `../stringency-toy-method` (committed there, not tagged; Lane A step 4 re-tags).
- `integrations/claude-science/stringency-operator/SKILL.md` rewritten: two-audiences preamble,
  intent table (3.3), loop on `operator_line`, `run --responses -`, `--deliver`, `plain`,
  `summary.md`, and the hold protocol verbatim from 5.1 as section 6. `templates/brief.md.j2` and
  `agent-context.md.j2` follow; both render (`render_brief.py` with `--declare` and `--context`).
- DECISIONS: eight entries (titles, `operator_line`, `--responses`, `--deliver`, `plain` and
  `completed_steps`, attest and migration 4, `summary.md`, toy 0.1.2). `spec/trace-schema.md`
  reviews row names `operator_harness`. Roadmap Lane A item 1 marked done; plan 3.2 carries a
  built note; backlog row J1 for `declare --check --print-hashes`.

- Test drive prepared on PROTSEQ (`integrations/claude-science/hosts/protseq-track1b-drive.md`):
  engine installed as `~/mytools/stringency/engine/versions/0.1.0+lane-a-1` with `current` moved
  to it; toy method tagged `v0.1.3` locally (not pushed); declarations in
  `/data/lab/projects/2026-09_stringency-exit_jrrose5/track1b/` pass `declare --check` against
  `toy-engine@v0.1.3`; brief and context rendered to `~/mytools/stringency/brief-track1b.md` and
  `context-track1b.md`. The brief template and `new-project.md` now route the confirm hold through
  the hold protocol instead of "I accept it at my own terminal".

- Test drive run by the owner the same day: 17 cards (10 commands, 7 transfers) against 26 on
  2026-09-14 for the same pipeline (that run included about 6 drafting cards this one skipped);
  confirm hold resolved by the relayed protocol, `via: relayed` with session ref and harness;
  three isolated delegates, all `claude-opus-5`, `saw_conversation: false`; no flags; `summary.md`
  shown as written. Measurement row added to `spec/plans/backlog.md`; backlog J2 (`submit
  --deliver`) opened; 3.4 answer 1 recorded in the integration README.

## Learned

- `IOSpec` has no `description`, so `summary.md` names each delivered file by output name, step
  title, type, and format. A description key is a module-contract question for the owner.
- `run --json` `completed_steps` (this invocation, Track 0) and `status --json` `completed_steps`
  (the run so far) share a key with different scope; recorded in DECISIONS rather than renamed.
- Downloads still cost a card each inside a data root, so 7 of 17 cards were transfers; the
  request files could be read by the delegate on the host instead of downloaded, which is a skill
  question for Lane E.
- When the last pipeline step is an operator ticket, the run completes inside `submit`, so
  `run --deliver` has nothing to attach to; `submit --deliver` would close that gap (J2).
- The mock dispatch harness reads response files it did not write, so `--responses` is testable
  end to end by harvesting the mock's own replies from a sibling project and re-noncing them.

## Altered

Nothing at contract level. The brief template's `sx` helper no longer promises a `stdin`
parameter; the responses document goes through a quoted heredoc.

## Verify

    uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && scripts/check_no_biology.sh
    uv run python integrations/claude-science/render_brief.py <dir> --provider protseq --method <url>@v0.1.2 --pipeline toy --declare

## Open

1. `declare --check --print-hashes` (backlog J1), the one 3.2 row not built.
2. Lane A step 2 (E1 and E2: `design` and `objective` in the job JSON, `considered_set`), then
   step 3 (review page) and step 4 (re-tag and reinstall on both machines; the toy method repo
   needs a tag for its titled pipelines).
3. Lane E opens: the owner runs the prepared test drive (`hosts/protseq-track1b-drive.md`:
   republish the operator skill, then one `toy-compare` project on `toy-engine`); the next session
   writes its note and the measurement row from the agent's report and the four `deliver/` files.
4. `templates/method-repo/README.md` still lacks the 3.1 all-engine paragraph (Track 1a text).

# PROTSEQ exit run: tooling, declare skill, chained projects

## Goal

The PROTSEQ half of the Phase A exit (build plan, "Phase A exit"), with step 3 of
`spec/declarations-and-objectives.md`: install the tooling on PROTSEQ, then run the toy from a
Claude Science session as two chained projects whose declarations the agent drafts from Jim's
brief and a sample manifest.

## Done

- Tooling on PROTSEQ, by Jim from `integrations/claude-science/hosts/protseq-setup.md`: apptainer
  1.5.3 (PPA, sudo), uv, engine checkout and toy method (`v0.1.2`) cloned under
  `~/mytools/stringency/`, engine installed per user with `scripts/install.sh --prefix
  ~/mytools/stringency/engine --link-bin ~/.local/bin`, SIF at `~/envs/toy-py.sif` (the path the
  manifest pins), checksum verified. E3 done. Exit area
  `/data/lab/projects/2026-09_stringency-exit_jrrose5/` with `data/groups.csv`,
  `data/samples.csv` (unit, group), parents `process/` and `compare/`.
- Session texts rendered with `render_brief.py` and patched by hand (image check in Phase 0,
  declare-skill hand-over as Phase 1): `hosts/protseq-exit-run.md` is the walkthrough; briefs and
  contexts as used are in `examples/protseq-chain/`. Both skills published to Jim's instance from
  the PROTSEQ checkout (`download` returns a transfer dict; an existing skill needs
  read-then-replace). README and operator skill text corrected (I9).
- Project 1 `toy-process` (pipeline toy-process, run `01M2GH5BY478331H517CV7BK1Z`): the skill
  drafted from the brief and manifest, asked three questions, `declare --check` clean first time,
  `init --drafted-by agent`, confirm accepted `via: tty`, one operator ticket, delivered
  `01_filter.object.csv` with sidecar. 12 approval cards.
- Project 2 `toy-compare` (pipeline toy-engine, run `01M2GJRNPDFVVWJ4GW76M44Q9W`): input bound to
  the delivered table with `derived_from` from the sidecar; `init` verified it; the run captured
  it; the methods paragraph names the upstream run. Two engine-run container steps, two tickets,
  one dispatch answered by three fresh delegates (unanimous, no flag hold), delivered
  comparison table, group labels, report. 26 approval-gated calls.
- Trace checked directly on PROTSEQ, not from the agent reports: `stringency.yml` `declarations`
  block (`drafted_by: agent`, harness, session_ref, brief); confirm hold context with
  `brief_blake3`; reviews `via: tty`; runs row with host, harness, session ref; executions for
  all five steps with `env: verified`; `captures.derived_from` at run open.
- `spec/improvements.md`: H4 tested, E3 done, new section I (eleven rows). Examples and reports
  in `examples/protseq-chain/session-reports.md`. Memory notes updated.

## Learned

- The engine held at every point the design says: `init.question_unsupported` blocked a
  processing objective on the comparison pipeline at `declare --check`, before anything existed;
  `run` after completion was refused with 16; `derived_from` was verified against the sidecar.
- The declare skill translates rather than invents. Jim left the replicate out of the brief on
  purpose and the skill asked. Its gaps are information it lacked: the file shapes (it read
  engine source), whether a manifest becomes an input, the `min_n_per_group` default, and where
  deliverable names come from (it picked `consensus` over `group_labels`). Section I.
- Operators misread silence. `run` issuing a ticket for step 2 with no mention of step 1 led the
  agent to report step 1 as "satisfied from `derived_from`". The trace says it ran. `run` should
  print what the engine completed (I8).
- Claude Science mechanics: `c.download` returns `{local_path, bytes, sha256}`; `host.skills.edit`
  creates only, replacement needs the current body; data roots are a per-provider list of paths
  under which downloads need no card; the project context is a per-project field. A reused Claude
  Science project works for successive stringency projects if the context names the directory
  "as given in the session brief".
- Both wrong-brief incidents were the owner attaching the wrong file, not the skill; the second
  was caught by the engine. Recorded as it happened rather than restarted.
- The judgment step produced no flag hold this time (BMESEQ flagged `judg.confidence_consistent`
  on the same module); three delegates gave three self-descriptions of one profile, all
  `claude-opus-5`.

## Altered

Nothing in a frozen contract. Docs only: README publish steps, operator skill mode B paragraph,
new `hosts/` directory with machine-specific texts, new example directory.

## Open

1. Section I of `spec/improvements.md`: skill text I1 to I5; code I6, I7, I8, I10.
2. Tag `v0.1.0` (Phase A exit is now complete on both machines), make the repo public, install
   from the tag on both machines (BMESEQ's install is still pre-backlog), push the singlecell
   skeleton, update design 10.4 text. Toy method `v0.1.2` has no remote; the `/data-raid` mirror
   is at `v0.1.0`.
3. G2 and H5 stay design questions. A5 on its trigger.
4. Planted controls still unscored.

## Verify

```
cd ~/github/stringency && uv run pytest -q && uv run ruff check . && uv run mypy
ssh protseq 'export PATH=~/.local/bin:$PATH; cd /data/lab/projects/2026-09_stringency-exit_jrrose5/compare/toy-compare && stringency status && cat deliver/*/methods.md'
```

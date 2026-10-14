# The plan documents refreshed, and the code review folded into the backlog (W0)

## Goal

The owner, the day the Xenium method had taken Lyons CLP v2 from QC to annotated cells: spend the
next effort on the project as a whole. Two inputs: an independent code review of the three
repositories (`~/mytools/stringency/code-review-Oct142026.md`, 2026-10-14; maintainability and
user experience; verdict: the architecture is sound, no redesign) and the owner's ask to refresh
the plan documents, which were stale and hard to track. A plan of eight work items W0 to W7 was
approved in the same session; this note is W0 and records the file-level shape of W1 to W7 so the
roadmap can stay short.

## Done

- `spec/plans/roadmap-2026-10.md`: the lane table (A, I, E, F, H, J, G, B, egress), one paragraph
  per lane, "How the plans are kept", the design amendment texts the owner approves in one sitting
  (2.5, 2.6, 14.1, 10.3; 10.1 and 10.2 drafted after the Codex survey), and verification.
- Archived with headers: `roadmap-2026-09.md`, `engine-v0.2.7-plan.md`; live references in
  `CLAUDE.md`, `README.md`, design section 0, and three plans now point at the new roadmap.
- `backlog.md`: done rows K1, K2, K7, K8, L8, L10, L12 to L23 moved to `spec/archive/backlog-done.md`
  with their ids; L28 to L34 added (compatibility `requires`, plugin version in provenance,
  `probe`, image root, decision points in the skills, the onboarding sprawl, harness flexibility);
  scheduled rows tagged with their work item.
- Status lines dated 2026-10-14 on every live plan. `console-and-fleet-plan.md` opens with "What
  is open" (its 8.5 moved up) and says what is released. `spatial-method-plan.md` carries Lyons v2
  as decisions 21 to 25, copied in from the session plan that lived outside the repository.
  `ux-two-audiences.md`, `confirm-once.md`, `judge-sources-plan.md` (S1, S2 to Lane J),
  `egress-and-remeasurement.md` (L3 to Lane J), `bulkrna-plan.md`.
- `spec/README.md` rewritten. Method `PLAN.md`: a three-line status, a dated history list, items
  5.12 to 5.17 (the review's method items), section 5's heading no longer cites a path outside the
  repository. Plugin READMEs: singlecell is 0.5.0, not a skeleton; the per-package README opens
  with what it is now.

## The work items, file by file (the roadmap names them; this is the detail)

What the code does today was read, not assumed; the paths are the ones to change.

- **W1, fork inherits its parent's parameters (L27; engine 0.2.17).** `fork.py` copies no
  `actions` rows (its docstring says it reads them); `runloop.py` line 329 to 332 passes only the
  `--set` delta to `steps.propose`, and `actions.build_action` fills the rest from defaults. Build
  `fork.inherited_params(rc, step_id)` walking `runs.parent_run_id` to the latest `actions` row
  (the query of `summary.py` 74 to 77); label those values `inherited`, the delta `fork`, the rest
  `default`; `cli/verb_propose.py` starts from the same; `fork` prints every re-run step's
  parameters with their source, `fork --check` prints and opens nothing; `console.py` 491 to 496
  renders the nested delta. `param.agent_proposed` untouched. Tests in `test_controls_fork.py`
  (a non-default accepted parent value; a grandchild; `--check` writes nothing). Design 2.6.
- **W2, parameters at init and the hold view (L24 to L26; 0.2.18).** `objective.yml` `params:`
  (`config.Objective`, validated in `project._init_in`, "Parameters declared" in `echo.generic_echo`,
  label `declared`, `review_serve._decision_rows` reads the source from the action);
  `present._rows_from_table` and `_captions` skip leading `#` lines; `hold_view` `where:
  {column, equals}` with `$param.<name>` through `present._marked_value`, filtered after
  `render_items` reads rows. Design 2.5; `spec/method-skills.md` section 2.
- **W3, compatibility and CI (L28 to L31; 0.2.19, plugin 0.5.1, method rc14).** `policy.Policy`
  gains `requires`; a comparator for `>=`, `<`, `==`; checked in `lint_path`, `declare --check`,
  `init`, run open. `StringencyConfig.plugins`; the captures event carries the installed plugins;
  `index.json`, `coverage.md`, `methods.py` name them. `stringency probe` (`cli/verb_probe.py`,
  `probe.py`) replaces the brief template's shell probe. `ApptainerExecutor.image_for` resolves a
  bare name through `$STRINGENCY_IMAGES`, `~/.config/stringency/config.yml` `images_root`, the
  method's `envs/`. `install.sh` computes the label. `compat/known-good.yml` and
  `.github/workflows/compat.yml`. Plugins repo: `ci.yml`, `pytest.mark.institutional`, the engine
  pinned to a tag in `tool.uv.sources`, `VERSION` tested against `pyproject.toml`,
  `spatial.coords_missing@2` per region, `sc.decision_unreviewed` treats `inherited` and
  `declared` as reviewed. Method: `requires`, `flag-outlier-punches` reads `design` from the job
  JSON (PLAN 5.12), `ci.yml` beside `image.yml`.
- **W4, shared method code (L7; 0.2.20, method rc15).** `Job.ro_bind_paths`, `job_for` fills it
  with the method root, `bind_set` keeps the module bind nested, `operator_line` carries it; no
  provenance field (the checkout's SHA and dirty check at run open pin it). Method: the `rlib/`
  copies, `qc_plots.py` copies and `sync-rlib.sh` go. Design 10.3.
- **W5, install and onboarding (L33).** `docs/install.md`, `docs/onboarding.md`,
  `docs/method-author.md`; `integrations/claude-science/` trimmed, `hosts/` historical files to
  `hosts/archive/`; the skills' lookup through `probe`, `STRINGENCY_HOME` and the shared path; the
  method-repo template with the toy's pipeline, two modules, a delivery skill, the hook and the CI
  workflow; `synthetic_run.sh` as the smoke test.
- **W6, the Xenium analysis skill (L32; method rc16).** `.analyze.yml` `decisions:`; the template's
  "Decisions the operator proposes" and the operator skill's section 9 kept identical by
  `test_render_skill.py`; `skills/xenium-upstream.analyze.yml`; `controls/synthetic_upstream.sh`
  with planted cell types; an acceptance run by someone other than the developer, measured.
- **W7, harness flexibility (L34; waits on the owner).** H1 a survey of Codex CLI on PROTSEQ
  (`integrations/codex/README.md`); H2 the skills split into a harness-neutral core and per-harness
  appendices, `render_skill.py --harness`, `operator_id.py` recognises Codex; H3 the
  `openai-compatible` adapter (judge-sources S1) and a `command` adapter (the engine runs a
  configured command per replicate against the request file: `codex exec`, headless Claude Code),
  L3 with them. Design 10.1, 10.2.

Owner decisions taken in the session: the roadmap is replaced, not edited; init parameters live
in `objective.yml`; `probe` is a verb; W7 waits.

## Learned

- Four install locations are written across thirteen documents, and the operator skill's lookup
  never checks the shared one; a reader cannot tell which is current. The thirteen are listed in
  backlog L33.
- No `*.analyze.yml` exists for a real pipeline; the operator flow for `xenium-upstream` (two
  `run --until` stops and two proposals) is described only in a stale pipeline header comment.
- The trace records the engine version and the method SHA and no plugin version anywhere.
- A plan that lives outside the repositories (the Lyons v2 session plan) is invisible to the next
  session; its decisions are now section 8 of the spatial plan.

## Altered

- Nothing at the contract level. The roadmap is a new file and the old one is archived (owner's
  choice). `CLAUDE.md` names `roadmap-2026-10.md`.

## Open

- Commit W0 in the three repositories when the owner says so (engine: spec, notes, CLAUDE.md,
  README; method: `PLAN.md`; plugins: two READMEs).
- The owner's approval of the amendment texts in the roadmap's "Needs the owner"; then W1.
- W7 waits on the owner's go and a Codex login on PROTSEQ.

## Verify

    grep -n '^\*\*Status 2026-10-14' spec/plans/*.md | wc -l    # 8
    grep -rn '~/.claude' spec/plans/ spec/README.md             # nothing
    sed -n '/^| id /,/^$/p' spec/plans/backlog.md | cut -d'|' -f2 | tr -d ' ' | tr '\n' ' '

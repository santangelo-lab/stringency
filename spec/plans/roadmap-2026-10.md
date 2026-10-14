# stringency: roadmap after the first full method (2026-10-14)

Working note, not the spec. Successor to `spec/archive/roadmap-2026-09.md` (approved 2026-09-14,
archived 2026-10-14 with every lane's history inside it). Written the day the Xenium method had
taken Lyons CLP v2 from QC to annotated cells under the engine, from two inputs: the owner's ask
to spend the next effort on the project as a whole, and an independent code review of the three
repositories (`~/mytools/stringency/code-review-Oct142026.md`, 2026-10-14) aimed at
maintainability and user experience. The review's verdict: the architecture is sound; what is
needed is correctness, integration reliability, maintainability and UX, not a redesign. The
work is eight items, W0 to W7, named in the lane paragraphs below; their file-level detail is in
`notes/2026-10-14-1500-plan-refresh-and-review.md`, and the backlog rows they close are the record.

**Status 2026-10-14.** Written. W0 (this refresh), W1 (fork inheritance, engine v0.2.17, L27) and W2 (declared parameters, the commented CSV, the hold-view filter; v0.2.18, L24 to L26) and W3 (`requires`, plugins in provenance, `probe`, images by name; v0.2.19, L28 to L31; plugin 0.5.1; method rc14; CI in all three repositories) W4 (the method checkout bound read-only, v0.2.20, L7; the method's copies gone in rc15) W5 (the three guides, the archive of the host notes, the skills' lookup; L33) and W6's build (decision points in the skills, `stringency-analyze-xenium-upstream`, the synthetic upstream run; L32; method rc16) done the same day. Open: W6's acceptance run by a non-developer, after the owner's pushes, install and republish. W7 waits on the owner.

## How the plans are kept

- This file's table is the only place lane state is written. A session that changes a lane's state
  edits the row and the lane's paragraph, nothing else.
- Every live plan under `spec/plans/` opens with a dated **Status** line. A plan whose work is done
  or superseded moves to `spec/archive/` with a header saying why and what succeeded it; nothing in
  `archive/` is an instruction to a session.
- `backlog.md` holds open items not owned by a lane; done rows move to `spec/archive/backlog-done.md`
  keeping their ids, since notes and the trace cite them.
- `spec/README.md` maps the directory; `notes/INDEX.md` is the session map. Both are updated in the
  same commit as the change they describe.

## Where things stand

Engine `v0.2.16`, installed on PROTSEQ as `0.2.16-sc0.5.0`. Plugin singlecell `0.5.0`. Method
`stringency-xenium-method` `v0.6.0-rc13` (tagged 2026-10-14, not yet run under the engine). Lyons
CLP v2 (`/lab/projects/Lyons_CLP/v2_rosc_controls/`): `qc_all` and the four `upstream_*` organs
delivered on rc12 and rc12.1 (2026-10-08 to 2026-10-12).

| lane | state | plan | next |
|---|---|---|---|
| A engine | open; W1 to W4 done (v0.2.17 to v0.2.20; not yet installed) | this file; `backlog.md` | `confirm-once.md` (L5, L6) when the owner asks; the engine side of W6 (the template's decision-point section) |
| I integration and CI | W3 done 2026-10-14 (engine v0.2.19, plugin 0.5.1, method rc14; `compat/known-good.yml` row) | this file | the owner's push, the plugin's `uv lock` and tag, the install `0.2.19-sc0.5.1`; then the lane keeps `known-good.yml` current and adds the synthetic upstream run (W6) to CI's institutional list |
| E skills and onboarding | W5 done; W6 built 2026-10-14 (method rc16; the synthetic upstream passes) | this file; `ux-two-audiences.md` (history) | the acceptance run: someone other than the developer runs the synthetic analysis through `stringency-analyze-xenium-upstream` with limited intervention, measured in the backlog's table; before it, the owner's pushes, the install `0.2.20-sc0.5.1`, and the republish of the operator, declare and analysis skills |
| F spatial method, Lyons CLP | active; F6 delivered 2026-10-12; rc14 to rc16 tagged 2026-10-14 (W3, W4, W6) | `spatial-method-plan.md`; method `PLAN.md` | the first real-data run on rc16 (which holds rc13's resolution step, `requires`, the group bands, the shared code and the analysis skill; the synthetic run already exercised the engine path); F7 the owner reads `cell_types_mouse@2`; F9 niches |
| H console | released (v0.2.8 to v0.2.16), second cut unscheduled | `console-and-fleet-plan.md` "What is open" | batch cards (L6), the delivery gallery, the decision history, the resource cap, when the owner asks |
| J harness flexibility | **proposed**, waiting on the owner | this file (W7 in the working plan) | H1 a survey of Codex CLI on PROTSEQ once the owner has it logged in; then the operator skills split into a harness-neutral core, and the `openai-compatible` and `command` judgment adapters |
| G judge sources | proposed, not started | `judge-sources-plan.md` | its S1 and S2 (the `openai-compatible` adapter, the Ollama evaluation) move to J; the panel specification and the remaining decisions of its section 6 stay here |
| B bulk RNA-seq | dormant since 2026-09-23 | `bulkrna-plan.md` | nothing until the owner reopens it |
| egress | unscheduled; the gate before the first PROTECT project | `egress-and-remeasurement.md`; backlog L1 to L4 | L3 (the judge on control results) is pulled into J; the rest waits |

## The lanes

**A, engine.** Serial, owns `src/stringency/`. The three engine items the review ranked first are
defects the Lyons v2 runs exposed: a fork rebuilds every re-run step from pipeline defaults and
drops the parent's accepted parameters (L27, the spleen re-fork of 2026-10-12); no parameter can
be set at init, so every upstream project opened an organ sign-off hold after the confirm (L24);
a hold page cannot filter a table by the proposed value and draws a commented CSV as empty (L25,
L26). Then the executor binds only the module directory, so the method copies its R library into
every module (L7). Each is one session and one release, in that order. After them, `confirm-once.md`.

**I, integration and CI.** New lane from the review. No file declares which engine and plugin a
method needs; the trace records the engine version and the method SHA but no plugin version;
there is no preflight verb; image paths are absolute; the plugin repository has no CI and the
method repository tests only its image builds. W3 adds `requires:` to the method's `policy.yml`
(checked by `lint`, `declare --check`, `init` and run open), records the installed plugins in
`stringency.yml`, the run's captures event and the delivery, adds `stringency probe`, lets a
manifest name an image by file name resolved against a site image root, computes the install
label, and gives all three repositories a CI that runs on a bare runner (lint, unit tests, the
skill check), with the container runs kept institutional and said to be. A `compat/known-good.yml`
in the engine repository is the documented supported combination.

**E, skills and onboarding.** The install location is written four ways across thirteen
documents; the operator skill cannot find the shared install; no real pipeline has an analysis
skill, so every Xenium run needs someone who knows the CLI. W5 writes `docs/install.md`,
`docs/onboarding.md` and `docs/method-author.md`, archives the historical host notes, fixes the
skills' lookup, and gives the method-repo template a worked example. W6 writes
`stringency-analyze-xenium-upstream` (the skill a person loads by describing their experiment),
teaches the template and the operator skill how the operator proposes a decision point (`ndim`,
`resolution`), builds a synthetic end-to-end run of `xenium-upstream`, and ends with a run by
someone other than the developer, measured as the toy was.

**F, spatial method.** `spatial-method-plan.md` is the plan; F6 delivered as Lyons v2 with ROSC
controls, whose decisions are now in that plan's section 8 (21 to 25). Method `PLAN.md` carries
the module items. Next is the data side's: one organ on rc13 through the engine and the console,
before W6's acceptance run uses that pipeline; then F7, F9 on.

**H, console.** Built and running (`stringency-console.service`, loopback 8765). The second cut
is listed under "What is open" in its plan and starts when the owner asks for it.

**J, harness flexibility.** The owner's objective of 2026-10-14: the lab has an OpenAI Codex team
plan; open Codex as a harness and build in as much flexibility on the harness side as possible.
Design 10.1 names two roles, and both open: the operator harness (what drives the CLI) and the
judgment harness (how a prompt is answered). Proposed: H1, a survey session of Codex CLI on
PROTSEQ (what it exports, its skill format, whether `codex exec` returns structured output
against a schema, what its sandbox restricts); H2, the operator and declare skills split into a
harness-neutral core with a per-harness appendix, rendered per target; H3, two direct judgment
adapters, `openai-compatible` (judge-sources S1) and `command` (the engine runs a configured
command per replicate against the request file; `codex exec` and headless Claude Code first),
with L3 so control results name the judge. Waits on the owner: Codex logged in on PROTSEQ, and
the go-ahead.

**G, judge sources.** Unchanged except that S1 and S2 move to J.

**B, bulk RNA-seq.** Dormant, kept as written.

## Needs the owner

Design amendment texts for one approval sitting. Each is built only after approval; the backlog
row names the item.

1. **2.5 Objective (L24, W2).** Applied 2026-10-14 with the build (the owner chose this form in the planning session); say so if it should read differently. Add: "An objective may carry `params: {<step>: {<parameter>:
   <value>}}`, values declared before the run for parameters the pipeline declares. `init` validates
   each against the pipeline and the module's schema, the echo-back lists them under 'Parameters
   declared', and the confirm hold covers them as it covers the rest of the file. A declared value
   is recorded with `param_source: declared`; it opens no `param.agent_proposed` hold, and
   `param.locked_changed` and `param.out_of_range` apply to it as to any value."
2. **2.6 Runs and forks (L27, W1).** Applied 2026-10-14 with the build on the owner's "continue on"; say so if it should read differently. Add: "For every step it re-runs, a fork inherits the
   parameters its parent admitted (through forks of forks), recorded with `param_source: inherited`;
   `--set` overrides only what it names (`fork`); a parameter neither inherited nor set takes its
   default. `fork` lists every re-run step's parameters with their source, and `fork --check` lists
   them without opening a run."
3. **14.1 Verbs (W1, W3).** Applied 2026-10-14 with the builds (the owner chose the verb in the planning session). `fork` row gains `[--check]`. New row: `probe` with
   `[--method <path|url@tag>] [--json]`: the engine version and install path, each plugin and
   version, the container runtime, and with `--method` each manifest image resolved and verified,
   the method's `requires` against what is installed, and the installed skills' version; exit 0
   when every check passes, 1 otherwise; reads only.
4. **10.3 Execution families (L7, L31; W3, W4).** Both sentences applied 2026-10-14 with the builds. Add: "An engine-run step also sees the project's
   `method/` checkout, bound read-only, so shared code beside the modules is reachable; the checkout
   is at a recorded SHA and checked for dirtiness at run open, so that code is pinned as the module
   scripts are." And: "An `image` in the environment manifest may be a bare file name, resolved
   against `$STRINGENCY_IMAGES`, then `images_root` in the user's `~/.config/stringency/config.yml`,
   then the method's `envs/` directory; an absolute path is used as given."
5. **10.1 and 10.2 Harnesses (J, W7).** Drafted after the H1 survey; waits.
6. **DEVIATIONS, `judgment.sign_off`** (engine 0.2.14): still "Awaiting acknowledgement by Jim".

Also the owner's: Codex CLI logged in on PROTSEQ for H1; installing each engine release and
restarting the console; republishing the operator, declare and analysis skills to Claude Science
after W5 and W6; the rc13 run on real data before W6's acceptance test, and the tester for it;
K6 tag cleanup and the toy method's GitHub remote.

## Verification

- Engine, after each release: the suite, ruff, format, mypy and the no-biology check green in
  `.venv-test`; one test per backlog row closed; DECISIONS entry; backlog row moved to done.
- W1 on real data: `fork --check` on the Lyons v2 spleen run `01M4R92YK8KEB8WEWSZFQT1XM1` lists
  ndim 40, igraph_leiden and resolution 0.6 as inherited, and opens nothing.
- W3: CI green in all three repositories; `probe --method` on PROTSEQ passes at the known-good
  combination; a `lint` against a method requiring a newer engine fails naming both versions.
- W5: a reader following `docs/install.md` alone reaches a passing `probe` and a delivered
  synthetic `xenium-qc-tma` run; no live document names `/usr/local/lib/stringency`,
  `/home/jrrose5` or a `bmeseq:` clone.
- W6: `render_skill.py --check` and `stringency lint .` clean; the synthetic `xenium-upstream`
  delivers; the acceptance run's row in the measurement table.

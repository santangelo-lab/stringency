# Judge sources: local models, API models, mixed panels

A plan note, drafted 2026-09-23 from a brainstorming session with the owner. Not the spec. It
proposes execution-level work under design 10.1, 10.2 and 17, one design amendment (a panel
specification), and one evaluation. Items marked *design* change design text and need the
owner's approval; the rest are DECISIONS-level. Section 6 lists the decisions the owner is asked
to make; section 7 the order.

**Status 2026-10-06.** Proposed (Lane G), not started; waits on the seven decisions in section 6. S2(b)'s answer key now exists: `qc2_outliers_all` run `01M492CYVV7JBT69W85MXZY8AF` (2026-10-06), the owner's verdicts on the same six punches as September.

## 1. The question

The owner wants the engine to source judgment agents from many places: delegated subagents of
the operator session, fixed local models on the PROTSEQ GPU, and hosted APIs. Nothing in the
commandments, the backlog or the roadmap covers where judges come from; Commandment 5 asks only
for three or more replicates. This note records what exists, what is missing, why a fixed local
judge is worth more here than a budget saving, and the order to build in.

## 2. What exists (engine `v0.2.4`)

Design 10.1 separates the *operator harness* (whatever drives the CLI) from the *judgment
harness* (how a rendered prompt gets answered). The judgment harness is a protocol in
`src/stringency/harness/base.py` with two families:

| family | mechanism | adapters | `isolation` recorded |
|---|---|---|---|
| direct | the engine calls the model in-process, once per replicate | `api` (Anthropic Messages, `schema.json` as structured output), `mock` | `enforced` |
| dispatch | the engine writes `req_N.json`, exits 20; the operator has one fresh subagent answer each; the engine collects on the next `run` | `subagent`, `mock` | `as_reported` |

Every invocation, whichever family, lands in the same append-only `invocations` row: model
requested and resolved, harness kind and version, `via`, `isolation`, nonce check, the judge's
`reported` block verbatim, `sampling_json`. Consensus, holds, gates, review and coverage all read
that shared record, so the choice of judge source changes how the trace is marked and nothing
else. Every real run so far (Lyons CLP, the toy exits) was judged by three Claude Science
delegates self-reporting `claude-opus-5`.

What is missing:

- **`openai-compatible` is a stub.** It is in the `JudgmentHarness` enum (`config.py`) and
  `harness_for` (`judgment.py`) raises "deferred (design 17)". Design 17's trigger is "the Qwen3
  evaluation". Ollama `0.32` is installed on PROTSEQ with `qwen3:8b`, `qwen3:32b` and a 27b
  variant pulled; the GPU is idle when Brian is not loaded.
- **One harness per project, bound at init.** `judgment_harness` sits in the read-only
  `stringency.yml`. Every Lyons project is bound to `subagent`. No per-module or per-step
  override of the harness exists; `module.yml` carries only a `model` alias for direct harnesses.
- **Panels are homogeneous.** All replicates come from one adapter and one model. `consensus`
  treats replicates as anonymous exchangeable samples. A mixed panel is not expressible.
- **No project-level model or sampling fields.** `ApiHarness` hardcodes its default model;
  `Sampling` has `temperature` and `max_tokens` but only `model` is ever set.
- **Judge identity is not shown to reviewers.** The review page and `present` show replicate
  labels, confidence and rationale but not which model produced each. The coverage report prints
  "model as reported".
- **Under dispatch, identity is self-reported and unverified.** The `reported` block is stored
  and trusted for nothing except the trace (design 10.2). When the operator relays answers with
  `run --responses`, it hand-carries the JSON.
- **The operator may judge itself.** The operator skill's fallback ("if you have no delegate
  tool, answer each request in its own fresh cell and say so") is the one path where operator and
  judge share a context. The design does not name it.

## 3. Why a fixed local judge matters beyond budget

Design 10.1 chose `subagent` for budget reasons and accepted `as_reported` isolation as the
price, with the eval controls as compensation. A local direct adapter reverses the trade at no
API cost:

1. **Isolation becomes `enforced`.** The engine controls the prompt, the context and the call
   count. All three properties in the design 10.1 table (exact evidence bundle, no session
   expectations, independent replicates) move from "reported" to "by construction".
2. **Provenance becomes pinnable.** Ollama exposes a weights digest per model tag. Recording it
   as `model_resolved`, with temperature 0 and a seed in `sampling_json`, gives a judge that can
   be re-run in a year. `bit_reproducible` stays false; the claim is "pinned", not "identical".
   This is the judge-side analogue of the `/lab/ref` rule: pin the version, do not float.
3. **Data stays on the machine.** For anything under `/data/protect`, both the Anthropic API and
   Claude Science delegates send evidence tables off-site. A local judge is the only path that
   keeps PROTECT judgment on PROTSEQ. Rule proposed in section 5.
4. **Model diversity.** Today the operator and every judge are one model family, so correlated
   blind spots pass unanimity. A second family in the panel is the one form of independence the
   current design cannot offer.

The cost is competence. A 32b open model may abstain or split more on domain tasks such as the
outlier judgment, which means more holds for the reviewer. That is measurable (section 4, S2),
not a matter of opinion.

## 4. Steps

### S1. Build the `openai-compatible` direct adapter [engine, DECISIONS-level; design 17 trigger met]

- `src/stringency/harness/openai_compat.py`, a near copy of `api.py`: `base_url`, `model`,
  `response_format: {type: json_schema, json_schema: {schema, strict: true}}`, `temperature`
  and `seed` from `Sampling`. Ollama's local endpoint (`/v1`) is the first target; vLLM and any
  other OpenAI-shaped server follow for free. Optional extra `stringency[openai]`, mirroring
  `stringency[api]`.
- `model_resolved`: the response's `model` string plus, when the server is Ollama, the weights
  digest from its show endpoint, recorded as `<tag>@<digest>`. Anything the server does not
  report is `unknown`, never guessed (design 10.2).
- Config, additive: `judgment_harness: openai-compatible` plus a new optional
  `judgment:` block in `stringency.yml` with `model`, `base_url`, `temperature`, `seed`; `init`
  gains `--judgment-harness`, `--judgment-model`, `--judgment-base-url`. `api` reads the same
  block so its hardcoded default becomes a fallback. `stringency.yml` stays read-only after
  init; changing the judge is a new project or (S4) a recorded run-level override.
- Tests against recorded responses only, as for `api` (`CLAUDE.md`: no network in tests). A
  refusal path for a server that ignores `response_format` (structured output absent: the
  invocation is invalid with `error: "server returned no structured output"`, not silently
  parsed).
- Operational: the operator skill checks `nvidia-smi` for resident processes before a local run
  and caps Ollama's memory when Brian is loaded (host context, GPU section).
- Estimate: one session.

### S2. The Qwen3 evaluation [method and owner; no engine change]

Two parts, both against fixed answer keys.

(a) **Harness fixtures and the toy.** Run `label_groups` (toy) under `openai-compatible` with
`qwen3:32b` and `qwen3:8b`, then the toy's negative control (shuffled group labels). Record
schema validity rate, `judg.evidence_exists` and `judg.numeric_claims_match` pass rates,
abstain rate, agreement with the known labels, latency.

(b) **The Lyons outlier judgment.** The clean second judgment of `qc_outliers_all` is already
Lane F phase 0 (module bump, new run). Run it twice: once under `subagent` as planned, once
under `openai-compatible` with `qwen3:32b`, in a sibling project so the trace of each is whole.
The owner's seven decided holds from the first run are the answer key. Compare each panel's
consensus labels to the owner's verdicts, the hold count each panel would have opened under the
current policy, and per-item confidence.

Competent means: agreement with the owner's verdicts at least equal to the Claude panel's,
schema validity above 95 percent, and the negative control abstaining or splitting rather than
labelling. Two further endpoints, borrowed from ClawBio's lifecycle page
(`egress-and-remeasurement.md` part 2): over-answer rate on ill-formed evidence once the
`ill_formed` control kind exists, and abstention stability across the three replicates, which
is computable from the `judgments` table today. Rule: this definition is committed before the
evaluation runs and is not revised to fit its result. Results go to `backlog.md` measurements. If the local judge is not competent at 32b,
S4 is designed for asymmetric roles (a local judge as a fourth, non-voting check) rather than
interchangeable votes.

Estimate: one session plus the Lane F phase 0 run it rides on.

### S3. Show judge identity to reviewers [engine, low, DECISIONS-level; independent of S1]

Render `harness_kind`, `model_resolved`, `isolation` and `via` per replicate on the review
page, in `present --hold`, in the hold packet, and in `summary.md`. The data is already in
`invocations`; this is a renderer change plus one golden update. A reviewer weighing replicate 1
against replicate 3 should see whether they came from the same model.

### S4. Panel specification [*design*: amends 10.1, 10.2, the `stringency.yml` example in 2.x, and 17]

Replace the scalar `judgment_harness` with a `panel` of judge slots:

```yaml
panel:
  - harness: subagent                 # dispatch family
    count: 2
  - harness: openai-compatible        # direct family
    model: qwen3:32b
    base_url: http://localhost:11434/v1
    count: 1
    role: vote                        # vote | check   (check: recorded, shown, not counted)
```

- `judgment.replicates` in `module.yml` becomes the minimum the module requires; the panel
  supplies the count. Lint refuses a panel smaller than the module's minimum.
- `consensus.decide` is unchanged for `role: vote`. `role: check` replicates are recorded and
  rendered (S3) but excluded from agreement; a check that disagrees with the vote consensus adds
  a consensus note, and under `profile: strict` opens a `run_disagreement` hold.
- Mixed families in one step: the engine runs the direct slots first, records their invocations,
  then writes the dispatch requests for the subagent slots and exits 20. The `dispatching` state
  must therefore hold a partially completed panel; on resume the engine collects only the
  dispatch replicates. This is the one non-trivial engine change and the reason S4 waits for S2.
- The `role` field is the hook for judges that cannot cite evidence (section 8, tabled). It is
  reserved now so the schema does not change twice.
- `judgment_harness: <kind>` remains valid as shorthand for a one-slot panel of the module's
  replicate count, so existing projects and tests do not change.

### S5. Close or mark the operator-judges-itself path [skill and engine, DECISIONS-level]

Either remove the fallback from the operator skill, or keep it and have `run --responses`
require `reported.agent` to differ from `STRINGENCY_OPERATOR`, recording `via: operator` and
`isolation: none` when it does not, and refusing under `profile: strict`. Recommendation: the
second, because a session with no delegate tool still needs a way to finish, and the trace
should say what happened.

### S6. Per-module harness override [*design*: module contract; via `DEVIATIONS.md` or an amendment; low]

`module.yml` `harness:` beside the existing `model:`, so a high-stakes judgment step can demand
a direct adapter while routine steps use the project's panel. Deferred until a module needs it;
S4's panel already covers the case where the whole project wants enforced isolation.

## 5. Constraints and rules proposed

- **Data routing.** Projects under `/data/protect` may bind only direct adapters whose
  `base_url` is loopback or a host inside the lab network. First written as a path check that
  refuses `subagent` and `api` under `/data/protect`; superseded the same evening by the egress
  classes and `policy.yml` `egress.max_class` in `egress-and-remeasurement.md` part 1, which
  cover the harness, module scripts and the operator runner together. The path check survives
  there as a lint warning when a PROTECT project binds a policy above class 1. Build before any
  PROTECT project is initialised.
- **GPU sharing.** The judge model shares the GPU with Brian on demand. The operator checks
  residency first and sets an explicit memory cap; no standing reservation.
- **Pinning.** A local judge is named by tag and digest in the trace. Two projects that should
  be comparable use the same digest, as they use the same genome build.
- **Tests.** No network, recorded fixtures only. The mock stays the test harness for both
  families.

## 6. Decisions for the owner

1. Approve S1 as DECISIONS-level under the existing design 17 row, or ask for design text first.
2. S2 (b): run the Lyons re-judgment under both harnesses in sibling projects, or under the
   local judge only and compare to the first run's Claude panel (cheaper, weaker: different
   module version).
3. The definition of "competent" in S2, or a different one.
4. Whether S4's `role: check` should open a hold under `strict` or only add a note.
5. S5: remove the fallback, or keep it marked as proposed.
6. The `/data/protect` routing rule in section 5: as written, or a warning rather than a refusal.
7. Where this work lives: a new Lane G (engine, serial, after Lane F phase 0 gives S2 its
   run), or folded into Lane F. Recommendation: Lane G, because S1, S3 and S5 touch the engine
   and Lane F is method work.

## 7. Order and estimates

| step | depends on | estimate | level |
|---|---|---|---|
| S3 judge identity to reviewers | nothing | half a session | engine, low |
| S1 `openai-compatible` adapter | nothing | one session | engine, DECISIONS |
| S5 mark the operator fallback | nothing | half a session | skill and engine, DECISIONS |
| section 5 routing lint | S1 | half a session | engine, DECISIONS |
| S2 Qwen3 evaluation | S1, Lane F phase 0 | one session plus the run | method, owner |
| S4 panel specification | S2 evidence, owner approval | design half a day, engine two sessions | *design* |
| S6 per-module override | a module that needs it | half a session | *design*, deferred |

## 8. Tabled: TypeSafe Jev (owner, 2026-09-23)

Assessed the same day and set aside. Jev (TypeSafe AI, early access from 2026-09-15, API-only,
closed weights, US-hosted) returns typed choices, scores and yes/no probabilities with a
calibrated confidence and no text. It fits the direct harness family without change but cannot
produce a rationale or evidence citations, so a Jev replicate fails `judg.evidence_exists` by
construction and cannot be a `role: vote` judge under the current record. Three roles were
identified if it is picked up again: a rationale-support post-gate (a Noul over evidence plus a
replicate's rationale), a `role: check` label-only vote, and pre-gate item triage. Its privacy
policy promises no training on inputs but names no retention window or DoD posture, so it is
out for PROTECT data regardless. The `role` field in S4 is reserved partly for this.

## 9. Assessed and not integrated: ClawBio (2026-09-23)

`github.com/ClawBio/ClawBio` (`v0.7.1`): a community library of about 97 single-task
bioinformatics Agent Skills (a `SKILL.md` plus an optional Python CLI writing `result.json`,
`report.md` and a `reproducibility/` folder), one lead maintainer with a daily auto-merge agent,
MIT with per-skill exceptions. Domain is consumer and clinical genomics, pharmacogenomics and
GWAS, with some bulk and single-cell RNA-seq and nf-core wrappers; nothing for Xenium or any
spatial platform. It shares stringency's rule ("the agent dispatches and explains, the skill
executes") and its abstain-rather-than-default instinct, and lacks what stringency is: a fixed
topology, a trace that outlives the session, and any structural handling of LLM judgment (no
replication, no consensus, no holds; its interpretation skills run unguarded). Its own benchmark
verdict is `pass: false`; 68 of 97 skills are "planned"; the registry is a hard-coded dict and the
MCP surface is being removed.

Three integrations were weighed. ClawBio skills as stringency modules (a shim over
`--input/--output`, `result.json` into the trace): feasible, low value while the active lane is
spatial, revisit if Track 2 wakes and only against a pinned tag under `/lab/env`. Stringency
published as a ClawBio skill: zero format cost (Lane E's skills are already Agent Skills
folders), but a distribution and licensing decision, not now. Stringency as ClawBio's judgment
layer (a `stringency_clawbio` plugin gating their interpretation steps): the right conceptual fit
and the largest scope, in their domain, dependent on their appetite; a conversation, not a build.
Decision: no integration lane. Two mechanisms borrowed into `egress-and-remeasurement.md`.

# Implementation order, November 2026: what can start without the owner, then what waits on him

Working note, not the spec. Drafted 2026-11-10 after the first benchmark slice, from three
surveys made that day: the open rows of this work list (91 open or partly open, 17 more done
but never archived), the method and plugin backlogs (scRNA-seq 26 items, Xenium about 33, the
plugin 15), and every plan document outside the work list (about sixty, in the engine's
`spec/`, loose beside the checkouts, in old worktrees, in the owner's Claude plan files and in
the method, beta and benchmarks repositories), which turned up 28 open items no row tracks and
about twenty statements that are stale or contradict another document. The owner's rule for the
order:
**what needs no input from him to start comes first.** Nothing here is built. It proposes an
order; `PLAN.md`'s "Next, in order" is rewritten from it once he has read it.

"Needs no input to start" means every decision the item rests on is already made or is below
the contract level. It does not mean it can land without him: he merges and tags. Sizes are
S (under half a day), M (a day or two), L (more).

## 1. The order in one table

| wave | what | rows | size | lands as |
|---|---|---|---|---|
| 0 | One work list again; the finished rows archived; rows for what no row tracks; stale documents fixed | housekeeping | M | docs PR on top of #25 |
| 1 | Names: a dataset's own columns and labels can be declared or proposed | L168, L161, L163 (b)(c)(d), L164, L167 | L | engine 0.2.42, method 0.1.12 |
| 2 | Hold and proposal friction from the owner's sessions; the skills kept current | L94, L107, L114, L95, L160, L110, L11, L146, L147, two new rows | L | engine 0.2.43; Xenium text at its next tag |
| 3 | Small correctness, and measurements never written up | L145, L148, L106, L80, L76, L155, L37, K3, K4, two new rows | M in all | rides with waves 1 and 2 |
| 4 | Lineage assignment and the QC predicates that need no decision | L98, L99, L117, L119, L120; method M1, M5, M2, M6, M10, M11, M12, M3 | L | plugin 0.10.4, method 0.1.13 |
| 5 | The gate review's first item | L100 | M | engine, then the Xenium decision blocks |
| then | Everything in section 7, as each answer arrives | | | |

Waves 1 to 3 are about three weeks of work for one person; wave 4 about two; wave 5 a few
days. Waves 1 and 2 do not depend on each other and may interleave.

## 2. Wave 0: housekeeping, first because everything else edits these files

**One list, and nothing finished left on it.**

- **One `PLAN.md`.** Rows L157 to L160 are on `marked-labels` (#25) and L161 to L171 on
  `benchmark-prereg`; `benchmark-plan.md` and the notes index have diverged the same way. A
  docs branch on top of #25 brings both together.
- **Archive what is done**: L93, L130 to L144, L157 to `spec/archive/backlog-done.md`; L86 after
  a check that Xenium rc26 names the egress gate; L166 (met by the runner). `confirm-once.md`
  moves to `spec/archive/` (every row closed).
- **Rewrite State, "Next, in order" and the waiting table** (dated 2026-10-21, engine 0.2.33;
  thirty rows since appear in none of them) from this note, after the owner has read it.

**Rows for what no row tracks** (the document survey's finds that are real work; each gets a
row, and its wave is named here):

| find | where it was | goes to |
|---|---|---|
| each per-item judgment request is numbered as its own replicate | Xenium `docs/open-tools-v2-plan.md` section 6; `judgment.py` still does it | wave 3 |
| the open-mode measurement table has no row, though liver, gut, spleen and lung have run | `measurements.md`; the archived open-mode plan's O2 | wave 3 |
| `render_skill.py --check` never compares with the `SKILL.md` on disk, so a stale rendered skill passes CI | Xenium pilot-triage note | wave 2, with L146 |
| a `cites:` key on a tool and an open path in the skill template | Xenium `docs/open-tools-v2-plan.md` section 6 | wave 2 |
| `qc.threshold_range`, named in the design, exists nowhere | `omicsbench-assessment.md` | wave 4 |
| the gaps #25 left: `5-10` reads as an identifier; two cited rows can be swapped; the story's rule | the marked-names note | section 7 |
| the Xenium `timepoint_factor: timepoint_h` moved to the name form | `declared-text-params.md` 7.4 | after wave 1, section 7 |
| the Lane F report and retrospective (F11, F12), which `PLAN.md` says the Xenium plan carries and it does not | `spatial-method-plan.md` | section 7 |
| design 17's two triggers that have been met: judgment tools on demand in open mode; the `reason_code` enum at fifty reviews | `stringency-design.md` section 17 | section 7 |
| `study: lyons_clp` on the Lyons projects (every one has `study: null`), and `must_cite` on two Xenium judgments | the old "Next, in order" prose | section 7 |
| a session test for a person away from the chat; the hold-to-verdict column for toy runs; `review --serve` finding projects only two levels deep | unmerged commits on `track-1h-text` | wave 3 for the last; the rest section 7 |
| SpatialBench-Long, Latch's own Xenium skill as the method-as-prompt arm, a glossary line before the Latch conversation | the owner's benchmark plan of 2026-10-21 | with SpatialBench, after scBench |
| low and filed only: `run --estimate`, a permalink per vocabulary entry, a data dictionary beside a module, a warning on an `exec` full of literal identifiers, parameter justifications reaching report modules, the console's four rough edges | `commons-assessment.md`, `omicsbench-assessment.md`, the October code review, `console-and-fleet-plan.md` 8.6 | section 8 |

- **Method backlog**: the nine scRNA-seq items that exist only in this repository's notes get
  rows in the method's `BACKLOG.md`, worded without naming an eval (L164). The five plugin
  changes that backlog rows wait on and nobody filed get rows here.

**Documents that say what is no longer so.**

- `spec/README.md`: `confirm-once` "proposed" and `decision-points` "designed" (both built),
  rows "to L127", and two plan files it does not list.
- Status lines: `judge-sources-plan.md` "proposed, not started" (three of its parts are built),
  `commons-assessment.md` "nothing built" (L36 is done), `annotation-controls.md` "the rest is
  filed" (built 2026-10-27), `DEVIATIONS.md` on egress "not built" (built in 0.2.28) and its
  pointers to files since archived.
- The benchmark text: "Phase 0 is running"; seventeen SpatialBench evals where sixteen exist;
  "Opus 5" for `claude-opus-5-5`; "no Opus 5 row exists" above a pre-registration that quotes
  one.
- Elsewhere: the Xenium `policy.yml` comment "held below 0.2.29" under `requires: >=0.2.36`
  and its `PLAN.md` pointers to moved files; the plugin README's status table (0.5.1) and its
  "scheduled" CI; `stringency-lab/maintainer.md`'s "Pending" of 2026-10-15.
- **The plan of record for the benchmark is in no repository**: the owner's document of
  2026-10-21 exists only among his Claude uploads. A copy goes beside `benchmark-plan.md`,
  which says it does not restate it.

## 3. Wave 1: names (`declared-text-params.md`, all five decisions made 2026-11-10)

In the order that note gives, with what each closes:

1. **L168** (a): `init` and `declare --check` refuse a declared value the step gate will block.
   Engine, S. With it **L161**: `declare --check` reads the site's executor as `init` does. S.
2. **L163 (b)**: the DE module reads the comparison from `objective.contrasts` and the design.
   Method, M, on the `scrnaseq-pca-pipeline` branch (0.1.12, untagged). A control on the fixture
   with its columns renamed.
3. **L164**: the benchmark commentary out of the method repository (the backlog's M2 wording,
   two changelogs, the `qc-metrics` docstring, the README, and the PCA pipeline's header and
   skill, which are phrased around one eval's question). Method, S. Before any stringency-arm
   run of QC, PCA or cell typing.
4. **L167**, by the method route: `reduce-pca` writes its two sentinels as a table beside the
   JSON, so an answer cites them without session code. Method, S.
5. **L163 (c)**: the name form in the engine: `text: column`, `text: {value_of: ...}`,
   `text: prefix`, `required`; declared under every profile, proposed under a hold where the
   profile lets the agent propose; the existence check; the hold packet showing what a name
   resolves to. Engine, design text and code, L. The design text is his to approve before it
   merges; the decisions it rests on are made.
6. **L163 (d)**: the method uses the form (`group_column`, `groups`, `keep_column`,
   `keep_value`, `batch_key`, `symbol_column`, `mt_prefix`); the skills' `decisions` entries;
   rendered again. Method, M, after 5.

Then the method is tagged and the benchmark's DE01 is run again (section 6). Left out of this
wave because they wait on him: (e) **L169** and strict-level limits **L171**.

## 4. Wave 2: hold and proposal friction (every row from a real session)

- **L94 with L107**: `propose --withdraw` for a held step; a step stranded in `proposed` by a
  crash is recoverable. The two share the proposal's lifecycle. M each.
- **L114**: an accepted hold on an open-mode tool step can complete. M.
- **L95**: the engine's own proposal checks get a hold view (the cited cells beside the
  unmatched numerals). M. After #25, since it shows what #25's rule found.
- **L160**: a person's file as a tool input in an open project (`inputs add`), which also
  closes the deferred L48. M. The design is small and is written first.
- **L110**: a person's choice at an item hold reaches `consensus.json`; the Xenium
  `apply-labels` change follows it. M.
- **L11**: a correction fork sees its parent's outputs. M.
- **L146 with L147**: the operator skill's engine line and a test that keeps it current; the
  skill says to `flag` a result a person calls wrong. S. The republish is his. With them the
  two new rows: `render_skill.py --check` compares with the `SKILL.md` on disk, so a rendered
  skill left behind its source fails CI; and the template's `cites:` key.
- Xenium text that needs no decision, at its next tag: 9.1 (answer first, offer paths after),
  1.10 (time points and ids in words), the pytest import (N1), the synthetic study re-run
  under the current engine (N2).

## 5. Waves 3 to 5

**Wave 3, small correctness**, each S unless said: L145 (the absolute tolerance that lets a
tiny p value match), L148 (`audit` counts flags), L106 (an immutable Action, M), L80 (the
synthetic Xenium run on CI's list), L76 (the console measurement written up), L155 (the beta
CLI's transcript flags), L37 (`review --export`, M), K3, K4; and three of the new rows: a
per-item judgment request no longer counted as a replicate of its own, the open-mode
measurement rows written from the four traces that exist, and `review --serve` finding a
project three levels deep.

**Wave 4, lineage assignment**, which the benchmark's cell-typing eval and every panel-scored
project use: L98 with method M1 (the margin and the background, then the flag), M5
(unassigned), M6 (a panel gene the object lacks), L99 with M2 (the interpretation judgment
when a lineage takes nothing; L), M10 and M11 (the figures and the why-assignment tool), M12
and M3 (the negative controls, the scoring options). With them the QC predicates that wait on
nothing: L117, L119, L120, `qc.threshold_range` (in the design, never built), and the
plugin's own lagging schemas and wording (its README's open items). The five plugin changes the method's rows need and nobody filed (a mixed-cluster
flag, a missing-panel-gene flag at `init`, the panel tree, a reference-model type, the DE
formula) get rows first.

**Wave 5, L100**: `decision.hold: always` never opens under `run`, because the run loop
proposes nothing. It is the first item of the gate review, waits on nothing, and the Xenium
method's decision blocks wait on it.

## 6. Releases, and the benchmark after each

| release | carries | then |
|---|---|---|
| engine 0.2.41 | #25 (a name is marked) | republish the operator skill |
| engine 0.2.42 | wave 1's engine half, wave 3's engine rows | |
| method scRNA-seq 0.1.12 | the PCA pipeline, (b), L164, L167 | |
| method scRNA-seq 0.1.13 | (d), wave 4's method rows as they land | |
| plugin 0.10.4 | wave 4's predicates | |
| engine 0.2.43 | wave 2 | |

After each tag: `bench.py due` (`stringency-benchmarks/BENCHMARKING.md`), a new stack file, and
the same study again beside the last one (`bench.py compare`). The first comparison that means
something is the November slice again on engine 0.2.42 with method 0.1.13: DE01 should reach
delivery in pipeline mode. PCA will not change until L171 is taken up. A run costs money
(about 35 USD for the quick study) and is proposed each time, never started unasked.

## 7. Waiting on the owner, ordered by what each answer unblocks

**Answered 2026-11-10** (items 1 to 4 of the list below; they move into the waves):

- #25 is merged (079b632) and #24 closed. Engine work branches from `main`.
- **L169**: "leave out an incomplete replicate" is built into the DE module. It joins wave 1
  beside (b).
- **L171**: strict-level limits are used whenever a benchmark runs. Taken up, not parked. The
  route is the engine's: a project chooses its limits band apart from its profile, the
  benchmark's runner asks for the strict band, and the released method is what is tested
  (design-level; the text is his to approve). It joins wave 1's engine half. The shortcut (a
  method release candidate whose `standard` profile reads the strict band) stays available if
  numbers are wanted sooner.
- **L159**: several holds from one proposal are handled in the skill: the operator relays
  every open hold before it waits. Text only; it joins wave 2 with L146 and L147.
- **L158**: `wait --job` gets a new exit code for "still running" at its timeout. An addition
  to design 14.2's frozen list, approved by him; a `DEVIATIONS.md` entry records it when it is
  built. It joins wave 2.
- **L129**: a decision left at `unset` with no proposal stops the run, which says the step and
  its evidence; no hold opens. It joins wave 2, beside the name form's "an unset required name
  stops its step".
- **L162**: `via: policy` in the trace for a fixed policy's verdicts, approved (a change to
  the trace schema, with its `DEVIATIONS.md` entry). It joins wave 1's engine half, before any
  benchmark number is published.

**One word each, and they unblock work already planned above:**

1. Merge #25 and close #24. Everything in the engine stacks on it. With it, acknowledge the
   two `DEVIATIONS.md` entries that have waited since October (`must_cite`, `outputs.key`).
2. **L169** (e): does "leave out a replicate that lacks a sample on either side" belong in the
   DE module as an option? Unblocks an answer on DE01 that is not labelled `untested`.
3. **L171**: strict-level limits, parked by him ("do nothing for it yet"). Unblocks the PCA
   eval's flag and the enforce arm. Until then the benchmark's headline cannot move on PCA.
4. **L159**: one proposal, two holds: fold the flags into one packet (engine) or have the skill
   relay every open hold (text).
5. **L158**: `wait --job` at its timeout: a new exit code against the frozen list, or exit 0
   with `state: running`.
6. **L129**: a decision left at `unset`: `run` stops for a proposal, or the plugin rewords the
   hold and the engine refuses the accept.
7. **L162**: a `via: policy` value in the trace, before the benchmark's tags freeze.

**Design choices that open a block of work:**

8. The gate review (L103, L104 with L105, L101, L108, L109): five choices recorded as waiting
   since 2026-10-22.
9. D1 to D3 (where species and tissue are declared; flag or block; the bound) for the
   mitochondrial predicates L115, L116, L118.
10. Annotation (L111): the state programmes, the `pct_diff` floor, the reading of gut
    cluster 9.
11. L35's rule for a table whose path is part trusted, part not.
12. What #25 left: whether `5-10` should stop reading as an identifier, whether a sentence must
    agree with the row its measurement came from, and whether a story follows the marked rule.
13. Design 17's triggers, both met: judgment tools on demand in open mode, and the
    `reason_code` enum now that there are fifty reviews. Schedule or leave.
14. The Lane F report and retrospective (F11, F12): still wanted? No row or module exists.
15. After wave 1: the Xenium `timepoint_factor` to the name form, so that pipeline is not tied
    to one study's factor name.

**His to do, nobody else's:**

16. Tags and republishing: Xenium `v0.6.0-rc26.1` and its two skills; the operator, declare and
    wrap skills; the scRNA-seq method's tags.
17. The Latch conversation (L88, L92, L170): the only route to a held-out number for scBench.
18. The tester for the acceptance runs (L79, L77); what "competent" means for the local-model
    judge (L34); the hand pass over the baseline's trajectories (L156).
19. The Xenium method's own questions (its PLAN 3.5, 3.6, 3.19, 8.6, 8.13, 8.18, 8.19, the GO
    tool's direct against propagated annotations) and the plugin's two (the intensity
    predicate's band, the permutation count).
20. `study: lyons_clp` on the Lyons projects, which are his projects: every one has
    `study: null`, so confirm-once has never applied to them.
21. SpatialBench's public evals: development or held-out. Until he says, only the baseline
    runs on them.
22. Small records: the Track 1h notify decision of 2026-09-23 (email only) sits in an unmerged
    commit on `lane-e`; land it or drop it, with the two docs commits on `track-1h-text`. The
    OmicsBench paragraph offered for the README. The finished briefs, walkthroughs and
    hand-offs loose beside the checkouts, which belong in an archive.


## 8. Not planned here

Deferred by the owner or filed "when he asks", and left there: the decision menus (L63 to L66),
structured claims (L58) and quotes (L38), the judge panel (L71, L73, L82, L4), trace integrity
beyond T2 (L52, L53), staged objectives (H5), the console rows (L74, L75, L81), the site
egress rule (L42), the plugin predicates that need a method module first (L122 to L127), the
Xenium method's large items (BANKSY and LIANA+, the Python 3.12 image, morphology), the
plasmidsaurus method and its plugin, and the Tapestri eval, which no backlog addresses.
Filed by wave 0 and left: the low finds of its table; region import from QuPath or Xenium
Explorer and an H&E hook (the questions catalog); the landscape survey's recommendations (a
preprint, three conversations, an audit-trail export), which are the owner's to raise. The
beta repository's open list and its app backlog have no ids and are that repository's own.

## 9. Where each wave stands, and the measurement half of wave 3 (2026-11-11)

Written after one night and a morning of work on waves 0 to 3. The sections above are the plan
as it was made; this one is what happened to it. `PLAN.md` "Next, in order" is the live list.

| wave | done | left |
|---|---|---|
| 0 | all of it (#26; the Xenium, plugin and scRNA-seq shares in their own repositories) | |
| 1 | L168, L161, L164, L169, L162, and with them L129 and L158; L163 (b), (c), (d) and L171 built (engine 0.2.42, plugin 0.10.4, method 0.1.12 and 0.1.13) | the method's tags and the slice run again close L163 and L171; L167 needs the owner's choice |
| 2 | L95, L146, L147, L159, L174; the first half of L114 | L94 with L107, the rest of L114, L160, L110, L11, L175 |
| 3, correctness | L145, L148 | L172, L106, L80, L37, K3, K4 |
| 3, measurement | nothing | L194, L193, L190, L155 with L191, L154 with L192, L156; L76, L173 |
| 4 | nothing | all of it |
| 5 | nothing | L100, in a session with the owner |

Outside the waves, found while testing and fixed: a control took the hosting project's
declared parameters; `init.column_missing` did not name the column; the plugin's CI had been
red since 0.9.0; the scRNA-seq DE module's controls failed in a project named unlike its
fixture; open mode interviewed a person who had already asked (#29). Filed and left: L186 to
L189.

**The measurement half of wave 3.** The owner asked on 2026-11-11 whether the total token
usage of a project can be measured, for evaluating the tool in general. It cannot: the
operator's session is outside the trace, the judges' counts are per call and absent under the
subagent harness, and only a benchmark replicate's `result.json` has a total. He agreed it
belongs in the beta's bundle and eval store, where the transcript and the trace already meet
and where the benchmark's run record (L154 to L156, already in this wave) was going. So the
wave's second half is one piece of work, in this order:

1. **L194** (S, `stringency-benchmarks`): token columns in the ledger, tokens per arm in
   `compare`. Before the slice is run again, since the data is already in every `result.json`
   and the overhead should be reported with the result.
2. **L193** (S, engine): the coverage report sums the judges' tokens and counts the calls that
   reported none.
3. **L190** (S, a check): what each harness keeps of a session. It decides whether the owner's
   own sessions can be measured or only Claude Code and benchmark runs, so it comes before
   any code in the beta.
4. **L155 with L191** (M, beta CLI): the bundle takes a transcript by path and reads usage per
   turn from it, a subagent's turns attributed to the judgment they answered.
5. **L154 with L192** (M, beta eval store): the usage table and its views (tokens per project,
   step, hold and arm), beside the benchmark's `benchmark_runs`.
6. **L156**, then **L76** and **L173**, which are write-ups from traces that exist.

Steps 1 and 2 need nothing from the owner. Step 3 needs a look at what Claude Science keeps,
which is his application's state and is read, never changed. Steps 4 and 5 are about a week
for one person and are what Phase 3 of the benchmark needs anyway.

Releases after this section: engine 0.2.43 carries wave 2's remainder, #29 and L193; the
plugin's next is 0.10.5 and the method's 0.1.14 (wave 4), since 0.10.4 and 0.1.13 were used by
wave 1.

## 10. Ready for a ROSC run (2026-11-11)

The owner: "I want to soon try re-running all of the ROSC data through a stringency pipeline
for the first time. I want to address some of the backlog we experienced in the Lyons dataset
first." This section is that work as one track, R, ordered by what would stop or spoil the
run. It goes ahead of the rest of wave 2 and takes four of its rows and wave 5's with it.

**What ROSC is, against what the method has run.** Retro-orbital against subcutaneous delivery
of an LNP Cre cargo in Ai14 reporter mice (`/lab/archive/bmeseq/Projects/ROSC_MTA2`; raw
regions under `/lab/archive/bmeseq/Xenium/prime/ROSC_MTA`, 183 GB, the copy the owner named
for Lyons v2). The manifest lists 132 punches, 104 included, on six TMAs.

| | Lyons CLP v2 | ROSC |
|---|---|---|
| tissues | four (liver, lung, small intestine, spleen) | eleven: those four and brain, heart, kidney, lymph node, large intestine, skin, female reproductive tract |
| design | one factor, the time point (control, 6, 24, 48 h) | route (RO, SC) by time (D1, D3), with untreated controls: five groups |
| replicates | two animals a time point, two punches each | two punches a group in most tissues |
| segmentation | Proseg and 10x | Proseg for 96 punches, 10x for 36 |
| the study's own question | what changes with time after CLP | where the cargo went: the reporter probes by cell type, zone, route and time |

The method was written on Lyons and carries three of its assumptions: the time-point factor is
named `timepoint_h`; an organ is one of four; nothing asks about a reporter.

**The track.**

| step | what | where | needs | size |
|---|---|---|---|---|
| R0 | The method verified under engine 0.2.42 and plugin 0.10.4: both synthetic studies, the open-tools check. The engine now stops `run` at a step whose decision is `unset` and asks for a proposal; the pipeline headers and the skill still describe the hold it replaced, and `sc.decision_unreviewed` no longer sees those steps. `requires.engine` moves | method | nothing | S |
| R1 | The ROSC declarations drafted from its manifest (`inputs.yml`, `design.yml`, the layout and exclusions per TMA), with the choices only the owner can make laid out: one group factor or two; punch or animal as the replicate; which organs first; the archived Proseg output or a new segmentation; the study name for confirm once | a draft for the owner | his reading | S |
| R2 | The time-point factor declared, not fixed: `timepoint_factor` on the engine's name form or read from the design, in the four steps and the modules that take "the first multi-level factor"; the Seurat extractor lists an object's columns so the name is checked (L178, L186) | method, plugin | R1's factor choice | M |
| R3 | QC revised without re-splitting: `punch_bundles` delivered, a `xenium-qc-cells` pipeline over them (the method's 3.3). Lyons re-split eight regions at every threshold change; ROSC has six TMAs | method | nothing | M |
| R4 | A judgment's rationale may name a time point, a punch or a slide: `judg.numeric_claims_match@3` reads it by the answer's rules (L195). Then the method's prompt wording (its 1.10) is a refinement, checked when a judge is next run | engine | nothing | S to M |
| R5 | The hold friction of the Lyons sessions that a larger study multiplies: a person's label and chosen replicate reach `consensus.json` and `apply-labels` (L110, the method's 3.18); a held step can be re-proposed and a stranded one recovers (L94, L107); every decision point opens one sign-off under `run` and the bridge predicate retires (L100, the method's 3.4) | engine, then method | a session with the owner for L100 | M each |
| R6 | A rehearsal: ROSC liver (the smallest, and already the annotation fixture) from the raw regions through QC, upstream and the layers to one open question, on the installed engine. What it finds is fixed before the other organs start | a project | the install of 0.2.42; R0 to R4 | a few days |

**Beside the track, not gating the first run.**

- **L197, the other seven organs.** Each needs its vocabulary, guide section and tissue
  defaults, and the vocabulary is the owner's to read (the method's 3.6). The four known
  organs (39 of the 104 included punches) run first; the rest follow in batches.
- **L198, the cargo tool.** The pipeline runs without it; the study's first question cannot
  be answered by a tested tool without it.
- **The owner's standing questions in the method's plan** that a second study makes sharper:
  the batch rule's thresholds (3.5), whether the per-domain pseudobulk is delivered (8.6),
  whether an animal's punches are summed before the sample filter (8.18).
- **Practice, no work:** every ROSC project names one `study:` so one confirmation covers
  the design (built, never used on Lyons: L181); the raw regions are bound from the archive
  copy, read and never changed.

**Not needed for ROSC**, and left where they are: the Python 3.12 image (the method's 7.13),
BANKSY and LIANA+ (7.12), local Moran's I (7.26), a morphology tool, the tag clean-up (4.1).

**How it sits with the waves.** R0, R3 and R4 wait on nothing and start now. R1 is a draft that
waits on a reading. R2 follows R1. R5's first two rows are wave 2's and are done here; L100 is
wave 5's and is done here, with the owner. The rest of wave 2 (the rest of L114, L160, L11,
L175), wave 3 and wave 4 follow the rehearsal. The measurement half of wave 3 keeps its one
early piece: the ledger's token columns (L194), before any benchmark is run again.


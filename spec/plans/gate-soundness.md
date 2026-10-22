# Gate soundness

**Status 2026-10-22.** Filed, nothing built; rows L100 to L109 of `PLAN.md`. The owner's
walkthrough of the gate, handed in on 2026-10-22 against `main` at `6947aa6`, checked in this
session against `491f1aa` (two console commits later; neither changes the code cited beyond the
predicates' reader-facing summaries). Every limitation below was confirmed by reading the code;
none has been reproduced as a failing run. Line references are to `491f1aa`.

The question the review asks: does "the gate admitted this step" mean that the choice was
supported, that the checks ran, and that any reused approval addressed the same concern? Today it
does not quite mean any of the three. This document is the reasoning behind the rows; the rows
are the work.

## The order

1. L103 first. A pre-gate accept can resolve a post-gate flag on the same attempt, on the
   ordinary path, with no one seeing the second concern (section 2).
2. L100. `decision.hold: always` never opens under `run`, the path most steps take, so the
   owner's ask behind L9 is met only when the operator proposes the default explicitly
   (section 1).
3. L104, with L105 beside it. A required check that raises is a fired verdict under its normal
   disposition, so under `log` it admits the step (sections 3 and 4).
4. L107, L106, L108: recovery, the admitted Action, the lifecycle audit.
5. L101, L102 and L109 wait on the owner's choice of design (the waiting table).

## Contract impact

| row | what it touches | level |
|---|---|---|
| L100 | `param.agent_proposed@3`, `param.uncited@2` | predicate versions, below the contract |
| L101 | design 3.1 and 6.5 (`decision-points.md` section 3) | *design* |
| L102 | plugin singlecell and the scRNA-seq method | plugin and method |
| L103 | design 7.2 (line 687: a rebind matches "the same hold kind, module version, and bindings") | *design*; no schema change, `holds.context_json` already carries predicate and phase |
| L104 | predicate contract 6.1, "Verdict" (frozen): a predicate that raises "is recorded as fired" | *design*, via `DEVIATIONS.md`; trace 9.4 too if the status wants a column |
| L105 | none for the mechanism; the outcome is L104's | engine, DECISIONS-level |
| L106 | none | engine, below the contract |
| L107 | none, unless resuming needs a new edge in 7.1 | engine; *design* if an edge |
| L108 | none for the audit; design 7.1 if admission and completion are to require evidence | engine; *design* for the evidence |
| L109 | predicate contract 6.1, "Purity and tests" and "Context" (frozen) | *design*, the owner's choice |

## 1. Defaults and evidence (L100, L101, L102)

`_decision_points()` (`src/stringency/predicates/engine/param.py:11`) keeps only parameters whose
`param_source` is `agent`. `param.agent_proposed@2` and `param.uncited@1` both read that set, so a
value whose source is `default`, `declared` (the objective's), `inherited` (a fork's ancestor) or
`fork` (a person's `--set`) is outside both checks before `hold: always` is read.

The review names the case of an implicit default. It is wider than an edge case: the run loop's
`pending` branch (`src/stringency/runloop.py:419`) calls `propose` with no values, so under `run`
every parameter is `default`, `declared` or `inherited`, and a `hold: always` step is admitted
silently. The L61 test (`tests/test_gate.py:587`) proposes the default explicitly, which is why
it passes. L9 ("a decision point taken at its default opens no hold") was closed by L61 on
0.2.29; its substance is open again here. Until L100 ships, plugin singlecell's
`sc.decision_unreviewed` is the only check on a default reached by `run`, so it must not retire
where a method declares `hold: always` (`PLAN.md` Next item 2 said it would).

Schema validation, ranges and the scientific predicates still run at a default; what a default
escapes is the scrutiny of the choice and its evidence. `obj.feasibility`
(`src/stringency/predicates/engine/obj.py:11`) is the nearest thing to a suitability check and is
not predictive: it reads the counts in the current state, skips a level whose count is absent,
and does not simulate the proposed filter. A pre-gate check of a filter's effect needs a preview
written upstream (L63's sweep table is that shape) or a computation the module provides.

Two workstreams, as the owner put them:

- Engine (L100 narrow, L101 the design). The evidence obligation follows the declared decision
  point and the current data, not who chose the value. The source stays recorded and is not
  itself evidence: a default is not presumed suitable, and a departure from it is not evidence
  against the new value. Missing, stale or inapplicable evidence is an explicit outcome ("not
  assessed"), never a pass. Who approves stays `hold:`, configured apart from the evidence.
- Method (L102). Predicates that look at the data's own summaries and fire on a mismatch
  whatever the value's source. For a cell filter: a table of candidate thresholds by retained
  cells per sample and group, and a predicate that flags a choice removing one group
  disproportionately or leaving too few units for the next step. Thresholds and the test are the
  method's, not a universal engine rule. `sc.qc_floor_above_data`, which blocked `min_genes` 200
  on the BD Rhapsody data (07:00 note of 2026-10-22), is the existing instance of the kind. These
  predicates do not need L64's deterministic rule.

Tests for the pair: a supported default, an unsupported default, a supported adaptation, missing
evidence, and implicit against explicit use of the same value (the same `predicate_results`).
Related, not duplicated: L63 to L66 (sweep, rule, judged, sensitivity).

## 2. Approval reuse (L103)

`holds.prior_verdict()` (`src/stringency/holds.py:38`) matches an earlier `accept` or `override`
on hold kind, module version, input digest and params hash, plus item and item evidence for an
item hold. It does not match the predicate, its version, the phase, the flag's evidence, the step,
the policy digest, or who may review.

The pre-gate (`src/stringency/steps.py:655`) and post-gate (`src/stringency/steps.py:1198`) open
flag holds with the same three bindings from the same Action, and the review copies the hold's
bindings (`src/stringency/review.py:253`). So on one attempt: the reviewer accepts a pre-gate
`param.agent_proposed` flag, the step runs, a post-gate predicate flags the output, and
`open_hold` resolves the new hold at once as `rebind` to the first review. The step completes with
a concern no person read. The same holds across two flags of one gate when a re-proposal repeats
the values, and across steps that share a module, inputs and parameters.

This is the code doing what design 7.2 says (line 687), so the fix is a design change. What
closes it: a rebind matches the predicate id and version and the phase as well (`context_json`
carries both today), and the flag's evidence digest where the evidence is the concern; a policy
change that alters the predicate's disposition, or a change in who may review, defeats it; the
rebound hold names the review it reuses, and the packet, `present --hold` and the console show
the reuse. Tests: pre accept then post flag on one attempt opens a hold; the same predicate on a
rerun with identical bindings still rebinds; a predicate version bump defeats it.

L6's accept-once across study siblings (`inherit_flag_acceptance`, `steps.py:702`) is a separate
rule, deliberately built, and already matches the predicate (`param.agent_proposed`) and the
proposed values. Under L101 an inherited acceptance stands beside fresh suitability checks on each
dataset; it does not replace them.

## 3. Evaluation failures (L104)

`gate.run_predicate()` (`src/stringency/gate.py:86`) turns an exception into `Verdict(True,
"predicate raised ...")`, and `evaluate()` applies the predicate's effective disposition to it.
So a broken check under `log` is logged and the step proceeds; under `flag` it is a hold a
reviewer can accept as if the check had found something; and its acceptance can then rebind
(section 2). The contract text says the same (`spec/predicate-contract.md:51`), on purpose: "a
broken check is not a passed one". It is not a passed one, but it can still be an admitting one.

What closes it: an evaluation status (`ok`, `error`, `timeout`) recorded apart from the verdict,
in the trace and in what a person reads. A failed evaluation of a required check stops admission
whatever the finding's disposition would have been; a waiver, if one is supported, is its own
recorded act bound to that failure and never rebinds to a scientific acceptance. An optional,
observational check has a documented failure policy. Tests raise inside predicates whose
findings map to `log`, `flag` and `block`. Which checks are "required" is part of the design:
the simplest reading is every predicate whose effective disposition is `flag` or `block`, plus any
a method marks.

## 4. A runtime limit that stops a predicate (L105)

`PREDICATE_BUDGET_S` (`gate.py:19`) is compared after the call returns; the docstring calls the
budget loose. A predicate that never returns stalls the gate: no row is written for it and the
predicates after it never run.

What closes it: predicates run under a mechanism that stops them at the deadline (a worker
process per gate, or per predicate, killed at the deadline plus a stated allowance), with no
worker left running; the trace records `timeout` (L104's status) and the step gets L104's outcome;
the rule for the remaining predicates after a timeout is stated (the simplest: evaluate them, so
the record is complete). A separate process does not by itself prevent I/O (section 8).

## 5. The admitted Action (L106)

`Action` (`src/stringency/actions.py:22`) is a frozen dataclass whose `parameters`,
`param_source`, `inputs` and `rationale` are ordinary dicts. `build_action` copies the outer
mapping of the proposal, not nested values, and computes `params_hash` once. `write_action`
persists the live dicts beside that hash, and `job_for` (`steps.py:809`) builds the job's stdin
from the live `action.parameters`. A predicate receives the Action in its context. Nothing in the
engine is known to mutate it; nothing prevents it.

What closes it: the Action carries deeply immutable values (or the job is rebuilt from the
persisted row), mutation through an alias, a nested list or a predicate's context cannot change
what runs, and the canonical values are checked against `params_hash` when written and before a
job is built. Tests mutate before and after persistence.

## 6. A step left in `proposed` (L107)

`propose()` commits the Action and the `proposed` transition together (`steps.py:621`); the gate,
the holds and the settling transition follow in separate writes. A crash between them leaves the
step `proposed`. The run loop treats `proposed` as an internal error (`runloop.py:430`), and
`propose` refuses a step that is not in `RETRYABLE` (`machine.py:76`). The only way out today is
`abandon` of the whole run (`proposed -> abandoned` is an edge) and a fork. Nothing executes
unsafely; nothing recovers.

What closes it: an incomplete gate is recognisable (a gate-complete step event, or the absence
of one beside the Action); recovery either re-evaluates the same recorded Action or closes the
attempt and opens a new one; partial `predicate_results` rows are distinguishable from a complete
assessment; no duplicate holds; nothing executes before admission is complete. Tests interrupt
after the proposal commit, after some predicate results, and after hold creation before the
settling transition. A transaction held open across arbitrary predicate code is not required;
staged commits with a stated recovery are. L94 (withdraw a held proposal) is the neighbouring
row; this one covers a step that never reached `held`.

## 7. Lifecycle edges and their evidence (L108)

Three layers check different things. `machine.transition()` (`machine.py:99`) refuses an edge not
in `EDGES`. `Store.set_step_status()` (`src/stringency/db/store.py:322`) writes the event and the
row atomically and checks no edge. `audit._steps()` (`src/stringency/audit.py:67`) compares the
row with the latest status event and does not replay the history. So a caller of the Store can
record an illegal edge with row and event in agreement, and a legal edge (`produced ->
completed`) does not show that the post-gate passed.

Found in this check: `fork.py:188` and `fork.py:199` call `Store.set_step_status` directly to
write inherited steps as `pending -> completed` and `pending -> skipped`; neither is in `EDGES`.
They are deliberate (the child inherits the parent's finished steps), and a replaying audit must
know them, or they become named edges.

What closes it: the guarantees of the lifecycle API and of the audit are written down; every
supported path that changes a status goes through edge validation (the fork's inheritance edges
named); the audit replays each step's events and names an illegal edge even when row and event
agree; if admission and completion are to require evidence, each names the gate run or verdict
that justified it, with empty gates, resolved holds, retries, skips and on-demand steps handled;
event and row stay atomic. This sits beside L52 (T3), which deliberately leaves transition
validity to `machine.transition` (`trace-integrity-plan.md`, T3); T3 and T4 make a bypass visible
or impossible, not sufficient evidence.

## 8. The predicate trust boundary (L109)

The contract says predicates do no I/O, read no clock, use no randomness and reach no network
(`predicate-contract.md:56`). The gate calls them as ordinary Python in the engine's process
(`gate.py:91`). A context without a Store narrows the interface and enforces nothing: a predicate
can import, open files, reach the network, or change the Action and context the next predicate
sees.

The owner chooses first: purity as a requirement on trusted plugin code, checked by review, tests
and tooling, with the limits stated; or restrictions enforced at runtime, with the isolation and
capabilities that promise needs. Either way a predicate cannot silently change what later checks
see (L106), the inputs and the inspected evidence stay reproducible, and the documents say what
is enforced. A worker process for L105 is not a sandbox by itself.

The contract's Context section also says "The agent's rationale is never in the context"
(`predicate-contract.md:46`). Since L55 (0.2.29) the Action carries the resolved rationale in
memory for `param.reason_unmatched` and `param.uncited`. The DECISIONS entry for decision points
records the field; the frozen text was not amended. L109 aligns it.

## Not filed

`invariant` means "never remapped by a profile"; an explicit override still applies
(`src/stringency/policy.py:123`, `predicate-contract.md:29`). Code and contract agree. A rule no
override can change would be a policy design question for the owner, not a defect; no row until
the owner wants one.

# Confirm once: the owner should not re-accept a design the engine has already seen them accept

Working note, not the spec. Drafted 2026-10-06 at the end of the Lane F phase 0 session for a later
Lane A (engine) session. Proposes changes to design 2.7 (inherited confirmation), 7.2 to 7.4
(hold kinds, review verdicts, binding and reuse of verdicts) and 14.1 (`review --holds`). Items
marked *design* change design text and need the owner's approval; the rest are DECISIONS-level.

**Status 2026-10-06.** Proposed, not started (Lane A). Backlog rows L5 and L6 are the two pieces
already filed; this note is the whole picture and the order. Decisions for the owner in section 5.

## 1. The problem, counted

On 2026-10-06 one experiment, Lyons CLP, with one `design.yml` (the same bytes in every project,
hash `18a12171…`), one owner and one reviewer, asked that owner to confirm the same reading of the
experiment five times, and to approve the same parameter choices sixteen times:

| when | hold | why it opened although nothing about the design had changed |
|---|---|---|
| eight `qc2_<slide>_<Region>` projects | 8 confirm holds, one batch review | raw inputs; the first projects of the chain, so one acceptance is right. Batch review (7.3) folded them into one echo-back and one verdict, which worked |
| `qc2_summary_all` | 1 confirm hold | every metrics table was `derived_from` a confirmed `qc2` project, but the layout and histology files are raw inputs, and inherited confirmation (2.7) requires *every* input to be derived. Those two files are the same bytes the eight upstream projects bound |
| `qc2_outliers_all` | 1 confirm hold | the 42-row table is derived from the confirmed summary; the reference table is a manual input with `role: reference`, which is not this design's data |
| `cluster_liver` | 1 confirm hold | two derived inputs and the owner's own `punch_exclusions.csv`, a raw observation file |
| `cluster_liver` again | 1 confirm hold | the project was re-declared on method `v0.5.0-rc2` after a packaging fix (`v0.5.0-rc1` had a module that could not start); identical declarations, same major version |
| eight `qc2_*` × two steps | 16 `param.agent_proposed` flag holds | the operator proposed the first chain's tissue thresholds on every project; the predicate fires on any departure from the pipeline default, per project and per step; batch review covers confirm holds only, so each was relayed alone with the owner's one sentence |

The owner's words at the fifth confirm: "the engine's repeated asks for confirming design are
annoying." Two mechanisms built on 2026-09-23 were meant to prevent this and did not reach these
cases: inherited confirmation (2.7) is defeated by any raw input, including a file the upstream
projects bound under the same hash; batch review (7.3) joins confirm holds only, and only when they
are open at the same time. Verdict reuse (7.4) binds to module version, input digest and params, so
a new project never matches.

Backlog L5 (raw-identical and reference inputs) and L6 (batch review of identical flag holds) are
pieces of this. L7, the executor's bind scope, is a different problem and stays separate.

## 2. What must not change

- A different `design.yml`, a different owner, a raw input whose hash no upstream project bound, a
  judgment module version bump, or a change of method major version still opens a hold.
- The echo-back is always written to the project, inherited or not; a person can always read what
  the engine understood.
- Every inheritance is a recorded row (hold, review, project, acceptance it rests on) so the trace
  lets a reader reconstruct who accepted what and when, from `run.db` alone. Inheriting is not
  skipping: it is a confirm hold resolved by the engine with `resolved_via = inherited` and a
  pointer, exactly as 2.7 does today.
- The operator still cannot accept anything. Every rule below moves work from the person to a
  recorded comparison with something the person already accepted.

## 3. Proposals

(a) **Widen inherited confirmation** (2.7; DECISIONS-level; backlog L5). A project inherits when
every input is one of: `derived_from` a run of a project the same owner confirmed with a
byte-identical `design.yml` and the same method major version (today's rule); raw and identical in
name, type and hash to an input one of those confirmed projects bound; or `role: reference`. The
inherited echo-back names which inputs matched by which rule. Today this alone would have cleared
`qc2_summary_all`, `qc2_outliers_all` and the first `cluster_liver`.

(b) **A study-level design acceptance** (2.7 and 7.2; *design*). The first accepted confirm hold
under a project tree (the directory `--projects` or `board` walks) records (owner, design hash,
method repository, major version) as an acceptance any later project in that tree may inherit when
its `design.yml` has the same hash and the same owner, whatever its inputs. The echo-back is still
written; the hold is created and resolved `inherited` with a pointer to that acceptance. Inputs are
still hashed and verified at init; an input the owner has never seen is a fact the echo-back
states, not a reason to re-ask about the design. This is the rule that makes a chained study one
acceptance. It is a design change because 2.7 ties confirmation to the project and 7.2 says the
init confirm opens in every profile.

(c) **Re-declaration on a new method tag** (2.7 and 7.4; DECISIONS-level). When a project is
initialised with declarations byte-identical to a project the same owner confirmed, under the same
method repository and major version, the acceptance carries over even if the inputs are raw; the
echo-back says which project it inherits from. Covers the `v0.5.0-rc1` to `rc2` case and any
re-declaration after a packaging fix. With (b) in place this is a corollary; without it, it is a
narrow rule worth having first.

(d) **Accept once for identical parameter flags** (7.3, 7.4 and 14.1; DECISIONS-level; backlog
L6). Two parts. Batch review takes flag holds whose predicate, step, module version and
`proposed` evidence are identical across sibling projects, shows the differing cells as the
confirm batch does, and refuses a batch whose packets differ. And `param.agent_proposed` reuses an
acceptance: when the same owner accepted the same proposed values for the same module version and
pipeline in a sibling project under the same tree, the new hold is resolved `inherited` with a
pointer, and the review page lists it under "inherited today" rather than "needs you". Sixteen
holds become one.

(e) **Say so in advance** (2.7 and 14.1; DECISIONS-level). `declare --check` and `init` print,
before the hold decision, which acceptance the project would inherit and by which rule, or why it
cannot (the input or field that breaks the match). `lint` is not the place: it reads the method,
not the project. The operator can then tell the person "no confirmation needed; it inherits
from `qc2_0076570_Gut`, accepted 15:04" instead of relaying a hold.

## 4. Order, estimates, tests

| step | depends on | estimate | tests (fixture shape: the Lyons chain, eight siblings, a summary over them, a judgment with a reference, a re-declared child) |
|---|---|---|---|
| (a) widen inheritance | nothing | half a session | one test per rule: raw-identical input inherits, raw input with a new hash does not, `role: reference` inherits, a different owner does not |
| (c) re-declaration | nothing | half a session | identical declarations on a new rc tag inherit; one changed byte in any declaration does not; a major version change does not |
| (d) flag batch and accept-once | nothing | one session | batch of identical `param.agent_proposed` packets accepted once; a batch with one differing value refused; a second sibling inherits the acceptance; a different module version does not |
| (e) say so in advance | (a), (c) | half a session | `declare --check` output names the rule and the acceptance; names the breaking input when none applies |
| (b) study-level acceptance | owner's yes (section 5) | one session plus design text | first project in a tree opens a hold; the next with the same design hash inherits whatever its inputs; a different hash or owner opens a hold; the trace row points at the acceptance; `review --serve` lists inherited holds under their own heading |

Every rule's inheritance writes the same row shape 2.7 writes today, so `present`, `board` and
the review page need no new column, only (d)'s "inherited today" list and (e)'s sentence.

## 5. Decisions for the owner

1. Approve (b), the study-level design acceptance, as a design change to 2.7 and 7.2, or keep
   confirmation per project and take only (a), (c), (d), (e). Recommendation: approve (b); the
   other four are still worth building first because they need no design text.
2. Scope of "the same tree" for (b) and (d): the directory the board walks (today `/lab/projects/<study>`), or an explicit `study:` field in `stringency.yml` that projects opt into. Recommendation: the directory, with the field as a later refinement.
3. Whether an inherited acceptance expires: never (the design hash is the identity), or after a declared number of days, or when the method major version changes (already a rule). Recommendation: never, since the hash is the identity and a changed design is a new hash.
4. Whether `param.agent_proposed` accept-once (d) applies across module versions when the schema of the parameters is unchanged, or only within one module version. Recommendation: one module version only; a version bump is the method author's statement that something changed.

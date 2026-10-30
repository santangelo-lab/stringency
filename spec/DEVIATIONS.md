# Deviations

Contracts marked frozen in the design that could not be implemented as written. Each entry needs acknowledgement by Jim.


## Module contract 3.2: `judgment.sign_off` (2026-10-08, backlog L10)

An optional field inside the frozen manifest's `judgment` block: `sign_off: {when: always | never,
labels: [...]}`. Additive: a manifest without it parses and behaves as before; a manifest with it
is refused by engines before 0.2.14 (the manifest model forbids unknown keys), which is the
intended failure for a method that relies on a person's sign-off. Needed because the batch-route
judgment's label is a route the run takes, and the only way to ask a person about an agreed label
was a plugin predicate whose accept/reject verdicts read as "accept the correction" (the owner,
2026-10-08: rejecting to decline a correction would have closed the attempt). The hold kind
`sign_off` and the `--choose` mapping need no frozen change: the `holds.kind` and
`reviews.verdict` columns carry no constraint and the verdicts stay accept, override, reject,
defer. Acknowledged by Jim, 2026-10-21.


## Module contract 3.2: `egress` (2026-10-16, backlog L1)

Proposed, not built. An optional field in the frozen manifest: `egress: {class: 0-4, hosts:
[...], sends: "<one sentence>"}`, saying what the module's scripts send off the machine
(`spec/plans/egress-and-remeasurement.md` part 1). Additive: a manifest without it parses as
before; a manifest with it is refused by engines that predate it (the model forbids unknown keys),
the intended failure for a method that relies on the declaration. Needed because the engine
otherwise counts a module whose scripts reach the network as class 4 ("scanned, undeclared"), so
a module that only downloads public reference data (class 1) cannot run under a ceiling below 4.
Once acknowledged: the assessment uses the declared class; `lint` fails a module whose scripts
match the network scan and declare no egress or class 0, and warns on a class above 0 with no
match. Acknowledged by Jim, 2026-10-21: build the field, `assess` reading it and the lint rule
(`PLAN.md` L46).


## Module contract 3.2: `judgment.sign_off.when: sample` (2026-10-21, backlog L84)

An additional value of the optional `sign_off.when` inside the frozen manifest's `judgment`
block, with its companion `fraction` (a number in (0, 1], required with `sample`, refused
otherwise): a seeded sample of the agreed items, `round(fraction x agreed)` of them and at
least one, is held for sign-off as `always` holds every one. Additive: a manifest without it
behaves as before; a manifest with it is refused by engines before 0.2.30 (the literal is
closed), the intended failure for a method that relies on the sample. Needed because agreement
is the weak half of the replicate signal (the literature check of 2026-10-21): replicates of one
model with one prompt agree on the errors the model makes consistently, and nothing put an
agreed label before a person unless the module signed off every one. Approved in advance by
Jim, 2026-10-21 (the owner's answer on the replicates proposals); built in engine 0.2.30.


## Module contract 3.2: `judgment.must_cite` (2026-10-22, backlog L56)

An optional list inside the frozen manifest's `judgment` block: `must_cite: [<table>.<column>,
...]`, the cells every replicate must cite for every item, as supporting or contradicting,
whatever they show. Additive: a manifest without it parses and behaves as before; a manifest
with it is refused by engines before 0.2.33 (the model forbids unknown keys), the intended
failure for a method that relies on the check. Needed because `judg.confidence_consistent`
counts only the cells a judge cited, so a judge that leaves a contradicting cell uncited keeps
`high` (`omicsbench-assessment.md` 4.3); with the list, the prompt names the cells and
`judg.required_evidence_uncited@1` flags an item that leaves one out. Lint checks the form and
that the table is one of `judgment.evidence`. First users: `assess-batch` and
`annotate-clusters`, on the method's side. Awaiting acknowledgement by Jim; built in engine
0.2.33 as the sign-off field was.


## Module contract 3.2: `outputs.<name>.key` (2026-10-29, PLAN L138)

An optional list on a module output in the frozen manifest: `key: [<column>, ...]`, the columns
whose values, joined with `|`, address one row of the table the output is. Additive: a manifest
without it parses and behaves as before, the engine taking the shortest prefix of the columns
that is unique over the table (the first column alone where it is unique, so every table keyed
before keeps its keys); a manifest with it is refused by engines before 0.2.35 (the model
forbids unknown keys), the intended failure for a method that relies on it. Needed because a
table whose first column repeats (one row per cluster and stratum, one per replicate and pair)
lost every row but the last per first-column value, so no citation reached the others; the
prefix rule fixes that without a declaration, and the declaration fixes the columns where the
prefix would pick a different set from the one a method means. Read where a cited output is
resolved: an answer's `--cite`, a proposal's `--cite`. Lint errors on an empty or repeated
list and warns on `key` declared on an input. Whether a declared key is unique is not linted
(an output exists only after a run); a declared key that repeats numbers each repeat `#<n>`.
The module contract document (`spec/module-contract.md`, the `outputs` row) says so. Awaiting
acknowledgement by Jim; built in engine 0.2.35 as `must_cite` was.

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

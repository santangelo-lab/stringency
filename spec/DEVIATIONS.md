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
defer. Awaiting acknowledgement by Jim.

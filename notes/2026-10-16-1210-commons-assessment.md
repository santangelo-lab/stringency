# posit-dev/commons assessed against the design (2026-10-16)

## Goal

The owner asked for a read of `github.com/posit-dev/commons`, a new Posit project with goals
near stringency's, to compare the designs and find what is worth using, taking or learning from.

## Done

- Cloned commons at HEAD `15de530` (2026-10-12) into a scratch directory and read: the README
  and `AGENTS.md`; the Python package's get-started and governance pages; the provenance,
  citation, citation-scanner, measures, reminders, skills, tracing, SQL guard, sandbox,
  guardrails, handles and `run_python` modules; the two design notes under `pkg-py/notes/`
  (execution prior art; the cross-language trace round trip); the R governance vignette, the
  trajectory reader and reviewer, the review-document snapshot; `tests/shared/README.md`,
  the provenance, turn-reminder and citation-corpus fixtures, `scripts/sync-shared.sh` and
  the staleness workflow; the `commons` author skill and its onboarding, extraction,
  evaluation and iterating references. A web-fetch agent summarised the
  `posit-dev/devrel-agent/evals` design (questions YAML, scorers, metrics, the Claude Code
  baseline arm).
- Re-read the engine side needed for the comparison: design 8, 9.1 to 9.3, 10.1, 10.3, 11,
  12, 13, 16, 17; the judgment predicates; the executors; the dispatch envelope test; the
  egress and re-measurement plan; the ClawBio assessment's shape.
- Wrote `spec/plans/commons-assessment.md`: what commons is, a side-by-side table, the shared
  instincts, four borrowings with mechanism and level, a G2 proposal, smaller practices, what
  is not borrowed, and what commons lacks that the engine has. Row in `spec/README.md`.
- Backlog rows L35 to L38 and a pointer on G2 (`spec/plans/backlog.md`).

## Learned

- commons and stringency sit at the two ends of one axis. commons lets the model go anywhere
  its tools reach and derives a three-way trust label from the path afterwards (`Trusted`,
  `Cited`, `Untrusted`); stringency denies the freedom and gates the action before it runs.
  commons' `trusted only` mode is the nearest thing to pipeline mode; stringency's deferred
  open mode would be the nearest thing to commons.
- The one mechanism commons has that the engine has no counterpart for is a sandbox for
  model-written code: a worker that restricts itself with Landlock or user namespaces plus
  seccomp (Seatbelt on macOS), an environment allowlist with `-I`, no network by default, and a
  constructor that refuses without a kernel mechanism. That is the shape of a G2 answer:
  `exec --step` running the operator's script under the step's executor, filing the blob, and
  letting the step read `env: verified`. `apptainer --containall` already contains the
  environment; the local executor inherits it and is development-only.
- commons' claim check verifies a *quote* against an enumerated corpus and declares query rows
  not citable, so the numbers in an answer are never checked against the rows. The engine's
  `judg.numeric_claims_match` is the predicate commons lacks; its citation match is the one the
  engine lacks (textual claims about the vocabulary or objective), and the second matters less.
- commons runs one call per question: no replication, no abstention stability, no hold. A
  low-trust answer is labelled and shipped.
- commons' trajectories are OTel spans, off by default, with reasoning content dropped as
  `generic`; its review tool writes one markdown per conversation with YAML frontmatter for a
  person and an agent to read together, and its iterate skill reads those first. The engine
  has the override corpus as a rate and no route from reviews to a prompt revision (L37).
- commons keeps two implementations honest with executable fixtures both suites enumerate and
  a CI job that fails on a stale copy ("prose cannot enforce agreement"). The engine already
  does this for the skills (`render_skill.py`, `tests/test_render_skill.py`); W7's harness
  split is where a fixture a new harness can run is missing (L36).
- The devrel evaluation's design is worth keeping in view for W6's acceptance run: an LLM
  grader handed the full trajectory, deterministic tools for the arithmetic, binary rubric
  items including `avoids_fabrication` and `provenance_is_honest`, three epochs, and
  independent reviewers of the pilot transcripts given no list of suspected defects.
- commons' design notes use this repository's dated-note convention, and its `AGENTS.md`
  asks for extraordinarily brief PR descriptions; its testing stance (test the real path,
  skip without a key) is the opposite of the rule here, and the rule here stands.

## Altered

- Nothing in the engine or the spec. One plan document added, one README row, four backlog
  rows, one pointer on G2, the index.

## Open

- The owner: whether L35 (the collapse rule for the per-artifact label) and L36 go into Lane
  H and Lane J; whether the G2 proposal (`exec --step`) is the answer to G2; whether L37's
  export verb and `stringency-revise` skill are wanted before the Lyons reviews are forgotten.
- To check on the workstation, for L1: whether unprivileged `apptainer exec --net --network
  none` works for the lab's account. If it does, egress class 0 for engine-run steps can be
  enforced at run time rather than declared.
- Nothing committed.

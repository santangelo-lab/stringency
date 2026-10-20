# The egress drive and the merge of `egress` onto open mode (2026-10-20)

## Goal

The owner drives branch `egress` as a person through Claude Science (not the AI brief), judges
the hold relay, then has both test-driven branches, `open-mode` and `egress`, set up to merge
into `main`.

## Done

- The drive. The worktree was installed as `0.2.21-egress` in a scratch prefix
  (`/lab/scratch/egress-test/prefix`), the toy method as a git repository at `v0.1.0`, an agent
  context carrying the engine path and the run settings, and the person spoke to the session in
  their words (`walkthrough-egress-drive.md` beside the repositories). Project `egress-drive`,
  pipeline `toy-engine`, subagent judge, hosted operator, ceiling 3: the ceiling question asked
  (declare skill 3a), the echo-back and the egress report verbatim, the two holds relayed in four
  parts, confirm first, "ok" refused, both verdicts recorded via relayed under the owner's name,
  the dispatch answered by three delegates, the delivery with the egress sentence in `summary.md`,
  the section in `coverage.md` (three invocations, highest class 3) and the `index.json` entry;
  the ceiling lowered to 2 at the terminal gave exit 11, `prov.egress_exceeds_ceiling`, relayed
  as a message with the report path and not as a hold. The owner was satisfied. Findings in
  `/lab/scratch/egress-test/findings.md` (wiped with the directory): the version, the wait, the
  "for engine" line, the brief template's missing flags, the "not assessed" line in the relay.
- The merge. `open-mode` (16 commits, a fast-forward of `main`) merged into `egress` (`43efd2b`):
  eight conflicts, every one both sides adding to the same place (`coverage.py` imports and the
  section order, the egress section written before the open-mode section's early return;
  `predicates/context.py` fields; `predicates/engine/__init__.py` imports; the toy-engine
  summary golden keeps open mode's predicate count and gains the egress sentence; the index,
  DECISIONS, roadmap and trace-schema both ways). Rehearsed first in a scratch worktree.
- This commit, after the merge: the scan's `URL` pattern no longer matches an XML namespace
  (`plot-groups` from open mode carries `xmlns="http://www.w3.org/2000/svg"` and the only failing
  test was `test_toy_modules_do_not_reach_the_network`; a case in `test_egress.py`); engine
  0.2.23 (`pyproject.toml`, `__init__.py`, `uv.lock`, the methods golden); the operator skill
  says "for engine 0.2.23" and, with the analysis template, that the wait in mode B is a job on
  the compute host, not `call_command`, whose commands end after 60 seconds (the drive's operator
  found this out); `publish-skills.md` revision lines.

## Learned

- A hosted-operator project on the subagent judge is class 3 by construction; the drive's person
  found the relay complete and free of advice. The refusal path at `declare --check` (answering
  below the setup's class) was not exercised in a session; it passed in a dry run.
- Claude Science's `call_command` ends a command at 60 seconds, so a one-day `wait` must be a job.
  The skill said "background command", which the operator read as `call_command` first.
- The script scan's `URL` pattern hits XML namespaces; the egress brief's scenario F asked for
  exactly this kind of false positive.

## Altered

- Nothing at the contract level. The merge resolution orders the data egress section before the
  open-mode section in `coverage.md`, so an open run's coverage carries both.

## Open

- The merge train, in the owner's hands: push `egress`; `main` fast-forwards to `open-mode` and is
  tagged `v0.2.22`; `egress` merges into `main` (clean after `43efd2b`) and is tagged `v0.2.23`;
  CI on each; install `0.2.23-sc0.5.1` into the shared prefix; republish the two skills; the toy
  method's `open-mode` branch merged and tagged `v0.2.0` with its analysis skill re-rendered on
  the merged template; the Xenium method's skills re-rendered and tagged; `compat/known-good.yml`
  rows; the console service restarted.
- From the egress note: the DEVIATIONS entry (`module.yml` `egress`), phase 4 (the field, lint
  failing), phase 6 (`exec` class from `executions.network`, `init --mode open --from-delivery`
  taking the upstream's ceiling), the design amendments.
- The brief template's declare variant should pass `--executor`, `--execution` and
  `--judgment-harness` (backlog).

## Verify

    uv run pytest; uv run ruff check . && uv run ruff format --check . && uv run mypy; scripts/check_no_biology.sh

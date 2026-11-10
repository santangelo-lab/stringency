# Benchmark Phase 2 started: the stringency arm runs, and a system to run it again

Session of 2026-11-10 on PROTSEQ, Claude Code. Branch `benchmark-prereg` (docs only, not
pushed). The code is in `stringency-benchmarks` (branch `phase2-adapter`) and the method
(branch `scrnaseq-pca-pipeline`), neither pushed.

## Goal

Pick the benchmark up where it stopped on 2026-10-22 (`benchmark-plan.md`, rows L87 to L92):
the owner approved a first slice of Phase 2, one harnessed arm end to end on two evals (PCA,
DE01) with the trace that hold precision and recall need. Later the same day: a plan for the
DE fixes the first replicates showed, and a system for benchmarking again as the engine and
methods change.

## Done

- Phase 0 exit read against Latch's published Opus 5 family rows (benchmarks.bio, 2026-11-08):
  our baseline model is Opus 5.5; the published Claude Code row is 56.4% on 195 evals; 9/18 on
  six is consistent and nothing sharper is testable. The owner approved proceeding.
- Pre-registration, before any stringency-arm run: `benchmark-plan.md` (7d51af3). Two fixed
  hold policies (observe, enforce), the owner's choice; hold precision and recall under
  observe; the six public scBench evals as the development set, scBench-Long's nine as
  held-out.
- The engine inside Latch's image: 0.2.40 and plugin 0.10.3 in a venv on the image's Python,
  the local executor. The method's planted fixture delivered with the planted counts, eight of
  eight controls passed, the audit was clean.
- `stringency-benchmarks` 66a7e43 to 9e707b3: the stringency arm (`latch/arms.py`), the hold
  policy as a process beside the agent (`latch/policy.py`), the method-as-prompt arm, the
  scorer (`latch/score.py`), the Phase 1 table as data (`evals/eval_predicates.yml`).
- Method `scrnaseq-pca` (68c475b on `scrnaseq-pca-pipeline`, 0.1.12, used as rc1): the
  upstream pipeline's first five steps, ending at the embedding.
- Two test replicates under the stringency arm, observe policy (`runs/dev-2026-11-10`):
  DE01 passed (1328, through open mode); PCA failed as the baseline does (depth correlation
  0.369, no flag).
- The slice (`runs/slice-2026-11`, finished 14:30): baseline 3/6, method as prompt 3/6,
  stringency under observe 0/6 (PCA 0/3 with no flag, DE01 0/3 abstained after the block);
  hold recall 0/3; 52 USD in all. `stringency-benchmarks/measurements.md` has the rows.
  Enforce deferred (Open).
- `declared-text-params.md` (81beeaa): the DE fixes as a plan, rows L163, L168, L169.
- Benchmarking over time (`benchmark-plan.md` 4446f0f; `stringency-benchmarks` 9e707b3):
  `bench.py` with stacks, suites, studies, a ledger, `history`, `compare`, `due`;
  `BENCHMARKING.md` there is the procedure.

## Learned

- Pipeline mode cannot be told a name: a parameter is ranged, optioned or fixed, and
  `param.locked_changed` blocked the DE step of a project that declared its own factor,
  reference and cell type, after `init` had accepted them (L163, L168). Open mode admits the
  same values as the person's, which is how DE01 ran.
- The method's standard ceiling for the PCA depth sentinel (0.5) is above the failing value
  (0.37 to 0.39), so the flag written for that trap does not fire, and the agent read the 0.5
  as reassurance (L165).
- A delivered JSON summary cannot be cited by an open project's answer, so the PCA answers
  went through session code and are labelled `untested` (L167).
- `declare --check` ignores the site's executor (L161). The engine's source tree must never
  be bound into an agent's container: `benchmark-plan.md` names every eval's expected values.
  The method repository carries benchmark commentary an agent can read (L164).
- A stringency replicate costs about 5.50 USD and 15 minutes against the baseline's 2 USD and
  10: the skills are read in full and the agent reads engine source when a route is unclear.
- Claude Code moved from 2.1.306 to 2.1.322 since Phase 0; old versions are removed, so the
  version is recorded per run and the baseline is rerun beside every arm (L166).

## Altered

- The approved slice named an enforce arm; it is deferred, since under the committed ceiling
  no judging hold fires on either eval and it would repeat observe.
- The first DE test replicate ran with the engine bound at its resolved path, which broke the
  venv's scripts; the agent patched around it. Stopped, kept as
  `runs/dev-2026-11-10-aborted-engine-path`, and the runner now runs `stringency probe` in the
  arm's container before the first replicate.
- No contract changed. `via: policy` (L162) and `text: declared` (`declared-text-params.md`
  (c)) are proposals for the owner.

- Later the same day, after reading what scBench-Long is (its paper, README and leaderboard,
  no eval opened): the pre-registration is amended. scBench-Long is not the held-out set for
  the scBench claim; Latch's withheld short evals are, and until then there is none (L170).
  The owner agreed. The focus is scBench; SpatialBench's baseline is parked.

## Open

- The slice is read and recorded. Next on scBench, in the owner's order: the PCA ceiling and
  the DE fixes, then the same slice again (`bench.py compare`), then the other four evals.
- The owner: the PCA ceiling (L165); `text: declared` (L163); `via: policy` (L162); whether
  SpatialBench's public evals are development or held-out; pushing the three branches.
- After the first pass: `declared-text-params.md` items (a), (b), (e), then (c), (d); the
  benchmark commentary out of the method repository (L164); the sham-gate arm; M2 and T04a.
- Stale text not yet fixed: `PLAN.md` item 8 says Phase 0 "is running"; the docs say seventeen
  SpatialBench evals where sixteen unique ones exist, and "Opus 5" for `claude-opus-5-5`.

## Verify

    cd ~/github/stringency-benchmarks
    PY=/lab/projects/2026-10_stringency-benchmark_jrrose5/.venv/bin/python
    $PY bench.py plan studies/2026-11-slice.yml     # the checks, the stack's lock, what is left to run
    $PY bench.py history                            # every eval in every study
    $PY latch/score.py /lab/projects/2026-10_stringency-benchmark_jrrose5/runs/slice-2026-11

# Compatibility, the plugin and method halves (singlecell 0.5.1, method rc14, roadmap W3 closed)

## Goal

Finish W3: the plugin repository's CI and the review's two small defects, the method's
`requires` and CI, and the first combination with `requires` on both sides checked on PROTSEQ.

## Done

- `stringency-plugins` 0.5.1 (`3aaefd5`): `spatial.coords_missing@2` checks every bound
  `xenium_bundle` and its evidence names the region that disagrees (version bumped: the check on
  existing multi-region inputs changed); `sc.decision_unreviewed` treats a `declared` or
  `inherited` decision point as a person's and says so in its reason (version kept: no earlier
  run carries those sources, the `topo.predecessor_incomplete` precedent); `VERSION` tested
  against `pyproject.toml`; tests needing the lab's data or a method checkout marked
  `institutional`, the hard-coded method path replaced by `STRINGENCY_XENIUM_METHOD`;
  `stringency>=0.2.19` with `tool.uv.sources` pinned to tag `v0.2.19`; `[tool.mypy]` with
  `tools/` excluded (eleven typing errors there, all in the extractor scripts, a later cleanup);
  `.github/workflows/ci.yml` (ruff, format, mypy, pytest). 68 tests pass against the engine
  checkout. `uv lock` and the tag `v0.5.1` wait for the engine tag to be on GitHub.
- `stringency-xenium-method` `v0.6.0-rc14` (`e44148d`): `policy.yml` `requires`;
  `flag-outlier-punches` 0.3.1 takes `design` from the job (PLAN 5.12: the walk-up never found
  one in the container, so no real run had group bands); `split-punches` 0.2.1 gates on
  `coords_missing@2`; `xenium-qc-tma` 0.1.1; `.github/workflows/ci.yml` (lint under the tags
  `requires` names, the skill check, `sync-rlib.sh --check`, `test_qc_lib.py`); the organ
  sign-off's hold view shows the QC delivery's punch table filtered by `$param.organ` (PLAN 5.8);
  the test scripts take the engine from `STR`; the upstream pipeline's header rewritten;
  `skills/README.md` to the current schema; README Develop says what needs PROTSEQ.
- Checked on PROTSEQ with the engine and plugin checkouts: `lint` clean (warnings only), `probe
  --method` ready, `tests/run_outliers.sh` (the new group-bands case, the engine run, both
  controls) and `controls/synthetic_run.sh HEAD` passed. `compat/known-good.yml` has the row.

## Learned

- The predicate registry holds one version per id, so a predicate version bump is a method
  change too: every `gates:` entry naming the old version stops resolving. `requires` is what
  makes that explicit, which is why both landed together.
- `controls/synthetic_run.sh` refuses to run without `STRINGENCY_SESSION_REF`; the README now
  says so by way of the test scripts' `STR`.

## Altered

- Nothing at the contract level.

## Open

- Owner: push the engine (`main`, tags v0.2.17 to v0.2.19); then in the plugins repository
  `uv lock`, commit, tag `v0.5.1`, push; push the method (`main`, `v0.6.0-rc14`); install
  `0.2.19-sc0.5.1` on PROTSEQ (`install.sh` now derives that label) and restart the console; run
  one organ on rc14 (it contains rc13's resolution step) before W6's acceptance run.
- The v2 upstream declarations can carry `params: {01_merge: {organ: ...}}` from the next project on.
- Next: W4 (the method checkout bound read-only; the `rlib/` copies go).

## Verify

    cd ~/github/stringency-xenium-method && STR=~/mytools/stringency/stringency/.venv/bin/stringency bash tests/run_outliers.sh

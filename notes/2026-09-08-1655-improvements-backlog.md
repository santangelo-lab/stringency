# Improvements backlog worked through on the toy

## Goal

Work `spec/improvements.md` in its stated order on the toy pipeline before Phase B: the review
display, operator ergonomics, trace semantics, toy-method and judgment-contract edits, the design
and skill text, then the review packet. Everything below the contract level; nothing frozen
reshaped.

## Done

Five commits on `main`, one per step of the backlog order (`git log f5b2167..741012a`).

- **A1 review display** (f5b2167): `src/stringency/review_render.py` renders design 7.3 per hold
  kind: confirm (echo-back and digests), flag (predicate, evidence one entry per line,
  parameters, the state the gate read, the execution row), judgment-predicate flag (every
  flagged replicate and item with its judgment row, cited cells resolved against the evidence
  table as `table[row].column = stored` or `cited x, stored y`, the failed criterion, the
  quoted rationale), and the two item kinds (evidence row, calls grouped by label, each
  replicate's cites and rationale). Verdict block states what each verdict does with the exact
  command; no recommendation. Golden per kind in `tests/golden/review_*.txt`. The toy-cs judges
  are replayed by `tests/fixtures/harness/context_contradicting.yml` (mock refs may now be
  dicts naming another row). Rendered against the real `toy-cs` trace: the flag hold that took
  four files to answer now prints in one screen.
- **A2, A3** (f5b2167): every hold message names the hold id and `stringency review --hold
  <id>`, which shows that one hold; owner holds name the owner, not the reviewer; `init` exits
  10 while its confirm hold is open.
- **B1, B2, B3, C1, C2** (e85fb0d): at ticket time the engine creates the step directory and
  writes `job.json`; the job spec carries `exec` (the executor's exact argv, from a new
  `Executor.command_line` that `run` itself uses) and `submit` (concrete paths, `--command`
  quoting `exec`); `submit --command` records the operator's account in `executions.command`;
  `executions.expected_env_digest` (migration `0002`) holds the resolved digest and `env_digest`
  is null unless verified; `status --json` lists the confirm hold and every open hold with id;
  `run` on a closed run exits 16 naming `run --new`, `propose` and `submit` inherit it.
- **C3, D1** (f1f951d): every judgment prompt ends with `prompting.evidence_suffix`, the
  definition of the two evidence slots and the policy's confidence criteria; the same text is
  in `spec/module-contract.md`. Toy operator modules declare `apptainer_inspect` evidence; the
  ticket's `evidence_commands` produce it as `{ apptainer inspect --json <image>; sha256sum
  <image>; } > inspect.json`, because a pulled SIF's labels carry no digest of the file (checked
  on `~/envs/toy-py.sif`). The parser reads the checksum line; a reported digest that disagrees
  with the manifest is `as_reported` and `exec.plan_drift` rejects it. Toy modules and pipelines
  are 0.1.1 in the plugin template and in `~/github/stringency-toy-method` (tagged `v0.1.1`,
  not pushed to the `/data-raid` bare mirror).
- **A4, D2, E1, E2, E3** (741012a): a review packet per open hold at
  `runs/<run>/<step>/review/<hold_id>.{md,html}` with the review render verbatim, named in the
  hold message and `review --json`; design 10.4 says the sandbox cannot start containers and
  remote mode is the default for apptainer projects; design 10.2 and 19 record that delegate
  isolation is instructional and `as_reported`; the skill names the brief's `PRE` line as the
  app-version route; the integration README documents `install.sh --prefix
  ~/.local/lib/stringency` for compute hosts.

Tests: 213 pass, 1 skipped (apptainer on PATH). ruff, mypy, `check_no_biology.sh` clean.
DECISIONS gained fourteen lines (from "The review display (7.3) lives in" onward).

## Learned

- `apptainer inspect --json` on an image pulled from Docker Hub reports build labels only; no
  digest of the SIF and no path. Environment verification for operator steps needs the
  checksum line, so the ticket asks for it.
- The name-match route in `env_status` let a wrong digest verify when the checksum line named
  the right path; a reported digest is now decisive.
- Under the local executor the run's env digest is a lockfile hash, so operator-reported image
  digests can only be exercised on an apptainer project; the test uses a fake `apptainer`
  script through `STRINGENCY_APPTAINER_BIN`.
- The `review_render` module imports `steps`, so the hold-open sites in `steps.py` import it
  locally when writing packets.

## Altered

Below contract level only. Design text edited at decisions level: 2.6 (`run` refuses on a
closed run; `--new`), 9.4 (`expected_env_digest` column added, nothing reshaped), 10.2 and 10.4
and 19 (observations recorded), 14.1 (`review --hold`, `run --new`, `submit --command`).
`spec/review-ux.md` now says layers 1 and 2 are built. The integration skill's ticket loop is
"run `exec`, run `evidence_commands`, run `submit`".

## Open

1. PROTSEQ half of the exit on the updated engine: install apptainer and uv (sudo), copy the
   SIF, `scripts/install.sh` (machine-wide or `--prefix ~/.local/lib/stringency`), push
   `v0.1.1` of the toy method to the bare mirror at
   `/data-raid/Projects/Jim/stringency-exit/kit/stringency-toy-method.git` (or point the project
   at `~/github/stringency-toy-method`), then a fresh toy project bound to `v0.1.1`. Count
   authorization points (B4) and check that operator steps show `verified` (C3) and no
   `judg.confidence_consistent` flag from context cells (D1). The BMESEQ machine install at
   `/usr/local/lib/stringency/current` is still the pre-backlog build; re-run `install.sh`.
2. E2 stays partly open: whether the app exposes its version to the session was not checked
   from here; the next exit run should look and record it.
3. Then `v0.1.0` tag, public repo, singlecell push, Phase B.
4. Planted controls still unscored (unchanged).

## Verify

```
cd ~/github/stringency && uv run pytest -q && uv run ruff check . && uv run mypy && scripts/check_no_biology.sh
cd /data-raid/Projects/Jim/stringency-exit/toy-cs && ~/github/stringency/.venv/bin/stringency review --hold 01M217F5B018Q3NDQS9XS3MPN6
uv run stringency lint ~/github/stringency-toy-method
```

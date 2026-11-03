# 2026-11-03 21:00: the beta-tester package's engine changes

## Goal

The engine side of the beta-tester package (`~/mytools/stringency/stringency-beta-tester-package-plan.md`
and its implementation plan beside it): what a tester's Mac with no container runtime needs,
what the bundle reads, and the after-delivery flag. Branch `beta-mac`.

## Done

- `c33bddd` CI: the suite on `macos-latest` (the mock harness and the local executor). The first
  spike of the Mac path; nothing on a Mac has been tried yet.
- `8d3a577` The site's executor: `~/.config/stringency/config.yml` `executor:`; `init` uses it
  when `--executor` is not given; `probe --method` under a local site reports images as not
  needed and fails an environment without a lock. The local executor activates
  `envs/<env>/.venv` (python, PATH, `VIRTUAL_ENV`) or an renv project (`RENV_PROJECT`,
  `R_PROFILE_USER`) when present, else runs as before. Docs in `install.md` and
  `method-author.md`; DECISIONS.
- `61b3f7a` `status --json` `sessions`: the distinct operator session references over runs,
  reviews and artifacts, with harness, version, first and last seen, runs and review counts.
- `58dfb99` `stringency flag`: migration 0008 `flags` (append-only), `flags.py`, the verb, the
  console's run page form beside each delivered file and once for the run (`POST /flag/<run>`,
  recorded as the serving account, `via: web`; none on the read-only instance), `present_run`
  and `/api/run/<id>` carry `flags`; trace-schema row; DECISIONS.
- `651eb3e` docs: the beta channel in `release.md`; the publish message on a machine of one's own.
- The full suite green after each package (`uv run pytest`, 2026-11-03).

## Learned

- The survey corrected the plan in thirteen places (implementation plan section 1): the scanpy
  method had no lockfile; the toy's lock is a stub; `init` defaulted to apptainer with no site
  default; `probe` judged any image; the session reference was already on every run and review;
  `review --serve` already prints the tokenised URL and takes `--token-file`; the console's JSON
  routes exist; the only Linux reads are `/proc` in `active.py` and `db/store.py`, both failing
  soft; the bootstrap prefix is `~/.local/lib/stringency`, which the operator skill already
  searches.
- `_href` on the console returns the path unchanged: the token travels by cookie after the
  first tokened visit, so the flag form needs no hidden field.

## Altered

- Two DECISIONS entries (the site executor and the activated environment; the flags table).
- `spec/trace-schema.md`: the `flags` row. The tables of design 9.4 are untouched.

## Open

- PR #17 open. The first macOS job: 636 passed, 4 skipped, 1 failed on a width assertion over a
  macOS temp path (`test_packets.py`, fixed in `66fc982`); no engine code broke on Darwin. The
  re-run's result, then merge and tag v0.2.37.
- The public toy method at v0.2.0 fails lint on 0.2.36 (`judg.numeric_claims_match@1`); the
  engine's in-repo toy copied over it as 0.3.0 (toy PR #1, `requires >=0.2.27`).
- The operator skill does not yet name `flag` (a person saying in chat that a result is wrong
  should become a relayed flag); filed as L147. `audit` does not read `flags` (as it does not
  read `findings`); L148.
- M1 in the scanpy method (`envs-lock` branch): the lockfile environment built and verified
  identical to the image on the planted fixture; to tag v0.1.11 and add a known-good row once
  v0.2.37 exists.
- The beta repository (`~/github/stringency-beta`) skeleton written; the CLI next.

## Verify

    uv run pytest tests/test_compat.py tests/test_m11.py tests/test_run.py tests/test_flags.py

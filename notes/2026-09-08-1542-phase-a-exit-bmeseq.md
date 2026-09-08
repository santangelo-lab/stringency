# Phase A exit on BMESEQ, driven from Claude Science

## Goal

Run the Phase A exit (build plan, "Phase A exit") on BMESEQ: the toy pipeline driven from a
Claude Science session with the subagent harness and the apptainer executor, then confirm the
design 10.4 assumptions and the section 19 questions that concern the engine.

## Done

- Preparation on BMESEQ: `~/.local/bin/apptainer` symlink to singularity-ce 4.2.1; toy SIF at
  `~/envs/toy-py.sif` (python:3.12-slim, sha256 `03a05256…858f7`); toy method as its own git
  repo at `~/github/stringency-toy-method`, tagged `v0.1.0`, manifest pointing at the SIF, with
  a bare mirror at `/data-raid/Projects/Jim/stringency-exit/kit/stringency-toy-method.git`;
  declarations and data staged under `/data-raid/Projects/Jim/stringency-exit/`; helper scripts
  and the two operator briefs under `.../stringency-exit/tools/`.
- Engine fixes found by the first containerized init (uncommitted at the time of writing, see
  Open): portable interpreters (`python3`, resolved to the engine venv by the local executor) and
  inferred binds in the apptainer executor; `apptainer` falls back to `singularity`, overridable
  by `STRINGENCY_APPTAINER_BIN`. Tests in `tests/test_m11.py`; three DECISIONS lines.
- Deployment: `scripts/install.sh` installs a versioned venv at
  `/usr/local/lib/stringency/{versions/<v>,current,envs}` on the system python; installed on
  BMESEQ. `integrations/claude-science/` holds a generic operator skill (two modes: engine in the
  sandbox, engine on a registered compute host), a project agent-context text, and a README.
- Hand rehearsal of the full toy pipeline through the CLI in a scratch project (all five steps,
  hand-written dispatch responses, deliver), then the real exit run in
  `/data-raid/Projects/Jim/stringency-exit/toy-cs`, project `01M216V6NKHXFHVTY88FSBP4S4`, run
  `01M2172HKP6E3RNQNEPP6DSFCE`: driven from a Claude Science session on Jim's MacBook with
  BMESEQ registered as an SSH compute provider. Init confirm and one flag hold accepted by Jim at
  a terminal (`via: tty`). Three fresh delegates answered the dispatch, each given only its
  request path; all reported `claude-opus-5`. Five steps completed, delivered, coverage report
  with no uncovered decision points, methods paragraph correct. Trace: 5 executions (2 engine
  verified, 3 operator as_reported), 3 invocations via subagent, 9 judgments, 85 predicate
  results, 7 artifacts, 2 reviews, 1 delivery; runs row carries host, operator harness, version
  `unknown`, and the session frame id.
- Exit checks: `propose 02_summarize` while step 1 is held exits 10, while step 1 awaits
  execution exits 15; a fabricated ticket is refused with 15; `lint` on the method with the
  negative control removed exits 15 naming the missing control.
- `spec/review-ux.md`: working notes on the review surface (see Learned); design 17 gains the
  deferred review page. `spec/improvements.md`: the full backlog from this run, ordered, to
  work through on the toy before Phase B.
- An earlier hand-started project at `.../stringency-exit/toy`, parked at its dispatch, and the
  interim `kit/venv` and `kit/bin` were deleted at session end; `kit/stringency-toy-method.git`
  stays, since the `toy-cs` trace names it as the method repo.

## Learned

- The Claude Science sandbox (bwrap) can run the CLI but cannot start a container: singularity
  fails the user lookup for an Active Directory uid inside the sandbox, and home directories are
  not mounted. So design 10.4's "sandbox that can execute the CLI" holds only for the CLI; an
  apptainer project is driven through a registered SSH compute host, from the workstation or a
  laptop. Recorded in the integration README.
- Section 19 answers: delegates exist and start with a fresh context, but cannot be restricted
  to one file; isolation is instructional, which is what the engine records (`as_reported`).
  They report model identity and tools. A frame id serves as the session reference. The app
  exposes artifacts through its own store; the deliver directory on the workstation is the
  durable copy.
- The first real flag hold (`judg.confidence_consistent`, judges citing context cells as
  contradicting evidence) showed that `review` prints counts where design 7.3 promises content;
  answering the hold took reading four files by hand. Also: the `run` hold message omits the
  hold id; `init` exits 0 with an open confirm hold; the operator had to create the step
  directory before writing job.json. All in `spec/review-ux.md`, order of work at the end.
- `run` issues the ticket itself with default parameters; `propose` is only for changing one.
  Calling `run` after the final submit opens a new run; go straight to `deliver`.
- Cost of the remote mode: 25 authorization points for the toy run (19 commands, 6 downloads).
- No `sqlite3` CLI on BMESEQ; use python. PROTSEQ has no apptainer, singularity, or uv.

## Altered

Nothing in a frozen contract. Design 17 gains one deferred row (review page). DECISIONS gains
entries for interpreter portability and binds, apptainer/singularity discovery, the install
layout and integration directory, and the deferred review page.

## Open

1. Work `spec/improvements.md` in its stated order (review display first, then operator
   ergonomics and trace semantics, then toy-method and judgment-contract edits), using the
   `toy-cs` trace as a fixture. `spec/review-ux.md` has the review surface in depth.
2. PROTSEQ half of the exit: install apptainer and uv (sudo), copy the SIF to `~/envs`, run
   `scripts/install.sh`, repeat the run. Then tag `v0.1.0`, make the repo public, install from
   the tag on both machines, push the singlecell skeleton, and update the design 10.4 text.
3. Planted controls still unscored (unchanged from the previous note).

## Verify

```
cd ~/github/stringency && uv run pytest -q && uv run ruff check . && uv run mypy && scripts/check_no_biology.sh
/usr/local/lib/stringency/current/bin/stringency plugins list
cd /data-raid/Projects/Jim/stringency-exit/toy-cs && /usr/local/lib/stringency/current/bin/stringency status
```

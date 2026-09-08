# Agent reports from the toy-cs exit run, 2026-09-08

Trimmed to the parts a new user should recognise. Session on a MacBook; compute provider
`bmeseq`; engine 0.1.0.dev0; run `01M2172HKP6E3RNQNEPP6DSFCE`.

## Phase 0

    uid=557268736 ... BMESANT-SEQ
    engine   /usr/local/lib/stringency/current/bin/stringency
    runtime  apptainer (singularity-ce 4.2.1)
    plugin   stringency-toy 0.1.0
    image    /home/jrrose5/envs/toy-py.sif, 42,377,216 bytes
    container start: Python 3.12.14

The agent noted it would record `STRINGENCY_OPERATOR_VERSION=unknown` rather than guess the app
version, and gave its frame id as the session reference. One approval card.

## Phase 1

    project 01M216V6NKHXFHVTY88FSBP4S4 bound at /data-raid/Projects/Jim/stringency-exit/toy-cs
    method /data-raid/Projects/Jim/stringency-exit/kit/stringency-toy-method.git @ v0.1.0 (567decf5f3de)
    echo-back written to .../toy-cs/echo.md
    held: confirm 01M216V74JVG8HHKHFYGV7BGWB waits on owner jrrose5

The agent printed the hold id, did not open `echo.md`, and stopped. It flagged that `init`
exited 0 while leaving a hold open (backlog item A3). The owner accepted at a terminal.

## Phase 2

| step | exit | what happened |
|---|---|---|
| run | 21 | ticket for 01_filter |
| 01_filter | 0 | ran in the container, `kept 41 of 50 rows`; submitted object.csv and run.log |
| 02_summarize | 0 | same shape |
| 03_label | 20 then 10 | three requests, three fresh delegates, three responses written; then a flag hold |

The hold: `judg.confidence_consistent` on 03_label. The agent reported the step and reviewer,
noted the message carried no hold id (backlog A2), and stopped. The owner reviewed and accepted
at a terminal. The agent also had to create the step directory before writing job.json (B1).

Delegates: each given only its request path, fetched it itself, returned JSON with its own nonce;
all reported `claude-opus-5`, a fresh frame, `saw_conversation: false`.

## Phase 3

    5 declared, 5 completed; 22 predicates evaluated; 0 block, 1 flag, 3 log
    3 operator-run steps as_reported, 2 engine-run verified; 0 plan drift
    label-groups: 3 items x 3 replicates, 3 agreed; override rate 0/3

Delivered `coverage.md`, `methods.md`, `index.json` (copies in `deliver/`). The agent counted 25
authorization points and pointed out, correctly, that `as_reported` on the operator steps means
the engine recorded its claim about the container rather than verifying it (backlog C3).

# Joining stringency on PROTSEQ

For a lab member who will run an analysis under stringency, and for the computational member who
sets them up. Design: `spec/plans/ux-two-audiences.md` section 7. Host detail:
`hosts/protseq-lab.md`. Nothing here needs `sudo`.

## Once, for the new member (a computational member does 1 and 2 with them)

1. **Group membership.** Ask IT to add the member's Emory AD account to `bme-santangelo-lab`.
   This gates `/data/lab` on PROTSEQ and on BMESEQ at once; nothing local substitutes for it.
   Check from PROTSEQ with `id <user>` once IT confirms.
2. **SSH alias.** On the member's laptop, an SSH config entry named `protseq` for their own AD
   account and key. Test: `ssh protseq id -gn` prints `domain users` and `ssh protseq id -Gn`
   lists `bme-santangelo-lab`.
3. **PATH line.** On PROTSEQ, in the member's `~/.profile`:

       export PATH=/data/lab/env/stringency/current/bin:$PATH

   Test from the laptop: `ssh protseq 'bash -lc "stringency plugins list"'` prints the plugins.
4. **Claude Science instance.** The member's own instance, not a shared one, so that every
   command runs as them and every review verdict is recorded against their account. In it, once:
   - compute provider `protseq` (SSH, using the alias above);
   - data root `/data/lab/projects`;
   - the skill publish cell (`publish-skills.md`): the operator skill, the declare skill, and each
     method's analysis skill when one exists.
5. **Optional, a review page.** `scripts/review-page.sh protseq` (engine repo) on the member's
   laptop opens an SSH tunnel and starts `stringency review --serve` on PROTSEQ as them; the URL
   it prints, with its one-time token, lists their open holds and records verdicts as `via: web`.
   Started by the member, never by an agent and never by someone else on their behalf. Holds
   answered in the chat are recorded as `via: relayed`; both appear in the trace.

## Once, for the setter-up

- Project area: the member's projects go under `/data/lab/projects/<YYYY-MM>_<topic>_<user>/`
  (the dated convention already in use). The default ACL makes whatever they create
  group-writable; nothing to chmod.
- Roles: unless the brief names someone else, the analysis skill passes
  `--owner $(id -un) --reviewer $(id -un)`, so the member is their own reviewer under the
  `standard` profile with `relayed_review: true`. Name a second reviewer when the analysis is
  manuscript-bound.
- Raw data: deposit with the `raw-deposit` skill into `/lab/raw/<delivery>/` with checksums; the
  member's declarations then point there.

## What to expect (for the member)

You describe the experiment in your own words, point at the data, and answer a few plain
questions. The assistant drafts the three declaration files, shows you an echo of what it
understood, and waits for your yes before anything runs. From then on it runs the pipeline and
reports progress in sentences. When a check fires or a judgment is uncertain, the run stops and
the assistant tells you where it paused, what the engine recorded, and the verdicts you may give.
It lists the options the engine lists and adds none. You choose, in your words, and your choice
and reason go into the record with your account name. Nothing is excluded, corrected or decided
without you.

Every number you read comes from an engine output; the assistant's own reading of a result is
labelled as its reading and never enters the delivered files. At the end you receive the
deliverables, a methods paragraph, a coverage report naming every check that ran and every one
that did not, and a one-page summary written for a reader who did not watch the run.

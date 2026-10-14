# Joining a stringency host

For a lab member who will run an analysis under stringency on a machine that is already set up
(`docs/install.md`), and for the computational member who sets them up. Nothing here needs
`sudo`. Fill in your site's values (`<group>`, `<alias>`, `<prefix>`, `<projects>`, `<raw>`).

## Once, for the new member (a computational member does 1 and 2 with them)

1. **Access to the machine and its data.** Membership in the group that owns the install and the
   project area (`<group>`; on a managed machine that is a directory group requested from IT, and
   nothing local substitutes for it). Check with `id <user>` once it is granted.
2. **SSH alias.** On the member's laptop, an SSH config entry for the host under their own
   account and key (`<alias>`). Test: `ssh <alias> id -Gn` lists the group.
3. **PATH line.** In the member's `~/.profile` on the host:

       export PATH=<prefix>/current/bin:$PATH

   Test from the laptop: `ssh <alias> 'bash -lc "stringency probe"'` ends with `ready`.
4. **An AI session of their own.** Either Claude Code run on the host under their account, which
   needs nothing more (it reads the skills beside the engine), or their own Claude Science
   instance, where three one-time steps remain: add the host as an SSH compute provider under
   the alias, set the project area as a data root, and paste the skill-publishing message from
   `integrations/claude-science/publish-skills.md` into a session. Their own instance, not a
   shared one, so every command runs as them and every verdict is recorded against their account.
5. **The console.** Holds are answered on the console (`stringency review --serve`, started by
   the member under their own account, or the standing service with its tunnel,
   `scripts/review-page.sh <alias> <projects>`) or in the chat; both are recorded, as `via: web` and
   `via: relayed`. Never answer a hold on someone else's behalf and never start a console for
   someone else: the page records the account that serves it.

## Once, for the setter-up

- Project area: `<projects>/<YYYY-MM>_<topic>_<user>/` (a dated convention).
  The default ACL makes whatever they create group-writable; nothing to chmod.
- Roles: unless the brief names someone else, the analysis skill passes
  `--owner $(id -un) --reviewer $(id -un)`, so the member is their own reviewer under the
  `standard` profile. Name a second reviewer when the analysis is manuscript-bound.
- Raw data: deposited with checksums into `<raw>/<delivery>/`; declarations point there.

## What to expect

To start an analysis you open a session and describe the experiment; the method's analysis
skill takes it from there (`integrations/claude-science/new-project.md`, "For a person").
You describe the experiment in your own words, point at the data, and answer a few plain
questions. The assistant drafts the three declaration files, shows you an echo of what it
understood, and waits for your yes before anything runs. From then on it runs the pipeline and
reports progress in sentences. When a check fires, a parameter needs your approval, or a judgment
is uncertain, the run stops and the assistant tells you where it paused, what the engine recorded,
and the verdicts you may give. It lists the options the engine lists and adds none. You choose,
in your words, and your choice and reason go into the record under your account. Nothing is
excluded, corrected or decided without you.

Every number you read comes from an engine output; the assistant's own reading of a result is
labelled as its reading and never enters the delivered files. At the end you receive the
deliverables, a methods paragraph naming the engine, plugin and method versions, a coverage
report naming every check that ran and every one that did not, and a one-page summary written
for a reader who did not watch the run.

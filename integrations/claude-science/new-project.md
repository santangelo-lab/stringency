# Running an analysis from Claude Science

## For a person

Once, with the help of whoever set the machine up (`docs/onboarding.md`): your account in the
lab group, an SSH alias to the workstation, and the PATH line. Then, in your own Claude Science
instance, once:

1. Add the workstation as an SSH compute provider under your alias (Customize, compute). Every
   command then runs on the workstation as you.
2. Set the project area (`<projects>`) as a data root, so reading
   results there does not raise a card each time.
3. Paste the skill-publishing message from `publish-skills.md` into a session. The session
   publishes the engine's skills and each method's analysis skill; you get a list back.

Per analysis, nothing to set up. Open a session and describe the experiment in your words: what
the data is and where it is, what you want out of it, and the organ or the groups if the method
asks. The method's analysis skill (for Xenium, `stringency-analyze-xenium-upstream`) loads from
that description. It asks you a few plain questions one at a time, shows you the engine's reading
of your experiment and waits for your yes, then runs the pipeline and reports progress in
sentences. When the run needs a decision it stops and tells you what it is asking and the
choices; you answer in the chat or on the console. At the end you get the deliverables, a methods
paragraph, a coverage report and a one-page summary. Then it offers to answer questions of the
delivered results (open mode): it proposes paths, asks for your yes, and labels every answer
trusted or untested from what ran (`docs/open-mode.md`).

If the method has no analysis skill yet, say "set up a stringency project for <pipeline> on
<data>" instead; the session follows the operator checklist below and still presents every
decision to you the same way.

## For the AI (the operator's checklist)

### On the workstation, once

1. Engine installed (`docs/install.md`). Check with `stringency probe --method <url>@<tag>`,
   which also checks the method's `requires` and images.
2. Container runtime present (`apptainer` or `singularity`) and the method's images where the
   site keeps them (`images_root` in `~/.config/stringency/config.yml`, or the paths the
   manifest names).
3. The method repository reachable by git URL from the workstation, tagged.
4. Data on the array, and the three declaration files (`objective.yml`, `design.yml`,
   `inputs.yml`) in the project's parent directory. `inputs.yml` carries the blake3 of each input.
   Write them by hand, or let the agent draft them from your brief and a sample manifest with the
   `stringency-declare` skill, which checks them with `declare --check` and shows you the
   echo-back before `init`.

### In Claude Science, once per instance

5. Add the workstation as an SSH compute provider under its SSH alias (Customize, compute).
   Set the project area, `<projects>`, as a data root so file
   downloads inside it do not each raise an approval card.
6. Publish the skills if the instance does not have them (`publish-skills.md`): the operator and
   declare skills, and the analysis skill of each method the person will use.

### Per project

7. Render the two texts on the workstation. For a project that `init` has not created yet:

        $(dirname "$(readlink -f "$(command -v stringency)")")/python integrations/claude-science/render_brief.py \
            <projects>/<project> --provider <alias> \
            --method <url>@<tag> --pipeline <name> > brief.md
        $(dirname "$(readlink -f "$(command -v stringency)")")/python integrations/claude-science/render_brief.py \
            <projects>/<project> --provider <alias> \
            --method <url>@<tag> --pipeline <name> --context > context.md

   For a project already bound, drop `--method` and `--pipeline`; the renderer reads
   `stringency.yml` and the manifest, and the brief skips the init phase.
8. Create the project in Claude Science. Paste `context.md` into its Agent Context.
9. Paste `brief.md` as the first message and ask for Phase 0 only. Read the probe.
10. Tell the agent to run Phase 1. It ends with a confirm hold, which the agent presents by the
    skill's hold protocol: where it paused, what the engine recorded, the verdicts with their
    effects, and the ask. Answer with a verdict word and your reason in the chat; the agent
    records it with `review --attest` under your name, `via: relayed`. Or accept at your terminal:

        cd <project> && stringency review --verdict accept --hold <id> --reason "echo-back matches"

11. Tell the agent to start Phase 2. Every exit 10 comes back to you the same way. When the agent
    reports the run completed and delivered, the deliverables are in `<project>/deliver/<run_id>/`,
    and `summary.md` there is the page written for you.

### What to expect

The measurement table in `spec/plans/measurements.md` has one row per measured run: the toy took 25
authorization points on 2026-09-08 and 7 turns in 15 minutes through its analysis skill on
2026-09-23 under a project-scoped command grant; the pilot study's QC chain of 2026-10-06 ran
eleven projects with 31 holds in under three hours.

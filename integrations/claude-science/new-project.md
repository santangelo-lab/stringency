# New Claude Science project for a stringency run (compute over SSH)

Time to first `run`: about ten minutes once the workstation is prepared. Nothing in this mode
runs in the Claude Science sandbox, so no directory grants are needed.

## On the workstation, once

1. Engine installed (`docs/install.md`). Check with `stringency probe --method <url>@<tag>`,
   which also checks the method's `requires` and images. On PROTSEQ the install is shared at
   `/data/lab/env/stringency/current/bin` (`hosts/protseq-lab.md`).
2. Container runtime present (`apptainer` or `singularity`) and the method's images where the
   site keeps them (`images_root` in `~/.config/stringency/config.yml`, or the paths the
   manifest names).
3. The method repository reachable by git URL from the workstation, tagged.
4. Data on the array, and the three declaration files (`objective.yml`, `design.yml`,
   `inputs.yml`) in the project's parent directory. `inputs.yml` carries the blake3 of each input.
   Write them by hand, or let the agent draft them from your brief and a sample manifest with the
   `stringency-declare` skill, which checks them with `declare --check` and shows you the
   echo-back before `init`.

## In Claude Science, once per instance

5. Add the workstation as an SSH compute provider under its SSH alias (Customize, compute).
   Set the project area, for example `/data/lab/projects/<area>`, as a data root so file
   downloads inside it do not each raise an approval card.
6. Publish the skills if the instance does not have them (`publish-skills.md`): the operator and
   declare skills, and the analysis skill of each method the person will use.

## Per project

7. Render the two texts on the workstation. For a project that `init` has not created yet:

        $(dirname "$(readlink -f "$(command -v stringency)")")/python integrations/claude-science/render_brief.py \
            /data/lab/projects/<area>/<project> --provider <alias> \
            --method <url>@<tag> --pipeline <name> > brief.md
        $(dirname "$(readlink -f "$(command -v stringency)")")/python integrations/claude-science/render_brief.py \
            /data/lab/projects/<area>/<project> --provider <alias> \
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

## What to expect

The measurement table in `spec/plans/backlog.md` has one row per measured run: the toy took 25
authorization points on 2026-09-08 and 7 turns in 15 minutes through its analysis skill on
2026-09-23 under a project-scoped command grant; the Lyons CLP chain of 2026-10-06 ran eleven
projects with 31 holds in under three hours. `examples/toy-cs/` has the texts of the first run and
the agent's reports.

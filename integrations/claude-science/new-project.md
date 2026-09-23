# New Claude Science project for a stringency run (compute over SSH)

Time to first `run`: about ten minutes once the workstation is prepared. Nothing in this mode
runs in the Claude Science sandbox, so no directory grants are needed.

## On the workstation, once

1. Engine installed: `scripts/install.sh` from a checkout (see the integration README). Check
   with `stringency plugins list`. On PROTSEQ the install is shared at
   `/data/lab/env/stringency/current/bin` (`hosts/protseq-lab.md`, `hosts/protseq-shared-install.md`).
2. Container runtime present (`apptainer` or `singularity`) and the method's images at the paths
   its `envs/manifest.yml` names.
3. The method repository reachable by git URL from the workstation, tagged.
4. Data on the array, and the three declaration files (`objective.yml`, `design.yml`,
   `inputs.yml`) in the project's parent directory. `inputs.yml` carries the blake3 of each input.
   Write them by hand, or let the agent draft them from your brief and a sample manifest with the
   `stringency-declare` skill, which checks them with `declare --check` and shows you the
   echo-back before `init`.

## In Claude Science, once per instance

5. Add the workstation as an SSH compute provider under its SSH alias (Customize, compute).
   Set the project area, for example `/data-raid/Projects/<you>/<area>`, as a data root so file
   downloads inside it do not each raise an approval card.
6. Publish the `stringency-operator` skill if the instance does not have it (README, "Operator
   skill").

## Per project

7. Render the two texts on the workstation. For a project that `init` has not created yet:

        /usr/local/lib/stringency/current/bin/python integrations/claude-science/render_brief.py \
            /data-raid/Projects/<you>/<area>/<project> --provider <alias> \
            --method <url>@<tag> --pipeline <name> > brief.md
        /usr/local/lib/stringency/current/bin/python integrations/claude-science/render_brief.py \
            /data-raid/Projects/<you>/<area>/<project> --provider <alias> \
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

The toy pipeline (five steps, one judgment) took 25 authorization points in this mode on
2026-09-08: 19 commands, 3 request downloads by delegates, 3 deliverable downloads. Two holds
needed the owner: the init confirm and one predicate flag. `examples/toy-cs/` has the texts as
used and the agent's reports.

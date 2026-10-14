# Claude Science integration

What a Claude Science session needs to drive a stringency project, and how to set one up.
A person reads two short sections: `new-project.md` "For a person" (the three one-time steps in
the instance, then describing an experiment to start an analysis) and `publish-skills.md` "For
a person" (one message to paste). Everything else here is for the AI: the operator's checklist in
`new-project.md`, `render_brief.py` for the two texts a project needs, `examples/toy-cs/` for a
completed run (the example runs with their real paths live in the lab's private repository).

## Files

| path | what |
|---|---|
| `new-project.md` | checklist: workstation once, app instance once, per project |
| `publish-skills.md` | the cell that publishes the engine and analysis skills into an instance, and when to republish |
| `render_brief.py`, `templates/` | render the session brief and the agent context from a project's `stringency.yml` |
| `stringency-operator/SKILL.md` | the skill: find the engine, the rules, the run loop, in two modes |
| `agent-context.md` | generic agent context; prefer the rendered one |
| `stringency-declare/SKILL.md` | drafts the three declaration files from a brief and a sample manifest, checks them with `declare --check`, runs `init --drafted-by agent` |
| `render_skill.py`, `templates/analyze-skill.md.j2` | render a method repository's `skills/<pipeline>.analyze.yml` to its analysis skill `skills/stringency-analyze-<name>/SKILL.md` (design 10.4); `--check` validates against the pipeline and modules |

## Machine install

`docs/install.md`. The engine is installed once per machine, images live where the site's
`images_root` says, and
`stringency probe` reports what is there. A session reaches the engine over SSH (mode B), so no
machine-wide location inside the sandbox is needed.

## Where the session runs

Tested on a lab workstation, 2026-09-08: a Claude Science sandbox on the workstation can run the CLI but
cannot start a container (`singularity` fails the user lookup for an Active Directory uid, and
nested namespaces are blocked). So a session drives an `apptainer` project through a registered
SSH compute provider, which runs commands on the workstation as the user, outside any sandbox.
The session itself can be on the workstation or on a laptop; the trace and deliverables are
written on the workstation either way.

## The skills

`stringency-operator/SKILL.md` (find the engine, the rules, the run loop, the hold protocol) and
`stringency-declare/SKILL.md` (draft the declarations) are the engine's skills; each method
carries its analysis skills. A person publishes them into their own instance by pasting the
message in `publish-skills.md` ("For a person") into a session with the workstation as a compute
host; the session downloads the current texts from `<prefix>/current/skills/` on the host and
publishes them. Republish after an engine release or a method tag.

Session test 3.4 of `spec/plans/ux-two-audiences.md`, measured 2026-09-15: delegate
downloads of request files and the operator's downloads of delivered files raise one card each
even inside a configured data root (7 of 17 cards on the toy-engine drive). Answered
2026-09-23 by the owner in the app: the
`download` card offers "allow for this conversation" scoped to the file's parent directory on the
host, and names the app's scratch directory as the only path it reads without asking; the
`call_command` card offers once, this conversation, this project, or global, and a project-scoped
grant covered every later `stringency` command without a card. The measured toy run through the
analysis skill (section D of the same checklist) gives the count under those grants.

## Rendering the brief and context

    <engine bin>/python integrations/claude-science/render_brief.py <project> --provider <alias> [--context]

Bound project: reads `stringency.yml` and the method manifest. Unbound: add `--method <url>@<tag>
--pipeline <name>`, and the brief includes the init phase. `--app-version` fills the operator
version the trace records; without it the agent records `unknown`.

## Project agent context

Claude Science lets a project carry an agent context that is added to every agent's system
prompt in that project. `agent-context.md` is the text to paste there. It is short on purpose:
it names the install location, the identity variables, and the hold rule, and points at the
skill for everything else. The skill can be discovered without it; the context makes the rules
hold even when discovery does not fire.

## Starting a project

Grant the project's parent directory read-write. The owner runs `stringency init` and accepts
the echo-back at a terminal, or asks the agent to run `init` and then accepts the hold it
reports. From there the agent follows the skill: `run`, tickets, dispatch, `deliver`.

The sandbox masks the hostname as `localhost`; the run's host capture will say so.

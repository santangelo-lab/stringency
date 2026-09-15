# Claude Science integration

What a Claude Science session needs to drive a stringency project, and how to set one up.
`new-project.md` is the step-by-step checklist; `render_brief.py` produces the two texts a
project needs; `examples/toy-cs/` shows a completed run.

## Files

| path | what |
|---|---|
| `new-project.md` | checklist: workstation once, app instance once, per project |
| `render_brief.py`, `templates/` | render the session brief and the agent context from a project's `stringency.yml` |
| `stringency-operator/SKILL.md` | the skill: find the engine, the rules, the run loop, in two modes |
| `agent-context.md` | generic agent context; prefer the rendered one |
| `stringency-declare/SKILL.md` | drafts the three declaration files from a brief and a sample manifest, checks them with `declare --check`, runs `init --drafted-by agent` |
| `examples/toy-cs/` | the 2026-09-08 exit run: brief, context, agent reports, deliverables |

## Machine install

Run once per workstation, from a checkout of this repository:

    scripts/install.sh

It creates `/usr/local/lib/stringency/versions/<version>/` (a venv with the engine and the toy
plugin), points `/usr/local/lib/stringency/current` at it, links `/usr/local/bin/stringency`
when that directory is writable, and creates `/usr/local/lib/stringency/envs/` for container
images. `/usr/local` is visible inside the Claude Science sandbox, which does not mount home
directories, so this is the location the operator skill looks in. Re-run with a new checkout to
add a version; `current` moves. Add `--plugin <path-or-url>` for further plugins.

Container images referenced by method manifests should live at a path that is the same on every
machine that will run the method, for example `/usr/local/lib/stringency/envs/<name>.sif`.

The machine-wide location matters only when the engine runs inside the sandbox (mode A). A
compute host reached over SSH (mode B) runs the engine as your own user, so a per-user install
needs no sudo:

    scripts/install.sh --prefix ~/.local/lib/stringency

and the brief's `PRE` line then puts `~/.local/lib/stringency/current/bin` on the PATH
(`render_brief.py --engine-bin`, or edit the line). Images can live under
`~/.local/lib/stringency/envs/` as long as the method manifest names that path on every host.

## Where the session runs

Tested on BMESEQ, 2026-09-08: a Claude Science sandbox on the workstation can run the CLI but
cannot start a container (`singularity` fails the user lookup for an Active Directory uid, and
nested namespaces are blocked). So a session drives an `apptainer` project through a registered
SSH compute provider, which runs commands on the workstation as the user, outside any sandbox.
The session itself can be on the workstation or on a laptop; the trace and deliverables are
written on the workstation either way.

## Operator skill

`stringency-operator/SKILL.md` is a Claude Science skill: how to find the engine, the operator's
rules, and the run loop. Publish it once per Claude Science instance. In a session, grant this
repository (or copy the file into a granted directory), then in a `repl` cell:

    content = open("<granted path>/integrations/claude-science/stringency-operator/SKILL.md").read()
    host.skills.edit("stringency-operator", "SKILL.md", content)
    host.skills.publish("stringency-operator")

Or from a compute host, without a grant: `t = c.download("<host path>/SKILL.md")` returns a
transfer dict, and `open(t["local_path"]).read()` is the content. Every unrestricted agent profile
then sees the skill through discovery, and a session that mentions stringency loads it. To
replace a published skill, `host.skills.edit` needs the current body as `old_string` (it creates
a file only when none exists), then `publish(name, overwrite=True)`. The same steps publish
`stringency-declare`. Both were published this way on 2026-09-14. The operator skill was revised
2026-09-15 (Track 1c): the intent table, the hold protocol, `operator_line`, `run --responses`,
`run --deliver`, `plain`, `summary.md`; republish it on each instance.

## Rendering the brief and context

    /usr/local/lib/stringency/current/bin/python integrations/claude-science/render_brief.py <project> --provider <alias> [--context]

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

# Claude Science integration

Two pieces make a new Claude Science project able to use stringency without custom setup.

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

Every unrestricted agent profile then sees it through skill discovery, and a session that
mentions stringency loads it. Re-publish with `overwrite=True` after changing the file.

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

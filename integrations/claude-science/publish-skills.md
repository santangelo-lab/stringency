# Publishing the stringency skills to a Claude Science instance

Skills are per instance, so each person publishes them once in their own instance and republishes
when a skill changes. Three kinds:

| skill | source | who uses it |
|---|---|---|
| `stringency-operator` | `integrations/claude-science/stringency-operator/SKILL.md` (engine repo) | the session, to drive a project |
| `stringency-declare` | `integrations/claude-science/stringency-declare/SKILL.md` (engine repo) | the session, to draft declarations from a brief |
| `stringency-analyze-<name>` | `skills/stringency-analyze-<name>/SKILL.md` in the method repo, rendered by `integrations/claude-science/render_skill.py` from `skills/<pipeline>.analyze.yml` (Track 1d, built 2026-09-23) | a lab member, as the entry point for one analysis |
| `stringency-analyze-toy-compare` | `skills/stringency-analyze-toy-compare/SKILL.md` in `stringency-toy-method` at `v0.1.4` (on PROTSEQ: `~/mytools/stringency/stringency-toy-method`) | the first instance, on the toy `toy-engine` pipeline; the Track 1 acceptance test runs through it |

## The cell

In a session with `protseq` as a compute host, for each skill, in a `repl` cell:

    t = c.download("/data/lab/env/stringency/skills/<skill>/SKILL.md")   # or any host path holding the file
    content = open(t["local_path"]).read()
    host.skills.edit("<skill>", "SKILL.md", content)
    host.skills.publish("<skill>")

Or, when the repository is a granted directory, read the file directly instead of downloading.
`host.skills.edit` creates the file only when none exists; to replace a published skill, pass the
current body as `old_string` and then `host.skills.publish("<skill>", overwrite=True)`. Every
unrestricted agent profile then sees the skill through discovery, and a session that mentions
stringency loads the operator skill.

## Where the current text lives

The canonical text is the engine repository at its installed tag (operator, declare) and the
method repository at its tag (analysis skills). A convenience copy for the download cell can be
kept at `/data/lab/env/stringency/skills/<skill>/SKILL.md`, refreshed by whoever installs a new
engine version; if the copy and the repository disagree, the repository wins.

## When to republish

- The operator skill: on every engine version that changes a verb, a flag or the hold protocol
  (last revision 2026-09-15, Track 1c; the outlier judgment of 2026-09-21 changed the dispatch
  brief so that the operator passes only the request file path).
- The declare skill: when the declaration grammar or the echo-back changes.
- An analysis skill: on every tag of its method repository. The rendered file is committed there;
  render it again with `render_skill.py <method repo> --pipeline <name> --write` before tagging
  when the `.analyze.yml`, the pipeline titles, or the engine template changed.
  `stringency-analyze-toy-compare`: not yet published on any instance (2026-09-23).

A publish is recorded nowhere by the engine; the session's transcript is the only record. Note
the date in this file's table when a republish is done on the lab's instances.

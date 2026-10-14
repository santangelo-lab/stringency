# Install for people, the site-neutral repository, and the first green CI (2026-10-15)

## Goal

After W0 to W6, the owner read `docs/install.md` and found it written for an agent, not a person;
asked for the lab's workstation names to leave the public repository; and pushed everything,
which ran the new CI workflows for the first time.

## Done

- Install for people: the README's "Install" section is a two-line message a person pastes into
  Claude Code, Codex or any AI with access to the machine; `scripts/bootstrap.sh` installs uv and
  Python when missing, reads `compat/known-good.yml`, installs the latest dated engine and plugin
  with the skills beside them, and ends with `probe`; `docs/install.md` has a person's half and an
  AI's half; `new-project.md` and `docs/onboarding.md` open with a person's section (three one-time
  steps in the instance, then describe the experiment); `publish-skills.md` is one message to
  paste; `docs/release.md` holds the recurring jobs with placeholders. Tested into a scratch prefix.
- Site-neutral: the lab's host page, the maintainer's commands with the lab's values, the service
  units as deployed, the archived host notes and the example runs moved to
  `~/mytools/stringency/stringency-lab/` (a plain directory outside the repository, by the owner's
  choice); every guide, both engine skills, the brief renderer, the scripts and the known-good
  table use `<prefix>`, `<projects>`, `<images>`, `<alias>`, `<group>`. `spec/` and `notes/` keep
  the pilot's names as the record. README's Develop split into "Develop the engine" and "The CLI
  in brief".
- Engine v0.2.21: `probe` read the skill's "for engine 0.2.19" line as "0" (a lazy pattern) and
  demanded equality with the engine; now the whole version, and a skill for an engine no newer
  than the installed one passes.
- CI, first runs after the pushes: engine `ci` red on an import order (fixed before the push),
  method `ci` red because the plugins repository was private (the owner made it public), then on
  a missing `pyarrow` (added), then on the skill check running the renderer of engine v0.2.20,
  which predates `decisions:` (the method's `requires` now says `>=0.2.21`); engine `compat` red
  on a colon in an unquoted evidence string (quoted; a test parses the table) and now skips a
  method it cannot read anonymously (the method repository is private). Every workflow green at
  the end of the day on `main`; the tag runs rc14 to rc16 stay red in the history.
- Installed on the workstation: `0.2.20-sc0.5.1`, then `0.2.21-sc0.5.1`; `probe --method
  <xenium method>@v0.6.0-rc16` ready.

## Learned

- A file read by two parsers must satisfy the stricter one: the bootstrap's small reader took
  the unquoted colon, PyYAML did not.
- The method's CI clones the engine at the tag `requires` names for the skill check, so a skill
  that uses a newer renderer feature needs `requires` raised with it.
- Workflow checks that need a private sibling repository fail on "could not read Username";
  either the repository is public or the workflow carries a token.

## Altered

- Nothing at the contract level.

## Open

- The owner: republish the skills (the filled-in message is in the lab directory's README); read
  the four design amendments; run one organ on rc16; pick the acceptance tester; Codex for W7.
- The method's next tag (rc17) carries `requires` engine `>=0.2.21`; rc16 runs on 0.2.20 or later.

## Verify

    stringency probe --method https://github.com/santangelo-lab/stringency-xenium-method@v0.6.0-rc16 --no-hash
    gh run list -R santangelo-lab/stringency --limit 3

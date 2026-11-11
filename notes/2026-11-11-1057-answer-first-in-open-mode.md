# 2026-11-11 10:57: answer first, in every method's open mode

Branch `open-mode-answer-first`, from `main` at 974b022 (`v0.2.42`). Text only.

## Goal

The owner's Lung finding (2026-11-09): asked a specific question of a delivery, the operator
presented the paths and the window questions before answering. The Xenium method's open-mode
intro was reworded for it (its pull request 3). The owner, reading that: "it should apply to
all open modes, not just in this method".

## Done

- The operator skill, 10.1: a paragraph "When the person has already asked". The paths are for
  a person who has not said what they want; a specific question is answered at once (the
  switch paragraph and the yes stay, since they are the open project's confirm), and the paths
  are offered after the answer or on request.
- The operator skill, 10.5: a tool's `asks` say what the call needs settled; what the question
  states is passed as the person's and not asked again; only what it leaves open is asked.
- The analysis-skill template, section 8: the same rule, so every method's rendered skill
  carries it.
- `docs/open-mode.md` (what a person is told) and `spec/method-skills.md` (the `open` key).
- DECISIONS 2026-11-11.

## Not done

- No session has run under the new text. The acceptance is the owner's next open-mode
  session: a specific first question answered without the paths.
- The template changed, so every method's committed skill is behind it: the two Xenium skills
  and the three scRNA-seq skills are to be rendered again at their next tags. The Xenium
  method's CI installs the newest engine that satisfies its `requires`, so it will fail on the
  stale skills as soon as an engine with this template is tagged; the scRNA-seq method's CI
  installs its floor and will not.

## Verify

    uv run pytest -q tests/test_render_skill.py tests/test_operator_skill_line.py

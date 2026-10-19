# Open mode: questions of a delivered dataset

Engine 0.2.22, `spec/plans/open_mode_plan.md`. The pipeline half of an analysis takes raw data to
a delivered dataset through a declared topology, gates and holds. Open mode is the second half:
once a pipeline has delivered, the assistant that operated it answers a person's questions of the
delivered dataset, interactively, with the engine recording and labelling every answer.

## The two words

Every answer carries one of two labels, printed by the engine from what ran, never written by
the assistant:

- **trusted**: the answer rests on tools the method ships (modules that list `open`), run by the
  engine on the delivered data in a verified environment, each with a passing control on record,
  every step completed. The words around the numbers are still the assistant's.
- **untested**: anything else; in particular, code the assistant wrote in the session, which the
  engine ran and recorded but which nothing has checked. A tool's answer can be untested too,
  when the tool missed a condition (its control failed, say); the label sentence then names the
  tool and the reason, never "code".

A deterministic tool's controls run on known data before its first use in the project, so a tool
the method tested is trusted without anyone asking for the check.

Beside the label one fixed line names what the two words would hide: flags a person accepted on
the path, parameters outside their range, parameters the person set, whether the upstream
delivery's environment was verified, whether the tools' controls are current, and which inputs
were untested.

## What you can ask

Anything about the delivered dataset the tools can compute, or that code can compute from it.
The open project also holds the pipeline's own inputs, read-only, so a question about what the
pipeline removed or changed (unfiltered against filtered rows, say) can be answered from the data
before it ran. Not a judgment ("is this good", "should we exclude these"): that is a hold or a
person's call. Not something neither the delivery nor the inputs hold: the assistant says what
would answer it. The
assistant proposes three to five paths before the switch, so the first question can be a pick.

## The three routes

For each question the assistant takes one route: a tool whose use-when fits; code written in the
session (`exec`), only when no tool fits and the delivery or the pipeline's inputs hold the
data, said before it runs;
or cannot. It never combines tools to approximate a question none answers.

## Decisions

A tool's parameters are the person's when the person set them in their own words (recorded as
such, no approval hold) or proposed by the assistant with a reason citing a cell, which opens a
hold the person answers. Every run of the same tool on the same inputs is counted; a delivered
answer says it is one of N.

## Delivering

When the person says they are done, the assistant asks once which answers to keep: all of them,
or some by number. `deliver --answer` (or `--answer all`) writes them into
`deliver/answers-<NN>/` in the open project: one `q<NN>-<words>.md` per answer with its label
sentence, qualifier, text and cited files, the cited tables and figures, `index.json` with a
provenance block per file, and `answers-summary.md`, `answers-coverage.md` and
`answers-methods.md`. The
summary of an open run says what was asked, what ran, what was untested, and what was explored.
Nothing asked changes the delivered files.

## Finding your way around later

The open project sits beside the delivered one as `<project>-open`. Its `README.md`, written by
the engine and kept current, lists every question with how it was answered, its label, the step
directories that hold its work and the file it was delivered as, then says what every path in
the project holds. Pipeline projects carry the same kind of README.

## What is recorded

The questions (the person's words verbatim, and whether the assistant suggested the path), every
tool run and script run as a step of the trace (the script's text under its hash), every answer
with the cells it cited and whether it was admissible or blocked, every label derived from the
lineage, the rerun counts, and the deliver gate's verdicts. The coverage report ends with what
was not checked: whether the answers delivered were chosen because they came out, what the
assistant said that was not filed as an answer, whether a script computed what it claims.

## For operators and authors

The operator's rules are section 10 of `integrations/claude-science/stringency-operator/SKILL.md`;
the verbs are `tools list`, `init --mode open --from-delivery`, `ask`, `call`, `exec`, `answer`,
`deliver --answer`, `present --answer`. A method author's side is `docs/method-author.md`,
"Tools for questions". The test drive on the toy is `docs/open-mode-rehearsal.md`.

## How it is measured

One row per run in `spec/plans/backlog.md`: questions asked (person and suggested), answers by
label, blocks and how each was cleared, unrequested ids shown (target zero), label lines relayed
verbatim (target all), turns and minutes to the first delivered answer.

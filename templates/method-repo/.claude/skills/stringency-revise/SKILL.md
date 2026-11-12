---
name: stringency-revise
description: Read the holds people resolved on one module version of this method (the documents `stringency review --export` writes), group them by theme, and propose changes to the module's prompt, vocabulary, confidence criteria or controls, each citing the hold ids it answers, then wait for the method author. Load when the method author asks what the reviews of a module say, why a judgment module is overridden or rejected, or for a revision of a module from its reviews. Do not load for running an analysis or answering a hold (the operator skill), or for wrapping existing code as a module (the wrap skill).
license: MIT
---

# stringency-revise

You read what people decided at the holds of one module version and propose what the method
should change because of it. You propose; the method author decides and edits. Nothing in this
skill changes a file until they say which proposals to take.

## 1. Gather the cases

Ask which module and version, and which projects ran it. In each project directory run

    stringency review --export --module <module>@<version> --json

It writes one Markdown document per resolved hold into `runs/<run>/reviews/<hold>.md` and
lists the paths. A delivered run carries the same documents in `deliver/<run>/reviews/`, so a
delivery someone sent you is enough when the project itself is not at hand. Each document has
YAML frontmatter (hold, kind, predicate, step, item, module, reviewer, `via`, verdict, reason,
the label it settled on, the bound hashes) and below it the packet the reviewer read. Read
every document whole before you group anything. `stringency status --overrides --module
<module>` gives the rate the cases sit behind; say it once.

`via` tells you whose verdict it is: `tty`, `web` and `relayed` are a person's; `rebind` and
`inherited` carry an earlier verdict forward and are not new evidence; `policy` is a fixed rule's,
not a person's, and is never read as a person's judgment.

## 2. Group by theme

A hold is a request for attention, not a conclusion that the module is wrong. An accept is
evidence the module asked well; an override or reject with a reason is evidence of what it
missed. Group the cases by what the reviewers were responding to (a label the vocabulary lacks,
evidence the prompt does not point at, a confidence band too strict for agreed calls, a
predicate that fires on cases people always accept), not by the words they used. A case may sit
in two themes. A theme with one case is still a theme; say how many cases stand behind each.

## 3. Propose

For each theme, at most one proposal, highest value first: a change to the module's `prompt.md`,
its vocabulary, the policy's confidence criteria, a predicate's disposition in `policy.yml`, or a
control fixture that would catch the case. Each proposal states:

- what changes, as the exact text or value;
- the hold ids it answers, every one;
- its class against what the method already has: **new**, **duplicate** (the method already
  says it; the reviewers did not see it, which is a packet or prompt-placement problem),
  **extension** (widens something already there), or **conflict** (contradicts something
  already there; name the line, and the author resolves it);
- what it would not fix.

Do not propose a change no case supports, and do not drop a case that fits no proposal: list it
at the end as unexplained.

## 4. Wait

Stop after the proposals and ask which to take. When the author chooses, make only those
changes, bump the module's version and its `CHANGELOG.md` line as the method's convention says,
and write the commit message so it cites the hold ids behind each change (design 7.6: a prompt
change cites the reviews that motivated it). A changed module runs its controls again before it
is used; say so, and do not run them unasked.

# Summary of run <ULID>

Project <ULID>; open mode on method v0.1.0; profile standard.

## What was analyzed

Your results are delivered. You can ask questions of them here. Nothing you ask is declared in
advance and nothing here is a pre-registered result. Some questions I answer with tools shipped with
this method, which are tested; some with code written in this session, which is not; the engine
labels each answer trusted or untested from what ran, counts every run of the same tool on the same
data, and nothing you ask changes the delivered files. Shall I open it for questions?

Delivery bound: run <ULID> of <UPSTREAM>: object (frame, step 01_filter, output object).
The upstream project asked process_rows.
Tools shipped with the method: compare-groups (compare_groups), plot-groups (plot_groups).

## What was asked

- Question 1 (the person's own words): "Which group is higher, A or B?"; one admissible answer(s).
- Question 2 (a path the operator proposed): "What is the mean per group?"; two admissible answer(s).

## What ran

- compare-groups (step 01_compare-groups) for the question "Which group is higher, A or B?": at defaults.
- A script written in the session (step 02_exec, blake3 <HASH12>) run in env toy-py for the question "What is the mean per group?": status completed; outputs means (table), untested.

## What was checked and decided

Nineteen checks were evaluated over two steps; no blocks and no flags were raised.

## Judgments

No step asked for a judgment.

## What you received

- `<ULID>.answer.md`: the answer to "Which group is higher, A or B?", labelled trusted; cited files 01_compare-groups.comparison_table.tsv; one of 1 run(s) of compare-groups@0.1.1 on these inputs (1 distinct parameter set(s)); asked after 0 result(s) on the same inputs existed.
- `<ULID>.answer.md`: the answer to "What is the mean per group?", labelled untested; cited files 02_exec.means.tsv; one of 1 run(s) of exec@<HASH12> on these inputs (1 distinct parameter set(s)); asked after 0 result(s) on the same inputs existed.
- `01_compare-groups.comparison_table.tsv`: the comparison_table output of step 01_compare-groups (table).
- `02_exec.means.tsv`: the means output of step 02_exec (table).
- `coverage.md`: the coverage report; `methods.md`: the methods paragraph; `index.json`: each file and answer linked to its run, step, action, hash and provenance.

## What was untested

- Answer `<ULID>.answer.md`: flags accepted on the path: none | parameters outside range: none | person-set parameters: none | upstream: verified | controls: none | untested inputs: 02_exec
- Scripts written in the session: steps 02_exec.

## Explored

- compare-groups@0.1.1 on one set of inputs: one run, one distinct parameter set, one delivered (steps 01_compare-groups).
- exec@<HASH12> on one set of inputs: one run, one distinct parameter set, one delivered (steps 02_exec).
- Questions: one in the person's own words, one a path the operator proposed.

## Not checked

not checked: whether the delivered answers were chosen because they came out (every run of every tool on the same inputs is counted above; the choice was the person's); anything the assistant said that was not filed as an answer; whether an untested script computed what its output claims, or used the seed it was given; what the operator read into the hosted session beyond the cited artifacts; whether the upstream delivery was re-run after a question here was answered; and anything not listed above

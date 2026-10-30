# Questions of proj1's results

What was asked of the results that `<UPSTREAM>` delivered (run <ULID>), under method v0.1.0, from <DATE> to <DATE>: two questions asked, one marked as a finding. The findings lead; everything else asked follows, in short, with its full answer in a file beside this one.

## Findings

### Which group is higher, A or B?

Question 1, asked by the person.

A is higher than B: the difference is 59.22 (adjusted p 1.33e-75).

**comparison_table (cited rows)**

| contrast | diff | mean_a | mean_b | n_a | n_b | p_adj | p_value |
|---|---|---|---|---|---|---|---|
| A_vs_B | 59.22 | 74.99 | 15.77 | 3 | 3 | 1.33e-75 | 4.44e-76 |

Label: trusted. Produced by compare-groups (compare-groups@0.1.1), a tool shipped with the method, run by the engine on the delivered data. Numbers checked against the cited cells: 2 of 2. Everything else in this answer is the assistant's reading.
Marked as a finding by <USER> on <DATE>: "this is the comparison I wanted".
Full record: `q01-which-group-is-higher-a-or-b.md`.

## Other questions

**2. What is the mean per group?** (code written in the session; untested). The means are A 74.82, B 15.86 and C 74.37.
Full answer with its tables: `q02-what-is-the-mean-per-group.md`.

## How to read the labels

Trusted means the engine ran a tool the method ships, in a verified environment, with a passing control on record, on the delivered data; the words around the numbers are still mine.

Trusted data, drawn by session code means the engine ran a tool the method ships for every number on the figure, and the drawing itself is code written in this session: the engine checked that every number the figure draws is a cell of those trusted tables, and nothing has checked the drawing code beyond that.

Untested means the engine ran code I wrote in this session and recorded it, but nothing has checked that the code computes what it claims; or it ran a tool the method ships that missed a condition of trusted, which the label names.

## The record

- Questions: one in the person's own words, one a path the assistant proposed; two answered.
- compare-groups ran one time on one set of inputs with one distinct parameter set; one of them is cited by a finding (steps 01_compare-groups).
- exec ran one time on one set of inputs with one distinct parameter set; none of them is cited by a finding (steps 02_exec).
- Scripts written in the session: 02_exec.
- Tools run without a current control: none.
- not checked: whether the answers marked as findings were chosen because they came out (every run of every tool on the same inputs is counted above; the choice was the person's); anything the assistant said that was not filed as an answer; whether an untested script computed what its output claims, or used the seed it was given; what the operator read into the hosted session beyond the cited artifacts; whether the upstream delivery was re-run after a question here was answered; and anything not listed above
- `coverage.md`, `methods.md` and `index.json` beside this file hold the checks, the methods paragraph, and every file's hash and provenance. Each answer's file carries its label sentence, its qualifier line and the files it cites.

# 2026-11-11 15:00: a rationale may name a punch or a time point; a person's choice in the consensus file

Branch `rationale-names-and-choices`, from `main` at 35e8c84 (#30). Rows L195 and L110, one
pull request for both, as the owner asked.

## Goal

The two engine rows the Xenium method's wave waits on (its X4): the outlier judgment's
rationale blocked for naming punches and time points (L195), and a person's choice at an
item hold not reaching the file the next module reads (L110).

## Done

- **L195.** `judg.numeric_claims_match@3`: a rationale is read by the answer's classifier
  (`judg.rationale_numerals`). Tested on the three Lyons rationales the earlier version
  blocked, read from that project's trace (`tests/test_rationale_numerals.py`).
- **L110.** The consensus item carries `chosen_replicate` and `correction`
  (`consensus.review_choice`); `_validate_correction` validates every field given
  (`tests/test_sign_off.py`).
- Design 6.5's predicate table, 7.3 and 8.4; `DECISIONS.md` (the last entry); both rows moved
  to `archive/backlog-done.md`; `PLAN.md` "Next, in order" and the order note's two tables.
- The bundled toy method's two gates name `@3`.

## Learned

- The Lyons block was mostly quotation: `24-2 and 48-2` and `1/5` were inside the cited
  histology note. The row's classes alone would not have passed `1/5`, so a cited cell that
  holds text now gives its numerals.
- A reviewer is not taught backticks, so the mark rule of L157 cannot apply to a rationale
  without a prompt change. A design level and the item's id pass bare.

## Altered

- The predicate's version moved, so a method that gates `@2` by version fails lint on the next
  engine until it names `@3`: the public toy method, and the Xenium method's
  `annotate-clusters` and `label-domains` (`flag-outlier-punches` gates the bare id).
- `consensus.json` has two more keys per item on every judgment, so its hash differs from one
  written by 0.2.42 for the same judgment.

## Open

- No version bump here: 0.2.43 is cut when wave 2's remainder is in (L94 with L107 next).
- `review --choose` on a label no replicate called still leaves the ontology id null; the
  applying module resolves it (the Xenium method's X4).
- The toy method repository's own gates, at its next tag.

## Verify

    uv run pytest -q tests/test_rationale_numerals.py tests/test_sign_off.py

# Open mode on a real delivery: the engine fixes behind the Xenium open tools (2026-10-20)

## Goal

Build the Xenium method's trusted open tools (the owner's approved plan, seven tools from the
ROSC code) and run them on the Lyons CLP liver delivery. The method work is in
`stringency-xenium-method` branch `open-tools` (its note `notes/2026-10-20-1900-open-tools-m2.md`);
this note records what the engine needed.

## Done (engine 0.2.24)

- `init --mode open --from-delivery` takes each delivered file's producing run from its sidecar
  (`declarations_from_delivery`): a resumed run delivers steps an earlier run completed, and the
  Lyons liver delivery was refused with "sidecar names run X, derived_from says Y". The report
  names the delivery's run (`report._upstream` reads the `deliver/<run>` directory). Test in
  `tests/test_open_init.py`.
- `tables.is_tabular`: a cited cell and an answer view of kind table may come from any csv or
  tsv artifact, not only kind `table`, so a method's own table types (`punch_table`,
  `proportion_table`) are citable and shown as tables (`answers.py`, `present.py`); DECISIONS.
- `exec --help` no longer crashes (backlog L43: rich read `[/<format>]` as markup);
  `tests/test_cli_help.py` renders every verb's help.
- The plugin `stringency-singlecell` 0.6.0 and 0.6.1 (open mode, the tools' operations,
  `shuffle_column`, list parameters as comma-separated strings since `--set k=v` is text) are
  installed with 0.2.23 as the shared current; 0.2.24 replaces it.

## Learned

- `--set k=v` values are coerced to numbers, booleans and null, never to lists; a list parameter
  is a comma-separated string the module splits (backlog candidate: a list form of `--set`).
- An optional input of a common type (`table`) binds the latest artifact of that type by
  accident; a tool's optional input wants its own type (`geneset_table`).
- The six tools on the liver delivery (146,589 cells, 8 punches) run end to end in 5 min 23 s
  with every control passing (`controls/open_tools_check.sh` in the method).

## Open

- The method's `cellchat-signaling` (xenium-r 0.3.0 building), the rc tag, the pilot through
  Claude Science, negative controls.
- A route for a person's own file into an open project (a declared input after init) is not
  built; `custom_genesets` binds only through `--in`.

## Verify

    uv run pytest; uv run ruff check . && uv run ruff format --check . && uv run mypy

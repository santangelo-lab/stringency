# 2026-11-16 13:01: an added input the engine cannot read

Branch `open-mode-added-input-defect`, from `main` at 029bd7a (engine v0.2.44). Docs only: no
engine code changed, no version bump. Written on the MacBook; the shared install on the lab
workstation and the ROSC project were not touched.

## Goal

A defect report, not a fix. On 2026-11-16 the ROSC Xenium open project
(`2026-11_rosc-xenium_jrrose5/qc_all-open`, engine 0.2.44, singlecell 0.10.8) became unusable
for `exec` after six gzipped CSVs were added with `inputs add --type table`, and the only way
out was a second project from the same delivery. The owner's session sent three findings and
four proposed fixes in an order; check them against the code at 0.2.44, file the report where
the repository files defects, and say which reading method the engine wants.

## Done

- Where defects go: the repository uses no issue tracker (no issues on
  `santangelo-lab/stringency`, no templates); a defect is a filed document under `spec/plans/`
  with rows in `PLAN.md` (as `gate-soundness.md`). Filed `spec/plans/added-input-unreadable.md`,
  rows L199 to L204, a waiting row for L202, a line in `spec/README.md`.
- Reproduced at 0.2.44 on the toy method's open project (the `questions` fixture of
  `tests/test_open_exec.py`) from an uncommitted scratch test, since deleted: the gzipped add
  exits 0, then an exec with no `--in` exits 1 with the ROSC line byte for byte. The traceback
  was recovered by patching what `handle_errors` writes through; the document's section 2 has
  the frames.
- The owner's three findings checked. Two are right as stated (no withdrawal; `recorded()` is
  project-wide; a taken name is refused; replacing the copy breaks its hash). Two are corrected:
  the crash does not pass through `is_tabular` (it is `evidence_tables_for`, which decides by
  type alone; `is_tabular` has the same flaw on other paths), and it is not every open-mode
  command that breaks but every `exec`, because `exec` binds every added input though design
  2.3 says by name only (L200, new). Two more found: a failed exec leaves its step `produced`,
  which `abandon --step` refuses (L203); the read happens after the script has run.
- Fix (b) decided: gzip-aware reading with the standard library behind one opener, kind
  `table` checked at the door and before a step runs; not a suffix rule, and not pandas, which
  is not an engine dependency. The reasons are in the document's section 2.

## Learned

- An in-project workaround exists that the ROSC session did not have: add each file again,
  decompressed, under a new name, and on every exec name the old input with the new one
  (`--in <old>=$inputs.<new>`). In the reproduction that exec exits 0.
- A tool `call` that names the gzipped input fails cleanly (exit 13, step `failed`); only
  `exec` reaches the internal error.
- Nothing under `src/stringency/` reads gzip today.

## Altered

Nothing beyond the plan files. `PLAN.md`'s State and "Next, in order" were not rewritten: where
these rows go in the order is the owner's.

## Open

- The owner places L199 to L204 in "Next, in order"; the document's own order follows his
  (a, b, c, d) with L200 beside L199 and L203 last.
- L202 waits on him (waiting table): whether to build a withdrawal at all once L199 is built,
  name reuse, and whose act a withdrawal is.
- PLAN's State still names `0.2.40-sc0.10.3` as the shared install; it is 0.2.44 with
  singlecell 0.10.8.
- The first ROSC project likely holds one `produced` exec step per failed exec; not checked
  from here.

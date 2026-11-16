# An added input the engine cannot read

**Status 2026-11-16.** Filed, nothing built; rows L199 to L204 of `PLAN.md`. Observed on the
ROSC Xenium open project on 2026-11-16 under the shared install on the lab workstation (engine
0.2.44, plugin singlecell 0.10.8). Checked in this session by reading `main` at `029bd7a`
(v0.2.44) and reproduced on the toy method's open project with the test fixtures (section 2).
Line references are to `029bd7a`. No engine code was changed, and the shared install and the
ROSC project were not touched: everything below about ROSC is as reported by the owner's
session, everything else was read or run here.

One unreadable file brought in with `stringency inputs add` made every `exec` in an open project
fail with a one-line internal error, and nothing in the engine let the file be taken back. Four
things compound: the add reads nothing (L199); `exec` binds every added input though the design
says a person's file binds only by name (L200); the table readers are plain-text only and an
unreadable table is found after the script has run (L201); and there is no withdrawal (L202).
Two more made it slow to see and leave debris: the traceback is discarded (L204), and each
failed `exec` leaves its step `produced` (L203).

## What happened

- The project: `/data/lab/projects/2026-11_rosc-xenium_jrrose5/qc_all-open`, project_id
  `01M7JEAV64PTRH2RD05S3XADQC`, open mode.
- Six gzipped CSVs, Proseg's `cell-metadata.csv.gz` and Xenium Ranger's `cell_id_map.csv.gz` for
  three regions, were added with `stringency inputs add <name> <path> --type table --source ...`.
  Each add exited 0.
- Every `stringency exec` after that exited 1 with
  `internal error: UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1`.
  A gzip stream opens with `1f 8b`; `1f` decodes as UTF-8 and `8b` does not.
- Two diagnostic execs both failed: one binding a single `.gz`, and one binding nothing. The
  owner's session read the first as failing before its script ran; in the reproduction the read
  is after the script has run (section 2). Which held on ROSC is in that step's status and
  directory, not checked from here.
- The way out taken: a second open project initialised from the same delivery, which is a full
  re-hash of about 200 GB and the init holds answered again. About forty minutes went to
  bisecting, because the line above was the only signal.

## The order

The owner's order of the fixes, with the two rows this session found placed beside them:

1. L199, the add reads the file as its declared type and refuses what the engine cannot read,
   before anything is copied or recorded. The cheapest fix and the one that stops the class.
   L200 goes with it: it is as small, and it keeps any input a script did not name from
   breaking that script. Either one alone would have left the ROSC project's other execs
   working; neither covers the other's case (a readable file can still break a step whose
   evidence it is, and a file can become unreadable to a later engine).
2. L201, one reader for tables: gzip read as gzip, and a table that cannot be read refused
   when the step is planned, not after it ran. Section 2 says why this and not a suffix rule.
3. L202, a withdrawal for an added input. Design text, so it waits on the owner.
4. L204, the traceback kept.
5. L203, a step left `produced` by an error after its outputs can be closed.

## Contract impact

| row | what it touches | level |
|---|---|---|
| L199 | design 2.3 and the `inputs add` line of 14.1 gain one refusal; exit 15 as now | engine; design text, no contract |
| L200 | none: brings `exec` to design 2.3 as written | engine, below the contract |
| L201 | none; a `DECISIONS.md` line for reading gzip with the standard library | engine, DECISIONS-level |
| L202 | design 2.3 and 14.1; a new run event (`run_events` payload, no new table or column) | *design* |
| L203 | none: `produced -> abandoned` is an edge of 7.1 already (`machine.py:72`) | engine, below the contract |
| L204 | none; exit code 1 (14.2, frozen) unchanged | engine, DECISIONS-level |

## 1. The add reads nothing (L199)

`added_inputs.add()` (`src/stringency/added_inputs.py:78`) checks, in order: an open project
(88), the name's form (93), the person's words (97), the name not already an input (101), a
type some tool takes (103 to 108), the path existing (110), and a directory not holding the
project (113). Then it copies the file (125 to 129), hashes the copy (135) and records
`input_added` (140). Nothing opens the file as the type it is declared to be. Of the input
types a method's tools take, `table` is the one the engine itself reads as delimited text (as
evidence, in citations and in answer views), so a `table` that is not delimited UTF-8 text is
accepted here and fails later inside the engine.

What closes it: before anything is copied, an input declared `table` has its first lines read
through the opener L201 introduces and parsed with the delimiter the engine would use (a
header and at least one row). A file that does not read is refused, exit 15, naming what was
found ("gzip-compressed", "not UTF-8 at byte n", "no delimiter in the header"). If L199 ships
before L201, a gzipped table is refused with the words to decompress it. Tests: a gzipped CSV,
a binary file and a Latin-1 CSV are each refused with nothing copied and no event; a plain CSV
and (after L201) a gzipped one are accepted.

## 2. Where the read is, and why an exec that names nothing reads it (L200, L201)

**The reproduction.** The `questions` fixture of `tests/test_open_exec.py` (the toy method's
open project over a delivered toy run); the toy `groups.csv` gzipped as
`cell-metadata.csv.gz`; `inputs add cellmeta <that file> --type table --source ...` exits 0;
then `exec summary.py --out summary=table --allow-local` with no `--in` exits 1 with the ROSC
line, byte for byte. The test lived in an uncommitted scratch file and was deleted. The
traceback was recovered by patching the `sys` that `handle_errors` writes through (section 5):

`cli/verb_exec.py:113` `exec_` → `steps.py:1380` `execute_engine` → `steps.py:1554` `finish`
→ `steps.py:1444` `evidence_tables_for` → `tables.py:112` `load_table` (the file opened as
text at 110) → the UTF-8 decoder.

**Why binding nothing binds it (L200).** An exec's bindings start from every project input
whose `upstream_input` is unset, and `--in` is laid over them (`steps.py:608` to `614`). By
then `added_inputs.include()` has run (`runs.py:384` and `561`, for every run context) and
folded every recorded added input into `project.inputs`. So an exec binds every person's file
in the project, whatever it names. Design 2.3 says the opposite: `$inputs.<name>` binds a
person's file "in `call --in` and `exec --in`, and only by name: a person's file never binds
by type alone." `call` keeps that rule (`steps.py:344` to `351` leaves out every name in
`project.added_inputs`), and `exec` does not. The finding as reported, that `include()` breaks
every open-mode command, is narrower in fact: in the reproduction `call compare-groups` (no
`--in`), `ask`, `status` and `tools list` all exit 0 after the bad add. What breaks is every
`exec`, and any `call` that names the file.

What closes L200: `exec` binds a person's added input only when `--in` names it, as `call`
does (the comprehension at `steps.py:612` leaves out names in `rc.project.added_inputs`).
Tests: after an unreadable add, an exec naming nothing runs and its Action does not bind the
file; an exec naming it binds it.

**Where the text read is (L201).** The exec's synthetic module types each binding by the
input's kind, so each gzipped copy is an input of type `table`, and `evidence_tables_for`
(`steps.py:1433`) loads every bound input of type `table` that is not `many` with `load_table`
(`steps.py:1436` to `1445`). It decides by `type` alone; it does not call `is_tabular`.

`is_tabular` (`tables.py:43`) has the flaw the owner's session found: `kind == "table"` makes
any path tabular and the suffix test is never reached. Its callers would make the same text
read of a gzipped artifact of kind `table`, each with a different outcome: `answers.py:176` to
`182` calls `load_table` and does not catch the decode error; `present.py:1833` and `2020` and
`citations.py:64` to `69` call `present._rows_from_table` and catch `ValueError`, of which
`UnicodeDecodeError` is one, and show the table as unreadable; `present.py:1541` and `1613`
read only its header, through `_header` (`present.py:1789`), which returns nothing on any
error, so the key column silently becomes `row`; `provenance.py:507` to `517` catches the
error and skips the table, so a figure drawn from a gzipped table reads as matching none of
its inputs. But the crash on ROSC does not pass through `is_tabular`.

A tool call that names the file fails cleanly: `call plot-groups --in
comparison=$inputs.cellmeta` exits 13 and the step is `failed`, because the tool's own read
fails and is recorded as a failure. That is the outcome L201 should give `exec`, earlier.

**Which fix the engine wants.** Read gzip as gzip, and keep `kind: table` meaning "the engine
can read this as a table", checked at the door (L199) and before a step runs. Do not make an
explicit kind defer to the suffix. The reasons:

- A suffix rule in `is_tabular` alone fixes nothing here, since the crash site does not call
  it. Copied into `evidence_tables_for`, it would drop a gzipped table from the step's
  evidence without a word: a judgment whose declared evidence is that table would go to its
  judges without it, and a number cited from it could not be checked. For a trace, a silent
  gap is worse than the crash.
- The tables a spatial method's tools take are delivered gzipped by the vendors (Xenium's
  `cells.csv.gz`, Proseg's `cell-metadata.csv.gz`, Xenium Ranger's `cell_id_map.csv.gz`), and
  the tools read them. The engine's evidence and citation layer should read the bytes the tool
  read, or an answer from them cannot be checked against them.
- pandas is not an engine dependency (`pyproject.toml`; the list in `CLAUDE.md`), and nothing
  under `src/stringency/` imports it or reads gzip today. The standard library's
  `gzip.open(path, "rt", newline="")` reads the same stream and adds no dependency.

What closes L201: one opener in `tables.py`, gzip when the first two bytes are `1f 8b`
whatever the suffix, plain text otherwise, UTF-8 with the failing byte named. The delimiter is
taken from the suffix inside a trailing `.gz` (today `x.tsv.gz` would be read as
comma-separated). `load_table` (`tables.py:97`), `numeric_texts` (`tables.py:153`),
`present._rows_from_table` (`present.py:155`) and `present._header` (`present.py:1789`) read
through it, and with them answers, citations and provenance. `is_tabular` matches `TABULAR_SUFFIXES` through a `.gz`
and keeps `kind == "table"`. A table input that still cannot be read is a `ConfigError`
naming the input and its path, raised when the step is planned (a read of the first lines),
so nothing is executed and no step is left `produced`. Tests: a gzipped CSV and a gzipped TSV
as evidence, cited in an answer and shown by `present`; a binary file of kind `table` refused
before execution with exit 15.

A cost seen while reading, not measured: `evidence_tables_for` parses every bound table in
full, so today every exec loads every table it binds by default, whether its script reads it
or not. For a whole region's cell table that is a real cost on each exec. L200 takes the added
inputs out of it; the delivered inputs exec binds by default stay in it.

## 3. No way to take an added input back (L202)

- `stringency inputs` has one subcommand, `add` (`cli/verb_inputs.py:19`; `inputs --help`
  lists nothing else).
- `added_inputs.recorded()` (`added_inputs.py:31`) selects every `input_added` event of the
  project with no run filter (35 to 38). That is by design: "The added inputs are a
  project's, read from every run's events, so a later open run sees them too" (design 2.3).
  Opening a new run does not drop them.
- `add` refuses a name that is already an input (101), so the files cannot be added again,
  decompressed, under their own names.
- Replacing the bytes at `inputs/added/<name>/` changes the hash that `input_added` recorded:
  `repro.input_digest_mismatch` then blocks every step that binds the file (exit 11, as
  `tests/test_inputs_add.py` shows), which for `exec` today means every exec. It would also
  make a hashed record say something false. It is not a fix.

What does work today, found in the reproduction: add each file again, decompressed, under a new
name, and on every exec name the old input with the new file, for example
`exec ... --in cellmeta=$inputs.cellmeta_csv`. That exits 0, because `--in` is laid over the
default bindings by input name (`steps.py:610` to `614`). It needs one `--in` per bad input on
every exec (six on ROSC), and the trace records the old name bound to the new file. It is a
workaround, not a recovery. It is written here so the next project this happens to has it
before a new project is made; after L200 it is not needed for execs that do not name the files.

What closes L202 (*design*, the owner's): `stringency inputs withdraw <name> --reason "<words>"`
appends an `input_withdrawn` run event (name, reason, operator) to the open run, and
`recorded()` leaves out a name whose latest event is a withdrawal. The copy stays where it is,
since its hash is in the trace and any step that bound it keeps its lineage. The methods
paragraph names the input as withdrawn, with the reason. Two choices for the owner: whether a
withdrawn name may be added again (keeping it taken means a name in the trace always means one
file), and whether a withdrawal is the operator's alone or a person's (a hold). With L199
built, the owner may choose to leave this row open.

## 4. A step left `produced` (L203)

`finish` raises after the step's outputs exist and the step has moved to `produced`, before
the post-gate, and nothing catches it, so the step stays `produced`. In the reproduction both
failed execs were left so (`02_exec`, `04_exec`), while numbering went on. `abandon --step`
refuses them (exit 16): "step 02_exec is produced; only a call that is proposed, held or
accepted and not yet run is closed this way". That is by intent (`runs.py:741` to `750`: a
step that has run has artifacts, and its post-run hold is a person's). Only `abandon --run`
closes such a step. The first ROSC project presumably holds one such step per failed exec; not
checked from here.

What closes it: `abandon --step` accepts an on-demand step that is `produced` with no post-gate
verdict for its Action, with the reason, by the existing edge to `abandoned`. Beside that, an
error raised in `finish` after `produced` is recorded on the step, so the step does not look
like work in progress. After L201 this cause cannot reach `finish`; other causes can. L107's
recovery of a step left `proposed` is the nearest precedent.

## 5. The traceback (L204)

`handle_errors` (`cli/common.py:65`) catches anything that is not a `StringencyError` or a
`typer.Exit`, writes `internal error: <type>: <message>` (78) and exits 1 with `from None`
(79). The traceback is neither printed nor written anywhere. In this session it could be
recovered only by patching the module's `sys` inside a test. Its six engine frames name the
cause (section 2); with them, the ROSC diagnosis is one reading instead of forty minutes of
bisecting execs.

What closes it: the traceback is written to a file every time and its path is printed on the
internal-error line: under the project's `prov/` when there is a project (`prov/jobs/` is the
precedent), else under the user's cache directory. `STRINGENCY_TRACEBACK=1` also prints it to
stderr. A file by default and not only a flag, because getting the traceback by running the
command again costs another run of the script and, here, another stranded step (L203). An
environment variable and not a `--traceback` option, because it reaches every verb, a
`--detach` child and a harness without each verb's signature changing. Exit code 1 as now.
Test: a verb made to raise writes the file, prints its path, and with the variable set prints
the frames.

## Not filed

- An object input added with `inputs add` (an `h5ad` under a type the plugin extracts) is not
  run through the plugin's extractor, as a declared input is at `init` (design 2.7), so a
  wrong object is found by the first tool that reads it. That tool's failure is recorded
  (exit 13), unlike this case.
- The PLAN's State section still names `0.2.40-sc0.10.3` as the shared install; on 2026-11-16
  it is 0.2.44 with singlecell 0.10.8. Left for the session that rewrites State.

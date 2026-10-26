# Module scripts people can find, read, and bring their own code into

**Status (2026-10-26):** the owner's comments and choices of 2026-10-26; row L113. Phase 0 (this
repository) built; phase 1 (the Xenium pilot, `cluster-umap`) next, then the owner's review of
the converted script before phases 2 to 7.

## 1. The owner's points

1. The `pre.*` scripts are what drives each analysis, and nothing in their name or place says
   so. A person opening `modules/cluster-umap/` sees `pre.R` beside `module.yml` and
   `params.schema.json`.
2. They must be legible: familiar, intuitive, readable by a person looking for what the method
   does and which tools it uses.
3. Existing code (a lab member's Seurat or scanpy script) should be easy to bring in.

## 2. What was found (2026-10-26)

Xenium method, 23 scripts (`v0.6.0-rc19`):

- 12 of the 23 headers are a version history that has fallen behind `module.yml`.
  `cluster-umap/pre.R` opens with 44 lines of it.
- The R scripts join statements with semicolons, from 5 to 33 lines per script. Lines run up to
  576 characters. Anonymous functions are defined inline.
- Stringency's bookkeeping (flags, figure manifests, the job) is interleaved with the analysis.
- `_rlib/stringency_upstream.R` mixes figure plumbing with analysis (the elbow table, the batch
  assessment, the resolution tables).
- `_rlib/composition_utils.R` defines a second `wide_counts` with another return type, which
  would silently replace the first in a script that loaded both.

The ROSC code the scripts wrap (`_rlib/Xen_Seurat_functions.R`) and the toy method's scripts read
like ordinary analysis code; that is the target.

The scRNA-seq method's eight scripts have no semicolons. The density there is tuple-packed
parameter reads and lines up to 252 characters. Its `_pylib/common.py` mixes the job with the
analysis, and its compiled `__pycache__` is committed. The Plasmidsaurus method is still the
empty template.

What the engine allows (read from the source):

- `entry:` is an existing manifest field; `pre.*` is only the fallback (`modules.py`
  `Module.entry_script`).
- The interpreter is chosen by suffix.
- The script blob is a hash of the content only. No hold, fork, accept-once or confirm-once rule
  reads the script's name.

So the rename needs no contract change. Two consequences follow:

- A rewritten script needs a version bump, so earlier verdicts stop rebinding and tool controls
  read "none" until they are run again.
- A module whose script hits the egress scan gets a new fingerprint (`path:line`), so the
  project's egress hold is acknowledged again once.

## 3. The convention

The text is in `docs/method-author.md`, "Module scripts" and "Bringing existing code in"; the
decision is in `DECISIONS.md` (2026-10-26). In short:

- **Names.**
  - The script is `<module name with underscores>.<ext>`, set by `entry:`.
  - A judgment module's script is `<name>_evidence.py`, since it builds evidence and the
    reviewers label.
  - Scripts stay in `modules/<name>/`. Elsewhere they would leave the egress scan, and the
    `_rlib`/`_pylib` lookups go through `..` from the script.
- **The header** is at most fifteen plain lines:
  - what the step does;
  - its inputs and outputs;
  - the parameters that are analysis choices;
  - the tools.

  The version history moves to the module's `CHANGELOG.md`.
- **One shape for every script:**
  1. shared code;
  2. the job;
  3. the parameters, with `log_params`;
  4. numbered steps;
  5. recording for stringency (flags live on the object that is written);
  6. writing the outputs.
- **Rules.**
  - One statement per line, and 100 characters at most per line.
  - Recognisable calls stay in the script. Long custom algorithms go to named functions in topic
    files.
- **Plumbing.** `stringency_io.R` and `stringency_io.py` share the same names in both languages.
  Their canonical copies are in `templates/method-repo/modules/`, and each method copies them.
  They load no analysis package.
- **Checked.** `ruff.toml` and `.lintr` in the template, run by pre-commit and CI. Vendored code
  is excluded.
- **Index.** Each method README's step tables link the script and name the tools.
- **Existing code** comes in three shapes:
  - a script with hard-coded paths (the job replaces them);
  - a library (copied unchanged, with a provenance header and `# stringency:` edit marks);
  - a command-line tool or workflow (the script builds the command).

  The wrap skill (phase 7) walks an agent through the first two.

## 4. Phases

| phase | where | what |
|---|---|---|
| 0 | engine | the guide sections; `DECISIONS.md`; the template's `stringency_io`, `ruff.toml`, `.lintr`, hooks and CI; `templates/module/` skeletons in R and Python (both run on a three-row table, the R one in the `xenium-r` image); the toy method's five scripts renamed with `entry:` and a `CHANGELOG.md`, content unchanged, versions unchanged (the toy is the engine's fixture and its tests pin the versions) |
| 1 | Xenium | baseline runs of `controls/synthetic_upstream.sh` and `synthetic_run.sh` at `v0.6.0-rc19` on PROTSEQ; `cluster-umap` converted (0.4.2); `_rlib` split (`stringency_io.R` from the template; `clustering.R`, `pca.R`, `batch.R` from `stringency_upstream.R`; the second `wide_counts` renamed); style checks with the unconverted modules excluded; `tools/check_index.py`; README index rows; the owner reads `cluster_umap.R` cold |
| 2 | Xenium | the rest of `xenium-upstream` converted as is, `assess_batch_evidence.py` and `annotate_clusters_evidence.py` with `_pylib/evidence_tables.py` |
| 3 | Xenium | the QC chain, `flag_outlier_punches_evidence.py`, `resegment_nextflow.sh` (its `params:` lines kept, egress acknowledged again) |
| 4 | Xenium | the open tools with their controls re-run; the text references; the next rc tag on the owner's word |
| 5 | scRNA-seq | eight scripts; `common.py` split into `stringency_io.py` and `scrnaseq.py`; `__pycache__` removed; `v0.1.10` |
| 6 | Plasmidsaurus | the template files only |
| 7 | engine | `integrations/claude-science/stringency-wrap/SKILL.md`, after the pilot's review; the owner publishes it |

The annotation items (Xenium 3.15 to 3.21, rows L110 to L112) stay parked. When they resume they
build on the converted `annotate-clusters`, `find-markers` and `apply-labels` (the owner,
2026-10-26).

## 5. Verification

The bar is identical behaviour for every converted module. `tests/compare_deliveries.py` (in each
method) compares a baseline run with a run after the change:

- delivered CSV, TSV and JSON files must be equal apart from version and run-id fields;
- RDS objects are compared with `all.equal` on `meta.data`, reductions, graphs and
  `misc$stringency`, the version fields removed;
- figures are compared by name and count.

The Xenium runs need PROTSEQ, where the images and `/lab` data are.

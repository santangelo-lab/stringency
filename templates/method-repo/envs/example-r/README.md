# example-r

A lockfile environment for R modules under the local executor (`docs/method-author.md` in the
engine repository, "Environments"). `DESCRIPTION` names the packages the R modules load (here
`jsonlite` and `ggplot2`, what `modules/_rlib/stringency_io.R` needs); `renv.lock` pins them,
their dependencies and renv itself against a dated CRAN snapshot (`renv/settings.json` sets the
explicit snapshot type, so the lock follows `DESCRIPTION`, not a scan of scripts); `.Rprofile`
and `renv/activate.R` are renv's own scaffold, so `Rscript` run with `RENV_PROJECT` naming this
directory (which the local executor sets) loads the project library.

Build it with `Rscript -e 'renv::restore()'` here, once per machine; the library lands under
`renv/library/`, which `renv/.gitignore` keeps out of git. Add a package by naming it in
`DESCRIPTION`, then `renv::install()` and `renv::snapshot()` here, and commit the new lock.
Keep the snapshot date and the renv version `renv/activate.R` names in step: renv bootstraps
itself from the lock's repository. Rename the directory and the manifest entry together.

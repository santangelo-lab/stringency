# stringency_io.R: the plumbing every R module script of a method shares, and nothing else.
#
# The engine runs a module's script with one JSON job on stdin (module contract, "Script
# contract"): inputs, params, outputs, output_dir, seed, design, objective. The script writes
# each declared output at the path the job names and exits 0. The analysis belongs in the module
# script, or in a topic file beside this one (load it with source_lib()); nothing here knows any
# biology. Needs jsonlite; ggplot2 only when a figure is saved.
#
# A module script reaches it relative to its own path (the engine binds the method checkout
# read-only into every step):
#
#   this_file <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
#   source(file.path(dirname(normalizePath(this_file)), "..", "_rlib", "stringency_io.R"))
#
# Copied from the stringency engine's templates/method-repo. The Python twin is
# _pylib/stringency_io.py, with the same function names.

suppressPackageStartupMessages(library(jsonlite))
options(warn = 1)

`%||%` <- function(a, b) if (is.null(a)) b else a

# The method's shared R directory: STRINGENCY_RLIB when set (tests), else modules/_rlib beside
# the directory of the running script.
rlib_dir <- function() {
  d <- Sys.getenv("STRINGENCY_RLIB", "")
  if (nzchar(d)) {
    return(d)
  }
  f <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
  if (length(f)) {
    return(file.path(dirname(normalizePath(f)), "..", "_rlib"))
  }
  "."
}

# Load a topic file of shared analysis code from the method's R directory.
source_lib <- function(name) source(file.path(rlib_dir(), name))

# The job the engine sent on stdin. Sets the random seed when the job carries one.
read_job <- function() {
  job <- fromJSON(file("stdin"), simplifyVector = TRUE)
  if (!is.null(job$seed) && !is.na(job$seed)) set.seed(as.integer(job$seed))
  job
}

# One progress line on stdout; the engine keeps stdout as the step's log.
say <- function(...) cat(paste0(..., collapse = ""), "\n", sep = "")

# The same, starting with the wall-clock time, for steps long enough that someone will ask.
say_time <- function(...) say(format(Sys.time(), "%H:%M:%S"), " ", ...)

# `v` as the engine's log reader reads it back, or NULL when it cannot be (a vector of several
# values, text with whitespace): the reader takes `name=value` up to the next space and compares
# numbers, true/false and none with the admitted value.
checkable_value <- function(v) {
  if (is.null(v) || (length(v) == 1 && is.na(v))) {
    return("none")
  }
  if (length(v) != 1 || is.list(v)) {
    return(NULL)
  }
  if (is.logical(v)) {
    return(tolower(as.character(v)))
  }
  if (is.numeric(v)) {
    return(as.character(v))
  }
  if (is.character(v) && nzchar(v) && !grepl("[[:space:]]", v)) {
    return(v)
  }
  NULL
}

# Print `params: name=value ...`, the line the engine reads back from an operator-run step's log
# and compares with the admitted values. Takes named arguments or one named list. Values it
# cannot compare (several values, text with spaces) go on a separate `other params:` line, which
# the engine does not read.
log_params <- function(...) {
  p <- list(...)
  if (length(p) == 1 && is.null(names(p)) && is.list(p[[1]])) p <- p[[1]]
  checked <- lapply(p, checkable_value)
  ok <- !vapply(checked, is.null, logical(1))
  say("params: ", paste(names(p)[ok], unlist(checked[ok]), sep = "=", collapse = " "))
  if (any(!ok)) say("other params: ", toJSON(p[!ok], auto_unbox = TRUE))
}

# A CSV or TSV (by suffix) as a data frame; lines starting with `#` are skipped.
read_table <- function(path) {
  lines <- readLines(path)
  lines <- lines[!startsWith(lines, "#")]
  sep <- if (endsWith(path, ".tsv")) "\t" else ","
  read.csv(text = lines, sep = sep, stringsAsFactors = FALSE, check.names = FALSE)
}

# Write a data frame as CSV or TSV (by suffix), without row names.
write_table <- function(df, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  if (endsWith(path, ".tsv")) {
    write.table(df, path, sep = "\t", quote = FALSE, row.names = FALSE)
  } else {
    write.csv(df, path, row.names = FALSE)
  }
}

# ---- figures: PNG files plus figures.csv, one row per figure, which the skills and the console
# ---- read to say what each figure shows

.figures <- new.env()

fig_start <- function(dir) {
  dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  .figures$dir <- dir
  .figures$rows <- list()
}

# Save a ggplot as <name>.png; a failed figure is logged, not fatal.
fig_save <- function(name, plot, width = 8, height = 6, what = "", dpi = 120) {
  f <- file.path(.figures$dir, paste0(name, ".png"))
  ok <- tryCatch(
    {
      ggplot2::ggsave(f, plot = plot, width = width, height = height, dpi = dpi, bg = "white")
      TRUE
    },
    error = function(e) {
      say("figure ", name, " failed: ", conditionMessage(e))
      FALSE
    }
  )
  if (ok) .figures$rows <- c(.figures$rows, list(data.frame(file = basename(f), what = what)))
  invisible(ok)
}

fig_finish <- function() {
  rows <- .figures$rows
  empty <- data.frame(file = character(), what = character())
  m <- if (length(rows)) do.call(rbind, rows) else empty
  write.csv(m, file.path(.figures$dir, "figures.csv"), row.names = FALSE)
  invisible(m)
}

# ---- flags: facts a step records on a Seurat object (misc$stringency) for the plugin's
# ---- predicates to read; the Python twin uses an AnnData object's uns["stringency"]

stringency_flags <- function(obj) obj@misc$stringency %||% list()

set_flag <- function(obj, name, value) {
  flags <- stringency_flags(obj)
  flags[[name]] <- value
  obj@misc[["stringency"]] <- flags
  obj
}

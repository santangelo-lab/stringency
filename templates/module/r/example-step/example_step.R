#!/usr/bin/env Rscript
# Keep the rows of a table whose value is at least a threshold, and count what was kept.
#
# In:      table     CSV with a numeric `value` column
# Out:     kept      the rows kept, same columns
#          summary   one row: rows in, rows kept, the threshold
# Choices: min_value (the threshold; a decision point)
# Tools:   base R
#
# The skeleton of a module script (the engine's docs/method-author.md, "Module scripts").
# Replace the numbered sections with your analysis and keep the order.

# Shared code for this method is in modules/_rlib, beside this module's directory.
this_file <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
source(file.path(dirname(normalizePath(this_file)), "..", "_rlib", "stringency_io.R"))

job <- read_job()

# ---- Parameters ----
min_value <- job$params$min_value # rows below this value are dropped
log_params(min_value = min_value)

# ---- 1. Load ----
table <- read_table(job$inputs$table)

# ---- 2. Keep the rows at or above the threshold ----
kept <- table[table$value >= min_value, , drop = FALSE]
say("kept ", nrow(kept), " of ", nrow(table), " rows")

# ---- Write outputs ----
write_table(kept, job$outputs$kept)
summary <- data.frame(rows_in = nrow(table), rows_kept = nrow(kept), min_value = min_value)
write_table(summary, job$outputs$summary)

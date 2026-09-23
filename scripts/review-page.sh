#!/usr/bin/env bash
# Open the stringency project page (board, progress, results, holds with the verdict form) for
# the projects on a workstation, through an SSH tunnel.
#
#   scripts/review-page.sh <ssh-alias> [<projects dir>] [<port>] [extra `review --serve` flags...]
#
# Runs `stringency review --serve --projects <dir>` on the workstation AS YOU (your SSH identity,
# so verdicts are recorded as your account, via: web) and forwards the port to this machine. The
# server prints its URL with a one-time token; paste it into a browser here. Ctrl-C stops both.
# Start this yourself; never let an agent start it, and never start one instance for other
# people: it would record you as the reviewer for verdicts they click (design 7.5). A page for
# other people to read is the read-only standing instance (scripts/stringency-page.service).
# `<projects dir>` is walked two levels deep; add `--project <path>` for a deeper one.
set -euo pipefail
alias_=${1:?usage: review-page.sh <ssh-alias> [<projects dir>] [<port>] [flags...]}
dir=${2:-/data/lab/projects}
port=${3:-8765}
shift $(( $# < 3 ? $# : 3 ))
extra=""
for a in "$@"; do extra="$extra $(printf %q "$a")"; done
exec ssh -t -L "${port}:127.0.0.1:${port}" "$alias_" \
  "bash -lc 'stringency review --serve --projects $(printf %q "$dir") --port $port$extra'"

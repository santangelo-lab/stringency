#!/usr/bin/env bash
# Open the stringency review page for the projects on a workstation, through an SSH tunnel.
#
#   scripts/review-page.sh <ssh-alias> [<projects dir>] [<port>]
#
# Runs `stringency review --serve --projects <dir>` on the workstation AS YOU (your SSH identity,
# so verdicts are recorded as your account, via: web) and forwards the port to this machine. The
# server prints its URL with a one-time token; paste it into a browser here. Ctrl-C stops both.
# Start this yourself; never let an agent start it, and never start one instance for other
# people: it would record you as the reviewer for verdicts they click (design 7.5).
set -euo pipefail
alias_=${1:?usage: review-page.sh <ssh-alias> [<projects dir>] [<port>]}
dir=${2:-/data/lab/projects}
port=${3:-8765}
exec ssh -t -L "${port}:127.0.0.1:${port}" "$alias_" \
  "bash -lc 'stringency review --serve --projects $(printf %q "$dir") --port $port'"

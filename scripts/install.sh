#!/usr/bin/env bash
# Install the stringency engine (and plugins) into a shared, versioned location that sandboxes
# and every user on the machine can see. Idempotent; re-run to add a version and move `current`.
#
#   scripts/install.sh [--prefix DIR] [--source PATH|URL] [--plugin PATH|URL]... [--label NAME]
#                      [--link-bin DIR] [--no-toy]
#
# Defaults: --prefix /usr/local/lib/stringency; --source is this checkout; the toy plugin from
# the same checkout is installed unless --no-toy; --label is the source's version (or the @ref of
# a git URL); --link-bin /usr/local/bin when that directory is writable.
#
# Layout:  <prefix>/versions/<label>/   a venv holding the engine and plugins
#          <prefix>/current             symlink to the version in use
#          <prefix>/envs/               container images referenced by method manifests
#
# Requires `uv` (https://docs.astral.sh/uv/) and a system python3 >= 3.12. No sudo is needed when
# <prefix> is writable; otherwise run under sudo with uv on root's PATH, or pre-create <prefix>
# owned by the lab group.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
prefix=/usr/local/lib/stringency
source=$here
plugins=()
label=""
link_bin=""
toy=1

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) prefix=$2; shift 2 ;;
    --source) source=$2; shift 2 ;;
    --plugin) plugins+=("$2"); shift 2 ;;
    --label) label=$2; shift 2 ;;
    --link-bin) link_bin=$2; shift 2 ;;
    --no-toy) toy=0; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v uv >/dev/null || { echo "uv not found; install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2; exit 1; }
# Prefer the system interpreter: a conda or pyenv python under a home directory is invisible
# to sandboxes that do not mount home.
python=${STRINGENCY_PYTHON:-}
for cand in /usr/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
  [ -n "$python" ] && break
  [ -x "$cand" ] && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' && python=$cand
done
[ -n "$python" ] || { echo "no python3 >= 3.12 found (set STRINGENCY_PYTHON)" >&2; exit 1; }

if [ -z "$label" ]; then
  if [ -d "$source" ]; then
    label=$(sed -n 's/^version = "\(.*\)"/\1/p' "$source/pyproject.toml" | head -1)
  else
    label=${source##*@}
  fi
  [ -n "$label" ] || { echo "cannot infer --label from $source" >&2; exit 1; }
fi
if [ $toy -eq 1 ]; then
  if [ -d "$source" ]; then plugins+=("$source/plugins/stringency-toy")
  else plugins+=("${source%%@*}@${source##*@}#subdirectory=plugins/stringency-toy") ; fi
fi

venv=$prefix/versions/$label
mkdir -p "$prefix/versions" "$prefix/envs"
uv venv --quiet --python "$python" "$venv"
uv pip install --quiet --python "$venv/bin/python" "$source" "${plugins[@]}"
ln -sfn "versions/$label" "$prefix/current"

if [ -z "$link_bin" ] && [ -w /usr/local/bin ]; then link_bin=/usr/local/bin; fi
if [ -n "$link_bin" ]; then
  mkdir -p "$link_bin"
  ln -sfn "$prefix/current/bin/stringency" "$link_bin/stringency" && echo "linked $link_bin/stringency"
fi

echo "installed stringency $label at $venv (python: $python)"
echo "current -> $(readlink "$prefix/current")"
"$venv/bin/stringency" plugins list | sed 's/^/  /'
echo "images directory: $prefix/envs"
if ! command -v stringency >/dev/null 2>&1; then
  echo "not on PATH; agents find it at $prefix/current/bin/stringency, or add: export PATH=$prefix/current/bin:\$PATH"
fi

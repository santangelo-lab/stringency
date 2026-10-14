#!/usr/bin/env bash
# One command installs a known-good stringency (engine and plugin at the tags compat/known-good.yml
# names, the skills beside them) and ends with `stringency probe`. For the AI or person setting up
# a machine; docs/install.md explains what it did and what comes next (images, PATH, the console).
#
#   curl -LsSf https://raw.githubusercontent.com/santangelo-lab/stringency/main/scripts/bootstrap.sh | bash -s -- [--prefix DIR] [--engine TAG] [--plugin NAME@TAG]
#   scripts/bootstrap.sh [--prefix DIR] [--engine TAG] [--plugin NAME@TAG]     # from a checkout
#
# Defaults: --prefix ~/.local/lib/stringency (no sudo; a shared machine uses a group-writable
# directory such as /data/lab/env/stringency with `umask 002`); the engine and plugin tags of the
# latest dated row of compat/known-good.yml on main. Needs curl and git; installs uv when missing.
set -euo pipefail
prefix=$HOME/.local/lib/stringency
engine=""
plugin=""
repo=https://github.com/santangelo-lab/stringency
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) prefix=$2; shift 2 ;;
    --engine) engine=$2; shift 2 ;;
    --plugin) plugin=$2; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
command -v git >/dev/null || { echo "git is needed" >&2; exit 1; }
if ! command -v uv >/dev/null; then
  echo "installing uv (https://docs.astral.sh/uv/)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null || { echo "uv is not on PATH after installing; open a new shell and run this again" >&2; exit 1; }
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "installing Python 3.12 with uv"; uv python install 3.12
  export STRINGENCY_PYTHON=$(uv python find 3.12)
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
echo "fetching the known-good combinations"
git clone --quiet --depth 1 "$repo" "$work/engine-main"
if [ -z "$engine" ] || [ -z "$plugin" ]; then
  read -r kg_engine kg_plugin < <(python3 - "$work/engine-main/compat/known-good.yml" <<'PY'
import re, sys
rows, cur = [], None
for line in open(sys.argv[1]):
    if line.startswith("  - engine:"):
        cur = {"engine": line.split(":", 1)[1].strip(), "plugins": {}, "date": ""}; rows.append(cur); section = None
    elif cur is not None:
        s = line.strip()
        if s.startswith("plugins:"): section = "plugins"
        elif s.startswith("methods:"): section = "methods"
        elif s.startswith("date:"): cur["date"] = s.split(":", 1)[1].strip()
        elif section == "plugins" and ":" in s and line.startswith("      "):
            k, v = s.split(":", 1); cur["plugins"][k.strip()] = v.strip()
dated = [r for r in rows if r["date"] and r["date"] != "pending"]
r = dated[-1]
name, tag = next(iter(r["plugins"].items()))
print(r["engine"], f"{name}@{tag}")
PY
)
  engine=${engine:-$kg_engine}
  plugin=${plugin:-$kg_plugin}
fi
echo "engine $engine, plugin $plugin"
git clone --quiet --branch "$engine" --depth 1 "$repo" "$work/engine"
pname=${plugin%%@*}; ptag=${plugin##*@}
"$work/engine/scripts/install.sh" --prefix "$prefix" --source "$work/engine" \
  --plugin "git+https://github.com/santangelo-lab/stringency-plugins@${ptag}#subdirectory=plugins/${pname}" --no-toy
cat <<MSG

installed. Next:
  1. put the engine on your PATH, in ~/.profile:   export PATH=$prefix/current/bin:\$PATH
  2. a container runtime (apptainer) for production runs; `stringency probe` says whether one is found
  3. the method's images where the site keeps them, named in ~/.config/stringency/config.yml as images_root
  4. `stringency probe --method <method url>@<tag>` ends with "ready" when a project on that method can run here
docs/install.md in the engine repository explains each.
MSG

#!/usr/bin/env bash
# The engine imports no biology. Fails if any forbidden import appears under src/stringency/.
set -euo pipefail
cd "$(dirname "$0")/.."
pattern='^\s*(import|from)\s+(scanpy|anndata|squidpy|mudata|scvi|celltypist|decoupler|pertpy|spatialdata|owlready2|pronto|obonet)\b'
if grep -rEn "$pattern" src/stringency/ ; then
  echo "forbidden biology import under src/stringency/" >&2
  exit 1
fi
echo "no biology imports in the engine"

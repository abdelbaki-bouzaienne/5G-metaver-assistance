#!/usr/bin/env bash
# Construit les packages VNF/NS (.tar.gz) au format attendu par OSM.
# Usage : ./build_packages.sh   (sortie dans infra/osm/_build/)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/_build"
mkdir -p "$OUT"

pack() { # pack <dir-du-package>
  local dir="$1" name
  name="$(basename "$dir")"
  tar -czf "$OUT/${name}.tar.gz" -C "$(dirname "$dir")" "$name"
  echo "OK  $OUT/${name}.tar.gz"
}

# osm1 - RAN
pack "$ROOT/osm1-ran/ueransim_gnb_vnf"
pack "$ROOT/osm1-ran/ran_xr_edge_ns"
# osm2 - edge/MEC
pack "$ROOT/osm2-edge/open5gs_upf_vnf"
pack "$ROOT/osm2-edge/edge_platform_vnf"
pack "$ROOT/osm2-edge/edge_mec_ns"
# osm3 - coeur
pack "$ROOT/osm3-core/open5gs_core_vnf"
pack "$ROOT/osm3-core/core_5g_ns"
pack "$ROOT/osm3-core/open5gs_core_knf"
pack "$ROOT/osm3-core/core_5g_knf_ns"

echo "Packages construits dans $OUT"

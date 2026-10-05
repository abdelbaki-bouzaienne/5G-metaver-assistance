#!/usr/bin/env bash
# Instanciation complete du PoC - ordre : coeur (osm3) -> MEC (osm2) -> RAN (osm1).
# En production OpenSlice/OSOM pilote ces creations via les RFS ; ce script sert aux
# tests manuels et au premier amorcage du banc.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"

osmc() { local host="$1"; shift; osm --hostname "$host" --user "$OSM_USER" --password "$OSM_PASSWORD" --project "$OSM_PROJECT" "$@"; }

wait_ns() { # wait_ns <host> <ns_name>
  local host="$1" name="$2" status
  for _ in $(seq 1 60); do
    status=$(osmc "$host" ns-list --filter "name=$name" 2>/dev/null | grep -oE 'READY|BROKEN' | head -1 || true)
    [ "$status" = "READY" ] && { echo "$name READY"; return 0; }
    [ "$status" = "BROKEN" ] && { echo "$name BROKEN"; osmc "$host" ns-show "$name"; return 1; }
    sleep 20
  done
  echo "Timeout sur $name"; return 1
}

echo "=== 1/3 coeur 5G (osm3) ==="
osmc "$OSM3" ns-create --ns_name core5g --nsd_name core_5g_ns --vim_account "$VIM3" \
     --config_file "$ROOT/osm3-core/params/core_params.yaml"
wait_ns "$OSM3" core5g

echo "=== 2/3 MEC (osm2) : UPF EDGE + UPF actuation + plateforme edge ==="
osmc "$OSM2" ns-create --ns_name edgemec --nsd_name edge_mec_ns --vim_account "$VIM2" \
     --config_file "$ROOT/osm2-edge/params/edge_params.yaml"
wait_ns "$OSM2" edgemec

echo "=== 3/3 RAN (osm1) : gNB + UE ==="
osmc "$OSM1" ns-create --ns_name ranxr --nsd_name ran_xr_edge_ns --vim_account "$VIM1" \
     --config_file "$ROOT/osm1-ran/params/ran_params.yaml"
wait_ns "$OSM1" ranxr

echo "Instanciation terminee. Lancer ensuite infra/tests/run_all.sh"

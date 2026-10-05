#!/usr/bin/env bash
# Onboarde les packages VNF/NS (et NST) sur les trois OSM.
# Pre-requis : ./build_packages.sh execute, env.sh renseigne, osmclient installe
#   (pip install osmclient  ou  snap install osmclient).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"
BUILD="$ROOT/_build"

osmc() { # osmc <hostname> <args...>
  local host="$1"; shift
  osm --hostname "$host" --user "$OSM_USER" --password "$OSM_PASSWORD" --project "$OSM_PROJECT" "$@"
}

echo "=== osm1 ($OSM1) : domaine RAN ==="
osmc "$OSM1" vnfd-create "$BUILD/ueransim_gnb_vnf.tar.gz"      || echo "ueransim_gnb_vnf deja present"
osmc "$OSM1" nsd-create  "$BUILD/ran_xr_edge_ns.tar.gz"        || echo "ran_xr_edge_ns deja present"

echo "=== osm2 ($OSM2) : domaine edge/MEC ==="
osmc "$OSM2" vnfd-create "$BUILD/open5gs_upf_vnf.tar.gz"       || echo "open5gs_upf_vnf deja present"
osmc "$OSM2" vnfd-create "$BUILD/edge_platform_vnf.tar.gz"     || echo "edge_platform_vnf deja present"
osmc "$OSM2" nsd-create  "$BUILD/edge_mec_ns.tar.gz"           || echo "edge_mec_ns deja present"

echo "=== osm3 ($OSM3) : domaine coeur ==="
osmc "$OSM3" vnfd-create "$BUILD/open5gs_core_vnf.tar.gz"      || echo "open5gs_core_vnf deja present"
osmc "$OSM3" nsd-create  "$BUILD/core_5g_ns.tar.gz"            || echo "core_5g_ns deja present"
# Option KNF (cluster Sylva enregistre au prealable : osm k8scluster-add)
osmc "$OSM3" vnfd-create "$BUILD/open5gs_core_knf.tar.gz"      || echo "open5gs_core_knf deja present"
osmc "$OSM3" nsd-create  "$BUILD/core_5g_knf_ns.tar.gz"        || echo "core_5g_knf_ns deja present"

echo "=== NST (optionnels, pour tests intra-domaine) ==="
for host in "$OSM1" "$OSM2" "$OSM3"; do
  osmc "$host" nst-create "$ROOT/nst/embb_xr_edge_nst.yaml"     || true
  osmc "$host" nst-create "$ROOT/nst/urllc_actuation_nst.yaml"  || true
done

echo "Onboarding termine. Verification :"
for host in "$OSM1" "$OSM2" "$OSM3"; do
  echo "--- $host ---"
  osmc "$host" vnfd-list
  osmc "$host" nsd-list
done

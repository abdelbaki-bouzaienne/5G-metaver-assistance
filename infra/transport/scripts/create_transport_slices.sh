#!/usr/bin/env bash
# Cree les 3 slices de transport via le controleur NSC (POST /network-slices) :
#   N3  [d1,d2]  PE-RAN  <-> PE-EDGE   (existant sur le banc : urllc2-like, re-cree ici)
#   N2  [d1,d3]  PE-RAN  <-> PE-CORE   (existant sur le banc : embb2-like, re-cree ici)
#   N6/N4 [d2,d3] PE-EDGE <-> PE-CORE  (TROISIEME SLICE, jamais instancie : cree ici)
# En nominal, c'est OpenSlice (RFS_Transport_InterSite) qui emet ces appels via le
# controleur de ressource generique ; ce script sert a l'amorcage et aux tests directs.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"
SLICES_DIR="$HERE/../slices"

AUTH=()
[ -n "${NSC_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $NSC_TOKEN")

create() { # create <fichier.json>
  local f="$1" id
  id=$(python3 -c "import json;print(json.load(open('$f'))['network_slice_id'])")
  echo "--- POST /network-slices : $id"
  curl -sS -X POST "$NSC_URL/network-slices" \
       -H "Content-Type: application/json" "${AUTH[@]}" \
       --data @"$f" | python3 -m json.tool || { echo "ECHEC pour $id"; exit 1; }
}

create "$SLICES_DIR/n3_ran_edge.json"
create "$SLICES_DIR/n2_ran_core.json"
create "$SLICES_DIR/n6n4_edge_core.json"

echo
echo "Slices demandes. Etat courant :"
curl -sS "${AUTH[@]}" "$NSC_URL/network-slices" | python3 -m json.tool

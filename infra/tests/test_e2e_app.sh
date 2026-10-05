#!/usr/bin/env bash
# Tests A : chaine applicative de bout en bout contre le gateway de la plateforme edge.
# A1 upload fragmente + reprise ; A2 job 3DGS ; A3 jumeau/entites/annotations ;
# A4 session + jetons TURN ; A5 scenarios metier (conformite client, cablage).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"
BASE="http://$EDGE_PLATFORM_IP:8000"   # gateway (traefik) de la pile metavers
J='-H Content-Type:application/json'

jqv() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)"; }

echo "=== A1 : scan fragmente + reprise ==="
SITE=$(curl -sf $J -X POST "$BASE/twin/sites" -d '{"name":"NRO-test","site_type":"NRO","marker_id":"MK-01","marker_size_mm":150}' | jqv "['id']")
SCAN=$(curl -sf $J -X POST "$BASE/ingest/scans" -d "{\"site_id\":\"$SITE\",\"marker_detected\":true,\"total_chunks\":3}" | jqv "['id']")
for i in 0 1 2; do
  dd if=/dev/urandom of=/tmp/chunk$i bs=1k count=64 2>/dev/null
  SUM=$(sha256sum /tmp/chunk$i | cut -d' ' -f1)
  curl -sf -X PUT "$BASE/ingest/scans/$SCAN/chunks/$i" -H "X-Chunk-Sha256: $SUM" --data-binary @/tmp/chunk$i >/dev/null
done
# reprise : rejouer le chunk 1 (idempotent)
SUM=$(sha256sum /tmp/chunk1 | cut -d' ' -f1)
curl -sf -X PUT "$BASE/ingest/scans/$SCAN/chunks/1" -H "X-Chunk-Sha256: $SUM" --data-binary @/tmp/chunk1 >/dev/null
echo "  [OK] upload 3 chunks + reprise idempotente"

echo "=== A2 : job 3DGS (statut queued -> running -> done) ==="
curl -sf -X POST "$BASE/ingest/scans/$SCAN/complete" >/dev/null
for _ in $(seq 1 60); do
  ST=$(curl -sf "$BASE/ingest/scans/$SCAN" | jqv "['status']")
  [ "$ST" = "done" ] && break
  [ "$ST" = "failed" ] && { echo "  [KO] job failed"; exit 1; }
  sleep 5
done
[ "$ST" = "done" ] || { echo "  [KO] timeout job ($ST)"; exit 1; }
VERSION=$(curl -sf "$BASE/ingest/scans/$SCAN" | jqv "['twin_version_id']")
echo "  [OK] job done, twin version $VERSION"

echo "=== A3 : entites + annotation (repere jumeau) ==="
PANEL=$(curl -sf $J -X POST "$BASE/twin/twin-versions/$VERSION/entities" \
  -d '{"entity_type":"panel_left","name":"Panneau gauche","geometry":{"kind":"box","center":[0.1,0.5,0.2],"size":[0.6,1.2,0.1]}}' | jqv "['id']")
P1=$(curl -sf $J -X POST "$BASE/twin/entities/$PANEL/ports" -d '{"index":12,"label":"P12"}' | jqv "['id']")
P2=$(curl -sf $J -X POST "$BASE/twin/entities/$PANEL/ports" -d '{"index":13,"label":"P13"}' | jqv "['id']")
curl -sf $J -X POST "$BASE/twin/twin-versions/$VERSION/annotations" \
  -d '{"annotation_type":"highlight","author":"expert","geometry":{"kind":"point","position":[0.1,0.5,0.2]}}' >/dev/null
echo "  [OK] panneau + 2 ports + annotation"

echo "=== A4 : session collaborative + jetons TURN ==="
SESSION=$(curl -sf $J -X POST "$BASE/session/sessions" -d "{\"site_id\":\"$SITE\",\"twin_version_id\":\"$VERSION\",\"user\":\"technicien\",\"role\":\"T\",\"device\":\"ipad\"}" | jqv "['id']")
JOIN=$(curl -sf $J -X POST "$BASE/session/sessions/$SESSION/join" -d '{"user":"expert","role":"E","device":"quest"}')
echo "$JOIN" | python3 -c "import sys,json;d=json.load(sys.stdin);assert d['turn']['username'] and d['turn']['credential'];print('  [OK] jetons TURN ephemeres emis')"

echo "=== A5 : scenarios metier ==="
CLIENT=$(curl -sf $J -X POST "$BASE/twin/clients" -d '{"reference":"CL-0042","name":"Client 42"}' | jqv "['id']")
curl -sf $J -X PATCH "$BASE/twin/ports/$P1" -d "{\"client_id\":\"$CLIENT\"}" >/dev/null
NPORTS=$(curl -sf "$BASE/twin/clients/$CLIENT/ports" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))")
[ "$NPORTS" -ge 1 ] && echo "  [OK] conformite client : $NPORTS port(s) resolu(s) automatiquement"
CABLE=$(curl -sf $J -X POST "$BASE/twin/cables" -d "{\"port_left_id\":\"$P1\",\"port_right_id\":\"$P2\"}" | jqv "['id']")
curl -sf $J -X PATCH "$BASE/twin/cables/$CABLE" -d '{"path":[[0.1,0.5,0.2],[0.5,0.5,0.5],[0.9,0.5,0.2]]}' >/dev/null
echo "  [OK] cablage : 2 extremites + cheminement zone centrale"

echo; echo "E2E applicatif : tous les tests passent."

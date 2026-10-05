#!/usr/bin/env bash
# Tests E : plateforme edge/cloud et trajet UE -> MEC via le slice eMBB.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

PASS=0; FAIL=0
ok()  { echo "  [OK]   $1"; PASS=$((PASS+1)); }
ko()  { echo "  [KO]   $1"; FAIL=$((FAIL+1)); }
sshq(){ ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$SSH_USER@$1" "$2"; }

echo "=== E1 : UE -> plateforme edge via le slice (gNB -> N3 -> UPF -> N6) ==="
sshq "$GNB_VM" "ping -I uesimtun0 -c 5 $EDGE_PLATFORM_IP >/dev/null 2>&1" \
  && ok "ping UE->edge via uesimtun0" || ko "pas de connectivite UE->edge"
sshq "$GNB_VM" "curl -s --interface uesimtun0 -o /dev/null -w '%{http_code}' http://$EDGE_PLATFORM_IP:8081/ | grep -q 200" \
  && ok "edge-video repond (HTTP 200)" || ko "edge-video injoignable"

echo "=== E2 : sante de la pile metavers ==="
for svc in "twin-service:8001" "scan-ingest:8002" "gs-pipeline:8003" "session-service:8004" "signaling:8005"; do
  name="${svc%%:*}"; port="${svc##*:}"
  code=$(sshq "$EDGE_VM" "curl -s -o /dev/null -w '%{http_code}' http://localhost:$port/healthz" || echo 000)
  [ "$code" = "200" ] && ok "$name healthz 200" || ko "$name healthz $code"
done
sshq "$EDGE_VM" "curl -s -o /dev/null -w '%{http_code}' http://localhost:9000/minio/health/live | grep -q 200" \
  && ok "MinIO live" || ko "MinIO KO"
sshq "$EDGE_VM" "docker ps --format '{{.Names}}' | grep -q coturn" && ok "coturn up" || ko "coturn absent"

echo "=== E3 : debit UE -> edge (profil F1, cible ~100 Mbit/s montant) ==="
sshq "$EDGE_VM" "pkill -f 'iperf3 -s' 2>/dev/null; nohup iperf3 -s -D >/dev/null 2>&1" || true
sleep 1
sshq "$GNB_VM" "iperf3 -c $EDGE_PLATFORM_IP -B \$(ip -4 addr show uesimtun0 | grep -oP '(?<=inet )[0-9.]+') -t 10" | tail -3

echo; echo "Edge : $PASS OK, $FAIL KO"; exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)

#!/usr/bin/env bash
# Verifie l'etat des slices de transport et mesure les segments (iperf3 + RTT CE<->CE).
# Reprend la methode du banc (doc 2, section 7.6), y compris le test propose pour le
# segment N6/N4 : iperf3 et RTT entre nf-edge et nf-core.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

AUTH=()
[ -n "${NSC_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $NSC_TOKEN")

echo "=== Etat des slices (controleur) ==="
curl -sS "${AUTH[@]}" "$NSC_URL/network-slices" | python3 -m json.tool

measure() { # measure <nom> <src_ip> <dst_ip>
  local name="$1" src="$2" dst="$3"
  echo
  echo "=== Segment $name : $src -> $dst ==="
  echo "--- RTT (20 pings) — rappel : mesure aller-retour CE<->CE, pas un delai aller simple SDP-a-SDP"
  ssh -o StrictHostKeyChecking=accept-new "$SSH_USER@$src" "ping -c 20 -i 0.2 $dst | tail -2"
  echo "--- iperf3 (10 s, TCP) — a comparer au plafond du tier (gold 100 / premium 50 sur le banc)"
  ssh "$SSH_USER@$dst" "pkill -f 'iperf3 -s' 2>/dev/null; nohup iperf3 -s -D >/dev/null 2>&1" || true
  sleep 1
  ssh "$SSH_USER@$src" "iperf3 -c $dst -t 10" | tail -4
}

measure "N3 (PE-RAN<->PE-EDGE)"   "$CE_RAN"  "$CE_EDGE"
measure "N2 (PE-RAN<->PE-CORE)"   "$CE_RAN"  "$CE_CORE"
measure "N6/N4 (PE-EDGE<->PE-CORE) — 3e slice, premiere mesure" "$CE_EDGE" "$CE_CORE"

echo
echo "=== Isolation (non-fuite) : trafic du slice N3 ne doit pas apparaitre sur N2, et reciproquement ==="
echo "Lancer en parallele : iperf3 N3 a saturation puis verifier que le debit N2 reste au plafond de son tier."
ssh "$SSH_USER@$CE_EDGE" "pkill -f 'iperf3 -s' 2>/dev/null; nohup iperf3 -s -D >/dev/null 2>&1" || true
ssh "$SSH_USER@$CE_CORE" "pkill -f 'iperf3 -s' 2>/dev/null; nohup iperf3 -s -D -p 5202 >/dev/null 2>&1" || true
sleep 1
ssh "$SSH_USER@$CE_RAN" "iperf3 -c $CE_EDGE -t 15 > /tmp/n3.log 2>&1 & iperf3 -c $CE_CORE -p 5202 -t 15 > /tmp/n2.log 2>&1 & wait; echo '--- N3 sous charge:'; tail -3 /tmp/n3.log; echo '--- N2 simultane:'; tail -3 /tmp/n2.log"

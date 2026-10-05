#!/usr/bin/env bash
# Tests C (coeur 5G) et R (RAN / sessions PDU). SSH vers les VM instanciees par OSM.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

PASS=0; FAIL=0
ok()  { echo "  [OK]   $1"; PASS=$((PASS+1)); }
ko()  { echo "  [KO]   $1"; FAIL=$((FAIL+1)); }
sshq(){ ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$SSH_USER@$1" "$2"; }

echo "=== C1 : fonctions du coeur actives ($CORE_VM) ==="
for nf in nrfd scpd amfd smfd ausfd udmd udrd pcfd nssfd bsfd; do
  if sshq "$CORE_VM" "systemctl is-active --quiet open5gs-$nf"; then ok "open5gs-$nf"; else ko "open5gs-$nf"; fi
done

echo "=== C2 : AMF ecoute NGAP (SCTP 38412) ==="
sshq "$CORE_VM" "ss -lnS | grep -q 38412" && ok "NGAP ouvert" || ko "NGAP absent"

echo "=== C3 : associations PFCP SMF<->UPF (via slice transport N6/N4) ==="
assoc=$(sshq "$CORE_VM" "grep -c 'PFCP associated' /var/log/open5gs/smf.log 2>/dev/null" || echo 0)
[ "${assoc:-0}" -ge 2 ] && ok "PFCP : $assoc associations (UPF EDGE + actuation)" || ko "PFCP : $assoc association(s) < 2"

echo "=== C4 : abonnes provisionnes ==="
subs=$(sshq "$CORE_VM" "mongosh --quiet open5gs --eval 'db.subscribers.countDocuments()' 2>/dev/null || mongo --quiet open5gs --eval 'db.subscribers.count()' 2>/dev/null" || echo 0)
[ "${subs:-0}" -ge 2 ] && ok "$subs abonnes" || ko "abonnes insuffisants ($subs < 2)"

echo "=== R1 : gNB enregistre a l'AMF (slice transport N2) ==="
sshq "$GNB_VM" "journalctl -u ueransim-gnb --no-pager | grep -q 'NG Setup procedure is successful'" \
  && ok "NG Setup reussi" || ko "NG Setup absent"

echo "=== R2 : UE eMBB - PDU session slice 1:657502 / DNN EDGE ==="
sshq "$GNB_VM" "sudo pkill -f ue-embb 2>/dev/null; sudo nohup /opt/UERANSIM/build/nr-ue -c /opt/ueransim-conf/ue-embb.yaml >/tmp/ue-embb.log 2>&1 & sleep 12; ip addr show uesimtun0 | grep -q '10\\.45\\.'" \
  && ok "uesimtun0 en 10.45.x.x (UPF EDGE)" || ko "pas de session eMBB (voir /tmp/ue-embb.log)"

echo "=== R3 : UE URLLC - PDU session slice 2:791515 / DNN actuation (UPF dedie) ==="
sshq "$GNB_VM" "sudo pkill -f ue-urllc 2>/dev/null; sudo nohup /opt/UERANSIM/build/nr-ue -c /opt/ueransim-conf/ue-urllc.yaml >/tmp/ue-urllc.log 2>&1 & sleep 12; ip addr show | grep -q '10\\.46\\.'" \
  && ok "uesimtun en 10.46.x.x (UPF actuation dedie)" || ko "pas de session URLLC (voir /tmp/ue-urllc.log)"

echo; echo "5G : $PASS OK, $FAIL KO"; exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)

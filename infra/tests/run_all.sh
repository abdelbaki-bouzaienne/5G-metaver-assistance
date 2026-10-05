#!/usr/bin/env bash
# Execution complete du plan de tests : Transport -> 5G (coeur+RAN) -> Edge -> E2E applicatif.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RES=0

echo "########## T - TRANSPORT ##########"
"$HERE/../transport/scripts/verify_transport_slices.sh" || RES=1

echo; echo "########## C+R - 5G COEUR + RAN ##########"
"$HERE/test_5g.sh" || RES=1

echo; echo "########## E - EDGE / CLOUD ##########"
"$HERE/test_edge.sh" || RES=1

echo; echo "########## A - E2E APPLICATIF ##########"
"$HERE/test_e2e_app.sh" || RES=1

echo
if [ $RES -eq 0 ]; then
  echo "TOUS LES TESTS AUTOMATISES PASSENT."
  echo "Reste O1/O2 (commande marketplace, checklist manuelle dans test-plan.md)."
else
  echo "DES TESTS ONT ECHOUE - voir ci-dessus."
fi
exit $RES

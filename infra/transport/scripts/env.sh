#!/usr/bin/env bash
# Valeurs du banc (2026-10-05). TRANSPORT_CONTROLLER=none -> stub inventaire en attendant V3.
export NSC_URL=http://127.0.0.1:8079     # stub : python3 ../stub/nsc_stub.py --port 8079
                                         # (remplacer par l'URL du vrai NSC en V3)
export NSC_TOKEN=

# CE de chaque site (mesures iperf3/RTT) - a confirmer avec l'inventaire OpenStack
export CE_RAN=10.10.1.1      # nf-ran  (d1)
export CE_EDGE=10.10.2.1     # nf-edge (d2)
export CE_CORE=10.10.3.1     # nf-core (d3)
export SSH_USER=ubuntu

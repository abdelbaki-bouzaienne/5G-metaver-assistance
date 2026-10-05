#!/usr/bin/env bash
# Valeurs du banc (fournies le 2026-10-05).

# NBI des trois OSM
export OSM1=nbi.10.0.3.8.nip.io          # domaine RAN (d1)
export OSM2=nbi.10.0.3.9.nip.io          # domaine edge/MEC (d2)
export OSM3=nbi.10.0.3.10.nip.io         # TODO: a confirmer - OSM2 indique deux fois dans la reponse

export OSM_USER=admin
export OSM_PASSWORD=admin
export OSM_PROJECT=admin

# Comptes VIM enregistres dans chaque OSM
export VIM1=osm-p1                       # OSM1
export VIM2=osm-p2                       # OSM2
export VIM3=osm-p3                       # OSM3

# Cluster K8s Sylva (option KNF coeur) enregistre dans osm3
export K8S_CLUSTER_CORE=wc-5g-core2

# Reseaux OpenStack du banc
export NET_MGMT=internal5G               # gestion
export NET_DATA=5g-inter-vm              # donnees (N2/N3/N4/N6 partages tant que
                                         # n2net/n3net/n6net ne sont pas crees - voir README)

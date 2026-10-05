# Plan de tests — 5G core, RAN, Edge, Transport, Cloud, E2E

Chaque test indique : objectif, commande, critère de succès. Les scripts (`test_*.sh`)
utilisent `infra/osm/scripts/env.sh` et `infra/transport/scripts/env.sh`.
Exécution complète : `./run_all.sh` (ordre T → C → R → E → A → O).

## T — Transport (`test_transport.sh`)

| # | Objectif | Méthode | Succès |
|---|---|---|---|
| T1 | Les 3 slices existent côté NSC | `GET /network-slices` | N3, N2, **N6/N4** présents, état établi |
| T2 | Débit sous plafond de tier par segment | iperf3 CE→CE 10 s | N3/N6-N4 ≈ plafond gold, N2 ≈ plafond premium (mesure sans contention, pas un minimum garanti) |
| T3 | RTT par segment | ping ×20 | RTT CE↔CE cohérent avec cible SDP-à-SDP (≤ 2×20 ms) ; **première mesure du segment N6/N4** |
| T4 | Isolation inter-slices | iperf3 simultané N3+N2 à saturation | aucun segment ne « fuit » dans l'autre : chacun reste à son plafond |

## C — Cœur 5G (`test_5g.sh`, partie core)

| # | Objectif | Méthode | Succès |
|---|---|---|---|
| C1 | NF actives | systemctl sur la VM core | nrfd, scpd, amfd, smfd, ausfd, udmd, udrd, pcfd, nssfd, bsfd `active` |
| C2 | AMF écoute N2 | `ss -lnS \| grep 38412` (SCTP) | port NGAP ouvert sur l'IP N2 |
| C3 | SMF ↔ UPF (N4) | log smfd : association PFCP | 2 associations (UPF EDGE + UPF actuation), via le slice transport N6/N4 |
| C4 | Abonnés provisionnés | mongo open5gs | 2 SUPI (…0001 eMBB, …0002 URLLC) avec les bons S-NSSAI/DNN |

## R — RAN + sessions PDU (`test_5g.sh`, partie ran)

| # | Objectif | Méthode | Succès |
|---|---|---|---|
| R1 | gNB enregistré à l'AMF | log nr-gnb | `NG Setup procedure is successful` (via slice N2) |
| R2 | UE eMBB : PDU session slice 1:657502 / DNN EDGE | `nr-ue -c ue-embb.yaml` | interface `uesimtun0` avec IP 10.45.x.x |
| R3 | UE URLLC : PDU session slice 2:791515 / DNN actuation | `nr-ue -c ue-urllc.yaml` | `uesimtun` avec IP 10.46.x.x (UPF **dédié**) |

## E — Edge / cloud (`test_edge.sh`)

| # | Objectif | Méthode | Succès |
|---|---|---|---|
| E1 | UE → plateforme edge par le slice | ping/curl 10.0.6.20 via `uesimtun0` | `edge-video` répond (HTTP 200 :8081), trajet gNB→N3→UPF→N6 |
| E2 | Pile métavers saine | `GET /healthz` de chaque service | twin, ingest, pipeline, session, signaling : 200 ; MinIO/PostgreSQL/Redis/coturn up |
| E3 | Débit UE→edge (profil F1) | iperf3 via uesimtun vers 10.0.6.20 | ≥ 100 Mbit/s montant (ou plafond radio sim.) |

## A — Applicatif E2E (`test_e2e_app.sh`)

| # | Objectif | Méthode | Succès |
|---|---|---|---|
| A1 | Scan fragmenté + reprise | upload 3 chunks, rejouer le 2ᵉ | checksums validés, reprise sans renvoi complet |
| A2 | Job 3DGS | complete → poll statut | `queued → running → done`, assets splat+tiles en S3 |
| A3 | Jumeau + entités + annotation | POST twin-version, entités panneau/ports, highlight | GET cohérents, coordonnées repère jumeau |
| A4 | Session collaborative | create + join (T+E), jetons TURN | jetons éphémères valides, journal d'événements |
| A5 | Scénarios métier | conformité client (ports surlignés) + câblage (2 ports + chemin) | entités résolues automatiquement des deux côtés |

## O — Commande marketplace (manuel, checklist)

| # | Objectif | Succès |
|---|---|---|
| O1 | Order `CFS_FieldAssist_Base` au marketplace | ordre `COMPLETED`, 3 slices transport créés par OSOM, NS OSM `READY`, release Helm déployée |
| O2 | Order `CFS_FieldAssist_WithActuation` | idem + slice URLLC et UPF dédié actifs ; test R3 passe |

## Budgets de qualité à mesurer en session (doc 1 §A.6)

- avatars p95 < 50 ms ; tracés AR < 100 ms ; vidéo verre-à-verre < 200 ms (720p30) ;
- erreur de relocalisation < 1–2 cm au panneau (spike) ; reconnexion < 5 s.

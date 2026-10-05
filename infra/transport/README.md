# Slices de transport entre PE (contrôleur NSC IETF)

Trois segments, chacun un slice de transport entre deux PE, matérialisé sur les PE par :
instance de service (VRF/EVI `metaverse-slice-<id>`), attachement SDP, politique de chemin
SR-TE délai minimal, protection TI-LFA (2 chemins disjoints), QoS 5QI → DSCP.

| Slice | sdps | Segment | Rôle | Statut banc |
|---|---|---|---|---|
| `metaverse-n3-ran-edge` | [d1, d2] | PE-RAN ⇄ PE-EDGE | N3 : gNB → UPF MEC (F1, F3/F4, boucle actuation) | testé (type urllc2) |
| `metaverse-n2-ran-core` | [d1, d3] | PE-RAN ⇄ PE-CORE | N2 : gNB → AMF | testé (type embb2) |
| `metaverse-n6n4-edge-core` | [d2, d3] | PE-EDGE ⇄ PE-CORE | N6/N4 : vidéo, avatars, supervision, SMF↔UPF | **à créer — 3ᵉ slice** (doc 2 §7.6) |

```bash
# TRANSPORT_CONTROLLER=none sur le banc : démarrer d'abord le stub inventaire
python3 stub/nsc_stub.py --port 8079 --inventory /var/lib/nsc/inventory.json &

./scripts/create_transport_slices.sh        # POST /network-slices ×3 (stub ou vrai NSC)
./scripts/verify_transport_slices.sh        # état + iperf3 + RTT + test d'isolation
```

**Stub NSC (V1/V2)** : `stub/nsc_stub.py` implémente la même API que le contrôleur du banc
mais ne configure aucun PE — il consigne l'intention exacte (slice, sdps, SLO) dans un
inventaire JSON et répond `ESTABLISHED`. La chaîne OpenSlice (RFS → AVAILABLE) fonctionne
donc dès maintenant ; au raccordement du vrai contrôleur V3, pointer `NSC_URL` dessus et
rejouer `create_transport_slices.sh` (les payloads sont identiques). Les mesures
iperf3/RTT de `verify_transport_slices.sh` restent valides (elles passent par les CE,
pas par le contrôleur) mais ne reflètent une politique de slice qu'avec le vrai NSC.

Notes :
- En nominal ces slices sont créés par OpenSlice à l'instanciation de `RFS_Transport_InterSite`
  (OSOM → contrôleur de ressource générique → HTTP vers le NSC) ; la ressource passe
  `AVAILABLE` quand le chemin est établi. Les JSON de ce répertoire sont exactement les
  caractéristiques portées par la RFS (`network_slice_id`, `sdps`, `connectivity_type` + KPI).
- Les mesures ping sont des RTT CE↔CE : ne pas les confondre avec la latence aller simple
  SDP-à-SDP du SLA (≤ 20 ms P99 ; ≤ 10 ms sur N3).
- Les plafonds mesurés sous iperf3 (gold ≈ 95/100, premium ≈ 48/50 sur le banc) sont des
  plafonds appliqués sans contention concurrente, pas des débits minimaux garantis.

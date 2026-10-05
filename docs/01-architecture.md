# Architecture de la solution

## 1. Les trois plans (séparation stricte)

| Plan | Contenu | Technologies | Tolérance |
|---|---|---|---|
| **Données lourdes (asynchrone)** | Scan, entraînement 3DGS, stockage, distribution des tuiles | `scan-ingest` + file de jobs + `gs-pipeline` (GPU) + S3/MinIO + CDN | Latence tolérée (≤ 500 ms), reprise obligatoire |
| **Métier (REST)** | Jumeau structuré (ports, panneaux, câbles, clients), annotations, sessions, droits | `twin-service` + `session-service` + PostgreSQL + OIDC | Dispo 99,5 %, reconnexion < 5 s |
| **Temps réel (P2P/relais)** | Avatars, gestes, tracés, vidéo | Netcode (UDP) + WebRTC (SRTP) + Unity Relay / coturn | p95 avatars < 50 ms, vidéo < 200 ms |

Une panne du plan 1 ou 2 ne coupe jamais une session en cours (plan 3 autonome une fois établie).

## 2. Vue réseau — slices et flux

### 2.1 Slices

| Slice | SST:SD | Rôle | Réalisation |
|---|---|---|---|
| **eMBB XR-Edge** | 1:657502 | Porte F1, F2, F3, F4, F5-supervision, F6 ; UPF au MEC ; DNN `EDGE` | RFS_RAN_XR_Edge + RFS_CN_XR_Edge + RFS_Transport_Access_XR |
| **URLLC Actuation** (option) | 2:791515 | Boucle de contrôle contrôleur MEC → actuateur uniquement ; DNN `actuation` ; UPF dédié | RFS_RAN_URLLC_Act + RFS_CN_URLLC_Act + RFS_Transport_Access_URLLC |
| **Transport N3** | — | PE-RAN ⇄ PE-EDGE (gNB → UPF MEC) | RFS_Transport_InterSite, sdps = [d1, d2] |
| **Transport N2** | — | PE-RAN ⇄ PE-CORE (gNB → AMF) | RFS_Transport_InterSite, sdps = [d1, d3] |
| **Transport N6/N4** | — | PE-EDGE ⇄ PE-CORE (vidéo, avatars, supervision) — **à instancier (3ᵉ slice)** | RFS_Transport_InterSite, sdps = [d2, d3] |
| **Hébergement edge** | — | K8s MEC : plateforme jumeau, synchro, décodeur, contrôleur d'actuation, S3 | RFS_Cloud_EdgePlatform (CRIDGE + Helm) |

### 2.2 Flux et priorités intra-slice eMBB (ordre de dégradation : F2 → F1 → F6 ; jamais F3 ni F5)

| Flux | Débit | Latence | Priorité | 5QI candidat | DSCP cible |
|---|---|---|---|---|---|
| F3 Synchro avatars | < 1 Mbit/s | < 50 ms | 1 | 3 (GBR) / 80 | AF41 |
| F5 Supervision expert→MEC | < 1 Mbit/s | < 50 ms | 1 | 80 | EF |
| F4 Avatars spatiaux (remplace F3) | > 10 Mbit/s | < 50 ms | 2 | 89/90 | AF41 |
| F6 Vidéo RGB(D) | 10 Mbit/s–1 Gbit/s | < 200 ms | 3 | 2 (GBR) | AF41 |
| F1 Capture 3D | ~100 Mbit/s montant | ≤ 500 ms | 4 | 8/9 | AF31 |
| F2 Chargement jumeau | rafale descendante | ≤ 500 ms | 5 (fond) | 8/9 | CS1 |
| F5 Boucle MEC→actuateur | < 1 Mbit/s | < 50 ms | slice URLLC isolée (option) | 82/83 | EF |

### 2.3 KPI de transport (par segment, CFS_Transport_InterSite)

Latence aller simple SDP-à-SDP ≤ 20 ms (P99) · gigue ≤ 2 ms · bande passante garantie 1 Gbit/s ·
rétablissement < 50 ms · segment N3 : latence ≤ 10 ms (RFS_Transport_Access_XR).

## 3. Vue orchestration

```
Client de slice ──commande──► OpenSlice (TMF633/641, marketplace)
                                   │ OSOM décompose CFS → RFS (+ règles LCM)
        ┌──────────────┬───────────┼─────────────────┬──────────────────┐
        ▼              ▼           ▼                 ▼                  ▼
   osm1 (RAN)     osm2 (edge)  osm3 (core)   Contrôleur transport   CRIDGE (K8s MEC)
   NS ran_ns      NS edge_ns   NS core_ns    NSC IETF /network-     chart Helm
   (gNB+UE)       (UPF×2 +     (Open5GS CP)  slices → config PE     metaverse-edge
                  edge apps)
```

- **OSM** : chaque domaine onboarde ses VNFD/NSD (répertoire `infra/osm/`). Les NSD sont
  référencés dans OpenSlice comme ResourceSpecifications via l'adaptateur OSM d'OpenSlice
  (synchronisation automatique des NSD au catalogue de ressources).
- **OpenSlice** : les RFS référencent ces ressources (`resourceSpecification`) ; les CFS sont
  reliées aux RFS (`isRealizedBy` → serviceSpecRelationship) ; deux composites statiques
  (`isBundle=true`) sont exposées au marketplace.
- **Transport** : à l'instanciation d'une RFS de transport, OSOM publie vers le contrôleur de
  ressource générique qui appelle en HTTP le NSC (`POST /network-slices`) avec
  `network_slice_id`, `sdps`, `connectivity_type` et les KPI ; la ressource passe AVAILABLE
  quand le chemin est établi.

## 4. Vue applicative (plateforme edge, MEC)

```
                       API Gateway (traefik) — TLS, OIDC
   ┌──────────────┬──────────────┬───────────────┬───────────────┐
   ▼              ▼              ▼               ▼               ▼
 twin-service  scan-ingest   gs-pipeline    session-service   signaling (WS)
 (REST, modèle (upload       (file de jobs, (sessions, rôles, (SDP/ICE WebRTC)
  jumeau,       fragmenté,    entraînement   jetons TURN/
  versions,     checksums,    3DGS GPU,      Relay, journal)
  entités,      reprise)      tuiles/LOD)
  annotations)
   │              │              │               │
 PostgreSQL     MinIO (S3): /raw /splat /tiles  Redis (jobs, sessions)
                                                 coturn (TURN/STUN, UDP+TCP 443)
```

Clients : app **Scan** (Unity iOS/Android), app **AR** (Unity iPad Pro, ARKit),
app **VR** (Unity Quest/OpenXR en V1 ; Vision Pro et Galaxy XR ensuite).
Canaux temps réel : Netcode for GameObjects (poses non fiables « dernier état gagnant »,
commandes fiables) + Unity WebRTC (vidéo H.264 720p30 adaptative, AR → VR).

## 5. Décisions d'architecture (rappel des ADR)

1. Jumeau = splat (visuel) **+** graphe structuré (métier).
2. Repère unique ancré sur le **marqueur image** (taille physique connue) ; transformation stockée par version de scan ; tous les tracés sont exprimés dans ce repère.
3. Pipeline 3DGS **asynchrone** (upload → job → statut → résultat).
4. Upload **fragmenté reprenable** (chunks + checksum SHA-256).
5. **Tuiles/LOD** + compression du splat ; préchargement hors session.
6. Hiérarchie de canaux : Netcode fiable (commandes) / non fiable (poses) / WebRTC (vidéo).
7. **TURN dès la V1** (coturn, TCP 443 en repli), Unity Relay en second choix.
8. **Session Service** = seul point de coordination (jetons, rôles, journal).
9. **OIDC unique** + URL S3 signées à courte durée.
10. Jumeau **versionné** immuable par scan (comparaison avant/après, audit).
11. **Mode dégradé** : vidéo → image fixe, avatars → pointeur seul.

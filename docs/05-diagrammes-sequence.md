# Diagrammes de séquence

## 1. Commande du service (marketplace → réseau)

```mermaid
sequenceDiagram
    actor NSC_client as Client de slice (direction interventions)
    participant OS as OpenSlice (TMF641/OSOM)
    participant OSM1 as osm1 (RAN)
    participant OSM2 as osm2 (edge)
    participant OSM3 as osm3 (core)
    participant NSC as Contrôleur transport (NSC IETF)
    participant K8S as CRIDGE / K8s MEC

    NSC_client->>OS: Order CFS_FieldAssist_Base (interventionSite=d1, expertSite=d3)
    OS->>OS: Décomposition CFS → RFS (règles LCM, projection des caractéristiques)
    par Domaines réseau
        OS->>OSM3: RFS_CN_XR_Edge → ns-create core_5g_ns (VIM3)
        OS->>OSM2: RFS_CN_XR_Edge → ns-create edge_mec_ns (UPF EDGE, VIM2)
        OS->>OSM1: RFS_RAN_XR_Edge → ns-create ran_xr_edge_ns (VIM1)
    and Transport (3 segments)
        OS->>NSC: POST /network-slices {sdps:[d1,d2]}  // N3
        OS->>NSC: POST /network-slices {sdps:[d1,d3]}  // N2
        OS->>NSC: POST /network-slices {sdps:[d2,d3]}  // N6/N4 (3e slice)
        NSC->>NSC: Configure PE1/PE2/PE3 (VRF, SDP, SR-TE, QoS, protection)
    and Hébergement
        OS->>K8S: RFS_Cloud_EdgePlatform → helm install metaverse-edge
    end
    NSC-->>OS: Ressources AVAILABLE
    OSM1-->>OS: NS READY (idem osm2, osm3)
    K8S-->>OS: Release deployed
    OS-->>NSC_client: Service ACTIVE (SLA : ordre de dégradation F2→F1→F6)
```

## 2. Phase A — Scan et jumeau (F1, F2)

```mermaid
sequenceDiagram
    actor T as Technicien (app Scan)
    participant GW as Gateway (MEC)
    participant SI as scan-ingest
    participant Q as File de jobs (Redis)
    participant GS as gs-pipeline (GPU)
    participant S3 as MinIO/S3
    participant TW as twin-service

    T->>T: Détection marqueur (échelle + origine) — scan refusé sinon
    T->>SI: POST /scans (site, marqueur) → scanId
    loop chunks (F1 ~100 Mbit/s, reprise)
        T->>SI: PUT /scans/{id}/chunks/{n} (+SHA-256)
        SI->>S3: /raw/...
    end
    T->>SI: POST /scans/{id}/complete
    SI->>Q: enqueue job 3DGS
    GS->>Q: poll → job
    GS->>GS: poses (COLMAP/ARKit) → entraînement → compression → tuiles/LOD
    GS->>S3: /splat /tiles
    GS->>TW: POST /twin-versions {site, transform_marker, assets, score}
    TW-->>T: notification « version prête »
    T->>TW: GET /twin-versions/{id}/assets?lod=low (F2, préchargement + cache)
    TW-->>T: URLs S3 signées (tuiles)
```

## 3. Phases B/C — Session collaborative (F3, F5, F6)

```mermaid
sequenceDiagram
    actor T as Technicien (iPad AR)
    actor E as Expert (VR Quest)
    participant SS as session-service
    participant SIG as signaling (WS)
    participant TURN as coturn
    participant TW as twin-service

    T->>T: Phase B : guidage local (procédure AR, aucune exigence réseau)
    T->>SS: POST /sessions (site, version) — difficulté rencontrée
    E->>SS: POST /sessions/{id}/join (rôle expert)
    SS-->>T: jeton + identifiants TURN éphémères (+ Relay en option)
    SS-->>E: idem
    E->>TW: GET assets (splat) — préchargé si possible
    par Netcode (UDP, P2P sinon Relay) — F3 priorité 1
        T-->>E: pose iPad (25 Hz, non fiable, dernier état gagnant)
        E-->>T: tête+mains, tracés/surlignages (repère jumeau), commandes fiables
    and WebRTC — F6 priorité 3
        T->>SIG: offer SDP
        E->>SIG: answer SDP
        T-->>E: vidéo H.264 720p30 adaptative (TURN TCP/443 si UDP bloqué)
    end
    E->>TW: GET /clients/{x}/ports → désignation entité
    E-->>T: highlight port gauche + droit (Netcode fiable)
    Note over T,E: Si réseau dégradé : vidéo→image fixe, avatars→pointeur ;<br/>reprise automatique < 5 s ; la coupure cloud ne coupe pas le P2P
```

## 4. Option actuation (F5 + boucle URLLC)

```mermaid
sequenceDiagram
    actor E as Expert
    participant SS as session-service
    participant AC as Contrôleur d'actuation (MEC)
    participant UPF as UPF dédié (DNN actuation)
    participant ACT as Actuateur (site)

    E->>AC: Supervision (slice transport N6/N4, flux EF, jamais mis en file)
    AC->>AC: Vérification droits + expiration de commande
    AC->>UPF: Boucle de contrôle (slice URLLC 2:791515, N3 isolé)
    UPF->>ACT: via gNB → passerelle actuateur
    ACT-->>AC: état (ack dans le délai, sinon comportement sûr local)
    AC-->>E: retour d'état + journal de session
```

## 5. Phase D — Clôture

```mermaid
sequenceDiagram
    actor T as Technicien
    participant SI as scan-ingest
    participant TW as twin-service
    participant SS as session-service

    T->>SI: Scan final (mêmes flux que Phase A)
    SI->>TW: nouvelle TwinVersion
    T->>TW: GET /sites/{id}/diff?from=avant&to=après
    T->>SS: POST /sessions/{id}/report (checklist, photos, annotations, tests)
    SS->>SS: validation explicite — le scan ne met pas à jour le SI seul
    SS-->>T: rapport archivé, session fermée
```

# PoC — Assistance métavers du technicien terrain (Network Slicing 5G multi-domaine)

Solution complète du PoC décrit dans les deux documents de référence :

1. **Cas d'usage réseau** : slicing 5G multi-domaine (eMBB XR-Edge + option URLLC actuation),
   3 sites (RAN / MEC / Core), 3 segments de transport entre PE, orchestration OSM ×3 +
   OpenSlice/OSOM, catalogue TMF (CFS/RFS) publié sur le marketplace.
2. **Solution applicative** : guidage expert (VR) / technicien (AR iPad) avec jumeau numérique
   3D Gaussian Splatting, Unity, Netcode for GameObjects, WebRTC, services cloud/edge.

## Topologie cible

```
  Site intervention (d1)          MEC (d2)                  Site central (d3)
  ┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
  │ gNB (UERANSIM)   │     │ UPF-EDGE  (DNN EDGE)│     │ Cœur 5G (AMF/SMF/...)│
  │ UE / technicien  │     │ UPF-ACT (DNN actua.)│     │ Expert (VR)          │
  │ Actuateur (opt.) │     │ Plateforme edge     │     │ Plateforme centrale  │
  │ CE nf-ran        │     │ (Twin, 3DGS, Sess.) │     │ CE nf-core           │
  └──────┬───────────┘     │ CE nf-edge          │     └──────────┬───────────┘
         │                 └────────┬────────────┘                │
       PE-RAN (PE1) ◄── N3 ──► PE-EDGE (PE2) ◄── N6/N4 ──► PE-CORE (PE3)
         └───────────────────── N2 ────────────────────────────┘
       osm1 (VIM1)             osm2 (VIM2)                  osm3 (VIM3)
                     OpenSlice / OSOM  +  Contrôleur de transport (NSC IETF)
```

## Arborescence du dépôt

| Répertoire | Contenu |
|---|---|
| `docs/` | Architecture, hypothèses & améliorations, plan de déploiement pas-à-pas, modèle de données du jumeau, diagrammes de séquence |
| `infra/osm/` | Packages VNF/NS (SOL006) pour osm1 (RAN), osm2 (edge), osm3 (cœur), NST de slices, scripts de build & onboarding |
| `infra/openslice/` | Payloads TMF633 : ResourceSpecs, RFS, CFS atomiques, 2 CFS composites ; règles LCM ; script Python de publication catalogue + marketplace |
| `infra/transport/` | Définitions des 3 slices de transport (N3, N2, N6/N4) et script d'appel du contrôleur NSC (`POST /network-slices`) |
| `infra/tests/` | Plan de tests E2E et scripts (iperf3, RTT, isolation inter-slices, validation 5G/RAN/Edge/Transport/cloud) |
| `apps/` | Services backend : `twin-service`, `scan-ingest`, `gs-pipeline`, `session-service`, `signaling`, coturn ; OpenAPI ; docker-compose ; chart Helm `metaverse-edge` (déployable par CRIDGE) |
| `unity/` | Squelettes C# des 3 apps Unity (Scan, AR iPad, VR Quest) : relocalisation marqueur, upload fragmenté, synchro avatars Netcode, vidéo WebRTC, tracés ancrés |

## Démarrage rapide

1. **Lire** `docs/03-plan-deploiement.md` (ordre complet, de l'onboarding OSM au test E2E).
2. **Infra** :
   ```bash
   # Packager et onboarder les VNF/NS sur les 3 OSM
   ./infra/osm/scripts/build_packages.sh
   ./infra/osm/scripts/onboard_all.sh            # utilise infra/osm/scripts/env.sh

   # Créer les 3 slices de transport (dont le segment N6/N4 manquant)
   ./infra/transport/scripts/create_transport_slices.sh

   # Publier le catalogue CFS/RFS sur OpenSlice + marketplace
   python3 infra/openslice/scripts/publish_catalog.py --env infra/openslice/scripts/env.example.json
   ```
3. **Tests** : `./infra/tests/run_all.sh` (voir `infra/tests/test-plan.md`).
4. **Applications** : `cd apps && docker compose up -d` en local/MEC, ou via la CFS
   `CFS_Edge_Hosting` (chart Helm `apps/deploy/helm/metaverse-edge` déployé par CRIDGE).

## Hypothèses principales (détail dans `docs/02-ameliorations.md`)

- RAN simulé par **UERANSIM** (gNB + UE) sur osm1 — remplaçable par un gNB réel.
- Cœur 5G **Open5GS** : plan de contrôle sur le site central (osm3 / cluster Sylva en option KNF),
  **UPF distribué au MEC** (osm2), un **UPF dédié** pour l'option URLLC.
- S-NSSAI du banc conservés : eMBB **1:657502**, URLLC **2:791515** ; DNN `EDGE` et `actuation`.
- Plateforme edge : les services métavers de ce dépôt remplacent Thing'In (non disponible) ;
  l'application `edge-video` du banc reste fournie comme substitution minimale.
- Contrôleur de transport : API `POST /network-slices` (NSC IETF) du banc, adaptateur OpenSlice
  existant ; sdps `d1`, `d2`, `d3`.

Les points à confirmer avec vous sont listés en fin de `docs/02-ameliorations.md`
(questions ouvertes : adresses/identifiants des OSM et d'OpenSlice, convention décimale/hexa
du SD dans l'API, disponibilité GPU au MEC pour l'entraînement 3DGS, choix Unity Relay vs TURN seul).

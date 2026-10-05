# Hypothèses, améliorations apportées et questions ouvertes

## 1. Hypothèses prises (faute d'information, modifiables)

| # | Hypothèse | Justification |
|---|---|---|
| H1 | RAN = **UERANSIM** (gNB + UE simulés) sur osm1 | Le banc n'atteste pas l'exécution d'un gNB réel ; UERANSIM permet de valider toute la chaîne S-NSSAI/DNN de bout en bout sur OpenStack sans radio |
| H2 | Cœur 5G = **Open5GS** (CP sur osm3, UPF au MEC sur osm2) | Open source, supporte multi-S-NSSAI, multi-DNN, UPF distribués ; le cluster Sylva `wc-5g-core2` est en cours — un package KNF (Helm) est fourni en alternative au package VM |
| H3 | S-NSSAI du banc conservés : 1:657502 et 2:791515 ; DNN `EDGE` et `actuation` | Cohérence avec les slices de transport déjà testées (embb2, urllc2) |
| H4 | Plateforme edge = les services de ce dépôt (`apps/`) à la place de **Thing'In** | Le chart Thing'In relève de Provorange et n'est pas disponible ; `edge-video` reste fournie comme substitution minimale du banc |
| H5 | GPU : l'entraînement 3DGS tourne au MEC si un nœud GPU existe, sinon le worker `gs-pipeline` fonctionne en **mode mock** (résultat pré-calculé) pour démontrer la chaîne | Un PoC réseau n'exige pas un vrai entraînement ; le pipeline, les statuts et les formats restent identiques |
| H6 | V1 VR = **Quest uniquement** (OpenXR), RGB seul (pas de profondeur) | Recommandations du document 1 ; Vision Pro / Galaxy XR et RGB-D en extension |
| H7 | TURN (coturn) hébergé sur la plateforme edge, secret partagé avec `session-service` | « TURN dès la V1 » ; Unity Relay optionnel (nécessite un compte UGS) |
| H8 | Contrôleur de transport : API `POST /network-slices`, sdps `d1/d2/d3`, tiers Gold/Premium comme sur le banc | Résultats acquis du banc (§7.6 du doc 2) |

## 2. Améliorations apportées par rapport aux documents

1. **Le 3ᵉ segment de transport N6/N4 (PE-EDGE ⇄ PE-CORE) est créé et testé** : le doc 2
   indique qu'il « reste à instancier ». Ce dépôt fournit la commande (`infra/transport/slices/n6n4.json`),
   le test proposé (iperf3 + RTT entre nf-edge et nf-core) et son intégration au plan de tests.
2. **Catalogue en deux composites statiques + catégories marketplace** : conformément au §3.5,
   `CFS_FieldAssist_Base` et `CFS_FieldAssist_WithActuation` réutilisent les mêmes CFS atomiques ;
   le script de publication crée le catalogue « Provorange Field Assist », la catégorie
   « Métavers terrain » et passe les CFS en `lifecycleStatus=Active` (visibles au marketplace).
3. **Ordre de dégradation dans le SLA** : les caractéristiques des CFS incluent
   `degradationOrder = F2,F1,F6` (jamais F3/F5), comme recommandé au §2.1 — c'est cet ordre,
   plus que les valeurs cibles, qui est contractualisé.
4. **Points de mesure explicites** : chaque KPI de latence porte son point de mesure et son
   percentile (terminal ↔ application MEC P95 pour l'eMBB ; SDP-à-SDP P99 pour le transport) —
   évite l'ambiguïté PDB 5QI vs latence applicative (annexe A du doc 2).
5. **Chargement du jumeau requalifié** : pas de cible « 10 Gbit/s » ; remplacé par
   `timeToFirstUsableTwin` (caractéristique applicative de la composite) + tuiles/LOD +
   préchargement + cache, et un plafond descendant conditionnel (1 Gbit/s non garanti).
6. **UPF URLLC réellement séparé** : le package `osm2` permet d'instancier le même VNFD UPF
   deux fois (DNN `EDGE` / DNN `actuation`) avec des jours-1 distincts, matérialisant
   l'`isolationLevel=DEDICATED` sans dupliquer le code.
7. **Sécurité par défaut** : OIDC unique (Keycloak mutualisable avec celui d'OpenSlice),
   URL S3 signées courtes, identifiants TURN éphémères (HMAC time-limited), TLS au gateway.
8. **Modèle de données du jumeau livré** (doc 1 le demandait) : `docs/04-modele-donnees-jumeau.md`
   + OpenAPI `apps/api/openapi.yaml` + implémentation `twin-service`.
9. **Mode dégradé implémenté côté clients** : scripts Unity `DegradedModeController.cs`
   (vidéo → image fixe, avatars → pointeur) et reconnexion automatique avec reprise d'état.
10. **Tests d'isolation systématisés** : chaque création de slice de transport est suivie d'un
    test de non-fuite vers l'autre slice (repris du banc) et d'une mesure sous plafond de tier.

## 3. Ce qui est démontré vs ce qui reste hors PoC

| Démontré par ce dépôt | Hors périmètre V1 (extension) |
|---|---|
| Chaîne complète intention → CFS → RFS → OSM/NSC/CRIDGE → réseau | Vrai gNB radio + terminaux 5G physiques |
| 3 slices de transport mesurées + isolation | Garanties de rafale (durée/volume/admission) |
| eMBB XR-Edge avec UPF MEC + DNN EDGE | URLLC avec actuateur physique réel (la slice et le contrôleur sont fournis, l'actuateur est simulé) |
| Pipeline scan → 3DGS → tuiles → chargement | Entraînement GPU production (mode mock par défaut) |
| Session collaborative Quest + iPad (avatars, tracés, vidéo) | Vision Pro, Galaxy XR, avatars spatiaux (F4), RGB-D |
| Scénarios conformité globale / client / câblage (modèle de données + API) | Détection automatique d'écarts entre scans |

## 4. Questions ouvertes — RÉPONSES REÇUES (2026-10-05)

| # | Question | Réponse | Appliqué dans |
|---|---|---|---|
| 1 | Accès OSM | OSM1 `nbi.10.0.3.8.nip.io` (VIM `osm-p1`), OSM2 `nbi.10.0.3.9.nip.io` (`osm-p2`), **OSM3 : à confirmer** (`osm-p3`) — OSM2 indiqué deux fois dans la réponse | `infra/osm/scripts/env.sh` |
| 1b | Accès OpenSlice | UI `http://10.0.3.7/`, API `http://10.0.3.7:13082/tmf-api`, Keycloak `http://10.0.3.7/auth/realms/openslice/...`, client `osapiWebClientId`/`secret`, user `admin` (mot de passe **non commité** : exporter `OPENSLICE_PASSWORD` avant `publish_catalog.py`) | `infra/openslice/scripts/env.json` |
| 2 | Convention SD | `decimal` côté catalogue/API TMF ; **hexadécimal côté Helm OSM** : 657502=`0A085E`, 791515=`0C13DB` | README OSM + descripteur KNF |
| 3 | GPU au MEC | `GPU_MEC=mock` jusqu'à preuve d'un nœud GPU | défaut `GS_MODE=mock` inchangé |
| 4 | Unity Relay | `off` — V1 = TURN uniquement | défaut `UNITY_RELAY_ENABLED=false` inchangé |
| 5 | Référentiel | `TWIN_INVENTORY=import` depuis `infrastructure-inventory` | `apps/twin-service/inventory/` (exemple + commande d'import vers `POST /twin/import`) |
| 6 | Images/réseaux | image `ubuntu-22.04` ; gestion `internal5G` ; données **`5g-inter-vm` partagé** (n2net/n3net/n6net à créer plus tard, cf. inventaire OpenStack) — ⚠ adapter les IP fixes des `params/*.yaml` au subnet réel | `params/*.yaml` + README OSM |
| 7 | Contrôleur transport | `TRANSPORT_CONTROLLER=none` → **stub NSC à inventaire** fourni (`infra/transport/stub/nsc_stub.py`), même API ; intention rejouable telle quelle sur le vrai contrôleur V3 | `infra/transport/` |

### Reste à confirmer
- Hostname NBI d'**OSM3** (seul manquant).
- Subnet réel de `5g-inter-vm` pour fixer (ou laisser en DHCP) les IP N2/N3/N4/N6 des
  `params/*.yaml`, et IP des CE (`infra/transport/scripts/env.sh`).

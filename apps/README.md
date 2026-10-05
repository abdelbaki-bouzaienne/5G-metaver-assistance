# Plateforme applicative (MEC) — services métavers

Implémentation des trois plans de l'architecture (voir `docs/01-architecture.md`).
Testée de bout en bout : scan fragmenté → job 3DGS → jumeau versionné → session
collaborative (TURN HMAC vérifié, signaling WebRTC relayé) → scénarios métier → clôture.

| Service | Port | Rôle |
|---|---|---|
| `gateway` (nginx) | 8000 | Routage `/twin` `/ingest` `/pipeline` `/session` `/actuation` `/signaling`, TLS+OIDC en production |
| `twin-service` | 8001 | Modèle métier du jumeau : sites, versions immuables, entités, ports, clients, câbles, annotations, diff, import, revue humaine |
| `scan-ingest` | 8002 | Upload fragmenté/reprenable (SHA-256, idempotent), refus sans marqueur, mise en file des jobs |
| `gs-pipeline` | 8003 | Pipeline 3DGS asynchrone avec reprises ; `GS_MODE=mock` (défaut, sans GPU) ou `gpu` (`GS_TRAIN_CMD`) ; produit splat + tuiles/LOD puis crée la TwinVersion |
| `session-service` | 8004 | Sessions, rôles T/E/A, identifiants TURN éphémères (HMAC coturn), option Unity Relay, journal, rapport de clôture |
| `signaling` | 8005 | Relais WebSocket SDP/ICE (une room par session) — jamais sur le chemin des médias |
| `actuation-controller` | 8006 | Supervision expert (N6/N4) → boucle de contrôle URLLC vers la passerelle actuateur ; expiration des commandes ; actuateur simulé par défaut |
| PostgreSQL / Redis / MinIO / coturn | — | Persistance, file de jobs, S3 (`/raw /splat /tiles`), TURN/STUN (UDP 3478 + TCP 443) |

## Lancer en local / sur la VM edge

```bash
cp deploy/env.example deploy/.env    # éditer PUBLIC_HOST + TURN_SECRET
docker compose --env-file deploy/.env up -d --build
curl http://localhost:8000/healthz
```

C'est exactement ce que fait le cloud-init de `edge_platform_vnf` (osm2).

## Déployer via OpenSlice (CFS_Edge_Hosting → CRIDGE)

Le chart `deploy/helm/metaverse-edge` est la réalisation de `RFS_Cloud_EdgePlatform` :

```bash
# construire et pousser les images vers votre registre
for s in twin-service scan-ingest gs-pipeline session-service signaling actuation-controller; do
  docker build -t $REGISTRY/$s:1.0.0 $s && docker push $REGISTRY/$s:1.0.0
done
helm install metaverse-edge deploy/helm/metaverse-edge \
  --set image.registry=$REGISTRY --set publicHost=<IP_N6> --set turnSecret=<secret>
```

Projections des caractéristiques CFS → values : `clusterSize→profile`,
`objectStorageGb→minio.storageGb`, `gpuEnabled→gsPipeline.gpuEnabled`.

## Contrat d'API

`api/openapi.yaml` (vue consolidée) ; chaque service FastAPI expose aussi son propre
`/docs` (Swagger UI) et `/openapi.json`.

## Sécurité (V1 → production)

- OIDC unique : activer la validation JWT au gateway (`auth_request` Keycloak) — le realm
  peut être mutualisé avec celui d'OpenSlice.
- URL S3 signées à courte durée pour les assets (presign MinIO) ; identifiants TURN
  éphémères déjà en place (HMAC time-limited, TTL 1 h).
- Flux temps réel chiffrés : SRTP (WebRTC) ; DTLS pour Netcode si Relay.

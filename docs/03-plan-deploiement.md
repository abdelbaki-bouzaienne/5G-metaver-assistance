# Plan de déploiement pas-à-pas

Pré-requis : les 3 OSM joignables (NBI), OpenSlice opérationnel (portail, Keycloak, OSOM,
CRIDGE, adaptateur transport), contrôleur de transport (NSC) joignable, connectivité
inter-VM en place, `osmclient` et `python3` sur la machine d'administration.

## Étape 0 — Configuration

```bash
cp infra/osm/scripts/env.sh.example infra/osm/scripts/env.sh        # éditer les 3 OSM + VIMs
cp infra/openslice/scripts/env.example.json infra/openslice/scripts/env.json   # éditer OpenSlice
cp infra/transport/scripts/env.sh.example infra/transport/scripts/env.sh       # éditer le NSC
```

Vérifier dans chaque VIM OpenStack : image `ubuntu-22.04` présente, réseaux `mgmt`
(avec DHCP + route vers l'admin), `n2net`, `n3net`, `n6net` créés (provider ou tenant routés
via les CE/PE du banc), flavors ≥ 2 vCPU / 4 Go.

## Étape 1 — Packages OSM (vnfpackage, nspackage, nsd)

```bash
./infra/osm/scripts/build_packages.sh      # produit les .tar.gz SOL004/SOL007
./infra/osm/scripts/onboard_all.sh         # osm1: RAN ; osm2: UPF×2 + edge ; osm3: cœur 5G
```

Contenu par domaine :

| OSM | VNFD | NSD | Rôle |
|---|---|---|---|
| osm1 (VIM1) | `ueransim_gnb_vnf` | `ran_xr_edge_ns` | gNB + UE, S-NSSAI 1:657502 et 2:791515, rattaché N2/N3 |
| osm2 (VIM2) | `open5gs_upf_vnf` (×2 instanciations), `edge_platform_vnf` | `edge_mec_ns` | UPF EDGE + UPF actuation + plateforme edge (edge-video + docker-compose métavers) |
| osm3 (VIM3) | `open5gs_core_vnf` (VM) ou `open5gs_core_knf` (Helm/Sylva) | `core_5g_ns` | AMF/SMF/NRF/UDM/UDR/AUSF/PCF/NSSF + WebUI |

Instanciation (exemples complets dans `infra/osm/scripts/instantiate_examples.sh`) :

```bash
# osm3 d'abord (le cœur), puis osm2 (UPF pointant vers le SMF), puis osm1 (gNB vers AMF)
osm --hostname $OSM3 ns-create --ns_name core5g   --nsd_name core_5g_ns    --vim_account VIM3 \
    --config_file infra/osm/osm3-core/params/core_params.yaml
osm --hostname $OSM2 ns-create --ns_name edgemec  --nsd_name edge_mec_ns   --vim_account VIM2 \
    --config_file infra/osm/osm2-edge/params/edge_params.yaml
osm --hostname $OSM1 ns-create --ns_name ranxr    --nsd_name ran_xr_edge_ns --vim_account VIM1 \
    --config_file infra/osm/osm1-ran/params/ran_params.yaml
```

(Optionnel) NST de slice : `infra/osm/nst/` contient `embb_xr_edge_nst.yaml` et
`urllc_actuation_nst.yaml` pour une instanciation « network slice » native OSM.

## Étape 2 — Slices de transport (contrôleur NSC)

```bash
./infra/transport/scripts/create_transport_slices.sh     # N3 [d1,d2], N2 [d1,d3], N6/N4 [d2,d3]
./infra/transport/scripts/verify_transport_slices.sh     # état + attachements
```

Le segment **N6/N4 (PE2 ⇄ PE3)** est le troisième slice encore jamais instancié sur le banc :
il est créé ici puis mesuré à l'étape 4 (iperf3 + RTT entre nf-edge et nf-core).

## Étape 3 — Catalogue OpenSlice (CFS + RFS) et marketplace

```bash
python3 infra/openslice/scripts/publish_catalog.py --env infra/openslice/scripts/env.json
```

Le script (idempotent) :
1. vérifie que les ResourceSpecs issues des NSD OSM sont synchronisées (sinon les crée en
   « logical resource » pour le transport et le K8s) ;
2. crée les **RFS** : `RFS_RAN_XR_Edge`, `RFS_CN_XR_Edge`, `RFS_Transport_Access_XR`,
   `RFS_RAN_URLLC_Act`, `RFS_CN_URLLC_Act`, `RFS_Transport_Access_URLLC`,
   `RFS_Transport_InterSite`, `RFS_Cloud_EdgePlatform` ;
3. crée les **CFS atomiques** : `CFS_eMBB_XR_Edge`, `CFS_URLLC_Actuation`,
   `CFS_Transport_InterSite`, `CFS_Edge_Hosting` (reliées à leurs RFS) ;
4. crée les **2 composites** : `CFS_FieldAssist_Base` et `CFS_FieldAssist_WithActuation`
   (`isBundle=true`, bundles + requires conformes au §4.1 du doc 2) ;
5. crée le catalogue **« Provorange Field Assist »** + catégorie **« Métavers terrain »**,
   y attache les CFS et les passe en `lifecycleStatus=Active` → visibles au **marketplace**.

Ensuite, dans le portail OpenSlice, importer les règles LCM décrites dans
`infra/openslice/lcm-rules/README.md` (Blockly, à recréer via l'UI — export non portable
entre instances) : projection des caractéristiques CFS → RFS et instanciation des 3 segments
de transport avec les bons `sdps`.

## Étape 4 — Tests (voir `infra/tests/test-plan.md`)

```bash
./infra/tests/run_all.sh
```

Ordre : transport (T1–T4) → cœur 5G (C1–C4) → RAN/PDU sessions (R1–R3) → edge/cloud (E1–E3)
→ E2E applicatif (A1–A5) → commande marketplace de bout en bout (O1–O2).

## Étape 5 — Applications

- **Backend (MEC)** : commandé via `CFS_Edge_Hosting` (CRIDGE déploie
  `apps/deploy/helm/metaverse-edge`) ou manuellement : `cd apps && docker compose up -d`.
- **Clients Unity** : ouvrir `unity/` — trois projets (Scan, ARClient, VRClient),
  packages requis listés dans `unity/README.md`. Renseigner l'URL du gateway et le realm OIDC
  dans `unity/Common/ClientConfig.cs`.

## Étape 6 — Commande client (démonstration marketplace)

1. Portail OpenSlice → Marketplace → **CFS_FieldAssist_Base** → Order
   (interventionSite=d1, expertSite=d3, maxTechnicians=2).
2. OSOM décompose : eMBB XR-Edge (osm1+osm2+osm3), 3 × Transport_InterSite (NSC),
   Edge_Hosting (CRIDGE). Suivre l'ordre dans Service Order Management.
3. Vérifier `ACTIVE`, puis dérouler le scénario métier : scan → jumeau → session AR/VR →
   conformité client → câblage → clôture (checklist A1–A5).
4. Rejouer avec **CFS_FieldAssist_WithActuation** pour l'option URLLC.

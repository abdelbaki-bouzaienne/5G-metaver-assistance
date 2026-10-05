# Catalogue OpenSlice (CFSS + RFSS) et marketplace

Modélisation TMF633 conforme au doc 2 (§4–5) : les **CFS** sont commandables par le client
de slice ; les **RFS** décrivent la réalisation domaine par domaine et référencent, via
`resourceSpecification`, la ressource dont le contrôleur assure l'instanciation
(NSD OSM synchronisés, ressource logique `transport-slice` pour le NSC, chart Helm pour CRIDGE).

```
CFS_FieldAssist_Base (isBundle) ────────────── CFS_FieldAssist_WithActuation (isBundle)
 ├─ bundles → CFS_eMBB_XR_Edge                  ├─ bundles → CFS_eMBB_XR_Edge
 ├─ requires → CFS_Transport_InterSite (×3)     ├─ bundles → CFS_URLLC_Actuation
 └─ requires → CFS_Edge_Hosting                 ├─ requires → CFS_Transport_InterSite (×3)
                                                └─ requires → CFS_Edge_Hosting
CFS atomiques → RFS (isRealizedBy) :
 CFS_eMBB_XR_Edge      → RFS_RAN_XR_Edge · RFS_CN_XR_Edge · RFS_Transport_Access_XR
 CFS_URLLC_Actuation   → RFS_RAN_URLLC_Act · RFS_CN_URLLC_Act · RFS_Transport_Access_URLLC
 CFS_Transport_InterSite → RFS_Transport_InterSite          (ressource : TransportSlice_NSC)
 CFS_Edge_Hosting      → RFS_Cloud_EdgePlatform             (ressource : MetaverseEdge_HelmChart)
RFS réseau → ressources : ran_xr_edge_ns (osm1) · edge_mec_ns (osm2) · core_5g_ns (osm3)
```

## Publication

```bash
cp scripts/env.example.json scripts/env.json   # éditer URL/identifiants OpenSlice
python3 scripts/publish_catalog.py --env scripts/env.json [--dry-run]
```

Le script est idempotent (upsert par nom). Il crée les ResourceSpecs logiques, les 8 RFS,
les 4 CFS atomiques, les 2 composites, le catalogue **« Provorange Field Assist »**, la
catégorie **« Métavers terrain »**, puis passe toutes les CFS en `lifecycleStatus=Active`
→ visibles et commandables au **marketplace** OpenSlice.

Pré-requis côté OpenSlice :
- adaptateur OSM configuré pour les 3 OSM (les NSD `ran_xr_edge_ns`, `edge_mec_ns`,
  `core_5g_ns` doivent apparaître comme ResourceSpecifications — le script le vérifie) ;
- CRIDGE enregistré sur le cluster K8s du MEC, chart `metaverse-edge` accessible
  (`apps/deploy/helm/metaverse-edge`) ;
- adaptateur transport (contrôleur de ressource générique → NSC) actif pour la catégorie
  `transport-slice`.

Après publication, recréer les règles LCM dans le portail : voir `lcm-rules/README.md`
(validation de commande, instanciation des 3 segments avec les bons `sdps`, projection
des caractéristiques, supervision SLA, désactivation propre).

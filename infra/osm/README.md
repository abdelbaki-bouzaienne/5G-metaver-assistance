# Packages OSM (vnfpackage / nspackage / nsd)

Un domaine OSM par site, conformément au banc : `osm1` (RAN, d1), `osm2` (edge/MEC, d2),
`osm3` (cœur, d3). Format SOL006 (OSM ≥ 12), images Ubuntu 22.04 + cloud-init (Jinja2,
variables jour-1 via `additionalParamsForVnf`).

| Package | Type | Domaine | Contenu |
|---|---|---|---|
| `ueransim_gnb_vnf` | VNF | osm1 | gNB UERANSIM + 2 profils UE (eMBB 1:657502/DNN EDGE, URLLC 2:791515/DNN actuation) |
| `ran_xr_edge_ns` | NS | osm1 | gNB rattaché à mgmt/n2net/n3net |
| `open5gs_upf_vnf` | VNF | osm2 | UPF Open5GS paramétrable (DNN, subnet, IP N3/N4) — instancié 2× : `upf-edge` et `upf-act` (isolation DEDICATED) |
| `edge_platform_vnf` | VNF | osm2 | Plateforme edge : pile métavers (`apps/`, docker compose) + `edge-video` (substitution du banc) |
| `edge_mec_ns` | NS | osm2 | UPF ×2 + plateforme, rattachés à mgmt/n3net/n4net/n6net |
| `open5gs_core_vnf` | VNF | osm3 | Cœur 5G Open5GS (CP seul : NRF/SCP/AMF/SMF/AUSF/UDM/UDR/PCF/NSSF/BSF + WebUI), 2 S-NSSAI, 2 DNN, UPF distants au MEC |
| `core_5g_ns` | NS | osm3 | Cœur rattaché à mgmt/n2net/n4net |
| `open5gs_core_knf` / `core_5g_knf_ns` | KNF/NS | osm3 | Alternative Helm (chart Gradiant `open5gs`) sur le cluster Sylva `wc-5g-core2` |
| `nst/*.yaml` | NST | tous | Templates de slice OSM (optionnels, tests intra-domaine) |

## Plan d'adressage par défaut (modifiable dans `*/params/*.yaml`)

| Réseau VIM | Usage | IPs |
|---|---|---|
| `mgmt` | gestion (DHCP) | — |
| `n2net` | gNB ↔ AMF | AMF 10.0.2.10 · gNB 10.0.2.21 |
| `n3net` | gNB ↔ UPF | gNB 10.0.3.21 · UPF-EDGE 10.0.3.10 · UPF-ACT 10.0.3.11 |
| `n4net` | SMF ↔ UPF | SMF 10.0.4.30 · UPF-EDGE 10.0.4.10 · UPF-ACT 10.0.4.11 |
| `n6net` | UPF → plateforme edge | plateforme 10.0.6.20 |
| Subnets UE | par DNN | EDGE 10.45.0.0/16 · actuation 10.46.0.0/16 |

Sur le banc, ces réseaux traversent les CE/PE : `n2net` emprunte le slice de transport N2
(PE-RAN ⇄ PE-CORE), `n3net` le slice N3 (PE-RAN ⇄ PE-EDGE), `n4net`/`n6net` le slice N6/N4
(PE-EDGE ⇄ PE-CORE). Voir `infra/transport/`.

## Utilisation

```bash
cp scripts/env.sh.example scripts/env.sh   # éditer
./scripts/build_packages.sh                # construit les .tar.gz dans _build/
./scripts/onboard_all.sh                   # vnfd-create / nsd-create / nst-create sur les 3 OSM
./scripts/instantiate_examples.sh          # cœur -> MEC -> RAN, avec attente READY
```

Points d'attention :
- renseigner `repo_url` dans `osm2-edge/params/edge_params.yaml` (URL de ce dépôt, accessible
  depuis la VM edge) ;
- le SD est en **convention décimale** (657502 / 791515) partout — à confirmer selon l'API
  de votre cœur (champ 24 bits, cf. doc 2 §4.2) ;
- adapter le nom d'image (`ubuntu-22.04`) et les noms de réseaux aux VIM réels ;
- UERANSIM se compile au premier boot (~5 min) ; le gNB démarre ensuite en service systemd,
  les UE (`nr-ue`) sont lancés par les scripts de test.

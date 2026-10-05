# Règles LCM (Blockly / OSOM)

Les règles LCM se créent dans le portail OpenSlice (Service Spec → onglet *LCM Rules*,
éditeur Blockly). L'export Blockly n'étant pas portable entre instances, ce document décrit
chaque règle à recréer ; la logique est volontairement simple et déterministe
(« le LLM décide du type de besoin et de la composite ; le code vérifie la cohérence de la
commande, la décompose et pilote sa réalisation »).

## R1 — `CFS_FieldAssist_Base` / PRE_PROVISION : validation de la commande

- Vérifier `interventionSite ∈ {d1}` et `expertSite ∈ {d3}` (sites du banc) ;
  sinon positionner l'ordre en `REJECTED` avec message.
- Vérifier `maxTechnicians ≤ 4` (dimensionnement cas défavorable F4+F6).

## R2 — `CFS_FieldAssist_Base` / CREATION : instanciation des 3 segments de transport

Pour la CFS `CFS_Transport_InterSite` référencée (requires), créer **3 instances** avec
projection des caractéristiques :

| Instance | network_slice_id | sdps | latencyOneWayMsP99 | guaranteedBandwidthMbps |
|---|---|---|---|---|
| N3 | `metaverse-n3-<orderId>` | `["<interventionSite>","d2"]` | 10 | 1000 |
| N2 | `metaverse-n2-<orderId>` | `["<interventionSite>","<expertSite>"]` | 20 | 50 |
| N6/N4 | `metaverse-n6n4-<orderId>` | `["d2","<expertSite>"]` | 20 | 1000 |

(Blockly : blocs « create new service order item » sur la spec Transport, avec
`setCharacteristicValue` pour chaque ligne.)

## R3 — `CFS_eMBB_XR_Edge` / CREATION : projection vers les RFS

- `RFS_CN_XR_Edge.sessionAMBR_UL ← ulPeakMbps` ; `sessionAMBR_DL ← dlPeakMbps`.
- `RFS_RAN_XR_Edge.cells ← interventionSite` (mapping site → cellules).
- `RFS_Transport_Access_XR.sdps ← ["<interventionSite>","d2"]`.

## R4 — `CFS_Edge_Hosting` / CREATION : paramètres Helm

- Projeter `clusterSize`, `objectStorageGb`, `gpuEnabled` vers les caractéristiques de la
  ressource `MetaverseEdge_HelmChart` (values du chart : `gsPipeline.gpuEnabled`,
  `minio.persistence.size`, `profile`).

## R5 — `CFS_FieldAssist_WithActuation` / CREATION

- Mêmes règles R1–R4, plus : propagation `actuatorGateway` vers `RFS_CN_URLLC_Act`
  et création du segment transport dédié `RFS_Transport_Access_URLLC`
  (`sdps = ["<interventionSite>","d2"]`, isolé du slice eMBB).

## R6 — `CFS_FieldAssist_*` / SUPERVISION : conformité SLA

- Surveiller les métriques des segments de transport (latence, BP) remontées par le NSC ;
  si violation : événement d'alarme + rappel de l'ordre de dégradation contractuel
  (`F2` d'abord, puis `F1`, puis `F6` par compression — jamais `F3` ni `F5`).

## R7 — `CFS_FieldAssist_*` / AFTER_DEACTIVATION

- Supprimer les slices de transport (DELETE /network-slices/<id> via le contrôleur de
  ressource) et désinstaller la release Helm ; archiver le journal de sessions.

> Piste expérimentale (doc 2 §3.5) : un constituant optionnel conditionnel dans **une seule**
> composite n'est pas supporté par les bundles statiques ; les règles LCM peuvent créer des
> commandes dynamiquement — à expérimenter sur l'instance installée avant de remplacer les
> deux composites par une seule.

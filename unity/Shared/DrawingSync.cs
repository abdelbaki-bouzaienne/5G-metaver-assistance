using System.Collections.Generic;
using Unity.Netcode;
using UnityEngine;
using FieldAssist.Common;

namespace FieldAssist.Shared
{
    /// <summary>
    /// Traces, surlignages et designations d'entites (US-3.3 / US-3.4 / US-3.6) :
    /// canal FIABLE ordonne (ce sont des commandes, pas des poses).
    /// Les points sont TOUJOURS en coordonnees du repere jumeau (ancre marqueur),
    /// jamais en coordonnees ecran : ils restent corrects des deux cotes (AR et VR).
    /// Propriete d'etat (ADR / divergence) : l'EXPERT est proprietaire des traces,
    /// le TECHNICIEN peut seulement les effacer/masquer chez lui.
    /// </summary>
    public class DrawingSync : NetworkBehaviour
    {
        public TwinCoordinateSpace TwinSpace;
        public LineRenderer TracePrefab;
        public float TraceLatencyBudgetMs = 100f;

        private readonly Dictionary<int, LineRenderer> _traces = new();
        private int _nextTraceId;

        // ---- cote emetteur (expert VR) -------------------------------------------
        public int BeginTrace() => _nextTraceId++;

        public void AppendTwinPoints(int traceId, Vector3[] twinPoints)
            => AppendPointsRpc(traceId, twinPoints, NetworkManager.LocalTime.Time);

        public void HighlightEntity(string entityId) => HighlightEntityRpc(entityId);
        public void ClearAll() => ClearAllRpc();

        // ---- replication fiable ---------------------------------------------------
        [Rpc(SendTo.Everyone, Delivery = RpcDelivery.Reliable)]
        private void AppendPointsRpc(int traceId, Vector3[] twinPoints, double sentAt)
        {
            float latencyMs = (float)((NetworkManager.LocalTime.Time - sentAt) * 1000.0);
            if (latencyMs > TraceLatencyBudgetMs)
                Debug.LogWarning($"Trace {traceId} : latence {latencyMs:F0} ms > budget {TraceLatencyBudgetMs} ms");

            if (!_traces.TryGetValue(traceId, out var line))
            {
                line = Instantiate(TracePrefab);
                _traces[traceId] = line;
            }
            int start = line.positionCount;
            line.positionCount = start + twinPoints.Length;
            for (int i = 0; i < twinPoints.Length; i++)
                line.SetPosition(start + i, TwinSpace.TwinPointToWorld(twinPoints[i])); // ancre monde reel cote AR
        }

        [Rpc(SendTo.Everyone, Delivery = RpcDelivery.Reliable)]
        private void HighlightEntityRpc(string entityId)
        {
            // Designation d'entite : chaque client resout entityId -> geometrie via
            // twin-service (GET /twin/clients/{id}/ports ou /entities) et surligne.
            BroadcastMessage("OnEntityHighlighted", entityId, SendMessageOptions.DontRequireReceiver);
        }

        [Rpc(SendTo.Everyone, Delivery = RpcDelivery.Reliable)]
        private void ClearAllRpc()
        {
            foreach (var line in _traces.Values) Destroy(line.gameObject);
            _traces.Clear();
        }
    }
}

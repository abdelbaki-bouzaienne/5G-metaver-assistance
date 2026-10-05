using Unity.Netcode;
using UnityEngine;
using FieldAssist.Common;

namespace FieldAssist.Shared
{
    /// <summary>
    /// Synchronisation d'avatars (flux F3) : 25 Hz, canal NON FIABLE, dernier etat gagnant
    /// (ADR 6). Position du technicien = pose de l'iPad ; tete + mains pour l'expert.
    /// Toutes les poses transitent dans le REPERE JUMEAU : chaque cote les re-projette
    /// dans son monde local via TwinCoordinateSpace.
    /// Budget : p95 < 50 ms (test US-2.6).
    /// </summary>
    public class AvatarSync : NetworkBehaviour
    {
        public ClientConfig Config;
        public TwinCoordinateSpace TwinSpace;
        public Transform HeadSource;          // camera iPad ou casque
        public Transform LeftHandSource;      // expert uniquement (peut etre nul)
        public Transform RightHandSource;
        public DegradedModeController Degraded;

        [Tooltip("En mode degrade : pointeur seul (on n'envoie plus les mains)")]
        public bool PointerOnly;

        private float _interval, _nextSend;

        private struct AvatarState : INetworkSerializable
        {
            public Vector3 HeadPos; public Quaternion HeadRot;
            public Vector3 LPos, RPos; public bool HasHands;
            public double SentAt;
            public void NetworkSerialize<T>(BufferSerializer<T> s) where T : IReaderWriter
            {
                s.SerializeValue(ref HeadPos); s.SerializeValue(ref HeadRot);
                s.SerializeValue(ref LPos); s.SerializeValue(ref RPos);
                s.SerializeValue(ref HasHands); s.SerializeValue(ref SentAt);
            }
        }

        private void Start() => _interval = 1f / Config.AvatarSyncHz;

        private void Update()
        {
            if (!IsSpawned || !IsOwner || Time.time < _nextSend) return;
            _nextSend = Time.time + _interval;

            var headTwin = TwinSpace.WorldPoseToTwin(new Pose(HeadSource.position, HeadSource.rotation));
            bool hands = !PointerOnly && LeftHandSource != null && RightHandSource != null;
            var state = new AvatarState
            {
                HeadPos = headTwin.position,
                HeadRot = headTwin.rotation,
                LPos = hands ? TwinSpace.WorldPointToTwin(LeftHandSource.position) : Vector3.zero,
                RPos = hands ? TwinSpace.WorldPointToTwin(RightHandSource.position) : Vector3.zero,
                HasHands = hands,
                SentAt = NetworkManager.LocalTime.Time,
            };
            SubmitStateRpc(state);
        }

        [Rpc(SendTo.NotOwner, Delivery = RpcDelivery.Unreliable)]
        private void SubmitStateRpc(AvatarState state)
        {
            // Dernier etat gagnant : pas de file, on ecrase.
            var worldPose = TwinSpace.TwinPoseToWorld(new Pose(state.HeadPos, state.HeadRot));
            transform.SetPositionAndRotation(worldPose.position, worldPose.rotation);

            float latencyMs = (float)((NetworkManager.LocalTime.Time - state.SentAt) * 1000.0);
            Degraded?.ReportStats(latencyMs, 0f); // les pertes sont tolerees (non fiable)
        }
    }
}

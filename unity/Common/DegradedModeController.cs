using UnityEngine;
using UnityEngine.Events;

namespace FieldAssist.Common
{
    /// <summary>
    /// Mode degrade (ADR 11 / US-X.2) : si le reseau chute, la session reste utilisable.
    /// - video -> image fixe (derniere frame recue)
    /// - avatars -> pointeur seul (on coupe mains/squelette, on garde la position)
    /// Reconnexion automatique avec reprise d'etat < 5 s.
    /// </summary>
    public class DegradedModeController : MonoBehaviour
    {
        public enum NetworkQuality { Good, Degraded, Offline }

        [Tooltip("RTT au-dela duquel on passe en degrade (ms)")]
        public float DegradedRttMs = 250f;
        [Tooltip("Pertes au-dela desquelles on passe en degrade (%)")]
        public float DegradedLossPct = 8f;
        public float OfflineTimeoutS = 3f;

        public UnityEvent OnEnterDegraded;   // VideoStream* : geler sur image fixe ; AvatarSync : pointeur seul
        public UnityEvent OnExitDegraded;
        public UnityEvent OnReconnect;       // resynchronisation de l'etat (annotations, checklist)

        public NetworkQuality Quality { get; private set; } = NetworkQuality.Good;
        private float _lastPacketTime;

        public void ReportStats(float rttMs, float lossPct)
        {
            _lastPacketTime = Time.time;
            var next = (rttMs > DegradedRttMs || lossPct > DegradedLossPct)
                ? NetworkQuality.Degraded : NetworkQuality.Good;
            Transition(next);
        }

        private void Update()
        {
            if (Quality != NetworkQuality.Offline && Time.time - _lastPacketTime > OfflineTimeoutS)
                Transition(NetworkQuality.Offline);
        }

        private void Transition(NetworkQuality next)
        {
            if (next == Quality) return;
            var prev = Quality;
            Quality = next;
            if (next != NetworkQuality.Good) OnEnterDegraded?.Invoke();
            else
            {
                OnExitDegraded?.Invoke();
                if (prev == NetworkQuality.Offline) OnReconnect?.Invoke();
            }
        }
    }
}

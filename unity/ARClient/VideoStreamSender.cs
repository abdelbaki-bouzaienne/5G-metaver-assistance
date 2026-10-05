using System.Collections;
using Unity.WebRTC;
using UnityEngine;
using FieldAssist.Common;
using FieldAssist.Shared;

namespace FieldAssist.AR
{
    /// <summary>
    /// Flux video RGB iPad -> expert (flux F6, US-3.1) via Unity WebRTC :
    /// H.264 720p/30, debit adaptatif 3-8 Mbit/s, latence cible < 200 ms.
    /// ICE : STUN + TURN (identifiants ephemeres de session-service) ; repli TCP/443.
    /// La signalisation (SDP/ICE) passe par le WebSocket /signaling/ws/{session}.
    /// En mode degrade : on gele sur image fixe (DegradedModeController).
    /// </summary>
    public class VideoStreamSender : MonoBehaviour
    {
        public SessionNetworkManager Session;
        public DegradedModeController Degraded;
        public Camera SourceCamera;
        public int Width = 1280, Height = 720, Fps = 30;
        public uint MinBitrateKbps = 500, MaxBitrateKbps = 8000;

        private RTCPeerConnection _pc;
        private VideoStreamTrack _track;

        public void StartStreaming()
        {
            var cfg = new RTCConfiguration
            {
                iceServers = new[]
                {
                    new RTCIceServer
                    {
                        urls = Session.Turn.uris,
                        username = Session.Turn.username,
                        credential = Session.Turn.credential,
                    }
                }
            };
            _pc = new RTCPeerConnection(ref cfg);
            _track = SourceCamera.CaptureStreamTrack(Width, Height);
            var sender = _pc.AddTrack(_track);

            // Adaptation de debit (ADR : le codec absorbe la contention avant F3/F5)
            var p = sender.GetParameters();
            foreach (var enc in p.encodings)
            {
                enc.minBitrate = MinBitrateKbps * 1000;
                enc.maxBitrate = MaxBitrateKbps * 1000;
                enc.maxFramerate = (uint)Fps;
            }
            sender.SetParameters(p);

            Degraded.OnEnterDegraded.AddListener(() => _track.Enabled = false); // image fixe cote recepteur
            Degraded.OnExitDegraded.AddListener(() => _track.Enabled = true);

            StartCoroutine(Negotiate());
            StartCoroutine(MonitorStats());
        }

        private IEnumerator Negotiate()
        {
            var offer = _pc.CreateOffer();
            yield return offer;
            var desc = offer.Desc;
            yield return _pc.SetLocalDescription(ref desc);
            // Envoyer desc.sdp sur Session.SignalingWsUrl ({"type":"offer","sdp":...}),
            // attendre {"type":"answer"} et appeler SetRemoteDescription.
            // Les candidats ICE partent/arrivent par le meme canal.
        }

        private IEnumerator MonitorStats()
        {
            while (_pc != null)
            {
                var op = _pc.GetStats();
                yield return op;
                foreach (var stat in op.Value.Stats.Values)
                    if (stat is RTCIceCandidatePairStats pair && pair.nominated)
                        Degraded.ReportStats((float)(pair.currentRoundTripTime * 1000.0), 0f);
                yield return new WaitForSeconds(2f);
            }
        }

        private void OnDestroy() { _track?.Dispose(); _pc?.Close(); }
    }
}

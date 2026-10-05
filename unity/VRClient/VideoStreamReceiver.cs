using Unity.WebRTC;
using UnityEngine;
using UnityEngine.UI;
using FieldAssist.Common;
using FieldAssist.Shared;

namespace FieldAssist.VR
{
    /// <summary>
    /// Reception du flux camera du technicien dans le casque (US-3.1) :
    /// panneau video dans la scene VR, a cote du jumeau 3DGS.
    /// Mode degrade : on conserve la DERNIERE IMAGE (image fixe) au lieu d'un ecran noir.
    /// </summary>
    public class VideoStreamReceiver : MonoBehaviour
    {
        public SessionNetworkManager Session;
        public DegradedModeController Degraded;
        public RawImage VideoPanel;

        private RTCPeerConnection _pc;
        private Texture _lastFrame;

        public void StartReceiving()
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
            _pc.OnTrack = e =>
            {
                if (e.Track is VideoStreamTrack video)
                    video.OnVideoReceived += tex =>
                    {
                        _lastFrame = tex;
                        if (Degraded.Quality == DegradedModeController.NetworkQuality.Good)
                            VideoPanel.texture = tex;
                        // sinon : on garde l'image fixe affichee (mode degrade)
                    };
            };
            // Signalisation : repondre a l'offer recue sur Session.SignalingWsUrl
            // (SetRemoteDescription -> CreateAnswer -> SetLocalDescription -> envoyer).
        }

        private void OnDestroy() => _pc?.Close();
    }
}

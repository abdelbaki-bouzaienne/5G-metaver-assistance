using System;
using System.Collections;
using UnityEngine;
using Unity.Netcode;
using Unity.Netcode.Transports.UTP;
using FieldAssist.Common;

namespace FieldAssist.Shared
{
    /// <summary>
    /// Jointure de session (US-2.4) : appelle session-service, recoit les jetons TURN
    /// (pour WebRTC) et l'URL du signaling, puis etablit Netcode en P2P direct ;
    /// repli Unity Relay si le P2P echoue (US-X.1 - TURN reste le premier choix, ADR 7).
    /// </summary>
    public class SessionNetworkManager : MonoBehaviour
    {
        public ApiClient Api;
        public string Role = "T"; // T technicien / E expert
        public string User = "user";
        public string Device = "device";

        public string SessionId { get; private set; }
        public TurnInfo Turn { get; private set; }
        public string SignalingWsUrl { get; private set; }

        public event Action OnSessionJoined;

        public IEnumerator CreateSession(string siteId, string twinVersionId)
        {
            string body = JsonUtility.ToJson(new CreateReq
            { site_id = siteId, twin_version_id = twinVersionId, user = User, role = Role, device = Device });
            yield return Api.PostJson("/session/sessions", body, HandleJoinResponse);
        }

        public IEnumerator JoinSession(string sessionId)
        {
            string body = JsonUtility.ToJson(new JoinReq { user = User, role = Role, device = Device });
            yield return Api.PostJson($"/session/sessions/{sessionId}/join", body, HandleJoinResponse);
        }

        private void HandleJoinResponse(long code, string resp)
        {
            if (code != 200 && code != 201) { Debug.LogError($"Session: échec ({code})"); return; }
            var data = JsonUtility.FromJson<JoinResp>(resp);
            SessionId = data.id;
            Turn = data.turn;
            SignalingWsUrl = Api.Config.GatewayBaseUrl.Replace("http", "ws") + data.signaling_ws;

            // Netcode : l'expert (E) heberge, le technicien se connecte (P2P direct).
            var nm = NetworkManager.Singleton;
            var utp = nm.GetComponent<UnityTransport>();
            if (Role == "E") nm.StartHost();
            else nm.StartClient();
            // En cas d'echec P2P : basculer utp sur Unity Relay (allocation cote session-service).

            OnSessionJoined?.Invoke();
        }

        [Serializable] public class TurnInfo { public string[] uris; public string username; public string credential; public int ttl; }
        [Serializable] private class CreateReq { public string site_id, twin_version_id, user, role, device; }
        [Serializable] private class JoinReq { public string user, role, device; }
        [Serializable] private class JoinResp { public string id; public TurnInfo turn; public string signaling_ws; }
    }
}

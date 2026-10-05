using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace FieldAssist.Common
{
    /// <summary>Client REST vers le gateway edge (plan metier). Porte le jeton OIDC.</summary>
    public class ApiClient : MonoBehaviour
    {
        public ClientConfig Config;
        [NonSerialized] public string AccessToken; // obtenu via le flux OIDC device/PKCE

        public IEnumerator Get(string path, Action<long, string> onDone)
            => Send(UnityWebRequest.Get(Config.GatewayBaseUrl + path), onDone);

        public IEnumerator PostJson(string path, string json, Action<long, string> onDone)
        {
            var req = new UnityWebRequest(Config.GatewayBaseUrl + path, "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
                downloadHandler = new DownloadHandlerBuffer()
            };
            req.SetRequestHeader("Content-Type", "application/json");
            return Send(req, onDone);
        }

        public IEnumerator PatchJson(string path, string json, Action<long, string> onDone)
        {
            var req = new UnityWebRequest(Config.GatewayBaseUrl + path, "PATCH")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
                downloadHandler = new DownloadHandlerBuffer()
            };
            req.SetRequestHeader("Content-Type", "application/json");
            return Send(req, onDone);
        }

        private IEnumerator Send(UnityWebRequest req, Action<long, string> onDone)
        {
            if (!string.IsNullOrEmpty(AccessToken))
                req.SetRequestHeader("Authorization", "Bearer " + AccessToken);
            yield return req.SendWebRequest();
            onDone?.Invoke(req.responseCode, req.downloadHandler?.text);
            req.Dispose();
        }
    }
}

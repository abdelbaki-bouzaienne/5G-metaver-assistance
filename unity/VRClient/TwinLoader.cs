using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using FieldAssist.Common;

namespace FieldAssist.VR
{
    /// <summary>
    /// Chargement du jumeau 3DGS cote expert (flux F2, US-2.5) :
    /// - PRECHARGEMENT hors session + cache disque (la cible "10 Gbit/s" est requalifiee :
    ///   on ne charge pas au moment de l'appel) ;
    /// - affichage progressif par LOD (grossier d'abord), budget de gaussiennes par profil
    ///   d'appareil (Quest vs PC) ;
    /// - objectif applicatif : timeToFirstUsableTwin < 30 s sur 5G.
    /// Le rendu du splat lui-meme s'appuie sur un plugin gaussian splatting Unity
    /// (ex. aras-p/UnityGaussianSplatting) alimente par les fichiers du cache.
    /// </summary>
    public class TwinLoader : MonoBehaviour
    {
        public ApiClient Api;
        public int DeviceGaussianBudget = 1_500_000; // profil Quest
        public event System.Action<int> OnLodReady;  // lod charge (2 = grossier, 0 = fin)

        private string CacheDir => Path.Combine(Application.persistentDataPath, "twin-cache");

        public IEnumerator PreloadVersion(string versionId)
        {
            Directory.CreateDirectory(CacheDir);
            List<Asset> assets = null;
            yield return Api.Get($"/twin/twin-versions/{versionId}/assets", (code, resp) =>
            {
                if (code == 200)
                    assets = new List<Asset>(JsonUtility.FromJson<AssetList>("{\"items\":" + resp + "}").items);
            });
            if (assets == null) yield break;

            // LOD grossier -> fin : premier affichage rapide, raffinement ensuite
            assets.Sort((a, b) => b.lod.CompareTo(a.lod));
            foreach (var asset in assets)
            {
                string local = Path.Combine(CacheDir, $"{versionId}_{asset.asset_type}_lod{asset.lod}");
                if (!File.Exists(local))
                {
                    // En production : URL S3 signee courte duree fournie par l'API
                    using var req = UnityWebRequest.Get(ResolveUri(asset.uri));
                    req.downloadHandler = new DownloadHandlerFile(local);
                    yield return req.SendWebRequest();
                    if (req.result != UnityWebRequest.Result.Success) { Debug.LogError(req.error); continue; }
                }
                if (asset.asset_type == "tile" || asset.asset_type == "splat")
                    OnLodReady?.Invoke(asset.lod); // le renderer splat consomme le fichier du cache
            }
        }

        private string ResolveUri(string uri)
            => uri.StartsWith("s3://")
                ? Api.Config.GatewayBaseUrl + "/assets/" + uri.Substring("s3://".Length)
                : uri;

        [System.Serializable] public class Asset { public string asset_type; public int lod; public string uri; public long size_bytes; }
        [System.Serializable] private class AssetList { public Asset[] items; }
    }
}

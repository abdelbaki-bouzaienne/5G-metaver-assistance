using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;
using FieldAssist.Common;

namespace FieldAssist.Scan
{
    /// <summary>
    /// Upload fragmente et reprenable (US-1.3 / ADR 4) : chunks + SHA-256, reprise
    /// automatique apres coupure (Wifi/5G instables), progression visible.
    /// </summary>
    public class ChunkedUploader : MonoBehaviour
    {
        public ApiClient Api;
        public int ChunkSizeBytes = 4 * 1024 * 1024;
        public int MaxRetriesPerChunk = 5;

        public event Action<float> OnProgress;          // 0..1
        public event Action<string> OnCompleted;        // scanId
        public event Action<string> OnFailed;

        public IEnumerator Upload(string filePath, string siteId, bool markerDetected, float[] transformMarker)
        {
            var total = (int)Mathf.Ceil((float)new FileInfo(filePath).Length / ChunkSizeBytes);
            string scanId = null;

            var body = JsonUtility.ToJson(new ScanCreate
            { site_id = siteId, marker_detected = markerDetected, total_chunks = total });
            yield return Api.PostJson("/ingest/scans", body, (code, resp) =>
            {
                if (code == 201) scanId = JsonUtility.FromJson<ScanCreated>(resp).id;
                else OnFailed?.Invoke(code == 422
                    ? "Marqueur non détecté : repositionnez-vous face au marqueur (échelle requise)."
                    : $"Création du scan refusée ({code})");
            });
            if (scanId == null) yield break;

            using var stream = File.OpenRead(filePath);
            var buffer = new byte[ChunkSizeBytes];
            for (int n = 0; n < total; n++)
            {
                int read = stream.Read(buffer, 0, ChunkSizeBytes);
                var chunk = new byte[read];
                Array.Copy(buffer, chunk, read);
                string sha = Sha256Hex(chunk);

                bool ok = false;
                for (int attempt = 0; attempt <= MaxRetriesPerChunk && !ok; attempt++)
                {
                    yield return PutChunk(scanId, n, chunk, sha, success => ok = success);
                    if (!ok) yield return new WaitForSeconds(Mathf.Pow(2, attempt)); // backoff
                }
                if (!ok) { OnFailed?.Invoke($"Chunk {n} : échec après reprises"); yield break; }
                OnProgress?.Invoke((n + 1f) / total);
            }

            yield return Api.PostJson($"/ingest/scans/{scanId}/complete", "{}", (code, _) =>
            {
                if (code == 200) OnCompleted?.Invoke(scanId);
                else OnFailed?.Invoke($"Complétion refusée ({code}) : chunks manquants ?");
            });
        }

        private IEnumerator PutChunk(string scanId, int n, byte[] data, string sha, Action<bool> done)
        {
            var req = new UnityWebRequest($"{Api.Config.GatewayBaseUrl}/ingest/scans/{scanId}/chunks/{n}", "PUT")
            {
                uploadHandler = new UploadHandlerRaw(data),
                downloadHandler = new DownloadHandlerBuffer()
            };
            req.SetRequestHeader("X-Chunk-Sha256", sha);
            yield return req.SendWebRequest();
            done(req.responseCode == 200);
            req.Dispose();
        }

        private static string Sha256Hex(byte[] data)
        {
            using var sha = SHA256.Create();
            return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] private class ScanCreate { public string site_id; public bool marker_detected; public int total_chunks; }
        [Serializable] private class ScanCreated { public string id; }
    }
}

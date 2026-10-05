using System.Collections;
using UnityEngine;
using FieldAssist.Common;
using FieldAssist.Shared;

namespace FieldAssist.VR
{
    /// <summary>
    /// Cote expert : designation d'entites et scenarios metier (US-3.4, US-3.7 a 3.9).
    /// L'idee cle : le CLIENT ou le CABLE est une entite du modele de donnees ;
    /// le systeme met automatiquement en evidence les DEUX positions (panneau gauche
    /// + droit). Le trace manuel ne sert que pour le cheminement libre en zone centrale.
    /// </summary>
    public class EntityHighlighter : MonoBehaviour
    {
        public ApiClient Api;
        public DrawingSync Drawing;

        /// <summary>Conformite client (US-3.8) : selectionner un client -> ses ports
        /// sont surlignes chez les deux participants.</summary>
        public void SelectClient(string clientId)
            => Drawing.HighlightEntity(clientId);

        /// <summary>Cablage (US-3.9) : cree le cable (2 extremites auto-surlignees),
        /// puis l'expert trace le cheminement central ; le chemin valide est persiste.</summary>
        public IEnumerator StartCabling(string portLeftId, string portRightId)
        {
            string cableId = null;
            string body = $"{{\"port_left_id\":\"{portLeftId}\",\"port_right_id\":\"{portRightId}\"}}";
            yield return Api.PostJson("/twin/cables", body, (code, resp) =>
            {
                if (code == 201) cableId = JsonUtility.FromJson<IdResp>(resp).id;
            });
            if (cableId == null) yield break;

            Drawing.HighlightEntity(portLeftId);
            Drawing.HighlightEntity(portRightId);
            _activeCable = cableId;
            _activeTrace = Drawing.BeginTrace();
        }

        private string _activeCable;
        private int _activeTrace = -1;
        private readonly System.Collections.Generic.List<Vector3> _path = new();

        /// <summary>Points du controleur VR, deja convertis en repere jumeau.</summary>
        public void AppendPathPoint(Vector3 twinPoint)
        {
            if (_activeTrace < 0) return;
            _path.Add(twinPoint);
            Drawing.AppendTwinPoints(_activeTrace, new[] { twinPoint });
        }

        public IEnumerator ValidateCablePath()
        {
            if (_activeCable == null) yield break;
            var sb = new System.Text.StringBuilder("{\"path\":[");
            for (int i = 0; i < _path.Count; i++)
                sb.Append(i > 0 ? "," : "").Append($"[{_path[i].x:F3},{_path[i].y:F3},{_path[i].z:F3}]");
            sb.Append("],\"status\":\"installed\"}");
            yield return Api.PatchJson($"/twin/cables/{_activeCable}", sb.ToString(), null);
            _activeCable = null; _activeTrace = -1; _path.Clear();
        }

        [System.Serializable] private class IdResp { public string id; }
    }
}

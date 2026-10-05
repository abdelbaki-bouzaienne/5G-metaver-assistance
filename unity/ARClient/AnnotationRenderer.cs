using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using FieldAssist.Common;

namespace FieldAssist.AR
{
    /// <summary>
    /// Affichage AR des indications de l'expert, ANCREES DANS LE MONDE REEL (US-3.3) :
    /// surlignages d'entites (ports/panneaux resolus via twin-service) et traces.
    /// Le technicien peut tout effacer/masquer pour degager son champ visuel (US-3.6).
    /// Le splat n'est PAS affiche cote AR : le technicien voit le reel.
    /// </summary>
    public class AnnotationRenderer : MonoBehaviour
    {
        public ApiClient Api;
        public TwinCoordinateSpace TwinSpace;
        public GameObject HighlightBoxPrefab;   // boite translucide
        public GameObject HighlightPointPrefab; // halo de port

        private readonly List<GameObject> _spawned = new();
        private bool _hidden;

        /// <summary>Recu via DrawingSync.HighlightEntityRpc.</summary>
        public void OnEntityHighlighted(string entityId)
            => StartCoroutine(ResolveAndShow(entityId));

        private IEnumerator ResolveAndShow(string entityId)
        {
            yield return Api.Get($"/twin/clients/{entityId}/ports", (code, resp) =>
            {
                if (code == 200) { foreach (var g in ParsePortGeometries(resp)) Spawn(g); }
                else StartCoroutine(ShowSingleEntity(entityId));
            });
        }

        private IEnumerator ShowSingleEntity(string entityId)
        {
            // entite simple : geometrie box/point en repere jumeau
            yield return Api.Get($"/twin/entities/{entityId}", (code, resp) =>
            {
                if (code == 200) Spawn(JsonUtility.FromJson<Geometry>(resp));
            });
        }

        private void Spawn(Geometry g)
        {
            var prefab = g.kind == "box" ? HighlightBoxPrefab : HighlightPointPrefab;
            var pos = g.kind == "box" ? ToV3(g.center) : ToV3(g.position);
            var obj = Instantiate(prefab, TwinSpace.TwinPointToWorld(pos), Quaternion.identity);
            if (g.kind == "box" && g.size != null) obj.transform.localScale = ToV3(g.size);
            obj.SetActive(!_hidden);
            _spawned.Add(obj);
        }

        public void ToggleHidden()
        {
            _hidden = !_hidden;
            foreach (var o in _spawned) o.SetActive(!_hidden);
        }

        public void ClearAll()
        {
            foreach (var o in _spawned) Destroy(o);
            _spawned.Clear();
        }

        private static Vector3 ToV3(float[] a) => new(a[0], a[1], a[2]);

        private IEnumerable<Geometry> ParsePortGeometries(string json)
        {
            // Les ports renvoient panel_geometry (position du client sur panneaux G+D)
            var wrapper = JsonUtility.FromJson<PortList>("{\"items\":" + json + "}");
            foreach (var p in wrapper.items) yield return p.panel_geometry;
        }

        [System.Serializable] public class Geometry { public string kind; public float[] center; public float[] position; public float[] size; }
        [System.Serializable] private class PortEntry { public Geometry panel_geometry; }
        [System.Serializable] private class PortList { public PortEntry[] items; }
    }
}

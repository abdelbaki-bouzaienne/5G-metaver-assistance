using System.Collections.Generic;
using UnityEngine;
using FieldAssist.Common;

namespace FieldAssist.Scan
{
    /// <summary>
    /// Capture guidee (US-1.1 / US-1.2) : indicateur de couverture en direct, alerte si
    /// mouvement trop rapide ou flou, refus si le marqueur n'est pas detecte.
    /// La detection du marqueur vient d'AR Foundation (ARTrackedImageManager) ;
    /// l'app enregistre la transformation marqueur -> premiere camera avec le scan.
    /// </summary>
    public class ScanCaptureController : MonoBehaviour
    {
        public ClientConfig Config;
        public TwinCoordinateSpace TwinSpace;
        public ChunkedUploader Uploader;

        [Tooltip("Vitesse angulaire max (deg/s) avant alerte 'trop rapide'")]
        public float MaxAngularSpeed = 60f;
        [Tooltip("Nombre de cellules de couverture (grille autour de la baie)")]
        public int CoverageCells = 32;

        public bool MarkerDetected { get; private set; }
        public float Coverage => (float)_coveredCells.Count / CoverageCells;
        public bool MovingTooFast { get; private set; }

        private readonly HashSet<int> _coveredCells = new();
        private Quaternion _lastRot;
        private readonly List<string> _capturedFrames = new();

        public void OnMarkerTracked(Pose markerWorldPose, float observedSizeM, float confidence)
        {
            MarkerDetected = true;
            TwinSpace.SetFromMarker(markerWorldPose, Config.MarkerSizeMm, observedSizeM, confidence);
        }

        private void Update()
        {
            var cam = Camera.main.transform;
            MovingTooFast = Quaternion.Angle(_lastRot, cam.rotation) / Time.deltaTime > MaxAngularSpeed;
            _lastRot = cam.rotation;

            if (!MovingTooFast && MarkerDetected)
            {
                // cellule de couverture = direction camera quantifiee autour du jumeau
                var dirTwin = TwinSpace.WorldToTwin.MultiplyVector(cam.forward);
                int cell = CellIndex(dirTwin);
                _coveredCells.Add(cell);
            }
        }

        private int CellIndex(Vector3 dir)
        {
            float az = Mathf.Atan2(dir.z, dir.x) + Mathf.PI;         // 0..2pi
            float el = Mathf.Clamp01((dir.y + 1f) * 0.5f);           // 0..1
            int azi = Mathf.Min(7, (int)(az / (2 * Mathf.PI) * 8));
            int eli = Mathf.Min(3, (int)(el * 4));
            return eli * 8 + azi;
        }

        /// <summary>Fin de capture : upload uniquement si le marqueur a ete vu (sinon le
        /// backend refusera aussi, defense en profondeur).</summary>
        public void FinishAndUpload(string recordedFilePath)
        {
            if (!MarkerDetected)
            {
                Debug.LogWarning("Scan refusé : marqueur non détecté (échelle/origine requises).");
                return;
            }
            StartCoroutine(Uploader.Upload(recordedFilePath, Config.SiteId, true, null));
        }
    }
}

using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using FieldAssist.Common;

namespace FieldAssist.AR
{
    /// <summary>
    /// Relocalisation par marqueur sur iPad (US-2.1 / US-2.2) : ARKit suit l'image de
    /// reference (taille physique connue) ; on en derive monde ARKit -> repere jumeau.
    /// Re-relocalisation reguliere contre la derive VIO + bouton "recaler" + indicateur
    /// de confiance. Objectif : < 5 s, erreur < 1-2 cm au panneau.
    /// </summary>
    [RequireComponent(typeof(ARTrackedImageManager))]
    public class MarkerRelocalization : MonoBehaviour
    {
        public ClientConfig Config;
        public TwinCoordinateSpace TwinSpace;
        public event System.Action<float> OnRelocalized; // confiance 0..1

        private ARTrackedImageManager _manager;

        private void Awake() => _manager = GetComponent<ARTrackedImageManager>();
        private void OnEnable() => _manager.trackedImagesChanged += OnChanged;
        private void OnDisable() => _manager.trackedImagesChanged -= OnChanged;

        private void OnChanged(ARTrackedImagesChangedEventArgs args)
        {
            foreach (var img in args.added) TryRelocalize(img);
            foreach (var img in args.updated) TryRelocalize(img);
        }

        private void TryRelocalize(ARTrackedImage img)
        {
            if (img.referenceImage.name != Config.MarkerId) return;
            if (img.trackingState != TrackingState.Tracking) return;

            float confidence = img.trackingState == TrackingState.Tracking ? 1f : 0.5f;
            TwinSpace.SetFromMarker(
                new Pose(img.transform.position, img.transform.rotation),
                Config.MarkerSizeMm,
                img.size.x,              // taille observee -> controle d'echelle
                confidence);
            OnRelocalized?.Invoke(TwinSpace.Confidence);
        }

        /// <summary>Bouton "recaler" (US-2.2) : force une nouvelle recherche du marqueur.</summary>
        public void ForceRelocalize()
        {
            _manager.enabled = false;
            _manager.enabled = true;
        }
    }
}

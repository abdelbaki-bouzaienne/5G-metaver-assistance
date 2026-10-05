using UnityEngine;

namespace FieldAssist.Common
{
    /// <summary>
    /// Repere unique du jumeau, ancre sur le marqueur image (ADR 2).
    /// Toutes les donnees echangees (poses, traces, surlignages) passent par ces
    /// conversions : jamais de coordonnees ecran ni de monde ARKit/OpenXR brut.
    /// </summary>
    public class TwinCoordinateSpace : MonoBehaviour
    {
        /// <summary>Transformation monde local (ARKit/OpenXR) -> repere jumeau,
        /// mise a jour a chaque relocalisation sur le marqueur.</summary>
        public Matrix4x4 WorldToTwin { get; private set; } = Matrix4x4.identity;
        public Matrix4x4 TwinToWorld { get; private set; } = Matrix4x4.identity;

        /// <summary>Qualite de la derniere relocalisation (0..1) ; en dessous de
        /// MinConfidence, l'UI demande un recalage (US-2.2).</summary>
        public float Confidence { get; private set; }
        public float MinConfidence = 0.7f;
        public System.DateTime LastRelocalization { get; private set; }

        public bool NeedsRelocalization =>
            Confidence < MinConfidence ||
            (System.DateTime.UtcNow - LastRelocalization).TotalSeconds > 120; // derive VIO

        /// <summary>Appele par MarkerRelocalization quand le marqueur est detecte.</summary>
        public void SetFromMarker(Pose markerWorldPose, float markerSizeMm, float observedSizeM, float confidence)
        {
            // Le marqueur definit l'origine et l'orientation du repere jumeau ;
            // sa taille physique connue valide l'echelle (le 3DGS n'a pas d'echelle native).
            var twinOriginWorld = Matrix4x4.TRS(markerWorldPose.position, markerWorldPose.rotation, Vector3.one);
            TwinToWorld = twinOriginWorld;
            WorldToTwin = twinOriginWorld.inverse;
            Confidence = confidence * ScaleAgreement(markerSizeMm / 1000f, observedSizeM);
            LastRelocalization = System.DateTime.UtcNow;
        }

        private static float ScaleAgreement(float expectedM, float observedM)
            => Mathf.Clamp01(1f - Mathf.Abs(expectedM - observedM) / expectedM * 10f);

        public Vector3 WorldPointToTwin(Vector3 world) => WorldToTwin.MultiplyPoint3x4(world);
        public Vector3 TwinPointToWorld(Vector3 twin) => TwinToWorld.MultiplyPoint3x4(twin);

        public Pose WorldPoseToTwin(Pose p) => new Pose(
            WorldToTwin.MultiplyPoint3x4(p.position),
            WorldToTwin.rotation * p.rotation);

        public Pose TwinPoseToWorld(Pose p) => new Pose(
            TwinToWorld.MultiplyPoint3x4(p.position),
            TwinToWorld.rotation * p.rotation);
    }
}

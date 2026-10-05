using UnityEngine;

namespace FieldAssist.Common
{
    /// <summary>Configuration des clients (Scan / AR / VR). Un seul endpoint : le gateway edge.</summary>
    [CreateAssetMenu(menuName = "FieldAssist/ClientConfig")]
    public class ClientConfig : ScriptableObject
    {
        [Header("Plateforme edge (MEC)")]
        public string GatewayBaseUrl = "http://10.0.6.20:8000";

        [Header("OIDC (fournisseur unique pour les trois apps)")]
        public string OidcAuthority = "https://keycloak.example.lan/realms/fieldassist";
        public string OidcClientId = "fieldassist-client";

        [Header("Site / marqueur")]
        public string SiteId = "";
        public string MarkerId = "MK-01";
        [Tooltip("Taille physique du bord du marqueur (mm) : donne l'echelle metrique du jumeau")]
        public float MarkerSizeMm = 150f;

        [Header("Temps reel")]
        [Tooltip("Frequence d'envoi des poses (Hz) - canal non fiable, dernier etat gagnant")]
        public float AvatarSyncHz = 25f;
        [Tooltip("Budget latence tracés (ms) - au-dela, alerte qualite")]
        public float TraceLatencyBudgetMs = 100f;
    }
}

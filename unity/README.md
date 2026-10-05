# Clients Unity — Scan, AR (iPad Pro), VR (Quest)

Squelettes C# des trois applications (V1 : Quest uniquement côté VR, RGB seul — extensions
Vision Pro / Galaxy XR / RGB-D ensuite). À importer dans trois projets Unity 2022.3 LTS+.

## Packages requis (Package Manager)

| Package | Apps | Usage |
|---|---|---|
| `com.unity.netcode.gameobjects` (≥ 1.8) | AR, VR | Synchro avatars/tracés (UDP, UnityTransport) |
| `com.unity.webrtc` (≥ 3.0) | AR, VR | Vidéo H.264 720p30 adaptative (AR → VR) |
| `com.unity.xr.arfoundation` + ARKit | Scan, AR | Suivi VIO/LiDAR, détection du marqueur image |
| `com.unity.xr.openxr` | VR | Quest (profils Meta Quest Support) |
| `com.unity.services.relay` (option) | AR, VR | Repli Unity Relay si TURN indisponible |

## Arborescence

```
Common/    ClientConfig, ApiClient (REST+OIDC), TwinCoordinateSpace, DegradedModeController
ScanApp/   ScanCaptureController (guidage, refus sans marqueur), ChunkedUploader (SHA-256, reprise)
ARClient/  MarkerRelocalization (recalage + confiance), AnnotationRenderer (ancrage monde réel),
           VideoStreamSender (WebRTC, adaptation de débit)
VRClient/  TwinLoader (tuiles/LOD, préchargement+cache), EntityHighlighter (désignation port/client),
           VideoStreamReceiver
Shared/    AvatarSync (25 Hz non fiable, dernier état gagnant), DrawingSync (tracés fiables,
           repère jumeau), SessionNetworkManager (jointure via session-service, P2P→Relay)
```

## Règles d'or (issues des ADR)

1. **Toutes** les coordonnées échangées (poses, tracés, surlignages) sont dans le **repère
   jumeau** (origine marqueur) — jamais en coordonnées écran ni monde ARKit brut.
2. Poses : canal **non fiable**, dernier état gagnant, 25 Hz. Commandes (désignation,
   effacement, checklist) : canal **fiable ordonné**.
3. Vidéo : WebRTC uniquement, débit adaptatif ; en dégradé → image fixe + pointeur seul.
4. Le splat n'est **pas affiché côté AR** (le technicien voit le réel) ; il est réservé à
   l'expert VR, en tuiles/LOD préchargées.
5. La session continue si le cloud tombe (P2P établi) ; resynchronisation à la reprise.

## Configuration

Renseigner `Common/ClientConfig.cs` : URL du gateway edge (`http://<IP_N6>:8000`),
realm OIDC, identifiant du site. Les jetons TURN et l'URL du signaling sont fournis
dynamiquement par `session-service` à la jointure.

# Bip — « L'argent est déjà chez toi » (vidéo 9:16)

**Vidéo finale :** `bip_argent_placard.mp4` (1080×1920, 30 fps, ~52 s, H.264 + AAC).

Tout est généré par code :

| Fichier | Rôle |
|---|---|
| `build_audio.py` | Voix FR (espeak-ng + MBROLA `fr1`, pitch +7 %, effet métallique discret), musique funky électro synthétisée, bruitages (bip, ding, cha-ching, boing, déclencheur photo…), ducking musique sous la voix, timeline partagée → `build/audio.wav`, `build/timeline.js` |
| `bip.html` | Animation (personnage Bip, 11 scènes, caméra, sous-titres blancs bordés de noir + mots-clés en jaune). Ouvrir dans un navigateur pour un aperçu avec le son. |
| `render.js` | Rendu image par image via Playwright + ffmpeg → MP4 |

## Régénérer
```bash
sudo apt-get install -y espeak-ng mbrola mbrola-fr1 ffmpeg
pip install numpy scipy
python3 build_audio.py      # audio + timeline
node render.js              # vidéo (≈ 4 min)
node render.js --stills 2,15,36   # captures de contrôle
```
Pour modifier une réplique : éditer `SCENES` dans `build_audio.py` (`|` = pause comique, `*mot*` = mot-clé jaune), relancer les deux commandes — l'animation se recale automatiquement.

# Vidéo verticale : « Et si les humains étaient tous devenus un animal ? »

Vidéo de 65 s au format 9:16 (1080x1920, 30 i/s), avec narration française, sous-titres
dynamiques mot par mot et 10 plans (24 sous-plans, une coupe toutes les 2 à 3 s).

- `out/et_si_animaux_1080x1920.mp4` : la vidéo finale (version animatique)
- `out/subtitles.srt` / `out/subtitles.ass` : les sous-titres
- `PROMPTS.md` : les prompts IA de chaque plan, le texte de la voix off et la feuille des sons

## Régénérer

```bash
sudo apt-get install -y ffmpeg espeak-ng mbrola mbrola-fr1
pip install numpy pillow
python3 src/make_video.py            # tout le pipeline (~5 min sur 4 cœurs)
python3 src/make_video.py mux        # réassemblage seul (après ajout de rushes)
```

## Remplacer par de vrais rushes ou une vraie voix

- `clips/plan01.mp4` … `clips/plan10.mp4` : un rush par plan, recadré automatiquement en 9:16.
- `voice/line01.wav` … `voice/line19.wav` : une réplique par fichier, recalée automatiquement.
  Les sous-titres sont alors recalculés (relancer tout le pipeline).

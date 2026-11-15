# Fabrication de `video_finale.mp4`

```bash
pip install edge-tts piper-tts onnx pycairo pillow numpy   # + ffmpeg installé
cd video
python voix.py        # voix + timings mot par mot  (edge-tts si dispo, sinon Piper)
python render.py      # animation + sous-titres + bruitages -> ../video_finale.mp4
```

- `python voix.py edge` force edge-tts (voix Microsoft, WordBoundary), `python voix.py piper` force Piper (hors-ligne).
- `python render.py --stills 1.5 20 40` exporte des images de contrôle dans `build/stills/`.
- Les répliques, pauses et réglages de voix sont dans `scenario_data.py` : tout le reste (animation, caméra,
  sous-titres) se recale automatiquement sur la durée réelle des voix.

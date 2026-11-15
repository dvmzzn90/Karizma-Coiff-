# Doublage voix des Shorts

Voix neuronales françaises **hors ligne** (Piper), synchro labiale automatique et musique qui baisse sous les voix.

## Installation
```bash
pip install piper-tts numpy pillow
mkdir -p voice/models && cd voice/models
for m in vits-piper-fr_FR-siwis-medium vits-piper-fr_FR-tom-medium vits-piper-fr_FR-upmc-medium; do
  curl -L -o $m.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$m.tar.bz2
  tar xjf $m.tar.bz2 && rm $m.tar.bz2
done
```
(Les modèles font ~60 Mo chacun : ils ne sont pas commités.)

## Rendu
```bash
python3 voice/dub.py 1   # -> short/karizma_short_voix.mp4
python3 voice/dub.py 2   # -> short2/salle_de_sport_short_voix.mp4
```

## Casting (modifiable dans `CAST` de `dub.py` : voix, vitesse, hauteur)
| Personnage | Voix |
|---|---|
| Narrateur Short 1 | upmc « pierre » |
| Théo, Malik, narrateur Short 2 | tom (hauteur ajustée) |
| Karim, Tony | upmc « pierre », grave |
| Inès | siwis |
| Sarah | upmc « jessica » |

Les répliques se modifient dans `CUES` ; chaque scène s'allonge automatiquement pour laisser la phrase se terminer.

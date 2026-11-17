# 7 jours sans électricité — vidéo TikTok (60 s, 9:16)

- `7-jours-sans-electricite.mp4` : la vidéo finale (1080×1920, 30 i/s, 60 s, H.264 + AAC).
- `images/` : les 15 illustrations du stickman utilisées.
- `render.py` : animation (mouvements de caméra, fondus, flash de coupure, éclair, sous-titres).
- `audio.py` : musique et bruitages générés (bourdonnement, coupure, foule, sirène, klaxons, pas, bip de caisse, vent, tonnerre, tic-tac, montée, retour du courant, impacts de fin).

Reconstruire :

```bash
pip install numpy scipy pillow
python3 audio.py audio.wav
python3 render.py audio.wav 7-jours-sans-electricite.mp4
```

## Voix off à enregistrer (pas incluse dans la vidéo)

| Temps | Image | Texte |
|---|---|---|
| 0–5 s | Ville illuminée → stickman qui joue | Et si demain… toute l'électricité du monde disparaissait pendant sept jours ? |
| 5–11 s | Stickman choqué → la ville s'éteint (20:00:00 → 20:00:10) | À vingt heures précises, tout s'éteint. Les télés, les téléphones, les lumières… absolument tout ! |
| 11–18 s | Batterie vide → rue sans réseau → ascenseur hors service | En quelques minutes, les transports sont paralysés, les réseaux tombent, et des millions de personnes ne comprennent plus rien. |
| 18–25 s | Rayons vides → caisse « paiement par carte indisponible » | Dans les magasins, les rayons se vident… et la carte bancaire ? Elle ne passe plus. |
| 25–32 s | Banque fermée → journal « Panne générale » → ville dans le noir | Les banques ferment. Toute la France est touchée. Et la nuit… les villes deviennent méconnaissables. |
| 32–40 s | Jour 1 → Jour 3 → Jour 5 → Jour 7 | Les jours passent. Les batteries sont vides, les réserves diminuent… et la fatigue s'installe. |
| 40–48 s | Fenêtre : les lumières réapparaissent | Au septième jour, la ville est toujours silencieuse… quand soudain, une lumière s'allume. Puis une autre ! |
| 48–55 s | Stickman qui saute de joie | Le courant revient, quartier par quartier ! Mais tout réparer pourrait prendre beaucoup plus de temps. |
| 55–60 s | Liste « À prévoir » + « TU TIENDRAIS ? » | Et toi… tu tiendrais sept jours sans électricité ? Dis-le en commentaire ! |

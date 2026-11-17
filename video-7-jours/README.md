# 7 jours sans électricité — vidéo TikTok (9:16)

- `7-jours-sans-electricite.mp4` : la vidéo (1080×1920, 30 i/s, ~76 s sans voix off).
- `images/` : les 17 illustrations. `rig.json` : position du visage et des mains du stickman dans chaque image.
- `timeline.py` : les 12 scènes (texte de voix off, plans, caméra, animations, effets).
- `film.py` : rendu image (caméra, animation du stickman, effets, sous-titres karaoké).
- `son.py` : musique sombre + bruitages + mixage de la voix off (la musique baisse sous la voix).

## Ajouter la voix off ElevenLabs

1. Générer **un fichier par scène** avec les textes ci-dessous.
2. Les nommer `01.mp3`, `02.mp3`, … `12.mp3` et les mettre dans `voix/`.
3. Relancer :

```bash
pip install numpy scipy pillow opencv-python-headless
python3 son.py son.wav
python3 film.py son.wav 7-jours-sans-electricite.mp4
```

Chaque scène prend automatiquement la durée de son clip ; sous-titres, bruitages et musique se recalent dessus.

**Voix conseillée :** « Henry, français ténébreux » (voice ID `CbCVr0nso2tHXdUrOh4e`).
Alternative plus « créateur TikTok » : « Hugo – Punchy French Creator » (`3Tp5mYhT9wrfnry9pzvV`).
**Modèle :** Eleven v3 (gère les balises entre crochets). Réglages : stabilité ~45 %, similarité ~75 %, style ~30 %, vitesse 1,05.

| Fichier | Texte à coller dans ElevenLabs |
|---|---|
| 01 | [mysterious] Et si demain… toute l'électricité du monde disparaissait. [pause] Pendant sept jours. |
| 02 | [tense] Vingt heures pile. [pause] Tout s'éteint. La télé. Les lumières. Le téléphone. [dramatic] Absolument tout. |
| 03 | [worried] Plus de batterie. Plus de réseau. Les feux sont morts, les ascenseurs bloqués… et personne ne comprend ce qui se passe. |
| 04 | [urgent] Dans les magasins, c'est la panique. Les rayons se vident… et ta carte bancaire ? Elle ne sert plus à rien. |
| 05 | [serious] Les banques ferment. Le pays entier est à l'arrêt. [whispering] Et quand la nuit tombe… la ville disparaît dans le noir. |
| 06 | [somber] Jour un. Jour trois. Jour cinq. Les réserves fondent, les bougies s'éteignent… et la peur s'installe. |
| 07 | [whispering] Jour sept. Toujours rien. [pause] Et puis, soudain… [surprised] une lumière. Puis une autre. |
| 08 | [excited] Le courant revient ! [serious] Mais remettre tout le pays en marche… ça prendra du temps. |
| 09 | [calm] Ce qu'il faut retenir ? Être préparé. Ne pas dépendre que du numérique. Et savoir s'adapter. |
| 10 | Garde toujours de l'eau, de la nourriture, une lampe, une batterie… et une radio. |
| 11 | [mysterious] Parce que la vraie question, c'est… et si ça se reproduisait demain ? |
| 12 | [intense] Toi… tu tiendrais sept jours ? Dis-le en commentaire. |

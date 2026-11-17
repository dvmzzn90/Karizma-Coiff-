# Voix off ElevenLabs : vidéo GTA 6

## Voix conseillée
**Hugo – Punchy French Creator** (bibliothèque de voix ElevenLabs, ID `3Tp5mYhT9wrfnry9pzvV`).
C'est une voix masculine française, jeune et énergique, faite pour les vidéos courtes.
Autres choix : *Maxence* (jeune et naturel) ou *Guillaume – Storytelling Naturel*.

## Réglages
- Modèle : **Eleven v3**, qui comprend les balises entre crochets comme `[excited]`.
- Stabilité : **Creative** (environ 35–45 %)
- Similarité : 75 %
- Vitesse : 1,05 à 1,1
- Génère **une scène à la fois** (6 fichiers). Chaque phrase doit durer moins de 10 secondes.

## Texte à coller dans ElevenLabs (une scène par génération)
Les textes ont été un peu raccourcis pour tenir dans 10 secondes chacun. Les sous-titres de la vidéo suivent déjà ces textes.

**Scène 1 (0–10 s)**
```
[excited] Tu veux GTA 6, mais t'as pas d'argent ? Regarde cette vidéo jusqu'à la fin !
```
**Scène 2 (10–20 s)**
```
[sighs] Comme beaucoup de joueurs, tu rêves de GTA 6... mais entre les dépenses du quotidien et le prix des jeux, c'est pas toujours facile de se faire plaisir !
```
**Scène 3 (20–30 s)**
```
[serious] Mais attention ! Certains sites promettent GTA 6 gratuit. Ne tombe pas dans le piège : ils veulent juste voler tes infos ou ton argent !
```
**Scène 4 (30–40 s)**
```
[confident] Voici l'astuce : mets un peu d'argent de côté chaque semaine, compare les prix chez les revendeurs fiables et surveille les promos officielles. Chaque euro compte !
```
**Scène 5 (40–50 s)**
```
[dreamy] Imagine le jour où tu pourras enfin lancer GTA 6, prendre le volant et découvrir tout cet univers. [excited] Alors prépare ton budget dès maintenant !
```
**Scène 6 (50–60 s)**
```
[excited] Alors dis-moi en commentaire : tu l'achètes dès sa sortie, ou tu attends une promo ? Et abonne-toi à Cinema Short pour plus d'astuces gaming !
```

## Ajouter la voix à la vidéo
Enregistre les fichiers dans `voix/` sous les noms `scene1.mp3` à `scene6.mp3`, puis lance `python3 render2.py sortie.mp4`.
Chaque voix démarre au début de sa scène, et la musique baisse automatiquement quand la voix parle.

## Images en vrai 9:16 plein écran
Pour avoir de vraies images verticales au lieu du montage « image entière en haut + zoom en bas », regénère les 6 images dans ton appli d'IA.
Choisis le format **9:16 (1080×1920)** et utilise ce début de prompt, suivi de la description de la case :
```
Format vertical 9:16, 1080x1920, même personnage cartoon (tête ronde blanche, casquette noire à l'envers, sweat à capuche noir), même style néon violet/rose, textes en haut et au centre (pas en bas), image remplie jusqu'aux bords.
```
Mets ensuite les images dans `images/` sous les noms `scene1.png` à `scene6.png` : le script passe tout seul en mode plein écran.

# Dossier de production : « Et si les humains étaient tous devenus un animal ? »

Format 9:16, 1080x1920, 30 i/s, 65 s. La vidéo de `out/` est un **animatique complet** : timing, voix,
sons, musique, sous-titres et transitions sont définitifs, mais les images sont des illustrations
procédurales. Pour obtenir le rendu photoréaliste, générez chaque plan avec un modèle vidéo IA
(Veo 3, Kling 2.x, Runway Gen-4, Sora, Hailuo…), puis déposez les fichiers dans `clips/planNN.mp4`
et relancez `python3 src/make_video.py mux`. Ils remplacent automatiquement les images du plan, sans
toucher au son ni aux sous-titres.

Suffixe commun à ajouter à chaque prompt :
> *vertical 9:16, photorealistic, cinematic lighting, high contrast, shallow depth of field, anamorphic lens, film grain, 35mm, constant subtle camera motion, no text*

Étalonnage : teal & orange pour les plans 1 à 6 (chaos), vert doré pour les plans 7 et 8 (nature).

| Plan | Durée | Prompt (anglais, plus fiable pour les modèles vidéo) |
|---|---|---|
| 01 | 0–5 s | Extreme close-up in a dark bedroom at night, cold moonlight through blinds. A human hand resting on white bedsheets slowly transforms into a furry clawed paw; long ivory claws extend and tear through the fabric. Cut to an extreme close-up of a closed furry eyelid that snaps open to reveal a golden feline eye with a vertical slit pupil contracting. |
| 02 | 5–10 s | Aerial drone shot of a modern European city at sunrise, golden haze, then the camera dives fast between skyscrapers toward empty streets, top-down view of the street canyon. Leave the top third of the frame calm for a title. |
| 03 | 10–17 s | Fast montage: (a) a corporate office, an empty suit collapses onto a chair and a majestic lion wearing a torn suit and red tie stands behind the desk; (b) a classroom, empty sweater on a desk, a sloth hangs from the top of a chalkboard; (c) inside a city bus, a dog sits in the driver's seat holding the steering wheel, seen from behind. |
| 04 | 17–24 s | (a) A crowded city square full of motionless animals of every species standing like people, overcast light, a giant building screen showing static; (b) top-down on cobblestones, smartphones lying on the ground ringing and vibrating with incoming calls, nobody answering; (c) a giant LED screen displaying "NO SIGNAL" static, then it switches off like an old CRT. |
| 05 | 24–31 s | (a) A city skyline at night, the window lights switch off block by block, abandoned cars on a ring road with hazard lights blinking; (b) a metro train stopped inside a dark tunnel, red tail lights, orange emergency lamp; (c) an empty nuclear power plant control room, red alarm lights flashing, empty chair, screens showing warnings. |
| 06 | 31–38 s | A residential building corridor at night, flickering fluorescent light. A gazelle slowly backs away toward the camera. At the far end of the corridor two glowing tiger eyes appear in the darkness and approach; the tiger's face barely emerges from the shadows. Smash zoom to the eyes, then black. |
| 07 | 38–46 s | 20-year time-lapse: the Eiffel Tower and Paris rooftops are slowly covered by vines and trees, roots crack the asphalt; (b) deer walking on a grass-covered Champs-Élysées toward the Arc de Triomphe, sun rays; (c) a flock of birds taking off in front of a huge golden sunrise. Warm green-gold grade. |
| 08 | 46–53 s | Forest at dusk, purple and orange sky, fog between pine trees. A wild grey wolf cautiously sniffs another wolf (the second wolf wears a torn piece of a red t-shirt around its neck), then both walk away together into the forest. |
| 09 | 53–60 s | Continuous pull-back: starting inside the golden slit pupil of the feline eye reflecting a forest, the camera pulls back from the eye, through the sky, up to Earth seen from space: green and blue, no city lights on the night side. |
| 10 | 60–65 s | Extreme close-up of the same golden feline eye, it blinks slowly, then the eyelids close completely into darkness (to loop back to the first shot). Leave the top quarter of the frame calm for text. |

## Voix off

La version fournie utilise une voix de synthèse hors ligne (espeak-ng + MBROLA « fr1 »). Elle est
grave et posée, égalisée pour la netteté (présence 2,8 kHz, coupe des bas-médiums, compression légère), mais reste synthétique. Pour la voix documentaire finale, enregistrez ou générez
(ElevenLabs, voix masculine grave et mystérieuse) **chaque réplique séparément** au nom
`voice/line01.wav` … `voice/line19.wav`, puis relancez `python3 src/make_video.py`. Le pipeline
recale automatiquement chaque réplique à son instant et recalcule les sous-titres mot par mot.

| # | Début | Réplique | Mot-clé (jaune) |
|---|---|---|---|
| 01 | 0,6 s | Ce matin, huit milliards d'humains se sont réveillés… avec des griffes. | griffes |
| 02 | 5,35 s | Et si, du jour au lendemain, tous les humains étaient devenus un animal ? | animal |
| 03 | 10,15 s | Ton patron ? Un lion. | lion |
| 04 | 12,3 s | Ton prof ? Un paresseux. | paresseux |
| 05 | 14,55 s | Et toi… tu serais quoi ? | toi |
| 06 | 17,2 s | Problème numéro un : plus personne ne parle. | parle |
| 07 | 20,6 s | Sept mille langues… remplacées par des cris. | cris |
| 08 | 24,25 s | En trois jours, les villes s'éteignent. | éteignent |
| 09 | 26,6 s | Les métros s'arrêtent. | métros |
| 10 | 28,15 s | Et les centrales… n'ont plus personne aux commandes. | centrales |
| 11 | 31,15 s | Problème numéro deux : la chaîne alimentaire. | alimentaire |
| 12 | 33,9 s | Si ton voisin est devenu un tigre… tu es peut-être son dîner. | dîner |
| 13 | 38,6 s | Mais pendant ce temps… la planète respire. | respire |
| 14 | 42,2 s | En vingt ans, la forêt reprend Paris. | forêt |
| 15 | 46,4 s | Et les vrais animaux ? Ils ne nous reconnaissent même pas. | reconnaissent |
| 16 | 50,0 s | Pour eux, on est juste… des nouveaux voisins. | voisins |
| 17 | 53,55 s | Alors la vraie question… est-ce qu'on serait plus heureux… sans être humains ? | heureux |
| 18 | 60,15 s | Abonne-toi… | abonne-toi |
| 19 | 61,15 s | et dis-moi en commentaire… quel animal tu serais. | animal |

## Sons (tous synthétisés dans `src/audio.py`)

- **Plan 1 :** silence, battements de cœur, tissu déchiré à 2,0 s, grognement, boom calé sur « griffes ».
- **Plan 2 :** whoosh, glitch, nappe de basse montante.
- **Plan 3 :** rugissement sur « lion », petit rire étouffé après « paresseux », aboiement, record scratch sur « toi ».
- **Plan 4 :** cacophonie (oiseaux, singes, chiens) et sonneries, coupée net sur « cris ».
- **Plan 5 :** alarme industrielle lointaine, « clac » électrique sur « éteignent », bourdonnement.
- **Plan 6 :** cœur qui accélère, respiration, grondement, silence total après « dîner ».
- **Plan 7 :** oiseaux, vent, rivière, piano et cordes.
- **Plan 8 :** hurlement de loup avec écho, branches, crescendo.
- **Plan 9 :** la musique s'arrête d'un coup, un seul battement de cœur, puis le vent.
- **Plan 10 :** grondement doux, impact final, fondu au noir qui boucle sur le plan 1.

Musique : tension hybride à 120 BPM de 5 s à 37,6 s (grille alignée sur les coupes), puis
piano et cordes (La m – Fa – Do – Sol) de 38 s à 53 s. Le mixage atténue musique et effets sous la
voix (ducking) et normalise à −14 LUFS, le standard TikTok/Reels.

"""Script, découpage et timing de la vidéo « Et si les humains étaient tous devenus un animal ? ».

Toutes les durées sont en secondes. La vidéo fait 65 s, 1080x1920, 30 i/s.
"""

W, H, FPS = 1080, 1920, 30
DURATION = 65.0
SR = 48000

# --- Narration ------------------------------------------------------------
# Chaque réplique : instant de départ, mot-clé surligné en jaune,
# et segments (texte, pause après en s). Les « … » du script deviennent des pauses.
LINES = [
    dict(plan=1, start=0.6, kw="griffes", segs=[
        ("Ce matin, huit milliards d'humains se sont réveillés…", 0.45),
        ("avec des griffes.", 0.0)]),
    dict(plan=2, start=5.35, kw="animal", segs=[
        ("Et si, du jour au lendemain, tous les humains étaient devenus un animal ?", 0.0)]),
    dict(plan=3, start=10.15, kw="lion", segs=[("Ton patron ?", 0.15), ("Un lion.", 0.0)]),
    dict(plan=3, start=12.3, kw="paresseux", segs=[("Ton prof ?", 0.15), ("Un paresseux.", 0.0)]),
    dict(plan=3, start=14.55, kw="toi", segs=[("Et toi…", 0.35), ("tu serais quoi ?", 0.0)]),
    dict(plan=4, start=17.2, kw="parle", segs=[("Problème numéro un :", 0.2), ("plus personne ne parle.", 0.0)]),
    dict(plan=4, start=20.6, kw="cris", segs=[("Sept mille langues…", 0.4), ("remplacées par des cris.", 0.0)]),
    dict(plan=5, start=24.25, kw="éteignent", segs=[("En trois jours, les villes s'éteignent.", 0.0)]),
    dict(plan=5, start=26.6, kw="métros", segs=[("Les métros s'arrêtent.", 0.0)]),
    dict(plan=5, start=28.15, kw="centrales", segs=[("Et les centrales…", 0.35), ("n'ont plus personne aux commandes.", 0.0)]),
    dict(plan=6, start=31.15, kw="alimentaire", segs=[("Problème numéro deux :", 0.2), ("la chaîne alimentaire.", 0.0)]),
    dict(plan=6, start=34.0, kw="dîner", segs=[("Si ton voisin est devenu un tigre…", 0.3), ("tu es peut-être son dîner.", 0.0)]),
    dict(plan=7, start=38.6, kw="respire", segs=[("Mais pendant ce temps…", 0.45), ("la planète respire.", 0.0)]),
    dict(plan=7, start=42.2, kw="forêt", segs=[("En vingt ans, la forêt reprend Paris.", 0.0)]),
    dict(plan=8, start=46.4, kw="reconnaissent", segs=[("Et les vrais animaux ?", 0.25), ("Ils ne nous reconnaissent même pas.", 0.0)]),
    dict(plan=8, start=50.0, kw="voisins", segs=[("Pour eux, on est juste…", 0.4), ("des nouveaux voisins.", 0.0)]),
    dict(plan=9, start=53.55, kw="heureux", segs=[("Alors la vraie question…", 0.45), ("est-ce qu'on serait plus heureux…", 0.4),
                                             ("sans être humains ?", 0.0)]),
    dict(plan=10, start=60.35, kw="animal", segs=[("Dis-moi en commentaire…", 0.35), ("quel animal tu serais.", 0.0)]),
]

# --- Plans -----------------------------------------------------------------
PLANS = [  # (numéro, début, fin, titre)
    (1, 0.0, 5.0, "ACCROCHE"),
    (2, 5.0, 10.0, "LA QUESTION"),
    (3, 10.0, 17.0, "QUI DEVIENT QUOI"),
    (4, 17.0, 24.0, "LE SILENCE"),
    (5, 24.0, 31.0, "LE CHAOS"),
    (6, 31.0, 38.0, "LA CHAÎNE ALIMENTAIRE"),
    (7, 38.0, 46.0, "LA NATURE REPREND SES DROITS"),
    (8, 46.0, 53.0, "LE RENVERSEMENT"),
    (9, 53.0, 60.0, "LA VRAIE QUESTION"),
    (10, 60.0, 65.0, "APPEL À L'ACTION"),
]

# Sous-plans : un changement d'image toutes les 2 à 3 s.
# (nom de la scène, début, fin, transition d'entrée)
SHOTS = [
    ("hand", 0.0, 2.6, "fadein"),
    ("eye_open", 2.6, 5.0, "cut"),
    ("skyline", 5.0, 7.5, "zoom"),
    ("canyon", 7.5, 10.0, "whipv"),
    ("office", 10.0, 12.2, "glitch"),
    ("classroom", 12.2, 14.0, "whip"),
    ("bus", 14.0, 15.4, "whip"),
    ("whoareyou", 15.4, 17.0, "cut"),
    ("square", 17.0, 19.5, "zoom"),
    ("phones", 19.5, 21.5, "cut"),
    ("screen", 21.5, 24.0, "whip"),
    ("city_off", 24.0, 26.5, "glitch"),
    ("metro", 26.5, 28.5, "whip"),
    ("control", 28.5, 31.0, "cut"),
    ("corridor", 31.0, 33.5, "zoom"),
    ("tiger_eyes", 33.5, 38.0, "cut"),
    ("eiffel", 38.0, 40.5, "flash"),
    ("avenue", 40.5, 43.0, "whip"),
    ("birds", 43.0, 46.0, "zoom"),
    ("wolves_meet", 46.0, 49.5, "dissolve"),
    ("wolves_leave", 49.5, 53.0, "whip"),
    ("eye_reflect", 53.0, 56.0, "cut"),
    ("earth", 56.0, 60.0, "zoomout"),
    ("eye_cta", 60.0, 65.0, "zoom"),
]

# Étalonnage par plan
GRADE = {1: "night", 2: "teal", 3: "teal", 4: "teal", 5: "teal", 6: "teal",
         7: "gold", 8: "gold", 9: "neutral", 10: "night"}


def plan_at(t):
    for n, a, b, _ in PLANS:
        if a <= t < b:
            return n
    return PLANS[-1][0]

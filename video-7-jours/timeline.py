"""Découpage de la vidéo : scènes, texte de voix off, plans, effets.

Chaque scène a une durée par défaut. Si un fichier de voix off existe dans
voix/NN.mp3 (NN = numéro de scène), la scène prend la durée de ce clip
(+ une petite marge) et la voix démarre à VO_OFFSET secondes du début de la scène.
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VO_DIR = os.path.join(HERE, "voix")
VO_OFFSET = 0.15
VO_TAIL = 0.45

# ---------------------------------------------------------------------------
# cam : liste d'images clés (p, cx, cy, zoom, roulis°) avec p ∈ [0, 1] sur la durée du plan
# act : nom de l'animation du stickman (voir ACTS dans film.py) + paramètres
# trans : transition d'entrée (cut, fade, flash, black, glitch, whip)
# grade : étalonnage (bright, contrast, sat, tint=(r,g,b))
# fx : effets additionnels
SCENES = [
    dict(n=1, dur=5.5,
         vo="Et si demain… toute l'électricité du monde disparaissait. Pendant sept jours.",
         shots=[
             dict(img=2, w=0.45, cam=[(0, .5, .30, 1.30, 0), (1, .5, .60, 1.65, 0)], trans="black",
                  grade=dict(bright=.9), fx=["twinkle"]),
             dict(img=1, w=0.55, cam=[(0, .45, .45, 1.05, 0), (1, .40, .50, 1.30, 0)], trans="whip",
                  act=("gamer", {}), fx=["screenglow"]),
         ]),
    dict(n=2, dur=7.0,
         vo="Vingt heures pile. Tout s'éteint. La télé. Les lumières. Le téléphone. Absolument tout.",
         shots=[
             dict(img=1, w=0.22, cam=[(0, .40, .50, 1.30, 0), (1, .38, .48, 1.42, 0)], trans="cut",
                  act=("gamer", {"cut": 0.25}), fx=["powercut"]),
             dict(img=3, w=0.34, cam=[(0, .40, .47, 1.15, -1.5), (1, .36, .44, 1.35, 1)], trans="glitch",
                  act=("shock", {}), grade=dict(bright=.85), shake=.004, impacts=[0.0]),
             dict(img=5, w=0.44, cam=[(0, .40, .17, 1.32, 0), (.3, .40, .17, 1.36, 0), (.5, .40, .50, 1.36, 0),
                                      (.72, .40, .50, 1.40, 0), (.9, .40, .83, 1.36, 0), (1, .40, .84, 1.40, 0)],
                  trans="glitch", fx=["glitchpanels"]),
         ]),
    dict(n=3, dur=7.5,
         vo="Plus de batterie. Plus de réseau. Les feux sont morts, les ascenseurs bloqués… et personne ne comprend ce qui se passe.",
         badge="JOUR 1",
         shots=[
             dict(img=4, w=0.30, cam=[(0, .50, .50, 1.05, 0), (1, .62, .58, 1.40, 2)], trans="whip",
                  act=("phone", {}), grade=dict(bright=.9), shake=.002),
             dict(img=6, w=0.40, cam=[(0, .45, .50, 1.10, -2), (1, .52, .45, 1.28, 1)], trans="flash",
                  act=("street", {}), fx=["rain"], shake=.005),
             dict(img=7, w=0.30, cam=[(0, .38, .55, 1.05, 0), (1, .50, .45, 1.30, 0)], trans="whip",
                  act=("elevator", {}), grade=dict(bright=.9)),
         ]),
    dict(n=4, dur=7.0,
         vo="Dans les magasins, c'est la panique. Les rayons se vident… et ta carte bancaire ? Elle ne sert plus à rien.",
         badge="JOUR 1",
         shots=[
             dict(img=8, w=0.50, cam=[(0, .30, .50, 1.20, 0), (1, .62, .47, 1.32, 0)], trans="whip",
                  act=("reach", {}), fx=["dust"], shake=.002),
             dict(img=9, w=0.50, cam=[(0, .40, .50, 1.10, 0), (.5, .70, .55, 1.45, 0), (.7, .32, .40, 1.50, 0),
                                      (1, .30, .38, 1.60, 0)], trans="whip",
                  act=("walk", {"hands": True}), impacts=[0.55]),
         ]),
    dict(n=5, dur=7.5,
         vo="Les banques ferment. Le pays entier est à l'arrêt. Et quand la nuit tombe… la ville disparaît dans le noir.",
         badge="JOUR 1",
         shots=[
             dict(img=10, w=0.32, cam=[(0, .55, .50, 1.05, 0), (1, .60, .42, 1.25, 0)], trans="whip",
                  act=("walk", {}), shake=.002),
             dict(img=11, w=0.33, cam=[(0, .50, .60, 1.05, 0), (1, .48, .62, 1.38, 0)], trans="whip",
                  act=("paper", {}), impacts=[0.15]),
             dict(img=2, w=0.35, cam=[(0, .50, .58, 1.45, 0), (1, .50, .45, 1.20, 0)], trans="black",
                  grade=dict(night=True), fx=["lightning", "torches", "dust"]),
         ]),
    dict(n=6, dur=8.0,
         vo="Jour un. Jour trois. Jour cinq. Les réserves fondent, les bougies s'éteignent… et la peur s'installe.",
         shots=[
             dict(img=12, w=1.0, cam=[(0, .5, .5, 1.0, 0), (.06, .5, .5, 1.0, 0), (.12, .25, .25, 2.0, 0),
                                      (.30, .25, .25, 2.06, 0), (.36, .75, .25, 2.0, 0), (.56, .75, .25, 2.06, 0),
                                      (.62, .25, .75, 2.0, 0), (.80, .25, .75, 2.06, 0), (.86, .75, .75, 2.0, 0),
                                      (1, .75, .75, 2.18, 0)],
                  trans="black", act=("days", {}), fx=["candles", "dust"], grade=dict(bright=.85)),
         ]),
    dict(n=7, dur=7.0,
         vo="Jour sept. Toujours rien. Et puis, soudain… une lumière. Puis une autre.",
         badge="JOUR 7",
         shots=[
             dict(img=13, w=1.0, cam=[(0, .45, .50, 1.0, 0), (.45, .50, .47, 1.15, 0), (1, .62, .42, 1.38, 0)],
                  trans="black", act=("window", {"t_light": 0.5}), fx=["lightsback", "lantern13"]),
         ]),
    dict(n=8, dur=5.5,
         vo="Le courant revient ! Mais remettre tout le pays en marche… ça prendra du temps.",
         badge="JOUR 7",
         shots=[
             dict(img=14, w=1.0, cam=[(0, .40, .45, 1.05, 0), (1, .45, .40, 1.30, 0)], trans="flash",
                  act=("joy", {}), fx=["lantern14", "sparkles"], impacts=[0.0]),
         ]),
    dict(n=9, dur=6.5,
         vo="Ce qu'il faut retenir ? Être préparé. Ne pas dépendre que du numérique. Et savoir s'adapter.",
         shots=[
             dict(img=16, w=1.0, cam=[(0, .35, .45, 1.10, 0), (.25, .60, .38, 1.35, 0), (.55, .70, .52, 1.40, 0),
                                      (.85, .70, .64, 1.40, 0), (1, .62, .60, 1.30, 0)],
                  trans="whip", act=("proud", {}), fx=["sunrays", "dust"], checks=[.30, .58, .85]),
         ]),
    dict(n=10, dur=5.5,
         vo="Garde toujours de l'eau, de la nourriture, une lampe, une batterie… et une radio.",
         shots=[
             dict(img=15, w=1.0, cam=[(0, .50, .45, 1.05, 0), (.5, .62, .42, 1.30, 0), (1, .60, .60, 1.35, 0)],
                  trans="whip", act=("write", {}), fx=["lantern15", "dust"]),
         ]),
    dict(n=11, dur=4.5,
         vo="Parce que la vraie question, c'est… et si ça se reproduisait demain ?",
         shots=[
             dict(img=17, w=1.0, cam=[(0, .45, .62, 1.05, 0), (1, .55, .32, 1.30, 0)], trans="fade",
                  act=("gaze", {}), fx=["sunglow", "dust"]),
         ]),
    dict(n=12, dur=4.2,
         vo="Toi… tu tiendrais sept jours ? Dis-le en commentaire.",
         shots=[
             dict(img=17, w=1.0, cam=[(0, .40, .55, 1.25, 0), (1, .33, .52, 1.75, 0)], trans="black",
                  act=("gaze", {}), grade=dict(bright=.55, sat=.6), fx=["cta", "dust"]),
         ]),
]


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True).stdout.strip()
    return float(out)


def vo_file(n):
    for ext in ("mp3", "wav", "m4a", "ogg"):
        p = os.path.join(VO_DIR, f"{n:02d}.{ext}")
        if os.path.exists(p):
            return p
    return None


def build():
    """Calcule les temps absolus. Retourne (scenes, shots, total)."""
    t = 0.0
    scenes, shots = [], []
    for sc in SCENES:
        vo = vo_file(sc["n"])
        dur = sc["dur"]
        vo_len = None
        if vo:
            vo_len = probe_duration(vo)
            dur = vo_len + VO_OFFSET + VO_TAIL
        s = dict(sc, start=t, end=t + dur, vo_path=vo, vo_len=vo_len)
        scenes.append(s)
        tw = sum(sh["w"] for sh in sc["shots"])
        u = t
        for sh in sc["shots"]:
            d = dur * sh["w"] / tw
            shots.append(dict(sh, start=u, end=u + d, scene=sc["n"]))
            u += d
        t += dur
    return scenes, shots, t


if __name__ == "__main__":
    sc, sh, total = build()
    for s in sc:
        print(f"scène {s['n']:2d}  {s['start']:6.2f} → {s['end']:6.2f}  voix={'oui' if s['vo_path'] else 'non'}")
    print("total", round(total, 2))
    json.dumps([])

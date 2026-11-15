"""Doublage voix des Shorts : voix neuronales FR (Piper), scènes étirées pour laisser
parler les personnages, synchro labiale sur l'enveloppe de la voix, musique « ducking ».

Usage : VOICES_DIR=/chemin/modeles python3 voice/dub.py 1   (Short Karizma)
        VOICES_DIR=/chemin/modeles python3 voice/dub.py 2   (Short salle de sport)
"""
import importlib.util, math, os, subprocess, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "short"))
from tts import say
SR, FPS = 44100, 30

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m

# ---------------------------------------------------------------- casting
CAST = {  # personnage -> (voix, vitesse, hauteur)
    "N": ("tom", 1.05, .92),        # narrateur
    "THEO": ("tom", 1.18, 1.10),
    "KARIM": ("pierre", 1.0, .84),
    "INES": ("siwis", 1.12, 1.06),
    "MALIK": ("tom", 1.12, 1.05),
    "SARAH": ("jessica", 1.08, 1.04),
    "TONY": ("pierre", .98, .80),
}
NARR1 = ("pierre", 1.02, .95)  # narrateur du Short 1 : voix différente de Théo

# (scène, t local d'origine, personnage, texte parlé)
CUES = {
1: [
    ("hook", .1, "N", "Il avait quinze minutes avant son premier rendez-vous…"),
    ("hook", 1.3, "N", "et il s'était coupé les cheveux tout seul !"),
    ("enter", .4, "THEO", "Aide-moi frère ! J'ai un rendez-vous dans quinze minutes !"),
    ("who", .1, "KARIM", "Qui t'a fait ça ?"),
    ("who", 1.9, "THEO", "Moi… avec la tondeuse de mon père."),
    ("montage", .1, "N", "Mode Karizma : activé !"),
    ("reveal", 1.0, "THEO", "Frère… c'est moi, ça ?!"),
    ("pay", .2, "THEO", "Merci ! Je te dois combien ?"),
    ("pay", 1.6, "KARIM", "Rien. Dis-moi juste… elle s'appelle comment ?"),
    ("pay", 4.3, "THEO", "Inès."),
    ("ines", .9, "INES", "Papa ! T'as fini ? Mon rendez-vous arrive !"),
    ("ines", 2.6, "KARIM", "Ah. Il est déjà là, ma chérie."),
    ("end", 1.2, "N", "Partie deux ? Abonne-toi pour la suite."),
],
2: [
    ("hook", .1, "N", "Il s'est mis au sport pour plaire à sa femme…"),
    ("hook", 1.6, "N", "sans savoir qui l'attendait à la salle."),
    ("home1", .3, "SARAH", "T'es mignon chéri… mais t'es trop maigre."),
    ("home1", 3.4, "MALIK", "Ah…"),
    ("home2", .2, "MALIK", "Je m'inscris à la salle. Dans trois mois, tu me reconnaîtras plus."),
    ("home2", 2.9, "SARAH", "Vas-y mon cœur… prends ton temps."),
    ("gym1", .6, "TONY", "Bienvenue à l'Iron Palace. Moi c'est Tony, le gérant."),
    ("gym1", 3.6, "MALIK", "Je veux devenir fort… pour ma femme."),
    ("gym1", 5.0, "TONY", "Ta femme ? … Elle a de la chance."),
    ("train1", .2, "N", "Tous les jours. Sans exception."),
    ("phone", .1, "N", "Chaque fois que Malik s'entraînait…"),
    ("phone", 1.6, "N", "Tony disparaissait."),
    ("phone", 3.0, "TONY", "Continue tes séries, champion. J'ai un rendez-vous important."),
    ("train2", .2, "N", "Plus fort. Plus lourd."),
    ("train2", 4.6, "N", "Malik, deux point zéro."),
    ("door", .1, "N", "Trois mois plus tard, il rentre plus tôt pour lui faire la surprise."),
    ("door", 2.4, "MALIK", "Surprise mon amour !"),
    ("caught", 1.4, "SARAH", "Malik ?! C'est pas ce que tu crois !"),
    ("caught", 4.0, "TONY", "Attends… c'est toi, son mari ?!"),
    ("mic", .4, "MALIK", "Merci Tony. Grâce à toi, j'ai pris quinze kilos de muscle."),
    ("mic", 4.2, "MALIK", "Et la salle m'a appris un truc, Sarah : il faut savoir lâcher le poids mort."),
    ("end", .2, "TONY", "Et ton abonnement ?"),
    ("end", 1.6, "MALIK", "Résilié."),
    ("end", 3.6, "N", "Partie deux : la vengeance. Abonne-toi pour la suite."),
],
}
# effets sonores : (scène, t local d'origine, effet)
SFX = {
1: [("enter", 0, "slam"), ("reveal", 0, "sparkle"), ("ines", 0, "dingdong"), ("end", 0, "scratch"),
    ("end", .6, "clic")] + [("montage", .5 * k, "tick") for k in range(14)] + [("montage", 1.0, "clipper")],
2: [("home2", 4.3, "notif"), ("phone", .8, "notif"), ("train2", 4.6, "sparkle"), ("door", 1.9, "knock"),
    ("caught", 0, "scratch"), ("mic", .9, "thud"), ("end", 1.6, "slam"), ("end", 3.4, "boom")]
   + [("train1", .47 * k, "clank") for k in range(16)] + [("train2", .47 * k, "clank") for k in range(10)],
}
# ambiance musicale par scène : (bpm, accords, batterie, volume)
MIN = [(220, 261.6, 329.6), (174.6, 220, 261.6), (130.8, 164.8, 196), (196, 246.9, 293.7)]
HYPE = [(164.8, 196, 246.9), (130.8, 164.8, 196), (146.8, 174.6, 220), (123.5, 155.6, 185)]
POP = [(220, 261.6, 329.6), (174.6, 220, 261.6), (196, 246.9, 293.7), (164.8, 207.7, 246.9)]
MUSIC = {
1: {"hook": (104, POP, True, .7), "enter": (104, POP, True, 1), "who": (104, POP, True, 1), "montage": (128, HYPE, True, 1),
    "reveal": (104, POP, True, 1), "pay": (104, POP, True, .8), "ines": (104, POP, True, .8), "end": "drone"},
2: {"hook": (92, MIN, True, .7), "home1": (92, MIN, True, .7), "home2": (92, MIN, True, .7), "gym1": (128, HYPE, True, .9),
    "train1": (128, HYPE, True, 1), "phone": (128, HYPE, True, .8), "train2": (128, HYPE, True, 1),
    "door": (92, [(261.6, 329.6, 392)], False, 1.2), "caught": "drone", "mic": "drone", "end": (128, HYPE, True, 1)},
}
CHAR_FUNCS = {1: {"THEO": "theo", "KARIM": "karim", "INES": "ines"}, 2: {"MALIK": "malik", "SARAH": "sarah", "TONY": "tony"}}
PAD = .35  # silence après chaque réplique

def build(which):
    if which == 1:
        mod = load(os.path.join(ROOT, "short", "render.py"), "render")
        out_dir, out_name = os.path.join(ROOT, "short"), "karizma_short_voix.mp4"
    else:
        load(os.path.join(ROOT, "short", "render.py"), "render")
        mod = load(os.path.join(ROOT, "short2", "render.py"), "render2")
        out_dir, out_name = os.path.join(ROOT, "short2"), "salle_de_sport_short_voix.mp4"
    frames = os.path.join(out_dir, "frames_voix"); os.makedirs(frames, exist_ok=True)

    # 1) synthèse des répliques
    cues = []
    for sc, t0, who, text in CUES[which]:
        v, sp, pi = (NARR1 if (which == 1 and who == "N") else CAST[who])
        audio = say(text, v, sp, pi); cues.append((sc, t0, who, audio))
        print(f"  {who:6s} {len(audio) / SR:4.1f}s  {text}")

    # 2) déformation temporelle par scène (linéaire par morceaux)
    warps, T0 = [], 0.0
    for s, e, name in mod.SCENES:
        D = e - s
        pts = sorted({0.0, D} | {t for sc, t, _, _ in cues if sc == name})
        need = {}
        for sc, t, _, a in cues:
            if sc == name: need[t] = max(need.get(t, 0), len(a) / SR + PAD)
        new = [0.0]
        for i in range(len(pts) - 1):
            seg = pts[i + 1] - pts[i]
            new.append(new[-1] + max(seg, need.get(pts[i], 0)))
        # une réplique qui déborde de la fin de scène rallonge le dernier segment
        warps.append((name, T0, pts, new)); T0 += new[-1]
    DUR = T0

    def to_new(name, t):
        for nm, start, pts, new in warps:
            if nm == name: return start + float(np.interp(t, pts, new))
    def to_old(Tn):
        for nm, start, pts, new in warps:
            if Tn < start + new[-1] or nm == warps[-1][0]:
                return nm, float(np.interp(Tn - start, new, pts))

    # 3) pistes voix + enveloppes pour la synchro labiale
    n = int(DUR * SR) + SR
    voice = np.zeros(n); tracks = {}
    for sc, t, who, a in cues:
        i = int(to_new(sc, t) * SR)
        voice[i:i + len(a)] += a * .95
        tr = tracks.setdefault(who, np.zeros(n)); tr[i:i + len(a)] += a
    env = {}
    hop = SR // FPS
    for who, tr in tracks.items():
        m = len(tr) // hop
        rms = np.sqrt((tr[: m * hop].reshape(m, hop) ** 2).mean(1))
        env[who] = np.clip(rms / max(1e-6, np.percentile(rms[rms > 0], 90)), 0, 1) if (rms > 0).any() else rms

    # 4) remplace l'animation de bouche par l'enveloppe de la voix
    state = {"f": 0}
    for who, fname in CHAR_FUNCS[which].items():
        orig = getattr(mod, fname)
        def wrapped(*a, _o=orig, _w=who, **k):
            e = env.get(_w); f = state["f"]
            val = float(e[f]) if e is not None and f < len(e) else 0.0
            a = list(a)
            if len(a) >= 6: a[5] = val
            else: k["talk"] = val
            return _o(*a, **k)
        setattr(mod, fname, wrapped)

    # 5) images
    mod.DUR = DUR
    nf = int(DUR * FPS)
    prev = None
    for f in range(nf):
        state["f"] = f
        Tn = f / FPS
        name, t = to_old(Tn)
        im = mod.scene(name, t, Tn)
        if name != prev and f: mod.flash(im, .35)
        prev = name
        mod.progress_bar(im, Tn)
        im.convert("RGB").save(os.path.join(frames, f"{f:05d}.jpg"), quality=90)
        if f % 300 == 0: print(f"  image {f}/{nf}")

    # 6) musique + effets
    rng = np.random.default_rng(5)
    music = np.zeros(n); fx = np.zeros(n)
    def put(buf, s, at):
        i = int(at * SR); j = min(len(buf), i + len(s))
        if i < j: buf[i:j] += s[: j - i]
    def kick(v=1):
        t = np.arange(int(SR * .25)) / SR
        return v * .9 * np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    def noise(d, decay, v): x = rng.standard_normal(int(SR * d)); return v * x * np.exp(-np.arange(len(x)) / SR * decay)
    def tone(f, d, v): t = np.arange(int(SR * d)) / SR; return v * np.sin(2 * np.pi * f * t) * np.exp(-t * 4)
    for name, start, pts, new in warps:
        cfg = MUSIC[which][name]; L = new[-1]
        if cfg == "drone":
            t = np.arange(int(SR * L)) / SR
            put(music, (.35 * np.sin(2 * np.pi * 55 * t) + .15 * np.sin(2 * np.pi * 58.3 * t)) * np.minimum(1, t / 1.5), start)
            continue
        bpm, ch, drums, v = cfg; beat = 60 / bpm; k = 0; tb = 0.0
        while tb < L - .05:
            if drums:
                put(music, kick(v), start + tb); put(music, noise(.05, 80, .1 * v), start + tb + beat / 2)
                if k % 2: put(music, noise(.18, 22, .3 * v), start + tb)
            if k % 4 == 0:
                d = min(beat * 4, L - tb); t = np.arange(int(SR * d)) / SR
                put(music, sum(.06 * v * np.sin(2 * np.pi * f_ * t) for f_ in ch[(k // 4) % len(ch)])
                    * np.minimum(1, t * 6) * np.exp(-t * .5) * np.minimum(1, (d - t) * 20), start + tb)
            tb += beat; k += 1
    def whoosh(d=.4):
        x = rng.standard_normal(int(SR * d)); return .3 * np.convolve(x, np.ones(30) / 30, "same") * np.sin(np.linspace(0, np.pi, len(x)))
    for name, start, _, _ in warps[1:]: put(fx, whoosh(), start - .2)
    clipper_end = None
    for sc, t, kind in SFX[which]:
        at = to_new(sc, t)
        if kind == "slam": put(fx, kick(1.5), at)
        elif kind == "sparkle":
            for k in range(10): put(fx, tone(1200 + 90 * k, .25, .16), at + k * .07)
        elif kind == "dingdong": put(fx, tone(988, .9, .35), at); put(fx, tone(784, 1.0, .35), at + .45)
        elif kind == "scratch":
            t_ = np.arange(int(SR * .5)) / SR
            put(fx, .55 * np.sin(2 * np.pi * (900 * np.exp(-t_ * 6)) * t_) * (rng.standard_normal(len(t_)) * .3 + .7), at)
        elif kind == "clic":
            for k in range(8): put(fx, noise(.03, 50, .4), at + k * .3)
        elif kind == "tick": put(fx, tone(1500 + 500 * (int(t / .5) % 2), .05, .25), at)
        elif kind == "clipper":
            end = to_new(sc, 6.4); t_ = np.arange(int(SR * (end - at))) / SR
            put(fx, .1 * np.sign(np.sin(2 * np.pi * 110 * t_)) * (.7 + .3 * np.sin(2 * np.pi * 7 * t_)), at)
        elif kind == "notif": put(fx, tone(1318, .12, .3), at); put(fx, tone(1760, .2, .3), at + .12)
        elif kind == "knock":
            for k in range(3): put(fx, kick(1.1), at + k * .22)
        elif kind == "thud": put(fx, kick(1.4), at)
        elif kind == "clank": put(fx, kick(.35) + 0, at); put(fx, noise(.08, 40, .08), at)
        elif kind == "boom":
            t_ = np.arange(int(SR * 2.6)) / SR; put(fx, .4 * np.sin(2 * np.pi * 73.4 * t_) * np.exp(-t_ * .8), at)
    # ducking : la musique baisse quand quelqu'un parle
    m = len(voice) // hop
    venv = np.sqrt((voice[: m * hop].reshape(m, hop) ** 2).mean(1)) > .01
    venv = np.convolve(venv.astype(float), np.ones(8) / 8, "same")
    duck = 1 - .65 * np.clip(np.repeat(venv, hop), 0, 1)
    duck = np.pad(duck, (0, n - len(duck)), constant_values=1)
    music = music / max(1e-6, np.abs(music).max()) * .45 * duck
    fx = fx / max(1e-6, np.abs(fx).max()) * .55
    mixb = music + fx + voice
    mixb = mixb[: int(DUR * SR)]
    mixb = np.tanh(mixb / max(1e-6, np.abs(mixb).max()) * 1.4) * .92  # léger limiteur
    wav = os.path.join(out_dir, "audio_voix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mixb * 32767).astype(np.int16).tobytes())
    mp4 = os.path.join(out_dir, out_name)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "%05d.jpg"),
                    "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("OK", mp4, f"{DUR:.1f}s")

if __name__ == "__main__":
    for a in sys.argv[1:] or ["1", "2"]: build(int(a))

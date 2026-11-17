"""Bande-son : musique sombre + bruitages, calés sur timeline.py.
Si des voix off voix/NN.mp3 existent, elles sont placées au début de chaque scène
et la musique baisse automatiquement sous la voix (ducking).

Usage : python3 son.py sortie.wav
"""
import math
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import fftconvolve, lfilter

import timeline

SR = 48000
SCENES, SHOTS, TOTAL = timeline.build()
N = int(SR * (TOTAL + 0.5))
rng = np.random.default_rng(11)

MUS = np.zeros((N, 2))   # musique
SFX = np.zeros((N, 2))   # bruitages
VOX = np.zeros((N, 2))   # voix


# ------------------------------------------------------------------ outils
def lp(x, fc):
    a = math.exp(-2 * math.pi * fc / SR)
    return lfilter([1 - a], [1, -a], lfilter([1 - a], [1, -a], x))


def hp(x, fc):
    return x - lp(x, fc)


def env(n, att, rel, hold=None):
    e = np.ones(n)
    a, r = int(att * SR), int(rel * SR)
    if a:
        e[:min(a, n)] = np.linspace(0, 1, min(a, n))
    if r:
        r = min(r, n)
        e[-r:] *= np.linspace(1, 0, r)
    return e


def expdec(n, k):
    return np.exp(-np.arange(n) / SR * k)


def T(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR))


def osc(f, d, kind="sin", det=0.0):
    t = T(d)
    if np.ndim(f) == 0:
        ph = t * f * (1 + det)
    else:
        ph = np.cumsum(np.asarray(f) * (1 + det)) / SR
    if kind == "saw":
        return 2 * (ph % 1) - 1
    if kind == "sq":
        return np.sign(np.sin(2 * np.pi * ph))
    if kind == "tri":
        return 2 * np.abs(2 * (ph % 1) - 1) - 1
    return np.sin(2 * np.pi * ph)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def put(buf, t0, sig, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= N or i0 < 0:
        return
    n = min(len(sig), N - i0)
    s = sig[:n] * gain
    buf[i0:i0 + n, 0] += s * min(1, 1 - pan)
    buf[i0:i0 + n, 1] += s * min(1, 1 + pan)


def mus(t0, sig, gain=1.0, pan=0.0):
    put(MUS, t0, sig, gain, pan)


def sfx(t0, sig, gain=1.0, pan=0.0):
    put(SFX, t0, sig, gain, pan)


# ------------------------------------------------------------------ instruments
def pad(notes, d, gain=0.3, att=1.5, rel=1.5, fc=700, kind="saw"):
    x = np.zeros(int(d * SR))
    for m in notes:
        for det in (-0.006, 0, 0.0055):
            x += osc(midi(m), d, kind, det)
    x = lp(x, fc) / (3 * len(notes))
    return x * env(len(x), att, rel) * gain


def piano(m, d=2.5, gain=0.25):
    f = midi(m)
    t = T(d)
    x = (np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 2)
         + 0.2 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 4))
    x *= np.exp(-t * 1.6) * env(len(t), 0.004, 0.3)
    return x * gain


def braam(d=3.0, root=26, gain=0.9):
    """gros cuivre grave cinématographique"""
    t = T(d)
    x = np.zeros(len(t))
    for m in (root, root + 7, root + 12, root + 15):
        for det in (-0.01, 0, 0.012):
            x += osc(midi(m), d, "saw", det)
    x /= 12
    fc = 200 + 1400 * np.exp(-t * 1.5)
    # filtre variable approximé par blocs
    y = np.zeros_like(x)
    blk = 2400
    for i in range(0, len(x), blk):
        y[i:i + blk] = lp(x[max(0, i - 4800):i + blk], float(fc[i]))[-len(x[i:i + blk]):]
    y = np.tanh(y * 3) / 1.5
    y += lp(noise(d), 90) * 0.6 * np.exp(-t * 2)
    return y * env(len(t), 0.02, 1.2) * gain


def boom(d=2.0, gain=1.0):
    t = T(d)
    f = 30 + 90 * np.exp(-t * 8)
    x = osc(f, d) * np.exp(-t * 2.2)
    x += lp(noise(d), 120) * np.exp(-t * 3) * 0.8
    return np.tanh(x * 1.5) * gain


def whoosh(d=0.5, gain=0.3, up=True):
    t = T(d)
    x = noise(d)
    k = np.sin(np.pi * t / d) ** 2
    y = np.zeros_like(x)
    blk = 1200
    for i in range(0, len(x), blk):
        fc = 600 + 5000 * (i / len(x) if up else 1 - i / len(x))
        y[i:i + blk] = lp(hp(x[max(0, i - 2400):i + blk], 300), fc)[-len(x[i:i + blk]):]
    return y * k * gain


def riser(d, gain=0.3):
    t = T(d)
    p = t / d
    x = lp(noise(d), 2500) * p ** 2.5 * 0.6
    x += osc(150 + 900 * p ** 2, d, "saw") * 0.12 * p ** 3
    return x * gain


def hit_click(gain=0.4, fc=3000):
    return hp(noise(0.025), fc) * expdec(int(0.025 * SR), 220) * gain


def kick(gain=0.8):
    d = 0.45
    t = T(d)
    return osc(45 + 110 * np.exp(-t * 28), d) * np.exp(-t * 8) * gain


def heartbeat(t0, gain=0.6):
    for off, g in ((0, 1.0), (0.2, 0.65)):
        d = 0.3
        t = T(d)
        x = osc(48 + 20 * np.exp(-t * 20), d) * np.exp(-t * 13)
        sfx(t0 + off, lp(x, 200) * g * gain)


def tick(t0, gain=0.25, high=True):
    sfx(t0, hp(noise(0.03), 3500 if high else 2200) * expdec(int(0.03 * SR), 180) * gain, pan=0.15 if high else -0.15)


def glitch_zap(gain=0.35):
    d = 0.25
    x = osc(np.repeat(rng.uniform(200, 2400, 25), int(d * SR / 25) + 1)[:int(d * SR)], d, "sq") * 0.4
    x += hp(noise(d), 2000) * 0.5
    x *= (rng.random(int(d * SR)) > 0.3)
    return lp(x, 6000) * env(len(x), 0.002, 0.05) * gain


def bell(m, gain=0.15):
    d = 2.0
    t = T(d)
    f = midi(m)
    x = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t * 3)
    return x * np.exp(-t * 2.5) * gain


def crowd(d, gain=0.2):
    x = lp(hp(noise(d), 250), 1300)
    x *= 1 + 0.6 * lp(np.abs(noise(d)), 3) * 6
    return x * env(len(x), 0.6, 0.6) * gain


def rain_amb(d, gain=0.25):
    x = hp(noise(d), 1500)
    x += lp(noise(d), 400) * 0.5
    drops = (rng.random(int(d * SR)) > 0.9993) * rng.uniform(0.5, 1.5, int(d * SR))
    x += lfilter([1], [1, -0.985], drops) * 0.6
    return lp(x, 7000) * env(len(x), 0.5, 0.5) * gain


def wind(d, gain=0.4):
    x = lp(noise(d), 450)
    t = T(d)
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t) * np.sin(2 * np.pi * 0.27 * t + 1)
    return x * env(len(x), 1.2, 1.5) * gain


def thunder(gain=1.0):
    d = 3.5
    x = lp(noise(d), 180) * env(int(d * SR), 0.03, 3.2)
    x *= 1 + 0.8 * lp(np.abs(noise(d)), 6) * 5
    crack = hp(noise(0.3), 1500) * expdec(int(0.3 * SR), 12)
    x[:len(crack)] += crack * 0.6
    return x * gain


def footsteps(t0, n, gap=0.36, gain=0.5):
    for k in range(n):
        st = lp(noise(0.1), 700) * expdec(int(0.1 * SR), 40)
        st[:int(0.02 * SR)] += hp(noise(0.02), 2500) * expdec(int(0.02 * SR), 200) * 0.3
        sfx(t0 + k * gap, st * gain, pan=0.2 if k % 2 else -0.2)


def error_beep(t0, gain=0.15):
    for k in range(2):
        sfx(t0 + k * 0.22, osc(420, 0.16, "sq") * env(int(0.16 * SR), 0.004, 0.02) * gain)


def rustle(t0, d=0.8, gain=0.25):
    x = hp(noise(d), 1800) * (lp(np.abs(noise(d)), 15) * 4)
    sfx(t0, x * env(len(x), 0.05, 0.2) * gain)


def scribble(t0, d, gain=0.12):
    t = T(d)
    x = hp(noise(d), 2500) * (0.5 + 0.5 * np.sin(2 * np.pi * 6 * t)) ** 2
    sfx(t0, x * env(len(x), 0.05, 0.1) * gain, pan=0.2)


def power_down(t0):
    d = 1.3
    t = T(d)
    f = 240 * np.exp(-t * 3.2)
    x = osc(f, d, "saw") * np.exp(-t * 2)
    sfx(t0, lp(x, 1500) * 0.35)
    sfx(t0, hp(noise(0.08), 1000) * expdec(int(0.08 * SR), 40) * 0.8)
    sfx(t0, boom(2.5, 1.0))


def power_up(t0, gain=0.3):
    d = 1.4
    t = T(d)
    x = osc(50 + 260 * (t / d) ** 1.5, d, "saw") * (t / d)
    sfx(t0, lp(x, 1800) * gain)
    sfx(t0 + d, hp(noise(0.05), 1200) * expdec(int(0.05 * SR), 50) * 0.6)


# ------------------------------------------------------------------ helpers timeline
def sc(n):
    return next(s for s in SCENES if s["n"] == n)


def shots_of(n):
    return [s for s in SHOTS if s["scene"] == n]


# ================================================================== MUSIQUE
s1, s2 = sc(1), sc(2)
cut_shot = shots_of(2)[0]
t_cut = cut_shot["start"] + cut_shot["act"][1]["cut"] * (cut_shot["end"] - cut_shot["start"])

# Intro mystérieuse : nappe Ré mineur + boîte à musique
d = t_cut - s1["start"]
mus(0, pad([50, 53, 57, 62], d + 0.05, 0.35, 1.5, 0.02, 900))
mus(0, osc(midi(26), d) * env(int(d * SR), 2, 0.02) * 0.18)
mel = [74, 72, 69, 65, 69, 72, 74, 77, 76, 72, 69, 67]
for i, m in enumerate(mel):
    tt = 0.4 + i * 0.5
    if tt < d - 0.2:
        mus(tt, piano(m, 2.2, 0.16), pan=0.3 if i % 2 else -0.3)
# bourdonnement électrique de la pièce
hum = osc(50, d) * 0.5 + osc(100, d) * 0.3 + osc(150, d, "saw") * 0.04
sfx(0, hum * env(len(hum), 0.8, 0.01) * 0.08)

# COUPURE : silence + impact
power_down(t_cut)
for k in range(5):
    sfx(t_cut + k * 0.07, glitch_zap(0.18))

# Tension : drone + ostinato + pulsations (de la coupure à la fin de la scène 5)
t_a, t_b = t_cut + 1.0, sc(5)["end"]
d = t_b - t_a
mus(t_a, pad([26, 33, 38], d, 0.45, 2.0, 1.5, 380))
mus(t_a, osc(midi(26), d) * env(int(d * SR), 2, 1) * 0.22)
mus(sc(3)["start"], pad([51, 62, 63], t_b - sc(3)["start"], 0.12, 3, 1.5, 900))  # dissonance
beat = 60 / 84
k = 0
tt = sc(3)["start"]
while tt < t_b - 0.3:
    inten = 0.5 + 0.5 * (tt - t_a) / d
    m = [38, 38, 41, 38, 38, 36, 38, 40][k % 8]
    x = osc(midi(m), beat / 2, "saw")
    x = lp(x, 300 + 900 * inten) * env(len(x), 0.005, 0.12) * 0.22 * inten
    mus(tt, x)
    if k % 2 == 0:
        mus(tt, kick(0.45 * inten))
    k += 1
    tt += beat / 2
for n in (2, 3, 5):
    mus(sc(n)["start"] + (0.05 if n != 2 else 1.0), braam(3.2, 26, 0.55))

# Scène 6 : les jours passent — piano lent, tic-tac, battements
s6 = sc(6)
d = s6["end"] - s6["start"]
mus(s6["start"], pad([38, 41, 45, 50], d, 0.35, 1.0, 1.0, 600))
for i, m in enumerate([62, 65, 64, 60, 62, 57, 58, 57]):
    mus(s6["start"] + 0.3 + i * d / 8, piano(m, 3.0, 0.2))
tt = s6["start"]
k = 0
while tt < s6["end"]:
    tick(tt, 0.22, k % 2 == 0)
    tt += 0.5
    k += 1
for i in range(int(d / 1.1)):
    heartbeat(s6["start"] + 0.5 + i * 1.1, 0.45 + 0.3 * i / (d / 1.1))
# transitions des cases du calendrier
for p in (0.06, 0.30, 0.56, 0.80):
    sfx(s6["start"] + p * d, whoosh(0.45, 0.22))

# Scène 7 : silence pesant puis la lumière revient
s7 = sc(7)
sh7 = shots_of(7)[0]
tl = sh7["start"] + sh7["act"][1]["t_light"] * (sh7["end"] - sh7["start"])
mus(s7["start"], pad([26, 38], tl - s7["start"] + 0.5, 0.35, 1.0, 0.6, 250))
mus(s7["start"] + 0.5, riser(tl - s7["start"] - 0.5, 0.25))
mus(tl, pad([50, 53, 57, 62, 65], s7["end"] - tl + 0.4, 0.4, 0.3, 0.8, 1400))
for i, m in enumerate((81, 84, 88, 86, 89)):
    sfx(tl + i * 0.45, bell(m, 0.13), pan=0.5 if i % 2 else -0.4)
power_up(tl - 1.4, 0.25)

# Scène 8 : le retour du courant — épique mais sombre
s8 = sc(8)
d = s8["end"] - s8["start"]
chords = [[38, 50, 53, 57, 62], [34, 46, 50, 53, 58], [41, 53, 57, 60, 65], [36, 48, 52, 55, 60]]
cd = d / 4
for i, ch in enumerate(chords):
    mus(s8["start"] + i * cd, pad(ch, cd + 0.3, 0.5, 0.05, 0.3, 2000))
    mus(s8["start"] + i * cd, osc(midi(ch[0] - 12), cd, "saw") * env(int(cd * SR), 0.01, 0.2) * 0.1)
tt = s8["start"]
k = 0
while tt < s8["end"] - 0.1:
    mus(tt, kick(0.7))
    if k % 2:
        mus(tt, hp(noise(0.2), 1500) * expdec(int(0.2 * SR), 20) * 0.22)
    tt += 60 / 110
    k += 1
mus(s8["start"], boom(2.5, 0.9))

# Scènes 9-10 : réflexion — piano + nappe douce mais grave
s9, s10 = sc(9), sc(10)
d = s10["end"] - s9["start"]
mus(s9["start"], pad([38, 45, 50, 53], d, 0.33, 0.6, 1.0, 700))
seq = [62, 69, 65, 69, 62, 69, 67, 69, 60, 67, 64, 67, 62, 69, 65, 74]
step = d / len(seq)
for i, m in enumerate(seq):
    mus(s9["start"] + i * step, piano(m, 2.0, 0.14), pan=0.25 if i % 2 else -0.25)
for p in shots_of(9)[0]["checks"]:
    sh = shots_of(9)[0]
    sfx(sh["start"] + p * (sh["end"] - sh["start"]), bell(86, 0.12))
    sfx(sh["start"] + p * (sh["end"] - sh["start"]), kick(0.3))

# Scène 11 : la question — montée
s11 = sc(11)
d = s11["end"] - s11["start"]
mus(s11["start"], pad([26, 33, 38, 39], d + 0.3, 0.45, 0.5, 0.1, 500))
mus(s11["start"], riser(d, 0.35))
for i in range(int(d / 0.5)):
    heartbeat(s11["start"] + i * 0.5, 0.35 + 0.4 * i / (d / 0.5))

# Scène 12 : appel à l'action — impact, drone, arrêt net
s12 = sc(12)
d = s12["end"] - s12["start"]
mus(s12["start"], braam(3.5, 26, 0.8))
mus(s12["start"], boom(2.5, 1.0))
mus(s12["start"] + 0.2, pad([50, 53, 56, 62], d - 0.4, 0.35, 0.3, 0.05, 900))
sfx(s12["end"] - 0.45, boom(1.5, 0.9))

# ================================================================== BRUITAGES PAR PLAN
for sh in SHOTS:
    st, en = sh["start"], sh["end"]
    D = en - st
    tr = sh.get("trans")
    if tr == "whip":
        sfx(st - 0.2, whoosh(0.45, 0.3))
    elif tr == "flash":
        sfx(st, boom(1.6, 0.6))
        sfx(st - 0.25, whoosh(0.35, 0.2))
    elif tr == "glitch":
        sfx(st, glitch_zap(0.3))
    elif tr == "black" and st > 1:
        sfx(st, boom(1.8, 0.4))
    act = sh.get("act", (None, {}))[0]
    if act == "gamer":
        tt = st + 0.1
        end = en if "cut" not in sh["act"][1] else t_cut + 1.6
        k = 0
        while tt < end:
            if not (t_cut <= tt < t_cut + 0.5):
                burst = True if tt < t_cut else ((tt - t_cut) % 0.7) < 0.35
                if burst:
                    sfx(tt, hit_click(0.12, 2500 + 800 * (k % 3)), pan=0.3)
            tt += 0.09 + 0.05 * rng.random()
            k += 1
    if act == "shock":
        tt = st + 0.4
        while tt < en:
            if ((tt - st) % 0.8) < 0.4:
                sfx(tt, hit_click(0.1, 2600), pan=0.3)
            tt += 0.1
    if act == "phone":
        for k in range(int(D / 0.13)):
            sfx(st + 0.1 + k * 0.13, lp(noise(0.05), 2500) * expdec(int(0.05 * SR), 60) * 0.18, pan=0.4)
        error_beep(st + 0.3, 0.1)
    if act == "street":
        sfx(st, crowd(D + 0.5, 0.25))
        sfx(st, rain_amb(D + 0.3, 0.3))
        t = T(D)
        siren = osc(720 + 230 * np.sign(np.sin(2 * np.pi * 0.8 * t)), D)
        sfx(st, lp(siren, 1500) * env(len(t), 1, 1) * 0.05, pan=0.6)
        for tt in (0.4, 1.2):
            hk = osc(400, 0.35, "saw") + osc(505, 0.35, "saw")
            sfx(st + tt, lp(hk, 2000) * env(len(hk), 0.01, 0.05) * 0.05, pan=-0.5)
    if act == "elevator":
        error_beep(st + 0.2, 0.12)
        sfx(st + 0.15, lp(noise(0.3), 300) * expdec(int(0.3 * SR), 10) * 0.6)  # coup sur la porte
    if act == "reach":
        sfx(st, crowd(D, 0.15))
        footsteps(st + 0.05, int(D / 0.42), 0.42, 0.4)
    if act == "walk":
        sfx(st, crowd(D, 0.2))
        footsteps(st + 0.05, int(D / 0.3), 0.3, 0.45)
        if sh["img"] == 9:
            error_beep(st + 0.55 * D, 0.14)
    if act == "paper":
        rustle(st + 0.05, 0.7, 0.3)
        rustle(st + 0.6 * D, 0.5, 0.2)
    if act == "joy":
        for k in range(int(D / (1 / 1.6))):
            sfx(st + 0.15 + k / 1.6, whoosh(0.22, 0.12))
    if act == "write":
        for k in range(int(D / 1.1)):
            scribble(st + k * 1.1, 0.9)
    if "lightning" in sh.get("fx", []):
        sfx(st, wind(D + 0.3, 0.5))
        for p in (0.35, 0.47):
            sfx(st + p * D + 0.15, thunder(0.9 if p < 0.4 else 0.5))
    if "rain" in sh.get("fx", []):
        pass
    if act in ("gaze", "proud"):
        sfx(st, wind(D, 0.15))

# ================================================================== VOIX + MIXAGE
vo_env = np.zeros(N)
for s in SCENES:
    if s["vo_path"]:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", s["vo_path"], "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                             capture_output=True).stdout
        v = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
        i0 = int((s["start"] + timeline.VO_OFFSET) * SR)
        n = min(len(v), N - i0)
        VOX[i0:i0 + n] += v[:n]
        vo_env[i0:i0 + n] = 1
has_vo = vo_env.any()

# réverbération (musique + un peu de bruitages)
def reverb(x, t60=2.6, mix=0.3):
    d = t60
    ir = rng.standard_normal((int(d * SR), 2)) * np.exp(-np.arange(int(d * SR)) / SR * 6.9 / t60)[:, None]
    ir[:, 0] = lp(ir[:, 0], 5000)
    ir[:, 1] = lp(ir[:, 1], 5000)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], axis=1)
    return x * (1 - mix) + wet * mix * 1.6


MUS = reverb(MUS, 3.0, 0.35)
SFX = reverb(SFX, 1.4, 0.15)

# arrêt net à la toute fin
MUS[int((TOTAL - 0.05) * SR):] = 0
SFX[int((TOTAL + 0.05) * SR):] = 0

if has_vo:
    sm = lfilter([0.0015], [1, -0.9985], vo_env)  # enveloppe lissée
    sm = np.clip(sm / max(sm.max(), 1e-9), 0, 1)
    duck = 1 - 0.55 * sm
    mix = MUS * 0.55 * duck[:, None] + SFX * 0.55 * (1 - 0.35 * sm)[:, None] + VOX * 1.0
else:
    mix = MUS * 0.75 + SFX * 0.7

peak = np.max(np.abs(mix)) + 1e-9
mix = np.tanh(mix / peak * 1.3) / np.tanh(1.3) * 0.9
pcm = (mix * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("ok", sys.argv[1], "voix" if has_vo else "sans voix", round(TOTAL, 2))

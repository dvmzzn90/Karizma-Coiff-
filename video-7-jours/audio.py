"""Bande-son synthétique (musique + bruitages) pour la vidéo de 60 s.
Usage : python3 audio.py sortie.wav
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 60.0
N = int(SR * DUR)
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR


def sl(a, b):
    return slice(int(a * SR), min(N, int(b * SR)))


def env(n, att, rel):
    e = np.ones(n)
    a, r = int(att * SR), int(rel * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, cutoff):
    # filtre passe-bas 1 pôle (appliqué 2 fois)
    a = np.exp(-2 * np.pi * cutoff / SR)
    for _ in range(2):
        x = _onepole(x, a)
    return x


def _onepole(x, a):
    # y[n] = (1-a) x[n] + a y[n-1]  -- implémenté avec scipy si dispo, sinon boucle numpy par blocs
    try:
        from scipy.signal import lfilter
        return lfilter([1 - a], [1, -a], x)
    except ImportError:
        y = np.empty_like(x)
        acc = 0.0
        b = 1 - a
        for i in range(len(x)):
            acc = b * x[i] + a * acc
            y[i] = acc
        return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


L = np.zeros(N)
R = np.zeros(N)


def add(a, sig, gain=1.0, pan=0.0):
    i0 = int(a * SR)
    n = min(len(sig), N - i0)
    s = slice(i0, i0 + n)
    sig = sig[:n] * gain
    L[s] += sig * (1 - max(0, pan))
    R[s] += sig * (1 + min(0, pan))


def tone(freq, dur, kind="sin", detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    f = freq * (1 + detune)
    if kind == "saw":
        x = 2 * ((t * f) % 1) - 1
    elif kind == "tri":
        x = 2 * np.abs(2 * ((t * f) % 1) - 1) - 1
    else:
        x = np.sin(2 * np.pi * f * t)
    return x


def pad(freqs, dur, gain, att=1.0, rel=1.0, bright=900):
    n = int(dur * SR)
    x = np.zeros(n)
    for f in freqs:
        for d in (-0.004, 0.0, 0.004):
            x += tone(f, dur, "saw", d)
    x = lowpass(x, bright) / (len(freqs) * 3)
    return x * env(n, att, rel) * gain


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- MUSIQUE
# 0-5 s : nappe mystérieuse (Ré mineur) + petit arpège
add(0, pad([midi(50), midi(53), midi(57), midi(62)], 5.0, 0.55, 0.6, 0.05, 1200))
arp = [62, 65, 69, 72, 69, 65, 62, 65, 69, 74]
for i, m in enumerate(arp):
    n = tone(midi(m), 0.45, "tri") * env(int(0.45 * SR), 0.005, 0.4) * 0.12
    add(0.2 + i * 0.48, n, pan=0.3 if i % 2 else -0.3)
# bourdonnement électrique (scène « avant »)
hum = (tone(50, 5.0) * 0.5 + tone(100, 5.0) * 0.3 + tone(150, 5.0, "saw") * 0.05)
add(0, hum * env(len(hum), 0.5, 0.01) * 0.10)

# 5 s : COUPURE — chute de fréquence + clac
d = 0.9
t = np.arange(int(d * SR)) / SR
f = 220 * np.exp(-t * 3.5)
sweep = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.5)
add(5.0, sweep * 0.5)
clack = noise(0.06) * np.exp(-np.arange(int(0.06 * SR)) / SR * 60)
add(5.0, lowpass(clack, 3000) * 1.2)
# souffle grave d'impact
boom = lowpass(noise(1.5), 120) * env(int(1.5 * SR), 0.005, 1.4) * 2.5
add(5.0, boom)

# 6-40 s : drone inquiétant qui monte
drone_dur = 34.0
dn = pad([midi(38), midi(45), midi(50)], drone_dur, 0.5, 2.5, 1.0, 500)
grow = np.linspace(0.6, 1.3, len(dn))
add(6.0, dn * grow)
# dissonance qui s'installe (seconde mineure) à partir de 18 s
add(18.0, pad([midi(51), midi(63)], 22.0, 0.18, 3.0, 1.0, 700))
# pulsation type battement de cœur
for k in range(int((40 - 11) / 0.9)):
    tt = 11 + k * 0.9
    g = 0.25 + 0.35 * (tt - 11) / 29
    for off, gg in ((0, 1.0), (0.18, 0.6)):
        n = int(0.25 * SR)
        x = tone(55, 0.25) * np.exp(-np.arange(n) / SR * 18)
        add(tt + off, x * g * gg)
# tic-tac de l'horloge (32-40 s, jours qui défilent)
for k in range(int(8 / 0.25)):
    tt = 32 + k * 0.25
    n = int(0.03 * SR)
    x = highpass(noise(0.03), 2500) * np.exp(-np.arange(n) / SR * 200)
    add(tt, x * (0.35 if k % 2 == 0 else 0.22), pan=0.2 if k % 2 else -0.2)

# 40-48 s : montée (crescendo + riser)
add(40.0, pad([midi(50), midi(57), midi(62), midi(65)], 8.0, 0.45, 5.0, 0.2, 800))
rd = 8.0
t = np.arange(int(rd * SR)) / SR
riser = lowpass(noise(rd), 1500) * (t / rd) ** 2 * 0.35
f = 200 + 600 * (t / rd) ** 2
riser += np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / rd) ** 3 * 0.12
add(40.0, riser)
# petits « ding » de lumières qui se rallument
for tt, m in ((44.0, 81), (46.0, 84), (47.2, 88)):
    n = int(1.4 * SR)
    x = (tone(midi(m), 1.4) + 0.4 * tone(midi(m) * 2.01, 1.4)) * np.exp(-np.arange(n) / SR * 3)
    add(tt, x * 0.12, pan=0.4 if m == 84 else -0.3)

# 48-55 s : épique (Ré majeur → Si bémol → Do → Ré), percussions
chords = [[50, 57, 62, 66, 69], [46, 53, 58, 62, 65], [48, 55, 60, 64, 67], [50, 57, 62, 66, 69]]
for i, ch in enumerate(chords):
    add(48.0 + i * 1.75, pad([midi(m) for m in ch], 1.9, 0.55, 0.05, 0.3, 2200))
    add(48.0 + i * 1.75, tone(midi(ch[0] - 12), 1.75, "saw") * env(int(1.75 * SR), 0.01, 0.3) * 0.15)
for k in range(14):
    tt = 48.0 + k * 0.5
    n = int(0.4 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(60 + 120 * np.exp(-np.arange(n) / SR * 30)) / SR)
    kick *= np.exp(-np.arange(n) / SR * 9)
    add(tt, kick * 0.7)
    if k % 2:
        sn = highpass(noise(0.2), 1200) * np.exp(-np.arange(int(0.2 * SR)) / SR * 22)
        add(tt, sn * 0.25)
# remontée électrique (courant qui revient)
t = np.arange(int(1.2 * SR)) / SR
f = 40 + 200 * (t / 1.2) ** 1.5
up = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / 1.2) * 0.35
add(46.8, up)

# 55-60 s : mystérieux + impacts, arrêt net à 59.6 s
add(55.0, pad([midi(50), midi(53), midi(57), midi(61)], 4.6, 0.5, 0.05, 0.02, 1000))
for tt in (55.0, 57.4):
    add(tt, lowpass(noise(1.8), 150) * env(int(1.8 * SR), 0.003, 1.7) * 3.0)
    n = int(0.08 * SR)
    add(tt, lowpass(noise(0.08), 4000) * np.exp(-np.arange(n) / SR * 40) * 0.8)

# ---------------------------------------------------------------- AMBIANCES
# foule / rue (11-18 s)
crowd = lowpass(highpass(noise(7.0), 300), 1200)
crowd *= (1 + 0.5 * np.sin(2 * np.pi * 0.7 * np.arange(len(crowd)) / SR)) * env(len(crowd), 0.8, 0.8)
add(11.0, crowd * 0.18)
# sirène lointaine (13-18 s)
t = np.arange(int(5 * SR)) / SR
f = 700 + 250 * np.sign(np.sin(2 * np.pi * 0.8 * t))
siren = np.sin(2 * np.pi * np.cumsum(f) / SR)
add(13.0, lowpass(siren, 1500) * env(len(siren), 1.5, 1.5) * 0.06, pan=0.6)
# klaxons (14.2 et 15.1 s)
for tt in (14.2, 15.1):
    hk = (tone(400, 0.35, "saw") + tone(500, 0.35, "saw")) * env(int(0.35 * SR), 0.01, 0.05)
    add(tt, lowpass(hk, 2000) * 0.06, pan=-0.5)
# pas dans le magasin (18-21.5 s)
for k in range(8):
    tt = 18.1 + k * 0.42
    n = int(0.09 * SR)
    st = lowpass(noise(0.09), 900) * np.exp(-np.arange(n) / SR * 45)
    add(tt, st * 0.6, pan=0.25 if k % 2 else -0.25)
# « bip » d'erreur de caisse (22.6 et 23.4 s)
for tt in (22.6, 23.4):
    add(tt, tone(330, 0.25, "tri") * env(int(0.25 * SR), 0.005, 0.05) * 0.12)
# vent (25-40 s)
wd = 15.0
wind = lowpass(noise(wd), 500)
mod = 0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * np.arange(len(wind)) / SR) * np.sin(2 * np.pi * 0.31 * np.arange(len(wind)) / SR)
add(25.0, wind * mod * env(len(wind), 1.5, 2.0) * 0.55)
# tonnerre (30 s)
th = lowpass(noise(3.0), 200) * env(int(3.0 * SR), 0.05, 2.8)
th *= 1 + 0.6 * lowpass(np.abs(noise(3.0)), 8)
add(30.9, th * 2.2)

# transitions « whoosh »
for tt in (2.6, 11.0, 18.0, 25.0, 32.0, 40.0):
    d = 0.5
    t = np.arange(int(d * SR)) / SR
    w = highpass(noise(d), 600) * np.sin(np.pi * t / d) ** 2
    add(tt - 0.25, lowpass(w, 4000) * 0.18)

# ---------------------------------------------------------------- MIX
# silence quasi total juste après la coupure (5.0-5.8 s) sauf les bruitages déjà posés
# fin nette
end = sl(59.6, 60.0)
L[end] = 0
R[end] = 0
st = np.stack([L, R], axis=1)
peak = np.max(np.abs(st))
st = np.tanh(st / peak * 1.4) / np.tanh(1.4) * 0.89
pcm = (st * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("ok", sys.argv[1])

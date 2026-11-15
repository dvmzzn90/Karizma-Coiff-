"""Bande son : voix + effets sonores synthétisés + musique + mixage avec ducking.

Produit out/audio.wav (stéréo 48 kHz) et out/timings.json (mots minutés + évènements).
"""
import json, os
import numpy as np
from timeline import LINES, SR, DURATION
import voice

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
rng = np.random.default_rng(7)
N = int(DURATION * SR)


# ---------------------------------------------------------------- outils DSP
def T(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR)).astype(np.float32)


def filt(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-3
    m = np.ones_like(f)
    if lo:
        m /= np.sqrt(1 + (lo / f) ** (2 * order))
    if hi:
        m /= np.sqrt(1 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * m, len(x)).astype(np.float32)


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def phase(freq):
    return 2 * np.pi * np.cumsum(freq) / SR


def saw(ph):
    return 2 * ((ph / (2 * np.pi)) % 1) - 1


def env(n, a=0.01, r=0.2, d=None):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    rel = d if d is not None else n / SR
    e *= np.clip((rel - t) / max(r, 1e-4), 0, 1)
    return e.astype(np.float32)


def echo(x, taps=((0.25, 0.4), (0.5, 0.2)), tail=1.5):
    y = np.concatenate([x, np.zeros(int(tail * SR), np.float32)])
    out = y.copy()
    for dt, g in taps:
        k = int(dt * SR)
        out[k:] += y[:-k] * g
    return out


def reverb(x, size=1.2, mix=0.25):
    ir_t = T(size)
    ir = (rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 5 / size)).astype(np.float32)
    ir = filt(ir, hi=5000)
    n = len(x) + len(ir)
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[: len(x) + len(ir) - 1].astype(np.float32)
    y = norm(y, np.max(np.abs(x)) + 1e-9)
    out = np.zeros(len(y), np.float32)
    out[: len(x)] += x * (1 - mix)
    return out + y * mix


# ---------------------------------------------------------------- effets
def thump(f0=52, d=0.32, amp=1.0):
    t = T(d)
    s = np.sin(phase(f0 * (1 + 1.4 * np.exp(-t * 35)))) * np.exp(-t * 14)
    s += filt(noise(d), hi=180) * np.exp(-t * 50) * 0.25
    return (s * amp).astype(np.float32)


def heartbeat(amp=1.0):
    out = np.zeros(int(0.7 * SR), np.float32)
    a, b = thump(50, 0.32, 1.0), thump(46, 0.32, 0.7)
    out[: len(a)] += a
    k = int(0.27 * SR)
    out[k:k + len(b)] += b
    return norm(out, amp)


def boom(amp=1.0, d=3.0):
    t = T(d)
    s = np.sin(phase(28 + 70 * np.exp(-t * 6))) * np.exp(-t * 2.4)
    s = np.tanh(s * 2.2) * 0.8
    s += filt(noise(d), hi=300) * np.exp(-t * 4) * 0.6
    s += filt(noise(d), lo=2000) * np.exp(-t * 60) * 0.35  # transitoire
    return norm(reverb(s.astype(np.float32), 1.2, 0.18), amp)


def tear(d=0.8, amp=0.7):
    n = noise(d)
    rough = np.abs(filt(noise(d), hi=90)) ** 3
    s = filt(n, lo=1200, hi=7500) * norm(rough) * env(len(n), 0.05, 0.25)
    s += filt(noise(d), lo=300, hi=1500) * norm(rough) * 0.3
    return norm(s, amp)


def growl(d=1.4, f0=62, amp=0.8, bright=900):
    t = T(d)
    jit = norm(filt(noise(d), hi=6)) * 0.18
    f = f0 * (1 + jit)
    am = np.clip(0.55 + 2.5 * np.abs(filt(noise(d), lo=14, hi=34)), 0, 1.3)
    s = filt(saw(phase(f)) * am, lo=45, hi=bright) + filt(noise(d), lo=70, hi=bright * 0.7) * am * 0.5
    s *= env(len(t), 0.25, 0.5)
    return norm(s.astype(np.float32), amp)


def roar(d=1.6, amp=1.0):
    t = T(d)
    f = 85 + 70 * np.sin(np.pi * np.clip(t / d, 0, 1)) + norm(filt(noise(d), hi=8)) * 8
    am = np.clip(0.6 + 2.0 * np.abs(filt(noise(d), lo=20, hi=45)), 0, 1.4)
    s = filt(saw(phase(f)) * am, lo=80, hi=2600) + filt(noise(d), lo=200, hi=2200) * am * 0.7
    s *= env(len(t), 0.08, 0.6)
    return norm(reverb(s, 1.0, 0.2), amp)


def whoosh(d=0.55, amp=0.7, up=True):
    out = np.zeros(int(d * SR), np.float32)
    bands = [(250, 600), (500, 1100), (900, 2000), (1600, 3500), (3000, 6000)]
    if not up:
        bands = bands[::-1]
    t = T(d)
    for i, (lo, hi) in enumerate(bands):
        c = d * (0.25 + 0.5 * i / (len(bands) - 1))
        out += filt(noise(d), lo, hi) * np.exp(-((t - c) / (d * 0.18)) ** 2)
    return norm(out, amp)


def glitch(d=0.5, amp=0.45):
    out = []
    while sum(len(x) for x in out) < d * SR:
        k = rng.integers(int(0.015 * SR), int(0.06 * SR))
        typ = rng.integers(0, 3)
        if typ == 0:
            f = rng.uniform(200, 3000)
            x = np.sign(np.sin(2 * np.pi * f * np.arange(k) / SR)) * 0.6
        elif typ == 1:
            x = np.round(rng.standard_normal(k) * 3) / 3 * 0.5
            x = np.repeat(x[::8], 8)[:k]
        else:
            x = np.zeros(k)
        out.append(x.astype(np.float32))
    s = np.concatenate(out)[: int(d * SR)]
    return norm(filt(s, lo=150, hi=9000), amp)


def riser(d=4.5, amp=0.6):
    t = T(d)
    s = np.sin(phase(32 + 22 * t / d)) * 0.8 + np.sin(phase(64 + 44 * t / d)) * 0.25
    s += filt(noise(d), lo=300, hi=2500) * (t / d) ** 2 * 0.25
    return norm((s * (t / d) ** 1.6).astype(np.float32), amp)


def laugh(amp=0.25):
    out = np.zeros(int(0.7 * SR), np.float32)
    for i in range(4):
        d = 0.09
        s = filt(noise(d), 700, 2200) + np.sin(phase(np.full(int(d * SR), 190 - i * 8))) * 0.4
        s *= env(len(s), 0.01, 0.05)
        k = int(i * 0.14 * SR)
        out[k:k + len(s)] += s * (1 - i * 0.15)
    return norm(filt(out, hi=1800), amp)


def bark(amp=0.8):
    out = np.zeros(int(0.6 * SR), np.float32)
    for k0, f0 in ((0.0, 720), (0.24, 660)):
        d = 0.17
        t = T(d)
        f = f0 * (1 - 0.45 * t / d)
        s = filt(saw(phase(f)), 300, 3000) + filt(noise(d), 500, 3000) * 0.5
        s *= np.exp(-t * 14) * np.minimum(1, t / 0.005)
        k = int(k0 * SR)
        out[k:k + len(s)] += s
    return norm(reverb(out, 0.5, 0.15), amp)


def scratch(amp=0.7):
    d = 0.5
    t = T(d)
    f = 400 + 350 * np.sin(2 * np.pi * 3.2 * t) * np.exp(-t * 1.5)
    s = filt(saw(phase(f)) * 0.6 + noise(d) * 0.5, 250, 4500) * env(len(t), 0.005, 0.15)
    return norm(s.astype(np.float32), amp)


def chirp(amp=0.3, f0=None):
    f0 = f0 or rng.uniform(2500, 4200)
    out = []
    for _ in range(rng.integers(2, 5)):
        d = rng.uniform(0.04, 0.09)
        t = T(d)
        f = f0 * (1 + rng.uniform(0.2, 0.6) * t / d)
        out.append(np.sin(phase(f)) * np.sin(np.pi * t / d))
        out.append(np.zeros(int(rng.uniform(0.03, 0.08) * SR)))
    return norm(np.concatenate(out).astype(np.float32), amp)


def monkey(amp=0.4):
    out = []
    for i in range(3):
        d = 0.18 if i < 2 else 0.32
        t = T(d)
        f = (380 if i < 2 else 520) * (1 + 0.8 * t / d)
        s = sum(np.sin(phase(f * k)) / k for k in range(1, 6))
        out.append(filt(s, 300, 2500) * np.sin(np.pi * t / d))
        out.append(np.zeros(int(0.05 * SR)))
    return norm(np.concatenate(out).astype(np.float32), amp)


def alarm(d=6.5, amp=0.25):
    t = T(d)
    f = np.where((t % 1.0) < 0.5, 760, 600)
    s = filt(np.sign(np.sin(phase(f))) * 0.5, hi=1800)
    s = echo(s, ((0.3, 0.35), (0.6, 0.18)), 0.8)[: len(t)]
    return norm(s * env(len(t), 0.6, 0.6), amp)


def clack(amp=0.9):
    d = 0.9
    t = T(d)
    s = filt(noise(d), lo=1500) * np.exp(-t * 90)
    s += np.sin(phase(np.full(len(t), 60.0))) * np.exp(-t * 6) * 0.8
    crack = (rng.random(len(t)) < 0.004) * rng.standard_normal(len(t)) * np.exp(-t * 5)
    s += filt(crack.astype(np.float32), lo=800) * 1.5
    return norm(reverb(s.astype(np.float32), 0.8, 0.25), amp)


def hum(d=4.0, amp=0.25):
    t = T(d)
    s = sum(np.sin(2 * np.pi * f * t) * g for f, g in ((50, 1), (100, 0.6), (150, 0.35), (51.5, 0.5), (250, 0.15)))
    return norm((s * env(len(t), 0.3, 0.5)).astype(np.float32), amp)


def breath(amp=0.3):
    out = []
    for i in range(3):
        for dur, lvl in ((0.42, 1.0), (0.38, 0.7)):
            s = filt(noise(dur), 450, 2400) * np.sin(np.pi * T(dur) / dur) ** 1.5 * lvl
            out.append(s)
    return norm(np.concatenate(out).astype(np.float32), amp)


def wind(d, amp=0.3):
    slow = norm(filt(noise(d), hi=0.6)) * 0.4 + 0.6
    return norm(filt(noise(d), 80, 700) * slow, amp)


def river(d, amp=0.2):
    bub = 0.75 + 0.25 * norm(filt(noise(d), 8, 30))
    return norm(filt(noise(d), 250, 4500) * bub, amp)


def howl(d=3.4, amp=0.6):
    t = T(d)
    f = np.interp(t, [0, 0.9, 2.4, d], [360, 600, 590, 430]) + 7 * np.sin(2 * np.pi * 5.2 * t) * (t > 0.8)
    s = sum(np.sin(phase(f * k)) * g for k, g in ((1, 1), (2, 0.35), (3, 0.15), (4, 0.06)))
    s = filt(s * env(len(t), 0.5, 1.0), 250, 2600).astype(np.float32)
    s = echo(s, ((0.45, 0.35), (0.9, 0.2), (1.4, 0.1)), 2.0)
    return norm(filt(s, hi=2200), amp)


def branches(amp=0.4):
    out = np.zeros(int(0.8 * SR), np.float32)
    for k0 in (0.0, 0.11, 0.35, 0.5):
        d = 0.05
        s = filt(noise(d), lo=900) * np.exp(-T(d) * 120)
        k = int(k0 * SR)
        out[k:k + len(s)] += s
    return norm(out, amp)


# ---------------------------------------------------------------- musique
def note_hz(n):
    return 440 * 2 ** ((n - 69) / 12)


def piano(n, d=2.4, amp=0.3):
    t = T(d)
    f = note_hz(n)
    s = np.zeros(len(t))
    for k in range(1, 9):
        fk = f * k * (1 + 0.0004 * k * k)
        s += np.sin(2 * np.pi * fk * t) / k ** 1.4 * np.exp(-t * (1.2 + 0.7 * k))
    s *= np.minimum(1, t / 0.004)
    return (norm(s) * amp).astype(np.float32)


def pad(notes, d, amp=0.2, attack=1.5, bright=1600):
    t = T(d)
    s = np.zeros(len(t))
    for n in notes:
        for det in (-0.0035, 0, 0.004):
            s += saw(phase(np.full(len(t), note_hz(n) * (1 + det))))
    s = filt(s.astype(np.float32), hi=bright, order=2)
    s *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    return norm(s * env(len(t), attack, 1.2), amp)


def tension_music():
    """5 s → 37.6 s : basses, percussions hybrides, 120 BPM (grille alignée sur les coupes)."""
    m = np.zeros(N, np.float32)
    beat = 0.5
    start, stop = 5.0, 37.6
    # drone
    d = stop - start
    t = T(d)
    drone = sum(saw(phase(np.full(len(t), note_hz(n) * (1 + det)))) for n in (33, 40) for det in (-0.003, 0.003))
    drone = filt(drone.astype(np.float32), hi=260)
    lvl = np.interp(t + start, [5, 7, 17, 20, 24, 31, 34, 37.6], [0.3, 0.55, 0.6, 0.35, 0.75, 0.8, 0.45, 0.6])
    m[int(start * SR): int(start * SR) + len(t)] += norm(drone) * 0.22 * lvl
    # percussions
    taiko = thump(48, 0.6, 1.0)
    taiko = norm(taiko + filt(noise(0.6), 80, 400) * np.exp(-T(0.6) * 25) * 0.4, 1)
    hat = filt(noise(0.05), lo=6000) * np.exp(-T(0.05) * 80)
    k = 0
    tt = start
    while tt < stop - 0.05:
        i = int(tt * SR)
        quiet = 17.0 <= tt < 24.0 or 33.5 <= tt
        if k % 4 in (0, 3) or (k % 8 == 6 and tt > 24):
            g = 0.25 if quiet else 0.55
            seg = taiko[: N - i]
            m[i:i + len(seg)] += seg * g
        if not (31 <= tt) and tt > 7.5:
            for sub in (0, 0.25):
                j = int((tt + sub) * SR)
                m[j:j + len(hat)] += hat[: N - j] * (0.05 if quiet else 0.11)
        k += 1
        tt += beat
    # pulsation de basse sur les temps (plan 5)
    for b in np.arange(24.0, 31.0, 0.25):
        s = np.sin(phase(np.full(int(0.2 * SR), 55.0))) * np.exp(-T(0.2) * 18) * 0.18
        i = int(b * SR)
        m[i:i + len(s)] += s
    m[int(stop * SR):] = 0
    return m


def emotional_music():
    """38 s → 53 s : piano + cordes, lumineux, crescendo, coupure nette à 53 s."""
    m = np.zeros(N, np.float32)
    start, stop = 38.0, 53.0
    prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62])]  # Am F C G
    bar = 2.4
    t0 = start + 0.15
    i_bar = 0
    while t0 < stop:
        root, chord = prog[i_bar % 4]
        swell = 0.55 + 0.45 * np.clip((t0 - 45) / 7, 0, 1)
        p = pad([root - 12] + chord + ([chord[1] + 12] if t0 > 46 else []), bar + 1.2, 0.16 * swell, 0.9,
                1300 + 1200 * np.clip((t0 - 45) / 7, 0, 1))
        i = int(t0 * SR)
        m[i:i + len(p)] += p[: N - i]
        arp = chord + [chord[0] + 12, chord[1] + 12]
        for j, n in enumerate(arp + arp[::-1][1:3]):
            tn = t0 + j * bar / 7
            if tn >= stop:
                break
            pn = piano(n + 12, 2.2, 0.16)
            k = int(tn * SR)
            m[k:k + len(pn)] += pn[: N - k]
        pb = piano(root - 12, 2.6, 0.2)
        k = int(t0 * SR)
        m[k:k + len(pb)] += pb[: N - k]
        t0 += bar
        i_bar += 1
    m = reverb(m[int(start * SR):int(stop * SR) + SR], 2.4, 0.35)
    out = np.zeros(N, np.float32)
    i = int(start * SR)
    out[i:i + len(m)] += m[: N - i]
    out[:int((start + 0.0) * SR)] *= 0
    fade = np.clip((np.arange(N) / SR - start) / 1.2, 0, 1)
    out *= fade
    out[int(stop * SR):] = 0   # la musique s'arrête d'un coup
    return out


# ---------------------------------------------------------------- mixage
def place(buf, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    seg = x[: len(buf) - i] * g
    buf[i:i + len(seg)] += seg


def wt(words, key, which=0, edge="start"):
    clean = lambda x: x.lower().strip(".,?…:! ").replace("’", "'")
    hits = [w for w in words if clean(w["w"]) == clean(key)]
    return hits[which][edge]


def build():
    v, words = voice.build()
    v = v[:N]
    v = reverb(v, 0.6, 0.12)[:N] * 1.0
    v = norm(v, 0.9)

    sfx = np.zeros(N, np.float32)      # effets atténués sous la voix
    hero = np.zeros(N, np.float32)     # impacts calés sur les mots-clés (non atténués)
    ev = {}

    g = lambda k, i=0, e="start": wt(words, k, i, e)
    # PLAN 1
    for k, tb in enumerate([0.25, 1.05, 1.8, 2.5, 3.15, 3.75]):
        place(sfx, heartbeat(0.9), tb)
    ev["tear"] = 2.0
    place(sfx, tear(0.9, 0.55), ev["tear"])
    ev["griffes"] = g("griffes")
    ev["eye_open"] = ev["griffes"] - 0.05
    place(sfx, growl(1.6, 58, 0.35), ev["griffes"] - 1.0)
    place(hero, boom(1.0), ev["griffes"])
    # PLAN 2
    place(hero, whoosh(0.6, 0.6), 4.75)
    place(sfx, glitch(0.55, 0.4), 5.55)
    place(sfx, glitch(0.25, 0.3), 8.1)
    place(sfx, riser(4.6, 0.35), 5.2)
    place(hero, whoosh(0.5, 0.45, False), 7.3)
    # PLAN 3
    ev["lion"] = g("lion.")
    ev["paresseux"] = g("paresseux.")
    ev["toi"] = g("toi…")
    place(sfx, glitch(0.25, 0.35), 9.9)
    place(hero, roar(1.3, 0.75), ev["lion"] - 0.05)
    place(hero, whoosh(0.4, 0.4), 12.0)
    place(sfx, laugh(0.32), ev["paresseux"] + 0.55)
    place(hero, whoosh(0.4, 0.4), 13.8)
    place(hero, bark(0.6), 14.05)
    place(hero, scratch(0.75), ev["toi"] - 0.04)
    # PLAN 4 : cacophonie qui se coupe net sur « cris »
    ev["cris"] = g("cris.")
    caco = np.zeros(N, np.float32)
    tt = 17.0
    while tt < ev["cris"] + 0.4:
        r = rng.random()
        x = chirp(0.25) if r < 0.4 else monkey(0.3) if r < 0.65 else bark(0.25) if r < 0.85 else growl(0.6, 90, 0.2, 1400)
        place(caco, x, tt)
        tt += rng.uniform(0.07, 0.22)
    ring = np.zeros(int(1.0 * SR), np.float32)
    tr = T(1.0)
    ring += (np.sin(2 * np.pi * 1400 * tr) + np.sin(2 * np.pi * 1750 * tr)) * ((tr % 0.25) < 0.12) * 0.3
    for t0 in (19.5, 20.6, 21.7):
        place(caco, ring + filt(noise(1.0), 100, 300) * 0.25 * ((tr % 0.1) < 0.05), t0, 0.6)
    lvl = np.clip((np.arange(N) / SR - 17.0) / 0.6, 0, 1)
    caco *= lvl * 0.5
    cut = int((ev["cris"] + 0.12) * SR)
    caco[cut:] = 0
    sfx += caco
    place(hero, whoosh(0.5, 0.35), 16.75)
    # PLAN 5
    ev["eteignent"] = g("s'éteignent.")
    place(sfx, alarm(7.0, 0.22), 24.0)
    place(hero, clack(0.9), ev["eteignent"])
    place(sfx, hum(5.5, 0.22), ev["eteignent"] + 0.6)
    place(sfx, glitch(0.3, 0.35), 23.85)
    place(hero, whoosh(0.4, 0.35), 26.3)
    ev["centrales"] = g("centrales…")
    # PLAN 6
    for i, tb in enumerate(np.cumsum([0.8, 0.75, 0.7, 0.64, 0.58, 0.52, 0.46, 0.42, 0.38, 0.35, 0.32, 0.3, 0.28, 0.27, 0.26])):
        place(sfx, heartbeat(0.75), 31.0 + tb)
    place(sfx, breath(0.32), 33.4)
    place(sfx, growl(2.4, 55, 0.4, 600), 34.8)
    place(hero, whoosh(0.4, 0.35, False), 30.75)
    ev["diner"] = g("dîner.")
    ev["tigre"] = g("tigre…")
    # silence brutal : tout coupé après « dîner »
    silence_at = ev["diner"] + 0.35
    # PLAN 7
    place(sfx, wind(8.0, 0.18), 38.0)
    place(sfx, river(8.0, 0.12), 40.5)
    for tb in np.arange(38.4, 46.0, 0.45):
        place(sfx, chirp(0.18), tb + rng.uniform(0, 0.3))
    place(hero, whoosh(0.6, 0.3), 42.8)
    # PLAN 8
    place(sfx, howl(3.4, 0.5), 46.15)
    place(sfx, branches(0.45), 48.6)
    place(sfx, branches(0.35), 50.4)
    place(sfx, wind(7.0, 0.12), 46.0)
    # PLAN 9 : la musique s'arrête, un seul battement, puis le vent
    place(hero, heartbeat(1.0), 53.02)
    place(sfx, wind(7.0, 0.3), 54.0)
    # PLAN 10
    place(sfx, growl(1.6, 52, 0.4, 500), 59.7)
    place(hero, boom(1.0, 3.5), 63.6)
    ev["final_boom"] = 63.6
    ev["heartbeats_p1"] = [0.25, 1.05, 1.8, 2.5, 3.15, 3.75]

    music = tension_music() + emotional_music()
    # silence brutal sur « dîner »
    i = int(silence_at * SR)
    music[i:int(38.0 * SR)] = 0
    sfx[i:int(38.0 * SR)] *= 0
    hero[i:int(38.0 * SR)] *= 0
    # le plan 1 commence dans le silence total
    music[: int(4.8 * SR)] = 0

    # ducking : la voix toujours au premier plan
    blk = 480
    nb = N // blk
    e = np.abs(v[: nb * blk]).reshape(nb, blk).max(1)
    e = e / (e.max() + 1e-9)
    env_b = np.zeros(nb, np.float32)
    cur = 0.0
    for i in range(nb):
        cur = e[i] if e[i] > cur else cur * 0.965  # relâchement ~300 ms
        env_b[i] = cur
    e = np.repeat(env_b, blk)
    e = np.concatenate([e, np.zeros(N - len(e), np.float32)])
    duck = np.clip(e * 1.6, 0, 1)
    mix_mono = v * 1.0 + music * (1 - 0.7 * duck) * 0.42 + sfx * (1 - 0.65 * duck) * 0.4 + hero * (1 - 0.45 * duck) * 0.8

    bg = mix_mono - v
    blk = SR // 2
    rep = []
    for b in range(N // blk):
        sl = slice(b * blk, (b + 1) * blk)
        rv, rb = np.sqrt((v[sl] ** 2).mean()) + 1e-9, np.sqrt((bg[sl] ** 2).mean()) + 1e-9
        if rv > 0.02:
            rep.append((round(20 * np.log10(rv / rb), 1), b / 2))
    rep.sort()
    print("voix/fond (dB) : pires", rep[:6], "médiane", rep[len(rep) // 2][0])
    # stéréo : légère largeur sur musique et effets
    wide = filt(music + sfx * 0.6, lo=200)
    dl = int(0.012 * SR)
    left = mix_mono + 0.25 * wide
    right = mix_mono + 0.25 * np.concatenate([np.zeros(dl, np.float32), wide[:-dl]])
    st = np.stack([left, right], 1)
    st = np.tanh(st / np.max(np.abs(st)) * 1.4) * 0.95
    os.makedirs(OUT, exist_ok=True)
    voice.write_wav_st(os.path.join(OUT, "audio.wav"), st)
    voice.write_wav(os.path.join(OUT, "voice_only.wav"), v)
    json.dump(dict(words=words, events=ev,
                   lines=[dict(start=l["start"], end=l.get("end"), kw=l["kw"]) for l in LINES]),
              open(os.path.join(OUT, "timings.json"), "w"), ensure_ascii=False, indent=1)
    print("audio ok", len(words), "mots")


def _write_wav_st(path, a):
    import wave
    a = np.clip(a, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


voice.write_wav_st = _write_wav_st

if __name__ == "__main__":
    build()

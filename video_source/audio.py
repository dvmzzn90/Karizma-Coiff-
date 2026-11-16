"""Synthesized sound design for the stickman classroom cartoon."""
import numpy as np, os, sys
from scipy import signal
from scipy.io import wavfile

SR = 44100
DUR = 35.0
N = int(SR * DUR)
rng = np.random.default_rng(3)
mix = np.zeros((N, 2))

def add(x, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N: return
    x = x[:N - i]
    l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
    mix[i:i + len(x), 0] += x * gain * l * 1.414
    mix[i:i + len(x), 1] += x * gain * r * 1.414

def tt(d): return np.arange(int(d * SR)) / SR

def bp(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band'); return signal.lfilter(b, a, x)
def lp(x, f, order=2):
    b, a = signal.butter(order, f / (SR / 2)); return signal.lfilter(b, a, x)
def hp(x, f, order=2):
    b, a = signal.butter(order, f / (SR / 2), 'high'); return signal.lfilter(b, a, x)
def peak(x, f, q):
    b, a = signal.iirpeak(f / (SR / 2), q); return signal.lfilter(b, a, x)

def saw_from_f0(f0):
    ph = np.cumsum(f0) / SR
    return 2 * (ph % 1.0) - 1, ph

def norm(x): return x / (np.max(np.abs(x)) + 1e-9)

# ------------------------------------------------------------ room tone
room = lp(rng.standard_normal(N), 400) * 0.004
mix[:, 0] += room; mix[:, 1] += room

# ------------------------------------------------------------ music (pizzicato, Karplus-Strong)
def pluck(freq, d=0.45):
    n = int(d * SR); p = int(SR / freq)
    buf = rng.uniform(-1, 1, p); out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.994
    return out * np.exp(-tt(d) * 6)

NOTE = {n: 261.63 * 2 ** (k / 12) for k, n in enumerate(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}
def f(n, o=0): return NOTE[n] * 2 ** o
melody = [('C', 0), ('E', 0), ('G', 0), ('E', 0), ('F', 0), ('A', 0), ('G', 0), (None, 0),
          ('E', 0), ('G', 0), ('C', 1), ('G', 0), ('A', 0), ('F', 0), ('D', 0), (None, 0)]
bass = [('C', -1), ('F', -1), ('G', -2), ('C', -1)]
cache = {}
def note(n, o, d=0.45):
    k = (n, o, d)
    if k not in cache: cache[k] = pluck(f(n, o), d)
    return cache[k]
def music(t0, t1, gain):
    step = 0.2; i = 0; t = t0
    while t < t1 - 0.1:
        n, o = melody[i % len(melody)]
        if n: add(note(n, o), t, gain * 0.5, -0.2)
        if i % 4 == 0:
            bn, bo = bass[(i // 4) % len(bass)]; add(note(bn, bo, 0.8), t, gain * 0.7, 0.2)
        t += step; i += 1
music(0.0, 5.75, 0.18)

# ------------------------------------------------------------ clock ticks
tick = bp(rng.standard_normal(int(0.03 * SR)), 2000, 6000) * np.exp(-tt(0.03) * 200)
for k in range(5): add(tick, 0.4 + k, 0.10, 0.4)
for k in range(4): add(tick, 15.3 + k * 0.8, 0.22, 0.4)

# ------------------------------------------------------------ chalk
def chalk(t0, t1):
    t = t0
    while t < t1:
        d = rng.uniform(0.08, 0.18)
        x = bp(rng.standard_normal(int(d * SR)), 2500, 7000)
        x *= (1 + 0.8 * np.sin(2 * np.pi * rng.uniform(25, 40) * tt(d))) * np.hanning(len(x))
        add(x, t, 0.05, -0.3)
        t += d + rng.uniform(0.03, 0.1)
chalk(0.6, 3.8); chalk(13.0, 13.25); chalk(18.6, 19.55)

# ------------------------------------------------------------ fart
def fart(d=1.15):
    t = tt(d)
    f0 = 78 + 25 * np.sin(2 * np.pi * 5.5 * t) + 18 * lp(rng.standard_normal(len(t)), 30) * 8 - 18 * t
    f0 = np.clip(f0, 35, 160)
    ph = np.cumsum(f0) / SR
    pulse = ((ph % 1.0) < 0.18).astype(float) - 0.18
    flutter = 0.6 + 0.4 * np.clip(lp(rng.standard_normal(len(t)), 25) * 10, -1, 1)
    x = lp(pulse * flutter, 900, 2) + 0.15 * lp(rng.standard_normal(len(t)), 1500)
    env = np.minimum(1, t / 0.02) * np.where(t < d - 0.25, 1, np.clip((d - t) / 0.25, 0, 1))
    x = norm(x * env)
    tail = bp(rng.standard_normal(int(0.22 * SR)), 300, 1800) * np.exp(-tt(0.22) * 12)
    return np.concatenate([x, 0.6 * norm(tail)])
add(fart(), 5.88, 0.9, -0.1)

# ------------------------------------------------------------ snorts / stifled laugh
def snort(d=0.12):
    x = bp(rng.standard_normal(int(d * SR)), 500, 2200) * np.hanning(int(d * SR))
    v, _ = saw_from_f0(np.full(int(d * SR), 230.0))
    return norm(x + 0.3 * lp(v, 600) * np.hanning(int(d * SR)))
def hum_held(t0, d):  # 'mmm' trembling held laugh
    t = tt(d)
    f0 = 260 + 30 * np.sin(2 * np.pi * 9 * t) + 15 * np.sin(2 * np.pi * 3 * t)
    v, _ = saw_from_f0(f0)
    x = lp(peak(v, 280, 3), 500) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 4.5 * t))) * np.hanning(len(t))
    add(norm(x), t0, 0.12, 0.25)
hum_held(7.4, 1.4); hum_held(9.4, 1.6); hum_held(11.2, 1.7)
for ts in (10.6, 11.0, 12.3, 12.7, 19.2, 19.45): add(snort(), ts, 0.25, 0.25)

# ------------------------------------------------------------ suspicious sting
def tone(freq, d, kind='tri'):
    t = tt(d)
    if kind == 'tri': x = signal.sawtooth(2 * np.pi * freq * t, 0.5)
    else: x = np.sin(2 * np.pi * freq * t)
    return x * np.exp(-t * 3) * np.minimum(1, t / 0.01)
add(tone(98, 0.6) + 0.5 * tone(196, 0.6), 14.45, 0.35)
add(tone(92.5, 0.9) + 0.5 * tone(185, 0.9), 14.85, 0.35)

# whoosh for turns
def whoosh(d=0.4, lo=300, hi=3000):
    t = tt(d); x = rng.standard_normal(len(t)); out = np.zeros_like(x)
    seg = 512
    for i in range(0, len(x), seg):
        fc = lo * (hi / lo) ** (i / len(x))
        out[i:i + seg] = bp(x[max(0, i - 2048):i + seg], fc * 0.7, min(fc * 1.4, 20000))[-len(x[i:i + seg]):]
    return out * np.sin(np.pi * t / d)
add(whoosh(0.8, 200, 1500), 13.6, 0.12)
add(whoosh(0.5, 300, 2500), 17.85, 0.1)
add(whoosh(0.25, 500, 4000), 24.95, 0.15)

# 'Hmm...' teacher voice
def hmm(d=0.95):
    t = tt(d)
    f0 = 125 + 20 * np.sin(np.pi * t / d) - 10 * t
    v, _ = saw_from_f0(f0)
    x = lp(peak(v, 250, 2) + 0.3 * peak(v, 900, 4), 700)
    env = np.minimum(1, t / 0.06) * np.clip((d - t) / 0.3, 0, 1)
    return norm(x * env)
add(hmm(), 16.85, 0.35)

# ------------------------------------------------------------ laughter
def ha_bout(f0, n, rate, open_=1.0):
    syl = []
    for i in range(n):
        d = 1.0 / rate
        t = tt(d)
        fi = f0 * (1.0 - 0.18 * i / max(1, n - 1)) * rng.uniform(0.96, 1.04)
        fc = fi * (1 + 0.05 * np.sin(2 * np.pi * 7 * t)) * (1 - 0.15 * t / d)
        v, _ = saw_from_f0(fc)
        F1, F2, F3 = 800 * open_, 1250, 2700
        voiced = peak(v, F1, 5) + 0.6 * peak(v, F2, 6) + 0.25 * peak(v, F3, 8)
        hpos = 0.035
        breath = bp(rng.standard_normal(len(t)), 900, 3500)
        venv = np.clip((t - hpos) / 0.012, 0, 1) * np.exp(-np.clip(t - hpos, 0, None) * 14)
        benv = np.exp(-((t - 0.02) / 0.02) ** 2)
        syl.append(voiced * venv + 0.5 * breath * benv)
    x = np.concatenate(syl)
    inhale = bp(rng.standard_normal(int(0.28 * SR)), 1500, 5000) * np.hanning(int(0.28 * SR)) * 0.25
    return norm(np.concatenate([x, inhale]))

def laugher(t0, t1, f0, gain, pan, rate=6.0):
    t = t0
    while t < t1:
        n = int(rng.integers(5, 10))
        b = ha_bout(f0 * rng.uniform(0.95, 1.08), n, rate * rng.uniform(0.9, 1.1), rng.uniform(0.85, 1.1))
        dur = len(b) / SR
        if t + dur > t1:
            b = b[:int((t1 - t) * SR)]
            b *= np.minimum(1, (len(b) - np.arange(len(b))) / (0.05 * SR))
        add(b, t, gain, pan)
        t += dur + rng.uniform(0.05, 0.3)

LAUGH_END = 30.25
laugher(19.6, LAUGH_END, 300, 0.30, 0.15, 6.5)  # buddy
starts = [20.3, 20.9, 20.98, 21.5, 21.58, 21.66, 21.74, 21.82, 22.1, 22.18]
pitches = [260, 330, 230, 360, 290, 210, 310, 380, 250, 340]
for k, (st, p) in enumerate(zip(starts, pitches)):
    laugher(st, LAUGH_END, p, 0.15, rng.uniform(-0.8, 0.8), rng.uniform(5.0, 7.0))
# cut laughter on the final scene (between 26.2 and 27.9 they keep laughing too)

# record scratch at the teacher's surprised turn
def scratch(d=0.35):
    t = tt(d); fc = 900 + 700 * np.sin(2 * np.pi * 9 * t)
    x = rng.standard_normal(len(t)); out = np.zeros_like(x); seg = 256
    for i in range(0, len(x), seg):
        f_ = fc[i]; out[i:i + seg] = bp(x[max(0, i - 1024):i + seg], f_ * 0.8, f_ * 1.25)[-len(x[i:i + seg]):]
    return norm(out) * np.hanning(len(t))
add(scratch(), 24.98, 0.25)

# ------------------------------------------------------------ escape
add(whoosh(0.35, 400, 3500), 27.9, 0.2, 0.3)
step = lp(rng.standard_normal(int(0.05 * SR)), 700) * np.exp(-tt(0.05) * 80)
t = 28.15; k = 0
while t < 29.8:
    add(norm(step), t, 0.22, -0.4 + 0.8 * (t - 28.15) / 1.7); t += 0.11; k += 1
# door slam
def slam():
    d = 0.7; t = tt(d)
    thump = np.sin(2 * np.pi * (70 - 25 * t) * t) * np.exp(-t * 9)
    crack = lp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 25)
    rattle = bp(rng.standard_normal(len(t)), 1500, 4000) * np.exp(-t * 6) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * t)))
    return norm(thump + 0.7 * crack + 0.08 * rattle)
add(slam(), 30.0, 1.0, 0.5)

# crickets in the awkward silence
def chirp():
    d = 0.18; t = tt(d)
    x = np.sin(2 * np.pi * 4600 * t) * (np.sin(2 * np.pi * 33 * t) > 0) * np.hanning(len(t))
    return x
for k in range(5): add(chirp(), 30.55 + k * 0.42, 0.05, 0.6)

# final boom
def boom():
    d = 2.2; t = tt(d)
    x = np.sin(2 * np.pi * (110 * np.exp(-t * 1.5) + 35) * t) * np.exp(-t * 1.8)
    x += 0.3 * lp(rng.standard_normal(len(t)), 300) * np.exp(-t * 6)
    return norm(x)
add(boom(), 31.2, 0.9)
add(tone(523.25, 0.8, 'sine') * 0.5 + tone(392, 0.8, 'sine') * 0.5, 31.55, 0.15)

# ------------------------------------------------------------ reverb + master
ir_t = tt(0.5); ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 9); ir /= np.sqrt(np.sum(ir ** 2))
for ch in range(2):
    wet = signal.fftconvolve(mix[:, ch], ir)[:N]
    mix[:, ch] = mix[:, ch] + 0.18 * wet
mix = hp(mix.T, 30).T
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6) / np.tanh(1.6) * 0.9
fade = np.ones(N); fade[-int(0.6 * SR):] = np.linspace(1, 0, int(0.6 * SR))
mix *= fade[:, None]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'audio.wav')
wavfile.write(out, SR, (mix * 32767).astype(np.int16))
print('ok', out)

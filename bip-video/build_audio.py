#!/usr/bin/env python3
"""Bip — « L'argent est déjà chez toi »
Génère : la voix (espeak-ng + MBROLA fr1, effet robot discret), la musique
funky électronique, les bruitages, le mixage final (audio.wav) et la
timeline partagée avec l'animation (timeline.js).

Usage : python3 build_audio.py
"""
import json
import os
import subprocess
import tempfile
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 44100
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "build")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)

# ---------------------------------------------------------------- script
# "|" = pause comique. *mot* = mot-clé en jaune dans les sous-titres.
# Le texte parlé (say) peut différer de l'affichage pour améliorer la diction.
SCENES = [
    dict(id="hook", lead=0.55, tail=0.35, lines=[
        dict(say="Tu veux faire de l'argent facilement ?|Regarde cette vidéo.",
             sub="Tu veux faire de l'*argent* *facilement* ?|Regarde cette *vidéo.*")]),
    dict(id="plant", lead=0.45, tail=0.9, lines=[
        dict(say="J'ai essayé de faire pousser de l'argent...",
             sub="J'ai essayé de faire *pousser* de l'*argent…*")]),
    dict(id="shake", lead=0.7, tail=0.6, lines=[
        dict(say="J'ai même vérifié mes poches internes...",
             sub="J'ai même vérifié mes *poches* *internes…*")]),
    dict(id="scam", lead=1.75, tail=0.6, lines=[
        dict(say="Et ça...|plus jamais.",
             sub="Et ça…|*plus* *jamais.*")]),
    dict(id="reveal", lead=2.25, tail=0.8, lines=[
        dict(say="Attends...|et si l'argent était déjà...|chez moi ?",
             sub="Attends…|et si l'*argent* était déjà…|*chez* *moi* ?")]),
    dict(id="step1", lead=0.55, tail=0.45, lines=[
        dict(say="Un :|tu fais le tour de chez toi.|Tout ce que tu n'as pas utilisé depuis un an, tu le mets de côté.",
             sub="*Un* :|tu fais le *tour* de *chez* *toi.*|Tout ce que tu n'as pas *utilisé* depuis *un* *an,* tu le mets de *côté.*")]),
    dict(id="step2", lead=0.55, tail=0.45, lines=[
        dict(say="Deux :|tu prends de belles photos, à la lumière du jour.|Une bonne photo, ça vend deux fois plus vite.",
             sub="*Deux* :|tu prends de belles *photos,* à la *lumière* *du* *jour.*|Une bonne photo, ça vend *deux* *fois* *plus* *vite.*")]),
    dict(id="step3", lead=0.55, tail=2.1, lines=[
        dict(say="Trois :|tu mets en vente sur une appli de revente, avec un prix un peu en dessous des autres.|Et là...",
             sub="*Trois* :|tu mets en vente sur une *appli* *de* *revente,* avec un *prix* un peu *en* *dessous* des autres.|Et là…")]),
    dict(id="outro", lead=0.45, tail=0.3, lines=[
        dict(say="Zéro investissement,|zéro arnaque.|Juste ton placard qui travaille pour toi.",
             sub="*Zéro* *investissement,*|*zéro* *arnaque.*|Juste ton *placard* qui *travaille* pour toi.")]),
    dict(id="tie", lead=2.75, tail=0.55, lines=[
        dict(say="...|Elle aussi,|je la vends.",
             sub="…|Elle aussi,|je la *vends.*")]),
    dict(id="final", lead=0.35, tail=1.5, lines=[
        dict(say="Abonne-toi,|je te montre la suite pour aller encore plus loin !",
             sub="*Abonne-toi,*|je te montre la *suite* pour aller *encore* *plus* *loin* !")]),
]
PAUSE = 0.2  # silence pour chaque "|"


# ---------------------------------------------------------------- helpers
def read_wav(path):
    with wave.open(path) as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    assert sr == SR, sr
    return data


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def tt(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=None, d=None):
    """Attack + exponential decay envelope."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    if d:
        e *= np.exp(-t / d)
    return e


def lp(x, f, order=2):
    b, a = butter(order, min(f, SR / 2 - 100) / (SR / 2), "low")
    return lfilter(b, a, x)


def hp(x, f, order=2):
    b, a = butter(order, f / (SR / 2), "high")
    return lfilter(b, a, x)


def bp(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], "band")
    return lfilter(b, a, x)


def add(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


# ---------------------------------------------------------------- voice
# VOICE=tom (défaut) : voix neuronale Piper « Tom » (fr_FR, medium, 44,1 kHz),
#                      masculine, claire, sans effet — priorité à la compréhension.
# VOICE=mbrola       : ancienne voix espeak-ng + MBROLA fr1 (effet robot).
VOICE = os.environ.get("VOICE", "tom")
PIPER_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fr_FR-tom-medium.tar.bz2"
PIPER_DIR = os.path.join(HERE, "voices")
PIPER_MODEL = os.path.join(PIPER_DIR, "vits-piper-fr_FR-tom-medium", "fr_FR-tom-medium.onnx")


def ensure_piper():
    if not os.path.exists(PIPER_MODEL):
        os.makedirs(PIPER_DIR, exist_ok=True)
        tgz = os.path.join(PIPER_DIR, "voice.tar.bz2")
        subprocess.run(["curl", "-sSL", "-o", tgz, PIPER_URL], check=True)
        subprocess.run(["tar", "xjf", tgz, "-C", PIPER_DIR], check=True)
        os.remove(tgz)


def tts(text, path):
    raw = path + ".raw.wav"
    if VOICE == "mbrola":
        subprocess.run(["espeak-ng", "-v", "mb-fr1", "-s", "156", "-p", "58", "-a", "110",
                        "-w", raw, text], check=True)
        af = ("asetrate=16000*1.07,aresample=44100,atempo=0.9346,"
              "highpass=f=110,lowpass=f=7600,aecho=0.85:0.55:5:0.22,"
              "equalizer=f=2800:t=q:w=1.2:g=3")
    else:
        ensure_piper()
        # Réglages pour la clarté : débit naturel, variations modérées (pas monotone).
        subprocess.run(["python3", "-m", "piper", "-m", PIPER_MODEL, "-f", raw,
                        "--length-scale", "1.0", "--noise-scale", "0.5", "--noise-w", "0.6",
                        "--sentence-silence", "0.15"],
                       input=text.encode(), check=True, capture_output=True)
        # Traitement « voix off » propre : coupe-bas, présence pour les consonnes,
        # compression douce pour un niveau régulier. Aucun effet de déformation.
        af = ("aresample=44100,highpass=f=75,"
              "equalizer=f=250:t=q:w=1.0:g=-2,equalizer=f=3500:t=q:w=1.2:g=3,"
              "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw, "-af", af,
                    "-ac", "1", "-ar", str(SR), path], check=True)
    x = read_wav(path)
    idx = np.where(np.abs(x) > 0.01)[0]
    if len(idx):
        x = x[max(0, idx[0] - 200): idx[-1] + 1500]
    return x / (np.max(np.abs(x)) + 1e-9) * 0.92


def trim(x):
    idx = np.where(np.abs(x) > 0.02 * np.max(np.abs(x)))[0]
    return x[max(0, idx[0] - 200): idx[-1] + 1200] if len(idx) else x


def piper_segments(segs, path):
    """Synthétise la réplique entière (plus stable et plus naturel que des
    fragments isolés), puis la recoupe aux pauses les plus longues pour
    retrouver chaque segment « | »."""
    parts = [s.strip().replace("...", "…") for s in segs]
    full = " ".join(p for p in parts)
    if full[-1] not in ".!?…":
        full += "."
    x = tts(full, path)
    k = len(parts) - 1
    if k == 0:
        return [x]
    hop = SR // 100
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    sil = rms < 0.05 * rms.max()
    runs, i = [], 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]:
                j += 1
            if i > 0 and j < len(sil):
                runs.append((j - i, i, j))
            i = j
        else:
            i += 1
    cuts = sorted(sorted(runs, reverse=True)[:k], key=lambda r: r[1])
    if len(cuts) < k:  # repli : découpe proportionnelle au texte
        w = np.cumsum([len(p) for p in parts])[:-1] / sum(len(p) for p in parts)
        bounds = [int(len(x) * f) for f in w]
    else:
        bounds = [int((a + b) / 2 * hop) for _, a, b in cuts]
    edges = [0] + bounds + [len(x)]
    return [trim(x[a:b]) for a, b in zip(edges[:-1], edges[1:])]


def chunk_words(text, max_chars=17):
    words = text.split()
    chunks, cur = [], []
    for w in words:
        cand = " ".join(cur + [w]).replace("*", "")
        if cur and (len(cand) > max_chars or len(cur) >= 3):
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        chunks.append(" ".join(cur))
    # ne laisse pas un ":" / "?" / "!" tout seul
    out = []
    for c in chunks:
        if out and c.strip() in (":", "?", "!"):
            out[-1] += " " + c
        else:
            out.append(c)
    return out


def build():
    tmp = tempfile.mkdtemp()
    t = 0.0
    timeline = dict(fps=FPS, scenes=[], lines=[], chunks=[], events={})
    voice_parts = []  # (start, samples)
    for s in SCENES:
        start = t
        t += s["lead"]
        for li, line in enumerate(s["lines"]):
            say = line["say"].split("|")
            sub = line["sub"].split("|")
            assert len(say) == len(sub), line
            lstart = t
            spoken = [sy for sy in say if sy.strip(". ") != ""]
            pieces = piper_segments(spoken, os.path.join(tmp, f"{s['id']}_{li}.wav")) if VOICE != "mbrola" else None
            for k, (sy, sb) in enumerate(zip(say, sub)):
                if k:
                    t += PAUSE
                if sy.strip(". ") == "":
                    # pause comique pure (« … »)
                    timeline["chunks"].append(dict(text=sb, start=round(t, 3), end=round(t + 0.6, 3)))
                    t += 0.6
                    continue
                x = pieces.pop(0) if pieces is not None else tts(sy, os.path.join(tmp, f"{s['id']}_{li}_{k}.wav"))
                d = len(x) / SR
                voice_parts.append((t, x))
                chunks = chunk_words(sb)
                weights = np.array([len(c.replace("*", "")) + 3 for c in chunks], float)
                bounds = np.concatenate([[0], np.cumsum(weights) / weights.sum()]) * d
                for c, a, b in zip(chunks, bounds[:-1], bounds[1:]):
                    timeline["chunks"].append(dict(text=c, start=round(t + a, 3), end=round(t + b, 3)))
                t += d
            timeline["lines"].append(dict(scene=s["id"], start=round(lstart, 3), end=round(t, 3)))
        t += s["tail"]
        timeline["scenes"].append(dict(id=s["id"], start=round(start, 3), end=round(t, 3)))
    dur = t
    timeline["duration"] = round(dur, 3)
    # extend chunk ends to fill small gaps (subtitles stay up while speaking pauses)
    ch = timeline["chunks"]
    for a, b in zip(ch, ch[1:]):
        if 0 < b["start"] - a["end"] < 0.45:
            a["end"] = b["start"]
    for a in ch:
        a["end"] = round(a["end"] + 0.15, 3)

    S = {s["id"]: s for s in timeline["scenes"]}
    L = {}
    for l in timeline["lines"]:
        L.setdefault(l["scene"], l)

    # ------------------------------------------------ events (shared with visuals)
    E = timeline["events"]
    sc = lambda k: S[k]["start"]
    E["hook_pop"] = sc("hook") + 0.05
    E["hook_eyes"] = sc("hook") + 0.32
    E["hook_point"] = L["hook"]["start"] + 1.55
    E["plant_coins"] = [sc("plant") + 0.15, sc("plant") + 0.4, sc("plant") + 0.65]
    E["plant_water"] = [sc("plant") + 1.0, sc("plant") + 2.2]
    E["plant_stare"] = L["plant"]["end"] - 0.2
    E["shake_flip"] = sc("shake") + 0.05
    E["shake_drop"] = [sc("shake") + 0.85, sc("shake") + 1.35]
    E["scam_click"] = sc("scam") + 0.85
    E["scam_boom"] = sc("scam") + 1.0
    E["scam_stamp"] = sc("scam") + 1.3
    E["reveal_look"] = sc("reveal") + 0.9
    E["reveal_ding"] = sc("reveal") + 1.75
    E["step1_num"] = sc("step1") + 0.05
    E["step2_num"] = sc("step2") + 0.05
    E["step3_num"] = sc("step3") + 0.05
    E["step1_items"] = [L["step1"]["start"] + 0.5 + i * 0.75 for i in range(7)]
    l2 = L["step2"]
    E["step2_snaps"] = [l2["start"] + 1.5, l2["start"] + 2.4, l2["start"] + 3.3, l2["end"] - 1.2]
    l3 = L["step3"]
    E["step3_listing"] = l3["start"] + 1.6
    E["step3_price"] = l3["start"] + 3.6
    E["step3_ching"] = l3["end"] + 0.25
    E["step3_sold"] = [l3["end"] + 0.6 + i * 0.32 for i in range(4)]
    E["outro_wink"] = sc("outro") + 0.15
    E["tie_adjust"] = sc("tie") + 0.1
    E["tie_fall"] = sc("tie") + 0.85
    E["tie_land"] = sc("tie") + 1.25
    E["tie_look"] = sc("tie") + 1.55
    E["tie_photo"] = sc("tie") + 2.3
    E["final_button"] = sc("final") + 0.5
    E["final_click"] = L["final"]["end"] - 0.6
    for k, v in list(E.items()):
        E[k] = [round(x, 3) for x in v] if isinstance(v, list) else round(v, 3)

    n = int((dur + 0.2) * SR)
    voice = np.zeros(n)
    for st, x in voice_parts:
        add(voice, x, st)

    # mouth envelope per frame (lip-sync LED)
    hop = SR // FPS
    nf = int(dur * FPS) + 2
    mouth = []
    for f in range(nf):
        seg = voice[f * hop:(f + 1) * hop]
        mouth.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    mouth = np.array(mouth)
    mouth = np.clip(mouth / (np.percentile(mouth[mouth > 0.01], 90) + 1e-9), 0, 1)
    timeline["mouth"] = [round(float(m), 2) for m in mouth]

    sfx = build_sfx(n, E, S)
    music = build_music(n, dur)
    # ducking
    ve = np.abs(voice)
    ve = lp(ve, 6, 1)
    ve = np.clip(ve / (ve.max() + 1e-9) * 3, 0, 1)
    duck = 1 - 0.78 * ve
    # musique nettement plus basse sous la voix pour une écoute sans effort
    mix = music * 0.36 * duck[:, None] + voice[:, None] * 0.95 + sfx * 0.5
    # final limiter-ish
    peak = np.max(np.abs(mix))
    mix = np.tanh(mix / max(peak, 1) * 1.1) * 0.92
    write_wav(os.path.join(OUT, "audio.wav"), mix)

    with open(os.path.join(OUT, "timeline.js"), "w") as f:
        f.write("window.TIMELINE = " + json.dumps(timeline, ensure_ascii=False) + ";\n")
    print(f"durée : {dur:.2f}s")
    for s in timeline["scenes"]:
        print(f"  {s['id']:7s} {s['start']:6.2f} → {s['end']:6.2f}")


# ---------------------------------------------------------------- sfx
def s_bip(f=1400, d=0.07):
    x = tt(d)
    return np.sin(2 * np.pi * f * x) * env(len(x), 0.002, d=d / 2.5) * 0.5


def s_ding(f=1568, d=1.4):
    x = tt(d)
    y = sum(a * np.sin(2 * np.pi * f * m * x) * np.exp(-x * k)
            for m, a, k in [(1, 1, 2.2), (2.76, 0.4, 4), (5.4, 0.2, 7), (2, 0.25, 3)])
    return y * env(len(x), 0.001) * 0.6


def s_boing(f0=180, d=0.55):
    x = tt(d)
    f = f0 * (1 + 0.6 * np.exp(-x * 6) * np.sin(2 * np.pi * 14 * x)) * (1 + x)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(len(x), 0.003, d=0.25) * 0.8


def s_whoosh(d=0.4, lo=300, hi=3000):
    x = tt(d)
    n = rng.standard_normal(len(x))
    y = bp(n, lo, hi)
    shape = np.sin(np.pi * x / d) ** 2
    return y * shape * 0.35


def s_pop(f=600):
    x = tt(0.12)
    ph = 2 * np.pi * np.cumsum(f * np.exp(-x * 25) + 200) / SR
    return np.sin(ph) * env(len(x), 0.001, d=0.03) * 0.7


def s_clink(f=3200):
    x = tt(0.5)
    y = sum(a * np.sin(2 * np.pi * f * m * x) for m, a in [(1, 1), (1.47, 0.6), (2.09, 0.4), (2.56, 0.3)])
    return y * env(len(x), 0.0005, d=0.08) * 0.25


def s_coins(n=8, spread=0.6):
    out = np.zeros(int((spread + 0.6) * SR))
    for i in range(n):
        add(out, s_clink(2400 + rng.random() * 2600), rng.random() * spread, 0.5 + rng.random() * 0.5)
    return out


def s_click():
    x = tt(0.04)
    return hp(rng.standard_normal(len(x)), 2000) * env(len(x), 0.0005, d=0.006) * 0.8


def s_shutter():
    out = np.zeros(int(0.25 * SR))
    add(out, s_click(), 0)
    add(out, hp(rng.standard_normal(int(0.06 * SR)), 1500) * env(int(0.06 * SR), 0.001, d=0.015) * 0.6, 0.07)
    return out


def s_water(d=1.0):
    x = tt(d)
    n = bp(rng.standard_normal(len(x)), 900, 5000)
    gl = 0.6 + 0.4 * np.sin(2 * np.pi * 9 * x + 2 * np.sin(2 * np.pi * 3 * x))
    return n * gl * np.sin(np.pi * x / d) ** 0.5 * 0.25


def s_boom():
    x = tt(1.0)
    y = lp(rng.standard_normal(len(x)), 900) * np.exp(-x * 4) * 1.4
    y += np.sin(2 * np.pi * np.cumsum(90 * np.exp(-x * 3) + 30) / SR) * np.exp(-x * 5)
    return y * 0.7


def s_confetti():
    out = np.zeros(int(1.2 * SR))
    for i in range(14):
        add(out, s_pop(500 + rng.random() * 900), rng.random() * 0.8, 0.2 + rng.random() * 0.3)
    return out


def s_buzzer():
    x = tt(0.9)
    out = np.zeros(len(x))
    for i, f in enumerate([392, 370, 349, 311]):
        seg = tt(0.22 if i < 3 else 0.5)
        tone = np.sign(np.sin(2 * np.pi * f * seg)) * 0.3 + np.sin(2 * np.pi * f * 1.005 * seg)
        tone = lp(tone, 1800) * env(len(seg), 0.01) * np.minimum(1, (len(seg) / SR - seg) * 20)
        if i == 3:
            tone *= 1 + 0.3 * np.sin(2 * np.pi * 6 * seg)
        add(out, tone * 0.22, i * 0.2)
    return out


def s_thud():
    x = tt(0.3)
    return np.sin(2 * np.pi * np.cumsum(120 * np.exp(-x * 12) + 50) / SR) * env(len(x), 0.001, d=0.08)


def s_chaching():
    out = np.zeros(int(1.6 * SR))
    # "cha" : bruit + mécanique
    add(out, hp(rng.standard_normal(int(0.08 * SR)), 2500) * env(int(0.08 * SR), 0.001, d=0.03) * 0.6, 0)
    add(out, hp(rng.standard_normal(int(0.08 * SR)), 2500) * env(int(0.08 * SR), 0.001, d=0.03) * 0.6, 0.11)
    # "ching" : cloche de caisse
    add(out, s_ding(2093, 1.3) * 1.2, 0.2)
    add(out, s_ding(2637, 1.1) * 0.6, 0.2)
    add(out, s_coins(10, 0.5) * 1.2, 0.25)
    return out


def s_sad():
    x = tt(1.4)
    out = np.zeros(len(x))
    for i, f in enumerate([311, 294, 277, 262]):
        d = 0.32 if i < 3 else 0.6
        seg = tt(d)
        vib = 1 + (0.01 * np.sin(2 * np.pi * 5 * seg) if i == 3 else 0)
        tone = sum(a * np.sin(2 * np.pi * f * m * np.cumsum(vib) / SR) for m, a in [(1, 1), (2, .5), (3, .3), (4, .15)])
        add(out, tone * env(len(seg), 0.03, d=0.4) * 0.12, i * 0.3)
    return out


def s_rattle(d=0.5):
    out = np.zeros(int(d * SR))
    for i in range(int(d * 22)):
        add(out, s_clink(1200 + rng.random() * 1500) * 0.6, i / 22 + rng.random() * 0.01)
    return out


def build_sfx(n, E, S):
    b = np.zeros(n)
    add(b, s_whoosh(0.3, 400, 2500), E["hook_pop"])
    add(b, s_boing(260, 0.4), E["hook_pop"] + 0.18, 0.6)
    add(b, s_bip(1200), E["hook_eyes"]); add(b, s_bip(1800), E["hook_eyes"] + 0.09)
    add(b, s_bip(2000, 0.05), E["hook_point"]); add(b, s_bip(2400, 0.05), E["hook_point"] + 0.12)
    for k in ["plant", "shake", "scam", "reveal", "step1", "step2", "step3", "outro", "final"]:
        add(b, s_whoosh(0.28, 600, 4000), S[k]["start"] - 0.12, 0.6)
    for x in E["plant_coins"]:
        add(b, s_clink(3000), x + 0.18)
    add(b, s_water(1.1), E["plant_water"][0])
    add(b, s_sad() * 0.8, E["plant_stare"])
    add(b, s_boing(150, 0.5), E["shake_flip"] + 0.1, 0.5)
    add(b, s_rattle(0.9), E["shake_flip"] + 0.25, 0.8)
    for i, x in enumerate(E["shake_drop"]):
        add(b, s_clink(1800 + 600 * i), x + 0.35)
        add(b, s_boing(300 + 80 * i, 0.3), x + 0.35, 0.4)
    add(b, s_bip(900, 0.05), E["scam_click"] - 0.5)
    add(b, s_click(), E["scam_click"])
    add(b, s_boom(), E["scam_boom"], 0.8)
    add(b, s_confetti(), E["scam_boom"] + 0.05)
    add(b, s_thud(), E["scam_stamp"], 0.9)
    add(b, s_buzzer(), E["scam_stamp"] + 0.15, 1.0)
    add(b, s_bip(700, 0.12), E["reveal_look"])
    add(b, s_ding(1568, 1.6) * 1.3, E["reveal_ding"])
    for k in ["step1_num", "step2_num", "step3_num"]:
        add(b, s_whoosh(0.25, 800, 5000), E[k])
        add(b, s_pop(700), E[k] + 0.2, 1.0)
        add(b, s_bip(1500), E[k] + 0.3)
    for x in E["step1_items"]:
        add(b, s_whoosh(0.2, 1000, 4000), x, 0.5)
        add(b, s_pop(500 + rng.random() * 300), x + 0.35, 0.8)
    for x in E["step2_snaps"]:
        add(b, s_shutter(), x, 1.0)
    add(b, s_pop(800), E["step3_listing"])
    add(b, s_bip(1700, 0.05), E["step3_listing"] + 0.1)
    add(b, s_bip(2000, 0.05), E["step3_price"])
    add(b, s_bip(1500, 0.05), E["step3_price"] + 0.08)
    add(b, s_chaching() * 1.3, E["step3_ching"])
    for i, x in enumerate(E["step3_sold"]):
        add(b, s_ding(1760 + i * 220, 0.5) * 0.55, x)
    add(b, s_bip(1900, 0.06), E["outro_wink"] + 0.1)
    add(b, s_boing(200, 0.6), E["tie_land"], 0.8)
    add(b, s_whoosh(0.35, 400, 2000), E["tie_fall"], 0.6)
    add(b, s_bip(600, 0.1), E["tie_look"])
    add(b, s_shutter(), E["tie_photo"], 1.0)
    add(b, s_pop(650), E["final_button"])
    add(b, s_click(), E["final_click"])
    add(b, s_ding(2093, 0.8) * 0.6, E["final_click"] + 0.05)
    return b[:, None] * np.array([[1.0, 1.0]])


# ---------------------------------------------------------------- music
def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def kick():
    x = tt(0.35)
    f = 50 + 110 * np.exp(-x * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)


def snare():
    x = tt(0.25)
    n = bp(rng.standard_normal(len(x)), 1200, 8000) * np.exp(-x * 18)
    b = np.sin(2 * np.pi * 190 * x) * np.exp(-x * 25)
    return n * 0.7 + b * 0.5


def hat(open_=False):
    d = 0.18 if open_ else 0.05
    x = tt(d)
    return hp(rng.standard_normal(len(x)), 7000) * np.exp(-x * (14 if open_ else 70)) * 0.35


def clap():
    x = tt(0.3)
    n = bp(rng.standard_normal(len(x)), 900, 5000)
    e = np.zeros(len(x))
    for o in (0, 0.01, 0.02):
        i = int(o * SR)
        e[i:] += np.exp(-(x[: len(x) - i]) * 30)
    return n * e * 0.4


def bass_note(f, d):
    x = tt(d)
    saw = 2 * ((x * f) % 1) - 1
    sq = np.sign(np.sin(2 * np.pi * f * x))
    y = saw * 0.6 + sq * 0.3 + np.sin(2 * np.pi * f * x) * 0.6
    # filtre « wah » rapide
    cutoff_env = np.exp(-x * 14)
    y1 = lp(y, 2600)
    y2 = lp(y, 380)
    y = y1 * cutoff_env + y2 * (1 - cutoff_env)
    a = np.minimum(1, x / 0.004) * np.minimum(1, (d - x) / 0.02)
    return y * a * 0.55


def epiano(freqs, d):
    x = tt(d)
    y = np.zeros(len(x))
    for f in freqs:
        y += np.sin(2 * np.pi * f * x + 0.6 * np.sin(2 * np.pi * f * 2 * x) * np.exp(-x * 5)) * np.exp(-x * 3.5)
    y *= 1 + 0.15 * np.sin(2 * np.pi * 5 * x)
    return y * env(len(x), 0.003) * np.minimum(1, (d - x) / 0.03) * 0.11


def pluck(f, d=0.18):
    x = tt(d)
    y = (2 * ((x * f) % 1) - 1)
    y = lp(y, 3500) * np.exp(-x * 16)
    return y * 0.12


def build_music(n, dur):
    bpm = 112
    beat = 60 / bpm
    st = beat / 4
    L = np.zeros(n); R = np.zeros(n)
    drums = np.zeros(n)
    # progression funky (i - IV en mi dorien, puis ii - V)
    prog = [
        (40, [64, 67, 71, 74]),      # Em9-ish
        (45, [64, 67, 69, 73]),      # A13
        (40, [64, 67, 71, 74]),
        (42, [64, 66, 69, 73]),      # F#m7 -> B7 flavour
    ]
    bass_pat = [0, None, 12, None, 0, 0, None, 10, None, 7, None, 0, 12, None, 7, 10]
    stab_pat = [2, 6, 10, 14]  # contretemps
    arp = [0, 3, 7, 10, 12, 10, 7, 3]
    nbars = int(dur / (beat * 4)) + 2
    K, Sn, H, Ho, C = kick(), snare(), hat(), hat(True), clap()
    for bar in range(nbars):
        root, chord = prog[bar % len(prog)]
        t0 = bar * beat * 4
        intro = bar == 0
        for s in range(16):
            ts = t0 + s * st + (0.018 if s % 2 else 0)  # swing
            if ts > dur + 0.2:
                break
            if s in (0, 6, 10) and not intro:
                add(drums, K, ts, 0.9)
            if s in (4, 12) and not intro:
                add(drums, Sn, ts, 0.55); add(drums, C, ts, 0.5)
            if s % 2 == 0 or not intro:
                add(drums, H if s != 14 else Ho, ts, 0.5 if s % 4 == 2 else 0.3)
            b = bass_pat[s]
            if b is not None and not intro:
                add(L, bass_note(note(root + b) , st * 1.6), ts, 0.8)
                add(R, bass_note(note(root + b), st * 1.6), ts, 0.8)
            if s in stab_pat:
                y = epiano([note(m) for m in chord], st * 2.2)
                add(L, y, ts, 1.0); add(R, y, ts + 0.008, 0.9)
            if bar % 2 == 1 and s % 2 == 0:
                p = pluck(note(root + 24 + arp[(s // 2) % 8]))
                add(L if s % 4 else R, p, ts, 0.8)
    # léger sidechain sur le kick pour le côté électro
    pump = np.ones(n)
    for bar in range(nbars):
        for s in (0, 6, 10):
            i = int((bar * beat * 4 + s * st) * SR)
            k = int(0.12 * SR)
            if i + k < n and bar > 0:
                pump[i:i + k] = np.minimum(pump[i:i + k], 0.55 + 0.45 * np.linspace(0, 1, k))
    L *= pump; R *= pump
    L += drums; R += drums
    # fin : coupe propre
    fade = np.ones(n)
    fe = int((dur - 0.4) * SR)
    if fe < n:
        fade[fe:] = np.linspace(1, 0, n - fe)
    m = np.stack([L * fade, R * fade], axis=1)
    return m / (np.max(np.abs(m)) + 1e-9)


if __name__ == "__main__":
    build()

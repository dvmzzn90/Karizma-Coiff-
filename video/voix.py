"""Étape 2 — génération des voix off + timings mot par mot.

Deux moteurs :
  * edge-tts (voix Microsoft, WordBoundary natif)  -> utilisé si le serveur répond
  * Piper (voix neuronales locales) + alignement phonème -> repli hors-ligne

Sortie : build/lines/NN.wav (44,1 kHz mono) + build/timings.json
"""
import asyncio
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request
import wave

import numpy as np

from scenario_data import LINES, CHARS, display_words

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
VOICES_DIR = os.path.join(ROOT, "voices")
SR = 44100

PIPER_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{}.tar.gz"
PUNCT_RE = re.compile(r"[!?…:;., ]+")
SUBS_PIPER = {"2019": "deux mille dix-neuf", "GISÈLE": "Gisèle"}


# ----------------------------------------------------------------- utilitaires
def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ffmpeg_filter(x, sr_in, filt):
    """Passe un signal float mono dans un filtre ffmpeg, retourne float @44.1k."""
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    cmd = ["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(sr_in), "-ac", "1", "-i", "-"]
    if filt:
        cmd += ["-af", filt]
    cmd += ["-ar", str(SR), "-ac", "1", "-f", "s16le", "-"]
    out = subprocess.run(cmd, input=pcm, capture_output=True, check=True).stdout
    return np.frombuffer(out, "<i2").astype(np.float32) / 32767


def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def clean(w):
    return PUNCT_RE.sub("", w).lower()


# ----------------------------------------------------------------- edge-tts
async def _edge_line(text, voice, rate, pitch, volume):
    import edge_tts

    try:
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume,
                                   boundary="WordBoundary")
    except TypeError:  # anciennes versions d'edge-tts
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
    audio, bounds = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            bounds.append((ch["text"], ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
    return bytes(audio), bounds


def edge_line(line):
    voice, rate, pitch, volume = CHARS[line["who"]]["edge"]
    mp3, bounds = asyncio.run(_edge_line(line["text"], voice, rate, pitch, volume))
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", "-", "-ar", str(SR), "-ac", "1",
                          "-f", "s16le", "-"], input=mp3, capture_output=True, check=True).stdout
    x = np.frombuffer(dec, "<i2").astype(np.float32) / 32767
    x, off = trim(x, SR)
    words = display_words(line["text"])
    spoken = [(t, s - off, e - off) for t, s, e in bounds if clean(t)]
    return x, map_words(words, spoken, len(x) / SR)


# ----------------------------------------------------------------- Piper
_voices = {}


def piper_voice(name):
    if name not in _voices:
        from piper import PiperVoice

        path = os.path.join(VOICES_DIR, name + ".onnx")
        if not os.path.exists(path):
            os.makedirs(VOICES_DIR, exist_ok=True)
            print("  téléchargement voix", name)
            data = urllib.request.urlopen(PIPER_URL.format(name)).read()
            tarfile.open(fileobj=io.BytesIO(data)).extractall(VOICES_DIR)
        _voices[name] = PiperVoice.load(path, include_alignments=True)
    return _voices[name]


def piper_segment(voice, text, length):
    """Synthétise un segment ; retourne audio float + liste [(start,end)] par mot phonétique."""
    from piper import SynthesisConfig

    idmap = voice.config.phoneme_id_map
    cfg = SynthesisConfig(length_scale=length, noise_scale=0.6, noise_w_scale=0.7)
    sr = voice.config.sample_rate
    audio, words = [], []
    base = 0
    for ch in voice.synthesize(text, syn_config=cfg, include_alignments=True):
        samples = ch.phoneme_id_samples
        pos = 0
        # BOS + PAD
        cursor = sum(samples[: len(idmap["^"]) + len(idmap["_"])])
        pos = len(idmap["^"]) + len(idmap["_"])
        cur = None
        for ph in ch.phonemes:
            if ph not in idmap:
                continue
            n = len(idmap[ph]) + len(idmap["_"])
            dur = int(sum(samples[pos:pos + n]))
            if ph == " ":
                if cur:
                    words.append(cur)
                cur = None
            elif not PUNCT_RE.fullmatch(ph) and ph not in ("ˈ", "ˌ"):
                s, e = (base + cursor) / sr, (base + cursor + dur) / sr
                cur = [cur[0], e] if cur else [s, e]
            pos += n
            cursor += dur
        if cur:
            words.append(cur)
        audio.append(ch.audio_float_array)
        base += len(ch.audio_float_array)
    return np.concatenate(audio), sr, words


def trim(x, sr, thr=0.02, margin=0.03):
    env = np.abs(x)
    idx = np.where(env > thr)[0]
    if len(idx) == 0:
        return x, 0.0
    a = max(0, idx[0] - int(margin * sr))
    b = min(len(x), idx[-1] + int(margin * sr))
    return x[a:b], a / sr


def piper_line(line):
    p = CHARS[line["who"]]["piper"]
    voice = piper_voice(p["model"])
    words = display_words(line["text"])
    # découpe en segments aux fins de phrase pour contrôler les pauses
    segs, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?…]$", w):
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)

    out, timings, t = [], [], 0.0
    for si, seg in enumerate(segs):
        spoken = []
        for w in seg:
            base = w.replace(" ", " ")
            core = PUNCT_RE.sub("", base)
            spoken.append(base.replace(core, SUBS_PIPER.get(core, core)) if core else base)
        txt = " ".join(spoken)
        txt = txt.replace("…", ",")  # Piper marque mieux une virgule qu'une ellipse
        x, sr, pw = piper_segment(voice, txt, p["length"])
        # nombre de mots phonétiques attendus par mot affiché
        n_exp = [len(SUBS_PIPER.get(PUNCT_RE.sub("", w.replace(" ", " ")).strip(),
                                    "x").split()) for w in seg]
        x, off = trim(x, sr)
        pw = [(s - off, e - off) for s, e in pw]
        seg_t = map_words_counts(seg, n_exp, pw, len(x) / sr)
        # resample en 44,1k (sans effet ici), effet appliqué sur la réplique entière
        x = ffmpeg_filter(x, sr, None)
        for w, s, e in seg_t:
            timings.append((w, t + s, t + e))
        out.append(x)
        t += len(x) / SR
        if si < len(segs) - 1:
            pause = 0.30 if seg[-1].endswith("…") else 0.20
            out.append(np.zeros(int(pause * SR), np.float32))
            t += pause
    x = np.concatenate(out)
    n0 = len(x)
    # hauteur (pitch) : asetrate + atempo => la durée est conservée
    k = 2 ** (p["semitones"] / 12)
    filt = f"asetrate={int(SR * k)},aresample={SR},atempo={1 / k:.5f}"
    if p.get("fx") == "robot":
        filt += ",aecho=0.8:0.6:9:0.22"
    if p.get("fx") == "grave":
        filt += ",bass=g=4"
    x = ffmpeg_filter(x, SR, filt)
    ratio = len(x) / n0
    timings = [(w, s * ratio, e * ratio) for w, s, e in timings]
    x = x / max(1e-6, np.abs(x).max()) * 0.92 * p.get("gain", 1.0)
    return x, timings


def map_words_counts(words, n_exp, pw, total):
    """Associe les mots affichés aux mots phonétiques de Piper."""
    if sum(n_exp) == len(pw):
        res, i = [], 0
        for w, n in zip(words, n_exp):
            res.append((w, pw[i][0], pw[i + n - 1][1]))
            i += n
        return res
    print(f"    ! alignement approx. ({len(words)} mots / {len(pw)} phonétiques) : {' '.join(words)}")
    s0 = pw[0][0] if pw else 0.0
    e0 = pw[-1][1] if pw else total
    return proportional(words, s0, e0)


def proportional(words, s0, e0):
    lens = [max(1, len(clean(w))) + 1 for w in words]
    tot, acc, res = sum(lens), 0, []
    for w, l in zip(words, lens):
        a = s0 + (e0 - s0) * acc / tot
        acc += l
        res.append((w, a, s0 + (e0 - s0) * acc / tot))
    return res


def map_words(words, spoken, total):
    """Pour edge-tts : associe mots affichés et WordBoundary."""
    if len(spoken) == len(words):
        return [(w, s, e) for w, (_, s, e) in zip(words, spoken)]
    # fusion gloutonne sur le texte normalisé
    res, j = [], 0
    for w in words:
        target, acc, s, e = clean(w), "", None, None
        while j < len(spoken) and len(acc) < len(target):
            acc += clean(spoken[j][0])
            s = spoken[j][1] if s is None else s
            e = spoken[j][2]
            j += 1
        if s is None:
            return proportional(words, spoken[0][1], spoken[-1][2]) if spoken else proportional(words, 0, total)
        res.append((w, s, e))
    return res


# ----------------------------------------------------------------- main
def edge_available():
    try:
        import edge_tts  # noqa

        asyncio.run(_edge_line("Test.", "fr-FR-HenriNeural", "+0%", "+0Hz", "+0%"))
        return True
    except Exception as exc:  # réseau bloqué, etc.
        print("  edge-tts indisponible :", type(exc).__name__)
        return False


def main(engine="auto"):
    os.makedirs(os.path.join(BUILD, "lines"), exist_ok=True)
    if engine == "auto":
        engine = "edge" if edge_available() else "piper"
    print("Moteur de voix :", engine)
    meta = []
    for i, line in enumerate(LINES):
        x, words = (edge_line if engine == "edge" else piper_line)(line)
        path = os.path.join(BUILD, "lines", f"{i:02d}.wav")
        write_wav(path, x)
        dur = len(x) / SR
        meta.append(dict(i=i, who=line["who"], text=line["text"], dur=dur, words=words))
        print(f"  {i:02d} {line['who']:7s} {dur:5.2f}s  {line['text']}")
    json.dump(dict(engine=engine, lines=meta), open(os.path.join(BUILD, "timings.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "auto")

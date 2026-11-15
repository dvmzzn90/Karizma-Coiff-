"""Narration : synthèse vocale française (voix masculine grave), timing mot par mot.

Par défaut : voix hors-ligne espeak-ng + MBROLA « fr1 » (masculine), abaissée en
hauteur et posée. Si un fichier `voice/lineNN.wav` existe (enregistrement réel ou
voix IA type ElevenLabs), il remplace la voix synthétique pour cette réplique.
"""
import json, os, re, subprocess, tempfile, wave
import numpy as np
from timeline import LINES, SR

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VOICE_DIR = os.path.join(ROOT, "voice")

PITCH = 0.86      # < 1 = voix plus grave
SPEED = 128       # mots/min espeak (lent, documentaire)


def read_wav(path):
    with wave.open(path) as w:
        n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    assert sr == SR, sr
    return a


def to48k(src, dst, pitch=1.0):
    af = f"asetrate={16000 * pitch:.0f},aresample={SR},atempo={1 / pitch:.4f}" if pitch != 1.0 else f"aresample={SR}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                    af + ",highpass=f=70,equalizer=f=140:t=q:w=1.2:g=5,equalizer=f=3200:t=q:w=1.5:g=2",
                    "-ac", "1", "-ar", str(SR), dst], check=True)


def trim(a, thr=0.012):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    return a[max(0, idx[0] - 240): idx[-1] + 960]


def synth_segment(text):
    clean = text.replace("…", "").strip()
    with tempfile.TemporaryDirectory() as d:
        raw, out = os.path.join(d, "r.wav"), os.path.join(d, "o.wav")
        subprocess.run(["espeak-ng", "-v", "mb-fr1", "-s", str(SPEED), "-p", "28", "-g", "2",
                        clean, "-w", raw], check=True, capture_output=True)
        to48k(raw, out, PITCH)
        return trim(read_wav(out))


def word_weights(words):
    return [len(re.sub(r"[^\wàâäéèêëîïôöùûüç]", "", w.lower())) + 1.2 for w in words]


def build():
    """Retourne (piste voix np.float32, liste de mots minutés)."""
    from timeline import DURATION
    track = np.zeros(int(DURATION * SR) + SR, np.float32)
    words_out = []
    for li, line in enumerate(LINES):
        override = os.path.join(VOICE_DIR, f"line{li + 1:02d}.wav")
        pieces = []
        for text, pause in line["segs"]:
            audio = synth_segment(text) if not os.path.exists(override) else None
            pieces.append((text, audio, pause))
        # Limite : la réplique doit tenir avant la suivante
        nxt = LINES[li + 1]["start"] if li + 1 < len(LINES) else DURATION - 0.6
        budget = nxt - line["start"] - 0.2
        if os.path.exists(override):
            a = trim(read_wav_any(override))
            total_w = sum(sum(word_weights(t.split())) for t, _, _ in pieces)
            dur = len(a) / SR
            pos = line["start"]
            seg_audio = [(t, None, p) for t, _, p in pieces]
            _place(track, a, pos)
            cur = pos
            for t, _, p in seg_audio:
                ws = t.split()
                for w, wt in zip(ws, word_weights(ws)):
                    d = dur * wt / total_w
                    words_out.append(_word(w, cur, cur + d, li, line))
                    cur += d
            continue
        total = sum(len(a) / SR + p for _, a, p in pieces)
        tempo = 1.0
        if total > budget:
            tempo = total / budget
        pos = line["start"]
        for text, a, pause in pieces:
            if tempo > 1.0:
                a = atempo(a, tempo)
            _place(track, a, pos)
            dur = len(a) / SR
            ws = text.split()
            wts = word_weights(ws)
            cur = pos
            for w, wt in zip(ws, wts):
                d = dur * wt / sum(wts)
                words_out.append(_word(w, cur, cur + d, li, line))
                cur += d
            pos += dur + pause / tempo
        line["end"] = pos
        line["tempo"] = tempo
    return track, words_out


def _word(w, a, b, li, line):
    key = re.sub(r"[^\wàâäéèêëîïôöùûüç'-]", "", w.lower())
    return dict(w=w, start=round(a, 3), end=round(b, 3), line=li, kw=(key == line["kw"]))


def _place(track, a, t):
    i = int(t * SR)
    track[i:i + len(a)] += a[: len(track) - i]


def atempo(a, f):
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
        write_wav(src, a)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", f"atempo={f:.4f}", dst], check=True)
        return read_wav(dst)


def read_wav_any(path):
    with tempfile.TemporaryDirectory() as d:
        dst = os.path.join(d, "x.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", str(SR), dst], check=True)
        return read_wav(dst)


def write_wav(path, a, ch=1):
    a = np.clip(a, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    tr, words = build()
    for l in LINES:
        print(l["plan"], l["start"], "->", round(l["end"], 2), "tempo", round(l["tempo"], 2))

"""Synthèse vocale française locale (Piper, voix neuronales hors ligne).
Modèles attendus dans VOICES_DIR — voir voice/README.md pour les télécharger."""
import os, glob, numpy as np
from piper import PiperVoice, SynthesisConfig
VOICES_DIR = os.environ.get("VOICES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
VOICES = {"siwis": ("vits-piper-fr_FR-siwis-medium", None), "tom": ("vits-piper-fr_FR-tom-medium", None),
          "gilles": ("vits-piper-fr_FR-gilles-low", None), "jessica": ("vits-piper-fr_FR-upmc-medium", 0),
          "pierre": ("vits-piper-fr_FR-upmc-medium", 1)}
_cache = {}
def _voice(model):
    if model not in _cache:
        _cache[model] = PiperVoice.load(glob.glob(os.path.join(VOICES_DIR, model, "*.onnx"))[0])
    return _cache[model]
def say(text, voice, speed=1.0, pitch=1.0, sr_out=44100):
    """Mono float à sr_out. speed>1 = plus rapide ; pitch>1 = plus aigu (et plus court)."""
    model, sid = VOICES[voice]
    v = _voice(model)
    cfg = SynthesisConfig(speaker_id=sid, length_scale=1.0 / speed)
    chunks = list(v.synthesize(text, syn_config=cfg))
    x = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float64)
    sr = chunks[0].sample_rate
    ratio = sr_out / sr / pitch
    n = int(len(x) * ratio)
    y = np.interp(np.arange(n) / ratio, np.arange(len(x)), x)
    nz = np.where(np.abs(y) > .02)[0]  # coupe les silences début/fin
    if len(nz): y = y[max(0, nz[0] - 400): nz[-1] + 2000]
    return y / max(1e-6, np.abs(y).max()) * .95
def save(path, y, sr=44100):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())

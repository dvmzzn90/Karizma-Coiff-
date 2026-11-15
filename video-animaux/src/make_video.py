"""Pipeline complet : python3 make_video.py

1. audio.py   -> out/audio.wav + out/timings.json (voix, effets, musique, mixage)
2. render.py  -> out/video_noaudio.mp4 (images procédurales, transitions, étalonnage)
3. subs.py    -> out/subtitles.ass / .srt (mot par mot, mot-clé en jaune)
4. assemblage -> out/et_si_animaux_1080x1920.mp4

Remplacement par de vrais rushes : déposer clips/plan01.mp4 … clips/plan10.mp4
(générés avec Veo / Kling / Runway / Sora à partir de PROMPTS.md) ; ils remplacent
automatiquement les images procédurales du plan correspondant, la bande son et
les sous-titres restent synchronisés.
"""
import os, subprocess, sys, time
from timeline import PLANS, DURATION

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
CLIPS = os.path.join(ROOT, "clips")
FINAL = os.path.join(OUT, "et_si_animaux_1080x1920.mp4")


def step(name, fn):
    t = time.time()
    print(f"[{name}]", flush=True)
    fn()
    print(f"  -> {time.time() - t:.0f} s", flush=True)


def assemble():
    inputs = ["-i", os.path.join(OUT, "video_noaudio.mp4"), "-i", os.path.join(OUT, "audio.wav")]
    fc, last, k = [], "[0:v]", 2
    for n, a, b, _ in PLANS:
        p = os.path.join(CLIPS, f"plan{n:02d}.mp4")
        if not os.path.exists(p):
            continue
        inputs += ["-i", p]
        fc.append(f"[{k}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,"
                  f"trim=duration={b - a},setpts=PTS-STARTPTS+{a}/TB[c{k}]")
        fc.append(f"{last}[c{k}]overlay=enable='between(t,{a},{b})':eof_action=pass[v{k}]")
        last = f"[v{k}]"
        print(f"  plan {n} : rush réel {os.path.basename(p)}")
        k += 1
    ass = os.path.join(OUT, "subtitles.ass").replace(":", r"\:")
    fc.append(f"{last}ass='{ass}'[vout]")
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "9M", "-bufsize", "18M", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-14:TP=-1.0:LRA=9", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", str(DURATION), "-movflags", "+faststart", FINAL]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    os.chdir(HERE)
    sys.path.insert(0, HERE)
    import audio, render, subs
    only = sys.argv[1:] or ["audio", "video", "subs", "mux"]
    if "audio" in only:
        step("bande son", audio.build)
    if "video" in only:
        step("images", render.render_all)
    if "subs" in only:
        step("sous-titres", subs.build)
    if "mux" in only:
        step("assemblage", assemble)
        print("OK :", FINAL)

"""Rendu des images (multi-processus) + transitions (whip pan, zoom, glitch, flash, fondu)."""
import json, os, subprocess, sys
import numpy as np
from multiprocessing import Pool
from timeline import W, H, FPS, DURATION, SHOTS, GRADE, plan_at
import gfx
import scenes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
EV = None
TR = 0.16  # demi-durée d'une transition


def load_ev():
    global EV
    if EV is None:
        EV = json.load(open(os.path.join(OUT, "timings.json")))["events"]
    return EV


def shot_index(t):
    for i, (_, a, b, _) in enumerate(SHOTS):
        if a <= t < b:
            return i
    return len(SHOTS) - 1


def draw_shot(i, t, fi):
    name, a, b, _ = SHOTS[i]
    tt = min(max(t, a), b - 1e-3)
    return scenes.SCENES[name](tt, tt - a, b - a, load_ev(), fi)


def frame(fi):
    t = fi / FPS
    i = shot_index(t)
    name, a, b, _ = SHOTS[i]
    img = draw_shot(i, t, fi)
    # transition d'entrée de ce plan (après la coupe)
    tin = SHOTS[i][3]
    if t - a < TR and i > 0:
        p = (t - a) / TR  # 0 -> 1
        img = trans_in(tin, img, p, fi, i, t)
    # transition de sortie (avant la coupe suivante)
    if i + 1 < len(SHOTS) and b - t < TR:
        p = 1 - (b - t) / TR  # 0 -> 1
        nxt = SHOTS[i + 1][3]
        img = trans_out(nxt, img, p, fi, i, t)
    if tin == "fadein" and t < 0.35:
        img = img * (t / 0.35)
    img = gfx.post(img, fi, GRADE[plan_at(t)])
    return img


def trans_out(kind, img, p, fi, i, t):
    if kind == "whip":
        e = gfx.ease_in(p)
        return gfx.hblur(np.roll(img, -int(e * W * 0.45), 1), e)
    if kind == "whipv":
        e = gfx.ease_in(p)
        return gfx.vblur(np.roll(img, -int(e * H * 0.35), 0), e)
    if kind in ("zoom",):
        e = gfx.ease_in(p)
        return gfx.zoom_blur(gfx.camera(img, 1 + 0.6 * e), e) + 0.25 * e
    if kind == "glitch":
        return glitchify(img, p, fi)
    if kind == "flash":
        return img + gfx.ease_in(p) * np.array([1.0, 0.95, 0.8], np.float32)
    if kind == "dissolve":
        nb = draw_shot(i + 1, SHOTS[i + 1][1], fi)
        return img * (1 - 0.5 * p) + nb * 0.5 * p
    if kind == "zoomout":
        return img
    return img


def trans_in(kind, img, p, fi, i, t):
    q = 1 - p
    if kind == "whip":
        e = q ** 2
        return gfx.hblur(np.roll(img, int(e * W * 0.45), 1), e)
    if kind == "whipv":
        e = q ** 2
        return gfx.vblur(np.roll(img, int(e * H * 0.35), 0), e)
    if kind == "zoom":
        e = q ** 2
        return gfx.zoom_blur(gfx.camera(img, 1 + 0.35 * e), e) + 0.25 * e
    if kind == "glitch":
        return glitchify(img, q, fi)
    if kind == "flash":
        return img + (q ** 1.5) * np.array([1.0, 0.95, 0.8], np.float32)
    if kind == "dissolve":
        pb = draw_shot(i - 1, SHOTS[i - 1][2] - 1e-3, fi)
        return img * (0.5 + 0.5 * p) + pb * 0.5 * q
    return img


def glitchify(img, s, fi):
    r = np.random.default_rng(fi * 31)
    out = img.copy()
    for _ in range(int(4 + 10 * s)):
        y0 = r.integers(0, H - 60)
        h = r.integers(10, 120)
        out[y0:y0 + h] = np.roll(out[y0:y0 + h], int(r.integers(-160, 160) * s), 1)
    dx = int(24 * s) + 1
    out[..., 0] = np.roll(out[..., 0], dx, 1)
    out[..., 2] = np.roll(out[..., 2], -dx, 1)
    return out


def render_range(args):
    f0, f1, path = args
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", path],
                         stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        img = frame(fi)
        p.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return path


def render_all(workers=4):
    total = int(DURATION * FPS)
    os.makedirs(os.path.join(OUT, "parts"), exist_ok=True)
    # découpe en morceaux alignés sur les plans pour profiter des caches
    bounds = sorted(set([0, total] + [int(round(a * FPS)) for _, a, _, _ in SHOTS]))
    jobs = [(bounds[k], bounds[k + 1], os.path.join(OUT, "parts", f"p{k:03d}.mp4")) for k in range(len(bounds) - 1)]
    jobs.sort(key=lambda j: -(j[1] - j[0]))
    with Pool(workers) as pool:
        for i, pth in enumerate(pool.imap_unordered(render_range, jobs)):
            print(f"  segment {i + 1}/{len(jobs)} ok", flush=True)
    lst = os.path.join(OUT, "parts", "list.txt")
    with open(lst, "w") as f:
        for j in sorted(jobs):
            f.write(f"file '{os.path.basename(j[2])}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    os.path.join(OUT, "video_noaudio.mp4")], check=True)


def stills(times, path):
    from PIL import Image
    ims = [gfx.to_img(frame(int(t * FPS))).resize((W // 4, H // 4)) for t in times]
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W // 4, rows * H // 4))
    for k, im in enumerate(ims):
        sheet.paste(im, ((k % cols) * W // 4, (k // cols) * H // 4))
    sheet.save(path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        ts = [float(x) for x in sys.argv[3:]]
        stills(ts, sys.argv[2])
    else:
        render_all()

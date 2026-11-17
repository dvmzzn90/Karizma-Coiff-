"""Moteur de rendu de la vidéo « 7 jours sans électricité ».

- caméra virtuelle (zoom, panoramique, roulis, tremblement) ;
- animation du stickman par déformation locale de l'image (tête, corps, mains) ;
- étalonnage sombre, grain, vignette, lueurs, particules, pluie, éclairs, glitch ;
- sous-titres karaoké.

Usage : python3 film.py audio.wav sortie.mp4 [--preview t1,t2,...] [--from T --to T]
"""
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import timeline

W, H, FPS = 1080, 1920, 30
UP = 2.0  # sur-échantillonnage des images sources
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_BLACK = os.path.join(HERE, "fonts", "InterDisplay-Black.otf")
FONT_BOLD = os.path.join(HERE, "fonts", "InterDisplay-ExtraBold.otf")
YELLOW = (255, 210, 0)
RIG = {int(k): v for k, v in json.load(open(os.path.join(HERE, "rig.json"))).items()}
SCENES, SHOTS, TOTAL = timeline.build()

# ============================================================== utilitaires


def ease(p):
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


def lerp(a, b, p):
    return a + (b - a) * p


def sn(t, seed=0.0):
    """bruit lisse dans [-1, 1]"""
    return (math.sin(t * 1.0 + seed * 1.7) * 0.5 + math.sin(t * 2.31 + seed * 3.1) * 0.3
            + math.sin(t * 4.7 + seed * 5.3) * 0.2)


def bounce(lt, t0, amp, freq=13.0, damp=6.0):
    if lt < t0:
        return 0.0
    d = lt - t0
    return amp * math.exp(-d * damp) * math.cos(d * freq)


def hash01(*a):
    x = math.sin(sum(v * k for v, k in zip(a, (12.9898, 78.233, 37.719, 4.581)))) * 43758.5453
    return x - math.floor(x)


# ============================================================== animations (acting)
# Chaque fonction renvoie un dict :
#   faces : [(rot°, tx, ty, sx, sy)] par visage ; hands : [(tx, ty)] ; breath : facteur ; body : (tx, ty)


def _base(lt, n_faces=1, n_hands=0, breath_amp=0.012, sway=1.6, rate=0.35):
    faces = [[sway * math.sin(2 * math.pi * rate * lt + i), 2.5 * math.sin(2 * math.pi * rate * 2 * lt + i), 0, 1, 1]
             for i in range(n_faces)]
    return dict(faces=faces, hands=[[0, 0] for _ in range(n_hands)],
                breath=1 + breath_amp * math.sin(2 * math.pi * 0.33 * lt), body=[0, 0])


def act_gamer(lt, D, cut=None):
    a = _base(lt, 1, 1)
    f = a["faces"][0]
    f[2] += -5 * abs(math.sin(2 * math.pi * 1.05 * lt))  # hoche la tête en rythme
    f[0] += 1.5 * math.sin(2 * math.pi * 0.5 * lt)
    a["hands"][0] = [2.5 * sn(lt * 15), 3.5 * abs(math.sin(lt * 31))]  # spam de boutons
    if cut is not None:
        tc = cut * D
        if lt >= tc:
            d = lt - tc
            f[2] += bounce(lt, tc, -16)
            f[0] = 6 * ease(d / 0.6) + 1.2 * sn(lt * 6)
            f[3] = f[4] = 1
            burst = 1 if (d % 0.7) < 0.35 else 0.15
            a["hands"][0] = [3 * sn(lt * 22) * burst, 5 * abs(math.sin(lt * 40)) * burst]
    return a


def act_shock(lt, D):
    a = _base(lt, 1, 1, sway=0.8)
    f = a["faces"][0]
    f[2] += bounce(lt, 0, -26)
    f[4] = 1 + 0.07 * math.exp(-lt * 6) * math.cos(lt * 13)
    f[3] = 1 - 0.04 * math.exp(-lt * 6) * math.cos(lt * 13)
    f[0] += 1.4 * sn(lt * 16, 2) + 4 * math.sin(2 * math.pi * 0.7 * lt) * ease(lt / 0.8)
    burst = 1 if (lt % 0.8) < 0.4 else 0.1
    a["hands"][0] = [3 * sn(lt * 25) * burst, 5 * abs(math.sin(lt * 42)) * burst]
    return a


def act_phone(lt, D):
    a = _base(lt, 1, 2, sway=1.0)
    f = a["faces"][0]
    f[0] += 1.2 * sn(lt * 14, 1)
    f[2] += bounce(lt, 0.05, -10)
    burst = 0.5 + 0.5 * math.sin(2 * math.pi * 0.9 * lt) ** 2
    a["hands"][0] = [14 * math.sin(2 * math.pi * 7.5 * lt) * burst, 6 * math.cos(2 * math.pi * 7.5 * lt) * burst]
    a["hands"][1] = [8 * math.cos(2 * math.pi * 2.6 * lt), 6 * math.sin(2 * math.pi * 2.6 * lt)]  # se gratte la tête
    return a


def act_street(lt, D):
    a = _base(lt, 1, 2, sway=0.6)
    f = a["faces"][0]
    f[1] += 12 * math.sin(2 * math.pi * 0.55 * lt)
    f[0] += 5 * math.sin(2 * math.pi * 0.55 * lt + 1)
    f[2] += 1.5 * sn(lt * 12)
    a["hands"][0] = [5 * math.sin(2 * math.pi * 6 * lt), -40 * ease(lt / D) + 4 * math.cos(2 * math.pi * 6 * lt)]
    a["hands"][1] = [8 * math.cos(2 * math.pi * 2.8 * lt), 6 * math.sin(2 * math.pi * 2.8 * lt)]
    return a


def act_elevator(lt, D):
    a = _base(lt, 1, 1, sway=0.5)
    f = a["faces"][0]
    f[0] += 6 * math.sin(2 * math.pi * 2.0 * lt) * (0.3 + 0.7 * ease(lt / 0.4))  # « non, non »
    f[2] += bounce(lt, 0.0, -10)
    a["hands"][0] = [8 * math.sin(2 * math.pi * 1.4 * lt), -14 * abs(math.sin(2 * math.pi * 1.4 * lt))]
    return a


def act_reach(lt, D):
    a = _base(lt, 1, 1, sway=0.8)
    f = a["faces"][0]
    f[2] += bounce(lt, 0.1, -14)
    f[0] += 1.5 * sn(lt * 15)
    f[1] += 6 * math.sin(2 * math.pi * 0.6 * lt)
    a["hands"][0] = [30 * math.sin(math.pi * min(lt / 1.6, 1)) ** 2 + 3 * sn(lt * 18), 4 * sn(lt * 9, 3)]
    a["body"] = [8 * math.sin(math.pi * min(lt / 1.6, 1)) ** 2, 0]
    return a


def act_walk(lt, D, hands=False):
    a = _base(lt, 1, 2 if hands else 0, sway=0.5)
    f = a["faces"][0]
    step = abs(math.sin(2 * math.pi * 1.7 * lt))
    f[2] += -9 * step
    f[0] += 2.5 * math.sin(2 * math.pi * 0.85 * lt)
    f[1] += 6 * math.sin(2 * math.pi * 0.3 * lt)
    a["body"] = [0, -6 * step]
    if hands:
        a["hands"][0] = [3 * sn(lt * 9), -8 * step]
        a["hands"][1] = [3 * sn(lt * 9, 4), -8 * step]
    return a


def act_paper(lt, D):
    a = _base(lt, 1, 1, sway=0.5)
    f = a["faces"][0]
    f[2] += bounce(lt, 0.15 * D, -16)
    f[1] += -10 + 20 * ease(lt / D)  # lit la page de gauche à droite
    f[0] += 1.0 * sn(lt * 14)
    a["hands"][0] = [3 * sn(lt * 22), 4 * sn(lt * 19, 2)]
    return a


def act_days(lt, D):
    a = _base(lt, 4, 0, sway=1.0)
    fs = a["faces"]
    fs[0][0] += 5 * math.sin(2 * math.pi * 0.9 * lt)  # jour 1 : cherche partout
    fs[0][1] += 6 * math.sin(2 * math.pi * 0.9 * lt)
    fs[1][2] += 3 * math.sin(2 * math.pi * 2.2 * lt)  # jour 3 : mâche
    fs[2][0] += 4 * math.sin(2 * math.pi * 0.6 * lt)  # jour 5 : secoue la tête
    fs[3][2] += 2 * math.sin(2 * math.pi * 0.25 * lt)  # jour 7 : abattu
    fs[3][0] += 2 * math.sin(2 * math.pi * 0.2 * lt)
    return a


def act_window(lt, D, t_light=0.5):
    a = _base(lt, 1, 1, sway=0.8, rate=0.25)
    f = a["faces"][0]
    tl = t_light * D
    if lt >= tl:
        k = ease((lt - tl) / 0.7)
        f[1] += 14 * k
        f[2] += -8 * k + bounce(lt, tl, -14)
        f[0] += 3 * k
        a["hands"][0] = [8 * k, -4 * k]
    return a


def act_joy(lt, D):
    a = _base(lt, 1, 2, sway=1.0)
    f = a["faces"][0]
    pump = abs(math.sin(2 * math.pi * 1.6 * lt))
    f[2] += -12 * pump + bounce(lt, 0, -20)
    f[0] += 4 * math.sin(2 * math.pi * 0.8 * lt)
    a["hands"][0] = [5 * math.sin(2 * math.pi * 0.8 * lt), -32 * pump]
    a["hands"][1] = [4 * sn(lt * 14), -10 * abs(math.sin(2 * math.pi * 1.6 * lt + 0.8))]
    a["body"] = [0, -6 * pump]
    return a


def act_proud(lt, D):
    a = _base(lt, 1, 1, sway=1.0, rate=0.3)
    f = a["faces"][0]
    f[2] += 4 * math.sin(2 * math.pi * 1.0 * lt) ** 2  # acquiesce
    f[0] += 2 * math.sin(2 * math.pi * 0.5 * lt)
    a["hands"][0] = [0, 2 * math.sin(2 * math.pi * 0.33 * lt)]
    return a


def act_write(lt, D):
    a = _base(lt, 1, 1, sway=0.7)
    f = a["faces"][0]
    f[2] += 3 * math.sin(2 * math.pi * 1.3 * lt)
    f[0] += 1.5 * math.sin(2 * math.pi * 0.5 * lt)
    phase = (lt % 1.1) / 1.1
    a["hands"][0] = [5 * math.sin(2 * math.pi * 6 * lt) + 14 * phase - 7, 4 * math.cos(2 * math.pi * 6 * lt)]
    return a


def act_gaze(lt, D):
    a = _base(lt, 1, 0, sway=0.6, rate=0.2)
    f = a["faces"][0]
    f[0] += 2.5 * math.sin(2 * math.pi * 0.18 * lt)
    f[2] += 1.5 * math.sin(2 * math.pi * 0.4 * lt)
    return a


ACTS = dict(gamer=act_gamer, shock=act_shock, phone=act_phone, street=act_street, elevator=act_elevator,
            reach=act_reach, walk=act_walk, paper=act_paper, days=act_days, window=act_window, joy=act_joy,
            proud=act_proud, write=act_write, gaze=act_gaze)

# ============================================================== ressources (par processus)
R = {}


def init_worker():
    R["img"] = {}
    for i in range(1, 18):
        im = cv2.cvtColor(cv2.imread(os.path.join(HERE, "images", f"{i:02d}.png")), cv2.COLOR_BGR2RGB)
        up = cv2.resize(im, None, fx=UP, fy=UP, interpolation=cv2.INTER_LANCZOS4)
        blur = cv2.GaussianBlur(up, (0, 0), 1.2)
        up = cv2.addWeighted(up, 1.35, blur, -0.35, 0)  # léger renforcement
        R["img"][i] = up
    u, v = np.meshgrid(np.arange(W, dtype=np.float32) - W / 2, np.arange(H, dtype=np.float32) - H / 2)
    R["u"], R["v"] = u, v
    yy, xx = np.ogrid[:H, :W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    R["vignette"] = np.clip(1.12 - 0.42 * d ** 2, 0.45, 1.0).astype(np.float32)[..., None]
    rng = np.random.default_rng(3)
    R["grain"] = [rng.normal(0, 7, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    # angle/distance pour les rayons de soleil
    cx, cy = W * 0.85, H * 0.12
    R["ray_ang"] = np.arctan2(yy - cy, xx - cx).astype(np.float32)
    R["ray_fall"] = np.exp(-np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / 900).astype(np.float32)
    # fenêtres allumées de l'image 13 (pour les faire se rallumer une à une)
    im13 = cv2.cvtColor(cv2.imread(os.path.join(HERE, "images", "13.png")), cv2.COLOR_BGR2HSV)
    hh, ss, vv = im13[..., 0], im13[..., 1], im13[..., 2]
    m = ((vv > 170) & (ss > 90) & (hh < 40)).astype(np.uint8)
    m[1150:, :] = 0
    m[:, :380] = 0
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    n, lab = cv2.connectedComponents(m)
    lab_up = cv2.resize(lab.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_NEAREST).astype(np.int32)
    soft = cv2.GaussianBlur((lab_up > 0).astype(np.float32), (0, 0), 6)
    R["win13"] = (lab_up, soft, n)
    # points lumineux de l'image 2 (scintillement)
    g2 = cv2.cvtColor(cv2.imread(os.path.join(HERE, "images", "02.png")), cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(g2 > 235)
    sel = rng.choice(len(xs), size=min(140, len(xs)), replace=False)
    R["bright2"] = list(zip(xs[sel] * UP, ys[sel] * UP))
    R["cap_cache"] = {}
    R["glow"] = make_glow(260)


def make_glow(r):
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    g = np.exp(-(xx ** 2 + yy ** 2) / (2 * (r / 2.6) ** 2)).astype(np.float32)
    return g


# ============================================================== caméra + déformation


def cam_params(shot, p):
    keys = shot["cam"]
    for (p0, *a), (p1, *b) in zip(keys, keys[1:]):
        if p <= p1:
            q = ease((p - p0) / (p1 - p0)) if p1 > p0 else 1
            return [lerp(x, y, q) for x, y in zip(a, b)]
    return list(keys[-1][1:])


def camera(shot, t):
    img = R["img"][shot["img"]]
    ih, iw = img.shape[:2]
    p = (t - shot["start"]) / (shot["end"] - shot["start"])
    cx, cy, zoom, roll = cam_params(shot, p)
    lt = t - shot["start"]
    # tremblement caméra à la main + impacts
    amp = shot.get("shake", 0.0)
    for ti in shot.get("impacts", []):
        ti_abs = ti * (shot["end"] - shot["start"])
        if lt >= ti_abs:
            amp += 0.02 * math.exp(-(lt - ti_abs) * 7)
    if iw / ih > W / H:
        bh = ih
    else:
        bh = iw * H / W
    bh /= zoom
    k = bh / H  # pixels source par pixel de sortie
    bw = W * k
    x = cx * iw + amp * bw * sn(t * 9, 1)
    y = cy * ih + amp * bh * sn(t * 9, 7)
    x = min(max(x, bw / 2), iw - bw / 2)
    y = min(max(y, bh / 2), ih - bh / 2)
    return x, y, k, math.radians(roll)


def src_coords(cam):
    x, y, k, a = cam
    ca, sa = math.cos(a) * k, math.sin(a) * k
    u, v = R["u"], R["v"]
    xs = x + ca * u - sa * v
    ys = y + sa * u + ca * v
    return xs, ys


def to_out(cam, px, py):
    """coordonnées source (sur-échantillonnées) → coordonnées écran"""
    x, y, k, a = cam
    dx, dy = px - x, py - y
    ca, sa = math.cos(-a) / k, math.sin(-a) / k
    return ca * dx - sa * dy + W / 2, sa * dx + ca * dy + H / 2


def smooth_w(d, r1, r2):
    q = np.clip((r2 - d) / (r2 - r1), 0, 1)
    return q * q * (3 - 2 * q)


def puppet(xs, ys, img_id, act):
    """Déplacement inverse : renvoie (mapx, mapy) après animation du personnage."""
    rig = RIG.get(img_id)
    if not rig or not act:
        return xs, ys
    dx = np.zeros_like(xs)
    dy = np.zeros_like(ys)
    for (cx, cy, r), (rot, tx, ty, sx, sy) in zip(rig["faces"], act["faces"]):
        cx, cy, r = cx * UP, cy * UP, r * UP
        tx, ty = tx * UP, ty * UP
        # boîte englobante pour limiter le calcul
        x0, x1 = cx - 2.0 * r, cx + 2.0 * r
        y0, y1 = cy - 2.0 * r, cy + 3.8 * r
        box = (xs > x0) & (xs < x1) & (ys > y0) & (ys < y1)
        if not box.any():
            continue
        X, Y = xs[box], ys[box]
        d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        w = smooth_w(d, 1.2 * r, 1.95 * r)
        px, py = cx, cy + 0.95 * r  # pivot au cou
        th = math.radians(rot)
        c, s = math.cos(th), math.sin(th)
        rx, ry = (X - px) * sx, (Y - py) * sy
        qx = px + c * rx - s * ry + tx
        qy = py + s * rx + c * ry + ty
        dx[box] += w * (qx - X)
        dy[box] += w * (qy - Y)
        # corps : respiration + translation, zone ovale sous la tête
        bcx, bcy = cx + act["body"][0] * 0, cy + 2.3 * r
        db = np.sqrt(((X - bcx) / 1.5) ** 2 + ((Y - bcy) / 1.4) ** 2)
        wb = smooth_w(db, 0.6 * r, 1.25 * r) * (1 - w)
        base = cy + 3.6 * r
        br = act["breath"]
        dy[box] += wb * ((br - 1) * (Y - base) + act["body"][1] * UP)
        dx[box] += wb * ((br - 1) * 0.5 * (X - bcx) + act["body"][0] * UP)
    for (hx, hy), (tx, ty) in zip(rig.get("hands", []), act.get("hands", [])):
        if tx == 0 and ty == 0:
            continue
        hx, hy = hx * UP, hy * UP
        rr = 150 * UP
        box = (np.abs(xs - hx) < rr) & (np.abs(ys - hy) < rr)
        if not box.any():
            continue
        X, Y = xs[box], ys[box]
        d = np.sqrt((X - hx) ** 2 + (Y - hy) ** 2)
        w = smooth_w(d, 45 * UP, rr)
        dx[box] += w * tx * UP
        dy[box] += w * ty * UP
    return xs - dx, ys - dy


def source_image(shot, t):
    img = R["img"][shot["img"]]
    lt = t - shot["start"]
    D = shot["end"] - shot["start"]
    if "lightsback" in shot.get("fx", []):
        lab, soft, n = R["win13"]
        tl = shot["act"][1].get("t_light", 0.5) * D
        on = np.zeros(n + 1, np.float32)
        for k in range(1, n + 1):
            tk = tl + hash01(k, 3) * 2.6
            if k % 9 == 0:
                tk = tl  # les premières fenêtres
            if lt >= tk:
                d = lt - tk
                on[k] = 1.0 if d > 0.35 else (1.0 if int(d * 30) % 3 else 0.3)  # grésille en s'allumant
        fac = 0.12 + 0.88 * on[lab]
        fac = soft * fac + (1 - soft) * 1.0
        img = (img.astype(np.float32) * fac[..., None]).astype(np.uint8)
    return img


def render_shot(shot, t):
    cam = camera(shot, t)
    xs, ys = src_coords(cam)
    act = None
    if shot.get("act"):
        name, kw = shot["act"]
        act = ACTS[name](t - shot["start"], shot["end"] - shot["start"], **kw)
    mx, my = puppet(xs, ys, shot["img"], act)
    img = source_image(shot, t)
    frame = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    frame = frame.astype(np.float32)
    frame = grade(frame, shot, t)
    frame = effects(frame, shot, t, cam)
    return frame


# ============================================================== étalonnage & effets


def grade(f, shot, t):
    g = shot.get("grade", {})
    lt = t - shot["start"]
    D = shot["end"] - shot["start"]
    if g.get("night"):
        gray = f.mean(axis=2, keepdims=True)
        f = gray + (f - gray) * 0.35
        f = f * np.array([0.24, 0.27, 0.45], np.float32) + np.array([0, 2, 8], np.float32)
    bright = g.get("bright", 1.0)
    sat = g.get("sat", 0.92)
    if "powercut" in shot.get("fx", []):
        tc = shot["act"][1]["cut"] * D
        if lt >= tc:
            d = lt - tc
            seq = [0.15, 1.0, 0.1, 0.8, 0.05, 0.4, 0.02]
            idx = int(d / 0.07)
            bright *= seq[idx] if idx < len(seq) else 0.42 + 0.04 * math.sin(lt * 3)
            if idx >= len(seq) - 1:
                gray = f.mean(axis=2, keepdims=True)
                f = gray + (f - gray) * 0.4
                f = f * np.array([0.6, 0.75, 1.3], np.float32)
    gray = f.mean(axis=2, keepdims=True)
    f = gray + (f - gray) * sat
    # contraste « sombre » : noirs écrasés, ombres froides
    f = f * bright
    f = np.clip((f - 10) * 1.08, 0, 255)
    shadow = np.clip(1 - f.mean(axis=2, keepdims=True) / 140, 0, 1)
    f = f + shadow * np.array([-3, 0, 8], np.float32)
    return f


def add_glow(f, cam, px, py, intensity, color, scale=1.0):
    ox, oy = to_out(cam, px * UP, py * UP)
    g = R["glow"]
    if scale != 1.0:
        g = cv2.resize(g, None, fx=scale, fy=scale)
    r = g.shape[0] // 2
    x0, y0 = int(ox) - r, int(oy) - r
    x1, y1 = x0 + g.shape[1], y0 + g.shape[0]
    cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if cx0 >= cx1 or cy0 >= cy1:
        return
    sub = g[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0][..., None]
    f[cy0:cy1, cx0:cx1] += sub * intensity * np.array(color, np.float32)


def flicker(t, seed=0):
    return 0.75 + 0.15 * math.sin(t * 13 + seed) + 0.1 * math.sin(t * 29.7 + seed * 2)


def particles(f, t, n, seed, color, size, speed, area=(0, 0, W, H), drift=0.0):
    ov = np.zeros((H, W), np.float32)
    x0, y0, x1, y1 = area
    for i in range(n):
        bx = x0 + hash01(i, seed) * (x1 - x0)
        by = y0 + hash01(i, seed + 1) * (y1 - y0)
        sp = speed * (0.5 + hash01(i, seed + 2))
        x = (bx + 25 * math.sin(t * 0.7 + i) + drift * t) % W
        y = y0 + ((by - y0 - sp * t) % (y1 - y0))
        tw = 0.5 + 0.5 * math.sin(t * (1 + hash01(i, seed + 3) * 3) + i)
        cv2.circle(ov, (int(x), int(y)), int(size * (0.6 + hash01(i, seed + 4))), tw, -1, cv2.LINE_AA)
    ov = cv2.GaussianBlur(ov, (0, 0), 1.5)
    f += ov[..., None] * np.array(color, np.float32)


def rain(f, t):
    ov = np.zeros((H, W), np.float32)
    for i in range(170):
        x = hash01(i, 11) * (W + 300) - 150
        sp = 2600 + 900 * hash01(i, 12)
        y = (hash01(i, 13) * (H + 400) + sp * t) % (H + 400) - 200
        ln = 50 + 40 * hash01(i, 14)
        cv2.line(ov, (int(x), int(y)), (int(x - ln * 0.18), int(y - ln)), 0.5 + 0.5 * hash01(i, 15), 2, cv2.LINE_AA)
    f += ov[..., None] * np.array([90, 105, 130], np.float32)


def glitch(f, t, strength):
    if strength <= 0:
        return f
    s = int(18 * strength)
    out = f.copy()
    out[..., 0] = np.roll(f[..., 0], s, axis=1)
    out[..., 2] = np.roll(f[..., 2], -s, axis=1)
    rng = np.random.default_rng(int(t * 1000))
    for _ in range(int(8 * strength) + 1):
        y = rng.integers(0, H - 80)
        h = rng.integers(10, 80)
        out[y:y + h] = np.roll(out[y:y + h], int(rng.integers(-90, 90) * strength), axis=1)
    out[::4] *= 0.75
    return out


def effects(f, shot, t, cam):
    fx = shot.get("fx", [])
    lt = t - shot["start"]
    D = shot["end"] - shot["start"]
    if "screenglow" in fx:
        add_glow(f, cam, 800, 950, 70 * flicker(t * 2, 1), (0.3, 0.5, 1.0), 1.6)
    if "twinkle" in fx:
        ov = np.zeros((H, W), np.float32)
        for i, (px, py) in enumerate(R["bright2"]):
            ox, oy = to_out(cam, px, py)
            if 0 <= ox < W and 0 <= oy < H:
                a = max(0.0, math.sin(t * (2 + hash01(i, 5) * 3) + i)) ** 6
                if a > 0.05:
                    cv2.line(ov, (int(ox - 14 * a), int(oy)), (int(ox + 14 * a), int(oy)), a, 2, cv2.LINE_AA)
                    cv2.line(ov, (int(ox), int(oy - 14 * a)), (int(ox), int(oy + 14 * a)), a, 2, cv2.LINE_AA)
        f += cv2.GaussianBlur(ov, (0, 0), 1.2)[..., None] * np.array([255, 235, 200], np.float32)
    if "powercut" in fx:
        tc = shot["act"][1]["cut"] * D
        if lt < tc:
            add_glow(f, cam, 800, 950, 70 * flicker(t * 2, 1), (0.3, 0.5, 1.0), 1.6)
        elif lt - tc < 0.45:
            f = glitch(f, t, 1 - (lt - tc) / 0.45)
    if "glitchpanels" in fx:
        p = lt / D
        for pc in (0.0, 0.40, 0.81):
            d = abs(p - pc) * D
            if d < 0.25:
                f = glitch(f, t, 0.8 * (1 - d / 0.25))
    if "rain" in fx:
        rain(f, t)
    if "dust" in fx:
        particles(f, t, 45, 21, (110, 100, 90), 2.2, 25)
    if "torches" in fx:
        for i in range(7):
            px = 470 + 300 * math.sin(t * 0.4 + i * 1.9) * hash01(i, 2)
            py = 900 + 600 * hash01(i, 8) + 30 * math.sin(t * 0.9 + i)
            add_glow(f, cam, px, py, 55 * (0.6 + 0.4 * math.sin(t * 5 + i)), (1.0, 0.85, 0.5), 0.22)
    if "lightning" in fx:
        for tl in (0.35, 0.47):
            d = lt - tl * D
            if 0 <= d < 0.22:
                k = (1 - d / 0.22) * (1 if int(d * 40) % 2 == 0 else 0.4)
                f += k * np.array([120, 130, 175], np.float32)
    if "candles" in fx:
        add_glow(f, cam, 880, 300, 90 * flicker(t, 2), (1.0, 0.7, 0.35), 0.8)
        add_glow(f, cam, 895, 520, 70 * flicker(t, 4), (1.0, 0.65, 0.3), 0.6)
    if "lantern13" in fx:
        add_glow(f, cam, 900, 1520, 95 * flicker(t, 3), (1.0, 0.65, 0.3), 1.2)
    if "lantern14" in fx:
        add_glow(f, cam, 900, 1520, 95 * flicker(t, 5), (1.0, 0.65, 0.3), 1.2)
    if "lantern15" in fx:
        add_glow(f, cam, 60, 1640, 110 * flicker(t, 6), (1.0, 0.65, 0.3), 1.3)
    if "sparkles" in fx:
        hx, hy = to_out(cam, 607 * UP, 560 * UP)
        particles(f, t, 30, 31, (255, 220, 120), 3.0, 140, area=(int(hx) - 260, int(hy) - 500, int(hx) + 260, int(hy) + 60))
    if "sunrays" in fx:
        rays = (0.5 + 0.5 * np.sin(R["ray_ang"] * 14 + t * 0.35)) ** 5 * R["ray_fall"]
        f += rays[..., None] * np.array([70, 45, 20], np.float32)
    if "sunglow" in fx:
        add_glow(f, cam, 690, 1050, 80 * (0.85 + 0.15 * math.sin(t * 1.5)), (1.0, 0.75, 0.4), 1.5)
    if "lightsback" in fx:
        tl = shot["act"][1].get("t_light", 0.5) * D
        if lt < tl:
            f *= 0.75
    return f


def checks(frame, shot, t, cam):
    """coches vertes qui « claquent » sur le panneau des leçons (image 16)"""
    if "checks" not in shot:
        return
    D = shot["end"] - shot["start"]
    lt = t - shot["start"]
    pos = [(522, 668), (512, 832), (508, 1002)]
    d = ImageDraw.Draw(frame)
    for (px, py), tc in zip(pos, shot["checks"]):
        dt = lt - tc * D
        if dt < 0:
            continue
        s = (1 + 0.8 * math.exp(-dt * 9)) / cam[2] * UP
        ox, oy = to_out(cam, px * UP, py * UP)
        pts = [(ox - 30 * s, oy), (ox - 8 * s, oy + 24 * s), (ox + 36 * s, oy - 34 * s)]
        a = int(255 * min(1, dt / 0.08))
        d.line(pts, fill=(0, 0, 0, a), width=int(22 * s), joint="curve")
        d.line(pts, fill=(60, 220, 60, a), width=int(12 * s), joint="curve")
        if dt < 0.4:
            rr = 60 * s * (1 + dt * 3)
            d.ellipse((ox - rr, oy - rr, ox + rr, oy + rr), outline=(255, 255, 255, int(200 * (1 - dt / 0.4))), width=5)


# ============================================================== texte


def font(size, black=True):
    key = (size, black)
    if key not in R:
        R[key] = ImageFont.truetype(FONT_BLACK if black else FONT_BOLD, size)
    return R[key]


def caption_chunks(scene):
    txt = scene["vo"].replace("…", "… ")
    for p in ("?", "!", ":", ";"):
        txt = txt.replace(" " + p, "\u00a0" + p)
    words = [w for w in txt.split(" ") if w]
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        txt = " ".join(cur)
        if len(txt) > 16 or (w[-1] in ".?!…," and len(txt) > 6):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # minutage proportionnel au nombre de lettres (+ pause après la ponctuation)
    if scene["vo_len"]:
        a, b = scene["start"] + timeline.VO_OFFSET, scene["start"] + timeline.VO_OFFSET + scene["vo_len"]
    else:
        a, b = scene["start"] + 0.2, scene["end"] - 0.25
    wts = []
    for c in chunks:
        wts.append([len(w) + 2 + (4 if w[-1] in ".?!…" else 1.5 if w[-1] == "," else 0) for w in c])
    tot = sum(sum(x) for x in wts)
    out, t = [], a
    for c, wt in zip(chunks, wts):
        times = []
        for w in wt:
            times.append(t)
            t += (b - a) * w / tot
        out.append((c, times, t))
    return out


CAPTIONS = []
for _sc in SCENES:
    if _sc["n"] == 12:
        continue
    for c, times, end in caption_chunks(_sc):
        CAPTIONS.append((c, times, end))


def caption_img(words, active):
    key = (tuple(words), active)
    if key in R["cap_cache"]:
        return R["cap_cache"][key]
    f = font(88)
    words = [w.upper() for w in words]
    space = f.getlength(" ")
    lines, cur, cw = [], [], 0
    for i, w in enumerate(words):
        wl = f.getlength(w)
        if cur and cw + space + wl > 920:
            lines.append(cur)
            cur, cw = [], 0
        cur.append((i, w, wl))
        cw += wl + (space if cw else 0)
    lines.append(cur)
    lh = 104
    img = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for li, line in enumerate(lines):
        tw = sum(x[2] for x in line) + space * (len(line) - 1)
        x = (W - tw) / 2
        y = 30 + li * lh
        for i, w, wl in line:
            col = YELLOW if i == active else (255, 255, 255)
            d.text((x, y), w, font=f, fill=col, stroke_width=8, stroke_fill=(0, 0, 0))
            x += wl + space
    sh = img.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.55))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(sh)
    out = Image.alpha_composite(shadow, img)
    R["cap_cache"][key] = out
    return out


def badge_img(text):
    key = ("badge", text)
    if key in R["cap_cache"]:
        return R["cap_cache"][key]
    f = font(50)
    tw = f.getlength(text)
    b = Image.new("RGBA", (int(tw) + 80, 92), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rounded_rectangle((0, 0, b.width - 1, b.height - 1), radius=20, fill=(10, 10, 14, 200), outline=(200, 30, 40, 255), width=4)
    d.ellipse((22, 38, 38, 54), fill=(230, 30, 40))
    d.text((50, 16), text, font=f, fill=(255, 255, 255))
    R["cap_cache"][key] = b
    return b


def big_text(lines, size, color=(255, 255, 255), stroke=12):
    key = ("big", tuple(lines), size, color)
    if key in R["cap_cache"]:
        return R["cap_cache"][key]
    f = font(size)
    lh = int(size * 1.12)
    img = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text(((W - f.getlength(l)) / 2, 30 + i * lh), l, font=f, fill=color, stroke_width=stroke, stroke_fill=(0, 0, 0))
    sh = img.split()[3].filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.7))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(sh)
    out = Image.alpha_composite(shadow, img)
    R["cap_cache"][key] = out
    return out


def paste(frame, layer, cx, cy, scale=1.0, alpha=1.0):
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if alpha < 1.0:
        layer = layer.copy()
        layer.putalpha(layer.split()[3].point(lambda v: int(v * alpha)))
    frame.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def text_overlays(frame, t):
    # sous-titres karaoké
    for words, times, end in CAPTIONS:
        if times[0] <= t < end:
            active = max(i for i, s in enumerate(times) if s <= t)
            dt = t - times[0]
            pop = 1 + 0.18 * math.exp(-dt * 16) * math.cos(dt * 22)
            wpop = 1 + 0.05 * math.exp(-(t - times[active]) * 18)
            paste(frame, caption_img(words, active), W / 2, 1390, pop * wpop, min(1.0, dt / 0.06))
            break
    # badges (heure / jour)
    for sc in SCENES:
        if sc.get("badge") and sc["start"] <= t < sc["end"]:
            dt = t - sc["start"]
            b = badge_img(sc["badge"])
            s = 1 + 0.3 * math.exp(-dt * 10)
            frame.alpha_composite(b.resize((int(b.width * s), int(b.height * s))), (50, 200))
    # appel à l'action final
    sc = SCENES[-1]
    if t >= sc["start"]:
        dt = t - sc["start"]
        D = sc["end"] - sc["start"]
        paste(frame, big_text(["TU TIENDRAIS", "7 JOURS ?"], 128, YELLOW, 14), W / 2, 520,
              1 + 0.5 * math.exp(-dt * 9), min(1, dt / 0.12))
        if dt > 0.45 * D:
            d2 = dt - 0.45 * D
            bob = 10 * math.sin(d2 * 6)
            paste(frame, big_text(["DIS-LE EN", "COMMENTAIRE ▼"], 76), W / 2, 1290 + bob,
                  1 + 0.3 * math.exp(-d2 * 10), min(1, d2 / 0.15))


# ============================================================== transitions & image finale


def shot_at(t):
    idx = max(i for i, s in enumerate(SHOTS) if s["start"] <= t)
    return idx, SHOTS[idx]


def render_frame(t):
    idx, sh = shot_at(t)
    f = render_shot(sh, t)
    lt = t - sh["start"]
    tr = sh.get("trans", "cut")
    if idx > 0:
        prev = SHOTS[idx - 1]
        if tr == "fade" and lt < 0.45:
            f = lerp(render_shot(prev, t), f, ease(lt / 0.45))
        elif tr == "whip" and lt < 0.24:
            q = lt / 0.24
            a = render_shot(prev, t) if q < 0.5 else f
            k = int(70 * (1 - abs(q - 0.5) * 2)) * 2 + 1
            f = cv2.blur(a, (k, 1)) if k > 1 else a
        elif tr == "flash" and lt < 0.25:
            f = f + 255 * (1 - lt / 0.25) ** 2
        elif tr == "black" and lt < 0.35:
            f = f * ease(lt / 0.35)
        elif tr == "glitch" and lt < 0.2:
            f = glitch(f, t, 1 - lt / 0.2)
    elif lt < 0.5:
        f = f * ease(lt / 0.5)
    # fin : noir
    if t > TOTAL - 0.25:
        f = f * max(0.0, (TOTAL - t) / 0.25)
    f = f * R["vignette"]
    g = R["grain"][int(t * FPS) % 6]
    f += cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    frame = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).convert("RGBA")
    cam = camera(sh, t)
    checks(frame, sh, t, cam)
    text_overlays(frame, t)
    return np.asarray(frame.convert("RGB"))


def _job(i):
    return render_frame(i / FPS).tobytes()


def main():
    args = sys.argv[1:]
    if args and args[0] == "--preview":
        init_worker()
        out = args[2]
        ts = [float(x) for x in args[1].split(",")]
        ims = [Image.fromarray(render_frame(t)).resize((360, 640)) for t in ts]
        sheet = Image.new("RGB", (360 * len(ims), 640))
        for k, im in enumerate(ims):
            sheet.paste(im, (360 * k, 0))
        sheet.save(out)
        return
    audio, out = args[0], args[1]
    total = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "slow", "-b:v", "7M", "-maxrate", "9M", "-bufsize", "18M",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4, initializer=init_worker) as pool:
        for i, buf in enumerate(pool.imap(_job, range(total), chunksize=4)):
            p.stdin.write(buf)
            if i % 300 == 0:
                print(f"{i}/{total}", flush=True)
    p.stdin.close()
    p.wait()
    print("ok", out, round(TOTAL, 2), "s")


if __name__ == "__main__":
    main()

"""Les 24 sous-plans, dessinés de façon procédurale (version animatique).

Chaque scène : fn(t_global, t_local, duree, ev, fi) -> image float32 HxWx3.
Les éléments statiques sont mis en cache dans CACHE.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from timeline import W, H
from gfx import *

CACHE = {}


def cached(key, fn):
    if key not in CACHE:
        CACHE[key] = fn()
    return CACHE[key]


def rngf(seed):
    return np.random.default_rng(seed)


# =================================================================== ŒIL
EYE_C = (540, 930)
EYE_HW, EYE_HH = 450, 300
IRIS_R = 290


def _fur(seed=1, base="#1a120c", tone=0.16):
    r = rngf(seed)
    streak = np.asarray(Image.fromarray((r.random((70, 300)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
    fine = np.asarray(Image.fromarray((r.random((H // 3, W // 3)) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255
    n = streak * 0.6 + fine * 0.4
    col = hexc(base)
    a = col * (0.55 + n[..., None] * 1.1)
    # léger halo de fourrure plus claire autour de l'œil
    d = np.sqrt(((XX - EYE_C[0]) / 1.4) ** 2 + (YY - EYE_C[1]) ** 2)
    ring = np.clip(1 - np.abs(d - 380) / 260, 0, 1) ** 2
    a = a + ring[..., None] * hexc("#5a3a1e") * 0.5 * n[..., None]
    return a.astype(np.float32)


def _iris(reflect=None):
    s = IRIS_R * 2
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) - IRIS_R
    r = np.sqrt(xx ** 2 + yy ** 2) / IRIS_R
    ang = (np.arctan2(yy, xx) + np.pi) / (2 * np.pi)
    rr = rngf(5)
    fib1 = np.interp(ang * 900, np.arange(901), rr.random(901))
    fib2 = np.interp(ang * 240, np.arange(241), rr.random(241))
    fib = fib1 * 0.6 + fib2 * 0.4
    centre, mid, edge = hexc("#ffe08a"), hexc("#f0a020"), hexc("#7a3c06")
    t = np.clip(r, 0, 1)[..., None]
    col = np.where(t < 0.45, centre + (mid - centre) * (t / 0.45), mid + (edge - mid) * ((t - 0.45) / 0.55))
    col = col * (0.72 + 0.45 * fib[..., None] * (0.4 + r[..., None]))
    col *= (1 - 0.75 * np.clip((r[..., None] - 0.86) / 0.14, 0, 1))  # anneau limbique
    col += hexc("#3a6a10") * np.clip(0.35 - r, 0, 1)[..., None] * 0.6   # reflet vert autour de la pupille
    if reflect is not None:
        ref = np.asarray(Image.fromarray((np.clip(reflect, 0, 1) * 255).astype(np.uint8)).resize((s, s)), np.float32) / 255
        col = col * 0.55 + ref * 0.75
    a = np.clip((1 - r) * 40, 0, 1)
    return np.dstack([np.clip(col, 0, 1), a]).astype(np.float32)


def eye(open_amt=1.0, pupil=40.0, reflect_key=None, fur_seed=1, look=(0, 0)):
    fur = cached(("fur", fur_seed), lambda: _fur(fur_seed))
    a = fur.copy()
    if open_amt <= 0.01:
        # paupière fermée : ligne sombre
        cx, cy = EYE_C
        y0, y1 = cy - 30, cy + 30
        xs = XX[y0:y1, cx - EYE_HW:cx + EYE_HW] - cx
        lid = np.clip(1 - np.abs(YY[y0:y1, cx - EYE_HW:cx + EYE_HW] - cy - 8 * (1 - (xs / EYE_HW) ** 2)) / 7, 0, 1)
        a[y0:y1, cx - EYE_HW:cx + EYE_HW] *= (1 - lid[..., None] * 0.9)
        return a
    cx, cy = EYE_C
    x0, x1, y0, y1 = cx - EYE_HW - 20, cx + EYE_HW + 20, cy - EYE_HH - 30, cy + EYE_HH + 30
    X = XX[y0:y1, x0:x1] - cx
    Y = YY[y0:y1, x0:x1] - cy
    hh = EYE_HH * open_amt * np.clip(1 - (X / EYE_HW) ** 2, 0, 1) ** 0.62
    # léger angle félin
    Yt = Y + X * 0.10
    inside = np.clip((hh - np.abs(Yt)) / 4, 0, 1)
    rim = np.clip((hh + 16 - np.abs(Yt)) / 4, 0, 1) - inside
    reg = a[y0:y1, x0:x1]
    # globe : iris + sclère sombre
    globe = np.zeros_like(reg) + hexc("#3a2a10") * 0.6
    key = ("iris", reflect_key)
    iris = cached(key, lambda: _iris(CACHE.get(("reflect_img", reflect_key))))
    ix, iy = int(cx - x0 + look[0]), int(cy - y0 + look[1])
    tmp = globe
    tmp = paste(tmp, iris, ix, iy)
    # pupille fendue
    pw = max(6.0, pupil)
    pd = (((X - look[0]) / pw) ** 2 + ((Y - look[1]) / (IRIS_R * 0.92)) ** 2)
    pm = np.clip((1 - pd) * 6, 0, 1)
    tmp = tmp * (1 - pm[..., None] * 0.97)
    # ombre de la paupière supérieure
    shade = np.clip(1 - (Yt + hh) / (hh * 0.9 + 1e-3), 0, 1) ** 1.5
    tmp = tmp * (1 - 0.55 * shade[..., None])
    # reflets spéculaires
    sp = np.clip(1 - np.sqrt(((X + 120) / 70) ** 2 + ((Y + 110) / 46) ** 2), 0, 1) ** 1.3
    sp2 = np.clip(1 - np.sqrt(((X + 40) / 22) ** 2 + ((Y + 150) / 16) ** 2), 0, 1)
    sp3 = np.clip(1 - np.sqrt(((X - 160) / 120) ** 2 + ((Y - 120) / 30) ** 2), 0, 1) ** 2
    tmp = tmp + (sp * 0.95 + sp2 * 0.8 + sp3 * 0.18)[..., None]
    out = reg * (1 - inside[..., None]) + tmp * inside[..., None]
    out = out * (1 - rim[..., None] * 0.95)
    a[y0:y1, x0:x1] = out
    return a


# =================================================================== PLAN 1 : main → patte
def _sheet():
    a = vgrad([(0, "#05070c"), (0.5, "#0b1220"), (1, "#070a10")])
    folds = (np.sin(XX * 0.008 + YY * 0.004 + np.sin(YY * 0.0025) * 2.2) * 0.5 + 0.5) ** 2
    folds2 = (np.sin(XX * 0.019 - YY * 0.006 + 1.3) * 0.5 + 0.5) ** 3
    lum = 0.10 + 0.20 * folds + 0.08 * folds2
    beam = np.clip(1 - np.abs((XX - 0.55 * YY) - 80) / 420, 0, 1) ** 1.5  # lumière lunaire de la fenêtre
    lum = lum * (0.45 + 1.4 * beam)
    a = a + lum[..., None] * hexc("#8aa6d0") * 0.75
    return a.astype(np.float32)


def _hand_geom(m, drag):
    pcx, pcy = 600, 1230 + drag
    fingers = []
    base_pts = [(-170, -150, -122), (-60, -205, -100), (50, -205, -86), (150, -160, -72)]
    lens = [300, 360, 340, 270]
    for (bx, by, ang), L in zip(base_pts, lens):
        L2 = L * (1 - 0.42 * m)
        a = math.radians(ang)
        p0 = (pcx + bx, pcy + by)
        p1 = (p0[0] + math.cos(a) * L2, p0[1] + math.sin(a) * L2)
        fingers.append((p0, p1, a))
    thumb0 = (pcx + 200, pcy - 20)
    ta = math.radians(-40)
    TL = 230 * (1 - 0.4 * m)
    thumb1 = (thumb0[0] + math.cos(ta) * TL, thumb0[1] + math.sin(ta) * TL)
    return (pcx, pcy), fingers, (thumb0, thumb1, ta)


def _draw_hand(m, drag):
    (pcx, pcy), fingers, thumb = _hand_geom(m, drag)
    skin = np.array([150, 160, 185])  # peau sous lumière lunaire
    fur = np.array([38, 32, 30])
    col = tuple(int(x) for x in skin * (1 - m) + fur * m)
    edge = tuple(int(x * 0.6) for x in col)
    fw = int(78 * (1 + 0.45 * m))
    r = rngf(11)

    def fn(d, im):
        d.ellipse([pcx - 260, pcy - 240, pcx + 260, pcy + 260], fill=edge)
        d.ellipse([pcx - 250, pcy - 230, pcx + 250, pcy + 250], fill=col)
        d.polygon([(pcx - 220, pcy + 120), (pcx + 240, pcy + 80), (pcx + 420, H + 50), (pcx - 60, H + 50)], fill=col)
        for p0, p1, a in fingers + [thumb]:
            d.line([p0, p1], fill=edge, width=fw + 8)
            d.line([p0, p1], fill=col, width=fw)
            d.ellipse([p1[0] - fw / 2, p1[1] - fw / 2, p1[0] + fw / 2, p1[1] + fw / 2], fill=col)
        if m > 0.25:  # poils
            k = (m - 0.25) / 0.75
            for _ in range(int(900 * k)):
                p0, p1, a = fingers[r.integers(0, 4)] if r.random() < 0.5 else (None, None, None)
                if p0 is None:
                    ang = r.uniform(0, 2 * math.pi)
                    x, y = pcx + math.cos(ang) * 245, pcy + math.sin(ang) * 245
                else:
                    u = r.random()
                    x, y = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
                    nx, ny = -math.sin(a), math.cos(a)
                    s = r.choice([-1, 1]) * fw / 2
                    x, y = x + nx * s, y + ny * s
                l = r.uniform(10, 34) * k
                aa = r.uniform(0, 2 * math.pi)
                c = int(20 + r.random() * 40)
                d.line([(x, y), (x + math.cos(aa) * l, y + math.sin(aa) * l)], fill=(c, c - 4, c - 8), width=2)
        if m > 0.45:  # griffes
            k = min(1, (m - 0.45) / 0.4)
            for p0, p1, a in fingers + [thumb]:
                L = 110 * k
                tip = (p1[0] + math.cos(a + 0.35) * L, p1[1] + math.sin(a + 0.35) * L)
                nx, ny = -math.sin(a) * fw * 0.28, math.cos(a) * fw * 0.28
                d.polygon([(p1[0] + nx, p1[1] + ny), (p1[0] - nx, p1[1] - ny), tip], fill=(222, 214, 196))
                d.line([(p1[0] + nx * 0.4, p1[1] + ny * 0.4), tip], fill=(255, 250, 235), width=3)
    return layer_draw(fn)


def scene_hand(t, lt, dur, ev, fi):
    a = cached("sheet", _sheet).copy()
    tear_t = ev["tear"]
    m = ease((lt - 0.2) / 1.6)
    drag = 160 * ease((t - tear_t) / 0.35) if t > tear_t else 0
    # déchirures dans le drap
    if t > tear_t:
        k = ease((t - tear_t) / 0.35)
        _, fingers, _ = _hand_geom(1.0, 0)
        def fn(d, im):
            r = rngf(21)
            for p0, p1, ang in fingers:
                L = 110
                tip = (p1[0] + math.cos(ang + 0.35) * L, p1[1] + math.sin(ang + 0.35) * L)
                y_end = tip[1] + 160 * k + 40
                pts_l, pts_r = [], []
                for i in range(12):
                    u = i / 11
                    y = tip[1] + (y_end - tip[1]) * u
                    w = 16 * math.sin(math.pi * u) + 3
                    pts_l.append((tip[0] - w + r.uniform(-4, 4), y))
                    pts_r.append((tip[0] + w + r.uniform(-4, 4), y))
                d.polygon(pts_l + pts_r[::-1], fill=(2, 3, 6, 255))
                for i in range(10):
                    y = r.uniform(tip[1], y_end)
                    d.line([(tip[0] - 14, y), (tip[0] - 26 - r.uniform(0, 14), y + r.uniform(-8, 8))], fill=(150, 165, 190, 200), width=2)
                    d.line([(tip[0] + 14, y), (tip[0] + 26 + r.uniform(0, 14), y + r.uniform(-8, 8))], fill=(150, 165, 190, 200), width=2)
        over(a, layer_draw(fn))
    hand = _draw_hand(m, drag)
    # éclairage lunaire sur la main
    light = (0.55 + 0.6 * np.clip(1 - np.abs((XX - 0.55 * YY) - 80) / 520, 0, 1))[..., None]
    hand[..., :3] *= light
    over(a, hand)
    zoom = 1.0 + 0.05 * lt / dur
    for hb in ev["heartbeats_p1"]:
        if 0 <= t - hb < 0.25:
            zoom += 0.012 * math.sin(math.pi * (t - hb) / 0.25)
    shake = (0, 0)
    if t > tear_t and t - tear_t < 0.3:
        r = rngf(fi)
        shake = (r.uniform(-12, 12), r.uniform(-12, 12))
    return camera(a, zoom, 0.5, 0.55, shake=shake)


def scene_eye_open(t, lt, dur, ev, fi):
    to = ev["eye_open"]
    if t < to:
        op = 0.0
        if 3.75 < t < 3.9:  # tressaillement de la paupière
            op = 0.04
    else:
        op = min(1.0, (t - to) / 0.07)
    pupil = 34 + 120 * math.exp(-max(0, t - to) * 7)
    a = eye(op, pupil)
    zoom = 1.25 + 0.15 * lt / dur
    sh = (0, 0)
    if 0 < t - ev["griffes"] < 0.4:
        r = rngf(fi)
        k = 1 - (t - ev["griffes"]) / 0.4
        sh = (r.uniform(-25, 25) * k, r.uniform(-25, 25) * k)
        zoom += 0.12 * k
    a = camera(a, zoom, 0.5, EYE_C[1] / H, shake=sh)
    if 0 <= t - ev["griffes"] < 0.12:
        a = a + 0.35 * (1 - (t - ev["griffes"]) / 0.12)
    return a


# =================================================================== PLAN 2 : ville au lever du soleil
def _buildings(seed, night=False):
    r = rngf(seed)
    layers = []
    specs = [(1080, 120, 230, "#7c86a0", 0.0), (1230, 160, 330, "#3c4458", 0.35), (1420, 200, 460, "#151a26", 0.6)]
    for li, (base, minh, maxh, col, win) in enumerate(specs):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        wins = []
        x = -40
        c = tuple(int(v * 255) for v in hexc(col))
        if night:
            c = tuple(int(v * 0.35) for v in c)
        while x < W + 40:
            bw = r.integers(90, 200) + li * 30
            bh = r.integers(minh, maxh)
            top = base - bh
            d.rectangle([x, top, x + bw, H], fill=c + (255,))
            if r.random() < 0.3:
                d.rectangle([x + bw // 2 - 3, top - r.integers(30, 120), x + bw // 2 + 3, top], fill=c + (255,))
            if r.random() < 0.25:
                d.polygon([(x, top), (x + bw, top), (x + bw // 2, top - bw // 3)], fill=c + (255,))
            if li > 0:
                ww, wh = 10 + li * 4, 14 + li * 6
                for wy in range(int(top + 20), H, wh + 14):
                    for wx in range(int(x + 12), int(x + bw - ww - 6), ww + 12):
                        wins.append((wx, wy, wx + ww, wy + wh, r.random(), li))
            x += bw + r.integers(-10, 25)
        layers.append(np.asarray(im, np.float32) / 255)
    return layers, wins


def _skyline_sunrise():
    a = vgrad([(0, "#0d1b3a"), (0.3, "#34507a"), (0.48, "#e98a4a"), (0.56, "#ffcf7a"), (0.7, "#a0583a"), (1, "#1a1418")])
    glow(a, 620, 1000, 700, "#ffb050", 0.9, 2.2)
    glow(a, 620, 1000, 130, "#fff2c0", 1.0, 1.0)
    layers, wins = _buildings(4)
    haze = [0.55, 0.25, 0.0]
    for (L, hz) in zip(layers, haze):
        L = L.copy()
        L[..., :3] = L[..., :3] * (1 - hz) + hexc("#f0a070") * hz
        over(a, L)
    im = to_img(a)
    d = ImageDraw.Draw(im)
    r = rngf(9)
    for (x0, y0, x1, y1, rv, li) in wins:
        if rv < 0.35:
            g = int(150 + 100 * r.random())
            d.rectangle([x0, y0, x1, y1], fill=(255, g, 120))
        else:
            d.rectangle([x0, y0, x1, y1], fill=(40 + li * 5, 60, 90) if li == 1 else (255, 170, 90) if rv > 0.93 else (25, 30, 40))
    # rais de lumière rasante
    a = to_arr(im)
    a += np.clip(1 - np.abs(YY - 1050) / 250, 0, 1)[..., None] * hexc("#ff9a50") * 0.18
    return a


def _title_layer():
    lines = [("ET SI LES HUMAINS", (255, 255, 255)), ("ÉTAIENT TOUS", (255, 255, 255)),
             ("DEVENUS", (255, 255, 255)), ("UN ANIMAL ?", (255, 229, 0))]
    f = font(96)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 250
    for txt, c in lines:
        bb = d.textbbox((0, 0), txt, font=f, stroke_width=9)
        d.text(((W - (bb[2] - bb[0])) // 2, y), txt, font=f, fill=c, stroke_width=9, stroke_fill=(0, 0, 0))
        y += 110
    return np.asarray(im, np.float32) / 255


def glitch_overlay(a, layer, strength, fi):
    r = rngf(fi * 13 + 1)
    L = layer.copy()
    if strength > 0:
        # tranches décalées
        for _ in range(int(3 + 8 * strength)):
            y0 = r.integers(0, H - 40)
            h = r.integers(8, 70)
            L[y0:y0 + h] = np.roll(L[y0:y0 + h], int(r.integers(-80, 80) * strength), 1)
        dx = int(18 * strength) + 2
        red = L.copy(); red[..., 1:3] = 0
        cyan = L.copy(); cyan[..., 0] = 0
        al = L[..., 3:4]
        a[:] = a * (1 - np.roll(al, -dx, 1) * 0.6) + np.roll(red[..., :3] * al, -dx, 1)
        a[:] = a + np.roll(cyan[..., :3] * al, dx, 1) * 0.8
    over(a, L)
    return a


def scene_skyline(t, lt, dur, ev, fi):
    base = cached("skyline", _skyline_sunrise)
    k = ease(lt / dur)
    a = camera(base, 1.0 + 0.3 * k, 0.53, 0.5 + 0.1 * k)
    title_t = 5.45
    if t > title_t:
        g = max(0, 1 - (t - title_t) / 0.45)
        if rngf(fi).random() < 0.08:
            g = max(g, 0.5)
        glitch_overlay(a, cached("title", _title_layer), g, fi)
    return a


def _canyon():
    w2, h2 = int(W * 1.3), int(H * 1.3)
    im = Image.new("RGB", (w2, h2), (20, 22, 28))
    d = ImageDraw.Draw(im)
    cx = w2 // 2
    sw = 150  # demi-largeur de la rue
    # rue
    d.rectangle([cx - sw, 0, cx + sw, h2], fill=(38, 38, 42))
    for y in range(0, h2, 120):
        d.rectangle([cx - 5, y, cx + 5, y + 60], fill=(200, 190, 150))
    d.rectangle([cx - sw - 40, 0, cx - sw, h2], fill=(70, 70, 75))
    d.rectangle([cx + sw, 0, cx + sw + 40, h2], fill=(70, 70, 75))
    r = rngf(2)
    # voitures minuscules
    for y in range(40, h2, 170):
        x = cx + (r.choice([-1, 1]) * r.integers(30, 110))
        d.rectangle([x - 18, y, x + 18, y + 60], fill=tuple(int(v) for v in r.integers(30, 200, 3)))
        d.rectangle([x - 15, y + 15, x + 15, y + 40], fill=(20, 25, 30))
    # murs en perspective (vus de dessus)
    for side in (-1, 1):
        inner = cx + side * (sw + 40)
        outer = 0 if side < 0 else w2
        lit = side > 0
        wall = (205, 130, 80) if lit else (40, 60, 80)
        d.polygon([(inner, 0), (outer, 0), (outer, h2), (inner, h2)], fill=wall)
        # fenêtres en perspective
        n_cols = 9
        for i in range(n_cols):
            u0 = (i + 0.15) / n_cols
            u1 = (i + 0.75) / n_cols
            # espacement perspective : compression vers la rue
            f0, f1 = u0 ** 1.8, u1 ** 1.8
            xa = inner + (outer - inner) * f0
            xb = inner + (outer - inner) * f1
            for y in range(20, h2, 64):
                c = (255, 210, 140) if (lit and r.random() < 0.3) else (wall[0] // 2, wall[1] // 2, wall[2] // 2 + 20)
                d.rectangle([min(xa, xb), y, max(xa, xb), y + 34], fill=c)
        # arête de toit
        d.rectangle([outer - (60 if side > 0 else 0), 0, outer + (0 if side > 0 else 60), h2], fill=(15, 18, 24))
    a = to_arr(im)
    yy = np.linspace(0, 1, h2)[:, None, None]
    a *= 0.8 + 0.3 * yy
    return a


def scene_canyon(t, lt, dur, ev, fi):
    base = cached("canyon", _canyon)
    k = ease_in(lt / dur) * 0.6 + lt / dur * 0.4
    z = 1.0 + 1.1 * k
    im = to_img(base)
    bw, bh = base.shape[1], base.shape[0]
    w2, h2 = W / z, H / z
    x0, y0 = (bw - w2) / 2, (bh - h2) / 2 - 80 * k
    im = im.rotate(8 * k, resample=Image.BILINEAR)
    im = im.transform((W, H), Image.EXTENT, (x0, y0, x0 + w2, y0 + h2), Image.BILINEAR)
    a = to_arr(im)
    glitch_overlay(a, cached("title", _title_layer), 0.6 if rngf(fi + 5).random() < 0.07 else 0.0, fi)
    return a


# =================================================================== PLAN 3
def _suit_layer(cx, cy, torn=False, collapse=0.0):
    def fn(d, im):
        sy = 1 - 0.55 * collapse
        top = cy + 120 * collapse
        sh = 360
        d.polygon([(cx - sh, top + 160 * sy), (cx - 150, top), (cx + 150, top), (cx + sh, top + 160 * sy),
                   (cx + sh + 40, H), (cx - sh - 40, H)], fill=(22, 24, 30, 255))
        d.polygon([(cx - 120, top), (cx + 120, top), (cx, top + 260 * sy)], fill=(225, 225, 230, 255))
        d.polygon([(cx - 22, top + 40 * sy), (cx + 22, top + 40 * sy), (cx + 34, top + 330 * sy), (cx, top + 380 * sy), (cx - 34, top + 330 * sy)],
                  fill=(150, 20, 30, 255))
        d.polygon([(cx - 120, top), (cx - 40, top + 300 * sy), (cx - 160, top + 120 * sy)], fill=(35, 38, 46, 255))
        d.polygon([(cx + 120, top), (cx + 40, top + 300 * sy), (cx + 160, top + 120 * sy)], fill=(35, 38, 46, 255))
        if torn:
            r = rngf(4)
            for sx in (-1, 1):
                x = cx + sx * 260
                pts = [(x, top + 120)]
                for i in range(8):
                    pts.append((x + sx * r.uniform(-30, 30), top + 120 + i * 60))
                d.line(pts, fill=(200, 200, 200, 255), width=5)
                d.line([(p[0] + sx * 10, p[1]) for p in pts], fill=(0, 0, 0, 255), width=10)
    return layer_draw(fn)


def _office_bg():
    a = vgrad([(0, "#0e1a20"), (0.6, "#1e2a2e"), (1, "#0b0c0e")])
    # fenêtre à stores
    im = to_img(a)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([700, 180, 1080, 1200], fill=(255, 170, 90))
    for y in range(180, 1200, 46):
        d.rectangle([700, y + 26, 1080, y + 46], fill=(40, 30, 30))
    for y in range(180, 1200, 46):  # rais de lumière sur le mur
        d.polygon([(700, y), (700, y + 26), (0, y + 520), (0, y + 470)], fill=(255, 150, 70, 22))
    d.rectangle([0, 1460, W, H], fill=(36, 22, 16))
    d.rectangle([0, 1460, W, 1475], fill=(120, 80, 50))
    d.polygon([(40, 1100), (420, 1080), (420, 1400), (40, 1420)], fill=(10, 14, 20))
    d.polygon([(60, 1115), (400, 1097), (400, 1385), (60, 1402)], fill=(60, 140, 220))
    d.rectangle([200, 1400, 260, 1462], fill=(15, 15, 18))
    a = to_arr(im)
    glow(a, 230, 1250, 450, "#2f7ad0", 0.25)
    d2 = ImageDraw.Draw(im)
    return blur(a, 2.5)  # profondeur de champ réduite


def scene_office(t, lt, dur, ev, fi):
    a = cached("office", _office_bg).copy()
    cx, cy = 540, 1050
    tl = ev["lion"]
    if t < tl - 0.12:
        k = ease((lt) / (tl - 0.12 - 10.0))
        over(a, _suit_layer(cx, cy, False, k * 0.9))
    else:
        over(a, cached("suit_torn", lambda: _suit_layer(cx, cy + 40, True, 0)))
        lion = cached("lion", lambda: silhouette("🦁", 760, "#140d08", "#ffa040", (1, -1), 10))
        s = 1.0 + 0.12 * max(0, 1 - (t - tl) / 0.25)
        paste(a, lion, cx, 760, s)
        hgt = lion.shape[0] * s
        for ex in (-0.15, 0.15):
            glow(a, cx + ex * hgt, 760 + 0.06 * hgt, 46 * s, "#ffc020", 0.9, 1.6)
            glow(a, cx + ex * hgt, 760 + 0.06 * hgt, 12 * s, "#fff4c0", 1.0, 1.0)
    zoom = 1.04 + 0.06 * lt / dur
    sh = (0, 0)
    if 0 <= t - tl < 0.6:
        r = rngf(fi)
        k = 1 - (t - tl) / 0.6
        sh = (r.uniform(-22, 22) * k, r.uniform(-22, 22) * k)
    a = camera(a, zoom, 0.5, 0.5, shake=sh)
    if 0 <= t - tl + 0.12 < 0.2:
        a = a + 0.5 * (1 - (t - tl + 0.12) / 0.2)
    return a


def _classroom_bg():
    a = vgrad([(0, "#1a2a28"), (1, "#0c1210")])
    im = to_img(a)
    d = ImageDraw.Draw(im)
    d.rectangle([70, 300, 1010, 1180], fill=(70, 46, 26))
    d.rectangle([95, 325, 985, 1155], fill=(30, 58, 44))
    b = to_arr(im)
    n = fbm(H, W, 3)
    mask = np.zeros((H, W, 1), np.float32)
    mask[325:1155, 95:985] = 1
    b = b + mask * (n[..., None] - 0.5) * 0.12
    im = to_img(b)
    d = ImageDraw.Draw(im)
    f = font(78, FONT_BOLD)
    d.text((150, 720), "LEÇON 12 :", font=f, fill=(220, 225, 215))
    d.text((150, 830), "2 + 2 = ...", font=f, fill=(210, 215, 205))
    r = rngf(8)
    for _ in range(14):
        x, y = r.integers(150, 900), r.integers(960, 1120)
        d.line([(x, y), (x + r.integers(40, 160), y + r.integers(-10, 10))], fill=(190, 195, 185), width=3)
    # pupitres vides au premier plan
    for row, (y, s) in enumerate(((1450, 1.0), (1700, 1.35))):
        for xx in range(-100, W + 200, int(420 * s)):
            d.polygon([(xx, y), (xx + 330 * s, y), (xx + 350 * s, y + 70 * s), (xx - 20 * s, y + 70 * s)], fill=(50, 34, 22))
            d.rectangle([xx + 20 * s, y + 70 * s, xx + 40 * s, y + 300 * s], fill=(20, 20, 22))
            d.rectangle([xx + 290 * s, y + 70 * s, xx + 310 * s, y + 300 * s], fill=(20, 20, 22))
    a = to_arr(im)
    glow(a, 540, 200, 700, "#f0d090", 0.25)
    return a


def scene_classroom(t, lt, dur, ev, fi):
    a = cached("classroom", _classroom_bg).copy()
    tp = ev["paresseux"]
    sloth = cached("sloth", lambda: silhouette("🦥", 620, "#16120e", "#e0d8a0", (0, -1), 9))
    if t >= tp - 0.35:
        k = ease((t - tp + 0.35) / 0.35)
        sway = 4 * math.sin(lt * 2.2)
        rot = Image.fromarray((sloth * 255).astype(np.uint8), "RGBA").rotate(sway, resample=Image.BILINEAR, expand=False)
        sl = np.asarray(rot, np.float32) / 255
        paste(a, sl, 640, -250 + 860 * k)
    else:
        # pull vide tombé sur un pupitre
        def fn(d, im):
            d.ellipse([380, 1400, 700, 1470], fill=(110, 40, 50, 255))
            d.ellipse([600, 1390, 760, 1440], fill=(95, 35, 45, 255))
        over(a, layer_draw(fn))
    return camera(a, 1.03 + 0.05 * lt / dur, 0.5, 0.48)


def _bus_bg():
    sky = cached("skyline", _skyline_sunrise)
    outside = blur(camera(sky, 1.4, 0.5, 0.6), 6)
    a = np.zeros((H, W, 3), np.float32) + hexc("#0d0f12")
    mask = layer_draw(lambda d, im: d.polygon([(60, 260), (1020, 200), (1060, 1150), (20, 1180)], fill=(255, 255, 255, 255)))
    a = a * (1 - mask[..., 3:4]) + outside * mask[..., 3:4]
    def fn(d, im):
        d.polygon([(0, 1150), (W, 1120), (W, H), (0, H)], fill=(18, 20, 24, 255))
        d.rectangle([0, 1150, W, 1175], fill=(60, 64, 70, 255))
        d.rectangle([520, 150, 560, 1180], fill=(12, 12, 14, 255))
        for i, x in enumerate((700, 780, 860)):
            d.ellipse([x, 1230, x + 60, 1290], outline=(220, 120, 40, 255), width=4)
    over(a, layer_draw(fn))
    return a


def scene_bus(t, lt, dur, ev, fi):
    tt = min(t, ev["toi"])  # arrêt sur image sur « toi »
    a = cached("bus", _bus_bg).copy()
    # route qui défile dans le pare-brise
    def road(d, im):
        off = (tt * 900) % 200
        for i in range(6):
            y = 1150 - (i * 200 + off) * 0.4
            w = 6 + i
            d.polygon([(540 - w, y), (540 + w, y), (540 + w * 1.6, y + 40), (540 - w * 1.6, y + 40)], fill=(230, 220, 160, 200))
    over(a, layer_draw(road))
    dog = cached("dog", lambda: silhouette("🐕", 700, "#18120c", "#ffb070", (1, -1), 9, flip=True))
    bob = 6 * math.sin(tt * 18)
    paste(a, dog, 470, 1180 + bob)
    def wheel(d, im):
        d.ellipse([500, 1150, 1020, 1430], outline=(8, 8, 10, 255), width=48)
        d.line([(760, 1290), (760, 1430)], fill=(8, 8, 10, 255), width=40)
    over(a, layer_draw(wheel))
    a = camera(a, 1.0 + 0.04 * (tt - 14.0), 0.5, 0.55)
    if t >= ev["toi"]:
        k = min(1, (t - ev["toi"]) / 0.15)
        g = a.mean(2, keepdims=True)
        a = a * (1 - 0.85 * k) + g * 0.85 * k
        a = camera(a, 1.0 + 0.08 * k)
        a = a * 0.9
    return a


WHO = ["🦁", "🐺", "🐈", "🦅", "🦍", "🐊", "🦉", "🐍", "🐬", "🦊", "🐘", "🐒"]


def scene_whoareyou(t, lt, dur, ev, fi):
    a = np.zeros((H, W, 3), np.float32) + hexc("#05070a")
    glow(a, 540, 900, 900, "#1f6a7a", 0.6, 1.6)
    q = cached("qmark", lambda: text_layer(["?"], 900, fill=(255, 229, 0), stroke=0, y=0.2))
    over(a, q, 0.12)
    idx = int(lt / 0.11) % len(WHO)
    if lt < 0.12:
        def fn(d, im):  # silhouette humaine
            d.ellipse([400, 520, 680, 860], fill=(8, 10, 12, 255))
            d.ellipse([200, 840, 880, 1500], fill=(8, 10, 12, 255))
        over(a, layer_draw(fn))
    else:
        rims = ["#ffb040", "#60e0ff", "#ffe080", "#ff7050"]
        sil = cached(("who", idx), lambda: silhouette(WHO[idx], 760, "#06080a", rims[idx % 4], (1, -1), 12))
        paste(a, sil, 540, 960, 1.0 + 0.03 * (lt % 0.11) / 0.11)
    return camera(a, 1.0 + 0.1 * lt / dur)


# =================================================================== PLAN 4
CROWD = ["🐘", "🦒", "🐄", "🐎", "🐖", "🐐", "🦍", "🐒", "🐕", "🐈", "🦌", "🐅", "🦓", "🦏", "🐫", "🐊", "🦘", "🐓", "🐧", "🦩", "🐑", "🐆"]


def _screen_static(fi, w=720, h=420):
    r = rngf(fi)
    s = r.random((h // 6, w // 6)).astype(np.float32)
    s = np.asarray(Image.fromarray((s * 255).astype(np.uint8)).resize((w, h), Image.NEAREST), np.float32) / 255
    s = s[..., None] * np.array([0.45, 0.5, 0.6], np.float32)
    s[::4] *= 0.5
    return s


def _square_bg():
    a = vgrad([(0, "#5d6a74"), (0.45, "#8a949a"), (1, "#3a3e42")])
    def fn(d, im):
        d.rectangle([0, 160, W, 1150], fill=(70, 74, 80, 255))
        for x in range(30, W, 130):
            for y in range(800, 1130, 110):
                d.rectangle([x, y, x + 60, y + 80], fill=(40, 44, 50, 255))
        d.rectangle([150, 270, 930, 740], fill=(15, 15, 18, 255))
    over(a, layer_draw(fn))
    r = rngf(12)
    rows = [(1180, 170, 0.55, 9), (1420, 270, 0.3, 7), (1730, 430, 0.0, 5)]
    for y, size, hz, n in rows:
        xs = np.linspace(-40, W + 40, n) + r.uniform(-40, 40, n)
        for x in xs:
            ch = CROWD[r.integers(0, len(CROWD))]
            col = "#101215"
            sil = silhouette(ch, size * r.uniform(0.85, 1.15), col, "#c8d4dc", (0, -1), 4, flip=r.random() < 0.5, rim_strength=0.5)
            sil[..., :3] = sil[..., :3] * (1 - hz) + hexc("#7a848c") * hz
            paste(a, sil, x, y - sil.shape[0] / 2 + size * 0.45)
        a[int(y - size):] = a[int(y - size):] * 0.97 + hexc("#80888e") * 0.03
    return a


def scene_square(t, lt, dur, ev, fi):
    a = cached("square", _square_bg).copy()
    st = _screen_static(fi, 760, 450)
    a[280:730, 160:920] = st[:450, :760]
    sig = cached("nosig", lambda: text_layer(["AUCUN SIGNAL"], 92, fill=(255, 40, 40), stroke=0, y=0.24))
    if (fi // 8) % 2 == 0:
        over(a, sig)
    glow(a, 540, 500, 600, "#6a80a0", 0.15)
    return camera(a, 1.02 + 0.07 * lt / dur, 0.5, 0.52)


def _phone_img(name, seed):
    pw, ph = 300, 600
    im = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + pw, 20 + ph], 42, fill=(12, 12, 14, 255))
    scr = vgrad([(0, "#2c4a7a"), (1, "#121c30")], ph - 40, pw - 30)
    s_im = Image.fromarray((scr * 255).astype(np.uint8)).convert("RGBA")
    im.paste(s_im, (35, 40))
    d.text((60, 120), "Appel entrant", font=font(30, FONT_BOLD), fill=(220, 230, 255))
    d.text((60, 165), name, font=font(48, FONT_BOLD), fill=(255, 255, 255))
    d.ellipse([60, 480, 140, 560], fill=(220, 50, 50))
    d.ellipse([200, 480, 280, 560], fill=(40, 200, 90))
    return np.asarray(im, np.float32) / 255


PHONES = [("Maman", 520, 860, 18, 1.15, 0), ("Bureau", 230, 1350, -32, 0.9, 1), ("Inconnu", 860, 1420, 40, 0.85, 1),
          ("Chéri(e)", 300, 470, -12, 0.75, 2), ("Papa", 830, 330, 25, 0.7, 2)]


def _ground():
    a = np.zeros((H, W, 3), np.float32) + 0.1
    r = rngf(30)
    def fn(d, im):
        for y in range(-40, H + 80, 90):
            off = (y // 90) % 2 * 60
            for x in range(-60 + off, W + 60, 120):
                c = int(r.integers(40, 75))
                d.rounded_rectangle([x + 4, y + 4, x + 114, y + 86], 22, fill=(c, c, c + 4, 255))
    over(a, layer_draw(fn))
    return a * 0.7


def scene_phones(t, lt, dur, ev, fi):
    a = cached("ground", _ground).copy()
    r = rngf(fi)
    for name, x, y, ang, s, blur_lvl in PHONES:
        ph = cached(("phone", name), lambda: _phone_img(name, 0))
        def mk():
            im = Image.fromarray((ph * 255).astype(np.uint8), "RGBA").rotate(ang, expand=True, resample=Image.BICUBIC)
            im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
            if blur_lvl:
                im = im.filter(ImageFilter.GaussianBlur(5 * blur_lvl))
            return np.asarray(im, np.float32) / 255
        img = cached(("phone_r", name), mk)
        ring = ((t + x * 0.001) % 0.6) < 0.35
        jx, jy = (r.uniform(-5, 5), r.uniform(-5, 5)) if ring else (0, 0)
        glow(a, x, y, 380 * s, "#3a70d0", 0.22 if ring else 0.12)
        paste(a, img, x + jx, y + jy)
    return camera(a, 1.0 + 0.06 * lt / dur, 0.5, 0.5, rot=-3 * lt / dur)


def scene_screen(t, lt, dur, ev, fi):
    a = np.zeros((H, W, 3), np.float32) + 0.02
    tc = ev["cris"]
    st = _screen_static(fi, W, H)
    st = st * (1.0 + 0.4 * rngf(fi).random())
    if t < tc:
        a = st * 0.8
        over(a, cached("nosig_big", lambda: text_layer(["AUCUN", "SIGNAL"], 170, fill=(255, 40, 40), stroke=10, y=0.2)))
        n = int(7000 * (1 - ease((t - 20.6) / max(0.1, tc - 20.6))))
        txt = text_layer(["LANGUES ACTIVES", f"{max(0, n):,}".replace(",", " ")], 70, fill=(255, 255, 255), stroke=6, y=0.48)
        over(a, txt)
        a[::6] *= 0.75  # lignes de balayage
    else:
        # extinction cathodique
        k = (t - tc) / 0.25
        if k < 1:
            hh = max(2, int(H * (1 - ease(k * 1.6))))
            ww = W if k < 0.6 else max(4, int(W * (1 - ease((k - 0.6) / 0.4))))
            y0, x0 = (H - hh) // 2, (W - ww) // 2
            a[y0:y0 + hh, x0:x0 + ww] = 1.0
        else:
            glow(a, 540, 960, 40, "#ffffff", 0.3 * max(0, 1 - (k - 1) * 0.5))
    return camera(a, 1.02 + 0.04 * lt / dur)


# =================================================================== PLAN 5
def _night_city():
    a = vgrad([(0, "#02040a"), (0.45, "#0b1630"), (0.62, "#20304a"), (1, "#05070a")])
    glow(a, 540, 1050, 800, "#e07030", 0.2, 2)
    layers, wins = _buildings(17, night=True)
    for L in layers:
        over(a, L)
    # périphérique avec voitures abandonnées
    def fn(d, im):
        d.polygon([(0, 1500), (W, 1440), (W, 1620), (0, 1700)], fill=(18, 20, 24, 255))
        d.line([(0, 1600), (W, 1530)], fill=(120, 120, 90, 255), width=3)
    over(a, layer_draw(fn))
    return a, wins


def scene_city_off(t, lt, dur, ev, fi):
    base, wins = cached("nightcity", _night_city)
    a = base.copy()
    te = ev["eteignent"]
    prog = (t - te) * 1.4 if t > te else -1
    im = to_img(a)
    d = ImageDraw.Draw(im)
    for (x0, y0, x1, y1, rv, li) in wins:
        if rv < 0.55 and not (prog > rv * 0.6 + x0 / W * 0.5):
            g = int(170 + 80 * rv)
            d.rectangle([x0, y0, x1, y1], fill=(255, g, 110))
    r = rngf(40)
    for i in range(14):
        x = 40 + i * 75 + r.integers(-10, 10)
        y = 1600 - x * 0.065 - r.integers(0, 90)
        haz = (t * 1.6 + i * 0.3) % 1 < 0.5
        d.rectangle([x, y, x + 50, y + 22], fill=(30, 30, 34))
        d.ellipse([x + 2, y + 4, x + 12, y + 14], fill=(255, 150, 20) if haz else (90, 20, 20))
        d.ellipse([x + 38, y + 4, x + 48, y + 14], fill=(255, 150, 20) if haz else (90, 20, 20))
    a = to_arr(im)
    if 0 <= t - te < 0.1:
        a = a + 0.4
    return camera(a, 1.08 + 0.08 * lt / dur, 0.5, 0.6)


def _metro():
    a = np.zeros((H, W, 3), np.float32) + 0.01
    vx, vy = 540, 900
    im = to_img(a)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(26, 0, -1):
        z = 1 + i * 0.55
        w, h = 900 / z, 1500 / z
        c = int(110 / (1 + i * 0.35))
        box = [vx - w, vy - h * 0.55, vx + w, vy + h * 0.45]
        d.rounded_rectangle(box, int(w * 0.9), outline=(c, int(c * 0.9), int(c * 0.8), 255), width=max(2, int(40 / z)))
        if i % 2 == 0:
            d.ellipse([vx - w * 0.92 - 6, vy - h * 0.1, vx - w * 0.92 + 6, vy - h * 0.1 + 12], fill=(255, 170, 80, int(200 / (1 + i * 0.1))))
    for sx in (-1, 1):
        for off in (120, 260):
            d.line([(vx + sx * off / 26, vy + 330 / 4), (vx + sx * off * 2.2, H)], fill=(110, 110, 120, 255), width=6)
    # arrière de la rame
    d.rounded_rectangle([vx - 200, vy - 190, vx + 200, vy + 250], 30, fill=(28, 30, 36, 255))
    d.rectangle([vx - 160, vy - 140, vx - 20, vy + 20], fill=(10, 12, 16, 255))
    d.rectangle([vx + 20, vy - 140, vx + 160, vy + 20], fill=(10, 12, 16, 255))
    return to_arr(im)


def scene_metro(t, lt, dur, ev, fi):
    a = cached("metro", _metro).copy()
    vx, vy = 540, 900
    for x in (vx - 150, vx + 150):
        glow(a, x, vy + 160, 110, "#ff2010", 1.0, 2.5)
        glow(a, x, vy + 160, 20, "#ffd0c0", 1.0, 1)
    beat = (math.sin(lt * 2 * math.pi * 0.9) * 0.5 + 0.5) ** 3
    glow(a, 120, 700, 700, "#ff8a20", 0.35 * beat)
    return camera(a, 1.0 + 0.12 * ease(lt / dur), 0.5, 0.47)


def _control():
    a = vgrad([(0, "#0a0c10"), (1, "#14161a")])
    im = to_img(a)
    d = ImageDraw.Draw(im)
    r = rngf(50)
    f = font(28, FONT_BOLD)
    for row in range(5):
        for col in range(4):
            x0, y0 = 70 + col * 240, 200 + row * 190
            d.rectangle([x0, y0, x0 + 220, y0 + 170], fill=(6, 6, 8))
            d.rectangle([x0 + 8, y0 + 8, x0 + 212, y0 + 162], fill=(60, 10, 10) if r.random() < 0.6 else (10, 30, 40))
            if r.random() < 0.5:
                d.text((x0 + 22, y0 + 60), "ALERTE", font=f, fill=(255, 70, 60))
            else:
                pts = [(x0 + 15 + i * 12, y0 + 85 + r.integers(-50, 50)) for i in range(17)]
                d.line(pts, fill=(255, 170, 40), width=3)
    # pupitres
    d.polygon([(0, 1250), (W, 1250), (W, 1500), (0, 1500)], fill=(26, 28, 34))
    d.polygon([(0, 1500), (W, 1500), (W, H), (0, H)], fill=(12, 13, 16))
    for i in range(60):
        x = r.integers(20, W - 20)
        y = r.integers(1290, 1470)
        c = [(255, 40, 30), (255, 170, 30), (40, 220, 90)][r.integers(0, 3)]
        d.ellipse([x, y, x + 10, y + 10], fill=c)
    # fauteuil vide
    d.rounded_rectangle([420, 1080, 660, 1400], 40, fill=(8, 8, 10))
    d.ellipse([380, 1380, 700, 1470], fill=(8, 8, 10))
    d.rectangle([530, 1460, 550, 1640], fill=(8, 8, 10))
    for ang in range(0, 360, 72):
        d.line([(540, 1640), (540 + 140 * math.cos(math.radians(ang)), 1640 + 40 * math.sin(math.radians(ang)))], fill=(8, 8, 10), width=14)
    return to_arr(im)


def scene_control(t, lt, dur, ev, fi):
    a = cached("control", _control).copy()
    pulse = (math.sin(t * 2 * math.pi * 1.2) * 0.5 + 0.5) ** 4
    a = a + np.array([0.35, 0.0, 0.0], np.float32) * pulse
    ang = t * 4.0
    bx = 540 + math.cos(ang) * 600
    glow(a, bx, 120, 700, "#ff1a10", 0.5 * (0.5 + 0.5 * math.sin(ang)))
    glow(a, 540, 60, 60, "#ff4030", 1.0)
    return camera(a, 1.0 + 0.1 * ease(lt / dur), 0.5, 0.55)


# =================================================================== PLAN 6
def _corridor():
    vx, vy = 540, 820
    a = np.zeros((H, W, 3), np.float32)
    im = to_img(a)
    d = ImageDraw.Draw(im)
    segs = 14

    def P(xn, yn, z):  # projection
        return vx + xn / z, vy + yn / z
    for i in range(segs, 0, -1):
        z0, z1 = 0.6 + i * 0.6, 0.6 + (i - 1) * 0.6
        br = 1 / (1 + 0.28 * i)
        wall = tuple(int(c * br) for c in (88, 84, 70))
        floor = tuple(int(c * br) for c in (60, 52, 44))
        ceil = tuple(int(c * br) for c in (50, 50, 48))
        for sx, col in ((-1, wall), (1, wall)):
            d.polygon([P(sx * 500, -600, z0), P(sx * 500, -600, z1), P(sx * 500, 900, z1), P(sx * 500, 900, z0)], fill=col)
        d.polygon([P(-500, 900, z0), P(500, 900, z0), P(500, 900, z1), P(-500, 900, z1)], fill=floor)
        d.polygon([P(-500, -600, z0), P(500, -600, z0), P(500, -600, z1), P(-500, -600, z1)], fill=ceil)
        if i % 3 == 1:  # portes
            for sx in (-1, 1):
                d.polygon([P(sx * 500, -250, z0 - 0.1), P(sx * 500, -250, z1 + 0.15), P(sx * 500, 900, z1 + 0.15), P(sx * 500, 900, z0 - 0.1)],
                          fill=tuple(int(c * br) for c in (40, 30, 24)))
    z = 0.6 + segs * 0.6
    d.polygon([P(-500, -600, z), P(500, -600, z), P(500, 900, z), P(-500, 900, z)], fill=(2, 2, 3))
    return to_arr(im), (vx, vy)


def corridor_frame(t, fi, dark=1.0):
    base, (vx, vy) = cached("corridor", _corridor)
    a = base.copy()
    r = rngf(fi // 2)
    flick = 1.0 if r.random() > 0.18 else 0.25
    for i, zz in enumerate((1.8, 3.6, 5.4)):
        x, y = vx, vy - 600 / zz
        k = flick if i == 0 else 1.0
        glow(a, x, y, 260 / zz * 3, "#d8e8d0", 0.5 * k)
        glow(a, x, vy + 900 / zz, 500 / zz * 2, "#a0b8a0", 0.18 * k)
    return a * dark * (0.55 + 0.45 * flick)


def scene_corridor(t, lt, dur, ev, fi):
    a = corridor_frame(t, fi)
    deer = cached("deer", lambda: silhouette("🦌", 780, "#0e0d0b", "#a8e0ff", (0, -1), 8))
    k = ease(lt / dur)
    paste(a, deer, 540 - 30 * k, 1300 + 160 * k, 0.9 + 0.3 * k)
    return camera(a, 1.0 + 0.05 * k, 0.5, 0.5)


def scene_tiger_eyes(t, lt, dur, ev, fi):
    td = ev["diner"]
    if t > td + 0.35:
        return np.zeros((H, W, 3), np.float32)
    a = camera(corridor_frame(t, fi, 0.45), 1.7, 0.5, 0.43)
    k = ease((t - 33.5) / (td - 33.5))
    s = 0.5 + 1.6 * k
    if t > td:
        s *= 1 + 1.2 * ease((t - td) / 0.15)
    cx, cy = 540, 840 + 120 * k
    head = cached("tigerhead", lambda: silhouette("🐯", 900, "#030303", "#3a3020", (0, -1), 6, rim_strength=0.6))
    paste(a, head, cx, cy + 40 * s, s, alpha=0.9)
    for sx in (-1, 1):
        ex = cx + sx * 115 * s
        ey = cy - 40 * s
        glow(a, ex, ey, 90 * s, "#b8ff40", 0.9, 1.8)
        glow(a, ex, ey, 34 * s, "#f8ffb0", 1.0, 1.0)
        def fn(d, im, ex=ex, ey=ey):
            d.ellipse([ex - 6 * s, ey - 28 * s, ex + 6 * s, ey + 28 * s], fill=(0, 0, 0, 255))
        over(a, layer_draw(fn))
    return a


# =================================================================== PLAN 7 : nature
def _tower_mask():
    def fn(d, im):
        cx, base, top = 540, 1520, 230
        pts_l, pts_r = [], []
        for i in range(60):
            u = i / 59
            y = base - (base - top) * u
            w = 330 * (1 - u) ** 2.2 + 14
            pts_l.append((cx - w, y)); pts_r.append((cx + w, y))
        d.polygon(pts_l + pts_r[::-1], fill=(255, 255, 255, 255))
        d.ellipse([cx - 210, 1380, cx + 210, 1700], fill=(0, 0, 0, 0))
        d.rectangle([cx - 4, 120, cx + 4, 240], fill=(255, 255, 255, 255))
    m = layer_draw(fn)[..., 3]
    lines = layer_draw(lambda d, im: [d.line([(x, 0), (x + 1400, 1400)], fill=(255, 255, 255, 255), width=3) for x in range(-1400, W, 34)]
                       + [d.line([(x, 0), (x - 1400, 1400)], fill=(255, 255, 255, 255), width=3) for x in range(0, W + 1400, 34)])[..., 3]
    lines = np.vstack([lines, lines])[:H]
    plat = layer_draw(lambda d, im: [d.rectangle([540 - w, y, 540 + w, y + 18], fill=(255, 255, 255, 255)) for y, w in ((1180, 190), (880, 95), (520, 40))])[..., 3]
    return m, np.clip(lines + plat, 0, 1) * m


def _vines(seed=3):
    r = rngf(seed)
    paths = []
    for start in [(360, 1520), (720, 1520), (440, 1300), (640, 1300), (520, 1000), (560, 760)]:
        x, y = start
        pts = [(x, y)]
        ang = -math.pi / 2
        for i in range(90):
            ang += r.uniform(-0.45, 0.45)
            ang = max(-math.pi + 0.3, min(-0.3, ang))
            x += math.cos(ang) * 14 + (540 - x) * 0.01
            y += math.sin(ang) * 14
            pts.append((x, y))
        paths.append(pts)
    return paths


def _paris_sky():
    a = vgrad([(0, "#3a6a8a"), (0.35, "#e8c890"), (0.6, "#ffd890"), (1, "#5a4a30")])
    glow(a, 760, 760, 650, "#fff0b0", 0.8, 2)
    return a


def scene_eiffel(t, lt, dur, ev, fi):
    a = cached("paris_sky", _paris_sky).copy()
    m, lat = cached("tower", _tower_mask)
    g = ease(lt / dur * 1.05)
    tower_col = hexc("#3a2e22")
    a[:] = a * (1 - m[..., None]) + tower_col * m[..., None]
    a[:] = a * (1 - lat[..., None] * 0.6) + hexc("#ffd890") * lat[..., None] * 0.15 * (1 - m[..., None]) + a * 0 * lat[..., None]
    paths = cached("vines", _vines)
    r = rngf(70)

    def fn(d, im):
        for pts in paths:
            n = int(len(pts) * g)
            if n > 1:
                d.line(pts[:n], fill=(40, 90, 30, 255), width=8)
                for i in range(1, n, 3):
                    x, y = pts[i]
                    s = 9 + (i % 5) * 3
                    d.ellipse([x - s, y - s * 0.7, x + s, y + s * 0.7], fill=(60 + (i * 7) % 60, 140 + (i * 13) % 60, 40, 255))
        # toits haussmanniens + arbres qui poussent
        for i, x in enumerate(range(-40, W + 80, 150)):
            h = 1480 + (i * 37) % 90
            d.rectangle([x, h, x + 140, H], fill=(46, 40, 36, 255))
            d.polygon([(x - 5, h), (x + 145, h), (x + 120, h - 50), (x + 20, h - 50)], fill=(60, 66, 76, 255))
            d.rectangle([x + 100, h - 80, x + 116, h - 50], fill=(70, 60, 55, 255))
        for i in range(12):
            x = (i * 97 + 40) % W
            y = 1500 + (i * 53) % 220
            R = 30 + 120 * g * (0.6 + (i % 3) * 0.25)
            d.ellipse([x - R, y - R, x + R, y + R * 0.8], fill=(50 + i * 4, 110 + i * 5, 40, 255))
    over(a, layer_draw(fn))
    yr = 1 + int(19 * g)
    over(a, text_layer([f"AN {yr}"], 64, fill=(255, 255, 255), stroke=5, y=0.06))
    return camera(a, 1.04 + 0.06 * lt / dur, 0.5, 0.5)


def _avenue():
    a = vgrad([(0, "#7aa0b0"), (0.42, "#ffe0a0"), (0.52, "#ffc870"), (1, "#3a3626")])
    vx, vy = 540, 980
    glow(a, vx, vy - 80, 600, "#fff4c0", 0.9, 2)
    im = to_img(a)
    d = ImageDraw.Draw(im, "RGBA")
    # rayons
    for i in range(14):
        ang = -math.pi / 2 + (i - 6.5) * 0.17
        d.polygon([(vx, vy - 80), (vx + math.cos(ang - 0.04) * 2000, vy - 80 + math.sin(ang - 0.04) * 2000),
                   (vx + math.cos(ang + 0.04) * 2000, vy - 80 + math.sin(ang + 0.04) * 2000)], fill=(255, 240, 190, 28))
    d.polygon([(vx - 30, vy), (vx + 30, vy), (W + 500, H), (-500, H)], fill=(70, 66, 60, 255))
    # Arc de triomphe
    d.rectangle([vx - 110, vy - 190, vx + 110, vy], fill=(60, 50, 40, 255))
    d.rectangle([vx - 125, vy - 215, vx + 125, vy - 185], fill=(60, 50, 40, 255))
    d.rectangle([vx - 40, vy - 110, vx + 40, vy], fill=(255, 230, 170, 255))
    d.ellipse([vx - 40, vy - 150, vx + 40, vy - 70], fill=(255, 230, 170, 255))
    return to_arr(im)


def scene_avenue(t, lt, dur, ev, fi):
    a = cached("avenue", _avenue).copy()
    vx, vy = 540, 980
    g = ease((t - 40.5) / 2.5) * 0.7 + 0.3
    # herbe qui recouvre le bitume
    n = cached("grassnoise", lambda: fbm(H, W, 77, 5, 6))
    road = np.zeros((H, W), np.float32)
    yy = YY - vy
    road = (yy > 0) & (np.abs(XX - vx) < 30 + yy * (570 / (H - vy)))
    grass = road & (n > 0.7 - 0.22 * g)
    a[grass] = a[grass] * 0.3 + hexc("#5a8a30") * (0.6 + 0.6 * n[grass, None])
    def fn(d, im):
        for sx in (-1, 1):
            for i in range(9):
                z = 1 + i * 0.9
                y = vy + 900 / z
                x = vx + sx * 820 / z
                R = (230 / z) * (0.5 + 0.7 * g)
                d.rectangle([x - 10 / z, y - R * 0.3, x + 10 / z, y + 80 / z], fill=(50, 40, 30, 255))
                d.ellipse([x - R, y - R * 1.8, x + R, y - R * 0.1], fill=(50 + i * 6, 100 + i * 6, 40, 255))
    over(a, layer_draw(fn))
    deer = cached("deer_av", lambda: silhouette("🦌", 300, "#2a1e14", "#ffe0a0", (0, -1), 4))
    deer_f = cached("deer_av_f", lambda: silhouette("🦌", 300, "#2a1e14", "#ffe0a0", (0, -1), 4, flip=True))
    for dx, dy, s, sp, f in ((-160, 1500, 1.4, 40, False), (210, 1260, 0.9, -30, True), (-40, 1120, 0.55, 20, False)):
        x = vx + dx + sp * (t - 40.5)
        paste(a, deer_f if f else deer, x, dy - 120 * s + 4 * math.sin(t * 6 + dx), s)
    return camera(a, 1.02 + 0.08 * ease(lt / dur), 0.5, 0.52)


def scene_birds(t, lt, dur, ev, fi):
    def bg():
        a = vgrad([(0, "#c88a40"), (0.4, "#ffc860"), (0.62, "#ffe8a0"), (1, "#3a3018")])
        glow(a, 540, 1050, 900, "#fff0a0", 0.6, 1.6)
        def fn(d, im):
            d.ellipse([540 - 330, 1050 - 330, 540 + 330, 1050 + 330], fill=(255, 250, 225, 255))
        over(a, layer_draw(fn))
        def trees(d, im):
            r = rngf(91)
            for x in range(-40, W + 60, 55):
                h = r.integers(140, 320)
                d.polygon([(x - 50, 1650), (x + 50, 1650), (x, 1650 - h)], fill=(30, 36, 18, 255))
            d.rectangle([0, 1640, W, H], fill=(24, 28, 14, 255))
        over(a, layer_draw(trees))
        return a
    a = cached("birds_bg", bg).copy()
    r = rngf(5)
    birds = cached("flock", lambda: [(r.uniform(-600, 200), r.uniform(700, 1500), r.uniform(0.4, 1.6), r.uniform(0, 6)) for _ in range(46)])

    def fn(d, im):
        for (x0, y0, s, ph) in birds:
            x = x0 + (t - 43) * 380 * s
            y = y0 - (t - 43) * 160 * s
            w = 46 * s
            f = math.sin(t * 14 + ph)
            d.line([(x - w, y - f * w * 0.6), (x - w * 0.3, y - 4 * s), (x, y), (x + w * 0.3, y - 4 * s), (x + w, y - f * w * 0.6)],
                   fill=(25, 20, 12, 255), width=max(2, int(5 * s)), joint="curve")
    over(a, layer_draw(fn))
    return camera(a, 1.0 + 0.06 * lt / dur, 0.5, 0.55)


# =================================================================== PLAN 8 : loups
def _forest_dusk():
    a = vgrad([(0, "#1c1838"), (0.35, "#5a3a68"), (0.55, "#e07a5a"), (0.66, "#f4b46a"), (1, "#100c14")])
    glow(a, 760, 560, 90, "#fff8e0", 1.0, 1.2)
    glow(a, 760, 560, 300, "#f0d0ff", 0.25, 2)
    r = rngf(60)
    layers = [(1180, "#8a5a78", 120, 0.0), (1300, "#4a3050", 170, 0), (1430, "#24182c", 240, 0), (1560, "#0c0810", 340, 0)]
    for li, (base, col, size, _) in enumerate(layers):
        c = tuple(int(v * 255) for v in hexc(col))
        def fn(d, im):
            x = -60
            while x < W + 60:
                h = size * r.uniform(1.4, 2.6)
                w = size * r.uniform(0.35, 0.5)
                for k in range(4):
                    yk = base - h * k / 4
                    wk = w * (1 - k / 5)
                    d.polygon([(x - wk, yk), (x + wk, yk), (x, yk - h * 0.45)], fill=c + (255,))
                d.rectangle([x - 6, base - 10, x + 6, base + 400], fill=c + (255,))
                x += w * r.uniform(0.9, 1.6)
            d.rectangle([0, base, W, H], fill=c + (255,))
        over(a, layer_draw(fn))
        fog = np.clip(1 - np.abs(YY - base - 20) / 90, 0, 1)[..., None]
        a = a * (1 - fog * 0.35) + hexc("#d8a0b0") * fog * 0.35
    return a


def scene_wolves_meet(t, lt, dur, ev, fi):
    a = cached("forest", _forest_dusk).copy()
    wild = cached("wolf_w", lambda: silhouette(WOLF, 520, "#0a0708", "#ffb080", (1, -1), 7, flip=True))
    human = cached("wolf_h", lambda: silhouette(WOLF, 520, "#0a0708", "#c0a8ff", (-1, -1), 7))
    k = ease(lt / 2.3)
    sniff = 8 * math.sin(t * 9) * (lt > 2.3)
    y = 1640
    paste(a, wild, 540 - 430 + 245 * k, y - wild.shape[0] / 2 + sniff)
    paste(a, human, 540 + 430 - 245 * k, y - human.shape[0] / 2 - sniff)
    # lambeau de tee-shirt rouge : l'humain devenu loup
    def fn(d, im):
        x = 540 + 430 - 245 * k - 80
        d.polygon([(x, y - 200 - sniff), (x + 50, y - 215 - sniff), (x + 60, y - 160 - sniff), (x + 15, y - 140 - sniff)], fill=(170, 20, 25, 255))
    over(a, layer_draw(fn))
    return camera(a, 1.0 + 0.06 * lt / dur, 0.5, 0.62)


def scene_wolves_leave(t, lt, dur, ev, fi):
    a = cached("forest", _forest_dusk).copy()
    wild = cached("wolf_w", lambda: silhouette(WOLF, 520, "#0a0708", "#ffb080", (1, -1), 7, flip=True))
    human = cached("wolf_h2", lambda: silhouette(WOLF, 520, "#0a0708", "#c0a8ff", (1, -1), 7, flip=True))
    k = ease(lt / dur)
    s = 1.0 - 0.6 * k
    for i, (L, dx) in enumerate(((wild, -60), (human, 110))):
        bob = 10 * abs(math.sin(t * 7 + i)) * s
        x = 420 + dx + 380 * k
        y = 1640 - 260 * k
        paste(a, L, x, y - L.shape[0] / 2 * s - bob, s)
    fog = np.clip(1 - np.abs(YY - 1500) / 160, 0, 1)[..., None] * (0.15 + 0.2 * k)
    a = a * (1 - fog) + hexc("#d8a0b0") * fog
    return camera(a, 1.06 - 0.04 * k, 0.5, 0.6)


# =================================================================== PLAN 9 : de l'œil à la Terre
def scene_eye_reflect(t, lt, dur, ev, fi):
    if ("reflect_img", "forest") not in CACHE:
        f = cached("forest", _forest_dusk)
        CACHE[("reflect_img", "forest")] = f[400:1700:2, ::2][::1, ::-1]
    a = eye(1.0, 60, "forest")
    if lt < 2.5:
        z = 4.0 * (1 - ease(lt / 2.5)) + 1.0 * ease(lt / 2.5)
        return camera(a, z, 0.5, EYE_C[1] / H)
    k = ease((lt - 2.5) / 0.5)
    s = 1 - 0.65 * k
    small = to_img(a).resize((int(W * s), int(H * s)), Image.BILINEAR)
    out = cached("stars", _stars).copy()
    sw, shh = small.size
    yy, xx = np.mgrid[0:shh, 0:sw].astype(np.float32)
    circ = np.clip(1 - np.sqrt(((xx - sw / 2) / (sw * 0.45)) ** 2 + ((yy - EYE_C[1] * s) / (sw * 0.36)) ** 2), 0, 1) ** 0.6
    rgba = np.dstack([np.asarray(small, np.float32) / 255, circ * (1 - k)])
    paste(out, rgba, 540, 960)
    return out


def _stars():
    a = np.zeros((H, W, 3), np.float32)
    r = rngf(100)
    for _ in range(900):
        x, y = r.integers(0, W), r.integers(0, H)
        b = r.random() ** 3
        a[y, x] = b
    return blur(a, 0.8) * 2.2


def _earth_tex():
    h, w = 1024, 2048
    land = fbm(h, w, 202, 7, 3)
    clouds = fbm(h, w, 303, 7, 5)
    lat = np.linspace(90, -90, h)[:, None] * np.ones((1, w))
    ocean = np.array([0.02, 0.10, 0.30], np.float32)
    tex = np.zeros((h, w, 3), np.float32) + ocean
    isl = land > 0.53
    coast = np.clip((land - 0.515) / 0.03, 0, 1)[..., None]
    green = np.array([0.10, 0.36, 0.08]) * (0.7 + 0.6 * land[..., None])
    brown = np.array([0.45, 0.36, 0.20])
    dry = np.clip((land - 0.62) * 5, 0, 1)[..., None] * (np.abs(lat[..., None]) < 35)
    landcol = green * (1 - dry * 0.6) + brown * dry * 0.6
    tex = tex * (1 - coast) + landcol * coast
    ice = np.abs(lat) > 72
    tex[ice] = 0.9
    cl = np.clip((clouds - 0.56) * 4, 0, 0.85)[..., None]
    tex = tex * (1 - cl) + cl
    return tex.astype(np.float32)


def render_earth(R, rot):
    tex = cached("earth_tex", _earth_tex)
    S = int(min(1500, max(500, 2 * R)))
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    x = (xx - S / 2) / (S / 2)
    y = (yy - S / 2) / (S / 2)
    rr = x * x + y * y
    inside = rr < 1
    z = np.sqrt(np.clip(1 - rr, 0, 1))
    lat = np.arcsin(np.clip(-y, -1, 1))
    lon = np.arctan2(x, z) + rot
    u = ((lon / (2 * np.pi)) % 1 * (tex.shape[1] - 1)).astype(int)
    v = ((0.5 - lat / np.pi) * (tex.shape[0] - 1)).astype(int)
    col = tex[v, u]
    L = np.array([0.75, -0.35, 0.55]); L /= np.linalg.norm(L)
    shade = np.clip(x * L[0] + (-y) * -L[1] + z * L[2], 0, 1) ** 0.8
    col = col * (0.02 + 1.1 * shade[..., None])
    atm = (1 - z) ** 3 * (0.3 + shade)
    col = col + atm[..., None] * np.array([0.25, 0.5, 1.0]) * 0.8
    alpha = np.clip((1 - rr) * S / 4, 0, 1)
    # halo atmosphérique hors du disque
    halo = np.clip(1 - (np.sqrt(rr) - 1) / 0.06, 0, 1) * (rr >= 1) * 0.6
    rgba = np.dstack([np.clip(col, 0, 1) * (alpha[..., None]) + np.array([0.3, 0.55, 1.0]) * halo[..., None] * (1 - alpha[..., None]),
                      np.clip(alpha + halo, 0, 1)]).astype(np.float32)
    return rgba, S


def scene_earth(t, lt, dur, ev, fi):
    a = cached("stars", _stars).copy()
    k = ease(lt / dur)
    R = 1700 * (1 - k) + 360 * k
    rgba, S = render_earth(R, 1.2 + lt * 0.08)
    paste(a, rgba, 540, 960 + 300 * (1 - k), (2 * R) / S)
    if lt < 0.4:
        a = a * ease(lt / 0.4)
    return a


# =================================================================== PLAN 10
def scene_eye_cta(t, lt, dur, ev, fi):
    op = 1.0
    for tb in (62.3,):
        if tb <= t < tb + 0.24:
            u = (t - tb) / 0.24
            op = abs(1 - 2 * u)
    close_t = ev["final_boom"] + 0.25
    if t > close_t:
        op = max(0.0, 1 - (t - close_t) / 0.25)
    a = eye(op, 38, None)
    zoom = 1.2 + 0.08 * lt / dur
    sh = (0, 0)
    fb = ev["final_boom"]
    if 0 <= t - fb < 0.45:
        r = rngf(fi)
        kk = 1 - (t - fb) / 0.45
        sh = (r.uniform(-24, 24) * kk, r.uniform(-24, 24) * kk)
        zoom += 0.1 * kk
    a = camera(a, zoom, 0.5, EYE_C[1] / H, shake=sh)
    if t > 60.4:
        k = min(1, (t - 60.4) / 0.18)
        cta = cached("cta", lambda: text_layer(["QUEL ANIMAL", "SERAIS-TU ?"], 118, fill=(255, 255, 255), stroke=10, y=0.07,
                                                 emoji_tail="👇"))
        s = 1.25 - 0.25 * ease(k)
        c = np.zeros_like(cta)
        c = paste(np.zeros((H, W, 3), np.float32), cta, 540, 960, 1.0)  # placeholder for shape
        over(a, cta if s <= 1.001 else _scaled_layer(cta, s), k)
    if 0 <= t - fb < 0.1:
        a = a + 0.4 * (1 - (t - fb) / 0.1)
    if t > close_t:
        a = a * max(0, 1 - (t - close_t) / 0.35)
    return a


def _scaled_layer(layer, s):
    im = Image.fromarray((layer * 255).astype(np.uint8), "RGBA")
    w, h = int(W * s), int(H * s)
    im = im.resize((w, h), Image.BILINEAR)
    x0, y0 = (w - W) // 2, int(0.12 * H * (s - 1))
    im = im.crop((x0, y0, x0 + W, y0 + H))
    return np.asarray(im, np.float32) / 255


SCENES = {k[6:]: v for k, v in globals().items() if k.startswith("scene_")}

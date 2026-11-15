"""Karizma Coiff — YouTube Short « Le date de Théo »
Rendu 100 % procédural : images (PIL) + son (numpy) + montage (ffmpeg).
Usage : python3 short/render.py  -> short/karizma_short.mp4
"""
import math, os, subprocess, wave, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
OUT = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)
FD = "/usr/share/fonts/opentype/inter/"
def F(sz, w="Black"): return ImageFont.truetype(FD + f"Inter-{w}.otf", sz)

# ------------------------------------------------------------------ timeline
# (start, end, scene)
SCENES = [
    (0.0, 3.2, "hook"),
    (3.2, 7.4, "enter"),
    (7.4, 11.2, "who"),
    (11.2, 18.0, "montage"),
    (18.0, 21.6, "reveal"),
    (21.6, 27.6, "pay"),
    (27.6, 32.4, "ines"),
    (32.4, 36.0, "end"),
]
DUR = SCENES[-1][1]

def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def pop(t):  # overshoot pop-in 0..1
    t = max(0, min(1, t)); return 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2 if t < 1 else 1

# ------------------------------------------------------------------ décor
def make_salon():
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):  # mur dégradé
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(28 + 20 * k), int(22 + 14 * k), int(48 + 10 * k)))
    # carrelage sol
    d.rectangle([0, 1380, W, H], fill=(235, 228, 215))
    for i in range(-10, 20):
        for j in range(8):
            if (i + j) % 2 == 0:
                x0 = i * 120 - j * 0; y0 = 1380 + j * 70
                d.rectangle([x0, y0, x0 + 120, y0 + 70], fill=(30, 30, 34))
    # miroir
    d.rounded_rectangle([140, 420, 940, 1180], 40, fill=(70, 90, 120), outline=(212, 175, 55), width=14)
    for k in range(6):
        d.line([(260 + k * 40, 460), (160 + k * 40, 700)], fill=(110, 135, 170), width=8)
    # enseigne néon
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((W // 2, 250), "KARIZMA COIFF", font=F(110), fill=(255, 60, 170, 255), anchor="mm")
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    im.paste(glow, (0, 0), glow); im.paste(glow, (0, 0), glow)
    d = ImageDraw.Draw(im)
    d.text((W // 2, 250), "KARIZMA COIFF", font=F(110), fill=(255, 215, 240), anchor="mm")
    # poteau barbier
    d.rounded_rectangle([960, 480, 1030, 900], 30, fill=(240, 240, 240))
    for k in range(8):
        d.polygon([(960, 500 + k * 50), (1030, 470 + k * 50), (1030, 490 + k * 50), (960, 520 + k * 50)], fill=(220, 30, 40))
    # plante
    d.rectangle([40, 1240, 120, 1380], fill=(150, 80, 40))
    for a in range(-60, 61, 30):
        r = math.radians(a - 90)
        d.ellipse([80 + 90 * math.cos(r) - 30, 1220 + 110 * math.sin(r) - 40, 80 + 90 * math.cos(r) + 30, 1220 + 110 * math.sin(r) + 40], fill=(60, 160, 90))
    return im

def make_street():
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(255 - 120 * k), int(130 - 60 * k), int(90 + 60 * k)))
    random.seed(3)
    for i in range(9):  # immeubles
        x = i * 130 - 20; h = random.randint(500, 1000)
        d.rectangle([x, 1400 - h, x + 120, 1400], fill=(40 + i * 3, 30, 60))
        for wy in range(1400 - h + 40, 1380, 80):
            for wx in (x + 20, x + 70):
                if random.random() > .4: d.rectangle([wx, wy, wx + 30, wy + 40], fill=(255, 210, 120))
    d.rectangle([0, 1400, W, H], fill=(50, 50, 60))
    return im

SALON, STREET = make_salon(), make_street()

# ------------------------------------------------------------------ personnages
SKIN_T, SKIN_K, SKIN_I = (196, 140, 100), (120, 78, 52), (150, 100, 70)

def eyes(d, cx, cy, s, mood, blink=False):
    for sx in (-1, 1):
        ex = cx + sx * 42 * s; ey = cy - 10 * s
        if blink:
            d.line([(ex - 16 * s, ey), (ex + 16 * s, ey)], fill=(20, 20, 20), width=int(6 * s)); continue
        r = 22 * s if mood in ("shock", "love") else 17 * s
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill="white")
        if mood == "love":
            hx, hy, hs = ex, ey, 12 * s
            d.ellipse([hx - hs, hy - hs, hx, hy], fill=(230, 30, 70)); d.ellipse([hx, hy - hs, hx + hs, hy], fill=(230, 30, 70))
            d.polygon([(hx - hs, hy - hs / 2), (hx + hs, hy - hs / 2), (hx, hy + hs)], fill=(230, 30, 70))
        else:
            pr = 8 * s if mood == "shock" else 10 * s
            d.ellipse([ex - pr, ey - pr, ex + pr, ey + pr], fill=(25, 25, 30))
        if mood == "angry":
            d.line([(ex - 26 * s, ey - 34 * s - sx * 10 * s), (ex + 26 * s, ey - 34 * s + sx * 10 * s)], fill=(20, 20, 20), width=int(9 * s))
        elif mood in ("sad", "panic"):
            d.line([(ex - 24 * s, ey - 30 * s + sx * 10 * s), (ex + 24 * s, ey - 30 * s - sx * 10 * s)], fill=(20, 20, 20), width=int(7 * s))
        else:
            d.arc([ex - 26 * s, ey - 46 * s, ex + 26 * s, ey - 20 * s], 200, 340, fill=(20, 20, 20), width=int(7 * s))

def mouth(d, cx, cy, s, mood, talk):
    my = cy + 50 * s
    if mood in ("shock", "panic"):
        o = 18 + 10 * talk
        d.ellipse([cx - 20 * s, my - o * s, cx + 20 * s, my + o * s], fill=(80, 20, 30))
    elif mood in ("happy", "love", "smug"):
        o = 8 + 22 * talk
        d.chord([cx - 45 * s, my - 30 * s, cx + 45 * s, my + o * s], 0, 180, fill=(80, 20, 30))
        d.rectangle([cx - 30 * s, my - 2 * s, cx + 30 * s, my + 6 * s], fill="white")
    elif mood in ("sad", "angry"):
        d.arc([cx - 35 * s, my, cx + 35 * s, my + 40 * s], 200, 340, fill=(60, 20, 30), width=int(8 * s))
        if talk > .3: d.ellipse([cx - 14 * s, my + 4 * s, cx + 14 * s, my + 24 * s], fill=(80, 20, 30))
    else:
        o = 4 + 18 * talk
        d.ellipse([cx - 28 * s, my - o * s / 2, cx + 28 * s, my + o * s / 2], fill=(80, 20, 30))

def body(d, cx, cy, s, shirt, cape=False):
    d.rectangle([cx - 28 * s, cy + 100 * s, cx + 28 * s, cy + 160 * s], fill=shirt if cape else (0, 0, 0, 0))
    col = (235, 235, 240) if cape else shirt
    d.rounded_rectangle([cx - 150 * s, cy + 150 * s, cx + 150 * s, cy + 560 * s], int(70 * s), fill=col)

def theo(im, cx, cy, s, mood="neutral", talk=0, hair=0.0, cape=False, blink=False, sweat=False):
    d = ImageDraw.Draw(im, "RGBA")
    body(d, cx, cy, s, (40, 110, 230), cape)
    d.rectangle([cx - 30 * s, cy + 90 * s, cx + 30 * s, cy + 160 * s], fill=SKIN_T)
    d.ellipse([cx - 120 * s, cy - 130 * s, cx + 120 * s, cy + 130 * s], fill=SKIN_T)
    d.ellipse([cx - 140 * s, cy - 20 * s, cx - 105 * s, cy + 40 * s], fill=SKIN_T)
    d.ellipse([cx + 105 * s, cy - 20 * s, cx + 140 * s, cy + 40 * s], fill=SKIN_T)
    # cheveux : coupe ratée -> dégradé propre
    a_bad, a_good = int(255 * (1 - hair)), int(255 * hair)
    if a_bad:
        c = (40, 25, 15, a_bad)
        pts = [(cx - 125 * s, cy - 10 * s), (cx - 120 * s, cy - 90 * s), (cx - 70 * s, cy - 150 * s), (cx - 50 * s, cy - 115 * s),
               (cx - 10 * s, cy - 170 * s), (cx + 20 * s, cy - 120 * s), (cx + 60 * s, cy - 175 * s), (cx + 80 * s, cy - 120 * s),
               (cx + 125 * s, cy - 120 * s), (cx + 125 * s, cy - 20 * s), (cx + 100 * s, cy - 60 * s), (cx - 100 * s, cy - 60 * s)]
        d.polygon(pts, fill=c)
        for (bx, by, br) in ((-40, -95, 26), (55, -80, 20), (-95, -40, 14)):  # trous de tondeuse
            d.ellipse([cx + (bx - br) * s, cy + (by - br) * s, cx + (bx + br) * s, cy + (by + br) * s], fill=SKIN_T + (a_bad,))
    if a_good:
        d.chord([cx - 122 * s, cy - 135 * s, cx + 122 * s, cy + 40 * s], 180, 360, fill=(70, 55, 50, int(a_good * .55)))
        d.rounded_rectangle([cx - 105 * s, cy - 185 * s, cx + 110 * s, cy - 85 * s], int(45 * s), fill=(25, 18, 12, a_good))
        d.polygon([(cx + 10 * s, cy - 185 * s), (cx + 120 * s, cy - 170 * s), (cx + 95 * s, cy - 130 * s)], fill=(25, 18, 12, a_good))
        d.line([(cx - 80 * s, cy - 92 * s), (cx - 20 * s, cy - 120 * s)], fill=SKIN_T + (a_good,), width=int(5 * s))  # trait
    eyes(d, cx, cy, s, mood, blink)
    mouth(d, cx, cy, s, mood, talk)
    if sweat:
        d.polygon([(cx + 120 * s, cy - 90 * s), (cx + 105 * s, cy - 50 * s), (cx + 135 * s, cy - 50 * s)], fill=(120, 200, 255))
        d.ellipse([cx + 105 * s, cy - 65 * s, cx + 135 * s, cy - 35 * s], fill=(120, 200, 255))

def karim(im, cx, cy, s, mood="smug", talk=0, blink=False, dark=0.0):
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle([cx - 165 * s, cy + 150 * s, cx + 165 * s, cy + 600 * s], int(70 * s), fill=(245, 245, 245))
    d.rounded_rectangle([cx - 110 * s, cy + 190 * s, cx + 110 * s, cy + 600 * s], int(30 * s), fill=(25, 25, 28))  # tablier
    d.text((cx, cy + 300 * s), "K", font=F(int(90 * s)), fill=(212, 175, 55), anchor="mm")
    d.rectangle([cx - 35 * s, cy + 90 * s, cx + 35 * s, cy + 160 * s], fill=SKIN_K)
    d.ellipse([cx - 125 * s, cy - 135 * s, cx + 125 * s, cy + 130 * s], fill=SKIN_K)
    d.chord([cx - 125 * s, cy - 140 * s, cx + 125 * s, cy + 20 * s], 180, 360, fill=(20, 15, 12))  # coupe courte
    d.chord([cx - 118 * s, cy - 40 * s, cx + 118 * s, cy + 150 * s], 0, 180, fill=(20, 15, 12))  # barbe
    d.ellipse([cx - 70 * s, cy + 20 * s, cx + 70 * s, cy + 90 * s], fill=SKIN_K)
    d.rectangle([cx - 60 * s, cy + 20 * s, cx + 60 * s, cy + 36 * s], fill=(20, 15, 12))  # moustache
    eyes(d, cx, cy, s, mood, blink)
    mouth(d, cx, cy + 5 * s, s, mood, talk)
    if dark > 0:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([cx - 135 * s, cy - 145 * s, cx + 135 * s, cy + 145 * s], fill=(0, 0, 0, int(140 * dark)))
        im.alpha_composite(sh)
        d = ImageDraw.Draw(im, "RGBA")
        for sx in (-1, 1):  # yeux rouges
            ex, ey = cx + sx * 42 * s, cy - 10 * s
            d.ellipse([ex - 12 * s, ey - 12 * s, ex + 12 * s, ey + 12 * s], fill=(255, 30, 30, int(255 * dark)))

def ines(im, cx, cy, s, mood="happy", talk=0, blink=False):
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([cx - 150 * s, cy - 150 * s, cx + 150 * s, cy + 260 * s], fill=(35, 20, 15))  # cheveux longs
    d.rounded_rectangle([cx - 140 * s, cy + 150 * s, cx + 140 * s, cy + 560 * s], int(70 * s), fill=(250, 200, 60))
    d.rectangle([cx - 28 * s, cy + 90 * s, cx + 28 * s, cy + 160 * s], fill=SKIN_I)
    d.ellipse([cx - 115 * s, cy - 125 * s, cx + 115 * s, cy + 125 * s], fill=SKIN_I)
    d.chord([cx - 125 * s, cy - 140 * s, cx + 125 * s, cy + 10 * s], 180, 360, fill=(35, 20, 15))
    d.ellipse([cx + 60 * s, cy - 190 * s, cx + 140 * s, cy - 110 * s], fill=(35, 20, 15))  # chignon
    d.ellipse([cx + 85 * s, cy - 135 * s, cx + 115 * s, cy - 105 * s], fill=(230, 40, 120))
    eyes(d, cx, cy, s, mood, blink)
    mouth(d, cx, cy, s, mood, talk)
    for sx in (-1, 1):
        d.ellipse([cx + sx * 70 * s - 18 * s, cy + 25 * s, cx + sx * 70 * s + 18 * s, cy + 45 * s], fill=(240, 120, 130, 120))

# ------------------------------------------------------------------ UI
def wrap(text, font, maxw, d):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w_
    lines.append(cur); return lines

def bubble(im, text, x, y, tail_x, tail_y, t, color=(255, 255, 255), fg=(15, 15, 20), size=58, name=None, ncol=(255, 60, 170)):
    if t <= 0: return
    sc = pop(min(1, t / 0.25))
    font = F(size, "ExtraBold")
    d0 = ImageDraw.Draw(im)
    lines = wrap(text, font, 780, d0)
    lh = size * 1.22
    bw = max(d0.textlength(l, font=font) for l in lines) + 80
    bh = lh * len(lines) + 60
    layer = Image.new("RGBA", (int(bw + 40), int(bh + 140)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, oy = 20, 50
    tx = max(60, min(bw - 60, tail_x - (x - bw / 2)))
    below = tail_y > y
    if below:
        d.polygon([(ox + tx - 30, oy + bh - 5), (ox + tx + 30, oy + bh - 5), (ox + tx + (tail_x - x) * .05, oy + bh + 70)], fill=color)
    d.rounded_rectangle([ox, oy, ox + bw, oy + bh], 40, fill=color, outline=(15, 15, 20), width=6)
    if below:
        d.polygon([(ox + tx - 24, oy + bh - 8), (ox + tx + 24, oy + bh - 8), (ox + tx, oy + bh + 55)], fill=color)
    for i, l in enumerate(lines):
        d.text((ox + bw / 2, oy + 30 + lh * i + lh / 2), l, font=font, fill=fg, anchor="mm")
    if name:
        nf = F(36, "Black")
        nw = d.textlength(name, font=nf) + 40
        d.rounded_rectangle([ox + 20, oy - 34, ox + 20 + nw, oy + 22], 20, fill=ncol)
        d.text((ox + 40, oy - 6), name, font=nf, fill="white", anchor="lm")
    if sc != 1:
        layer = layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))))
    im.alpha_composite(layer, (int(x - layer.width / 2), int(y - layer.height / 2)))

def caption(im, text, y, t, size=92, fill=(255, 255, 255), stroke=(0, 0, 0), hl=None):
    if t <= 0: return
    font = F(size)
    d = ImageDraw.Draw(im)
    lines = wrap(text, font, 960, d)
    sc = pop(min(1, t / 0.2))
    for i, l in enumerate(lines):
        f2 = F(max(8, int(size * sc)))
        col = hl if (hl and i == len(lines) - 1) else fill
        d.text((W // 2, y + i * size * 1.15), l, font=f2, fill=col, anchor="mm", stroke_width=10, stroke_fill=stroke)

def talkv(t): return abs(math.sin(t * 18)) if t > 0 else 0
def blinkv(t): return (t % 3.1) < 0.12

def camera(im, zoom=1.0, fx=W / 2, fy=H / 2, shake=0, rot=0):
    if zoom == 1 and not shake and not rot: return im
    cw, ch = W / zoom, H / zoom
    x0 = min(max(0, fx - cw / 2), W - cw) + (random.uniform(-shake, shake))
    y0 = min(max(0, fy - ch / 2), H - ch) + (random.uniform(-shake, shake))
    out = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BICUBIC)
    if rot: out = out.rotate(rot, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 255))
    return out

def flash(im, a):
    if a > 0: im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * min(1, a)))))

def sparkles(im, t, cx, cy, n=14, rad=320):
    d = ImageDraw.Draw(im)
    for i in range(n):
        a = i / n * 6.283 + t * 1.5
        r = rad + 40 * math.sin(t * 5 + i)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a) * .8
        k = 18 + 14 * abs(math.sin(t * 8 + i))
        d.polygon([(x, y - k), (x + k / 4, y - k / 4), (x + k, y), (x + k / 4, y + k / 4), (x, y + k), (x - k / 4, y + k / 4), (x - k, y), (x - k / 4, y - k / 4)], fill=(255, 225, 90))

def clock(im, x, y, r, secs_left, red=False):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x - r * 1.6, y - r * .6, x + r * 1.6, y + r * .6], 30, fill=(230, 30, 50) if red else (20, 20, 25), outline="white", width=6)
    m, s = int(secs_left // 60), int(secs_left % 60)
    d.text((x, y), f"{m:02d}:{s:02d}", font=F(int(r * .75)), fill="white", anchor="mm")

def progress_bar(im, t):
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 14, W * t / DUR, H], fill=(255, 60, 170))

# ------------------------------------------------------------------ scènes
def scene(name, t, T):
    """t = temps local, T = temps global. Renvoie une image RGBA."""
    if name == "hook":
        im = STREET.copy().convert("RGBA")
        run = math.sin(t * 22) * 18
        theo(im, 540 + run, 1150 + abs(run), 1.25, "panic", talkv(t), hair=0, sweat=True)
        d = ImageDraw.Draw(im)
        for i in range(6):  # traits de vitesse
            yy = 950 + i * 90; xx = (t * 1800 + i * 200) % 1300 - 200
            d.line([(xx, yy), (xx + 180, yy)], fill=(255, 255, 255), width=8)
        caption(im, "Il avait 15 MINUTES", 330, t - .1, 84)
        caption(im, "avant son 1er date…", 440, t - .5, 80, hl=(255, 230, 60))
        caption(im, "et il s'était coupé les cheveux TOUT SEUL", 1720, t - 1.3, 64, hl=(255, 80, 80))
        return camera(im, 1 + .06 * t, 540, 1100, shake=4)
    if name == "enter":
        im = SALON.copy().convert("RGBA")
        k = ease(t / .5)
        karim(im, 790, 900, .95, "neutral" if t < 2.3 else "shock", 0, blinkv(T))
        theo(im, -200 + 540 * k, 1000, 1.0, "panic", talkv(t - .4), hair=0, sweat=True)
        flash(im, max(0, .6 - t * 3))
        bubble(im, "AIDE-MOI FRÈRE !! J'ai un date dans 15 min !!", 470, 420, 340, 800, t - .4, name="THÉO", ncol=(40, 110, 230))
        clock(im, 840, 1700, 110, 15 * 60 - t * 3)
        return camera(im, 1, shake=8 if t < .6 else 0)
    if name == "who":
        im = SALON.copy().convert("RGBA")
        karim(im, 760, 860, 1.05, "angry" if t < 1.9 else "smug", talkv(t - .1) if t < 1.6 else 0, blinkv(T))
        theo(im, 320, 1020, 1.0, "sad", talkv(t - 2.0) if t > 2.0 else 0, hair=0)
        bubble(im, "…Qui t'a fait ÇA ?", 640, 400, 760, 700, t - .1, name="KARIM", ncol=(212, 140, 30))
        bubble(im, "Moi… avec la tondeuse de mon père", 420, 640, 320, 860, t - 1.9, name="THÉO", ncol=(40, 110, 230))
        return camera(im, 1.12 - .08 * ease(t / 3), 540, 900)
    if name == "montage":
        im = SALON.copy().convert("RGBA")
        p = ease((t - 1.0) / 5.2)
        theo(im, 540, 1000, 1.05, "shock" if p < .5 else "happy", 0, hair=p, cape=True, blink=blinkv(T))
        karim(im, 900, 760, .7, "smug", 0, blinkv(T + .5))
        d = ImageDraw.Draw(im)
        # ciseaux / tondeuse qui tournent autour de la tête
        for i in range(2):
            a = t * 9 + i * 3.14
            sx, sy = 540 + 210 * math.cos(a), 860 + 120 * math.sin(a)
            d.ellipse([sx - 22, sy - 22, sx + 22, sy + 22], outline=(220, 220, 230), width=8)
            d.line([(sx, sy), (sx + 90 * math.cos(a + 1), sy + 90 * math.sin(a + 1))], fill=(200, 200, 210), width=12)
        random.seed(int(T * 30))
        for _ in range(int(25 * (1 - p)) + 5):  # cheveux qui volent
            hx, hy = 540 + random.uniform(-260, 260), 860 + random.uniform(-200, 500)
            d.line([(hx, hy), (hx + random.uniform(-25, 25), hy + 25)], fill=(40, 25, 15), width=6)
        caption(im, "MODE KARIZMA : ACTIVÉ", 360, t, 86, fill=(255, 230, 60))
        secs = 15 * 60 * (1 - t / 6.8) + 3
        clock(im, 540, 1700, 130, secs, red=secs < 120)
        z = 1.06 + .04 * math.sin(t * 6)
        return camera(im, z, 540, 1000, shake=6 * (1 - p))
    if name == "reveal":
        im = SALON.copy().convert("RGBA")
        theo(im, 540, 1000, 1.15, "love" if t > .9 else "shock", talkv(t - 1.0) if t > 1.0 else 0, hair=1, blink=False)
        sparkles(im, T, 540, 900)
        flash(im, max(0, 1 - t * 3))
        bubble(im, "FRÈRE… c'est MOI ça ?!", 540, 380, 560, 700, t - 1.0, name="THÉO", ncol=(40, 110, 230), size=66)
        clock(im, 540, 1730, 100, 32, red=True)
        return camera(im, 1.0 + .05 * t, 540, 950)
    if name == "pay":
        im = SALON.copy().convert("RGBA")
        theo(im, 300, 1020, .95, "happy", talkv(t - .2) if t < 1.4 or 4.3 < t < 5.4 else 0, hair=1, blink=blinkv(T))
        karim(im, 790, 900, .95, "smug", talkv(t - 1.6) if 1.6 < t < 4.0 else 0, blinkv(T + 1))
        if t < 4.3:
            bubble(im, "Merci !! Je te dois combien ?", 380, 420, 300, 830, t - .2, name="THÉO", ncol=(40, 110, 230))
            bubble(im, "Rien. Dis-moi juste… elle s'appelle comment ?", 640, 690, 790, 760, t - 1.6, name="KARIM", ncol=(212, 140, 30))
        else:
            theo(im, 300, 1020, .95, "love", talkv(t - 4.3), hair=1)
            bubble(im, "INÈS", 330, 560, 300, 830, t - 4.3, name="THÉO", ncol=(40, 110, 230), size=110, color=(255, 220, 235))
        return im
    if name == "ines":
        im = SALON.copy().convert("RGBA")
        d = ImageDraw.Draw(im)
        k = ease((t - .3) / .6)
        ines(im, 1300 - 420 * k, 940, .95, "happy", talkv(t - .9) if t > .9 else 0, blinkv(T))
        theo(im, 280, 1020, .95, "love" if t < .8 else "shock", 0, hair=1, sweat=t > 1.0)
        karim(im, 600, 880, .85, "smug" if t < 2.6 else "happy", talkv(t - 2.6) if t > 2.6 else 0, blinkv(T))
        if t < .7: caption(im, "*ding dong*", 520, t, 80, fill=(255, 230, 60))
        bubble(im, "PAPA ! T'as fini ? Mon date arrive !", 560, 420, 880, 800, t - .9, name="INÈS", ncol=(230, 40, 120))
        bubble(im, "Ah. Il est déjà là, ma chérie.", 520, 1580, 600, 1200, t - 2.6, name="KARIM", ncol=(212, 140, 30), size=54)
        return im
    if name == "end":
        im = SALON.copy().convert("RGBA")
        karim(im, 760, 800, 1.0, "angry", 0, False, dark=ease(t / 1.0))
        theo(im, 320, 1060, 1.0, "panic", 0, hair=1, sweat=True)
        d = ImageDraw.Draw(im)
        if t > .6:  # ciseaux qui claquent
            a = .25 * abs(math.sin(t * 10))
            for sgn in (-1, 1):
                d.line([(960, 1180), (960 - 160 * math.cos(a * sgn), 1180 - 160 * math.sin(a * sgn) - 40)], fill=(220, 220, 230), width=16)
            caption(im, "*clic clic*", 1350, t - .6, 70, fill=(255, 230, 60))
        z = 1 + .35 * ease(t / 1.2)
        im = camera(im, z, 560, 950, shake=3)
        caption(im, "PARTIE 2 ?", 300, t - 1.2, 130, fill=(255, 60, 170))
        caption(im, "Abonne-toi pour la suite", 1700, t - 1.6, 64)
        return im

# ------------------------------------------------------------------ rendu images
def render_frames():
    n = int(DUR * FPS)
    for f in range(n):
        T = f / FPS
        for s, e, name in SCENES:
            if s <= T < e: break
        im = scene(name, T - s, T)
        # fondu rapide entre scènes
        if T - s < .08 and f: flash(im, .35)
        progress_bar(im, T)
        im.convert("RGB").save(os.path.join(FRAMES, f"{f:05d}.jpg"), quality=90)
    return n

# ------------------------------------------------------------------ audio
SR = 44100
def tone(f, d, v=.3, kind="sin"):
    t = np.arange(int(SR * d)) / SR
    w = np.sin(2 * np.pi * f * t) if kind == "sin" else np.sign(np.sin(2 * np.pi * f * t))
    return v * w * np.exp(-t * 4)

def mix(buf, snd, at):
    i = int(at * SR); j = min(len(buf), i + len(snd)); buf[i:j] += snd[: j - i]

def render_audio(path):
    n = int(SR * DUR); buf = np.zeros(n)
    bpm = 104; beat = 60 / bpm
    rng = np.random.default_rng(1)
    def kick():
        t = np.arange(int(SR * .25)) / SR
        return .9 * np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    def hat(): return .12 * rng.standard_normal(int(SR * .05)) * np.exp(-np.arange(int(SR * .05)) / SR * 80)
    def snare(): return .35 * rng.standard_normal(int(SR * .18)) * np.exp(-np.arange(int(SR * .18)) / SR * 22)
    chords = [(220, 261.6, 329.6), (174.6, 220, 261.6), (196, 246.9, 293.7), (164.8, 207.7, 246.9)]
    b, i = 0.0, 0
    while b < 32.4:  # musique jusqu'au twist
        mix(buf, kick() * (.5 if b < 3.2 else 1), b)
        mix(buf, hat(), b + beat / 2)
        if i % 2 == 1: mix(buf, snare(), b)
        if i % 4 == 0:
            for f_ in chords[(i // 4) % 4]:
                t = np.arange(int(SR * beat * 4)) / SR
                mix(buf, .06 * np.sin(2 * np.pi * f_ * t) * np.minimum(1, t * 8) * np.exp(-t * .6), b)
        b += beat; i += 1
    # SFX
    def whoosh(d=.4):
        x = rng.standard_normal(int(SR * d)); env = np.sin(np.linspace(0, np.pi, len(x)))
        return .35 * np.convolve(x, np.ones(30) / 30, "same") * env
    for s, _, _ in SCENES[1:]: mix(buf, whoosh(), s - .2)
    mix(buf, kick() * 1.4, 3.2)  # porte claquée
    for k in range(int(6.8 / .5)):  # tic-tac
        mix(buf, tone(2000 if k % 2 else 1500, .05, .25), 11.2 + k * .5)
    t = np.arange(int(SR * 5.4)) / SR  # tondeuse
    buzz = .12 * np.sign(np.sin(2 * np.pi * 110 * t)) * (0.7 + .3 * np.sin(2 * np.pi * 7 * t))
    mix(buf, buzz, 12.2)
    for k in range(10): mix(buf, tone(1200 + 80 * k, .25, .18), 18.0 + k * .07)  # sparkle
    mix(buf, tone(988, .9, .35) + 0, 27.7); mix(buf, tone(784, 1.0, .35), 28.15)  # ding dong
    # record scratch + silence + ton grave
    t = np.arange(int(SR * .5)) / SR
    mix(buf, .5 * np.sin(2 * np.pi * (900 * np.exp(-t * 6)) * t) * (rng.standard_normal(len(t)) * .3 + .7), 32.35)
    t = np.arange(int(SR * 3.4)) / SR
    mix(buf, .3 * np.sin(2 * np.pi * 55 * t) * np.minimum(1, t * 2) + .12 * np.sin(2 * np.pi * 58 * t), 32.6)
    for k in range(8): mix(buf, .4 * rng.standard_normal(int(SR * .03)), 33.0 + k * .3)  # clic clic
    buf = buf / max(1e-6, np.abs(buf).max()) * .9
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    render_frames()
    wav = os.path.join(OUT, "audio.wav"); render_audio(wav)
    mp4 = os.path.join(OUT, "karizma_short.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(FRAMES, "%05d.jpg"),
                    "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("OK", mp4)

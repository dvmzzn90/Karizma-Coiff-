"""YouTube Short #2 — « Il s'est mis au sport pour sa femme… »
Rendu procédural : PIL (images) + numpy (son) + ffmpeg.
Usage : python3 short2/render.py  -> short2/salle_de_sport_short.mp4
"""
import math, os, sys, random, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "short"))
from render import (F, ease, pop, eyes, mouth, bubble, caption, camera, flash, sparkles,
                    talkv, blinkv, tone, mix, SR)  # helpers du premier Short

W, H, FPS = 1080, 1920, 30
OUT = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)

SCENES = [
    (0.0, 4.0, "hook"),
    (4.0, 10.5, "home1"),
    (10.5, 16.5, "home2"),
    (16.5, 23.5, "gym1"),
    (23.5, 31.0, "train1"),
    (31.0, 37.5, "phone"),
    (37.5, 44.0, "train2"),
    (44.0, 48.5, "door"),
    (48.5, 55.5, "caught"),
    (55.5, 63.5, "mic"),
    (63.5, 70.0, "end"),
]
DUR = SCENES[-1][1]

C_MALIK, C_SARAH, C_TONY = (60, 170, 90), (230, 40, 120), (220, 60, 40)

# ------------------------------------------------------------------ décors
def vgrad(top, bot):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bot)))
    return im

def neon(im, text, y, col, size=110):
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).text((W // 2, y), text, font=F(size), fill=col + (255,), anchor="mm")
    g = g.filter(ImageFilter.GaussianBlur(18)); im.paste(g, (0, 0), g); im.paste(g, (0, 0), g)
    ImageDraw.Draw(im).text((W // 2, y), text, font=F(size), fill=(255, 240, 230), anchor="mm")

def make_home(night=False):
    im = vgrad((70, 60, 90), (120, 95, 85)) if night else vgrad((245, 220, 190), (225, 190, 160))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1400, W, H], fill=(140, 95, 60) if not night else (80, 55, 40))
    for x in range(0, W, 90): d.line([(x, 1400), (x - 120, H)], fill=(120, 80, 50) if not night else (65, 45, 32), width=4)
    # fenêtre
    sky = (120, 190, 240) if not night else (20, 25, 60)
    d.rectangle([110, 380, 470, 900], fill=sky, outline=(255, 255, 255), width=18)
    d.line([(290, 380), (290, 900)], fill="white", width=12); d.line([(110, 640), (470, 640)], fill="white", width=12)
    if night: d.ellipse([340, 430, 420, 510], fill=(250, 245, 210))
    # cadre photo de mariage
    d.rectangle([620, 420, 900, 640], fill=(212, 175, 55)); d.rectangle([640, 440, 880, 620], fill=(250, 240, 245))
    d.ellipse([690, 480, 750, 540], fill=(170, 115, 80)); d.ellipse([770, 480, 830, 540], fill=(200, 145, 110))
    d.text((760, 590), "Malik + Sarah", font=F(26, "Bold"), fill=(150, 60, 90), anchor="mm")
    # canapé
    d.rounded_rectangle([90, 1130, 990, 1420], 60, fill=(150, 60, 70) if not night else (110, 45, 55))
    d.rounded_rectangle([60, 1060, 200, 1440], 50, fill=(130, 50, 60) if not night else (95, 38, 48))
    d.rounded_rectangle([880, 1060, 1020, 1440], 50, fill=(130, 50, 60) if not night else (95, 38, 48))
    # lampe
    d.polygon([(960, 700), (1060, 700), (1030, 600), (990, 600)], fill=(255, 220, 140))
    d.rectangle([1005, 700, 1015, 1060], fill=(60, 60, 60))
    return im

def make_gym():
    im = vgrad((25, 25, 30), (55, 50, 55)); d = ImageDraw.Draw(im)
    d.rectangle([0, 1420, W, H], fill=(35, 35, 38))
    for x in range(0, W, 140): d.rectangle([x, 1420, x + 70, H], fill=(45, 45, 48))
    # miroirs
    for x in (60, 560): d.rectangle([x, 420, x + 460, 1200], fill=(60, 75, 95), outline=(150, 150, 160), width=8)
    # rack d'haltères
    d.rectangle([60, 1260, 1020, 1290], fill=(90, 90, 95))
    for i in range(10):
        x = 100 + i * 95; r = 22 + i * 2
        d.ellipse([x - r, 1230 - r, x + r, 1230 + r], fill=(30, 30, 30), outline=(120, 120, 120), width=4)
    neon(im, "IRON PALACE", 250, (255, 70, 40))
    return im

def make_door():
    im = vgrad((15, 15, 40), (40, 35, 70)); d = ImageDraw.Draw(im)
    d.rectangle([0, 1450, W, H], fill=(60, 50, 50))
    d.rectangle([230, 450, 850, 1450], fill=(110, 70, 45), outline=(60, 40, 25), width=16)
    for y in (520, 980): d.rectangle([290, y, 790, y + 380], outline=(80, 50, 30), width=8)
    d.ellipse([760, 940, 800, 980], fill=(220, 190, 80))
    d.rectangle([450, 330, 630, 400], fill=(220, 220, 220)); d.text((540, 365), "N° 12", font=F(40), fill=(40, 40, 40), anchor="mm")
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([380, 150, 700, 330], fill=(255, 220, 120, 160))
    g = g.filter(ImageFilter.GaussianBlur(40)); im.paste(g, (0, 0), g)
    return im

HOME, HOME_N, GYM, DOOR = make_home(), make_home(True), make_gym(), make_door()
STREET_N = vgrad((10, 10, 35), (60, 30, 70))

# ------------------------------------------------------------------ personnage générique
def heart(d, x, y, s, col=(230, 30, 70)):
    d.ellipse([x - s, y - s, x, y]); d.ellipse([x - s, y - s, x, y], fill=col); d.ellipse([x, y - s, x + s, y], fill=col)
    d.polygon([(x - s, y - s / 2), (x + s, y - s / 2), (x, y + s)], fill=col)

def arm(d, x0, y0, x1, y1, w, col, skin, bicep=0):
    d.line([(x0, y0), (x1, y1)], fill=skin, width=int(w)); d.ellipse([x1 - w / 2, y1 - w / 2, x1 + w / 2, y1 + w / 2], fill=skin)
    if bicep > 0:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        d.ellipse([mx - w * bicep, my - w * bicep * .75, mx + w * bicep, my + w * bicep * .75], fill=skin)

def person(im, cx, cy, s, skin, shirt, mood="neutral", talk=0, muscle=0.0, pose="down", blink=False,
           hair=None, extra=None, sweat=False, glasses=False, logo=None, lift=1.0):
    d = ImageDraw.Draw(im, "RGBA")
    tw = (105 + 95 * muscle) * s          # demi-largeur torse
    aw = (30 + 45 * muscle) * s           # épaisseur bras
    sh_y = cy + 175 * s
    # bras derrière le torse (poses)
    if pose == "flex":
        for sx in (-1, 1):
            ex, ey = cx + sx * (tw + 110 * s), sh_y - 10 * s
            arm(d, cx + sx * tw * .85, sh_y + 20 * s, ex, ey, aw, shirt, skin)
            arm(d, ex, ey, ex - sx * 20 * s, ey - 150 * s, aw, shirt, skin, bicep=.9 + .8 * muscle)
    elif pose == "lift":
        for sx in (-1, 1):
            ex, ey = cx + sx * (tw + 70 * s), sh_y - 60 * s
            arm(d, cx + sx * tw * .85, sh_y + 20 * s, ex, ey, aw, shirt, skin)
            arm(d, ex, ey, ex, ey - 170 * s * lift, aw, shirt, skin, bicep=.6 * muscle)
    # torse (débardeur)
    wa = tw * (1 - .38 * min(1, muscle))  # silhouette en V
    d.polygon([(cx - tw, cy + 200 * s), (cx + tw, cy + 200 * s), (cx + wa, cy + 580 * s), (cx - wa, cy + 580 * s)], fill=shirt)
    sr = (55 + 45 * muscle) * s
    for sx in (-1, 1):
        d.ellipse([cx + sx * (tw - sr * .6) - sr, cy + 150 * s, cx + sx * (tw - sr * .6) + sr, cy + 150 * s + 2 * sr], fill=shirt)
        if muscle > .4:  # deltoïdes
            d.ellipse([cx + sx * tw - sr * .8, cy + 160 * s, cx + sx * tw + sr * .8, cy + 160 * s + 1.6 * sr], fill=skin)
    d.rectangle([cx - tw + sr * .4, cy + 150 * s, cx + tw - sr * .4, cy + 260 * s], fill=shirt)
    if muscle > .4:
        d.arc([cx - tw * .8, cy + 190 * s, cx, cy + 300 * s], 20, 160, fill=(0, 0, 0, 60), width=int(6 * s))
        d.arc([cx, cy + 190 * s, cx + tw * .8, cy + 300 * s], 20, 160, fill=(0, 0, 0, 60), width=int(6 * s))
    if logo: d.text((cx, cy + 380 * s), logo, font=F(int(46 * s)), fill=(255, 255, 255, 230), anchor="mm")
    if pose in ("down", "phone", "flowers", "point"):
        for sx in (-1, 1):
            hx = cx + sx * (tw + 25 * s); hy = cy + 470 * s
            if pose == "phone" and sx == 1: hx, hy = cx + 80 * s, cy + 250 * s
            if pose == "flowers" and sx == -1: hx, hy = cx + 30 * s, cy + 300 * s
            if pose == "point" and sx == 1: hx, hy = cx + tw + 230 * s, cy + 200 * s
            arm(d, cx + sx * tw * .8, sh_y + 10 * s, hx, hy, aw, shirt, skin, bicep=.7 * muscle)
    # cou + tête
    nw = (30 + 25 * muscle) * s
    d.rectangle([cx - nw, cy + 90 * s, cx + nw, cy + 165 * s], fill=skin)
    d.ellipse([cx - 115 * s, cy - 130 * s, cx + 115 * s, cy + 130 * s], fill=skin)
    for sx in (-1, 1): d.ellipse([cx + sx * 122 * s - 18 * s, cy - 20 * s, cx + sx * 122 * s + 18 * s, cy + 40 * s], fill=skin)
    if hair: hair(d, cx, cy, s)
    eyes(d, cx, cy, s, mood, blink)
    mouth(d, cx, cy, s, mood, talk)
    if glasses:
        for sx in (-1, 1):
            ex = cx + sx * 42 * s
            d.ellipse([ex - 32 * s, cy - 42 * s, ex + 32 * s, cy + 22 * s], outline=(20, 20, 20), width=int(7 * s))
        d.line([(cx - 10 * s, cy - 12 * s), (cx + 10 * s, cy - 12 * s)], fill=(20, 20, 20), width=int(6 * s))
    if sweat:
        d.ellipse([cx + 100 * s, cy - 70 * s, cx + 130 * s, cy - 30 * s], fill=(120, 200, 255))
    if extra: extra(d, cx, cy, s)

# coiffures
def hair_malik(d, cx, cy, s):
    d.chord([cx - 118 * s, cy - 140 * s, cx + 118 * s, cy + 20 * s], 180, 360, fill=(25, 18, 12))
    for i in range(7):
        x = cx - 95 * s + i * 32 * s; d.ellipse([x - 24 * s, cy - 150 * s, x + 24 * s, cy - 100 * s], fill=(25, 18, 12))
def hair_sarah(d, cx, cy, s):
    d.chord([cx - 130 * s, cy - 150 * s, cx + 130 * s, cy + 30 * s], 180, 360, fill=(120, 50, 25))
    d.polygon([(cx + 100 * s, cy - 60 * s), (cx + 170 * s, cy + 280 * s), (cx + 90 * s, cy + 260 * s)], fill=(120, 50, 25))
    d.polygon([(cx - 100 * s, cy - 60 * s), (cx - 170 * s, cy + 280 * s), (cx - 90 * s, cy + 260 * s)], fill=(120, 50, 25))
def hair_tony(d, cx, cy, s):
    d.ellipse([cx - 60 * s, cy - 128 * s, cx - 10 * s, cy - 110 * s], fill=(255, 255, 255, 110))  # crâne brillant
    d.chord([cx - 70 * s, cy + 30 * s, cx + 70 * s, cy + 130 * s], 0, 180, fill=(230, 190, 70))   # bouc blond
    d.rounded_rectangle([cx - 105 * s, cy - 140 * s, cx + 105 * s, cy - 100 * s], int(15 * s), fill=(20, 20, 20))  # lunettes sur la tête
def sarah_extra(d, cx, cy, s):
    for sx in (-1, 1):
        d.ellipse([cx + sx * 68 * s - 18 * s, cy + 25 * s, cx + sx * 68 * s + 18 * s, cy + 45 * s], fill=(240, 120, 130, 130))
        d.ellipse([cx + sx * 118 * s - 8 * s, cy + 40 * s, cx + sx * 118 * s + 8 * s, cy + 60 * s], fill=(255, 215, 80))
    d.chord([cx - 34 * s, cy + 38 * s, cx + 34 * s, cy + 72 * s], 0, 360, outline=(200, 20, 60), width=int(5 * s))

SK_M, SK_S, SK_T = (165, 112, 78), (210, 155, 120), (225, 170, 125)
def malik(im, cx, cy, s, mood="neutral", talk=0, muscle=0, pose="down", blink=False, sweat=False, lift=1.0):
    person(im, cx, cy, s, SK_M, (150, 150, 160) if muscle < .9 else (30, 30, 35), mood, talk, muscle, pose, blink,
           hair_malik, None, sweat, glasses=muscle < .9, lift=lift)
def sarah(im, cx, cy, s, mood="smug", talk=0, pose="down", blink=False):
    person(im, cx, cy, s, SK_S, (200, 30, 60), mood, talk, 0, pose, blink, hair_sarah, sarah_extra)
def tony(im, cx, cy, s, mood="smug", talk=0, pose="down", blink=False, sweat=False):
    person(im, cx, cy, s, SK_T, (20, 20, 22), mood, talk, 1.25, pose, blink, hair_tony, None, sweat, logo="GÉRANT")

# ------------------------------------------------------------------ accessoires
def phone(im, x, y, s, notif=None, t=1):
    d = ImageDraw.Draw(im, "RGBA")
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([x - 120 * s, y - 160 * s, x + 120 * s, y + 160 * s], fill=(120, 200, 255, 90))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle([x - 45 * s, y - 80 * s, x + 45 * s, y + 80 * s], int(14 * s), fill=(20, 20, 25))
    d.rounded_rectangle([x - 38 * s, y - 70 * s, x + 38 * s, y + 70 * s], int(10 * s), fill=(150, 210, 255))
    if notif and t > 0:
        sc = pop(min(1, t / .3))
        nw, nh = 600 * sc, 130 * sc; nx, ny = W / 2 - nw / 2, 1470
        d.rounded_rectangle([nx, ny, nx + nw, ny + nh], int(30 * sc), fill=(255, 255, 255, 245), outline=(0, 0, 0), width=4)
        if sc > .6:
            d.text((nx + 30, ny + 40 * sc), "NOUVEAU MESSAGE", font=F(int(26 * sc), "Bold"), fill=(120, 120, 130), anchor="lm")
            d.text((nx + 30, ny + 90 * sc), notif, font=F(int(44 * sc)), fill=(20, 20, 25), anchor="lm")
            heart(d, nx + nw - 60 * sc, ny + 70 * sc, 26 * sc)

def barbell(im, cx, y, s, plates):
    d = ImageDraw.Draw(im)
    d.rectangle([cx - 380 * s, y - 10 * s, cx + 380 * s, y + 10 * s], fill=(190, 190, 200))
    for sx in (-1, 1):
        for i in range(plates):
            x = cx + sx * (300 * s + i * 30 * s); r = (60 + 30 * plates) * s
            d.rounded_rectangle([x - 13 * s, y - r, x + 13 * s, y + r], int(8 * s), fill=(25, 25, 25), outline=(200, 40, 40), width=4)

def week_card(im, n, t):
    if t <= 0: return
    d = ImageDraw.Draw(im); sc = pop(min(1, t / .2))
    w, h = 360 * sc, 150 * sc
    d.rounded_rectangle([W / 2 - w / 2, 1660 - h / 2, W / 2 + w / 2, 1660 + h / 2], int(30 * sc), fill=(255, 70, 40), outline="white", width=6)
    if sc > .5: d.text((W / 2, 1660), f"SEMAINE {n}", font=F(int(64 * sc)), fill="white", anchor="mm")

def bouquet(d, x, y, s):
    d.polygon([(x - 40 * s, y), (x + 40 * s, y), (x, y + 160 * s)], fill=(60, 150, 80))
    for i, c in enumerate([(230, 40, 80), (255, 200, 60), (240, 90, 160), (230, 40, 80), (255, 140, 60)]):
        a = -2.6 + i * .5; fx, fy = x + 60 * s * math.cos(a), y + 50 * s * math.sin(a) - 10 * s
        d.ellipse([fx - 32 * s, fy - 32 * s, fx + 32 * s, fy + 32 * s], fill=c)

def progress_bar(im, T): ImageDraw.Draw(im).rectangle([0, H - 14, W * T / DUR, H], fill=(255, 70, 40))
def vignette_red(im, a):
    if a > 0: im.alpha_composite(Image.new("RGBA", (W, H), (180, 0, 0, int(90 * a))))

# ------------------------------------------------------------------ scènes
def scene(name, t, T):
    if name == "hook":
        im = HOME.copy().convert("RGBA")
        wob = math.sin(t * 14) * 6
        malik(im, 540, 900 + wob, 1.2, "sad" if t < 2 else "panic", 0, 0, "flex", blinkv(T), sweat=True)
        caption(im, "Il s'est mis au sport", 320, t - .1, 80)
        caption(im, "pour plaire à sa femme…", 420, t - .5, 70, hl=(255, 230, 60))
        caption(im, "sans savoir QUI l'attendait à la salle", 1700, t - 1.6, 66, hl=(255, 80, 80))
        return camera(im, 1 + .05 * t, 540, 1000)
    if name == "home1":
        im = HOME.copy().convert("RGBA")
        sarah(im, 760, 900, .95, "smug", talkv(t - .3) if t < 3.2 else 0, "phone", blinkv(T))
        phone(im, 836, 1140, .95)
        malik(im, 300, 940, .95, "happy" if t < 3.2 else "sad", 0, 0, "flex" if t < 3.2 else "down", blinkv(T + .7))
        bubble(im, "T'es mignon chéri… mais t'es TROP MAIGRE.", 620, 400, 760, 770, t - .3, name="SARAH", ncol=C_SARAH)
        if t > 3.4: bubble(im, "…ah.", 280, 680, 300, 820, t - 3.4, name="MALIK", ncol=C_MALIK, size=70)
        return im
    if name == "home2":
        im = HOME.copy().convert("RGBA")
        malik(im, 300, 940, .95, "angry", talkv(t - .2) if t < 2.6 else 0, 0, "point", blinkv(T))
        sarah(im, 760, 900, .95, "smug" if t < 2.8 else "love", talkv(t - 2.9) if 2.9 < t < 4.6 else 0, "phone", blinkv(T))
        phone(im, 836, 1140, .95, notif="Tony (salle)" if t > 4.3 else None, t=t - 4.3)
        bubble(im, "Je m'inscris à la salle. Dans 3 mois, tu me reconnaîtras plus.", 450, 420, 300, 800, t - .2, name="MALIK", ncol=C_MALIK, size=54)
        if t < 4.3: bubble(im, "Vas-y mon cœur… prends ton temps.", 660, 1660, 760, 1250, t - 2.9, name="SARAH", ncol=C_SARAH, size=54)
        return im
    if name == "gym1":
        im = GYM.copy().convert("RGBA")
        k = ease(t / .6)
        tony(im, 1300 - 520 * k, 860, .85, "smug", talkv(t - .6) if t < 3.4 or t > 5.0 else 0, "down", blinkv(T))
        malik(im, 280, 960, .85, "shock" if t < 3.6 else "happy", talkv(t - 3.6) if 3.6 < t < 5 else 0, 0, "down", blinkv(T + .3))
        if t < 5.0:
            bubble(im, "Bienvenue à l'IRON PALACE. Moi c'est Tony, le gérant.", 620, 430, 780, 720, t - .6, name="TONY", ncol=C_TONY, size=52)
            bubble(im, "Je veux devenir fort… pour ma femme.", 400, 1680, 280, 1330, t - 3.6, name="MALIK", ncol=C_MALIK, size=52)
        else:
            bubble(im, "Ta femme ? …Elle a de la chance.", 620, 430, 780, 720, t - 5.0, name="TONY", ncol=C_TONY, size=56)
        return im
    if name in ("train1", "train2"):
        im = GYM.copy().convert("RGBA")
        base = 0 if name == "train1" else .5
        p = base + .5 * ease(t / (7.5 if name == "train1" else 5.0))
        if name == "train2" and t > 5.0: p = 1
        lf = .25 + .75 * abs(math.sin(t * 3.2)) if p < 1 else 1
        malik(im, 540, 960, 1.0, "panic" if p < .3 else ("angry" if p < .9 else "happy"), 0, p, "lift", blinkv(T), sweat=p < .9, lift=lf)
        barbell(im, 540, 960 + 115 - 170 * lf, 1.0, 1 + int(p * 4))
        weeks = 1 + int((p) * 11.99)
        week_card(im, weeks, 1)
        if name == "train1": caption(im, "Tous les jours. Sans exception.", 360, t - .2, 60, fill=(255, 230, 60))
        else:
            if t < 4.6: caption(im, "Plus fort. Plus lourd.", 360, t - .2, 76, fill=(255, 230, 60))
            else:
                sparkles(im, T, 540, 900, rad=380)
                caption(im, "MALIK 2.0", 360, t - 4.6, 140, fill=(255, 70, 40))
        return camera(im, 1.03 + .02 * math.sin(t * 6.4), 540, 950, shake=2 if p < .5 else 0)
    if name == "phone":
        im = GYM.copy().convert("RGBA")
        lf = .25 + .75 * abs(math.sin(t * 3))
        malik(im, 240, 1060, .7, "angry", 0, .5, "lift", blinkv(T), sweat=True, lift=lf)
        barbell(im, 240, 1060 + (115 - 170 * lf) * .7, .7, 3)
        tony(im, 760, 860, .9, "smug" if t < 1.0 else "love", talkv(t - 3.0) if t > 3.0 else 0, "phone", blinkv(T))
        phone(im, 840, 1080, .9, notif="Sarah" if .8 < t < 3.0 else None, t=t - .8)
        caption(im, "Chaque fois que Malik s'entraînait…", 330, t - .1, 50)
        if t > 1.6: caption(im, "…Tony disparaissait.", 430, t - 1.6, 64, fill=(255, 80, 80))
        if t > 3.0: bubble(im, "Continue tes séries, champion… J'ai un RDV important.", 640, 1660, 760, 1350, t - 3.0, name="TONY", ncol=C_TONY, size=50)
        return im
    if name == "door":
        im = DOOR.copy().convert("RGBA")
        k = ease(t / .8)
        malik(im, 540, 1020 - 40 * (1 - k), 1.0, "happy", talkv(t - 2.4) if t > 2.4 else 0, 1, "flowers", blinkv(T),)
        bouquet(ImageDraw.Draw(im), 560, 1260, 1.2)
        caption(im, "3 mois plus tard, il rentre plus tôt", 250, t - .1, 50)
        caption(im, "pour lui faire la surprise…", 340, t - .6, 56, fill=(255, 230, 60))
        if t > 2.4: bubble(im, "SURPRISE mon amour !", 540, 1700, 540, 1450, t - 2.4, name="MALIK", ncol=C_MALIK, size=64)
        return camera(im, 1 + .05 * t, 540, 1000)
    if name == "caught":
        im = HOME_N.copy().convert("RGBA")
        sarah(im, 720, 960, .85, "shock", talkv(t - 1.4) if 1.4 < t < 3.6 else 0, "down", False)
        tony(im, 360, 900, .85, "shock", talkv(t - 4.0) if t > 4.0 else 0, "down", False, sweat=True)
        d = ImageDraw.Draw(im)
        heart(d, 540, 760, 50 * (1 - ease(t / .6)) + 1)
        flash(im, max(0, 1 - t * 2.5))
        if t < .9: caption(im, "…", 400, t, 160)
        bubble(im, "MALIK ?! C'est pas ce que tu crois !", 640, 420, 720, 780, t - 1.4, name="SARAH", ncol=C_SARAH, size=56)
        if t > 4.0: bubble(im, "Attends… C'EST TOI son mari ?!", 400, 1660, 360, 1330, t - 4.0, name="TONY", ncol=C_TONY, size=56)
        vignette_red(im, .6)
        return camera(im, 1, shake=14 if t < .5 else 0)
    if name == "mic":
        im = HOME_N.copy().convert("RGBA")
        malik(im, 540, 900, 1.1, "neutral" if t < 4.2 else "smug", talkv(t - .4) if .4 < t < 3.8 or 4.4 < t < 7.4 else 0, 1, "down", blinkv(T))
        if t < 1.2: bouquet(ImageDraw.Draw(im), 560, 1240 + 500 * ease(t / 1.2), 1.1)
        bubble(im, "Merci Tony. Grâce à toi, j'ai pris 15 kilos de muscle.", 540, 420, 540, 760, t - .4, name="MALIK", ncol=C_MALIK, size=52)
        if t > 4.2:
            bubble(im, "Et la salle m'a appris un truc, Sarah : il faut savoir lâcher le POIDS MORT.", 540, 1640, 540, 1300, t - 4.2, name="MALIK", ncol=C_MALIK, size=50)
        return camera(im, 1 + .08 * ease(t / 8), 540, 950)
    if name == "end":
        im = HOME_N.copy().convert("RGBA")
        k = ease((t - 2.4) / 1.6)
        tony(im, 760, 920, .8, "panic", talkv(t - .2) if t < 1.6 else 0, "down", blinkv(T), sweat=True)
        malik(im, 300 - 600 * k, 960, .95, "smug", talkv(t - 1.6) if 1.6 < t < 2.4 else 0, 1, "down", blinkv(T))
        bubble(im, "…Et ton abonnement ?", 700, 420, 760, 790, t - .2, name="TONY", ncol=C_TONY, size=58)
        if t > 1.6: bubble(im, "RÉSILIÉ.", 330, 700, 300, 830, t - 1.6, name="MALIK", ncol=C_MALIK, size=96)
        if t > 3.4:
            im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(150 * ease((t - 3.4) / .6)))))
            caption(im, "PARTIE 2 :", 820, t - 3.6, 110, fill=(255, 255, 255))
            caption(im, "LA VENGEANCE", 950, t - 3.9, 120, fill=(255, 70, 40))
            caption(im, "Abonne-toi pour la suite", 1660, t - 4.4, 64)
        return im

def render_frames():
    for f in range(int(DUR * FPS)):
        T = f / FPS
        for s, e, name in SCENES:
            if s <= T < e: break
        im = scene(name, T - s, T)
        if T - s < .08 and f: flash(im, .35)
        progress_bar(im, T)
        im.convert("RGB").save(os.path.join(FRAMES, f"{f:05d}.jpg"), quality=90)

# ------------------------------------------------------------------ audio
def render_audio(path):
    n = int(SR * DUR); buf = np.zeros(n); rng = np.random.default_rng(7)
    def kick(v=1):
        t = np.arange(int(SR * .25)) / SR
        return v * .9 * np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    def hat(): x = rng.standard_normal(int(SR * .05)); return .1 * x * np.exp(-np.arange(len(x)) / SR * 80)
    def snare(): x = rng.standard_normal(int(SR * .18)); return .3 * x * np.exp(-np.arange(len(x)) / SR * 22)
    def pad(freqs, d, v=.06):
        t = np.arange(int(SR * d)) / SR
        return sum(v * np.sin(2 * np.pi * f * t) for f in freqs) * np.minimum(1, t * 6) * np.exp(-t * .5)
    def music(a, b, bpm, chords, drums=True, v=1.0):
        beat = 60 / bpm; t0, i = a, 0
        while t0 < b - .05:
            if drums:
                mix(buf, kick(v), t0); mix(buf, hat() * v, t0 + beat / 2)
                if i % 2: mix(buf, snare() * v, t0)
            if i % 4 == 0: mix(buf, pad(chords[(i // 4) % len(chords)], min(beat * 4, b - t0), .06 * v), t0)
            t0 += beat; i += 1
    minor = [(220, 261.6, 329.6), (174.6, 220, 261.6), (130.8, 164.8, 196), (196, 246.9, 293.7)]
    hype = [(164.8, 196, 246.9), (130.8, 164.8, 196), (146.8, 174.6, 220), (123.5, 155.6, 185)]
    music(0, 16.5, 92, minor, drums=True, v=.7)          # chez eux, mélancolique
    music(16.5, 44.0, 128, hype, drums=True, v=1.0)      # salle : hype
    music(44.0, 48.5, 92, [(261.6, 329.6, 392)], drums=False, v=1.2)  # surprise, doux
    music(63.5, 67.4, 128, hype, drums=True, v=1.0)      # sortie triomphale
    def whoosh(d=.4):
        x = rng.standard_normal(int(SR * d)); env = np.sin(np.linspace(0, np.pi, len(x)))
        return .3 * np.convolve(x, np.ones(30) / 30, "same") * env
    for s, _, _ in SCENES[1:]: mix(buf, whoosh(), s - .2)
    for at in (14.8, 31.8): mix(buf, tone(1318, .12, .3) + 0, at); mix(buf, tone(1760, .2, .3), at + .12)  # notifs
    for k in range(40): mix(buf, kick(.35), 23.5 + k * .47 * (1 if k < 30 else .8)) if 23.5 + k * .47 < 44 else None  # fonte qui tombe
    for k in range(10): mix(buf, tone(1200 + 90 * k, .25, .16), 42.1 + k * .07)  # sparkle MALIK 2.0
    for k in range(3): mix(buf, kick(1.2), 46.2 + k * .25)  # toc toc toc / porte
    t = np.arange(int(SR * .5)) / SR  # scratch
    mix(buf, .55 * np.sin(2 * np.pi * (900 * np.exp(-t * 6)) * t) * (rng.standard_normal(len(t)) * .3 + .7), 48.45)
    t = np.arange(int(SR * 15)) / SR  # drone tendu
    mix(buf, (.22 * np.sin(2 * np.pi * 55 * t) + .1 * np.sin(2 * np.pi * 58.3 * t)) * np.minimum(1, t / 2) * np.minimum(1, (15 - t) / 1), 48.8)
    mix(buf, kick(1.5), 55.6)  # bouquet qui tombe
    mix(buf, kick(1.6), 65.1); mix(buf, whoosh(.6), 65.0)  # « RÉSILIÉ »
    t = np.arange(int(SR * 2.6)) / SR
    mix(buf, .25 * np.sin(2 * np.pi * 73.4 * t) * np.exp(-t * .8), 67.4)  # boom final
    buf = buf / max(1e-6, np.abs(buf).max()) * .9
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    only = sys.argv[1:]  # ex: python3 render.py 30 400  -> n'écrit que ces images (aperçu)
    if only:
        for f in map(int, only):
            T = f / FPS
            for s, e, name in SCENES:
                if s <= T < e: break
            im = scene(name, T - s, T); progress_bar(im, T)
            im.convert("RGB").save(os.path.join(FRAMES, f"{f:05d}.jpg"), quality=90)
        sys.exit()
    render_frames()
    wav = os.path.join(OUT, "audio.wav"); render_audio(wav)
    mp4 = os.path.join(OUT, "salle_de_sport_short.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(FRAMES, "%05d.jpg"),
                    "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("OK", mp4)

"""Étapes 3 à 5 — animation 2D (cairo), sous-titres karaoké, bruitages, export MP4.

Lit build/timings.json + build/lines/*.wav (produits par voix.py).
"""
import json
import math
import os
import random
import re
import subprocess
import sys
import wave

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from scenario_data import LINES, TAIL

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(os.path.dirname(ROOT), "video_finale.mp4")
W, H, FPS, SR = 1080, 1920, 30, 44100
FY = 1250                    # ligne du sol (monde)
ANCHOR = (540, 900)          # point écran où la caméra centre sa cible
SUB_Y = 1130                 # centre vertical des sous-titres (≈ 59 % de la hauteur)
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
TAU = math.tau

# =============================================================== timeline
TM = json.load(open(os.path.join(BUILD, "timings.json")))
S, E = [], []
t = 0.0
for ln, m in zip(LINES, TM["lines"]):
    t += ln["gap"]
    S.append(t)
    t += m["dur"]
    E.append(t)
TOTAL = t + TAIL
NF = int(math.ceil(TOTAL * FPS))

T_BITE = E[4] + 0.18
T_TRANS = E[5] + 0.20            # whoosh atelier -> salon (0,4 s)
T_SALON = T_TRANS + 0.20
T_DROP = E[6] + 0.05
T_ZAP = E[6] + 0.55
T_WALK0, T_WALK1 = S[8], E[8]
T_HUG = E[9] + 0.10
T_BOING = E[9] + 0.55
T_LAND = S[10] - 0.02
T_STOP = S[12] - 1.05
T_RED = S[12] - 0.65
T_SPARK = E[16] + 0.15
T_RIP = S[17] - 0.40


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x):
    x = clamp(x)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def hexc(h, a=1.0):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def speaking(i, t):
    return S[i] <= t <= E[i]


# =============================================================== audio : enveloppes bouche
def read_wav(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32767


VOICE = [read_wav(os.path.join(BUILD, "lines", f"{i:02d}.wav")) for i in range(len(LINES))]
MOUTH = {c: np.zeros(NF) for c in ("BOULON", "GISELE", "ASPI")}
for i, (ln, x) in enumerate(zip(LINES, VOICE)):
    win = SR // FPS
    nfr = len(x) // win + 1
    rms = np.array([np.sqrt(np.mean(x[k * win:(k + 1) * win] ** 2) + 1e-12) for k in range(nfr)])
    ref = np.percentile(rms, 90) + 1e-6
    env = np.clip(rms / ref, 0, 1) ** 0.7
    f0 = int(round(S[i] * FPS))
    for k, v in enumerate(env):
        if 0 <= f0 + k < NF:
            MOUTH[ln["who"]][f0 + k] = max(MOUTH[ln["who"]][f0 + k], v)
for c in MOUTH:  # lissage léger (attaque rapide, relâche douce)
    m = MOUTH[c]
    for k in range(1, NF):
        if m[k] < m[k - 1]:
            m[k] = max(m[k], m[k - 1] * 0.55)


def mouth(c, t):
    return float(MOUTH[c][clamp(int(t * FPS), 0, NF - 1)])


# =============================================================== primitives cairo
def ellipse(ctx, cx, cy, rx, ry):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -TAU / 4, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, TAU / 4)
    ctx.arc(x + r, y + h - r, r, TAU / 4, TAU / 2)
    ctx.arc(x + r, y + r, r, TAU / 2, 3 * TAU / 4)
    ctx.close_path()


def fs(ctx, fill, stroke=None, lw=7):
    ctx.set_source_rgba(*hexc(fill) if isinstance(fill, str) else fill)
    if stroke:
        ctx.fill_preserve()
        ctx.set_source_rgba(*hexc(stroke) if isinstance(stroke, str) else stroke)
        ctx.set_line_width(lw)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke()
    else:
        ctx.fill()


def line(ctx, pts, col, lw, cap=cairo.LINE_CAP_ROUND):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.set_source_rgba(*hexc(col) if isinstance(col, str) else col)
    ctx.set_line_width(lw)
    ctx.set_line_cap(cap)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def glow(ctx, cx, cy, r, col, a=0.5):
    g = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
    c = hexc(col)
    g.add_color_stop_rgba(0, c[0], c[1], c[2], a)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
    ctx.set_source(g)
    ctx.arc(cx, cy, r, 0, TAU)
    ctx.fill()


def star(ctx, cx, cy, r, rot, col):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    ctx.move_to(0, -r)
    for k in range(1, 8):
        rr = r if k % 2 == 0 else r * 0.32
        a = k * TAU / 8
        ctx.line_to(rr * math.sin(a), -rr * math.cos(a))
    ctx.close_path()
    ctx.restore()
    fs(ctx, col)


def gear(ctx, cx, cy, r, rot, col, teeth=10):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    ctx.new_path()
    for k in range(teeth * 2):
        a0 = k * TAU / (teeth * 2)
        a1 = (k + 1) * TAU / (teeth * 2)
        rr = r if k % 2 == 0 else r * 0.8
        ctx.arc(0, 0, rr, a0, a1)
    ctx.close_path()
    ctx.restore()
    fs(ctx, col, "#1d2433", 4)
    ellipse(ctx, cx, cy, r * 0.3, r * 0.3)
    fs(ctx, "#1d2433")


def blink(t, off):
    p = (t + off) % 3.1
    return 1.0 if p < 0.11 else 0.0


# =============================================================== décors
def draw_atelier(ctx, t):
    g = cairo.LinearGradient(0, -200, 0, FY)
    g.add_color_stop_rgb(0, *hexc("#1b2440")[:3])
    g.add_color_stop_rgb(1, *hexc("#34507a")[:3])
    ctx.set_source(g)
    ctx.rectangle(-700, -900, 2500, FY + 900)
    ctx.fill()
    # fenêtre de nuit
    rrect(ctx, 650, 230, 330, 340, 20)
    fs(ctx, "#0c1630", "#6b4b33", 18)
    ellipse(ctx, 890, 320, 42, 42)
    fs(ctx, "#fff3c4")
    glow(ctx, 890, 320, 110, "#fff3c4", 0.25)
    rnd = random.Random(3)
    for _ in range(14):
        x, y = rnd.uniform(670, 960), rnd.uniform(250, 550)
        tw = 0.5 + 0.5 * math.sin(t * 3 + x)
        ellipse(ctx, x, y, 3 + 2 * tw, 3 + 2 * tw)
        fs(ctx, (1, 1, 0.85, 0.5 + 0.5 * tw))
    line(ctx, [(815, 230), (815, 570)], "#6b4b33", 12)
    line(ctx, [(650, 400), (980, 400)], "#6b4b33", 12)
    # panneau à outils
    rrect(ctx, 60, 300, 500, 360, 16)
    fs(ctx, "#b07a45", "#5a3a1f", 8)
    for yy in range(330, 650, 40):
        for xx in range(90, 540, 40):
            ellipse(ctx, xx, yy, 4, 4)
            fs(ctx, "#7a5130")
    # clé
    ctx.save()
    ctx.translate(170, 480)
    ctx.rotate(-0.5 + 0.03 * math.sin(t * 2))
    rrect(ctx, -14, -100, 28, 190, 12)
    fs(ctx, "#9aa7b8", "#2a3140", 6)
    ellipse(ctx, 0, -110, 40, 40)
    fs(ctx, "#9aa7b8", "#2a3140", 6)
    rrect(ctx, -12, -160, 24, 50, 4)
    fs(ctx, "#b07a45")
    ctx.restore()
    # marteau
    ctx.save()
    ctx.translate(320, 470)
    ctx.rotate(0.25 + 0.03 * math.sin(t * 2.3 + 1))
    rrect(ctx, -12, -60, 24, 200, 10)
    fs(ctx, "#d49a5a", "#5a3a1f", 6)
    rrect(ctx, -60, -100, 120, 50, 10)
    fs(ctx, "#6d7787", "#2a3140", 6)
    ctx.restore()
    # tournevis
    ctx.save()
    ctx.translate(460, 470)
    ctx.rotate(-0.15)
    rrect(ctx, -20, -110, 40, 90, 16)
    fs(ctx, "#e74c3c", "#5a1a14", 6)
    rrect(ctx, -6, -25, 12, 140, 4)
    fs(ctx, "#c0c8d4", "#2a3140", 4)
    ctx.restore()
    # étagère + engrenages qui tournent
    rrect(ctx, 640, 760, 400, 22, 6)
    fs(ctx, "#6b4b33", "#3a2616", 5)
    gear(ctx, 720, 705, 55, t * 0.8, "#e0a93b")
    gear(ctx, 812, 718, 42, -t * 1.05 + 0.2, "#c96f3b")
    gear(ctx, 940, 700, 60, t * 0.6, "#8fa3b8")
    # sol
    ctx.rectangle(-700, FY, 2500, 1600)
    fs(ctx, "#8a5a3b")
    for k in range(9):
        y = FY + 30 + k * k * 9 + k * 40
        line(ctx, [(-700, y), (1800, y)], "#6e4529", 5)
    for k in range(-6, 14):
        x0 = 540 + k * 130
        line(ctx, [(540 + (x0 - 540) * 0.6, FY), (540 + (x0 - 540) * 2.2, FY + 900)], "#7a4d31", 4)
    rrect(ctx, -700, FY - 18, 2500, 24, 4)
    fs(ctx, "#4a3020")
    # fauteuil de Gisèle (dossier)
    armchair_back(ctx, 760, FY + 20)


def armchair_back(ctx, x, y):
    rrect(ctx, x - 160, y - 590, 320, 460, 70)
    fs(ctx, "#c0392b", "#5e1a14", 8)
    rrect(ctx, x - 120, y - 540, 240, 330, 50)
    fs(ctx, "#a93226")
    rrect(ctx, x - 175, y - 220, 350, 120, 30)
    fs(ctx, "#c0392b", "#5e1a14", 8)
    for dx in (-140, 140):
        rrect(ctx, x + dx - 12, y - 110, 24, 110, 6)
        fs(ctx, "#5e1a14")


def armchair_front(ctx, x, y):
    for dx in (-190, 140):
        rrect(ctx, x + dx, y - 330, 50, 230, 25)
        fs(ctx, "#cd4a3b", "#5e1a14", 8)


def draw_salon(ctx, t):
    ctx.rectangle(-700, -900, 2500, FY + 900)
    fs(ctx, "#f6c28b")
    for k in range(-10, 30):
        x = k * 80
        ctx.rectangle(x, -900, 30, FY + 900)
        fs(ctx, "#f0b27a")
    # tableau
    rrect(ctx, 120, 330, 300, 230, 10)
    fs(ctx, "#c9932e", "#7a5518", 8)
    ctx.rectangle(145, 355, 250, 180)
    fs(ctx, "#8fd3f4")
    ellipse(ctx, 340, 400, 26, 26)
    fs(ctx, "#ffd43b")
    ellipse(ctx, 230, 560, 160, 90)
    fs(ctx, "#6abf69")
    ctx.rectangle(120, 535, 300, 30)
    fs(ctx, "#c9932e")
    # fenêtre + rideaux
    rrect(ctx, 650, 260, 300, 360, 16)
    fs(ctx, "#ff9f68", "#ffffff", 14)
    g = cairo.LinearGradient(0, 260, 0, 620)
    g.add_color_stop_rgb(0, *hexc("#5b6bd6")[:3])
    g.add_color_stop_rgb(1, *hexc("#ff9f68")[:3])
    ctx.set_source(g)
    ctx.rectangle(657, 267, 286, 346)
    ctx.fill()
    line(ctx, [(800, 260), (800, 620)], "#ffffff", 12)
    sway = 6 * math.sin(t * 1.4)
    for x0, sgn in ((630, 1), (970, -1)):
        ctx.move_to(x0 - 40 * sgn, 230)
        ctx.line_to(x0 + 70 * sgn, 230)
        ctx.curve_to(x0 + 40 * sgn + sway, 400, x0 + 60 * sgn - sway, 560, x0 + 30 * sgn + sway, 690)
        ctx.line_to(x0 - 40 * sgn, 690)
        ctx.close_path()
        fs(ctx, "#d9534f", "#8e2b28", 6)
    rrect(ctx, 580, 215, 440, 26, 12)
    fs(ctx, "#8e2b28")
    # plante
    for k in range(6):
        a = -1.2 + k * 0.48 + 0.06 * math.sin(t * 1.7 + k)
        ctx.save()
        ctx.translate(70, 1080)
        ctx.rotate(a)
        ellipse(ctx, 0, -110, 26, 95)
        ctx.restore()
        fs(ctx, "#3fa34d", "#1f5e2a", 5)
    rrect(ctx, 10, 1060, 120, 150, 18)
    fs(ctx, "#c0603a", "#6b2f18", 7)
    # sol + tapis
    ctx.rectangle(-700, FY, 2500, 1600)
    fs(ctx, "#b5835a")
    for k in range(9):
        y = FY + 30 + k * k * 9 + k * 40
        line(ctx, [(-700, y), (1800, y)], "#a0704a", 5)
    ellipse(ctx, 540, FY + 190, 470, 120)
    fs(ctx, "#d95d7a", "#9c3550", 8)
    ellipse(ctx, 540, FY + 190, 360, 80)
    fs(ctx, "#f28ca0")
    rrect(ctx, -700, FY - 18, 2500, 24, 4)
    fs(ctx, "#ffffff")
    # lampe
    line(ctx, [(1010, FY + 10), (1010, 760)], "#3a3a3a", 10)
    glow(ctx, 1010, 720, 200, "#ffe08a", 0.35 + 0.05 * math.sin(t * 5))
    ctx.move_to(940, 760)
    ctx.line_to(1080, 760)
    ctx.line_to(1050, 660)
    ctx.line_to(970, 660)
    ctx.close_path()
    fs(ctx, "#ffe08a", "#b38b2e", 6)
    # canapé (dossier)
    sofa_back(ctx, 760, FY + 20)


def sofa_back(ctx, x, y):
    rrect(ctx, x - 300, y - 560, 600, 430, 80)
    fs(ctx, "#2e9e8f", "#16544b", 8)
    rrect(ctx, x - 270, y - 230, 540, 130, 30)
    fs(ctx, "#36b3a2", "#16544b", 8)
    for dx in (-250, 250):
        rrect(ctx, x + dx - 12, y - 110, 24, 110, 6)
        fs(ctx, "#16544b")


def sofa_front(ctx, x, y):
    for dx in (-340, 260):
        rrect(ctx, x + dx, y - 360, 80, 260, 36)
        fs(ctx, "#36b3a2", "#16544b", 8)


# =============================================================== personnages
def draw_boulon(ctx, x, y, s, st, t):
    m = st.get("mouth", 0)
    # ombre
    ellipse(ctx, x, st.get("ground", y) + 4, 95 * s, 16 * s)
    fs(ctx, (0, 0, 0, 0.25))
    sq = st.get("squash", 0)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(st.get("tilt", 0))
    ctx.scale(s * (1 - sq * 0.5), s * (1 + sq))
    body, dark, light = "#5ec8f2", "#1b3a57", "#bfefff"
    # jambes / pieds
    for dx in (-36, 36):
        rrect(ctx, dx - 13, -70, 26, 66, 10)
        fs(ctx, "#3a9cc9", dark, 6)
        ellipse(ctx, dx * 1.15, -8, 32, 14)
        fs(ctx, dark)
    # bras gauche
    sw = math.sin(t * 4) * 10
    line(ctx, [(-80, -170), (-128, -128 + sw)], dark, 20)
    line(ctx, [(-80, -170), (-128, -128 + sw)], "#3a9cc9", 11)
    ellipse(ctx, -132, -122 + sw, 20, 20)
    fs(ctx, body, dark, 6)
    # corps
    rrect(ctx, -88, -210, 176, 160, 44)
    fs(ctx, body, dark, 8)
    rrect(ctx, -48, -180, 96, 80, 16)
    fs(ctx, light, dark, 5)
    line(ctx, [(-28, -158), (28, -158)], dark, 7)
    line(ctx, [(-28, -138), (28, -138)], dark, 7)
    ellipse(ctx, -20, -115, 8, 8)
    fs(ctx, "#f25f5c")
    ellipse(ctx, 6, -115, 8, 8)
    fs(ctx, "#ffd43b")
    # bras droit (+ baguette)
    au = st.get("arm_up", 0)
    hx, hy = lerp(128, 150, au), lerp(-128, -250, au)
    if st.get("bite_arm", 0) > 0:
        k = st["bite_arm"]
        hx, hy = lerp(hx, 60, k), lerp(hy, -250, k)
    line(ctx, [(80, -170), (hx, hy)], dark, 20)
    line(ctx, [(80, -170), (hx, hy)], "#3a9cc9", 11)
    # cou + tête
    rrect(ctx, -22, -228, 44, 26, 6)
    fs(ctx, "#3a9cc9", dark, 6)
    ht = st.get("head_tilt", 0)
    ctx.save()
    ctx.translate(0, -222)
    ctx.rotate(ht)
    ctx.translate(0, 222)
    for dx in (-140, 140):
        ellipse(ctx, dx, -312, 26, 26)
        fs(ctx, "#f25f5c", dark, 6)
    rrect(ctx, -132, -405, 264, 190, 62)
    fs(ctx, body, dark, 8)
    # antenne
    asw = 14 * math.sin(t * 6) * (0.4 + st.get("antenna_kick", 0))
    line(ctx, [(0, -404), (asw * 0.5, -440), (asw, -478)], dark, 7)
    glow(ctx, asw, -478, 44, "#ff5d5d", 0.45)
    ellipse(ctx, asw, -478, 17, 17)
    fs(ctx, "#f25f5c", dark, 5)
    # écran visage
    rrect(ctx, -104, -385, 208, 152, 42)
    fs(ctx, "#12263a")
    gc = "#7fffd4"
    eyes = st.get("eyes", "normal")
    bl = st.get("blink", 0)
    lx = st.get("look", 0) * 10
    gl = st.get("glitch", 0)
    for side, ex in ((-1, -48), (1, 48)):
        ex += lx
        ey = -322
        if gl > 0:
            line(ctx, [(ex - 18, ey - 18), (ex + 18, ey + 18)], "#ff6b6b", 9)
            line(ctx, [(ex + 18, ey - 18), (ex - 18, ey + 18)], "#ff6b6b", 9)
            continue
        glow(ctx, ex, ey, 50, gc, 0.25)
        if eyes == "happy":
            ctx.arc(ex, ey + 10, 22, TAU / 2, TAU)
            ctx.set_source_rgba(*hexc(gc))
            ctx.set_line_width(10)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
        elif eyes == "shock":
            ellipse(ctx, ex, ey, 31, 36)
            ctx.set_source_rgba(*hexc(gc))
            ctx.set_line_width(8)
            ctx.stroke()
            ellipse(ctx, ex, ey, 9, 9)
            fs(ctx, gc)
        elif eyes == "sparkle":
            star(ctx, ex, ey, 36 + 4 * math.sin(t * 9), t * 2.5 * side, "#ffe66d")
            glow(ctx, ex, ey, 60, "#ffe66d", 0.35)
        elif eyes == "dizzy":
            ctx.save()
            ctx.translate(ex, ey)
            ctx.rotate(t * 8 * side)
            ctx.move_to(0, 0)
            for k in range(1, 40):
                a = k * 0.45
                ctx.line_to(math.cos(a) * k * 0.75, math.sin(a) * k * 0.75)
            ctx.restore()
            ctx.set_source_rgba(*hexc(gc))
            ctx.set_line_width(6)
            ctx.stroke()
        else:
            ry = 32 * (1 - bl) + 3
            ellipse(ctx, ex, ey, 25, ry)
            fs(ctx, gc)
            if eyes == "sad":
                ctx.move_to(ex - 34, ey - 40 + side * 0)
                ctx.line_to(ex + 34, ey - 40)
                ctx.line_to(ex + 34 * side, ey - 6)
                ctx.close_path()
                fs(ctx, "#12263a")
                line(ctx, [(ex - 30 * side * -1, ey - 30), (ex + 30 * side * -1, ey - 46)], gc, 6)
    # bouche
    if gl > 0:
        rnd = random.Random(int(t * 30))
        for k in range(6):
            yy = -380 + rnd.uniform(0, 140)
            ctx.rectangle(-100, yy, 200, rnd.uniform(3, 10))
            fs(ctx, (0.5, 1, 0.85, 0.7))
    elif m > 0.08:
        rrect(ctx, -30, -270 - 4, 60, 8 + 34 * m, 10)
        fs(ctx, gc)
        rrect(ctx, -20, -266, 40, max(1, 22 * m), 8)
        fs(ctx, "#0b5a4a")
    elif eyes in ("happy", "sparkle"):
        ctx.arc(0, -268, 22, 0.15 * TAU / 2, TAU / 2 - 0.15 * TAU / 2)
        ctx.set_source_rgba(*hexc(gc))
        ctx.set_line_width(8)
        ctx.stroke()
    elif eyes in ("sad", "dizzy"):
        ctx.arc(0, -245, 20, TAU / 2 + 0.5, TAU - 0.5)
        ctx.set_source_rgba(*hexc(gc))
        ctx.set_line_width(8)
        ctx.stroke()
    else:
        line(ctx, [(-20, -265), (20, -265)], gc, 8)
    # moustache collée de travers
    if st.get("mustache", False):
        draw_mustache(ctx, 0, -290, 1.0, -0.2)
    ctx.restore()  # tête
    # baguette
    bg = st.get("baguette", 0)
    if bg:
        ctx.save()
        ctx.translate(hx, hy)
        ctx.rotate(-0.9 if st.get("bite_arm", 0) < 0.5 else -2.4)
        L = 230 if bg == 1 else 150
        rrect(ctx, -30, -20, L, 40, 20)
        fs(ctx, "#e3a857", "#8a5a1e", 6)
        for k in range(3):
            xx = 10 + k * (L - 40) / 3
            line(ctx, [(xx, -10), (xx + 30, 10)], "#b87a2e", 6)
        if bg == 2:
            for k, yy in enumerate((-14, 0, 14)):
                ellipse(ctx, L - 28, yy, 10, 10)
                fs(ctx, "#fbe6b8")
        ctx.restore()
    ellipse(ctx, hx, hy, 21, 21)
    fs(ctx, body, dark, 6)
    ctx.restore()


def draw_mustache(ctx, x, y, s, rot):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(s, s)
    for sgn in (-1, 1):
        ctx.move_to(0, -6)
        ctx.curve_to(sgn * 25, -22, sgn * 55, -18, sgn * 62, 2)
        ctx.curve_to(sgn * 50, -4, sgn * 38, 10, sgn * 22, 8)
        ctx.curve_to(sgn * 10, 6, 0, 4, 0, -6)
        ctx.close_path()
        fs(ctx, "#5b3a1e", "#2e1c0d", 4)
    ctx.restore()


def draw_gisele(ctx, x, y, s, st, t):
    m = st.get("mouth", 0)
    sq = st.get("squash", 0)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * (1 + sq * 0.4), s * (1 - sq))
    skin, line_c = "#ffd3b5", "#7a4b3a"
    # jambes
    for dx in (-42, 42):
        rrect(ctx, dx - 16, -190, 32, 180, 14)
        fs(ctx, "#e8c9a9", line_c, 5)
        ellipse(ctx, dx * 1.2, -12, 34, 16)
        fs(ctx, "#7a1f3d", "#3b0f1f", 5)
    # jupe + gilet
    rrect(ctx, -115, -260, 230, 90, 30)
    fs(ctx, "#4a3b78", "#241a44", 6)
    breath = 4 * math.sin(t * 2.4)
    ctx.move_to(-110, -230)
    ctx.curve_to(-120, -300, -95, -360 - breath, -60, -370 - breath)
    ctx.line_to(60, -370 - breath)
    ctx.curve_to(95, -360 - breath, 120, -300, 110, -230)
    ctx.close_path()
    fs(ctx, "#8e5bd6", "#3b2266", 7)
    line(ctx, [(0, -365), (0, -235)], "#3b2266", 5)
    for yy in (-335, -300, -265):
        ellipse(ctx, 12, yy, 6, 6)
        fs(ctx, "#ffd43b")
    # tête
    hb = st.get("head_bob", 0) + 3 * math.sin(t * 2.4)
    ctx.save()
    ctx.translate(0, hb)
    ho = st.get("head_open", 0)
    # cheveux arrière + chignon
    for dx in (-88, 88):
        ellipse(ctx, dx, -470, 36, 46)
        fs(ctx, "#cfcfdb", "#6e6e80", 6)
    if not st.get("bun_off", False):
        ellipse(ctx, 0, -572, 54, 48)
        fs(ctx, "#cfcfdb", "#6e6e80", 6)
        ctx.arc(0, -572, 34, 3.6, 5.4)
        ctx.set_source_rgba(*hexc("#9a9aae"))
        ctx.set_line_width(5)
        ctx.stroke()
    ellipse(ctx, 0, -460, 98, 98)
    fs(ctx, skin, line_c, 7)
    if ho > 0:  # trappe ouverte + ressort
        ellipse(ctx, 0, -548, 52, 15)
        fs(ctx, "#2b2b33", "#555", 4)
        L = 40 + 150 * ho + st.get("spring_wob", 0)
        pts = []
        n = 9
        for k in range(n + 1):
            yy = -548 - L * k / n
            xx = 0 if k in (0, n) else (26 if k % 2 else -26)
            pts.append((xx, yy))
        line(ctx, pts, "#3a3f4a", 13)
        line(ctx, pts, "#c5ccd6", 7)
        ellipse(ctx, 0, -548 - L, 20, 9)
        fs(ctx, "#c5ccd6", "#3a3f4a", 4)
    # frange
    ctx.arc(0, -470, 99, TAU / 2 + 0.25, TAU - 0.25)
    ctx.curve_to(60, -520, 20, -540, 0, -530)
    ctx.curve_to(-30, -545, -70, -520, -95, -490)
    ctx.close_path()
    fs(ctx, "#cfcfdb", "#6e6e80", 5)
    # joues
    for dx in (-60, 60):
        ellipse(ctx, dx, -415, 20, 13)
        fs(ctx, (1, 0.5, 0.55, 0.45))
    # yeux derrière les lunettes
    eyes = st.get("eyes", "normal")
    bl = st.get("blink", 0)
    lk = st.get("look", 0)
    for dx in (-42, 42):
        cx, cy = dx, -455
        ellipse(ctx, cx, cy, 38, 38)
        fs(ctx, (1, 1, 1, 0.9))
        pr = 8 if eyes == "shock" else 13
        ellipse(ctx, cx + lk * 14, cy + (4 if eyes == "sad" else 0), pr, pr)
        fs(ctx, "#2b1b2e")
        ellipse(ctx, cx + lk * 14 + 4, cy - 4, 4, 4)
        fs(ctx, "#ffffff")
        lid = bl
        if eyes == "bored":
            lid = max(lid, 0.5)
        if eyes == "sad":
            lid = max(lid, 0.35)
        if lid > 0:
            ctx.save()
            ellipse(ctx, cx, cy, 38, 38)
            ctx.clip()
            ctx.rectangle(cx - 40, cy - 40, 80, 80 * lid)
            fs(ctx, skin)
            line(ctx, [(cx - 40, cy - 40 + 80 * lid), (cx + 40, cy - 40 + 80 * lid)], line_c, 5)
            ctx.restore()
        ellipse(ctx, cx, cy, 40, 40)
        ctx.set_source_rgba(*hexc("#3b2266"))
        ctx.set_line_width(8)
        ctx.stroke()
        # sourcils
        if eyes in ("shock", "nervous"):
            line(ctx, [(cx - 22, cy - 62), (cx + 22, cy - 66)], "#6e6e80", 7)
        elif eyes in ("bored", "annoyed"):
            line(ctx, [(cx - 24, cy - 50 - (dx > 0) * 4), (cx + 24, cy - 50 - (dx < 0) * 4)], "#6e6e80", 7)
        elif eyes == "sad":
            line(ctx, [(cx - 22, cy - 48 - (dx > 0) * 12), (cx + 22, cy - 48 - (dx < 0) * 12)], "#6e6e80", 7)
    line(ctx, [(-4, -455), (4, -455)], "#3b2266", 7)
    # nez
    ellipse(ctx, 0, -422, 13, 11)
    fs(ctx, "#f3b393", line_c, 4)
    # bouche
    if m > 0.08:
        ellipse(ctx, 0, -385, 20, 4 + 17 * m)
        fs(ctx, "#5a1a1a", line_c, 4)
    elif eyes in ("sad",):
        ctx.arc(0, -370, 18, TAU / 2 + 0.6, TAU - 0.6)
        ctx.set_source_rgba(*hexc(line_c))
        ctx.set_line_width(6)
        ctx.stroke()
    elif eyes == "nervous":
        line(ctx, [(-20, -385), (-8, -380), (4, -388), (18, -382)], line_c, 6)
    else:
        line(ctx, [(-18, -384), (18, -384)], line_c, 6)
    # goutte de sueur
    sw = st.get("sweat", 0)
    if sw > 0:
        yy = -520 + 40 * ((t * 0.8) % 1)
        ctx.move_to(100, yy - 26)
        ctx.curve_to(112, yy - 6, 116, yy + 4, 100, yy + 8)
        ctx.curve_to(84, yy + 4, 88, yy - 6, 100, yy - 26)
        fs(ctx, (0.55, 0.85, 1, sw), "#3a7bbf", 4)
    ctx.restore()  # tête
    # bras + journal
    if st.get("paper", 0) > 0.01:
        p = st["paper"]
        py = lerp(-230, -300, p)
        rrect(ctx, -120, py - 60, 240, 150, 6)
        fs(ctx, "#f4f1ea", "#8d8a80", 5)
        rrect(ctx, -105, py - 45, 95, 60, 4)
        fs(ctx, "#c9c4b6")
        for k in range(6):
            line(ctx, [(5, py - 40 + k * 18), (105, py - 40 + k * 18)], "#a9a497", 5)
        for k in range(3):
            line(ctx, [(-105, py + 35 + k * 18), (-10, py + 35 + k * 18)], "#a9a497", 5)
        for dx in (-128, 128):
            ellipse(ctx, dx, py + 10, 22, 22)
            fs(ctx, skin, line_c, 5)
    else:
        for dx in (-70, 70):
            line(ctx, [(dx * 1.4, -340), (dx * 0.9, -250)], "#3b2266", 34)
            line(ctx, [(dx * 1.4, -340), (dx * 0.9, -250)], "#8e5bd6", 24)
            ellipse(ctx, dx * 0.85, -245, 22, 22)
            fs(ctx, skin, line_c, 5)
    ctx.restore()


def draw_aspi(ctx, x, y, s, st, t):
    m = st.get("mouth", 0)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ellipse(ctx, 0, 6, 135, 26)
    fs(ctx, (0, 0, 0, 0.25))
    # brosse latérale
    for k in range(3):
        a = st.get("brush", t * 12) + k * TAU / 3
        line(ctx, [(105, 0), (105 + 34 * math.cos(a), 0 + 10 * math.sin(a))], "#2b2b2b", 4)
    # flanc
    ctx.move_to(-125, -70)
    ctx.line_to(-125, -14)
    ctx.curve_to(-125, 14, 125, 14, 125, -14)
    ctx.line_to(125, -70)
    ctx.close_path()
    fs(ctx, "#4a5561", "#1e252c", 6)
    # bouche = fente d'aspiration
    mh = 6 + 24 * m
    rrect(ctx, -64, -16 - mh / 2, 128, mh, mh / 2)
    fs(ctx, "#0e1114", "#1e252c", 4)
    if m > 0.15:
        for k in range(5):
            xx = -40 + k * 20
            line(ctx, [(xx, -16 - mh / 2 + 5), (xx, -16 + mh / 2 - 5)], "#3a434d", 4)
    # dessus
    ellipse(ctx, 0, -70, 125, 34)
    fs(ctx, "#8795a3", "#1e252c", 6)
    ellipse(ctx, 0, -72, 78, 20)
    fs(ctx, "#6c7a89", "#4a5561", 4)
    lc = "#ff3b3b" if st.get("red", False) else "#3dff8f"
    pulse = 0.5 + 0.5 * math.sin(t * (10 if st.get("red") else 3))
    glow(ctx, 0, -76, 60 + 40 * m, lc, 0.45 + 0.3 * pulse * (0.5 + m))
    ellipse(ctx, 0, -76, 16, 8)
    fs(ctx, lc, "#1e252c", 3)
    ctx.restore()


# =============================================================== particules (déterministes)
def smoke(ctx, t, t0, dur, ox, oy, seed, n=14, big=1.0):
    rnd = random.Random(seed)
    for k in range(n):
        b = t0 + k * dur / n
        age = t - b
        if age < 0 or age > 1.4:
            continue
        vx = rnd.uniform(-60, 60)
        sgn = rnd.choice((-1, 1))
        x = ox[0 if sgn < 0 else 1] if isinstance(ox, tuple) else ox
        px = x + sgn * 30 * age + vx * age
        py = oy - 160 * age
        r = (18 + 50 * age) * big
        ellipse(ctx, px, py, r, r)
        fs(ctx, (0.55, 0.55, 0.6, 0.55 * (1 - age / 1.4)))


def sparks(ctx, t, t0, cx, cy, seed, n=14, col="#ffe66d", spread=1.0):
    age = t - t0
    if age < 0 or age > 0.45:
        return
    rnd = random.Random(seed)
    for k in range(n):
        a = rnd.uniform(0, TAU)
        sp = rnd.uniform(250, 650) * spread
        d0, d1 = sp * age, sp * age + 40 * (1 - age / 0.45)
        line(ctx, [(cx + math.cos(a) * d0, cy + math.sin(a) * d0),
                   (cx + math.cos(a) * d1, cy + math.sin(a) * d1)], col, 7)
    glow(ctx, cx, cy, 120 * (1 - age / 0.45), col, 0.6)


def oil_drops(ctx, t, t0, eyes, seed):
    rnd = random.Random(seed)
    for k in range(8):
        b = t0 + k * 0.06
        age = t - b
        if age < 0 or age > 0.7:
            continue
        ex, ey = eyes[k % 2]
        px = ex + rnd.uniform(-12, 12)
        py = ey + 30 + 500 * age * age + 60 * age
        ctx.move_to(px, py - 22)
        ctx.curve_to(px + 12, py - 2, px + 12, py + 12, px, py + 12)
        ctx.curve_to(px - 12, py + 12, px - 12, py - 2, px, py - 22)
        fs(ctx, "#111111", "#000000", 2)


def bolts(ctx, t, t0, cx, cy, seed):
    age = t - t0
    if age < 0 or age > 1.6:
        return
    rnd = random.Random(seed)
    for k in range(7):
        vx, vy = rnd.uniform(-420, 420), rnd.uniform(-1100, -700)
        px, py = cx + vx * age, cy + vy * age + 1500 * age * age
        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(age * rnd.uniform(-12, 12))
        ctx.move_to(16, 0)
        for j in range(1, 6):
            ctx.line_to(16 * math.cos(j * TAU / 6), 16 * math.sin(j * TAU / 6))
        ctx.close_path()
        ctx.restore()
        fs(ctx, "#b7c0cc", "#3a3f4a", 4)
        ellipse(ctx, px, py, 6, 6)
        fs(ctx, "#3a3f4a")


# =============================================================== caméra
def cam_keys():
    BX = 300
    k = [
        (0.0, 0.0, BX, 1050, 1.55),
        (E[0] + 0.05, 0.35, 540, 930, 1.0),
        (S[2] - 0.02, 0.15, BX + 40, 1060, 1.3),
        (S[3] - 0.05, 0.3, 700, 900, 1.25),
        (S[4] - 0.05, 0.3, BX + 30, 1040, 1.3),
        (T_BITE, 0.12, BX + 20, 1010, 1.55),
        (S[5] + 0.4, 1.5, BX + 30, 1030, 1.4),
        (T_SALON, 0.0, 540, 930, 1.0),
        (S[6], 0.4, 330, 1040, 1.3),
        (T_ZAP, 0.1, 330, 1020, 1.5),
        (S[7] - 0.05, 0.35, 720, 900, 1.25),
        (S[8] - 0.05, 0.35, 540, 960, 1.1),
        (S[9] - 0.05, 0.6, 740, 880, 1.35),
        (T_HUG, 0.3, 650, 930, 1.15),
        (T_BOING, 0.12, 770, 780, 1.55),
        (S[10] - 0.05, 0.25, 360, 1040, 1.4),
        (S[11] - 0.05, 0.4, 760, 860, 1.3),
        (T_STOP - 0.2, 1.1, 560, 1370, 1.9),
        (S[13] - 0.05, 0.25, 360, 1040, 1.35),
        (S[14] - 0.05, 0.4, 560, 1375, 2.1),
        (S[15] - 0.05, 0.3, 760, 860, 1.35),
        (S[16] - 0.05, 0.4, 560, 1380, 2.3),
        (E[16] + 0.1, 0.5, 340, 1060, 1.75),
    ]
    return k


CAM = cam_keys()
SHAKES = [
    (0.05, 10, 0.25), (S[2], 8, 0.2), (T_BITE, 16, 0.35), (T_ZAP, 28, 0.45),
    (T_BOING, 32, 0.5), (S[10], 12, 0.3), (S[12], 10, 0.3), (S[13], 8, 0.2), (T_RIP, 10, 0.25),
]


def camera(t):
    cx, cy, z = CAM[0][2:]
    for k in range(1, len(CAM)):
        t0, d, x1, y1, z1 = CAM[k]
        if t < t0:
            break
        a = 1.0 if d <= 0 else ease((t - t0) / d)
        cx, cy, z = lerp(cx, x1, a), lerp(cy, y1, a), lerp(z, z1, a)
    z *= 1 + 0.018 * math.sin(t * 0.9)
    cx += 8 * math.sin(t * 0.55)
    sx = sy = 0.0
    for t0, amp, d in SHAKES:
        if t0 <= t < t0 + d:
            k = (1 - (t - t0) / d) ** 2
            sx += amp * k * math.sin(t * 97)
            sy += amp * k * math.cos(t * 83)
    return cx, cy, z, sx, sy


# =============================================================== état des personnages
def boulon_state(t, salon):
    st = dict(mouth=mouth("BOULON", t), blink=blink(t, 0.4), mustache=True, eyes="normal")
    y = 1290
    st["ground"] = y
    if not salon:
        x = 300
        st["baguette"] = 1 if t < T_BITE else 2
        if t < E[0]:
            st["arm_up"] = 1
            st["eyes"] = "happy"
            y -= abs(math.sin(t * 7.5)) * 34
        elif t < S[2]:
            st["arm_up"] = 0.6
        elif t < E[2] + 0.2:
            st["eyes"] = "shock"
            k = (t - S[2]) / 0.45
            y -= 70 * math.sin(math.pi * clamp(k)) if k < 1 else 0
            st["arm_up"] = 0.6
        elif t < S[4]:
            st["arm_up"] = 0.4
        elif t < T_BITE - 0.15:
            st["arm_up"] = 1
            st["eyes"] = "happy"
            y -= abs(math.sin((t - S[4]) * 6)) * 20
        else:
            st["arm_up"] = 0.4
            st["bite_arm"] = clamp((t - (T_BITE - 0.15)) / 0.15) if t < T_BITE + 0.35 else clamp(1 - (t - T_BITE - 0.35) / 0.3)
            st["eyes"] = "dizzy" if t < S[5] + 1.2 else "happy"
            if S[5] <= t <= E[5]:
                st["tilt"] = 0.04 * math.sin(t * 40) * mouth("BOULON", t)
        if t >= T_BITE and t < T_BITE + 0.2:
            st["squash"] = -0.08 * math.sin((t - T_BITE) / 0.2 * math.pi)
    else:
        x = 300
        st["baguette"] = 0
        if t < S[6] + 0.3:
            st["eyes"] = "normal"
        elif t < T_ZAP:
            st["eyes"] = "sad"
        elif t < T_ZAP + 0.5:
            st["glitch"] = 1
        elif t < S[8]:
            st["eyes"] = "dizzy"
        if T_WALK0 <= t:
            k = ease((t - T_WALK0) / max(0.3, T_WALK1 - T_WALK0))
            x = lerp(300, 470, k)
            if k < 1:
                y -= abs(math.sin(t * 12)) * 14
            st["eyes"] = "happy"
        if t >= S[9]:
            st["eyes"] = "normal"
            st["look"] = 0.8
        if t >= T_HUG:
            if t < T_HUG + 0.3:
                k = (t - T_HUG) / 0.3
                x = lerp(470, 670, k)
                y = 1290 - 120 * k - 160 * math.sin(math.pi * k)
                st["eyes"] = "happy"
            elif t < T_BOING:
                x = 670 + 3 * math.sin(t * 60)
                y = 1170
                st["eyes"] = "happy"
                st["squash"] = 0.06
            elif t < T_LAND:
                k = (t - T_BOING) / (T_LAND - T_BOING)
                x = lerp(670, 360, k)
                y = lerp(1170, 1290, k) - 220 * math.sin(math.pi * k)
                st["tilt"] = -1.2 * math.sin(math.pi * k)
                st["eyes"] = "shock"
            else:
                x = 360
                st["eyes"] = "shock"
                k = t - T_LAND
                if k < 0.25:
                    st["squash"] = -0.15 * math.sin(k / 0.25 * math.pi)
        if t >= S[11] and t < S[12] - 0.6:
            st["eyes"] = "normal"
            st["look"] = 1
        if t >= S[12] - 0.6:
            st["look"] = 0.7
            st["eyes"] = "shock" if t < E[13] + 0.3 else "normal"
        if t >= T_SPARK:
            st["eyes"] = "sparkle"
            st["look"] = 0
        if t >= T_RIP:
            st["mustache"] = False
        if t >= S[17]:
            y -= abs(math.sin((t - S[17]) * 7)) * 30
        if S[13] <= t <= E[13]:
            k = (t - S[13]) / 0.4
            y -= 60 * math.sin(math.pi * clamp(k)) if k < 1 else 0
        if S[10] <= t <= E[10]:
            st["tilt"] = 0.05 * math.sin(t * 30)
    if mouth("BOULON", t) > 0.1:
        y -= 6 * mouth("BOULON", t)
    st["squash"] = st.get("squash", 0) + 0.015 * math.sin(t * 3.2)
    return x, y, st


def gisele_state(t, salon):
    st = dict(mouth=mouth("GISELE", t), blink=blink(t, 1.7), eyes="bored", paper=1.0, look=-0.6)
    if not salon:
        if S[1] <= t < S[1] + 0.6 or S[3] - 0.1 <= t <= E[3] + 0.2:
            st["paper"] = 0.4
        if t >= T_BITE:
            st["eyes"] = "normal"
            st["look"] = -1
    else:
        st["look"] = -0.8
        if t < T_ZAP:
            st["eyes"] = "bored"
        elif t < S[8]:
            st["eyes"] = "annoyed"
            st["paper"] = 0.5
        if t >= S[8]:
            st["paper"] = clamp(1 - (t - S[8]) / 0.4)
            st["eyes"] = "normal"
        if t >= S[9] - 0.1:
            st["eyes"] = "nervous"
            st["look"] = 1 if int(t * 2.5) % 2 else -0.3
            st["sweat"] = 1
        if t >= T_HUG + 0.3 and t < T_BOING:
            st["squash"] = 0.08
            st["eyes"] = "shock"
        if t >= T_BOING:
            st.pop("sweat", None)
            st["bun_off"] = True
            k = t - T_BOING
            st["head_open"] = ease_out(k / 0.25)
            st["spring_wob"] = 40 * math.exp(-2.2 * k) * math.sin(k * 22)
            st["eyes"] = "shock"
            st["look"] = -0.8
            if k < 0.3:
                st["squash"] = -0.1 * math.sin(k / 0.3 * math.pi)
        if t >= S[11] - 0.1:
            st["eyes"] = "sad"
            st["look"] = 0
        if t >= S[12] - 0.6:
            st["eyes"] = "shock"
            st["look"] = -0.9
        if t >= S[15] - 0.05 and t <= E[15] + 0.2:
            st["eyes"] = "normal"
        if t >= T_SPARK:
            st["eyes"] = "shock"
            st["look"] = -1
    return 760, 1270, st


def aspi_state(t):
    st = dict(mouth=mouth("ASPI", t), red=t >= T_RED)
    tt = t - T_SALON

    def roam(u):
        return 560 + 360 * math.sin(0.55 * u)

    if t < T_STOP:
        x = roam(tt)
    else:
        x0 = roam(T_STOP - T_SALON)
        x = lerp(x0, 560, ease_out((t - T_STOP) / 0.45))
        st["brush"] = (T_STOP * 12) + 6 * (1 - math.exp(-(t - T_STOP) * 4))
    y = 1400
    if st["mouth"] > 0.1:
        y -= 4 * st["mouth"]
    return x, y, st


# =============================================================== scène complète
def draw_world(ctx, t, salon):
    if not salon:
        draw_atelier(ctx, t)
        gx, gy, gst = gisele_state(t, False)
        draw_gisele(ctx, gx, gy, 1.0, gst, t)
        armchair_front(ctx, 760, FY + 20)
        bx, by, bst = boulon_state(t, False)
        draw_boulon(ctx, bx, by, 1.0, bst, t)
        # bruitages visuels
        if t >= T_BITE:
            mx, my = bx + 10, by - 268
            sparks(ctx, t, T_BITE, mx + 30, my, 11, n=10, col="#ffd166", spread=0.6)
            smoke(ctx, t, T_BITE + 0.05, 2.6, (bx - 140, bx + 140), by - 312, 5)
        # ampoule qui se balance (premier plan haut)
        sw = 14 * math.sin(t * 1.3)
        line(ctx, [(540, -400), (540 + sw, 150)], "#111", 5)
        glow(ctx, 540 + sw, 180, 260, "#ffe9a0", 0.28)
        ellipse(ctx, 540 + sw, 180, 28, 30)
        fs(ctx, "#fff2b8", "#a38a3a", 5)
        rrect(ctx, 528 + sw, 140, 24, 22, 4)
        fs(ctx, "#555")
        ctx.move_to(540 + sw, 190)
        ctx.line_to(140, FY + 120)
        ctx.line_to(940, FY + 120)
        ctx.close_path()
        ctx.set_source_rgba(1, 0.92, 0.6, 0.07)
        ctx.fill()
    else:
        draw_salon(ctx, t)
        gx, gy, gst = gisele_state(t, True)
        draw_gisele(ctx, gx, gy, 1.0, gst, t)
        sofa_front(ctx, 760, FY + 20)
        bx, by, bst = boulon_state(t, True)
        draw_boulon(ctx, bx, by, 1.0, bst, t)
        ax, ay, ast = aspi_state(t)
        draw_aspi(ctx, ax, ay, 1.0, ast, t)
        # larmes d'huile + court-circuit
        eyes = [(bx - 48, by - 322), (bx + 48, by - 322)]
        oil_drops(ctx, t, T_DROP, eyes, 21)
        sparks(ctx, t, T_ZAP, bx, by - 330, 31, n=18, col="#9ff7ff", spread=1.2)
        sparks(ctx, t, T_ZAP + 0.12, bx + 60, by - 420, 32, n=10, col="#ffe66d")
        smoke(ctx, t, T_ZAP + 0.1, 0.8, bx, by - 470, 7, n=6, big=0.8)
        # BOING : chignon qui s'envole + boulons
        if t >= T_BOING:
            k = t - T_BOING
            px, py = 760 + 260 * k, 1270 - 572 - 1400 * k + 1300 * k * k
            if py > -900:
                ctx.save()
                ctx.translate(px, py)
                ctx.rotate(k * 9)
                ellipse(ctx, 0, 0, 54, 48)
                fs(ctx, "#cfcfdb", "#6e6e80", 6)
                ctx.restore()
            bolts(ctx, t, T_BOING, 760, 1270 - 600, 41)
            sparks(ctx, t, T_BOING, 760, 1270 - 560, 42, n=12, col="#ffffff", spread=0.8)
        # moustache arrachée
        if t >= T_RIP:
            k = t - T_RIP
            if k < 1.2:
                draw_mustache(ctx, bx + 0 + 500 * k, by - 290 - 700 * k + 900 * k * k, 1.0, -0.2 + k * 10)
            if k < 0.3:
                sparks(ctx, t, T_RIP, bx, by - 290, 51, n=8, col="#ffffff", spread=0.5)


SUB_CACHE = {}
FNT = ImageFont.truetype(FONT, 92)
STROKE = 12


def subtitle_groups():
    groups = []
    for i, m in enumerate(TM["lines"]):
        words = [(w.replace(" ", " "), S[i] + s, S[i] + min(e, m["dur"])) for w, s, e in m["words"]]
        phrases, cur = [], []
        for w in words:
            cur.append(w)
            if re.search(r"[.!?…]$", w[0]):
                phrases.append(cur)
                cur = []
        if cur:
            phrases.append(cur)
        chunks = []
        for ph in phrases:
            def fits(c):
                return FNT.getlength(" ".join(x[0] for x in c)) + 2 * STROKE <= 960
            if len(ph) <= 3 and fits(ph) or (len(ph) == 4 and fits(ph)):
                chunks.append(ph)
                continue
            n = math.ceil(len(ph) / 3)
            while True:
                size = math.ceil(len(ph) / n)
                parts = [ph[k:k + size] for k in range(0, len(ph), size)]
                if all(fits(p) for p in parts) or n >= len(ph):
                    break
                n += 1
            chunks.extend(parts)
        # fusionner un mot isolé très court avec le suivant si ça tient
        merged = []
        for c in chunks:
            if merged and len(merged[-1]) == 1 and len(merged[-1][0][0]) <= 4 and len(merged[-1]) + len(c) <= 3 \
                    and FNT.getlength(" ".join(x[0] for x in merged[-1] + c)) + 2 * STROKE <= 960:
                merged[-1] = merged[-1] + c
            else:
                merged.append(c)
        chunks = merged
        for ci, ch in enumerate(chunks):
            t0 = ch[0][1] - 0.06
            t1 = chunks[ci + 1][0][1] - 0.06 if ci + 1 < len(chunks) else E[i] + 0.12
            groups.append(dict(words=ch, t0=t0, t1=t1))
    return groups


GROUPS = subtitle_groups()


def render_sub(g, hi):
    key = (id(g), hi)
    if key in SUB_CACHE:
        return SUB_CACHE[key]
    words = [w[0] for w in g["words"]]
    space = FNT.getlength(" ")
    widths = [FNT.getlength(w) for w in words]
    tw = sum(widths) + space * (len(words) - 1)
    pad = STROKE + 10
    asc, desc = FNT.getmetrics()
    img = Image.new("RGBA", (int(tw + 2 * pad), asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ombre portée douce
    x = pad
    for k, w in enumerate(words):
        d.text((x + 5, pad + 7), w, font=FNT, fill=(0, 0, 0, 150), stroke_width=STROKE, stroke_fill=(0, 0, 0, 150))
        x += widths[k] + space
    x = pad
    for k, w in enumerate(words):
        col = (255, 225, 30, 255) if k == hi else (255, 255, 255, 255)
        d.text((x, pad), w, font=FNT, fill=col, stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
        x += widths[k] + space
    arr = np.asarray(img).astype(np.float32)
    SUB_CACHE[key] = arr
    return arr


def blend(frame, arr, cx, cy, scale=1.0):
    if scale != 1.0:
        h, w = arr.shape[:2]
        im = Image.fromarray(arr.astype(np.uint8), "RGBA").resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.BICUBIC)
        arr = np.asarray(im).astype(np.float32)
    h, w = arr.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    src = arr[ya - y0:yb - y0, xa - x0:xb - x0]
    a = src[..., 3:4] / 255.0
    dst = frame[ya:yb, xa:xb, :3].astype(np.float32)
    rgb = src[..., [2, 1, 0]]  # RGBA -> BGR
    frame[ya:yb, xa:xb, :3] = (dst * (1 - a) + rgb * a).astype(np.uint8)


def draw_subs(frame, t):
    for g in GROUPS:
        if g["t0"] <= t < g["t1"]:
            hi = 0
            for k, w in enumerate(g["words"]):
                if t >= w[1] - 0.03:
                    hi = k
            sc = lerp(0.78, 1.0, ease_out_back((t - g["t0"]) / 0.13))
            blend(frame, render_sub(g, hi), W / 2, SUB_Y, sc)
            break


def render_frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    cx, cy, z, sx, sy = camera(t)
    salon = t >= T_TRANS + 0.2
    slide = 0.0
    if T_TRANS <= t < T_TRANS + 0.2:
        slide = -W * (ease((t - T_TRANS) / 0.2) ** 1.5)
    elif T_TRANS + 0.2 <= t < T_TRANS + 0.4:
        slide = W * (1 - ease_out((t - T_TRANS - 0.2) / 0.2))
    ctx.save()
    ctx.translate(ANCHOR[0] + sx + slide, ANCHOR[1] + sy)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)
    draw_world(ctx, t, salon)
    ctx.restore()
    # traînées de vitesse pendant la transition (pas de texte)
    if T_TRANS <= t < T_TRANS + 0.4:
        rnd = random.Random(int(t * 30))
        for k in range(14):
            y = rnd.uniform(0, H)
            line(ctx, [(rnd.uniform(-200, 400), y), (rnd.uniform(700, 1300), y)], (1, 1, 1, 0.35), rnd.uniform(4, 14))
    # flash du court-circuit
    for t0, d, a in ((T_ZAP, 0.12, 0.85), (T_BOING, 0.08, 0.5)):
        if t0 <= t < t0 + d:
            ctx.rectangle(0, 0, W, H)
            ctx.set_source_rgba(1, 1, 1, a * (1 - (t - t0) / d))
            ctx.fill()
    # lueur rouge quand Aspi se réveille
    if T_RED <= t < T_RED + 0.5:
        ctx.rectangle(0, 0, W, H)
        ctx.set_source_rgba(1, 0.1, 0.1, 0.18 * (1 - (t - T_RED) / 0.5))
        ctx.fill()
    # vignette
    g = cairo.RadialGradient(W / 2, H * 0.45, H * 0.35, W / 2, H * 0.45, H * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.45)
    ctx.set_source(g)
    ctx.rectangle(0, 0, W, H)
    ctx.fill()
    surf.flush()
    frame = np.ndarray((H, W, 4), np.uint8, surf.get_data()).copy()
    draw_subs(frame, t)
    return frame


# =============================================================== bruitages
def sfx():
    rnd = np.random.default_rng(7)

    def env(n, a=0.005, r=None):
        e = np.ones(n)
        na = max(1, int(a * SR))
        e[:na] = np.linspace(0, 1, na)
        if r:
            e *= np.exp(-np.arange(n) / (r * SR))
        return e

    def lp(x, k):
        y = np.zeros_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += k[i] * (v - acc) if hasattr(k, "__len__") else k * (v - acc)
            y[i] = acc
        return y

    def whoosh(d=0.45):
        n = int(d * SR)
        x = rnd.standard_normal(n)
        k = 0.02 + 0.25 * np.sin(np.linspace(0, math.pi, n)) ** 2
        y = lp(x, k) - lp(lp(x, k), 0.02)
        return y * np.sin(np.linspace(0, math.pi, n)) ** 2 * 0.9

    def pop(f0=900, f1=250, d=0.09):
        n = int(d * SR)
        f = np.linspace(f0, f1, n)
        return np.sin(np.cumsum(f) * TAU / SR) * env(n, 0.002, 0.03)

    def boing(d=0.75):
        n = int(d * SR)
        tt = np.arange(n) / SR
        f = 160 + 140 * tt / d + 70 * np.sin(TAU * 11 * tt) * np.exp(-3 * tt)
        return np.sin(np.cumsum(f) * TAU / SR) * env(n, 0.003, 0.35)

    def crunch():
        out = np.zeros(int(0.32 * SR))
        for k in range(4):
            n = int(0.05 * SR)
            b = rnd.standard_normal(n) * env(n, 0.001, 0.012)
            b = b - lp(b, 0.15)
            s = int(k * 0.07 * SR)
            out[s:s + n] += b
        return out * 0.9

    def zap(d=0.5):
        n = int(d * SR)
        tt = np.arange(n) / SR
        sq = np.sign(np.sin(TAU * 110 * tt)) * 0.35 + rnd.standard_normal(n) * 0.5
        am = (np.sin(TAU * 32 * tt) > 0).astype(float)
        return sq * am * env(n, 0.002, 0.2)

    def beep():
        out = np.zeros(int(0.35 * SR))
        for k in range(2):
            n = int(0.09 * SR)
            tt = np.arange(n) / SR
            s = int(k * 0.15 * SR)
            out[s:s + n] += np.sin(TAU * (1250 if k == 0 else 950) * tt) * env(n, 0.003, 0.05)
        return out

    def ting():
        n = int(0.6 * SR)
        tt = np.arange(n) / SR
        return sum(np.sin(TAU * f * tt) * np.exp(-tt * 6) for f in (1568, 2093, 2637)) / 3

    def rip():
        n = int(0.18 * SR)
        x = rnd.standard_normal(n)
        return (x - lp(x, 0.3)) * env(n, 0.002, 0.06) * 0.8

    ev = [
        (0.0, pop(500, 900, 0.08), 0.35),
        (T_BITE - 0.02, crunch(), 0.6),
        (T_BITE + 0.05, zap(0.25), 0.25),
        (T_TRANS - 0.05, whoosh(), 0.8),
        (T_ZAP, zap(), 0.55),
        (T_HUG, whoosh(0.3), 0.4),
        (T_BOING - 0.02, pop(), 0.6),
        (T_BOING, boing(), 0.55),
        (T_RED, beep(), 0.35),
        (T_SPARK, ting(), 0.35),
        (T_RIP, rip(), 0.6),
        (T_RIP + 0.03, pop(1100, 400, 0.07), 0.4),
    ]
    return ev


def build_audio(path):
    n = NF * SR // FPS
    mix = np.zeros(n + SR, np.float32)
    for i, x in enumerate(VOICE):
        s = int(S[i] * SR)
        mix[s:s + len(x)] += x
    for t0, x, g in sfx():
        s = max(0, int(t0 * SR))
        x = np.asarray(x, np.float32)
        x = x / (np.abs(x).max() + 1e-9) * g
        mix[s:s + len(x)] += x[: len(mix) - s]
    mix = mix[:n]
    mix = mix / max(1.0, np.abs(mix).max() / 0.97)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())


# =============================================================== main
def main():
    wav = os.path.join(BUILD, "mix.wav")
    build_audio(wav)
    print(f"Durée : {TOTAL:.2f} s ({NF} images)")
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":
        os.makedirs(os.path.join(BUILD, "stills"), exist_ok=True)
        for tt in [float(v) for v in sys.argv[2:]]:
            fr = render_frame(tt)
            Image.fromarray(fr[..., [2, 1, 0]]).save(os.path.join(BUILD, "stills", f"t{tt:05.2f}.png"))
        return
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-shortest", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(NF):
        p.stdin.write(render_frame(f / FPS).tobytes())
        if f % 150 == 0:
            print(f"  image {f}/{NF}")
    p.stdin.close()
    p.wait()
    print("OK ->", OUT)


if __name__ == "__main__":
    main()

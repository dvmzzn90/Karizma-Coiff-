"""Couvertures TikTok (1080x1920). Zone visible sur la grille du profil : centre 3:4 (y 240 → 1680).

python3 cover.py  ->  out/couverture_A.png, out/couverture_B.png, out/apercu_profil.png
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from timeline import W, H
from gfx import *
import scenes

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
SAFE = (240, 1680)


def lines_layer(lines, y0, stroke=12):
    """lines: [(texte, taille, couleur)] centrés, avec ombre portée."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = y0
    for txt, size, col in lines:
        f = font(size)
        bb = d.textbbox((0, 0), txt, font=f, stroke_width=stroke)
        tw = bb[2] - bb[0]
        if tw > W - 70:  # ajuste la taille pour tenir dans la largeur
            size = int(size * (W - 70) / tw)
            f = font(size)
            bb = d.textbbox((0, 0), txt, font=f, stroke_width=stroke)
            tw = bb[2] - bb[0]
        d.text(((W - tw) // 2, y), txt, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += int(size * 1.02)
    shadow = im.split()[3].filter(ImageFilter.GaussianBlur(18))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.putalpha(shadow.point(lambda v: int(v * 0.85)))
    out = Image.alpha_composite(sh, im)
    return np.asarray(out, np.float32) / 255


def claw_marks(a, cx, cy, ang=-0.95, length=1300, gap=120, glow_col="#ff7a1a", width=34):
    """Trois griffures lumineuses en diagonale."""
    def fn(d, im):
        r = np.random.default_rng(4)
        for k in (-1, 0, 1):
            ox, oy = -math.sin(ang) * gap * k, math.cos(ang) * gap * k
            pts_l, pts_r = [], []
            for i in range(30):
                u = i / 29
                x = cx + ox + math.cos(ang) * (u - 0.5) * length
                y = cy + oy + math.sin(ang) * (u - 0.5) * length
                w = width * math.sin(math.pi * u) ** 0.8 + 2
                nx, ny = -math.sin(ang), math.cos(ang)
                j = r.uniform(-5, 5)
                pts_l.append((x + nx * (w + j), y + ny * (w + j)))
                pts_r.append((x - nx * (w - j), y - ny * (w - j)))
            d.polygon(pts_l + pts_r[::-1], fill=(255, 255, 255, 255))
    m = layer_draw(fn)[..., 3]
    halo = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(40)), np.float32) / 255
    a += halo[..., None] * hexc(glow_col) * 1.3
    core = hexc("#fff0c0") * 0.6 + hexc(glow_col) * 0.6
    a[:] = a * (1 - m[..., None]) + core * m[..., None]
    return a


def cover_a():
    """Œil félin doré + griffures + question choc."""
    a = scenes.eye(1.0, 30)
    a = camera(a, 1.12, 0.5, (scenes.EYE_C[1] - 30) / H)
    a = np.roll(a, 300, 0)  # descend l'œil sous le texte
    a[:300] = a[300:301] * 0 + scenes._fur(1)[:300] * 0.6
    # assombrit le haut pour le texte
    top = np.clip(1 - (YY - 250) / 650, 0, 1)[..., None]
    a = a * (1 - 0.7 * top)
    a = claw_marks(a, 930, 1560, length=520, gap=62, width=17)
    over(a, lines_layer([("ET SI TU", 120, (255, 255, 255)),
                         ("DEVENAIS", 150, (255, 255, 255)),
                         ("UN ANIMAL ?", 165, (255, 229, 0))], 300))
    over(a, lines_layer([("8 MILLIARDS D'HUMAINS… AVEC DES GRIFFES", 46, (255, 255, 255))], 1590, stroke=6))
    return post(a, 0, "teal")


def cover_b():
    """Silhouette humaine qui se fend en lion, contre-jour orange."""
    a = vgrad([(0, "#05070a"), (0.55, "#2a1408"), (1, "#05070a")])
    glow(a, 540, 1150, 900, "#ff7a20", 0.9, 1.8)
    glow(a, 540, 1150, 260, "#ffd890", 0.6, 1.5)
    lion = silhouette("🦁", 820, "#140c06", "#ffc060", (0, -1), 18, rim_strength=1.4)
    paste(a, lion, 540, 1150)
    for ex in (-0.15, 0.15):
        glow(a, 540 + ex * 820, 1150 + 0.06 * 820, 60, "#ffc020", 1.0, 1.6)
        glow(a, 540 + ex * 820, 1150 + 0.06 * 820, 16, "#fffbe0", 1.0, 1.0)
    a = claw_marks(a, 930, 1560, ang=-1.0, length=520, gap=62, width=17)
    over(a, lines_layer([("TON PATRON ?", 110, (255, 255, 255)),
                         ("UN LION.", 170, (255, 229, 0)),
                         ("ET TOI ?", 120, (255, 255, 255))], 280))
    return post(a, 1, "teal")


def profile_preview(covers):
    """Simule la grille du profil TikTok (vignettes 3:4)."""
    tw, th = 300, 400
    sheet = Image.new("RGB", (tw * 3 + 8, th * 2 + 4), (18, 18, 18))
    others = [vgrad([(0, "#333333"), (1, "#222222")], th, tw)] * 6
    tiles = [to_img(c).crop((0, SAFE[0], W, SAFE[1])).resize((tw, th), Image.LANCZOS) for c in covers]
    tiles += [to_img(o) for o in others][: 6 - len(tiles)]
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 3) * (tw + 4), (i // 3) * (th + 4)))
    d = ImageDraw.Draw(sheet)
    for i in range(len(covers), 6):
        d.text(((i % 3) * (tw + 4) + 90, (i // 3) * (th + 4) + 180), "autre vidéo", font=font(26, FONT_BOLD), fill=(110, 110, 110))
    sheet.save(os.path.join(OUT, "apercu_profil.png"))


if __name__ == "__main__":
    ca, cb = cover_a(), cover_b()
    to_img(ca).save(os.path.join(OUT, "couverture_A.png"))
    to_img(cb).save(os.path.join(OUT, "couverture_B.png"))
    profile_preview([ca, cb])
    print("ok")

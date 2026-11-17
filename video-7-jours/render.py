"""Rendu de la vidéo « 7 jours sans électricité » (1080x1920, 30 i/s, 60 s).
Usage : python3 render.py audio.wav sortie.mp4
Les images frame par frame sont générées avec Pillow puis envoyées à ffmpeg.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 60.0
HERE = os.path.dirname(os.path.abspath(__file__))
IMG = {i: Image.open(os.path.join(HERE, "images", f"{i:02d}.png")).convert("RGB") for i in range(1, 16)}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
YELLOW = (255, 214, 0)
RED = (235, 40, 40)


def ease(p):
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


def lerp(a, b, p):
    return a + (b - a) * p


# --------------------------------------------------------------------------- caméra
def crop_frame(img, cx, cy, zoom, shake=(0.0, 0.0)):
    """cx, cy : centre normalisé ; zoom 1 = plus grande fenêtre 9:16 tenant dans l'image."""
    iw, ih = img.size
    if iw / ih > W / H:
        bh = ih
        bw = ih * W / H
    else:
        bw = iw
        bh = iw * H / W
    bw /= zoom
    bh /= zoom
    x = cx * iw - bw / 2 + shake[0] * bw
    y = cy * ih - bh / 2 + shake[1] * bh
    x = min(max(x, 0), iw - bw)
    y = min(max(y, 0), ih - bh)
    return img.resize((W, H), Image.BICUBIC, box=(x, y, x + bw, y + bh))


def shake_at(t, amp, freq=9.0):
    return (amp * (math.sin(t * freq * 2.1) + 0.5 * math.sin(t * freq * 3.7 + 1)),
            amp * (math.sin(t * freq * 1.7 + 2) + 0.5 * math.sin(t * freq * 4.3)))


class Shot:
    def __init__(self, img, start, end, cam, fade=0.0, fx=None):
        self.img, self.start, self.end, self.cam, self.fade, self.fx = img, start, end, cam, fade, fx

    def render(self, t):
        p = (t - self.start) / (self.end - self.start)
        frame = self.cam(IMG[self.img], t, p)
        if self.fx:
            frame = self.fx(frame, t, p)
        return frame


def linear_cam(c0, c1, shake=0.0, punch=None):
    """c0/c1 = (cx, cy, zoom). punch=(t0, amount) ajoute un zoom percutant."""
    def cam(img, t, p):
        e = ease(p) * 0.85 + p * 0.15
        cx, cy, z = (lerp(a, b, e) for a, b in zip(c0, c1))
        if punch:
            t0, amt = punch
            if t >= t0:
                z *= 1 + amt * math.exp(-(t - t0) * 6)
        return crop_frame(img, cx, cy, z, shake_at(t, shake) if shake else (0, 0))
    return cam


def keyframe_cam(keys, shake=0.0):
    """keys = [(p, cx, cy, zoom), ...] avec p dans [0, 1]."""
    def cam(img, t, p):
        for (p0, *a), (p1, *b) in zip(keys, keys[1:]):
            if p <= p1:
                q = ease((p - p0) / (p1 - p0)) if p1 > p0 else 1
                v = [lerp(x, y, q) for x, y in zip(a, b)]
                break
        else:
            v = keys[-1][1:]
        return crop_frame(img, *v, shake_at(t, shake) if shake else (0, 0))
    return cam


# --------------------------------------------------------------------------- effets
def fx_brightness(fn):
    def fx(frame, t, p):
        b = fn(t, p)
        return ImageEnhance.Brightness(frame).enhance(b) if abs(b - 1) > 1e-3 else frame
    return fx


def fx_night(frame, t, p):
    # ville plongée dans le noir : sombre, bleutée, légèrement désaturée
    f = ImageEnhance.Color(frame).enhance(0.35)
    f = ImageEnhance.Brightness(f).enhance(0.22)
    a = np.asarray(f).astype(np.float32)
    a[..., 2] = np.minimum(255, a[..., 2] * 1.6 + 6)
    a[..., 0] *= 0.8
    # éclair de tonnerre vers 30.0 s
    if 30.85 <= t <= 31.25:
        k = 1 - abs(t - 31.0) / 0.25
        a = a + 120 * max(k, 0)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_city_blackout(frame, t, p):
    # 7.4 s → 11 s : la ville s'éteint (complété par les horloges de l'image)
    return frame


# --------------------------------------------------------------------------- texte
_font_cache = {}


def font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT, size)
    return _font_cache[size]


def text_layer(lines, size, fill=(255, 255, 255), stroke=10, highlight=None, max_w=980):
    """Bloc de texte centré avec contour noir. highlight : mots à colorer."""
    f = font(size)
    # retour à la ligne automatique
    wrapped = []
    for line in lines:
        line = line.replace(" !", "\u00a0!").replace(" ?", "\u00a0?").replace(" ▼", "\u00a0▼")
        words, cur = line.split(" "), ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if f.getlength(test) + 2 * stroke > max_w and cur:
                wrapped.append(cur)
                cur = w_
            else:
                cur = test
        wrapped.append(cur)
    lh = int(size * 1.18)
    hgt = lh * len(wrapped) + 2 * stroke + 10
    layer = Image.new("RGBA", (W, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = stroke
    for line in wrapped:
        x = (W - f.getlength(line)) / 2
        for w_ in line.split(" "):
            col = fill
            if highlight and any(h in w_ for h in highlight):
                col = YELLOW
            d.text((x, y), w_, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += f.getlength(w_ + " ")
        y += lh
    # ombre portée douce
    sh = layer.split()[3].filter(ImageFilter.GaussianBlur(14))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(sh.point(lambda v: int(v * 0.6)))
    out = Image.alpha_composite(shadow, layer)
    return out


def badge(text, color=(0, 0, 0, 190), fg=(255, 255, 255), size=46):
    f = font(size)
    tw = int(f.getlength(text))
    b = Image.new("RGBA", (tw + 56, size + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rounded_rectangle((0, 0, b.width - 1, b.height - 1), radius=22, fill=color, outline=(255, 255, 255, 220), width=3)
    d.text((28, 16), text, font=f, fill=fg)
    return b


# Sous-titres synchronisés (début, fin, texte, mots surlignés)
CAPTIONS = [
    (0.15, 1.5, "ET SI DEMAIN…", []),
    (1.5, 3.2, "TOUTE L'ÉLECTRICITÉ DU MONDE", ["ÉLECTRICITÉ"]),
    (3.2, 5.0, "DISPARAISSAIT PENDANT 7 JOURS ?", ["7", "JOURS"]),
    (5.25, 6.5, "À 20H PRÉCISES…", ["20H"]),
    (6.5, 7.4, "TOUT S'ÉTEINT.", ["S'ÉTEINT."]),
    (7.4, 8.7, "LES TÉLÉS, LES TÉLÉPHONES,", []),
    (8.7, 9.8, "LES LUMIÈRES…", []),
    (9.8, 11.0, "ABSOLUMENT TOUT !", ["TOUT"]),
    (11.0, 13.4, "PLUS UNE SEULE BATTERIE À RECHARGER.", ["BATTERIE"]),
    (13.4, 15.8, "PLUS DE RÉSEAU. PLUS DE FEUX ROUGES.", ["RÉSEAU.", "FEUX"]),
    (15.8, 18.0, "ASCENSEURS BLOQUÉS.", ["BLOQUÉS."]),
    (18.0, 19.8, "DANS LES MAGASINS…", ["MAGASINS…"]),
    (19.8, 21.5, "LES RAYONS SE VIDENT.", ["VIDENT."]),
    (21.5, 23.3, "ET LA CARTE BANCAIRE ?", ["CARTE"]),
    (23.3, 25.0, "ELLE NE PASSE PLUS.", ["PLUS."]),
    (25.0, 27.4, "LES BANQUES FERMENT.", ["FERMENT."]),
    (27.4, 29.8, "TOUT LE PAYS EST TOUCHÉ.", ["TOUCHÉ."]),
    (29.8, 32.0, "LA NUIT, LA VILLE DISPARAÎT.", ["NUIT,"]),
    (32.0, 34.0, "LES JOURS PASSENT…", ["JOURS"]),
    (34.0, 36.0, "LES BATTERIES SONT VIDES.", ["VIDES."]),
    (36.0, 38.0, "LES RÉSERVES DIMINUENT.", ["RÉSERVES"]),
    (38.0, 40.0, "LA FATIGUE S'INSTALLE.", ["FATIGUE"]),
    (40.0, 42.4, "7E JOUR. TOUJOURS LE SILENCE…", ["7E"]),
    (42.4, 44.0, "QUAND SOUDAIN…", []),
    (44.0, 46.0, "UNE LUMIÈRE.", ["LUMIÈRE."]),
    (46.0, 48.0, "PUIS UNE AUTRE !", ["AUTRE"]),
    (48.0, 50.5, "LE COURANT REVIENT !", ["COURANT"]),
    (50.5, 53.0, "QUARTIER PAR QUARTIER…", []),
    (53.0, 55.0, "MAIS TOUT RÉPARER PRENDRA DU TEMPS.", ["TEMPS."]),
]
CAP_LAYERS = [(a, b, text_layer([txt], 76, highlight=hl)) for a, b, txt, hl in CAPTIONS]
CAP_Y = 1330

BADGES = [
    (11.0, 32.0, badge("JOUR 1")),
    (40.0, 48.0, badge("JOUR 7", color=(150, 20, 20, 210))),
]
OUTRO1 = text_layer(["7 JOURS SANS", "ÉLECTRICITÉ…"], 104, stroke=12)
OUTRO2 = text_layer(["TU TIENDRAIS ?"], 98, fill=YELLOW, stroke=14)
OUTRO3 = text_layer(["DIS-LE EN COMMENTAIRE ▼"], 54, stroke=8)


def paste(frame, layer, y, alpha=1.0, scale=1.0):
    if scale != 1.0:
        layer = layer.resize((int(layer.width * scale), int(layer.height * scale)), Image.BICUBIC)
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    x = (W - layer.width) // 2
    frame.alpha_composite(layer, (x, int(y - layer.height / 2)))


def overlays(frame, t):
    frame = frame.convert("RGBA")
    for a, b, lay in CAP_LAYERS:
        if a <= t < b:
            dt = t - a
            pop = 1 + 0.12 * math.exp(-dt * 14) * math.cos(dt * 20)  # petit « pop »
            alpha = min(1.0, dt / 0.08, (b - t) / 0.08)
            paste(frame, lay, CAP_Y, alpha, pop)
    for a, b, lay in BADGES:
        if a <= t < b:
            alpha = min(1.0, (t - a) / 0.3, (b - t) / 0.3)
            l2 = lay
            if alpha < 1:
                l2 = lay.copy()
                l2.putalpha(lay.split()[3].point(lambda v: int(v * alpha)))
            frame.alpha_composite(l2, (48, 120))
    # écran de fin
    if t >= 55.0:
        dt = t - 55.0
        paste(frame, OUTRO1, 330, min(1, dt / 0.2), 1 + 0.25 * math.exp(-dt * 8))
    if t >= 57.4:
        dt = t - 57.4
        paste(frame, OUTRO2, 1370, 1.0, 1 + 0.45 * math.exp(-dt * 9))
        if t >= 58.0:
            paste(frame, OUTRO3, 1530, min(1, (t - 58.0) / 0.3))
    return frame


# --------------------------------------------------------------------------- découpage
def zoom_punch_brightness(t, p):
    return 1.0


SHOTS = [
    # SCÈNE 1 – le monde avant (0-5 s) : descente sur la ville puis le salon
    Shot(2, 0.0, 2.6, linear_cam((0.5, 0.35, 1.25), (0.5, 0.62, 1.55))),
    Shot(1, 2.6, 5.0, linear_cam((0.5, 0.42, 1.05), (0.45, 0.48, 1.28)), fade=0.35),
    # SCÈNE 2 – la coupure (5-11 s)
    Shot(3, 5.0, 7.4, linear_cam((0.45, 0.45, 1.12), (0.42, 0.42, 1.3), shake=0.004, punch=(5.12, 0.18)),
         fx=fx_brightness(lambda t, p: 0.0 if t < 5.12 else 1.0)),
    Shot(5, 7.4, 11.0, keyframe_cam([(0, 0.4, 0.18, 1.3), (0.22, 0.4, 0.18, 1.33), (0.45, 0.4, 0.5, 1.33),
                                     (0.68, 0.4, 0.5, 1.36), (0.9, 0.4, 0.83, 1.33), (1.0, 0.4, 0.84, 1.36)])),
    # SCÈNE 3 – premières conséquences (11-18 s)
    Shot(4, 11.0, 13.4, linear_cam((0.5, 0.5, 1.05), (0.68, 0.6, 1.45), shake=0.003)),
    Shot(6, 13.4, 15.8, linear_cam((0.45, 0.5, 1.1), (0.55, 0.45, 1.25), shake=0.006)),
    Shot(7, 15.8, 18.0, linear_cam((0.4, 0.55, 1.05), (0.55, 0.45, 1.3)), fade=0.25),
    # SCÈNE 4 – magasins (18-25 s)
    Shot(8, 18.0, 21.5, linear_cam((0.3, 0.5, 1.2), (0.65, 0.48, 1.3))),
    Shot(9, 21.5, 25.0, keyframe_cam([(0, 0.4, 0.5, 1.1), (0.5, 0.7, 0.55, 1.45), (0.7, 0.3, 0.4, 1.5),
                                      (1.0, 0.28, 0.38, 1.6)]), fade=0.25),
    # SCÈNE 5 – banques, infos, première nuit (25-32 s)
    Shot(10, 25.0, 27.4, linear_cam((0.55, 0.5, 1.05), (0.6, 0.42, 1.25), shake=0.002)),
    Shot(11, 27.4, 29.8, linear_cam((0.5, 0.6, 1.05), (0.5, 0.62, 1.35)), fade=0.25),
    Shot(2, 29.8, 32.0, linear_cam((0.5, 0.55, 1.4), (0.5, 0.45, 1.2)), fade=0.5, fx=fx_night),
    # SCÈNE 6 – les jours passent (32-40 s)
    Shot(12, 32.0, 40.0, keyframe_cam([(0, 0.5, 0.5, 1.0), (0.12, 0.5, 0.5, 1.0), (0.2, 0.25, 0.25, 2.0),
                                       (0.36, 0.25, 0.25, 2.05), (0.42, 0.75, 0.25, 2.0), (0.58, 0.75, 0.25, 2.05),
                                       (0.64, 0.25, 0.75, 2.0), (0.8, 0.25, 0.75, 2.05), (0.86, 0.75, 0.75, 2.0),
                                       (1.0, 0.75, 0.75, 2.15)])),
    # SCÈNE 7 – le septième jour (40-48 s) : la lumière revient peu à peu
    Shot(13, 40.0, 48.0, linear_cam((0.45, 0.5, 1.0), (0.6, 0.42, 1.35)), fade=0.4,
         fx=fx_brightness(lambda t, p: 0.38 if t < 43.8 else min(1.0, 0.38 + (t - 43.8) * 0.2))),
    # SCÈNE 8 – le grand retour (48-55 s)
    Shot(14, 48.0, 55.0, linear_cam((0.4, 0.45, 1.05), (0.45, 0.4, 1.3), punch=(48.0, 0.15)),
         fx=fx_brightness(lambda t, p: 1.0 + 1.8 * math.exp(-(t - 48.0) * 5))),
    # SCÈNE 9 – la question finale (55-60 s)
    Shot(15, 55.0, 60.0, linear_cam((0.45, 0.55, 1.0), (0.32, 0.36, 1.45))),
]


def render_frame(t):
    idx = max(i for i, s in enumerate(SHOTS) if s.start <= t)
    s = SHOTS[idx]
    frame = s.render(t)
    if s.fade and idx > 0 and t < s.start + s.fade:
        prev = SHOTS[idx - 1].render(t)
        frame = Image.blend(prev, frame, ease((t - s.start) / s.fade))
    # flash noir au moment de la coupure
    if 5.0 <= t < 5.12:
        frame = Image.new("RGB", (W, H), (0, 0, 0))
    # vignette légère
    frame = Image.composite(frame, Image.new("RGB", (W, H), (0, 0, 0)), VIGNETTE)
    return overlays(frame, t).convert("RGB")


def make_vignette():
    y, x = np.ogrid[:H, :W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    m = np.clip(1.15 - 0.45 * d ** 2, 0.55, 1.0)
    return Image.fromarray((m * 255).astype(np.uint8), "L")


VIGNETTE = make_vignette()


def main():
    audio, out = sys.argv[1], sys.argv[2]
    only = float(sys.argv[3]) if len(sys.argv) > 3 else None
    if only is not None:  # aperçu d'une image
        render_frame(only).save(out)
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for i in range(total):
        p.stdin.write(render_frame(i / FPS).tobytes())
        if i % 150 == 0:
            print(f"{i}/{total}", flush=True)
    p.stdin.close()
    p.wait()
    print("ok", out)


if __name__ == "__main__":
    main()

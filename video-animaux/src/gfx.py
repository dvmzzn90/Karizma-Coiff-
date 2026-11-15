"""Outils graphiques : dégradés, silhouettes d'animaux, caméra, étalonnage, grain."""
import math, os
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
from timeline import W, H

FONT_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def font(size, path=FONT_BLACK):
    return _font(path, int(size))


@lru_cache(64)
def _font(path, size):
    return ImageFont.truetype(path, size)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def vgrad(stops, h=H, w=W):
    """stops: [(pos 0..1, '#rrggbb'), ...] -> float32 HxWx3"""
    ys = np.linspace(0, 1, h)
    cols = np.stack([np.interp(ys, [p for p, _ in stops], [hexc(c)[k] for _, c in stops]) for k in range(3)], 1)
    return np.repeat(cols[:, None, :], w, 1).astype(np.float32)


def radial(cx, cy, r, h=H, w=W, power=2.0):
    if h == H and w == W:
        d = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
    else:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.clip(1 - d / r, 0, 1) ** power


def glow(img, cx, cy, r, color, strength=1.0, power=2.0):
    img += radial(cx, cy, r, power=power)[..., None] * hexc(color) * strength
    return img


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def to_arr(img):
    return np.asarray(img.convert("RGB"), np.float32) / 255


def fbm(h, w, seed=0, octaves=5, base=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        small = rng.random((n, max(2, int(n * w / h)))).astype(np.float32)
        layer = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        out += layer * amp
        tot += amp
        amp *= 0.5
    return out / tot


# ---------------------------------------------------------------- silhouettes
OPEN_EMOJI = {"🐕‍🦺"}
WOLF = "🐕‍🦺"


@lru_cache(64)
def emoji_alpha(ch, size):
    f = ImageFont.truetype(FONT_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((8, 8), ch, font=f, embedded_color=True)
    a = im.split()[3]
    bbox = a.getbbox()
    a = a.crop(bbox)
    if ch in OPEN_EMOJI:  # gomme les fines lignes (poignée de harnais)
        a = a.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))
        a = a.crop(a.point(lambda v: 255 if v > 60 else 0).getbbox())
    s = size / max(a.size)
    a = a.resize((max(1, int(a.size[0] * s)), max(1, int(a.size[1] * s))), Image.LANCZOS)
    a = a.filter(ImageFilter.GaussianBlur(size / 400))
    arr = np.asarray(a, np.float32) / 255
    arr = np.clip((arr - 0.5) * 3 + 0.5, 0, 1)
    return arr


def silhouette(ch, size, fill="#07080a", rim="#ffb060", rim_dir=(-1, -1), rim_w=None, flip=False, rim_strength=1.0):
    """Silhouette RGBA float (h,w,4) d'un animal, éclairée en contre-jour."""
    a = emoji_alpha(ch, int(size))
    if flip:
        a = a[:, ::-1]
    rim_w = rim_w or max(2, int(size / 90))
    dx, dy = int(rim_dir[0] * rim_w), int(rim_dir[1] * rim_w)
    shifted = np.roll(np.roll(a, -dy, 0), -dx, 1)
    rim_mask = np.clip(a - shifted, 0, 1)
    rim_mask = np.asarray(Image.fromarray((rim_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rim_w * 0.6)), np.float32) / 255 * a
    rgb = np.ones(a.shape + (3,), np.float32) * hexc(fill)
    rgb = rgb + rim_mask[..., None] * hexc(rim) * 1.6 * rim_strength
    return np.dstack([np.clip(rgb, 0, 1), a])


def paste(dst, rgba, cx, cy, scale=1.0, alpha=1.0):
    """Colle un RGBA float centré en (cx,cy) dans dst (float HxWx3)."""
    if scale != 1.0:
        h, w = rgba.shape[:2]
        im = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        rgba = np.asarray(im, np.float32) / 255
    h, w = rgba.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return dst
    src = rgba[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    a = src[..., 3:4] * alpha
    dst[Y0:Y1, X0:X1] = dst[Y0:Y1, X0:X1] * (1 - a) + src[..., :3] * a
    return dst


def layer_draw(fn, size=(W, H)):
    """Dessine avec PIL sur un calque RGBA et le renvoie en float."""
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), im)
    return np.asarray(im, np.float32) / 255


def over(dst, rgba, alpha=1.0):
    a = rgba[..., 3:4] * alpha
    dst[:] = dst * (1 - a) + rgba[..., :3] * a
    return dst


def text_layer(lines, size, fill=(255, 255, 255), stroke=8, y=0.25, spacing=1.08, path=FONT_BLACK, emoji_tail=None):
    f = font(size, path)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    yy = int(y * H)
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=f, stroke_width=stroke)
        tw = bb[2] - bb[0]
        extra = 0
        if emoji_tail and ln is lines[-1]:
            extra = int(size * 1.1)
        x = (W - tw - extra) // 2
        d.text((x, yy), ln, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
        if emoji_tail and ln is lines[-1]:
            e = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
            ImageDraw.Draw(e).text((8, 8), emoji_tail, font=ImageFont.truetype(FONT_EMOJI, 109), embedded_color=True)
            e = e.crop(e.getbbox()).resize((int(size * 0.95), int(size * 0.95)), Image.LANCZOS)
            im.alpha_composite(e, (x + tw + int(size * 0.12), yy + int(size * 0.08)))
        yy += int(size * spacing)
    return np.asarray(im, np.float32) / 255


# ---------------------------------------------------------------- caméra et post
def camera(arr, zoom=1.0, cx=0.5, cy=0.5, rot=0.0, shake=(0, 0)):
    if zoom == 1.0 and rot == 0.0 and shake == (0, 0) and cx == 0.5 and cy == 0.5:
        return arr
    im = to_img(arr)
    w2, h2 = W / zoom, H / zoom
    x0 = cx * W - w2 / 2 + shake[0]
    y0 = cy * H - h2 / 2 + shake[1]
    if rot:
        im = im.rotate(rot, resample=Image.BILINEAR, center=(cx * W, cy * H))
    im = im.transform((W, H), Image.EXTENT, (x0, y0, x0 + w2, y0 + h2), Image.BILINEAR)
    return to_arr(im)


def hblur(arr, amount):
    """Flou de bougé horizontal (whip pan)."""
    if amount <= 0.01:
        return arr
    im = to_img(arr)
    k = 1 + amount * 40
    small = im.resize((max(8, int(W / k)), H), Image.BILINEAR)
    return to_arr(small.resize((W, H), Image.BILINEAR))


def vblur(arr, amount):
    if amount <= 0.01:
        return arr
    im = to_img(arr)
    k = 1 + amount * 40
    small = im.resize((W, max(8, int(H / k))), Image.BILINEAR)
    return to_arr(small.resize((W, H), Image.BILINEAR))


def blur(arr, r):
    if r < 0.5:
        return arr
    return to_arr(to_img(arr).filter(ImageFilter.GaussianBlur(r)))


def zoom_blur(arr, amount):
    if amount < 0.01:
        return arr
    acc = arr.copy()
    for i, z in enumerate((1 + amount * 0.05, 1 + amount * 0.1, 1 + amount * 0.16)):
        acc += camera(arr, z)
    return acc / 4


VIGNETTE = (1 - 0.55 * np.clip(((XX - W / 2) / (W * 0.75)) ** 2 + ((YY - H / 2) / (H * 0.7)) ** 2, 0, 1) ** 1.2)[..., None]
_grain_rng = np.random.default_rng(3)
GRAIN = [(_grain_rng.standard_normal((H // 2, W // 2)).astype(np.float32)) for _ in range(6)]


def grade(arr, kind):
    a = arr
    if kind == "teal":
        lum = a.mean(2, keepdims=True)
        sh = np.array([0.0, 0.10, 0.13], np.float32)
        hi = np.array([0.12, 0.04, -0.06], np.float32)
        a = a + (1 - lum) ** 2 * sh * 0.6 + lum ** 2 * hi * 0.8
        a = (a - 0.5) * 1.12 + 0.5
    elif kind == "gold":
        lum = a.mean(2, keepdims=True)
        a = a + (1 - lum) ** 2 * np.array([-0.01, 0.05, 0.0], np.float32) + lum ** 2 * np.array([0.10, 0.07, -0.05], np.float32)
        a = (a - 0.5) * 1.06 + 0.5
    elif kind == "night":
        a = a * np.array([0.92, 0.98, 1.08], np.float32)
        a = (a - 0.5) * 1.1 + 0.5
    return np.clip(a, 0, 1)


def post(arr, frame_idx, kind):
    a = grade(arr, kind)
    a = a * VIGNETTE
    g = GRAIN[frame_idx % len(GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    a = a + g * 0.028
    return np.clip(a, 0, 1)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_in(x):
    x = min(1.0, max(0.0, x))
    return x ** 3

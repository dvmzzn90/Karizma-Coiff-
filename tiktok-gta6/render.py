import sys, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

SRC = __import__('os').path.join(__import__('os').path.dirname(__file__), 'storyboard.png')
OUT = sys.argv[1]
W, H, FPS, DUR = 1080, 1920, 30, 60.0
N = int(FPS * DUR)
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf'
FONT_SUB = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'

src = Image.open(SRC).convert('RGB')
BOX = [(642, 90, 944, 356), (954, 90, 1276, 356), (1287, 64, 1626, 356),
       (642, 368, 944, 634), (954, 368, 1276, 636), (1287, 368, 1624, 636)]
BADGE = [(0, 0, 100, 42)] * 2 + [(0, 0, 112, 48)] + [(0, 0, 100, 42)] * 3

def prep(i):
    p = src.crop(BOX[i])
    x0, y0, x1, y1 = BADGE[i]
    region = p.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(14))
    p.paste(region, (x0, y0))
    # upscale once, then sharpen to fight softness
    big = p.resize((p.width * 4, p.height * 4), Image.LANCZOS)
    big = big.filter(ImageFilter.UnsharpMask(radius=3, percent=120, threshold=2))
    big = ImageEnhance.Color(big).enhance(1.15)
    return big

panels = [prep(i) for i in range(6)]
hero = src.crop((0, 40, 700, 941)).resize((1400, 1802), Image.LANCZOS).filter(
    ImageFilter.UnsharpMask(radius=3, percent=100))

def cover_bg(img):
    s = max(W / img.width, H / img.height)
    b = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.BILINEAR)
    b = b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H))
    b = b.filter(ImageFilter.GaussianBlur(28))
    return ImageEnhance.Brightness(b).enhance(0.45)

bgs = [cover_bg(p) for p in panels]
hero_bg = cover_bg(hero)

# ---------- script ----------
SCENES = [
    dict(t0=0, title=[('TU VEUX GTA 6 ?', 0.0), ("MAIS T'AS PAS D'ARGENT ?", 1.6)],
         vo="Tu veux GTA 6, mais t'as pas d'argent ? Regarde cette vidéo jusqu'à la fin !"),
    dict(t0=10, title=[('LE GAMING', 0.3), ('COÛTE CHER !', 0.9)],
         vo="Comme beaucoup de joueurs, tu rêves de découvrir GTA 6, mais entre les dépenses du quotidien et le prix des jeux, ce n'est pas toujours facile de se faire plaisir !"),
    dict(t0=20, title=[('⚠ ATTENTION', 0.2), ('AUX ARNAQUES ! ⚠', 0.8)],
         vo="Mais attention ! Sur Internet, certains sites promettent GTA 6 gratuitement pour attirer les joueurs. Ne tombe surtout pas dans le piège ! Certains cherchent simplement à voler tes informations ou ton argent."),
    dict(t0=30, title=[('1. ÉCONOMISE', 0.3), ('2. COMPARE LES PRIX', 2.8), ('3. SURVEILLE LES PROMOS', 5.2)],
         vo="Alors, voici ce que tu peux faire : mets un peu d'argent de côté chaque semaine, compare les prix chez les revendeurs fiables et surveille les promotions officielles. Même quelques euros économisés peuvent faire la différence !"),
    dict(t0=40, title=[('BIENTÔT,', 0.4), ('À TOI DE JOUER !', 1.0)],
         vo="Imagine maintenant le jour où tu pourras enfin lancer GTA 6, prendre le volant et découvrir tout cet univers. Autant bien préparer ton budget dès maintenant !"),
    dict(t0=50, title=[('TU VAS ACHETER GTA 6 ?', 0.3), ('OUI OU NON ?', 4.5)],
         vo="Maintenant, dis-moi en commentaire : tu comptes acheter GTA 6 dès sa sortie ou attendre une promotion ? Et abonne-toi à Cinema Short pour découvrir d'autres astuces gaming !"),
]

def chunks(text, start, end, maxw=5):
    words = text.replace('GTA 6', 'GTA 6').split(' ')
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or w[-1] in ',!?:.':
            if len(cur) >= 2 or w[-1] in '!?.':
                groups.append(' '.join(cur)); cur = []
    if cur:
        if groups and len(cur) == 1:
            groups[-1] += ' ' + cur[0]
        else:
            groups.append(' '.join(cur))
    total = sum(len(g) for g in groups)
    out, t = [], start
    for g in groups:
        d = (end - start) * len(g) / total
        out.append((t, t + d, g)); t += d
    return out

SUBS = []
for s in SCENES:
    SUBS += chunks(s['vo'], s['t0'] + 0.15, s['t0'] + 9.7)

def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

with open(OUT.replace('.mp4', '.srt'), 'w') as f:
    for i, (a, b, g) in enumerate(SUBS, 1):
        f.write(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{g}\n\n')

# ---------- drawing helpers ----------
_fc = {}
def font(path, size):
    k = (path, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]

def text_img(txt, size, fill, stroke=10, path=FONT, highlight=None, maxw=980):
    f = font(path, size)
    while f.getlength(txt) > maxw and size > 30:
        size -= 4; f = font(path, size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    im = Image.new('RGBA', (r - l + 30, b - t + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x, y = 15 - l, 15 - t
    # drop shadow
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + 6, y + 8), txt, font=f, fill=(0, 0, 0, 200), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(im)
    if highlight and highlight in txt:
        pre, post = txt.split(highlight, 1)
        d.text((x, y), pre, font=f, fill=fill, stroke_width=stroke, stroke_fill='black')
        x2 = x + f.getlength(pre)
        d.text((x2, y), highlight, font=f, fill=(255, 70, 200), stroke_width=stroke, stroke_fill='black')
        d.text((x2 + f.getlength(highlight), y), post, font=f, fill=fill, stroke_width=stroke, stroke_fill='black')
    else:
        d.text((x, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill='black')
    return im

_tc = {}
def cached_text(*a, **k):
    key = (a, tuple(sorted(k.items())))
    if key not in _tc: _tc[key] = text_img(*a, **k)
    return _tc[key]

def paste_scaled(canvas, im, cx, cy, scale, rot=0):
    if scale <= 0.01: return
    w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    s = im.resize((w, h), Image.BILINEAR)
    if rot: s = s.rotate(rot, expand=True, resample=Image.BILINEAR)
    canvas.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))

def ease_back(x):
    x = min(max(x, 0), 1); c = 2.2
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def pop(t, start, dur=0.28):
    return ease_back((t - start) / dur) if t >= start else 0

def rounded_mask(size, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m

PW = 1040
def panel_frame(i, lt, zoom_from=1.0, zoom_to=1.10, focus=(0.5, 0.5), shake=0.0):
    p = panels[i]
    z = zoom_from + (zoom_to - zoom_from) * min(lt / 10, 1)
    ph = int(PW * p.height / p.width)
    cw, ch = p.width / z, p.height / z
    fx, fy = focus
    x0 = (p.width - cw) * fx; y0 = (p.height - ch) * fy
    if shake:
        x0 += math.sin(lt * 53) * shake * p.width; y0 += math.cos(lt * 47) * shake * p.height
        x0 = min(max(x0, 0), p.width - cw); y0 = min(max(y0, 0), p.height - ch)
    img = p.resize((PW, ph), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    return img

def neon_frame(img, color):
    pad = 40
    out = Image.new('RGBA', (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    glow = Image.new('RGBA', out.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((pad - 8, pad - 8, pad + img.width + 7, pad + img.height + 7), 40, fill=color + (255,))
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
    rgba = img.convert('RGBA'); rgba.putalpha(rounded_mask(img.size, 32))
    out.alpha_composite(rgba, (pad, pad))
    return out

COL = [(190, 60, 255), (120, 90, 255), (255, 40, 60), (60, 220, 120), (255, 80, 200), (190, 60, 255)]
PANEL_CY = 890

def render(n):
    t = n / FPS
    si = min(int(t // 10), 5); s = SCENES[si]; lt = t - s['t0']
    shake = 0.0
    use_hero = (si == 0 and lt < 1.8) or (si == 5 and lt >= 7.2)
    if use_hero:
        cv = hero_bg.convert('RGBA')
        hl = lt if si == 0 else lt - 7.2
        z = (1.0 + 0.9 * min(hl / 0.35, 1)) if si == 0 else (1.15 + 0.25 * min(hl / 2.8, 1))
        cw, ch = hero.width / z, hero.width / z * (H / W)
        ch = min(ch, hero.height / z * 1.0)
        fx, fy = 0.30, 0.42 if si == 0 else 0.45
        cw = ch * W / H
        x0 = (hero.width - cw) * fx + (math.sin(t * 60) * 10 if hl < 0.6 and si == 0 else 0)
        y0 = (hero.height - ch) * fy
        x0 = min(max(x0, 0), hero.width - cw); y0 = min(max(y0, 0), hero.height - ch)
        cv.paste(hero.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)), (0, 0))
    else:
        cv = bgs[si].copy().convert('RGBA')
        # subtle background drift
        if si == 0:
            img = panel_frame(0, lt - 1.8, 1.25, 1.05, (0.35, 0.3))
        elif si == 1:
            # whip between face / phone / screen
            foc = [(0.2, 0.3), (0.85, 0.75), (0.85, 0.15), (0.5, 0.5)][min(int(lt / 2.5), 3)]
            img = panel_frame(1, lt % 2.5 * 4, 1.45, 1.35, foc) if lt < 7.5 else panel_frame(1, lt, 1.0, 1.06)
        elif si == 2:
            shake = 0.004 if 4.8 < lt < 6.0 else 0.0
            foc = (0.75, 0.12) if lt < 4.8 else (0.5, 0.5)
            img = panel_frame(2, lt, 1.35 if lt < 4.8 else 1.0, 1.5 if lt < 4.8 else 1.08, foc, shake)
        elif si == 3:
            img = panel_frame(3, lt, 1.0, 1.12, (0.3, 0.7))
        elif si == 4:
            img = panel_frame(4, lt, 1.0, 1.35, (0.5, 0.85 - 0.5 * lt / 10))
        else:
            img = panel_frame(5, lt, 1.0, 1.15, (0.5, 0.3))
        fr = neon_frame(img, COL[si])
        intro = 0 if si == 0 else 0
        sc = 1.0 + 0.18 * max(0, 1 - (lt - (1.8 if si == 0 else 0)) / 0.25)
        paste_scaled(cv, fr, W / 2, PANEL_CY, sc * 1.0)

    # scene 3 red alert overlay
    if si == 2 and lt > 4.8:
        a = int(110 * (0.5 + 0.5 * math.sin((lt - 4.8) * 10))) if lt < 8 else 50
        cv.alpha_composite(Image.new('RGBA', (W, H), (255, 0, 30, a)))
        if lt < 8:
            al = cached_text('⚠  ARNAQUE  ⚠', 120, (255, 255, 255), stroke=12, path=FONT_SUB)
            paste_scaled(cv, al, W / 2, PANEL_CY, pop(lt, 4.8) * (1 + 0.05 * math.sin(lt * 14)), rot=-4)
    # scene 2: money draining counter
    if si == 1 and 3 < lt < 9.6:
        v = max(3.27, 79.99 - (lt - 3) * 40)
        ct = cached_text(f'SOLDE : {v:0.2f} €', 70, (255, 80, 80), stroke=8, path=FONT_SUB)
        paste_scaled(cv, ct, W / 2, 1420, pop(lt, 3))
    # scene 4: piggy bank counter
    if si == 3 and lt > 1:
        v = min(80, int((lt - 1) * 11))
        ct = cached_text(f'TIRELIRE : {v} €', 70, (120, 255, 140), stroke=8, path=FONT_SUB)
        paste_scaled(cv, ct, W / 2, 1420, pop(lt, 1))
    # scene 6 end card
    if si == 5 and lt >= 7.2:
        ab = cached_text('ABONNE-TOI À CINEMA SHORT', 58, (255, 255, 255), stroke=7, path=FONT_SUB)
        paste_scaled(cv, ab, W / 2, 1440, pop(lt, 7.6))

    # titles (top)
    y = 230
    lines = s['title']
    big = len(lines) <= 2
    for k, (txt, st) in enumerate(lines):
        if lt < st: continue
        col = (255, 225, 40) if k % 2 else (255, 255, 255)
        if si == 2: col = (255, 255, 255) if k == 0 else (255, 230, 40)
        if si == 3: col = (120, 255, 140)
        size = 104 if big else 76
        if si == 5 and k == 1:
            if use_hero:
                im = cached_text(txt, 150, (255, 225, 40), stroke=14)
                paste_scaled(cv, im, W / 2, 1230, pop(lt, max(st, 7.2)) * (1 + 0.06 * math.sin(lt * 9)), rot=-3)
                continue
            im = cached_text(txt, 120, (255, 225, 40), stroke=12)
            paste_scaled(cv, im, W / 2, 1420, pop(lt, st) * (1 + 0.06 * math.sin(lt * 9)), rot=-3)
            continue
        im = cached_text(txt, size, col, stroke=11, highlight='GTA 6')
        paste_scaled(cv, im, W / 2, y, pop(lt, st), rot=(-2 if k % 2 else 0))
        y += im.height - 10
    # scene 1 hero hook title stays visible during hero
    # subtitles
    for a, b, g in SUBS:
        if a <= t < b:
            im = cached_text(g.replace(' ', ' '), 66, (255, 255, 255), stroke=7, path=FONT_SUB, highlight='GTA 6', maxw=960)
            paste_scaled(cv, im, W / 2, 1560, 0.85 + 0.15 * pop(t, a, 0.15))
            break
    # white flash on cuts
    for c in [1.8, 10, 20, 30, 40, 50, 57.2]:
        if c <= t < c + 0.12:
            cv.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(200 * (1 - (t - c) / 0.12)))))
    if t > 59.6:
        cv.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(255 * min(1, (t - 59.6) / 0.4)))))
    return cv.convert('RGB')

# ---------- audio ----------
SR = 44100
def build_audio(path):
    L = int(SR * DUR); a = np.zeros(L)
    tt = np.arange(L) / SR
    bpm = 120; beat = 60 / bpm
    def add(sig, at, gain=1.0):
        i = int(at * SR); j = min(L, i + len(sig))
        if i < L: a[i:j] += sig[:j - i] * gain
    def env(d, atk=0.005, rel=None):
        n = int(d * SR); e = np.ones(n)
        k = max(1, int(atk * SR)); e[:k] = np.linspace(0, 1, k)
        e *= np.exp(-np.arange(n) / SR / (rel or d / 4))
        return e
    rng = np.random.default_rng(1)
    def kick():
        d = 0.35; x = np.arange(int(d * SR)) / SR
        f = 50 + 120 * np.exp(-x * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)
    def hat():
        d = 0.05; return rng.standard_normal(int(d * SR)) * env(d, rel=0.012) * 0.3
    def snare():
        d = 0.2; x = np.arange(int(d * SR)) / SR
        return (rng.standard_normal(len(x)) * 0.6 + np.sin(2 * np.pi * 190 * x) * 0.5) * np.exp(-x * 18)
    # chord progression (minor, synthwave): Am F C G
    roots = [110.0, 87.31, 130.81, 98.0]
    nb = int(DUR / beat)
    for b in range(nb):
        t0 = b * beat
        sc = min(int(t0 // 10), 5)
        if sc == 2:  # suspense: sparse
            if b % 4 == 0: add(kick(), t0, 0.8)
        else:
            add(kick(), t0, 0.9)
            if b % 2 == 1: add(snare(), t0, 0.5 if sc >= 3 else 0.35)
        for h in range(2): add(hat(), t0 + h * beat / 2 + beat / 4, 0.6 if sc != 2 else 0.25)
        # bass (8ths)
        r = roots[(b // 4) % 4]
        for h in range(2):
            d = beat / 2; x = np.arange(int(d * SR)) / SR
            saw = 2 * ((x * r) % 1) - 1
            add(saw * np.exp(-x * 6) * 0.22, t0 + h * d)
    # pad
    for bar in range(int(DUR / (4 * beat))):
        t0 = bar * 4 * beat; r = roots[bar % 4] * 2
        d = 4 * beat; x = np.arange(int(d * SR)) / SR
        sig = sum(np.sin(2 * np.pi * r * m * x + np.sin(2 * np.pi * 0.3 * x)) for m in (1, 1.189, 1.498)) / 3
        e = np.minimum(1, x / 0.3) * np.minimum(1, (d - x) / 0.3)
        sc = min(int(t0 // 10), 5)
        add(sig * e * (0.12 if sc < 4 else 0.18), t0)
    # rising riser into scene 5 and 6
    for st in (38.0, 48.0):
        d = 2.0; x = np.arange(int(d * SR)) / SR
        add(rng.standard_normal(len(x)) * (x / d) ** 2 * 0.25, st)
    a *= 0.55
    # SFX
    def impact():
        d = 0.8; x = np.arange(int(d * SR)) / SR
        return (np.sin(2 * np.pi * (40 + 60 * np.exp(-x * 8)) * x) + rng.standard_normal(len(x)) * 0.4 * np.exp(-x * 20)) * np.exp(-x * 4)
    def whoosh():
        d = 0.35; x = np.arange(int(d * SR)) / SR
        n = rng.standard_normal(len(x)); n = np.convolve(n, np.ones(8) / 8, 'same')
        return n * np.sin(np.pi * x / d) * 0.6
    def ping(f=1320):
        d = 0.4; x = np.arange(int(d * SR)) / SR
        return (np.sin(2 * np.pi * f * x) + 0.5 * np.sin(2 * np.pi * f * 1.5 * x)) * np.exp(-x * 9) * 0.5
    def coin():
        return np.concatenate([ping(1975)[:int(0.08 * SR)], ping(2637)]) * 0.8
    def alarm():
        d = 1.2; x = np.arange(int(d * SR)) / SR
        f = 700 + 300 * (np.sin(2 * np.pi * 3 * x) > 0)
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.18 * np.minimum(1, (d - x) * 5)
    def boing():
        d = 0.5; x = np.arange(int(d * SR)) / SR
        f = 500 * np.exp(-x * 3)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 5) * 0.5
    add(impact(), 0.0, 1.0)
    for c in [1.8, 10, 20, 30, 40, 50, 57.2]: add(whoosh(), c - 0.15, 0.9); add(impact(), c, 0.5)
    add(boing(), 2.3); add(boing(), 13.0); add(boing(), 15.5)
    for k in range(3): add(ping(), 21.0 + k * 1.2)
    add(alarm(), 24.8); add(alarm(), 26.0)
    for k in range(10): add(coin(), 31.0 + k * 0.8, 0.6)
    for k in range(3): add(ping(1760), 30.3 + k * 2.5, 0.5)
    add(impact(), 54.5, 0.9); add(impact(), 59.4, 1.2)
    a = np.tanh(a * 1.2) * 0.85
    pcm = (a * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] == 'preview':
        for tsec in [0.3, 1.0, 2.5, 6, 14, 22, 26, 34, 45, 53, 58]:
            render(int(tsec * FPS)).save(OUT.replace('.mp4', f'_{tsec}.jpg'), quality=80)
        sys.exit()
    wav = OUT.replace('.mp4', '.wav')
    build_audio(wav)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
                          '-movflags', '+faststart', '-shortest', OUT], stdin=subprocess.PIPE)
    for n in range(N):
        p.stdin.write(render(n).tobytes())
        if n % 300 == 0: print(n, flush=True)
    p.stdin.close(); p.wait()
    print('done')

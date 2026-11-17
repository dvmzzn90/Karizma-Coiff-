"""TikTok GTA 6 video, 1080x1920, 60 s.

Mode A (default): uses the 6-panel storyboard (storyboard2.png). Each scene fills the
whole 9:16 frame: full panel on top + animated zoomed detail of the same panel below.
Mode B: if images/scene1.png ... scene6.png exist (vertical 9:16 images), each scene is
shown full screen with camera moves.
Voice-over: if voix/scene1.mp3 ... scene6.mp3 exist they are mixed in at each scene start.
Usage: python3 render2.py out.mp4 [preview]
"""
import sys, os, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
W, H, FPS, DUR = 1080, 1920, 30, 60.0
N = int(FPS * DUR)
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'

BOX = [(0, 0, 548, 471), (558, 0, 1113, 471), (1123, 0, 1672, 471),
       (0, 482, 548, 941), (558, 482, 1113, 941), (1123, 482, 1672, 941)]
# detail keyframes per scene: (time in scene, cx, cy, width) in panel pixels
DET = [
    [(0, 140, 235, 200), (0.5, 140, 235, 260), (4.5, 140, 235, 260), (5.2, 380, 350, 320), (10, 390, 350, 300)],
    [(0, 120, 250, 260), (3.0, 120, 250, 240), (3.4, 450, 215, 240), (6.0, 450, 215, 220), (6.4, 350, 350, 240), (10, 350, 350, 220)],
    [(0, 380, 270, 300), (4.6, 380, 270, 260), (5.0, 130, 280, 260), (7.4, 130, 280, 240), (7.8, 480, 120, 200), (10, 480, 120, 180)],
    [(0, 390, 100, 320), (3.2, 390, 100, 300), (3.6, 220, 320, 300), (6.6, 220, 320, 280), (7.0, 440, 300, 240), (10, 440, 300, 220)],
    [(0, 380, 130, 300), (4.6, 380, 150, 260), (5.0, 380, 230, 280), (10, 380, 230, 220)],
    [(0, 130, 190, 260), (2.6, 130, 190, 240), (3.0, 400, 100, 320), (5.0, 400, 100, 300), (5.4, 400, 340, 300), (10, 400, 340, 270)],
]
TOP_H = 930
DH = H - TOP_H

VO = [
    "Tu veux GTA 6, mais t'as pas d'argent ? Regarde cette vidéo jusqu'à la fin !",
    "Comme beaucoup de joueurs, tu rêves de GTA 6... mais entre les dépenses du quotidien et le prix des jeux, c'est pas toujours facile de se faire plaisir !",
    "Mais attention ! Certains sites promettent GTA 6 gratuit. Ne tombe pas dans le piège : ils veulent juste voler tes infos ou ton argent !",
    "Voici l'astuce : mets un peu d'argent de côté chaque semaine, compare les prix chez les revendeurs fiables et surveille les promos officielles. Chaque euro compte !",
    "Imagine le jour où tu pourras enfin lancer GTA 6, prendre le volant et découvrir tout cet univers. Alors prépare ton budget dès maintenant !",
    "Alors dis-moi en commentaire : tu l'achètes dès sa sortie, ou tu attends une promo ? Et abonne-toi à Cinema Short pour plus d'astuces gaming !",
]
COL = [(200, 70, 255), (255, 200, 40), (255, 40, 60), (60, 230, 120), (255, 80, 200), (200, 70, 255)]
CUTS = [10, 20, 30, 40, 50]

full_imgs = [os.path.join(HERE, 'images', f'scene{i + 1}.png') for i in range(6)]
MODE_B = all(os.path.exists(p) for p in full_imgs)

def enhance(img, k):
    big = img.resize((img.width * k, img.height * k), Image.LANCZOS)
    big = big.filter(ImageFilter.UnsharpMask(radius=2.5, percent=110, threshold=2))
    return ImageEnhance.Color(big).enhance(1.08)

if MODE_B:
    fulls = []
    for p in full_imgs:
        im = Image.open(p).convert('RGB')
        s = max(W * 1.25 / im.width, H * 1.25 / im.height)
        fulls.append(im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS))
else:
    src = Image.open(os.path.join(HERE, 'storyboard2.png')).convert('RGB')
    K = 4
    panels = [enhance(src.crop(b), K) for b in BOX]

# ---------------- helpers ----------------
def lerp(a, b, x): return a + (b - a) * x
def smooth(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)
def ease_back(x):
    x = min(max(x, 0), 1); c = 2.0
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def keyframe(kf, t):
    if t <= kf[0][0]: return kf[0][1:]
    for a, b in zip(kf, kf[1:]):
        if a[0] <= t <= b[0]:
            x = (t - a[0]) / (b[0] - a[0])
            # short segments = fast whip (smoothstep); long ones = linear drift
            x = smooth(x) if b[0] - a[0] < 1 else x
            return tuple(lerp(u, v, x) for u, v in zip(a[1:], b[1:]))
    return kf[-1][1:]

def crop_fill(img, cx, cy, cw, ch, outw, outh):
    cw = min(cw, img.width); ch = min(ch, img.height)
    x0 = min(max(cx - cw / 2, 0), img.width - cw); y0 = min(max(cy - ch / 2, 0), img.height - ch)
    return img.resize((outw, outh), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))

_fc = {}
def font(size):
    if size not in _fc: _fc[size] = ImageFont.truetype(FONT, size)
    return _fc[size]

_tc = {}
def text_img(txt, size, fill=(255, 255, 255), stroke=8, maxw=860, hl='GTA 6'):
    key = (txt, size, fill, stroke)
    if key in _tc: return _tc[key]
    f = font(size)
    while f.getlength(txt) > maxw: size -= 3; f = font(size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    im = Image.new('RGBA', (r - l + 40, b - t + 40), (0, 0, 0, 0))
    x, y = 20 - l, 20 - t
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + 5, y + 7), txt, font=f, fill=(0, 0, 0, 210), stroke_width=stroke, stroke_fill=(0, 0, 0, 210))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(im)
    parts = txt.split(hl) if hl in txt else [txt]
    cx = x
    for k, part in enumerate(parts):
        d.text((cx, y), part, font=f, fill=fill, stroke_width=stroke, stroke_fill='black'); cx += f.getlength(part)
        if k < len(parts) - 1:
            d.text((cx, y), hl, font=f, fill=(255, 70, 200), stroke_width=stroke, stroke_fill='black'); cx += f.getlength(hl)
    _tc[key] = im
    return im

def paste_c(cv, im, cx, cy, scale=1.0, rot=0):
    if scale < 0.02: return
    s = im if scale == 1 else im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot: s = s.rotate(rot, expand=True, resample=Image.BILINEAR)
    cv.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))

def chunks(text, start, end, maxw=4):
    words = text.replace('GTA 6', 'GTA\u00a06').replace(' ?', '\u00a0?').replace(' !', '\u00a0!').replace(' :', '\u00a0:').split(' ')
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or w[-1] in ',!?:.':
            if len(cur) >= 2 or w[-1] in '!?.':
                groups.append(' '.join(cur)); cur = []
    if cur:
        if groups and len(cur) == 1: groups[-1] += ' ' + cur[0]
        else: groups.append(' '.join(cur))
    groups = [g.replace(' ', ' ') for g in groups]
    total = sum(len(g) + 6 for g in groups)
    out, t = [], start
    for g in groups:
        d = (end - start) * (len(g) + 6) / total
        out.append((t, t + d, g)); t += d
    return out

def vo_len(i):
    p = os.path.join(HERE, 'voix', f'scene{i + 1}.mp3')
    if not os.path.exists(p): return None
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip())

SUBS = []
for i, v in enumerate(VO):
    L = vo_len(i)
    SUBS += chunks(v, i * 10 + 0.2, i * 10 + 0.2 + min(L, 9.7) if L else i * 10 + 9.7)

def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

with open(OUT.replace('.mp4', '.srt'), 'w') as f:
    for i, (a, b, g) in enumerate(SUBS, 1):
        f.write(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{g}\n\n')

def rgb_split(img, px):
    r, g, b = img.split()
    r = ImageChops.offset(r, px, 0); b = ImageChops.offset(b, -px, 0)
    return Image.merge('RGB', (r, g, b))

# light sweep texture
sweep = Image.new('L', (W, H), 0)
ImageDraw.Draw(sweep).polygon([(0, 0), (160, 0), (-200, H), (-360, H)], fill=110)
sweep = sweep.filter(ImageFilter.GaussianBlur(40))

# ---------------- frame ----------------
def render(n):
    t = n / FPS
    si = min(int(t // 10), 5); lt = t - si * 10
    # punch: zoom kick at scene start and on detail jumps
    kicks = [0] + [k[0] for k in DET[si][1:] if 0 < k[0] < 10 and DET[si][DET[si].index(k) - 1][0] < k[0] - 1]
    punch = max([max(0, 1 - (lt - k) / 0.35) for k in kicks if lt >= k] + [0])
    shake = 0
    if si == 2 and 4.6 < lt < 6.2: shake = 10
    if lt < 0.3: shake = 14 * (1 - lt / 0.3)
    sx = math.sin(t * 71) * shake; sy = math.cos(t * 63) * shake

    if MODE_B:
        im = fulls[si]
        z = 1.0 + 0.12 * lt / 10 + 0.08 * punch
        cw, ch = im.width / 1.25 / z, im.height / 1.25 / z
        cx = im.width / 2 + math.sin(lt * 0.4) * im.width * 0.04 + sx
        cy = im.height / 2 + sy
        frame = crop_fill(im, cx, cy, cw, ch, W, H)
    else:
        p = panels[si]
        Kp = p.width / (BOX[si][2] - BOX[si][0])
        # top: whole panel, cover-filled to 1080x930, slow push-in
        z = 1.0 + 0.06 * lt / 10 + 0.05 * punch
        aspect = W / TOP_H
        ch = min(p.height, p.width / aspect) / z; cw = ch * aspect
        top = crop_fill(p, p.width / 2 + sx, p.height / 2 + sy, cw, ch, W, TOP_H)
        # bottom: animated detail
        cx, cy, wd = keyframe(DET[si], lt)
        wd = wd * Kp / (1 + 0.10 * punch)
        det = crop_fill(p, cx * Kp - sx, cy * Kp - sy, wd, wd * DH / W, W, DH)
        frame = Image.new('RGB', (W, H))
        # scene entry: slide the two halves in from opposite sides
        e = 1 - smooth(lt / 0.28) if si > 0 else 0
        frame.paste(top, (int(e * W), 0)); frame.paste(det, (int(-e * W), TOP_H))
        if si > 0 and e > 0:
            prev = panels[si - 1]
            frame.paste(Image.new('RGB', (W, H), COL[si]).resize((int(e * W) + 1, TOP_H)), (0, 0))
    if si == 2 and 4.6 < lt < 6.2 and int(lt * 15) % 2 == 0:
        frame = rgb_split(frame, 14)
    cv = frame.convert('RGBA')

    if not MODE_B:
        # neon divider
        d = ImageDraw.Draw(cv)
        c = COL[si]
        glow = Image.new('RGBA', (W, 60), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle((0, 24, W, 36), fill=c + (255,))
        cv.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)), (0, TOP_H - 30))
        d.rectangle((0, TOP_H - 4, W, TOP_H + 4), fill=(255, 255, 255))

    # scene-specific overlays
    if si == 2 and lt > 4.6:
        a = int(95 * (0.5 + 0.5 * math.sin((lt - 4.6) * 11))) if lt < 8.5 else 40
        cv.alpha_composite(Image.new('RGBA', (W, H), (255, 0, 30, a)))
        if lt < 8.5:
            al = text_img('⚠ ARNAQUE ⚠', 130, (255, 255, 255), 12)
            paste_c(cv, al, W / 2, TOP_H + 260, ease_back((lt - 4.6) / 0.3) * (1 + 0.05 * math.sin(lt * 14)), rot=-6)
    if si == 4:
        x = int(((lt / 2.5) % 1) * (W + 900)) - 300
        layer = Image.new('RGBA', (W, H), (255, 220, 255, 0)); layer.putalpha(ImageChops.offset(sweep, x, 0))
        cv.alpha_composite(layer)
    if si == 5 and lt > 5.4:
        # pulsing ring around OUI OU NON area
        pul = 0.5 + 0.5 * math.sin(lt * 8)
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle((20, TOP_H + 20, W - 20, H - 20), outline=(255, 230, 40, int(160 + 90 * pul)), width=12)
        cv.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4)))

    # subtitles (word-pop)
    for a, b, g in SUBS:
        if a <= t < b:
            im = text_img(g, 72, (255, 255, 255), 9)
            paste_c(cv, im, W / 2, 1540, 0.8 + 0.2 * ease_back((t - a) / 0.16))
            break
    # cut flash
    for c in CUTS:
        if c <= t < c + 0.15:
            cv.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(220 * (1 - (t - c) / 0.15)))))
    if t < 0.12:
        cv.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * (1 - t / 0.12)))))
    if t > 59.55:
        cv.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(255 * min(1, (t - 59.55) / 0.45)))))
    return cv.convert('RGB')

# ---------------- audio ----------------
SR = 44100
def load_vo(i):
    p = os.path.join(HERE, 'voix', f'scene{i + 1}.mp3')
    if not os.path.exists(p): return None
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768

def build_audio(path):
    L = int(SR * DUR); music = np.zeros(L); sfx = np.zeros(L); voice = np.zeros(L)
    rng = np.random.default_rng(3)
    def add(buf, sig, at, gain=1.0):
        i = int(at * SR); j = min(L, i + len(sig))
        if 0 <= i < L: buf[i:j] += sig[:j - i] * gain
    def x_(d): return np.arange(int(d * SR)) / SR
    def kick():
        x = x_(0.35); f = 48 + 130 * np.exp(-x * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)
    def hat(): x = x_(0.05); return rng.standard_normal(len(x)) * np.exp(-x * 80) * 0.3
    def snare():
        x = x_(0.22); return (rng.standard_normal(len(x)) * 0.6 + np.sin(2 * np.pi * 190 * x) * 0.5) * np.exp(-x * 17)
    beat = 0.5; roots = [110.0, 87.31, 130.81, 98.0]
    for b in range(int(DUR / beat)):
        t0 = b * beat; sc = min(int(t0 // 10), 5)
        if sc == 2:
            if b % 4 == 0: add(music, kick(), t0, 0.8)
            if b % 8 == 4: add(music, snare(), t0, 0.25)
        else:
            add(music, kick(), t0, 0.9)
            if b % 2: add(music, snare(), t0, 0.45 if sc >= 3 else 0.32)
        for h in range(2): add(music, hat(), t0 + h * 0.25 + 0.125, 0.6 if sc != 2 else 0.2)
        r = roots[(b // 4) % 4]
        for h in range(2):
            x = x_(0.25); saw = 2 * ((x * r) % 1) - 1
            add(music, saw * np.exp(-x * 6) * 0.22, t0 + h * 0.25)
    for bar in range(int(DUR / 2)):
        t0 = bar * 2; r = roots[bar % 4] * 2; x = x_(2)
        sig = sum(np.sin(2 * np.pi * r * m * x + np.sin(2 * np.pi * 0.3 * x)) for m in (1, 1.189, 1.498)) / 3
        add(music, sig * np.minimum(1, x / 0.3) * np.minimum(1, (2 - x) / 0.3), t0, 0.12 if t0 < 40 else 0.2)
    for st in (38.0, 48.0):
        x = x_(2.0); add(music, rng.standard_normal(len(x)) * (x / 2) ** 2 * 0.25, st)
    # sfx
    def impact():
        x = x_(0.8); return (np.sin(2 * np.pi * (40 + 60 * np.exp(-x * 8)) * x) + rng.standard_normal(len(x)) * 0.4 * np.exp(-x * 20)) * np.exp(-x * 4)
    def whoosh():
        x = x_(0.35); n = np.convolve(rng.standard_normal(len(x)), np.ones(8) / 8, 'same'); return n * np.sin(np.pi * x / 0.35) * 0.7
    def ping(f=1320):
        x = x_(0.4); return (np.sin(2 * np.pi * f * x) + 0.5 * np.sin(3 * np.pi * f * x)) * np.exp(-x * 9) * 0.5
    def coin(): return np.concatenate([ping(1975)[:int(0.08 * SR)], ping(2637)]) * 0.8
    def alarm():
        x = x_(1.2); f = 700 + 300 * (np.sin(2 * np.pi * 3 * x) > 0)
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.16 * np.minimum(1, (1.2 - x) * 5)
    def boing():
        x = x_(0.5); f = 500 * np.exp(-x * 3); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 5) * 0.5
    def swish():
        x = x_(0.18); n = np.diff(rng.standard_normal(len(x) + 1)); return n * np.sin(np.pi * x / 0.18) * 0.25
    add(sfx, impact(), 0.0, 1.0)
    for c in CUTS: add(sfx, whoosh(), c - 0.2, 0.9); add(sfx, impact(), c, 0.5)
    for si, kf in enumerate(DET):
        for a, b in zip(kf, kf[1:]):
            if b[0] - a[0] < 1: add(sfx, swish(), si * 10 + a[0], 0.8)
    add(sfx, boing(), 12.8); add(sfx, boing(), 16.4)
    for k in range(3): add(sfx, ping(), 20.6 + k * 1.3)
    add(sfx, alarm(), 24.6); add(sfx, alarm(), 25.8)
    for k in range(8): add(sfx, coin(), 33.6 + k * 0.38, 0.6)
    for k in range(3): add(sfx, ping(1760), 30.3 + k * 0.5, 0.4)
    add(sfx, impact(), 55.4, 0.9); add(sfx, impact(), 59.4, 1.2)
    has_vo = False
    for i in range(6):
        v = load_vo(i)
        if v is not None:
            has_vo = True; add(voice, v, i * 10 + 0.2, 1.0)
    if has_vo:
        envl = np.convolve(np.abs(voice), np.ones(4410) / 4410, 'same')
        duck = 1 - 0.6 * np.clip(envl * 12, 0, 1)
        music *= duck; sfx *= 0.7
    a = music * 0.5 + sfx * 0.6 + voice * 1.1
    a = np.tanh(a * 1.2) * 0.9
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())

if __name__ == '__main__':
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[2] == 'preview':
        ts = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else [0.5, 3, 6, 12, 15, 18, 23, 26, 35, 45, 52, 57]
        sheet = Image.new('RGB', (6 * 270, ((len(ts) + 5) // 6) * 480))
        for i, tsec in enumerate(ts):
            sheet.paste(render(int(tsec * FPS)).resize((270, 480)), ((i % 6) * 270, (i // 6) * 480))
        sheet.save(OUT.replace('.mp4', '_sheet.jpg'), quality=85); sys.exit()
    wav = OUT.replace('.mp4', '.wav'); build_audio(wav)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
                          '-movflags', '+faststart', '-shortest', OUT], stdin=subprocess.PIPE)
    for n in range(N):
        p.stdin.write(render(n).tobytes())
        if n % 300 == 0: print(n, flush=True)
    p.stdin.close(); p.wait(); os.remove(wav); print('done')

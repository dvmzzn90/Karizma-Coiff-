"""Stickman classroom cartoon — 'IL A DÉTRUIT LE COURS'. 1080x1920 @30fps."""
import cairo, math, sys, subprocess, os
import numpy as np

W, H, FPS = 1080, 1920, 30
DUR = 35.0
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, t): return a + (b - a) * t
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def ramp(t, a, b): return ease((t - a) / (b - a)) if b > a else float(t >= a)
def lin(t, a, b): return clamp((t - a) / (b - a))
def back_out(t):
    t = clamp(t); c1 = 1.9; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
def noise(t, seed=0.0):
    return (math.sin(t * 37.1 + seed * 13.7) * 0.5 + math.sin(t * 61.3 + seed * 7.1) * 0.3
            + math.sin(t * 91.7 + seed * 3.3) * 0.2)

BLACK = (0.07, 0.07, 0.08)
WALL = (0.97, 0.93, 0.83)
WALL_DARK = (0.90, 0.84, 0.72)
FLOOR = (0.80, 0.72, 0.62)
FLOOR_LINE = (0.70, 0.62, 0.52)
BOARD = (0.15, 0.32, 0.25)
WOOD = (0.55, 0.36, 0.20)
DESK = (0.86, 0.66, 0.44)
DESK_D = (0.72, 0.52, 0.33)
CHAIR = (0.30, 0.45, 0.70)
TEAR = (0.45, 0.75, 1.0)
GREEN = (0.45, 0.80, 0.18)

def rgb(ctx, c, a=1.0):
    if len(c) == 4: ctx.set_source_rgba(*c)
    else: ctx.set_source_rgba(c[0], c[1], c[2], a)

def line(ctx, pts, lw, col=BLACK, a=1.0):
    ctx.move_to(*pts[0])
    for p in pts[1:]: ctx.line_to(*p)
    ctx.set_line_width(lw); ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    rgb(ctx, col, a); ctx.stroke()

def circle(ctx, x, y, r, fill=None, stroke=None, lw=4, a=1.0):
    ctx.new_sub_path(); ctx.arc(x, y, r, 0, 2 * math.pi)
    if fill is not None:
        rgb(ctx, fill, a)
        if stroke is not None: ctx.fill_preserve()
        else: ctx.fill()
    if stroke is not None:
        rgb(ctx, stroke, a); ctx.set_line_width(lw); ctx.stroke()

def rect(ctx, x, y, w, h, fill=None, stroke=None, lw=4):
    ctx.rectangle(x, y, w, h)
    if fill is not None:
        rgb(ctx, fill)
        if stroke is not None: ctx.fill_preserve()
        else: ctx.fill()
    if stroke is not None:
        rgb(ctx, stroke); ctx.set_line_width(lw); ctx.set_line_join(cairo.LINE_JOIN_ROUND); ctx.stroke()

def rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()

def font(ctx, size, bold=True):
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)

def outlined_text(ctx, txt, x, y, size, fill=(1, 1, 1), stroke=BLACK, lw=None, angle=0.0, scale=1.0, a=1.0, center=True):
    if scale <= 0.01 or a <= 0.01: return
    ctx.save(); ctx.translate(x, y); ctx.rotate(angle); ctx.scale(scale, scale)
    font(ctx, size)
    ext = ctx.text_extents(txt)
    dx = -(ext.x_bearing + ext.width / 2) if center else 0
    dy = -(ext.y_bearing + ext.height / 2) if center else 0
    ctx.move_to(dx, dy); ctx.text_path(txt)
    lw = lw if lw is not None else size * 0.16
    rgb(ctx, stroke, a); ctx.set_line_width(lw); ctx.set_line_join(cairo.LINE_JOIN_ROUND); ctx.stroke_preserve()
    rgb(ctx, fill, a); ctx.fill()
    ctx.restore()

def ik(sx, sy, tx, ty, L1, L2, bend):
    dx, dy = tx - sx, ty - sy
    d = math.hypot(dx, dy) + 1e-6
    if d >= L1 + L2:  # stretch: elbow at midpoint
        return ((sx + tx) / 2, (sy + ty) / 2)
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    mx, my = sx + dx * a / d, sy + dy * a / d
    return (mx - bend * h * dy / d, my + bend * h * dx / d)

# ---------------------------------------------------------------- face
def head_fill(blush):
    b = clamp(blush)
    return (1.0, 1.0 - 0.62 * b, 1.0 - 0.66 * b)

def draw_face(ctx, hx, hy, R, ex, t, turn=1.0):
    if turn <= 0.08: return
    k = turn
    ox = (1 - turn) * 0.7 * R
    lw = 0.075 * R
    look = ex.get('look', (0, 0))
    eyes = ex.get('eyes', 'dot'); mouth = ex.get('mouth', 'flat'); brows = ex.get('brows')
    edy = ex.get('eye_dy', 0.0) * R
    ey = hy - 0.08 * R + edy
    lx, ly = look[0] * 0.09 * R, look[1] * 0.08 * R
    X = lambda dx: hx + ox + dx * k
    # cheeks
    if ex.get('cheeks', 0) > 0:
        for sd in (-1, 1):
            ctx.save(); ctx.translate(X(sd * 0.52 * R), hy + 0.25 * R + edy); ctx.scale(k, 0.6)
            circle(ctx, 0, 0, 0.16 * R, fill=(1.0, 0.45, 0.45), a=0.55 * ex['cheeks']); ctx.restore()
    for sd in (-1, 1):
        exx = X(sd * 0.36 * R)
        if eyes == 'dot':
            circle(ctx, exx + lx, ey + ly, 0.105 * R, fill=BLACK)
        elif eyes in ('big', 'shock'):
            r = 0.21 * R if eyes == 'big' else 0.24 * R
            ctx.save(); ctx.translate(exx, ey); ctx.scale(k, 1)
            circle(ctx, 0, 0, r, fill=(1, 1, 1), stroke=BLACK, lw=lw * 0.8); ctx.restore()
            pr = 0.10 * R if eyes == 'big' else 0.05 * R
            circle(ctx, exx + lx * 1.2, ey + ly * 1.2, pr, fill=BLACK)
        elif eyes == 'happy':
            line(ctx, [(exx - 0.14 * R * k, ey + 0.05 * R), (exx, ey - 0.09 * R), (exx + 0.14 * R * k, ey + 0.05 * R)], lw)
        elif eyes == 'squeeze':
            line(ctx, [(exx - sd * 0.13 * R * k, ey - 0.11 * R), (exx + sd * 0.11 * R * k, ey), (exx - sd * 0.13 * R * k, ey + 0.11 * R)], lw)
        elif eyes == 'half':
            ctx.save(); ctx.new_path()
            ctx.arc(exx + lx, ey + 0.02 * R, 0.12 * R, 0, math.pi); ctx.close_path(); rgb(ctx, BLACK); ctx.fill(); ctx.restore()
            line(ctx, [(exx - 0.17 * R * k, ey + 0.02 * R), (exx + 0.17 * R * k, ey + 0.02 * R)], lw)
        elif eyes == 'closed':
            line(ctx, [(exx - 0.13 * R * k, ey), (exx + 0.13 * R * k, ey)], lw)
        elif eyes == 'sad':
            circle(ctx, exx + lx, ey + ly + 0.04 * R, 0.09 * R, fill=BLACK)
        # corner tears
        tr = ex.get('tears', 0)
        if tr > 0:
            tx, ty = exx + sd * 0.2 * R * k, ey + 0.1 * R
            r = 0.09 * R * tr
            ctx.new_path(); ctx.move_to(tx, ty - r * 1.9)
            ctx.curve_to(tx + r * 1.1, ty - 0.2 * r, tx + r, ty + r, tx, ty + r)
            ctx.curve_to(tx - r, ty + r, tx - r * 1.1, ty - 0.2 * r, tx, ty - r * 1.9)
            rgb(ctx, TEAR); ctx.fill_preserve(); rgb(ctx, (0.2, 0.45, 0.8)); ctx.set_line_width(lw * 0.4); ctx.stroke()
        if ex.get('streams', 0) > 0:
            s = ex['streams']
            pts = []
            for i in range(9):
                u = i / 8
                pts.append((exx + sd * (0.12 + 0.25 * u) * R * k + math.sin(t * 20 + u * 6) * 0.03 * R,
                            ey + 0.08 * R + u * 1.15 * R * s))
            line(ctx, pts, 0.11 * R, TEAR, 0.95)
            # flying droplets
            for j in range(4):
                ph = (t * 2.4 + j * 0.25 + (0.5 if sd > 0 else 0)) % 1.0
                dx = sd * (0.2 + ph * 0.9) * R
                dy = -0.15 * R + (ph * ph * 1.6 - ph * 0.6) * R
                circle(ctx, exx + dx, ey + dy, 0.05 * R * (1 - ph * 0.5), fill=TEAR, a=1 - ph)
    # brows
    by = ey - 0.27 * R
    if brows == 'raise_one':
        line(ctx, [(X(-0.52 * R), by - 0.06 * R), (X(-0.36 * R), by - 0.16 * R), (X(-0.2 * R), by - 0.08 * R)], lw)
        line(ctx, [(X(0.2 * R), by + 0.06 * R), (X(0.52 * R), by - 0.02 * R)], lw)
    elif brows == 'worried':
        for sd in (-1, 1):
            line(ctx, [(X(sd * 0.18 * R), by - 0.08 * R), (X(sd * 0.5 * R), by + 0.04 * R)], lw)
    elif brows == 'up':
        for sd in (-1, 1):
            line(ctx, [(X(sd * 0.2 * R), by - 0.12 * R), (X(sd * 0.36 * R), by - 0.18 * R), (X(sd * 0.52 * R), by - 0.12 * R)], lw)
    elif brows == 'angry':
        for sd in (-1, 1):
            line(ctx, [(X(sd * 0.16 * R), by + 0.06 * R), (X(sd * 0.5 * R), by - 0.06 * R)], lw)
    elif brows == 'flat':
        for sd in (-1, 1):
            line(ctx, [(X(sd * 0.2 * R), by), (X(sd * 0.5 * R), by)], lw)
    # mouth
    mx = X(0); my = hy + 0.4 * R + ex.get('mouth_dy', 0) * R
    if mouth == 'smile':
        ctx.new_path(); ctx.save(); ctx.translate(mx, my - 0.15 * R); ctx.scale(k, 1)
        ctx.arc(0, 0, 0.24 * R, math.radians(25), math.radians(155)); ctx.restore()
        rgb(ctx, BLACK); ctx.set_line_width(lw); ctx.stroke()
    elif mouth == 'smirk':
        ctx.new_path(); ctx.move_to(mx - 0.18 * R * k, my - 0.02 * R)
        ctx.curve_to(mx - 0.05 * R * k, my + 0.08 * R, mx + 0.12 * R * k, my + 0.04 * R, mx + 0.24 * R * k, my - 0.12 * R)
        rgb(ctx, BLACK); ctx.set_line_width(lw); ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.stroke()
    elif mouth == 'flat':
        line(ctx, [(mx - 0.17 * R * k, my), (mx + 0.17 * R * k, my)], lw)
    elif mouth == 'frown':
        ctx.new_path(); ctx.save(); ctx.translate(mx, my + 0.15 * R); ctx.scale(k, 1)
        ctx.arc(0, 0, 0.2 * R, math.radians(205), math.radians(335)); ctx.restore()
        rgb(ctx, BLACK); ctx.set_line_width(lw); ctx.stroke()
    elif mouth in ('O', 'bigO'):
        rx, ry = (0.09, 0.12) if mouth == 'O' else (0.15, 0.21)
        ctx.save(); ctx.translate(mx, my + 0.02 * R); ctx.scale(rx * R * k, ry * R)
        ctx.new_path(); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore(); rgb(ctx, BLACK); ctx.fill()
    elif mouth == 'laugh':
        op = ex.get('open', 1.0)
        w = 0.3 * R * k; top = my - 0.1 * R; bot = my + (0.12 + 0.28 * op) * R
        ctx.new_path(); ctx.move_to(mx - w, top); ctx.line_to(mx + w, top)
        ctx.curve_to(mx + w, bot, mx - w, bot, mx - w, top); ctx.close_path()
        rgb(ctx, BLACK); ctx.fill_preserve(); ctx.save(); ctx.clip()
        ctx.save(); ctx.translate(mx, bot); ctx.scale(1, 0.6)
        circle(ctx, 0, 0, 0.17 * R, fill=(0.95, 0.35, 0.35)); ctx.restore(); ctx.restore()
    elif mouth == 'wavy':
        pts = [(mx + (u - 0.5) * 0.4 * R * k, my + math.sin(u * 4 * math.pi + t * 30) * 0.03 * R) for u in np.linspace(0, 1, 12)]
        line(ctx, pts, lw)
        for sd in (-1, 1):  # puffed cheeks hint
            line(ctx, [(mx + sd * 0.23 * R * k, my - 0.05 * R), (mx + sd * 0.27 * R * k, my), (mx + sd * 0.23 * R * k, my + 0.05 * R)], lw * 0.6)
    elif mouth == 'wobble':
        pts = [(mx + (u - 0.5) * 0.36 * R * k, my + math.sin(u * 3 * math.pi) * 0.05 * R) for u in np.linspace(0, 1, 12)]
        line(ctx, pts, lw)
    elif mouth == 'grit':
        rrect(ctx, mx - 0.24 * R * k, my - 0.08 * R, 0.48 * R * k, 0.16 * R, 0.05 * R)
        rgb(ctx, (1, 1, 1)); ctx.fill_preserve(); rgb(ctx, BLACK); ctx.set_line_width(lw * 0.8); ctx.stroke()
        line(ctx, [(mx - 0.24 * R * k, my), (mx + 0.24 * R * k, my)], lw * 0.5)
    # sweat
    if ex.get('sweat', 0) > 0:
        s = ex['sweat']; ph = (t * 0.8) % 1.0
        for j, (sx, sy0) in enumerate(((0.75, -0.55), (-0.8, -0.35))):
            if j == 1 and s < 0.6: continue
            x = hx + sx * R; y = hy + sy0 * R + ph * 0.25 * R
            r = 0.1 * R
            ctx.new_path(); ctx.move_to(x, y - r * 2.2)
            ctx.curve_to(x + r * 1.2, y - 0.2 * r, x + r, y + r, x, y + r)
            ctx.curve_to(x - r, y + r, x - r * 1.2, y - 0.2 * r, x, y - r * 2.2)
            rgb(ctx, TEAR); ctx.fill_preserve(); rgb(ctx, (0.2, 0.45, 0.8)); ctx.set_line_width(lw * 0.45); ctx.stroke()

# ---------------------------------------------------------------- stickman
ARM = {  # left arm (viewer-left), relative to shoulder: elbow, hand  (units of s)
    'rest': ((-46, 56), (-6, 56)),
    'down': ((-16, 36), (-22, 74)),
    'belly': ((-34, 26), (-6, 40)),
    'slap_up': ((-44, -2), (-52, -38)),
    'slap_down': ((-42, 32), (-34, 54)),
    'up': ((-34, -26), (-50, -64)),
    'wipe': ((-36, 20), (-18, -30)),
    'face': ((-30, 20), (-12, -26)),
    'back_desk': ((-30, 26), (-26, 10)),
    'cheer': ((-40, -20), (-46, -60)),
    'hips': ((-36, 20), (-12, 50)),
}

def arm_pts(spec, side, s, sx, sy, R):
    if isinstance(spec, str): spec = ARM[spec]
    if spec[0] == 'ik':  # ('ik', (tx,ty) absolute, bend)
        tx, ty = spec[1]
        L = 40 * s if len(spec) < 4 else spec[3] * s
        e = ik(sx, sy, tx, ty, L, L, spec[2] * side)
        return [(sx, sy), e, (tx, ty)]
    (ex_, ey_), (hx_, hy_) = spec
    if side > 0: ex_, hx_ = -ex_, -hx_
    return [(sx, sy), (sx + ex_ * s, sy + ey_ * s), (sx + hx_ * s, sy + hy_ * s)]

def stick(ctx, x, y, s, ex=None, t=0.0, arms=('rest', 'rest'), legs=None, back=False, lean=(0, 0),
          head_off=(0, 0), part='all', turn=1.0, chalk=None, torso=85, hip=None):
    """(x, y) = neck base position before lean. part: 'all' | 'body' | 'top'."""
    R = 34 * s
    lw = 7.5 * s
    hipx, hipy = hip if hip else (x, y + torso * s)
    nx, ny = x + lean[0] * s, y + lean[1] * s
    hx, hy = nx + head_off[0] * s, ny - (R + 3 * s) + head_off[1] * s
    sx, sy = lerp(nx, hipx, 0.13), lerp(ny, hipy, 0.13)
    ex = ex or {}
    if part in ('all', 'body'):
        if legs:
            for side, spec in ((-1, legs[0]), (1, legs[1])):
                (kx, ky), (fx, fy) = spec
                if side > 0 and not isinstance(legs, dict): pass
                line(ctx, [(hipx, hipy), (hipx + kx * s, hipy + ky * s), (hipx + fx * s, hipy + fy * s)], lw)
        line(ctx, [(nx, ny), (hipx, hipy)], lw)
    if part in ('all', 'top'):
        pts = []
        for side, spec in ((-1, arms[0]), (1, arms[1])):
            p = arm_pts(spec, side, s, sx, sy, R)
            line(ctx, p, lw)
            pts.append(p)
        if chalk:
            px, py = pts[1][2] if chalk == 'R' else pts[0][2]
            ctx.save(); ctx.translate(px, py); ctx.rotate(-0.6)
            rect(ctx, -3 * s, -9 * s, 6 * s, 14 * s, fill=(1, 1, 1), stroke=BLACK, lw=1.5 * s); ctx.restore()
        circle(ctx, hx, hy, R, fill=head_fill(ex.get('blush', 0)), stroke=BLACK, lw=6 * s)
        if not back:
            draw_face(ctx, hx, hy, R, ex, t, turn)
    return dict(head=(hx, hy), R=R, shoulder=(sx, sy), neck=(nx, ny))

# ---------------------------------------------------------------- furniture
def desk_front(ctx, cx, top, w, s):
    th = 14 * s; ph = 96 * s
    ctx.new_path(); ctx.move_to(cx - w / 2 - 6 * s, top); ctx.line_to(cx + w / 2 + 6 * s, top)
    ctx.line_to(cx + w / 2, top + th); ctx.line_to(cx - w / 2, top + th); ctx.close_path()
    rgb(ctx, DESK); ctx.fill_preserve(); rgb(ctx, BLACK); ctx.set_line_width(4 * s); ctx.stroke()
    rect(ctx, cx - w / 2 + 8 * s, top + th, w - 16 * s, ph, fill=DESK_D, stroke=BLACK, lw=4 * s)
    for sd in (-1, 1):
        line(ctx, [(cx + sd * (w / 2 - 18 * s), top + th + ph), (cx + sd * (w / 2 - 18 * s), top + th + ph + 46 * s)], 6 * s)

def desk_back(ctx, cx, top, w, s):
    th = 16 * s
    ctx.new_path(); ctx.move_to(cx - w / 2 + 10 * s, top); ctx.line_to(cx + w / 2 - 10 * s, top)
    ctx.line_to(cx + w / 2, top + th); ctx.line_to(cx - w / 2, top + th); ctx.close_path()
    rgb(ctx, DESK); ctx.fill_preserve(); rgb(ctx, BLACK); ctx.set_line_width(4 * s); ctx.stroke()
    for sd in (-1, 1):
        line(ctx, [(cx + sd * (w / 2 - 12 * s), top + th), (cx + sd * (w / 2 - 12 * s), top + th + 70 * s)], 5 * s)

def chair_back(ctx, cx, y, s):
    rrect(ctx, cx - 30 * s, y, 60 * s, 30 * s, 6 * s); rgb(ctx, CHAIR); ctx.fill_preserve()
    rgb(ctx, BLACK); ctx.set_line_width(4 * s); ctx.stroke()
    for sd in (-1, 1):
        line(ctx, [(cx + sd * 24 * s, y + 30 * s), (cx + sd * 24 * s, y + 90 * s)], 5 * s)

# ---------------------------------------------------------------- board
BOARD_LINES = ["2x + 3 = 7", "2x = 4", "x = 2"]

def board_prog(t):
    p = 2.0 * lin(t, 0.6, 3.8)
    if t >= 13.0: p = 2.0 + 0.25 * lin(t, 13.0, 13.25)
    if t >= 18.6: p = 2.25 + 0.75 * lin(t, 18.6, 20.4)
    return p

def draw_board(ctx, x0, y0, w, h, prog):
    """returns chalk cursor position"""
    rect(ctx, x0 - 0.025 * w, y0 - 0.025 * w, w * 1.05, h + 0.05 * w, fill=WOOD, stroke=BLACK, lw=5)
    rect(ctx, x0, y0, w, h, fill=BOARD, stroke=BLACK, lw=4)
    # chalk smudges
    for i in range(5):
        ctx.save(); ctx.translate(x0 + w * (0.15 + 0.17 * i), y0 + h * (0.2 + 0.13 * (i % 3))); ctx.scale(1, 0.35)
        circle(ctx, 0, 0, w * 0.08, fill=(1, 1, 1), a=0.035); ctx.restore()
    # tray
    rect(ctx, x0 + 0.05 * w, y0 + h + 0.005 * w, 0.9 * w, 0.025 * w, fill=WOOD, stroke=BLACK, lw=3)
    fs = h * 0.17
    font(ctx, fs, bold=False)
    cur = (x0 + 0.1 * w, y0 + h * 0.3)
    for i, txt in enumerate(BOARD_LINES):
        frac = clamp(prog - i)
        if frac <= 0: break
        bx, by = x0 + 0.1 * w, y0 + h * (0.3 + 0.27 * i)
        n = len(txt); shown = txt[:int(math.ceil(frac * n))] if frac < 1 else txt
        ctx.move_to(bx, by); rgb(ctx, (0.97, 0.97, 0.95), 0.92); ctx.show_text(shown)
        ext = ctx.text_extents(shown)
        cur = (bx + ext.x_advance, by - fs * 0.3)
    return cur

# ---------------------------------------------------------------- scenes
def wall_and_floor(ctx, floor_y):
    rect(ctx, -400, -400, W + 800, floor_y + 400, fill=WALL)
    rect(ctx, -400, floor_y - 30, W + 800, 30, fill=WALL_DARK)
    rect(ctx, -400, floor_y, W + 800, H + 800, fill=FLOOR)
    line(ctx, [(-400, floor_y), (W + 400, floor_y)], 4)
    for i in range(-6, 14):
        line(ctx, [(540 + i * 140 * 0.4, floor_y), (540 + i * 140 * 2.2, H + 400)], 2, FLOOR_LINE)

# --- layout of students in front view (B)
ROWS_B = [(1530, 1.32), (1215, 1.12), (950, 0.94)]  # row0 = front row (closest to camera)
COLS = [-340, -160, 160, 340]

def pos_b(r, c):
    y, s = ROWS_B[r]
    return 540 + COLS[c] * s / 1.2, y, s

CULPRIT = (1, 0)
BUDDY = (1, 1)
LAUGH_START = {}  # filled below

def laugh_ex(t, i, start, crying=False):
    a = t - start
    op = 0.55 + 0.45 * abs(math.sin(t * 9 + i))
    ex = dict(eyes='happy' if (i % 3) else 'squeeze', mouth='laugh', open=op, blush=0.15)
    if crying or i % 4 == 1:
        ex['tears'] = 1.0
    if crying:
        ex['streams'] = clamp(a / 0.8); ex['eyes'] = 'squeeze'; ex['blush'] = 0.6
    return ex

def laugh_arms(t, i):
    kind = i % 4
    if kind == 0: return ('belly', 'belly')
    if kind == 1:
        up = math.sin(t * 22 + i) > 0
        return ('slap_up' if up else 'slap_down', 'slap_down' if up else 'slap_up')
    if kind == 2: return ('belly', 'slap_up' if math.sin(t * 20 + i) > 0 else 'slap_down')
    return ('wipe', 'belly')

def ha_particles(ctx, x, y, s, t, start, i):
    for k in range(40):
        st = start + k * 0.55 + (i * 0.17) % 0.5
        age = t - st
        if age < 0: break
        if age > 1.0: continue
        side = 1 if (k + i) % 2 else -1
        outlined_text(ctx, "HA" if k % 3 else "HAHA", x + side * (60 + age * 50) * s, y - 40 * s - age * 90 * s,
                      26 * s, fill=(1.0, 0.85, 0.2), lw=5 * s, angle=side * 0.2, scale=back_out(age * 4), a=1 - age ** 2)

def scene_front(ctx, t, mode):
    """Front wide view of the class (camera at the board). mode: 'serious' | 'laugh' | 'run'"""
    wall_and_floor(ctx, 880)
    # windows, poster, clock, door
    for wx in (90, 330):
        rect(ctx, wx, 300, 170, 230, fill=(0.75, 0.90, 1.0), stroke=BLACK, lw=5)
        line(ctx, [(wx + 85, 300), (wx + 85, 530)], 4); line(ctx, [(wx, 415), (wx + 170, 415)], 4)
    circle(ctx, 640, 250, 46, fill=(1, 1, 1), stroke=BLACK, lw=5)
    line(ctx, [(640, 250), (640, 220)], 5); line(ctx, [(640, 250), (662, 262)], 5)
    rect(ctx, 560, 380, 170, 120, fill=(1.0, 0.95, 0.6), stroke=BLACK, lw=4)
    font(ctx, 30); ctx.move_to(585, 450); rgb(ctx, BLACK); ctx.show_text("π = 3,14")
    # door
    door_open = 0.0
    if mode == 'run':
        door_open = ramp(t, 28.9, 29.2) * (1 - ramp(t, 29.95, 30.05))
    dx0, dy0, dw, dh = 870, 450, 165, 430
    rect(ctx, dx0 - 10, dy0 - 10, dw + 20, dh + 10, fill=WOOD, stroke=BLACK, lw=5)
    rect(ctx, dx0, dy0, dw, dh, fill=(0.18, 0.15, 0.13))
    if door_open < 0.98:
        pw = dw * (1 - door_open * 0.85)
        rect(ctx, dx0, dy0, pw, dh, fill=(0.68, 0.45, 0.26), stroke=BLACK, lw=4)
        circle(ctx, dx0 + pw - 22, dy0 + dh * 0.52, 9, fill=(0.95, 0.8, 0.3), stroke=BLACK, lw=3)
    # students, back row first
    run_t = None
    for r in (2, 1, 0):
        studs = []
        for c in range(4):
            x, y, s = pos_b(r, c)
            idx = r * 4 + c
            if mode == 'run' and (r, c) == CULPRIT and t >= 27.9:
                continue
            bob = 0; jit = (0, 0)
            ex = dict(eyes='dot', mouth='flat'); arms = ('rest', 'rest'); head_off = (0, 0)
            if (r, c) == BUDDY:
                if mode == 'serious':
                    ex = dict(eyes='squeeze', mouth='wavy', blush=0.85, tears=0.8, eye_dy=0.15, mouth_dy=0.05)
                    head_off = (0, 16 * ramp(t, 15.4, 15.9)); jit = (noise(t, 5) * 2.5 * s, noise(t, 9) * 1.5 * s)
                    arms = ('rest', 'rest')
                else:
                    ex = laugh_ex(t, idx, 19.6, crying=True); arms = ('wipe', 'belly') if math.sin(t * 2) > 0 else ('slap_up', 'belly')
                    bob = abs(math.sin(t * 11)) * 7 * s; jit = (noise(t, 3) * 3 * s, 0)
            elif (r, c) == CULPRIT:
                if mode == 'serious':
                    ex = dict(eyes='dot', mouth='flat', look=(1, 0), sweat=0.5)
                else:
                    ex = dict(eyes='dot', mouth='wobble', look=(1 if math.sin(t * 5) > 0 else -1, 0), sweat=1.0,
                              blush=0.3 + 0.5 * ramp(t, 23, 25), brows='worried')
                    if mode == 'run':
                        ex = dict(eyes='big', mouth='wobble', blush=0.9, sweat=1.0, brows='worried', look=(0, 1))
            else:
                st = LAUGH_START.get(idx, 99)
                if mode == 'serious':
                    look_dir = 0.7 * math.sin(t * 1.5 + idx)
                    ex = dict(eyes='dot', mouth='flat', look=(look_dir, 0))
                elif t >= st:
                    ex = laugh_ex(t, idx, st)
                    arms = laugh_arms(t, idx)
                    if mode == 'run' and idx % 3 == 0:  # pointing at the culprit
                        cx_, cy_, _ = pos_b(*CULPRIT)
                        tx = lerp(x, cx_, 0.25); arms = ('belly', ('ik', (tx + (30 if cx_ > x else -30) * s, y - 20 * s), -1))
                    bob = abs(math.sin(t * 10 + idx)) * 6 * s; jit = (noise(t, idx) * 2 * s, 0)
                else:
                    ex = dict(eyes='dot', mouth='flat', look=(0.6 * math.sin(t * 2 + idx), 0))
                    if st - t < 0.6: ex = dict(eyes='squeeze', mouth='wavy', blush=0.4)
            studs.append((x + jit[0], y - bob + jit[1], s, ex, arms, head_off, idx))
        # bodies
        for (x, y, s, ex, arms, ho, idx) in studs:
            stick(ctx, x, y, s, ex, t, arms, part='body', head_off=ho)
        for d in (0, 1):
            xa, _, s = pos_b(r, d * 2); xb, y, s = pos_b(r, d * 2 + 1)
            desk_front(ctx, (xa + xb) / 2, y + 60 * s, (xb - xa) + 120 * s, s)
        for (x, y, s, ex, arms, ho, idx) in studs:
            stick(ctx, x, y, s, ex, t, arms, part='top', head_off=ho)
            if mode != 'serious' and t >= LAUGH_START.get(idx, 99) and (r, c) != CULPRIT:
                ha_particles(ctx, x, y - 70 * s, s, t, LAUGH_START.get(idx, 99), idx)
    if mode == 'run' and t >= 27.9:
        draw_runner(ctx, t)

def draw_runner(ctx, t):
    cx, cy, cs = pos_b(*CULPRIT)
    # path keyframes (time, x, neck_y, scale)
    keys = [(27.9, cx, cy, cs), (28.15, cx, cy - 70, cs), (28.5, 540, cy - 80, 1.08), (28.95, 560, 720, 0.86),
            (29.5, 950, 660, 0.78), (29.9, 1000, 650, 0.76)]
    for i in range(len(keys) - 1):
        if keys[i][0] <= t <= keys[i + 1][0] or i == len(keys) - 2:
            a, b = keys[i], keys[i + 1]; u = lin(t, a[0], b[0]); break
    x, y, s = lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u)
    if t > 29.85: return
    running = t > 28.15
    ph = t * 18
    if running:
        legs = (((-10 + 22 * math.sin(ph), 45), (-10 + 46 * math.sin(ph), 92)), ((10 - 22 * math.sin(ph), 45), (10 - 46 * math.sin(ph), 92)))
        arms = (((-30, 20 + 15 * math.sin(ph)), (-40, -10 + 30 * math.sin(ph))), ((30, 20 - 15 * math.sin(ph)), (40, -10 - 30 * math.sin(ph))))
        y += -abs(math.sin(ph)) * 10 * s
    else:
        legs = (((-14, 48), (-18, 95)), ((14, 48), (18, 95)))
        arms = ('up', 'up')
    # speed lines + dust
    if running:
        for k in range(5):
            yy = y + (k - 1) * 30 * s
            line(ctx, [(x - 90 * s - k * 15, yy), (x - 190 * s - k * 25, yy)], 5 * s, BLACK, 0.55)
        for k in range(3):
            circle(ctx, x - (70 + 40 * k) * s, y + 175 * s + noise(t, k) * 5, (18 + 8 * k) * s, fill=(0.85, 0.82, 0.78), stroke=BLACK, lw=2 * s, a=0.7)
    ctx.save()
    if t > 29.45:  # clip to door opening
        ctx.rectangle(-1000, -1000, 1870, 4000); ctx.clip()
    ex = dict(eyes='squeeze', mouth='wobble', blush=1.0, sweat=1.0, tears=0.7, brows='worried')
    stick(ctx, x, y, s, ex, t, arms, legs=legs, lean=(10 if running else 0, 0), torso=80)
    ctx.restore()
    if t < 28.4:
        outlined_text(ctx, "!!", x + 70 * s, y - 120 * s, 70 * s, fill=(1, 0.3, 0.3), scale=back_out((t - 27.9) * 5))

def scene_back(ctx, t, laugh_stage=0):
    """Wide shot from the back of the class: board, teacher (back), students (backs)."""
    wall_and_floor(ctx, 900)
    rect(ctx, 990, 380, 20, 300, fill=WOOD)
    cur = draw_board(ctx, 130, 250, 820, 380, board_prog(t))
    # teacher
    tx = clamp(cur[0] + 120, 330, 860)
    writing = (0.6 < t < 3.9) or (18.6 < t < 20.4)
    wig = math.sin(t * 25) * 6 if writing else 0
    hand = (cur[0] + 6 + wig, cur[1] + 8 + (abs(math.sin(t * 25)) * 6 if writing else 0))
    s = 1.3
    stick(ctx, tx, 680, s, {}, t, arms=('down', ('ik', hand, 1)), back=True, chalk='R',
          legs=(((-12, 55), (-18, 112)), ((12, 55), (18, 112))), torso=95)
    # students from behind (mirror of the front view): row0 farthest
    rows = [(1170, 0.98), (1440, 1.14), (1720, 1.34)]
    for r, (y, s) in enumerate(rows):
        xs = [540 - c * s / 1.2 for c in COLS]  # mirrored
        for d in (0, 1):
            xa, xb = xs[d * 2], xs[d * 2 + 1]
            desk_back(ctx, (xa + xb) / 2, y - 6 * s, abs(xb - xa) + 120 * s, s)
        for c in range(4):
            x = xs[c]
            bob = 0; jit = 0
            if (r, c) == BUDDY and t > 19.0:
                jit = noise(t, 2) * 3 * s; bob = abs(math.sin(t * 9)) * 4 * s * ramp(t, 19.0, 19.4)
            stick(ctx, x + jit, y - bob, s, None, t, arms=('back_desk', 'back_desk'), back=True)
            chair_back(ctx, x, y + 58 * s, s)
            if (r, c) == BUDDY and t > 19.2:
                outlined_text(ctx, "pff...", x + 60 * s, y - 110 * s, 30 * s, fill=(1, 1, 1),
                              scale=back_out((t - 19.2) * 4), angle=-0.15)

def scene_duo(ctx, t):
    """Close-up on culprit (left) and buddy (right) at their desk."""
    wall_and_floor(ctx, 1020)
    rect(ctx, 60, 330, 260, 300, fill=(0.75, 0.90, 1.0), stroke=BLACK, lw=6)
    line(ctx, [(190, 330), (190, 630)], 5); line(ctx, [(60, 480), (320, 480)], 5)
    rect(ctx, 700, 300, 230, 160, fill=(0.85, 0.95, 0.75), stroke=BLACK, lw=5)
    font(ctx, 34); ctx.move_to(722, 365); rgb(ctx, BLACK); ctx.show_text("SILENCE")
    ctx.move_to(740, 420); ctx.show_text("SVP !")
    # background students (back row), small
    for bx in (110, 980):
        stick(ctx, bx, 800, 1.2, dict(eyes='dot', mouth='flat', look=(0.5 if bx < 540 else -0.5, 0)), t, part='all')
    rect(ctx, -50, 880, W + 100, 70, fill=DESK, stroke=BLACK, lw=5)
    s = 3.0
    cx, cy, bx, by = 350, 1060, 740, 1060
    # ---- culprit state
    lean_u = ramp(t, 5.2, 5.6) * (1 - ramp(t, 8.6, 9.0))
    c_ex = dict(eyes='dot', mouth='flat')
    if t < 4.3:
        c_ex = dict(eyes='dot', mouth='flat', look=(0, 0))
    elif t < 5.2:
        c_ex = dict(eyes='half', mouth='smirk', look=(-1 if t < 4.75 else 1, 0), brows='raise_one')
    elif t < 5.9:
        c_ex = dict(eyes='half', mouth='smirk', look=(1, 0), brows='raise_one')
    elif t < 9.0:
        c_ex = dict(eyes='happy', mouth='smile', cheeks=0.6)
        if t > 8.0: c_ex = dict(eyes='dot', mouth='smirk', look=(0, -0.5))
    # culprit in S6b (realizing)
    if t >= 26.0:
        u = t - 26.2
        if u < 0.5:
            c_ex = dict(eyes='shock', mouth='O', brows='up', look=(1, 0))
        else:
            c_ex = dict(eyes='sad', mouth='wobble', brows='worried', blush=ramp(t, 26.7, 27.4), sweat=1.0,
                        eye_dy=0.12, look=(0, 1), cheeks=0.8)
    # ---- buddy state
    b_ex = dict(eyes='dot', mouth='flat', look=(0.3, 0))
    b_jit = (0, 0); b_head = (0, 0)
    if 5.2 <= t < 5.9:
        b_ex = dict(eyes='dot', mouth='flat', look=(-1, 0))
    elif 5.9 <= t < 7.0:
        b_ex = dict(eyes='shock', mouth='bigO', brows='up', look=(-1, 0))
    elif 7.0 <= t < 9.0:
        b_ex = dict(eyes='big', mouth='wavy', brows='worried', look=(0, -0.2), blush=0.25 * ramp(t, 7.5, 9.0))
        b_jit = (noise(t, 1) * 2, 0)
    elif 9.0 <= t < 14.0:
        u = ramp(t, 9.2, 12.5)
        b_ex = dict(eyes='squeeze', mouth='wavy', brows='worried', blush=0.25 + 0.75 * u, tears=ramp(t, 9.8, 12.2),
                    sweat=1.0 if t > 11.0 else 0)
        amp = 2 + 9 * u
        b_jit = (noise(t, 1) * amp, noise(t, 4) * amp * 0.5)
    elif t >= 26.0:  # laughing in background of S6b
        b_ex = laugh_ex(t, 5, 19.6, crying=True); b_jit = (noise(t, 3) * 4, -abs(math.sin(t * 11)) * 10)
    c_lean = (22 * lean_u, 4 * lean_u)
    c_hand_target = (bx - 20, by + 30)
    c_arms = ('rest', ('ik', c_hand_target, -1, 52) if lean_u > 0.02 else 'rest')
    if lean_u > 0.02 and lean_u < 1:
        # interpolate between rest hand and shoulder target
        rest = arm_pts('rest', 1, s, cx + 22 * lean_u * s, cy + 13 * s, 0)[2]
        c_arms = ('rest', ('ik', (lerp(rest[0], c_hand_target[0], lean_u), lerp(rest[1], c_hand_target[1], lean_u)), -1, 52))
    if t >= 26.0:
        c_arms = ('rest', 'rest')
        c_lean = (0, 8 * ramp(t, 26.8, 27.4))
    b_arms = ('rest', 'rest') if t < 26 else ('wipe', 'belly')
    if 9.0 <= t < 14.0 and t > 11.5:
        b_arms = ('face', 'rest')  # hand over mouth
    c_head = (0, 22 * ramp(t, 26.8, 27.4)) if t >= 26 else (0, 0)
    # draw
    stick(ctx, cx, cy, s, c_ex, t, c_arms, part='body', lean=c_lean, head_off=c_head)
    stick(ctx, bx + b_jit[0], by + b_jit[1], s, b_ex, t, b_arms, part='body')
    desk_front(ctx, 540, cy + 60 * s, 1000, s)
    stink_drawn = False
    if 5.9 <= t < 9.6:
        stink(ctx, cx + 30, cy + 150, t - 5.9, 1.6)
        stink_drawn = True
    if b_arms[0] == 'face':
        stick(ctx, bx + b_jit[0], by + b_jit[1], s, b_ex, t, ('rest', 'rest'), part='top')
        # hand over mouth on top
        hd = (bx + b_jit[0], by + b_jit[1] - (34 * s + 3 * s))
        sh = (bx + b_jit[0], by + b_jit[1] + 11 * s)
        line(ctx, [sh, (sh[0] - 40 * s, sh[1] + 30 * s), (hd[0] - 4 * s, hd[1] + 14 * s)], 7.5 * s)
        circle(ctx, hd[0] - 4 * s, hd[1] + 14 * s, 7 * s, fill=BLACK)
    else:
        stick(ctx, bx + b_jit[0], by + b_jit[1], s, b_ex, t, b_arms, part='top')
    stick(ctx, cx, cy, s, c_ex, t, c_arms, part='top', lean=c_lean, head_off=c_head)
    if 5.9 <= t < 9.6 and stink_drawn:
        stink(ctx, cx + 220, cy - 60, t - 6.4, 1.3, front=True)
    return dict(culprit=(cx, cy - 37 * s), buddy=(bx, by - 37 * s))

def stink(ctx, ox, oy, u, sc, front=False):
    if u < 0: return
    for j in range(7):
        p = u * 0.9 - j * 0.13
        if p <= 0: continue
        p = p % 1.6
        a = clamp(1 - p / 1.6) * clamp(p * 4)
        bx = ox + (j - 3) * 34 * sc + p * 160 * sc * (1 if front else 0.7)
        by = oy - p * 260 * sc
        pts = [(bx + math.sin(v * 9 + u * 8 + j) * 14 * sc, by - v * 110 * sc) for v in np.linspace(0, 1, 14)]
        line(ctx, pts, 11 * sc, GREEN, 0.85 * a)
        line(ctx, pts, 4 * sc, (0.75, 1.0, 0.45), 0.8 * a)
    if not front:
        for j in range(6):
            p = clamp(u * 1.2 - j * 0.08)
            if p <= 0: continue
            circle(ctx, ox + (j - 2.5) * 50 * sc + p * 60 * sc, oy - 40 * sc - p * 120 * sc, (30 + j * 4) * sc * (0.5 + p),
                   fill=(0.55, 0.85, 0.3), a=0.35 * (1 - p * 0.7))

def scene_teacher(ctx, t):
    """Close-up on the teacher in front of the board."""
    wall_and_floor(ctx, 1700)
    cur = draw_board(ctx, 120, 160, 1100, 950, board_prog(t))
    s = 3.1
    tx, ty = 560, 1260
    # turn amount: -1 back, 1 front
    turn = -1.0
    if 13.6 <= t < 17.8: turn = lerp(-1, 1, ramp(t, 13.6, 14.5))
    elif 17.8 <= t < 18.6: turn = lerp(1, -1, ramp(t, 17.85, 18.4))
    elif t >= 25.0: turn = 1.0 if t >= 25.15 else lerp(-1, 1, ramp(t, 24.95, 25.15))
    ex = dict(eyes='dot', mouth='flat')
    if 14.2 <= t < 17.8:
        sweep = 0
        if t > 16.8: sweep = math.sin((t - 16.8) * 5)
        ex = dict(eyes='half', mouth='flat', brows='raise_one', look=(sweep, 0))
    if t >= 25.0:
        ex = dict(eyes='shock', mouth='bigO', brows='up')
    if t >= 30.3:
        ex = dict(eyes='dot', mouth='flat', brows='flat')
        if t > 33.6: ex['blink'] = True
    writing = (t < 13.25) or (18.4 <= t < 20.4)
    face_front = turn > 0
    if not face_front:
        wig = math.sin(t * 25) * 8 if writing else 0
        hand = (cur[0] + 6 + wig, cur[1] + 10)
        arms = ('down', ('ik', hand, 1))
        chalk = 'R'
    else:
        arms = ('down', 'down')
        chalk = 'R'
        if t >= 25.0 and t < 30.3: arms = ('up', 'up')
    legs = (((-12, 55), (-18, 112)), ((12, 55), (18, 112)))
    info = stick(ctx, tx, ty, s, ex, t, arms, legs=legs, back=not face_front, turn=abs(turn) if face_front else 0,
                 chalk=chalk if not (t >= 25.0 and t < 30.3) else None, torso=95)
    # falling chalk in surprise
    if 25.0 <= t < 26.2:
        u = t - 25.0
        circle(ctx, tx + 150 + u * 60, 1160 + u * u * 1400, 10, fill=(1, 1, 1), stroke=BLACK, lw=3)
    return info

# ---------------------------------------------------------------- overlays
def burst(ctx, x, y, r1, r2, n, rot, fill, scale):
    if scale <= 0.01: return
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(scale, scale)
    ctx.new_path()
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        a = i * math.pi / n
        rr = r * (1 + 0.08 * math.sin(i * 2.7))
        (ctx.move_to if i == 0 else ctx.line_to)(math.cos(a) * rr, math.sin(a) * rr)
    ctx.close_path(); rgb(ctx, fill); ctx.fill_preserve(); rgb(ctx, BLACK); ctx.set_line_width(8); ctx.stroke()
    ctx.restore()

SKULL = cairo.ImageSurface.create_from_png(os.path.join(HERE, 'skull.png'))

def end_title(ctx, t):
    u = t - 31.2
    if u < 0: return
    sc1 = back_out(u * 3.2); sc2 = back_out((u - 0.35) * 3.2)
    wob = math.sin(t * 3) * 0.02
    ctx.save()
    rrect(ctx, 50, 190, 980, 360, 40); rgb(ctx, BLACK, 0.82 * clamp(u * 4)); ctx.fill()
    ctx.restore()
    outlined_text(ctx, "IL A DÉTRUIT", 540, 300, 118, fill=(1, 1, 1), lw=22, angle=-0.05 + wob, scale=sc1)
    if u > 0.35:
        if sc2 <= 0.01: return
        ctx.save(); ctx.translate(540, 450); ctx.rotate(0.04 - wob); ctx.scale(sc2, sc2)
        outlined_text(ctx, "LE COURS", -70, 0, 118, fill=(1.0, 0.85, 0.15), lw=22)
        ctx.save(); ctx.translate(268, -62); ctx.scale(1.15, 1.15)
        ctx.set_source_surface(SKULL, -18, -4); ctx.paint(); ctx.restore()
        ctx.restore()

# ---------------------------------------------------------------- timeline
rng = np.random.default_rng(7)
order = [i for i in range(12) if i not in (CULPRIT[0] * 4 + CULPRIT[1], BUDDY[0] * 4 + BUDDY[1])]
waves = [[11], [3, 6], [0, 2, 9, 7, 10], [1, 8]]
times = [20.3, 20.9, 21.5, 22.1]
for grp, tt in zip(waves, times):
    for k, i in enumerate(grp):
        LAUGH_START[i] = tt + 0.08 * k

def camera(ctx, t):
    """returns (view, zoom, cx, cy, shake)"""
    if t < 4.0:
        return 'back', lerp(1.0, 1.1, ease(t / 4)), 540, 900, 0
    if t < 9.0:
        z = 1.0 + 0.12 * ramp(t, 5.9, 6.1) - 0.06 * ramp(t, 6.2, 8.0)
        cx = 560 + 40 * ramp(t, 5.9, 6.2)
        sh = 22 * clamp(1 - (t - 5.9) / 0.8) if t > 5.9 else 0
        if t < 4.25: z *= lerp(1.12, 1.0, back_out((t - 4.0) / 0.25))
        return 'duo', z * 1.08, cx, 1060, sh
    if t < 13.0:
        z = lerp(1.15, 2.1, ease((t - 9.0) / 0.6)) + 0.4 * lin(t, 9.6, 13.0)
        return 'duo', z, 760, 950, 2 * lin(t, 10, 13)
    if t < 15.2:
        z = lerp(1.0, 1.35, ramp(t, 14.4, 15.2))
        return 'teacher', z, 560, 1100, 0
    if t < 16.8:
        z = lerp(1.0, 1.25, ease((t - 15.2) / 1.6))
        return 'front_serious', z, 420, 1150, 0
    if t < 18.6:
        z = lerp(1.6, 1.45, lin(t, 16.8, 18.6))
        return 'teacher', z, 560, 1060, 0
    if t < 19.6:
        return 'back', 1.05, 540, 1000, 0
    if t < 25.0:
        z = lerp(1.25, 1.0, ease((t - 19.6) / 2.5))
        cx = lerp(420, 540, ease((t - 19.6) / 2.5))
        return 'front_laugh', z, cx, lerp(1150, 1000, ease((t - 19.6) / 2.5)), 3 + 6 * lin(t, 21, 24)
    if t < 26.2:
        z = lerp(1.7, 1.55, lin(t, 25, 26.2))
        return 'teacher', z * (1 + 0.15 * clamp(1 - (t - 25) * 5)), 560, 1050, 10 * clamp(1 - (t - 25) * 3)
    if t < 27.9:
        z = lerp(1.6, 2.0, ease((t - 26.2) / 1.7))
        return 'duo', z, 360, 980, 0
    if t < 30.3:
        sh = 4 + (26 * clamp(1 - (t - 30.0) * 3) if t >= 30.0 else 0)
        return 'front_run', 1.0, 540, 960, sh
    z = lerp(1.25, 2.0, ease((t - 30.3) / 4.5))
    return 'teacher', z, 560, 1040, 0

def render_frame(t, surf):
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*WALL); ctx.paint()
    view, z, cx, cy, sh = camera(ctx, t)
    shx = noise(t, 1) * sh; shy = noise(t, 2) * sh
    ctx.save()
    ctx.translate(W / 2 + shx, H / 2 + shy); ctx.scale(z, z); ctx.translate(-cx, -cy)
    if view == 'back': scene_back(ctx, t)
    elif view == 'duo': scene_duo(ctx, t)
    elif view == 'teacher': scene_teacher(ctx, t)
    elif view == 'front_serious': scene_front(ctx, t, 'serious')
    elif view == 'front_laugh': scene_front(ctx, t, 'laugh')
    elif view == 'front_run': scene_front(ctx, t, 'run')
    ctx.restore()
    # --- screen-space overlays
    if 5.9 <= t < 7.6:
        u = t - 5.9
        sc = back_out(u * 4) * (1 - 0.2 * clamp(u - 1.2))
        burst(ctx, 560, 560, 300, 200, 14, -0.12 + u * 0.05, (1.0, 0.85, 0.15), sc)
        outlined_text(ctx, "PRRRT !", 560, 560, 120, fill=(0.4, 0.75, 0.1), lw=20, angle=-0.12, scale=sc * (1 + 0.04 * math.sin(t * 40)))
    if 14.5 <= t < 15.2:
        outlined_text(ctx, "?", 840, 560, 170, fill=(1, 1, 1), lw=24, scale=back_out((t - 14.5) * 4))
    if 16.8 <= t < 17.8:
        sc = back_out((t - 16.8) * 4)
        if sc > 0.01:
            ctx.save(); ctx.translate(800, 760); ctx.scale(sc, sc)
            ctx.save(); ctx.scale(1, 0.62); circle(ctx, 0, 0, 190, fill=(1, 1, 1), stroke=BLACK, lw=8); ctx.restore()
            ctx.move_to(-120, 90); ctx.line_to(-210, 200); ctx.line_to(-40, 110); rgb(ctx, (1, 1, 1)); ctx.fill_preserve()
            rgb(ctx, BLACK); ctx.set_line_width(8); ctx.stroke()
            ctx.save(); ctx.scale(1, 0.62); circle(ctx, 0, 0, 182, fill=(1, 1, 1)); ctx.restore()
            outlined_text(ctx, "Hmm...", 0, 0, 72, fill=BLACK, stroke=(1, 1, 1), lw=2)
            ctx.restore()
    if 25.0 <= t < 26.2:
        outlined_text(ctx, "?!", 820, 420, 200, fill=(1.0, 0.3, 0.3), lw=26, angle=0.1, scale=back_out((t - 25.0) * 4))
    if 30.0 <= t < 30.8:
        u = t - 30.0
        burst(ctx, 820, 700, 260, 170, 12, 0.1, (1, 1, 1), back_out(u * 5))
        outlined_text(ctx, "BAM !", 820, 700, 120, fill=(1.0, 0.3, 0.2), lw=20, angle=0.1, scale=back_out(u * 5))
    if 30.3 <= t < 31.2:
        outlined_text(ctx, "...", 540, 380, 140, fill=(1, 1, 1), lw=20, a=clamp((t - 30.4) * 3))
    end_title(ctx, t)
    # quick white flash on hard moments
    for ft in (5.9, 30.0):
        if 0 <= t - ft < 0.1:
            ctx.set_source_rgba(1, 1, 1, 0.6 * (1 - (t - ft) / 0.1)); ctx.paint()
    surf.flush()

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'video_noaudio.mp4')
    only = sys.argv[2:]  # optional preview times
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    if only:
        for ts in only:
            render_frame(float(ts), surf); surf.write_to_png(os.path.join(HERE, f'prev_{ts}.png'))
        return
    n = int(DUR * FPS)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                          '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for f in range(n):
        render_frame(f / FPS, surf)
        p.stdin.write(bytes(surf.get_data()))
        if f % 150 == 0: print(f, '/', n, flush=True)
    p.stdin.close(); p.wait()

if __name__ == '__main__':
    main()

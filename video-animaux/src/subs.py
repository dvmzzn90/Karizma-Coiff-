"""Sous-titres dynamiques mot par mot (ASS) : blanc épais, contour noir, mot-clé en jaune.
Écrit aussi un .srt classique (pour TikTok/CapCut)."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Mot,Inter Display Black,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,4,2,60,60,470,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
YELLOW = r"{\c&H00E5FF&}"
WHITE = r"{\c&HFFFFFF&}"


def ts(t):
    t = max(0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def chunks(words):
    """Groupes de 1 à 3 mots, coupés à la ponctuation et entre répliques."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        end_punct = w["w"][-1] in ".?…:,!"
        nxt = words[i + 1] if i + 1 < len(words) else None
        new_line = nxt is None or nxt["line"] != w["line"]
        width = sum(len(x["w"]) + 1 for x in cur) + (len(nxt["w"]) if nxt else 0)
        if len(cur) == 3 or end_punct or new_line or w["kw"] or width > 17:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    # évite les mots-clés isolés collés au groupe suivant : déjà géré par la coupe sur kw
    return out


def disp(w):
    t = w["w"].upper().replace("…", "…")
    return t


def build():
    d = json.load(open(os.path.join(OUT, "timings.json")))
    words = d["words"]
    groups = chunks(words)
    ev = []
    srt = []
    for gi, g in enumerate(groups):
        g_end = g[-1]["end"] + 0.35
        if gi + 1 < len(groups):
            g_end = min(g_end, groups[gi + 1][0]["start"])
        g_end = max(g_end, g[-1]["end"])
        srt.append((g[0]["start"], g_end, " ".join(w["w"] for w in g)))
        for k, w in enumerate(g):
            a = w["start"]
            b = g[k + 1]["start"] if k + 1 < len(g) else g_end
            parts = []
            for j, x in enumerate(g[: k + 1]):
                col = YELLOW if x["kw"] else WHITE
                txt = disp(x)
                if j == k:  # mot qui vient d'apparaître : effet « pop »
                    pop = r"{\fscx128\fscy128\t(0,90,\fscx100\fscy100)}" if not x["kw"] else r"{\fscx145\fscy145\t(0,120,\fscx112\fscy112)}"
                    parts.append(col + pop + txt + r"{\fscx100\fscy100}")
                else:
                    parts.append(col + (r"{\fscx112\fscy112}" if x["kw"] else "") + txt + r"{\fscx100\fscy100}")
            ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Mot,,0,0,0,,{' '.join(parts)}")
    with open(os.path.join(OUT, "subtitles.ass"), "w", encoding="utf-8") as f:
        f.write(HEADER + "\n".join(ev) + "\n")
    with open(os.path.join(OUT, "subtitles.srt"), "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(srt):
            f.write(f"{i + 1}\n{srt_ts(a)} --> {srt_ts(b)}\n{txt}\n\n")
    print("sous-titres :", len(ev), "évènements")


def srt_ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


if __name__ == "__main__":
    build()

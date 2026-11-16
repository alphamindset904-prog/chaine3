"""Format « Énigmes » (Shorts 9:16) : un paradoxe ou une énigme de logique expliquée avec des pictogrammes roses
sur fond sombre. Chaque séquence = quelques pictogrammes qui apparaissent EN SYNCHRO avec les mots de la narration."""
import math
import random
import re

from PIL import Image, ImageDraw, ImageFilter

import anim
from anim import K, font

WV, HV, FPS = 720, 1280, 24

BG = (43, 43, 45)
PINK = (250, 168, 232)
PINK_D = (122, 70, 116)
PINK_M = (196, 110, 176)
WHITE = (246, 246, 246)
GREY = (128, 124, 128)
BLUE = (150, 200, 255)
RED = (255, 96, 120)

ICONS = ("door", "door_open", "box", "money", "button", "cookie", "fork", "brain", "bulb", "person", "question",
         "clock", "dice", "orb", "apple", "heart", "check", "cross", "scale", "coin", "arrow", "people", "goat",
         "lock", "key")

_bg = None


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def back(x):
    """Apparition avec léger rebond."""
    x = clamp(x)
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def make_bg():
    global _bg
    if _bg is None:
        size = (WV * K, HV * K)
        bg = Image.new("RGB", size, BG)
        vig = Image.radial_gradient("L").resize(size).point(lambda v: int(v * .42))
        bg = Image.composite(Image.new("RGB", size, (14, 14, 16)), bg, vig)
        rnd = random.Random(7)
        d = ImageDraw.Draw(bg, "RGBA")
        for _ in range(950):                       # grain de points, comme les vidéos de référence
            x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
            r = rnd.choice((1, 1, 2, 2, 3))
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.choice((7, 10, 14))))
        _bg = bg
    return _bg


# ----------------------------------------------------------------------------
# Primitives (coordonnées 1x, dessin supersamplé)
# ----------------------------------------------------------------------------
class Pen:
    """Dessine un pictogramme en coordonnées unitaires [-1, 1] centrées en (cx, cy), taille `s` (hauteur en px)."""

    def __init__(self, img, texts, cx, cy, s, alpha=1.0, outline=PINK, fill=PINK_D):
        self.d = ImageDraw.Draw(img, "RGBA")
        self.texts, self.cx, self.cy, self.s, self.a = texts, cx, cy, s, alpha
        self.oc, self.fc = outline, fill
        self.w = max(3.0, s * .035)

    def X(self, u):
        return (self.cx + u * self.s / 2) * K

    def Y(self, v):
        return (self.cy + v * self.s / 2) * K

    def col(self, c, f=1.0):
        return tuple(c[:3]) + (int(255 * self.a * f),)

    def poly(self, pts, fill=None, outline=True, closed=True, width=None):
        P = [(self.X(u), self.Y(v)) for u, v in pts]
        w = int((width or self.w) * K)
        if fill is not None:
            self.d.polygon(P, fill=self.col(fill))
        if outline:
            self.d.line(P + ([P[0]] if closed else []), fill=self.col(self.oc), width=w, joint="curve")
            r = w / 2
            for x, y in P:
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=self.col(self.oc))

    def rect(self, u0, v0, u1, v1, fill=None, outline=True, radius=0.0, width=None):
        b = [self.X(u0), self.Y(v0), self.X(u1), self.Y(v1)]
        w = int((width or self.w) * K)
        rad = radius * self.s / 2 * K
        fc = self.col(fill) if fill is not None else None
        oc = self.col(self.oc) if outline else None
        if rad > 0:
            self.d.rounded_rectangle(b, radius=rad, fill=fc, outline=oc, width=w)
        else:
            self.d.rectangle(b, fill=fc, outline=oc, width=w)

    def circ(self, u, v, r, fill=None, outline=True, width=None):
        R = r * self.s / 2 * K
        x, y = self.X(u), self.Y(v)
        self.d.ellipse([x - R, y - R, x + R, y + R], fill=self.col(fill) if fill is not None else None,
                       outline=self.col(self.oc) if outline else None, width=int((width or self.w) * K))

    def ell(self, u0, v0, u1, v1, fill=None, outline=True, width=None):
        self.d.ellipse([self.X(u0), self.Y(v0), self.X(u1), self.Y(v1)],
                       fill=self.col(fill) if fill is not None else None,
                       outline=self.col(self.oc) if outline else None, width=int((width or self.w) * K))

    def line(self, pts, col=None, width=None):
        P = [(self.X(u), self.Y(v)) for u, v in pts]
        w = int((width or self.w) * K)
        c = self.col(col or self.oc)
        self.d.line(P, fill=c, width=w, joint="curve")
        r = w / 2
        for x, y in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=c)

    def text(self, s, u, v, size, color=WHITE):
        self.texts.append((s, size * self.s / 200.0, color, self.cx + u * self.s / 2, self.cy + v * self.s / 2, self.a))


# ----------------------------------------------------------------------------
# Pictogrammes
# ----------------------------------------------------------------------------
def i_door(pen, t, it):
    pen.rect(-.52, -1, .52, 1, PINK_D, radius=.06)
    pen.rect(-.34, -.82, .34, .02, None, width=pen.w * .7)
    pen.rect(-.34, .14, .34, .82, None, width=pen.w * .7)
    pen.circ(.30, .02, .07, PINK)


def i_door_open(pen, t, it):
    pen.rect(-.52, -1, .52, 1, (30, 30, 33), radius=.04)
    pen.poly([(.52, -1), (.98, -.82), (.98, .86), (.52, 1)], PINK_D)
    pen.circ(.80, .02, .05, PINK)


def i_box(pen, t, it):
    top = [(0, -1), (.9, -.55), (0, -.1), (-.9, -.55)]
    left = [(-.9, -.55), (0, -.1), (0, .95), (-.9, .5)]
    right = [(0, -.1), (.9, -.55), (.9, .5), (0, .95)]
    pen.poly(left, PINK_D)
    pen.poly(right, PINK_M)
    pen.poly(top, PINK)
    pen.text("?", -.45, .22, 105, WHITE)


def i_money(pen, t, it):
    pen.rect(-1, -.48, 1, .48, PINK_D, radius=.08)
    pen.rect(-.88, -.36, .88, .36, None, width=pen.w * .6, radius=.06)
    v = str(it.get("value") or "100e")
    pen.text(v, 0, 0, 100 * min(1.0, 5.0 / max(len(v), 1)), WHITE)


def i_button(pen, t, it):
    pen.ell(-1, .05, 1, .78, PINK_D)
    pen.rect(-1, .2, 1, .42, PINK_D, outline=False)
    pen.ell(-.78, -.32, .78, .30, PINK_M)
    pen.ell(-.78, -.02, .78, .42, PINK_M, outline=False)
    pen.ell(-.78, -.32, .78, .30, PINK)


def i_cookie(pen, t, it):
    pen.circ(0, 0, 1, PINK_D)
    pen.circ(.78, -.62, .42, BG, outline=False)
    for u, v in ((-.4, -.3), (.1, .3), (-.45, .4), (.25, -.35), (.55, .5)):
        pen.circ(u, v, .1, PINK, outline=False)


def i_fork(pen, t, it):
    pen.line([(-.35, -1), (-.35, -.35)])
    pen.line([(0, -1), (0, -.35)])
    pen.line([(.35, -1), (.35, -.35)])
    pen.line([(-.35, -.35), (-.2, -.1), (0, -.05), (.2, -.1), (.35, -.35)])
    pen.line([(0, -.05), (0, 1)], width=pen.w * 1.4)


def i_brain(pen, t, it):
    for u, v, r in ((-.4, -.25, .5), (.1, -.45, .5), (.5, -.1, .46), (-.45, .3, .42), (.15, .35, .5), (.55, .4, .36)):
        pen.circ(u, v, r, PINK_D)
    for u, v, r in ((-.4, -.25, .5), (.1, -.45, .5), (.5, -.1, .46), (-.45, .3, .42), (.15, .35, .5), (.55, .4, .36)):
        pen.circ(u, v, r * .8, PINK_D, outline=False)
    pen.line([(-.2, -.1), (0, .05), (.1, -.2)], width=pen.w * .6)
    pen.line([(.2, .2), (.4, .1), (.35, .35)], width=pen.w * .6)


def i_bulb(pen, t, it):
    pen.circ(0, -.2, .62, PINK_D)
    pen.rect(-.25, .38, .25, .62, PINK_M, radius=.05)
    pen.rect(-.18, .62, .18, .84, PINK_M, radius=.05)
    for k in range(7):
        ang = math.radians(-160 + k * 23)
        pen.line([(math.cos(ang) * .82, -.2 + math.sin(ang) * .82), (math.cos(ang) * 1.0, -.2 + math.sin(ang) * 1.0)],
                 width=pen.w * .8)


def i_person(pen, t, it):
    pen.circ(0, -.62, .3, PINK)
    pen.poly([(-.6, .9), (-.5, -.15), (-.2, -.28), (.2, -.28), (.5, -.15), (.6, .9)], PINK, outline=False)


def i_people(pen, t, it):
    for dx, sc in ((-.55, .8), (.55, .8), (0, 1)):
        pen.circ(dx, -.45 * sc + .1, .26 * sc, PINK)
        pen.poly([(dx - .42 * sc, .95), (dx - .34 * sc, .05 * sc), (dx + .34 * sc, .05 * sc), (dx + .42 * sc, .95)],
                 PINK, outline=False)


def i_question(pen, t, it):
    pen.text("?", 0, 0, 250, PINK)


def i_clock(pen, t, it):
    pen.circ(0, 0, 1, PINK_D)
    for k in range(12):
        a = math.radians(k * 30)
        pen.line([(math.sin(a) * .82, -math.cos(a) * .82), (math.sin(a) * .93, -math.cos(a) * .93)], width=pen.w * .6)
    a = t * 1.8
    pen.line([(0, 0), (math.sin(a) * .7, -math.cos(a) * .7)])
    pen.line([(0, 0), (math.sin(a / 12) * .45, -math.cos(a / 12) * .45)], width=pen.w * 1.3)
    pen.circ(0, 0, .07, PINK)


def i_dice(pen, t, it):
    pen.rect(-.9, -.9, .9, .9, PINK_D, radius=.3)
    n = max(1, min(6, int(str(it.get("value") or "5")[:1] or 5))) if str(it.get("value") or "5")[:1].isdigit() else 5
    spots = {1: [(0, 0)], 2: [(-.45, -.45), (.45, .45)], 3: [(-.45, -.45), (0, 0), (.45, .45)],
             4: [(-.45, -.45), (.45, -.45), (-.45, .45), (.45, .45)],
             5: [(-.45, -.45), (.45, -.45), (0, 0), (-.45, .45), (.45, .45)],
             6: [(-.45, -.5), (.45, -.5), (-.45, 0), (.45, 0), (-.45, .5), (.45, .5)]}[n]
    for u, v in spots:
        pen.circ(u, v, .12, PINK, outline=False)


def i_orb(pen, t, it):
    pulse = 1 + .05 * math.sin(t * 3)
    a0 = pen.a
    for r, a in ((1.6, .10), (1.35, .16), (1.15, .26)):
        pen.a = a0 * a
        pen.circ(0, 0, r * pulse, PINK, outline=False)
    pen.a = a0
    pen.circ(0, 0, .95 * pulse, (255, 214, 244))
    pen.circ(-.25, -.3, .3, (255, 255, 255), outline=False)


def i_apple(pen, t, it):
    pen.circ(-.3, .1, .62, PINK_D)
    pen.circ(.3, .1, .62, PINK_D)
    pen.circ(0, .28, .6, PINK_D, outline=False)
    pen.line([(0, -.45), (.08, -.85)])
    pen.poly([(.08, -.8), (.5, -.95), (.4, -.6)], PINK)


def i_heart(pen, t, it):
    pen.circ(-.42, -.28, .5, PINK_M)
    pen.circ(.42, -.28, .5, PINK_M)
    pen.poly([(-.88, -.05), (0, .95), (.88, -.05)], PINK_M, outline=False)
    pen.circ(-.42, -.28, .38, PINK_M, outline=False)
    pen.circ(.42, -.28, .38, PINK_M, outline=False)
    pen.line([(-.87, -.02), (0, .95), (.87, -.02)])


def i_check(pen, t, it):
    pen.line([(-.8, .05), (-.25, .6), (.85, -.7)], WHITE, pen.w * 2.4)


def i_cross(pen, t, it):
    pen.line([(-.7, -.7), (.7, .7)], RED, pen.w * 2.4)
    pen.line([(.7, -.7), (-.7, .7)], RED, pen.w * 2.4)


def i_scale(pen, t, it):
    tilt = float(it.get("tilt", 0) or 0)
    pen.line([(0, -.9), (0, .85)])
    pen.line([(-.5, .9), (.5, .9)])
    yl, yr = -.55 + tilt * .2, -.55 - tilt * .2
    pen.line([(-.95, yl), (.95, yr)])
    for sx, sy in ((-.95, yl), (.95, yr)):
        pen.line([(sx, sy), (sx - .3, sy + .5)], width=pen.w * .6)
        pen.line([(sx, sy), (sx + .3, sy + .5)], width=pen.w * .6)
        pen.poly([(sx - .4, sy + .5), (sx + .4, sy + .5), (sx + .25, sy + .68), (sx - .25, sy + .68)], PINK_D)


def i_coin(pen, t, it):
    f = abs(math.cos(t * 2.2)) if it.get("spin") else 1.0
    pen.ell(-.95 * max(f, .08), -.95, .95 * max(f, .08), .95, PINK)
    if f > .35:
        pen.text(str(it.get("value") or "€"), 0, 0, 110 * f, (60, 30, 60))


def i_arrow(pen, t, it):
    pen.line([(-.9, 0), (.8, 0)], width=pen.w * 1.6)
    pen.line([(.35, -.45), (.9, 0), (.35, .45)], width=pen.w * 1.6)


def i_goat(pen, t, it):
    pen.ell(-.8, -.25, .6, .55, PINK_D)
    pen.circ(.65, -.4, .28, PINK_D)
    pen.line([(.55, -.65), (.5, -1)])
    pen.line([(.75, -.65), (.82, -1)])
    for u in (-.55, -.25, .25, .5):
        pen.line([(u, .35), (u, .95)])


def i_lock(pen, t, it):
    pen.rect(-.65, -.1, .65, .9, PINK_D, radius=.12)
    pen.line([(-.4, -.1), (-.4, -.55), (-.2, -.85), (.2, -.85), (.4, -.55), (.4, -.1)])
    pen.circ(0, .4, .12, PINK)


def i_key(pen, t, it):
    pen.circ(-.55, 0, .38, PINK_D)
    pen.line([(-.17, 0), (.95, 0)], width=pen.w * 1.3)
    pen.line([(.6, 0), (.6, .35)])
    pen.line([(.85, 0), (.85, .3)])


DRAW = {"door": i_door, "door_open": i_door_open, "box": i_box, "money": i_money, "button": i_button,
        "cookie": i_cookie, "fork": i_fork, "brain": i_brain, "bulb": i_bulb, "person": i_person,
        "question": i_question, "clock": i_clock, "dice": i_dice, "orb": i_orb, "apple": i_apple,
        "heart": i_heart, "check": i_check, "cross": i_cross, "scale": i_scale, "coin": i_coin, "arrow": i_arrow,
        "people": i_people, "goat": i_goat, "lock": i_lock, "key": i_key}


# ----------------------------------------------------------------------------
# Textes
# ----------------------------------------------------------------------------
def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and d.textlength(trial, font=f) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def fit_lines(d, text, size, maxw, maxlines, custom=""):
    sz = max(22, int(size))
    f = font("bold", sz, custom)
    lines = wrap(d, text, f, maxw)
    while len(lines) > maxlines and sz > 22:
        sz -= 2
        f = font("bold", sz, custom)
        lines = wrap(d, text, f, maxw)
    return f, sz, lines


def draw_text_block(layer_draw, text, size, color, cx, y, maxw, maxlines, alpha, custom="", stroke=True):
    f, sz, lines = fit_lines(layer_draw, text, size, maxw, maxlines, custom)
    lh = int(sz * 1.18)
    a = int(255 * alpha)
    for i, ln in enumerate(lines):
        x = cx - layer_draw.textlength(ln, font=f) / 2
        layer_draw.text((x, y + i * lh), ln, font=f, fill=tuple(color[:3]) + (a,),
                        stroke_width=max(2, sz // 14) if stroke else 0, stroke_fill=(20, 20, 22, a))
    return y + len(lines) * lh


# ----------------------------------------------------------------------------
# Séquence
# ----------------------------------------------------------------------------
def anchor_time(narration, anchor, speech_dur, default):
    """Instant (s) où le mot `anchor` est prononcé, estimé à partir de sa position dans la phrase."""
    if not anchor:
        return default
    norm = lambda s: re.sub(r"[^\wàâäéèêëîïôöùûüç0-9/%-]", "", s.lower())
    words = narration.split()
    a = norm(str(anchor).split()[0])
    total = sum(len(w) + 1 for w in words) or 1
    pos = 0
    for w in words:
        if a and (norm(w).startswith(a) or a in norm(w)):
            return max(0.15, clamp((pos + len(w) * .3) / total) * speech_dur - .12)
        pos += len(w) + 1
    return default


def layout(n):
    """Positions (cx, cy) et taille des pictogrammes."""
    if n == 1:
        return [(360, 600)], 430
    if n == 2:
        return [(190, 600), (530, 600)], 320
    if n == 3:
        return [(125, 600), (360, 600), (595, 600)], 250
    if n == 4:
        return [(205, 470), (515, 470), (205, 800), (515, 800)], 260
    rows = [(0, 3), (3, n)]
    out = []
    for ri, (a, b) in enumerate(rows):
        k = b - a
        y = 470 if ri == 0 else 780
        xs = [360] if k == 1 else [130 + j * (460 / (k - 1)) for j in range(k)]
        out += [(x, y) for x in xs]
    return out, 215


class BeatRenderer:
    def __init__(self, beat, dur, speech_dur, cfg, last=False):
        self.b, self.dur, self.last = beat, max(dur, 3.0), last
        self.speech = max(speech_dur, 1.5)
        self.cfg = cfg
        self.bg = make_bg()
        self.font = cfg.get("font_bold", "")
        items = beat.get("items", [])
        res = layout(len(items)) if items else ([], 0)
        self.pos, self.size = res if items else ([], 0)
        n = len(items)
        self.t_in = []
        for i, it in enumerate(items):
            default = .35 + i * min(.7, self.speech * .5 / max(n, 1))
            self.t_in.append(anchor_time(beat["narration"], it.get("at"), self.speech, default))
        self.t_big = anchor_time(beat["narration"], beat.get("big_at"), self.speech, .5) if beat.get("big") else 0
        self.cues = self.sound_cues()

    def sound_cues(self):
        cues = [round(t, 2) for t in self.t_in]
        for it in self.b.get("items", []):
            for key in ("then", "dim_at"):
                v = it.get(key)
                if isinstance(v, dict) and v.get("at"):
                    cues.append(round(anchor_time(self.b["narration"], v["at"], self.speech, 1.0), 2))
        if self.b.get("big"):
            cues.append(round(self.t_big, 2))
        return cues

    def frame(self, t):
        img = self.bg.copy()
        texts = []
        b = self.b
        items = b.get("items", [])
        for i, it in enumerate(items):
            cx, cy = self.pos[i]
            k = back((t - self.t_in[i]) / .38)
            if t < self.t_in[i]:
                continue
            icon = it.get("icon", "box")
            then = it.get("then") if isinstance(it.get("then"), dict) else None
            swap_t = anchor_time(b["narration"], then.get("at"), self.speech, 1.2) if then else None
            if then and swap_t is not None and t >= swap_t:
                icon = then.get("icon", icon)
                k = max(k, 1.0) * (1 + .13 * math.sin(clamp((t - swap_t) / .35) * math.pi))
            dim = 1.0
            dd = it.get("dim_at")
            if dd:
                dt = anchor_time(b["narration"], dd, self.speech, 1.5)
                dim = 1 - .62 * ease((t - dt) / .3)
            bob = math.sin(t * 2.2 + i) * 3
            s = self.size * max(k, 0.01)
            pen = Pen(img, texts, cx, cy + bob, s, alpha=clamp(k * 1.4) * dim,
                      outline=PINK if dim > .8 else GREY, fill=PINK_D if dim > .8 else (70, 66, 70))
            if icon in ICONS:
                it_ = dict(it, icon=icon)
                DRAW[icon](pen, t, it_)
            tag, label = it.get("tag"), it.get("label")
            fa = clamp((t - self.t_in[i] - .1) / .25) * dim
            if tag:
                texts.append((str(tag), 44, WHITE, cx, cy - self.size / 2 - 52, fa))
            if label:
                texts.append((str(label), 40, PINK if it.get("hl") else WHITE, cx, cy + self.size / 2 + 42, fa))
        out = img.resize((WV, HV), Image.LANCZOS).convert("RGBA")
        layer = Image.new("RGBA", (WV, HV), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        top = b.get("top")
        if top:
            draw_text_block(d, top, 54, PINK, WV / 2, 150, 620, 3, ease((t - .1) / .35), self.font)
        big = b.get("big")
        if big and t >= self.t_big:
            kk = back((t - self.t_big) / .35)
            y = 1000 if items else 520
            size = (96 if items else 128) * (.8 + .2 * min(kk, 1.1))
            col = PINK if b.get("big_hl") else WHITE
            draw_text_block(d, big, size, col, WV / 2, y - size * .6, 640, 3, clamp(kk * 1.5), self.font)
        for s, size, color, x, y, a in texts:
            if a <= 0.01:
                continue
            f = font("bold", max(10, int(size)), self.font)
            w = d.textlength(s, font=f)
            ac = int(255 * clamp(a))
            d.text((x - w / 2, y - size * .62), s, font=f, fill=tuple(color[:3]) + (ac,),
                   stroke_width=max(2, int(size / 16)), stroke_fill=(20, 20, 22, ac))
        out.alpha_composite(layer)
        name = self.cfg.get("channel_name", "")
        if name:
            dd = ImageDraw.Draw(out)
            f = font("bold", 22, self.font)
            dd.text(((WV - dd.textlength(name, font=f)) / 2, 1196), name, font=f, fill=(150, 146, 152, 255))
        out = out.convert("RGB")
        a0 = min(1.0, t / .18)
        if a0 < 1.0:
            out = Image.blend(Image.new("RGB", (WV, HV), BG), out, a0)
        return out

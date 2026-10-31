"""Moteur d'animation verticale 9:16 (YouTube Shorts) : une métaphore visuelle par séquence."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

import anim
from anim import Canvas, K, font, vgrad

WV, HV, FPS = 720, 1280, 24
RED = (255, 52, 84)
PALETTES = [
    {"top": (11, 13, 18), "bot": (3, 4, 7), "acc": (60, 255, 170)},
    {"top": (24, 22, 9), "bot": (8, 7, 2), "acc": (255, 205, 70)},
    {"top": (8, 17, 24), "bot": (2, 6, 11), "acc": (80, 205, 255)},
    {"top": (22, 10, 22), "bot": (7, 2, 9), "acc": (255, 115, 205)},
]
KINDS = ("chart", "traffic", "sliders", "acrostic", "bars", "battery", "hourglass", "counter", "text")
_bg_cache = {}


def make_bg(pal_idx):
    if pal_idx in _bg_cache:
        return _bg_cache[pal_idx]
    pal = PALETTES[pal_idx]
    size = (WV * K, HV * K)
    bg = vgrad(size, pal["top"], pal["bot"])
    vig = Image.radial_gradient("L").resize(size).point(lambda v: int(v * .55))
    bg = Image.composite(Image.new("RGB", size, (0, 0, 0)), bg, vig)
    noise = Image.effect_noise((size[0] // 3, size[1] // 3), 30).resize(size).convert("RGB")
    bg = Image.blend(bg, noise, .035)
    _bg_cache[pal_idx] = bg
    return bg


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def partial(pts, frac):
    """Début d'une polyligne sur la fraction `frac` de sa longueur."""
    if frac <= 0:
        return []
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    target, acc, out = sum(seg) * clamp(frac), 0.0, [pts[0]]
    for i, s in enumerate(seg):
        if acc + s >= target:
            r = (target - acc) / s if s else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r))
            return out
        acc += s
        out.append(pts[i + 1])
    return out


def neon_line(cv, pts, color, w=5, a=1.0):
    if len(pts) < 2:
        return
    cv.polyline(pts, w * 3.4, color + (int(46 * a),))
    cv.polyline(pts, w * 1.8, color + (int(70 * a),))
    cv.polyline(pts, w, color + (int(255 * a),))


def silhouette(cv, x, y, h=96, col=(245, 245, 245)):
    cv.circ((x, y - h + 12), 12, col)
    cv.line((x, y - h + 26), (x, y - 38), 16, col)
    cv.line((x - 5, y - 40), (x - 8, y), 10, col)
    cv.line((x + 5, y - 40), (x + 8, y), 10, col)


# ----------------------------------------------------------------------------
# Métaphores
# ----------------------------------------------------------------------------
def d_chart(cv, img, p, t, par, pal):
    rnd = random.Random(par.get("seed", 3))
    down = [(60 + i * 20, 650 + i * 29 + (rnd.uniform(-24, 24) if 0 < i < 12 else 0)) for i in range(13)]
    down[-1] = (300, 1000)
    up = [(300 + i * 23, 1000 - i * 22 + (rnd.uniform(-26, 26) if 0 < i < 16 else 0)) for i in range(17)]
    up[-1] = (668, 650)
    neon_line(cv, partial(down, ease(p / .42)), RED)
    if p > .5:
        neon_line(cv, partial(up, ease((p - .5) / .45)), pal["acc"])
    if .36 < p < .62:
        silhouette(cv, 300, 1000 - 4)


def d_traffic(cv, img, p, t, par, pal):
    base = 1010
    cv.line((40, base + 4), (680, base + 4), 3, (90, 90, 100, 160))
    cv.rect((548, 660, 562, base), (70, 70, 80))
    cv.rect((520, 560, 590, 690), (28, 28, 34), 10)
    green = p >= .5
    for i, (c, on) in enumerate([(RED, not green), ((255, 190, 60), False), ((70, 255, 150), green)]):
        cy = 592 + i * 40
        if on:
            cv.circ((555, cy), 30, c + (60,))
        cv.circ((555, cy), 13, c if on else (50, 50, 56))
    x = 150 if not green else 150 + 900 * ease((p - .5) / .5) ** 1.6
    if x > 700:
        return
    col = (120, 120, 255)
    y = base
    cv.rect((x, y - 40, x + 210, y - 6), col, 14)
    cv.poly([(x + 48, y - 40), (x + 74, y - 74), (x + 146, y - 74), (x + 174, y - 40)], col)
    cv.poly([(x + 62, y - 42), (x + 82, y - 68), (x + 110, y - 68), (x + 110, y - 42)], (180, 190, 255))
    for wx in (x + 48, x + 160):
        cv.circ((wx, y - 4), 22, (22, 22, 28))
        cv.circ((wx, y - 4), 9, (160, 160, 170))
    if not green:                                    # deuxième voiture derrière, sombre
        cv.rect((x - 190, y - 36, x - 12, y - 6), (60, 60, 68), 12)
        cv.poly([(x - 150, y - 36), (x - 128, y - 62), (x - 70, y - 62), (x - 46, y - 36)], (60, 60, 68))
        for wx in (x - 150, x - 56):
            cv.circ((wx, y - 4), 19, (22, 22, 28))


def d_sliders(cv, img, p, t, par, pal):
    labels = par["labels"]
    hi = par["highlight"]
    cols, rows = (130, 360, 590), (700, 860)
    for i, name in enumerate(labels[:6]):
        cx, cy = cols[i % 3], rows[i // 3]
        f = font("bold", 26 * K)
        w = ImageDraw.Draw(Image.new("L", (1, 1))).textlength(name, font=f) / K
        cv.text((cx - w / 2, cy - 48), name, f, (170, 170, 178, 255))
        cv.line((cx - 70, cy), (cx + 70, cy), 5, (70, 70, 78, 255))
        v = .04
        col = (120, 120, 126, 255)
        if i == hi:
            v = .04 + .96 * ease((p - .08) / .6)
            col = pal["acc"] + (255,)
            cv.line((cx - 70, cy), (cx - 70 + 140 * v, cy), 12, pal["acc"] + (50,))
            cv.line((cx - 70, cy), (cx - 70 + 140 * v, cy), 5, col)
        kx = cx - 70 + 140 * v
        cv.circ((kx, cy), 9, col)
        if i == hi:
            cv.poly([(kx + 6, cy + 8), (kx + 6, cy + 34), (kx + 13, cy + 27), (kx + 19, cy + 38), (kx + 24, cy + 35), (kx + 18, cy + 25), (kx + 28, cy + 24)],
                    (235, 235, 245, 240))


def d_acrostic(cv, img, p, t, par, pal):
    word, items = par["word"], par["items"]
    n = len(word)
    step = min(58, 450 // max(n, 1))
    y0 = 640
    for i, ch in enumerate(word):
        a = ease((p - .04 - i * (.72 / n)) / .1)
        if a <= 0:
            continue
        y = y0 + i * step
        cv.text((150, y), ch, font("bold", 44 * K), pal["acc"] + (int(255 * a),))
        rest = items[i][1:] if i < len(items) and items[i] else ""
        cv.text((150 + 38, y + 10), rest, font("bold", 30 * K), (225, 225, 230, int(225 * a)))


def d_bars(cv, img, p, t, par, pal):
    n, base = 12, 1030
    cv.line((60, base + 6), (660, base + 6), 3, (110, 110, 118, 200))
    for i in range(n):
        h = 26 * 1.28 ** i
        a = ease((p - .04 - i * .06) / .12)
        if a <= 0:
            continue
        hh = h * a
        x = 70 + i * 50
        cv.rect((x - 4, base - hh - 6, x + 34, base), pal["acc"] + (46,), 4)
        cv.rect((x, base - hh, x + 30, base), pal["acc"] + (255,), 3)


def d_battery(cv, img, p, t, par, pal):
    x0, y0, x1, y1 = 130, 700, 560, 880
    cv.rect((x0, y0, x1, y1), (200, 200, 208), 24)
    cv.rect((x0 + 8, y0 + 8, x1 - 8, y1 - 8), (10, 10, 14), 18)
    cv.rect((x1, y0 + 55, x1 + 22, y1 - 55), (200, 200, 208), 6)
    if p < .5:
        lvl, col = .8 - .72 * ease(p / .45), RED
    else:
        lvl, col = .08 + .92 * ease((p - .5) / .45), pal["acc"]
    wdt = (x1 - x0 - 36) * lvl
    cv.rect((x0 + 18, y0 + 18, x0 + 18 + wdt, y1 - 18), col + (60,), 12)
    cv.rect((x0 + 22, y0 + 22, x0 + 18 + max(wdt - 4, 0), y1 - 22), col + (255,), 10)
    if p >= .5:
        cv.poly([(355, 730), (300, 810), (338, 810), (318, 855), (392, 770), (350, 770)], (255, 255, 255, 235))


def d_hourglass(cv, img, p, t, par, pal):
    f = ease(p)
    sand = (255, 200, 80)
    top_lvl, bot_lvl = 1 - f, f
    ytop = 760 - top_lvl * 150 * .92
    wtop = 230 * (760 - ytop) / 150
    if top_lvl > .02:
        cv.poly([(360 - wtop / 2, ytop), (360 + wtop / 2, ytop), (360, 760)], sand + (255,))
    yb = 940 - bot_lvl * 150 * .9
    wb = 230 * (yb - 790) / 150
    if bot_lvl > .02:
        cv.poly([(360 - wb / 2, yb), (360 + wb / 2, yb), (475, 940), (245, 940)], sand + (255,))
    if 0 < f < 1:
        cv.line((360, 760), (360, yb), 3, sand + (255,))
    ln = (205, 205, 212, 255)
    cv.polyline([(245, 610), (475, 610), (360, 760), (475, 940), (245, 940), (360, 790), (245, 610)], 5, ln)
    cv.line((230, 610), (490, 610), 8, ln)
    cv.line((230, 940), (490, 940), 8, ln)


def d_counter(cv, img, p, t, par, pal):
    a, b = par["from"], par["to"]
    v = int(round(a + (b - a) * ease(p / .85)))
    s = str(v)
    size = 200 if len(s) < 4 else 150
    f = font("bold", size * K)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = d.textlength(s, font=f) / K
    cv.d.text(((WV - w) / 2 * K, 690 * K), s, font=f, fill=pal["acc"] + (255,))
    cv.d.text(((WV - w) / 2 * K + 4, 690 * K + 4), "", font=f, fill=(0, 0, 0, 0))


def d_text(cv, img, p, t, par, pal):
    pass


DRAW = {"chart": d_chart, "traffic": d_traffic, "sliders": d_sliders, "acrostic": d_acrostic, "bars": d_bars,
        "battery": d_battery, "hourglass": d_hourglass, "counter": d_counter, "text": d_text}


# ----------------------------------------------------------------------------
# Séquence (texte + métaphore)
# ----------------------------------------------------------------------------
def text_layer(text, size, color, y, glow=False, maxw=620, cfg_font=""):
    layer = Image.new("RGBA", (WV, HV), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for sz in range(size, 29, -2):
        f = font("bold", sz, cfg_font)
        lines = anim._wrap(d, text, f, maxw)
        if len(lines) <= 2:
            break
    lh = int(sz * 1.3)
    for i, ln in enumerate(lines):
        x = (WV - d.textlength(ln, font=f)) / 2
        d.text((x, y + i * lh), ln, font=f, fill=color + (255,))
    bottom = y + len(lines) * lh
    if glow:
        g = layer.filter(ImageFilter.GaussianBlur(11))
        g.putalpha(g.getchannel("A").point(lambda v: min(255, int(v * 1.5))))
        layer = Image.alpha_composite(g, layer)
    return layer, bottom


def _paste_faded(img, layer, f):
    if f <= 0:
        return
    if f < 1:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * f)))
    img.paste(layer, (0, 0), layer)


class BeatRenderer:
    def __init__(self, beat, dur, pal_idx, cfg, last=False):
        self.b, self.dur, self.last = beat, max(dur, 3.0), last
        self.pal = PALETTES[pal_idx]
        self.bg = make_bg(pal_idx)
        c = cfg.get("font_bold", "")
        self.la, bottom = text_layer(beat.get("a", ""), 46, (245, 245, 245), 290, False, cfg_font=c)
        self.lb, _ = text_layer(beat.get("b", ""), 46, self.pal["acc"], bottom + 14, True, cfg_font=c)
        self.foot = self._footer(cfg)

    def _footer(self, cfg):
        layer = Image.new("RGBA", (WV, HV), (0, 0, 0, 0))
        cv = Canvas(layer)
        cv.circ((360, 1148), 17, (238, 232, 216, 255))
        cv.line((343, 1142), (377, 1142), 5, (205, 30, 36, 255))
        name = cfg.get("channel_name", "")
        if name:
            f = font("bold", 22, cfg.get("font_bold", ""))
            d = ImageDraw.Draw(layer)
            small = layer.resize((WV, HV))
            ImageDraw.Draw(small).text(((WV - d.textlength(name, font=f)) / 2, 1182), name, font=f, fill=(190, 190, 196, 255))
            layer = small
        return layer.resize((WV, HV), Image.LANCZOS) if layer.size != (WV, HV) else layer

    def frame(self, t):
        p = clamp(t / self.dur)
        img = self.bg.copy()
        cv = Canvas(img)
        DRAW[self.b["kind"]](cv, img, p, t, self.b, self.pal)
        out = img.resize((WV, HV), Image.BILINEAR).convert("RGBA")
        _paste_faded(out, self.la, ease((t - .25) / .5))
        _paste_faded(out, self.lb, ease((p - .5) / .1))
        out.alpha_composite(self.foot)
        if self.last:
            self._cta(out, ease((t - .8) / .5))
        out = out.convert("RGB")
        a0 = min(1.0, t / .3)
        if a0 < 1.0:
            out = Image.blend(Image.new("RGB", (WV, HV)), out, a0)
        return out

    def _cta(self, out, f):
        if f <= 0:
            return
        layer = Image.new("RGBA", (WV, HV), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        d.rounded_rectangle([200, 880, 520, 960], radius=40, fill=(214, 28, 28, int(255 * f)))
        d.polygon([(232, 904), (232, 936), (260, 920)], fill=(255, 255, 255, int(255 * f)))
        d.text((278, 905), "ABONNE-TOI", font=font("bold", 30), fill=(255, 255, 255, int(255 * f)))
        out.alpha_composite(layer)

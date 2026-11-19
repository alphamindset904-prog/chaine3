"""Moteur d'animation 9:16 « braquage » : décors dessinés, personnages cartoon, effets, sous-titres mot à mot.

Tout est dessiné par le programme (Pillow) : aucune image à fournir, rien qui puisse tomber en panne.
Repère logique 540x960, dessiné en x2 (1080x1920) puis recadré/réduit en 720x1280 (caméra qui bouge).
"""
import asyncio
import math
import random
import time
import wave
from array import array

from PIL import Image, ImageDraw, ImageFilter

import anim

LW, LH, S = 540, 960, 2
CW, CH = LW * S, LH * S
OW, OH, FPS = 720, 1280, 24
GY = 560                       # ligne du sol (repère logique)
INK = (32, 22, 34)

SCENES = ("street_night", "bank_front", "bank_inside", "vault", "hideout", "chase", "police_hq", "museum",
          "beach", "jail")
KINDS = ("thief", "boss", "guard", "cop", "banker", "civilian", "prisoner", "fox", "biscuit", "detective")
NAMES = {"fox": "LE RENARD", "biscuit": "BISCUIT", "detective": "INSP. MOUCHOIR"}
ACTIONS = ("idle", "walk", "run", "sneak", "hands_up", "point", "carry", "celebrate", "talk")
FXS = ("none", "alarm", "siren", "money", "flash", "lights_off", "shake")
SKINS = [(244, 204, 166), (222, 170, 128), (176, 120, 84), (120, 80, 56), (250, 214, 184)]


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------------------
# Primitives de dessin (repère logique)
# ----------------------------------------------------------------------------
class Cv:
    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img, "RGBA")

    @staticmethod
    def _b(b):
        return [v * S for v in b]

    def rect(self, b, fill, r=0, ol=None, w=2.5):
        kw = {"fill": fill}
        if ol:
            kw.update(outline=ol, width=max(1, int(w * S)))
        if r:
            self.d.rounded_rectangle(self._b(b), radius=r * S, **kw)
        else:
            self.d.rectangle(self._b(b), **kw)

    def ell(self, b, fill, ol=None, w=2.5):
        kw = {"fill": fill}
        if ol:
            kw.update(outline=ol, width=max(1, int(w * S)))
        self.d.ellipse(self._b(b), **kw)

    def circ(self, c, r, fill, ol=None, w=2.5):
        self.ell((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill, ol, w)

    def poly(self, pts, fill, ol=None, w=2.5):
        p = [(x * S, y * S) for x, y in pts]
        self.d.polygon(p, fill=fill)
        if ol:
            self.d.line(p + [p[0]], fill=ol, width=max(1, int(w * S)), joint="curve")

    def line(self, p1, p2, w, fill):
        a, b = (p1[0] * S, p1[1] * S), (p2[0] * S, p2[1] * S)
        self.d.line([a, b], fill=fill, width=max(1, int(w * S)))
        r = w * S / 2
        for x, y in (a, b):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def limb(self, p1, p2, w, fill, ow=2.5):
        self.line(p1, p2, w + 2 * ow, INK)
        self.line(p1, p2, w, fill)

    def text(self, xy, s, size, fill, anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), s, font=anim.font("bold", int(size * S)), fill=fill, anchor=anchor)


def grad(img, box, top, bot):
    x0, y0, x1, y1 = [int(v * S) for v in box]
    img.paste(anim.vgrad((x1 - x0, y1 - y0), top, bot), (x0, y0))


def glow(img, c, r, color, alpha):
    size = int(r * 2 * S)
    layer = Image.new("RGBA", (size, size), color + (0,))
    ImageDraw.Draw(layer).ellipse([size * .2, size * .2, size * .8, size * .8], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(size * .14))
    img.alpha_composite(layer, (int(c[0] * S - size / 2), int(c[1] * S - size / 2))) if img.mode == "RGBA" else \
        img.paste(layer, (int(c[0] * S - size / 2), int(c[1] * S - size / 2)), layer)


# ----------------------------------------------------------------------------
# Décors (dessinés une fois, mis en cache)
# ----------------------------------------------------------------------------
def night_sky(cv, img, rnd, moon=True):
    grad(img, (0, 0, LW, GY), (12, 16, 46), (84, 48, 108))
    for _ in range(45):
        cv.circ((rnd.uniform(0, LW), rnd.uniform(0, 330)), rnd.uniform(.8, 2), (255, 255, 255, rnd.randint(110, 230)))
    if moon:
        glow(img, (430, 150), 120, (255, 240, 200), 120)
        cv.circ((430, 150), 44, (250, 244, 214))
        cv.circ((416, 140), 9, (232, 224, 190))
        cv.circ((446, 166), 6, (232, 224, 190))


def skyline(cv, rnd, base, col, lit=.35, hmin=120, hmax=300, wmin=46, wmax=90):
    x = -10
    while x < LW:
        w, h = rnd.randint(wmin, wmax), rnd.randint(hmin, hmax)
        cv.rect((x, base - h, x + w, base), col)
        for wy in range(int(base - h + 14), int(base - 16), 26):
            for wx in range(int(x + 10), int(x + w - 12), 22):
                if rnd.random() < lit:
                    cv.rect((wx, wy, wx + 10, wy + 14), (255, 214, 110))
        x += w + rnd.randint(0, 6)


def road(cv, img, y0=GY, dashes=True):
    cv.rect((0, y0, LW, y0 + 70), (112, 108, 134))                  # trottoir
    cv.rect((0, y0 + 70, LW, LH), (44, 44, 58))                      # route
    cv.rect((0, y0 + 66, LW, y0 + 74), (80, 78, 98))
    if dashes:
        for x in range(10, LW, 110):
            cv.rect((x, 835, x + 60, 846), (235, 230, 200))


def lamp(cv, img, x):
    cv.rect((x - 4, 330, x + 4, GY + 30), (30, 30, 40))
    cv.rect((x - 22, 322, x + 22, 336), (30, 30, 40), r=5)
    glow(img, (x, 345), 90, (255, 214, 110), 130)
    cv.circ((x, 340), 9, (255, 240, 170))


def sc_street_night(cv, img, rnd):
    night_sky(cv, img, rnd)
    skyline(cv, rnd, GY - 40, (34, 30, 74), .3, 150, 330)
    skyline(cv, rnd, GY, (52, 44, 100), .4, 100, 230)
    road(cv, img)
    lamp(cv, img, 60)
    lamp(cv, img, 480)


def sc_bank_front(cv, img, rnd):
    night_sky(cv, img, rnd)
    skyline(cv, rnd, GY - 30, (34, 30, 74), .3, 140, 300)
    road(cv, img)
    stone, dark = (222, 212, 192), (170, 160, 140)
    cv.rect((60, 262, 480, GY - 24), stone, ol=INK)
    cv.poly([(46, 262), (270, 150), (494, 262)], (232, 222, 202), ol=INK)
    cv.circ((270, 218), 26, (240, 196, 50), ol=INK)
    cv.text((270, 218), "$", 34, (120, 80, 10), "mm")
    cv.rect((60, 262, 480, 296), dark, ol=INK)
    cv.text((270, 279), "BANQUE", 24, (60, 44, 30), "mm")
    for i in range(5):
        cx = 92 + i * 89
        cv.rect((cx - 15, 300, cx + 15, GY - 40), (240, 232, 214), ol=INK)
        cv.rect((cx - 21, 296, cx + 21, 308), dark, ol=INK)
        cv.rect((cx - 21, GY - 46, cx + 21, GY - 36), dark, ol=INK)
    for cx in (136, 404):
        cv.rect((cx - 24, 340, cx + 24, 440), (255, 210, 110), r=6, ol=INK)
        glow(img, (cx, 390), 70, (255, 214, 110), 90)
    cv.rect((238, 350, 302, GY - 40), (120, 74, 44), r=4, ol=INK)
    cv.rect((246, 360, 270, GY - 48), (170, 220, 240, 190))
    cv.rect((274, 360, 296, GY - 48), (170, 220, 240, 190))
    for i in range(3):
        cv.rect((44 + i * 6, GY - 24 + i * 8, 496 - i * 6, GY - 16 + i * 8), (200, 192, 176), ol=INK, w=2)


def sc_bank_inside(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (236, 210, 160), (206, 176, 126))
    cv.rect((0, 400, LW, GY), (122, 76, 46))
    for x in range(0, LW, 60):
        cv.rect((x + 6, 412, x + 54, GY - 8), (140, 92, 58), ol=(90, 54, 30), w=1.5)
    cv.circ((270, 190), 52, (250, 246, 232), ol=INK, w=4)
    cv.line((270, 190), (270, 156), 4, INK)
    cv.line((270, 190), (292, 200), 4, INK)
    for x in (110, 270, 430):
        cv.line((x, 0), (x, 70), 3, INK)
        cv.poly([(x - 36, 100), (x - 18, 66), (x + 18, 66), (x + 36, 100)], (60, 110, 80), ol=INK)
        glow(img, (x, 105), 100, (255, 226, 150), 150)
    for y in range(GY, LH, 48):
        for i, x in enumerate(range(0, LW, 54)):
            c = (236, 232, 222) if (i + (y // 48)) % 2 == 0 else (84, 84, 98)
            cv.rect((x, y, x + 54, y + 48), c)
    cv.rect((0, 468, LW, 560), (92, 54, 30), ol=INK)
    cv.rect((0, 460, LW, 476), (160, 108, 66), ol=INK)
    for x in (95, 270, 445):
        cv.rect((x - 62, 330, x + 62, 460), (170, 214, 232, 70), ol=INK, w=3)
        for bx in range(int(x - 50), int(x + 56), 20):
            cv.line((bx, 336), (bx, 456), 2, INK)
    for x in (24, 516):
        cv.rect((x - 16, 432, x + 16, 470), (170, 80, 50), ol=INK)
        for a in (-1, 0, 1):
            cv.ell((x + a * 16 - 12, 380, x + a * 16 + 12, 440), (60, 160, 80), ol=INK)


def sc_vault(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (46, 74, 88), (78, 110, 124))
    for x in range(0, LW, 90):
        cv.line((x, 0), (x, GY), 3, (36, 58, 70))
    cv.rect((0, GY, LW, LH), (40, 50, 58))
    for y in range(GY, LH, 60):
        cv.line((0, y), (LW, y), 2, (54, 66, 76))
    glow(img, (270, 330), 230, (255, 236, 170), 70)
    for x0 in (26, 414):                                        # lingots
        for row in range(4):
            for col in range(4 - row):
                bx = x0 + col * 34 + row * 17
                by = GY + 28 - row * 22
                cv.rect((bx, by - 18, bx + 32, by), (244, 194, 40), r=3, ol=INK, w=2)
                cv.rect((bx + 4, by - 14, bx + 20, by - 9), (255, 232, 130))
    glow(img, (70, GY - 30), 70, (255, 220, 90), 90)
    glow(img, (470, GY - 30), 70, (255, 220, 90), 90)


def dyn_vault(cv, t):
    c, a0 = (270, 330), t * .5
    cv.circ(c, 168, (92, 104, 116), ol=INK, w=4)
    cv.circ(c, 150, (176, 188, 198), ol=INK, w=4)
    for i in range(16):
        a = i * math.tau / 16
        cv.circ((c[0] + 134 * math.cos(a), c[1] + 134 * math.sin(a)), 5, (110, 122, 134), ol=INK, w=1.5)
    cv.circ(c, 104, (128, 140, 152), ol=INK, w=4)
    for i in range(3):
        a = a0 + i * math.tau / 3
        cv.limb((c[0] - 78 * math.cos(a), c[1] - 78 * math.sin(a)), (c[0] + 78 * math.cos(a), c[1] + 78 * math.sin(a)),
                12, (214, 222, 230))
        for s in (-1, 1):
            cv.circ((c[0] + s * 78 * math.cos(a), c[1] + s * 78 * math.sin(a)), 14, (226, 232, 238), ol=INK)
    cv.circ(c, 30, (240, 196, 50), ol=INK, w=3)
    cv.circ(c, 11, (150, 100, 20))


def sc_hideout(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (30, 28, 42), (46, 40, 58))
    for y in range(0, GY, 36):
        for i, x in enumerate(range(-30 if (y // 36) % 2 else 0, LW, 70)):
            cv.rect((x + 2, y + 2, x + 68, y + 34), (50, 44, 62), w=1)
    cv.rect((0, GY, LW, LH), (66, 44, 36))
    for x in range(0, LW, 78):
        cv.line((x, GY), (x, LH), 2, (46, 30, 26))
    cv.rect((34, 140, 234, 340), (170, 124, 74), ol=INK, w=4)
    pins = [(70, 190), (130, 175), (190, 205), (95, 270), (170, 290), (205, 250)]
    for i, (px, py) in enumerate(pins):
        cv.rect((px - 18, py - 20, px + 18, py + 20), (240, 236, 224), ol=INK, w=2)
        cv.circ((px, py - 4), 8, (150, 120, 100))
    for a, b in zip(pins, pins[1:] + pins[:1]):
        cv.line(a, b, 2, (210, 40, 40))
    cv.rect((360, 170, 500, 330), (20, 20, 30), ol=INK, w=4)
    for y in range(180, 326, 18):
        cv.rect((366, y, 494, y + 10), (70, 80, 110))
    cv.line((270, 0), (270, 120), 3, INK)
    cv.poly([(226, 168), (250, 118), (290, 118), (314, 168)], (232, 186, 64), ol=INK)
    glow(img, (270, 190), 170, (255, 224, 140), 130)
    cv.poly([(250, 170), (290, 170), (440, GY + 50), (100, GY + 50)], (255, 232, 160, 34))
    cv.rect((92, 492, 448, 514), (128, 82, 52), ol=INK)
    for x in (110, 420):
        cv.rect((x, 514, x + 16, 596), (100, 62, 40), ol=INK)
    cv.poly([(130, 478), (410, 478), (440, 500), (100, 500)], (46, 100, 184), ol=INK, w=2)
    for i in range(4):
        cv.line((150 + i * 60, 482), (140 + i * 60 + 18, 498), 2, (210, 230, 255))
    cv.rect((170, 484, 290, 492), (210, 230, 255, 220))


def sc_chase(cv, img, rnd):
    grad(img, (0, 0, LW, 430), (70, 44, 120), (255, 150, 84))
    glow(img, (270, 420), 190, (255, 200, 110), 150)
    cv.circ((270, 400), 56, (255, 232, 160))
    skyline(cv, rnd, 440, (60, 36, 82), .25, 80, 210)
    cv.rect((0, 440, LW, LH), (54, 52, 66))
    cv.rect((0, 440, LW, 462), (94, 90, 110))


def car(cv, x, y, col, s=1.0, wheel_t=0.0, police=False, t=0.0, heads=False):
    def X(v):
        return x + v * s

    def Y(v):
        return y + v * s
    cv.ell((X(-120), Y(-6), X(120), Y(16)), (0, 0, 0, 80))
    cv.rect((X(-110), Y(-62), X(110), Y(-14)), col, r=16 * s, ol=INK, w=3)
    cv.poly([(X(-66), Y(-62)), (X(-42), Y(-104)), (X(52), Y(-104)), (X(84), Y(-62))], col, ol=INK, w=3)
    cv.poly([(X(-54), Y(-64)), (X(-36), Y(-96)), (X(-2), Y(-96)), (X(-2), Y(-64))], (176, 222, 244), ol=INK, w=2)
    cv.poly([(X(8), Y(-64)), (X(8), Y(-96)), (X(46), Y(-96)), (X(72), Y(-64))], (176, 222, 244), ol=INK, w=2)
    if police:
        cv.rect((X(-110), Y(-44), X(110), Y(-34)), (240, 240, 250))
        on = int(t * 8) % 2 == 0
        cv.rect((X(-24), Y(-118), X(-2), Y(-104)), (255, 40, 50) if on else (110, 20, 26), ol=INK, w=2)
        cv.rect((X(2), Y(-118), X(24), Y(-104)), (60, 110, 255) if not on else (24, 40, 110), ol=INK, w=2)
        glow(cv.img, (X(-13) if on else X(13), Y(-110)), 60 * s, (255, 40, 50) if on else (60, 110, 255), 160)
    if heads:
        for hx, mask in ((-26, True), (30, True)):
            cv.circ((X(hx), Y(-82)), 17 * s, (244, 204, 166), ol=INK, w=2)
            cv.rect((X(hx - 15), Y(-90), X(hx + 15), Y(-78)), (24, 24, 30))
            cv.circ((X(hx - 6), Y(-84)), 3 * s, (255, 255, 255))
            cv.circ((X(hx + 6), Y(-84)), 3 * s, (255, 255, 255))
    for wx in (-64, 66):
        cv.circ((X(wx), Y(-14)), 25 * s, (28, 28, 34), ol=INK, w=2)
        cv.circ((X(wx), Y(-14)), 11 * s, (186, 186, 198))
        a = wheel_t * 9
        cv.line((X(wx) + 10 * s * math.cos(a), Y(-14) + 10 * s * math.sin(a)),
                (X(wx) - 10 * s * math.cos(a), Y(-14) - 10 * s * math.sin(a)), 2, (90, 90, 104))


def dyn_chase(cv, t, p):
    off = (t * 520) % 110
    for x in range(-110, LW + 110, 110):
        cv.rect((x - off, 660, x - off + 60, 672), (235, 230, 200))
    for x in range(-200, LW + 200, 180):
        cv.rect((x - (t * 280) % 180, 470, x - (t * 280) % 180 + 70, 482), (90, 86, 108))
    bob = math.sin(t * 16) * 2.2
    car(cv, 160 + math.sin(t * 1.6) * 16, 610 + bob, (240, 240, 250), 1.0, t, police=True, t=t)
    car(cv, 130 + math.sin(t * 1.3 + 1) * 10, 530 + bob * .6, (240, 240, 250), .74, t, police=True, t=t + .2)
    car(cv, 385 + math.sin(t * 2) * 10, 590 - bob, (214, 48, 52), 1.12, t, heads=True)


def sc_police_hq(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (50, 94, 96), (38, 74, 78))
    cv.rect((0, GY, LW, LH), (72, 72, 80))
    for y in range(GY, LH, 56):
        cv.line((0, y), (LW, y), 2, (60, 60, 68))
    cv.rect((90, 100, 450, 380), (176, 128, 78), ol=INK, w=5)
    cv.rect((190, 130, 350, 330), (246, 238, 214), ol=INK, w=3)
    cv.text((270, 158), "RECHERCHÉS", 17, (150, 30, 30), "mm")
    cv.circ((270, 232), 40, (60, 60, 70), ol=INK)
    cv.rect((230, 224, 310, 244), (20, 20, 26))
    cv.rect((246, 214, 294, 218), (20, 20, 26))
    for x, y in ((118, 150), (118, 250), (410, 170), (410, 280)):
        cv.rect((x - 22, y - 26, x + 22, y + 26), (240, 236, 224), ol=INK, w=2)
        cv.circ((x, y - 6), 10, (150, 120, 100))
        cv.line((x, y), (270, 232), 2, (210, 40, 40))
    cv.rect((0, 476, LW, 560), (112, 76, 50), ol=INK)
    cv.rect((0, 466, LW, 482), (150, 104, 66), ol=INK)
    cv.rect((70, 440, 110, 468), (240, 240, 240), r=6, ol=INK)
    cv.line((80, 440), (80, 420), 3, (240, 240, 240))
    cv.rect((420, 448, 470, 468), (250, 246, 232), ol=INK, w=2)
    cv.rect((428, 440, 478, 460), (236, 232, 218), ol=INK, w=2)
    cv.line((340, 468), (340, 400), 4, INK)
    cv.poly([(310, 400), (370, 400), (360, 376), (320, 376)], (240, 200, 70), ol=INK)
    glow(img, (340, 392), 90, (255, 226, 140), 120)


def sc_museum(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (196, 184, 164), (170, 156, 136))
    cv.rect((0, GY, LW, LH), (212, 206, 198))
    for y in range(GY, LH, 70):
        cv.line((0, y), (LW, y), 2, (186, 180, 172))
    arts = [(48, 150, 150, 300, (60, 120, 170), (240, 200, 60)), (196, 130, 344, 270, (190, 80, 70), (240, 230, 200)),
            (390, 150, 492, 300, (70, 140, 90), (230, 140, 60))]
    for x0, y0, x1, y1, a, b in arts:
        cv.rect((x0 - 8, y0 - 8, x1 + 8, y1 + 8), (150, 104, 52), ol=INK, w=3)
        cv.rect((x0, y0, x1, y1), a)
        cv.circ(((x0 + x1) / 2, (y0 + y1) / 2 - 10), (x1 - x0) / 4, b)
        cv.poly([(x0, y1), ((x0 + x1) / 2, y1 - 50), (x1, y1)], (30, 30, 50, 140))
    for x in (120, 270, 420):
        cv.poly([(x - 30, 0), (x + 30, 0), (x + 80, 330), (x - 80, 330)], (255, 246, 210, 30))
    cv.rect((228, 470, 312, 560), (240, 236, 228), ol=INK, w=3)
    cv.rect((220, 462, 320, 476), (250, 246, 238), ol=INK, w=3)
    cv.rect((236, 380, 304, 464), (180, 220, 240, 70), ol=INK, w=3)
    glow(img, (270, 430), 80, (170, 230, 255), 140)
    cv.poly([(270, 400), (292, 420), (270, 450), (248, 420)], (150, 230, 255), ol=INK, w=2)
    cv.poly([(270, 400), (270, 450), (248, 420)], (210, 246, 255))


def sc_beach(cv, img, rnd):
    grad(img, (0, 0, LW, 440), (255, 120, 100), (255, 214, 130))
    glow(img, (270, 400), 240, (255, 220, 140), 160)
    cv.circ((270, 392), 72, (255, 240, 180))
    cv.rect((0, 436, LW, GY + 8), (54, 160, 204))
    for y in range(448, GY, 20):
        for x in range(-20 + (y % 40), LW, 80):
            cv.line((x, y), (x + 34, y), 3, (210, 240, 250))
    cv.rect((0, GY + 8, LW, LH), (242, 214, 152))
    pts = [(70, GY + 40), (84, 430), (110, 330), (150, 270)]
    for a, b in zip(pts, pts[1:]):
        cv.limb(a, b, 16, (136, 90, 52))
    for ang in (-2.6, -1.9, -1.2, -.5, .2):
        ex, ey = 150 + 90 * math.cos(ang), 270 + 70 * math.sin(ang) + 26
        cv.poly([(150, 268), (150 + 50 * math.cos(ang - .35), 252 + 40 * math.sin(ang - .35)), (ex, ey),
                 (150 + 50 * math.cos(ang + .35), 262 + 40 * math.sin(ang + .35))], (50, 150, 70), ol=INK, w=2)
    cv.circ((140, 280), 8, (110, 70, 30), ol=INK, w=2)
    cv.circ((160, 286), 8, (110, 70, 30), ol=INK, w=2)


def sc_jail(cv, img, rnd):
    grad(img, (0, 0, LW, GY), (82, 86, 100), (62, 66, 80))
    cv.rect((0, GY, LW, LH), (58, 58, 66))
    for y in range(GY, LH, 64):
        cv.line((0, y), (LW, y), 2, (46, 46, 54))
    cv.poly([(330, 0), (480, 0), (540, 600), (260, 600)], (255, 244, 200, 26))
    cv.rect((340, 60, 480, 200), (30, 34, 44), ol=INK, w=4)
    cv.rect((346, 66, 474, 194), (150, 190, 230))
    for x in range(366, 474, 28):
        cv.rect((x - 4, 60, x + 4, 200), INK)
    cv.rect((30, 440, 220, 470), (110, 90, 70), ol=INK)
    cv.rect((30, 470, 220, 490), (196, 200, 214), ol=INK)
    cv.rect((30, 330, 220, 350), (110, 90, 70), ol=INK)
    cv.rect((30, 350, 220, 370), (196, 200, 214), ol=INK)
    for x in (36, 214):
        cv.rect((x - 5, 330, x + 5, 560), (70, 60, 50), ol=INK, w=1.5)
    for x in range(20, LW, 70):                                  # barreaux au premier plan
        cv.rect((x - 8, 0, x + 8, 600), (24, 26, 34, 215))
    cv.rect((0, 0, LW, 28), (24, 26, 34, 215))


BUILD = {"street_night": sc_street_night, "bank_front": sc_bank_front, "bank_inside": sc_bank_inside,
         "vault": sc_vault, "hideout": sc_hideout, "chase": sc_chase, "police_hq": sc_police_hq,
         "museum": sc_museum, "beach": sc_beach, "jail": sc_jail}
_bg = {}


def get_bg(name):
    if name not in _bg:
        img = Image.new("RGB", (CW, CH), (0, 0, 0))
        BUILD[name](Cv(img), img, random.Random(sum(map(ord, name))))
        _bg[name] = img
    return _bg[name]


# ----------------------------------------------------------------------------
# Personnages
# ----------------------------------------------------------------------------
OUTFIT = {
    "thief": {"shirt": (250, 250, 250), "stripe": (30, 30, 40), "pants": (44, 44, 58), "hat": "beanie", "hc": (30, 30, 40), "mask": True},
    "boss": {"shirt": (118, 44, 156), "pants": (60, 36, 80), "hat": "fedora", "hc": (50, 36, 40), "glasses": True},
    "guard": {"shirt": (64, 116, 196), "pants": (44, 64, 116), "hat": "cap", "hc": (44, 80, 150)},
    "cop": {"shirt": (34, 56, 130), "pants": (26, 38, 86), "hat": "cop", "hc": (24, 34, 92), "badge": True},
    "banker": {"shirt": (150, 152, 164), "pants": (110, 112, 124), "hat": "bald", "hc": (120, 100, 80), "tie": True, "glasses": True},
    "civilian": {"shirt": (244, 148, 44), "pants": (62, 94, 154), "hat": "hair", "hc": (92, 56, 34)},
    "fox": {"shirt": (30, 38, 56), "pants": (30, 30, 42), "hat": "fox", "hc": (240, 124, 36), "mask": True,
            "maskcol": (240, 124, 36), "scarf": (214, 56, 50)},
    "biscuit": {"shirt": (250, 250, 250), "stripe": (60, 92, 204), "pants": (60, 60, 92), "hat": "beanie", "hc": (60, 92, 204),
                "mask": True, "wide": 1.38},
    "detective": {"shirt": (198, 166, 112), "pants": (86, 68, 52), "hat": "fedora", "hc": (156, 124, 74), "coat": True,
                  "stache": True, "prop": "lens"},
    "prisoner": {"shirt": (250, 250, 250), "stripe": (30, 30, 40), "pants": (250, 250, 250), "hat": "hair", "hc": (60, 44, 36)},
}


def bag(cv, x, y, r):
    cv.circ((x, y), r, (170, 132, 76), ol=INK, w=2.5)
    cv.poly([(x - r * .35, y - r * .85), (x + r * .35, y - r * .85), (x + r * .55, y - r * 1.35), (x - r * .55, y - r * 1.35)],
            (170, 132, 76), ol=INK, w=2.5)
    cv.text((x, y + r * .08), "$", int(r * 1.3), (255, 255, 255), "mm")


def person(cv, kind, x, fy, h, t, action, face, idx, skin, mood=None):
    o = OUTFIT[kind]
    ph = t * (11 if action == "run" else 7 if action in ("walk", "carry") else 3.6 if action == "sneak" else 2.4) + idx * 1.7
    moving = action in ("walk", "run", "sneak", "carry")
    bob = abs(math.sin(ph)) * (h * .035 if moving else 0) + math.sin(t * 2.6 + idx) * h * .008
    if action == "celebrate":
        bob = abs(math.sin(t * 6 + idx)) * h * .09
    if action == "sneak":
        h *= .92
    hip, sh = fy - h * .28 - bob, fy - h * .58 - bob
    hr = h * .185
    hx, hy = x + (face * h * .03 if action == "sneak" else 0), sh - hr * .82
    cv.ell((x - h * .24, fy - h * .02, x + h * .24, fy + h * .045), (0, 0, 0, 70))
    sw = math.sin(ph) * (.9 if action == "run" else .5)
    for side, leg in ((-1, 0), (1, 1)):                          # jambes
        a = sw * (1 if leg else -1) if moving else side * .06
        fx = x + side * h * .08 + math.sin(a) * h * .26
        ffy = fy - max(0, -math.cos(a)) * 0 - (abs(math.sin(a)) * h * .04 if moving else 0)
        cv.limb((x + side * h * .07, hip), (fx, ffy - h * .03), h * .12, o["pants"])
        cv.ell((fx - h * .09 + face * h * .03, ffy - h * .05, fx + h * .09 + face * h * .03, ffy + h * .012), (36, 28, 34), ol=INK, w=2)
    tw = h * .16 * o.get("wide", 1)                               # torse
    body = (x - tw, sh, x + tw, hip + h * .04)
    cv.rect(body, o["shirt"], r=h * .06, ol=INK, w=2.5)
    if "stripe" in o:
        for yy in range(int(sh + h * .04), int(hip + h * .02), int(h * .075)):
            cv.rect((x - tw + 2, yy, x + tw - 2, yy + h * .035), o["stripe"])
    if o.get("tie"):
        cv.poly([(x - 6, sh), (x + 6, sh), (x + 9, sh + h * .22), (x, sh + h * .26), (x - 9, sh + h * .22)], (190, 40, 50), ol=INK, w=1.5)
    if o.get("badge"):
        cv.circ((x - tw * .45, sh + h * .1), h * .028, (244, 204, 70), ol=INK, w=1.5)
    if o.get("coat"):
        for s_ in (-1, 1):
            cv.poly([(x + s_ * tw * .9, sh), (x + s_ * 3, sh), (x + s_ * tw * .25, sh + h * .2)], (150, 118, 70), ol=INK, w=1.5)
        cv.rect((x - tw, hip - h * .03, x + tw, hip + h * .01), (110, 80, 44), ol=INK, w=1.5)
    if o.get("scarf"):
        cv.rect((x - tw * 1.05, sh - h * .02, x + tw * 1.05, sh + h * .07), o["scarf"], r=h * .03, ol=INK, w=2)
        sw_ = math.sin(t * 5 + idx) * h * .02
        cv.poly([(x + tw * .5, sh + h * .05), (x + tw + sw_, sh + h * .05), (x + tw * 1.3 + sw_ * 2, sh + h * .3),
                 (x + tw * .75 + sw_, sh + h * .3)], o["scarf"], ol=INK, w=2)
    L = h * .27
    sy = sh + h * .05
    held = hand = None
    arms = []
    if action == "hands_up":
        arms = [(-1, math.pi - .35, -1), (1, math.pi - .35, 1)]
    elif action == "celebrate":
        s2 = math.sin(t * 6 + idx) * .3
        arms = [(-1, math.pi - .5 + s2, -1), (1, math.pi - .5 - s2, 1)]
    elif action == "point":
        arms = [(-1, .15, -1), (1, math.pi / 2 + .1, face)]
    elif action == "carry":
        arms = [(-1, sw * .5 + .1, -1), (1, .75, face)]
    elif moving:
        arms = [(-1, -sw, -1), (1, sw, 1)]
    else:
        sway = math.sin(t * 2.2 + idx) * .07
        arms = [(-1, .14 + sway, -1), (1, .14 - sway, 1)]
    for side, a, sgn in arms:
        s0 = (x + side * tw * .9, sy)
        e = (s0[0] + L * math.sin(a) * sgn * (1 if a != 0 else 0), s0[1] + L * math.cos(a))
        if action == "carry" and side == 1:
            held = e
        if side == 1:
            hand = e
        cv.limb(s0, e, h * .095, o["shirt"] if "stripe" not in o else (240, 240, 240))
        cv.circ(e, h * .052, skin, ol=INK, w=2)
    if held:
        bag(cv, held[0] + face * h * .02, held[1] + h * .09, h * .11)
    if o.get("prop") == "lens" and hand:
        lx, ly = hand[0] + face * h * .07, hand[1] - h * .13
        cv.line(hand, (lx - face * h * .02, ly + h * .02), 3.5, (90, 60, 30))
        cv.circ((lx, ly - h * .02), h * .075, (190, 230, 250, 150), ol=(90, 60, 30), w=3.5)
    # tête
    cv.circ((hx, hy), hr, skin, ol=INK, w=2.8)
    openm = action in ("hands_up", "celebrate", "talk") and math.sin(t * 9 + idx) > -.2
    scared = action == "hands_up" or mood == "scared"
    ey = hy + hr * .05
    ex = hr * .42
    er = hr * (.26 if scared else .21)
    if o.get("mask"):
        cv.ell((hx - hr * 1.02, ey - hr * .3, hx + hr * 1.02, ey + hr * .46), o.get("maskcol", (22, 20, 28)))
        for s_ in (-1, 1):
            cv.ell((hx + s_ * ex - er, ey - er * .7, hx + s_ * ex + er, ey + er * .8), (255, 255, 255))
            cv.circ((hx + s_ * ex + face * er * .4, ey), er * .5, INK)
    elif o.get("glasses"):
        for s_ in (-1, 1):
            cv.rect((hx + s_ * ex - er * 1.2, ey - er, hx + s_ * ex + er * 1.2, ey + er), (24, 24, 32), r=4)
        cv.line((hx - ex + er, ey - er * .4), (hx + ex - er, ey - er * .4), 2, (24, 24, 32))
    else:
        for s_ in (-1, 1):
            cv.ell((hx + s_ * ex - er, ey - er * 1.1, hx + s_ * ex + er, ey + er * 1.1), (255, 255, 255), ol=INK, w=1.5)
            cv.circ((hx + s_ * ex + face * er * .35, ey), er * .52, INK)
        if scared:
            for s_ in (-1, 1):
                cv.line((hx + s_ * ex - er, ey - er * 2), (hx + s_ * ex + er, ey - er * 1.5 * (1 if s_ < 0 else 1)), 2.5, INK)
    my = hy + hr * .58
    if openm or scared:
        cv.ell((hx - hr * .2, my - hr * .1, hx + hr * .2, my + hr * .3), (150, 30, 40), ol=INK, w=2)
    else:
        cv.d.arc([(hx - hr * .28) * S, (my - hr * .22) * S, (hx + hr * .28) * S, (my + hr * .12) * S], 20, 160, fill=INK, width=int(2.4 * S))
    if o.get("stache"):
        cv.ell((hx - hr * .42, my - hr * .4, hx + hr * .42, my - hr * .06), (50, 34, 26), ol=INK, w=1.5)
    hat, hc = o["hat"], o["hc"]
    box = [(hx - hr) * S, (hy - hr) * S, (hx + hr) * S, (hy + hr) * S]
    if hat == "beanie":
        cv.d.pieslice(box, 180, 360, fill=hc, outline=INK, width=int(2.5 * S))
        cv.rect((hx - hr, hy - hr * .5, hx + hr, hy - hr * .18), (250, 250, 250), ol=INK, w=2)
        cv.circ((hx, hy - hr * 1.02), hr * .16, (250, 250, 250), ol=INK, w=2)
    elif hat == "fox":
        for s_ in (-1, 1):
            cv.poly([(hx + s_ * hr * .95, hy - hr * .3), (hx + s_ * hr * .8, hy - hr * 1.45), (hx + s_ * hr * .2, hy - hr * .85)],
                    hc, ol=INK, w=2.5)
            cv.poly([(hx + s_ * hr * .82, hy - hr * .5), (hx + s_ * hr * .74, hy - hr * 1.15), (hx + s_ * hr * .4, hy - hr * .8)],
                    (252, 204, 164))
        cv.d.pieslice(box, 180, 360, fill=hc, outline=INK, width=int(2.5 * S))
        cv.rect((hx - hr, hy - hr * .5, hx + hr, hy - hr * .18), (250, 250, 250), ol=INK, w=2)
    elif hat in ("cap", "cop"):
        cv.d.pieslice(box, 180, 360, fill=hc, outline=INK, width=int(2.5 * S))
        cv.rect((hx - hr * 1.1 + face * hr * .3, hy - hr * .3, hx + hr * 1.1 + face * hr * .3, hy - hr * .1), hc, r=3, ol=INK, w=2)
        if hat == "cop":
            cv.circ((hx, hy - hr * .62), hr * .17, (244, 204, 70), ol=INK, w=1.5)
    elif hat == "fedora":
        cv.ell((hx - hr * 1.5, hy - hr * .6, hx + hr * 1.5, hy - hr * .12), hc, ol=INK, w=2.5)
        cv.rect((hx - hr * .75, hy - hr * 1.3, hx + hr * .75, hy - hr * .35), hc, r=hr * .3, ol=INK, w=2.5)
        cv.rect((hx - hr * .75, hy - hr * .6, hx + hr * .75, hy - hr * .42), (190, 150, 60))
    elif hat == "hair":
        cv.d.pieslice(box, 190, 350, fill=hc, outline=INK, width=int(2.5 * S))
    elif hat == "bald":
        for s_ in (-1, 1):
            cv.ell((hx + s_ * hr * .98 - hr * .12, hy - hr * .2, hx + s_ * hr * .98 + hr * .12, hy + hr * .3), (200, 200, 200), ol=INK, w=1.5)


# ----------------------------------------------------------------------------
# Effets, caméra, sous-titres
# ----------------------------------------------------------------------------
_masks = {}


def tint(img, color, a):
    a = int(clamp(a, 0, 255))
    if a <= 0:
        return
    m = _masks.get(a)
    if m is None:
        m = _masks[a] = Image.new("L", (CW, CH), a)
    img.paste(color, (0, 0), m)


_side = {}


def side_tint(img, color, a, left):
    key = (left, int(a // 6))
    if key not in _side:
        g = Image.new("L", (CW, 1))
        g.putdata([int(max(0, 1 - (x / CW) / .6) * a) if left else int(max(0, 1 - ((CW - x) / CW) / .6) * a) for x in range(CW)])
        _side[key] = g.resize((CW, CH))
    img.paste(color, (0, 0), _side[key])


_dark = {}


def lights_off(img, cx, cy):
    if "m" not in _dark:
        m = Image.radial_gradient("L").resize((CW, CH)).point(lambda v: int(min(255, v * 1.7) * .9))
        _dark["m"] = m
    layer = Image.new("RGB", (CW, CH), (4, 6, 18))
    img.paste(layer, (0, 0), _dark["m"])


def bills(cv, t, seed=1):
    rnd = random.Random(seed)
    for i in range(26):
        x0, sp, ph, rot = rnd.uniform(20, LW - 20), rnd.uniform(.35, .7), rnd.random(), rnd.uniform(-3, 3)
        y = ((t * sp + ph) % 1.0) * (LH + 120) - 60
        x = x0 + math.sin(t * 2 + i) * 26
        a = rot * t + i
        pts = []
        for dx, dy in ((-20, -10), (20, -10), (20, 10), (-20, 10)):
            pts.append((x + dx * math.cos(a) - dy * math.sin(a * .7), y + dx * math.sin(a) * .5 + dy))
        cv.poly(pts, (98, 190, 108), ol=(40, 110, 60), w=1.5)
        cv.circ((x, y), 5, (180, 236, 190))


def caption_chunks(tokens):
    chunks, cur = [], []
    for i, tk in enumerate(tokens):
        cur.append(i)
        text = " ".join(tokens[j] for j in cur)
        if len(cur) >= 2 or len(text) >= 11 or tk[-1] in ".,!?;:…":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def word_times(tokens, dur, boundaries=None):
    """Début de chaque mot : repères réels du moteur vocal s'ils existent, sinon répartition proportionnelle."""
    if boundaries and len(boundaries) == len(tokens):
        return [b[0] for b in boundaries]
    w = []
    for tk in tokens:
        x = len(tk) + 1.5
        if tk[-1] in ".!?…":
            x += 5
        elif tk[-1] in ",;:":
            x += 2.5
        w.append(x)
    tot, acc, out = sum(w), 0.0, []
    for x in w:
        out.append(dur * .96 * acc / tot)
        acc += x
    return out


class Beat:
    def __init__(self, b, dur, idx, boundaries=None, intro=()):
        self.b, self.dur, self.idx = b, dur, idx
        self.intro = set(intro)
        self.tokens = b["narration"].split()
        self.starts = word_times(self.tokens, dur - .12, boundaries)
        self.chunks = caption_chunks(self.tokens)
        self.skins = [SKINS[(idx * 2 + i * 3) % len(SKINS)] for i in range(3)]

    # -- caméra
    def camera(self, t):
        e = ease(t / self.dur)
        z0, z1 = (1.0, 1.12) if self.idx % 2 == 0 else (1.14, 1.0)
        z = z0 + (z1 - z0) * e
        if t > self.dur * .58 and self.b["scene"] != "chase":
            z += .13
        fx = self.b["fx"]
        sx = sy = 0.0
        if fx in ("shake", "flash", "alarm"):
            amp = (22 if fx == "shake" else 10) * math.exp(-t * (3 if fx == "shake" else 1.2))
            sx, sy = math.sin(t * 61) * amp, math.cos(t * 53) * amp
        cx = CW / 2 + ((self.idx % 3) - 1) * 40 * (e - .5) + sx
        cy = CH * .42 + sy
        w, h = CW / z, CH / z
        x0 = clamp(cx - w / 2, 0, CW - w)
        y0 = clamp(cy - h / 2, 0, CH - h)
        return (int(x0), int(y0), int(x0 + w), int(y0 + h))

    def draw(self, t):
        b = self.b
        img = get_bg(b["scene"]).copy()
        cv = Cv(img)
        p = clamp(t / self.dur)
        if b["scene"] == "vault":
            dyn_vault(cv, t)
        if b["scene"] == "chase":
            dyn_chase(cv, t, p)
        else:
            n = len(b["actors"])
            placed = []
            xs = {1: [270], 2: [180, 360], 3: [110, 270, 430]}.get(n, [])
            for i, kind in enumerate(b["actors"]):
                face = 1 if (i < n / 2 or n == 1) else -1
                if n == 2 and i == 1:
                    face = -1
                x = xs[i]
                act = b["action"] if (i == 0 or b["action"] in ("walk", "run", "sneak", "carry", "talk", "hands_up", "celebrate")) else "idle"
                if kind in ("guard", "banker", "civilian") and b["action"] in ("walk", "carry", "sneak", "celebrate"):
                    act = "hands_up" if b["scene"] in ("bank_inside", "vault", "museum") else "idle"
                if act in ("walk", "run", "sneak", "carry"):
                    x += (p - .5) * (260 if act == "run" else 150)
                placed.append((x, kind))
                person(cv, kind, x, 604 + (i % 2) * 16 - (6 if n == 3 and i == 1 else 0), 300, t, act, face, i + self.idx,
                       self.skins[i % 3], "scared" if kind in ("guard", "banker", "civilian") and b["fx"] in ("alarm", "money") else None)
            if self.intro and t < 2.6:
                a = int(255 * clamp(min(t / .2, (2.6 - t) / .4)))
                f = anim.font("bold", int(16 * S))
                for pi_, (x, kind) in enumerate(placed):
                    if kind in self.intro and kind in NAMES:
                        name = NAMES[kind]
                        w = cv.d.textlength(name, font=f) / S + 22
                        dy = 0 if len(placed) < 3 else (-34 if pi_ % 2 else 0)
                        cv.rect((x - w / 2, 268 + dy, x + w / 2, 296 + dy), (0, 0, 0, int(a * .75)), r=14, ol=(255, 214, 40, a), w=2)
                        cv.text((x, 282 + dy), name, 16, (255, 255, 255, a), "mm")
            if b.get("loot"):
                for j, (bx, by, r) in enumerate(((60, 650, 36), (110, 664, 30), (486, 656, 38), (436, 668, 28))):
                    bag(cv, bx, by, r)
        fx = b["fx"]
        if fx == "money":
            bills(cv, t, self.idx + 1)
        if fx == "alarm":
            tint(img, (255, 20, 30), 40 + 70 * (.5 + .5 * math.sin(t * 13)))
        elif fx == "siren":
            on = int(t * 4) % 2 == 0
            side_tint(img, (255, 30, 40) if on else (50, 100, 255), 120, on)
        elif fx == "flash" and t < .55:
            tint(img, (255, 255, 255), 255 * (1 - t / .55))
        elif fx == "lights_off":
            lights_off(img, 270, 380)
        return img

    def frame(self, t, gt, gtotal):
        img = self.draw(t)
        out = img.crop(self.camera(t)).resize((OW, OH), Image.BILINEAR)
        d = ImageDraw.Draw(out, "RGBA")
        d.rectangle([0, 0, int(OW * gt / gtotal), 7], fill=(255, 214, 40, 235))       # barre de progression
        self.caption(d, t)
        return out

    def caption(self, d, t):
        if not self.chunks:
            return
        ci = 0
        for k, ch in enumerate(self.chunks):
            if t >= self.starts[ch[0]]:
                ci = k
        ch = self.chunks[ci]
        text = " ".join(self.tokens[j] for j in ch).upper()
        age = t - self.starts[ch[0]]
        sc = .78 + .22 * ease(age / .12)
        size = 84
        while size > 40 and d.textlength(text, font=anim.font("bold", int(size * sc))) > OW - 70:
            size -= 4
        f = anim.font("bold", int(size * sc))
        col = (255, 226, 40) if (self.idx + ci) % 3 == 2 else (255, 255, 255)
        d.text((OW / 2, 930), text, font=f, fill=col, anchor="mm", stroke_width=9, stroke_fill=(0, 0, 0))


# ----------------------------------------------------------------------------
# Voix (repères mot à mot si le moteur les fournit) et bande-son synthétique
# ----------------------------------------------------------------------------
def synth_words(text, path, voice, rate):
    """Écrit la voix en mp3 ; renvoie [(début, fin)] par mot si disponible, sinon None."""
    import edge_tts

    async def run():
        words = []
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        with open(path, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
        return words

    last = None
    for attempt in range(3):
        try:
            words = asyncio.run(run())
            if path.exists() and path.stat().st_size > 1000:
                return words or None
        except TypeError:                                         # vieille version sans « boundary »
            asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(path)))
            return None
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"edge-tts indisponible : {last}")


SR = 22050


def make_bed(total, events, dest):
    """Nappe de tension + bruitages (alarme, sirène, billets, flash, coupes) en pur Python -> wav mono."""
    n = int(total * SR)
    buf = [0.0] * n
    for i in range(n):
        t = i / SR
        buf[i] = .05 * math.sin(math.tau * 55 * t) + .035 * math.sin(math.tau * 82.4 * t + math.sin(t * .6)) \
            + .02 * math.sin(math.tau * 110 * t) * (.5 + .5 * math.sin(t * .8))

    def add(t0, dur, fn, vol):
        s = int(t0 * SR)
        for k in range(int(dur * SR)):
            if s + k >= n:
                break
            buf[s + k] += vol * fn(k / SR, k / SR / dur)

    rnd = random.Random(7)
    beat = 0.0
    while beat < total:                                             # pouls sourd
        add(beat, .35, lambda x, u: math.sin(math.tau * 48 * x) * (1 - u) ** 3, .16)
        add(beat + .22, .3, lambda x, u: math.sin(math.tau * 44 * x) * (1 - u) ** 3, .1)
        beat += 1.05
    for t0, kind in events:
        if kind == "cut":
            add(t0, .28, lambda x, u: (rnd.random() * 2 - 1) * math.sin(math.pi * u) ** 2 * .6, .16)
        elif kind == "alarm":
            add(t0 + .1, 1.6, lambda x, u: (1 if math.sin(math.tau * 3.2 * x) > 0 else 0) * math.sin(math.tau * 880 * x) * (1 - u * .4), .12)
        elif kind == "siren":
            add(t0 + .1, 2.0, lambda x, u: math.sin(math.tau * (720 * x + 140 * math.sin(math.tau * 1.1 * x) / (math.tau * 1.1) * 3)) * (1 - u * .5), .11)
        elif kind == "money":
            for j in range(7):
                add(t0 + .1 + j * .09, .25, lambda x, u: math.sin(math.tau * 2600 * x) * (1 - u) ** 2, .06)
            add(t0 + .1, .9, lambda x, u: (rnd.random() * 2 - 1) * (1 - u) * .5, .06)
        elif kind == "flash":
            add(t0, .9, lambda x, u: (math.sin(math.tau * 58 * x) + (rnd.random() * 2 - 1) * .5) * (1 - u) ** 2, .45)
        elif kind == "shake":
            add(t0, .7, lambda x, u: (math.sin(math.tau * 42 * x) + (rnd.random() * 2 - 1) * .7) * (1 - u) ** 2, .4)
        elif kind == "lights_off":
            add(t0, .8, lambda x, u: math.sin(math.tau * (260 - 200 * u) * x) * (1 - u), .2)
    m = max(1e-6, max(abs(v) for v in buf))
    scale = min(1.0, .8 / m)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(array("h", [int(clamp(v * scale, -1, 1) * 32000) for v in buf]).tobytes())

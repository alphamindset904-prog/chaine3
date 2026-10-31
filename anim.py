"""Moteur d'animation 2D (Pillow) : décors, personnage, ombre rouge, textes."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, K = 1280, 720, 24, 2
GROUND = 560          # ligne du sol (px, échelle 1x)
FEET = 572            # position des pieds du personnage
CREAM, CREAM_FAR, OUTLINE, INK = (238, 232, 216), (190, 185, 170), (150, 146, 134), (30, 30, 36)
RED = (228, 38, 44)

FONTS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"],
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf"],
}
_font_cache = {}


def font(kind, size, custom=""):
    key = (kind, size, custom)
    if key not in _font_cache:
        f = None
        for p in ([custom] if custom else []) + FONTS[kind]:
            if p and Path(p).exists():
                f = ImageFont.truetype(p, size)
                break
        _font_cache[key] = f or ImageFont.load_default()
    return _font_cache[key]


class Canvas:
    """Dessin à l'échelle K (supersampling) avec des coordonnées 1x."""

    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img, "RGBA")

    def line(self, p1, p2, w, fill):
        self.polyline([p1, p2], w, fill)

    def polyline(self, pts, w, fill):
        pts = [(x * K, y * K) for x, y in pts]
        self.d.line(pts, fill=fill, width=max(1, int(w * K)), joint="curve")
        r = w * K / 2
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def circ(self, c, r, fill, outline=None, width=2):
        x, y = c
        self.d.ellipse([(x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K],
                       fill=fill, outline=outline, width=int(width * K))

    def rect(self, box, fill, radius=0):
        b = [box[0] * K, box[1] * K, box[2] * K, box[3] * K]
        if radius:
            self.d.rounded_rectangle(b, radius=radius * K, fill=fill)
        else:
            self.d.rectangle(b, fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([(x * K, y * K) for x, y in pts], fill=fill)

    def text(self, xy, s, f, fill):
        self.d.text((xy[0] * K, xy[1] * K), s, font=f, fill=fill)


def vgrad(size, top, bottom):
    g = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), g)


def glow(size, color, alpha, blur):
    layer = Image.new("RGBA", size, color + (0,))
    ImageDraw.Draw(layer).ellipse([size[0] * .25, size[1] * .25, size[0] * .75, size[1] * .75], fill=color + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(blur))


# ----------------------------------------------------------------------------
# Décors (pré-calculés une fois, à l'échelle K)
# ----------------------------------------------------------------------------
def _room(top=(14, 16, 26), bot=(8, 8, 12), floor=(12, 12, 16), wide=1):
    size = (W * K * wide, H * K)
    img = vgrad(size, top, bot)
    cv = Canvas(img)
    for i in range(wide):
        pass
    fl = vgrad((size[0], (H - GROUND) * K), (20, 20, 26), floor)
    img.paste(fl, (0, GROUND * K))
    cv.line((0, GROUND), (W * wide, GROUND), 2, (58, 58, 70, 255))
    return img, cv


def bg_void():
    img, cv = _room((12, 12, 18), (6, 6, 9))
    import random
    r = random.Random(4)
    for _ in range(40):
        cv.circ((r.randint(0, W), r.randint(0, GROUND - 40)), r.choice([1, 1, 1.5]), (200, 200, 230, r.randint(40, 110)))
    return img


def bg_bedroom():
    img, cv = _room((16, 18, 30), (8, 8, 13))
    cv.rect((1000, 70, 1092, 162), (74, 76, 90), 4)
    cv.rect((1006, 76, 1086, 156), (24, 30, 52))
    cv.line((1046, 76), (1046, 156), 3, (74, 76, 90))
    cv.line((1006, 116), (1086, 116), 3, (74, 76, 90))
    cv.circ((1066, 98), 17, (228, 228, 238))
    cv.circ((1074, 94), 15, (24, 30, 52))
    beam = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon([(1006 * K, 160 * K), (1090 * K, 160 * K), (800 * K, GROUND * K), (560 * K, GROUND * K)],
                                 fill=(170, 185, 235, 26))
    img.paste(beam, (0, 0), beam)
    cv = Canvas(img)
    cv.rect((190, 500, 640, 566), (58, 58, 74), 6)             # cadre du lit
    cv.rect((196, 468, 636, 506), (40, 46, 74), 8)             # matelas
    cv.rect((206, 446, 292, 476), (84, 90, 120), 12)           # oreiller
    cv.rect((90, 478, 160, 566), (46, 46, 58), 4)              # table de nuit
    cv.rect((98, 446, 152, 478), (40, 40, 50), 6)              # réveil
    cv.text((103, 450), "5:00", font("mono", 20), (255, 50, 50, 255))
    img.paste(glow((120, 90), (255, 40, 40), 70, 14), (88 * K // K * 0 + 70 * K, 430 * K), glow((120, 90), (255, 40, 40), 70, 14))
    return img


def bg_street():
    wide = 2
    img, cv = _room((9, 11, 24), (26, 24, 42), floor=(12, 12, 16), wide=wide)
    import random
    r = random.Random(7)
    sky = vgrad((W * K * wide, GROUND * K), (8, 10, 22), (34, 30, 52))
    img.paste(sky, (0, 0))
    cv = Canvas(img)
    for tile in range(wide):
        ox = tile * W
        x = 0
        while x < W:                                                 # immeubles lointains
            w = r.randint(70, 130)
            h = r.randint(150, 330)
            cv.rect((ox + x, GROUND - h, ox + min(x + w, W), GROUND), (22, 24, 40))
            for wy in range(GROUND - h + 16, GROUND - 20, 30):
                for wx in range(x + 10, min(x + w, W) - 12, 24):
                    if r.random() < .22:
                        cv.rect((ox + wx, wy, ox + wx + 9, wy + 13), (210, 180, 90, r.randint(60, 120)))
            x += w + r.randint(-6, 14)
        for lx in (160, 480, 800, 1120):                             # lampadaires
            cv.line((ox + lx, GROUND + 6), (ox + lx, 330), 6, (40, 40, 52))
            cv.line((ox + lx, 330), (ox + lx + 26, 326), 5, (40, 40, 52))
            g = glow((220, 220), (255, 200, 90), 110, 26)
            img.paste(g, ((ox + lx + 26 - 110) * K, (326 - 110) * K), g)
            Canvas(img).circ((ox + lx + 26, 328), 7, (255, 226, 150))
        for dx in range(0, W, 120):                                  # route
            cv.rect((ox + dx + 20, 640, ox + dx + 80, 646), (70, 70, 76))
    return img


def bg_stairs():
    img, cv = _room((12, 12, 20), (6, 6, 10), floor=(8, 8, 12))
    img.paste(vgrad((W * K, H * K), (12, 12, 20), (6, 6, 10)), (0, 0))
    cv = Canvas(img)
    pts = [(60, 700)]
    for i in range(14):
        x = 100 + i * 82
        y = 640 - i * 36
        pts += [(x, y), (x + 82, y)]
        pts += [(x + 82, y)]
    pts += [(100 + 14 * 82, 720), (60, 720)]
    cv.poly(pts, (30, 30, 40))
    for i in range(14):
        x = 100 + i * 82
        y = 640 - i * 36
        cv.line((x, y), (x + 82, y), 3, (74, 74, 88))
    return img


def stairs_y(x):
    return 640 - ((x - 100) / 82.0) * 36 - 36 + 36


def bg_mountain():
    img = vgrad((W * K, H * K), (26, 18, 52), (250, 150, 80))
    cv = Canvas(img)
    sun = glow((520, 520), (255, 190, 110), 200, 60)
    img.paste(sun, ((640 - 260) * K, (470 - 260) * K), sun)
    cv = Canvas(img)
    cv.circ((640, 470), 54, (255, 214, 130))
    cv.poly([(0, 520), (160, 400), (300, 500), (460, 380), (640, 520), (820, 410), (980, 510), (1140, 400), (1280, 500), (1280, 720), (0, 720)], (74, 36, 66))
    cv.poly([(0, 600), (200, 470), (380, 580), (1280, 560), (1280, 720), (0, 720)], (40, 24, 46))
    cv.poly([(250, 720), (640, 340), (1030, 720)], (14, 10, 20))
    return img


def bg_dojo():
    img, cv = _room((20, 14, 18), (10, 8, 10), floor=(28, 20, 18))
    for x in range(0, W, 90):
        cv.line((x, GROUND), (x - 40, 720), 2, (44, 32, 30))
    cv.rect((60, 200, 76, 330), (46, 40, 44))
    cv.line((900, 0), (900, 40), 6, (90, 90, 96))
    return img


def bg_desk():
    img, cv = _room((12, 14, 22), (7, 8, 12))
    cv.circle = None
    cv.circ((270, 130), 42, (60, 60, 74), (96, 96, 110), 3)
    cv.line((270, 130), (270, 100), 3, (210, 210, 220))
    cv.line((270, 130), (292, 138), 3, (210, 210, 220))
    cv.rect((500, 470, 1010, 486), (74, 56, 44))
    cv.rect((520, 486, 536, 566), (60, 46, 38))
    cv.rect((974, 486, 990, 566), (60, 46, 38))
    for i, c in enumerate([(120, 60, 60), (60, 90, 130), (90, 120, 80)]):
        cv.rect((900 - i * 4, 452 - i * 18, 990 - i * 2, 470 - i * 18), c)
    cv.line((760, 470), (800, 380), 5, (80, 80, 90))
    cv.line((800, 380), (860, 340), 5, (80, 80, 90))
    cv.poly([(850, 330), (900, 346), (888, 378), (836, 360)], (205, 176, 80))
    cone = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(cone).polygon([(846 * K, 362 * K), (892 * K, 372 * K), (1000 * K, 470 * K), (700 * K, 470 * K)], fill=(255, 220, 120, 46))
    img.paste(cone, (0, 0), cone)
    cv = Canvas(img)
    cv.rect((390, 500, 470, 514), (36, 36, 48), 4)
    cv.rect((388, 514, 400, 566), (36, 36, 48))
    return img


def bg_couch():
    img, cv = _room((12, 12, 22), (7, 7, 12))
    cv.rect((300, 390, 780, 530), (36, 36, 52), 26)
    cv.rect((290, 470, 790, 566), (46, 46, 64), 18)
    cv.rect((270, 430, 330, 566), (40, 40, 58), 18)
    cv.rect((750, 430, 810, 566), (40, 40, 58), 18)
    return img


def bg_mirror():
    img, cv = _room((12, 12, 20), (6, 6, 10))
    cv.d.ellipse([740 * K, 150 * K, 980 * K, 470 * K], fill=(86, 86, 98))
    cv.d.ellipse([750 * K, 160 * K, 970 * K, 460 * K], fill=(14, 14, 24))
    cv.line((860, 470), (860, 566), 8, (60, 60, 70))
    cv.line((800, 566), (920, 566), 8, (60, 60, 70))
    for a, b in [((850, 160), (870, 300)), ((870, 300), (930, 360)), ((870, 300), (800, 380)), ((850, 240), (820, 270))]:
        cv.line(a, b, 2, (225, 225, 235, 120))
    return img


BG_BUILDERS = {"void": bg_void, "bedroom": bg_bedroom, "street": bg_street, "stairs": bg_stairs,
               "mountain": bg_mountain, "dojo": bg_dojo, "desk": bg_desk, "couch": bg_couch, "mirror": bg_mirror}
_bg_cache = {}


def get_bg(name):
    if name not in _bg_cache:
        _bg_cache[name] = BG_BUILDERS[name]()
    return _bg_cache[name]


# ----------------------------------------------------------------------------
# Personnage, ombre
# ----------------------------------------------------------------------------
def _shift(J, dx, dy):
    def sp(p):
        return (p[0] + dx, p[1] + dy)
    return {"head": sp(J["head"]), "torso": (sp(J["torso"][0]), sp(J["torso"][1])),
            "legs": [[sp(p) for p in l] for l in J["legs"]], "arms": [[sp(p) for p in a] for a in J["arms"]]}


def upright(x, y, a_leg, b_arm, lean=0.0, bob=0.0, up_arms=False):
    L, T, A = 62, 56, 46
    hip = (x, y - L)
    sh = (x + lean, hip[1] - T)
    head = (sh[0] + lean * .35, sh[1] - 31)
    legs = [[hip, (hip[0] + math.sin(-a_leg) * L, hip[1] + math.cos(a_leg) * L)],
            [hip, (hip[0] + math.sin(a_leg) * L, hip[1] + math.cos(a_leg) * L)]]
    if up_arms:
        arms = [[sh, (sh[0] - 38, sh[1] - 44)], [sh, (sh[0] + 38, sh[1] - 44)]]
    else:
        arms = [[sh, (sh[0] + math.sin(b_arm) * A, sh[1] + math.cos(b_arm) * A)],
                [sh, (sh[0] + math.sin(-b_arm) * A, sh[1] + math.cos(b_arm) * A)]]
    J = {"head": head, "torso": (hip, sh), "legs": legs, "arms": arms}
    foot = max(l[1][1] for l in legs)
    return _shift(J, 0, y - foot + bob)


def draw_figure(cv, J, mood, band, t):
    far_leg, near_leg = J["legs"]
    far_arm, near_arm = J["arms"]
    cv.polyline(far_leg, 15, CREAM_FAR)
    cv.polyline(far_arm, 13, CREAM_FAR)
    cv.line(J["torso"][0], J["torso"][1], 32, CREAM)
    cv.polyline(near_leg, 15, CREAM)
    cv.polyline(near_arm, 13, CREAM)
    draw_head(cv, J["head"][0], J["head"][1], mood, band, t)


def draw_head(cv, x, y, mood, band, t):
    cv.circ((x, y), 25, CREAM, OUTLINE, 2)
    if band:
        cv.line((x - 24, y - 11), (x + 24, y - 11), 7, (205, 30, 36))
        sw = math.sin(t * 7)
        cv.line((x - 24, y - 11), (x - 44, y - 6 + sw * 7), 5, (205, 30, 36))
        cv.line((x - 24, y - 11), (x - 40, y - 17 - sw * 6), 5, (205, 30, 36))
    ink = INK
    if mood == "closed":
        for dx in (-8, 9):
            cv.line((x + dx - 5, y - 2), (x + dx + 4, y - 2), 2.5, ink)
        cv.line((x - 5, y + 10), (x + 6, y + 10), 2.5, ink)
        return
    for dx in (-8, 9):
        cv.circ((x + dx, y - 2), 3, ink)
    if mood == "angry":
        cv.line((x - 16, y - 14), (x - 3, y - 8), 3, ink)
        cv.line((x + 17, y - 14), (x + 4, y - 8), 3, ink)
        cv.line((x - 6, y + 11), (x + 7, y + 11), 2.5, ink)
    elif mood == "sad":
        cv.line((x - 16, y - 9), (x - 3, y - 14), 2.5, ink)
        cv.line((x + 17, y - 9), (x + 4, y - 14), 2.5, ink)
        cv.polyline([(x - 6, y + 13), (x + 1, y + 9), (x + 8, y + 13)], 2.5, ink)
    elif mood == "tired":
        cv.line((x - 14, y - 6), (x - 2, y - 6), 4, CREAM)
        cv.line((x + 3, y - 6), (x + 16, y - 6), 4, CREAM)
        cv.line((x - 14, y - 6), (x - 2, y - 6), 1.5, ink)
        cv.line((x + 3, y - 6), (x + 16, y - 6), 1.5, ink)
        cv.line((x - 5, y + 11), (x + 7, y + 11), 2.5, ink)
    elif mood == "calm":
        cv.polyline([(x - 6, y + 9), (x + 1, y + 13), (x + 8, y + 9)], 2.5, ink)
    else:
        cv.line((x - 5, y + 10), (x + 7, y + 10), 2.5, ink)


_sprites = {}


def shadow_sprite():
    if "shadow" not in _sprites:
        size = (300, 380)
        shapes = [("c", (150, 66), 36), ("l", (150, 96), (150, 210), 70),
                  ("l", (126, 118), (70, 236), 26), ("l", (174, 118), (232, 236), 26),
                  ("l", (134, 210), (116, 350), 34), ("l", (166, 210), (184, 350), 34)]

        def paint(layer, fill, grow):
            cv = Canvas(layer)
            for s in shapes:
                if s[0] == "c":
                    cv.circ(s[1], s[2] + grow, fill)
                else:
                    cv.line(s[1], s[2], s[3] + grow * 2, fill)
        gl = Image.new("RGBA", (size[0] * K, size[1] * K), (0, 0, 0, 0))
        paint(gl, (235, 34, 44, 255), 10)
        gl = gl.filter(ImageFilter.GaussianBlur(14 * K))
        gl.putalpha(gl.getchannel("A").point(lambda v: int(v * .95)))
        body = Image.new("RGBA", gl.size, (0, 0, 0, 0))
        paint(body, (7, 7, 9, 255), 0)
        cv = Canvas(body)
        cv.d.ellipse([136 * K, 58 * K, 146 * K, 64 * K], fill=(255, 90, 90, 255))
        cv.d.ellipse([154 * K, 58 * K, 164 * K, 64 * K], fill=(255, 90, 90, 255))
        _sprites["shadow"] = Image.alpha_composite(gl, body)
    return _sprites["shadow"]


def paste_shadow(img, feet_x, feet_y, bob, scale=1.0):
    spr = shadow_sprite()
    if scale != 1.0:
        spr = spr.resize((int(spr.width * scale), int(spr.height * scale)), Image.BILINEAR)
    x = int(feet_x * K - spr.width / 2)
    y = int((feet_y + bob) * K - spr.height * (350 / 380))
    img.paste(spr, (x, y), spr)


def phone_glow(img, x, y, a):
    if "phone" not in _sprites:
        _sprites["phone"] = glow((420, 420), (80, 130, 255), 190, 46)
    g = _sprites["phone"].copy()
    g.putalpha(g.getchannel("A").point(lambda v: int(v * a)))
    img.paste(g, (int(x * K - g.width / 2), int(y * K - g.height / 2)), g)


# ----------------------------------------------------------------------------
# Scènes
# ----------------------------------------------------------------------------
POSE_BG = {"sleep": "bedroom", "sit": "couch", "work": "desk", "punch": "dojo", "climb": "stairs",
           "summit": "mountain", "run": "street", "walk": "street", "title": "void"}
BG_FREE = ("void", "bedroom", "street", "mountain", "mirror")
POSES = ("sleep", "sit", "hunch", "stand", "walk", "run", "punch", "climb", "work", "summit", "title")


def _wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_block(d, text, size, fill, cx, y, maxw, custom, shake=0.0, alpha=1.0, bold="bold"):
    f = font(bold, size, custom)
    lines = _wrap(d, text, f, maxw)
    lh = int(size * 1.25)
    a = int(255 * alpha)
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=f)
        x = cx - w / 2 + shake
        d.text((x + 3, y + i * lh + 3), ln, font=f, fill=(0, 0, 0, int(a * .8)))
        d.text((x, y + i * lh), ln, font=f, fill=fill[:3] + (a,))
    return y + len(lines) * lh


class SceneRenderer:
    def __init__(self, scene, dur, cfg):
        self.s = scene
        self.dur = max(float(dur), 1.0)
        self.font_custom = cfg.get("font_bold", "")
        self.watermark = cfg.get("channel_name", "")
        pose = scene["pose"]
        free = scene.get("bg") if scene.get("bg") in BG_FREE else "void"
        self.bgname = POSE_BG.get(pose) or free
        self.shadow = scene.get("shadow", "none")
        if self.shadow == "mirror" and self.bgname != "mirror":
            self.shadow = "right"
        self.bg = get_bg(self.bgname)
        if self.shadow == "mirror":
            bg = self.bg.copy()
            spr = shadow_sprite().resize((int(300 * K * .6), int(380 * K * .6)), Image.BILINEAR)
            bg.paste(spr, (int(860 * K - spr.width / 2), int(458 * K - spr.height * 350 / 380)), spr)
            mask = Image.new("L", bg.size, 0)
            ImageDraw.Draw(mask).ellipse([752 * K, 162 * K, 968 * K, 458 * K], fill=255)
            self.bg = Image.composite(bg, self.bg, mask)

    # -- personnage -----------------------------------------------------
    def _figure(self, img, cv, t):
        s, pose, band = self.s, self.s["pose"], bool(self.s.get("band"))
        sin = math.sin
        x0 = 420
        if pose == "stand":
            J = upright(x0, FEET, .05, .12 + .04 * sin(t * 3), bob=1.5 * sin(t * 2.4))
            mood = "neutral" if band else "tired"
        elif pose == "walk":
            a = .42 * sin(t * 2 * math.pi)
            J = upright(x0, FEET, a, a * 1.1, lean=7 if band else 2)
            mood = "angry" if band else "tired"
        elif pose == "run":
            ph = t * 2 * math.pi * 1.9
            a = .9 * sin(ph)
            J = upright(x0, FEET, a, a * 1.25, lean=16, bob=-7 * abs(sin(ph)))
            mood = "angry"
        elif pose == "punch":
            e = max(0.0, sin(t * 2 * math.pi * 1.6)) ** 2
            J = upright(780 - 20, FEET, .34, 0, lean=4 + 6 * e)
            sh = J["torso"][1]
            J["arms"] = [[sh, (sh[0] + 20, sh[1] + 14)], [sh, (sh[0] + 22 + 48 * e, sh[1] + 8 - 4 * e)]]
            mood = "angry"
            self._bag(cv, t, e)
        elif pose == "climb":
            prog = min(1.0, t / self.dur)
            x = 190 + prog * 820
            y = 640 - 36 * ((x - 100) / 82.0 + .5)
            a = .5 * sin(t * 2 * math.pi * 1.2)
            J = upright(x, y, a, a * 1.1, lean=10)
            mood = "angry"
        elif pose == "summit":
            J = upright(640, 346, .16, 0, up_arms=True, bob=2 * sin(t * 1.8))
            mood = "calm"
        elif pose == "work":
            hip = (430, 486)
            sh = (hip[0] + 16, hip[1] - 54)
            hx = sh[0] + 84 + 5 * sin(t * 2 * math.pi * 1.4)
            J = {"head": (sh[0] + 22, sh[1] - 26), "torso": (hip, sh),
                 "legs": [[hip, (hip[0] + 44, hip[1] + 6), (hip[0] + 50, 566)],
                          [hip, (hip[0] + 40, hip[1] + 4), (hip[0] + 42, 566)]],
                 "arms": [[sh, (sh[0] + 18, sh[1] + 34), (sh[0] + 70, 466)],
                          [sh, (sh[0] + 22, sh[1] + 30), (hx, 466)]]}
            mood = "angry" if band else "tired"
        elif pose == "sit":
            hip, sh = (500, 470), (488, 418)
            J = {"head": (514, 394), "torso": (hip, sh),
                 "legs": [[hip, (548, 466), (556, 566)], [hip, (540, 470), (546, 566)]],
                 "arms": [[sh, (500, 446), (536, 424)], [sh, (504, 444), (542, 426)]]}
            mood = "tired"
            cv.rect((538, 410, 552, 432), (214, 228, 255), 3)
            phone_glow(img, 546, 420, .55 + .2 * sin(t * 6))
        elif pose == "hunch":
            g, x = 566, 430
            b = 1.5 * sin(t * 1.8)
            sh = (x + 6, g - 70 + b)
            J = {"head": (x + 34, g - 92 + b), "torso": ((x, g - 14), sh),
                 "legs": [[(x, g - 14), (x + 38, g - 52), (x + 62, g - 2)], [(x, g - 14), (x + 34, g - 48), (x + 56, g - 2)]],
                 "arms": [[sh, (x + 30, g - 58), (x + 44, g - 50)], [sh, (x + 26, g - 62), (x + 40, g - 54)]]}
            mood = "sad"
        elif pose == "sleep":
            self._sleeper(cv, t)
            return
        else:
            return
        draw_figure(cv, J, mood, band, t)

    def _sleeper(self, cv, t):
        br = 2.2 * math.sin(t * 1.6)
        draw_head(cv, 252, 442, "closed", False, t)
        cv.rect((286, 454 - br, 632, 508), (34, 40, 72), 16)
        cv.line((300, 470 - br), (620, 470 - br), 2, (60, 68, 108))
        f = font("bold", 24, self.font_custom)
        for i in range(3):
            ph = (t * .5 + i * .33) % 1.0
            cv.text((300 + i * 26 + ph * 20, 410 - ph * 90), "Z", font("bold", 20 + i * 8, self.font_custom),
                    (200, 205, 235, int(220 * (1 - ph))))

    def _bag(self, cv, t, e):
        ang = .16 * math.sin(t * 2 * math.pi * 1.6 - .9) + .05 * e
        px, py = 885, 0
        pts = [(847, 190), (923, 190), (923, 430), (847, 430)]
        rot = [(px + (x - px) * math.cos(ang) - (y - py) * math.sin(ang),
                py + (x - px) * math.sin(ang) + (y - py) * math.cos(ang)) for x, y in pts]
        cv.line((px, 0), rot[0] if False else ((rot[0][0] + rot[1][0]) / 2, (rot[0][1] + rot[1][1]) / 2), 4, (100, 100, 108))
        cv.poly(rot, (170, 24, 30))
        cv.line(((rot[0][0] * 3 + rot[1][0]) / 4, (rot[0][1] * 3 + rot[1][1]) / 4),
                ((rot[3][0] * 3 + rot[2][0]) / 4, (rot[3][1] * 3 + rot[2][1]) / 4), 5, (230, 70, 70, 160))
        if e > .75:
            for k in range(6):
                a = -.9 + k * .35
                cv.line((838 - 6 * k * 0, 312 + k * 6), (838 - 70 * math.cos(a) - 20, 312 + k * 6 - 70 * math.sin(a)), 3, (255, 214, 70, 230))

    # -- image ----------------------------------------------------------
    def frame(self, t):
        s = self.s
        if self.bgname == "street":
            off = int((t * 150 % W) * K)
            img = self.bg.crop((off, 0, off + W * K, H * K))
        else:
            img = self.bg.copy()
        cv = Canvas(img)
        if self.shadow == "right":
            bob = 3 * math.sin(t * 1.3)
            if self.bgname == "stairs":
                paste_shadow(img, 1060, 201, bob, .5)
            elif self.bgname == "mountain":
                paste_shadow(img, 1090, 690, bob)
            else:
                paste_shadow(img, 1030, FEET, bob)
        self._figure(img, cv, t)
        z = 1 + .05 * min(1.0, t / self.dur)
        bw, bh = W * K / z, H * K / z
        l, tp = (W * K - bw) / 2, (H * K - bh) / 2
        out = img.resize((W, H), Image.BILINEAR, box=(l, tp, l + bw, tp + bh))
        self._overlay(out, t)
        a0 = min(1.0, t / .35)
        if a0 < 1.0:
            out = Image.blend(Image.new("RGB", (W, H)), out, a0)
        return out

    def _overlay(self, img, t):
        s = self.s
        d = ImageDraw.Draw(img, "RGBA")
        fa = min(1.0, max(0.0, (t - .25) / .5))
        c = self.font_custom
        if s["pose"] == "title":
            y = 150
            f = font("bold", 104, c)
            word = s.get("title_word", "")
            wsize = 104
            while d.textlength(word, font=font("bold", wsize, c)) > 1100 and wsize > 50:
                wsize -= 6
            end = _text_block(d, word, wsize, (255, 255, 255), W / 2, y, 1180, c, alpha=fa)
            wf = font("bold", wsize, c)
            tw = min(1100, d.textlength(word, font=wf))
            pts = [(W / 2 - tw / 2 + i * 8, end + 4 + 4 * math.sin(i * .6 + t * 3)) for i in range(int(tw / 8) + 1)]
            if len(pts) > 1:
                d.line(pts, fill=RED + (int(255 * fa),), width=5)
            e2 = _text_block(d, s.get("tagline", ""), 34, (240, 240, 240), W / 2, end + 40, 1000, c, alpha=fa)
            _text_block(d, s.get("punchline", ""), 42, RED, W / 2, e2 + 14, 1000, c, alpha=fa)
            _text_block(d, "Abonne-toi pour ne rien manquer", 22, (170, 170, 176), W / 2, 650, 900, c, alpha=fa)
        else:
            text, style = s.get("text", ""), s.get("text_style", "white")
            if text:
                if style == "red":
                    _text_block(d, text, 58, RED, W / 2, 80, 1150, c, shake=math.sin(t * 38) * 1.8, alpha=fa)
                elif style == "big":
                    _text_block(d, text, 68, (255, 255, 255), W / 2, 80, 1150, c, alpha=fa)
                else:
                    _text_block(d, text, 36, (240, 240, 240), W / 2, 90, 1000, c, alpha=fa)
            if s.get("day"):
                d.text((40, 28), f"JOUR {s['day']}", font=font("bold", 22, c), fill=(205, 205, 210, int(230 * fa)))
        if self.watermark:
            f = font("bold", 16, c)
            d.text((W - 24 - d.textlength(self.watermark, font=f), H - 32), self.watermark, font=f, fill=(255, 255, 255, 90))

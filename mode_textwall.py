"""TEXTWALL: night dolly along a brick wall while DedSec graffiti sprays itself on, under flickering lamps."""

import math
import random
import time

import numpy as np

from sysdata import DATA
from lib import (BLACK, CYAN, DIM_PINK, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW, Glitch,
                 blend, ease_out, pulse)
from widgets import PostFX

NAME = "TEXTWALL"

L = 10                 # light levels
R = 2                  # canvas cells per wall unit
WH = 40.0              # wall height (units)
ZW = 58.0              # wall plane z
CW = 1024 * R // 2     # ring canvas width (cells) = 512 units
CH = int(WH * R)
HCAM = 16.0
LAMP_SP = 64.0
LAMP_H = 35.0
LAMP_Z = ZW - 11.0
FG_Z = 16.0

# ------------------------------------------------------------------ colours
COLS = []
EMISSIVE = set()


def col_id(rgb, emissive=False):
    rgb = tuple(int(max(0, min(255, c))) for c in rgb)
    key = (rgb, emissive)
    for i, c in enumerate(COLS):
        if c == key:
            return i
    COLS.append(key)
    if emissive:
        EMISSIVE.add(len(COLS) - 1)
    return len(COLS) - 1


BRICKS = [col_id(c) for c in ((120, 52, 44), (104, 44, 40), (132, 62, 50), (92, 40, 42), (140, 74, 60))]
MORTAR = col_id((70, 64, 66))
COPING = col_id((120, 118, 124))
COPING2 = col_id((80, 78, 86))
SIDEWALK = col_id((64, 62, 70))
JOINT = col_id((40, 38, 46))
CURB = col_id((110, 108, 112))
ROAD = col_id((28, 28, 36))
LANE = col_id((200, 170, 60))
POST = col_id((22, 22, 30))
FENCE = col_id((60, 64, 76))
SKY = [col_id(blend((4, 2, 14), (40, 14, 60), i / 5), True) for i in range(6)]
SKYLINE = col_id((14, 8, 26), True)
SKYWIN = col_id((240, 190, 90), True)
STAR = col_id((200, 200, 240), True)
PAPER_BACK = col_id((200, 196, 186))
PAPER_SHADE = col_id((150, 146, 140))
VENT = col_id((50, 62, 64))
VENT_EDGE = col_id((100, 115, 110))
PIPE = col_id((82, 94, 90))

INK = (20, 8, 26)


def paint(rgb):
    return col_id(rgb)


# ------------------------------------------------------------------ bitmaps
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "#": ["01010", "11111", "01010", "01010", "11111", "01010", "00000"],
    " ": ["00000"] * 7,
    "0": ["01110", "10011", "10101", "10101", "10101", "11001", "01110"],
}
SKULL = [
    "......XXXXXXXXXX......",
    "....XXXXXXXXXXXXXX....",
    "...XXXXXXXXXXXXXXXX...",
    "..XXXXXXXXXXXXXXXXXX..",
    ".XXXXXXXXXXXXXXXXXXXX.",
    ".XXXX.X...XX...X.XXXX.",
    ".XXXXX.X.XXXX.X.XXXXX.",
    ".XXXX.X...XX...X.XXXX.",
    ".XXXXXXXXX..XXXXXXXXX.",
    "..XXXXXXXX..XXXXXXXX..",
    "...XXXXXX....XXXXXX...",
    "....XXXXXXXXXXXXXX....",
    ".....X.X.X.X.X.X.X....",
    ".....XXXXXXXXXXXXX....",
    "......XXXXXXXXXXX.....",
]
CROWN = [
    "X.....X.....X",
    "XX...XXX...XX",
    "X.X.X.X.X.X.X",
    "X..X..X..X..X",
    "X...........X",
    "X...........X",
    "XXXXXXXXXXXXX",
]
ARROW = ["......X....", "......XX...", "XXXXXXXXX..", "XXXXXXXXXX.", "XXXXXXXXX..", "......XX...", "......X...."]
WRENCH = [
    "...XXXXXXXXXXXX...",
    "..XXXXXXXXXXXXXX..",
    ".XXXXXXXXXXXXXXXX.",
    "XXXXXXXXXXXXXXXXXX",
    "XX1XXXXXXXXXXXX2XX",
    "XXX1XXXXXXXXXX2XXX",
    "XXXX1XXXXXXXX2XXXX",
    "XXX1XXXXXXXXXX2XXX",
    "XX1XXXXXXXXXXXX2XX",
    "XXXXXXXXXXXXXXXXXX",
    "XXX3X3X3X3X3X3XXXX",
    "XXXX333333333XXXXX",
    ".XXXXXXXXXXXXXXXX.",
    "..XXXXXXXXXXXXXX..",
    "...XXXXX..XXXXX...",
]
STICKERS = [
    (["WWWWWWWWWW", "WWKKKKKKWW", "WKKWKKWKKW", "WKKKKKKKKW", "WWKWKWKWWW", "WWWWWWWWWW"], {"W": (235, 235, 235), "K": INK}),
    (["PPPPPPPPPPPP", "PWPWWPWWPWWP", "PWPWPPWPPWPP", "PWPWWPWWPWWP", "PPPPPPPPPPPP"], {"P": PINK, "W": WHITE}),
    ([".YYYYYY.", "YYKYYKYY", "YYYYYYYY", "YKYYYYKY", "YYKKKKYY", ".YYYYYY."], {"Y": YELLOW, "K": INK}),
    (["..RRRR..", ".R....R.", "R..R...R", "R...R..R", "R....R.R", ".R....R.", "..RRRR.."], {"R": (230, 30, 40)}),
    (["CCCCCCCCCC", "CKKCKKCKKC", "CKCCKCCKCC", "CKKCKKCKKC", "CCCCCCCCCC"], {"C": CYAN, "K": INK}),
]
CREW = ["SITARA", "WRENCH", "MARCUS", "JOSH", "HORATIO", "DEDSEC"]


def word_mask(text, k, gap=1, shear=0.0, jitter=0, rng=None):
    rows = 7
    letters = []
    for ch in text:
        g = FONT.get(ch, FONT[" "])
        letters.append(np.array([[c == "1" for c in r] for r in g]))
    wcells = sum(l.shape[1] + gap for l in letters) * k
    hcells = rows * k + 2 * jitter + int(abs(shear) * rows * k) + 2
    m = np.zeros((hcells, wcells + int(abs(shear) * rows * k) + 2), bool)
    x = 0
    for l in letters:
        big = np.kron(l, np.ones((k, k), bool))
        jy = rng.randint(-jitter, jitter) + jitter if jitter else 0
        h, w = big.shape
        for yy in range(h):
            off = int((h - yy) * shear)
            m[jy + yy, x + off:x + off + w] |= big[yy]
        x += (l.shape[1] + gap) * k
    return m


def bitmap_mask(art, k, chars="X"):
    a = np.array([[c in chars for c in r] for r in art])
    return np.kron(a, np.ones((k, k), bool))


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + r and (dx or dy):
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def smooth(m, n=2):
    f = m.astype(np.float32)
    for _ in range(n):
        f = (f + np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 5
    return f > 0.45


def pad(m, p):
    return np.pad(m, p)


class Layer:
    def __init__(self, mask, ids, mode="zigzag", band=8, dur=None, rng=None):
        self.mask = mask
        self.ids = ids             # int array same shape or scalar
        h, w = mask.shape
        yy, xx = np.mgrid[0:h, 0:w]
        if mode == "zigzag":
            nb = max(1, int(math.ceil(h / band)))
            bi = yy // band
            fr = np.where(bi % 2 == 0, xx / max(1, w - 1), 1 - xx / max(1, w - 1))
            self.order = (bi + fr) / nb
            self.path = ("zz", nb, band, w)
        elif mode == "columns":
            nb = max(1, int(math.ceil(w / band)))
            bi = xx // band
            fr = np.where(bi % 2 == 0, yy / max(1, h - 1), 1 - yy / max(1, h - 1))
            self.order = (bi + fr) / nb
            self.path = ("col", nb, band, h)
        else:   # stencil fog: random
            self.order = rng.random_sample((h, w)) if rng is not None else np.random.rand(h, w)
            self.path = ("rand",)
        self.order = self.order + (np.random.rand(h, w) * 0.012)
        n = int(mask.sum())
        self.dur = dur if dur is not None else max(0.6, min(4.5, n / 900))
        self.p = 0.0

    def can_pos(self):
        """position (x, y) in layer cells of the spray frontier"""
        kind = self.path[0]
        p = min(0.999, self.p)
        if kind == "zz":
            _, nb, band, w = self.path
            b = int(p * nb)
            fr = p * nb - b
            x = fr * w if b % 2 == 0 else (1 - fr) * w
            return x, (b + 0.5) * band
        if kind == "col":
            _, nb, band, h = self.path
            b = int(p * nb)
            fr = p * nb - b
            y = fr * h if b % 2 == 0 else (1 - fr) * h
            return (b + 0.5) * band, y
        return None


class Piece:
    """A graffiti piece: stack of layers revealed one after another into the ring canvas."""

    def __init__(self, kind, u0, rng):
        self.kind = kind
        self.u0 = u0
        self.layers = []
        self.state = "wait"
        self.li = 0
        self.drips = []
        self.color = PINK
        self.stencil = False
        build = getattr(self, "b_" + kind)
        build(rng)
        h, w = self.layers[0].mask.shape
        self.h, self.w = h, w
        self.v0 = int(max(3 * R, min(CH - h - 3 * R, rng.uniform(0.3, 0.6) * (CH - h))))
        self.width_units = w / R

    # -- builders ---------------------------------------------------------
    def gradient(self, h, w, a, b, steps=5):
        ids = [paint(blend(a, b, i / (steps - 1))) for i in range(steps)]
        rows = (np.arange(h) * steps // max(1, h)).clip(0, steps - 1)
        return np.array(ids)[rows][:, None].repeat(w, 1)

    def letters(self, rng, text, k, fill_a, fill_b, outline, shadow, jitter):
        m = word_mask(text, k, gap=1, shear=0.28, jitter=jitter, rng=rng)
        m = pad(m, 8)
        m = smooth(m, 2)
        out = dilate(m, 2) & ~m
        sh = np.roll(np.roll(dilate(m, 2), 3, 0), 4, 1) & ~dilate(m, 2)
        hl = m & ~np.roll(m, 2, 0) & ~np.roll(m, 2, 1)
        hl2 = m & (np.random.rand(*m.shape) < 0.006)
        h, w = m.shape
        self.layers = [
            Layer(m, self.gradient(h, w, fill_a, fill_b), band=7),
            Layer(sh, paint(shadow), mode="columns", band=10),
            Layer(out, paint(outline), mode="columns", band=6),
            Layer(hl | hl2, paint(WHITE), band=9),
        ]
        self.color = fill_a
        self.fillmask = m

    def b_dedsec(self, rng):
        a, b = rng.choice([(PINK, PURPLE), (CYAN, (0, 90, 200)), (YELLOW, ORANGE), ((255, 90, 200), (120, 0, 160))])
        self.letters(rng, "DEDSEC", 4, a, b, rng.choice([WHITE, INK]), (40, 0, 60), 4)
        self.title = "DEDSEC"

    def b_hack(self, rng):
        top = word_mask("HACK THE", 2, shear=0.2, rng=rng)
        bot = word_mask("PLANET!", 2, shear=0.2, rng=rng)
        w = max(top.shape[1], bot.shape[1])
        m = np.zeros((top.shape[0] + bot.shape[0] + 2, w), bool)
        m[:top.shape[0], :top.shape[1]] = top
        m[top.shape[0] + 2:, (w - bot.shape[1]) // 2:(w - bot.shape[1]) // 2 + bot.shape[1]] = bot
        m = pad(m, 6)
        out = dilate(m, 1) & ~m
        sh = np.roll(np.roll(dilate(m, 1), 2, 0), 2, 1) & ~dilate(m, 1)
        h, w = m.shape
        self.layers = [Layer(m, self.gradient(h, w, CYAN, GREEN), band=5),
                       Layer(out, paint(PINK), mode="columns", band=5),
                       Layer(sh, paint(INK), mode="columns", band=8)]
        self.color = CYAN
        self.fillmask = m
        self.title = "HACK THE PLANET"

    def b_skull(self, rng):
        m = pad(smooth(bitmap_mask(SKULL, 3), 1), 6)
        out = dilate(m, 2) & ~m
        h, w = m.shape
        eyes = pad(bitmap_mask(SKULL, 3, "."), 6) & dilate(m, 1) & ~m
        self.layers = [Layer(m, self.gradient(h, w, WHITE, (200, 200, 220)), band=6),
                       Layer(out, paint(INK), mode="columns", band=6),
                       Layer(m & ~np.roll(m, 2, 0), paint(PINK), band=10)]
        self.color = WHITE
        self.fillmask = m
        self.title = "SKULL"

    def b_crown(self, rng):
        m = pad(dilate(bitmap_mask(CROWN, 4), 1), 6)
        out = dilate(m, 1) & ~m
        self.layers = [Layer(m, paint(YELLOW), mode="columns", band=5),
                       Layer(out, paint(INK), mode="columns", band=5)]
        self.color = YELLOW
        self.fillmask = m
        self.title = "CROWN"

    def b_arrows(self, rng):
        a = bitmap_mask(ARROW, 4)
        m = np.zeros((a.shape[0] * 2 + 6, a.shape[1] + 20), bool)
        m[:a.shape[0], :a.shape[1]] = a
        m[a.shape[0] + 6:, 20:] = a
        m = pad(smooth(m, 1), 6)
        out = dilate(m, 2) & ~m
        h, w = m.shape
        self.layers = [Layer(m, self.gradient(h, w, (0, 200, 255), PINK), band=6),
                       Layer(out, paint(WHITE), mode="columns", band=6)]
        self.color = CYAN
        self.fillmask = m
        self.title = "ARROWS"

    def b_wrench(self, rng):
        k = 3
        black = pad(bitmap_mask(WRENCH, k, "X123"), 6)
        led1 = pad(bitmap_mask(WRENCH, k, "1"), 6)
        led2 = pad(bitmap_mask(WRENCH, k, "2"), 6)
        teeth = pad(bitmap_mask(WRENCH, k, "3"), 6)
        rng2 = np.random.RandomState(rng.randint(0, 9999))
        self.layers = [Layer(black, paint(INK), mode="rand", dur=2.2, rng=rng2),
                       Layer(led1 | led2 | teeth, np.where(led1, paint(CYAN), np.where(led2, paint(PINK), paint(WHITE))),
                             mode="rand", dur=1.4, rng=rng2)]
        self.stencil = True
        self.color = CYAN
        self.fillmask = black
        self.title = "WRENCH STENCIL"


class Poster:
    KINDS = ["blume", "wanted", "ctos"]

    def __init__(self, u0, v0, rng):
        self.u0, self.v0 = u0, v0          # left, top (units)
        self.kind = rng.choice(self.KINDS)
        self.wu, self.hu = 18.0, 24.0
        w, h = int(self.wu * R), int(self.hu * R)
        img = np.zeros((h, w), np.int64)
        if self.kind == "blume":
            img[:] = paint((30, 70, 190))
            t = word_mask("BLUME", 1, gap=1)
            img[6:6 + t.shape[0], 3:3 + t.shape[1]][t[:, :min(t.shape[1], w - 3)]] = paint(WHITE)
            yy, xx = np.mgrid[0:h, 0:w]
            eye = ((xx - w / 2) ** 2 / 100 + (yy - h * 0.62) ** 2 / 25) < 1
            img[eye] = paint(WHITE)
            img[((xx - w / 2) ** 2 + (yy - h * 0.62) ** 2) < 9] = paint((30, 70, 190))
            img[((xx - w / 2) ** 2 + (yy - h * 0.62) ** 2) < 3] = paint(INK)
            t2 = word_mask("CTOS", 1, gap=1)
            img[h - 10:h - 10 + 7, 7:7 + t2.shape[1]][t2[:7, :w - 7]] = paint((180, 200, 255))
        elif self.kind == "wanted":
            img[:] = paint((225, 205, 160))
            t = word_mask("WANTED", 1, gap=0)
            img[3:3 + t.shape[0], 2:2 + min(t.shape[1], w - 2)][t[:, :w - 2]] = paint((120, 30, 20))
            yy, xx = np.mgrid[0:h, 0:w]
            head = ((xx - w / 2) ** 2 + (yy - h * 0.5) ** 2) < 36
            body = (np.abs(xx - w / 2) < 9 - (h * 0.85 - yy) * 0.2) & (yy > h * 0.62) & (yy < h * 0.86)
            img[head | body] = paint((60, 40, 30))
            img[(yy > h * 0.88) & (yy < h * 0.92) & (xx > 4) & (xx < w - 4)] = paint((120, 30, 20))
        else:
            img[:] = paint((10, 20, 30))
            yy, xx = np.mgrid[0:h, 0:w]
            r = np.hypot(xx - w / 2, yy - h * 0.45)
            img[(r > 7) & (r < 10)] = paint(CYAN)
            img[r < 3] = paint(CYAN)
            t = word_mask("SAFE", 1, gap=1)
            img[h - 11:h - 4, 8:8 + t.shape[1]][t[:7, :w - 8]] = paint(WHITE)
        img[0, :] = img[-1, :] = paint((240, 240, 230))
        img[:, 0] = img[:, -1] = paint((240, 240, 230))
        self.img = img
        self.peel = 2.0            # fold line threshold (2 = intact)
        self.peel_speed = 0.0
        self.dead = False


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = 2 * h
        self.last = time.time()
        self.rng = random.Random()
        self.glitch = Glitch(0.004)
        self.fx = PostFX()
        self.f = self.ph * 0.95
        self.cx, self.cy = w / 2, self.ph * 0.5
        self.yaw = 0.22
        self.camx = 0.0
        a = (np.arange(w) - self.cx) / self.f
        self.A = a
        self.Bv = (-(np.arange(self.ph) - self.cy) / self.f)[:, None].astype(np.float32)
        self.canvas = np.zeros((CH, CW), np.int16)
        self.pieces = []
        self.posters = []
        self.stickers = []          # pending slaps
        self.next_u = 30.0
        self.kinds = ["dedsec", "skull", "hack", "crown", "wrench", "arrows"]
        self.rng.shuffle(self.kinds)
        self.kind_i = 0
        self.spray = []
        self.lamp_flick = {}
        self.make_skyline()
        self.pal = []
        self.ncols_pal = 0
        self.palette()
        # pre-seed some pieces so the first frame is not empty
        for _ in range(3):
            self.spawn_slot()
        for p in self.pieces[:1]:
            self.start_piece(p)
            while p.state == "paint":
                self.advance_piece(p, 0.25, None)

    # ------------------------------------------------------------ palette
    def palette(self):
        if self.ncols_pal == len(COLS):
            return
        lamp = (255, 214, 160)
        for cid in range(self.ncols_pal, len(COLS)):
            rgb, em = COLS[cid]
            for l in range(L):
                if em:
                    self.pal.append(rgb)
                    continue
                k = l / (L - 1)
                dark = blend((rgb[0] * 0.16, rgb[1] * 0.14, rgb[2] * 0.2), (8, 6, 30), 0.35)
                lit = (rgb[0] * lamp[0] / 255, rgb[1] * lamp[1] / 255, rgb[2] * lamp[2] / 255)
                c = blend(dark, lit, k ** 0.85)
                if l == L - 1:
                    c = blend(c, WHITE, 0.12)
                self.pal.append(c)
        self.ncols_pal = len(COLS)

    def make_skyline(self):
        n = 2048
        rng = random.Random(11)
        hs = np.zeros(n)
        i = 0
        while i < n:
            wdt = rng.randint(6, 30)
            hs[i:i + wdt] = rng.uniform(4, 30) if rng.random() < 0.8 else rng.uniform(30, 55)
            i += wdt + rng.randint(0, 6)
        self.sky_h = hs

    # ------------------------------------------------------------ slots
    def spawn_slot(self):
        kind = self.kinds[self.kind_i % len(self.kinds)]
        self.kind_i += 1
        p = Piece(kind, self.next_u, self.rng)
        # clear canvas region
        c0 = int(p.u0 * R) - 20
        cols = np.arange(c0, c0 + p.w + 60) % CW
        self.canvas[:, cols] = 0
        self.pieces.append(p)
        end = p.u0 + p.width_units
        # a poster or old-tag gap after the piece
        gap = self.rng.uniform(14, 26)
        if self.rng.random() < 0.6:
            pu = end + gap * 0.5
            self.posters.append(Poster(pu, self.rng.uniform(26, 34), self.rng))
            gap = max(gap, 24)
            cols = np.arange(int(pu * R) - 2, int((pu + 20) * R)) % CW
            self.canvas[:, cols] = 0
        self.next_u = end + gap
        self.pieces = self.pieces[-6:]
        self.posters = [q for q in self.posters if q.u0 > self.camx - 120 and not q.dead][-5:]

    def start_piece(self, p):
        p.state = "paint"
        p.li = 0
        p.crew = self.rng.choice(CREW)

    def write(self, p, layer, sel):
        """write selected layer cells into the ring canvas"""
        ys, xs = np.nonzero(sel)
        if ys.size == 0:
            return
        ids = layer.ids if np.isscalar(layer.ids) or getattr(layer.ids, "ndim", 0) == 0 else layer.ids[ys, xs]
        cv = CH - 1 - (p.v0 + ys)
        cu = (int(p.u0 * R) + xs) % CW
        ok = (cv >= 0) & (cv < CH)
        self.canvas[cv[ok], cu[ok]] = ids if np.isscalar(ids) else np.asarray(ids)[ok]

    def advance_piece(self, p, dt, now):
        lay = p.layers[p.li]
        p0 = lay.p
        lay.p = min(1.0, lay.p + dt / lay.dur)
        sel = lay.mask & (lay.order >= p0) & (lay.order < lay.p + (0.02 if lay.p >= 1 else 0))
        self.write(p, lay, sel)
        if lay.p >= 1.0:
            if p.li == 0 and not p.stencil:
                self.make_drips(p)
            p.li += 1
            if p.li >= len(p.layers):
                p.state = "done"
                p.done_at = now

    def make_drips(self, p):
        m = p.fillmask
        bottom = m & ~np.roll(m, -1, 0)
        ys, xs = np.nonzero(bottom)
        if ys.size == 0:
            return
        sel = np.random.choice(ys.size, min(ys.size, max(3, ys.size // 25)), replace=False)
        lay = p.layers[0]
        for i in sel:
            y, x = ys[i], xs[i]
            cid = lay.ids if np.isscalar(lay.ids) or getattr(lay.ids, "ndim", 0) == 0 else int(lay.ids[y, x])
            p.drips.append([x, y + 1, 0.0, self.rng.uniform(3, 18), self.rng.uniform(2, 7), int(cid)])

    def step_drips(self, p, dt):
        for d in p.drips:
            if d[2] >= d[3]:
                continue
            old = int(d[2])
            d[2] = min(d[3], d[2] + d[4] * dt)
            d[4] *= 0.995
            for k in range(old, int(d[2]) + 1):
                cv = CH - 1 - (p.v0 + d[1] + k)
                if 0 <= cv < CH:
                    self.canvas[cv, (int(p.u0 * R) + d[0]) % CW] = d[5]

    # ------------------------------------------------------------ projection
    def wall_to_screen(self, u, v, z=ZW):
        cy_, sy_ = math.cos(self.yaw), math.sin(self.yaw)
        x, y, zz = u - self.camx, v - HCAM, z
        cxv = x * cy_ - zz * sy_
        czv = x * sy_ + zz * cy_
        if czv < 1:
            return None
        return self.cx + self.f * cxv / czv, self.cy - self.f * y / czv, czv

    # ------------------------------------------------------------ raster
    def raster(self, now, beat):
        cy_, sy_ = math.cos(self.yaw), math.sin(self.yaw)
        A = self.A
        dxw = A * cy_ + sy_
        dzw = -A * sy_ + cy_
        tw = ZW / dzw                                   # per column depth to wall
        u = self.camx + tw * dxw                        # per column wall x
        B = self.Bv
        v = HCAM + B * tw[None, :]                      # (ph, w)
        wall = (v >= 0) & (v < WH)
        sky = v >= WH
        ground = v < 0
        uu = np.broadcast_to(u[None, :], v.shape)
        # bricks
        row = np.floor(v / 3.0)
        off = (row % 2) * 3.0
        bx = np.floor((uu + off) / 6.0)
        hsh = ((bx.astype(np.int64) * 73856093) ^ (row.astype(np.int64) * 19349663)) & 0xFFFF
        bid = np.array(BRICKS)[hsh % len(BRICKS)]
        mort = ((v % 3.0) < 0.55) | (((uu + off) % 6.0) < 0.55)
        ids = np.where(mort, MORTAR, bid)
        ids = np.where(v > WH - 1.8, np.where(v > WH - 0.6, COPING2, COPING), ids)
        # paint canvas
        cu = (np.floor(u * R).astype(np.int64)) % CW
        cv = np.clip((CH - 1 - np.floor(v * R)).astype(np.int64), 0, CH - 1)
        pv = self.canvas[cv, cu[None, :]]
        painted = wall & (pv > 0) & (v < WH - 1.8)
        ids = np.where(painted, pv, ids)
        # Attached street details: recessed service vents and conduit on the
        # actual wall plane. They inherit the camera's perspective and lighting.
        service_u = uu % 128
        vent = wall & (service_u > 92) & (service_u < 108) & (v > 6) & (v < 17)
        trim = vent & ((service_u < 92.6) | (service_u > 107.4) | (v < 6.5) | (v > 16.5))
        slats = vent & (((v * 1.4) % 1) < 0.28)
        ids = np.where(vent, np.where(trim | slats, VENT_EDGE, VENT), ids)
        conduit = wall & (np.abs(service_u - 89) < 0.4) & (v < 30)
        ids = np.where(conduit, PIPE, ids)
        # posters
        for po in self.posters:
            if po.u0 > u[-1] + 5 or po.u0 + po.wu < u[0] - 5:
                continue
            lx = (uu - po.u0) / po.wu
            ly = (po.v0 - v) / po.hu
            inside = wall & (lx >= 0) & (lx < 1) & (ly >= 0) & (ly < 1)
            if not inside.any():
                continue
            ph_, pw_ = po.img.shape
            ix = np.clip((lx * pw_).astype(np.int64), 0, pw_ - 1)
            iy = np.clip((ly * ph_).astype(np.int64), 0, ph_ - 1)
            d = lx + ly
            c = po.peel
            front = inside & (d <= c)
            ids = np.where(front, po.img[iy, ix], ids)
            if c < 2.0:
                mx, my = lx + (c - d), ly + (c - d)   # mirror across x+y=c
                flap = inside & (d <= c) & (mx >= 0) & (mx < 1) & (my >= 0) & (my < 1) & (2 * c - d <= 2)
                flap = (wall & (lx + ly <= c) & ((lx + (c - d)) < 1) & ((ly + (c - d)) < 1) & (lx >= 0) & (ly >= 0)
                        & (lx < 1) & (ly < 1) & (d >= 2 * c - 2))
                ids = np.where(flap, np.where((c - d) < 0.06, PAPER_SHADE, PAPER_BACK), ids)
        # ground
        with np.errstate(divide="ignore", invalid="ignore"):
            tg = np.where(B < -1e-4, HCAM / -B, 1e9)
        gx = self.camx + tg * dxw[None, :]
        gz = tg * dzw[None, :]
        side = gz > ZW - 13
        curb = (gz > ZW - 14) & ~side
        gids = np.where(side, np.where(((gx % 8) < 0.35) | ((gz % 8) < 0.35), JOINT, SIDEWALK),
                        np.where(curb, CURB, np.where((np.abs(gz - (ZW - 26)) < 0.35) & ((gx % 12) < 6), LANE, ROAD)))
        ids = np.where(ground, gids, ids)
        # sky + skyline
        ang = ((self.yaw + np.arctan(A)) * 400 + self.camx * 0.6).astype(np.int64) % self.sky_h.size
        hgt = self.sky_h[ang]
        top_py = self.cy - self.f * (WH - HCAM) / tw            # wall top row per column
        rowsP = np.arange(self.ph)[:, None]
        skyl = sky & (rowsP > (top_py - hgt * 0.5)[None, :])
        sk_band = np.clip(rowsP * 6 // max(1, self.ph // 2), 0, 5)
        sids = np.array(SKY)[sk_band]
        sids = np.broadcast_to(sids, v.shape)
        sids = np.where(skyl, np.where(((rowsP * 5 + ang[None, :] * 3) % 17 == 0), SKYWIN, SKYLINE), sids)
        star = sky & ~skyl & (((rowsP * 131 + ang[None, :] * 71) % 97) == 0)
        sids = np.where(star, STAR, sids)
        ids = np.where(sky, sids, ids)

        # lighting
        li = np.round((u - LAMP_SP / 2) / LAMP_SP)
        lxp = li * LAMP_SP + LAMP_SP / 2
        inten = np.array([self.lamp_level(int(k), now, beat) for k in li])
        du = (u - lxp)[None, :]
        dv = LAMP_H - v
        sig = 7 + np.maximum(dv, 0) * 0.85
        I = 0.18 + inten[None, :] * np.exp(-(du * du) / (2 * sig * sig)) * np.exp(-np.maximum(-dv, 0) / 3.5) * 1.05
        # ground pools
        gd2 = (gx - lxp[None, :]) ** 2 + (gz - LAMP_Z) ** 2 * 1.4
        Ig = 0.16 + inten[None, :] * np.exp(-gd2 / 260)
        I = np.where(ground, Ig, I)
        I = np.where(painted, I + 0.22, I)
        # Mortar relief, irregular clay chips and damp streaks remain fixed in
        # world coordinates as the camera moves past; paint keeps its pigment.
        clay = ((np.floor(uu * 3).astype(np.int64) * 31) ^
                (np.floor(v * 3).astype(np.int64) * 73)) % 23
        relief = 0.90 + clay / 180
        relief = np.where((v % 3) < 0.7, relief * 0.68, relief)
        relief = np.where((v % 3) > 2.65, relief * 1.16, relief)
        damp = (v < 4.5 + (hsh % 11) * 0.3) & (((uu + off) % 6) < 2.1)
        relief = np.where(damp, relief * 0.65, relief)
        I = np.where(wall & ~painted & ~vent & ~conduit, I * relief, I)
        lvl = np.clip((I * (L - 1)).astype(np.int64), 0, L - 1)
        # foreground: lamp posts, poles, fence
        ids, lvl = self.foreground(ids, lvl, v, dxw, dzw, B, now, beat)
        return ids * L + lvl, u

    def lamp_level(self, k, now, beat):
        r = (k * 2654435761) & 0xFFFF
        base = 1.0
        if r % 3 == 0:     # the flickering lamp
            t = now * 13 + k
            fl = 0.5 + 0.5 * math.sin(t) * math.sin(t * 2.7 + 1)
            base = 0.25 + 0.75 * (fl > -0.1 * (1 - beat)) * (0.6 + 0.4 * fl)
            if beat > 0.6:
                base *= 0.25
        return base * (0.86 + 0.24 * beat)

    def foreground(self, ids, lvl, v, dxw, dzw, B, now, beat):
        # lamp posts (just in front of the wall)
        t_l = LAMP_Z / dzw
        xl = self.camx + t_l * dxw
        vl = HCAM + B * t_l[None, :]
        k = np.round((xl - LAMP_SP / 2) / LAMP_SP)
        lpx = k * LAMP_SP + LAMP_SP / 2
        post = (np.abs(xl - lpx) < 0.45)[None, :] & (vl >= -0.2) & (vl < LAMP_H)
        arm = (np.abs(xl - lpx - 2.2) < 2.6)[None, :] & (np.abs(vl - LAMP_H) < 0.5)
        m = post | arm
        ids = np.where(m, POST, ids)
        lvl = np.where(m, 2, lvl)
        # near poles + chain fence
        t_f = FG_Z / dzw
        xf = self.camx * 1.0 + t_f * dxw
        vf = HCAM + B * t_f[None, :]
        seg = np.floor(xf / 46.0)
        lx = xf - seg * 46.0
        has_fence = ((seg.astype(np.int64) * 7) % 5 < 2)
        pole = (lx < 0.5)[None, :] & (vf >= -1) & (vf < 26)
        fence = (has_fence & (lx > 0.5) & (lx < 30))[None, :] & (vf >= -1) & (vf < 13) & \
            ((((xf[None, :] + vf) % 1.6) < 0.16) | (((xf[None, :] - vf) % 1.6) < 0.16) | (np.abs(vf - 13) < 0.2))
        mf = pole | fence
        ids = np.where(mf, np.where(pole, POST, FENCE), ids)
        lvl = np.where(mf, np.where(pole, 1, 3), lvl)
        return ids, lvl

    # ------------------------------------------------------------ main
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        beat = DATA.beat
        glitch = self.glitch.active(now)
        self.camx += 6.0 * dt
        self.yaw = 0.22 + 0.05 * math.sin(now * 0.11)

        # slots ahead
        while self.next_u < self.camx + 230:
            self.spawn_slot()
        # start / advance painting
        active = []
        for p in self.pieces:
            if p.state == "wait":
                q = self.wall_to_screen(p.u0 + p.width_units * 0.35, WH / 2)
                if q and q[0] < self.w * 0.82 and sum(1 for o in self.pieces if o.state == "paint") < 2:
                    self.start_piece(p)
            if p.state == "paint":
                self.advance_piece(p, dt, now)
                active.append(p)
            self.step_drips(p, dt)
        # posters peel
        for po in self.posters:
            q = self.wall_to_screen(po.u0, po.v0)
            if po.peel_speed == 0 and q and q[0] < self.w * 0.6 and self.rng.random() < 0.02:
                po.peel_speed = self.rng.uniform(0.12, 0.3)
            if po.peel_speed:
                po.peel -= po.peel_speed * dt
                if po.peel < 0.9:
                    po.peel_speed *= 1.0 + dt * 2
                if po.peel < 0.0:
                    po.dead = True
        self.posters = [p for p in self.posters if not p.dead]
        # stickers
        if self.rng.random() < dt * 0.35:
            self.slap_sticker(now)
        self.palette()

        idx, ucols = self.raster(now, beat)
        # lamp cones (screen space brighten) & heads
        heads = self.draw_lamps_prep(ucols)
        if heads:
            rows = np.arange(self.ph)[:, None]
            xs = np.arange(self.w)[None, :]
            for hx, hy, inten in heads:
                if inten < 0.4:
                    continue
                cone = (rows > hy + 1) & (np.abs(xs - hx) < (rows - hy) * 0.42 + 0.5) & ((rows - hy) < self.ph * 0.75)
                idx = np.where(cone & ((idx % L) < L - 1), idx + 1, idx)
        pal = self.pal
        g = pal.__getitem__
        Lr = idx.tolist()
        for y in range(self.h):
            s.pt[y] = list(map(g, Lr[2 * y]))
            s.pb[y] = list(map(g, Lr[2 * y + 1]))
        for hx, hy, inten in heads:
            col = blend((60, 50, 40), (255, 236, 200), inten)
            s.pixel_rect(hx - 2, hy - 1, 6, 2, col)
            s.pixel_rect(hx - 1, hy - 2, 4, 1, (30, 30, 40))
        self.draw_stickers(s, now, dt)
        for p in active:
            self.draw_can(s, p, now, dt)
        self.step_spray(s, dt)
        self.draw_hud(s, now, active, beat)
        if glitch:
            self.fx.apply(s, now, True)

    def draw_lamps_prep(self, ucols):
        heads = []
        k0 = int(math.floor((self.camx - 40) / LAMP_SP))
        for k in range(k0, k0 + 8):
            lx = k * LAMP_SP + LAMP_SP / 2
            q = self.wall_to_screen(lx + 4.6, LAMP_H - 0.6, LAMP_Z)
            if q and -10 < q[0] < self.w + 10:
                heads.append((int(q[0]), int(q[1]), self.lamp_level(k, self.last, DATA.beat)))
        return heads

    # ------------------------------------------------------------ sprays & cans
    def draw_can(self, s, p, now, dt):
        if p.li >= len(p.layers):
            return
        lay = p.layers[p.li]
        pos = lay.can_pos()
        cid = lay.ids if np.isscalar(lay.ids) or getattr(lay.ids, "ndim", 0) == 0 else None
        col = COLS[int(cid)][0] if cid is not None else p.color
        if pos is None:
            # stencil: card + random fog
            q0 = self.wall_to_screen(p.u0 - 1, (CH - p.v0) / R + 1)
            q1 = self.wall_to_screen(p.u0 + p.width_units + 1, (CH - p.v0 - p.h) / R - 1)
            if q0 and q1:
                x0, y0, x1, y1 = int(q0[0]), int(q0[1]), int(q1[0]), int(q1[1])
                card = (150, 120, 80)
                for x in range(max(0, x0), min(s.w, x1)):
                    for py in (y0, y1):
                        s.pixel(x, py, card)
                for py in range(max(0, y0), min(s.ph, y1)):
                    s.pixel(x0, py, card)
                    s.pixel(x1 - 1, py, card)
                for _ in range(6):
                    x = random.uniform(x0, x1)
                    y = random.uniform(y0, y1)
                    self.spray.append([x, y, random.uniform(-6, 6), random.uniform(-6, 6), 0.0, 0.5, blend(col, BLACK, 0.3)])
            return
        cx, cy = pos
        u = p.u0 + cx / R
        v = (CH - p.v0 - cy) / R
        q = self.wall_to_screen(u, v)
        if not q:
            return
        x, y = q[0], q[1]
        for _ in range(7):
            a = random.uniform(0, math.tau)
            sp = random.uniform(4, 22)
            self.spray.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 0.0, random.uniform(0.15, 0.45),
                               blend(col, WHITE, random.uniform(0, 0.3))])
        # overspray specks into canvas
        if random.random() < 0.6:
            ox = int(cx + random.gauss(0, 4))
            oy = int(cy + random.gauss(0, 4))
            cvv = CH - 1 - (p.v0 + oy)
            if 0 <= cvv < CH and cid is not None:
                self.canvas[cvv, (int(p.u0 * R) + ox) % CW] = int(cid)
        # the can (pixels), held a bit in front / right of the spray point
        bx, by = int(x + 4), int(y - 1)
        s.pixel_rect(bx, by, 3, 7, (170, 170, 180))
        s.pixel_rect(bx, by + 2, 3, 3, col)
        s.pixel_rect(bx + 1, by - 1, 1, 1, WHITE)
        s.pixel_rect(bx + 3, by + 2, 1, 4, (90, 90, 100))
        for k in range(1, 4):
            s.pixel(bx - k, by - 1 + random.randint(-1, 1), blend(col, WHITE, 0.5))

    def step_spray(self, s, dt):
        alive = []
        for sp in self.spray:
            sp[4] += dt
            if sp[4] >= sp[5]:
                continue
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            t = sp[4] / sp[5]
            s.pixel(int(sp[0]), int(sp[1]), blend(sp[6], BLACK, t * 0.8))
            alive.append(sp)
        self.spray = alive[-400:]

    def slap_sticker(self, now):
        art, cmap = random.choice(STICKERS)
        u = self.camx + random.uniform(10, 110)
        v = random.uniform(5, WH - 8)
        self.stickers.append({"art": art, "cmap": cmap, "u": u, "v": v, "t": now})

    def draw_stickers(self, s, now, dt):
        keep = []
        for st in self.stickers:
            age = now - st["t"]
            art = st["art"]
            hh, ww = len(art), len(art[0])
            if age >= 0.28:
                # commit to canvas (1 cell = 1 sticker pixel)
                c0 = int(st["u"] * R)
                r0 = CH - 1 - int(st["v"] * R)
                for j, row in enumerate(art):
                    for i, ch in enumerate(row):
                        if ch in st["cmap"] and 0 <= r0 + j < CH:
                            self.canvas[r0 + j, (c0 + i) % CW] = paint(st["cmap"][ch])
                q = self.wall_to_screen(st["u"] + ww / R / 2, st["v"] - hh / R / 2)
                if q:
                    for _ in range(10):
                        a = random.uniform(0, math.tau)
                        self.spray.append([q[0], q[1], math.cos(a) * 25, math.sin(a) * 12, 0, 0.25, WHITE])
                continue
            q = self.wall_to_screen(st["u"], st["v"])
            if not q:
                continue
            k = (3.5 - 2.5 * ease_out(age / 0.28)) * self.f / q[2] / R
            for j, row in enumerate(art):
                for i, ch in enumerate(row):
                    if ch in st["cmap"]:
                        s.pixel_rect(q[0] + i * k, q[1] + j * k, max(1, k + 0.5), max(1, k + 0.5), st["cmap"][ch])
            keep.append(st)
        self.stickers = keep

    def draw_hud(self, s, now, active, beat):
        x, y = 2, 1
        lines = []
        if active:
            p = active[0]
            tot = sum(l.dur for l in p.layers)
            done = sum(l.dur * l.p for l in p.layers)
            pct = done / tot
            bw = 16
            lines.append(("◆ %s IS PAINTING" % p.crew, PINK))
            lines.append(("PIECE: %s" % p.title, WHITE))
            lines.append(("[" + "▓" * int(bw * pct) + "░" * (bw - int(bw * pct)) + "] %3d%%" % (pct * 100), CYAN))
        else:
            lines.append(("◆ DEDSEC STREET CREW", PINK))
            lines.append(("SCOUTING NEXT WALL...", GREY))
        for i, (t, c) in enumerate(lines):
            for k, ch in enumerate(t):
                s.put(x + k, y + i, ch, c)
                s.set_bg(x + k, y + i, (10, 4, 18))
        cam = "ctOS CAM: " + ("OFFLINE" if int(now * 2) % 2 else "OFFLINE ●")
        s.text(s.w - len("ctOS CAM: OFFLINE ●") - 2, 1, cam, GREEN if int(now) % 2 else YELLOW)
        if s.h > 30:
            msg = "#HACKTHEPLANET"
            s.text(s.w - len(msg) - 2, s.h - 2, msg, blend(PINK, YELLOW, beat))

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "spray", "LAST TAG // DEDSEC WAS HERE", PINK)
        if t >= 1:
            return
        # The last can crosses the wall, leaving a travelling cloud of pigment.
        x, py = int(s.w * t), int(s.ph * 0.58)
        s.pixel_rect(x - 2, py, 4, 9, (154, 156, 170))
        s.pixel_rect(x - 2, py + 3, 4, 4, PINK)
        s.pixel_rect(x - 1, py - 2, 2, 2, WHITE)
        for k in range(28):
            age = ((k * 7) % 29) / 29
            sx = x - int(age * 14)
            sy = py - 2 + int(math.sin(k * 2.1) * age * 13)
            s.pixel(sx, sy, blend(PINK, BLACK, age * 0.85 + t * 0.1))

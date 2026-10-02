"""TEXTWALL: night dolly along a brick wall while DedSec graffiti sprays itself on, under flickering lamps."""

import math
import random
import time

import numpy as np

from sysdata import DATA
from lib import (BLACK, CYAN, DIM_PINK, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW, Glitch,
                 blend, ease_out, line_points, pulse)
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


# Bold block alphabet for the lettering pieces: 2-wide verticals, 7 rows.
BOLD = {
    "A": [".1111.", "11..11", "11..11", "111111", "11..11", "11..11", "11..11"],
    "B": ["11111.", "11..11", "11..11", "11111.", "11..11", "11..11", "11111."],
    "C": [".11111", "11....", "11....", "11....", "11....", "11....", ".11111"],
    "D": ["11111.", "11..11", "11..11", "11..11", "11..11", "11..11", "11111."],
    "E": ["111111", "11....", "11....", "11111.", "11....", "11....", "111111"],
    "F": ["111111", "11....", "11....", "11111.", "11....", "11....", "11...."],
    "G": [".11111", "11....", "11....", "11.111", "11..11", "11..11", ".1111."],
    "H": ["11..11", "11..11", "11..11", "111111", "11..11", "11..11", "11..11"],
    "I": ["11", "11", "11", "11", "11", "11", "11"],
    "K": ["11..11", "11.11.", "1111..", "111...", "1111..", "11.11.", "11..11"],
    "L": ["11....", "11....", "11....", "11....", "11....", "11....", "111111"],
    "M": ["11...11", "111.111", "1111111", "11.1.11", "11...11", "11...11", "11...11"],
    "N": ["11..11", "111.11", "111111", "11.111", "11..11", "11..11", "11..11"],
    "O": [".1111.", "11..11", "11..11", "11..11", "11..11", "11..11", ".1111."],
    "P": ["11111.", "11..11", "11..11", "11111.", "11....", "11....", "11...."],
    "R": ["11111.", "11..11", "11..11", "11111.", "11.11.", "11..11", "11..11"],
    "S": [".11111", "11....", "11....", ".1111.", "....11", "....11", "11111."],
    "T": ["111111", "..11..", "..11..", "..11..", "..11..", "..11..", "..11.."],
    "U": ["11..11", "11..11", "11..11", "11..11", "11..11", "11..11", ".1111."],
    "W": ["11...11", "11...11", "11...11", "11.1.11", "11.1.11", "1111111", ".11.11."],
    "X": ["11..11", "11..11", ".1111.", "..11..", ".1111.", "11..11", "11..11"],
    "Y": ["11..11", "11..11", ".1111.", "..11..", "..11..", "..11..", "..11.."],
    "!": ["11", "11", "11", "11", "11", "..", "11"],
    " ": ["...", "...", "...", "...", "...", "...", "..."],
}
GLYPHS = {ch: np.array([[c == "1" for c in r] for r in g]) for ch, g in BOLD.items()}

# Lettering colour schemes: fill top, mid, bottom, outline, 3D, cut-line, cloud.
SCHEMES = {
    "dedsec": [((255, 130, 215), (255, 15, 123), (150, 0, 150), WHITE, (0, 150, 175), INK, (26, 14, 40)),
               ((170, 250, 255), (0, 210, 255), (0, 90, 210), INK, (210, 0, 120), WHITE, (36, 10, 46))],
    "hack": [((230, 255, 120), (57, 230, 110), (0, 170, 230), INK, (200, 0, 110), WHITE, (30, 16, 48))],
    "resist": [((255, 240, 90), (255, 140, 0), (230, 40, 40), INK, (0, 110, 150), (245, 245, 245), (40, 12, 44))],
}


def shift(m, dy, dx):
    """Shift a bool mask (no wrap) by dy rows / dx cols."""
    out = np.zeros_like(m)
    h, w = m.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = m[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def bold_line(text, k, shear, bounce, base_id, phase):
    gws = [GLYPHS.get(ch, GLYPHS[" "]).shape[1] for ch in text]
    gh = 7 * k
    extra = int(shear * gh) + 1
    wcells = sum((g + 1) * k for g in gws) + extra
    m = np.zeros((gh + 2 * bounce + 1, wcells), bool)
    lid = np.full(m.shape, -1, np.int32)
    x = 0
    for i, ch in enumerate(text):
        g = GLYPHS.get(ch, GLYPHS[" "])
        big = np.kron(g, np.ones((k, k), bool))
        dy = bounce + int(round(bounce * math.sin(i * 1.9 + phase)))
        bw = big.shape[1]
        for yy in range(gh):
            off = int((gh - yy) * shear)
            row = big[yy]
            seg = m[dy + yy, x + off:x + off + bw]
            seg |= row
            lid[dy + yy, x + off:x + off + bw][row] = base_id + i
        x += (g.shape[1] + 1) * k
    return m, lid


def ord_zigzag(shape, band):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    nb = max(1, int(math.ceil(h / band)))
    bi = yy // band
    fr = np.where(bi % 2 == 0, xx / max(1, w - 1), 1 - xx / max(1, w - 1))
    return (bi + fr) / nb


def ord_columns(shape, band):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    nb = max(1, int(math.ceil(w / band)))
    bi = xx // band
    fr = np.where(bi % 2 == 0, yy / max(1, h - 1), 1 - yy / max(1, h - 1))
    return (bi + fr) / nb


def ord_letters(lid, band):
    """Letter by letter, each letter filled in a zigzag of horizontal strokes."""
    order = np.zeros(lid.shape)
    ids = [j for j in np.unique(lid) if j >= 0]
    n = max(1, len(ids))
    yy, xx = np.mgrid[0:lid.shape[0], 0:lid.shape[1]]
    for rank, j in enumerate(ids):
        sel = lid == j
        ys, xs = yy[sel], xx[sel]
        y0, x0, x1 = ys.min(), xs.min(), xs.max()
        nb = max(1, int(math.ceil((ys.max() - y0 + 1) / band)))
        bi = (ys - y0) // band
        f = (xs - x0) / max(1, x1 - x0)
        fr = np.where(bi % 2 == 0, f, 1 - f)
        order[sel] = (rank + (bi + fr) / nb) / n
    return order


def spread_ids(lid, steps):
    out = lid.copy()
    for _ in range(steps):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.roll(np.roll(out, dy, 0), dx, 1)
            take = (out < 0) & (nb >= 0)
            out[take] = nb[take]
    return out


class Layer:
    """One paint pass. Cells are pre-sorted by paint order; the can follows the frontier."""

    def __init__(self, mask, ids, order, dur=None, can=True):
        ys, xs = np.nonzero(mask)
        o = order[ys, xs] + np.random.rand(ys.size) * 0.004
        idx = np.argsort(o, kind="stable")
        self.ys, self.xs, self.o = ys[idx], xs[idx], o[idx]
        if np.isscalar(ids) or getattr(ids, "ndim", 0) == 0:
            self.cid = int(ids)
            self.ids = None
        else:
            self.cid = None
            self.ids = np.asarray(ids)[ys, xs][idx]
        self.n = int(ys.size)
        self.dur = dur if dur is not None else max(0.6, min(4.5, self.n / 900))
        self.p = 0.0
        self.i = 0
        self.can = can
        self.mask = mask

    def can_pos(self):
        if not self.can or self.n == 0:
            return None
        i = min(self.n - 1, self.i)
        return self.xs[i], self.ys[i]


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
        self.drip_after = 0
        self.drip_mask = None
        self.drip_ids = None
        build = getattr(self, "b_" + kind)
        build(rng)
        h, w = self.layers[0].mask.shape
        self.h, self.w = h, w
        # top canvas row of the piece (canvas row 0 is the top of the wall)
        lo, hi = 4, max(4, CH - 2 - h)
        self.v0 = int(lo + rng.uniform(0.25, 0.75) * (hi - lo))
        self.width_units = w / R

    # -- builders ---------------------------------------------------------
    def gradient(self, h, w, a, b, steps=5):
        ids = [paint(blend(a, b, i / (steps - 1))) for i in range(steps)]
        rows = (np.arange(h) * steps // max(1, h)).clip(0, steps - 1)
        return np.array(ids)[rows][:, None].repeat(w, 1)

    def lettering(self, rng, lines, k, scheme, shear=0.18, title=""):
        fa, fb, fc, outline, ext_c, cut_c, cloud_c = scheme
        bounce = 2 if len(lines) == 1 else 1
        rows, lids, nid = [], [], 0
        phase = rng.uniform(0, 6)
        for text in lines:
            m, lid = bold_line(text, k, shear, bounce, nid, phase)
            nid += len(text)
            rows.append(m)
            lids.append(lid)
        gap = k + 3
        W = max(r.shape[1] for r in rows)
        H = sum(r.shape[0] for r in rows) + gap * (len(rows) - 1)
        pad = 9
        m = np.zeros((H + 2 * pad, W + 2 * pad + k), bool)
        lid = np.full(m.shape, -1, np.int32)
        spans = []
        y = pad
        for r, l in zip(rows, lids):
            x = pad + (W - r.shape[1]) // 2
            m[y:y + r.shape[0], x:x + r.shape[1]] |= r
            lid[y:y + r.shape[0], x:x + r.shape[1]][l >= 0] = l[l >= 0]
            spans.append((y + bounce, y + bounce + 7 * k))
            y += r.shape[0] + gap
        h, w = m.shape
        yy, xx = np.mgrid[0:h, 0:w]
        # fill: three-tone split with a wavy seam and a bright seam line
        t = np.zeros((h, w))
        for y0, y1 in spans:
            band = (yy >= y0 - 2) & (yy < y1 + 2)
            t[band] = ((yy - y0) / max(1, y1 - y0) + 0.09 * np.sin(xx * 0.13 + phase))[band]
        t = t.clip(0, 0.999)
        steps = [paint(blend(fa, fb, i / 2)) for i in range(3)] + [paint(blend(fb, fc, i / 2)) for i in range(1, 4)]
        fill_ids = np.array(steps)[(t * 6).astype(np.int64)]
        seam = np.abs(t - 0.52) < 0.03
        fill_ids = np.where(seam, paint(blend(fb, WHITE, 0.45)), fill_ids)
        ro = 2
        O = dilate(m, ro)
        out = O & ~m
        # 3D block extrusion down-right, lighter next to the letters
        d3 = k + 1
        ext = np.zeros_like(m)
        ext_ids = np.zeros(m.shape, np.int64)
        for i in range(d3, 0, -1):
            s_ = shift(O, i, i)
            ext |= s_
            ext_ids[s_] = paint(blend(blend(ext_c, WHITE, 0.18), blend(ext_c, BLACK, 0.45), (i - 1) / max(1, d3 - 1)))
        ext &= ~O
        OE = O | ext
        edge = ext & (~shift(OE, -1, 0) | ~shift(OE, 0, -1))
        ext_ids[edge] = paint(blend(ext_c, BLACK, 0.7))
        cut = dilate(OE, 1) & ~OE
        ALL = OE | cut
        # bubbly background cloud with a sprayed (speckled) rim
        bub = dilate(ALL, 3)
        for _ in range(max(3, w // 22)):
            cx, cy, r = rng.uniform(pad, w - pad), rng.choice((pad, h - pad)), rng.uniform(3, 7)
            bub |= ((xx - cx) ** 2 + (yy - cy) ** 2) < r * r
        bub = smooth(bub, 2)
        cloud = bub & ~ALL
        rim = cloud & ~smooth(dilate(ALL, 2), 1)
        cloud &= ~(rim & (np.random.rand(h, w) < 0.45))
        cloud_ids = np.where(np.random.rand(h, w) < 0.07, paint(blend(cloud_c, WHITE, 0.12)), paint(cloud_c))
        # shine: top edge of each stroke, left part of each letter
        th = 1
        top = m & ~shift(m, th, 0)
        lx = np.zeros(m.shape)
        for j in range(nid):
            sel = lid == j
            if sel.any():
                xs = xx[sel]
                lx[sel] = (xs - xs.min()) / max(1, xs.max() - xs.min())
        shine = top & (lx < 0.55) & ~shift(out, 0, -th - 1)
        # star glints on a few letter corners
        glint = np.zeros_like(m)
        for j in range(nid):
            if rng.random() < 0.4:
                sel = lid == j
                if not sel.any():
                    continue
                gy, gx = yy[sel].min() - 1, xx[sel].min() + 1
                for d in range(-3, 4):
                    for e in (0, 1):
                        if 0 <= gy + d < h and 0 <= gx + e < w:
                            glint[gy + d, gx + e] = True
                        if 0 <= gy + e < h and 0 <= gx + d < w:
                            glint[gy + e, gx + d] = True
        lid_o = spread_ids(lid, ro + 1)
        nf = int(m.sum())
        self.layers = [
            Layer(cloud, cloud_ids, ord_zigzag(m.shape, 12), dur=1.4),
            Layer(m, fill_ids, ord_letters(lid, max(2, k)), dur=max(2.2, nf / 1000)),
            Layer(ext, ext_ids, ord_columns(m.shape, 8), dur=1.4),
            Layer(out, paint(outline), ord_letters(np.where(out, lid_o, -1), 6), dur=2.0),
            Layer(cut, paint(cut_c), ord_columns(m.shape, 10), dur=0.9),
            Layer(shine & ~glint, paint(blend(fa, WHITE, 0.7)), ord_zigzag(m.shape, 8), dur=0.8),
            Layer(glint, paint(WHITE), ord_zigzag(m.shape, 6), dur=0.4),
        ]
        bottom = O & ~shift(O, -1, 0)
        self.drip_after = len(self.layers) - 1
        self.drip_mask = bottom & (xx % 3 == 0)
        self.drip_ids = paint(outline)
        self.color = fb
        self.fillmask = m
        self.title = title

    def b_dedsec(self, rng):
        self.lettering(rng, ["DEDSEC"], 4, rng.choice(SCHEMES["dedsec"]), title="DEDSEC")

    def b_hack(self, rng):
        self.lettering(rng, ["HACK THE", "PLANET!"], 3, SCHEMES["hack"][0], shear=0.14, title="HACK THE PLANET")

    def b_resist(self, rng):
        self.lettering(rng, ["RESIST"], 4, SCHEMES["resist"][0], shear=0.2, title="RESIST")

    def _simple(self, m, layers, color, title, drip=True):
        h, w = m.shape
        self.layers = layers
        self.color = color
        self.fillmask = m
        self.title = title
        if drip:
            self.drip_after = 0
            self.drip_mask = m & ~shift(m, -1, 0)
            self.drip_ids = layers[0].ids_full

    def b_skull(self, rng):
        m = pad(smooth(bitmap_mask(SKULL, 3), 1), 6)
        out = dilate(m, 2) & ~m
        h, w = m.shape
        g = self.gradient(h, w, WHITE, (200, 200, 220))
        L0 = Layer(m, g, ord_zigzag(m.shape, 6))
        L0.ids_full = g
        self._simple(m, [L0, Layer(out, paint(INK), ord_columns(m.shape, 6)),
                         Layer(m & ~shift(m, 2, 0), paint(PINK), ord_zigzag(m.shape, 10))], WHITE, "SKULL")

    def b_crown(self, rng):
        m = pad(dilate(bitmap_mask(CROWN, 4), 1), 6)
        out = dilate(m, 1) & ~m
        L0 = Layer(m, paint(YELLOW), ord_columns(m.shape, 5))
        L0.ids_full = paint(YELLOW)
        self._simple(m, [L0, Layer(out, paint(INK), ord_columns(m.shape, 5))], YELLOW, "CROWN")

    def b_arrows(self, rng):
        a = bitmap_mask(ARROW, 4)
        m = np.zeros((a.shape[0] * 2 + 6, a.shape[1] + 20), bool)
        m[:a.shape[0], :a.shape[1]] = a
        m[a.shape[0] + 6:, 20:] = a
        m = pad(smooth(m, 1), 6)
        out = dilate(m, 2) & ~m
        h, w = m.shape
        g = self.gradient(h, w, (0, 200, 255), PINK)
        L0 = Layer(m, g, ord_zigzag(m.shape, 6))
        L0.ids_full = g
        self._simple(m, [L0, Layer(out, paint(WHITE), ord_columns(m.shape, 6))], CYAN, "ARROWS")

    def b_wrench(self, rng):
        k = 3
        black = pad(bitmap_mask(WRENCH, k, "X123"), 6)
        led1 = pad(bitmap_mask(WRENCH, k, "1"), 6)
        led2 = pad(bitmap_mask(WRENCH, k, "2"), 6)
        teeth = pad(bitmap_mask(WRENCH, k, "3"), 6)
        rng2 = np.random.RandomState(rng.randint(0, 9999))
        self.layers = [Layer(black, paint(INK), rng2.random_sample(black.shape), dur=2.2, can=False),
                       Layer(led1 | led2 | teeth, np.where(led1, paint(CYAN), np.where(led2, paint(PINK), paint(WHITE))),
                             rng2.random_sample(black.shape), dur=1.4, can=False)]
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


# ------------------------------------------------------------------ baked wall texture
TR = 4                 # texture cells per wall unit
TU = 384               # ring period in units (multiple of brick 6 and service bay 128)
TW = TU * TR
TH = int(WH * TR)


def bake_wall():
    V = ((TH - 1 - np.arange(TH)) + 0.5)[:, None] / TR          # row 0 = top of wall
    U = (np.arange(TW) + 0.5)[None, :] / TR
    V = np.broadcast_to(V, (TH, TW))
    U = np.broadcast_to(U, (TH, TW))
    row = np.floor(V / 3.0)
    off = (row % 2) * 3.0
    bx = np.floor((U + off) / 6.0) % (TU // 6)
    hsh = ((bx.astype(np.int64) * 73856093) ^ (row.astype(np.int64) * 19349663)) & 0xFFFF
    bid = np.array(BRICKS)[hsh % len(BRICKS)]
    mort = ((V % 3.0) < 0.55) | (((U + off) % 6.0) < 0.55)
    ids = np.where(mort, MORTAR, bid)
    ids = np.where(V > WH - 1.8, np.where(V > WH - 0.6, COPING2, COPING), ids)
    service_u = U % 128
    vent = (service_u > 92) & (service_u < 108) & (V > 6) & (V < 17)
    trim = vent & ((service_u < 92.6) | (service_u > 107.4) | (V < 6.5) | (V > 16.5))
    slats = vent & (((V * 1.4) % 1) < 0.28)
    ids = np.where(vent, np.where(trim | slats, VENT_EDGE, VENT), ids)
    conduit = (np.abs(service_u - 89) < 0.4) & (V < 30)
    ids = np.where(conduit, PIPE, ids)
    clay = ((np.floor(U * 3).astype(np.int64) * 31) ^ (np.floor(V * 3).astype(np.int64) * 73)) % 23
    relief = 0.90 + clay / 180
    relief = np.where((V % 3) < 0.7, relief * 0.68, relief)
    relief = np.where((V % 3) > 2.65, relief * 1.16, relief)
    damp = (V < 4.5 + (hsh % 11) * 0.3) & (((U + off) % 6) < 2.1)
    relief = np.where(damp, relief * 0.65, relief)
    relief = np.where(vent | conduit, 1.0, relief)
    return ids.astype(np.int64), relief.astype(np.float32)


# ------------------------------------------------------------------ street sprites
CAT_A = [".X.X..........",
         ".XXX........T.",
         "XEXX.........T",
         "XXXX........T.",
         ".XSXSXSXSXXXT.",
         "..XXXXXXXXXX..",
         "..X.X....X.X..",
         ".X...X..X...X."]
CAT_B = CAT_A[:6] + ["...XX....XX...", "...X.X...X.X.."]
CAT_COL = {"X": (196, 118, 52), "S": (140, 74, 30), "T": (180, 104, 44), "E": (190, 255, 90)}
PIGEON = {
    "stand": ["HH...", "NBBBT", ".BBB.", "..l.."],
    "peck": [".....", "NBBBT", "HBBB.", "..l.."],
    "fly1": ["W...W", ".WBW.", "..H.."],
    "fly2": [".....", "WWBWW", "..H.."],
}
PIGEON_COL = {"H": (96, 96, 116), "N": (80, 140, 125), "B": (150, 150, 166), "T": (72, 72, 88),
              "l": (210, 90, 90), "W": (176, 176, 192)}
SKATER = ["....HHH.....",
          "...HHHHH....",
          "...HHSSS....",
          "...HHSES....",
          "....HHS.....",
          "...HHHHH....",
          "..HHHPPHH...",
          ".HH.HPHHHH..",
          "SH..HHHH.HS.",
          "....HHHH...S",
          "....HHHH....",
          "....JJJJ....",
          "...JJJ.JJ...",
          "...JJ...JJ..",
          "..JJ.....JJ.",
          "..JJ.....JJ.",
          ".KKK....KKK.",
          "BBBBBBBBBBBB",
          ".WW......WW."]
SKATER_COL = {"H": (52, 52, 66), "P": (255, 15, 123), "S": (200, 150, 116), "E": (40, 30, 30),
              "J": (44, 58, 96), "K": (226, 226, 226), "B": (150, 84, 44), "W": (240, 220, 90)}
CAM_HEAD = ["GGGGGL.", "GGGGGLL", "DDDDDL.", ".A....."]
CAM_COL = {"G": (178, 180, 190), "L": (40, 44, 56), "D": (110, 112, 124), "A": (70, 72, 84)}


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
        self.A = a.astype(np.float32)
        self.Bv = (-(np.arange(self.ph) - self.cy) / self.f)[:, None].astype(np.float32)
        self.rowsP = np.arange(self.ph, dtype=np.float32)[:, None]
        self.canvas = np.zeros((CH, CW), np.int16)
        self.wall_ids, self.wall_rel = bake_wall()
        self.pieces = []
        self.posters = []
        self.stickers = []          # pending slaps
        self.next_u = 30.0
        # lettering pieces alternate with the bitmap pieces; DEDSEC opens the wall
        art = ["skull", "crown", "wrench", "arrows"]
        self.rng.shuffle(art)
        words = ["hack", "resist"]
        self.rng.shuffle(words)
        self.kinds = ["dedsec", art[0], words[0], art[1], words[1], art[2], "dedsec", art[3]]
        self.kind_i = 0
        self.spray = []
        self.make_skyline()
        self.pal = []
        self.ncols_pal = 0
        self.palette()
        # street life
        self.cat = None
        self.next_cat = self.last + self.rng.uniform(3, 8)
        self.flocks = []
        self.rider = None
        self.next_rider = self.last + self.rng.uniform(4, 9)
        self.cams = []
        self.next_cam_u = 70.0
        self.cam_status = ("ctOS CAM: ONLINE", (255, 60, 60))
        self.occ = None
        self.pud_rows = None
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
        c0 = int(p.u0 * R) - 20
        cols = np.arange(c0, c0 + p.w + 60) % CW
        self.canvas[:, cols] = 0
        self.pieces.append(p)
        end = p.u0 + p.width_units
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

    def write_cells(self, p, ys, xs, ids):
        if ys.size == 0:
            return
        cv = p.v0 + ys
        cu = (int(p.u0 * R) + xs) % CW
        ok = (cv >= 0) & (cv < CH)
        self.canvas[cv[ok], cu[ok]] = ids if np.isscalar(ids) else ids[ok]

    def advance_piece(self, p, dt, now):
        lay = p.layers[p.li]
        lay.p = min(1.0, lay.p + dt / lay.dur)
        j = lay.n if lay.p >= 1.0 else int(np.searchsorted(lay.o, lay.p * (lay.o[-1] if lay.n else 1)))
        if j > lay.i:
            sl = slice(lay.i, j)
            self.write_cells(p, lay.ys[sl], lay.xs[sl], lay.cid if lay.cid is not None else lay.ids[sl])
            lay.i = j
        if lay.p >= 1.0:
            if p.li == p.drip_after and p.drip_mask is not None:
                self.make_drips(p)
            p.li += 1
            if p.li >= len(p.layers):
                p.state = "done"
                p.done_at = now

    def make_drips(self, p):
        ys, xs = np.nonzero(p.drip_mask)
        if ys.size == 0:
            return
        sel = np.random.choice(ys.size, min(ys.size, max(3, ys.size // 9)), replace=False)
        for i in sel:
            y, x = ys[i], xs[i]
            ids = p.drip_ids
            cid = int(ids) if np.isscalar(ids) or getattr(ids, "ndim", 0) == 0 else int(ids[y, x])
            p.drips.append([x, y + 1, 0.0, self.rng.uniform(3, 14), self.rng.uniform(2, 6), cid])

    def step_drips(self, p, dt):
        for d in p.drips:
            if d[2] >= d[3]:
                continue
            old = int(d[2])
            d[2] = min(d[3], d[2] + d[4] * dt)
            d[4] *= 0.995
            for k in range(old, int(d[2]) + 1):
                cv = p.v0 + d[1] + k
                if 0 <= cv < CH:
                    self.canvas[cv, (int(p.u0 * R) + d[0]) % CW] = d[5]
                    if k == int(d[3]) and cv + 1 < CH:   # the bead at the end of the run
                        self.canvas[cv + 1, (int(p.u0 * R) + d[0]) % CW] = d[5]

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
        ph, w = self.ph, self.w
        rowsP = self.rowsP
        v = HCAM + B * tw[None, :]                      # (ph, w)
        r_top = self.cy - self.f * (WH - HCAM) / tw     # wall top row per column
        r_bot = self.cy + self.f * HCAM / tw            # wall bottom row per column
        s1 = int(min(ph, max(0, math.ceil(r_top.max()) + 1)))
        g0 = int(min(ph, max(0, math.floor(r_bot.min()))))
        wall = (v >= 0) & (v < WH)
        sky = v >= WH
        ground = v < 0
        # wall: baked bricks + paint canvas
        tu = (np.floor(u * TR).astype(np.int64)) % TW
        tv = np.clip((TH - 1 - np.floor(v * TR)).astype(np.int64), 0, TH - 1)
        ids = self.wall_ids[tv, tu[None, :]]
        rel = self.wall_rel[tv, tu[None, :]]
        cu = (np.floor(u * R).astype(np.int64)) % CW
        cv = np.clip((CH - 1 - np.floor(v * R)).astype(np.int64), 0, CH - 1)
        pv = self.canvas[cv, cu[None, :]]
        painted = wall & (pv > 0) & (v < WH - 1.8)
        ids = np.where(painted, pv, ids)
        uu = None
        # posters
        for po in self.posters:
            if po.u0 > u[-1] + 5 or po.u0 + po.wu < u[0] - 5:
                continue
            if uu is None:
                uu = np.broadcast_to(u[None, :], v.shape)
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
                flap = (inside & (d <= c) & ((lx + (c - d)) < 1) & ((ly + (c - d)) < 1) & (d >= 2 * c - 2))
                ids = np.where(flap, np.where((c - d) < 0.06, PAPER_SHADE, PAPER_BACK), ids)
            rel = np.where(inside, 1.0, rel)
        # lamp light on the wall
        li = np.round((u - LAMP_SP / 2) / LAMP_SP)
        lxp = li * LAMP_SP + LAMP_SP / 2
        uk, inv = np.unique(li, return_inverse=True)
        inten = np.array([self.lamp_level(int(k), now, beat) for k in uk], np.float32)[inv]
        du = (u - lxp)[None, :]
        dv = LAMP_H - v
        sig = 7 + np.maximum(dv, 0) * 0.85
        I = 0.18 + inten[None, :] * np.exp(-(du * du) / (2 * sig * sig)) * np.exp(-np.maximum(-dv, 0) / 3.5) * 1.05
        I = np.where(painted, I + 0.22, I * rel)
        # ground (only rows that can contain it)
        if g0 < ph:
            Bg = B[g0:]
            with np.errstate(divide="ignore", invalid="ignore"):
                tg = np.where(Bg < -1e-4, HCAM / -Bg, 1e9).astype(np.float32)
            gx = self.camx + tg * dxw[None, :]
            gz = tg * dzw[None, :]
            side = gz > ZW - 13
            curb = (gz > ZW - 14) & ~side
            gids = np.where(side, np.where(((gx % 8) < 0.35) | ((gz % 8) < 0.35), JOINT, SIDEWALK),
                            np.where(curb, CURB, np.where((np.abs(gz - (ZW - 26)) < 0.35) & ((gx % 12) < 6), LANE, ROAD)))
            gsel = ground[g0:]
            ids[g0:] = np.where(gsel, gids, ids[g0:])
            gd2 = (gx - lxp[None, :]) ** 2 + (gz - LAMP_Z) ** 2 * 1.4
            Ig = 0.16 + inten[None, :] * np.exp(-gd2 / 260)
            I[g0:] = np.where(gsel, Ig, I[g0:])
            # puddles: hashed blobs on the road and along the curb
            cell = np.floor(gx / 38.0).astype(np.int64)
            hh = (cell * 2654435761) & 0xFFFF
            pcx = cell * 38.0 + 14 + (hh % 11)
            pz = ZW - 17 - ((hh >> 4) % 11)
            pa = 6.0 + (hh >> 8) % 7
            pb = 2.6 + ((hh >> 3) % 4) * 0.7
            dd = ((gx - pcx) / pa) ** 2 + ((gz - pz) / pb) ** 2 + 0.18 * np.sin(gx * 0.9 + gz * 1.7)
            pud = gsel & (hh % 3 != 0) & (dd < 1.0) & (gz < ZW - 1)
            self.pud = (g0, pud)
        else:
            self.pud = None
        # sky + skyline (only rows that can contain it)
        if s1 > 0:
            ang = ((self.yaw + np.arctan(A)) * 400 + self.camx * 0.6).astype(np.int64) % self.sky_h.size
            hgt = self.sky_h[ang]
            rs = rowsP[:s1]
            skys = sky[:s1]
            skyl = skys & (rs > (r_top - hgt * 0.5)[None, :])
            sk_band = np.clip(np.arange(s1) * 6 // max(1, ph // 2), 0, 5)
            sids = np.broadcast_to(np.array(SKY)[sk_band][:, None], skys.shape)
            ri = np.arange(s1)[:, None]
            sids = np.where(skyl, np.where(((ri * 5 + ang[None, :] * 3) % 17 == 0), SKYWIN, SKYLINE), sids)
            star = skys & ~skyl & (((ri * 131 + ang[None, :] * 71) % 97) == 0)
            sids = np.where(star, STAR, sids)
            ids[:s1] = np.where(skys, sids, ids[:s1])
        lvl = np.clip((I * (L - 1)).astype(np.int64), 0, L - 1)
        # foreground: lamp posts, poles, fence
        ids, lvl, occ = self.foreground(ids, lvl, dxw, dzw, B)
        idx = ids * L + lvl
        # puddle reflections: mirror about the wall foot, darkened, with a slow shimmer
        if self.pud is not None:
            g0, pud = self.pud
            pud = pud & (occ[g0:] > 1e8)
            ys, xs = np.nonzero(pud)
            if ys.size:
                ry = ys + g0
                src = (2 * r_bot[xs] - ry + np.sin(ry * 0.9 + now * 2.6) * 0.8).astype(np.int64)
                src = np.clip(src, 0, ph - 1)
                rv = idx[src, xs]
                lv = rv % L
                rv = rv - lv + np.maximum(0, lv - 1)
                edge = ~pud[np.clip(ys - 1, 0, pud.shape[0] - 1), xs]
                rv = np.where(edge, CURB * L + 4, rv)
                idx[ry, xs] = rv
            self.pud_mask = (g0, pud)
        else:
            self.pud_mask = None
        self.occ = occ
        self.r_bot = r_bot
        return idx, u

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

    def light_at(self, u):
        k = round((u - LAMP_SP / 2) / LAMP_SP)
        lx = k * LAMP_SP + LAMP_SP / 2
        inten = self.lamp_level(int(k), self.last, DATA.beat)
        return 0.42 + 0.7 * inten * math.exp(-((u - lx) ** 2) / 300)

    def foreground(self, ids, lvl, dxw, dzw, B):
        rowsP = self.rowsP
        occ = np.full(ids.shape, 1e9, np.float32)
        # lamp posts (just in front of the wall): per column test + row range
        t_l = LAMP_Z / dzw
        xl = self.camx + t_l * dxw
        k = np.round((xl - LAMP_SP / 2) / LAMP_SP)
        lpx = k * LAMP_SP + LAMP_SP / 2
        ry0 = self.cy - self.f * (LAMP_H - HCAM) / t_l
        ry1 = self.cy - self.f * (-0.2 - HCAM) / t_l
        ryarm = (self.f * 0.5 / t_l)
        pc = np.nonzero((xl - lpx > -0.45) & (xl - lpx < 4.8))[0]
        if pc.size:
            rp = rowsP
            d = (xl - lpx)[pc]
            post = (np.abs(d) < 0.45)[None, :] & (rp >= ry0[pc][None, :]) & (rp <= ry1[pc][None, :])
            arm = (np.abs(d - 2.2) < 2.6)[None, :] & (np.abs(rp - ry0[pc][None, :]) <= ryarm[pc][None, :])
            m = post | arm
            ids[:, pc] = np.where(m, POST, ids[:, pc])
            lvl[:, pc] = np.where(m, 2, lvl[:, pc])
            so = occ[:, pc]
            so[m] = LAMP_Z
            occ[:, pc] = so
        # near poles + chain fence, evaluated only on the columns that hold them
        t_f = FG_Z / dzw
        xf = self.camx * 1.0 + t_f * dxw
        seg = np.floor(xf / 46.0)
        lx = xf - seg * 46.0
        has_fence = ((seg.astype(np.int64) * 7) % 5 < 2)
        cols = np.nonzero((lx < 0.5) | (has_fence & (lx > 0.5) & (lx < 30)))[0]
        if cols.size:
            vf = HCAM + B * t_f[cols][None, :]
            xc = xf[cols][None, :]
            pole = (lx[cols] < 0.5)[None, :] & (vf >= -1) & (vf < 26)
            fence = (lx[cols] >= 0.5)[None, :] & (vf >= -1) & (vf < 13) & \
                ((((xc + vf) % 1.6) < 0.16) | (((xc - vf) % 1.6) < 0.16) | (np.abs(vf - 13) < 0.2))
            mf = pole | fence
            sub_i, sub_l, sub_o = ids[:, cols], lvl[:, cols], occ[:, cols]
            ids[:, cols] = np.where(mf, np.where(pole, POST, FENCE), sub_i)
            lvl[:, cols] = np.where(mf, np.where(pole, 1, 3), sub_l)
            sub_o[mf] = FG_Z
            occ[:, cols] = sub_o
        return ids, lvl, occ

    # ------------------------------------------------------------ main
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        beat = DATA.beat
        glitch = self.glitch.active(now)
        self.camx += 6.0 * dt
        self.yaw = 0.22 + 0.05 * math.sin(now * 0.11)

        while self.next_u < self.camx + 230:
            self.spawn_slot()
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
        if self.rng.random() < dt * 0.35:
            self.slap_sticker(now)
        self.palette()

        idx, ucols = self.raster(now, beat)
        heads = self.draw_lamps_prep(ucols)
        if heads:
            for hx, hy, inten in heads:
                if inten < 0.4:
                    continue
                r0, r1 = max(0, hy + 2), min(self.ph, int(hy + self.ph * 0.75))
                if r1 <= r0:
                    continue
                spread = (r1 - hy) * 0.42 + 1
                c0, c1 = max(0, int(hx - spread)), min(self.w, int(hx + spread) + 1)
                if c1 <= c0:
                    continue
                rows = np.arange(r0, r1)[:, None]
                xs = np.arange(c0, c1)[None, :]
                sub = idx[r0:r1, c0:c1]
                cone = (np.abs(xs - hx) < (rows - hy) * 0.42 + 0.5) & ((sub % L) < L - 1)
                sub += cone
        pal = self.pal
        g = pal.__getitem__
        Lr = idx.tolist()
        for y in range(self.h):
            s.pt[y] = list(map(g, Lr[2 * y]))
            s.pb[y] = list(map(g, Lr[2 * y + 1]))
        self.occ_item = self.occ.item
        pm = getattr(self, "pud_mask", None)
        for hx, hy, inten in heads:
            col = blend((60, 50, 40), (255, 236, 200), inten)
            s.pixel_rect(hx - 2, hy - 1, 6, 2, col)
            s.pixel_rect(hx - 1, hy - 2, 4, 1, (30, 30, 40))
            # the lamp glints in nearby puddles
            if pm is not None and 0 <= hx < self.w:
                g0, pud = pm
                ry = int(2 * self.r_bot[hx] - hy) - g0
                for dx in (-1, 0, 1, 2):
                    for dy in (0, 1, 2):
                        yy, xx = ry + dy, hx + dx
                        if 0 <= yy < pud.shape[0] and 0 <= xx < self.w and pud[yy, xx]:
                            s.pixel(xx, yy + g0, blend(col, (120, 140, 200), 0.25 + dy * 0.2))
        self.draw_stickers(s, now, dt)
        self.street(s, now, dt)
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

    # ------------------------------------------------------------ street life
    def spx(self, s, x, py, col, z):
        x, py = int(x), int(py)
        if 0 <= x < self.w and 0 <= py < self.ph and self.occ_item(py, x) > z:
            if py & 1:
                s.pb[py >> 1][x] = col
            else:
                s.pt[py >> 1][x] = col

    def sprite(self, s, art, cmap, x0, y0, z, light, sc=1, flip=False, emissive="E"):
        w = len(art[0])
        for j, row in enumerate(art):
            for i, ch in enumerate(row):
                c = cmap.get(ch)
                if c is None:
                    continue
                if ch not in emissive:
                    c = (min(255, int(c[0] * light)), min(255, int(c[1] * light)), min(255, int(c[2] * light)))
                ii = (w - 1 - i) if flip else i
                for a in range(sc):
                    for b in range(sc):
                        self.spx(s, x0 + ii * sc + a, y0 + j * sc + b, c, z)

    def scale_at(self, z, unit):
        return max(1, int(round(self.f / z * unit)))

    def street(self, s, now, dt):
        self.step_cams(s, now, dt)
        self.step_flocks(s, now, dt)
        self.step_cat(s, now, dt)
        self.step_rider(s, now, dt)

    # -- the ctOS camera pole that DedSec takes over
    def step_cams(self, s, now, dt):
        while self.next_cam_u < self.camx + 200:
            k = math.floor(self.next_cam_u / LAMP_SP)
            u = k * LAMP_SP + LAMP_SP / 2 + 26
            self.cams.append({"u": u, "state": "idle", "t": 0.0, "id": self.rng.randint(10, 99)})
            self.next_cam_u = u + self.rng.uniform(150, 230)
        self.cams = [c for c in self.cams if c["u"] > self.camx - 60]
        z = ZW - 12.5
        for c in self.cams:
            base = self.wall_to_screen(c["u"], 0, z)
            top = self.wall_to_screen(c["u"], 27, z)
            if not base or not top or not (-20 < base[0] < self.w + 20):
                continue
            if c["state"] == "idle" and self.w * 0.3 < top[0] < self.w * 0.7:
                c["state"], c["t"] = "hack", now
            if c["state"] == "hack" and now - c["t"] > 3.2:
                c["state"], c["t"] = "owned", now
            lt = self.light_at(c["u"])
            pc = (int(40 * lt), int(42 * lt), int(52 * lt))
            pw = self.scale_at(top[2], 0.5)
            x = int(base[0])
            for py in range(int(top[1]), int(base[1]) + 1):
                for a in range(pw):
                    self.spx(s, x + a, py, pc, z)
            sc = self.scale_at(top[2], 0.8)
            art = CAM_HEAD
            hx, hy = x + pw - sc, int(top[1]) - 2 * sc
            if c["state"] == "owned":       # hacked cameras droop toward the pavement
                art = [CAM_HEAD[1], CAM_HEAD[0], CAM_HEAD[2], CAM_HEAD[3]]
                hy += sc
            self.sprite(s, art, CAM_COL, hx, hy, z, lt, sc)
            if c["state"] == "owned":
                led = GREEN
            elif c["state"] == "hack":
                led = (255, 40, 40) if int(now * 8) % 2 else (255, 200, 40)
            else:
                led = (255, 40, 40) if int(now * 2) % 3 else (90, 10, 10)
            for a in range(sc):
                for b in range(sc):
                    self.spx(s, hx + a, hy + sc + b, led, 0)
            # glow halo
            if c["state"] != "idle" or int(now * 2) % 3:
                gl = blend(led, BLACK, 0.55)
                for dx, dy in ((-1, 0), (sc, 0), (0, -1), (0, sc)):
                    self.spx(s, hx + dx, hy + sc + dy, gl, 0)
            if c["state"] == "hack":
                self.hack_fx(s, now, c, hx, hy, sc)
                pct = min(99, int((now - c["t"]) / 3.2 * 100))
                self.cam_status = ("ctOS CAM %02d: BREACH %2d%%" % (c["id"], pct), YELLOW)
            elif c["state"] == "owned":
                age = now - c["t"]
                if age < 2.5:
                    self.label(s, hx // 1 - 3, (hy // 2) - 2, "OWNED", GREEN)
                self.cam_status = ("ctOS CAM %02d: OURS" % c["id"], GREEN)
            else:
                self.cam_status = ("ctOS CAM %02d: WATCHING" % c["id"], (255, 70, 70))

    def hack_fx(self, s, now, c, hx, hy, sc):
        age = now - c["t"]
        # targeting brackets snap in around the camera head
        k = 1 - ease_out(min(1, age / 0.4))
        pad_ = int(3 + k * 10)
        x0, y0 = hx - pad_, hy - pad_
        x1, y1 = hx + 7 * sc + pad_, hy + 4 * sc + pad_
        col = blend(CYAN, WHITE, k)
        for d in range(4):
            for (ax, ay, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                self.spx(s, ax + d * sx, ay, col, 0)
                self.spx(s, ax, ay + d * sy, col, 0)
        # data packets ride a link from the bottom-left (our phone) to the camera
        sx_, sy_ = 6, self.ph - 4
        tx, ty = hx + 3 * sc, hy + sc
        for i in range(14):
            f = (i / 14 + age * 0.9) % 1.0
            px = sx_ + (tx - sx_) * f
            py = sy_ + (ty - sy_) * f - math.sin(f * math.pi) * self.ph * 0.18
            self.spx(s, px, py, blend(CYAN, PINK, f) if i % 3 else WHITE, 0)
        pct = min(99, int(age / 3.2 * 100))
        self.label(s, x0, (y1 >> 1) + 1, "HACK %2d%%" % pct, CYAN)

    def label(self, s, x, y, txt, col):
        if not 0 <= y < s.h:
            return
        for i, ch in enumerate(txt):
            xx = x + i
            if 0 <= xx < s.w:
                s.put(xx, y, ch, col)
                s.set_bg(xx, y, blend(s.pt[y][xx] or (10, 6, 20), BLACK, 0.55))

    # -- pigeons pecking on the pavement; they scatter when something passes
    def step_flocks(self, s, now, dt):
        if len(self.flocks) < 2 and self.rng.random() < dt * 0.3:
            u = self.camx + self.rng.uniform(60, 110)
            birds = []
            for _ in range(self.rng.randint(3, 6)):
                birds.append({"u": u + self.rng.uniform(-5, 5), "z": ZW - self.rng.uniform(3, 9), "v": 0.0,
                              "vu": 0.0, "vv": 0.0, "ph": self.rng.uniform(0, 6), "fly": False,
                              "dir": self.rng.choice((-1, 1))})
            self.flocks.append(birds)
        threats = []
        if self.cat:
            threats.append(self.cat["u"])
        if self.rider:
            threats.append(self.rider["u"])
        keep = []
        for birds in self.flocks:
            alive = []
            for b in birds:
                if not b["fly"] and (any(abs(t - b["u"]) < 9 for t in threats) or self.rng.random() < dt * 0.01):
                    b["fly"] = True
                    b["vu"] = self.rng.uniform(4, 10) * self.rng.choice((-1, 1))
                    b["vv"] = self.rng.uniform(7, 11)
                    b["dir"] = 1 if b["vu"] > 0 else -1
                if b["fly"]:
                    b["u"] += b["vu"] * dt
                    b["v"] += b["vv"] * dt
                    b["z"] -= 3 * dt
                    if b["v"] > 60:
                        continue
                elif self.rng.random() < dt * 0.5:
                    b["u"] += b["dir"] * 0.4
                q = self.wall_to_screen(b["u"], b["v"], b["z"])
                if q is None or q[0] < -30:
                    continue
                if q[0] < self.w + 10:
                    if b["fly"]:
                        art = PIGEON["fly1" if int(now * 10 + b["ph"]) % 2 else "fly2"]
                    else:
                        art = PIGEON["peck" if math.sin(now * 3.1 + b["ph"]) > 0.55 else "stand"]
                    sc = self.scale_at(q[2], 0.42)
                    self.sprite(s, art, PIGEON_COL, int(q[0]) - 2 * sc, int(q[1]) - len(art) * sc, b["z"],
                                self.light_at(b["u"]), sc, flip=b["dir"] > 0)
                alive.append(b)
            if alive:
                keep.append(alive)
        self.flocks = keep

    # -- a ginger cat strolling along the wall
    def step_cat(self, s, now, dt):
        if self.cat is None:
            if now > self.next_cat:
                self.cat = {"u": self.camx + 95, "z": ZW - 3.5, "pause": None}
            return
        c = self.cat
        if c["pause"] is None and self.rng.random() < dt * 0.06:
            c["pause"] = now
        walking = c["pause"] is None or now - c["pause"] > 2.2
        if c["pause"] is not None and now - c["pause"] > 2.2:
            c["pause"] = -1e9 if c["pause"] > 0 else c["pause"]
        if walking:
            c["u"] -= 3.2 * dt
        q = self.wall_to_screen(c["u"], 0, c["z"])
        if q is None or q[0] < -40:
            self.cat = None
            self.next_cat = now + self.rng.uniform(14, 26)
            return
        sc = self.scale_at(q[2], 0.42)
        art = (CAT_A if int(now * 6) % 2 else CAT_B) if walking else CAT_A[:6] + ["..XX.....XX...", "..XX.....XX..."]
        self.sprite(s, art, CAT_COL, int(q[0]), int(q[1]) - len(art) * sc, c["z"], self.light_at(c["u"]), sc)

    # -- a skater or a cyclist rolling by on the road, close to the camera
    def step_rider(self, s, now, dt):
        if self.rider is None:
            if now > self.next_rider:
                kind = self.rng.choice(("skate", "bike"))
                self.rider = {"kind": kind, "u": self.camx - 40, "z": self.rng.uniform(31, 37),
                              "spd": self.rng.uniform(17, 23) if kind == "skate" else self.rng.uniform(22, 28)}
            return
        r = self.rider
        r["u"] += r["spd"] * dt
        q = self.wall_to_screen(r["u"], 0, r["z"])
        if q is None or q[0] > self.w + 60:
            self.rider = None
            self.next_rider = now + self.rng.uniform(9, 18)
            return
        lt = max(0.75, self.light_at(r["u"]))
        if r["kind"] == "skate":
            sc = self.scale_at(q[2], 0.45)
            bob = int(math.sin(now * 5) * 0.6 + 0.5)
            art = SKATER
            if int(now * 8) % 2:
                art = SKATER[:-1] + [".W.W....W.W."]
            self.sprite(s, art, SKATER_COL, int(q[0]) - 6 * sc, int(q[1]) - len(art) * sc - bob, r["z"], lt, sc)
        else:
            self.draw_bike(s, now, r, lt)

    def draw_bike(self, s, now, r, lt):
        u, z = r["u"], r["z"]

        def P(du, dv):
            q = self.wall_to_screen(u + du, dv, z)
            return (q[0], q[1]) if q else (0, 0)

        def ln(a, b, col, thick=1):
            for x, y in line_points(int(a[0]), int(a[1]), int(b[0]), int(b[1])):
                for t in range(thick):
                    self.spx(s, x + t, y, col, z)

        sh = lambda c: (min(255, int(c[0] * lt)), min(255, int(c[1] * lt)), min(255, int(c[2] * lt)))
        frame, tyre, body, skin = sh((0, 190, 220)), sh((30, 30, 36)), sh((60, 50, 70)), sh((200, 150, 116))
        rad = 2.3
        q = self.wall_to_screen(u, 0, z)
        rp = rad * self.f / q[2]
        rot = u / rad
        for hub in (-3.3, 3.3):
            cx, cy = P(hub, rad)
            n = max(16, int(rp * 7))
            for i in range(n):
                a = i / n * math.tau
                self.spx(s, cx + math.cos(a) * rp, cy + math.sin(a) * rp, tyre, z)
            for k in range(3):
                a = rot + k * math.pi / 3
                ln((cx - math.cos(a) * rp, cy + math.sin(a) * rp), (cx + math.cos(a) * rp, cy - math.sin(a) * rp),
                   sh((120, 120, 130)))
        bb, rear, front = P(0, 2.0), P(-3.3, rad), P(3.3, rad)
        seat, head = P(-1.1, 5.6), P(2.5, 5.9)
        bar = P(2.3, 7.0)
        for a, b in ((rear, bb), (bb, seat), (seat, head), (bb, head), (rear, seat), (head, front), (head, bar)):
            ln(a, b, frame)
        # rider
        hip, sho = P(-1.0, 6.6), P(1.0, 10.6)
        hq = P(1.5, 12.0)
        thick = max(2, int(rp * 0.55))
        ln(hip, sho, body, thick)
        ln(sho, bar, body)
        hr = max(1.0, rp * 0.42)
        s_ = self.f / q[2]
        for dy in range(-int(hr) - 1, int(hr) + 2):
            for dx in range(-int(hr) - 1, int(hr) + 2):
                if dx * dx + dy * dy <= hr * hr + 0.5:
                    self.spx(s, hq[0] + dx, hq[1] + dy, body if dx < 0 or dy < -hr * 0.3 else skin, z)
        self.spx(s, hq[0] + hr * 0.4, hq[1] - hr - 1, sh(PINK), z)
        ph_ = now * 7
        for side in (0, math.pi):
            a = ph_ + side
            pedal = (bb[0] + math.cos(a) * 1.1 * s_, bb[1] + math.sin(a) * 1.1 * s_)
            knee = ((hip[0] + pedal[0]) / 2 + 1.6 * s_, (hip[1] + pedal[1]) / 2 - 0.6 * s_)
            col = body if side == 0 else blend(body, BLACK, 0.4)
            ln(hip, knee, col, 2 if thick > 2 else 1)
            ln(knee, pedal, col)
        self.spx(s, front[0] + rp, front[1] - rp * 0.6, (255, 250, 200), 0)   # headlight
        for k in range(1, 6):
            self.spx(s, front[0] + rp + k * 2, front[1] - rp * 0.6, blend((255, 250, 200), BLACK, k / 6), 0)

    # ------------------------------------------------------------ sprays & cans
    def draw_can(self, s, p, now, dt):
        if p.li >= len(p.layers):
            return
        lay = p.layers[p.li]
        pos = lay.can_pos()
        col = COLS[lay.cid][0] if lay.cid is not None else p.color
        if pos is None:
            # stencil: card + random fog
            q0 = self.wall_to_screen(p.u0 - 1, (CH - 1 - p.v0) / R + 1)
            q1 = self.wall_to_screen(p.u0 + p.width_units + 1, (CH - 1 - p.v0 - p.h) / R - 1)
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
        if lay.ids is not None:
            i = min(lay.n - 1, lay.i)
            col = COLS[int(lay.ids[i])][0]
        u = p.u0 + cx / R
        v = (CH - 1 - p.v0 - cy) / R
        q = self.wall_to_screen(u, v)
        if not q:
            return
        x, y = q[0], q[1]
        for _ in range(7):
            a = random.uniform(0, math.tau)
            sp = random.uniform(4, 22)
            self.spray.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 0.0, random.uniform(0.15, 0.45),
                               blend(col, WHITE, random.uniform(0, 0.3))])
        # overspray specks just outside the piece
        if random.random() < 0.35:
            ox = int(cx + random.gauss(0, 5))
            oy = int(cy + random.gauss(0, 5))
            cvv = p.v0 + oy
            if 0 <= cvv < CH and 0 <= oy < p.h and 0 <= ox < p.w and not p.fillmask[oy, ox]:
                cc = paint(col)
                self.canvas[cvv, (int(p.u0 * R) + ox) % CW] = cc
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
            k = 1 - sp[4] / sp[5] * 0.8
            c = sp[6]
            s.pixel(int(sp[0]), int(sp[1]), (int(c[0] * k), int(c[1] * k), int(c[2] * k)))
            alive.append(sp)
        self.spray = alive[-400:]

    def slap_sticker(self, now):
        art, cmap = random.choice(STICKERS)
        u = self.camx + random.uniform(10, 110)
        v = random.uniform(5, WH - 8)
        # never slap over a piece: the lettering has to stay readable
        c0, r0 = int(u * R), CH - 1 - int(v * R)
        cols = np.arange(c0 - 2, c0 + len(art[0]) + 2) % CW
        if self.canvas[max(0, r0 - 2):r0 + len(art) + 2][:, cols].any():
            return
        for p in self.pieces:
            if p.u0 - 4 < u < p.u0 + p.width_units + 2:
                return
        self.stickers.append({"art": art, "cmap": cmap, "u": u, "v": v, "t": now})

    def draw_stickers(self, s, now, dt):
        keep = []
        for st in self.stickers:
            age = now - st["t"]
            art = st["art"]
            hh, ww = len(art), len(art[0])
            if age >= 0.28:
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
        cam, col = self.cam_status
        cam += " ●" if int(now * 2) % 2 else "  "
        cx = s.w - len(cam) - 2
        for k, ch in enumerate(cam):
            s.put(cx + k, 1, ch, col)
            s.set_bg(cx + k, 1, (10, 4, 18))
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

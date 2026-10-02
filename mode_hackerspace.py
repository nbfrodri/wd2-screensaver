"""HACKERSPACE: a camera tour through the DedSec hideout.

The room shell (brick, cinderblock, concrete, rug, posters, the neon sign with
its bloom and the skyline window) is ray cast per pixel with numpy and lit by a
handful of coloured point lights that pulse with the music. Furniture is solid
3D boxes lit by the same lights; small props and actors are pixel-art sprites
mapped onto planes in the scene.
"""

import math
import random
import time
from functools import lru_cache

import numpy as np

from engine3d import clip2d
from lib import (BLACK, CYAN, DIM_CYAN, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, blend, pulse)
from sysdata import DATA
from widgets import CUBE_E, CUBE_V, ICO_E, ICO_V, OCTA_E, OCTA_V, Particles, draw_wire, p_minimap, p_radar

NAME = "HACKERSPACE"

NEAR = 0.2
X0, X1, Z0, Z1, YC = -10.0, 10.0, -3.0, 13.0, 7.0     # room box (camera looks towards +z)

WOOD = (120, 78, 52)
DARKM = (46, 46, 58)
METAL = (92, 96, 116)
CARD = (190, 140, 84)
CARD_EDGE = (230, 180, 120)

# Local copies so this mode does not depend on other modes' internals.
FONT = {
    "D": ["█████ ", "██  ██", "██  ██", "██  ██", "█████ "],
    "E": ["██████", "██    ", "█████ ", "██    ", "██████"],
    "S": [" █████", "██    ", " ████ ", "    ██", "█████ "],
    "C": [" █████", "██    ", "██    ", "██    ", " █████"],
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
TV_NEWS = ["#DEDSEC trends worldwide for the 3rd day", "Blume stock drops 14% after ctOS outage",
           "Mysterious skull logo appears on every billboard in SF", "Police baffled by dancing traffic lights",
           "Tidis Bank ATMs dispense cat pictures", "Oakland goes dark for 7 minutes",
           "DedSec denies stealing every office stapler in SF", "Pizza delivery drones now 40% more punctual",
           "Blume: 'ctOS is totally fine, please stop asking'"]

PRINTS = [("SKULL KEYCHAIN", lambda u: 0.55 + 0.45 * math.sin(min(1, u * 1.2) * math.pi) if u < 0.85 else 0.25),
          ("J-BOT SPARE HEAD", lambda u: 0.9 if u < 0.7 else 0.5),
          ("DEDSEC TROPHY", lambda u: 0.8 - u * 0.5 if u < 0.6 else 0.45 + 0.4 * math.sin((u - 0.6) * 7.8)),
          ("TINY VASE", lambda u: 0.45 + 0.35 * math.sin(u * 5))]

# ---------------------------------------------------------------- lights
# position, colour, radius, base intensity, beat gain
LIGHTS = [
    ((1.6, 5.95, 12.55), (255, 40, 150), 3.6, 1.25, 0.55),     # 0 neon DEDSEC sign
    ((-5.3, 2.6, 11.2), (40, 200, 255), 2.8, 0.85, 0.25),      # 1 monitor wall
    ((4.3, 2.9, 12.2), (90, 110, 255), 2.8, 0.75, 0.15),       # 2 TV
    ((-8.75, 2.35, 11.7), (255, 165, 70), 2.0, 1.15, 0.0),     # 3 desk lamp
    ((-5.0, 6.1, 4.5), (255, 190, 120), 4.6, 0.45, 0.35),      # 4 string lights (left)
    ((4.5, 6.1, 8.5), (255, 170, 140), 4.6, 0.45, 0.35),       # 5 string lights (right)
    ((9.5, 4.2, 7.0), (100, 130, 230), 3.2, 0.55, 0.0),        # 6 window / moonlight
    ((8.9, 2.0, 10.9), (60, 255, 140), 1.5, 0.45, 0.3),        # 7 server rack LEDs
    ((-8.9, 1.9, 7.4), (255, 120, 40), 1.2, 0.35, 0.0),        # 8 3D printer hot end
]
AMBIENT = np.array([0.26, 0.23, 0.30], np.float32)

# camera tour: (x, y, z, yaw, pitch); one key every KEY_T seconds, looped
KEY_T = 11.0
KEYS = [
    (0.6, 3.5, 0.2, 0.02, 0.15, "CAM 01 // MAIN ROOM"),
    (-3.9, 2.75, 6.2, -0.06, 0.10, "CAM 02 // RIG"),
    (-4.3, 3.3, 5.2, -0.62, 0.16, "CAM 03 // WORKSHOP"),
    (-0.8, 1.75, 3.2, 0.05, 0.0, "CAM 04 // FLOOR"),
    (3.6, 3.0, 4.6, 0.58, 0.12, "CAM 05 // LOUNGE"),
    (2.2, 4.3, 1.4, 0.18, 0.24, "CAM 06 // OVERHEAD"),
]


# ---------------------------------------------------------------- pixel art
def art(rows, pal):
    """Char art -> (rgb float32 (h, w, 3), alpha bool (h, w))."""
    h, w = len(rows), max(len(r) for r in rows)
    rgb = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), bool)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = pal.get(ch)
            if c is not None:
                rgb[y, x] = c
                alpha[y, x] = True
    return rgb, alpha


def font_rows(word, on="#", off="."):
    rows = [""] * 5
    for ch in word:
        for i, line in enumerate(FONT[ch]):
            rows[i] += "".join(on if c != " " else off for c in line) + off
    return [r[:-1] for r in rows]


def dilate_rows(rows, ch="o"):
    h, w = len(rows), len(rows[0])
    out = []
    for r in range(-1, h + 1):
        line = ""
        for c in range(-1, w + 1):
            if 0 <= r < h and 0 <= c < w and rows[r][c] != ".":
                line += rows[r][c]
            elif any(0 <= r + dy < h and 0 <= c + dx < w and rows[r + dy][c + dx] != "."
                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                line += ch
            else:
                line += "."
        out.append(line)
    return out


POSTER_EYE = [
    "kkkkkkkkkkk",
    "kbbbbbbbbbk",
    "kbbbbybbbbk",
    "kbbbyyybbbk",
    "kbbyywyybbk",
    "kbyywkwyybk",
    "kyywkkkwyyk",
    "kbyywkwyybk",
    "kbbyywyybbk",
    "kbbbbbbbbbk",
    "kpppppppppk",
    "kp.pp.pp.pk",
    "kkkkkkkkkkk",
]
POSTER_BARS = ["kkkkkkkk", "kppppppk", "kppppppk", "kcccccck", "kcc..cck", "kyyyyyyk", "ky.yy.yk",
               "kppppppk", "kwwwwwwk", "kcccccck", "kcc.ccck", "kkkkkkkk"]

MASK = [
    "...h......h...",
    "..hkh....hkh..",
    "..hkkhhhhkkh..",
    ".hkkkkkkkkkkh.",
    ".kkkkkkkkkkkk.",
    "kk1111kk2222kk",
    "kk1111kk2222kk",
    "kk1111kk2222kk",
    "kk1111kk2222kk",
    ".kkkkkkkkkkkk.",
    ".kkkkkhhkkkkk.",
    "..kgkgkgkgkk..",
    "..kkkkkkkkkk..",
    "...hkkkkkkh...",
    ".....kkkk.....",
]
GLYPH = {
    "^": ["....", ".ee.", "e..e", "...."],
    "X": ["e..e", ".ee.", ".ee.", "e..e"],
    "o": [".ee.", "e..e", "e..e", ".ee."],
    "-": ["....", "eeee", "....", "...."],
    ">": ["e...", ".ee.", ".ee.", "e..."],
    "<": ["...e", ".ee.", ".ee.", "...e"],
    "v": ["e..e", "e..e", ".ee.", "...."],
    "#": ["eeee", "eeee", "eeee", "eeee"],
}
EYES = [("^", "^"), ("X", "X"), ("o", "o"), ("-", "-"), (">", "<"), ("v", "v"), ("o", "-")]

ROBOT = [
    "......r.......",
    "......n.......",
    "......n.......",
    "...wwwwwwww...",
    "..wwwwwwwwww..",
    "..wwEEwwEEww..",
    "..wwEEwwEEww..",
    "..wwwwwwwwww..",
    "...wwmmmmww...",
    "....gggggg....",
    ".oooooooooooo.",
    "aoooyyyyyyoooa",
    "aoooyppppyoooa",
    "a.oooooooooo.a",
    ".TtTtTtTtTtTt.",
    ".tTtTtTtTtTtT.",
]

CAT_WALK = [
    [
        "................",
        ".k.k..........k.",
        ".kkk.........k..",
        "kgkgk.......k...",
        "kkkkk......k....",
        ".kkkkkkkkkkk....",
        "..kkkkkkkkkk....",
        "..kkkkkkkkk.....",
        "..k.k.....k.k...",
        ".k...k...k...k..",
    ],
    [
        "................",
        ".k.k...........k",
        ".kkk..........k.",
        "kgkgk........k..",
        "kkkkk.......k...",
        ".kkkkkkkkkkkk...",
        "..kkkkkkkkkk....",
        "..kkkkkkkkk.....",
        "...kk.....kk....",
        "...kk.....kk....",
    ],
]
CAT_SIT = [
    "..........",
    ".k.k......",
    ".kkk......",
    "kgkgk.....",
    "kkkkk.....",
    ".kkkk.....",
    ".kkkkk....",
    ".kkkkkk...",
    ".kkkkkk..k",
    ".kkkkkkkk.",
]

PLANT = [
    ".....G......",
    "..G..Gg..G..",
    "..gG.gG.Gg..",
    "G..gGgGgG..G",
    "gG..gGGg..Gg",
    ".gGg.gG.gGg.",
    "..gGgGgGgG..",
    "Gg.gGgGgG.gG",
    ".gGg.gGg.gG.",
    "...gGgGgGg..",
    ".G..gGgGg..G",
    ".gG..sGs..Gg",
    "..gG.s.s.Gg.",
    "....s.s.s...",
    ".....sss....",
]

PIZZA = [
    "..cccccc..",
    ".cyyryyyc.",
    "cyryyyyryc",
    "cyyyyryyyc",
    "cyrc..yyyc",
    "cyyc..yryc",
    "cyyyyyyyyc",
    ".cyryyyyc.",
    "..cccccc..",
]


# ---------------------------------------------------------------- pixel-space 3D helpers

class Cam:
    def __init__(self, w, h, fov=0.85):
        self.w, self.h = w, h
        self.f = h * fov
        self.f2 = self.f * 2
        self.cx, self.cy = w / 2, h / 2
        self.pos = [0.0, 0.0, 0.0]
        self.yaw = self.pitch = 0.0
        self.setup()

    def setup(self):
        self.c, self.s = math.cos(self.yaw), math.sin(self.yaw)
        self.cp, self.sp = math.cos(self.pitch), math.sin(self.pitch)

    def view(self, p):
        x, y, z = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        x, z = x * self.c - z * self.s, x * self.s + z * self.c
        return x, y * self.cp + z * self.sp, -y * self.sp + z * self.cp

    def pp(self, v):
        return self.cx + v[0] / v[2] * self.f2, (self.cy - v[1] / v[2] * self.f) * 2

    def proj(self, p):
        v = self.view(p)
        if v[2] < NEAR:
            return None
        return self.cx + v[0] / v[2] * self.f2, (self.cy - v[1] / v[2] * self.f) * 2, v[2]

    def poly(self, pts):
        vs = [self.view(p) for p in pts]
        if all(v[2] >= NEAR for v in vs):
            return [self.pp(v) for v in vs]
        out = []
        for i in range(len(vs)):
            a, b = vs[i - 1], vs[i]
            ia, ib = a[2] >= NEAR, b[2] >= NEAR
            if ia != ib:
                t = (NEAR - a[2]) / (b[2] - a[2])
                out.append(self.pp((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR)))
            if ib:
                out.append(self.pp(b))
        return out if len(out) >= 3 else None

    def seg(self, a, b):
        va, vb = self.view(a), self.view(b)
        if va[2] < NEAR and vb[2] < NEAR:
            return None
        if va[2] < NEAR or vb[2] < NEAR:
            if va[2] < NEAR:
                va, vb = vb, va
            t = (va[2] - NEAR) / (va[2] - vb[2])
            vb = (va[0] + (vb[0] - va[0]) * t, va[1] + (vb[1] - va[1]) * t, NEAR)
        return self.pp(va), self.pp(vb)


@lru_cache(maxsize=32768)
def span(col, width):
    """Reusable slice sources; assigning a slice copies the entries."""
    return [col] * width


def fill(s, P, col):
    """Scan a convex polygon using precomputed edge slopes."""
    ys = [p[1] for p in P]
    y0, y1 = max(0, int(min(ys))), min(s.ph - 1, int(max(ys)))
    if y1 < y0:
        return
    xs = [p[0] for p in P]
    if int(max(xs) + 0.5) <= 0 or int(min(xs) + 0.5) >= s.w:
        return
    edges = []
    for i, (ax, ay) in enumerate(P):
        bx, by = P[i - 1]
        if ay != by:
            if ay > by:
                ax, ay, bx, by = bx, by, ax, ay
            slope = (bx - ax) / (by - ay)
            edges.append((ay, by, ax - ay * slope, slope))
    W = s.w
    if y1 - y0 >= 6:
        cuts = sorted({y0, y1 + 1} | {max(y0, min(y1 + 1, math.ceil(y - 0.5))) for y in ys})
        for start, end in zip(cuts, cuts[1:]):
            if end <= start:
                continue
            yc = start + 0.5
            active = [(offset + yc * slope, slope) for ay, by, offset, slope in edges if ay <= yc < by]
            if len(active) != 2:
                continue
            (lo, dl), (hi, dh) = sorted(active)
            for py in range(start, end):
                xa, xb = int(lo + 0.5), int(hi + 0.5)
                if xa < 0:
                    xa = 0
                if xb > W:
                    xb = W
                if xb > xa:
                    k, cy = xb - xa, py >> 1
                    (s.pb if py & 1 else s.pt)[cy][xa:xb] = span(col, k)
                    s.ch[cy][xa:xb] = span(" ", k)
                    s.bg[cy][xa:xb] = span(None, k)
                lo += dl
                hi += dh
        return
    for py in range(y0, y1 + 1):
        yc = py + 0.5
        inter = [offset + yc * slope for ay, by, offset, slope in edges if ay <= yc < by]
        if len(inter) < 2:
            continue
        lo, hi = min(inter), max(inter)
        xa, xb = max(0, int(lo + 0.5)), min(W, int(hi + 0.5))
        if xb > xa:
            k, cy = xb - xa, py >> 1
            (s.pb if py & 1 else s.pt)[cy][xa:xb] = span(col, k)
            s.ch[cy][xa:xb] = span(" ", k)
            s.bg[cy][xa:xb] = span(None, k)


def pline(s, x0, y0, x1, y1, col):
    if max(x0, x1) < 0 or min(x0, x1) >= s.w or max(y0, y1) < 0 or min(y0, y1) >= s.ph:
        return
    if 0 <= x0 < s.w and 0 <= x1 < s.w and 0 <= y0 < s.ph and 0 <= y1 < s.ph:
        ta, tb = 0., 1.
    else:
        c = clip2d(x0, y0, x1, y1, s.w, s.ph)
        if not c:
            return
        ta, tb = c
    dx, dy = x1 - x0, y1 - y0
    ax, ay = x0 + dx * ta, y0 + dy * ta
    bx, by = x0 + dx * tb, y0 + dy * tb
    n = int(max(abs(bx - ax), abs(by - ay))) + 1
    sx, sy = (bx - ax) / n, (by - ay) / n
    pt, pb = s.pt, s.pb
    for i in range(n + 1):
        x, py = int(ax + sx * i), int(ay + sy * i)
        if 0 <= x < s.w and 0 <= py < s.ph:
            (pb if py & 1 else pt)[py >> 1][x] = col


def line3(s, cam, a, b, col):
    r = cam.seg(a, b)
    if r:
        pline(s, r[0][0], r[0][1], r[1][0], r[1][1], col)


def prect(s, x, py, w, h, col):
    x, py = int(x), int(py)
    x0, x1 = max(0, x), min(s.w, x + w)
    if x1 <= x0:
        return
    for yy in range(max(0, py), min(s.ph, py + h)):
        (s.pb if yy & 1 else s.pt)[yy >> 1][x0:x1] = span(col, x1 - x0)


_BL = {}


def shade(col, k):
    k = max(0.0, min(1.0, k))
    key = (col, int(k * 40))
    v = _BL.get(key)
    if v is None:
        if len(_BL) > 30000:
            _BL.clear()
        q = int(k * 40) / 40
        v = _BL[key] = (int(col[0] * q), int(col[1] * q), int(col[2] * q))
    return v


def mul(col, m):
    return (min(255, int(col[0] * m[0])), min(255, int(col[1] * m[1])), min(255, int(col[2] * m[2])))


def tint_rows(s, y0, y1, col, t):
    memo = {}
    for y in range(max(0, y0), min(s.h, y1)):
        for layer in (s.fg, s.pt, s.pb, s.bg):
            row = layer[y]
            for x, c in enumerate(row):
                if c is not None:
                    o = memo.get(c)
                    if o is None:
                        o = memo[c] = blend(c, col, t)
                    row[x] = o


def postfx(s, now, glitch, speed=5.0):
    band = s.h + 16
    by = int((now * speed) % band) - 8
    tint_rows(s, by, by + 1, WHITE, 0.10)
    if glitch:
        for _ in range(random.randint(1, 3)):
            y0 = random.randrange(s.h)
            dx = random.randint(-8, 8)
            n = random.randint(1, 2)
            for y in range(y0, min(s.h, y0 + n)):
                s.shift_row(y, dx)
            tint_rows(s, y0, y0 + n, random.choice((PINK, CYAN)), 0.25)


def text_over_pixels(s):
    for y in range(s.h):
        rc, pt, pb, bg = s.ch[y], s.pt[y], s.pb[y], s.bg[y]
        for x in range(s.w):
            if rc[x] != " " and bg[x] is None:
                c = pb[x] or pt[x]
                if c is not None:
                    bg[x] = (c[0] * 3 // 4, c[1] * 3 // 4, c[2] * 3 // 4)


_CUBE = None


def colour_cube():
    """Object array of 4-bit-per-channel RGB tuples, indexed by r<<8|g<<4|b."""
    global _CUBE
    if _CUBE is None:
        lv = [i * 17 for i in range(16)]
        arr = np.empty(4096, dtype=object)
        for i in range(4096):
            arr[i] = (lv[i >> 8], lv[(i >> 4) & 15], lv[i & 15])
        _CUBE = arr
    return _CUBE


# ---------------------------------------------------------------- scene objects

class Box:
    __slots__ = ("c", "y0", "size", "col", "yaw", "screen", "edge", "tag", "_faces", "bound", "fc", "emit")

    def __init__(self, cx, y0, cz, sx, sy, sz, col, yaw=0.0, screen=None, edge=None, tag=None, emit=False):
        self.c = (cx, cz)
        self.y0 = y0
        self.size = (sx, sy, sz)
        self.col, self.yaw, self.screen, self.edge, self.tag, self.emit = col, yaw, screen, edge, tag, emit
        self._faces = None
        self.fc = None
        self.bound = (self.center(), math.sqrt((sx * sx + sy * sy + sz * sz) / 4))

    def center(self):
        return (self.c[0], self.y0 + self.size[1] / 2, self.c[1])

    def faces(self):
        if self._faces is not None:
            return self._faces
        cx, cz = self.c
        hx, hy, hz = self.size[0] / 2, self.size[1], self.size[2] / 2
        cs, sn = math.cos(self.yaw), math.sin(self.yaw)

        def P(dx, y, dz):
            return (cx + dx * cs - dz * sn, self.y0 + y, cz + dx * sn + dz * cs)

        def N(nx, nz):
            return (nx * cs - nz * sn, 0.0, nx * sn + nz * cs)

        self._faces = [
            (N(0, -1), [P(-hx, 0, -hz), P(hx, 0, -hz), P(hx, hy, -hz), P(-hx, hy, -hz)], "front"),
            (N(0, 1), [P(hx, 0, hz), P(-hx, 0, hz), P(-hx, hy, hz), P(hx, hy, hz)], "back"),
            (N(-1, 0), [P(-hx, 0, hz), P(-hx, 0, -hz), P(-hx, hy, -hz), P(-hx, hy, hz)], "left"),
            (N(1, 0), [P(hx, 0, -hz), P(hx, 0, hz), P(hx, hy, hz), P(hx, hy, -hz)], "right"),
            ((0.0, 1.0, 0.0), [P(-hx, hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), P(-hx, hy, hz)], "top"),
        ]
        return self._faces


def form_light(n):
    if n[1] > 0.5:
        return 1.15
    return 0.7 + 0.25 * max(0.0, -n[2]) + 0.1 * abs(n[0])


class Sprite:
    """Pixel art on a plane: origin = world top-left, u = column step, v = row step."""
    __slots__ = ("name", "origin", "u", "v", "pos")

    def __init__(self, name, origin, u, v):
        self.name, self.origin, self.u, self.v = name, origin, u, v
        self.pos = origin


# ---------------------------------------------------------------- the mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = Cam(w, h, fov=0.85)
        self.glitch = Glitch(0.003)
        self.parts = Particles(300)
        self.last = self.t0 = time.time()
        self.rnd = random.Random(42)
        self.st = [{} for _ in range(8)]
        self.eyes = random.choice(EYES)
        self.next_eyes = self.t0 + 2
        self.blink_until = 0.0
        self.print_i = random.randrange(len(PRINTS))
        self.print_t = self.t0 - random.uniform(0, 15)
        self.print_state = ("", 0.0)
        self.blackout = 0.0
        self.msg_i = 0
        self.msg_next = 0.0
        self.sign_dead = (None, 0.0)
        self.cam_label = KEYS[0][5]
        self.leds = [(self.rnd.random(), self.rnd.random()) for _ in range(30)]
        self.robot = {"x": -4.0, "dir": 1, "pause": 0.0}
        self.cat_t0 = self.t0 - 3.0
        self.robot_pos = (0, 0, 0)
        self.bitmap_cache = {}
        self.cube = colour_cube()
        self.light_pos = np.array([l[0] for l in LIGHTS], np.float32)
        self.light_col = np.array([l[1] for l in LIGHTS], np.float32) / 255.0
        self.light_inv_r2 = np.array([1.0 / (l[2] * l[2]) for l in LIGHTS], np.float32)
        self.setup_grid()
        self.setup_textures()
        self.static = self.build()
        self.setup_face_lighting()
        self.strands = self.make_strands()

    # ------------------------------------------------------------ precomputation
    def setup_grid(self):
        cam, W, PH = self.cam, self.w, self.h * 2
        xs = (np.arange(W, dtype=np.float32) + 0.5 - cam.cx) / cam.f2
        ys = (cam.cy * 2 - np.arange(PH, dtype=np.float32) - 0.5) / cam.f2
        self.VX = np.broadcast_to(xs[None, :], (PH, W)).ravel().copy()
        self.VY = np.broadcast_to(ys[:, None], (PH, W)).ravel().copy()
        b4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 2.0
        self.dither = np.tile(b4, (PH // 4 + 1, W // 4 + 1))[:PH, :W].ravel()[:, None].copy()
        grid = np.arange(PH * W).reshape(PH, W)[::2, ::2]
        self.sub_shape = grid.shape
        self.sub = grid.ravel()

    def setup_textures(self):
        # neon sign: font upsampled 3x, tube core, letter ids and a blurred bloom
        rows = font_rows("DEDSEC")
        mask = np.array([[c == "#" for c in r] for r in rows], bool)
        letters = np.array([[(x // 7) + 1 for x in range(len(rows[0]))] for _ in rows], np.int8)
        up = 3
        m = np.kron(mask, np.ones((up, up), bool))
        lid = np.kron(letters, np.ones((up, up), np.int8)) * m
        core = m.copy()
        core[1:-1, 1:-1] = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
        core[0, :] = core[-1, :] = False
        pad = 14
        H, Wd = m.shape[0] + pad * 2, m.shape[1] + pad * 2
        big = np.zeros((H, Wd), np.float32)
        big[pad:-pad, pad:-pad] = m
        k = np.exp(-np.linspace(-2.2, 2.2, 2 * pad + 1) ** 2).astype(np.float32)
        k /= k.sum()
        blur = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, big)
        blur = np.apply_along_axis(lambda c: np.convolve(c, k, "same"), 0, blur)
        blur /= blur.max()
        lid_big = np.zeros((H, Wd), np.int8)
        lid_big[pad:-pad, pad:-pad] = lid
        core_big = np.zeros((H, Wd), bool)
        core_big[pad:-pad, pad:-pad] = core
        tex = 0.24 / up
        sw = len(rows[0]) * 0.24
        sx0 = 1.6 - sw / 2 - pad * tex
        stop = 6.55 + pad * tex
        self.sign = (sx0, stop, tex, lid_big, core_big, blur)
        self.sign_rect = (sx0, sx0 + Wd * tex, stop - H * tex, stop)

        # lit decals: (wall, u0, vtop, texel, rgb, alpha)
        pal = {"b": (40, 40, 90), "y": (250, 220, 40), "w": (240, 240, 250), "k": (14, 12, 18),
               "p": (250, 30, 130), "c": (20, 210, 240)}
        skull = ["k" * 24] + ["k" + "".join("w" if c == "X" else "p" for c in r) + "k" for r in SKULL] + ["k" * 24]
        g = dilate_rows(font_rows("DS", "#", "."), "o")
        graffiti_pal = {"o": (20, 16, 26), "#": (250, 210, 40)}
        gr = art(g, graffiti_pal)
        # yellow -> pink vertical spray gradient
        hgt = gr[0].shape[0]
        for y in range(hgt):
            t = y / max(1, hgt - 1)
            sel = gr[1][y] & (gr[0][y, :, 0] > 100)
            gr[0][y, sel] = np.array(blend((250, 220, 40), (255, 40, 150), t), np.float32)
        self.decals = [
            ("back", -6.35, 6.75, 0.075, *art(skull, {"w": (235, 235, 245), "p": (210, 30, 110), "k": (14, 12, 18)})),
            ("back", 7.4, 6.6, 0.16, *art(POSTER_EYE, pal)),
            ("left", 3.4, 6.2, 0.22, *art(POSTER_BARS, pal)),
            ("left", 9.0, 4.1, 0.2, *gr),
        ]
        self.window = self.make_window()

    def make_window(self):
        r = self.rnd
        TW, TH = 96, 66
        u0, u1, v0, v1 = -9.3, -5.2, 2.55, 5.25      # u = -z on the right wall
        img = np.zeros((TH, TW, 3), np.float32)
        for y in range(TH):
            img[y, :] = blend((6, 8, 30), (70, 30, 90), (y / TH) ** 1.4)
        for _ in range(40):
            x, y = r.randrange(TW), r.randrange(TH // 2)
            img[y, x] = (200, 200, 230)
        mx, my = 74, 12
        for y in range(TH):
            for x in range(TW):
                d = math.hypot(x - mx, (y - my) * 1.0)
                if d < 5.5:
                    img[y, x] = (235, 230, 200) if d < 4.6 else (150, 140, 150)
        # Golden Gate silhouette on the left horizon
        deck = 46
        for tx in (8, 30):
            img[deck - 22:deck + 8, tx:tx + 2] = (190, 60, 40)
            img[deck - 22, tx - 1:tx + 3] = (190, 60, 40)
        for x in range(0, 40):
            cy = deck - 21 + int(18 * (1 - ((x - 19) / 11.0) ** 2)) if 8 <= x <= 31 else deck - 21 + int(18 * min(1, abs(x - (8 if x < 8 else 31)) / 9))
            cy = max(deck - 21, min(deck - 1, cy))
            img[cy, x] = (170, 60, 50)
        img[deck, 0:44] = (150, 50, 40)
        # skyline with lit windows and the Transamerica pyramid
        lit = []
        x = 40
        while x < TW:
            bw = r.randint(5, 10)
            bh = r.randint(10, 30)
            top = TH - bh
            img[top:TH, x:x + bw] = (18, 18, 44)
            for wy in range(top + 2, TH - 1, 3):
                for wx in range(x + 1, min(TW, x + bw) - 1, 2):
                    if r.random() < 0.35:
                        img[wy, wx] = (240, 190, 100) if r.random() < 0.8 else (140, 220, 255)
                        lit.append((wy, wx))
            x += bw + r.randint(0, 2)
        px = 58
        for y in range(TH - 44, TH):
            half = (y - (TH - 44)) * 0.13
            img[y, int(px - half):int(px + half) + 1] = (26, 24, 52)
        img[TH - 46:TH - 44, px] = (255, 60, 60)
        # frame and mullions
        img[:2, :] = img[-2:, :] = (34, 32, 44)
        img[:, :2] = img[:, -2:] = (34, 32, 44)
        img[:, TW // 2 - 1:TW // 2 + 1] = (34, 32, 44)
        img[TH // 2, :] = (34, 32, 44)
        self.window_lit = lit
        return (u0, v1, (u1 - u0) / TW, img)

    def build(self):
        B = []
        # --- desk run with monitor wall (back left)
        B.append(Box(-5.3, 1.3, 12.0, 7.8, 0.1, 1.6, WOOD, edge=(170, 120, 80)))
        B.append(Box(-8.6, 0.0, 12.0, 1.1, 1.3, 1.4, DARKM, edge=(80, 80, 96)))
        B.append(Box(-2.0, 0.0, 12.0, 1.1, 1.3, 1.4, DARKM, edge=(80, 80, 96)))
        mons = [(-7.6, 1.72, 12.25, 0.3, 1.35, 0), (-5.3, 1.72, 12.4, 0.0, 1.35, 1), (-3.0, 1.72, 12.25, -0.3, 1.35, 2),
                (-6.45, 3.25, 12.6, 0.08, 1.2, 3), (-4.15, 3.25, 12.6, -0.08, 1.2, 5)]
        for x, y, z, yaw, hh, idx in mons:
            if idx in (3, 5):
                B.append(Box(x, 1.4, z + 0.2, 0.14, y - 1.4 + 0.3, 0.14, METAL))
            else:
                B.append(Box(x, 1.4, z + 0.12, 0.5, 0.08, 0.4, DARKM))
                B.append(Box(x, 1.48, z + 0.14, 0.14, 0.3, 0.14, DARKM))
            B.append(Box(x, y, z, 2.1, hh, 0.12, (22, 22, 30), yaw=yaw, screen=idx, edge=(70, 70, 92)))
        B.append(Box(-5.3, 1.4, 11.5, 1.3, 0.06, 0.4, (40, 40, 52), edge=PINK, tag="keyboard"))
        B.append(Box(-4.35, 1.4, 11.5, 0.18, 0.06, 0.26, (60, 60, 70), edge=CYAN))
        B.append(Box(-6.6, 1.4, 11.45, 0.18, 0.3, 0.18, (220, 40, 40)))
        B.append(Box(-6.9, 1.4, 11.6, 0.18, 0.3, 0.18, (40, 200, 90)))
        # laptop on the right end of the desk
        B.append(Box(-1.9, 1.4, 11.55, 1.0, 0.05, 0.65, (60, 60, 72)))
        B.append(Box(-1.9, 1.45, 11.88, 1.0, 0.62, 0.05, (30, 30, 38), screen=6, edge=(90, 90, 110)))
        # desk lamp
        B.append(Box(-8.75, 1.4, 11.9, 0.45, 0.08, 0.45, METAL))
        B.append(Box(-8.75, 2.2, 11.6, 0.45, 0.28, 0.4, (255, 190, 90), emit=True, tag="lamp"))
        # office chair, back to the camera and low enough not to hide the screens
        B.append(Box(-4.3, 0.0, 10.4, 0.16, 0.75, 0.16, DARKM))
        B.append(Box(-4.3, 0.0, 10.4, 1.0, 0.08, 0.16, DARKM))
        B.append(Box(-4.3, 0.75, 10.4, 1.1, 0.18, 1.0, (90, 24, 56), edge=PINK))
        B.append(Box(-4.3, 0.93, 9.95, 1.1, 1.0, 0.16, (110, 28, 66), edge=PINK))
        # --- shelf with Wrench's mask (back wall, upper left)
        B.append(Box(-7.9, 4.85, 12.65, 3.0, 0.1, 0.7, WOOD, edge=(170, 120, 80)))
        B.append(Box(-7.75, 4.95, 12.62, 0.35, 0.12, 0.35, (30, 30, 38)))
        for dx, col in ((-9.0, (240, 30, 130)), (-8.75, (20, 200, 230)), (-6.75, (245, 220, 30))):
            B.append(Box(dx, 4.95, 12.6, 0.2, 0.5, 0.2, col))
        # --- pizza tower and plant between desk and TV
        for i, yaw in enumerate((0.1, -0.15, 0.25, 0.0, -0.3)):
            B.append(Box(-0.45, i * 0.14, 12.2, 1.2, 0.13, 1.2, CARD, yaw=yaw, edge=CARD_EDGE))
        B.append(Box(0.75, 0.0, 12.35, 0.75, 0.6, 0.75, (160, 70, 50), edge=(200, 110, 80)))
        # --- TV corner (back right)
        B.append(Box(4.3, 0.0, 12.5, 4.6, 0.75, 0.8, (52, 38, 42), edge=(110, 84, 80)))
        B.append(Box(3.3, 0.75, 12.4, 0.9, 0.16, 0.55, (24, 24, 30), edge=GREEN, tag="console"))
        B.append(Box(5.4, 0.75, 12.4, 0.5, 0.5, 0.5, (40, 40, 50), edge=(120, 60, 200)))
        B.append(Box(4.3, 1.55, 12.85, 4.4, 2.55, 0.1, (16, 16, 22), screen=4, edge=(70, 70, 90)))
        # --- server rack (back right corner)
        B.append(Box(9.0, 0.0, 11.9, 1.3, 4.0, 1.6, (34, 36, 48), edge=(80, 92, 116), tag="rack"))
        B.append(Box(7.9, 0.0, 12.3, 0.7, 1.4, 0.8, (40, 42, 56), edge=(80, 92, 116)))
        # --- lounge: couch under the window, facing the room
        cushion = (150, 70, 170)
        B.append(Box(8.7, 0.0, 7.4, 1.6, 0.5, 4.0, (110, 50, 130)))
        B.append(Box(9.5, 0.5, 7.4, 0.4, 0.75, 4.0, (120, 56, 140), edge=(190, 120, 210)))
        B.append(Box(8.7, 0.5, 5.25, 1.6, 0.35, 0.3, (120, 56, 140)))
        B.append(Box(8.7, 0.5, 9.55, 1.6, 0.35, 0.3, (120, 56, 140)))
        B.append(Box(8.6, 0.5, 6.4, 1.3, 0.16, 1.7, cushion, edge=(200, 130, 220)))
        B.append(Box(8.6, 0.5, 8.4, 1.3, 0.16, 1.7, cushion, edge=(200, 130, 220)))
        B.append(Box(9.1, 0.66, 6.0, 0.35, 0.45, 0.6, (240, 200, 40), yaw=0.3))          # pillow
        B.append(Box(9.0, 0.0, 4.6, 0.6, 0.55, 0.6, (160, 70, 50), edge=(200, 110, 80)))  # plant pot
        # --- left wall workshop: 3D printer table
        B.append(Box(-9.1, 0.0, 7.4, 1.6, 1.0, 2.2, WOOD, edge=(170, 120, 80)))
        B.append(Box(-9.1, 1.0, 7.4, 1.3, 0.12, 1.3, (60, 60, 76), tag="printer"))
        B.append(Box(-9.3, 1.0, 8.35, 0.5, 0.5, 0.25, (20, 200, 230)))                    # filament spool
        # --- floor clutter: open pizza box, cans
        B.append(Box(2.6, 0.0, 6.2, 1.1, 0.08, 1.1, CARD, edge=CARD_EDGE, tag="pizza"))
        B.append(Box(2.6, 0.0, 6.78, 1.1, 1.0, 0.05, CARD, edge=CARD_EDGE))
        B.append(Box(3.5, 0.0, 5.7, 0.2, 0.32, 0.2, (40, 160, 230)))
        B.append(Box(-1.8, 0.0, 5.2, 0.32, 0.2, 0.2, (240, 200, 40), yaw=1.2))
        return B

    def setup_face_lighting(self):
        """Static per-face light transfer, so each frame is one small matrix product."""
        faces, alb, form = [], [], []
        for b in self.static:
            for n, quad, kind in b.faces():
                c = [sum(p[i] for p in quad) / 4 for i in range(3)]
                faces.append((c, n))
                alb.append(b.col)
                form.append(form_light(n))
        F = np.zeros((len(faces), len(LIGHTS)), np.float32)
        for i, (c, n) in enumerate(faces):
            for j, (p, col, R, base, gain) in enumerate(LIGHTS):
                d = [p[k] - c[k] for k in range(3)]
                d2 = d[0] ** 2 + d[1] ** 2 + d[2] ** 2 + 1e-6
                lam = max(0.0, (n[0] * d[0] + n[1] * d[1] + n[2] * d[2]) / math.sqrt(d2))
                F[i, j] = (0.25 + 0.75 * lam) / (1 + d2 / (R * R))
        self.face_F = F
        self.face_alb = np.array(alb, np.float32)
        self.face_form = np.array(form, np.float32)[:, None]

    def make_strands(self):
        strands = [((X0, 6.5, 2.0), (X1, 6.7, 6.5)), ((X0, 6.7, 8.0), (X1, 6.5, 12.5)), ((-9.8, 6.6, 12.8), (9.8, 6.6, 12.8))]
        out = []
        for a, b in strands:
            n = 18
            pts = []
            for i in range(n + 1):
                t = i / n
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - math.sin(t * math.pi) * 0.7,
                            a[2] + (b[2] - a[2]) * t))
            out.append(pts)
        return out

    # ------------------------------------------------------------ audio fallback
    def audio(self, now):
        bands = DATA.bands
        if DATA.audio_live or any(b > 0 for b in bands):
            return bands, DATA.beat, DATA.level
        bands = [max(0.0, 0.35 + 0.3 * math.sin(now * (1.3 + i * 0.21) + i)) * (1 - i / 24) for i in range(16)]
        beat = max(0.0, 1 - ((now * 2.0) % 1.0) * 3.5)
        return bands, beat, 0.4

    # ------------------------------------------------------------ lights
    def light_levels(self, now, beat):
        K = []
        for i, (p, col, R, base, gain) in enumerate(LIGHTS):
            k = base * (1 + gain * beat)
            if i == 0:
                k *= 0.92 + 0.08 * math.sin(now * 31)
                if self.sign_dead[1] > now:
                    k *= 0.7
            elif i == 1:
                k *= 0.9 + 0.1 * math.sin(now * 13) * math.sin(now * 3.1)
            elif i == 8:
                k *= 1.0 if self.print_state[1] < 1 else 0.2
            K.append(k)
        K = np.array(K, np.float32)
        if now < self.blackout:
            K *= 0.4
        return K

    def light_at(self, p, K):
        r, g, b = AMBIENT.tolist()
        for i, (lp, col, R, base, gain) in enumerate(LIGHTS):
            d2 = (lp[0] - p[0]) ** 2 + (lp[1] - p[1]) ** 2 + (lp[2] - p[2]) ** 2
            f = K[i] * 0.6 / (1 + d2 / (R * R))
            r += col[0] / 255 * f
            g += col[1] / 255 * f
            b += col[2] / 255 * f
        return (r, g, b)

    # ------------------------------------------------------------ the room shell (numpy ray cast)
    def shell(self, s, now, K, beat):
        cam = self.cam
        c, sn, cp, sp = cam.c, cam.s, cam.cp, cam.sp
        VX, VY = self.VX, self.VY
        dy = VY * cp - sp
        z1 = VY * sp + cp
        dx = VX * c + z1 * sn
        dz = z1 * c - VX * sn
        ox, oy, oz = cam.pos
        eps = np.float32(1e-6)
        dx = np.where(np.abs(dx) < eps, eps, dx)
        dy = np.where(np.abs(dy) < eps, eps, dy)
        dz = np.where(np.abs(dz) < eps, eps, dz)
        f32 = np.float32
        tx = np.where(dx > 0, f32(X1 - ox), f32(X0 - ox)) / dx
        ty = np.where(dy > 0, f32(YC - oy), f32(-oy)) / dy
        tz = np.where(dz > 0, f32(Z1 - oz), f32(Z0 - oz)) / dz
        ox, oy, oz = f32(ox), f32(oy), f32(oz)
        t = np.minimum(np.minimum(tx, ty), tz)
        hx, hy, hz = ox + t * dx, oy + t * dy, oz + t * dz
        pix = t / cam.f2                          # world size of one pixel at the hit
        on_x = t == tx
        on_y = (t == ty) & ~on_x
        on_z = ~(on_x | on_y)
        N = t.shape[0]
        alb = np.empty((N, 3), np.float32)

        def brick(idx, u, v, base, mortar, bw, bh):
            pp = pix[idx]
            row = np.floor(v / bh)
            uu = u + (row % 2) * (bw * 0.5) + 40
            col = np.floor(uu / bw)
            fu, fv = uu / bw - col, v / bh - row
            m = (fv < np.maximum(0.13, pp / bh * 0.9)) | (fu < np.maximum(0.05, pp / bw * 0.9))
            hsh = ((row.astype(np.int32) * 7919) ^ (col.astype(np.int32) * 104729)) & 255
            var = (0.84 + hsh.astype(np.float32) * (0.26 / 255))[:, None]
            out = np.asarray(base, np.float32)[None, :] * var
            far = np.clip(pp / bh * 1.6 - 0.6, 0, 1)[:, None]
            mcol = np.asarray(mortar, np.float32)[None, :] * (1 - far) + out * far
            out = np.where(m[:, None], mcol, out)
            return out

        back = np.flatnonzero(on_z & (dz > 0))
        front = np.flatnonzero(on_z & (dz <= 0))
        left = np.flatnonzero(on_x & (dx < 0))
        right = np.flatnonzero(on_x & (dx > 0))
        floor = np.flatnonzero(on_y & (dy < 0))
        ceil = np.flatnonzero(on_y & (dy > 0))
        if back.size:
            u, v = hx[back], hy[back]
            a = brick(back, u, v, (132, 66, 70), (70, 48, 58), 0.9, 0.36)
            sk = v < 0.18
            a[sk] = (60, 30, 90)
            alb[back] = a
        if front.size:
            alb[front] = brick(front, -hx[front], hy[front], (90, 74, 112), (56, 46, 70), 1.2, 0.6)
        if left.size:
            alb[left] = brick(left, hz[left], hy[left], (96, 76, 128), (58, 46, 78), 1.2, 0.6)
        if right.size:
            alb[right] = brick(right, -hz[right], hy[right], (66, 92, 112), (40, 56, 70), 1.2, 0.6)
        if floor.size:
            u, v = hx[floor], hz[floor]
            pp = pix[floor]
            fu, fv = u / 1.5 - np.floor(u / 1.5), v / 1.5 - np.floor(v / 1.5)
            m = (fu < np.maximum(0.04, pp / 1.5 * 0.8)) | (fv < np.maximum(0.04, pp / 1.5 * 0.8))
            stain = (0.9 + 0.1 * np.sin(u * 1.3 + 2) * np.sin(v * 1.7)).astype(np.float32)[:, None]
            a = np.where(m[:, None], np.float32([62, 56, 64]), np.float32([104, 96, 104]) * stain)
            # Woven rug: muted dyes sit below the neon and monitor light.
            rug = (u > -3.6) & (u < 4.2) & (v > 4.4) & (v < 10.2)
            if rug.any():
                e = np.minimum(np.minimum(u - -3.6, 4.2 - u), np.minimum(v - 4.4, 10.2 - v))[rug]
                band = (np.floor(e / 0.28).astype(np.int32)) % 4
                rp = np.float32([(112, 40, 72), (44, 34, 68), (140, 104, 62), (44, 34, 68)])
                ru, rv = u[rug], v[rug]
                # Fade the weave below pixel size, so distant fabric stays calm.
                weave = ((np.floor(ru * 14) + np.floor(rv * 14)) % 2 - .5)
                detail = np.clip(1 - pp[rug] * 18, 0, 1)
                wear = .93 + .045 * np.sin(ru * 1.7) * np.sin(rv * 2.1)
                a[rug] = rp[band] * (wear + weave * detail * .08)[:, None]
            alb[floor] = a
        if ceil.size:
            v = hz[ceil]
            beam = (v / 2.0 - np.floor(v / 2.0)) < 0.12
            alb[ceil] = np.where(beam[:, None], np.float32([30, 28, 38]), np.float32([54, 50, 64]))

        # decals on walls (lit like the wall they are on)
        for wall, u0, vt, tex, rgb, alpha in self.decals:
            idx = back if wall == "back" else left
            if not idx.size:
                continue
            u = hx[idx] if wall == "back" else hz[idx]
            v = hy[idx]
            th, tw = alpha.shape
            iu = ((u - u0) / tex).astype(np.int32)
            iv = ((vt - v) / tex).astype(np.int32)
            ok = (iu >= 0) & (iu < tw) & (iv >= 0) & (iv < th) & (u >= u0) & (v <= vt)
            if not ok.any():
                continue
            sel = idx[ok]
            iu, iv = iu[ok], iv[ok]
            on = alpha[iv, iu]
            alb[sel[on]] = rgb[iv[on], iu[on]]

        # lighting is smooth: evaluate it on a half-resolution grid, then upsample
        PH, W = s.ph, s.w
        sub = self.sub
        ax = np.where(on_x, 0, np.where(on_y, 1, 2))[sub]
        lp = self.light_pos
        sx, sy, sz = hx[sub], hy[sub], hz[sub]
        hh = np.where(ax == 0, sx, np.where(ax == 1, sy, sz))
        ddx = sx[:, None] - lp[None, :, 0]
        ddy = sy[:, None] - lp[None, :, 1]
        ddz = sz[:, None] - lp[None, :, 2]
        d2 = ddx * ddx + ddy * ddy + ddz * ddz + f32(1e-4)
        dp = np.abs(hh[:, None] - lp.T[ax])
        f = (f32(0.3) + f32(0.7) * dp / np.sqrt(d2)) / (f32(1) + d2 * self.light_inv_r2[None, :])
        lh = (f @ (self.light_col * K[:, None]) + AMBIENT).reshape(self.sub_shape + (3,))
        light = np.repeat(np.repeat(lh, 2, axis=0), 2, axis=1)[:PH, :W].reshape(N, 3)
        out = alb * light * 1.12

        # emissive: neon sign + bloom on the back wall, skyline window on the right wall
        if back.size:
            sx0, stop, tex, lid, core, blur = self.sign
            u, v = hx[back], hy[back]
            th, tw = lid.shape
            iu = ((u - sx0) / tex).astype(np.int32)
            iv = ((stop - v) / tex).astype(np.int32)
            ok = (iu >= 0) & (iu < tw) & (iv >= 0) & (iv < th) & (u >= sx0) & (v <= stop)
            if ok.any():
                sel = back[ok]
                iu, iv = iu[ok], iv[ok]
                glow = 0.55 + 0.45 * beat
                dead = self.sign_dead[0] if self.sign_dead[1] > now else None
                bl = blur[iv, iu]
                out[sel] += bl[:, None] * np.float32([150, 20, 90]) * glow
                L = lid[iv, iu]
                tube = L > 0
                if dead is not None:
                    tube &= L != dead + 1
                tsel = sel[tube]
                out[tsel] = np.float32([255, 60, 160]) * (0.8 + 0.2 * glow)
                cs = core[iv, iu] & tube
                out[sel[cs]] = np.float32([255, 205, 235])
                if dead is not None:
                    out[sel[L == dead + 1]] = np.float32([70, 20, 46])
        if right.size:
            u0, vt, tex, img = self.window
            u, v = -hz[right], hy[right]
            th, tw = img.shape[:2]
            iu = ((u - u0) / tex).astype(np.int32)
            iv = ((vt - v) / tex).astype(np.int32)
            ok = (iu >= 0) & (iu < tw) & (iv >= 0) & (iv < th) & (u >= u0) & (v <= vt)
            if ok.any():
                out[right[ok]] = img[iv[ok], iu[ok]]

        # A compact palette keeps smooth wall lighting cheap to encode in the terminal.
        q = np.clip(out, 0, 255.9).astype(np.int32) >> 4
        key = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
        rows = self.cube[key].reshape(s.ph, s.w).tolist()
        pt, pb = s.pt, s.pb
        for py in range(s.ph):
            if py & 1:
                pb[py >> 1] = rows[py]
            else:
                pt[py >> 1] = rows[py]
        # ceiling pipes and cable trays as strokes
        for x in (-6.0, 3.5):
            line3(s, cam, (x, YC - 0.35, Z0), (x, YC - 0.35, Z1), (96, 92, 112))
            line3(s, cam, (x + 0.12, YC - 0.35, Z0), (x + 0.12, YC - 0.35, Z1), (54, 52, 66))
        line3(s, cam, (X0 + 0.02, 1.1, Z0), (X0 + 0.02, 1.1, Z1), (36, 30, 40))

    # ------------------------------------------------------------ geometry
    def draw_box(self, s, b):
        cam = self.cam
        center, radius = b.bound
        vx, vy, vz = cam.view(center)
        f, cx, cy = cam.f2, cam.cx, cam.cy * 2
        if (vz + radius < NEAR or
                abs(vx) * f - cx * vz > radius * math.hypot(f, cx) or
                abs(vy) * f - cy * vz > radius * math.hypot(f, cy)):
            return []
        px, py, pz = cam.pos
        drawn = []
        for fi, (n, quad, kind) in enumerate(b.faces()):
            q0 = quad[0]
            if n[0] * (px - q0[0]) + n[1] * (py - q0[1]) + n[2] * (pz - q0[2]) <= 0:
                continue
            views = [cam.view(p) for p in quad]
            unclipped = all(v[2] >= NEAR for v in views)
            P = [cam.pp(v) for v in views] if unclipped else cam.poly(quad)
            if not P:
                continue
            xs, ys = zip(*P)
            if max(xs) < 0 or min(xs) >= s.w or max(ys) < 0 or min(ys) >= s.ph:
                continue
            col = b.fc[fi] if b.fc else b.col
            fill(s, P, col)
            if (unclipped and b.screen is None and not b.emit and b.col in (WOOD, CARD)
                    and max(xs) - min(xs) >= 5 and max(ys) - min(ys) >= 3):
                A, Bv, C, D = views
                tc = shade(col, 0.78)
                for j in (1, 2, 3):
                    u = j / 4
                    pa = cam.pp(tuple(A[k] + (D[k] - A[k]) * u for k in range(3)))
                    pb = cam.pp(tuple(Bv[k] + (C[k] - Bv[k]) * u for k in range(3)))
                    pline(s, pa[0], pa[1], pb[0], pb[1], tc)
            drawn.append((kind, quad, P))
            if b.edge:
                ec = b.edge if b.emit or b.edge in (PINK, CYAN, GREEN) else blend(col, b.edge, 0.6)
                for i in range(4):
                    if kind == "top" or i == 2:
                        if unclipped:
                            pline(s, P[i - 1][0], P[i - 1][1], P[i][0], P[i][1], ec)
                        else:
                            line3(s, cam, quad[i - 1], quad[i], ec)
        return drawn

    def bitmap(self, s, origin, u, v, rows, pal):
        """Draw char art on a plane: origin = top-left, u = column step, v = row step (down)."""
        cam = self.cam
        R, C = len(rows), len(rows[0])
        corners = [cam.proj((origin[0] + u[0] * c + v[0] * r, origin[1] + u[1] * c + v[1] * r,
                             origin[2] + u[2] * c + v[2] * r)) for c, r in ((0, 0), (C, 0), (C, R), (0, R))]
        if any(p is None for p in corners):
            return None
        x0 = max(0, math.ceil(min(p[0] for p in corners) - 0.5))
        x1 = min(s.w, math.ceil(max(p[0] for p in corners) - 0.5))
        y0 = max(0, math.ceil(min(p[1] for p in corners) - 0.5))
        y1 = min(s.ph, math.ceil(max(p[1] for p in corners) - 0.5))
        if x1 <= x0 or y1 <= y0:
            return corners
        O = cam.view(origin)
        U = cam.view(tuple(origin[i] + u[i] for i in range(3)))
        V = cam.view(tuple(origin[i] + v[i] for i in range(3)))
        U = tuple(U[i] - O[i] for i in range(3))
        V = tuple(V[i] - O[i] for i in range(3))
        X = (np.arange(x0, x1)[None, :] + 0.5 - cam.cx) / cam.f2
        Y = (cam.cy * 2 - np.arange(y0, y1)[:, None] - 0.5) / cam.f2
        A, B, D, E = U[0] - X * U[2], V[0] - X * V[2], U[1] - Y * U[2], V[1] - Y * V[2]
        F, G = X * O[2] - O[0], Y * O[2] - O[1]
        det = A * E - B * D
        safe = np.where(np.abs(det) > 1e-12, det, 1.0)
        uc, vr = (F * E - B * G) / safe, (A * G - F * D) / safe
        inside = (np.abs(det) > 1e-12) & (uc >= 0) & (uc < C) & (vr >= 0) & (vr < R)
        cols = np.clip(uc.astype(int), 0, C - 1)
        rr = np.clip(vr.astype(int), 0, R - 1)
        key = tuple(rows)
        texture = self.bitmap_cache.get(key)
        if texture is None:
            symbols = sorted(set("".join(rows)))
            codes = {ch: i for i, ch in enumerate(symbols)}
            texture = (np.array([[codes[ch] for ch in row] for row in rows], dtype=np.uint8), symbols)
            if len(self.bitmap_cache) >= 96:
                self.bitmap_cache.clear()
            self.bitmap_cache[key] = texture
        codes, symbols = texture
        palette = np.empty(len(symbols) + 1, dtype=object)
        for i, ch in enumerate(symbols):
            palette[i] = pal.get(ch)
        palette[-1] = None
        idx = np.where(inside, codes[rr, cols], len(symbols))
        colors = palette[idx]
        for i, py in enumerate(range(y0, y1)):
            cy = py >> 1
            row = (s.pb if py & 1 else s.pt)[cy]
            values = colors[i].tolist()
            row[x0:x1] = [c if c is not None else old for c, old in zip(values, row[x0:x1])]
            rc = s.ch[cy]
            for k, c in enumerate(values):
                if c is not None and rc[x0 + k] != " ":
                    rc[x0 + k] = " "
        return corners

    # ------------------------------------------------------------ screens
    def screen_rect(self, P):
        bl, br, tr, tl = P
        x0 = math.ceil(max(bl[0], tl[0])) + 1
        x1 = int(min(br[0], tr[0])) - 1
        y0 = math.ceil(max(tl[1], tr[1]) / 2)
        y1 = int(min(bl[1], br[1]) / 2) - 1
        return x0, y0, x1 - x0 + 1, y1 - y0 + 1

    def screen(self, s, b, P, now, bands, beat):
        idx = b.screen
        tints = {0: (6, 22, 34), 1: (16, 8, 30), 2: (4, 26, 14), 3: (10, 14, 30), 4: (14, 20, 60),
                 5: (6, 18, 30), 6: (24, 6, 22)}
        tint = tints.get(idx, (8, 22, 30))
        fill(s, P, blend(tint, WHITE, 0.04 * beat))
        x, y, w, h = self.screen_rect(P)
        if w < 3 or h < 2:
            # far away: just a glowing panel with a hint of its content colour
            accent = (CYAN, PINK, GREEN, YELLOW, (90, 110, 255), CYAN, PINK)[idx]
            xs = [p[0] for p in P]
            ys = [p[1] for p in P]
            cxp, cyp = sum(xs) / 4, sum(ys) / 4
            s.pixel(int(cxp), int(cyp), blend(tint, accent, 0.6 + 0.4 * pulse(now, 3, idx)))
            return
        st = self.st[idx]
        if idx == 0:
            self.scr_bars(s, x, y, w, h, bands)
        elif idx == 1:
            shapes = ((CUBE_V, CUBE_E), (ICO_V, ICO_E), (OCTA_V, OCTA_E))
            vs, es = shapes[int(now / 8) % 3]
            size = max(1.0, min(h / 2 - 0.6, w / 4 - 0.6))
            draw_wire(s, vs, es, x + w / 2, y + h / 2, size, now * 0.9, now * 1.3, now * 0.4, near=PINK, far=DIM_CYAN)
        elif idx == 2:
            if h >= 3:
                p_radar(s, x, y, w, h, now, st)
        elif idx == 3:
            p_minimap(s, x, y, w, h, now, st)
        elif idx == 4:
            self.tv(s, x, y, w, h, now)
        elif idx == 5:
            self.scr_scope(s, x, y, w, h, now, bands)
        elif idx == 6:
            self.scr_skull(s, x, y, w, h, now, beat)
        # clip anything that spilled out of the screen
        for yy in range(max(0, y - 2), min(s.h, y + h + 2)):
            rc = s.ch[yy]
            inside_row = y <= yy < y + h
            for xx in range(max(0, x - 6), min(s.w, x + w + 6)):
                if rc[xx] != " " and not (inside_row and x <= xx < x + w):
                    rc[xx] = " "
        for yy in range(max(0, y), min(s.h, y + h)):
            rc, rb = s.ch[yy], s.bg[yy]
            for xx in range(max(0, x), min(s.w, x + w)):
                if rc[xx] != " ":
                    rb[xx] = tint

    def scr_bars(self, s, x, y, w, h, bands):
        n = max(2, w // 2)
        bw = max(1, w // n)
        ph = h * 2
        for i in range(n):
            v = min(1.0, bands[int(i * 16 / n)] * 1.1)
            hh = max(1, int(v * ph))
            for k in range(hh):
                col = blend(CYAN, PINK, k / max(1, ph - 1))
                prect(s, x + i * bw, (y + h) * 2 - 1 - k, max(1, bw - (1 if bw > 1 else 0)), 1, col)
            # peak cap
            prect(s, x + i * bw, (y + h) * 2 - 2 - hh, max(1, bw - (1 if bw > 1 else 0)), 1, WHITE)

    def scr_scope(self, s, x, y, w, h, now, bands):
        ph = h * 2
        mid = y * 2 + ph / 2
        lvl = sum(bands) / 16 + 0.15
        for k, (col, f, sp) in enumerate(((CYAN, 0.35, 5.0), (YELLOW, 0.21, -3.2))):
            prev = None
            for i in range(w):
                vv = math.sin(i * f + now * sp) * lvl * (1.3 - k * 0.5) + math.sin(i * f * 2.3 - now * 7) * 0.15
                py = int(mid + vv * (ph / 2 - 1))
                py = max(y * 2, min(y * 2 + ph - 1, py))
                if prev is not None:
                    for t in range(min(prev, py), max(prev, py) + 1):
                        s.pixel(x + i, t, blend(col, BLACK, 0.4))
                s.pixel(x + i, py, col)
                prev = py
        for i in range(0, w, 4):
            s.pixel(x + i, int(mid), (30, 60, 70))

    def scr_skull(self, s, x, y, w, h, now, beat):
        ph = h * 2
        sc = max(1, min(w // 22, (ph - 2) // 15))
        sw, sh = 22 * sc, 15 * sc
        ox, oy = x + (w - sw) // 2, y * 2 + max(0, (ph - 2 - sh) // 2)
        if sw > w or sh > ph:
            # too small for the skull: a pulsing pink core
            s.pixel(x + w // 2, y * 2 + ph // 2, blend(PINK, WHITE, beat))
        else:
            col = blend(PINK, WHITE, 0.2 + 0.5 * beat)
            for r, row in enumerate(SKULL):
                for c, ch in enumerate(row):
                    if ch == "X":
                        prect(s, ox + c * sc, oy + r * sc, sc, sc, col)
        p = (now * 0.07) % 1.0
        bw = max(1, int(w * p))
        prect(s, x, (y + h) * 2 - 1, bw, 1, GREEN)

    def tv(self, s, x, y, w, h, now):
        cx = x + w // 2
        if h >= 4:
            # studio backdrop, anchor and an inset showing the DedSec skull
            prect(s, x, y * 2, w, h * 2, (20, 26, 70))
            prect(s, x, (y + h) * 2 - 6, w, 3, (40, 30, 90))
            hr = max(1.5, h * 0.32)
            ay = (y + h * 0.48) * 2
            prect(s, cx - int(hr * 1.9), int(ay + hr), int(hr * 3.8), int((y + h) * 2 - ay - hr) - 2, (40, 40, 80))
            s.pixel_circle(cx, ay, hr, (190, 140, 120))
            prect(s, cx - int(hr), int(ay - hr), int(hr * 2), max(1, int(hr * 0.6)), (50, 30, 26))
            if w > 16:
                iw, ih = max(6, w // 4), max(4, h)
                ix = x + w - iw - 1
                prect(s, ix, y * 2 + 2, iw, ih, (90, 10, 50))
                sc = 1
                if iw >= 22 * sc and ih >= 15:
                    for r, row in enumerate(SKULL):
                        for c, ch in enumerate(row):
                            if ch == "X":
                                s.pixel(ix + (iw - 22) // 2 + c, y * 2 + 2 + (ih - 15) // 2 + r, (240, 220, 235))
                else:
                    s.pixel_circle(ix + iw / 2, y * 2 + 2 + ih / 2, min(iw / 2, ih / 2) - 1, (240, 220, 235))
        head = "SFN LIVE" if w < 22 else "SFN LIVE // BREAKING"
        s.text(x, y, head[:w], WHITE if int(now * 2) % 2 else PINK)
        txt = "  ///  ".join(TV_NEWS) + "  ///  "
        off = int(now * 9) % len(txt)
        line = (txt + txt)[off:off + w]
        s.text(x, y + h - 1, line, YELLOW)
        for xx in range(x, x + w):
            s.set_bg(xx, y + h - 1, (90, 10, 40))

    # ------------------------------------------------------------ props
    def printer(self, s, b, now):
        cam = self.cam
        cx, cz = b.c
        base = b.y0 + 0.12
        fc = (130, 134, 156)
        corners = [(cx - 0.65, cz - 0.65), (cx + 0.65, cz - 0.65), (cx + 0.65, cz + 0.65), (cx - 0.65, cz + 0.65)]
        top = base + 1.8
        for x, z in corners:
            line3(s, cam, (x, base, z), (x, top, z), fc)
        for i in range(4):
            a, c = corners[i - 1], corners[i]
            line3(s, cam, (a[0], top, a[1]), (c[0], top, c[1]), fc)
        name, prof = PRINTS[self.print_i]
        dur = 24.0
        el = now - self.print_t
        if el > dur + 4:
            self.print_i = (self.print_i + 1) % len(PRINTS)
            self.print_t = now
            el = 0
        p = min(1.0, el / dur)
        self.print_state = (name, p)
        NL = 28
        hstep = 1.25 / NL
        if not cam.proj((cx, base, cz)):
            return
        done = int(p * NL)
        for i in range(done + 1):
            u = i / NL
            if i == done and p >= 1:
                break
            qq = cam.proj((cx, base + i * hstep, cz))
            if not qq:
                continue
            hw = prof(u) * 0.5 * cam.f2 / qq[2]
            ph = max(1, int(hstep * cam.f2 / qq[2] + 0.99))
            if i == done:
                col = blend(ORANGE, YELLOW, pulse(now, 9))
                hw *= (el / dur * NL) % 1.0
            else:
                col = blend(PINK, PURPLE, (i % 4) / 6)
            prect(s, qq[0] - hw, qq[1] - ph, max(1, int(hw * 2)), ph, col)
        ny = base + min(done, NL) * hstep + 0.12
        line3(s, cam, (cx - 0.65, ny, cz), (cx + 0.65, ny, cz), (170, 170, 190))
        if p < 1:
            nx = cx + math.sin(now * 7) * 0.45 * prof(min(0.99, p))
            qn = cam.proj((nx, ny, cz))
            if qn:
                sz = max(1, int(0.18 * cam.f2 / qn[2]))
                prect(s, qn[0] - sz, qn[1] - sz, sz * 2, sz, (190, 190, 210))
                s.pixel(int(qn[0]), int(qn[1]), ORANGE)
                if random.random() < 0.15:
                    self.parts.add(qn[0], qn[1] / 2, random.uniform(-2, 2), -random.uniform(1, 3), 0.6, "·", ORANGE)
        elif int(now * 4) % 2:
            qt = cam.proj((cx, base + 1.5, cz))
            if qt:
                s.text(int(qt[0]) - 2, int(qt[1] / 2), "DONE", GREEN)

    def rack_leds(self, s, b, now, beat):
        cam = self.cam
        cx, cz = b.c
        z = cz - 0.81
        if cam.pos[2] > z:
            return
        for i, (a, ph) in enumerate(self.leds):
            r, c = i // 5, i % 5
            q = cam.proj((cx - 0.5 + c * 0.25, 0.4 + r * 0.6, z))
            if not q:
                continue
            on = math.sin(now * (2 + a * 9) + ph * 20) > 0.2 - a * 0.5 - beat * 0.3
            col = (GREEN if a > 0.3 else (ORANGE if a > 0.12 else CYAN)) if on else (20, 40, 26)
            sz = max(1, int(0.08 * cam.f2 / q[2]))
            prect(s, q[0], q[1], sz, sz, col)
        # unit seams
        for r in range(7):
            line3(s, cam, (cx - 0.62, 0.2 + r * 0.6, z), (cx + 0.62, 0.2 + r * 0.6, z), (60, 66, 84))

    def lamp_cone(self, s, now):
        cam = self.cam
        line3(s, cam, (-8.75, 1.48, 11.9), (-8.95, 2.3, 11.95), (150, 150, 170))
        line3(s, cam, (-8.95, 2.3, 11.95), (-8.75, 2.35, 11.65), (150, 150, 170))

    def mask_sprite(self, s, now, K):
        if now > self.next_eyes:
            self.eyes = random.choice(EYES)
            self.next_eyes = now + random.uniform(1.6, 4.0)
            self.blink_until = now + 0.14
        le, re = ("-", "-") if now < self.blink_until else self.eyes
        rows = []
        for r, row in enumerate(MASK):
            line = ""
            for c, ch in enumerate(row):
                if ch in "12":
                    g = GLYPH[le if ch == "1" else re]
                    gr, gc = r - 5, (c - 2) if ch == "1" else (c - 8)
                    line += "e" if g[gr][gc] == "e" else "d"
                else:
                    line += ch
            rows.append(line)
        lt = self.light_at((-7.75, 5.6, 12.4), K)
        led = blend(PINK, CYAN, pulse(now, 0.9)) if int(now * 7) % 23 else WHITE
        pal = {"k": mul((40, 38, 48), lt), "h": mul((120, 120, 140), lt), "g": mul((80, 80, 92), lt),
               "e": led, "d": blend(led, BLACK, 0.85)}
        tex = 0.09
        corners = self.bitmap(s, (-7.75 - 7 * tex, 5.07 + 15 * tex, 12.45), (tex, 0, 0), (0, -tex, 0), rows, pal)
        if corners and (corners[1][0] - corners[0][0]) < 15:
            # too small for the LED pixels to read: show the expression as text
            for k, ec in ((0, 3.5), (1, 10.5)):
                q = self.cam.proj((-7.75 - 7 * tex + ec * tex, 5.07 + 15 * tex - 7 * tex, 12.44))
                if q:
                    s.put(int(q[0]), int(q[1] / 2), (le, re)[k], led)

    def plant(self, s, x, z, scale, K, yv=0.0):
        lt = self.light_at((x, 1.0, z), K)
        pal = {"g": mul((40, 150, 60), lt), "G": mul((80, 210, 90), lt), "s": mul((90, 70, 40), lt)}
        tex = 0.11 * scale
        self.bitmap(s, (x - 6 * tex, yv + 15 * tex + 0.55, z), (tex, 0, 0), (0, -tex, 0), PLANT, pal)

    def pizza_top(self, s, b, K):
        lt = self.light_at((b.c[0], 0.3, b.c[1]), K)
        pal = {"c": mul((210, 140, 60), lt), "y": mul((250, 200, 70), lt), "r": mul((200, 40, 30), lt)}
        tex = 0.1
        self.bitmap(s, (b.c[0] - 5 * tex, 0.085, b.c[1] + 4.5 * tex), (tex, 0, 0), (0, 0, -tex), PIZZA, pal)

    # ------------------------------------------------------------ actors
    def robot_step(self, now, dt):
        r = self.robot
        if now < r["pause"]:
            return
        r["x"] += r["dir"] * dt * 0.9
        if r["x"] > 5.6 or r["x"] < -5.6:
            r["x"] = max(-5.6, min(5.6, r["x"]))
            r["dir"] *= -1
            r["pause"] = now + 1.6

    def robot_sprite(self, s, now, K):
        r = self.robot
        x, z = r["x"], 7.7
        rows = list(ROBOT)
        if int(r["x"] * 12) % 2:
            rows[14], rows[15] = rows[15], rows[14]
        if now < r["pause"]:
            wave = int(now * 6) % 2
            rows[11] = ("a" if wave else ".") + rows[11][1:-1] + ("." if wave else "a")
            rows[12] = ("." if wave else "a") + rows[12][1:-1] + ("a" if wave else ".")
        if int(now * 2) % 2:
            rows[0] = rows[0].replace("r", "R")
        blink = int(now * 3.3) % 11 == 0
        lt = self.light_at((x, 0.6, z), K)
        pal = {"w": mul((225, 228, 236), lt), "o": mul((240, 130, 30), lt), "y": mul((40, 40, 50), lt),
               "p": PINK if int(now * 4) % 2 else CYAN, "E": (20, 30, 40) if blink else CYAN,
               "m": mul((50, 50, 60), lt), "g": mul((140, 140, 150), lt), "T": (24, 24, 30),
               "t": mul((90, 90, 100), lt), "a": mul((170, 170, 180), lt), "n": mul((150, 150, 160), lt),
               "r": (120, 20, 20), "R": (255, 50, 50)}
        tex = 0.065
        bob = abs(math.sin(now * 9)) * 0.015 if now >= r["pause"] else 0
        self.bitmap(s, (x - 7 * tex, 16 * tex + bob, z), (tex, 0, 0), (0, -tex, 0), rows, pal)
        self.robot_pos = (x, z, r["dir"])

    def cat_state(self, now):
        """40 s loop: walk right, hop onto the couch, nap, hop down, walk back."""
        t = (now - self.cat_t0) % 44.0
        z = 9.0
        if t < 12:
            u = t / 12
            return (-8.2 + 15.0 * u, 0.0, z, 1, "walk")
        if t < 13.2:
            u = (t - 12) / 1.2
            return (6.8 + 1.4 * u, 0.5 * u + 0.6 * math.sin(u * math.pi), z - 1.6 * u, 1, "hop")
        if t < 26:
            return (8.2, 0.66, 7.4, 1, "sit")
        if t < 27.2:
            u = (t - 26) / 1.2
            return (8.2 - 1.4 * u, 0.66 * (1 - u) + 0.5 * math.sin(u * math.pi), 7.4 + 1.6 * u, -1, "hop")
        if t < 39.2:
            u = (t - 27.2) / 12
            return (6.8 - 15.0 * u, 0.0, z, -1, "walk")
        return None

    def cat_sprite(self, s, now, K, st):
        x, y, z, d, mode = st
        if mode == "sit":
            rows = list(CAT_SIT)
            if int(now * 1.5) % 2:
                rows[8], rows[9] = ".kkkkkk.k.", ".kkkkkkkk."
            if int(now * 0.7) % 5 == 0:
                rows[3] = "kkkkk....."
        else:
            rows = CAT_WALK[int(now * 6) % 2] if mode == "walk" else CAT_WALK[1]
        if d > 0:
            rows = [r[::-1] for r in rows]
        lt = self.light_at((x, 0.5, z), K)
        pal = {"k": mul((34, 30, 44), lt), "g": (170, 255, 60)}
        tex = 0.06
        wdt = len(rows[0])
        self.bitmap(s, (x - wdt / 2 * tex, y + len(rows) * tex, z), (tex, 0, 0), (0, -tex, 0), rows, pal)

    def bulbs(self, s, now, beat, K):
        cam = self.cam
        pal = (PINK, CYAN, YELLOW, (255, 170, 80), GREEN, PURPLE)
        shift = int(now * 2.5)
        wire = (70, 64, 76)
        bright = min(1.0, 0.65 + 0.35 * beat)
        if now < self.blackout:
            bright *= 0.4
        for k, pts in enumerate(self.strands):
            prev = None
            for i, p in enumerate(pts):
                q = cam.proj(p)
                if prev is not None and q is not None:
                    pline(s, prev[0], prev[1], q[0], q[1], wire)
                prev = q
                if q is None or i == 0 or i == len(pts) - 1:
                    continue
                x, y = int(q[0]), int(q[1])
                if not (0 <= x < s.w and 0 <= y < s.ph):
                    continue
                col = pal[(i + k + shift) % len(pal)]
                core = blend(col, WHITE, 0.5 * bright)
                r = 0.09 * cam.f2 / q[2]
                halo = 0.55 * bright
                for hx, hy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    old = s.get_pixel(hx, hy) or BLACK
                    s.pixel(hx, hy, blend(old, col, halo))
                if r >= 1.6:
                    for hx, hy in ((x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1)):
                        old = s.get_pixel(hx, hy) or BLACK
                        s.pixel(hx, hy, blend(old, col, halo * 0.6))
                s.pixel(x, y, blend(BLACK, core, 0.4 + 0.6 * bright))

    # ------------------------------------------------------------ camera
    def camera(self, t):
        n = len(KEYS)
        f = t / KEY_T
        i = int(f) % n
        u = f - int(f)
        u = u * u * (3 - 2 * u) * 0.35 + u * 0.65          # gentle ease into every key
        P = [KEYS[(i + k) % n] for k in (-1, 0, 1, 2)]

        def cr(a, b, c, d):
            return 0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)

        v = [cr(P[0][k], P[1][k], P[2][k], P[3][k]) for k in range(5)]
        cam = self.cam
        cam.pos = [v[0] + 0.08 * math.sin(t * 0.7), v[1] + 0.05 * math.sin(t * 0.9), v[2]]
        cam.yaw = v[3] + 0.015 * math.sin(t * 0.53)
        cam.pitch = v[4]
        cam.setup()
        self.cam_label = KEYS[(i + (1 if u > 0.5 else 0)) % n][5]

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        t = now - self.t0
        bands, beat, level = self.audio(now)
        glitch = self.glitch.active(now)
        if beat > 0.9 and random.random() < 0.02:
            self.blackout = now + random.uniform(0.05, 0.12)
        if random.random() < 0.012:
            self.sign_dead = (random.randrange(6), now + random.uniform(0.1, 0.5))
        if random.random() < 0.2 and self.window_lit:
            # a skyline window switches on or off
            wy, wx = random.choice(self.window_lit)
            img = self.window[3]
            img[wy, wx] = (240, 190, 100) if img[wy, wx, 0] < 100 else (18, 18, 44)
        self.camera(t)
        cam = self.cam
        K = self.light_levels(now, beat)

        # per-face lighting for every static box
        lc = self.light_col * K[:, None]
        L = AMBIENT[None, :] * self.face_form + self.face_F @ lc
        cols = np.clip(self.face_alb * L * 1.12, 0, 255).astype(np.int32) & 0xFC
        cols = [tuple(c) for c in cols.tolist()]
        fi = 0
        for b in self.static:
            if b.emit:
                b.fc = [b.col] * 5
            else:
                b.fc = cols[fi:fi + 5]
            fi += 5

        self.shell(s, now, K, beat)

        self.robot_step(now, dt)
        cat = self.cat_state(now)
        items = []
        px, py, pz = cam.pos
        for seq, b in enumerate(self.static):
            c = b.center()
            items.append(((c[0] - px) ** 2 + (c[1] - py) ** 2 + (c[2] - pz) ** 2, seq, "box", b))
        sprites = [((-7.75, 5.6, 12.45), "mask"), ((0.75, 1.0, 12.3), "plant1"), ((9.0, 1.0, 4.4), "plant2"),
                   ((self.robot["x"], 0.5, 7.7), "robot")]
        if cat:
            sprites.append(((cat[0], cat[1] + 0.3, cat[2] - 0.2), "cat"))
        for k, (p, name) in enumerate(sprites):
            items.append(((p[0] - px) ** 2 + (p[1] - py) ** 2 + (p[2] - pz) ** 2, 1000 + k, name, None))
        items.sort(key=lambda it: (-it[0], it[1]))
        for d, _, kind, obj in items:
            if kind == "box":
                drawn = self.draw_box(s, obj)
                if not drawn:
                    continue
                if obj.screen is not None:
                    for k, quad, P in drawn:
                        if k == "front":
                            self.screen(s, obj, P, now, bands, beat)
                tag = obj.tag
                if tag == "rack":
                    self.rack_leds(s, obj, now, beat)
                elif tag == "printer":
                    self.printer(s, obj, now)
                elif tag == "pizza":
                    self.pizza_top(s, obj, K)
                elif tag == "lamp":
                    self.lamp_cone(s, now)
                elif tag == "console" and int(now * 1.5) % 2:
                    q = cam.proj((obj.c[0] + 0.3, 0.85, obj.c[1] - 0.28))
                    if q:
                        s.pixel(int(q[0]), int(q[1]), GREEN)
            elif kind == "mask":
                self.mask_sprite(s, now, K)
            elif kind == "plant1":
                self.plant(s, 0.75, 12.0, 1.25, K, 0.05)
            elif kind == "plant2":
                self.plant(s, 9.0, 4.4, 1.0, K)
            elif kind == "robot":
                self.robot_sprite(s, now, K)
            elif kind == "cat":
                self.cat_sprite(s, now, K, cat)
        self.bulbs(s, now, beat, K)
        self.parts.step(s, dt)
        text_over_pixels(s)
        self.hud(s, now, level, cat)
        postfx(s, now, glitch)

    def hud(self, s, now, level, cat):
        w, h = self.w, self.h
        s.text(1, 0, "▌DEDSEC HACKERSPACE", PINK)
        if w >= 100:
            s.text(21, 0, "// SAN FRANCISCO", GREY)
        name, p = self.print_state
        mood = "".join(self.eyes)
        msgs = ["3D PRINTER: %s %d%%" % (name, p * 100) if p < 1 else "3D PRINTER: %s DONE" % name,
                "J-BOT: PATROLLING SECTOR PIZZA", "WRENCH MASK MOOD: %s" % mood,
                "MEMBERS ONLINE: 4   //   PIZZA RESERVES: LOW",
                "CAT.EXE: %s" % ("NAPPING ON THE COUCH" if cat and cat[4] == "sit" else ("ON PATROL" if cat else "HIDING"))]
        if now > self.msg_next:
            self.msg_i = (self.msg_i + 1) % len(msgs)
            self.msg_next = now + 4
        m = "> " + msgs[self.msg_i % len(msgs)]
        s.text(1, h - 1, m[:w - 2], YELLOW)
        rec = self.cam_label + ("  ● REC" if int(now * 2) % 2 else "    REC")
        if w < 80:
            rec = rec[:6] + rec[-6:]
        s.text(w - len(rec) - 1, 0, rec, PINK)
        np_ = DATA.now_playing()
        if np_ and w >= 90:
            tline = ("NOW PLAYING: " + np_)[:w // 2]
            s.text(w - len(tline) - 1, h - 1, tline, CYAN)
        else:
            vu = int(min(1.0, level * 1.6) * 10)
            bar = "VU " + "▮" * vu + "▯" * (10 - vu)
            if w - len(bar) - 1 > len(m) + 2:
                s.text(w - len(bar) - 1, h - 1, bar, CYAN)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "blackout", "DEDSEC // LIGHTS OUT", PURPLE)
        if .05 < t < .7:
            x, y = s.w // 2, s.h // 2
            s.put(x, y, "_" if t < .38 else ".", blend(GREEN, BLACK, t))

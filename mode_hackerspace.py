"""HACKERSPACE: a slow camera dolly through the DedSec hideout, in solid 3D with live monitors."""

import math
import random
import time
from functools import lru_cache

import numpy as np

from engine3d import clip2d
from lib import (BLACK, CYAN, DIM_CYAN, DIM_PINK, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, blend, pulse)
from mode_logo import FONT, NEWS, SKULL
from sysdata import DATA
from widgets import CUBE_E, CUBE_V, ICO_E, ICO_V, OCTA_E, OCTA_V, PARTIAL, Particles, draw_wire, p_minimap, p_radar

NAME = "HACKERSPACE"

NEAR = 0.2
X0, X1, Z0, Z1, YC = -10.0, 10.0, -2.0, 13.0, 7.0     # room box

WALL_BACK = (58, 34, 62)
WALL_SIDE = (46, 36, 66)
FLOOR = (36, 30, 42)
CEIL = (20, 18, 30)
WOOD = (92, 58, 40)
METAL = (70, 74, 92)
DARKM = (34, 34, 46)
CARD = (168, 120, 70)

TV_NEWS = NEWS + ["DedSec denies stealing every office stapler in SF", "Local cat elected mayor of the internet",
                  "Blume: 'ctOS is totally fine, please stop asking'", "Pizza delivery drones now 40% more punctual"]
EYES = ["^ ^", "X X", "> <", "o o", "- -", "@ @", "? ?", "* *", "$ $", "0 0"]
PRINTS = [("SKULL KEYCHAIN", lambda u: 0.55 + 0.45 * math.sin(min(1, u * 1.2) * math.pi) if u < 0.85 else 0.25),
          ("J-BOT SPARE HEAD", lambda u: 0.9 if u < 0.7 else 0.5),
          ("DEDSEC TROPHY", lambda u: 0.8 - u * 0.5 if u < 0.6 else 0.45 + 0.4 * math.sin((u - 0.6) * 7.8)),
          ("TINY VASE", lambda u: 0.45 + 0.35 * math.sin(u * 5))]


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
        # Between vertex rows a convex polygon has the same two active edges.
        # Walk these spans without searching every edge for every pixel row.
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
        intersections = [offset + yc * slope for ay, by, offset, slope in edges if ay <= yc < by]
        if len(intersections) < 2:
            continue
        lo, hi = intersections[0], intersections[1]
        if lo > hi:
            lo, hi = hi, lo
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


def fill_alpha(s, P, col, a):
    ys = [p[1] for p in P]
    y0, y1 = max(0, int(min(ys))), min(s.ph - 1, int(max(ys)))
    n, W = len(P), s.w - 1
    r, g, b = col
    memo = {}
    for py in range(y0, y1 + 1):
        yc = py + 0.5
        lo, hi = 1e9, -1e9
        for i in range(n):
            ax, ay = P[i]
            bx, by = P[i - 1]
            if (ay <= yc < by) or (by <= yc < ay):
                x = ax + (yc - ay) / (by - ay) * (bx - ax)
                if x < lo:
                    lo = x
                if x > hi:
                    hi = x
        xa, xb = max(0, int(lo + 0.5)), min(W, int(hi + 0.5) - 1)
        if xb < xa:
            continue
        row = (s.pb if py & 1 else s.pt)[py >> 1]
        for x in range(xa, xb + 1):
            c = row[x] or BLACK
            o = memo.get(c)
            if o is None:
                o = memo[c] = (min(255, int(c[0] + (r - c[0]) * a)), min(255, int(c[1] + (g - c[1]) * a)),
                               min(255, int(c[2] + (b - c[2]) * a)))
            row[x] = o


def pline(s, x0, y0, x1, y1, col):
    # Reject invisible strokes cheaply; most masonry joints miss the viewport.
    if max(x0,x1) < 0 or min(x0,x1) >= s.w or max(y0,y1) < 0 or min(y0,y1) >= s.ph:
        return
    if 0 <= x0 < s.w and 0 <= x1 < s.w and 0 <= y0 < s.ph and 0 <= y1 < s.ph:
        ta,tb=0.,1.
    else:
        c = clip2d(x0, y0, x1, y1, s.w, s.ph)
        if not c:
            return
        ta,tb=c
    dx,dy=x1-x0,y1-y0
    ax,ay=x0+dx*ta,y0+dy*ta
    bx,by=x0+dx*tb,y0+dy*tb
    n=int(max(abs(bx-ax),abs(by-ay)))+1
    sx,sy=(bx-ax)/n,(by-ay)/n
    pt,pb=s.pt,s.pb
    if abs(bx-ax) >= 24 and abs(by-ay) <= 8:
        # DDA samples sharing a pixel row form a contiguous run. Write the run
        # once instead of revisiting every width cell of every brick course.
        i=0
        while i <= n:
            py=int(ay+sy*i)
            if abs(sy) < 1e-10:
                j=n
            elif sy > 0:
                j=min(n,max(i,math.ceil((py+1-ay)/sy)-1))
            else:
                j=min(n,max(i,math.floor((py-ay)/sy)))
            xa,xb=int(ax+sx*i),int(ax+sx*j)
            if xa>xb:xa,xb=xb,xa
            xa,xb=max(0,xa),min(s.w-1,xb)
            if 0 <= py < s.ph and xb>=xa:
                (pb if py&1 else pt)[py>>1][xa:xb+1]=span(col,xb-xa+1)
            i=j+1
    else:
        for i in range(n+1):
            x,py=int(ax+sx*i),int(ay+sy*i)
            if 0 <= x < s.w and 0 <= py < s.ph:
                (pb if py&1 else pt)[py>>1][x]=col


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
        (s.pb if yy & 1 else s.pt)[yy >> 1][x0:x1] = [col] * (x1 - x0)


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
    span = s.h + 16
    by = int((now * speed) % span) - 8
    for k, t in ((0, 0.16), (-1, 0.08), (1, 0.08)):
        tint_rows(s, by + k, by + k + 1, WHITE, t)
    if glitch:
        for _ in range(random.randint(1, 4)):
            y0 = random.randrange(s.h)
            dx = random.randint(-10, 10)
            n = random.randint(1, 3)
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


# ---------------------------------------------------------------- scene objects

class Box:
    __slots__ = ("c", "y0", "size", "col", "yaw", "screen", "edge", "glow", "tag", "_faces", "bound")

    def __init__(self, cx, y0, cz, sx, sy, sz, col, yaw=0.0, screen=None, edge=None, glow=0.0, tag=None):
        self.c = (cx, cz)
        self.y0 = y0
        self.size = (sx, sy, sz)
        self.col, self.yaw, self.screen, self.edge, self.glow, self.tag = col, yaw, screen, edge, glow, tag
        self._faces = None
        self.bound = (self.center(), math.sqrt((sx * sx + sy * sy + sz * sz) / 4))

    def center(self):
        return (self.c[0], self.y0 + self.size[1] / 2, self.c[1])

    def faces(self):
        """Yields (normal, quad) for the 5 faces that can be seen (no bottom)."""
        if self._faces is not None:
            return self._faces
        cx, cz = self.c
        hx, hy, hz = self.size[0] / 2, self.size[1], self.size[2] / 2
        cs, sn = math.cos(self.yaw), math.sin(self.yaw)

        def P(dx, y, dz):
            return (cx + dx * cs - dz * sn, self.y0 + y, cz + dx * sn + dz * cs)

        def N(nx, nz):
            return (nx * cs - nz * sn, 0.0, nx * sn + nz * cs)

        faces = []
        faces.append((N(0, -1), [P(-hx, 0, -hz), P(hx, 0, -hz), P(hx, hy, -hz), P(-hx, hy, -hz)], "front"))
        faces.append((N(0, 1), [P(hx, 0, hz), P(-hx, 0, hz), P(-hx, hy, hz), P(hx, hy, hz)], "back"))
        faces.append((N(-1, 0), [P(-hx, 0, hz), P(-hx, 0, -hz), P(-hx, hy, -hz), P(-hx, hy, hz)], "left"))
        faces.append((N(1, 0), [P(hx, 0, -hz), P(hx, 0, hz), P(hx, hy, hz), P(hx, hy, -hz)], "right"))
        faces.append(((0.0, 1.0, 0.0), [P(-hx, hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), P(-hx, hy, hz)], "top"))
        self._faces = faces
        return faces

def face_light(n):
    if n[1] > 0.5:
        return 1.0
    return 0.52 + 0.33 * max(0.0, -n[2]) + 0.12 * abs(n[0])


def bitmap_from_font(word):
    rows = [""] * 5
    for ch in word:
        for i, line in enumerate(FONT[ch]):
            rows[i] += "".join("#" if c != " " else "." for c in line) + "."
    return [r[:-1] for r in rows]


def dilate(rows):
    h, w = len(rows), len(rows[0])
    out = []
    for r in range(-1, h + 1):
        line = ""
        for c in range(-1, w + 1):
            hit = any(0 <= r + dy < h and 0 <= c + dx < w and rows[r + dy][c + dx] != "."
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            line += "#" if hit else "."
        out.append(line)
    return out


POSTER_EYE = [
    "bbbbbbbbb",
    "bbbbybbbb",
    "bbbyyybbb",
    "bbyywyybb",
    "byywkwyyb",
    "yywkkkwyy",
    "byywkwyyb",
    "bbyywyybb",
    "pppppppp.",
    "p.pp.pp.p",
    "bbbbbbbbb",
]
POSTER_BARS = ["pppppp", "pppppp", "cccccc", "cc..cc", "yyyyyy", "y.yy.y", "pppppp", "kkkkkk", "cccccc", "cc.ccc"]


# ---------------------------------------------------------------- the mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = Cam(w, h, fov=0.85)
        self.glitch = Glitch(0.004)
        self.parts = Particles(300)
        self.last = self.t0 = time.time()
        self.rnd = random.Random(42)
        self.sign = bitmap_from_font("DEDSEC")
        self.sign_halo = dilate(self.sign)
        self.graffiti = bitmap_from_font("DS")
        self.skull = ["".join("w" if ch == "X" else "p" for ch in row) for row in SKULL]
        self.window = self.make_window()
        self.static = self.build()
        self.st = [{} for _ in range(6)]
        self.bars = [0.0] * 16
        self.robot = {"i": 0, "t": 0.0}
        self.path = [(-1.0, 4.6), (6.5, 4.4), (7.5, 5.0), (0.6, 5.2), (0.0, 8.6), (-4.0, 8.4), (-6.0, 6.0), (-5.0, 4.4)]
        self.cat_t = self.t0 + random.uniform(6, 12)
        self.eyes = random.choice(EYES)
        self.next_eyes = self.t0 + 2
        self.print_i = random.randrange(len(PRINTS))
        self.print_t = self.t0 - random.uniform(0, 15)
        self.dim = 1.0
        self.blackout = 0.0
        self.msg_i = 0
        self.leds = [(self.rnd.random(), self.rnd.random()) for _ in range(28)]

    def make_window(self):
        r = self.rnd
        cols, rows = 26, 13
        hts = []
        hgt = r.randint(3, 8)
        for c in range(cols):
            if r.random() < 0.3:
                hgt = max(2, min(rows - 2, hgt + r.randint(-3, 3)))
            hts.append(hgt)
        out = []
        for rr in range(rows):
            line = ""
            for c in range(cols):
                if rows - rr <= hts[c]:
                    line += "l" if r.random() < 0.28 else "k"
                else:
                    line += "s" if rr < rows // 2 else "t"
            out.append(line)
        return out

    def build(self):
        B = []
        # desk + cabinets + monitors
        B.append(Box(-5.5, 1.42, 11.8, 8.2, 0.14, 2.0, WOOD, edge=(150, 100, 70)))
        B.append(Box(-8.9, 0.0, 11.8, 1.2, 1.42, 1.8, DARKM))
        B.append(Box(-2.1, 0.0, 11.8, 1.2, 1.42, 1.8, DARKM))
        mons = [(-8.0, 1.75, 12.0, 0.35, 0), (-5.5, 1.75, 12.3, 0.0, 1), (-3.0, 1.75, 12.0, -0.35, 2),
                (-5.5, 3.45, 12.4, 0.0, 3)]
        for x, y, z, yaw, idx in mons:
            B.append(Box(x, y - 0.33, z + 0.1, 0.25, 0.33, 0.25, DARKM))
            B.append(Box(x, y, z, 2.45, 1.55, 0.14, (24, 24, 34), yaw=yaw, screen=idx, edge=(80, 80, 110)))
        B.append(Box(-7.6, 1.56, 11.2, 0.9, 0.12, 0.35, (40, 40, 52), edge=PINK))       # keyboard
        B.append(Box(-3.4, 1.56, 11.2, 0.25, 0.32, 0.25, (200, 40, 40)))                  # soda can
        # gaming chair
        B.append(Box(-4.4, 0.0, 9.6, 0.25, 0.85, 0.25, DARKM))
        B.append(Box(-4.4, 0.85, 9.6, 1.4, 0.25, 1.3, (60, 20, 40)))
        B.append(Box(-4.4, 1.1, 9.0, 1.4, 1.9, 0.25, (80, 22, 52), edge=PINK))
        # couch facing the TV
        purple = (72, 44, 110)
        B.append(Box(5.0, 0.0, 6.9, 7.0, 0.85, 1.9, purple))
        B.append(Box(5.0, 0.85, 6.15, 7.0, 1.15, 0.45, (86, 52, 128), edge=(130, 90, 180)))
        B.append(Box(1.75, 0.85, 6.9, 0.5, 0.55, 1.9, (86, 52, 128)))
        B.append(Box(8.25, 0.85, 6.9, 0.5, 0.55, 1.9, (86, 52, 128)))
        B.append(Box(3.4, 0.85, 7.0, 2.6, 0.22, 1.3, (100, 64, 140)))
        B.append(Box(6.6, 0.85, 7.0, 2.6, 0.22, 1.3, (100, 64, 140)))
        # coffee table with pizza and cans
        B.append(Box(5.0, 0.62, 9.4, 3.6, 0.12, 1.4, WOOD, edge=(150, 100, 70)))
        B.append(Box(3.5, 0.0, 9.4, 0.2, 0.62, 1.1, DARKM))
        B.append(Box(6.5, 0.0, 9.4, 0.2, 0.62, 1.1, DARKM))
        B.append(Box(4.3, 0.74, 9.4, 1.3, 0.12, 1.3, CARD, yaw=0.2, edge=(220, 170, 110)))
        B.append(Box(4.3, 0.86, 9.4, 1.3, 0.12, 1.3, CARD, yaw=-0.1, edge=(220, 170, 110)))
        B.append(Box(6.0, 0.74, 9.2, 0.22, 0.34, 0.22, (40, 200, 90)))
        B.append(Box(6.4, 0.74, 9.6, 0.22, 0.34, 0.22, (40, 160, 230)))
        B.append(Box(-1.5, 0.0, 5.0, 1.3, 0.12, 1.3, CARD, yaw=0.5, edge=(220, 170, 110)))   # floor pizza
        B.append(Box(-0.6, 0.0, 5.6, 0.22, 0.34, 0.22, (230, 60, 60)))
        B.append(Box(2.8, 0.0, 3.4, 0.34, 0.22, 0.22, (240, 200, 40), yaw=1.2))             # fallen can
        # TV + cabinet + console
        B.append(Box(5.5, 0.0, 12.55, 6.0, 0.9, 0.9, (40, 30, 34), edge=(90, 70, 70)))
        B.append(Box(4.5, 0.9, 12.6, 0.9, 0.18, 0.6, (20, 20, 26), edge=GREEN, tag="console"))
        B.append(Box(5.5, 1.9, 12.85, 5.2, 2.9, 0.12, (16, 16, 22), screen=4, edge=(70, 70, 90)))
        # server rack in the corner
        B.append(Box(9.2, 0.0, 10.5, 1.3, 4.4, 1.6, (30, 32, 42), edge=(70, 80, 100), tag="rack"))
        # left wall: shelf with Wrench's mask, printer table
        B.append(Box(-9.65, 3.0, 8.6, 0.7, 0.1, 3.4, WOOD, edge=(150, 100, 70)))
        B.append(Box(-9.6, 3.1, 8.6, 0.55, 0.75, 0.6, (22, 22, 26), edge=(60, 60, 70), tag="mask"))
        for dz in (-0.2, 0.0, 0.2):
            B.append(Box(-9.6, 3.85, 8.6 + dz, 0.12, 0.22, 0.08, (60, 60, 70)))
        B.append(Box(-9.6, 3.1, 7.4, 0.22, 0.5, 0.22, (240, 20, 120)))
        B.append(Box(-9.6, 3.1, 7.75, 0.22, 0.5, 0.22, (0, 200, 230)))
        B.append(Box(-9.6, 3.1, 9.8, 0.22, 0.42, 0.22, (245, 220, 20)))
        B.append(Box(-8.8, 0.0, 5.6, 2.0, 1.1, 2.4, WOOD, edge=(150, 100, 70)))
        B.append(Box(-8.8, 1.1, 5.6, 1.5, 0.12, 1.5, (50, 50, 64), tag="printer"))
        return B

    # ------------------------------------------------------------ audio fallback
    def audio(self, now):
        bands = DATA.bands
        if DATA.audio_live or any(b > 0 for b in bands):
            return bands, DATA.beat, DATA.level
        t = now
        bands = [max(0.0, 0.35 + 0.3 * math.sin(t * (1.3 + i * 0.21) + i)) * (1 - i / 24) for i in range(16)]
        beat = max(0.0, 1 - ((t * 2.0) % 1.0) * 3.5)
        return bands, beat, 0.4

    # ------------------------------------------------------------ geometry helpers
    def draw_box(self, s, b, L):
        cam = self.cam
        center, radius = b.bound
        vx, vy, vz = cam.view(center)
        # Conservative sphere/frustum test avoids all face work for offscreen furniture.
        f, cx, cy = cam.f2, cam.cx, cam.cy * 2
        if (vz + radius < NEAR or
                abs(vx) * f - cx * vz > radius * math.hypot(f, cx) or
                abs(vy) * f - cy * vz > radius * math.hypot(f, cy)):
            return []
        px, py, pz = cam.pos
        drawn = []
        for n, quad, kind in b.faces():
            q0 = quad[0]
            if n[0] * (px - q0[0]) + n[1] * (py - q0[1]) + n[2] * (pz - q0[2]) <= 0:
                continue
            views = [cam.view(p) for p in quad]
            unclipped = all(v[2] >= NEAR for v in views)
            P = [cam.pp(v) for v in views] if unclipped else cam.poly(quad)
            if not P:
                continue
            xs,ys=zip(*P)
            if max(xs)<0 or min(xs)>=s.w or max(ys)<0 or min(ys)>=s.ph:
                continue
            col = shade(b.col, face_light(n) * L * (1.25 if kind == "top" and b.glow else 1.0))
            fill(s, P, col)
            # Material strokes are coplanar with the furniture and rotate with it.
            if (unclipped and max(v[2] for v in views) < 26 and b.screen is None
                    and max(q[0] for q in P)-min(q[0] for q in P) >= 4
                    and max(q[1] for q in P)-min(q[1] for q in P) >= 3):
                A, B, C, D = views
                mix = lambda a, b, u: tuple(a[k]+(b[k]-a[k])*u for k in range(3))
                tc = shade(b.col, face_light(n)*L*.72)
                if b.col in (WOOD, CARD) or kind == "top":
                    for j in range(1, 4):
                        u = j/4
                        pa,pb=cam.pp(mix(A,D,u)),cam.pp(mix(B,C,u))
                        pline(s,pa[0],pa[1],pb[0],pb[1],tc)
                elif b.col in (METAL, DARKM) and kind != "top":
                    for u in (.28,.42,.56,.70):
                        pa,pb=cam.pp(mix(A,D,u)),cam.pp(mix(B,C,u))
                        pline(s,pa[0],pa[1],pb[0],pb[1],tc)
            drawn.append((kind, quad, P))
            if b.edge:
                ec = shade(b.edge, L * 0.8)
                for i in range(4):
                    if kind == "top" or i == 2:
                        if unclipped:
                            pline(s, P[i - 1][0], P[i - 1][1], P[i][0], P[i][1], ec)
                        else:
                            line3(s, cam, quad[i - 1], quad[i], ec)
        return drawn

    def bitmap(self, s, origin, u, v, rows, pal, alpha=None):
        """Draw a bitmap on a plane: origin = top-left, u = one column step, v = one row step (down)."""
        cam = self.cam
        R, C = len(rows), len(rows[0])
        corners = [cam.proj((origin[0] + u[0] * c + v[0] * r,
                            origin[1] + u[1] * c + v[1] * r,
                            origin[2] + u[2] * c + v[2] * r))
                   for c, r in ((0, 0), (C, 0), (C, R), (0, R))]
        if any(p is None for p in corners):
            return
        x0 = max(0, math.ceil(min(p[0] for p in corners) - 0.5))
        x1 = min(s.w, math.ceil(max(p[0] for p in corners) - 0.5))
        y0 = max(0, math.ceil(min(p[1] for p in corners) - 0.5))
        y1 = min(s.ph, math.ceil(max(p[1] for p in corners) - 0.5))
        if x1 <= x0 or y1 <= y0:
            return
        # Intersect each pixel-center ray with the bitmap plane. This draws every
        # texel at the current camera pose without rasterizing hundreds of quads.
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
        cache = getattr(self, "bitmap_cache", None)
        if cache is None:
            cache = self.bitmap_cache = {}
        texture = cache.get(key)
        if texture is None:
            symbols = sorted(set("".join(rows)))
            codes = {ch: i for i, ch in enumerate(symbols)}
            texture = (np.array([[codes[ch] for ch in row] for row in rows], dtype=np.uint8), symbols)
            if len(cache) >= 64:
                cache.clear()
            cache[key] = texture
        codes, symbols = texture
        palette = np.empty(len(symbols) + 1, dtype=object)
        for i, ch in enumerate(symbols):
            palette[i] = pal.get(ch)
        palette[-1] = None
        indexes = codes[rr, cols]
        indexes = np.where(inside, indexes, len(symbols))
        colors = palette[indexes]
        for i, py in enumerate(range(y0, y1)):
            cy = py >> 1
            row = (s.pb if py & 1 else s.pt)[cy]
            values = colors[i].tolist()
            if alpha is None:
                row[x0:x1] = [c if c is not None else old for c, old in zip(values, row[x0:x1])]
            else:
                row[x0:x1] = [blend(old or BLACK, c, alpha) if c is not None else old
                              for c, old in zip(values, row[x0:x1])]
            # Wall art is drawn before text; preserve the existing painter behavior.
            s.ch[cy][x0:x1] = [" "] * (x1 - x0)
            s.bg[cy][x0:x1] = [None] * (x1 - x0)

    # ------------------------------------------------------------ room shell
    def shell(self, s, now, L):
        cam = self.cam
        strokes=[]
        stroke=lambda _s,_cam,a,b,col: strokes.append((a,b,col))
        fill_q = lambda q, col: (lambda P: P and fill(s, P, col))(cam.poly(q))
        fill_q([(X0, 0, Z0), (X1, 0, Z0), (X1, 0, Z1), (X0, 0, Z1)], shade(FLOOR, L))
        fill_q([(X0, YC, Z1), (X1, YC, Z1), (X1, YC, Z0), (X0, YC, Z0)], shade(CEIL, L))
        fill_q([(X0, 0, Z1), (X1, 0, Z1), (X1, YC, Z1), (X0, YC, Z1)], shade(WALL_BACK, L))
        fill_q([(X0, 0, Z0), (X0, 0, Z1), (X0, YC, Z1), (X0, YC, Z0)], shade(WALL_SIDE, L * 0.9))
        fill_q([(X1, 0, Z1), (X1, 0, Z0), (X1, YC, Z0), (X1, YC, Z1)], shade(WALL_SIDE, L * 0.8))
        # floor tiles + wall brick courses
        lc = shade((52, 46, 60), L)
        for i in range(1, 10):
            x = X0 + i * 2.0
            stroke(s, cam, (x, 0, Z0), (x, 0, Z1), lc)
        for z in range(0, 13, 2):
            stroke(s, cam, (X0, 0, z), (X1, 0, z), lc)
        bc = shade((70, 44, 74), L)
        for i in range(1, 12):
            y = i * 0.58
            stroke(s, cam, (X0, y, Z1 - 0.01), (X1, y, Z1 - 0.01), bc)
        # Staggered masonry joints, chipped mortar and floor scuffs.
        for row in range(12):
            y = row*.58
            for j in range(12):
                x = X0 + j*1.8 + (.9 if row%2 else 0)
                if x < X1:
                    stroke(s, cam, (x,y,Z1-.02), (x,y+.58,Z1-.02), shade((43,28,49),L))
                    if (j+row)%5 == 0:
                        stroke(s, cam, (x+.15,y+.12,Z1-.025), (min(X1,x+.75),y+.17,Z1-.025), shade((84,51,78),L))
        for j in range(24):
            x = X0+.6+(j*3.17)%18
            z = .4+(j*1.71)%11
            stroke(s, cam, (x,.012,z), (x+.4,.012,z+.12), shade((61,48,61),L))
        # Cable runs fixed to the side wall and small pipe brackets.
        for y in (1.1,1.18):
            stroke(s,cam,(X0+.025,y,Z0),(X0+.025,y,Z1),shade((30,24,33),L))
        for z in range(1,13,2):
            stroke(s,cam,(-6.1,YC-.4,z),(-5.75,YC-.4,z),shade((125,103,118),L))
        # skirting + ceiling pipes
        stroke(s, cam, (X0, 0.02, Z1), (X1, 0.02, Z1), shade(PURPLE, L))
        for x in (-6.0, 3.5):
            pc = shade((90, 90, 110), L)
            stroke(s, cam, (x, YC - 0.35, Z0), (x, YC - 0.35, Z1), pc)
            stroke(s, cam, (x + 0.15, YC - 0.35, Z0), (x + 0.15, YC - 0.35, Z1), shade((60, 60, 80), L))

        # Transform all static shell strokes together. Near-plane crossings keep
        # the exact segment clipper; visible strokes retain the full texture.
        P=np.asarray([(a,b) for a,b,_ in strokes],float)
        x=P[...,0]-cam.pos[0]; y=P[...,1]-cam.pos[1]; z=P[...,2]-cam.pos[2]
        x,z=x*cam.c-z*cam.s,x*cam.s+z*cam.c
        y,z=y*cam.cp+z*cam.sp,-y*cam.sp+z*cam.cp
        safe=np.maximum(z,NEAR)
        X=cam.cx+x/safe*cam.f2;Y=cam.cy*2-y/safe*cam.f2
        keep=(z.max(1)>=NEAR)&((z.min(1)<NEAR)|~((X.max(1)<0)|(X.min(1)>=s.w)|(Y.max(1)<0)|(Y.min(1)>=s.ph)))
        XX,YY=X.tolist(),Y.tolist()
        crossing=(z.min(1)<NEAR).tolist()
        for i in np.flatnonzero(keep).tolist():
            if crossing[i]:
                a,b,col=strokes[i];line3(s,cam,a,b,col)
            else:
                pline(s,XX[i][0],YY[i][0],XX[i][1],YY[i][1],strokes[i][2])

    def wall_art(self, s, now, L, beat):
        zb = Z1 - 0.02
        # neon glow on the wall, then the sign itself (flickers with the music)
        cols = len(self.sign[0])
        cw = 0.26
        w = cols * cw
        ox = -w / 2
        y_top = 6.55
        glow = 0.35 + 0.65 * beat
        if random.random() < 0.02:
            self.sign_dead = (random.randrange(6), now + random.uniform(0.1, 0.5))
        halo_col = shade(blend(WALL_BACK, PINK, 0.35 + 0.25 * glow), L)
        self.bitmap(s, (ox - cw, y_top + cw, zb), (cw, 0, 0), (0, -cw, 0), self.sign_halo, {"#": halo_col})
        bright = blend(PINK, WHITE, 0.15 + 0.45 * glow)
        dead = getattr(self, "sign_dead", (None, 0))
        rows = self.sign
        if dead[1] > now:
            a, b = dead[0] * 7, dead[0] * 7 + 6
            rows = [r[:a] + r[a:b].replace("#", "d") + r[b:] for r in rows]
        self.bitmap(s, (ox, y_top, zb - 0.01), (cw, 0, 0), (0, -cw, 0), rows, {"#": bright, "d": shade(PINK, 0.3)})
        # skull poster above the desk-left, eye poster, glitch poster
        self.bitmap(s, (-9.4, 6.2, zb), (0.12, 0, 0), (0, -0.12, 0), self.skull,
                    {"w": shade(WHITE, L * 0.9), "p": shade(PINK, L * 0.75)})
        pal = {"b": shade((30, 30, 60), L), "y": shade(YELLOW, L), "w": shade(WHITE, L), "k": shade(BLACK, L),
               "p": shade(PINK, L), "c": shade(CYAN, L)}
        self.bitmap(s, (6.3, 6.4, zb), (0.22, 0, 0), (0, -0.22, 0), POSTER_EYE, pal)
        self.bitmap(s, (X0 + 0.02, 6.0, 3.0), (0, 0, 0.3), (0, -0.25, 0), POSTER_BARS, pal)
        # graffiti tag on the left wall
        gp = {"#": shade(blend(YELLOW, PINK, pulse(now, 0.4)), L)}
        self.bitmap(s, (X0 + 0.02, 2.6, 10.6), (0, 0, 0.22), (0, -0.3, 0), self.graffiti, gp)
        # window on the right wall: SF skyline at night
        wp = {"s": (10, 12, 40), "t": (30, 16, 60), "k": (8, 8, 16), "l": (230, 190, 90)}
        if random.random() < 0.3:
            r = random.randrange(len(self.window))
            c = random.randrange(len(self.window[0]))
            row = self.window[r]
            if row[c] in "kl":
                self.window[r] = row[:c] + ("l" if row[c] == "k" else "k") + row[c + 1:]
        self.bitmap(s, (X1 - 0.02, 5.4, 2.6), (0, 0, 0.23), (0, -0.25, 0), self.window, wp)
        cam = self.cam
        fc = shade((120, 120, 140), L)
        for a, b in (((X1 - 0.03, 5.45, 2.55), (X1 - 0.03, 5.45, 8.6)), ((X1 - 0.03, 2.1, 2.55), (X1 - 0.03, 2.1, 8.6)),
                     ((X1 - 0.03, 5.45, 5.6), (X1 - 0.03, 2.1, 5.6)), ((X1 - 0.03, 3.8, 2.55), (X1 - 0.03, 3.8, 8.6))):
            line3(s, cam, a, b, fc)

    # ------------------------------------------------------------ screens
    def screen_rect(self, P):
        """Inner cell rectangle of a projected quad (front face: bl, br, tr, tl)."""
        bl, br, tr, tl = P
        x0 = math.ceil(max(bl[0], tl[0])) + 1
        x1 = int(min(br[0], tr[0])) - 1
        y0 = math.ceil(max(tl[1], tr[1]) / 2)
        y1 = int(min(bl[1], br[1]) / 2) - 1
        return x0, y0, x1 - x0 + 1, y1 - y0 + 1

    def screen(self, s, b, P, now, L, bands):
        idx = b.screen
        x, y, w, h = self.screen_rect(P)
        if w < 3 or h < 2:
            return
        tint = (8, 22, 30) if idx != 4 else (14, 20, 60)
        fill(s, P, shade(tint, 0.6 + 0.4 * L))
        st = self.st[idx]
        x0 = max(0, x)
        if idx == 0:          # audio bars
            n = max(1, w // 2)
            for i in range(n):
                v = bands[int(i * 16 / n)]
                hh = v * h
                full = int(hh)
                for r in range(h):
                    ch = "█" if r < full else (PARTIAL[int((hh - full) * 8)] if r == full else " ")
                    if ch != " ":
                        s.put(x + i * 2, y + h - 1 - r, ch, blend(CYAN, PINK, r / max(1, h - 1)))
        elif idx == 1:        # spinning wireframe
            shapes = ((CUBE_V, CUBE_E), (ICO_V, ICO_E), (OCTA_V, OCTA_E))
            vs, es = shapes[int(now / 8) % 3]
            size = max(1.0, min(h / 2 - 0.6, w / 4 - 0.6))
            draw_wire(s, vs, es, x + w / 2, y + h / 2, size, now * 0.9, now * 1.3, now * 0.4, near=PINK, far=DIM_CYAN)
        elif idx == 2:        # radar
            if h >= 3:
                p_radar(s, x, y, w, h, now, st)
        elif idx == 3:        # minimap blocks
            p_minimap(s, x, y, w, h, now, st)
        elif idx == 4:        # TV: news
            self.tv(s, x, y, w, h, now)
        # clip anything that spilled out of the screen
        for yy in range(max(0, y - 2), min(s.h, y + h + 2)):
            rc = s.ch[yy]
            for xx in range(max(0, x - 6), min(s.w, x + w + 6)):
                if rc[xx] != " " and not (x <= xx < x + w and y <= yy < y + h):
                    if not (yy < y or yy >= y + h) or True:
                        if xx < x or xx >= x + w or yy < y or yy >= y + h:
                            rc[xx] = " "
        bgc = shade(tint, 0.6 + 0.4 * L)
        for yy in range(max(0, y), min(s.h, y + h)):
            rc, rb = s.ch[yy], s.bg[yy]
            for xx in range(x0, min(s.w, x + w)):
                if rc[xx] != " ":
                    rb[xx] = bgc

    def tv(self, s, x, y, w, h, now):
        # anchor silhouette in pixels, header + ticker text
        cx = x + w // 2
        if h >= 4:
            hr = max(1.0, h * 0.35)
            s.pixel_circle(cx, (y + h * 0.42) * 2, hr, (60, 70, 120))
            prect(s, cx - int(hr * 2.2), int((y + h * 0.42) * 2 + hr + 1), int(hr * 4.4), int((y + h) * 2 - ((y + h * 0.42) * 2 + hr + 1)) - 2, (50, 30, 90))
            if w > 16:
                prect(s, x + 1, (y + 1) * 2, max(2, w // 5), max(2, h), (90, 20, 60))
        head = "SFN LIVE" if w < 22 else "SFN LIVE // BREAKING"
        s.text(x, y, head[:w], WHITE if int(now * 2) % 2 else PINK)
        txt = "  ///  ".join(TV_NEWS) + "  ///  "
        off = int(now * 9) % len(txt)
        line = (txt + txt)[off:off + w]
        s.text(x, y + h - 1, line, YELLOW)
        for xx in range(x, x + w):
            s.set_bg(xx, y + h - 1, (90, 10, 40))

    # ------------------------------------------------------------ special objects
    def printer(self, s, b, now, L):
        cam = self.cam
        cx, cz = b.c
        base = b.y0 + 0.12
        # frame
        fc = shade(METAL, L)
        corners = [(cx - 0.7, cz - 0.7), (cx + 0.7, cz - 0.7), (cx + 0.7, cz + 0.7), (cx - 0.7, cz + 0.7)]
        top = base + 1.9
        for x, z in corners:
            line3(s, cam, (x, base, z), (x, top, z), fc)
        for i in range(4):
            a, c = corners[i - 1], corners[i]
            line3(s, cam, (a[0], top, a[1]), (c[0], top, c[1]), fc)
        # print job
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
        q = cam.proj((cx, base, cz))
        if not q:
            return
        done = int(p * NL)
        for i in range(done + 1):
            u = i / NL
            if i == done and p >= 1:
                break
            yy = base + i * hstep
            qq = cam.proj((cx, yy, cz))
            if not qq:
                continue
            hw = prof(u) * 0.5 * cam.f2 / qq[2]
            ph = max(1, int(hstep * cam.f2 / qq[2] + 0.99))
            if i == done:
                col = blend(ORANGE, YELLOW, pulse(now, 9))
                frac = (el / dur * NL) % 1.0
                hw *= frac
            else:
                col = shade(blend(PINK, PURPLE, (i % 4) / 6), L * (1.15 if p >= 1 else 1.0))
            prect(s, qq[0] - hw, qq[1] - ph, max(1, int(hw * 2)), ph, col)
        # gantry + nozzle
        ny = base + min(done, NL) * hstep + 0.12
        line3(s, cam, (cx - 0.7, ny, cz), (cx + 0.7, ny, cz), shade((140, 140, 160), L))
        if p < 1:
            nx = cx + math.sin(now * 7) * 0.45 * prof(min(0.99, p))
            qn = cam.proj((nx, ny, cz))
            if qn:
                sz = max(1, int(0.18 * cam.f2 / qn[2]))
                prect(s, qn[0] - sz, qn[1] - sz, sz * 2, sz, (170, 170, 190))
                s.pixel(int(qn[0]), int(qn[1]), ORANGE)
                if random.random() < 0.15:
                    self.parts.add(qn[0], qn[1] / 2, random.uniform(-2, 2), -random.uniform(1, 3), 0.6, "·", ORANGE)
        elif int(now * 4) % 2:
            qt = cam.proj((cx, base + 1.5, cz))
            if qt:
                s.put(int(qt[0]) - 2, int(qt[1] / 2), "DONE", GREEN)

    def mask_eyes(self, s, b, now):
        if now > self.next_eyes:
            self.eyes = random.choice(EYES)
            self.next_eyes = now + random.uniform(1.5, 4)
        cam = self.cam
        cx, cz = b.c
        if cam.pos[0] < cx:
            return
        col = blend(PINK, CYAN, pulse(now, 1.3)) if int(now * 7) % 13 else WHITE
        for k, dz in ((0, -0.15), (2, 0.15)):
            q = cam.proj((cx + 0.3, b.y0 + 0.48, cz + dz))
            if q:
                s.put(int(q[0]), int(q[1] / 2), self.eyes[k], col)

    def rack_leds(self, s, b, now):
        cam = self.cam
        cx, cz = b.c
        z = cz - 0.81
        for i, (a, ph) in enumerate(self.leds):
            r, c = i // 4, i % 4
            p = (cx - 0.45 + c * 0.3, 0.5 + r * 0.55, z)
            q = cam.proj(p)
            if not q:
                continue
            on = (math.sin(now * (2 + a * 9) + ph * 20) > 0.2 - a * 0.5)
            col = (GREEN if a > 0.3 else ORANGE) if on else (20, 40, 20)
            sz = max(1, int(0.08 * cam.f2 / q[2]))
            prect(s, q[0], q[1], sz, sz, col)

    def string_lights(self, now, L, beat):
        items = []
        strands = [((X0, 6.4, 1.0), (X1, 6.6, 6.0)), ((X0, 6.6, 7.0), (X1, 6.4, 12.0)), ((X0, 6.5, 12.5), (X1, 6.5, 2.5))]
        pal = (PINK, CYAN, YELLOW, PURPLE, GREEN)
        shift = int(now * 2 + beat * 2)
        for k, (a, b) in enumerate(strands):
            n = 16
            prev = None
            for i in range(n + 1):
                t = i / n
                p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - math.sin(t * math.pi) * 0.9, a[2] + (b[2] - a[2]) * t)
                if prev is not None:
                    items.append(("wire", prev, p))
                if 0 < i < n:
                    col = pal[(i + k + shift) % len(pal)]
                    items.append(("bulb", p, blend(BLACK, col, min(1.0, 0.45 + 0.55 * L * (0.6 + 0.4 * beat)))))
                prev = p
        return items

    # ------------------------------------------------------------ actors
    def robot_parts(self, now, dt):
        r = self.robot
        a = self.path[r["i"]]
        b = self.path[(r["i"] + 1) % len(self.path)]
        seg = math.dist(a, b)
        r["t"] += dt * 1.1 / max(0.1, seg)
        if r["t"] >= 1:
            r["t"] = 0.0
            r["i"] = (r["i"] + 1) % len(self.path)
        t = r["t"]
        x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        yaw = math.atan2(-(b[0] - a[0]), b[1] - a[1])
        bob = abs(math.sin(now * 9)) * 0.03
        cs, sn = math.cos(yaw), math.sin(yaw)
        self.robot_pos = (x, z, yaw)

        def off(dx, dz):
            return x + dx * cs - dz * sn, z + dx * sn + dz * cs

        parts = []
        for side in (-0.4, 0.4):
            wx, wz = off(side, 0)
            parts.append(Box(wx, 0.0, wz, 0.14, 0.32, 0.42, (20, 20, 24), yaw=yaw))
        parts.append(Box(x, 0.12 + bob, z, 0.66, 0.5, 0.7, (200, 200, 214), yaw=yaw, edge=CYAN))
        hx, hz = off(0, 0.05)
        parts.append(Box(hx, 0.68 + bob, hz, 0.42, 0.32, 0.4, (230, 120, 30), yaw=yaw, edge=YELLOW, tag="bothead"))
        return parts

    def robot_extras(self, s, now):
        cam = self.cam
        x, z, yaw = self.robot_pos
        top = (x, 1.0, z)
        tip = (x + 0.1, 1.42, z)
        line3(s, cam, top, tip, (160, 160, 170))
        q = cam.proj(tip)
        if q and int(now * 3) % 2:
            s.pixel(int(q[0]), int(q[1]), (255, 50, 50))
        # eye on the front of the head (front = local -z rotated)
        fx, fz = x - (-0.22) * math.sin(yaw) * 0 + math.sin(yaw) * 0.22, z - math.cos(yaw) * 0.22 + 0.05 * 0
        fx = x + 0.05 * -math.sin(yaw) + 0.22 * math.sin(yaw)
        n = (math.sin(yaw), -math.cos(yaw))
        if n[0] * (cam.pos[0] - x) + n[1] * (cam.pos[2] - z) > 0:
            qe = cam.proj((x + n[0] * 0.21, 0.86, z + n[1] * 0.21 + 0.05))
            if qe:
                s.put(int(qe[0]), int(qe[1] / 2), "◉" if int(now * 5) % 9 else "-", CYAN)

    def cat_parts(self, now):
        el = now - self.cat_t
        A, B = (-9.0, 10.2), (9.6, 3.0)
        dur = math.dist(A, B) / 1.5
        if el < 0:
            return []
        if el > dur:
            self.cat_t = now + random.uniform(18, 32)
            return []
        t = el / dur
        x, z = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
        yaw = math.atan2(-(B[0] - A[0]), B[1] - A[1])
        cs, sn = math.cos(yaw), math.sin(yaw)

        def off(dx, dz):
            return x + dx * cs - dz * sn, z + dx * sn + dz * cs

        black = (34, 30, 40)
        parts = [Box(x, 0.26, z, 0.32, 0.3, 0.85, black, yaw=yaw, edge=(70, 60, 90))]
        hx, hz = off(0, -0.5)
        parts.append(Box(hx, 0.42, hz, 0.3, 0.28, 0.26, black, yaw=yaw, tag="cathead"))
        for ex in (-0.09, 0.09):
            ax, az = off(ex, -0.5)
            parts.append(Box(ax, 0.7, az, 0.07, 0.1, 0.06, black, yaw=yaw))
        ph = now * 10
        for i, (lx, lz) in enumerate(((-0.1, -0.3), (0.1, -0.3), (-0.1, 0.3), (0.1, 0.3))):
            sw = math.sin(ph + (i % 2) * math.pi + (i // 2) * math.pi) * 0.08
            px, pz = off(lx, lz + sw)
            parts.append(Box(px, 0.0, pz, 0.08, 0.27, 0.08, black, yaw=yaw))
        tx, tz = off(math.sin(now * 3) * 0.1, 0.45)
        parts.append(Box(tx, 0.45, tz, 0.07, 0.55, 0.07, black, yaw=yaw))
        self.cat_pos = (x, z, yaw)
        return parts

    def cat_eyes(self, s, now):
        x, z, yaw = self.cat_pos
        cam = self.cam
        n = (math.sin(yaw), -math.cos(yaw))
        hx, hz = x + n[0] * 0.64, z + n[1] * 0.64
        if n[0] * (cam.pos[0] - hx) + n[1] * (cam.pos[2] - hz) <= 0:
            return
        px, pz = -n[1], n[0]
        for e in (-0.07, 0.07):
            q = cam.proj((hx + px * e, 0.58, hz + pz * e))
            if q:
                s.put(int(q[0]), int(q[1] / 2), "•", (190, 255, 60))

    # ------------------------------------------------------------ camera
    def camera(self, t):
        cam = self.cam
        cam.pos = [3.2 * math.sin(t * 0.07), 3.3 + 0.35 * math.sin(t * 0.13), 1.6 + 1.5 * math.sin(t * 0.045 + 0.5)]
        cam.yaw = 0.48 * math.sin(t * 0.09 + 1.0) - cam.pos[0] * 0.03
        cam.pitch = 0.16 + 0.05 * math.sin(t * 0.11)
        cam.setup()

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        t = now - self.t0
        bands, beat, level = self.audio(now)
        glitch = self.glitch.active(now)
        if beat > 0.9 and random.random() < 0.04:
            self.blackout = now + random.uniform(0.06, 0.16)
        L = 0.72 + 0.22 * beat + 0.04 * math.sin(now * 23)
        if now < self.blackout:
            L *= 0.45
        self.camera(t)
        cam = self.cam

        self.shell(s, now, L)
        self.wall_art(s, now, L, beat)
        # cyan monitor glow + warm desk lamp light pool
        P = cam.poly([(-9.5, 0.01, 8.0), (-1.5, 0.01, 8.0), (-1.5, 0.01, 11.0), (-9.5, 0.01, 11.0)])
        if P:
            fill_alpha(s, P, CYAN, 0.06 + 0.05 * beat)
        P = cam.poly([(2.0, 0.01, 10.0), (9.0, 0.01, 10.0), (9.0, 0.01, 12.0), (2.0, 0.01, 12.0)])
        if P:
            fill_alpha(s, P, (80, 90, 255), 0.08)

        items = []
        px, py, pz = cam.pos
        seq = 0
        for b in self.static + self.robot_parts(now, dt) + self.cat_parts(now):
            c = b.center()
            d = (c[0] - px) ** 2 + (c[1] - py) ** 2 + (c[2] - pz) ** 2
            items.append((d, seq, "box", b))
            seq += 1
        for it in self.string_lights(now, L, beat):
            p = it[1] if it[0] == "bulb" else it[2]
            d = (p[0] - px) ** 2 + (p[1] - py) ** 2 + (p[2] - pz) ** 2
            items.append((d, seq, it[0], it))
            seq += 1
        items.sort(key=lambda it: (-it[0], it[1]))
        for d, _, kind, obj in items:
            if kind == "box":
                drawn = self.draw_box(s, obj, L)
                if not drawn:
                    continue
                if obj.screen is not None:
                    for k, quad, P in drawn:
                        if k == "front":
                            self.screen(s, obj, P, now, L, bands)
                tag = obj.tag
                if tag == "mask":
                    self.mask_eyes(s, obj, now)
                elif tag == "rack":
                    self.rack_leds(s, obj, now)
                elif tag == "printer":
                    self.printer(s, obj, now, L)
                elif tag == "bothead":
                    self.robot_extras(s, now)
                elif tag == "cathead":
                    self.cat_eyes(s, now)
                elif tag == "console" and int(now * 1.5) % 2:
                    q = cam.proj((obj.c[0] + 0.3, 1.0, obj.c[1] - 0.31))
                    if q:
                        s.pixel(int(q[0]), int(q[1]), GREEN)
            elif kind == "wire":
                line3(s, cam, obj[1], obj[2], shade((60, 60, 70), L))
            else:
                q = cam.proj(obj[1])
                if q:
                    x, y = int(q[0]), int(q[1] / 2)
                    s.put(x, y, "●" if q[2] < 9 else "•", obj[2])
        self.parts.step(s, dt)
        text_over_pixels(s)
        self.hud(s, now, level)
        postfx(s, now, glitch)

    def hud(self, s, now, level):
        w, h = self.w, self.h
        s.text(1, 0, "▌DEDSEC HACKERSPACE", PINK)
        if w >= 100:
            s.text(21, 0, "// SAN FRANCISCO", GREY)
        name, p = getattr(self, "print_state", ("", 0))
        msgs = ["3D PRINTER: %s %d%%" % (name, p * 100) if p < 1 else "3D PRINTER: %s DONE" % name,
                "J-BOT: PATROLLING SECTOR PIZZA", "WRENCH MASK MOOD: %s" % self.eyes,
                "MEMBERS ONLINE: 4   //   PIZZA RESERVES: LOW", "CAT.EXE: %s" % ("CROSSING" if now >= self.cat_t else "NAPPING")]
        if now > getattr(self, "msg_next", 0):
            self.msg_i = (self.msg_i + 1) % len(msgs)
            self.msg_next = now + 4
        m = "> " + msgs[self.msg_i % len(msgs)]
        s.text(1, h - 1, m[:w - 2], YELLOW)
        rec = "CAM 02 ● REC" if int(now * 2) % 2 else "CAM 02   REC"
        s.text(w - len(rec) - 1, 0, rec, PINK)
        np_ = DATA.now_playing()
        if np_ and w >= 90:
            t = "♪ " + np_ if False else "NOW PLAYING: " + np_
            t = t[:w // 2]
            s.text(w - len(t) - 1, h - 1, t, CYAN)
        else:
            vu = int(min(1.0, level * 1.6) * 10)
            bar = "VU " + "▮" * vu + "▯" * (10 - vu)
            s.text(w - len(bar) - 1, h - 1, bar, CYAN)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "blackout", "DEDSEC // LIGHTS OUT", PURPLE)
        if .05 < t < .7:
            # Last monitor power indicator extinguishes after the room lights.
            x,y=s.w//2,s.h//2
            s.put(x,y,"_" if t < .38 else ".",blend(GREEN,BLACK,t))

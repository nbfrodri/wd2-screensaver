"""TOWER: DedSec raids the Blume ctOS tower at night.

The camera spirals up a stepped glass skyscraper above a dense night city. Every
firewall layer is a hexagonal energy shield around a floor: drones hit it, it
cracks, shatters into falling shards and the floor turns DedSec pink. At the top
the tower goes dark floor by floor and a giant DedSec skull is projected into the
sky with a shockwave that flips the city lights.

Rendering notes: a lens-shift camera (no pitch) keeps world verticals vertical,
so the tower and the city are ray cast per screen column and textured per pixel
into a private half-block frame buffer (one list per pixel row).
"""

import math
import random
import time

from engine3d import clip2d
from lib import BLACK, CYAN, DIM_CYAN, DIM_PINK, GREY, PINK, WHITE, YELLOW, Glitch, blend, ease_out, pulse
from mode_logo import SKULL
from sysdata import DATA

try:  # newer detailed skull rasteriser (DEDSEC mode); SKULL bitmap is the fallback
    from mode_logo import make_skull
except ImportError:  # pragma: no cover
    make_skull = None

NAME = "TOWER"

TAU = math.tau
NEAR = 0.6
NF = 40                       # firewall layers
INTRO = 3.0
LAYER_T = 0.95
CLIMB_END = INTRO + NF * LAYER_T
F_DARK0, F_DARK1 = 2.6, 5.0   # finale beats, seconds after CLIMB_END
F_SHOCK = 5.4
F_OUT = 12.6
CYCLE = CLIMB_END + F_OUT + 0.6
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# (y0, y1, half width, chamfer, kind)
TIERS = [
    (0.0, 3.0, 7.0, 0.9, "lobby"),
    (3.0, 21.0, 5.0, 1.5, "office"),
    (21.0, 31.0, 4.4, 1.4, "office"),
    (31.0, 38.0, 3.8, 1.3, "office"),
    (38.0, 41.5, 3.15, 1.1, "crown"),
]
ROOF = 41.5
SPIRE = 52.0
LOGO_Y0, LOGO_Y1 = 33.8, 36.9
MOD = 0.8                     # curtain wall module width

MOON_AZ, MOON_E = 2.35, 0.40
LIGHT = (math.cos(MOON_AZ), math.sin(MOON_AZ))

PINK_LED = (255, 40, 150)
CYAN_LED = (40, 210, 255)
SHIELD_C = (40, 225, 255)
HAZE = (70, 30, 72)


def yshield(x):
    return 2.4 + x * 0.95


def tier_at(y):
    for t in TIERS:
        if t[0] <= y < t[1]:
            return t
    return TIERS[-1]


def q4(c):
    """Quantise colours a little so the terminal escape cache stays warm."""
    return (int(c[0]) & 0xF8, int(c[1]) & 0xF8, int(c[2]) & 0xF8)


def mix(a, b, t):
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return q4((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- baked sky (module cache)

AZN = 512
AZK = AZN / TAU
E0, E1 = -0.30, 1.40
EK = AZN / TAU
ER = int((E1 - E0) * EK) + 1
_SKY = []


def _grid(rnd, gw, gh):
    return [[rnd.random() for _ in range(gw)] for _ in range(gh)]


def _vn(G, gw, gh, x, y):
    xi, yi = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - xi, y - yi
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    x0, x1 = xi % gw, (xi + 1) % gw
    y0, y1 = min(gh - 1, max(0, yi)), min(gh - 1, max(0, yi + 1))
    r0, r1 = G[y0], G[y1]
    a = r0[x0] + (r0[x1] - r0[x0]) * fx
    b = r1[x0] + (r1[x1] - r1[x0]) * fx
    return a + (b - a) * fy


def sky_color(e):
    if e < 0:
        return blend((96, 38, 88), (26, 12, 32), min(1.0, -e / 0.25))
    if e < 0.07:
        return blend((160, 62, 112), (88, 30, 96), e / 0.07)
    if e < 0.32:
        return blend((88, 30, 96), (26, 14, 58), (e - 0.07) / 0.25)
    return blend((26, 14, 58), (4, 4, 16), min(1.0, (e - 0.32) / 0.8))


def sky_texture():
    if _SKY:
        return _SKY[0]
    rnd = random.Random(11)
    G1, G2, G3 = _grid(rnd, 14, 12), _grid(rnd, 28, 24), _grid(rnd, 56, 48)
    rows = []
    for ei in range(ER):
        e = E0 + ei / EK
        base = sky_color(e)
        band = smooth(0.0, 0.07, e) * (1 - smooth(0.35, 0.75, e))
        under = blend((150, 80, 128), (52, 44, 86), min(1.0, e / 0.45))
        row = []
        for ai in range(AZN):
            u = ai / AZN
            col = base
            daz = (u * TAU - MOON_AZ + math.pi) % TAU - math.pi
            dm = math.hypot(daz * math.cos(e), e - MOON_E)
            if band > 0:
                n = (0.55 * _vn(G1, 14, 12, u * 14, e * 9) + 0.3 * _vn(G2, 28, 24, u * 28, e * 22)
                     + 0.15 * _vn(G3, 56, 48, u * 56, e * 44))
                d = (n - 0.48) * 3.4 * band
                if d > 0:
                    cc = blend(under, (176, 176, 206), max(0.0, 1 - dm / 0.55) * 0.8)
                    col = blend(col, cc, min(0.85, d))
            if dm < 0.5:
                col = blend(col, (120, 116, 160), (1 - dm / 0.5) ** 2 * 0.55)
            row.append(q4(col))
        rows.append(row)
    _SKY.append(rows)
    return rows


_SKYT = []


def sky_texture_t():
    if not _SKYT:
        _SKYT.append([list(c) for c in zip(*sky_texture())])
    return _SKYT[0]


_SKULLS = {}


def skull_raster(sw, sh):
    key = (sw, sh)
    if key not in _SKULLS:
        if make_skull is not None:
            _SKULLS[key] = make_skull(sw, sh)
        else:
            cells = []
            for v in range(sh):
                for u in range(sw):
                    r, c = v * len(SKULL) // sh, u * len(SKULL[0]) // sw
                    if SKULL[r][c] == "X":
                        cells.append((u, v, 6))
            _SKULLS[key] = cells
    return _SKULLS[key]


# ---------------------------------------------------------------- frame buffer helpers

def _fill_alpha_rm(fb, W, PH, P, col, a):
    """Translucent convex polygon over the frame buffer (rows of pixel colours)."""
    if a <= 0.01 or not P:
        return
    ys = [p[1] for p in P]
    y0, y1 = max(0, int(min(ys))), min(PH - 1, int(max(ys)))
    n = len(P)
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
        xa, xb = max(0, int(lo + 0.5)), min(W, int(hi + 0.5))
        if xb <= xa:
            continue
        row = fb[py]
        seg = row[xa:xb]
        for c in set(seg):
            if c not in memo:
                memo[c] = (int(c[0] + (r - c[0]) * a) & 0xF8, int(c[1] + (g - c[1]) * a) & 0xF8, int(c[2] + (b - c[2]) * a) & 0xF8)
        row[xa:xb] = [memo[c] for c in seg]


def _fill_poly_rm(fb, W, PH, P, col):
    ys = [p[1] for p in P]
    y0, y1 = max(0, int(min(ys))), min(PH - 1, int(max(ys)))
    n = len(P)
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
        xa, xb = max(0, int(lo + 0.5)), min(W, int(hi + 0.5))
        if xb > xa:
            fb[py][xa:xb] = [col] * (xb - xa)


def _ellipse_alpha_rm(fb, W, PH, cx, cy, rx, ry, col, a):
    if a <= 0.01 or rx < 0.5 or ry < 0.5:
        return
    r, g, b = col
    memo = {}
    for py in range(max(0, int(cy - ry)), min(PH, int(cy + ry) + 1)):
        dy = (py + 0.5 - cy) / ry
        if dy * dy >= 1:
            continue
        hw = rx * math.sqrt(1 - dy * dy)
        xa, xb = max(0, int(cx - hw + 0.5)), min(W, int(cx + hw + 0.5))
        if xb <= xa:
            continue
        row = fb[py]
        seg = row[xa:xb]
        for c in set(seg):
            if c not in memo:
                memo[c] = (int(c[0] + (r - c[0]) * a) & 0xF8, int(c[1] + (g - c[1]) * a) & 0xF8, int(c[2] + (b - c[2]) * a) & 0xF8)
        row[xa:xb] = [memo[c] for c in seg]


def _pline_rm(fb, W, PH, x0, y0, x1, y1, col):
    c = clip2d(x0, y0, x1, y1, W, PH)
    if not c:
        return
    ta, tb = c
    dx, dy = x1 - x0, y1 - y0
    ax, ay = x0 + dx * ta, y0 + dy * ta
    bx, by = x0 + dx * tb, y0 + dy * tb
    n = int(max(abs(bx - ax), abs(by - ay))) + 1
    sx, sy = (bx - ax) / n, (by - ay) / n
    for i in range(n + 1):
        x, py = int(ax + sx * i), int(ay + sy * i)
        if 0 <= x < W and 0 <= py < PH:
            fb[py][x] = col


def _disc_rm(fb, W, PH, cx, cy, r, col):
    for py in range(max(0, int(cy - r)), min(PH, int(cy + r) + 1)):
        dy = py + 0.5 - cy
        if dy * dy > r * r:
            continue
        hw = math.sqrt(r * r - dy * dy)
        xa, xb = max(0, int(cx - hw + 0.5)), min(W, int(cx + hw + 0.5))
        if xb > xa:
            fb[py][xa:xb] = [col] * (xb - xa)


# The frame buffer is column-major (fb[x][py]) so column renderers can use slice
# runs; the generic scanline helpers above run on swapped axes.
def fill_alpha(fb, W, PH, P, col, a):
    _fill_alpha_rm(fb, PH, W, [(p[1], p[0]) for p in P], col, a)


def fill_poly(fb, W, PH, P, col):
    _fill_poly_rm(fb, PH, W, [(p[1], p[0]) for p in P], col)


def ellipse_alpha(fb, W, PH, cx, cy, rx, ry, col, a):
    _ellipse_alpha_rm(fb, PH, W, cy, cx, ry, rx, col, a)


def pline(fb, W, PH, x0, y0, x1, y1, col):
    _pline_rm(fb, PH, W, y0, x0, y1, x1, col)


def disc(fb, W, PH, cx, cy, r, col):
    _disc_rm(fb, PH, W, cy, cx, r, col)


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


def text_over_pixels(s):
    w = s.w
    for y in range(s.h):
        rc = s.ch[y]
        if rc.count(" ") == w:
            continue
        pt, pb, bg = s.pt[y], s.pb[y], s.bg[y]
        if rc[6:].count(" ") == w - 6:
            xs = [i for i in range(6) if rc[i] != " "]
        else:
            xs = [i for i, ch in enumerate(rc) if ch != " "]
        for x in xs:
            if True:
                c = pb[x] or pt[x]
                if c is not None:
                    bg[x] = (c[0] * 2 // 5, c[1] * 2 // 5, c[2] * 2 // 5)


def postfx(s, now, glitch):
    span = s.h + 16
    by = int((now * 6.0) % span) - 8
    for k, t in ((0, 0.14), (-1, 0.07), (1, 0.07)):
        tint_rows(s, by + k, by + k + 1, WHITE, t)
    if glitch:
        for _ in range(random.randint(1, 3)):
            y0 = random.randrange(s.h)
            dx = random.choice((-1, 1)) * random.randint(2, 8)
            n = random.randint(1, 2)
            for y in range(y0, min(s.h, y0 + n)):
                s.shift_row(y, dx)
                # fill the gap with the edge colour instead of a black hole
                if dx > 0:
                    for layer in (s.pt, s.pb):
                        r = layer[y]
                        r[:dx] = [r[dx]] * dx
                else:
                    for layer in (s.pt, s.pb):
                        r = layer[y]
                        r[dx:] = [r[dx - 1]] * -dx
            tint_rows(s, y0, y0 + n, random.choice((PINK, CYAN)), 0.18)


# ---------------------------------------------------------------- static tables

NQ = 12
RB = 16
LITC = [None, (255, 192, 112), (244, 168, 88), (228, 230, 236), (150, 206, 255), (136, 98, 60), (96, 116, 236)]
LITH = [None] + [q4(blend(c, WHITE, 0.25)) for c in LITC[1:]]
LITC = [None] + [q4(c) for c in LITC[1:]]


def _reflect(rb):
    # rb < 8: rows above the horizon reflect the city below; >= 8 reflect the sky.
    if rb < 8:
        return blend((20, 12, 32), (110, 46, 92), (rb / 7) ** 2)
    return blend((64, 64, 128), (16, 20, 52), (rb - 8) / 7)


GLASS = [[mix((6, 10, 24), _reflect(rb), 0.22 + 0.7 * q / (NQ - 1)) for rb in range(RB)] for q in range(NQ)]
SPAN = [mix((12, 14, 24), (74, 82, 116), q / (NQ - 1)) for q in range(NQ)]
MULL = [mix((28, 32, 50), (140, 150, 186), q / (NQ - 1)) for q in range(NQ)]
CHAM = [mix((16, 18, 30), (92, 98, 132), q / (NQ - 1)) for q in range(NQ)]
CHAMD = [mix(c, BLACK, 0.45) for c in CHAM]
EDGE = [mix(c, (200, 220, 255), 0.35) for c in MULL]
FIN = [mix((26, 28, 44), (150, 156, 190), q / (NQ - 1)) for q in range(NQ)]


def _hex_tile(a=0.44, res=16):
    tw, th = 3 * a, math.sqrt(3) * a
    nx, ny = int(tw * res + 0.5), int(th * res + 0.5)
    centers = []
    for i in range(-1, 4):
        for j in range(-2, 3):
            centers.append((i * 1.5 * a, j * th + (th / 2 if i % 2 else 0)))
    tile = []
    k = math.sqrt(3) / 2 * a
    for ty in range(ny):
        row = []
        for tx in range(nx):
            x, y = (tx + 0.5) / nx * tw, (ty + 0.5) / ny * th
            best = 9.0
            for cx, cy in centers:
                dx, dy = abs(x - cx), abs(y - cy)
                hn = max(dy, (math.sqrt(3) * dx + dy) / 2) / k
                if hn < best:
                    best = hn
            row.append(2 if best > 0.80 else (1 if best > 0.55 else 0))
        tile.append(row)
    return tile, tw, th, nx / tw, ny / th


HEXT, HTW, HTH, HKX, HKY = _hex_tile(0.6)


def _panel_tex(pw=36, ph=22):
    """Backlit ctOS emblem panel and a DedSec skull version (from SKULL)."""
    ctos, dsec = [], []
    for v in range(ph):
        r1, r2 = [], []
        for u in range(pw):
            nx, ny = (u + 0.5) / pw * 2 - 1, (v + 0.5) / ph * 2 - 1
            r = math.hypot(nx * 1.5, ny)
            if abs(nx) > 0.94 or abs(ny) > 0.9:
                c = (150, 176, 196)
            elif 0.48 < r < 0.72:
                c = (12, 24, 48)
            elif r < 0.2:
                c = (20, 200, 255)
            elif abs(ny) < 0.07 and 0.72 <= r < 0.9 and nx > 0:
                c = (12, 24, 48)
            else:
                c = blend((236, 246, 255), (176, 214, 236), r)
            r1.append(q4(c))
            sr = int(v / ph * len(SKULL))
            sc = int(u / pw * len(SKULL[0]))
            hit = SKULL[sr][sc] == "X"
            r2.append(q4(blend((255, 120, 200), WHITE, 0.3 * (1 - ny)) if hit else (40, 4, 26)))
        ctos.append(r1)
        dsec.append(r2)
    return ctos, dsec


PANEL_CTOS, PANEL_DSEC = _panel_tex()

_RND = random.Random(4242)
LT = [_RND.randrange(100) for _ in range(4096)]
FLOOR_ACT = [_RND.choice((0.08, 0.2, 0.35, 0.6)) for _ in range(64)]
LITTAB = []
for _i in range(4096):
    _fl = (_i * 7) % 64
    LITTAB.append(_RND.choice((1, 1, 2, 2, 3, 4, 5, 6)) if _RND.random() < FLOOR_ACT[_fl] else 0)


# ---------------------------------------------------------------- the mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.PH = h * 2
        self.F0 = self.PH * 1.15
        self.cxs = w / 2
        self.glitch = Glitch(0.004)
        self.last = time.time()
        self.skyT = sky_texture_t()
        rnd = random.Random(7)
        self.build_city(rnd)
        self.stars = []
        for _ in range(110):
            az, e = rnd.uniform(0, TAU), rnd.uniform(0.18, 1.3)
            self.stars.append((az, e, rnd.uniform(0.35, 1.0), rnd.uniform(0, 9)))
        self.lamps = [(rnd.uniform(0, TAU), rnd.uniform(110, 200), rnd.uniform(0.22, 0.42), rnd.uniform(0, 6))
                      for _ in range(3)]
        self.clouds = []
        for deck, (ya, yb) in enumerate(((12.5, 16.5), (27.0, 31.0), (44.0, 48.0))):
            for _ in range(4):
                self.clouds.append([rnd.uniform(0, TAU), rnd.uniform(16, 80), rnd.uniform(ya, yb),
                                    rnd.uniform(5, 11), rnd.uniform(0.01, 0.04),
                                    [(rnd.uniform(-0.7, 0.7), rnd.uniform(-0.15, 0.15), rnd.uniform(0.5, 1.0))
                                     for _ in range(3)]])
        self.skull_cells = None
        self.reset(self.last)

    def build_city(self, rnd):
        F0 = self.F0
        self.layers = []
        spec = [(56, 4.6, 3, 20), (76, 5.2, 3, 28), (102, 6.0, 4, 34), (136, 7.0, 4, 38),
                (182, 8.5, 3, 32), (252, 10.5, 3, 24), (380, 14.0, 2, 14)]
        for li, (D, cw, hmin, hmax) in enumerate(spec):
            n = max(8, int(TAU * D / cw))
            cw = TAU * D / n
            fog = min(0.88, (D - 40) / 420) ** 0.8
            hts, seeds, kinds = [], [], []
            for i in range(n):
                az = i / n * TAU
                avenue = min((az * 6 / TAU) % 1.0, 1 - (az * 6 / TAU) % 1.0) * TAU / 6 * D < cw * 0.6
                if avenue or rnd.random() < 0.05:
                    hts.append(0.0)
                else:
                    down = math.exp(-(((az - 0.9 + math.pi) % TAU - math.pi) / 0.5) ** 2)
                    hh = rnd.uniform(hmin, hmax) * (1 + 0.9 * down * (1 <= li <= 5))
                    if rnd.random() < 0.06 and li < 5:
                        hh *= 1.5
                    if i and hts[-1] and rnd.random() < 0.3:
                        hh = hts[-1]
                    hts.append(hh)
                seeds.append(rnd.randrange(4096))
                kinds.append(rnd.randrange(4))
            t_typ = D + 10
            wy = max(1.1, 2.6 * t_typ / F0)
            nm = max(1, int(round(cw / max(1.0, 2.4 * t_typ / F0))))
            bodies = [mix(b, HAZE, fog) for b in ((16, 14, 30), (22, 20, 36), (12, 16, 30), (26, 18, 34))]
            rims = [mix(b, (110, 110, 160), 0.35) for b in bodies]
            wins = [mix(c, HAZE, fog * 0.75) for c in LITC[1:]]
            pinks = [mix(c, HAZE, fog * 0.6) for c in (PINK, (255, 120, 200), CYAN, WHITE, PINK, (190, 60, 255))]
            lp = int(30 - li)
            ground = mix((14, 10, 22), HAZE, fog)
            street = mix((120, 64, 30), HAZE, fog * 0.8)
            head = mix((255, 236, 190), HAZE, fog * 0.6)
            tail = mix((255, 40, 36), HAZE, fog * 0.6)
            self.layers.append(dict(D=D, D2=D * D, n=n, icw=1 / cw, hts=hts, seeds=seeds, kinds=kinds,
                                    wy=1 / wy, nm=nm, bodies=bodies, rims=rims, wins=wins, pinks=pinks, lp=lp,
                                    ground=ground, street=street, head=head, tail=tail, Ds=D - 3.0,
                                    Ds2=(D - 3.0) ** 2, hmax=hmax * 2.0))

    def reset(self, now):
        self.t0 = now
        self.broken = 0
        self.cracks = None
        self.shards = []
        self.sparks = []
        self.pulses = []
        self.flash = 0.0
        self.shocked = False
        self.last_break = -9.0

    # ------------------------------------------------------------ camera
    def camera(self, t, now):
        w, PH = self.w, self.PH
        th = 0.7 + t * 0.2
        p = max(0.0, min(float(NF), (t - INTRO) / LAYER_T))
        R = 24 + 1.5 * math.sin(t * 0.23)
        camy = yshield(p) + 2.2 + 0.35 * math.sin(t * 0.5)
        hz = 0.42 * PH
        aim = 0.03 * math.sin(t * 0.13)
        F = self.F0
        if t < INTRO:
            k = ease_out(t / INTRO)
            camy = 1.4 + (camy - 1.4) * k
            hz = PH * (0.88 - 0.46 * k)
            R = 34 - 10 * k
        fe = t - CLIMB_END
        if fe > 0:
            k = smooth(0.0, 2.6, fe)
            k = k * k * (3 - 2 * k)
            R += (56 - R) * k
            camy += (24.0 - camy) * k
            hz += (0.57 * PH - hz) * k
            F *= 1 - 0.14 * k
            aim -= math.atan((0.17 * w) / F) * k
            th = 0.7 + CLIMB_END * 0.2 + fe * (0.2 - 0.16 * k)
        self.R, self.camy, self.hz, self.F, self.p = R, camy, hz, F, p
        self.Cx, self.Cz = R * math.cos(th), R * math.sin(th)
        a = th + math.pi + aim
        self.fx, self.fz = math.cos(a), math.sin(a)
        self.rx, self.rz = self.fz, -self.fx
        self.alpha = a
        self.KS = [(x + 0.5 - self.cxs) / F for x in range(w)]
        self.t_axis = -self.Cx * self.fx - self.Cz * self.fz

    def proj(self, x, y, z):
        vx, vz = x - self.Cx, z - self.Cz
        t = vx * self.fx + vz * self.fz
        if t < NEAR:
            return None
        iF = self.F / t
        return self.cxs + (vx * self.rx + vz * self.rz) * iF, self.hz - (y - self.camy) * iF, t

    def line3(self, fb, a, b, col):
        pa, pb = self.proj(*a), self.proj(*b)
        if pa and pb:
            pline(fb, self.w, self.PH, pa[0], pa[1], pb[0], pb[1], col)

    # ------------------------------------------------------------ sky
    def draw_sky(self, now):
        w, PH, F, hz = self.w, self.PH, self.F, self.hz
        a = self.alpha
        azs = [int(((a - math.atan(k)) % TAU) * AZK) % AZN for k in self.KS]
        tex = self.skyT
        EI = []
        for py in range(PH):
            ei = int((math.atan((hz - py - 0.5) / F) - E0) * EK)
            EI.append(0 if ei < 0 else (ER - 1 if ei >= ER else ei))
        cache = {}
        fb = []
        for ai in azs:
            c = cache.get(ai)
            if c is None:
                tc = tex[ai]
                c = cache[ai] = [tc[e] for e in EI]
            fb.append(c[:])
        # stars (hidden behind clouds by checking the baked brightness)
        for az, e, b, ph in self.stars:
            d = (a - az + math.pi) % TAU - math.pi
            if abs(d) > 1.2:
                continue
            x = int(self.cxs + F * math.tan(d))
            py = int(hz - F * math.tan(e))
            if 0 <= x < w and 0 <= py < PH:
                c = fb[x][py]
                if c[0] + c[1] + c[2] < 90:
                    tw = b * (0.55 + 0.45 * math.sin(now * (1.3 + ph * 0.2) + ph))
                    fb[x][py] = mix(c, (210, 214, 255), tw)
        # moon
        d = (a - MOON_AZ + math.pi) % TAU - math.pi
        if abs(d) < 1.2:
            mx, my = self.cxs + F * math.tan(d), hz - F * math.tan(MOON_E)
            r = max(1.6, F * 0.034)
            disc(fb, w, PH, mx, my, r + 0.8, (150, 146, 178))
            disc(fb, w, PH, mx, my, r, (232, 230, 214))
            disc(fb, w, PH, mx - r * 0.3, my - r * 0.2, r * 0.32, (196, 192, 184))
            disc(fb, w, PH, mx + r * 0.35, my + r * 0.3, r * 0.22, (204, 200, 190))
        return fb

    def searchlights(self, fb, now):
        w, PH = self.w, self.PH
        for a0, d, sp, ph in self.lamps:
            bx, bz = math.cos(a0) * d, math.sin(a0) * d
            ang = now * sp + ph
            tilt = 0.35 + 0.25 * math.sin(now * sp * 0.6 + ph)
            ux, uz = math.cos(ang) * tilt, math.sin(ang) * tilt
            q0 = self.proj(bx, 0, bz)
            if not q0:
                continue
            best = None
            for hh in (160, 90, 45):
                q1 = self.proj(bx + ux * hh, hh, bz + uz * hh)
                if q1:
                    best = (q1, hh)
                    break
            if not best:
                continue
            q1, hh = best
            half = max(1.5, 7.0 * hh / 160 * self.F / q1[2])
            P = [(q0[0], q0[1]), (q1[0] - half, q1[1]), (q1[0] + half, q1[1])]
            fill_alpha(fb, w, PH, P, (200, 210, 255), 0.10)

    # ------------------------------------------------------------ city
    def draw_city(self, fb, now, cover):
        w, PH, F, hz, camy = self.w, self.PH, self.F, self.hz, self.camy
        Cx, Cz, fx, fz, rx, rz = self.Cx, self.Cz, self.fx, self.fz, self.rx, self.rz
        cc = Cx * Cx + Cz * Cz
        atan2, sqrt = math.atan2, math.sqrt
        pi = math.pi
        R = self.R
        shock_r = (now - self.shock_t) * 140.0 if self.shocked else -1.0
        blink = int(now * 1.5) % 2
        cars = now * 7.0
        hzi = max(0, int(hz + 1))
        # per-layer tuples plus a conservative "nothing of this layer or beyond can reach above row" bound
        lay = []
        for L in self.layers:
            D, Hm = L["D"], L["hmax"]
            if Hm > camy:
                mt = hz - (Hm - camy) * F / max(1.0, D - R)
            else:
                mt = hz + (camy - Hm) * F / (D + R)
            lay.append([mt, L["D2"], (L["D"] - 3.0) / L["D"], L["Ds"], L["D"] * L["icw"], L["n"], L["hts"], L["kinds"],
                        L["bodies"], L["rims"], L["nm"], L["seeds"], L["lp"],
                        L["pinks"] if L["D"] < shock_r else L["wins"], L["wy"], L["ground"], L["street"],
                        L["head"], L["tail"], L["hmax"] * 0.62])
        lim = 1e9
        for row in reversed(lay):
            lim = min(lim, row[0])
            row[0] = int(lim)
        KS = self.KS
        ceil_f, floor_f = math.ceil, math.floor
        for x in range(w):
            if cover[x]:
                continue
            col = fb[x]
            k = KS[x]
            dx, dz = fx + rx * k, fz + rz * k
            a = 1 + k * k
            b = Cx * dx + Cz * dz
            bb = b * b
            ceil = PH
            for (mt, D2, Ds2, Ds, Dc, n, hts, kinds, bodies, rims, nm, seeds, lp, wins, iwy,
                 g, street, head, tail, tall) in lay:
                if ceil <= mt:
                    break
                t = (-b + sqrt(bb - a * (cc - D2))) / a
                iF = F / t
                ib = int(hz + camy * iF + 0.5)
                phi = atan2(Cz + t * dz, Cx + t * dx) + pi
                if ib < ceil:
                    g0 = ib if ib > hzi else hzi
                    if ceil > g0:
                        col[g0:ceil] = [g] * (ceil - g0)
                    sr = int(hz + camy * F / (t * Ds2) + 0.5)
                    if ib <= sr < ceil and sr >= 0:
                        sarc = phi * Ds
                        col[sr] = head if LT[int((sarc + cars) * 0.4) & 4095] < 30 else street
                        if sr + 1 < ceil and LT[int((sarc - cars) * 0.4 + 777) & 4095] < 30:
                            col[sr + 1] = tail
                s = phi * Dc
                ci = int(s) % n
                H = hts[ci]
                if H <= 0:
                    if ib < ceil:
                        ceil = ib if ib > 0 else 0
                    continue
                it = int(hz - (H - camy) * iF + 0.5)
                r1 = ib if ib < ceil else ceil
                if it < r1:
                    r0 = it if it > 0 else 0
                    u = s - int(s)
                    kind = kinds[ci]
                    body = bodies[kind]
                    col[r0:r1] = [body] * (r1 - r0)
                    mu = u * nm
                    mi = int(mu)
                    if 0.08 < u < 0.92 and 0.15 < mu - mi < 0.75:
                        seed = seeds[ci] + mi * 7
                        yb = t / F * iwy
                        ya = camy * iwy + (hz - 0.5) * yb
                        # window rows: v = ya - py*yb, lit part is frac(v) in (0.35, 1)
                        rtop = int(floor_f(ya - r0 * yb))
                        rbot = int(floor_f(ya - (r1 - 1) * yb))
                        iyb = 1.0 / yb
                        for ri in range(rtop, rbot - 1, -1):
                            h_ = LT[(seed + ri * 53) & 4095]
                            if h_ >= lp:
                                continue
                            pa = int(floor_f((ya - ri - 1) * iyb)) + 1
                            pb = int(ceil_f((ya - ri - 0.35) * iyb))
                            if pa < r0:
                                pa = r0
                            if pb > r1:
                                pb = r1
                            if pb > pa:
                                col[pa:pb] = [wins[h_ % 6]] * (pb - pa)
                    if it >= 0:
                        col[it] = rims[kind]
                        if blink and H > tall and it > 0 and 0.4 < u < 0.6:
                            col[it - 1] = (255, 36, 36)
                    ceil = r0
                elif ib < ceil:
                    ceil = ib if ib > 0 else 0
                if ceil <= 0:
                    break

    def plaza(self, fb, now):
        # ctOS ring on the plaza and a light ring at the tower foot
        if self.camy > 14:
            return
        for k, (rr, col) in enumerate(((11.0, (0, 150, 190)), (15.0, (140, 20, 90)))):
            n = 25
            prev = None
            for i in range(n + 1):
                a = i / n * TAU + now * (0.12 if k else -0.1)
                p = (math.cos(a) * rr, 0.05, math.sin(a) * rr)
                if prev and i % 5:
                    self.line3(fb, prev, p, col)
                prev = p

    # ------------------------------------------------------------ tower
    def tier_geo(self, tier):
        y0, y1, A, C, kind = tier
        B = A - C
        V = [(A, -B), (A, B), (B, A), (-B, A), (-A, B), (-A, -B), (-B, -A), (B, -A)]
        E = []
        for i in range(8):
            ax, az = V[i]
            bx, bz = V[(i + 1) % 8]
            ln = math.hypot(bx - ax, bz - az)
            ex, ez = (bx - ax) / ln, (bz - az) / ln
            nx, nz = ez, -ex
            E.append((nx, nz, nx * ax + nz * az, ax, az, ex, ez, ln, "L" if i % 2 == 0 else "C"))
        return V, E

    def column_hits(self, E, x0, x1):
        """Per-column entry/exit (t, facet) of a convex prism via projected facet spans."""
        Cx, Cz, fx, fz, rx, rz = self.Cx, self.Cz, self.fx, self.fz, self.rx, self.rz
        F, cxs, KS, W = self.F, self.cxs, self.KS, self.w
        front, backs = {}, {}
        for i, (nx, nz, d, ax, az, ex, ez, ln, _) in enumerate(E):
            bx, bz = ax + ex * ln, az + ez * ln
            ta = (ax - Cx) * fx + (az - Cz) * fz
            tb = (bx - Cx) * fx + (bz - Cz) * fz
            if ta < NEAR or tb < NEAR:
                return self.column_hits_slow(E, x0, x1)
            xa = cxs + ((ax - Cx) * rx + (az - Cz) * rz) * F / ta
            xb = cxs + ((bx - Cx) * rx + (bz - Cz) * rz) * F / tb
            if xa > xb:
                xa, xb = xb, xa
            lo, hi = max(0, int(math.ceil(xa - 0.5))), min(W, int(math.ceil(xb - 0.5)))
            nf, nr = nx * fx + nz * fz, nx * rx + nz * rz
            num = d - (nx * Cx + nz * Cz)
            tgt = front if num < 0 else backs
            for x in range(lo, hi):
                den = nf + nr * KS[x]
                if den != 0:
                    tgt[x] = (num / den, i)
        hits = {}
        for x, (te, fe) in front.items():
            b = backs.get(x)
            if b and b[0] > te > NEAR:
                hits[x] = (te, fe, b[0], b[1])
        return hits

    def column_hits_slow(self, E, x0, x1):
        Cx, Cz, fx, fz, rx, rz = self.Cx, self.Cz, self.fx, self.fz, self.rx, self.rz
        pre = [(nx * fx + nz * fz, nx * rx + nz * rz, d - (nx * Cx + nz * Cz)) for nx, nz, d, *_ in E]
        hits = {}
        KS = self.KS
        for x in range(x0, x1):
            k = KS[x]
            te, tx, fe, fo = -1e9, 1e9, -1, -1
            ok = True
            for i, (nf, nr, num) in enumerate(pre):
                den = nf + nr * k
                if den < -1e-9:
                    tt = num / den
                    if tt > te:
                        te, fe = tt, i
                elif den > 1e-9:
                    tt = num / den
                    if tt < tx:
                        tx, fo = tt, i
                elif num < 0:
                    ok = False
                    break
            if ok and fe >= 0 and te < tx and te > NEAR:
                hits[x] = (te, fe, tx, fo)
        return hits

    def xrange_of(self, V):
        xs = []
        for vx, vz in V:
            q = self.proj(vx, 0, vz)
            if q is None:
                return 0, self.w
            xs.append(q[0])
        return max(0, int(min(xs)) - 1), min(self.w, int(max(xs)) + 2)

    def draw_tower(self, fb, now, fe_t, cover):
        w, PH, F, hz, camy = self.w, self.PH, self.F, self.hz, self.camy
        Cx, Cz, fx, fz, rx, rz = self.Cx, self.Cz, self.fx, self.fz, self.rx, self.rz
        hack_y = yshield(self.broken) - 0.6
        dark = self.dark_y
        owned = self.shocked
        RBK = PH * 0.055
        RBROW = [min(RB - 1, max(0, int((py - hz) / RBK) + 8)) for py in range(PH)]
        tiers = sorted(TIERS, key=lambda T: -abs((T[0] + T[1]) / 2 - camy))
        led_on = pulse(now, 5) > 0.3
        led_pink = PINK_LED if (not owned or led_on) else (150, 20, 90)
        flash_on = int(now * 20) % 2 == 0
        floor_f = math.floor
        GRC = {}
        self.tcols = {}
        for ti, tier in enumerate(tiers):
            y0, y1, A, C, kind = tier
            V, E, x0, x1, hits = self.tier_cache[tier]
            if not hits:
                continue
            lam = []
            for nx, nz, *_ in E:
                lam.append(max(0.0, nx * LIGHT[0] + nz * LIGHT[1]))
            prev_mi = None
            prev_fe = None
            for x in range(x0, x1):
                hit = hits.get(x)
                if hit is None:
                    prev_fe = None
                    continue
                t, fe, _, _ = hit
                nx, nz, d, vx, vz, ex, ez, ln, fk = E[fe]
                k = self.KS[x]
                dx, dz = fx + rx * k, fz + rz * k
                Px, Pz = Cx + t * dx, Cz + t * dz
                s = (Px - vx) * ex + (Pz - vz) * ez
                iF = F / t
                r0 = int(hz - (y1 - camy) * iF + 0.5)
                r1 = int(hz - (y0 - camy) * iF + 0.5)
                if r0 < 0:
                    r0 = 0
                if r1 > PH:
                    r1 = PH
                if r1 <= r0:
                    prev_fe = fe
                    continue
                if r0 == 0 and r1 == PH:
                    cover[x] = True
                cosv = abs(nx * dx + nz * dz) / math.sqrt(1 + k * k)
                fres = (1 - cosv) ** 1.5
                q = int(min(1.0, 0.12 + 0.5 * lam[fe] + 0.55 * fres) * (NQ - 1))
                edge_col = fe != prev_fe or hits.get(x + 1, (0, fe))[1] != fe
                rim = (x - 1) not in hits or (x + 1) not in hits
                yb = t / F
                ya = camy + (hz - 0.5) * yb
                col = fb[x]
                n_ = r1 - r0
                if fk == "L" and kind in ("office", "lobby"):
                    mod = MOD if kind == "office" else 1.25
                    mi = int(s / mod)
                    mull = (fe == prev_fe and mi != prev_mi) or s < 0.1 or s > ln - 0.1
                    prev_mi = mi
                    G = GLASS[q]
                    sp, mu = SPAN[q], MULL[q]
                    if kind == "lobby":
                        for py in range(r0, r1):
                            y = ya - py * yb
                            if y < 0.12 or y > 2.75:
                                c = sp
                            elif mull:
                                c = mu
                            elif dark < 2:
                                c = G[RBROW[py]]
                            elif y < 0.9 and LT[(mi * 13 + int(y * 3)) & 4095] < 25:
                                c = (60, 44, 36)
                            else:
                                c = (212, 182, 124) if y > 2.45 else (128, 100, 70)
                            col[py] = c
                    else:
                        if mull:
                            col[r0:r1] = [mu] * n_
                        else:
                            gr = GRC.get(q)
                            if gr is None:
                                gr = GRC[q] = [G[rb] for rb in RBROW]
                            col[r0:r1] = gr[r0:r1]
                        hcol = fe * 37 + mi * 11 + int(y0) * 101
                        iyb = 1.0 / yb
                        ftop = int(floor_f(ya - r0 * yb))
                        fbot = int(floor_f(ya - (r1 - 1) * yb))
                        for fl in range(ftop, fbot - 1, -1):
                            gb = int(floor_f((ya - fl - 0.27) * iyb)) + 1
                            bb = int(floor_f((ya - fl) * iyb)) + 1
                            ba = gb if gb > r0 else r0
                            if bb > r1:
                                bb = r1
                            if bb > ba:
                                col[ba:bb] = [sp] * (bb - ba)
                                if fl + 0.27 < hack_y and gb > r0:
                                    col[ba] = led_pink
                            if mull:
                                continue
                            ga = int(floor_f((ya - fl - 1) * iyb)) + 1
                            if ga < r0:
                                ga = r0
                            if gb > r1:
                                gb = r1
                            if gb <= ga:
                                continue
                            if fl + 0.5 < dark:
                                v = LITTAB[(fl * 131 + hcol) & 4095]
                                if v:
                                    col[ga:gb] = [LITC[v]] * (gb - ga)
                                    col[ga] = LITH[v]
                            # Mechanical floors read as continuous dark belts,
                            # giving the curtain wall a deliberate vertical rhythm.
                            if fl % 7 == 0 and fl > 3:
                                col[ga:gb] = [sp] * (gb - ga)
                            if dark - 0.5 <= fl < dark + 0.5 and flash_on:
                                col[ga:gb] = [(255, 255, 255)] * (gb - ga)
                        # ctOS / DedSec logo panel
                        if y0 <= LOGO_Y0 and y1 >= LOGO_Y1:
                            u = (s / ln - 0.18) / 0.64
                            if 0 <= u < 1:
                                tex = PANEL_DSEC if dark < LOGO_Y1 else PANEL_CTOS
                                pw = len(tex[0])
                                tu = int(u * pw)
                                pr0 = max(r0, int(hz - (LOGO_Y1 - camy) * iF + 0.5))
                                pr1 = min(r1, int(hz - (LOGO_Y0 - camy) * iF + 0.5))
                                nv = len(tex)
                                span = LOGO_Y1 - LOGO_Y0
                                flick = dark < LOGO_Y1 + 1.5 and dark > LOGO_Y1 - 3 and int(now * 15) % 3 == 0
                                for py in range(pr0, pr1):
                                    v = (LOGO_Y1 - (ya - py * yb)) / span
                                    tv = min(nv - 1, max(0, int(v * nv)))
                                    col[py] = (20, 10, 26) if flick else tex[tv][tu]
                    prev_fe = fe
                elif kind == "crown":
                    fin = (s % 0.55) < 0.3
                    fc = FIN[q] if fin else (8, 10, 18)
                    if not fin:
                        if dark < y0:
                            led = PINK_LED if owned and led_on else (30, 12, 30)
                        else:
                            led = mix(CYAN_LED, BLACK, 0.3 * pulse(now, 2, s))
                    for py in range(r0, r1):
                        y = ya - py * yb
                        if y > y1 - 0.35 or y < y0 + 0.25:
                            c = EDGE[q]
                        elif fin:
                            c = fc
                        else:
                            c = led if (y * 2.2 + now * 1.5) % 1.0 < 0.75 else fc
                        col[py] = c
                    prev_fe = fe
                else:
                    # chamfered corner: metal louvres and a vertical LED strip
                    ledc = abs(s - ln / 2) < yb * 0.75
                    cm, cd = CHAM[q], CHAMD[q]
                    if ledc and kind == "office":
                        for py in range(r0, r1):
                            y = ya - py * yb
                            col[py] = led_pink if y < hack_y else ((30, 150, 200) if y < dark else (20, 26, 40))
                    else:
                        col[r0:r1] = [cm] * n_
                        iyb = 1.0 / yb
                        ftop = int(floor_f(ya - r0 * yb))
                        fbot = int(floor_f(ya - (r1 - 1) * yb))
                        for fl in range(ftop, fbot - 1, -1):
                            ba = max(r0, int(floor_f((ya - fl - 0.18) * iyb)) + 1)
                            bb = min(r1, int(floor_f((ya - fl) * iyb)) + 1)
                            if bb > ba:
                                col[ba:bb] = [cd] * (bb - ba)
                    prev_fe = fe
                if edge_col:
                    col[r0:r1] = [EDGE[q]] * n_
                if rim:
                    rc = (90, 210, 255) if (x - 1) not in hits else (255, 70, 170)
                    for py in range(r0, r1):
                        c = col[py]
                        col[py] = ((c[0] + rc[0]) >> 1, (c[1] + rc[1]) >> 1, (c[2] + rc[2]) >> 1)
                old = self.tcols.get(x)
                self.tcols[x] = (min(r0, old[0]), max(r1, old[1])) if old else (r0, r1)
            # Each setback has a raised parapet and short metal outriggers.
            # These follow real corners instead of outlining every glass floor.
            if kind != "lobby":
                for i, (vx, vz) in enumerate(V):
                    bx, bz = V[(i + 1) % len(V)]
                    self.line3(fb, (vx, y1 + 0.12, vz),
                               (bx, y1 + 0.12, bz), (100, 116, 142))
                    self.line3(fb, (vx, y1 - 0.45, vz),
                               (vx, y1 + 0.12, vz), (62, 76, 100))
            # setback roof
            if camy > y1:
                P = [self.proj(vx, y1, vz) for vx, vz in V]
                if all(P):
                    P2 = [(p[0], p[1]) for p in P]
                    fill_poly(fb, w, PH, P2, (22, 22, 34))
                    for i in range(8):
                        pline(fb, w, PH, P2[i - 1][0], P2[i - 1][1], P2[i][0], P2[i][1], (70, 80, 110))
                    if kind == "crown":
                        self.helipad(fb, now)

    def helipad(self, fb, now):
        w, PH = self.w, self.PH
        y = ROOF + 0.02
        n = 24
        pts = [(math.cos(i / n * TAU) * 2.0, y, math.sin(i / n * TAU) * 2.0) for i in range(n + 1)]
        P = [self.proj(*p) for p in pts]
        if all(P):
            fill_poly(fb, w, PH, [(p[0], p[1]) for p in P[:-1]], (40, 40, 52))
            for i in range(n):
                pline(fb, w, PH, P[i][0], P[i][1], P[i + 1][0], P[i + 1][1], (220, 190, 60))
            for a, b in (((-0.7, -0.9), (-0.7, 0.9)), ((0.7, -0.9), (0.7, 0.9)), ((-0.7, 0), (0.7, 0))):
                self.line3(fb, (a[0], y, a[1]), (b[0], y, b[1]), (230, 230, 240))
        for i in range(8):
            a = TAU * i / 8
            q = self.proj(math.cos(a) * 2.9, ROOF + 0.1, math.sin(a) * 2.9)
            if q and (int(now * 2) + i) % 2:
                pline(fb, w, PH, q[0], q[1], q[0], q[1], (255, 60, 50))

    def spire(self, fb, now):
        w, PH = self.w, self.PH
        steel = (120, 126, 156)
        dim = (70, 74, 98)
        legs = [(-0.55, 0.0), (0.55, 0.0), (0.0, 0.55)]
        for lx, lz in legs:
            self.line3(fb, (lx, ROOF, lz), (0, SPIRE, 0), steel)
        yy = ROOF
        i = 0
        while yy < SPIRE - 1:
            f0 = 1 - (yy - ROOF) / (SPIRE - ROOF)
            f1 = 1 - (yy + 1.2 - ROOF) / (SPIRE - ROOF)
            a, b = legs[i % 3], legs[(i + 1) % 3]
            self.line3(fb, (a[0] * f0, yy, a[1] * f0), (b[0] * f1, yy + 1.2, b[1] * f1), dim)
            yy += 1.2
            i += 1
        for yy, col, rate in ((SPIRE + 0.2, (255, 40, 40), 1.2), (ROOF + 5.2, (255, 255, 255), 0.7)):
            q = self.proj(0, yy, 0)
            if not q:
                continue
            on = (now * rate) % 1.0 < 0.45
            if self.shocked and yy > SPIRE:
                col, on = PINK, True
            if on:
                r = max(0.8, min(1.6, 0.25 * self.F / q[2]))
                ellipse_alpha(fb, w, PH, q[0], q[1], r * 2.2, r * 2.2, col, 0.22)
                disc(fb, w, PH, q[0], q[1], r, blend(col, WHITE, 0.4))

    # ------------------------------------------------------------ firewall shields
    def shield_geo(self, L, now):
        yc = yshield(L)
        _, _, A, C, _ = tier_at(yc)
        Rs = (math.hypot(A, A - C) + 0.9) / 0.866
        rot = L * 0.37 + now * 0.12
        V = [(Rs * math.cos(rot + i * TAU / 6), Rs * math.sin(rot + i * TAU / 6)) for i in range(6)]
        E = []
        for i in range(6):
            ax, az = V[i]
            bx, bz = V[(i + 1) % 6]
            ex, ez = (bx - ax) / Rs, (bz - az) / Rs
            nx, nz = -ez, ex
            if nx * ax + nz * az < 0:
                nx, nz = -nx, -nz
            E.append((nx, nz, nx * ax + nz * az, ax, az, ex, ez, Rs, "S"))
        return yc, Rs, rot, V, E

    def hex_point(self, p, Rs, rot, y):
        i = int(p // Rs) % 6
        f = (p % Rs) / Rs
        a0, a1 = rot + i * TAU / 6, rot + (i + 1) * TAU / 6
        x = Rs * (math.cos(a0) + (math.cos(a1) - math.cos(a0)) * f)
        z = Rs * (math.sin(a0) + (math.sin(a1) - math.sin(a0)) * f)
        return x, y, z

    def prep_shields(self, now):
        self.shields = []
        if self.t < INTRO - 0.6 or self.broken >= NF:
            return
        intro = min(1.0, max(0.0, (self.t - INTRO + 0.6) / 0.8))
        atk = max(0.0, self.p - self.broken) if self.t >= INTRO else 0.0
        for L in range(self.broken, min(NF, self.broken + 3)):
            dist = L - self.broken
            vis = (1.0, 0.38, 0.18)[dist] * intro
            yc, Rs, rot, V, E = self.shield_geo(L, now)
            x0, x1 = self.xrange_of(V)
            full = self.column_hits(E, x0, x1)
            self.shields.append((L, yc, Rs, rot, E, full, vis, atk if dist == 0 else 0.0))

    def draw_shields(self, fb, now, back):
        w, PH, F, hz, camy = self.w, self.PH, self.F, self.hz, self.camy
        Cx, Cz, fx, fz, rx, rz = self.Cx, self.Cz, self.fx, self.fz, self.rx, self.rz
        for L, yc, Rs, rot, E, full, vis, atk in reversed(self.shields):
            cur = atk > 0
            col = SHIELD_C
            if cur:
                col = blend(SHIELD_C, PINK, min(1.0, atk * 1.1)) if (atk < 0.45 or int(now * 14) % 4) else (230, 240, 255)
            sc = vis * (0.55 if back else 1.0)
            lv = [0.0, 0.14 * sc, 0.55 * sc, 0.85 * sc]
            r, g, b = col
            memos = [{}, {}, {}, {}, {}]
            hot = (255, 230, 250)
            y0, y1 = yc - 1.0, yc + 1.0
            P6 = 6 * Rs
            if cur and self.cracks:
                hp, hy = self.cracks[1], self.cracks[2]
                rip = atk * 9.0
            else:
                hp, hy, rip = 0.0, 0.0, -9.0
            outline = (not cur and L > self.broken) or back
            if back and L > self.broken:
                continue
            for x, (te, fe, tx, fxi) in full.items():
                if back:
                    if fxi < 0:
                        continue
                    t, fi = tx, fxi
                else:
                    t, fi = te, fe
                nx, nz, d, vx, vz, ex, ez, ln, _ = E[fi]
                k = self.KS[x]
                dx, dz = fx + rx * k, fz + rz * k
                s = (Cx + t * dx - vx) * ex + (Cz + t * dz - vz) * ez
                p = fi * Rs + s
                iF = F / t
                r0 = int(hz - (y1 - camy) * iF + 0.5)
                r1 = int(hz - (y0 - camy) * iF + 0.5)
                corner = s < 1.2 / iF or s > ln - 1.2 / iF
                tx_ = int((p % HTW) * HKX)
                yb = t / F
                ya = camy + (hz - 0.5) * yb
                dp = ((p - hp + P6 / 2) % P6) - P6 / 2
                dp2 = dp * dp
                col_ = fb[x]
                if outline and not corner:
                    rows = [py for py in (r0, r1 - 1) if 0 <= py < PH]
                else:
                    rows = range(max(0, r0), min(PH, r1))
                for py in rows:
                    if py == r0 or py == r1 - 1:
                        lvl = 3
                    elif corner:
                        lvl = 2
                    else:
                        y = ya - py * yb
                        lvl = HEXT[int(((y - y0) % HTH) * HKY)][tx_]
                        if rip > 0:
                            dd = dp2 + (y - hy) * (y - hy)
                            if dd < rip * rip and dd > (rip - 1.6) ** 2 and lvl:
                                lvl = 4
                        if lvl == 0:
                            continue
                    c = col_[py]
                    # The shield remains luminous in free air, translucent over
                    # architecture: belts, columns and hacked floors stay visible.
                    span = self.tcols.get(x) if not back else None
                    over_tower = span is not None and span[0] <= py < span[1]
                    transmission = 0.32 if over_tower else 1.0
                    key = (c, over_tower)
                    m = memos[lvl]
                    o = m.get(key)
                    if o is None:
                        if lvl == 4:
                            a = 0.45 * sc * transmission
                            o = (int(c[0] + (hot[0] - c[0]) * a), int(c[1] + (hot[1] - c[1]) * a),
                                 int(c[2] + (hot[2] - c[2]) * a))
                        else:
                            a = lv[lvl] * transmission
                            o = (int(c[0] + (r - c[0]) * a) & 0xF8, int(c[1] + (g - c[1]) * a) & 0xF8, int(c[2] + (b - c[2]) * a) & 0xF8)
                        m[key] = o
                    col_[py] = o
            if not back and cur:
                self.draw_cracks(fb, now, atk, Rs, rot, yc)

    def make_cracks(self, L, now):
        yc, Rs, rot, V, E = self.shield_geo(L, now)
        # perimeter coordinate facing the camera
        ca = math.atan2(self.Cz, self.Cx) + random.uniform(-0.35, 0.35) - rot
        ca %= TAU
        i = int(ca // (TAU / 6))
        f = (ca % (TAU / 6)) / (TAU / 6)
        hp = (i + f) * Rs
        hy = yc + random.uniform(-0.2, 0.2)
        cr = []
        n = 7
        for j in range(n):
            ang = j / n * TAU + random.uniform(-0.3, 0.3)
            p, y = hp, hy
            pts = [(p, y)]
            for _ in range(random.randint(5, 8)):
                ang += random.uniform(-0.5, 0.5)
                st = random.uniform(0.2, 0.45)
                p += math.cos(ang) * st
                y += math.sin(ang) * st * 0.45
                y = min(yc + 0.95, max(yc - 0.95, y))
                pts.append((p, y))
            cr.append(pts)
            if random.random() < 0.6:
                k = random.randint(1, len(pts) - 2)
                bp, by = pts[k]
                bang = ang + random.choice((-1, 1)) * 1.1
                br = [(bp, by)]
                for _ in range(3):
                    bp += math.cos(bang) * 0.4
                    by = min(yc + 0.95, max(yc - 0.95, by + math.sin(bang) * 0.2))
                    br.append((bp, by))
                cr.append(br)
        self.cracks = (L, hp, hy, cr)

    def draw_cracks(self, fb, now, atk, Rs, rot, yc):
        if not self.cracks:
            return
        w, PH = self.w, self.PH
        _, hp, hy, cr = self.cracks
        grow = min(1.0, atk / 0.62)
        ta = self.t_axis
        for j, pts in enumerate(cr):
            nseg = len(pts) - 1
            kseg = grow * nseg
            for i in range(int(kseg + 0.999)):
                (p1, y1_), (p2, y2_) = pts[i], pts[i + 1]
                frac = min(1.0, kseg - i)
                p2, y2_ = p1 + (p2 - p1) * frac, y1_ + (y2_ - y1_) * frac
                a = self.proj(*self.hex_point(p1, Rs, rot, y1_))
                b = self.proj(*self.hex_point(p2, Rs, rot, y2_))
                if a and b and (a[2] + b[2]) / 2 < ta:
                    col = (255, 255, 255) if (i + j + int(now * 18)) % 4 else (255, 90, 190)
                    pline(fb, w, PH, a[0], a[1], b[0], b[1], col)
        q = self.proj(*self.hex_point(hp, Rs, rot, hy))
        if q:
            r = (1.2 + 2.5 * grow) * (0.7 + 0.3 * pulse(now, 30))
            ellipse_alpha(fb, w, PH, q[0], q[1], r * 2.2, r * 1.4, (255, 120, 210), 0.35)
            disc(fb, w, PH, q[0], q[1], max(0.8, r * 0.5), (255, 245, 255))
            self.hit_q = q

    def shatter(self, L, now):
        yc, Rs, rot, V, E = self.shield_geo(L, now)
        rnd = random
        cols, P6 = 16, 6 * Rs
        y0, y1 = yc - 1.0, yc + 1.0
        grid = []
        for i in range(cols + 1):
            p = i / cols * P6
            grid.append([(p + rnd.uniform(-0.25, 0.25) * (0 < i < cols), yy) for yy in
                         (y0, y1)])
        grid[-1] = [(P6 + q[0] - grid[0][j][0] * 0, q[1]) for j, q in enumerate(grid[0])]
        for i in range(cols):
            for j in range(1):
                a, b, c, d = grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]
                for tri in ((a, b, c), (a, c, d)):
                    P = [self.hex_point(p, Rs, rot, y) for p, y in tri]
                    cx = sum(q[0] for q in P) / 3
                    cy = sum(q[1] for q in P) / 3
                    cz = sum(q[2] for q in P) / 3
                    off = [[(q[0] - cx) * 0.55, (q[1] - cy) * 0.55, (q[2] - cz) * 0.55] for q in P]
                    rr = math.hypot(cx, cz) or 1
                    sp = rnd.uniform(1.5, 4.5)
                    ax, ay, az = rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)
                    an = math.sqrt(ax * ax + ay * ay + az * az) or 1
                    self.shards.append([cx, cy, cz, cx / rr * sp, rnd.uniform(-0.5, 2.5), cz / rr * sp, off,
                                        (ax / an, ay / an, az / an), rnd.uniform(3, 8), 0.0, rnd.uniform(0.7, 1.25),
                                        rnd.choice((SHIELD_C, SHIELD_C, (200, 245, 255), (255, 90, 190)))])
        if len(self.shards) > 90:
            self.shards = self.shards[-90:]
        self.pulses.append((now, yc, Rs))
        self.broken = L + 1
        self.cracks = None
        self.last_break = now
        self.glitch.trigger(now, 0.12 if L % 5 != 4 else 0.3)
        q = getattr(self, "hit_q", None)
        if q:
            for _ in range(40):
                a = rnd.uniform(0, TAU)
                v = rnd.uniform(8, 40)
                self.sparks.append([q[0], q[1], math.cos(a) * v, math.sin(a) * v * 0.7, 0.0, rnd.uniform(0.3, 0.8),
                                    rnd.choice(((255, 255, 255), (255, 120, 210), (120, 240, 255)))])

    def update_shards(self, dt):
        alive = []
        for sh in self.shards:
            sh[9] += dt
            if sh[9] > sh[10]:
                continue
            sh[4] -= 9.0 * dt
            sh[0] += sh[3] * dt
            sh[1] += sh[4] * dt
            sh[2] += sh[5] * dt
            ux, uy, uz = sh[7]
            ang = sh[8] * dt
            ca, sa = math.cos(ang), math.sin(ang)
            for o in sh[6]:
                x, y, z = o
                dot = ux * x + uy * y + uz * z
                cx_, cy_, cz_ = uy * z - uz * y, uz * x - ux * z, ux * y - uy * x
                o[0] = x * ca + cx_ * sa + ux * dot * (1 - ca)
                o[1] = y * ca + cy_ * sa + uy * dot * (1 - ca)
                o[2] = z * ca + cz_ * sa + uz * dot * (1 - ca)
            alive.append(sh)
        self.shards = alive

    def draw_shards(self, fb, back):
        w, PH, ta = self.w, self.PH, self.t_axis
        for sh in self.shards:
            cx, cy, cz = sh[0], sh[1], sh[2]
            P = []
            for o in sh[6]:
                q = self.proj(cx + o[0], cy + o[1], cz + o[2])
                if not q:
                    P = None
                    break
                P.append(q)
            if not P:
                continue
            depth = (P[0][2] + P[1][2] + P[2][2]) / 3
            if (depth > ta) != back:
                continue
            f = 1 - sh[9] / sh[10]
            P2 = [(q[0], q[1]) for q in P]
            fill_poly(fb, w, PH, P2, mix((10, 30, 60), sh[11], 0.25 + 0.75 * f))
            if f > 0.4:
                pline(fb, w, PH, P2[0][0], P2[0][1], P2[1][0], P2[1][1], blend(sh[11], WHITE, 0.5))

    def draw_pulses(self, fb, now, back):
        ta = self.t_axis
        keep = []
        for t0, yc, Rs in self.pulses:
            age = now - t0
            if age > 0.9:
                continue
            keep.append((t0, yc, Rs))
            rr = Rs + ease_out(age / 0.9) * 16
            col = blend((255, 60, 170), BLACK, age / 0.9)
            n = 32
            prev = None
            for i in range(n + 1):
                a = i / n * TAU
                p = self.proj(math.cos(a) * rr, yc, math.sin(a) * rr)
                if p and prev and ((p[2] + prev[2]) / 2 > ta) == back:
                    pline(fb, self.w, self.PH, prev[0], prev[1], p[0], p[1], col)
                prev = p
        self.pulses = keep

    # ------------------------------------------------------------ actors
    def drones(self, now):
        out = []
        if self.broken >= NF or self.t < INTRO:
            return out
        yc = yshield(self.broken)
        _, Rs, _, _, _ = self.shield_geo(self.broken, now)[:5]
        base = math.atan2(self.Cz, self.Cx)
        for i in range(3):
            a = base + (i - 1) * 0.55 + 0.12 * math.sin(now * 1.3 + i)
            rad = Rs + 3.0 + 0.6 * math.sin(now + i * 2)
            out.append((math.cos(a) * rad, yc + 1.6 + 0.5 * math.sin(now * 2.1 + i), math.sin(a) * rad, i))
        return out

    def draw_drones(self, fb, now, back):
        w, PH, ta = self.w, self.PH, self.t_axis
        atk = self.p - self.broken
        q_hit = getattr(self, "hit_q", None)
        for x, y, z, i in self.drones(now):
            q = self.proj(x, y, z)
            if not q or (q[2] > ta) != back:
                continue
            sc = max(1.0, min(2.6, 0.5 * self.F / q[2]))
            if (not back and q_hit and self.cracks and 0.0 < atk < 0.7
                    and int(now * 10 + i * 3) % 5):
                lc = (255, 60, 170) if i % 2 == 0 else (60, 230, 255)
                pline(fb, w, PH, q[0], q[1] + 1, q_hit[0], q_hit[1], lc)
                pline(fb, w, PH, q[0] + 1, q[1] + 1, q_hit[0] + 1, q_hit[1], blend(lc, WHITE, 0.6))
            arm = int(sc * 1.4) + 1
            pline(fb, w, PH, q[0] - arm, q[1], q[0] + arm, q[1], (60, 62, 84))
            ellipse_alpha(fb, w, PH, q[0], q[1] + 1, sc * 2.2, sc * 1.6, (255, 40, 150), 0.18)
            disc(fb, w, PH, q[0], q[1] + 0.5, max(0.8, sc * 0.5), (46, 44, 62))
            for sx in (-arm, arm):
                pline(fb, w, PH, q[0] + sx - 1, q[1] - 1, q[0] + sx + 1, q[1] - 1,
                      (150, 150, 170) if int(now * 30 + i) % 2 else (90, 90, 110))
            fb_y, fb_x = int(q[1] + 1.5), int(q[0])
            if 0 <= fb_y < PH and 0 <= fb_x < w:
                fb[fb_x][fb_y] = PINK if int(now * 6 + i) % 2 else (255, 200, 230)

    def heli_state(self, now):
        a = 1.3 - now * 0.17
        rad = 33.0
        y = self.camy + 4.5 + 1.5 * math.sin(now * 0.4)
        if self.t > CLIMB_END:
            y = 34 + 2 * math.sin(now * 0.4)
        return (math.cos(a) * rad, y, math.sin(a) * rad), a

    def draw_heli(self, fb, now, back):
        w, PH, ta = self.w, self.PH, self.t_axis
        (x, y, z), a = self.heli_state(now)
        q = self.proj(x, y, z)
        if not q or (q[2] > ta) != back:
            return
        # second, distant patrol: only strobes
        sc = self.F / q[2]
        L = max(3.0, 3.2 * sc)
        nxt = self.proj(x - math.sin(a) * -1, y, z + math.cos(a) * -1)
        dirx = 1 if (nxt and nxt[0] > q[0]) else -1
        cx, cy = q[0], q[1]
        body = (34, 36, 50)
        if not back and self.t < CLIMB_END + F_DARK1:
            # searchlight onto the facade
            ty = y - 3.0
            ang = math.atan2(z, x)
            tq = self.proj(math.cos(ang) * 5.2, ty, math.sin(ang) * 5.2)
            if tq and tq[2] < q[2] + 6:
                rad = max(2.0, 1.4 * self.F / tq[2])
                fill_alpha(fb, w, PH, [(cx + dirx * L * 0.3, cy + 1), (tq[0] - rad, tq[1]), (tq[0] + rad, tq[1])],
                           (220, 230, 255), 0.12)
                ellipse_alpha(fb, w, PH, tq[0], tq[1], rad * 1.2, rad * 0.8, (235, 240, 255), 0.35)
        ellipse_alpha(fb, w, PH, cx, cy, L * 0.45, max(1.0, L * 0.2), body, 0.95)
        pline(fb, w, PH, cx - dirx * L * 0.3, cy, cx - dirx * L * 1.0, cy - L * 0.08, body)
        pline(fb, w, PH, cx - dirx * L * 1.0, cy - L * 0.25, cx - dirx * L * 1.0, cy + L * 0.05, body)
        pline(fb, w, PH, cx - L * 0.4, cy + L * 0.28, cx + L * 0.4, cy + L * 0.28, (60, 62, 80))
        rot = (110, 112, 130) if int(now * 24) % 2 else (64, 66, 84)
        pline(fb, w, PH, cx - L * 0.95, cy - L * 0.3, cx + L * 0.95, cy - L * 0.3, rot)
        blink = int(now * 4) % 2
        pline(fb, w, PH, cx - 1, cy - 1, cx - 1, cy - 1, (255, 40, 40) if blink else (40, 60, 255))
        pline(fb, w, PH, cx + dirx * L * 0.42, cy, cx + dirx * L * 0.42, cy, (255, 250, 220))

    def far_patrol(self, fb, now):
        a = now * 0.08 + 2.0
        q = self.proj(math.cos(a) * 95, self.camy + 14, math.sin(a) * 95)
        if q:
            blink = int(now * 3) % 3
            x, y = int(q[0]), int(q[1])
            if 0 <= x < self.w - 2 and 0 <= y < self.PH:
                fb[x][y] = (255, 40, 40) if blink == 0 else (40, 40, 60)
                fb[x + 2][y] = (60, 90, 255) if blink == 1 else (40, 40, 60)

    def draw_clouds(self, fb, now, back):
        w, PH, F, ta = self.w, self.PH, self.F, self.t_axis
        for cl in self.clouds:
            a0, rho, y, size, sp, puffs = cl
            a = a0 + now * sp
            bx, bz = math.cos(a) * rho, math.sin(a) * rho
            for ox, oy, sz in puffs:
                px, pz = bx - math.sin(a) * ox * size, bz + math.cos(a) * ox * size
                q = self.proj(px, y + oy * size, pz)
                if not q or (q[2] > ta) != back:
                    continue
                if q[2] < 4:
                    continue
                rx = sz * size * F / q[2]
                if rx < 2:
                    continue
                fade = min(1.0, (q[2] - 4) / 8)
                rx = min(rx, w * 0.32)
                if back and rx > 30:
                    continue
                ry = rx * 0.26
                col = (112, 84, 134) if y < 40 else (90, 90, 140)
                if back:
                    ellipse_alpha(fb, w, PH, q[0], q[1], rx, ry, col, 0.2 * fade)
                else:  # fb is row-major here (after the transpose)
                    _ellipse_alpha_rm(fb, w, PH, q[0], q[1], rx, ry, col, 0.2 * fade)

    def draw_sparks(self, fb, dt):
        w, PH = self.w, self.PH
        alive = []
        for sp in self.sparks:
            sp[4] += dt
            if sp[4] > sp[5]:
                continue
            sp[3] += 30 * dt
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            x, y = int(sp[0]), int(sp[1])
            if 0 <= x < w and 0 <= y < PH:
                fb[x][y] = blend(sp[6], BLACK, sp[4] / sp[5] * 0.7)
            alive.append(sp)
        self.sparks = alive[-300:]

    # ------------------------------------------------------------ finale
    def draw_skull(self, fb, now, fe):
        w, PH = self.w, self.PH
        k = (fe - F_SHOCK) / 0.9
        if k <= 0:
            return
        fade = 1.0 if fe < F_OUT - 0.5 else max(0.0, (F_OUT - fe) / 0.5)
        sh = int(PH * 0.6)
        sw = int(sh * 0.95)
        cells = skull_raster(sw, sh)
        x0 = int(w * 0.64 - sw / 2)
        y0 = int(PH * 0.04 + math.sin(now * 1.2) * 1.5)
        reveal = min(1.0, k) * sh
        pal = [blend((90, 10, 60), (255, 214, 240), i / 7) for i in range(8)] + [None, (255, 30, 130), (90, 240, 255)]
        jit = {}
        if random.random() < 0.12:
            for _ in range(3):
                jit[random.randrange(sh)] = random.randint(-4, 4)
        memo = {}
        alpha_base = 0.85 * fade
        for u, v, idx in cells:
            if v > reveal:
                continue
            col = pal[idx]
            if col is None:
                continue
            py = y0 + v
            if not 0 <= py < PH:
                continue
            x = x0 + u + jit.get(v, 0)
            if not 0 <= x < w:
                continue
            a = alpha_base * (0.55 if v % 3 == 0 else 1.0)
            if reveal - v < 2 and k < 1:
                col, a = (255, 255, 255), 1.0
            c = fb[x][py]
            key = (c, col, a)
            o = memo.get(key)
            if o is None:
                o = memo[key] = (int(c[0] + (col[0] - c[0]) * a), int(c[1] + (col[1] - c[1]) * a),
                                 int(c[2] + (col[2] - c[2]) * a))
            fb[x][py] = o
        # projector beams from the spire
        q = self.proj(0, SPIRE, 0)
        if q:
            P = [(q[0], q[1]), (x0 + sw * 0.15, y0 + sh * 0.25), (x0 + sw * 0.2, y0 + sh * 0.9)]
            fill_alpha(fb, w, PH, P, (255, 60, 170), 0.10 * fade)
        self.skull_box = (x0, y0, sw, sh)

    def shockwave(self, fb, now, back):
        if not self.shocked:
            return
        age = now - self.shock_t
        if age > 3.0:
            return
        ta = self.t_axis
        for yy, sp in ((SPIRE - 1, 70.0), (0.3, 140.0)):
            rr = 3 + age * sp
            col = blend(blend(WHITE, PINK, min(1.0, age / 0.8)), BLACK, age / 3.0)
            n = 72
            prev = None
            for i in range(n + 1):
                a = i / n * TAU
                p = self.proj(math.cos(a) * rr, yy, math.sin(a) * rr)
                if p and prev and ((p[2] + prev[2]) / 2 > ta) == back:
                    pline(fb, self.w, self.PH, prev[0], prev[1], p[0], p[1], col)
                prev = p

    # ------------------------------------------------------------ HUD
    def hud(self, s, now):
        w, h = self.w, self.h
        t = self.t
        alt = self.camy * 4.1
        s.text(2, 0, "▌BLUME ctOS TOWER", CYAN)
        s.text(2, 1, "▌ALT %5.1fm  HDG %03d" % (alt, int(math.degrees(self.alpha)) % 360), GREY)
        lay = "FIREWALL LAYER %02d/%02d" % (min(NF, self.broken), NF)
        s.text(w - len(lay) - 2, 0, lay, PINK if self.broken < NF else YELLOW)
        bw = min(NF, max(10, w // 5))
        filled = int(bw * self.broken / NF)
        s.text(w - bw - 2, 1, "▰" * filled, PINK)
        s.text(w - bw - 2 + filled, 1, "▱" * (bw - filled), DIM_PINK)
        if w >= 110:
            st = "DEDSEC UPLINK ● 3 DRONES"
            s.center(0, st, blend(PINK, WHITE, pulse(now, 4) * 0.5))
        top, bot = 3, h - 4
        if bot - top > 6:
            prev = None
            for yy in range(top, bot + 1):
                fl = NF - 1 - int((yy - top) / (bot - top) * (NF - 1) + 0.5)
                ch = "┤" if fl % 5 == 0 and fl != prev else "│"
                s.put(1, yy, ch, PINK if fl < self.broken else DIM_CYAN)
                if fl % 10 == 0 and fl and fl != prev:
                    s.text(3, yy, "%02d" % fl, GREY)
                prev = fl
            my = bot - int(min(NF, self.p) / NF * (bot - top))
            s.text(2, my, "◄", YELLOW)
        fe = t - CLIMB_END
        if t < INTRO:
            msg, col = "> CONNECTING TO BLUME ctOS " + SPIN[int(now * 12) % 10], CYAN
        elif self.broken < NF:
            pc = int(min(1.0, (self.p - self.broken) / 0.7) * 100)
            if now - self.last_break < 0.6:
                msg, col = "> LAYER %02d BREACHED" % self.broken, PINK
            else:
                msg, col = "> BREACHING LAYER %02d %s %3d%%" % (self.broken + 1, SPIN[int(now * 12) % 10], pc), YELLOW
        elif fe < F_DARK0:
            msg, col = "> ALL FIREWALLS DOWN // CORE EXPOSED", PINK if int(now * 6) % 2 else WHITE
        elif fe < F_SHOCK:
            msg, col = "> CUTTING TOWER POWER " + SPIN[int(now * 12) % 10], YELLOW
        else:
            msg, col = "> BLUME ctOS OFFLINE // SF GRID IS OURS", PINK
        s.text(3, h - 2, msg[:w - 6], col)
        if w >= 120:
            tag = "DEDSEC // ctOS TOWER RAID"
            s.text(w - len(tag) - 2, h - 2, tag, GREY)
        box = getattr(self, "skull_box", None)
        if fe > F_SHOCK + 1.0 and box and fe < F_OUT - 0.3:
            x0, y0, sw, sh = box
            yy = (y0 + sh) // 2 + 1
            msg = "WE ARE DEDSEC"
            if yy < h - 3:
                s.text(int(x0 + sw / 2 - len(msg) / 2), yy, msg, PINK if int(now * 3) % 2 else WHITE)
        # BLUME sign on the lobby
        if t < INTRO + 6:
            q = self.proj(0, 3.4, 0)
            if q:
                qq = self.proj(-self.fx * 7.2, 3.4, -self.fz * 7.2)
                if qq and 2 <= int(qq[1] / 2) < h - 3:
                    s.text(int(qq[0]) - 2, int(qq[1] / 2), "BLUME", (220, 240, 255))

    # ------------------------------------------------------------ frame
    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "blackout", "ctOS / POWER DOWN", CYAN)
        if 0.1 < t < 0.85:
            q = self.proj(0, ROOF * 0.65, 0) if hasattr(self, "Cx") else None
            cx, py = (q[0], q[1]) if q else (s.w / 2, s.ph / 2)
            radius = (1 - t) * min(s.w / 5, s.ph / 6)
            for i in range(48):
                a = i * math.tau / 48
                s.pixel(int(cx + math.cos(a) * radius), int(py + math.sin(a) * radius * 0.38),
                        blend(CYAN, BLACK, t))

    def step(self, s, now):
        dt, self.last = min(0.1, max(0.0, now - self.last)), now
        t = now - self.t0
        if t > CYCLE:
            self.reset(now)
            self.glitch.trigger(now, 0.4)
            t = 0.0
        self.t = t
        self.camera(t, now)
        fe = t - CLIMB_END
        # breach progress
        if t >= INTRO:
            while self.broken < NF and self.p - self.broken >= 0.7:
                if self.cracks is None or self.cracks[0] != self.broken:
                    self.make_cracks(self.broken, now)
                self.shatter(self.broken, now)
            if self.broken < NF and (self.cracks is None or self.cracks[0] != self.broken):
                self.make_cracks(self.broken, now)
        if self.broken >= NF:
            self.cracks = None
        self.dark_y = 99.0
        if fe > F_DARK0:
            self.dark_y = ROOF * (1 - min(1.0, (fe - F_DARK0) / (F_DARK1 - F_DARK0))) - 0.5
        if fe > F_SHOCK and not self.shocked:
            self.shocked = True
            self.shock_t = now
            self.flash = 1.0
            self.glitch.trigger(now, 0.45)
        glitch = self.glitch.active(now)
        if DATA.beat > 0.8 and random.random() < 0.08:
            self.glitch.trigger(now, 0.06)
        self.flash = max(0.0, self.flash - dt * 1.8)
        w, PH = self.w, self.PH
        self.hit_q = None if self.cracks is None else getattr(self, "hit_q", None)

        fb = self.draw_sky(now)
        self.searchlights(fb, now)
        if fe > F_SHOCK:
            self.draw_skull(fb, now, fe)
        cover = [False] * w
        # tower first pass only to know fully covered columns: cheap estimate from the main tier
        self.estimate_cover(cover)
        self.draw_city(fb, now, cover)
        self.plaza(fb, now)
        self.far_patrol(fb, now)
        self.prep_shields(now)
        self.draw_clouds(fb, now, True)
        self.draw_pulses(fb, now, True)
        self.shockwave(fb, now, True)
        self.draw_shields(fb, now, True)
        self.draw_shards(fb, True)
        self.draw_drones(fb, now, True)
        self.draw_heli(fb, now, True)
        self.draw_tower(fb, now, fe, [False] * w)
        self.spire(fb, now)
        self.draw_shields(fb, now, False)
        self.update_shards(dt)
        self.draw_shards(fb, False)
        self.draw_pulses(fb, now, False)
        self.draw_drones(fb, now, False)
        self.draw_heli(fb, now, False)
        self.shockwave(fb, now, False)
        self.draw_sparks(fb, dt)
        rows = [list(r) for r in zip(*fb)]
        self.draw_clouds(rows, now, False)
        for y in range(self.h):
            s.pt[y] = rows[2 * y]
            s.pb[y] = rows[2 * y + 1]
        self.hud(s, now)
        text_over_pixels(s)
        if self.flash > 0.05:
            tint_rows(s, 0, s.h, (255, 200, 235), self.flash * 0.7)
        postfx(s, now, glitch)

    def estimate_cover(self, cover):
        """Columns fully hidden by the tower (the city is skipped there); caches tier hits."""
        F, hz, camy, PH = self.F, self.hz, self.camy, self.PH
        spans = {}
        self.tier_cache = {}
        for tier in TIERS:
            y0, y1, A, C, kind = tier
            V, E = self.tier_geo(tier)
            x0, x1 = self.xrange_of(V)
            hits = self.column_hits(E, x0, x1)
            self.tier_cache[tier] = (V, E, x0, x1, hits)
            for x, (t, fe, tx, fo) in hits.items():
                iF = F / t
                spans.setdefault(x, []).append((hz - (y1 - camy) * iF, hz - (y0 - camy) * iF))
        for x, sp in spans.items():
            sp.sort()
            reach = 0.5
            for a, b in sp:
                if a > reach + 0.5:
                    break
                reach = max(reach, b)
            if reach >= PH - 0.5:
                cover[x] = True

"""GOLDENGATE: cinematic day/night timelapse of the Golden Gate Bridge, seen by ctOS cam 04."""

import math
import random
import time

import numpy as np

from lib import BLACK, CYAN, GREY, PINK, WHITE, YELLOW, blend
from sysdata import DATA

NAME = "GOLDENGATE"

# DedSec skull bitmap (local copy so this scene does not depend on another mode's internals)
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

# bridge dimensions (1 unit ~ 10 m, heights a bit exaggerated)
TX = 64.0       # tower x
HT = 31.0       # tower height
DK = 7.5        # deck top
DW = 4.0        # deck half width
ANCH = 100.0    # anchorage x
ROAD = 175.0    # road extends to here

TOWER = np.array((222, 66, 46), float)
DECK = np.array((170, 50, 40), float)
CABLE = np.array((200, 70, 50), float)
STONE = np.array((95, 85, 90), float)
CITY = np.array((48, 50, 70), float)
FLOOD = np.array((255, 150, 70), float)

MSGS = ["FOG DENSITY ALERT", "TRAFFIC FLOW NOMINAL", "BRIDGE TOLL SYSTEM ONLINE", "MARINE TRAFFIC: 3 VESSELS",
        "WIND SHEAR WARNING", "CAMERA STABILISED", "ctOS UPTIME 99.97%", "NUDLE MAPS SYNC OK"]


def lerp(a, b, t):
    return a + (b - a) * t


def keyed(keys, x):
    """Piecewise-linear lookup in [(x, value), ...] (values numpy arrays)."""
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, v0), (x1, v1) in zip(keys, keys[1:]):
        if x <= x1:
            u = (x - x0) / (x1 - x0)
            return tuple(a + (b - a) * u for a, b in zip(v0, v1))
    return keys[-1][1]


def C(*v):
    return np.array(v, float)


# sky keyframes on sun elevation (-1..1): (top, horizon) for dawn and dusk
SKY_DUSK = [(-1.0, (C(3, 3, 14), C(18, 12, 40))),
            (-0.3, (C(6, 5, 24), C(40, 18, 64))),
            (-0.1, (C(28, 14, 66), C(170, 40, 110))),
            (0.04, (C(70, 36, 120), C(255, 96, 70))),
            (0.22, (C(60, 90, 170), C(250, 170, 130))),
            (0.5, (C(36, 104, 200), C(150, 200, 240))),
            (1.0, (C(30, 96, 196), C(140, 196, 240)))]
SKY_DAWN = [(-1.0, (C(3, 3, 14), C(18, 12, 40))),
            (-0.3, (C(8, 8, 30), C(36, 22, 70))),
            (-0.1, (C(36, 30, 90), C(150, 80, 120))),
            (0.04, (C(70, 70, 140), C(255, 150, 90))),
            (0.22, (C(60, 110, 190), C(245, 200, 150))),
            (0.5, (C(36, 104, 200), C(150, 200, 240))),
            (1.0, (C(30, 96, 196), C(140, 196, 240)))]


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.W, self.PH = w, 2 * h
        self.cx = w / 2.0
        self.cy = self.PH * 0.53
        self.f = min(0.62 * w, 1.25 * self.PH)
        self.hor = int(math.ceil(self.cy))
        self.rng = random.Random()
        self.last = self.t0 = time.time()
        self.p0 = (DATA.hour() / 24.0) % 1.0
        self.period = 84.0
        self.cols = np.arange(self.W)
        self.rows = np.arange(self.PH)
        self.prev = None
        self.cache_t = [None] * h
        self.cache_b = [None] * h
        self.glitch_until = 0.0
        self.skull_t = self.t0 + self.rng.uniform(18, 30)
        self.msg = (self.rng.choice(MSGS), self.t0 + 3)
        self.next_msg = self.t0 + 12
        self.spark = None
        self.spark_t = 0.0
        self.static = self.work = None
        self.stage = 0
        self.w_occl = np.zeros((self.PH, self.W), bool)
        self.w_fogA = None
        self.w_ripple = np.zeros(self.PH - self.hor, int)
        self.fog_now = 0.3
        self.build_bridge()
        self.build_world()
        self.pos = np.zeros(3)
        self.yaw = 0.0

    # ------------------------------------------------------------------ scene setup
    def build_bridge(self):
        # (x0, x1, y0, y1, z0, z1, material, layer); layers: 0 far legs, 1 struts, 2 piers, 4 near legs
        # (3 = deck + traffic, drawn separately)
        boxes = []
        for tx in (-TX, TX):
            for zs in (-DW, DW):
                lay = 0 if zs > 0 else 4
                boxes.append((tx - 1.1, tx + 1.1, 0, HT, zs - 0.9, zs + 0.9, "tower", lay))
                boxes.append((tx - 1.6, tx + 1.6, -0.5, 2.5, zs - 1.4, zs + 1.4, "stone", lay))
            for y0, y1 in ((DK - 2.6, DK - 1.4), (15.5, 16.8), (21.5, 22.8), (27.0, HT)):
                boxes.append((tx - 0.8, tx + 0.8, y0, y1, -DW + 0.9, DW - 0.9, "strut", 1))
            boxes.append((tx - 1.3, tx + 1.3, HT, HT + 0.8, -DW - 1.0, DW + 1.0, "tower", 1))
        for ax in (-ANCH, ANCH):
            boxes.append((ax - 4, ax + 4, -0.5, DK - 0.4, -DW - 1, DW + 1, "stone", 2))
        for px in (-ANCH - 25, -ANCH - 50, ANCH + 25, ANCH + 50):
            boxes.append((px - 1, px + 1, 0, DK - 1.2, -DW + 0.5, DW - 0.5, "stone", 2))
        self.boxes = boxes
        self.box_P = {m: self.box_verts([b[:6] for b in boxes], m) for m in (False, True)}
        # cables: polyline points along x for each side
        def cable_y(x):
            ax = abs(x)
            if ax <= TX:
                return DK + 0.8 + (HT + 0.4 - DK - 0.8) * (x / TX) ** 2
            t = (ax - TX) / (ANCH - TX)
            return lerp(HT + 0.4, DK + 0.6, t) - 2.2 * math.sin(t * math.pi)
        self.cable_y = cable_y
        self.cables = {}
        xs = np.arange(-ANCH, ANCH + 0.01, 4.0)
        sx = np.array([x for x in xs if abs(abs(x) - TX) > 2 and abs(abs(x) - ANCH) > 4])
        for zs in (-DW, DW):
            pts = np.array([(x, cable_y(x), zs) for x in xs])
            top = np.array([(x, cable_y(x), zs) for x in sx])
            bot = top.copy()
            bot[:, 1] = DK
            self.cables[zs] = (pts, top, bot)

    def build_world(self):
        r = self.rng
        # city skyline far across the water (left/back)
        self.city = []
        x = -230.0
        while x < 96:
            bw = r.uniform(5, 13)
            core = max(0.0, 1 - abs(x + 20) / 80)
            h = r.uniform(8, 22) * (1 + 1.4 * core)
            z = r.uniform(270, 340)
            self.city.append([x, x + bw, 0, h, z, z + r.uniform(6, 14)])
            x += bw + r.uniform(-2, 3)
        self.city.append([-16, -4, 0, 72, 292, 304])               # salesforce-ish tall tower
        self.pyramid = (34.0, 286.0, 8.0, 58.0)                     # transamerica-ish
        self.city_P = np.array([((b[0], b[2], b[4]), (b[1], b[3], b[4])) for b in self.city], float).reshape(-1, 3)
        self.city_order = sorted(range(len(self.city)), key=lambda i: -self.city[i][4])
        # windows: points on z0 faces of city boxes
        wins, owner = [], []
        for i, (x0, x1, y0, y1, z0, z1) in enumerate(self.city):
            for wy in np.arange(2.5, y1 - 1, 3.6):
                for wx in np.arange(x0 + 1.5, x1 - 1, 3.4):
                    if r.random() < 0.5:
                        wins.append((wx, wy, z0 - 0.1))
                        owner.append(i)
        self.win = np.array(wins, float) if wins else np.zeros((0, 3))
        self.win_col = np.array([r.choice(((255, 210, 120), (255, 230, 170), (120, 230, 255), (255, 120, 200)))
                                 if r.random() < 0.9 else (255, 255, 255) for _ in wins], float)
        self.win_phase = np.array([r.uniform(0, 1) for _ in wins])
        # Marin headlands (right, behind north tower) and far ridge
        self.marin = [(ANCH + 4, 2, -10), (130, 18, 0), (160, 30, 30), (210, 36, 70), (270, 28, 120),
                      (330, 34, 170), (420, 22, 240), (560, 16, 330), (800, 10, 450)]
        self.marin_lights = [(r.uniform(115, 400), r.uniform(1.5, 8), r.uniform(-5, 200)) for _ in range(40)]
        self.marin_lights = [(x, min(y, 0.6 * self.hill_y(x)), z) for x, y, z in self.marin_lights]
        self.far = [(-1500 + i * 120, r.uniform(15, 55) if i % 3 else r.uniform(5, 20), 1600) for i in range(26)]
        # stars as directions
        n = int(self.W * self.PH / 90)
        az = np.array([r.uniform(-0.6, 2.0) for _ in range(n)])
        el = np.array([r.uniform(0.0, 0.75) ** 1.3 + 0.02 for _ in range(n)])
        self.stars = np.stack([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)], 1)
        self.star_ph = np.array([r.uniform(0, 6.28) for _ in range(n)])
        self.star_b = np.array([r.uniform(0.3, 1.0) for _ in range(n)])
        # cars: [x, lane z, dir, speed, colour]
        self.cars = []
        for lane, d in ((-3.0, 1), (-1.3, 1), (1.3, -1), (3.0, -1)):
            for _ in range(11):
                self.cars.append([r.uniform(-ROAD, ROAD), lane, d, r.uniform(16, 26),
                                  r.choice(((230, 230, 235), (40, 40, 50), (200, 30, 40), (40, 80, 170), (150, 150, 160)))])
        # boats: [x, z, dir, speed, kind]
        self.boats = [[r.uniform(-200, 200), -45.0, 1, 4.0, "sail"],
                      [r.uniform(-200, 200), 40.0, -1, 6.0, "ferry"],
                      [r.uniform(-300, 300), 170.0, 1, 2.2, "ship"],
                      [r.uniform(-200, 200), -15.0, -1, 3.0, "sail"]]
        # fog banks: list of puffs [x, y, z, rx, ry, phase]
        self.fog = []
        for _ in range(7):
            self.fog.append(self.new_bank(r.uniform(-120, 260)))
        # clouds: puffs far away
        self.clouds = [[r.uniform(-600, 1400), r.uniform(120, 300), r.uniform(1300, 1700), r.uniform(80, 220),
                        r.uniform(12, 30)] for _ in range(9)]
        self.cirrus = [[r.uniform(-500, 1300), r.uniform(150, 330), r.uniform(1400, 1700), r.uniform(260, 560),
                        r.uniform(8, 13), 0.32] for _ in range(5)]
        self.plane = None
        self.next_plane = self.t0 + r.uniform(4, 15)
        # seagulls in screen space: [x, y, vx, flap phase, size, bob phase]
        self.gulls = [self.new_gull(True) for _ in range(5 if self.W >= 120 else 3)]
        # DedSec takeover of the bridge lights, and the ctOS tracker
        self.ds_t = self.t0 + r.uniform(14, 24)
        lx = np.arange(-ANCH, ANCH + 1, 8.0)
        self.lamp_P = np.concatenate([np.stack([lx, np.full_like(lx, DK + 1.6), np.full_like(lx, z)], 1)
                                      for z in (-DW, DW)])
        self.lamp_i = np.concatenate([np.arange(len(lx)), np.arange(len(lx))])
        self.cab_P = np.concatenate([self.cables[z][1] for z in (-DW, DW)])
        self.cab_i = np.concatenate([np.arange(len(self.cables[-DW][1]))] * 2)
        self.track = None
        self.track_t = self.t0 + 5

    def new_gull(self, anywhere=False):
        r = self.rng
        d = r.choice((-1, 1))
        size = r.choice((1, 1, 2, 2, 3))
        x = r.uniform(0, self.W) if anywhere else (-6 if d > 0 else self.W + 6)
        return [x, r.uniform(self.PH * 0.12, self.PH * 0.45), d * r.uniform(3, 7) * (0.6 + 0.3 * size),
                r.uniform(0, 6.28), size, r.uniform(0, 6.28)]

    @staticmethod
    def box_verts(bounds, mirror):
        out = []
        for x0, x1, y0, y1, z0, z1 in bounds:
            if mirror:
                y0, y1 = -y1, -y0
            out.append([((x0, x1)[i & 1], (y0, y1)[(i >> 1) & 1], (z0, z1)[i >> 2]) for i in range(8)])
        return np.array(out, float).reshape(-1, 3)

    def hill_y(self, x):
        pts = self.marin
        for (x0, y0, _), (x1, y1, _) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return lerp(y0, y1, (x - x0) / (x1 - x0))
        return 0.0

    def new_bank(self, z):
        r = self.rng
        cx = r.uniform(-140, 200)
        cy = r.uniform(1, 13)
        puffs = []
        for _ in range(r.randint(3, 6)):
            puffs.append([cx + r.uniform(-30, 30), cy + r.uniform(-2, 3), z + r.uniform(-15, 15),
                          r.uniform(14, 34), r.uniform(2.5, 5.5), r.uniform(0, 6.28)])
        return puffs

    # ------------------------------------------------------------------ camera
    def proj(self, P, mirror=False):
        """P (..., 3) world -> sx, sy (pixel space), z."""
        P = np.asarray(P, float)
        x = P[..., 0] - self.pos[0]
        y = (-P[..., 1] if mirror else P[..., 1]) - self.pos[1]
        z = P[..., 2] - self.pos[2]
        X = x * self.cyaw - z * self.syaw
        Z = x * self.syaw + z * self.cyaw
        Zs = np.maximum(Z, 0.5)
        return self.cx + X / Zs * self.f, self.cy - y / Zs * self.f, Z

    def proj_dir(self, D):
        X = D[..., 0] * self.cyaw - D[..., 2] * self.syaw
        Z = D[..., 0] * self.syaw + D[..., 2] * self.cyaw
        Zs = np.maximum(Z, 1e-3)
        return self.cx + X / Zs * self.f, self.cy - D[..., 1] / Zs * self.f, Z

    # ------------------------------------------------------------------ raster helpers
    def quad_v(self, img, xl, xr, ytl, ybl, ytr, ybr, col):
        """Fill a quad with vertical left/right edges (projected vertical face)."""
        if xr < xl:
            xl, xr, ytl, ybl, ytr, ybr = xr, xl, ytr, ybr, ytl, ybl
        c0, c1 = int(xl + 0.5), int(xr + 0.5)
        if c1 <= c0:
            c1 = c0 + 1
        c0, c1 = max(0, c0), min(self.W, c1)
        if c1 <= c0:
            return
        r0 = max(0, int(min(ytl, ytr)))
        r1 = min(self.PH, int(max(ybl, ybr)) + 1)
        if r1 <= r0:
            return
        span = xr - xl
        if c1 - c0 <= 4:
            for c in range(c0, c1):
                u = min(1.0, max(0.0, (c + 0.5 - xl) / span)) if span > 1e-6 else 0.0
                a = ytl + u * (ytr - ytl)
                b = max(ybl + u * (ybr - ybl), a + 0.6)
                ra, rb = max(0, int(a + 0.5)), min(self.PH, int(b + 0.5))
                if rb > ra:
                    img[ra:rb, c] = col
            return
        t = np.clip((self.cols[c0:c1] + 0.5 - xl) / span, 0, 1) if span > 1e-6 else np.zeros(c1 - c0)
        top = ytl + t * (ytr - ytl)
        bot = np.maximum(ybl + t * (ybr - ybl), top + 0.6)
        rr = self.rows[r0:r1, None] + 0.5
        m = (rr >= top) & (rr < bot)
        img[r0:r1, c0:c1][m] = col

    def poly(self, img, xs, ys, col):
        """Column-wise fill of a convex polygon in pixel space."""
        c0 = max(0, int(min(xs) + 0.5))
        c1 = min(self.W, int(max(xs) + 0.5))
        if c1 <= c0:
            return
        r0 = max(0, int(min(ys)))
        r1 = min(self.PH, int(max(ys)) + 1)
        if r1 <= r0:
            return
        c = self.cols[c0:c1] + 0.5
        lo = np.full(c1 - c0, 1e9)
        hi = np.full(c1 - c0, -1e9)
        n = len(xs)
        for i in range(n):
            ax, ay, bx, by = xs[i], ys[i], xs[i - 1], ys[i - 1]
            if abs(bx - ax) < 1e-6:
                continue
            if ax > bx:
                ax, ay, bx, by = bx, by, ax, ay
            m = (c >= ax) & (c <= bx)
            y = ay + (c - ax) * ((by - ay) / (bx - ax))
            lo = np.where(m, np.minimum(lo, y), lo)
            hi = np.where(m, np.maximum(hi, y), hi)
        hi = np.maximum(hi, lo + 0.6)
        rr = self.rows[r0:r1, None] + 0.5
        m = (rr >= lo) & (rr < hi)
        img[r0:r1, c0:c1][m] = col

    def lines(self, img, X0, Y0, X1, Y1, col, add=False, ramp=None, occl=None, fog=None):
        X0, Y0, X1, Y1 = map(np.atleast_1d, (X0, Y0, X1, Y1))
        if not len(X0):
            return
        # Clip segments before choosing the sampling count: distant off-screen
        # cars otherwise force every visible trail to allocate 400 samples.
        dx, dy = X1 - X0, Y1 - Y0
        ta, tb = np.zeros(len(X0)), np.ones(len(X0))
        valid = np.ones(len(X0), dtype=bool)
        for start, delta, limit in ((X0, dx, self.W - 1), (Y0, dy, self.PH - 1)):
            parallel = np.abs(delta) < 1e-9
            valid &= ~parallel | ((start >= -0.5) & (start <= limit + 0.5))
            safe = np.where(parallel, 1.0, delta)
            t0, t1 = (-0.5 - start) / safe, (limit + 0.5 - start) / safe
            ta = np.maximum(ta, np.where(parallel, 0.0, np.minimum(t0, t1)))
            tb = np.minimum(tb, np.where(parallel, 1.0, np.maximum(t0, t1)))
        valid &= tb >= ta
        if not valid.any():
            return
        col = np.asarray(col, float)
        if col.ndim == 2:
            col = col[valid]
        X0, Y0, dx, dy, ta, tb = (v[valid] for v in (X0, Y0, dx, dy, ta, tb))
        k = int(min(400, max(2, np.max(np.maximum(np.abs(dx), np.abs(dy)) * (tb - ta)) + 2)))
        u = np.linspace(0, 1, k)
        t = ta[:, None] + (tb - ta)[:, None] * u
        xs = (X0[:, None] + dx[:, None] * t).round().astype(int).ravel()
        ys = (Y0[:, None] + dy[:, None] * t).round().astype(int).ravel()
        m = (xs >= 0) & (xs < self.W) & (ys >= 0) & (ys < self.PH)
        if col.ndim == 2:
            col = np.repeat(col, k, axis=0)
        if add:
            inten = (t if ramp is None else ramp(t)).ravel()
            col = (col * inten[:, None]) if col.ndim == 2 else np.outer(inten, col)
        idx = np.nonzero(m)[0]
        xs, ys = xs[idx], ys[idx]
        if col.ndim == 2:
            col = col[idx]
        if occl is not None:
            keep = ~occl[ys, xs]
            xs, ys = xs[keep], ys[keep]
            if col.ndim == 2:
                col = col[keep]
        if fog is not None and col.ndim == 2:
            col = col * (1 - fog[ys, xs])[:, None]
        if add:
            img[ys, xs] += col
        else:
            img[ys, xs] = col

    def dots(self, img, xs, ys, col, add=False, occl=None):
        xs = np.asarray(xs).round().astype(int)
        ys = np.asarray(ys).round().astype(int)
        m = (xs >= 0) & (xs < self.W) & (ys >= 0) & (ys < self.PH)
        if occl is not None:
            m[m] &= ~occl[ys[m], xs[m]]
        c = col if np.ndim(col) == 1 else np.asarray(col)[m]
        if add:
            img[ys[m], xs[m]] += c
        else:
            img[ys[m], xs[m]] = c

    def blob(self, A, px, py, rx, ry, a):
        """Accumulate a soft gaussian puff into alpha map A."""
        if rx < 0.8 or ry < 0.4:
            return
        c0, c1 = max(0, int(px - 2.2 * rx)), min(self.W, int(px + 2.2 * rx) + 1)
        r0, r1 = max(0, int(py - 2.2 * ry)), min(self.PH, int(py + 2.2 * ry) + 1)
        if c1 <= c0 or r1 <= r0:
            return
        gx = np.exp(-((self.cols[c0:c1] - px) / rx) ** 2)
        gy = np.exp(-((self.rows[r0:r1] - py) / ry) ** 2)
        A[r0:r1, c0:c1] += a * np.outer(gy, gx)

    # ------------------------------------------------------------------ lighting
    def lighting(self, p):
        el = math.sin(2 * math.pi * (p - 0.25))
        dusk = p > 0.5
        top, hor = keyed(SKY_DUSK if dusk else SKY_DAWN, el)
        wx = DATA.weather or {}
        overcast = 0.45 if wx.get("rain") else 0.25 if wx.get("clouds") or wx.get("fog") else 0.0
        if overcast:
            grey = (top + hor) / 2 * 0.8
            top, hor = top + (grey - top) * overcast, hor + (grey - hor) * overcast
        day = max(0.0, min(1.0, (el + 0.12) / 0.45))
        night = max(0.0, min(1.0, (-el - 0.02) / 0.25))
        golden = max(0.0, 1 - abs(el - 0.05) / 0.22)
        self.el, self.day, self.night, self.golden = el, day, night, golden
        self.top, self.hcol = top, hor

    # ------------------------------------------------------------------ main
    def step(self, s, now):
        """The static scene is rebuilt in 4 stages (one per frame, ~6 Hz) into a work buffer;
        every frame only the fast movers (car light trails, beacons, skull, glitch) are drawn on top."""
        dt, self.last = min(0.1, now - self.last), now
        self.dt = dt
        t = now - self.t0
        self.advance(dt, now)
        stages = (self.stage_sky, self.stage_reflect, self.stage_water, self.stage_main)
        if self.static is None:
            for st in stages:
                st(t, now)
            self.swap()
        else:
            stages[self.stage](t, now)
            self.stage = (self.stage + 1) % len(stages)
            if self.stage == 0:
                self.swap()
        img = self.static.copy()
        self.draw_cars(img, now)
        self.draw_gulls(img, now)

        # ---- DedSec skull hologram
        sk = now - self.skull_t
        if 0 <= sk < 5.0:
            self.draw_skull(img, now, sk)
            if sk < 0.4 or 4.6 < sk:
                self.glitch_until = max(self.glitch_until, now + 0.15)
        elif sk >= 5.0:
            self.skull_t = now + self.rng.uniform(26, 42)
        if self.rng.random() < 0.002:
            self.glitch_until = now + self.rng.uniform(0.1, 0.3)
        glitch = now < self.glitch_until
        if glitch:
            for _ in range(self.rng.randint(2, 5)):
                y0 = self.rng.randrange(self.PH)
                y1 = min(self.PH, y0 + self.rng.randint(1, 6))
                img[y0:y1] = np.roll(img[y0:y1], self.rng.randint(-10, 10), axis=1)
                img[y0:y1, :, self.rng.choice((0, 2))] += 45
        self.blit(s, img)
        self.hud(s, now, glitch)

    def swap(self):
        self.static = self.work
        self.occl, self.fogA, self.ripple = self.w_occl, self.w_fogA, self.w_ripple
        self.cam_shown = (self.pos.copy(), self.cyaw, self.syaw)

    def advance(self, dt, now):
        for c in self.cars:
            c[0] += c[2] * c[3] * dt
            if c[0] > ROAD:
                c[0] = -ROAD
            elif c[0] < -ROAD:
                c[0] = ROAD
        for bt in self.boats:
            bt[0] += bt[2] * bt[3] * dt
            if abs(bt[0]) > 320:
                bt[0] = -320 * bt[2]
        for bank in self.fog:
            for pf in bank:
                pf[0] += 1.6 * dt
                pf[2] -= 4.0 * dt
        for c in self.clouds + self.cirrus:
            c[0] += 3.0 * dt
            if c[0] > 1600:
                c[0] = -700
        for i, g in enumerate(self.gulls):
            g[0] += g[2] * dt
            g[3] += dt * (2.0 if math.sin(now * 0.45 + g[5]) > 0.35 else 9.0)
            if g[0] < -10 or g[0] > self.W + 10:
                self.gulls[i] = self.new_gull()
        if self.plane is None and now > self.next_plane:
            d = self.rng.choice((-1, 1))
            self.plane = [-0.6 if d > 0 else 2.2, self.rng.uniform(0.18, 0.4), d * 0.05]
        if self.plane is not None:
            self.plane[0] += self.plane[2] * dt
            if self.plane[0] > 2.3 or self.plane[0] < -0.7:
                self.plane = None
                self.next_plane = now + self.rng.uniform(15, 35)

    def stage_sky(self, t, now):
        W, PH = self.W, self.PH
        p = (self.p0 + t / self.period) % 1.0
        self.phase = p
        self.lighting(round(p * 400) / 400)
        # camera: slow orbit + dolly + gentle height bob
        a = 0.66 + 0.2 * math.sin(t * 2 * math.pi / 150)
        rad = 138 + 14 * math.sin(t * 2 * math.pi / 97 + 1)
        hc = 9.0 + 3.5 * math.sin(t * 2 * math.pi / 71)
        tgt = (8.0, 0, 20.0)
        self.pos = np.array((tgt[0] - rad * math.sin(a), hc, tgt[2] - rad * math.cos(a)))
        self.yaw = a
        self.cyaw, self.syaw = math.cos(a), math.sin(a)

        img = self.work = np.empty((PH, W, 3), np.float32)
        hor = self.hor
        k = (np.arange(hor) / max(1, hor - 1)) ** 1.7
        sky = self.top[None, :] + (self.hcol - self.top)[None, :] * k[:, None]
        img[:hor] = sky[:, None, :]
        nw = PH - hor
        kw = (np.arange(nw) / max(1, nw - 1)) ** 0.6
        wtop = self.hcol * 0.62 + C(4, 10, 24)
        wbot = self.top * 0.35 + C(2, 6, 16)
        self.wtop = wtop
        img[hor:] = (wtop[None, :] + (wbot - wtop)[None, :] * kw[:, None])[:, None, :]
        # sun / moon
        sp = (p - 0.25) % 1.0  # 0 = sunrise, 0.5 = sunset
        sun_dir = self.body_dir(sp)
        moon_dir = self.body_dir((sp + 0.5) % 1.0) * np.array((1, 0.8, 1))
        sx, sy, sz = self.proj_dir(sun_dir)
        sx, sy = float(sx), float(sy)
        if sz > 0 and sun_dir[1] > -0.12:
            r1 = min(PH, int(sy + 40))
            if r1 > 0:
                dx = self.cols[None, :] - sx
                dy = self.rows[:r1, None] - sy
                d2 = dx * dx + dy * dy
                gcol = blend((255, 250, 220), (255, 110, 60), self.golden)
                g = np.exp(-d2 / (2 * (10 + 18 * self.golden) ** 2)) * (0.35 + 0.4 * self.golden)
                img[:r1] += g[..., None] * np.array(gcol, np.float32)
                rr = 3.2 + 1.5 * self.golden
                img[:r1][d2 <= rr * rr] = np.array(blend((255, 250, 225), (255, 150, 90), self.golden), float)
        self.sun_px = (sx, sy, sz > 0 and sun_dir[1] > 0)
        mx, my, mz = self.proj_dir(moon_dir)
        mx, my = float(mx), float(my)
        self.moon_px = (mx, my, mz > 0 and moon_dir[1] > 0.0 and self.night > 0.2)
        if self.night > 0.02:
            xs, ys, zs = self.proj_dir(self.stars)
            tw = 0.6 + 0.4 * np.sin(t * 2.3 + self.star_ph)
            b = self.star_b * tw * self.night
            m = (zs > 0) & (ys < hor - 1)
            xs, ys, b = xs[m].round().astype(int), ys[m].round().astype(int), b[m]
            ok = (xs >= 0) & (xs < W) & (ys >= 0)
            xs, ys, b = xs[ok], ys[ok], b[ok]
            img[ys, xs] = img[ys, xs] * (1 - b[:, None]) + np.array((235, 235, 255.0)) * b[:, None]
        if self.moon_px[2] and 0 <= my < hor:
            self.draw_moon(img, mx, my)
        self.draw_clouds(img, t)
        self.draw_plane(img, now)

    def stage_reflect(self, t, now):
        self.draw_far(self.work, True)
        self.draw_scene(self.work, now, True)

    def stage_water(self, t, now):
        img, hor, W = self.work, self.hor, self.W
        nw = self.PH - hor
        if nw <= 1:
            return
        ri = np.arange(nw, dtype=np.float32)
        d = ri / max(1, nw - 1)                       # 0 at the horizon, 1 at the camera
        # Perspective wave field: crests get wider apart and longer towards the camera, so the
        # surface reads as long horizontal ripples instead of per-row noise.
        py = (3.4 * (ri + 1.0) ** 0.62)[:, None]
        kx = (0.16 / (1.0 + ri * 0.09))[:, None]
        X = self.cols[None, :].astype(np.float32)
        ph1 = py + X * kx + t * 1.9
        ph2 = 0.57 * py - X * kx * 0.61 - t * 1.25 + 1.7
        wave = 0.62 * np.sin(ph1) + 0.38 * np.sin(ph2)
        slope = 0.62 * np.cos(ph1) + 0.38 * np.cos(ph2)
        amp = (0.5 + 2.7 * d ** 1.15)[:, None]
        disp = np.round(amp * wave).astype(int)
        vdisp = np.round(amp * 0.45 * slope).astype(int)
        self.w_ripple = disp[:, W // 2]
        srccol = np.clip(self.cols[None, :] - disp, 0, W - 1)
        srcrow = np.clip(ri.astype(int)[:, None] + vdisp, 0, nw - 1)
        water = img[hor:]
        warped = water[srcrow, srccol]
        # soften the mirror vertically a touch: reflections smear on moving water
        warped[1:] = warped[1:] * 0.7 + warped[:-1] * 0.3
        # crest lighting: faces tilted towards the sky pick up the horizon colour, troughs darken
        lit = np.clip(slope, -1, 1).astype(np.float32)
        crest = np.maximum(0, lit - 0.55) * 2.2
        shade = (0.86 + 0.14 * lit)[..., None]
        sky = (self.hcol * (0.25 + 0.35 * self.day)).astype(np.float32)
        img[hor:] = warped * shade + crest[..., None] * sky * (0.35 + 0.45 * d[:, None, None])
        self.w_slope = slope
        self.glitter(img, now, t)
        self.draw_wakes(img)
        self.draw_far(img, False)
        self.fog_prep(t)
        self.draw_fog(img, t, far=True)

    def stage_main(self, t, now):
        img = self.work
        self.draw_scene(img, now, False)
        self.w_fogA = self.draw_fog(img, t, far=False)
        if self.sun_px[2] and self.golden > 0.3:
            self.flare(img)

    def draw_cars(self, img, now):
        pos, cyaw, syaw = self.pos, self.cyaw, self.syaw
        self.pos, self.cyaw, self.syaw = self.cam_shown
        cars = np.array([(c[0], DK + 0.35, c[1]) for c in self.cars])
        dirs = np.array([c[2] for c in self.cars], float)
        nf = min(1.0, self.night * 0.7 + self.golden * 0.4)
        hor = self.hor
        for mirror in (True, False):
            hx, hy, hz = self.proj(cars, mirror)
            ok = hz > 1
            if mirror:
                ri = np.clip(hy.round().astype(int) - hor, 0, len(self.ripple) - 1)
                hx = hx + self.ripple[ri]
            if nf > 0.05:
                tails = cars.copy()
                tails[:, 0] -= dirs * 7
                tx, ty, _ = self.proj(tails, mirror)
                if mirror:
                    tx = tx + self.ripple[ri]
                col = np.where((dirs > 0)[:, None], np.array((255, 40, 50.0)), np.array((255, 245, 220.0)))
                col = col * nf * (0.45 if mirror else 1.0)
                self.lines(img, tx[ok], ty[ok], hx[ok], hy[ok], col[ok], add=True, ramp=lambda u: u ** 1.5,
                           occl=None if mirror else self.occl, fog=self.fogA)
            if self.day > 0.1 and not mirror:
                col = np.array([c[4] for c in self.cars], float) * (0.4 + 0.6 * self.day)
                self.dots(img, hx[ok], hy[ok] - 0.4, col[ok], occl=self.occl)
        if int(now * 1.3) % 2 == 0:
            B = np.array([(tx, HT + 1.2, z) for tx in (-TX, TX) for z in (-DW, DW)])
            xs, ys, zs = self.proj(B)
            self.dots(img, xs, ys, np.array((255, 30, 30.0)))
        ds = now - self.ds_t
        if 0 <= ds < 4.6:
            self.draw_ds_lights(img, now, ds)
        elif ds >= 4.6:
            self.ds_t = now + self.rng.uniform(32, 55)
        self.update_track(now)
        self.pos, self.cyaw, self.syaw = pos, cyaw, syaw

    def draw_ds_lights(self, img, now, ds):
        """The deck lamps and suspender tops are taken over and chase in DedSec pink."""
        k = int(ds * 14)
        fade = min(1.0, ds / 0.3, (4.6 - ds) / 0.3)
        finale = ds > 3.4
        for P, idx, phase in ((self.lamp_P, self.lamp_i, 0), (self.cab_P, self.cab_i, 3)):
            if finale:
                on = np.full(len(idx), int(ds * 8) % 2 == 0)
            else:
                on = ((idx + phase - k) % 6) < 2
            hot = np.array(PINK, float) * fade
            cool = np.array(blend(PINK, (40, 0, 30), 0.75), float) * fade
            col = np.where(on[:, None], hot, cool)
            for mirror in (False, True):
                xs, ys, zs = self.proj(P, mirror)
                okz = zs > 1
                xs, ys, c = xs[okz], ys[okz], col[okz]
                if mirror:
                    ri = np.clip(ys.round().astype(int) - self.hor, 0, len(self.ripple) - 1)
                    xs = xs + self.ripple[ri]
                    c = c * 0.45
                self.dots(img, xs, ys, c, occl=None if mirror else self.occl)
                self.dots(img, xs + 1, ys, c * 0.35, add=True)
                self.dots(img, xs - 1, ys, c * 0.35, add=True)
        B = np.array([(tx, HT + 1.2, z) for tx in (-TX, TX) for z in (-DW, DW)])
        xs, ys, zs = self.proj(B)
        self.dots(img, xs, ys, np.array(CYAN if k % 4 < 2 else PINK, float))

    def update_track(self, now):
        """ctOS vessel tracker: pick a boat every few seconds and keep its screen box."""
        if now > self.track_t:
            self.track_t = now + self.rng.uniform(11, 17)
            vis = []
            for i, bt in enumerate(self.boats):
                x, y, z = self.proj(np.array((bt[0], 1.0, bt[1])))
                if z > 5 and 8 < float(x) < self.W - 8:
                    vis.append(i)
            self.track = (self.rng.choice(vis), now, self.rng.randint(11, 97)) if vis else None
        self.track_box = None
        if self.track is None or now - self.track[1] > 6.5:
            return
        bt = self.boats[self.track[0]]
        x, z, d, _, kind = bt
        ln, hh = {"sail": (2.6, 7.0), "ferry": (6.0, 3.0), "ship": (18.0, 7.0)}[kind]
        P = np.array([(x + a * ln, yy, z + b * 2) for a in (-1, 1) for yy in (0, hh) for b in (-1, 1)])
        X, Y, Z = self.proj(P)
        if (Z < 1).any():
            return
        self.track_box = (float(X.min()), float(Y.min()), float(X.max()), float(Y.max()), kind, bt[3])

    def draw_gulls(self, img, now):
        vis = max(self.day, self.golden * 0.9)
        if vis < 0.12:
            return
        sil = self.golden > 0.45 or self.day < 0.5
        for x, y, vx, ph, size, bob in self.gulls:
            yy = y + math.sin(now * 0.8 + bob) * 2.0
            f = math.sin(ph)
            lift = 1 if f > 0.45 else (-1 if f < -0.45 else 0)
            pts = [(0, 0)]
            for i in range(1, size + 1):
                if lift > 0:
                    dy = -i
                elif lift < 0:
                    dy = i - 1
                else:
                    dy = -1 if i < size or size == 1 else 0
                pts += [(-i, dy), (i, dy)]
            if size >= 2:
                pts.append((1 if vx > 0 else -1, 0))
            ix, iy = int(round(x)), int(round(yy))
            for dx, dy in pts:
                px, py = ix + dx, iy + dy
                if 0 <= px < self.W and 0 <= py < self.hor:
                    tip = abs(dx) == size and size >= 2
                    if sil:
                        col = np.array((30, 22, 36.0))
                    else:
                        col = np.array((70, 72, 84.0) if tip or size == 1 else (228, 230, 236.0))
                    a = vis * (0.55 + 0.15 * size)
                    img[py, px] = img[py, px] * (1 - a) + col * a

    # ------------------------------------------------------------------ pieces
    def body_dir(self, sp):
        """Sun/moon direction for its day fraction sp (0 rise .. 0.5 set)."""
        if sp < 0.5:
            u = sp / 0.5
            el = math.sin(u * math.pi) * 0.42 - 0.03
        else:
            u = 1.0 if sp < 0.75 else 0.0
            el = -0.3
        az = lerp(0.15, 1.15, u)
        return np.array((math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)))

    def draw_moon(self, img, mx, my):
        r = 3.6 if self.W >= 120 else 2.8
        c0, c1 = max(0, int(mx - 14)), min(self.W, int(mx + 15))
        r0, r1 = max(0, int(my - 14)), min(self.hor, int(my + 15))
        if c1 <= c0 or r1 <= r0:
            return
        dx = self.cols[None, c0:c1] - mx
        dy = self.rows[r0:r1, None] - my
        d2 = dx * dx + dy * dy
        img[r0:r1, c0:c1] += (np.exp(-d2 / 60.0) * 0.3 * self.night)[..., None] * np.array((170, 180, 255.0))
        # waxing gibbous: soft terminator on the left, a few maria
        disk = d2 <= r * r
        lit = np.clip(((dx + 1.6 * r) ** 2 + dy ** 2 - (1.25 * r) ** 2) / (r * r * 1.2), 0.08, 1.0)
        maria = (((dx - 0.9) ** 2 + (dy + 1.0) ** 2) < 1.4) | (((dx + 0.6) ** 2 + (dy - 1.2) ** 2) < 0.9) | \
                (((dx - 1.4) ** 2 + (dy - 0.8) ** 2) < 0.6)
        disk &= lit > 0.12
        base = np.where(maria, 0.8, 1.0) * np.sqrt(lit)
        moon = np.array((238, 238, 250.0))[None, None, :] * base[..., None]
        sky = img[r0:r1, c0:c1]
        sky[disk] = np.maximum(sky[disk], moon[disk])

    def draw_clouds(self, img, t):
        wx = DATA.weather or {}
        n = len(self.clouds) if (wx.get("clouds") or wx.get("rain") or self.golden > 0.3) else 6
        A = np.zeros((self.hor, self.W))
        for c in self.clouds[:n] + self.cirrus:
            x, y, z = self.proj(np.array((c[0], c[1], c[2])))
            if z > 0:
                self.blob(A, float(x), float(y), c[3] / z * self.f, c[4] / z * self.f, c[5] if len(c) > 5 else 0.55)
        A = np.minimum(A, 0.8)
        # underside rim: where there is more cloud just above, the sun lights the belly
        up = np.zeros_like(A)
        up[2:] = A[:-2]
        rim = np.clip((up - A) * 3.0, 0, 1)[..., None]
        A = A[..., None]
        lit = blend(blend((60, 50, 90), (255, 140, 160), self.golden), (240, 240, 248), self.day * (1 - self.golden * 0.7))
        lit = np.array(lit, float) * (0.35 + 0.65 * max(self.day, 0.15 + self.golden))
        top = lit * (0.78 + 0.22 * self.day)
        under = np.array(blend((255, 210, 200), (255, 120, 70), self.golden), float)
        under = under * (0.25 + 0.75 * max(self.day, self.golden)) * (0.35 + 0.65 * self.golden)
        cl = top + (under - top) * rim * (0.4 + 0.6 * self.golden)
        img[:self.hor] = img[:self.hor] * (1 - A) + cl * A

    def draw_plane(self, img, now):
        if self.plane is None:
            return
        pl = self.plane
        def dirv(az, el):
            return np.array((math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)))
        x, y, z = self.proj_dir(dirv(pl[0], pl[1]))
        if z <= 0:
            return
        x, y = float(x), float(y)
        if self.day > 0.3:  # contrail
            tx, ty, _ = self.proj_dir(dirv(pl[0] - pl[2] * 6, pl[1]))
            self.lines(img, float(tx), float(ty), x, y, np.array((60, 60, 60.0)) * self.day, add=True)
        self.dots(img, [x], [y], np.array((210, 210, 220.0)) * max(0.4, self.day))
        if int(now * 2) % 2 and self.night > 0.1:
            self.dots(img, [x + 1], [y], np.array((255, 40, 40.0)))

    def glitter(self, img, now, t):
        """Sun / moon path: horizontally stretched glints riding the wave crests."""
        hor, nw = self.hor, self.PH - self.hor
        ri = np.arange(nw, dtype=np.float32)
        X = self.cols[None, :].astype(np.float32)
        for (bx, by, vis), strength, col in ((self.sun_px, self.day * 0.75 + self.golden * 0.7, (255, 214, 150)),
                                              (self.moon_px, self.night * 0.85, (190, 205, 255))):
            if not vis or strength < 0.05 or not -40 < bx < self.W + 40:
                continue
            width = (2.5 + ri * 0.55)[:, None]
            c0, c1 = max(0, int(bx - 3 * width[-1, 0])), min(self.W, int(bx + 3 * width[-1, 0]) + 1)
            if c1 <= c0:
                continue
            Xs = X[:, c0:c1]
            path = np.exp(-((Xs - bx) / width) ** 2)
            # fast, short, wide glints: high-frequency crest pattern on top of the wave slope
            g = np.sin(Xs * (0.55 / (1 + ri * 0.05))[:, None] + (ri * 1.9)[:, None] + t * 4.3) \
                * np.sin(Xs * 0.09 - (ri * 0.8)[:, None] - t * 2.1)
            sl = self.w_slope[:, c0:c1]
            glint = np.maximum(0, g - 0.25) * 1.6 + np.maximum(0, sl - 0.4) * 0.9
            a = np.minimum(1.4, path * glint * min(1.0, strength))
            img[hor:, c0:c1] += a[..., None] * np.array(col, np.float32)

    # far silhouettes ------------------------------------------------------
    def ridge(self, img, pts, col, mirror, base_y=None):
        P = np.array(pts, float)
        xs, ys, zs = self.proj(P, mirror)
        B = P.copy()
        B[:, 1] = 0
        _, bys, _ = self.proj(B, mirror)
        ok = zs > 1
        if ok.sum() < 2:
            return
        xs, ys, bys = xs[ok], ys[ok], bys[ok]
        o = np.argsort(xs)
        xs, ys, bys = xs[o], ys[o], bys[o]
        c0, c1 = max(0, int(xs[0])), min(self.W, int(xs[-1]) + 1)
        if c1 <= c0:
            return
        c = self.cols[c0:c1]
        ry = np.interp(c, xs, ys)
        rb = np.interp(c, xs, bys)
        lo, hi = (np.minimum(ry, rb), np.maximum(ry, rb))
        r0, r1 = max(0, int(lo.min())), min(self.PH, int(hi.max()) + 1)
        if r1 <= r0:
            return
        rr = self.rows[r0:r1, None] + 0.5
        m = (rr >= lo) & (rr < hi + 0.5)
        img[r0:r1, c0:c1][m] = col

    def tint(self, col, mirror, haze=0.0):
        col = np.asarray(col, float)
        col = col + (self.hcol - col) * min(0.85, haze)
        if mirror:
            col = col * 0.55 + self.wtop * 0.3
        return col

    def draw_far(self, img, mirror):
        L = 0.25 + 0.75 * self.day
        far = self.tint(blend((70, 90, 120), (40, 25, 60), self.golden * 0.6), mirror, 0.6) * (0.5 + 0.5 * L)
        self.ridge(img, self.far, far, mirror)
        hill = np.array(blend((70, 95, 60), (55, 30, 60), self.golden * 0.8), float) * L * 0.75 + C(6, 5, 14)
        self.ridge(img, self.marin, self.tint(hill, mirror, 0.25), mirror)
        if self.night > 0.1:
            P = np.array(self.marin_lights)
            xs, ys, zs = self.proj(P, mirror)
            col = np.array((255, 200, 120.0)) * self.night * (0.4 if mirror else 0.8)
            self.dots(img, xs[zs > 0], ys[zs > 0], col, add=True)
        # city boxes far behind, painter by depth
        base = CITY * (0.3 + 0.7 * L) + self.hcol * 0.15
        base = self.tint(base, mirror, 0.35)
        lit = self.night > 0.05
        X, Y, Z = self.proj(self.city_P, mirror)
        X, Y, Z = X.reshape(-1, 2).tolist(), Y.reshape(-1, 2).tolist(), Z.reshape(-1, 2).tolist()
        for i in self.city_order:
            if Z[i][0] < 1:
                continue
            c0, c1 = max(0, int(X[i][0] + 0.5)), min(self.W, int(X[i][1] + 0.5))
            ya, yb = sorted(Y[i])
            r0, r1 = max(0, int(ya + 0.5)), min(self.PH, int(yb + 0.5))
            if c1 > c0 and r1 > r0:
                img[r0:r1, c0:c1] = base * (0.85 + 0.3 * (i % 3) / 2)
        # pyramid
        px, pz, half, ph = self.pyramid
        xs, ys, zs = self.proj(np.array(((px - half, 0, pz), (px + half, 0, pz), (px, ph, pz + 2))), mirror)
        if (zs > 1).all():
            self.poly(img, list(xs), list(ys), base * 1.1)
        if lit and len(self.win):
            xs, ys, zs = self.proj(self.win, mirror)
            on = (np.sin(self.phase * 40 + self.win_phase * 60) > -0.3)
            b = self.night * (0.45 if mirror else 1.0)
            self.dots(img, xs[on], ys[on], self.win_col[on] * b * 0.85)
            # salesforce-ish crown light show
            cx, cy, cz = self.proj(np.array((-10, 71.5, 291.0)), mirror)
            hue = blend(PINK, CYAN, 0.5 + 0.5 * math.sin(self.phase * 90))
            self.dots(img, [float(cx) - 1, float(cx), float(cx) + 1], [float(cy)] * 3,
                      np.array(hue, float) * b)

    # bridge + boats ---------------------------------------------------------
    def box(self, img, b, col, mirror, shade=(1.0, 0.72, 1.15, 0.55)):
        X, Y, Z = self.proj(self.box_verts([b], mirror))
        if (Z < 1).any():
            return
        self.box_faces(img, X.tolist(), Y.tolist(), b, col, mirror, shade)

    def box_faces(self, img, X, Y, b, col, mirror, shade=(1.0, 0.72, 1.15, 0.55)):
        if max(X) < 0 or min(X) >= self.W or max(Y) < 0 or min(Y) >= self.PH:
            return
        x0, x1, y0, y1, z0, z1 = b
        if mirror:
            y0, y1 = -y1, -y0
        px, py, pz = self.pos
        cz, cx_ = shade[0], shade[1]
        # vertical faces: z-face and x-face facing camera
        if pz < z0:
            self.quad_v(img, X[0], X[1], Y[2], Y[0], Y[3], Y[1], col * cz)
        elif pz > z1:
            self.quad_v(img, X[4], X[5], Y[6], Y[4], Y[7], Y[5], col * cz)
        if px < x0:
            self.quad_v(img, X[0], X[4], Y[2], Y[0], Y[6], Y[4], col * cx_)
        elif px > x1:
            self.quad_v(img, X[1], X[5], Y[3], Y[1], Y[7], Y[5], col * cx_)
        if py > y1 and max(Y[2], Y[3], Y[6], Y[7]) - min(Y[2], Y[3], Y[6], Y[7]) > 1.2:
            self.poly(img, [X[2], X[3], X[7], X[6]], [Y[2], Y[3], Y[7], Y[6]], col * shade[2])
        elif py < y0 and max(Y[0], Y[1], Y[4], Y[5]) - min(Y[0], Y[1], Y[4], Y[5]) > 1.2:
            self.poly(img, [X[0], X[1], X[5], X[4]], [Y[0], Y[1], Y[5], Y[4]], col * shade[3])

    def steel_detail(self, img, b, col, mirror):
        """Recessed plate courses and joint rivets projected onto real tower faces."""
        x0,x1,y0,y1,z0,z1 = b
        if y1-y0 < 2 or x1-x0 > 12:
            return
        z = z0-.015 if self.pos[2] < z0 else z1+.015
        levels = np.arange(y0+.7,y1,.95 if y1 < 8 else 2.0)
        if not len(levels):
            return
        a = [(x0,y,z) for y in levels]; c = [(x1,y,z) for y in levels]
        n = len(a)
        if y1-y0 > 12:
            # Inner flange edges distinguish steel tower legs from stone piers.
            a += [(x0+.24,y0,z),(x1-.24,y0,z)]
            c += [(x0+.24,y1,z),(x1-.24,y1,z)]
        X,Y,Z=self.proj(np.array(a+c),mirror)
        m = len(a)
        ok=(Z[:m]>1)&(Z[m:]>1)
        cols=np.empty((m,3)); cols[:n]=col*.55; cols[n:]=col*1.18
        self.lines(img,X[:m][ok],Y[:m][ok],X[m:][ok],Y[m:][ok],cols[ok])

    def materials(self, mirror):
        L = 0.2 + 0.8 * self.day
        warm = self.hcol * 0.25 * self.golden
        flood = FLOOD * 0.45 * self.night
        m = {
            "tower": TOWER * L + warm + flood,
            "strut": TOWER * L * 0.85 + warm + flood * 0.8,
            "deck": DECK * L * 0.9 + warm + flood * 0.5,
            "stone": STONE * L + warm * 0.5 + flood * 0.3,
            "cable": CABLE * L + warm + flood * 0.8,
        }
        return {k: self.tint(v, mirror, 0.08) for k, v in m.items()}

    def draw_scene(self, img, now, mirror):
        mats = self.materials(mirror)
        px, pz = self.pos[0], self.pos[2]
        X, Y, Z = self.proj(self.box_P[mirror])
        nb = len(self.boxes)
        X, Y, Z = X.reshape(nb, 8).tolist(), Y.reshape(nb, 8).tolist(), Z.reshape(nb, 8).min(1).tolist()
        items = []
        for i, b in enumerate(self.boxes):
            if Z[i] >= 1:
                cx, cz = (b[0] + b[1]) / 2, (b[4] + b[5]) / 2
                items.append((b[7], -((cx - px) * self.syaw + (cz - pz) * self.cyaw), i))
        items.sort()
        for k, bt in enumerate(self.boats):
            if bt[1] > 0:
                self.draw_boat(img, bt, now, mirror)
        self.draw_cable(img, DW, mats["cable"] * 0.8, mirror)
        deck_done = False
        for lay, d, i in items:
            if lay >= 3 and not deck_done:
                self.draw_deck(img, mats["deck"], mirror)
                self.draw_lamps(img, mirror)
                deck_done = True
                if not mirror:
                    before = img.copy()
            b = self.boxes[i]
            self.box_faces(img, X[i], Y[i], b[:6], mats[b[6]], mirror)
            if not mirror:  # the rippled reflection cannot show plate seams anyway
                self.steel_detail(img, b[:6], mats[b[6]], mirror)
        self.draw_cable(img, -DW, mats["cable"], mirror)
        for k, bt in enumerate(self.boats):
            if bt[1] <= 0:
                self.draw_boat(img, bt, now, mirror)
        if not mirror:
            self.w_occl = (img != before).any(axis=2)

    def draw_deck(self, img, col, mirror):
        # clip the deck to the part in front of the camera
        x0 = -ROAD
        if self.syaw > 1e-3:
            x0 = max(x0, self.pos[0] + (6 - (-DW - self.pos[2]) * self.cyaw) / self.syaw)
        if x0 < ROAD:
            self.box(img, (x0, ROAD, DK - 1.3, DK, -DW, DW), col, mirror)

        # Perspective lane paint and deck expansion plates follow the roadway.
        for z in (-2.2, 0, 2.2):
            xs=np.arange(max(x0,-ROAD),ROAD,6.)
            a=np.stack([xs,np.full_like(xs,DK+.025),np.full_like(xs,z)],1)
            b=a.copy();b[:,0]+=2.8
            X,Y,Z=self.proj(a,mirror);U,V,Q=self.proj(b,mirror)
            ok=(Z>6)&(Q>6)
            self.lines(img,X[ok],Y[ok],U[ok],V[ok],self.tint(C(185,174,132)*(.25+.75*self.day),mirror))
        xs=np.arange(max(x0,-ROAD),ROAD,12.)
        a=np.stack([xs,np.full_like(xs,DK+.03),np.full_like(xs,-DW)],1)
        b=a.copy();b[:,2]=DW
        X,Y,Z=self.proj(a,mirror);U,V,Q=self.proj(b,mirror)
        ok=(Z>6)&(Q>6)
        self.lines(img,X[ok],Y[ok],U[ok],V[ok],col*.48)

    def draw_cable(self, img, zs, col, mirror):
        pts, top, bot = self.cables[zs]
        X, Y, Z = self.proj(pts, mirror)
        if (Z < 1).any():
            return
        self.lines(img, X[:-1], Y[:-1], X[1:], Y[1:], col)
        sx, sy, _ = self.proj(top, mirror)
        bx, by, _ = self.proj(bot, mirror)
        self.lines(img, sx, sy, bx, by, col * 0.6 + self.hcol * 0.15)

    def draw_lamps(self, img, mirror):
        if self.night > 0.05:
            lx = np.arange(-ANCH, ANCH + 1, 8.0)
            L = np.concatenate([np.stack([lx, np.full_like(lx, DK + 1.6), np.full_like(lx, z)], 1) for z in (-DW, DW)])
            xs, ys, zs = self.proj(L, mirror)
            self.dots(img, xs, ys, FLOOD * self.night * (0.4 if mirror else 0.9), add=True)

    def draw_boat(self, img, bt, now, mirror):
        x, z, d, _, kind = bt
        L = 0.25 + 0.75 * self.day
        hull = self.tint(np.array((230, 230, 235.0)) * L, mirror)
        dark = self.tint(np.array((40, 40, 55.0)) * L + 5, mirror)
        if kind == "sail":
            parts = [((x - 2.5, x + 2.5, 0, 0.8, z - 0.8, z + 0.8), hull)]
        elif kind == "ferry":
            parts = [((x - 6, x + 6, 0, 1.4, z - 1.8, z + 1.8), dark), ((x - 4, x + 4, 1.4, 3.0, z - 1.4, z + 1.4), hull)]
        else:
            parts = [((x - 18, x + 18, 0, 2.2, z - 3, z + 3), self.tint(C(60, 30, 40) * L + 6, mirror))]
            cols = ((40, 120, 200), (200, 60, 60), (230, 180, 40), (60, 160, 90))
            for i in range(6):
                bx = x - 15 + i * 4.8
                parts.append(((bx, bx + 4.2, 2.2, 4.4, z - 2.5, z + 2.5),
                              self.tint(np.array(cols[(i + int(z)) % 4], float) * L, mirror)))
            parts.append(((x + 13 * -d - 2, x + 13 * -d + 2, 2.2, 7.0, z - 2.5, z + 2.5), hull))
        X, Y, Z = self.proj(self.box_verts([p_[0] for p_ in parts], mirror))
        if (Z < 1).any() or X.max() < -5 or X.min() > self.W + 5:
            return
        X, Y = X.reshape(-1, 8).tolist(), Y.reshape(-1, 8).tolist()
        for k, (b, col) in enumerate(parts):
            self.box_faces(img, X[k], Y[k], b, col, mirror)
        if kind == "sail":
            sy = -1 if mirror else 1
            P = np.array(((x - 1.8 * d, 1.0 * sy, z), (x + 1.6 * d, 1.0 * sy, z), (x + 0.4 * d, 7.0 * sy, z)))
            X, Y, Z = self.proj(P)
            if (Z > 1).all():
                self.poly(img, X.tolist(), Y.tolist(), hull * 1.05)
        if self.night > 0.1:
            ly = (-1 if mirror else 1) * 3.0
            X, Y, Z = self.proj(np.array(((x, ly, z), (x + 2 * d, ly * 0.5, z))))
            if (Z > 1).all():
                self.dots(img, X, Y, np.array((255, 230, 180.0)) * self.night * (0.5 if mirror else 1.0), add=True)
                if int(now * 2 + z) % 2:
                    self.dots(img, [X[1]], [Y[1]], np.array((60, 255, 90.0)) if d > 0 else np.array((255, 40, 40.0)))

    def draw_wakes(self, img):
        for x, z, d, sp, kind in self.boats:
            n = 10
            k = np.arange(1, n + 1, dtype=float)
            ln = {"sail": 2.5, "ferry": 6.0, "ship": 18.0}[kind]
            back = x - d * (ln + k * (1.5 + sp * 0.4))
            spread = k * (0.35 + sp * 0.05) + (0.8 if kind == "sail" else 2.0)
            P = np.concatenate([np.stack([back, np.zeros(n), z + spread], 1), np.stack([back, np.zeros(n), z - spread], 1),
                                np.stack([back, np.zeros(n), np.full(n, z)], 1)])
            X, Y, Z = self.proj(P)
            if (Z < 1).any():
                continue
            # V-shaped Kelvin wake: two foam arms plus a churned centre line, fading aft
            col = (self.hcol * 0.3 + 34)
            fade = (1 - k / (n + 1))
            cols = col[None, :] * fade[:-1, None]
            for arm in range(3):
                sl = slice(arm * n, arm * n + n)
                ax, ay = X[sl], Y[sl] + 0.5
                self.lines(img, ax[:-1], ay[:-1], ax[1:], ay[1:], cols * (0.55 if arm == 2 else 1.0), add=True,
                           ramp=lambda u: 0.6 + 0.4 * u)
            hx, hy, _ = self.proj(np.array(((x + d * ln, 0, z), (x - d * ln, 0, z))))
            self.lines(img, hx[1:], hy[1:] + 0.5, hx[:1], hy[:1] + 0.5, col * 0.5, add=True)

        # Tidal eddies wrap around the actual tower foundations, not the screen.
        angle=np.linspace(0,math.tau,19)
        for tx in (-TX,TX):
            for radius in (3.0,5.2):
                P=np.stack([tx+np.cos(angle)*radius,np.zeros_like(angle),
                            -DW+np.sin(angle)*radius*.65],1)
                X,Y,Z=self.proj(P)
                ok=(Z[:-1]>2)&(Z[1:]>2)
                self.lines(img,X[:-1][ok],Y[:-1][ok],X[1:][ok],Y[1:][ok],
                           self.hcol*.14+9,add=True)

    # fog ---------------------------------------------------------------------
    def fog_level(self, t):
        wx = DATA.weather or {}
        base = 0.2 + 0.55 * max(0.0, math.sin(t / 31.0 + 1.0)) ** 2 + 0.15 * math.sin(t / 7.3)
        if wx.get("fog"):
            base = max(base, 0.65)
        return max(0.05, min(1.0, base))

    def fog_prep(self, t):
        self.fog_now = lvl = self.fog_level(t)
        P = np.array([pf[:3] for bank in self.fog for pf in bank])
        X, Y, Z = self.proj(P)
        split = float(self.proj(np.array((0.0, 0.0, 0.0)))[2])
        items = []
        k = 0
        for i, bank in enumerate(self.fog):
            closest = 1e9
            for pf in bank:
                z = float(Z[k])
                closest = min(closest, z)
                if z > 8:
                    wob = 1 + 0.15 * math.sin(t * 0.4 + pf[5])
                    items.append((z > split, float(X[k]), float(Y[k]), pf[3] * wob / z * self.f, pf[4] / z * self.f))
                k += 1
            if closest < 12:
                self.fog[i] = self.new_bank(self.rng.uniform(230, 300))
        self.fog_items = items
        self.fog_alpha = 0.42 * lvl

    def draw_fog(self, img, t, far):
        A = np.zeros((self.PH, self.W))
        any_ = False
        for fl, x, y, rx, ry in self.fog_items:
            if fl == far:
                self.blob(A, x, y, rx, ry, self.fog_alpha)
                any_ = True
        if not any_:
            return None
        rows = np.nonzero(A.max(1) > 0.02)[0]
        if not len(rows):
            return None
        r0, r1 = rows[0], rows[-1] + 1
        q = (np.round(np.minimum(A[r0:r1], 0.88) * 24) / 24).astype(np.float32)
        fc = blend(blend((48, 44, 80), (255, 165, 175), self.golden), (226, 228, 236), self.day * (1 - 0.6 * self.golden))
        fc = np.array(fc, float) * (0.4 + 0.6 * max(self.day, 0.2 + self.golden))
        img[r0:r1] = img[r0:r1] * (1 - q[..., None]) + fc.astype(np.float32) * q[..., None]
        return np.minimum(A, 0.88)

    def flare(self, img):
        sx, sy, _ = self.sun_px
        vx, vy = self.cx - sx, self.cy - sy
        for k, r, c in ((0.6, 2, (255, 120, 180)), (1.2, 3, (120, 220, 255)), (1.6, 1.5, (255, 230, 120))):
            x, y = sx + vx * k * 2, sy + vy * k * 2
            if 0 <= x < self.W and 0 <= y < self.PH:
                self.dots(img, [x, x + 1, x - 1, x, x], [y, y, y, y + 1, y - 1],
                          np.array(c, float) * 0.25 * self.golden, add=True)

    def draw_skull(self, img, now, sk):
        X, Y, Z = self.proj(np.array(((-TX, HT * 0.62, -DW - 1.5), (-TX, HT + 1, 0))))
        if Z[0] < 1:
            return
        hpx = max(8, (Y[0] - Y[1]) * 0.9)
        rows, cols = len(SKULL), len(SKULL[0])
        sc = hpx / rows
        wpx = cols * sc
        left, top = float(X[0]) - wpx / 2, float(Y[1]) - hpx * 0.15
        fade = min(1.0, sk / 0.6, (5.0 - sk) / 0.6)
        col = np.array(blend(PINK, CYAN, 0.5 + 0.5 * math.sin(now * 3)), float)
        for r_ in range(int(hpx)):
            row = SKULL[min(rows - 1, int(r_ / sc))]
            if (r_ + int(now * 12)) % 3 == 0:
                continue
            yy = int(top + r_)
            if not 0 <= yy < self.PH:
                continue
            jit = self.rng.randint(-2, 2) if self.rng.random() < 0.08 else 0
            for c_ in range(int(wpx)):
                if row[min(cols - 1, int(c_ / sc))] == "X":
                    xx = int(left + c_) + jit
                    if 0 <= xx < self.W:
                        img[yy, xx] = img[yy, xx] * (1 - 0.6 * fade) + col * 0.6 * fade
        self.skull_box = (left, top, wpx, hpx)

    # ------------------------------------------------------------------ output
    def blit(self, s, img):
        q = np.clip(img, 0, 255).astype(np.uint8) & 0xFC
        # moving water: coarser colour steps keep the diff renderer from repainting every cell
        q[self.hor:] &= 0xF8
        prev = self.prev
        self.prev = q
        if prev is None or prev.shape != q.shape:
            for y in range(self.h):
                self.cache_t[y] = list(map(tuple, q[2 * y].tolist()))
                self.cache_b[y] = list(map(tuple, q[2 * y + 1].tolist()))
        else:
            diff = (q != prev).any(axis=2)
            per_row = diff.sum(axis=1)
            for py in np.nonzero(per_row)[0].tolist():
                row = (self.cache_b if py & 1 else self.cache_t)[py >> 1]
                if per_row[py] > 40:
                    row[:] = list(map(tuple, q[py].tolist()))
                else:
                    qr = q[py]
                    for x in np.nonzero(diff[py])[0].tolist():
                        row[x] = tuple(qr[x].tolist())
        for y in range(self.h):
            s.pt[y] = self.cache_t[y][:]
            s.pb[y] = self.cache_b[y][:]

    def label(self, s, x, y, txt, col):
        """Text over the pixel image with a darkened backing."""
        if not 0 <= y < self.h:
            return
        for i, ch in enumerate(txt):
            xx = x + i
            if 0 <= xx < self.w:
                a, b = s.pt[y][xx], s.pb[y][xx]
                base = a or b or (0, 0, 0)
                s.bg[y][xx] = blend(base, BLACK, 0.7)
                s.ch[y][xx] = ch
                s.fg[y][xx] = col

    def hud(self, s, now, glitch):
        w, h = self.w, self.h
        rec = PINK if int(now * 1.5) % 2 else blend(PINK, BLACK, 0.6)
        self.label(s, 2, 1, "●", rec)
        self.label(s, 3, 1, " REC  ctOS // GOLDEN GATE CAM 04 ", WHITE)
        hh = int(self.phase * 24)
        mm = int(self.phase * 1440) % 60
        ss = int(self.phase * 86400) % 60
        lt = time.localtime(now)
        clock = " %02d/%02d/%04d  %02d:%02d:%02d  TL x1028 " % (lt.tm_mon, lt.tm_mday, lt.tm_year, hh, mm, ss)
        self.label(s, w - len(clock) - 2, 1, clock, CYAN)
        # bottom data
        wx = DATA.weather
        if wx:
            temp = "%dC %s" % (wx["temp_c"], wx["desc"].strip().upper()[:14])
        else:
            temp = "%dC" % int(11 + 7 * self.day)
        fog = int(self.fog_now * 100)
        info = " %s  FOG %d%%  VIS %.1fkm  WIND %dkt W " % (temp, fog, max(0.3, 9.5 - fog * 0.09),
                                                           int(9 + 6 * math.sin(now / 9)))
        if w >= 120:
            info += " DECK %03d VEH " % len(self.cars)
        self.label(s, 2, h - 2, info[:max(10, w - 26)] if w < 120 else info, GREY if not glitch else PINK)
        geo = " 37.8199N 122.4783W "
        if w >= 90 and len(info) + len(geo) + 6 < w:
            self.label(s, w - len(geo) - 2, h - 2, geo, GREY)
        # frame brackets
        col = blend(CYAN, BLACK, 0.35)
        arm = 3 if w < 120 else 5
        for x, y, a, d in ((0, 0, "┌", 1), (w - 1, 0, "┐", -1), (0, h - 1, "└", 1), (w - 1, h - 1, "┘", -1)):
            self.label(s, x, y, a, col)
            for i in range(1, arm + 1):
                self.label(s, x + d * i, y, "─", col)
        # centre reticle
        cx, cy = w // 2, h // 2
        self.label(s, cx - 1, cy, "+", blend(WHITE, BLACK, 0.5))
        # status message
        if now > self.next_msg:
            self.msg = (self.rng.choice(MSGS), now)
            self.next_msg = now + self.rng.uniform(10, 18)
        self.draw_tracker(s, now)
        if w >= 120:
            self.heading_tape(s, now)
        sk = now - self.skull_t
        ds = now - self.ds_t
        if 0 <= ds < 4.6 and not 0 <= sk < 5.0:
            txt = " ctOS > BRIDGE LIGHTING: UNAUTHORISED PATTERN " if int(now * 3) % 2 else " ctOS > LIGHTING GRID // DEDSEC "
            self.label(s, (w - len(txt)) // 2, 3, txt, PINK)
        elif 0 <= sk < 5.0:
            txt = " SIGNAL HIJACKED // DEDSEC " if int(now * 4) % 2 else " ctOS CAM 04 // OVERRIDE "
            self.label(s, (w - len(txt)) // 2, 3, txt, PINK if int(now * 4) % 2 else YELLOW)
        elif now - self.msg[1] < 3.5:
            txt = " ctOS > " + self.msg[0] + " "
            n = min(len(txt), int((now - self.msg[1]) * 30))
            self.label(s, (w - len(txt)) // 2, 3, txt[:n], YELLOW)
        if DATA.weather and DATA.weather.get("rain"):
            for _ in range(w * h // 60):
                x = self.rng.randrange(w)
                y = self.rng.randrange(h)
                if s.ch[y][x] == " ":
                    self.label(s, x, y, "/", (110, 120, 150))

    def mark(self, s, x, y, ch, col):
        """A HUD glyph that keeps the picture behind it as its cell background."""
        if 0 <= x < self.w and 0 <= y < self.h:
            a, b = s.pt[y][x], s.pb[y][x]
            base = a or b or (0, 0, 0)
            if a and b:
                base = ((a[0] + b[0]) >> 1, (a[1] + b[1]) >> 1, (a[2] + b[2]) >> 1)
            s.bg[y][x] = blend(base, BLACK, 0.18)
            s.ch[y][x] = ch
            s.fg[y][x] = col

    def draw_tracker(self, s, now):
        tb = getattr(self, "track_box", None)
        if tb is None:
            return
        x0, y0, x1, y1, kind, sp = tb
        age = now - self.track[1]
        grow = max(0.0, 1 - age / 0.5) * 6
        cx0, cx1 = int(x0 - 1 - grow), int(x1 + 1.999 + grow)
        cy0, cy1 = int(y0 / 2 - 1 - grow / 2), int(y1 / 2 + 1.999 + grow / 2)
        if cx1 - cx0 < 3:
            cx1 = cx0 + 3
        if cy1 - cy0 < 2:
            cy1 = cy0 + 2
        if cy0 < 3 or cy1 > self.h - 4 or cx0 < 1 or cx1 > self.w - 2:
            return
        locked = age > 0.5
        col = blend(YELLOW if locked else WHITE, BLACK, 0.15 if int(now * 4) % 2 or locked else 0.5)
        if age > 6.0:
            col = blend(col, BLACK, (age - 6.0) / 0.5)
        for x, y, ch in ((cx0, cy0, "┌"), (cx1, cy0, "┐"), (cx0, cy1, "└"), (cx1, cy1, "┘")):
            self.mark(s, x, y, ch, col)
        if locked and self.w >= 120:
            name = {"sail": "SAILBOAT", "ferry": "FERRY", "ship": "CARGO"}[kind]
            txt = " TRK-%02d %s %.1fKN " % (self.track[2], name, sp * 1.9)
            n = min(len(txt), int((age - 0.5) * 40))
            lx = cx0 if cx0 + len(txt) < self.w - 2 else cx1 - len(txt)
            self.label(s, lx, cy0 - 1, txt[:n], blend(YELLOW, WHITE, 0.2))

    def heading_tape(self, s, now):
        hdg = math.degrees(self.yaw) % 360
        names = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}
        width = 31
        x0 = (self.w - width) // 2
        dim = blend(CYAN, BLACK, 0.5)
        for i in range(width):
            deg = hdg + (i - width // 2) * 3
            k = int(round(deg / 3)) * 3 % 360
            if k % 15 == 0:
                self.mark(s, x0 + i, 1, "·", dim)
        for a, nm in names.items():
            off = ((a - hdg + 180) % 360 - 180) / 3
            if abs(off) < width // 2 - 1:
                for j, ch in enumerate(nm):
                    self.mark(s, x0 + width // 2 + int(round(off)) + j - (len(nm) > 1), 1, ch, CYAN)
        num = "[%03d]" % int(hdg)
        for i, ch in enumerate(num):
            self.mark(s, x0 + width // 2 - 2 + i, 2, ch, YELLOW if ch in "[]" else blend(CYAN, WHITE, 0.3))

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "shutter", "CAM 04 // IRIS CLOSED", CYAN)
        if .06 < t < .65:
            self.label(s,2,1," REC STOP  //  BUFFER SEALED ",blend(CYAN,BLACK,t))

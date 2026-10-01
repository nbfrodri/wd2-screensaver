"""NUDLE: Nudle Maps on a tilted 3D city that folds Inception-style, pins, routes, traffic, hijacks."""

import math
import random
import time

import numpy as np

from lib import (BLACK, CYAN, DIM_CYAN, DIM_PINK, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE,
                 YELLOW, Glitch, blend, ease_out, pulse)
from widgets import Particles, PostFX, Ticker

NAME = "NUDLE"

T = 640          # texture tile size (texels), wraps
S = 20           # street spacing
F = 6            # fog levels
SH = 2           # shades (floor / folded panel)
NB = 22          # base colours
SKYN = 8
SKY0 = NB * SH * F

# base colour ids
LAND, BUILD, BLOCK2, MINOR, MAJOR, MARKET, PARK, PATH, WATER, WATER2, COAST, BRIDGE, TR_G, TR_O, TR_R, PIER, VOID = range(17)
ROOF, ROOF_LIGHT, TREES, LANE, PAPER = range(17, 22)

NIGHT = {
    LAND: (16, 18, 32), BUILD: (34, 38, 64), BLOCK2: (24, 26, 46), MINOR: (62, 68, 104),
    MAJOR: (0, 140, 165), MARKET: (220, 40, 130), PARK: (14, 66, 40), PATH: (40, 112, 62),
    WATER: (6, 22, 66), WATER2: (14, 40, 100), COAST: (0, 210, 240), BRIDGE: (255, 140, 20),
    TR_G: (57, 230, 60), TR_O: (255, 150, 0), TR_R: (255, 30, 60), PIER: (70, 60, 50), VOID: (30, 0, 50),
}
HACKED = {
    LAND: (10, 0, 12), BUILD: (40, 0, 36), BLOCK2: (22, 0, 24), MINOR: (110, 10, 70),
    MAJOR: (255, 15, 123), MARKET: (245, 230, 10), PARK: (30, 0, 60), PATH: (80, 20, 120),
    WATER: (24, 0, 48), WATER2: (60, 0, 90), COAST: (255, 15, 123), BRIDGE: (0, 229, 255),
    TR_G: (0, 229, 255), TR_O: (245, 230, 10), TR_R: (255, 15, 123), PIER: (60, 0, 60), VOID: (0, 0, 0),
}
NIGHT.update({ROOF: (49,53,78), ROOF_LIGHT: (76,79,100), TREES: (24,94,53),
              LANE: (121,139,169), PAPER: (24,27,43)})
HACKED.update({ROOF: (58,5,47), ROOF_LIGHT: (83,17,66), TREES: (49,10,79),
               LANE: (255,85,166), PAPER: (18,2,24)})
FOG_N = (54, 16, 78)
FOG_H = (90, 0, 50)

DISTRICTS = ["MISSION", "SOMA", "MARINA", "OAKLAND", "CHINATOWN", "NOB HILL", "THE CASTRO", "HAIGHT",
             "TENDERLOIN", "DOGPATCH", "PRESIDIO", "NORTH BEACH", "EMBARCADERO", "SUNSET", "RICHMOND",
             "BERNAL HTS", "POTRERO", "FIDI", "JAPANTOWN", "TWIN PEAKS"]

QUERIES = [
    ("best taco near me", ["TACO LOCO", "EL GUAPO", "TACOS 24/7", "SALSA SAM'S", "BURRITO BOB"]),
    ("how to hide from ctOS", ["SAFE HOUSE", "HACKERSPACE", "TINFOIL HATS", "NO-CAM ALLEY"]),
    ("cat cafe open now", ["WHISKERS", "PURR BREW", "MEOW & CO", "LITTER LOUNGE"]),
    ("parking under $40", ["NOPE", "STILL NOPE", "MYTHICAL SPOT", "TOW ZONE"]),
    ("vegan donuts", ["HOLE FOODS", "DOUGH-NOT", "GLAZE ME", "SPRINKLE LAB"]),
    ("drone charging station", ["ZAP SPOT", "BATTERY BAR", "VOLT CAFE", "PROP SHOP"]),
    ("karaoke tonight", ["MIC DROP", "OFF KEY", "SING SING", "ECHO ROOM"]),
    ("retro arcade", ["8-BIT BAR", "INSERT COIN", "HIGH SCORE", "PIXEL PALACE"]),
    ("boba with no line", ["TAPIOCA TOM", "BOBA FETT-UCCINE", "PEARL JAM", "BUBBLE HUB"]),
    ("where did i park", ["HERE?", "MAYBE HERE", "DEFINITELY NOT", "IMPOUND LOT"]),
    ("is blume watching me", ["YES", "ALSO YES", "BLUME HQ", "CAMERA #4471"]),
    ("free wifi no tracking", ["LOL", "DEDSEC NODE", "OPEN NET", "LIBRARY"]),
]
STREETS = ["MARKET ST", "MISSION ST", "VALENCIA ST", "VAN NESS AVE", "LOMBARD ST", "HWY 101", "BAY BRIDGE",
           "GEARY BLVD", "DIVISADERO", "EMBARCADERO"]
NEWS = ["#NUDLE Maps now 3% less creepy", "Traffic heavy on HWY 101, as always", "#ctOS sync complete",
        "New: Street View for your fridge", "Reroute: Lombard St still curvy",
        "Nudle CEO: 'we only know where you are'", "#BLUME partners with Nudle for 'safety'",
        "Bay Bridge: 14 min delay", "Report a pothole, win a pothole"]

SKULL_PX = ["..XXXXX..", ".XXXXXXX.", "XXXXXXXXX", "XX..X..XX", "XX..X..XX", "XXXXXXXXX",
            ".XXX.XXX.", "..X.X.X..", "..XXXXX.."]


def _wrap(d):
    return (d + T / 2) % T - T / 2


def build_textures():
    ax = np.arange(T)
    X, Z = np.meshgrid(ax, ax)          # tex[z, x]
    tex = np.full((T, T), LAND, np.int16)
    mx, mz = X % S, Z % S
    dx = np.minimum(mx, S - mx)
    dz = np.minimum(mz, S - mz)
    bx, bz = X // S, Z // S
    h = (bx * 73856093 ^ bz * 19349663) & 0xFFFF
    # blocks and building footprints
    inner = (dx > 2) & (dz > 2)
    tex[inner & (h % 3 == 0)] = BLOCK2
    lx, lz = (X + bz * 3) % 7, (Z + bx * 5) % 6
    tex[inner & (dx > 3) & (dz > 3) & (lx != 0) & (lz != 0)] = BUILD
    # parks: random blocks + one big park
    park = ((h % 11) == 0) | ((bx >= 3) & (bx <= 6) & (bz >= 10) & (bz <= 11))
    tex[park & (dx > 1) & (dz > 1)] = PARK
    tex[park & (dx > 1) & (dz > 1) & ((((X + Z) % 9) == 0) | (((X - Z) % 13) == 0))] = PATH
    # streets
    minor = (dx <= 1) | (dz <= 1)
    tex[minor] = MINOR
    rmx = ((X + S // 2) // S) % 4 == 0
    rmz = ((Z + S // 2) // S) % 4 == 0
    major_v = rmx & (dx <= 2)
    major_h = rmz & (dz <= 2)
    tex[major_v | major_h] = MAJOR
    # traffic on major segments
    seg_v = ((Z // S) * 31 + (X // S) * 7) % 7
    seg_h = ((X // S) * 17 + (Z // S) * 11) % 7
    for cls, val in ((TR_G, 2), (TR_O, 3), (TR_R, 4)):
        tex[major_v & (dx <= 1) & (seg_v == val)] = cls
        tex[major_h & (dz <= 1) & (seg_h == val)] = cls
    # Market Street diagonal
    d = (X - Z) % T
    dd = np.minimum(d, T - d) * 0.7071
    tex[dd <= 2.2] = MARKET
    # water (periodic blob) with coast and bridges
    f = (np.sin(4 * np.pi * X / T) + np.sin(4 * np.pi * Z / T + 0.7) +
         0.5 * np.sin(2 * np.pi * (X + 2 * Z) / T))
    water = f > 1.55
    coast = (f > 1.42) & ~water
    tex[coast] = COAST
    tex[water] = np.where(((X * 3 + Z * 5) % 11) < 2, WATER2, WATER)[water]
    tex[water & (major_v | major_h)] = BRIDGE
    tex[water & (major_v | major_h) & ((X + Z) % 6 < 3)] = PIER
    # Roof seams and rooftop equipment stay inside footprints; park crowns are clustered.
    roof = tex == BUILD
    tex[roof & ((lx == 1) | (lz == 1))] = ROOF
    tex[roof & (lx == 3) & (lz == 3)] = ROOF_LIGHT
    trees = (tex == PARK) & (((X % 7-3)**2 + (Z % 7-3)**2) < 5)
    tex[trees] = TREES
    tex[(tex == LAND) & ((X*7+Z*11)%23 == 0)] = PAPER
    tex[(tex == MAJOR) & ((dx == 0) | (dz == 0)) & ((X+Z)%7 < 3)] = LANE
    # far LOD: no minor streets / buildings
    mid = tex.copy()
    mid[(mid == BUILD) | (mid == BLOCK2) | (mid == ROOF) | (mid == ROOF_LIGHT) | (mid == PAPER)] = LAND
    mid[(mid == PATH) | (mid == TREES)] = PARK
    mid[mid == LANE] = MAJOR
    mid[mid == WATER2] = WATER
    far = mid.copy()
    far[far == MINOR] = LAND
    land = ~(water | coast)
    return tex, mid, far, land


class Pin:
    def __init__(self, wx, wz, label, col, now, kind="poi", delay=0.0):
        self.wx, self.wz, self.label, self.col = wx, wz, label, col
        self.born = now + delay
        self.kind = kind
        self.rating = "%.1f" % random.uniform(2.1, 5.0)
        self.dying = None


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = 2 * h
        self.last = time.time()
        self.tex, self.texmid, self.texfar, self.land = build_textures()
        self.glitch = Glitch(0.004)
        self.fx = PostFX(band_speed=5)
        self.particles = Particles()
        self.ticker = Ticker("NUDLE", NEWS, color=CYAN)
        # camera
        self.f = self.ph * 1.15
        self.cxp = w / 2
        self.Hc = 75.0
        self.Zf = 235.0
        self.campos = [random.uniform(0, T), random.uniform(0, T)]
        self.yaw = 0.0
        self.top = 3                    # first map cell row below search bar
        self.cyp = (self.top * 2 + self.ph) / 2 + 2
        self.pitch_base = math.atan((self.cyp - self.top * 2 - 5) / self.f)
        self.A = ((np.arange(w) - self.cxp) / self.f)[None, :]
        self.B = (-(np.arange(self.ph) - self.cyp) / self.f)[:, None]
        rows = np.arange(self.ph)
        self.skyrow = (SKY0 + np.minimum(SKYN - 1, rows * SKYN // max(1, int(self.ph * 0.35)))).astype(np.int16)[:, None]
        self.offset = [0.0, 0.0]
        self.atanA = np.arctan(self.A)
        self.rowsP = np.arange(self.ph)[:, None]
        self.skyline = self.make_skyline()
        self.offset_new = None
        # labels
        rng = random.Random(7)
        self.labels = []
        names = DISTRICTS[:]
        rng.shuffle(names)
        for i, nm in enumerate(names * 2):
            for _ in range(60):
                tx, tz = rng.randrange(T), rng.randrange(T)
                if self.land[tz, tx] and all(min(abs(_wrap(tx - a)), 999) + abs(_wrap(tz - b)) > 110 for a, b, _ in self.labels):
                    self.labels.append((tx, tz, nm))
                    break
        self.labels.append((int(T * 0.125), int(T * 0.07), "SF BAY"))
        self.labels.append((int(T * 0.625), int(T * 0.57), "LAKE MERRITT"))
        # state
        self.pins = []
        self.route = None
        self.cars = [self.new_car() for _ in range(40)]
        self.fold = 0.0
        self.event = None
        self.flip = None
        self.hack_until = 0.0
        self.hack_start = 0.0
        self.eta = None
        self.phase_q = list(range(len(QUERIES)))
        random.shuffle(self.phase_q)
        self.cycle = 0
        self.new_cycle(self.last)

    def make_skyline(self):
        n = 1440
        k = self.ph / 90
        rng = random.Random(3)
        hgt = np.zeros(n)
        i = 0
        while i < n:
            wdt = rng.randint(3, 10)
            hgt[i:i + wdt] = rng.choice((0, 0, 1, 2, 3, 4, 5, 6, 8)) * k
            i += wdt + rng.randint(0, 3)
        hgt += 1
        # landmarks: pyramid, towers, sutro
        for c, kind in ((200, "pyr"), (520, "tower"), (560, "tower"), (900, "sutro"), (1200, "pyr")):
            for d in range(-14, 15):
                if kind == "pyr":
                    v = max(0, 22 - abs(d) * 1.9)
                elif kind == "tower":
                    v = 18 - (abs(d) ** 2) * 0.6 if abs(d) < 5 else 0
                else:
                    v = 20 if d == 0 else (9 if abs(d) == 3 else 0)
                hgt[(c + d) % n] = max(hgt[(c + d) % n], v * k)
        return hgt

    # ------------------------------------------------------------ coordinates
    def to_local(self, wx, wz):
        dx, dz = _wrap(wx - self.campos[0]), _wrap(wz - self.campos[1])
        c, s = self.cy_, self.sy_
        return dx * c - dz * s, dx * s + dz * c

    def to_world(self, lx, lz):
        c, s = self.cy_, self.sy_
        return self.campos[0] + lx * c + lz * s, self.campos[1] - lx * s + lz * c

    def proj(self, lx, lz, hgt=0.0):
        """local map point (+height along surface normal) -> (sx, spy, depth) in pixel space."""
        th = self.fold
        if th <= 0 or lz <= self.Zf:
            px, py, pz = lx, hgt, lz
        else:
            sv = lz - self.Zf
            st, ct = math.sin(th), math.cos(th)
            px, py, pz = lx, sv * st + hgt * ct, self.Zf + sv * ct - hgt * st
        vy, vz = py - self.Hc, pz
        cp, sp = self.cp_, self.sp_
        b = vy * cp + vz * sp
        c = -vy * sp + vz * cp
        if c < 2:
            return None
        return self.cxp + self.f * px / c, self.cyp - self.f * b / c, c

    # ------------------------------------------------------------ game flow
    def new_car(self):
        axis = random.random() < 0.5
        line = (random.randrange(T // (S * 4)) * 4) * S
        return [axis, line, random.uniform(0, T), random.choice((-1, 1)) * random.uniform(6, 16)]

    def new_cycle(self, now):
        self.cycle += 1
        qi = self.phase_q[self.cycle % len(self.phase_q)]
        self.query, self.results = QUERIES[qi]
        self.q_start = now + 0.6
        self.q_done = self.q_start + len(self.query) / 14.0 + 0.6
        self.pins_at = self.q_done + 0.2
        self.route_at = self.pins_at + 1.8
        self.cycle_end = self.route_at + 11.0
        self.route = None
        self.eta = None
        for p in self.pins:
            p.dying = now
        r = random.random()
        self.event = "fold" if r < 0.45 else ("flip" if r < 0.75 else "hack")
        if self.event == "flip":
            self.flip = {"start": now, "dur": 3.2}
            self.offset_new = [random.uniform(60, 260), random.uniform(60, 260)]
            self.q_start += 3.0
            self.q_done += 3.0
            self.pins_at += 3.0
            self.route_at += 3.0
            self.cycle_end += 3.0

    def drop_pins(self, now):
        # you-are-here near the camera, results further ahead
        ylx, ylz = random.uniform(-20, 20), random.uniform(125, 140)
        wx, wz = self.to_world(ylx, ylz)
        wx, wz = self.snap(wx, wz)
        self.here = (wx, wz)
        spots = []
        for i, nm in enumerate(self.results):
            for _ in range(30):
                lx = random.uniform(-140, 140) * min(1.0, self.w / 175)
                lz = random.uniform(180, 300)
                px, pz = self.snap(*self.to_world(lx, lz))
                if not self.land[int(pz + self.offset[1]) % T, int(px + self.offset[0]) % T]:
                    continue
                if all(abs(_wrap(px - a)) + abs(_wrap(pz - b)) > 70 for a, b in spots) and \
                        abs(_wrap(px - wx)) + abs(_wrap(pz - wz)) > 90:
                    spots.append((px, pz))
                    break
        cols = [PINK, YELLOW, GREEN, ORANGE, CYAN]
        for i, (px, pz) in enumerate(spots):
            self.pins.append(Pin(px, pz, self.results[i], cols[i % len(cols)], now, delay=i * 0.28))
        self.pins.append(Pin(wx, wz, "YOU", CYAN, now, kind="here"))
        self.targets = spots

    def snap(self, wx, wz):
        ox, oz = self.offset
        tx, tz = wx + ox, wz + oz
        return round(tx / S) * S - ox, round(tz / S) * S - oz

    def make_route(self, now):
        if not getattr(self, "targets", None):
            return
        tx, tz = random.choice(self.targets)
        hx, hz = self.here
        ex, ez = hx + _wrap(tx - hx), hz + _wrap(tz - hz)
        pts = [(hx, hz)]
        x, z = hx, hz
        while abs(ex - x) > 0.5 or abs(ez - z) > 0.5:
            go_x = abs(ex - x) > 0.5 and (abs(ez - z) < 0.5 or random.random() < 0.5)
            if go_x:
                x += math.copysign(min(S * random.choice((1, 2)), abs(ex - x)), ex - x)
            else:
                z += math.copysign(min(S * random.choice((1, 2)), abs(ez - z)), ez - z)
            pts.append((x, z))
        dense = []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(bx - ax, bz - az) / 2.5))
            for i in range(n):
                dense.append((ax + (bx - ax) * i / n, az + (bz - az) * i / n))
        dense.append(pts[-1])
        dist = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        for p in self.pins:
            if p.kind == "poi" and abs(_wrap(p.wx - tx)) < 1 and abs(_wrap(p.wz - tz)) < 1:
                p.kind = "dest"
        self.route = {"pts": dense, "start": now, "draw": 1.4, "travel": 7.0, "dist": dist}
        self.eta = {"start": now + 1.4, "min": max(2, int(dist / 22)), "mi": dist / 150,
                    "via": random.choice(STREETS), "end": (ex, ez)}

    # ------------------------------------------------------------ map raster
    def raster(self, s, now, hacked):
        cp, sp = self.cp_, self.sp_
        B = self.B
        dy = B * cp - sp
        dz = B * sp + cp
        Hc, Zf = self.Hc, self.Zf
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = np.where(dy < -1e-6, Hc / -dy, np.inf)
            z1 = dz * t1
            th = self.fold
            if th > 1e-3:
                st, ct = math.sin(th), math.cos(th)
                t1 = np.where(z1 < Zf, t1, np.inf)
                den = dy * ct - dz * st
                t2 = (-Hc * ct - Zf * st) / den
                sv = (Hc + t2 * dy) * st + (t2 * dz - Zf) * ct
                t2 = np.where((t2 > 0) & (sv >= 0) & (sv < 600), t2, np.inf)
                use2 = t2 < t1
                t = np.minimum(t1, t2)
                lz = np.where(use2, Zf + sv, z1)
                shade = use2.astype(np.int16)
            else:
                t = t1
                lz = z1
                shade = np.zeros_like(t1, np.int16)
            sky = ~np.isfinite(t)
            t = np.where(sky, 1e4, t)
            lz = np.where(sky, 0, lz)
        lx = self.A * t
        c, sn = self.cy_, self.sy_
        U = self.campos[0] + self.offset[0] + lx * c + lz * sn
        V = self.campos[1] + self.offset[1] - lx * sn + lz * c
        fl = self.flip
        if fl is not None:
            prog = (now - fl["start"]) / fl["dur"]
            TS = 4 * S
            iu = np.floor(U / TS)
            iv = np.floor(V / TS)
            fu = U / TS - iu
            ccx = (self.campos[0] + self.offset[0]) / TS
            ccz = (self.campos[1] + self.offset[1]) / TS
            dist = np.hypot(iu + 0.5 - ccx, iv + 0.5 - ccz)
            a = np.clip(prog * 2.4 - dist * 0.3 - (((iu * 7 + iv * 3) % 5) * 0.05), 0, 1) * np.pi
            ca = np.cos(a)
            safe = np.where(np.abs(ca) < 0.04, 0.04, ca)
            fu2 = (fu - 0.5) / safe + 0.5
            gap = (fu2 < 0) | (fu2 > 1) | (np.abs(ca) < 0.04)
            fu2 = np.where(ca < 0, 1 - fu2, fu2)
            U = (iu + np.clip(fu2, 0, 0.999)) * TS
            alt = ca < 0
            U = np.where(alt, U + (self.offset_new[0] - self.offset[0]), U)
            V = np.where(alt, V + (self.offset_new[1] - self.offset[1]), V)
            shade = np.broadcast_to(shade, U.shape) | alt.astype(np.int16)
        ui = (U + T * 4096).astype(np.int64) % T
        vi = (V + T * 4096).astype(np.int64) % T
        base = self.tex[vi, ui]
        base = np.where(t > 260, self.texmid[vi, ui], base)
        base = np.where(t > 480, self.texfar[vi, ui], base)
        fogd = 820.0
        fog = np.clip(t * (F / fogd), 0, F - 1).astype(np.int16)
        if fl is not None:
            fog = np.minimum(F - 1, fog + ((1 - np.abs(ca)) * 3).astype(np.int16))
            flipping = (a > 0.01) & (a < 3.13)
            edge = flipping & ((fu2 < 0.04) | (fu2 > 0.96) | (fu - 0.0 < 0.0))
            base = np.where(edge, COAST, base)
            base = np.where(gap, VOID, base)
        idx = (base * (SH * F) + shade * F + fog)
        idx = np.where(sky, self.skyrow, idx)
        # distant skyline silhouette on the horizon
        hy = self.cyp - self.f * (sp / cp)
        ang = ((self.yaw + self.atanA) * (self.skyline.size / (2 * math.pi))).astype(np.int64) % self.skyline.size
        hcol = self.skyline[ang[0]]
        rows = self.rowsP
        sil = sky & (rows > hy - hcol[None, :]) & (rows <= hy + 1)
        win = sil & (((rows * 7 + ang * 3) % 23) == 0)
        idx = np.where(sil, SKY0 + SKYN, idx)
        idx = np.where(win, SKY0 + SKYN + 1, idx)
        pal = self.palette(now, hacked)
        L = idx.tolist()
        g = pal.__getitem__
        gb = self._palb.__getitem__
        band = int((now * 5) % (self.h + 12)) - 6
        pt, pb = s.pt, s.pb
        for y in range(self.top, self.h):
            gg = gb if band <= y <= band + 1 else g
            pt[y] = list(map(gg, L[2 * y]))
            pb[y] = list(map(gg, L[2 * y + 1]))
        self.pal = pal

    def palette(self, now, hacked):
        src = HACKED if hacked else NIGHT
        fogc = FOG_H if hacked else FOG_N
        key = (hacked, int(now * 8))
        if getattr(self, "_pkey", None) == key:
            return self._pal
        pal = [None] * (SKY0 + SKYN + 2)
        for b in range(NB):
            col = src[b]
            if b in (TR_G, TR_O, TR_R):
                col = blend(col, WHITE, 0.35 * pulse(now, 5, b))
                col = blend(col, BLACK, 0.4 * (1 - pulse(now, 3, b * 2)))
            elif b == WATER2:
                col = blend(src[WATER], src[WATER2], pulse(now, 1.7))
            elif b == COAST:
                col = blend(col, WHITE, 0.25 * pulse(now, 2.2))
            for sh in range(SH):
                c2 = blend(col, PURPLE if not hacked else PINK, 0.16) if sh else col
                if sh:
                    c2 = blend(c2, WHITE, 0.06)
                for fg in range(F):
                    k = (fg / (F - 1)) ** 1.3 * 0.88
                    pal[(b * SH + sh) * F + fg] = blend(c2, fogc, k)
        top = (6, 0, 16) if not hacked else (20, 0, 10)
        for i in range(SKYN):
            pal[SKY0 + i] = blend(top, blend(fogc, PINK, 0.25), (i / (SKYN - 1)) ** 1.6)
        pal[SKY0 + SKYN] = (26, 8, 44) if not hacked else (40, 0, 24)
        pal[SKY0 + SKYN + 1] = blend(YELLOW, PINK, 0.3) if not hacked else CYAN
        self._pkey, self._pal = key, pal
        self._palb = [blend(c, WHITE, 0.22) for c in pal]
        return pal

    # ------------------------------------------------------------ overlays
    def draw_pin(self, s, p, now, hacked):
        age = now - p.born
        if age < 0:
            return
        lx, lz = self.to_local(p.wx, p.wz)
        q = self.proj(lx, lz)
        if not q:
            return
        sx, sy, depth = q
        if not (-10 < sx < s.w + 10 and self.top * 2 < sy < s.ph + 10):
            return
        scale = max(0.55, min(1.3, 190 / depth))
        if p.dying is not None:
            k = 1 - (now - p.dying) / 0.5
            if k <= 0:
                return
            scale *= k
        # drop with bounce
        T0 = 0.45
        if age < T0:
            off = 70 * (1 - (age / T0) ** 2)
        else:
            u = age - T0
            off = 10 * abs(math.sin(u * 8)) * math.exp(-u * 4.5)
        x, y = int(sx), int(sy)
        # shadow
        sw = max(1, int((3 - min(2.5, off / 25)) * scale))
        for dx in range(-sw, sw + 1):
            s.pixel(x + dx, y, (0, 0, 0))
        if p.kind == "here":
            r = (now * 1.6) % 1
            s.pixel_circle(sx, sy, 2 + r * 7 * scale, blend(CYAN, BLACK, r), fill=False)
            s.pixel_circle(sx, sy, 2.2 * scale + 0.5, WHITE)
            s.pixel_circle(sx, sy, 1.5 * scale, (40, 130, 255))
            return
        top = y - int(off)
        col = p.col
        if p.kind == "dest":
            col = blend(PINK, WHITE, 0.3 * pulse(now, 6))
        if hacked:
            sk = [r for r in SKULL_PX]
            hgt = len(sk)
            k = max(1, int(round(scale)))
            for j, row in enumerate(sk):
                for i, ch in enumerate(row):
                    if ch == "X":
                        for a in range(k):
                            for b in range(k):
                                s.pixel(x - 4 * k + i * k + a, top - (hgt - j) * k - 2 + b,
                                        PINK if j < 3 else blend(PINK, WHITE, 0.5))
            s.pixel_line(x, top - 2, x, top, PINK)
            return
        r = 3.0 * scale
        cy = top - r - 3 * scale
        for k in range(int(3 * scale) + 1):
            hw = int((1 - k / (3 * scale + 1)) * r * 0.75)
            for dx in range(-hw, hw + 1):
                s.pixel(x + dx, top - k, blend(col, BLACK, 0.25))
        s.pixel_circle(sx+1, cy+1, r, blend(col, BLACK, .45))
        s.pixel_circle(sx, cy, r, col)
        s.pixel(int(sx)-1, int(cy)-1, blend(col, WHITE, .65))
        s.pixel_circle(sx, cy, max(0.8, r * 0.38), WHITE)
        # label
        if age > 0.6 and p.dying is None:
            ly = int(cy - r) // 2 - 1
            lab = p.label if p.kind != "dest" else "> " + p.label
            if ly > self.top:
                lx0 = x - len(lab) // 2
                self.label(s, lx0, ly, lab, WHITE if p.kind == "dest" else col, avoid=p.kind != "dest")
                if p.kind == "dest" or (age < 3 and s.w > 120):
                    rt = p.rating + "/5"
                    self.label(s, x - len(rt) // 2, ly - 1 if ly - 1 > self.top else ly + 1, rt, YELLOW,
                               avoid=p.kind != "dest")

    def label(self, s, x, y, txt, col, avoid=False):
        if not (0 <= y < s.h):
            return
        r = (x - 1, y, len(txt) + 2, 1)
        if avoid and any(not (r[0] + r[2] <= o[0] or o[0] + o[2] <= r[0]) and r[1] == o[1] for o in self.occ):
            return
        self.occ.append(r)
        for i, ch in enumerate(txt):
            xx = x + i
            if 0 <= xx < s.w:
                under = s.pt[y][xx] or (0, 0, 0)
                s.bg[y][xx] = blend(under, BLACK, 0.55)
                s.ch[y][xx] = ch
                s.fg[y][xx] = col

    def draw_route(self, s, now, hacked):
        rt = self.route
        if not rt:
            return
        age = now - rt["start"]
        pts = rt["pts"]
        n = len(pts)
        drawn = int(n * min(1, age / rt["draw"]))
        tprog = (age - rt["draw"]) / rt["travel"]
        dot_i = int(max(0, min(1, tprog)) * (n - 1))
        proj = []
        for wx, wz in pts[:max(1, drawn)]:
            lx, lz = self.to_local(wx, wz)
            proj.append(self.proj(lx, lz, 0.3))
        base = PINK if hacked else (40, 140, 255)
        glow = YELLOW if hacked else CYAN
        for i in range(len(proj) - 1):
            a, b = proj[i], proj[i + 1]
            if not a or not b:
                continue
            done = i < dot_i
            band = (i - now * 18) % 22 < 3
            col = blend(base, (60, 60, 90), 0.5) if done else (blend(glow, WHITE, 0.4) if band else base)
            s.pixel_line(a[0], a[1], b[0], b[1], col)
            s.pixel_line(a[0], a[1] - 1, b[0], b[1] - 1, col if done else blend(col, WHITE, 0.25))
        if age < rt["draw"] and proj and proj[-1]:
            hx, hy, _ = proj[-1]
            self.particles.add(hx / 1.0, hy / 2, random.uniform(-4, 4), random.uniform(-2, 1), 0.4, "·", glow)
        if 0 <= tprog <= 1.05 and dot_i < len(proj) and proj[dot_i]:
            dx, dy, _ = proj[dot_i]
            s.pixel_circle(dx, dy - 1, 3, blend(glow, WHITE, 0.5 * pulse(now, 10)))
            s.pixel_circle(dx, dy - 1, 1.6, WHITE)
        if tprog > 1.05 and not rt.get("arrived"):
            rt["arrived"] = True
            q = proj[-1] if proj else None
            if q:
                self.particles.burst(q[0], q[1] / 2, 30, (PINK, YELLOW, CYAN, WHITE), speed=9)

    def draw_eta(self, s, now, hacked):
        e = self.eta
        if not e or now < e["start"]:
            return
        lx, lz = self.to_local(*e["end"])
        q = self.proj(lx, lz)
        k = ease_out((now - e["start"]) / 0.35)
        cw = 24
        ch_ = 6
        if q:
            x = int(q[0]) + 4
            y = int(q[1]) // 2 - ch_ - 2
        else:
            x, y = s.w - cw - 2, self.top + 2
        x = max(1, min(s.w - cw - 2, x))
        y = max(self.top + 1, min(s.h - ch_ - 3, y))
        w2 = max(4, int(cw * k))
        col = PINK if hacked else CYAN
        s.box(x, y, w2, ch_, col, title=("NUDLE" if not hacked else "DEDSEC") if k >= 1 else None)
        if k < 1:
            return
        rt = self.route
        prog = max(0.0, min(1.0, (now - rt["start"] - rt["draw"]) / rt["travel"])) if rt else 0
        mins = max(0, int(round(e["min"] * (1 - prog))))
        if hacked:
            lines = [("ETA  ??? MIN", YELLOW), ("ROUTE BY #DEDSEC", PINK), ("ctOS CAN'T SEE YOU", WHITE)]
        else:
            lines = [("ETA %2d MIN  %.1f MI" % (mins, e["mi"] * (1 - prog)), WHITE),
                     ("VIA " + e["via"], GREY), ("ARRIVING" if prog >= 1 else "TRAFFIC: " +
                                                 random.Random(int(e["start"])).choice(("LIGHT", "MEH", "UGH")), YELLOW)]
        for i, (t, c) in enumerate(lines):
            s.text(x + 2, y + 1 + i, t[:cw - 4], c)
        bw = cw - 4
        fill = int(bw * prog)
        s.text(x + 2, y + 4, "█" * fill + "░" * (bw - fill), col)

    def draw_search(self, s, now, hacked):
        bw = min(72, s.w - 14)
        x0 = (s.w - bw) // 2
        col = PINK if hacked else blend(CYAN, WHITE, 0.2)
        s.box(x0, 0, bw, 3, col)
        logo = [("N", (66, 133, 244)), ("U", (234, 67, 53)), ("D", (251, 188, 5)), ("L", (66, 133, 244)),
                ("E", (52, 168, 83))]
        if hacked:
            logo = [(c, random.choice((PINK, CYAN, YELLOW))) for c in "DEDSEC"]
        for i, (c, cc) in enumerate(logo):
            s.put(x0 + 2 + i, 1, c, cc)
        tx = x0 + 3 + len(logo) + 1
        s.put(tx - 1, 1, "│", GREY)
        q = self.query if not hacked else "dedsec was here"
        typed = q[:max(0, int((now - self.q_start) * 14))] if now > self.q_start else ""
        if hacked:
            typed = "".join(random.choice("#$%&!") if random.random() < 0.15 else ch for ch in q)
        s.text(tx + 1, 1, typed[:bw - 16], WHITE)
        if int(now * 3) % 2 and len(typed) < len(q):
            s.put(tx + 1 + len(typed), 1, "█", YELLOW)
        s.text(x0 + bw - 4, 1, "◉", YELLOW if now < self.q_done else col)
        # suggestions while typing
        if self.q_start < now < self.q_done and len(typed) > 2 and s.h > 30 and not hacked:
            sug = [q + " open now", q + " (no cameras)", q + " ctOS-free"][: 3 if s.h > 40 else 2]
            sw = min(bw - 8, max(len(t) for t in sug) + 6)
            s.box(tx - 1, 2, sw, len(sug) + 2, DIM_CYAN)
            s.put(tx - 1, 2, "├", col)
            for i, t in enumerate(sug):
                s.text(tx + 1, 3 + i, "○ ", GREY)
                s.text(tx + 3, 3 + i, typed, WHITE)
                s.text(tx + 3 + len(typed), 3 + i, t[len(typed):sw - 5], GREY)

    def draw_hud(self, s, now, hacked):
        # compass
        cx, cy = s.w - 5, 1
        if cx > (s.w + min(72, s.w - 14)) // 2 + 2:
            a = -self.yaw
            nx, ny = int(round(cx + math.sin(a) * 2)), int(round(cy - math.cos(a) * 1))
            s.put(cx, cy, "◆", GREY)
            s.put(nx, max(0, ny), "N", PINK if hacked else YELLOW)
            s.put(int(round(cx - math.sin(a) * 2)), min(2, int(round(cy + math.cos(a)))), "·", GREY)
        # zoom controls
        zx = s.w - 4
        zy = s.h // 2 - 2
        for i, t in enumerate(("┌─┐", "│+│", "├─┤", "│-│", "└─┘")):
            s.text(zx, zy + i, t, GREY)
        # scale bar & layers
        y = s.h - 3
        s.text(2, y, "├────┤ 0.5 MI", GREY)
        lay = "LAYERS: TRAFFIC ● TRANSIT ○ CAMERAS " + ("●" if hacked else "○")
        if s.w > 110:
            s.text(s.w - len(lay) - 6, y, lay, PINK if hacked else DIM_CYAN)
        # district labels
        for tx, tz, nm in self.labels:
            if self.flip is not None:
                break
            lx, lz = self.to_local(tx - self.offset[0], tz - self.offset[1])
            if lz < 50:
                continue
            q = self.proj(lx, lz)
            if not q or q[2] > 750:
                continue
            x, yy = int(q[0]), int(q[1]) // 2
            if not (self.top + 1 <= yy < s.h - 3):
                continue
            name = nm
            if hacked:
                name = "".join(random.choice("#%&$") if random.random() < 0.3 else c for c in "OWNED BY DEDSEC"[:len(nm) + 4])
            far = q[2] / 750
            col = blend(WHITE, (120, 100, 150), far) if not hacked else PINK
            spaced = " ".join(name) if q[2] < 330 and len(name) < 12 else name
            self.label(s, x - len(spaced) // 2, yy, spaced, col, avoid=True)

    def draw_cars(self, s, dt, hacked):
        for car in self.cars:
            axis, line, pos, v = car
            car[2] = (pos + v * dt) % T
            ox, oz = self.offset
            if axis:
                tx, tz = line + 0.6 * (1 if v > 0 else -1), car[2]
            else:
                tx, tz = car[2], line + 0.6 * (1 if v > 0 else -1)
            lx, lz = self.to_local(tx - ox, tz - oz)
            if lz < 10 or lz > 520:
                continue
            q = self.proj(lx, lz, 0.2)
            if q:
                col = (WHITE if v > 0 else (255, 40, 40)) if not hacked else CYAN
                s.pixel(int(q[0]), int(q[1]), col)

    # ------------------------------------------------------------ main
    def farewell(self, s, now, t):
        # Three hinged paper panels accordion inward before the map is put away.
        old = getattr(self, "_exit_snapshot", None)
        if old is None:
            self.step(s, now)
            old = self._exit_snapshot = s.snapshot()
        t = max(0, min(1, t))
        if t >= 1:
            return
        k = max(.025, math.cos(t * math.pi / 2))
        panel = s.w / 3
        width = panel * k
        left = (s.w - 3 * width) / 2
        layers = (s.ch, s.fg, s.bg, s.pt, s.pb)
        for y in range(s.h):
            dy = int(y * (1-t*.35) + s.h*t*.175)
            for x in range(int(left), int(left+3*width)):
                j = min(2, max(0, int((x-left)/width)))
                u = ((x-left)/width-j)
                sx = min(s.w-1, max(0,int((j+u)*panel)))
                shade = (1-t*.6) * (1-.35*math.sin(t*math.pi/2) if j==1 else 1)
                layers[0][dy][x] = old[0][y][sx]
                for n in range(1,5):
                    col = old[n][y][sx]
                    if col is not None:
                        layers[n][dy][x] = tuple(int(c*shade) for c in col)
        for j in (1,2):
            x = int(left+j*width)
            s.pixel_line(x, int(s.h*t*.35), x, int(s.h*2*(1-t*.175)), blend(GREEN, BLACK, t))
        if .1 < t < .85:
            s.center(s.h-3, "NUDLE MAP / FOLDED", blend(GREEN, BLACK, t))

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        hacked = now < self.hack_until
        glitch = self.glitch.active(now) or (hacked and now - self.hack_start < 0.5)

        # camera drift
        self.yaw = math.sin(now * 0.05) * 0.5 + now * 0.01
        spd = 4.5
        self.campos[0] += math.sin(self.yaw) * spd * dt
        self.campos[1] += math.cos(self.yaw) * spd * dt
        pitch = self.pitch_base + math.sin(now * 0.13) * 0.03
        self.cy_, self.sy_ = math.cos(self.yaw), math.sin(self.yaw)
        self.cp_, self.sp_ = math.cos(pitch), math.sin(pitch)

        # flow
        if self.pins_at and now > self.pins_at:
            self.pins = [p for p in self.pins if p.dying is None]
            self.drop_pins(now)
            self.pins_at = None
        if self.route_at and now > self.route_at:
            self.make_route(now)
            self.route_at = None
            if self.event == "fold":
                self.fold_start = now + 2.0
            elif self.event == "hack":
                self.hack_start = now + random.uniform(2.5, 4.0)
                self.hack_until = self.hack_start + 5.5
        if self.event == "hack" and self.hack_start <= now < self.hack_start + dt * 1.5:
            self.glitch.trigger(now, 0.6)
            for p in self.pins:
                lx, lz = self.to_local(p.wx, p.wz)
                q = self.proj(lx, lz)
                if q:
                    self.particles.burst(q[0], q[1] / 2, 12, (PINK, PURPLE, WHITE), speed=8)
        if now > self.cycle_end:
            self.new_cycle(now)
        self.pins = [p for p in self.pins if p.dying is None or now - p.dying < 0.6]

        # fold animation
        self.fold = 0.0
        if self.event == "fold" and getattr(self, "fold_start", None) is not None and self.route_at is None:
            u = now - self.fold_start
            dur_up, hold, dur_dn = 2.2, 2.8, 2.0
            top_angle = 2.45
            if 0 <= u < dur_up:
                self.fold = top_angle * (0.5 - 0.5 * math.cos(math.pi * u / dur_up))
            elif dur_up <= u < dur_up + hold:
                self.fold = top_angle + math.sin((u - dur_up) * 2) * 0.05
            elif dur_up + hold <= u < dur_up + hold + dur_dn:
                v = (u - dur_up - hold) / dur_dn
                self.fold = top_angle * (0.5 + 0.5 * math.cos(math.pi * v))
        if self.flip is not None and now - self.flip["start"] > self.flip["dur"]:
            self.offset = self.offset_new
            self.flip = None

        self.occ = []
        self.raster(s, now, hacked)
        if self.fold > 0.02:
            q = self.proj(0, self.Zf)
            if q:
                py = int(q[1])
                gc = blend(CYAN if not hacked else PINK, WHITE, 0.3 * pulse(now, 8))
                s.pixel_line(0, py, s.w - 1, py, gc)
                for x in range(int(now * 40) % 12, s.w, 12):
                    s.pixel_line(x, py - 1, x + 3, py - 1, blend(gc, BLACK, 0.4))
        self.draw_cars(s, dt, hacked)
        self.draw_route(s, now, hacked)
        for p in sorted(self.pins, key=lambda p: -self.to_local(p.wx, p.wz)[1]):
            self.draw_pin(s, p, now, hacked)
        self.draw_hud(s, now, hacked)
        self.draw_eta(s, now, hacked)
        self.particles.step(s, dt)
        self.draw_search(s, now, hacked)

        if self.flip is not None:
            k = (now - self.flip["start"]) / self.flip["dur"]
            msg = " RECALCULATING REALITY %d%% " % int(min(1, k) * 100)
            s.center(self.top + 2, msg, YELLOW if int(now * 4) % 2 else WHITE)
        if self.fold > 0.3:
            msg = " NUDLE STREET VIEW: FOLD MODE (BETA) "
            s.center(s.h - 4, msg, blend(CYAN, WHITE, pulse(now, 4)))
        if hacked:
            self.draw_hack(s, now)
        self.ticker.draw(s, s.h - 1, now)
        if glitch:
            self.fx.apply(s, now, True)

    def draw_hack(self, s, now):
        msg = ["NUDLE MAPS HAS BEEN HIJACKED", "#DEDSEC  -  YOUR ROUTE IS OURS NOW"]
        bw = max(len(m) for m in msg) + 8
        x = (s.w - bw) // 2
        y = s.h // 2 - 2
        if (now - self.hack_start) % 1.6 < 1.2:
            col = PINK if int(now * 6) % 2 else YELLOW
            s.box(x, y, bw, 4, col, double=True)
            for i, m in enumerate(msg):
                s.center(y + 1 + i, m, WHITE if i else col)

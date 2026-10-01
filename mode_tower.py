"""TOWER: the camera spirals up the Blume ctOS tower, DedSec breaks every firewall ring, then boom."""

import math
import random
import time

from engine3d import clip2d
from lib import (BLACK, CYAN, DIM_CYAN, DIM_PINK, GREY, PINK, PURPLE, WHITE, YELLOW, Glitch,
                 blend, ease_out, pulse)
from mode_logo import SKULL
from sysdata import DATA
from widgets import Particles, PostFX

NAME = "TOWER"

NEAR = 0.25
NF = 40                 # floors / firewall layers
FH = 1.2                # floor height (world units)
TOP = NF * FH
TIERS = [(0, 18, 5.0), (18, 32, 4.2), (32, 40, 3.4)]
LAYER_T = 0.95          # seconds per firewall layer
INTRO = 2.5
HOLD = 2.2              # pause at the top before the boom
BOOM = 9.0              # explosion + skull duration
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

NAVY = (16, 20, 44)
STEEL = (44, 66, 120)
OCT = [math.radians(22.5 + 45 * k) for k in range(8)]
HEX = [math.tau * k / 6 for k in range(6)]


def tier_r(floor):
    for a, b, r in TIERS:
        if a <= floor < b:
            return r
    return TIERS[-1][2]


# ---------------------------------------------------------------- tiny pixel-space 3D helpers

class Cam:
    def __init__(self, w, h, fov=1.0):
        self.w, self.h = w, h
        self.f = h * fov
        self.cx, self.cy = w / 2, h / 2
        self.pos = [0.0, 0.0, 0.0]
        self.yaw = self.pitch = 0.0
        self.setup()

    def setup(self):
        self.c, self.s = math.cos(self.yaw), math.sin(self.yaw)
        self.cp, self.sp = math.cos(self.pitch), math.sin(self.pitch)
        self.f2 = self.f * 2

    def view(self, p):
        x, y, z = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        x, z = x * self.c - z * self.s, x * self.s + z * self.c
        return x, y * self.cp + z * self.sp, -y * self.sp + z * self.cp

    def pp(self, v):
        """view-space point -> pixel coords (x, py)."""
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
        n = len(vs)
        for i in range(n):
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
        return self.pp(va), self.pp(vb), (va[2] + vb[2]) / 2


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
                    (s.pb if py & 1 else s.pt)[cy][xa:xb] = [col] * k
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
            (s.pb if py & 1 else s.pt)[cy][xa:xb] = [col] * k


def fill_alpha(s, P, col, a):
    """Translucent polygon: blends over whatever pixel / sky is already there."""
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
        bgr = s.bg[py >> 1]
        for x in range(xa, xb + 1):
            c = row[x] or bgr[x] or BLACK
            o = memo.get(c)
            if o is None:
                o = memo[c] = (int(c[0] + (r - c[0]) * a), int(c[1] + (g - c[1]) * a), int(c[2] + (b - c[2]) * a))
            row[x] = o


def pline(s, x0, y0, x1, y1, col):
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
        (pb if py & 1 else pt)[py >> 1][x] = col


def line3(s, cam, a, b, col):
    r = cam.seg(a, b)
    if r:
        pline(s, r[0][0], r[0][1], r[1][0], r[1][1], col)


_BL = {}


def cblend(a, b, t):
    """Memoised blend for colours that repeat every frame (t is quantised)."""
    k = (a, b, int(t * 32))
    v = _BL.get(k)
    if v is None:
        if len(_BL) > 20000:
            _BL.clear()
        v = _BL[k] = blend(a, b, int(t * 32) / 32)
    return v


def tint_rows(s, y0, y1, col, t):
    """Cheap row tint (memoised per colour) used for scan band, glitch and flash."""
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


def postfx(s, now, glitch, speed=6.0):
    span = s.h + 16
    by = int((now * speed) % span) - 8
    for k, t in ((0, 0.2), (-1, 0.1), (1, 0.1)):
        tint_rows(s, by + k, by + k + 1, WHITE, t)
    if glitch:
        for _ in range(random.randint(2, 5)):
            y0 = random.randrange(s.h)
            dx = random.randint(-14, 14)
            n = random.randint(1, 4)
            for y in range(y0, min(s.h, y0 + n)):
                s.shift_row(y, dx)
            tint_rows(s, y0, y0 + n, random.choice((PINK, CYAN)), 0.25)
        if random.random() < 0.3:
            s.noise_lines(2)


def text_over_pixels(s):
    """Give text cells the colour of the pixels underneath instead of a black hole."""
    for y in range(s.h):
        rc, pt, pb, bg = s.ch[y], s.pt[y], s.pb[y], s.bg[y]
        for x in range(s.w):
            if rc[x] != " ":
                c = pb[x] or pt[x]
                if c is not None:
                    bg[x] = (c[0] * 3 // 4, c[1] * 3 // 4, c[2] * 3 // 4)


def prect(s, x, py, w, h, col):
    x, py = int(x), int(py)
    x0, x1 = max(0, x), min(s.w, x + w)
    if x1 <= x0:
        return
    for yy in range(max(0, py), min(s.ph, py + h)):
        (s.pb if yy & 1 else s.pt)[yy >> 1][x0:x1] = [col] * (x1 - x0)


# ---------------------------------------------------------------- the mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = Cam(w, h, fov=1.0)
        self.glitch = Glitch(0.006)
        self.fx = PostFX(band_speed=6)
        self.parts = Particles(900)
        self.vox = []
        self.last = time.time()
        rnd = random.Random(7)
        # city: lights on the ground and low blocks
        self.lights = []
        for _ in range(260 if w * h > 6000 else 170):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(14, 230) ** 1.0
            col = rnd.choice((YELLOW, (255, 170, 60), CYAN, PINK, WHITE, (255, 200, 120)))
            self.lights.append((math.cos(a) * d, math.sin(a) * d, col))
        self.blocks = []
        for _ in range(70):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(16, 120)
            self.blocks.append((math.cos(a) * d, math.sin(a) * d, rnd.uniform(1.5, 9), rnd.uniform(1.2, 3.5),
                                rnd.choice((CYAN, PINK, PURPLE, CYAN))))
        self.stars = [(rnd.uniform(0, math.tau), rnd.uniform(0.05, 0.9), rnd.choice((WHITE, CYAN, PINK, GREY)))
                      for _ in range(70)]
        self.wins = {}
        for f in range(NF):
            for k in range(8):
                for j in range(4):
                    self.wins[(f, k, j)] = rnd.random()
        self.lamps = [(rnd.uniform(0, math.tau), rnd.uniform(70, 120), rnd.uniform(0.25, 0.5), rnd.uniform(0, 6)) for _ in range(3)]
        self.helis = [(17.0, 0.32, 0.0, -2.0), (21.0, -0.22, 2.5, 5.0)]
        self.drones = [(rnd.uniform(0, math.tau), rnd.uniform(8.5, 10.5), rnd.uniform(0.6, 1.1), rnd.uniform(-1, 2.5))
                       for _ in range(4)]
        skull = [(c, r) for r, row in enumerate(SKULL) for c, ch in enumerate(row) if ch == "X"]
        self.skull = skull
        sk = set(skull)
        self.skull_halo = {(c + dx, r + dy) for c, r in skull for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - sk
        self.reset(self.last)

    def reset(self, now):
        self.t0 = now
        self.broken = 0
        self.cracks = None
        self.boomed = False
        self.vox = []
        self.flash = 0.0
        self.shock = None
        self.build = 0

    # ------------------------------------------------------------ timeline
    def timeline(self, now):
        t = now - self.t0
        climb = max(0.0, t - INTRO) / LAYER_T
        return t, min(float(NF), climb)

    def camera(self, t, climb, now):
        cam = self.cam
        end = INTRO + NF * LAYER_T
        theta = t * 0.28 + 0.6
        R = 25 + math.sin(t * 0.21) * 2.5
        y = climb * FH + 8.5
        look = climb * FH + 1.0
        if t > end:
            k = ease_out((t - end) / (HOLD + 2.5))
            R += k * 26
            y += k * 6
            look += k * 8
        cam.pos = [-R * math.sin(theta), y, -R * math.cos(theta)]
        cam.yaw = theta
        cam.pitch = math.atan2(y - look, R)
        cam.setup()

    # ------------------------------------------------------------ background
    def sky(self, s, now):
        cam = self.cam
        hz = int(cam.cy - math.tan(cam.pitch) * cam.f)
        hz = max(-1, min(s.h, hz))
        flash = self.flash
        top, mid = (6, 3, 20), (78, 16, 72)
        if flash > 0:
            top, mid = blend(top, WHITE, flash * 0.8), blend(mid, WHITE, flash)
        if hz > 0:
            s.gradient_bg(top, mid, 0, hz + 1)
        if hz < s.h:
            s.gradient_bg(blend((40, 10, 46), WHITE, flash * 0.6), (5, 4, 12), max(0, hz + 1), s.h)
        # stars
        for a, el, col in self.stars:
            ang = (a - cam.yaw + math.pi) % math.tau - math.pi
            if abs(ang) > 1.3:
                continue
            x = cam.cx + math.tan(ang) * cam.f2 * 0.5
            y = cam.cy - math.tan(el - cam.pitch) * cam.f
            if 0 <= y < hz - 1:
                tw = 0.4 + 0.6 * pulse(now, 1.5 + el * 3, a * 9)
                s.put(int(x), int(y), "·" if el < 0.5 else "•", blend(BLACK, col, tw * 0.8))
        return hz

    def searchlights(self, s, now):
        cam = self.cam
        for a0, d, sp, ph in self.lamps:
            bx, bz = math.cos(a0) * d, math.sin(a0) * d
            ang = now * sp + ph
            tilt = 0.25 + 0.2 * math.sin(now * sp * 0.7 + ph)
            dx, dz = math.cos(ang) * tilt, math.sin(ang) * tilt
            top = (bx + dx * 140, 140, bz + dz * 140)
            # beam widens upward: perpendicular offset
            px, pz = -dz / max(0.01, tilt) * 4, dx / max(0.01, tilt) * 4
            P = cam.poly([(bx, 0, bz), (top[0] + px, top[1], top[2] + pz), (top[0] - px, top[1], top[2] - pz)])
            if P:
                fill_alpha(s, P, (170, 190, 255), 0.07)
            q = cam.proj((bx, 0.3, bz))
            if q:
                s.pixel(int(q[0]), int(q[1]), WHITE)

    def city(self, s, now):
        cam = self.cam
        far = 230.0
        # glowing avenues
        for i in range(-2, 3):
            x = i * 30.0 + 11
            col = DIM_PINK if i % 2 else (20, 50, 80)
            line3(s, cam, (x, 0, -far), (x, 0, far), col)
            line3(s, cam, (-far, 0, x), (far, 0, x), col)
        # ctOS rings around the tower
        for k, rr in enumerate((9.0, 14.0)):
            pts = []
            for i in range(25):
                a = i / 24 * math.tau + now * (0.2 if k else -0.15)
                pts.append((math.cos(a) * rr, 0.05, math.sin(a) * rr))
            col = blend(CYAN, BLACK, 0.45 + 0.3 * pulse(now, 2, k))
            for i in range(24):
                if i % 3 != 2:
                    line3(s, cam, pts[i], pts[i + 1], col)
        for x, z, col in self.lights:
            q = cam.proj((x, 0, z))
            if q and 0 <= q[1] < s.ph:
                s.pixel(int(q[0]), int(q[1]), cblend(col, BLACK, min(0.85, q[2] / 260)))
        for x, z, hgt, wd, col in self.blocks:
            q0 = cam.proj((x, 0, z))
            if not q0:
                continue
            q1 = cam.proj((x, hgt, z))
            if not q1:
                continue
            wpx = max(1, int(wd * cam.f2 / q0[2]))
            hp = max(1, int(q0[1] - q1[1]))
            fog = min(0.85, q0[2] / 170)
            prect(s, q0[0] - wpx // 2, q1[1], wpx, hp, cblend((24, 18, 46), BLACK, fog))
            prect(s, q0[0] - wpx // 2, q1[1], wpx, 1, cblend(col, BLACK, fog + 0.1))

    # ------------------------------------------------------------ tower
    def tower(self, s, now, climb):
        cam = self.cam
        cx, cz = cam.pos[0], cam.pos[2]
        cy = cam.pos[1]
        light = cam.yaw + 0.9
        wins, W, PH, PT, PB = self.wins, s.w, s.ph, s.pt, s.pb
        tiers = list(TIERS) + [("crown",)]
        tiers.sort(key=lambda t: -abs(((t[0] + t[1]) / 2 * FH if len(t) == 3 else TOP + 1.2) - cy))
        for tr in tiers:
            if len(tr) == 1:
                if self.build >= NF:
                    self.crown(s, now)
                continue
            fa, fb, r = tr
            fb = min(fb, self.build)
            if fb <= fa:
                continue
            y0, y1 = fa * FH, fb * FH
            V = [(math.cos(a) * r, math.sin(a) * r) for a in OCT]
            for k in range(8):
                m = math.radians(45 * k + 45)
                nx, nz = math.cos(m), math.sin(m)
                if nx * cx + nz * cz <= r * 0.924:
                    continue
                (ax, az), (bx, bz) = V[k], V[(k + 1) % 8]
                lam = 0.3 + 0.7 * max(0.0, math.cos(m - light - math.pi))
                col = blend(NAVY, STEEL, lam)
                P = cam.poly([(ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az)])
                if not P:
                    continue
                fill(s, P, col)
                # Steel spandrels and cross-braced mechanical floors follow the facade.
                rib = blend(col, BLACK, .28)
                for floor in range(fa, fb, 2):
                    yy = floor * FH
                    line3(s, cam, (ax, yy, az), (bx, yy, bz), rib)
                for u in (.25, .5, .75):
                    xx, zz = ax+(bx-ax)*u, az+(bz-az)*u
                    line3(s, cam, (xx, y0, zz), (xx, y1, zz), blend(col, WHITE, .12))
                if fb-fa > 2:
                    yy = min(y1, y0+FH*1.5)
                    line3(s, cam, (ax, y0, az), (bx, yy, bz), blend(STEEL, CYAN, .2))
                    line3(s, cam, (bx, y0, bz), (ax, yy, az), blend(STEEL, CYAN, .2))
                # windows
                la, lb = (ax * 0.97 + bx * 0.03, az * 0.97 + bz * 0.03), (bx * 0.97 + ax * 0.03, bz * 0.97 + az * 0.03)
                A0, A1 = cam.proj((la[0], y0 + 0.55, la[1])), cam.proj((la[0], y1 - 0.65, la[1]))
                B0, B1 = cam.proj((lb[0], y0 + 0.55, lb[1])), cam.proj((lb[0], y1 - 0.65, lb[1]))
                if not (A0 and A1 and B0 and B1):
                    continue
                nfl = max(1, fb - fa - 1)
                for fl in range(fa, fb):
                    u = (fl - fa) / nfl
                    pa = (A0[0] + (A1[0] - A0[0]) * u, A0[1] + (A1[1] - A0[1]) * u, A0[2])
                    if pa[1] < -4 or pa[1] > PH + 4:
                        continue
                    pb = (B0[0] + (B1[0] - B0[0]) * u, B0[1] + (B1[1] - B0[1]) * u)
                    sc = cam.f2 / pa[2]
                    ww = max(1, int(sc * 0.45))
                    wh = max(1, int(sc * 0.4))
                    if fl < self.broken:
                        base = PINK if fl % 3 else PURPLE
                    elif fl == self.broken:
                        base = WHITE if int(now * 8) % 2 else YELLOW
                    else:
                        base = None
                    x0, y0w = pa[0] - ww / 2, pa[1] - wh / 2
                    dxw, dyw = (pb[0] - pa[0]) / 4, (pb[1] - pa[1]) / 4
                    for j in range(4):
                        v = wins[(fl, k, j)]
                        if base is None:
                            if v < 0.35:
                                wc = blend(col, BLACK, .55)
                            else:
                                wc = (255, 214, 120) if v > 0.8 else blend(DIM_CYAN, CYAN, v)
                        else:
                            wc = base if v > 0.15 else DIM_PINK
                        wc = cblend(wc, BLACK, 0.55 - 0.45 * lam)
                        wx = int(x0 + dxw * (j + 0.5))
                        wy = int(y0w + dyw * (j + 0.5))
                        if 0 <= wx and wx + ww <= W and 0 <= wy and wy + wh <= PH:
                            for yy in range(wy, wy + wh):
                                (PB if yy & 1 else PT)[yy >> 1][wx:wx + ww] = [wc] * ww
                # glowing corner edge
                ec = blend(CYAN, BLACK, 0.55) if fa >= self.broken else blend(PINK, BLACK, 0.35)
                line3(s, cam, (ax, y0, az), (ax, y1, az), ec)
                line3(s, cam, (bx, y0, bz), (bx, y1, bz), ec)
            if cy > y1:
                P = cam.poly([(x, y1, z) for x, z in V])
                if P:
                    fill(s, P, (30, 34, 66))
                for k in range(8):
                    line3(s, cam, (V[k][0], y1, V[k][1]), (V[k - 1][0], y1, V[k - 1][1]), blend(CYAN, BLACK, 0.4))

    def crown(self, s, now):
        cam = self.cam
        y0, y1, r0, r1 = TOP, TOP + 2.6, 3.0, 1.6
        cx, cz = cam.pos[0], cam.pos[2]
        hot = self.broken >= NF
        for k in range(8):
            a, b = OCT[k], OCT[(k + 1) % 8]
            m = math.radians(45 * k + 45)
            if math.cos(m) * cx + math.sin(m) * cz <= r0 * 0.9:
                continue
            col = blend((40, 30, 70), PINK if hot else CYAN, 0.25 + 0.25 * pulse(now, 4 if hot else 1.5, k))
            P = cam.poly([(math.cos(a) * r0, y0, math.sin(a) * r0), (math.cos(b) * r0, y0, math.sin(b) * r0),
                          (math.cos(b) * r1, y1, math.sin(b) * r1), (math.cos(a) * r1, y1, math.sin(a) * r1)])
            if P:
                fill(s, P, col)
        # antenna mast with rings
        line3(s, cam, (0, y1, 0), (0, y1 + 11, 0), (150, 160, 190))
        line3(s, cam, (0.25, y1, 0), (0.12, y1 + 7, 0), (90, 100, 130))
        for i in range(3):
            yy = y1 + 2 + i * 2.6
            rr = 0.9 - i * 0.22
            pts = [(math.cos(a) * rr, yy, math.sin(a) * rr) for a in HEX]
            for j in range(6):
                line3(s, cam, pts[j], pts[j - 1], blend(GREY, CYAN, 0.4))
        q = cam.proj((0, y1 + 11.3, 0))
        if q and int(now * 2.5) % 2:
            col = PINK if hot else (255, 40, 40)
            s.pixel_circle(q[0], q[1], max(1.2, 0.5 * cam.f2 / q[2]), blend(col, WHITE, 0.3))
            s.put(int(q[0]), int(q[1] / 2), "●", WHITE)

    # ------------------------------------------------------------ firewall shields
    def shield_geo(self, L, now):
        r = tier_r(L)
        rin, rout = r + 0.35, r + 2.8
        y = L * FH + 0.15
        rot = now * 0.25 + L * 0.37
        return y, rin, rout, rot

    def shields(self, s, now, climb, front):
        cam = self.cam
        for L in range(self.broken, min(NF, self.broken + 3)):
            dist = L - self.broken
            vis = 1.0 - dist / 3.2
            cur = L == self.broken
            y, rin, rout, rot = self.shield_geo(L, now)
            ax_v = cam.view((0, y, 0))
            col = CYAN
            if cur:
                atk = climb - int(climb)
                col = blend(CYAN, PINK, atk) if int(now * 14) % 3 else WHITE
            for i in range(6):
                a, b = HEX[i] + rot, HEX[(i + 1) % 6] + rot
                ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
                mid = cam.view(((ca + cb) * rout / 2, y, (sa + sb) * rout / 2))
                if (mid[2] < ax_v[2]) != front:
                    continue
                pa_o, pb_o = (ca * rout, y, sa * rout), (cb * rout, y, sb * rout)
                pa_i, pb_i = (ca * rin, y, sa * rin), (cb * rin, y, sb * rin)
                P = cam.poly([pa_i, pb_i, pb_o, pa_o])
                if P:
                    fill_alpha(s, P, col, (0.16 if front else 0.12) * vis * vis + (0.1 if cur else 0))
                # rim band
                up = 0.45
                R = cam.poly([pa_o, pb_o, (pb_o[0], y + up, pb_o[2]), (pa_o[0], y + up, pa_o[2])])
                if R:
                    fill_alpha(s, R, col, 0.28 * vis * vis + (0.12 if cur else 0))
                ec = blend(BLACK, col, 0.35 + 0.65 * vis)
                line3(s, cam, (pa_o[0], y + up, pa_o[2]), (pb_o[0], y + up, pb_o[2]), ec)
                if cur:
                    line3(s, cam, pa_o, pb_o, blend(BLACK, ec, 0.7))
                # energy pulse running around the ring
                ph = (now * 1.6 + L * 0.3) % 6
                if int(ph) == i:
                    t = ph - int(ph)
                    q = cam.proj((pa_o[0] + (pb_o[0] - pa_o[0]) * t, y + up / 2, pa_o[2] + (pb_o[2] - pa_o[2]) * t))
                    if q and front:
                        s.put(int(q[0]), int(q[1] / 2), "◆", blend(col, WHITE, 0.5))

    def attack(self, s, now, climb, glitch):
        """Lasers + cracks on the current shield, shatter when the layer falls."""
        cam = self.cam
        L = self.broken
        if L >= NF:
            return
        atk = climb - L
        y, rin, rout, rot = self.shield_geo(L, now)
        face = cam.yaw + math.pi        # world angle pointing from tower to camera (xz)
        fa = math.atan2(-math.cos(cam.yaw), -math.sin(cam.yaw))
        if self.cracks is None or self.cracks[0] != L:
            rnd = random.Random(L * 31 + int(self.t0))
            hit = fa + rnd.uniform(-0.5, 0.5)
            cr = []
            for _ in range(5):
                a, rr = hit, rout - 0.2
                pts = [(a, rr)]
                da = rnd.uniform(-0.18, 0.18)
                for _ in range(6):
                    a += da + rnd.uniform(-0.08, 0.08)
                    rr -= rnd.uniform(0.15, 0.45)
                    if rr < rin + 0.1:
                        break
                    pts.append((a, rr))
                cr.append(pts)
            self.cracks = (L, hit, cr)
        _, hit, cr = self.cracks
        hp = cam.proj((math.cos(hit) * rout, y + 0.25, math.sin(hit) * rout))
        if atk < 0.7 and hp:
            # lasers from the DedSec drones
            for i, (a0, rad, sp, dy) in enumerate(self.drones):
                if int(now * 10 + i * 3) % 4 == 0:
                    continue
                dp = self.drone_pos(i, now)
                q = cam.proj(dp)
                if q:
                    lc = PINK if i % 2 else CYAN
                    pline(s, q[0], q[1], hp[0], hp[1], blend(lc, WHITE, 0.3))
                    pline(s, q[0] + 1, q[1], hp[0], hp[1], lc)
            if random.random() < 0.7:
                self.parts.add(hp[0], hp[1] / 2, random.uniform(-14, 14), random.uniform(-6, 2), 0.4, "*+·", YELLOW, 10)
            n = min(1.0, atk / 0.6)
            for pts in cr:
                k = max(1, int(len(pts) * n))
                for j in range(k - 1):
                    (a1, r1), (a2, r2) = pts[j], pts[j + 1]
                    q1 = cam.proj((math.cos(a1) * r1, y, math.sin(a1) * r1))
                    q2 = cam.proj((math.cos(a2) * r2, y, math.sin(a2) * r2))
                    if q1 and q2:
                        pline(s, q1[0], q1[1], q2[0], q2[1], WHITE if (j + int(now * 12)) % 3 else PINK)
            s.put(int(hp[0]), int(hp[1] / 2), "*", WHITE)
        if atk >= 0.7:
            self.shatter(L, now)

    def shatter(self, L, now):
        cam = self.cam
        y, rin, rout, rot = self.shield_geo(L, now)
        ax_v = cam.view((0, y, 0))
        for i in range(70):
            a = random.uniform(0, math.tau)
            rr = random.uniform(rin, rout)
            p = (math.cos(a) * rr, y + random.uniform(0, 0.4), math.sin(a) * rr)
            v = cam.view(p)
            if v[2] > ax_v[2] + 1.5:
                continue
            q = cam.proj(p)
            if not q:
                continue
            ox = q[0] - cam.cx
            self.parts.add(q[0], q[1] / 2, ox * 0.3 + random.uniform(-14, 14), random.uniform(-9, 3), random.uniform(0.6, 1.4),
                           random.choice(("▓▒░", "◆•·", "/·", "\\·", "▒░")), random.choice((CYAN, CYAN, WHITE, PINK)), 16)
        for _ in range(26):
            a = random.uniform(0, math.tau)
            rr = random.uniform(rin, rout)
            sp = random.uniform(2, 6)
            self.vox.append([math.cos(a) * rr, y, math.sin(a) * rr, math.cos(a) * sp, random.uniform(-1, 3),
                             math.sin(a) * sp, 0.0, random.uniform(1.0, 2.0), random.choice((CYAN, WHITE, (120, 230, 255)))])
        self.broken = L + 1
        self.cracks = None
        if L % 5 == 4 or random.random() < 0.25:
            self.glitch.trigger(now, 0.18)

    # ------------------------------------------------------------ actors
    def drone_pos(self, i, now):
        a0, rad, sp, dy = self.drones[i]
        a = a0 + now * sp
        return (math.cos(a) * rad, self.cam.pos[1] - 5.2 + dy + math.sin(now * 2 + i) * 0.4, math.sin(a) * rad)

    def hidden(self, p, q):
        """True if a text sprite at world point p sits behind the tower silhouette."""
        cam = self.cam
        if self.boomed or p[1] > TOP + 3:
            return False
        v = cam.view(p)
        ax = cam.view((0, p[1], 0))
        if v[2] <= ax[2] or ax[2] < NEAR:
            return False
        ap = cam.pp(ax)
        half = (tier_r(p[1] / FH) + 0.3) * cam.f2 / ax[2]
        return abs(q[0] - ap[0]) < half

    def actors(self, s, now):
        cam = self.cam
        blink = int(now * 3) % 2
        for i, (rad, sp, ph, dy) in enumerate(self.helis):
            a = ph + now * sp
            p = (math.cos(a) * rad, cam.pos[1] + dy + math.sin(now * 0.4 + i) * 1.5, math.sin(a) * rad)
            q = cam.proj(p)
            if not q or self.hidden(p, q):
                continue
            x, y = int(q[0]), int(q[1] / 2)
            near = q[2] < 22
            rot = "═══╤═══" if int(now * 12) % 2 else "───╤───"
            if near:
                s.text(x - 3, y - 1, rot, GREY)
                s.text(x - 3, y, "◄▐██▌═", (60, 64, 90))
            else:
                s.text(x - 2, y - 1, rot[1:-1], GREY)
                s.text(x - 1, y, "▐█▌", (60, 64, 90))
            s.put(x - 2 if near else x - 1, y + (0 if near else 0), "•", (255, 40, 40) if blink else BLACK)
            s.put(x + 2, y, "•", GREEN_L if not blink else BLACK)
            # spotlight on the tower
            if not self.boomed and i == 0:
                ta = cam.proj((0, p[1] - 3, 0))
                if ta:
                    sw = max(2.0, 1.2 * cam.f2 / ta[2])
                    fill_alpha(s, [(q[0], q[1] + 2), (ta[0] - sw, ta[1]), (ta[0] + sw, ta[1])], (220, 230, 255), 0.13)
        for i in range(len(self.drones)):
            p = self.drone_pos(i, now)
            q = cam.proj(p)
            if not q or self.hidden(p, q):
                continue
            x, y = int(q[0]), int(q[1] / 2)
            s.text(x - 1, y, "╶◆╴", PINK if (int(now * 6) + i) % 2 else blend(PINK, WHITE, 0.5))

    # ------------------------------------------------------------ boom
    def explode(self, now):
        self.boomed = True
        self.flash = 1.0
        self.shock = now
        self.glitch.trigger(now, 0.5)
        rnd = random
        n = 900 if self.w * self.h > 6000 else 550
        for _ in range(n):
            y = rnd.uniform(0, TOP + 2.5)
            r = tier_r(min(NF - 1, int(y / FH))) if y < TOP else 2.4
            a = rnd.uniform(0, math.tau)
            sp = rnd.uniform(3, 16) * (0.5 + y / TOP)
            col = rnd.choice((PINK, PINK, CYAN, STEEL, (90, 110, 170), YELLOW, WHITE, PURPLE))
            self.vox.append([math.cos(a) * r, y, math.sin(a) * r, math.cos(a) * sp, rnd.uniform(-2, 12),
                             math.sin(a) * sp, 0.0, rnd.uniform(2.5, 6.0), col])
        q = self.cam.proj((0, TOP, 0))
        if q:
            self.parts.burst(q[0], q[1] / 2, 140, colors=(PINK, YELLOW, WHITE, CYAN), speed=34, chars="█▓▒░*+·")

    def draw_vox(self, s, dt):
        cam = self.cam
        alive = []
        for v in self.vox:
            v[6] += dt
            if v[6] > v[7]:
                continue
            v[4] -= 9.0 * dt
            v[0] += v[3] * dt
            v[1] += v[4] * dt
            v[2] += v[5] * dt
            if v[1] < 0:
                v[1], v[4] = 0, -v[4] * 0.3
            alive.append(v)
            q = cam.proj(v)
            if not q:
                continue
            sz = max(1, min(4, int(cam.f2 * 0.35 / q[2] + 0.5)))
            t = v[6] / v[7]
            prect(s, q[0], q[1], sz, sz, blend(v[8], BLACK, t * t))
        self.vox = alive

    def shockwave(self, s, now):
        if self.shock is None:
            return
        age = now - self.shock
        if age > 3:
            return
        cam = self.cam
        for k, (yy, sp) in enumerate(((TOP * 0.7, 42), (0.2, 30))):
            rr = 3 + ease_out(age / 3) * sp * 3
            col = blend(blend(WHITE, PINK, age / 1.5), BLACK, age / 3)
            prev = None
            for i in range(73):
                a = i / 72 * math.tau
                p = (math.cos(a) * rr, yy, math.sin(a) * rr)
                if prev:
                    line3(s, cam, prev, p, col)
                prev = p

    def draw_skull(self, s, now, k):
        """Giant DedSec skull in the night sky, pixel art."""
        w, ph = s.w, s.ph
        sc = max(1, int(min(ph * 0.45 / 15, w * 0.4 / 22)))
        sw, sh = 22 * sc, 15 * sc
        x0 = (w - sw) // 2
        y0 = int(ph * 0.08) + int(math.sin(now * 1.3) * 2)
        glitch = random.random() < 0.08
        fade = ease_out(k)
        halo = blend(BLACK, DIM_PINK, fade * (0.6 + 0.4 * pulse(now, 3)))
        for c, r in self.skull_halo:
            prect(s, x0 + c * sc, y0 + r * sc, sc, sc, halo)
        for c, r in self.skull:
            if fade < 1 and random.random() > fade:
                continue
            off = random.randint(-3, 3) * sc if glitch and r % 4 == int(now * 9) % 4 else 0
            col = blend(WHITE, PINK, 0.25 + 0.35 * pulse(now, 2.5, r * 0.3))
            if r >= 12:
                col = blend(col, CYAN, 0.3)
            col = blend(BLACK, col, fade)
            prect(s, x0 + c * sc + off, y0 + r * sc, sc, sc, col)
            if sc > 2:
                prect(s, x0 + c * sc + off, y0 + r * sc + sc - 1, sc, 1, blend(col, BLACK, 0.35))
        if fade > 0.5:
            msg = "ctOS CORE: OWNED BY DEDSEC"
            yy = (y0 + sh) // 2 + 1
            if yy < s.h - 4:
                s.center(yy, msg, PINK if int(now * 3) % 2 else WHITE)

    # ------------------------------------------------------------ HUD
    def hud(self, s, now, climb, t):
        w, h = self.w, self.h
        alt = self.cam.pos[1] * 4.1
        s.text(2, 0, "▌BLUME ctOS CORE", CYAN)
        s.text(2, 1, "▌ALT %6.1fm  HDG %03d°" % (alt, math.degrees(self.cam.yaw) % 360), GREY)
        lay = "FIREWALL LAYER %02d/%02d" % (min(NF, self.broken), NF)
        s.text(w - len(lay) - 2, 0, lay, PINK if self.broken < NF else YELLOW)
        bw = min(NF, max(10, w // 5))
        filled = int(bw * self.broken / NF)
        bar = "▰" * filled + "▱" * (bw - filled)
        s.text(w - bw - 2, 1, bar[:filled], PINK)
        s.text(w - bw - 2 + filled, 1, bar[filled:], DIM_PINK)
        if w >= 110:
            st = "DEDSEC UPLINK ● %d DRONES" % len(self.drones)
            s.center(0, st, blend(PINK, WHITE, pulse(now, 4) * 0.5))
        # altitude ladder on the left
        top, bot = 3, h - 4
        if bot - top > 6:
            prev = None
            for yy in range(top, bot + 1):
                fl = NF - 1 - int((yy - top) / (bot - top) * (NF - 1) + 0.5)
                ch = "┤" if fl % 5 == 0 and fl != prev else "│"
                col = PINK if fl < self.broken else DIM_CYAN
                s.put(1, yy, ch, col)
                if fl % 10 == 0 and fl and fl != prev:
                    s.text(3, yy, "%02d" % fl, GREY)
                prev = fl
            my = bot - int(min(NF, climb) / NF * (bot - top))
            s.text(2, my, "◄", YELLOW)
        # status line
        end = INTRO + NF * LAYER_T
        if t < INTRO:
            msg = "> CONNECTING TO BLUME ctOS CORE " + SPIN[int(now * 12) % 10]
            col = CYAN
        elif self.broken < NF:
            pc = int((climb - int(climb)) / 0.7 * 100)
            msg = "> BREACHING LAYER %02d %s %3d%%" % (self.broken + 1, SPIN[int(now * 12) % 10], min(100, pc))
            col = YELLOW
        elif not self.boomed:
            msg = "> ALL FIREWALLS DOWN // CORE EXPOSED // DETONATING LOGIC BOMB"
            col = PINK if int(now * 6) % 2 else WHITE
        else:
            msg = "> BLUME ctOS CORE OFFLINE // SF GRID IS OURS"
            col = PINK
        s.text(3, h - 2, msg[:w - 6], col)
        if w >= 120:
            tag = "DEDSEC // ctOS TOWER RAID"
            s.text(w - len(tag) - 2, h - 2, tag, GREY)

    # ------------------------------------------------------------ frame
    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "blackout", "ctOS / POWER DOWN", CYAN)
        if 0.1 < t < 0.85:
            # The final firewall contracts around the tower before power is cut.
            q = self.cam.proj((0, TOP * 0.65, 0))
            cx, py = (q[0], q[1]) if q else (s.w / 2, s.ph / 2)
            radius = (1 - t) * min(s.w / 5, s.ph / 6)
            for i in range(48):
                a = i * math.tau / 48
                s.pixel(int(cx + math.cos(a) * radius), int(py + math.sin(a) * radius * 0.38),
                        blend(CYAN, BLACK, t))

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        t, climb = self.timeline(now)
        end = INTRO + NF * LAYER_T
        if t > end + HOLD + BOOM:
            self.reset(now)
            self.glitch.trigger(now, 0.4)
            t, climb = self.timeline(now)
        if t > end + HOLD and not self.boomed:
            self.explode(now)
        glitch = self.glitch.active(now)
        beat = DATA.beat
        if beat > 0.8 and random.random() < 0.1:
            self.glitch.trigger(now, 0.08)
        self.flash = max(0.0, self.flash - dt * 1.6)

        self.camera(t, climb, now)
        self.sky(s, now)
        self.searchlights(s, now)
        self.city(s, now)
        if self.boomed:
            k = min(1.0, (t - end - HOLD - 1.0) / 2.0)
            if k > 0:
                self.draw_skull(s, now, k)
        else:
            if t >= INTRO:
                self.shields(s, now, climb, front=False)
            self.build = NF if t >= INTRO else max(1, int(ease_out(t / INTRO) * NF))
            self.tower(s, now, climb)
            if self.build < NF:
                q = self.cam.proj((0, self.build * FH, 0))
                if q:
                    for _ in range(3):
                        self.parts.add(q[0] + random.uniform(-14, 14), q[1] / 2, random.uniform(-4, 4), random.uniform(-5, -1),
                                       0.6, "▪·", random.choice((CYAN, WHITE)))
            if t >= INTRO:
                self.shields(s, now, climb, front=True)
                self.attack(s, now, climb, glitch)
        self.shockwave(s, now)
        self.draw_vox(s, dt)
        self.actors(s, now)
        self.parts.step(s, dt)
        text_over_pixels(s)
        if self.flash > 0.05:
            tint_rows(s, 0, s.h, WHITE, self.flash * 0.8)
        self.hud(s, now, climb, t)
        postfx(s, now, glitch)


GREEN_L = (60, 255, 90)

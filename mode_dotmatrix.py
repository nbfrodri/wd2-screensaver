"""The wallpaper's halftone hands, suspended in a quiet monochrome volume.

The bundled centroids are extracted from the reference wallpaper once, offline.
No wallpaper, filesystem activity, notifications or desktop data are read live.
Braille supplies eight independent round dots per terminal cell; grey levels
stand in for halftone dot size and depth.

One particle per wallpaper dot. A 44 second loop:
  0-9    hands as a halftone relief under a slow 3D camera; they reach, touch,
         and a dotted ripple runs out from the fingertips across the floor.
  9-16   the spark between the fingertips becomes a stream: the hands pour
         through it, fingertips first, and build DEDSEC letter by letter
         behind a bright scanning column.
  16-30  DEDSEC holds; a halftone light wave rolls through it, two dotted
         orbit rings turn around it in depth, one brief scan glitch.
  30-35  the word folds into a rotating halftone globe.
  35-44  the globe unfolds into the hands, arms first, fingertips last.
"""
import json
import math
from pathlib import Path
import numpy as np

NAME = 'DOTMATRIX'
BLACK = (0, 0, 0)
_PALETTE = [(i, i, i) for i in range(256)]
_BITLUT = np.array([[1, 8], [2, 16], [4, 32], [64, 128]], dtype=np.int64)
# Raster footprints in braille sub-dots: single, vertical pair, 2x2, round 3x3.
_FOOT = (((0, 0),),
         ((0, 0), (0, 1)),
         ((0, 0), (1, 0), (0, 1), (1, 1)),
         ((0, -1), (-1, 0), (0, 0), (1, 0), (0, 1), (-1, 1), (1, 1), (0, 2)))
_FOOT_DX = [np.array([o[0] for o in f]) for f in _FOOT]
_FOOT_DY = [np.array([o[1] for o in f]) for f in _FOOT]
_FONT = {
    'D': ('111111100', '111111110', '110000111', '110000011', '110000011', '110000011', '110000011',
          '110000011', '110000011', '110000011', '110000111', '111111110', '111111100'),
    'E': ('111111111', '111111111', '110000000', '110000000', '110000000', '111111100', '111111100',
          '110000000', '110000000', '110000000', '110000000', '111111111', '111111111'),
    'S': ('001111111', '011111111', '111000000', '110000000', '110000000', '011111100', '001111110',
          '000000011', '000000011', '000000011', '000000111', '111111110', '111111100'),
    'C': ('001111111', '011111111', '111000000', '110000000', '110000000', '110000000', '110000000',
          '110000000', '110000000', '110000000', '111000000', '011111111', '001111111'),
}

LOOP = 44.0
TOUCH = 3.2            # first touch, ripple
REL0, REL1, FLIGHT = 9.0, 13.2, 2.6
GLITCH = 23.4
DISS = 29.5
REFORM = 36.0


def _smooth(a):
    a = np.clip(a, 0, 1)
    return a * a * (3 - 2 * a)


def _sm(a):
    a = max(0.0, min(1.0, a))
    return a * a * (3 - 2 * a)


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.W, self.H = w * 2, h * 4
        asset = json.loads((Path(__file__).parent / 'assets' / 'dot_hands.json').read_text())
        aspect = asset.get('aspect', 1.547)
        d = np.array(asset['dots'], dtype=float)
        n = self.n = len(d)
        self.start = None
        self.last = None
        rng = np.random.default_rng(7)
        # World units: wallpaper width == 1, origin at the image centre.
        self.S = min(self.W * .98, self.H * 3.05)
        hx = d[:, 0] - .5
        hy = (d[:, 1] - .5) / aspect
        size = (d[:, 2] - .848) / .152
        left = d[:, 0] < .475
        # Relief: each forearm is a soft cylinder (per-column bulge) and the
        # arms recede towards the screen edges, fingertips nearest to us.
        bulge = np.zeros(n)
        for side in (left, ~left):
            xs, ys = hx[side], hy[side]
            bins = np.clip(((xs - xs.min()) / (np.ptp(xs) + 1e-9) * 36).astype(int), 0, 35)
            lo = np.full(36, 9.0); hi = np.full(36, -9.0)
            np.minimum.at(lo, bins, ys); np.maximum.at(hi, bins, ys)
            mid, half = (lo + hi) / 2, np.maximum(.01, (hi - lo) / 2)
            bulge[side] = np.sqrt(np.clip(1 - ((ys - mid[bins]) / half[bins]) ** 2, 0, 1))
        hz = .2 * ((d[:, 0] - .475) * 2) ** 2 - .05 * bulge - .012 * size
        self.hand = np.stack((hx, hy, hz))
        self.hside = np.where(left, 1.0, -1.0)
        # The wallpaper halftone encodes the anatomy in dot size. Keep that
        # relief, with a white rim at fingers and wrist silhouettes.
        rim = bulge < .36
        self.hsize = np.where(size > .65, 2, np.where((size > .30) | rim, 1, 0))
        self.hlum = np.where(rim, 255, 156 + 99 * np.power(size, 1.15) * (.78 + .22 * bulge))
        self.phase = d[:, 0] * 23 + d[:, 1] * 9
        self.build_word()
        # One particle per word dot plus the orbit rings; wallpaper dots are
        # shared when the word needs more (duplicates coincide in the hands).
        m = len(self.wx)
        circ = self.S * .46 * math.tau * .62
        self.ring_n = int(circ / 2.4) * 2
        P = max(n, m + self.ring_n)
        src = np.concatenate((np.arange(n), rng.integers(0, n, P - n))) if P > n else np.arange(n)
        self.n = n = P
        self.hand = self.hand[:, src]
        self.hside, self.hsize = self.hside[src], self.hsize[src]
        self.hlum, self.phase = self.hlum[src], self.phase[src]
        hx, hy = self.hand[0], self.hand[1]
        self.touch = np.array([-.025, .012, -.03])
        dist = np.hypot(hx - self.touch[0], (hy - self.touch[1]) * 1.6)
        drank = np.argsort(np.argsort(dist + rng.random(n) * .02)) / max(1, n - 1)
        # Release fingertips first; arms re-form first (fingertips last).
        self.rel = REL0 + (REL1 - REL0) * drank
        self.ref = REFORM + 2.6 * (1 - drank) + rng.random(n) * .25
        self.jit = rng.normal(0, 1, (2, n))
        # Each released particle takes the next word dot (left to right); the
        # rest become orbit rings; any extra particles double up on word dots.
        order = np.argsort(self.rel)
        self.target = np.empty(n, dtype=int)
        self.target[order] = np.arange(n)
        self.arrive = self.rel + FLIGHT
        self.diss = DISS + 1.3 * rng.random(n) + .9 * self.target / max(1, n)
        # The word folds into a halftone globe between the hands. Fibonacci
        # points, matched by x so letters wrap around it coherently.
        k = np.arange(n) + .5
        lat = np.arccos(1 - 2 * k / n)
        lon = k * math.pi * (3 - math.sqrt(5))
        sph = np.stack((np.sin(lat) * np.cos(lon), np.cos(lat), np.sin(lat) * np.sin(lon)))
        sph = sph[:, np.argsort(sph[0] + rng.random(n) * .2)]
        self.sph = np.empty_like(sph)
        self.sph[:, np.argsort(self.target)] = sph
        self.globe_r = min(.145, .4 * self.H / self.S)
        # Ambient motes, independent of the particles.
        self.motes = np.stack((rng.uniform(-1.4, 1.4, 150), rng.uniform(-.32, .3, 150),
                               rng.uniform(-.9, 5.0, 150)))
        self.mote_ph = rng.uniform(0, math.tau, 150)
        # Floor lattice (world). Rows recede in z; columns subsample with depth.
        fx = np.arange(-2.4, 2.4001, .03)
        self.fdz = .14
        fz = np.arange(0, 60) * self.fdz - 1.1
        gx, gz = np.meshgrid(fx, fz)
        self.fl_x, self.fl_z = gx.ravel(), gz.ravel()
        self.fl_ix = np.tile(np.arange(len(fx)), len(fz))
        self.fl_row = np.repeat(np.arange(len(fz)), len(fx))

    # ------------------------------------------------------------------ word
    def build_word(self):
        """DEDSEC as a fine dot-matrix lattice (every other braille sub-dot)."""
        W, H = self.W, self.H
        unit = min(W * .84 / 65, H * .42 / 13)
        left = W / 2 - unit * 65 / 2 - unit * .7
        top = H / 2 - unit * 13 / 2
        step = 2 if unit < 6.5 else 3
        pts = []
        for py in range(int(math.ceil(top / 2) * 2), int(top + unit * 13) + 1, step):
            v = (py + .5 - top) / unit
            row = int(v)
            if not 0 <= row < 13 or v < 0:
                continue
            rake = (12.5 - v) * .11
            for px in range(int(math.ceil(left / 2) * 2), int(left + unit * 67) + 1, step):
                u = (px + .5 - left) / unit - rake
                letter = int(u // 11)
                col = int(u - letter * 11)
                if 0 <= letter < 6 and 0 <= col < 9 and _FONT['DEDSEC'[letter]][row][col] == '1':
                    pts.append((px, py, v / 13))
        pts.sort(key=lambda p: (p[0], p[1]))
        pts = np.array(pts, dtype=float)
        self.wstep = step
        self.wx, self.wy, self.wv = pts[:, 0], pts[:, 1], pts[:, 2]
        self.wleft, self.wright = self.wx.min(), self.wx.max()
        self.wtop, self.wbot = self.wy.min(), self.wy.max()

    # ---------------------------------------------------------------- camera
    def camera(self, t):
        yaw = .12 * math.sin(t * .113) + .03 * math.sin(t * .31)
        pitch = .012 + .008 * math.sin(t * .087)
        dist = 2.3 + .12 * math.sin(t * .071)
        return math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), dist, yaw

    def project(self, cam, x, y, z):
        cy_, sy_, cp, sp, F, _ = cam
        x1 = x * cy_ - z * sy_
        z1 = x * sy_ + z * cy_
        y2 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp
        p = F / np.maximum(.15, F + z2)
        return self.W / 2 + self.S * x1 * p, self.H / 2 + self.S * y2 * p, z2, p

    # ------------------------------------------------------------- elements
    def hands(self, t, cyc, cam):
        x, y, z = self.hand
        # The hands reach for each other before the touch and before the pour.
        reach = .013 * math.exp(-((cyc - TOUCH) / 1.4) ** 2) + .009 * math.exp(-((cyc - 8.6) / 1.2) ** 2)
        reach += .004 * math.sin(t * .4)
        x = x + self.hside * reach
        y = y + .004 * np.sin(t * .5 + self.hside * 1.3) + .0012 * np.sin(self.phase - t * .9)
        z = z + .006 * np.sin(self.phase * .3 - t * .6)
        sx, sy, zz, p = self.project(cam, x, y, z)
        lum = self.hlum * np.clip(1.08 - zz * .9, .55, 1.15)
        lum = lum * (.97 + .03 * np.sin(self.phase * .5 - t * .7))
        # Before the pour, a bright halftone pulse runs down both arms into
        # the fingertips, where it ignites the spark.
        if 5.2 < cyc < 8.9:
            front = .62 * (1 - (cyc - 5.2) / 3.4)
            ax = np.abs(x - self.touch[0])
            lum = lum + 95 * np.exp(-((ax - front) / .035) ** 2) * min(1.0, (8.9 - cyc) * 3)
        r = self.ripple_radius(cyc)
        if r is not None:
            rad, fade = r
            dd = np.hypot(x - self.touch[0], y - self.touch[1])
            band = np.exp(-((dd - rad) / .025) ** 2) * fade
            lum = lum + 120 * band
            sy = sy - 2.0 * band
        return sx, sy, lum

    def ripple_radius(self, cyc):
        for t0 in (TOUCH, 8.6):
            if t0 <= cyc < t0 + 4.5:
                a = (cyc - t0) / 4.5
                return .9 * a ** .75, (1 - a) ** 1.5
        return None

    def word(self, t, cyc):
        tgt = self.target
        m = len(self.wx)
        ri = tgt - m
        isr = (ri >= 0) & (ri < self.ring_n)
        isw = ~isr
        # Any particles beyond the rings double up on word dots (invisible).
        wi = np.where(tgt < m, tgt, (tgt - m - self.ring_n) % m)
        wi = np.where(isr, 0, wi)
        x = self.wx[wi].copy()
        y = self.wy[wi].copy()
        v = self.wv[wi]
        # Halftone light: a diagonal band rolls slowly through the letters.
        band = np.sin((x / self.W) * 7.5 - v * 2.2 - t * .55)
        lum = 242 + 10 * band + 8 * (.5 - v)
        # Fixed footprints keep counters and stems intact while light moves.
        size = np.full(len(x), 2, dtype=int)
        # Glitch: a short horizontal slice shift and a scanning line.
        if GLITCH <= cyc < GLITCH + .9:
            a = (cyc - GLITCH) / .9
            for k, (y0, dx) in enumerate(((.22, 3), (.62, -4))):
                yy = self.wtop + (self.wbot - self.wtop) * ((y0 + a * .35 * (k - 1)) % 1)
                sl = np.abs(y - yy) < 2 + self.wstep
                x[sl] += dx * math.sin(a * math.pi) * (1 + self.W / 400)
                lum[sl] *= .78
        return x, y, lum, size, isw, isr, np.maximum(ri, 0)

    def rings(self, t, cam, ri, weight):
        k = ri % 2
        nper = max(1, self.ring_n // 2)
        a = (ri // 2) / nper * math.tau + t * np.where(k == 0, .16, -.11)
        R = np.where(k == 0, .4, .44)
        tilt = np.where(k == 0, .24, .3)
        roll = np.where(k == 0, .06, -.09)
        x0 = R * np.cos(a)
        y0 = R * np.sin(a) * tilt
        z0 = R * np.sin(a) * .55
        x = x0 * np.cos(roll) - y0 * np.sin(roll)
        y = x0 * np.sin(roll) + y0 * np.cos(roll)
        sx, sy, zz, p = self.project(cam, x, y, z0)
        dash = .5 + .5 * np.cos(a * 11 + k * 2)
        lum = (40 + 110 * dash) * np.where(z0 < 0, 1.0, .55)
        tracer = np.cos(a - t * 1.3 - k * math.pi)
        lum = lum + 90 * np.clip(tracer, 0, 1) ** 24
        return sx, sy, lum * weight, z0 < 0

    def globe(self, t, cam, cyc):
        """Rotating halftone sphere: lit front dots bright, far side faint."""
        x, y, z = self.sph
        a = t * .5
        c, s = math.cos(a), math.sin(a)
        x, z = x * c - z * s, x * s + z * c
        tilt = .38
        ct, st = math.cos(tilt), math.sin(tilt)
        y, z = y * ct - z * st, y * st + z * ct
        lit = np.clip(-.45 * x - .55 * y - .7 * z, 0, 1)
        breathe = 1 + .04 * math.sin(cyc * 2.2)
        r = self.globe_r * breathe
        sx, sy, z2, p = self.project(cam, self.touch[0] + r * x, self.touch[1] + r * y, .05 + r * z)
        front = z < .08
        lum = np.where(front, 55 + 200 * lit ** 1.3, 26 + 14 * (y < 0))
        # One bright meridian sweeps around, like a scanner over a globe.
        lum = lum + np.where(front, 70, 15) * np.exp(-((np.sin(np.arctan2(x, -z) - math.sin(t * .8) * 1.2)) / .06) ** 2)
        return sx, sy, lum, front

    # ----------------------------------------------------------- particles
    def particles(self, t):
        cyc = t % LOOP
        cam = self.camera(t)
        n = self.n
        size = self.hsize.copy()
        fg = np.ones(n, dtype=bool)
        if cyc < REL0 or cyc >= REFORM + 5.85:
            hx, hy, hl = self.hands(t, cyc, cam)
            return cam, hx, hy, hl, size, fg, cyc
        hx, hy, hl = self.hands(t, cyc, cam)
        wx, wy, wl, ws, isw, isr, ri = self.word(t, cyc)
        ring_w = _sm((cyc - (REL1 + FLIGHT - .6)) / 1.5) * (1 - _sm((cyc - DISS) / 1.6))
        rx, ry, rl, rfront = self.rings(t, cam, ri, max(ring_w, .35))
        dx, dy, dl, dfront = self.globe(t, cam, cyc)
        # Targets for the "formed" state.
        tx = np.where(isw, wx, rx)
        ty = np.where(isw, wy, ry)
        tl = np.where(isw, wl, rl)
        ts = np.where(isw, ws, 0)
        fg = np.where(isr, rfront, isw)
        if cyc < DISS:
            s = np.clip((cyc - self.rel) / FLIGHT, 0, 1)
            cx = self.W / 2 + self.S * self.touch[0]
            cy = self.H / 2 + self.S * self.touch[1]
            # First half: flow along the dot rows into the fingertips; second
            # half: burst from the spark and fan out to the letters.
            u = np.clip(s / .45, 0, 1)
            v = _smooth((s - .45) / .55)
            ax = hx + (cx - hx) * u ** 1.6
            ay = hy + (cy - hy) * u ** 3.5
            jx = self.jit[0] * 1.5 * (1 - v)
            jy = (self.hside * 4 + self.jit[1] * .6) * np.sin(v * math.pi)
            x = np.where(s < .45, ax, cx + (tx - cx) * (1 - (1 - v) ** 2) + jx)
            y = np.where(s < .45, ay, cy + (ty - cy) * v + jy)
            fly = (s > 0) & (s < 1)
            pop = np.where(cyc >= self.arrive, np.exp(-(cyc - self.arrive) / .45), 0)
            flum = np.where(s < .45, hl + (235 - hl) * u ** 2, 235 - 40 * v)
            lum = np.where(s <= 0, hl, np.where(fly, flum, tl + 60 * pop))
            size = np.where(s <= 0, size, np.where(fly, 0, np.where(pop > .4, np.minimum(ts + 1, 3), ts)))
            fg = np.where(s < 1, True, fg)
            return cam, x, y, lum, size, fg, cyc
        if cyc < REFORM:
            s = _smooth((cyc - self.diss) / 2.0)
            sway = np.sin(s * math.pi)
            x = tx + (dx - tx) * s + sway * self.jit[0] * 2
            y = ty + (dy - ty) * s + sway * (self.jit[1] * 1.5 - 4)
            lum = tl + (dl - tl) * s + 25 * sway
            size = np.where(s < .3, ts, 0)
            fg = np.where(s > .5, dfront, fg)
            return cam, x, y, lum, size, fg, cyc
        s = _smooth((cyc - self.ref) / 3.0)
        sway = np.sin(s * math.pi)
        x = dx + (hx - dx) * s + sway * self.hside * 5
        y = dy + (hy - dy) * s + sway * self.jit[0] * 1.0
        lum = dl + (hl - dl) * s + 40 * sway
        size = np.where(s > .8, size, 0)
        fg = np.where(s < .3, dfront, True)
        return cam, x, y, lum, size, fg, cyc

    # ---------------------------------------------------------- background
    def background(self, t, cyc, cam):
        xs, ys, ls = [], [], []
        # Dotted floor plane drifting slowly towards us.
        off = (t * .05) % self.fdz
        fz = self.fl_z - off
        fy = np.full(fz.shape, .2)
        row = self.fl_row + int(t * .05 // self.fdz)
        sx, sy, zz, p = self.project(cam, self.fl_x + (np.sin(row * 12.9898) * 43758.5453 % 1) * .03, fy, fz)
        spacing = self.S * .03 * p
        keep_k = np.maximum(1, np.ceil(3.2 / np.maximum(spacing, 1e-3))).astype(int)
        vis = ((self.fl_ix + row * 7) % keep_k == 0) & (row % 2 == 0) & (sx >= 0) & (sx < self.W) & (sy >= 0) & (sy < self.H) & (zz > -1.6)
        dep = np.clip((fz + 1.1) / 7.6, 0, 1)
        lum = 28 * (1 - dep) ** 2.2
        # Negative space around the subject leaves the halftone readable.
        clearance = np.exp(-((sy - self.H * .5) / (self.H * .24)) ** 4)
        lum *= 1 - .8 * clearance
        r = self.ripple_radius(cyc)
        if r is not None:
            rad, fade = r
            dd = np.hypot(self.fl_x - self.touch[0], (fz - self.touch[2]) * .9)
            lum = lum + 140 * np.exp(-((dd - rad * 1.6) / .05) ** 2) * fade * (1 - dep)
        xs.append(sx[vis]); ys.append(sy[vis]); ls.append(lum[vis])
        # Sparse motes with parallax.
        mx, my, mz = self.motes
        mx = (mx + t * .012 + 1.4) % 2.8 - 1.4
        sx, sy, zz, p = self.project(cam, mx, my + .01 * np.sin(t * .3 + self.mote_ph), mz)
        ml = (18 + 24 * (.5 + .5 * np.sin(t * .7 + self.mote_ph))) * np.clip(1.2 - zz * .2, .3, 1)
        xs.append(sx); ys.append(sy); ls.append(ml)
        # The dotted ripple ring itself, on the vertical plane of the touch.
        if r is not None:
            rad, fade = r
            k = max(24, int(rad * self.S * .9))
            a = np.linspace(0, math.tau, k, endpoint=False)
            keep = (np.arange(k) % 4) != 3
            a = a[keep]
            rx = self.touch[0] + rad * np.cos(a)
            ry = self.touch[1] + rad * np.sin(a)
            sx, sy, zz, p = self.project(cam, rx, ry, np.full(a.shape, self.touch[2]))
            xs.append(sx); ys.append(sy); ls.append(np.full(a.shape, 150 * fade))
        return np.concatenate(xs), np.concatenate(ys), np.concatenate(ls)

    def accents(self, t, cyc, cam):
        """Foreground accents: spark, scanning column, glitch scan line."""
        xs, ys, ls = [], [], []
        cx = self.W / 2 + self.S * self.touch[0]
        cy = self.H / 2 + self.S * self.touch[1]
        flash = max(0.0, 1 - abs(cyc - TOUCH) / .7)
        if flash:
            u = np.linspace(0, 1, 23)
            ax = cx + (u - .5) * self.S * .055
            ay = cy - np.sin(u * math.pi) * self.S * .012 + np.sin(u * 19 + t * 8) * .8
            xs.append(ax); ys.append(ay); ls.append(np.full(u.shape, 230 * flash))
        glow = _sm((cyc - 8.2) / .6) * (1 - _sm((cyc - (REL1 + .6)) / .8))
        if glow:
            k = 14
            a = np.arange(k) * 2.4 + t * 3
            rr = (1.5 + 3.5 * (.5 + .5 * np.sin(a * 1.7 + t * 5))) * (self.S / 390) ** .5
            xs.append(cx + rr * np.cos(a) * 1.4); ys.append(cy + rr * np.sin(a))
            ls.append(np.full(k, 255 * glow))
        # Scanning assembly column at the arrival frontier.
        span = (cyc - (REL0 + FLIGHT)) / (REL1 - REL0)
        if -.02 < span < 1.08:
            fx = self.wleft + (self.wright - self.wleft) * span
            yy = np.arange(self.wtop - 6, self.wbot + 7, 1.0)
            for back, lv in ((0, 255), (2, 150), (5, 80)):
                xs.append(np.full(yy.shape, fx - back)); ys.append(yy)
                fade = min(1.0, (1.08 - span) * 8)
                ls.append(np.full(yy.shape, lv * fade) * (.7 + .3 * (yy.astype(int) % 2)))
        if GLITCH <= cyc < GLITCH + .9:
            a = (cyc - GLITCH) / .9
            yy = self.wtop - 4 + (self.wbot - self.wtop + 8) * a
            xx = np.arange(self.wleft - 8, self.wright + 8, 2.0)
            xs.append(xx); ys.append(np.full(xx.shape, yy)); ls.append(np.full(xx.shape, 170.0))
        if not xs:
            return np.empty(0), np.empty(0), np.empty(0)
        return np.concatenate(xs), np.concatenate(ys), np.concatenate(ls)

    # -------------------------------------------------------------- raster
    def raster(self, x, y, lum, size=None):
        """Return (mask, level) arrays of shape w*h for a set of sub-dots."""
        if size is not None and len(x):
            px, py, pl = [], [], []
            for code in range(4):
                sel = size == code
                if not sel.any():
                    continue
                bx = np.floor(x[sel] - (.5 if code else 0) + .5).astype(np.int64)
                by = np.floor(y[sel] - (.5 if code else 0) + .5).astype(np.int64)
                px.append((bx[:, None] + _FOOT_DX[code]).ravel())
                py.append((by[:, None] + _FOOT_DY[code]).ravel())
                pl.append(np.repeat(lum[sel], len(_FOOT[code])))
            xi, yi, li = np.concatenate(px), np.concatenate(py), np.concatenate(pl)
        else:
            xi = np.floor(x + .5).astype(np.int64)
            yi = np.floor(y + .5).astype(np.int64)
            li = lum
        ok = (xi >= 0) & (xi < self.W) & (yi >= 0) & (yi < self.H)
        xi, yi, li = xi[ok], yi[ok], li[ok]
        cell = (yi >> 2) * self.w + (xi >> 1)
        mask = np.zeros(self.w * self.h, dtype=np.int64)
        np.bitwise_or.at(mask, cell, _BITLUT[yi & 3, xi & 1])
        level = np.zeros(self.w * self.h)
        np.maximum.at(level, cell, li)
        return mask, level

    def compose(self, s, fg, bg=None):
        mask, level = fg
        if bg is not None:
            bmask, blevel = bg
            empty = mask == 0
            mask = np.where(empty, bmask, mask)
            level = np.where(empty, blevel, level)
        level = np.clip(level, 0, 255).astype(int)
        s.bg = [[BLACK] * self.w for _ in range(self.h)]
        idx = np.flatnonzero(mask)
        w = self.w
        chs, fgs = s.ch, s.fg
        for i, m, lv in zip(idx.tolist(), mask[idx].tolist(), level[idx].tolist()):
            if lv < 6:
                continue
            y, x = divmod(i, w)
            chs[y][x] = chr(0x2800 + m)
            fgs[y][x] = _PALETTE[lv]

    # ---------------------------------------------------------------- API
    def step(self, s, now):
        if self.start is None:
            self.start = now
        t = now - self.start
        cam, x, y, lum, size, fg, cyc = self.particles(t)
        ax, ay, al = self.accents(t, cyc, cam)
        fx = np.concatenate((x[fg], ax))
        fy = np.concatenate((y[fg], ay))
        fl = np.concatenate((lum[fg], al))
        fs = np.concatenate((size[fg], np.zeros(len(ax), dtype=int)))
        bx, by, bl = self.background(t, cyc, cam)
        back = ~fg
        bx = np.concatenate((bx, x[back]))
        by = np.concatenate((by, y[back]))
        bl = np.concatenate((bl, lum[back]))
        self.last = (fx, fy, fl, fs)
        self.compose(s, self.raster(fx, fy, fl, fs), self.raster(bx, by, bl))

    def farewell(self, s, now, t):
        # Every dot yields to one brief spark between the fingertips, then black.
        t = max(0.0, min(1.0, t))
        if self.last is None:
            cam, x, y, lum, size, fg, cyc = self.particles(0)
            self.last = (x, y, lum, size)
        x, y, lum, size = self.last
        if t >= .88:
            s.bg = [[BLACK] * self.w for _ in range(self.h)]
            if t < 1:
                cx = int((self.W / 2 + self.S * self.touch[0]) / 2)
                cy = int((self.H / 2 + self.S * self.touch[1]) / 4)
                s.put(cx, cy, chr(0x2800 + 0x1b), _PALETTE[int(255 * (1 - t) / .12)])
            return
        cx = self.W / 2 + self.S * self.touch[0]
        cy = self.H / 2 + self.S * self.touch[1]
        dist = np.hypot(x - cx, y - cy)
        lag = dist / (dist.max() + 1e-9)
        q = _smooth(np.clip(t / .82 * (1.15 - lag * .3), 0, 1)) ** 1.5
        xx = x + (cx - x) * q
        yy = y + (cy - y) * q
        bright = lum * (1 - t * .6) + 60 * q * (1 - t)
        self.compose(s, self.raster(xx, yy, bright, np.where(q > .5, 0, size)))

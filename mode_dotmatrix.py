"""The wallpaper's halftone hands, one terminal cell per wallpaper dot.

The bundled centroids (assets/dot_hands.json, extracted offline from the
user's wallpaper) sit on a regular 178 x 24 grid. Each grid dot becomes one
cell: big wallpaper dots are drawn as '●', small ones as '·', so the hands keep
the wallpaper's exact pose and row pattern. DEDSEC is lettered with the same
dots. No wallpaper, filesystem activity or desktop data is read live.
Black, white and greys only.

40 second loop:
  0-10   the hands; light travels along both arms, a spark jumps the gap.
  10-14  the dots pour through the spark and letter DEDSEC.
  14-26  DEDSEC holds: halftone shading, dotted drop shadow, light sweep.
  26-30  the letters pour back through the spark into the hands.
  30-40  the hands again.
"""
import json
import math
from pathlib import Path

import numpy as np

NAME = 'DOTMATRIX'
LOOP = 40.0
SPARK = (6.0, 36.0)
CHARGE, ABSORB, BURST, HOLD = 10.0, 11.2, 13.6, 15.4     # hands -> DEDSEC
IMPLODE, EMERGE, HANDS = 26.0, 27.6, 30.0                # DEDSEC -> hands
SPIN = 2.6                                               # radians of swirl per flight
ASPECT = 2.2                                             # terminal cells are ~2.2x taller than wide
GREY = [(i, i, i) for i in range(256)]
BIG, MID, SMALL = '●', '•', '·'

# Letters on the cell grid; '#' is a dot.
FONT_BIG = {
    'D': ("###########...", "############..", "###.......###.", "###........###", "###........###",
          "###........###", "###.......###.", "############..", "###########..."),
    'E': ("##############", "##############", "###...........", "###...........", "###########...",
          "###...........", "###...........", "##############", "##############"),
    'S': ("..############", ".#############", "###...........", "###...........", ".############.",
          "...........###", "...........###", "#############.", "############.."),
    'C': ("..############", ".#############", "###...........", "###...........", "###...........",
          "###...........", "###...........", ".#############", "..############"),
}
FONT_SMALL = {
    'D': ("######.", "##...##", "##...##", "##...##", "######."),
    'E': ("#######", "##.....", "#####..", "##.....", "#######"),
    'S': (".######", "##.....", ".#####.", ".....##", "######."),
    'C': (".######", "##.....", "##.....", "##.....", ".######"),
}


def _smooth(a):
    a = np.clip(a, 0.0, 1.0)
    return a * a * (3 - 2 * a)


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.start = None
        self.last = None
        self._hands()
        self._word()
        self._links()
        rng = np.random.default_rng(9)
        self.dust = np.column_stack([rng.uniform(0, w, 26), rng.uniform(0, h, 26), rng.uniform(-1.5, 1.5, 26)])
        top, bot = self.wy0 - 4, self.wy0 + self.wlh + 3
        cand = [y for y in range(2, h - 2) if y < top or y > bot] or [1]
        self.lanes = [cand[int(i * (len(cand) - 1) / 3)] for i in range(4)]

    # ------------------------------------------------------------------ layout
    def _hands(self):
        d = np.array(json.loads((Path(__file__).parent / 'assets' / 'dot_hands.json').read_text())['dots'])
        u, v, size = d[:, 0], d[:, 1], d[:, 2]
        col = np.round((u - u.min()) / 0.00559).astype(int)
        order = np.argsort(v)
        row = np.empty(len(v), dtype=int)
        r, prev = 0, v[order[0]]
        for i in order:
            if v[i] - prev > 0.006:
                r += 1
            row[i] = r
            prev = v[i]
        ncol, nrow = col.max() + 1, row.max() + 1
        big = size > 0.97
        left = u < 0.47
        # Narrow screens: sample the grid; wide ones: centre it.
        k = min(1.0, (self.w - 1) / ncol)
        x = np.round(col * k + (self.w - (ncol - 1) * k) / 2 - 0.5).astype(int)
        y = np.round(row * min(1.0, k * 1.15) + self.h * 0.47 - nrow * min(1.0, k * 1.15) / 2).astype(int)
        # One dot per cell; a big dot wins over a small one.
        key = y * 10000 + x
        pri = np.lexsort((~big, key))
        _, first = np.unique(key[pri], return_index=True)
        keep = pri[first]
        keep = keep[(x[keep] >= 0) & (x[keep] < self.w) & (y[keep] >= 0) & (y[keep] < self.h)]
        self.hx, self.hy = x[keep].astype(float), y[keep].astype(float)
        self.hbig = big[keep]
        self.left = left[keep]
        # Arms end where the wallpaper ends; fade them when the screen is wider.
        x0, x1 = self.hx.min(), self.hx.max()
        self.hfade = np.ones(len(self.hx))
        if (ncol - 1) * k < self.w - 6:
            edge = np.minimum(self.hx - x0, x1 - self.hx)
            self.hfade = np.clip(edge / 14, 0.15, 1)
        lt = np.argmax(np.where(self.left, self.hx, -1e9))
        rt = np.argmin(np.where(~self.left, self.hx, 1e9))
        self.tip = (np.array([self.hx[lt], self.hy[lt]]), np.array([self.hx[rt], self.hy[rt]]))
        self.spark = (self.tip[0] + self.tip[1]) / 2
        lx, rx = self.hx[self.left].min(), self.hx[~self.left].max()
        along = np.where(self.left, (self.hx - lx) / max(1, self.tip[0][0] - lx),
                         (rx - self.hx) / max(1, rx - self.tip[1][0]))
        self.along = np.clip(along, 0, 1)

    def _word(self):
        font = FONT_BIG if self.w >= 110 and self.h >= 20 else FONT_SMALL
        lw, lh = len(font['D'][0]), len(font['D'])
        gap = 3 if font is FONT_BIG else 2
        total = 6 * lw + 5 * gap
        x0 = (self.w - total) // 2
        y0 = int(self.h * 0.45 - lh / 2)
        xs, ys, shade = [], [], []
        for n, ch in enumerate('DEDSEC'):
            for r, line in enumerate(font[ch]):
                for c, px in enumerate(line):
                    if px == '#':
                        xs.append(x0 + n * (lw + gap) + c)
                        ys.append(y0 + r)
                        # Halftone light from the top left: the lowest row and the
                        # right-hand edges turn into smaller dots.
                        # the outermost right column and the bottom row are the
                        # shadow side: one dot size smaller
                        right = c + 1 >= len(line) or (line[c + 1] != '#' and c >= lw - 4)
                        big_font = font is FONT_BIG
                        shade.append(0.8 if big_font and (r == lh - 1 or right) else 1.0)
        self.wx, self.wy = np.array(xs, dtype=float), np.array(ys, dtype=float)
        self.wshade = np.array(shade)
        self.wx0, self.wy0, self.wtotal, self.wlh = x0, y0, total, lh
        occupied = set(zip(xs, ys))

        def inside_box(x, y):
            n = (x - x0) // (lw + gap)
            lx = x - x0 - n * (lw + gap)
            return 0 <= n < 6 and lx < lw and y0 <= y < y0 + lh

        # A dotted drop shadow, only where it falls outside the letters.
        sh = [(x + 1, y + 1) for x, y in zip(xs, ys)
              if (x + 1, y + 1) not in occupied and not inside_box(x + 1, y + 1)]
        self.shx = np.array([p[0] for p in sh], dtype=float)
        self.shy = np.array([p[1] for p in sh], dtype=float)

    def _links(self):
        nh, nw = len(self.hx), len(self.wx)
        rng = np.random.default_rng(5)
        self.hphase = rng.uniform(-0.5, 0.5, nh)
        self.wphase = rng.uniform(-0.5, 0.5, nw)
        self._q_over = np.zeros(1)

    # ------------------------------------------------------------------ frame
    def _hand_layer(self, t):
        """Hands at rest: (x, y, size, brightness)."""
        wave = (t % 4.0) / 4.0 * 1.3 - 0.15
        glow = np.exp(-((self.along - wave) / 0.07) ** 2)
        size = np.where(self.hbig, 1.0, 0.25 + 0.4 * glow)
        bright = np.where(self.hbig, 0.86, 0.62) + 0.14 * glow
        return self.hx, self.hy, size, bright * self.hfade

    def _word_layer(self, t):
        band = ((t - HOLD) % 5.0) / 5.0 * 1.6 - 0.3
        pos = (self.wx - self.wx0) / self.wtotal - (self.wy - self.wy0) * 0.012
        shine = np.exp(-((pos - band) / 0.045) ** 2)
        size = np.where(self.wshade > 0.9, 1.0, 0.6) + 0.4 * shine
        bright = 0.66 + 0.2 * self.wshade + 0.3 * shine
        return self.wx, self.wy, size, bright

    def _spiral(self, x0, y0, q, inward, phase):
        """Swirl between a dot's home and the spark centre.

        inward: home -> centre; otherwise centre -> home. q in 0..1 (eased inside)."""
        cx, cy = self.spark
        dx, dy = x0 - cx, (y0 - cy) * ASPECT
        r0 = np.hypot(dx, dy)
        a0 = np.arctan2(dy, dx)
        e = _smooth(q)
        if inward:
            r = r0 * (1 - e) ** 1.4
            a = a0 + SPIN * e + phase * e
        else:
            r = r0 * (1 - (1 - e) ** 1.6)
            a = a0 - (SPIN + phase) * (1 - e)
        return cx + r * np.cos(a), cy + r * np.sin(a) / ASPECT

    def _travel(self, hx, hy, q, inward, phase, base_size, base_bright, land_flash=False):
        """Moving dots plus two trailing dots; returns layers."""
        out = []
        moving = (q > 0) & (q < 1)
        if moving.any():
            for lag, sz, br in ((0.0, 0.62, 1.0), (0.05, 0.3, 0.55), (0.1, 0.3, 0.3)):
                qq = np.clip(q[moving] - lag, 0, 1)
                x, y = self._spiral(hx[moving], hy[moving], qq, inward, phase[moving])
                out.append((x, y, np.full(len(x), sz), np.full(len(x), br)))
        # dots that are home (outward) or still at rest (inward)
        rest = (q >= 1) if not inward else (q <= 0)
        if rest.any():
            sz, br = base_size[rest], base_bright[rest]
            if land_flash:
                fresh = np.clip(1 - (self._q_over[rest] / 0.35), 0, 1)
                sz = np.maximum(sz, fresh * 1.0)
                br = np.minimum(1.0, br + 0.5 * fresh)
            out.append((hx[rest], hy[rest], sz, br))
        return out

    def layers(self, t):
        if t < CHARGE or t >= HANDS:
            return [self._hand_layer(t)]
        hx, hy, hs, hb = self._hand_layer(t)
        if t < ABSORB:
            # charge: light pours down the arms into the fingertips
            k = (t - CHARGE) / (ABSORB - CHARGE)
            glow = np.exp(-((self.along - k * 1.1) / 0.12) ** 2) + 0.6 * k * self.along ** 3
            return [(hx, hy, np.maximum(hs, glow * 0.7), np.minimum(1.0, hb + 0.45 * glow))]
        if t < BURST:
            # absorb: fingertips first, each dot swirls into the spark
            start = ABSORB + (1 - self.along) * 1.5
            q = np.clip((t - start) / 0.9, 0, 1)
            return self._travel(hx, hy, q, True, self.hphase, hs, hb)
        wx, wy, ws, wb = self._word_layer(HOLD)
        if t < HOLD:
            # burst: letters are thrown out of the spark from left to right
            start = BURST + (self.wx - self.wx0) / self.wtotal * 1.0
            q = np.clip((t - start) / 0.75, 0, 1)
            self._q_over = np.clip((t - start) / 0.75 - 1, 0, None) * 0.75
            return self._travel(wx, wy, q, False, self.wphase, ws, wb, land_flash=True)
        if t < IMPLODE:
            x, y, size, bright = self._word_layer(t)
            # a slow ripple of dot size from the centre of the word
            d = np.hypot(self.wx - self.spark[0], (self.wy - self.spark[1]) * ASPECT)
            rip = 0.5 + 0.5 * np.sin(d * 0.35 - (t - HOLD) * 3.0)
            return [(x, y, size, np.clip(bright * (0.86 + 0.2 * rip), 0, 1))]
        if t < EMERGE:
            # implode: right to left back into the spark
            start = IMPLODE + (1 - (self.wx - self.wx0) / self.wtotal) * 0.8
            q = np.clip((t - start) / 0.7, 0, 1)
            return self._travel(wx, wy, q, True, self.wphase, ws, wb)
        # emerge: the hands grow back out of the contact point
        start = EMERGE + (1 - self.along) * 1.4
        q = np.clip((t - start) / 0.9, 0, 1)
        self._q_over = np.clip((t - start) / 0.9 - 1, 0, None) * 0.9
        return self._travel(hx, hy, q, False, self.hphase, hs, hb, land_flash=True)

    def energy(self, t):
        """Size of the energy ball between the fingertips, 0..1.3."""
        if CHARGE <= t < ABSORB:
            return (t - CHARGE) / (ABSORB - CHARGE) * 0.6
        if ABSORB <= t < BURST:
            return 0.6 + 0.7 * (t - ABSORB) / (BURST - ABSORB)
        if BURST <= t < HOLD:
            return 1.3 * max(0.0, 1 - (t - BURST) / 1.2)
        if IMPLODE <= t < EMERGE:
            return 1.3 * (t - IMPLODE) / (EMERGE - IMPLODE)
        if EMERGE <= t < HANDS:
            return 1.3 * max(0.0, 1 - (t - EMERGE) / 1.6)
        return 0.0

    def spark_fx(self, t):
        """Spark / energy ball between the fingertips: (x, y, char, brightness)."""
        cells = []
        cx, cy = self.spark
        for s0 in SPARK:
            dt = t - s0
            if 0 <= dt < 2.0:
                k = 1 - dt / 2.0
                if dt < 0.5:
                    cells.append((cx, cy, BIG, 1.0))
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        cells.append((cx + dx, cy + dy, MID, 0.8))
                r = dt * 26
                for i in range(64):
                    a = i / 64 * math.tau
                    cells.append((cx + math.cos(a) * r, cy + math.sin(a) * r / ASPECT, SMALL, 0.55 * k))
        e = self.energy(t)
        if e > 0.02:
            flick = 0.8 + 0.2 * math.sin(t * 31)
            cells.append((cx, cy, BIG, flick))
            for dx in (-1, 1):
                cells.append((cx + dx, cy, MID if e < 0.8 else BIG, 0.85 * flick))
            # rotating dotted rings, tilted, growing with the energy
            for ring, (rad, n, spd) in enumerate(((3.0, 14, 2.4), (5.5, 22, -1.6), (8.5, 30, 1.1))):
                rr = rad * e
                if rr < 1.2:
                    continue
                for i in range(n):
                    a = i / n * math.tau + t * spd
                    tilt = 0.55 + 0.25 * ring
                    x = cx + math.cos(a) * rr * 2.0
                    y = cy + math.sin(a) * rr * tilt / 1.4
                    front = math.sin(a) > 0
                    cells.append((x, y, MID if front and ring == 0 else SMALL, (0.85 if front else 0.4) * min(1, e)))
        # flash when the ball bursts into the letters
        db = t - BURST
        if 0 <= db < 0.9:
            r = db * 70
            for i in range(90):
                a = i / 90 * math.tau
                cells.append((cx + math.cos(a) * r, cy + math.sin(a) * r / ASPECT, SMALL, 0.7 * (1 - db / 0.9)))
        return cells

    # ------------------------------------------------------------------ draw
    def draw(self, s, layers, fx=(), shadow=0.0):
        best = {}
        if shadow > 0:
            for x, y in zip(self.shx, self.shy):
                best[(int(x), int(y))] = (0.3, 0.22 * shadow)
        for x, y, size, bright in layers:
            xi = np.round(x).astype(int)
            yi = np.round(y).astype(int)
            for cx, cy, sz, b in zip(xi.tolist(), yi.tolist(), size.tolist(), bright.tolist()):
                cur = best.get((cx, cy))
                if cur is None or sz > cur[0] or (sz == cur[0] and b > cur[1]):
                    best[(cx, cy)] = (sz, b)
        for x, y, ch, b in fx:
            sz = 1.0 if ch == BIG else 0.6 if ch == MID else 0.3
            key = (int(round(x)), int(round(y)))
            cur = best.get(key)
            if cur is None or sz >= cur[0]:
                best[key] = (sz, b)
        for (x, y), (sz, b) in best.items():
            if 0 <= x < self.w and 0 <= y < self.h and b > 0.04:
                ch = BIG if sz > 0.8 else MID if sz > 0.45 else SMALL
                s.ch[y][x] = ch
                s.fg[y][x] = GREY[int(30 + 225 * min(1.0, b))]

    def effects(self, t):
        """Extra elements around the hands -> DEDSEC transition: (x, y, char, brightness)."""
        cells = []
        cx, cy = self.spark
        rnd = np.random.default_rng(int(t * 30))
        (lx, ly), (rx, ry) = self.tip
        # 1. charge: an electric arc of dots jumps between the fingertips; embers rise off the arms
        if CHARGE <= t < BURST:
            k = min(1.0, (t - CHARGE) / (ABSORB - CHARGE))
            n = max(2, int(abs(rx - lx)))
            jag = rnd.normal(0, 1.2 * k, n)
            for i in range(n):
                u = i / (n - 1)
                x = lx + (rx - lx) * u
                y = ly + (ry - ly) * u + jag[i] * math.sin(u * math.pi)
                cells.append((x, y, MID if rnd.random() < 0.3 else SMALL, 0.5 + 0.5 * k))
            if t < ABSORB + 0.6:
                idx = rnd.choice(len(self.hx), size=int(18 * k) + 2)
                for j in idx:
                    rise = rnd.uniform(0.5, 3.0) * k
                    cells.append((self.hx[j] + rnd.normal(0, 0.6), self.hy[j] - rise, SMALL, 0.6))
        # 2. absorb: converging dotted rays and dust pulled in from the screen edges
        if ABSORB <= t < BURST:
            k = (t - ABSORB) / (BURST - ABSORB)
            for i in range(16):
                a = i / 16 * math.tau + t * 0.6
                r0 = (1 - ((t * 1.6 + i * 0.37) % 1.0)) * max(self.w, self.h * ASPECT) * 0.55
                for d in range(3):
                    r = r0 + d * 2.5
                    cells.append((cx + math.cos(a) * r, cy + math.sin(a) * r / ASPECT, SMALL, (0.4 + 0.5 * k) * (1 - d / 3)))
        # 3. burst: a second shock ring, radial streaks and a brief field of lit dots
        db = t - BURST
        if 0 <= db < 1.6:
            r2 = db * 45
            for i in range(70):
                a = i / 70 * math.tau
                cells.append((cx + math.cos(a) * r2, cy + math.sin(a) * r2 / ASPECT, SMALL, 0.5 * (1 - db / 1.6)))
            if db < 0.7:
                for i in range(24):
                    a = i / 24 * math.tau + 0.13
                    for d in range(4):
                        r = db * 60 + d * 1.6
                        cells.append((cx + math.cos(a) * r, cy + math.sin(a) * r / ASPECT, MID if d == 0 else SMALL,
                                      0.8 * (1 - db / 0.7) * (1 - d / 4)))
            if db < 1.0:
                field = rnd.random((self.h, self.w)) < 0.025 * (1 - db)
                for y, x in zip(*np.nonzero(field)):
                    cells.append((x, y, SMALL, 0.3 * (1 - db)))
        # 4. letters form: corner brackets draw in, an underline runs, a scan column passes
        x0, y0 = self.wx0 - 3, self.wy0 - 2
        x1, y1 = self.wx0 + self.wtotal + 2, self.wy0 + self.wlh + 1
        if HOLD - 0.6 <= t < IMPLODE:
            k = min(1.0, (t - (HOLD - 0.6)) / 0.8)
            arm = int(6 * k) + 1
            for (bx, by, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                for i in range(arm):
                    cells.append((bx + sx * i, by, MID, 0.75))
                for i in range(max(1, arm // 2)):
                    cells.append((bx, by + sy * i, MID, 0.75))
            ul = int((self.wtotal + 4) * min(1.0, (t - HOLD) / 1.2)) if t >= HOLD else 0
            for i in range(ul):
                cells.append((x0 + 1 + i, y1 + 1, SMALL, 0.45))
            sc = t - HOLD
            if 0 <= sc < 1.1:
                xs = x0 + (x1 - x0) * (sc / 1.1)
                for y in range(int(y0), int(y1) + 1):
                    cells.append((xs, y, MID, 0.9))
                    cells.append((xs - 1, y, SMALL, 0.5))
        # 5. while the word holds: drifting dust and streams of data dots behind it
        if HOLD <= t < IMPLODE:
            k = min(1.0, (t - HOLD) / 1.5, (IMPLODE - t) / 0.8)
            for i in range(26):
                x = (self.dust[i, 0] + t * self.dust[i, 2]) % self.w
                y = (self.dust[i, 1] + math.sin(t * 0.5 + i) * 1.5) % self.h
                cells.append((x, y, SMALL, 0.3 * k))
            for i in range(4):
                lane = self.lanes[i]
                head = ((t * (14 + i * 5) + i * 40) % (self.w + 30)) - 15
                for d in range(10):
                    cells.append((head - d, lane, SMALL if d else MID, 0.55 * k * (1 - d / 10)))
        return cells

    def step(self, s, now):
        if self.start is None:
            self.start = now
        t = (now - self.start) % LOOP
        layers = self.layers(t)
        shadow = 0.0
        if HOLD - 0.4 <= t < IMPLODE + 0.3:
            shadow = min(1.0, (t - (HOLD - 0.4)) / 0.8, (IMPLODE + 0.3 - t) / 0.6)
        self.draw(s, layers, self.spark_fx(t) + self.effects(t), shadow)
        self.last = layers

    def farewell(self, s, now, t):
        # Everything streams into the spark, which then goes out.
        t = max(0.0, min(1.0, t))
        layers = self.last or self.layers(0.0)
        q = float(_smooth(np.array(t / 0.8))) ** 1.5
        cx, cy = self.spark
        moved = [(x + (cx - x) * q, y + (cy - y) * q, size, bright * (1 - 0.5 * q))
                 for x, y, size, bright in layers]
        fx = [(cx, cy, BIG, 1.0 - max(0.0, t - 0.8) / 0.2)] if t < 1 else []
        self.draw(s, moved, fx)

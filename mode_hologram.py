"""HOLOGRAM: a translucent voxel object (DedSec skull, Wrench mask, DS logo) projected in a dark lab.

The projector sits on a floor of glowing rings with data columns on the back wall; its light cone
feeds a scanlined, flickering hologram that dissolves into particles and reassembles between shapes.
Side panels show the object library and the emitter telemetry.
"""

import math
import random
import time

from lib import (BLACK, CYAN, DIM_CYAN, GREY, PINK, PURPLE, WHITE, YELLOW, Glitch, blend,
                 pulse)
from sysdata import DATA
from widgets import SHAPES, Particles, rot

NAME = "HOLOGRAM"

SKULL = [
    "......XXXXXXXXXX......",
    "....XXXXXXXXXXXXXX....",
    "...XXXXXXXXXXXXXXXX...",
    "..XXXXXXXXXXXXXXXXXX..",
    ".XXXXXXXXXXXXXXXXXXXX.",
    ".XXX......XX......XXX.",
    ".XXX......XX......XXX.",
    ".XXXX....XXXX....XXXX.",
    ".XXXXXXXXX..XXXXXXXXX.",
    "..XXXXXXXX..XXXXXXXX..",
    "...XXXXXX....XXXXXX...",
    "....XXXXXXXXXXXXXX....",
    ".....X.X.X.X.X.X.X....",
    ".....XXXXXXXXXXXXX....",
    "......XXXXXXXXXXX.....",
]

FONT = {
    "D": ["█████ ", "██  ██", "██  ██", "██  ██", "█████ "],
    "S": [" █████", "██    ", " ████ ", "    ██", "█████ "],
}


def extrude(filled, accent=(), depth=2):
    """Grid cells -> hollow voxel slab: both faces plus the side walls. Voxel = (x, y, z, kind)
    with kind 0 = wall, 1 = face, 2 = accent (eyes)."""
    cs = [c for c, r in filled]
    rs = [r for c, r in filled]
    mx, my = (min(cs) + max(cs)) / 2, (min(rs) + max(rs)) / 2
    vox = []
    for (c, r) in filled:
        edge = any((c + dx, r + dy) not in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for z in range(-depth, depth + 1):
            if abs(z) == depth or edge:
                vox.append((c - mx, r - my, z * 0.9, 1 if abs(z) == depth else 0))
    for (c, r) in accent:
        for z in (-(depth + 1), depth + 1):
            vox.append((c - mx, r - my, z * 0.9, 2))
    return vox


def skull_cells():
    return {(c, r) for r, row in enumerate(SKULL) for c, ch in enumerate(row) if ch == "X"}, []


EYE = ["X...X", ".X.X.", "..X..", ".X.X.", "X...X"]


def mask_cells():
    """Wrench's LED mask: chamfered plate with two X_X eyes and a grille mouth."""
    w, h = 25, 13
    filled = set()
    for r in range(h):
        cut = (2 - r) if r < 2 else (r - (h - 4)) * 2 if r > h - 4 else 0
        for c in range(cut, w - cut):
            filled.add((c, r))
    accent = []
    for ox in (3, w - 8):
        for r, row in enumerate(EYE):
            for c, ch in enumerate(row):
                if ch == "X":
                    accent.append((ox + c, 2 + r))
    for c in range(7, w - 7, 2):
        accent.append((c, h - 3))
    return filled, accent


def letter_cells(word="DS", scale=2):
    filled = set()
    x0 = 0
    for letter in word:
        for r, row in enumerate(FONT[letter]):
            for c, ch in enumerate(row):
                if ch != " ":
                    for i in range(scale):
                        for j in range(scale):
                            filled.add((x0 + c * scale + i, r * scale + j))
        x0 += (len(FONT[letter][0]) + 1) * scale
    return filled, [], (len(FONT[word[0]][0]) + 0.5) * scale - x0 / 2


def build_skull():
    return extrude(skull_cells()[0])


def build_mask():
    filled, accent = mask_cells()
    return extrude(filled, accent, depth=1)


def build_letters():
    filled, _, split = letter_cells()
    vox = extrude(filled)
    # the second letter glows pink on its faces, like the DedSec logo colours
    return [(x, y, z, 2 if (k == 1 and x > split) else k) for (x, y, z, k) in vox]


MORPH = 3.2
SHAPE_NAMES = ["DEDSEC.OBJ", "WRENCH.OBJ", "DS_LOGO.OBJ"]
SHAPE_INFO = ["SKULL // EMBLEM", "LED MASK // WRENCH", "LOGOTYPE // DS"]


def pad(vox, n):
    """Order voxels top-to-bottom and stretch the list to n entries (duplicates flagged)."""
    vox = sorted(vox, key=lambda v: (round(v[1]), v[0], v[2]))
    m = len(vox)
    out, last = [], -1
    for i in range(n):
        j = int(i * m / n)
        out.append(vox[j] + (j == last,))
        last = j
    return out


def thumb(filled, accent=(), split=None):
    """Front-view silhouette for the library panel: [(col, row, kind)]."""
    cs = [c for c, r in filled]
    rs = [r for c, r in filled]
    c0, r0 = min(cs), min(rs)
    acc = set(accent)
    out = []
    for c, r in filled:
        k = 2 if (c, r) in acc else 1
        if split is not None and c - (min(cs) + max(cs)) / 2 > split:
            k = 2
        out.append((c - c0, r - r0, k))
    return out, max(cs) - c0 + 1, max(rs) - r0 + 1


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.glitch = Glitch(0.012)
        self.particles = Particles()
        shapes = [build_skull(), build_mask(), build_letters()]
        self.counts = [len(v) for v in shapes]
        n = max(self.counts)
        self.shapes = [pad(v, n) for v in shapes]
        self.cur, self.nxt = 0, 1
        self.morph_t = None
        self.next_morph = time.time() + random.uniform(7, 10)
        self.delay = [random.uniform(0, 0.45) for _ in range(n)]
        self.swirl = [random.choice((-1, 1)) * random.uniform(0.6, 1.4) for _ in range(n)]
        self.bump = 0.0
        self.ring_t = 0.0
        self.nvox = self.counts[0]
        self.scale = 1.45 if h >= 40 and w >= 120 else 1.0
        self.bw = math.ceil(2 * self.scale)
        self.bph = max(2, round(2 * self.scale))
        self.cx, self.cy = w / 2, h / 2 - 2
        self.last = time.time()
        self.started = self.last
        self.sats = [(random.choice(SHAPES), random.uniform(0, math.tau), random.uniform(0.4, 0.9)) for _ in range(3)]
        self.ghosts = []
        self.flick_hist = [0.5] * 24
        self.zoom = self.scale
        self.voxel_palette = [[blend(BLACK, col, (k + 5) / 20) for k in range(16)]
                              for col in ((0, 110, 145), (90, 240, 255), (255, 150, 220))]
        self.mask_palette = [[blend(col, BLACK, .52 * level / 16)
                              for col in self.voxel_palette[1]] for level in range(17)]
        self.accent_palette = [blend(col, WHITE, .32) for col in self.voxel_palette[2]]
        self.voxel_shading = {col: (blend(col, WHITE, 0.25), blend(col, BLACK, 0.35),
                                    blend(col, BLACK, 0.8))
                              for palette in self.voxel_palette + self.mask_palette + [self.accent_palette]
                              for col in palette}
        sk = skull_cells()
        mk = mask_cells()
        lt = letter_cells()
        self.thumbs = [thumb(sk[0]), thumb(mk[0], mk[1]), thumb(lt[0], (), lt[2])]
        # side panels only when there is room beside the projection
        self.panel_w = 28 if w >= 140 and h >= 34 else 0
        self.build_room()
        self.columns = []
        rnd = random.Random(5)
        step = 12 if w >= 140 else 9
        for x in range(4, w - 3, step):
            packets = [[rnd.uniform(0, 1), rnd.uniform(0.15, 0.45), rnd.randint(3, 7), rnd.random() < 0.15]
                       for _ in range(rnd.randint(2, 3))]
            self.columns.append((x, packets))

    # ------------------------------------------------------------ static room
    def build_room(self):
        w, h = self.w, self.h
        ph = h * 2
        self.hz = hz = int((self.cy + 4) * 2)              # wall/floor seam in pixel rows
        pt = [[None] * w for _ in range(h)]
        pb = [[None] * w for _ in range(h)]
        vx = w / 2
        for py in range(ph):
            layer = (pb if py & 1 else pt)[py >> 1]
            if py < hz:
                f = py / max(1, hz)
                base = blend((3, 5, 11), (9, 15, 26), f)
                seam = py % 16 == 0
                for x in range(w):
                    c = base
                    if seam or x % 24 == 0:
                        c = blend(base, BLACK, 0.4)
                    elif (x % 24 == 1) or (py % 16 == 1):
                        c = blend(base, (40, 60, 80), 0.12)
                    layer[x] = c
            else:
                f = (py - hz) / max(1, ph - hz)
                base = blend((7, 12, 20), (2, 3, 7), f)
                depth = py - hz + 1
                for x in range(w):
                    c = base
                    # perspective floor grid converging on the vanishing point
                    gx = (x - vx) / depth
                    if abs(gx - round(gx / 3) * 3) < 0.6 / depth + 0.06:
                        c = blend(base, (20, 50, 66), 0.6 * (1 - f * 0.5))
                    layer[x] = c
                if depth in (1, 2, 4, 7, 11, 17, 25, 35, 48):
                    for x in range(w):
                        layer[x] = blend(layer[x], (20, 50, 66), 0.45)
        # hazy reflection band where the wall meets the floor
        for x in range(w):
            for k, a in ((0, 0.35), (1, 0.18), (-1, 0.18)):
                py = hz + k
                if 0 <= py < ph:
                    layer = (pb if py & 1 else pt)[py >> 1]
                    layer[x] = blend(layer[x], (0, 90, 110), a)
        self.room = (pt, pb)

    # ------------------------------------------------------------ helpers
    def project(self, x, y, z, D):
        k = D / max(1.0, D + z)
        return self.cx + x * 2 * k * self.zoom, self.cy + y * k * self.zoom, z

    def ring(self, s, radius, tilt, spin, color, front, D, dots=3, now=0.0):
        bump = self.bump
        dim = (0.55 if front else 0.8) - 0.3 * bump
        dot_col = blend(color, BLACK, dim)
        for i in range(90):
            a = i / 90 * math.tau
            p = rot((math.cos(a) * radius, 0, math.sin(a) * radius), tilt, spin)
            if (p[2] < 0) == front:
                x, y, z = self.project(*p, D)
                s.put(int(x), int(y), "·", dot_col)
        head = blend(color, WHITE, bump * 0.6)
        trail = 6 + int(bump * 6)
        for d in range(dots):
            a = self.ring_t * 1.2 + d * math.tau / dots
            for k in range(trail):
                p = rot((math.cos(a - k * 0.06) * radius, 0, math.sin(a - k * 0.06) * radius), tilt, spin)
                if (p[2] < 0) == front:
                    x, y, z = self.project(*p, D)
                    s.put(int(x), int(y), "●" if k == 0 else "•", blend(head, BLACK, k / trail))

    def draw_room(self, s, now):
        pt, pb = self.room
        for y in range(s.h):
            s.pt[y] = pt[y][:]
            s.pb[y] = pb[y][:]
        hz = self.hz
        # data columns: glass tubes on the back wall with packets streaming upward
        top = 4
        span = hz - top - 2
        if span < 6:
            return
        for x, packets in self.columns:
            for py in range(top, hz - 1):
                layer = (s.pb if py & 1 else s.pt)[py >> 1]
                layer[x] = (8, 22, 30)
            for p in packets:
                pos, speed, ln, hot = p
                head = hz - 2 - int(((pos + now * speed * 0.35) % 1.0) * span)
                col = (255, 60, 160) if hot else CYAN
                for k in range(ln):
                    py = head + k
                    if top <= py < hz - 1:
                        s.pixel(x, py, blend(col, (8, 22, 30), k / ln * 0.85))
            s.pixel(x, hz, (0, 70, 90))
            s.pixel(x, hz + 1, (0, 40, 52))

    def draw_floor_rings(self, s, now, D, base_y, tilt):
        cy_floor = base_y + 1.9
        for r in (11.5, 15.5, 20.5, 26.5):
            wave = max(0.0, math.cos((r - now * 9) / 3.2))
            lvl = 0.18 + 0.55 * wave ** 3 + 0.25 * self.bump
            col = blend((4, 10, 16), CYAN, lvl)
            prev = None
            n = int(24 + r * 2.5)
            for i in range(n + 1):
                a = i / n * math.tau
                p = rot((math.cos(a) * r, cy_floor, math.sin(a) * r), tilt, 0)
                if D + p[2] < D * 0.5:
                    prev = None
                    continue
                x, y, _ = self.project(*p, D)
                cur = (int(x), int(y * 2))
                if prev and abs(cur[0] - prev[0]) < 30:
                    s.pixel_line(prev[0], prev[1], cur[0], cur[1], col)
                prev = cur

    def draw_cone(self, s, now, D, base_y, tilt):
        """Translucent light cone from the lens up through the object."""
        bot = self.project(*rot((0, base_y - 0.4, 0), tilt, 0), D)
        topp = self.project(*rot((0, -10.5, 0), tilt, 0), D)
        rb = 5.5 * 2 * self.zoom
        rt = 15.5 * 2 * self.zoom
        y0, y1 = int(topp[1] * 2), int(bot[1] * 2)
        if y1 <= y0:
            return
        cr, cg, cb = (40, 220, 255)
        boost = 1 + 0.6 * self.bump
        shift = int(now * 14)
        W = s.w
        for py in range(max(0, y0), min(s.ph, y1)):
            f = (py - y0) / (y1 - y0)                 # 0 at the top, 1 at the lens
            cx = topp[0] + (bot[0] - topp[0]) * f
            hw = rt + (rb - rt) * f
            fade = (0.25 + 0.75 * f) * boost
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            xa, xb = max(0, int(cx - hw)), min(W - 1, int(cx + hw))
            inv = 1 / max(1.0, hw)
            for x in range(xa, xb + 1):
                e = abs(x - cx) * inv
                a = (0.05 + 0.2 * e ** 6) * fade
                if (x * 5 + shift) % 13 == 0:
                    a += 0.05 * fade
                c = layer[x]
                if c is None:
                    c = BLACK
                layer[x] = (int(c[0] + (cr - c[0]) * a), int(c[1] + (cg - c[1]) * a), int(c[2] + (cb - c[2]) * a))
        # bright cone edges
        for side in (-1, 1):
            s.pixel_line(int(bot[0] + side * rb), y1, int(topp[0] + side * rt * 0.82), int(y0 + (y1 - y0) * 0.18),
                         blend((0, 60, 80), CYAN, 0.35 + 0.4 * self.bump))

    # ------------------------------------------------------------ side panels
    def panel_box(self, s, x, y, w, h, title, col):
        for yy in range(max(0, y), min(s.h, y + h)):
            for xx in range(max(0, x), min(s.w, x + w)):
                s.ch[yy][xx] = " "
                s.pt[yy][xx] = s.pb[yy][xx] = None
                s.bg[yy][xx] = (3, 10, 15)
        s.text(x, y, "┌" + "─" * (w - 2) + "┐", col)
        for i in range(1, h - 1):
            s.put(x, y + i, "│", col)
            s.put(x + w - 1, y + i, "│", col)
        s.text(x, y + h - 1, "└" + "─" * (w - 2) + "┘", col)
        s.text(x + 2, y, " " + title + " ", blend(col, WHITE, 0.4))

    def draw_library(self, s, now, mt):
        pw = self.panel_w
        x0, y0 = 1, 3
        slot = 10 if self.h >= 40 else 8
        hgt = 3 * slot + 2
        self.panel_box(s, x0, y0, pw, hgt, "OBJECT LIBRARY", DIM_CYAN)
        for i, (cells, tw, th) in enumerate(self.thumbs):
            y = y0 + 1 + i * slot
            active = i == self.cur
            target = mt is not None and i == self.nxt
            if active:
                col, tag = CYAN, "LIVE"
            elif target:
                col, tag = PINK if int(now * 6) % 2 else blend(PINK, WHITE, 0.4), "LOAD"
            else:
                col, tag = (40, 70, 90), "IDLE"
            s.text(x0 + 2, y, SHAPE_NAMES[i], col)
            s.text(x0 + pw - 2 - len(tag), y, tag, col)
            s.text(x0 + 2, y + 1, SHAPE_INFO[i][:pw - 4], GREY if active or target else (40, 50, 62))
            # pixel silhouette, scanlined like the projection
            tx = x0 + (pw - tw) // 2
            ty = (y + 2) * 2 + 1
            maxr = (slot - 3) * 2
            ry = 1 if th <= maxr else th / maxr
            scan = int(now * 10)
            for c, r, k in cells:
                py = ty + int(r / ry)
                base = col if k == 1 else (blend(col, WHITE, 0.5) if active else blend(col, PINK, 0.6))
                if (py + scan) % 3 == 0:
                    base = blend(base, BLACK, 0.55)
                if target and mt is not None and r / th > mt:
                    base = blend(base, BLACK, 0.7)
                s.pixel(tx + c, py, base)
            if target and mt is not None:
                bar = int(mt * (pw - 4))
                s.text(x0 + 2, y + slot - 1, "▰" * bar + "▱" * (pw - 4 - bar), PINK)

    def draw_telemetry(self, s, now, D, yaw, flick):
        pw = self.panel_w
        x0, y0 = self.w - pw - 1, 3
        rows = 16 if self.h >= 40 else 12
        self.panel_box(s, x0, y0, pw, rows + 2, "EMITTER", DIM_CYAN)
        x = x0 + 2
        inner = pw - 4

        def bar(y, label, v, col):
            n = inner - 9
            k = int(max(0.0, min(1.0, v)) * n)
            s.text(x, y, label.ljust(8), GREY)
            s.text(x + 8, y, "█" * k + "░" * (n - k), col)

        y = y0 + 1
        live = "● LIVE" if int(now * 2) % 2 else "○ LIVE"
        s.text(x, y, "STATUS", GREY)
        s.text(x + inner - len(live), y, live, PINK)
        y += 1
        temp = 41 + DATA.cpu * 24 + self.bump * 3 + math.sin(now * 0.3)
        s.text(x, y, "LENS", GREY)
        s.text(x + inner - 6, y, "%4.1f°C" % temp, YELLOW if temp > 55 else CYAN)
        y += 1
        s.text(x, y, "FOCAL", GREY)
        s.text(x + inner - 5, y, "%3dmm" % D, CYAN)
        y += 1
        s.text(x, y, "YAW", GREY)
        s.text(x + inner - 4, y, "%03d°" % (math.degrees(yaw) % 360), CYAN)
        y += 1
        bar(y, "POWER", 0.55 + 0.35 * DATA.level + 0.1 * self.bump, CYAN)
        y += 1
        bar(y, "CPU", DATA.cpu, (0, 160, 190))
        y += 1
        bar(y, "MEM", DATA.mem, (0, 160, 190))
        y += 2
        s.text(x, y, "BEAM STABILITY", GREY)
        y += 1
        # sparkline of the projector flicker (pixel bars, 2 rows high)
        hist = self.flick_hist[-inner:]
        base_py = (y + 2) * 2
        for i, v in enumerate(hist):
            hgt = 1 + int(max(0.0, min(1.0, (v - 0.75) / 0.5)) * 3)
            for k in range(hgt):
                s.pixel(x + i, base_py - 1 - k, blend(DIM_CYAN, CYAN, k / 3))
        y += 2
        if y + 3 < y0 + rows + 1:
            y += 1
            s.text(x, y, "AUDIO SYNC", GREY)
            y += 1
            base_py = (y + 2) * 2
            nb = min(16, inner // 2)
            for i in range(nb):
                v = DATA.band(i, nb)
                hgt = 1 + int(v * 3)
                for k in range(hgt):
                    s.pixel(x + i * 2, base_py - 1 - k, blend(PURPLE, PINK, k / 3))

    # ------------------------------------------------------------ main loop
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        self.bump = max(DATA.beat, self.bump - dt * 3.5)
        self.ring_t += dt * (1 + 1.2 * DATA.level + 1.5 * self.bump)

        # dolly zoom: perspective strength changes while the size is compensated
        dz = pulse(now, 0.35)
        D = 25 + dz * 140
        self.zoom = self.scale * (0.85 + 0.25 * (1 - dz))

        # Hold the face toward the room long enough to read its eyes and jaw,
        # then make one smooth inspection turn before returning to the front.
        age = max(0.0, now - self.started)
        phase = age % 12.0
        turn = max(0.0, min(1.0, (phase - 8.0) / 4.0))
        yaw = math.tau * turn * turn * (3 - 2 * turn) + 0.18 * math.sin(age * 0.5)
        pitch = math.sin(now * 0.5) * 0.35
        roll = math.sin(now * 0.23) * 0.12
        tilt = pitch * 0.3
        base_y = 11

        self.draw_room(s, now)
        self.draw_floor_rings(s, now, D, base_y, tilt)

        # Machined projector housing: layered decks, cooling fins and a hot lens.
        rings = []
        for yy, rr, col in ((base_y + 1.6, 9.6, (24, 34, 48)),
                            (base_y + 0.8, 10.0, (58, 72, 86)),
                            (base_y + 0.25, 9.2, (26, 48, 58))):
            ring = []
            for k in range(48):
                a = k / 48 * math.tau
                px, py, z = self.project(*rot((math.cos(a) * rr, yy, math.sin(a) * rr), tilt, 0), D)
                ring.append((px, py, z))
                if k:
                    b = ring[k - 1]
                    s.pixel_line(int(b[0]), int(b[1] * 2), int(px), int(py * 2), col)
            rings.append(ring)
        for k in range(0, 48, 3):
            a, b = rings[0][k], rings[2][k]
            s.pixel_line(int(a[0]), int(a[1] * 2), int(b[0]), int(b[1] * 2), (90, 110, 122))
        base_col = blend(blend(CYAN, BLACK, 0.3), WHITE, self.bump * 0.5)
        lens = []
        for i in range(36):
            a = i / 36 * math.tau + now * 0.4
            x0, y0, _ = self.project(*rot((math.cos(a) * 6, base_y - 0.2, math.sin(a) * 6), tilt, 0), D)
            lens.append((int(x0), int(y0 * 2)))
        for (ax, ay), (bx, by) in zip(lens, lens[1:] + lens[:1]):
            s.pixel_line(ax, ay, bx, by, base_col)

        for x, py, col in self.ghosts:
            s.pixel(x, py, col)
        self.draw_cone(s, now, D, base_y, tilt)
        for _ in range(1 + int(self.bump * 3)):
            if random.random() > 0.6:
                continue
            a = random.uniform(0, math.tau)
            x, y, _ = self.project(math.cos(a) * 5, base_y - 0.5, math.sin(a) * 5, D)
            self.particles.add(x, y, 0, -random.uniform(4, 9) * (1 + self.bump), random.uniform(1, 2.5), "·•+", CYAN)

        self.ring(s, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, False, D, now=now)
        self.ring(s, 16, 0.4, -now * 0.2, PURPLE, False, D, dots=2, now=now)

        # voxel model (morphing between shapes), painter-sorted back to front
        mt = None
        if self.morph_t is None and now > self.next_morph:
            self.morph_t = now
            self.glitch.trigger(now, 0.2)
        if self.morph_t is not None:
            mt = (now - self.morph_t) / MORPH
            if mt >= 1:
                self.cur, self.nxt = self.nxt, (self.nxt + 1) % len(self.shapes)
                self.morph_t, mt = None, None
                self.next_morph = now + random.uniform(8, 12)
                self.particles.burst(self.cx, self.cy, 40, (CYAN, PINK, WHITE), speed=18)
        cyw, syw = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        pts = []
        src_v = self.shapes[self.cur]
        if mt is None:
            for (x, y, z, kind, dup) in src_v:
                if dup:
                    continue
                x, z = x * cyw + z * syw, -x * syw + z * cyw
                y, z = y * cp - z * sp, y * sp + z * cp
                pts.append((z, x * cr - y * sr, x * sr + y * cr, kind, 0.0))
        else:
            dst_v = self.shapes[self.nxt]
            delay, swirl = self.delay, self.swirl
            for i, (a_, b_) in enumerate(zip(src_v, dst_v)):
                # each voxel leaves on a top-down sweep, dissolves into a particle that spirals
                # through the light cone, then condenses into its new place
                q = (mt * 1.55 - delay[i] - (a_[1] + 8) / 16 * 0.35) / 0.8
                q = 0.0 if q < 0 else 1.0 if q > 1 else q
                if (a_[4] and q < 0.5) or (b_[4] and q >= 0.5):
                    continue
                e = q * q * (3 - 2 * q)
                arc = math.sin(q * math.pi)
                x = a_[0] + (b_[0] - a_[0]) * e
                y = a_[1] + (b_[1] - a_[1]) * e + arc * 1.5
                z = a_[2] + (b_[2] - a_[2]) * e
                ang = arc * swirl[i] * 1.6
                ca, sa = math.cos(ang), math.sin(ang)
                spread = 1 + arc * 0.35
                x, z = (x * ca + z * sa) * spread, (-x * sa + z * ca) * spread
                x, z = x * cyw + z * syw, -x * syw + z * cyw
                y, z = y * cp - z * sp, y * sp + z * cp
                pts.append((z, x * cr - y * sr, x * sr + y * cr, a_[3] if q < 0.5 else b_[3], arc))
        pts.sort(key=lambda t: -t[0])
        self.nvox = len(pts)
        flick = 0.85 + 0.15 * random.random() + 0.2 * self.bump
        if random.random() < 0.03:
            flick *= 0.55                                  # brief brown-out of the emitter
        self.flick_hist = self.flick_hist[1:] + [flick]
        W, PH = s.w, s.ph
        hb = [None] * PH
        bw, bph = self.bw, self.bph
        hx, hy = bw // 2, bph // 2
        kz = self.zoom
        cx0, cy0 = self.cx, self.cy
        pal = self.voxel_palette
        mask_weight = (1.0 if self.cur == 1 else 0.0) if mt is None else (
            (1 - mt) * (self.cur == 1) + mt * (self.nxt == 1))
        face_palette = self.mask_palette[round(mask_weight * 16)]
        ghosts = []
        tear = {}
        for Z, X, Y, kind, arc in pts:
            k = D / max(1.0, D + Z) * kz
            sx = int(cx0 + X * 2 * k)
            spy = int((cy0 + Y * k) * 2)
            if glitch:
                band = spy >> 2
                if band not in tear:
                    tear[band] = random.randint(-2, 2) if random.random() < 0.18 else 0
                sx += tear[band]
            if arc > 0.08:
                # dissolved: a single bright mote with a faint wake
                if random.random() < arc * 0.25 or not (0 <= sx < W and 1 <= spy < PH):
                    continue
                col = blend(CYAN, WHITE, random.random() * 0.8) if random.random() < 0.75 else blend(PINK, WHITE, 0.3)
                row = hb[spy]
                if row is None:
                    row = hb[spy] = [None] * W
                row[sx] = col
                row = hb[spy - 1]
                if row is None:
                    row = hb[spy - 1] = [None] * W
                if row[sx] is None:
                    row[sx] = blend(col, BLACK, 0.6)
                continue
            light = (0.88 - Z / 55) * flick
            index = max(0, min(15, int(light * 12)))
            col = pal[min(2, kind)][index]
            # A low-light mask plate supports the luminous X eyes and grille.
            # Solid front faces share a surface; beveling every voxel used to
            # turn the eyes/jaw into an unreadable masonry grid.
            if kind == 1:
                col = face_palette[index]
            if kind == 2:
                col = self.accent_palette[index]
            hi, lo, ghost = self.voxel_shading[col]
            x0, y0 = sx - hx, spy - hy
            for py in range(max(0, y0), min(PH, y0 + bph)):
                row = hb[py]
                if row is None:
                    row = hb[py] = [None] * W
                c = hi if kind == 0 and py == y0 else col
                left, right = max(0, x0), min(W, x0 + bw)
                if left < right:
                    row[left:right] = [c] * (right - left)
                    if kind == 0 and right == x0 + bw:
                        row[right - 1] = lo
            if len(ghosts) < 260 and kind != 0 and 0 <= sx < W and 0 <= spy < PH:
                ghosts.append((sx, spy, ghost))
        self.ghosts = ghosts
        # composite: translucent, scanlined, with a rolling bright interference line
        scan = int(now * 16)
        roll_line = int((now * 9) % (PH + 20)) - 10
        chs = s.ch
        for py in range(PH):
            row = hb[py]
            if row is None:
                continue
            ph_ = (py + scan) % 4
            a = 0.68 if ph_ == 0 else 0.90
            if abs(py - roll_line) < 2:
                a = 1.0
            a *= min(1.0, flick)
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            crow = chs[py >> 1]
            for x in [i for i, c in enumerate(row) if c is not None]:
                c = row[x]
                b = layer[x] or BLACK
                if abs(py - roll_line) < 2:
                    c = blend(c, WHITE, 0.22)
                layer[x] = (int(b[0] + (c[0] - b[0]) * a), int(b[1] + (c[1] - b[1]) * a), int(b[2] + (c[2] - b[2]) * a))
                crow[x] = " "

        self.ring(s, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, True, D, now=now)
        self.ring(s, 16, 0.4, -now * 0.2, PURPLE, True, D, dots=2, now=now)

        # wireframe satellites, kept inside the space between the panels
        orbit = 19 if self.panel_w else 17
        for i, ((verts, edges), ph, sp_) in enumerate(self.sats):
            a = now * sp_ + ph
            c = rot((math.cos(a) * orbit, math.sin(a * 1.3) * 4, math.sin(a) * orbit), 0.25, 0)
            x, y, z = self.project(*c, D)
            size = 2.0 * self.zoom * (1.2 if z < 0 else 0.8)
            for va, vb in edges:
                pa = rot(verts[va], now * 1.3, now * 0.9 + i)
                pb = rot(verts[vb], now * 1.3, now * 0.9 + i)
                s.line(int(x + pa[0] * size * 2), int(y + pa[1] * size), int(x + pb[0] * size * 2), int(y + pb[1] * size),
                       "·", YELLOW if z < 0 else blend(YELLOW, BLACK, 0.6))

        self.particles.step(s, dt)

        if self.panel_w:
            self.draw_library(s, now, mt)
            self.draw_telemetry(s, now, D, yaw, flick)
        s.text(2, 0, "HOLO-PROJECTOR // " + SHAPE_NAMES[self.cur], CYAN)
        s.text(2, 1, "VOXELS %d   YAW %03d°   FOCAL %3dmm" % (self.nvox, math.degrees(yaw) % 360, D), GREY)
        if mt is not None:
            bar = int(mt * 16)
            msg = "MORPH > %s  %s%s %3d%%" % (SHAPE_NAMES[self.nxt], "▓" * bar, "░" * (16 - bar), mt * 100)
            s.center(2, msg, PINK if int(now * 8) % 2 else YELLOW)
        st = "● TRANSMITTING" if int(now * 2) % 2 else "○ TRANSMITTING"
        s.text(self.w - len(st) - 2, 0, st, PINK)
        s.center(self.h - 2, "> WE ARE DEDSEC. WE SEE EVERYTHING. <", blend(PINK, WHITE, pulse(now, 3) * 0.5))
        self.backfill(s)
        # Interference belongs to the projected voxels (the bounded tear above).
        # Keep the room and telemetry stable so the emitter reads as a physical
        # object, and never cover an entire face with opaque CRT colour bands.

    @staticmethod
    def backfill(s):
        """Text cells take the colour of the pixels beneath, so glyphs don't punch black holes."""
        for y in range(s.h):
            rc = s.ch[y]
            if rc.count(" ") == s.w:
                continue
            rb, rt, rp = s.bg[y], s.pt[y], s.pb[y]
            for x in [i for i, c in enumerate(rc) if c != " "]:
                if rb[x] is None:
                    p = rt[x] or rp[x]
                    if p is not None:
                        rb[x] = p

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "scan", "PROJECTOR // VOXELS RECALLED", CYAN)
        if t >= 1:
            return
        # Projected particles are sucked into the emitter before its final blink.
        if t < 0.85:
            for i in range(48):
                a = i * 2.39996 + t * 5
                radius = (1 - t) ** 2 * min(s.w / 3, s.h)
                x = s.w / 2 + math.cos(a) * radius * 2
                y = s.h * 0.7 + math.sin(a) * radius * 0.5
                s.pixel(int(x), int(y * 2), blend(CYAN, WHITE, i % 3 / 4))
        else:
            s.put(s.w // 2, int(s.h * 0.7), "·", blend(CYAN, BLACK, t))

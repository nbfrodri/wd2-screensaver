"""DEDSEC: skull + logo that assembles, explodes and reassembles, surrounded by chaos."""

import math
import random
import time

from lib import (BLACK, CYAN, DIM_PINK, GREEN, GREY, NEON, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, Rain, Typer, blend, ease_out, line_points, overlaps, pulse)
from sysdata import DATA
from engine3d import Floor
from widgets import Panels, Particles, PostFX, Sticker, Ticker

NAME = "DEDSEC"

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

FONT = {
    "D": ["█████ ", "██  ██", "██  ██", "██  ██", "█████ "],
    "E": ["██████", "██    ", "█████ ", "██    ", "██████"],
    "S": [" █████", "██    ", " ████ ", "    ██", "█████ "],
    "C": [" █████", "██    ", "██    ", "██    ", " █████"],
}

TAGLINES = [
    "WE ARE DEDSEC. WE ARE LEGION.", "ctOS 2.0 HAS BEEN COMPROMISED", "HACK THE PLANET",
    "INFORMATION SHOULD BE FREE", "BLUME IS WATCHING. WE WATCH BACK.", "JOIN US.",
    "YOUR DATA. YOUR RULES.", "NO MORE SECRETS",
]
NEWS = [
    "#DEDSEC trends worldwide for the 3rd day", "Blume stock drops 14% after ctOS outage",
    "Mysterious skull logo appears on every billboard in SF", "Nudle CEO: 'we take privacy very seriously'",
    "Invite Only party crashed by unknown hacker group", "#HACKTHEPLANET", "Police baffled by dancing traffic lights",
    "Tidis Bank ATMs dispense cat pictures", "#JOINUS", "Oakland goes dark for 7 minutes",
]
STICKERS = ["#DEDSEC", "(⌐■_■)", "[x_x]", "\\(^o^)/", "HACK THE\n PLANET", "<3 ctOS", "▓▓ JOIN US ▓▓"]


# ------------------------------------------------------------------ graffiti tags (pixel art)
TAG_FONT = {
    "D": ["XX.", "X.X", "X.X", "X.X", "XX."],
    "E": ["XXX", "X..", "XX.", "X..", "XXX"],
    "S": [".XX", "X..", ".X.", "..X", "XX."],
    "C": [".XX", "X..", "X..", "X..", ".XX"],
    "#": ["X.X", "XXX", "X.X", "XXX", "X.X"],
}


def tag_text(*lines):
    out = []
    for i, word in enumerate(lines):
        rows = [""] * 5
        for ch in word:
            for r in range(5):
                rows[r] += TAG_FONT[ch][r] + "."
        rows = [r[:-1] for r in rows]
        if i:
            out.append("")
        out += rows
    wid = max(len(r) for r in out)
    return [r.center(wid, ".") for r in out]


TAGS = [
    ["..XXXXXXX..", ".XXXXXXXXX.", "XXXXXXXXXXX", "XX...X...XX", "XX...X...XX", "XXXXX.XXXXX",
     ".XXXX.XXXX.", "..XXXXXXX..", "..X.X.X.X..", "..XXXXXXX.."],                     # skull
    ["X....X....X", "XX..XXX..XX", "XXX.XXX.XXX", "XXXXXXXXXXX", "XXXXXXXXXXX", "X.X.X.X.X.X",
     "XXXXXXXXXXX"],                                                                    # crown
    ["......X....", "......XX...", "XXXXXXXXX..", "XXXXXXXXXX.", "XXXXXXXXX..", "......XX...",
     "......X...."],                                                                    # arrow
    [".XX...XX.", "XXXX.XXXX", "XXXXXXXXX", "XXXXXXXXX", ".XXXXXXX.", "..XXXXX..", "...XXX...",
     "....X...."],                                                                      # heart
    tag_text("#DED", "SEC"),
    tag_text("DED", "SEC"),
]
TAG_COLORS = [(PINK, PURPLE), (CYAN, PURPLE), (YELLOW, ORANGE), (GREEN, CYAN), (PINK, YELLOW)]


class Graffiti:
    """A spray can that paints a tag pixel by pixel, lets it drip, then it flakes away."""

    def __init__(self, region, panels):
        self.region, self.panels = region, panels
        self.state, self.t = "wait", time.time() + random.uniform(1.5, 6)
        self.paint, self.queue, self.drips, self.keep = {}, [], [], None
        self.emitter = None

    def start(self, now):
        x0, y0, x1, y1 = self.region
        rw, rh = x1 - x0, y1 - y0
        art = random.choice(TAGS)
        aw, ah = len(art[0]), len(art)
        k = min(3, rw // (aw + 2), (rh - 8) // ah)
        if k < 1:
            art = TAGS[2] if aw > 11 else art
            aw, ah = len(art[0]), len(art)
            k = min(rw // (aw + 1), (rh - 6) // ah)
            if k < 1:
                self.t = now + 5
                return
        pw, ph = aw * k, ah * k
        for _ in range(25):
            ox = random.randint(x0, max(x0, x1 - pw))
            oy = random.randint(y0, max(y0, y1 - ph - 6))
            rect = (ox - 1, oy // 2 - 1, pw + 2, (ph + 6) // 2 + 2)
            if not any(overlaps(rect, p["r"], 0) for p in self.panels.items):
                break
        else:
            self.t = now + 2
            return
        self.keep = rect
        self.panels.keepout.append(rect)
        c1, c2 = random.choice(TAG_COLORS)
        outline = random.choice((WHITE, (25, 5, 40), YELLOW if c1 is not YELLOW else WHITE))
        fill, order = set(), []
        for r in range(ah):
            cols = range(aw) if r % 2 == 0 else range(aw - 1, -1, -1)
            for c in cols:
                if art[r][c] == "X":
                    col = blend(c1, c2, r / max(1, ah - 1))
                    for j in range(k):
                        for i in (range(k) if r % 2 == 0 else range(k - 1, -1, -1)):
                            p = (ox + c * k + i, oy + r * k + j)
                            fill.add(p)
                            order.append((p, col))
        edge = []
        for (x, y) in fill:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)):
                q = (x + dx, y + dy)
                if q not in fill:
                    edge.append(q)
        edge = sorted(set(edge), key=lambda q: (q[1], q[0] if q[1] % 2 else -q[0]))
        self.queue = order + [(q, outline) for q in edge]
        self.rate = len(self.queue) / random.uniform(2.2, 3.4)
        self.done = 0.0
        self.paint, self.drips = {}, []
        self.bottom = [(x, y) for (x, y) in fill if (x, y + 1) not in fill]
        self.state, self.t = "paint", now

    def finish(self):
        if self.keep in self.panels.keepout:
            self.panels.keepout.remove(self.keep)
        self.keep = None

    def update(self, s, now, dt, particles, sky):
        if self.state == "wait":
            if now > self.t:
                self.start(now)
            return
        if self.state == "paint":
            self.done += self.rate * dt
            n = min(len(self.queue), int(self.done))
            paint = self.paint
            for (p, col) in self.queue[:n]:
                paint[p] = (col, random.random())
                if random.random() < 0.07:   # overspray specks
                    q = (p[0] + random.randint(-2, 2), p[1] + random.randint(-2, 2))
                    if q not in paint:
                        paint[q] = (blend(col, BLACK, 0.55), random.random())
            if n:
                self.emitter = self.queue[n - 1]
                del self.queue[:n]
                self.done -= n
            if not self.queue:
                self.state, self.t = "hold", now
                self.emitter = None
                for (x, y) in random.sample(self.bottom, min(len(self.bottom), max(2, len(self.bottom) // 5))):
                    col = paint[(x, y)][0] if (x, y) in paint else PINK
                    self.drips.append([x, y + 1, 0.0, random.uniform(2, 9), random.uniform(2, 6), blend(col, BLACK, 0.2)])
        elif self.state == "hold":
            if now - self.t > 7:
                self.state, self.t = "fade", now
        elif self.state == "fade" and now - self.t > 2.5:
            self.state, self.t = "wait", now + random.uniform(3, 9)
            self.paint, self.drips = {}, []
            self.finish()
            return
        for d in self.drips:
            d[2] = min(d[3], d[2] + d[4] * dt)
        fade = (now - self.t) / 2.5 if self.state == "fade" else 0.0
        chs, pts, pbs = s.ch, s.pt, s.pb
        w, h = s.w, s.h
        for (x, py), (col, rnd) in self.paint.items():
            if rnd < fade or not (0 <= x < w and 0 <= py < 2 * h):
                continue
            if fade:
                col = blend(col, sky[py >> 1], fade * 0.6)
            chs[py >> 1][x] = " "
            (pbs if py & 1 else pts)[py >> 1][x] = col
        for (x, y, ln, _, _, col) in self.drips:
            if fade and (x * 7 + y) % 10 < fade * 12:
                continue
            for k in range(int(ln) + 1):
                s.pixel(x, y + k, col if k < int(ln) else blend(col, WHITE, 0.3))
                if 0 <= y + k < 2 * h and 0 <= x < w:
                    chs[(y + k) >> 1][x] = " "
        if self.emitter:
            (ex, ey), col = self.emitter
            cy = ey / 2
            s.put(ex + 1, int(cy) - 1, "▐", GREY)
            s.put(ex + 2, int(cy) - 1, "█", blend(col, BLACK, 0.3))
            s.put(ex + 2, int(cy) - 2, "▄", GREY)
            for _ in range(3):
                particles.add(ex + random.uniform(-1, 1), cy + random.uniform(-0.5, 0.5), random.uniform(-6, 6),
                              random.uniform(-3, 3), random.uniform(0.15, 0.4), "·•", blend(col, WHITE, 0.3))


def build_word(word, scale):
    rows = [""] * 5
    for letter in word:
        for i, line in enumerate(FONT[letter]):
            rows[i] += "".join(c * scale for c in line) + " " * scale
    return rows


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rain = Rain(w, h, step=6)
        self.glitch = Glitch(0.015)
        self.typer = Typer(TAGLINES)
        self.fx = PostFX()
        self.particles = Particles()
        self.ticker = Ticker("DEDSEC NEWS", NEWS)
        self.stickers = [Sticker(w, h, random.choice(STICKERS)) for _ in range(2 if w > 120 else 1)]
        self.frame = 0
        self.last = time.time()
        self.followers = random.randint(1200, 4800)

        scale = 2 if w >= 100 else 1
        word = build_word("DEDSEC", scale)
        skull = ["".join(("█" if p == "X" else " ") * scale for p in row) for row in SKULL]
        show_skull = h >= len(skull) + len(word) + 16
        total = len(word) + 8 + (len(skull) + 2 if show_skull else 0)
        top = max(3, (h - total) // 2)
        self.box = (0, top - 1, 0, total + 2)

        # every filled cell of the logo becomes a "fragment" that can fly around
        self.cells = []
        y = top
        if show_skull:
            left = (w - len(skull[0])) // 2
            for r, row in enumerate(skull):
                for c, ch in enumerate(row):
                    if ch != " ":
                        self.cells.append((left + c, y + r, ch, "skull"))
            y += len(skull) + 2
        self.word_top = y
        left = (w - len(word[0])) // 2
        self.word_left, self.word_w = left, len(word[0])
        for r, row in enumerate(word):
            for c, ch in enumerate(row):
                if ch != " ":
                    self.cells.append((left + c, y + r, ch, "word"))
        self.tag_y = y + len(word) + 3
        bw = max(len(word[0]), len(skull[0]) if show_skull else 0, 44) + 10
        self.box = ((w - bw) // 2, top - 1, bw, total + 2)
        self.center = (w / 2, top + total / 2)
        self.orbit = (bw / 2 + 4, total / 2 + 2)
        self.panels = Panels(w, h, keepout=[self.box], max_panels=7)
        self.floor = Floor(w, h, horizon=min(0.85, (self.tag_y + 2) / h), color=PURPLE)

        bottom_drips = [c for c in self.cells if c[3] == "word" and c[1] == y + len(word) - 1]
        self.drips = [{"x": c[0], "y": c[1] + 1, "len": 0.0, "max": random.randint(1, 3),
                       "speed": random.uniform(0.6, 2.0)} for c in bottom_drips if random.random() < 0.2]

        # synthwave sky + sun sitting on the horizon behind the logo
        self.hz = hz = int(self.floor.cam.cy)
        self.sky_top, self.sky_bot = (10, 2, 22), (70, 12, 70)
        self.sky = [blend(self.sky_top, self.sky_bot, y / max(1, hz)) for y in range(hz + 1)] + [None] * (h - hz)
        self.sky_rows = [[c] * w for c in self.sky[:hz + 1]]
        r = max(8.0, min((hz - top + 1) * 2 * 0.95, bw * 0.46))
        self.sun = (w / 2, 2 * hz - r * 0.22, r)
        cx, cy, r = self.sun
        self.sun_rows = []
        for py in range(max(0, int(cy - r)), min(2 * hz, int(cy + r) + 1)):
            dy = py - cy
            if dy * dy > r * r:
                continue
            span = math.sqrt(r * r - dy * dy)
            v = (py - (cy - r)) / (2 * r)
            col = blend(PINK, ORANGE, v / 0.45) if v < 0.45 else blend(ORANGE, YELLOW, (v - 0.45) / 0.4)
            self.sun_rows.append((py, max(0, int(cx - span)), min(w, int(cx + span) + 1), v, col))
        # halo around the sun, baked into the sky background
        for y in range(hz + 1):
            row = self.sky_rows[y]
            for x in range(w):
                d = math.hypot((x - cx), (2 * y + 1 - cy)) - r
                if 0 < d < r * 0.35:
                    row[x] = blend(row[x], (150, 20, 90), 0.35 * (1 - d / (r * 0.35)) ** 2)
        # Thin horizontal haze follows sky altitude; stars live above the sun.
        for y, row in enumerate(self.sky_rows):
            for x in range(w):
                if y < hz*.48 and (x*73+y*151)%433 == 0:
                    row[x] = (83, 68, 115)
                elif y > hz*.45:
                    k = .05*(.5+.5*math.sin(x*.045 + y*.73))
                    row[x] = blend(row[x], (160, 43, 100), k)
        self.sun_t = 0.0
        self.cut = (2 * self.tag_y - 1, 2 * self.tag_y + 3)
        self.plate = (2 * self.word_top - 2, 2 * (self.word_top + 5) + 1, self.word_left - 4, self.word_left + self.word_w + 2)

        # graffiti walls on both sides of the logo
        gy0, gy1 = 7, 2 * hz - 3
        regions = [(2, gy0, bx0 - 2, gy1) for bx0 in [self.box[0]]] + \
                  [(self.box[0] + self.box[2] + 2, gy0, w - 3, gy1)]
        self.graffiti = [Graffiti(rg, self.panels) for rg in regions if rg[2] - rg[0] >= 12 and rg[3] - rg[1] >= 14]

        self.bolt = None
        self.next_bolt = time.time() + random.uniform(4, 10)
        self.flash = 0.0
        self.orb_t = self.floor_t = 0.0
        self.bump = 0.0
        self.start_assembly(time.time())

    # ------------------------------------------------------------ sky, sun, lightning
    def draw_sky(self, s):
        f = self.flash
        hz = self.hz
        if f > 0.02:
            for y in range(hz + 1):
                s.bg[y] = [blend(c, (200, 170, 255), f * 0.55) for c in self.sky_rows[y]]
        else:
            for y in range(hz + 1):
                s.bg[y] = self.sky_rows[y][:]

    def draw_sun(self, s, now):
        glow = 0.8 + 0.15 * self.bump + 0.08 * DATA.level + 0.3 * self.flash
        scroll = self.sun_t
        for (py, x0, x1, v, col) in self.sun_rows:
            if self.cut[0] <= py < self.cut[1]:
                continue
            if v > 0.42:
                gap = 0.7 + (v - 0.42) * 7.5
                if (py + scroll) % 7 < gap:
                    continue
            c = (int(col[0] * glow), int(col[1] * glow), int(col[2] * glow)) if glow < 1 else blend(col, WHITE, glow - 1)
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            if self.plate[0] <= py < self.plate[1]:
                # dark banner behind the word keeps DEDSEC readable over the sun
                d = (c[0] // 6 + 14, c[1] // 10, c[2] // 5 + 28)
                p0, p1 = max(x0, self.plate[2]), min(x1, self.plate[3])
                if p1 > p0:
                    layer[x0:x1] = [c] * (p0 - x0) + [d] * (p1 - p0) + [c] * (x1 - p1)
                    continue
            layer[x0:x1] = [c] * (x1 - x0)

    def make_bolt(self, now):
        w, hzp = self.w, 2 * self.hz
        x, y = random.uniform(w * 0.06, w * 0.94), 0.0
        end = hzp * random.uniform(0.55, 1.0)
        main, branches = [(x, y)], []
        while y < end:
            y += random.uniform(1.5, 5)
            x += random.choice((-1, 1)) * random.uniform(1.5, 5)
            main.append((x, min(y, end)))
            if random.random() < 0.2 and len(branches) < 5:
                bx, by, d = x, y, random.choice((-1, 1))
                br = [(bx, by)]
                for _ in range(random.randint(3, 8)):
                    by += random.uniform(1, 3.5)
                    bx += d * random.uniform(0.5, 4.5)
                    br.append((bx, by))
                branches.append(br)
        self.bolt = {"t": now, "main": main, "br": branches}
        if end >= hzp * 0.93:
            self.particles.burst(x, self.hz, 30, (WHITE, CYAN, PURPLE), speed=14, gravity=8)

    def draw_bolt(self, s, now, clip=None):
        b = self.bolt
        age = now - b["t"]
        if age < 0.07 or 0.13 < age < 0.5:
            fade = 1 - max(0.0, age - 0.13) / 0.37
            core = blend((150, 120, 255), WHITE, fade)
            halo = blend((25, 5, 45), (150, 60, 255), fade)
            for path, c, hc in ((b["main"], core, halo), *((br, blend(core, PURPLE, 0.4), None) for br in b["br"])):
                for (ax, ay), (bx, by) in zip(path, path[1:]):
                    for (x, y) in line_points(int(ax), int(ay), int(bx), int(by)):
                        if clip and not (clip[0] <= x < clip[1] and clip[2] <= y < clip[3]):
                            continue
                        if hc:
                            s.pixel(x - 1, y, hc)
                            s.pixel(x + 1, y, hc)
                        s.pixel(x, y, c)

    def set_view(self, now):
        yaw = math.sin(now * 0.45) * 0.75
        pitch = math.sin(now * 0.31) * 0.25
        self.rot = (math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch))
        self.yaw = yaw

    def proj(self, x, y, z):
        """Rotate a logo cell (screen coords + depth) around the logo centre."""
        cx, cy = self.center
        cyw, syw, cp, sp = self.rot
        X, Y, Z = (x - cx) * 0.5, y - cy, z
        X, Z = X * cyw + Z * syw, -X * syw + Z * cyw
        Y, Z = Y * cp - Z * sp, Y * sp + Z * cp
        k = 70 / (70 + Z) * (1 + 0.035 * self.bump)
        return int(cx + X * 2 * k), int(cy + Y * k)

    def draw_logo(self, s, cells, now, glitch):
        cx, cy = self.center
        cyw, syw, cp, sp = self.rot
        bump = 1 + 0.035 * self.bump
        # rotate every cell once; depth offsets are linear in z
        dX, dY, dZ = syw, -cyw * sp, cyw * cp
        base = []
        for (x, y, ch, kind) in cells:
            X = (x - cx) * 0.5
            Y = y - cy
            Z1 = -X * syw
            base.append((X * cyw, Y * cp - Z1 * sp, Y * sp + Z1 * cp))
        W, H = s.w, s.h
        chs, fgs = s.ch, s.fg
        # extrusion: back layers first, dark, then the lit front face
        for depth in (4, 3, 2, 1):
            shade = 0.45 + depth * 0.1
            cw, cs = blend(PURPLE, BLACK, shade), blend(GREY, BLACK, shade)
            ox, oy, oz = dX * depth, dY * depth, dZ * depth
            for (X, Y, Z), cell in zip(base, cells):
                k = 70 / (70 + Z + oz) * bump
                px, py = int(cx + (X + ox) * 2 * k), int(cy + (Y + oy) * k)
                if 0 <= px < W and 0 <= py < H:
                    chs[py][px] = "█"
                    fgs[py][px] = cw if cell[3] == "word" else cs
        front = []
        for (X, Y, Z) in base:
            k = 70 / (70 + Z) * bump
            front.append((int(cx + X * 2 * k), int(cy + Y * k)))
        offsets = {}
        if glitch:
            for (x, y, ch, kind), (px, py) in zip(cells, front):
                if y not in offsets:
                    offsets[y] = random.randint(-5, 5) if random.random() < 0.3 else 0
                s.put(px - 2 + offsets[y], py, ch, CYAN)
                s.put(px + 2 + offsets[y], py, ch, PINK)
        light = 0.55 + 0.45 * (0.5 + 0.5 * math.cos(self.yaw * 2))
        rows = {}
        shine = ((now * 60) % (self.w + 80)) - 40
        sx0 = self.w // 2 - self.word_w // 2
        for (x, y, ch, kind), (px, py) in zip(cells, front):
            key = (y, kind)
            col = rows.get(key)
            if col is None:
                col = rows[key] = self.color(x, y, kind, now, False, shine=False)
            grain = (x * 17 + y * 31) % 29
            if grain < 3:
                col = blend(col, (45,12,54), .26)
            elif grain == 8:
                col = blend(col, WHITE, .25)
            d = abs((x - sx0) - shine + (y - self.word_top) * 3)
            if d < 6:
                col = blend(col, WHITE, 1 - d / 6)
            if glitch and random.random() < 0.05:
                col = YELLOW
            px += offsets.get(y, 0)
            if 0 <= px < W and 0 <= py < H:
                chs[py][px] = ch
                fgs[py][px] = (int(col[0] * light), int(col[1] * light), int(col[2] * light))

    def start_assembly(self, now):
        self.phase, self.phase_t = "in", now
        self.starts = [(random.uniform(-20, self.w + 20), random.uniform(-10, self.h + 10), random.uniform(-60, 40)) for _ in self.cells]

    def explode(self, now):
        cx, cy = self.center
        for (x0, y0, ch, kind) in self.cells:
            x, y = self.proj(x0, y0, 0)
            a = math.atan2(y - cy, (x - cx) / 2) + random.uniform(-0.4, 0.4)
            v = random.uniform(10, 40)
            self.particles.add(x, y, math.cos(a) * v * 2, math.sin(a) * v, random.uniform(0.6, 1.6),
                               ch if random.random() < 0.6 else "▓▒░", PINK if kind == "word" else WHITE, gravity=6)
        self.phase, self.phase_t = "gone", now
        self.glitch.trigger(now, 0.4)

    def color(self, x, y, kind, now, glitch, shine=True):
        base = blend(WHITE, PINK, pulse(now) * 0.6) if kind == "skull" else blend(PINK, PURPLE, (y - self.word_top) / 5)
        # Screen-printed face: bevel highlights, worn pigment, and inset scratches.
        grain = (x * 17 + y * 31) % 29
        if grain < 3:
            base = blend(base, (45, 12, 54), .26)
        elif grain == 8:
            base = blend(base, WHITE, .25)
        if y == self.word_top:
            base = blend(base, WHITE, .35)
        if shine:
            shine = ((now * 60) % (self.w + 80)) - 40
            d = abs((x - self.w // 2 + self.word_w // 2) - shine + (y - self.word_top) * 3)
            if d < 6:
                base = blend(base, WHITE, 1 - d / 6)
        if self.bump > 0.05:
            base = blend(base, WHITE, self.bump * 0.35)
        if glitch and random.random() < 0.05:
            base = YELLOW
        return base

    def draw_orbit(self, s, now, front):
        cx, cy = self.center
        rx, ry = self.orbit
        for i in range(5):
            sp = 0.6 + i * 0.17
            for k in range(8):
                a = self.orb_t * sp + i * 1.26 - k * 0.05
                if (math.sin(a) > 0) != front:
                    continue
                x = cx + math.cos(a) * rx * (1 + 0.08 * i)
                y = cy + math.sin(a) * ry * (1 + 0.05 * i) * math.cos(now * 0.2 + i)
                col = blend(NEON[i % len(NEON)], BLACK, k / 8 + (0 if front else 0.4))
                s.put(int(x), int(y), "●" if k == 0 else "•" if k < 3 else "·", col)

    def draw_hud(self, s, now):
        w, h = self.w, self.h
        s.text(2, 0, "▌ctOS 2.0 // SAN FRANCISCO", CYAN)
        s.text(2, 1, "▌NODE 0x%04X  //  %s" % ((self.frame * 7) & 0xFFFF, time.strftime("%H:%M:%S")), GREY)
        status = "● DEDSEC NETWORK ONLINE"
        s.text(w - len(status) - 2, 0, status, PINK if int(now * 2) % 2 == 0 else DIM_PINK)
        if self.frame % 4 == 0 and random.random() < 0.6:
            self.followers += random.randint(1, 37)
        fol = "FOLLOWERS: {:,}".format(self.followers)
        s.text(w - len(fol) - 2, 1, fol, YELLOW)
        # threat meter
        lvl = int(pulse(now, 0.8) * 10)
        meter = "THREAT " + "".join("▰" if i < lvl else "▱" for i in range(10))
        s.text((w - len(meter)) // 2, 0, meter, blend(YELLOW, PINK, lvl / 10))

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "spray", "DEDSEC / PAINT CLEARED", PINK)

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        beat, level = DATA.beat, DATA.level
        self.bump = max(beat, self.bump - dt * 4)
        self.orb_t += dt * (0.8 + 1.4 * level + 1.5 * self.bump)
        self.floor_t += dt * (3 + 9 * level)
        self.sun_t += dt * (3 + 4 * level)

        if self.bolt is None and now > self.next_bolt:
            self.make_bolt(now)
            self.glitch.trigger(now, 0.1)
        if self.bolt:
            age = now - self.bolt["t"]
            self.flash = max(0.0, 1 - age / 0.35) if (age < 0.07 or age > 0.13) else 0.25
            if age > 0.5:
                self.bolt, self.flash = None, 0.0
                self.next_bolt = now + random.uniform(5, 16)

        self.draw_sky(s)
        if self.bolt:
            self.draw_bolt(s, now)
        self.rain.draw(s)
        for g in self.graffiti:
            g.update(s, now, dt, self.particles, self.sky)
        for st in self.stickers:
            st.step(s, dt, self.particles)
        self.panels.draw(s, now)

        self.set_view(now)
        bx, by, bw, bh = self.box
        s.fill(bx, by, bw, bh)
        self.draw_sun(s, now)
        if self.bolt:
            self.draw_bolt(s, now, clip=(bx, bx + bw, 2 * by, 2 * (by + bh)))
        self.floor.draw(s, self.floor_t, speed=1, sway=math.sin(now * 0.3) * 0.05)
        self.draw_orbit(s, now, front=False)

        age = now - self.phase_t
        if self.phase == "in":
            t = ease_out(age / 1.6)
            for (x, y, ch, kind), (sx, sy, sz) in zip(self.cells, self.starts):
                px, py = self.proj(sx + (x - sx) * t, sy + (y - sy) * t, sz * (1 - t))
                s.put(px, py, ch, self.color(x, y, kind, now, glitch) if t > 0.95 else blend(CYAN, PINK, t))
            if age > 1.6:
                self.phase, self.phase_t = "hold", now
                self.particles.burst(self.center[0], self.center[1], 60, speed=25)
        elif self.phase == "hold":
            self.draw_logo(s, self.cells, now, glitch)
            for d in self.drips:
                d["len"] = min(d["max"], d["len"] + d["speed"] * dt)
                for k in range(int(d["len"])):
                    px, py = self.proj(d["x"], d["y"] + k, 0)
                    s.put(px, py, "█" if k < int(d["len"]) - 1 else "▀", PURPLE)
                if d["len"] >= d["max"] and random.random() < 0.01:
                    self.particles.add(d["x"], d["y"] + d["max"], 0, 4, 1.5, "•", PURPLE, gravity=10)
            if random.random() < 0.05:
                x, y = self.proj(*random.choice(self.cells)[:2], 0)
                self.particles.add(x, y, random.uniform(-6, 6), random.uniform(-6, -2), 0.8, "+*·", YELLOW)
            if age > 20:
                self.explode(now)
        elif age > 1.2:
            self.start_assembly(now)

        self.typer.draw(s, self.tag_y, now, glitch=glitch)
        self.draw_orbit(s, now, front=True)
        self.particles.step(s, dt)
        self.draw_hud(s, now)
        self.ticker.draw(s, self.h - 1, now)
        if self.flash > 0.6:
            for y in range(self.hz + 1):
                s.tint_row(y, WHITE, (self.flash - 0.6) * 0.5)
        self.fx.apply(s, now, glitch)
        self.frame += 1

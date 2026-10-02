"""DEDSEC: skull + logo that assembles, explodes and reassembles, surrounded by chaos."""

import math
import random
import time
from functools import lru_cache

from lib import (BLACK, CYAN, DIM_PINK, GREEN, GREY, NEON, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, Rain, Typer, blend, ease_out, line_points, overlaps, pulse)
from sysdata import DATA
from widgets import Panels, Particles, PostFX, Sticker, Ticker

NAME = "DEDSEC"

# Compatibility bitmap used by TOWER's finale; the logo uses make_skull().
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




@lru_cache(maxsize=32768)
def _tint(c, col, t):
    return blend(c, col, t)


def tint_row(s, y, color, t):
    """Cached-colour version of Screen.tint_row (the scan band runs every frame)."""
    if 0 <= y < s.h:
        for layer in (s.fg, s.pt, s.pb, s.bg):
            layer[y] = [None if c is None else _tint(c, color, t) for c in layer[y]]


def post_fx(s, now, glitch):
    """CRT scan band and row tearing, as widgets.PostFX but with cached blends."""
    span = s.h + 16
    by = int((now * 7.0) % span) - 8
    for k, t in ((0, 0.45), (-1, 0.25), (1, 0.25), (-2, 0.1)):
        tint_row(s, by + k, WHITE, t)
    if glitch:
        for _ in range(random.randint(2, 5)):
            y0 = random.randrange(s.h)
            dx = random.randint(-14, 14)
            for y in range(y0, min(s.h, y0 + random.randint(1, 4))):
                s.shift_row(y, dx)
                tint_row(s, y, random.choice((PINK, CYAN)), 0.5)
        if random.random() < 0.3:
            s.noise_lines(2)


def build_word(word, scale):
    rows = [""] * 5
    for letter in word:
        for i, line in enumerate(FONT[letter]):
            rows[i] += "".join(c * scale for c in line) + " " * scale
    return rows


# ------------------------------------------------------------------ the DedSec skull (pixel art)
# Palette indices: 0..7 bone shades (dark -> lit), 8 socket/void, 9 outline, 10 eye glow.
BONE = [blend((92, 62, 128), (252, 248, 255), i / 7) for i in range(8)]
SOCKET, OUTLINE, EYE = 8, 9, 10
SKULL_BASE = BONE + [(16, 3, 26), (6, 0, 12), PINK]


def make_skull(sw, sh):
    """Rasterise a crisp, front-facing stylised skull at any pixel size.

    Returns (u, v, index) with u in columns and v in half-block pixel rows.
    Built from simple shapes so it stays recognisable when small: domed
    cranium, cheekbones, angled eye sockets with glowing pupils, inverted-heart
    nasal cavity, two rows of teeth, and a DedSec crack across the crown.
    """
    def nxy(u, v):
        return (u + 0.5) / sw * 2 - 1, (v + 0.5) / sh * 2 - 1

    def solid(nx, ny):
        a = abs(nx)
        if ny <= 0.16 and (nx / 0.92) ** 2 + ((ny + 0.28) / 0.70) ** 2 <= 1:
            return True
        if -0.12 <= ny <= 0.42 and a <= 0.80 - 0.42 * max(0.0, ny - 0.05):
            return not (a > 0.70 and -0.02 < ny < 0.10)           # temple notch
        return (a / 0.52) ** 4 + ((ny - 0.62) / 0.36) ** 4 <= 1      # jaw

    def void(nx, ny):
        a = abs(nx)
        brow = -0.17 + 0.32 * (0.40 - a)
        if ((a - 0.37) / 0.25) ** 2 + ((ny - 0.05) / 0.21) ** 2 <= 1 and ny >= brow:
            return True                                              # eye socket
        if 0.17 <= ny <= 0.41 and a <= 0.02 + 0.13 * (ny - 0.17) / 0.24 and not (a < 0.025 and ny > 0.33):
            return True                                              # nose
        if a < 0.42 and 0.49 <= ny <= 0.82:
            mouth = 0.635 + 0.07 * nx * nx
            if abs(ny - mouth) < 0.035:
                return True
            if ((nx + 0.065) / 0.13) % 1.0 < 0.2 and abs(ny - mouth) < 0.14:
                return True                                          # tooth gaps
        return False

    grid = {}
    for v in range(sh):
        for u in range(sw):
            nx, ny = nxy(u, v)
            if solid(nx, ny):
                grid[(u, v)] = "v" if void(nx, ny) else "b"
    # crack running down the crown (pixel polyline)
    crack = [(0.20, -0.99), (0.10, -0.82), (0.24, -0.68), (0.13, -0.53), (0.21, -0.43)]
    for (ax, ay), (bx, by) in zip(crack, crack[1:]):
        for p in line_points(int((ax + 1) / 2 * sw), int((ay + 1) / 2 * sh), int((bx + 1) / 2 * sw), int((by + 1) / 2 * sh)):
            if p in grid:
                grid[p] = "v"
    out = []
    for v in range(sh):
        for u in range(sw):
            k = grid.get((u, v))
            nx, ny = nxy(u, v)
            if k is None:
                if any((u + du, v + dv) in grid for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out.append((u, v, OUTLINE))
                continue
            if k == "v":
                a = abs(nx)
                glow = ((a - 0.36) / 0.10) ** 2 + ((ny - 0.08) / 0.085) ** 2 <= 1
                out.append((u, v, EYE if glow and ny < 0.2 else SOCKET))
                continue
            lum = 0.80 - 0.22 * ny - 0.35 * max(0.0, abs(nx) - 0.55)
            up, down = grid.get((u, v - 1)), grid.get((u, v + 1))
            if up is None:
                lum += 0.22
            elif up == "v":
                lum += 0.12                                           # lit lower rim of a hole
            if down is None or down == "v":
                lum -= 0.28                                           # shadow under ledges
            if (u + 1, v) not in grid:
                lum -= 0.18
            if (u - 1, v) not in grid:
                lum += 0.08
            if 0.18 < ny < 0.42 and 0.42 < abs(nx) < 0.72:
                lum -= 0.16                                           # hollow under cheekbones
            out.append((u, v, max(0, min(7, int(lum * 7.99)))))
    return out


# ------------------------------------------------------------------ San Francisco skyline
def make_skyline(w, sky_px, seed=7):
    """Height map (pixels above horizon) plus thin structures and window lights."""
    rnd = random.Random(seed)
    hgt = [0] * w
    S = sky_px
    x = 0
    while x < w:                                    # low continuous city blocks
        bw = rnd.randint(2, 5)
        hh = rnd.randint(1, max(2, int(S * 0.07)))
        for i in range(x, min(w, x + bw)):
            hgt[i] = hh
        x += bw

    def bump(c, half, top):                         # rolling hills
        for i in range(max(0, int(c - half)), min(w, int(c + half) + 1)):
            t = (i - c) / half
            hgt[i] = max(hgt[i], int(top * max(0.0, 1 - t * t) ** 1.5))

    bump(w * 0.10, w * 0.10, S * 0.13)
    bump(w * 0.72, w * 0.06, S * 0.07)
    extra = []
    # downtown cluster
    for _ in range(int(w * 0.11)):
        c = rnd.gauss(0.45, 0.12) * w
        bw = rnd.randint(2, 5)
        top = int(S * rnd.uniform(0.08, 0.22) * max(0.35, 1 - abs(c / w - 0.45) * 2.2))
        for i in range(max(0, int(c)), min(w, int(c) + bw)):
            hgt[i] = max(hgt[i], top)
    # Transamerica pyramid
    tx, th = int(w * 0.30), int(S * 0.36)
    for i in range(-3, 4):
        if 0 <= tx + i < w:
            hgt[tx + i] = max(hgt[tx + i], int(th * (1 - abs(i) / 3.6)))
    extra += [(tx, -th - k) for k in range(1, max(2, int(S * 0.05)))]
    # Salesforce tower with its rounded crown
    sx, sh_ = int(w * 0.62), int(S * 0.40)
    for i, cut in zip(range(-3, 4), (3, 1, 0, 0, 0, 1, 3)):
        if 0 <= sx + i < w:
            hgt[sx + i] = max(hgt[sx + i], sh_ - cut)
    # Sutro tower on the hill
    ux = int(w * 0.10)
    base = hgt[ux] if 0 <= ux < w else 0
    mast = int(S * 0.20)
    for k in range(mast):
        spread = 2 if k > mast * 0.75 else (1 if k < mast * 0.3 else 0)
        for dx in {-spread, spread}:
            extra.append((ux + dx, -base - k))
    for dx in range(-2, 3):
        extra.append((ux + dx, -base - mast))
        extra.append((ux + dx, -base - int(mast * 0.75)))
    for dx in (-2, 0, 2):
        extra += [(ux + dx, -base - mast - 1), (ux + dx, -base - mast - 2)]
    # Golden Gate towers + cables on the far right
    gx0, gx1, deck = int(w * 0.83), int(w * 0.97), int(S * 0.06)
    tower = int(S * 0.26)
    for gx in (gx0, gx1):
        for k in range(tower):
            extra += [(gx - 1, -k), (gx + 1, -k)]
            if k % max(3, tower // 4) == 0 or k == tower - 1:
                extra.append((gx, -k))
    for i in range(int(w * 0.78), w):
        extra.append((i, -deck))
    span = max(1, gx1 - gx0)
    for i in range(gx0, gx1 + 1):
        t = (i - gx0) / span * 2 - 1
        cy = deck + 1 + (tower - deck - 1) * t * t
        extra.append((i, -int(cy)))
        if i % 3 == 0:
            for k in range(deck + 1, int(cy)):
                if k % 2 == 0:
                    extra.append((i, -k))
    for i in range(int(w * 0.78), gx0):
        t = (gx0 - i) / max(1, gx0 - int(w * 0.78))
        extra.append((i, -int(tower - (tower - deck) * t)))
    lights = []
    for i in range(w):
        for k in range(2, hgt[i] - 1):
            if rnd.random() < 0.06:
                lights.append((i, k, rnd.choice(((130, 90, 40), (150, 40, 110), (60, 110, 140))), rnd.random()))
    beacons = [(tx, th + max(2, int(S * 0.05))), (sx, sh_ + 1), (ux, base + mast + 3), (gx0, tower), (gx1, tower)]
    return hgt, extra, lights, beacons


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.glitch = Glitch(0.015)
        self.typer = Typer(TAGLINES)
        self.fx = PostFX()
        self.particles = Particles()
        self.ticker = Ticker("DEDSEC NEWS", NEWS)
        self.frame = 0
        self.last = time.time()
        self.followers = random.randint(1200, 4800)

        scale = 2 if w >= 100 else 1
        word = build_word("DEDSEC", scale)
        # vertical layout: skull + word sit in the sky, the horizon at ~60%
        sr = min(int(h * 0.36), max(6, int(h * 0.6) - 11))
        show_skull = sr >= 6 and w >= 60 and h >= 24
        sr = sr if show_skull else 0
        content = (sr + 1 if show_skull else 0) + 5 + 2
        hz = self.hz = max(int(h * 0.6), content + 4)
        top = max(3, hz - content)
        self.rain = Rain(w, hz, step=9)
        self.stickers = [Sticker(w, h, random.choice(STICKERS), bottom=h - hz + 1)] if w > 150 else []

        # every filled cell of the word becomes a "fragment" that can fly around
        self.cells = []
        self.skull = []
        sw = 0
        if show_skull:
            sh = 2 * sr
            sw = int(sh * 1.08) // 2 * 2
            left = (w - sw) // 2
            # (cell x, cell y, palette index, pixel u, v) for each skull pixel
            self.skull = [(left + u, top + v / 2, k) for (u, v, k) in make_skull(sw, sh)]
            self.skull_left, self.skull_top, self.skull_w = left, top, sw
            y = top + sr + 1
        else:
            y = top
        self.word_top = y
        left = (w - len(word[0])) // 2
        self.word_left, self.word_w = left, len(word[0])
        for r, row in enumerate(word):
            for c, ch in enumerate(row):
                if ch != " ":
                    self.cells.append((left + c, y + r, ch, "word"))
        self.tag_y = h - 3
        bw = max(len(word[0]), sw, 44) + 10
        self.box = ((w - bw) // 2, top - 1, bw, hz - top + 1)
        total = y + 5 - top
        self.center = (w / 2, top + total / 2)
        self.orbit = (bw / 2 + 4, total / 2 + 2)
        self.panels = Panels(w, h, keepout=[self.box], max_panels=4 if w > 150 else 3, bottom=h - hz + 1,
                             kinds=["spark", "eq", "wave", "decrypt", "loaders", "bars", "cam", "radar"])

        bottom_drips = [c for c in self.cells if c[1] == y + len(word) - 1]
        self.drips = [{"x": c[0], "y": c[1] + 1, "len": 0.0, "max": random.randint(1, 2),
                       "speed": random.uniform(0.6, 2.0)} for c in bottom_drips if random.random() < 0.2]

        # synthwave sky + sun sitting on the horizon behind the logo
        self.sky_top, self.sky_bot = (10, 2, 22), (78, 14, 76)
        self.sky = [blend(self.sky_top, self.sky_bot, (y / max(1, hz)) ** 1.4) for y in range(hz + 1)] + [None] * (h - hz)
        self.sky_rows = [[c] * w for c in self.sky[:hz + 1]]
        r = max(8.0, min(bw * 0.46, (hz - 2) * 2 * 0.8))
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
        self.sun_by_py = {row[0]: row for row in self.sun_rows}
        # halo around the sun, baked into the sky background
        for y in range(hz + 1):
            row = self.sky_rows[y]
            for x in range(w):
                d = math.hypot((x - cx), (2 * y + 1 - cy)) - r
                if 0 < d < r * 0.45:
                    row[x] = blend(row[x], (160, 24, 96), 0.4 * (1 - d / (r * 0.45)) ** 2)
        for y, row in enumerate(self.sky_rows):
            for x in range(w):
                if y < hz * .48 and (x * 73 + y * 151) % 433 == 0:
                    row[x] = (83, 68, 115)
                elif y > hz * .45:
                    k = .05 * (.5 + .5 * math.sin(x * .045 + y * .73))
                    row[x] = blend(row[x], (160, 43, 100), k)
        self.sun_t = 0.0
        self.plate = (2 * self.word_top - 2, 2 * (self.word_top + 5) + 1, self.word_left - 4, self.word_left + self.word_w + 2)

        self.build_floor()
        self.build_skyline()
        self.palms = []
        if w >= 120:
            hp = self.hp
            base = hp + int(self.dmax * 0.55)
            ph = min(base - int(hz * 0.85), int(h * 0.9))
            self.palms = [(w * 0.045, base, ph, 1), (w * 0.955, base, ph, -1)]
        self.palm_cache = {}
        self.cars = []
        self.word_front = []

        # graffiti walls on both sides of the logo
        gy0, gy1 = 7, 2 * hz - 3 - int(hz * 0.4)
        regions = [(2, gy0, self.box[0] - 2, gy1), (self.box[0] + self.box[2] + 2, gy0, w - 3, gy1)]
        self.graffiti = [Graffiti(rg, self.panels) for rg in regions if rg[2] - rg[0] >= 12 and rg[3] - rg[1] >= 14]

        self.bolt = None
        self.next_bolt = time.time() + random.uniform(4, 10)
        self.flash = 0.0
        self.orb_t = self.floor_t = 0.0
        self.bump = 0.0
        self.start_assembly(time.time())

    # ------------------------------------------------------------ floor: grid, reflections, cars
    def build_floor(self):
        w, h, hz = self.w, self.h, self.hz
        self.hp = hp = 2 * hz + 1                      # horizon pixel row
        self.pbot = pbot = 2 * (h - 1) - 1              # last floor pixel above the ticker
        self.dmax = dmax = max(2, pbot - hp)
        self.floor_bg = []
        for y in range(hz + 1, h):
            t = min(1.0, (2 * y + 1 - hp) / dmax)
            self.floor_bg.append([blend((46, 8, 54), (4, 0, 10), t ** 0.5)] * w)
        self.g = max(10.0, w / 6.5)                     # grid spacing at the bottom row
        self.zs = 4.0
        self.vcol, self.hcol, self.glow, self.vfar = [None], [None], [None], [None]
        for d in range(1, dmax + 1):
            u = d / dmax
            f = u ** 0.7
            # Keep the moving perspective legible without giving the floor
            # the same luminous weight as the face of the logo.
            self.vcol.append(blend((44, 10, 55), (158, 28, 132), f))
            self.hcol.append(blend((34, 9, 44), (104, 27, 103), f ** 0.8))
            self.glow.append(blend((26, 5, 34), (53, 10, 57), f))
            self.vfar.append(blend((30, 7, 40), (76, 17, 76), f))
        # floor row d -> colour of the floor background there (for reflections)
        self.fbg = [None] + [self.floor_bg[min(len(self.floor_bg) - 1, (hp + d) // 2 - hz - 1)][0] for d in range(1, dmax + 1)]
        self.horizon = [(158, 62, 126), (122, 27, 99)]

    def build_skyline(self):
        w, hp = self.w, self.hp
        sky_px = 2 * self.hz
        hgt, extra, lights, beacons = make_skyline(w, sky_px)
        self.sky_h = hgt
        top = hp - 2                                    # skyline stands on the horizon line
        self.sky_top_px = top
        maxh = max(hgt) if hgt else 0
        runs = []
        for k in range(maxh):
            row, x = [], 0
            while x < w:
                if hgt[x] > k:
                    x0 = x
                    while x < w and hgt[x] > k:
                        x += 1
                    row.append((x0, x))
                else:
                    x += 1
            runs.append(row)
        self.sky_runs = runs
        self.sky_extra = [(x, top + dy) for (x, dy) in extra if 0 <= x < w and top + dy >= 0]
        cx, cy, r = self.sun
        rim = []
        for x in range(w):
            if hgt[x]:
                py = top - hgt[x] + 1
                lit = abs(x - cx) < r * 1.05
                rim.append((x, py, (190, 60, 110) if lit else (96, 30, 104)))
        self.sky_rim = rim
        self.sky_lights = [(x, top - k, c, ph) for (x, k, c, ph) in lights]
        self.beacons = [(x, top - k) for (x, k) in beacons if 0 <= x < w]
        self.silhouette = (14, 3, 26)

    def draw_skyline(self, s, now):
        pt, pb = s.pt, s.pb
        top, col, w = self.sky_top_px, self.silhouette, self.w
        for k, row in enumerate(self.sky_runs):
            py = top - k
            if py < 0:
                break
            layer = (pb if py & 1 else pt)[py >> 1]
            for x0, x1 in row:
                layer[x0:x1] = [col] * (x1 - x0)
        for x, py in self.sky_extra:
            (pb if py & 1 else pt)[py >> 1][x] = col
        for x, py, c in self.sky_rim:
            (pb if py & 1 else pt)[py >> 1][x] = c
        tick = now * 0.4
        for x, py, c, ph in self.sky_lights:
            if (tick + ph) % 1.0 < 0.93:
                (pb if py & 1 else pt)[py >> 1][x] = c
        if int(now * 1.2) % 2 == 0:
            for x, py in self.beacons:
                if 0 <= py < 2 * self.hz:
                    (pb if py & 1 else pt)[py >> 1][x] = (255, 40, 60)

    def spawn_car(self, near=False):
        oncoming = random.random() < 0.55
        lane = random.choice((-2.5, -1.5, -0.5)) if oncoming else random.choice((0.5, 1.5, 2.5))
        z = random.uniform(30, 70) if oncoming else self.zs * 0.9
        if near:
            z = random.uniform(self.zs * 1.2, 60)
        self.cars.append({"lane": lane, "z": z, "dir": -1 if oncoming else 1,
                          "v": random.uniform(5, 13), "len": random.uniform(2, 5)})

    def draw_floor(self, s, now, dt):
        w, h, hz = self.w, self.h, self.hz
        hp, dmax, zs, g = self.hp, self.dmax, self.zs, self.g
        pt, pb = s.pt, s.pb
        for i, row in enumerate(self.floor_bg):
            s.bg[hz + 1 + i] = row[:]
        cx = w / 2
        off = math.sin(now * 0.21) * g * 0.7
        t = now
        # reflection of the sun (streaky, rippled) and the skyline/logo silhouettes
        sun_by_py = self.sun_by_py
        scroll = self.sun_t
        band = int(t * 3)
        ripple = [0] + [int(round(math.sin(d * 0.72 + t * 2.3) * (0.4 + 1.4 * d / dmax))) for d in range(1, dmax + 1)]
        for d in range(1, dmax + 1):
            py = hp + d
            if py > self.pbot:
                break
            src = hp - 2 - int(d * 0.8)
            row = sun_by_py.get(src)
            if row is None or d > dmax * 0.7 or ((d + band) % 6 == 0 and d > 3):
                continue
            _, x0, x1, v, col = row
            if v > 0.42 and (src + scroll) % 7 < 0.7 + (v - 0.42) * 7.5:
                continue
            fade = 0.3 + 0.6 * (d / (dmax * 0.7)) ** 0.8
            c = blend(blend(col, PINK, 0.2), self.fbg[d], fade)
            dx = ripple[d]
            shrink = int((x1 - x0) * 0.22 * d / dmax)
            a, b = max(0, x0 + dx + shrink), min(w, x1 + dx - shrink)
            if b > a:
                (pb if py & 1 else pt)[py >> 1][a:b] = [c] * (b - a)
        # the word mirrored on the wet grid
        refl = blend(PINK, (60, 10, 60), 0.55)
        for (px, cy_) in self.word_front:
            for sp in (2 * cy_, 2 * cy_ + 1):
                d = int((hp - sp) * 1.25)
                py = hp + d
                if 1 <= d <= dmax and py <= self.pbot and (d + band) % 5:
                    x = px + ripple[d]
                    if 0 <= x < w:
                        (pb if py & 1 else pt)[py >> 1][x] = refl
        # horizontal grid lines rushing towards us
        fz = self.floor_t
        last, drawn = None, -9
        hcol, vcol, glow = self.hcol, self.vcol, self.glow
        for d in range(1, dmax + 1):
            py = hp + d
            if py > self.pbot:
                break
            idx = int(zs * dmax / d + fz)
            if idx != last and last is not None and d - drawn > 2 + d * 0.08:
                (pb if py & 1 else pt)[py >> 1][:] = [hcol[d]] * w
                drawn = d
            last = idx
        # vertical grid lines converging on the vanishing point
        n = 9
        side_fade = w * 0.3
        vfar = self.vfar
        rows = [(d, hp + d, (pb if (hp + d) & 1 else pt)[(hp + d) >> 1]) for d in range(1, min(dmax, self.pbot - hp) + 1)]
        glow_from = dmax * 0.45
        for i in range(-n, n + 1):
            X = i * g - off
            step = X / dmax
            if step > 3.0 or step < -3.0:
                continue                                 # too shallow: reads as clutter
            px_prev = cx + step
            for d, py, layer in rows:
                xx = cx + step * d
                if xx < px_prev:
                    a, b = int(xx), int(px_prev)
                else:
                    a, b = int(px_prev), int(xx)
                px_prev = xx
                if b < 0 or a >= w:
                    continue
                if a < 0:
                    a = 0
                if b > w - 1:
                    b = w - 1
                if d > glow_from and a == b:
                    gc = glow[d]
                    if a > 0:
                        layer[a - 1] = gc
                    if a < w - 1:
                        layer[a + 1] = gc
                c = vfar[d] if (xx - cx > side_fade or cx - xx > side_fade) else vcol[d]
                if a == b:
                    layer[a] = c
                else:
                    layer[a:b + 1] = [c] * (b - a + 1)
        # horizon: a hot neon line where floor meets sky
        hc0, hc1 = self.horizon
        pt_row = pt[hz]
        pb_row = pb[hz]
        pt_row[:] = [hc0] * w
        pb_row[:] = [hc1] * w
        s.bg[hz] = [hc1] * w
        # light trails: cars racing along the grid lanes
        spd = 1 + 1.5 * DATA.level
        if len(self.cars) < (7 if w > 120 else 4) and random.random() < 0.08:
            self.spawn_car()
        alive = []
        for c in self.cars:
            c["z"] += c["dir"] * c["v"] * spd * dt
            if c["z"] < zs * 0.85 or c["z"] > 80:
                continue
            alive.append(c)
            oncoming = c["dir"] < 0
            head_c = (235, 250, 255) if oncoming else (255, 50, 80)
            tail_c = (0, 140, 200) if oncoming else (150, 10, 70)
            z0 = c["z"]
            z1 = z0 + c["len"] if oncoming else max(zs * 0.8, z0 - c["len"])
            for lat in (-0.16, 0.16):
                X = (c["lane"] + lat) * g - off
                d0, d1 = zs * dmax / z0, zs * dmax / z1
                lo, hi = int(min(d0, d1)), int(max(d0, d1))
                for d in range(max(1, lo), min(dmax, hi) + 1):
                    py = hp + d
                    if py > self.pbot:
                        break
                    q = (d - d1) / (d0 - d1) if d0 != d1 else 1.0
                    x = int(cx + X * d / dmax)
                    if 0 <= x < w:
                        (pb if py & 1 else pt)[py >> 1][x] = blend(tail_c, head_c, q * q)
                hd = int(d0)
                py = hp + hd
                x = int(cx + X * hd / dmax)
                if 1 <= hd <= dmax and py <= self.pbot and 0 <= x < w:
                    (pb if py & 1 else pt)[py >> 1][x] = WHITE if oncoming else (255, 120, 140)
        self.cars = alive

    def palm_pixels(self, bx, by, ph, side, sway):
        """Silhouette of one palm: curved ringed trunk and feathery drooping fronds."""
        sil, rim, ring = (9, 1, 17), (170, 40, 150), (80, 18, 84)
        pix = {}
        lean = -side * ph * 0.22
        crown = (bx, by)
        for k in range(ph):
            t = k / ph
            x = bx + lean * t ** 1.7
            wdt = 2 if t > 0.5 else 3
            py = by - k
            x0 = int(x) - wdt // 2
            for j in range(wdt):
                pix[(x0 + j, py)] = sil
            pix[(x0 + (wdt - 1 if side > 0 else 0), py)] = rim if k % 3 else ring
            crown = (x, py)
        cx_, cy_ = crown
        L = max(6.0, min(ph * 0.4, self.w * 0.07))
        for n, a0 in enumerate((-2.95, -2.5, -2.05, -1.62, -1.15, -0.7, -0.25, 0.2, 2.95 + 0.0)):
            a = a0 + sway * (1 if n % 2 else -0.6)
            ca, sa = math.cos(a), math.sin(a)
            steps = int(L * 1.6)
            out = 1 if ca >= 0 else -1
            for k in range(steps):
                q = k / steps
                dist = q * L
                x = cx_ + ca * dist * 1.2
                y = cy_ + sa * dist * 0.8 + q * q * L * 0.9
                xi, yi = int(x), int(y)
                pix[(xi, yi)] = sil
                if q < 0.5:
                    pix[(xi, yi + 1)] = sil
                if 0.08 < q < 0.97:
                    ln = int(1 + 3.2 * (1 - q))
                    for j in range(1, ln + 1):
                        pix[(xi + out * (j // 2), yi + j)] = sil
                if q < 0.9 and (xi, yi - 1) not in pix:
                    pix[(xi, yi - 1)] = rim if q < 0.6 else ring
        for dx, dy in ((-1, 2), (1, 2), (0, 3)):
            pix[(int(cx_) + dx, int(cy_) + dy)] = (36, 8, 34)
        W, PH = self.w, 2 * self.h - 2
        return [(x, py, c) for (x, py), c in pix.items() if 0 <= x < W and 0 <= py < PH]

    def draw_palms(self, s, now):
        pt, pb = s.pt, s.pb
        for i, (bx, by, ph, side) in enumerate(self.palms):
            q = int((math.sin(now * 0.7 + bx) + 1) * 3.5)
            key = (i, q)
            pix = self.palm_cache.get(key)
            if pix is None:
                pix = self.palm_cache[key] = self.palm_pixels(bx, by, ph, side, (q / 7 - 0.5) * 0.12)
            for x, py, c in pix:
                (pb if py & 1 else pt)[py >> 1][x] = c

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

    def draw_bolt(self, s, now):
        b = self.bolt
        age = now - b["t"]
        if age < 0.07 or 0.13 < age < 0.5:
            fade = 1 - max(0.0, age - 0.13) / 0.37
            core = blend((150, 120, 255), WHITE, fade)
            halo = blend((25, 5, 45), (150, 60, 255), fade)
            for path, c, hc in ((b["main"], core, halo), *((br, blend(core, PURPLE, 0.4), None) for br in b["br"])):
                for (ax, ay), (bx, by) in zip(path, path[1:]):
                    for (x, y) in line_points(int(ax), int(ay), int(bx), int(by)):
                        if hc:
                            s.pixel(x - 1, y, hc)
                            s.pixel(x + 1, y, hc)
                        s.pixel(x, y, c)

    # ------------------------------------------------------------ the logo in 3D
    def set_view(self, now):
        yaw = math.sin(now * 0.45) * 0.5
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

    def proj_px(self, x, y, z):
        """Like proj, but returns a half-block pixel row for sub-cell placement."""
        cx, cy = self.center
        cyw, syw, cp, sp = self.rot
        X, Y, Z = (x - cx) * 0.5, y - cy, z
        X, Z = X * cyw + Z * syw, -X * syw + Z * cyw
        Y, Z = Y * cp - Z * sp, Y * sp + Z * cp
        k = 70 / (70 + Z) * (1 + 0.035 * self.bump)
        return int(cx + X * 2 * k), int(2 * (cy + Y * k))

    def skull_palette(self, now, light):
        pal = [(int(c[0] * light), int(c[1] * light), int(c[2] * light)) for c in SKULL_BASE]
        eye = blend((200, 0, 90), WHITE, 0.15 + 0.5 * self.bump) if (now * 0.9) % 6 > 0.25 else (40, 0, 20)
        pal[EYE] = blend(eye, PINK, 0.2 + 0.2 * pulse(now, 3))
        pal[SOCKET] = SKULL_BASE[SOCKET]
        pal[OUTLINE] = SKULL_BASE[OUTLINE]
        return pal

    def draw_skull(self, s, now, glitch):
        if not self.skull:
            return
        cx, cy = self.center
        cyw, syw, cp, sp = self.rot
        bump = 1 + 0.035 * self.bump
        dX, dY, dZ = syw, -cyw * sp, cyw * cp
        W, PH = s.w, 2 * s.h
        pt, pb = s.pt, s.pb
        base = []
        for (x, y, k) in self.skull:
            X = (x - cx) * 0.5
            Y = y - cy
            Z1 = -X * syw
            base.append((X * cyw, Y * cp - Z1 * sp, Y * sp + Z1 * cp, k))
        # extruded bone thickness, back to front
        ring = [p for p in base if p[3] == OUTLINE]
        for depth, col in ((2.4, (24, 6, 38)), (1.8, (36, 12, 54)), (1.2, (50, 20, 74)), (0.6, (64, 30, 92))):
            ox, oy, oz = dX * depth, dY * depth, dZ * depth
            for (X, Y, Z, k) in ring:
                kk = 70 / (70 + Z + oz) * bump
                px, py = int(cx + (X + ox) * 2 * kk), int(2 * (cy + (Y + oy) * kk))
                if 0 <= px < W and 0 <= py < PH:
                    (pb if py & 1 else pt)[py >> 1][px] = col
        light = 0.6 + 0.4 * (0.5 + 0.5 * math.cos(self.yaw * 2))
        pal = self.skull_palette(now, light)
        offsets = {}
        shine = ((now * 60) % (self.w + 80)) - 40 - (self.w // 2 - self.word_w // 2)
        sl = self.skull_left
        for (X, Y, Z, k), (x, y, _) in zip(base, self.skull):
            kk = 70 / (70 + Z) * bump
            px, py = int(cx + X * 2 * kk), int(2 * (cy + Y * kk))
            if glitch:
                o = offsets.get(py >> 2)
                if o is None:
                    o = offsets[py >> 2] = random.randint(-4, 4) if random.random() < 0.3 else 0
                px += o
            col = pal[k]
            if k < 8:
                dd = abs((x - sl) * 0.6 - shine * 0.6 + (y - self.skull_top) * 2)
                if dd < 4:
                    col = blend(col, WHITE, 0.6 * (1 - dd / 4))
            if 0 <= px < W and 0 <= py < PH - 1:
                (pb if py & 1 else pt)[py >> 1][px] = col
                if kk > 1.0:
                    py += 1
                    (pb if py & 1 else pt)[py >> 1][px] = col

    def draw_logo(self, s, cells, now, glitch):
        cx, cy = self.center
        cyw, syw, cp, sp = self.rot
        bump = 1 + 0.035 * self.bump
        dX, dY, dZ = syw, -cyw * sp, cyw * cp
        base = []
        for (x, y, ch, kind) in cells:
            X = (x - cx) * 0.5
            Y = y - cy
            Z1 = -X * syw
            base.append((X * cyw, Y * cp - Z1 * sp, Y * sp + Z1 * cp))
        W, H = s.w, s.h
        chs, fgs = s.ch, s.fg
        for depth in (3, 2, 1):
            cw = blend((70, 10, 70), BLACK, 0.2 + depth * 0.2)
            ox, oy, oz = dX * depth, dY * depth, dZ * depth
            for (X, Y, Z) in base:
                k = 70 / (70 + Z + oz) * bump
                px, py = int(cx + (X + ox) * 2 * k), int(cy + (Y + oy) * k)
                if 0 <= px < W and 0 <= py < H:
                    chs[py][px] = "█"
                    fgs[py][px] = cw
        front = []
        for (X, Y, Z) in base:
            k = 70 / (70 + Z) * bump
            front.append((int(cx + X * 2 * k), int(cy + Y * k)))
        self.word_front = front
        offsets = {}
        if glitch:
            for (x, y, ch, kind), (px, py) in zip(cells, front):
                if y not in offsets:
                    offsets[y] = random.randint(-5, 5) if random.random() < 0.3 else 0
                s.put(px - 2 + offsets[y], py, ch, CYAN)
                s.put(px + 2 + offsets[y], py, ch, PINK)
        light = 0.78 + 0.22 * (0.5 + 0.5 * math.cos(self.yaw * 2))
        rows = {}
        shine = ((now * 60) % (self.w + 80)) - 40
        sx0 = self.w // 2 - self.word_w // 2
        for (x, y, ch, kind), (px, py) in zip(cells, front):
            col = rows.get(y)
            if col is None:
                col = rows[y] = self.color(x, y, kind, now, False, shine=False)
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
        self.skull_starts = [(random.uniform(-20, self.w + 20), random.uniform(-10, self.hz), random.uniform(-60, 40)) for _ in self.skull]

    def explode(self, now):
        cx, cy = self.center
        for (x0, y0, ch, kind) in self.cells:
            x, y = self.proj(x0, y0, 0)
            a = math.atan2(y - cy, (x - cx) / 2) + random.uniform(-0.4, 0.4)
            v = random.uniform(10, 40)
            self.particles.add(x, y, math.cos(a) * v * 2, math.sin(a) * v, random.uniform(0.6, 1.6),
                               ch if random.random() < 0.6 else "▓▒░", PINK, gravity=6)
        pal = self.skull_palette(now, 1.0)
        for (x0, y0, k) in self.skull[::3]:
            if k == OUTLINE:
                continue
            x, y = self.proj(x0, y0, 0)
            a = math.atan2(y - cy, (x - cx) / 2) + random.uniform(-0.5, 0.5)
            v = random.uniform(8, 36)
            self.particles.add(x, y, math.cos(a) * v * 2, math.sin(a) * v, random.uniform(0.5, 1.4),
                               "▀" if random.random() < 0.7 else "▓▒░", pal[k], gravity=6)
        self.phase, self.phase_t = "gone", now
        self.word_front = []
        self.glitch.trigger(now, 0.4)

    def color(self, x, y, kind, now, glitch, shine=True):
        # Bright screen-printed face: pale pink cap fading to hot pink, so the
        # letters separate cleanly from their dark extruded sides.
        base = blend((255, 170, 225), (255, 20, 130), (y - self.word_top) / 4)
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
                if y > self.hz - 1:
                    continue
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
        lvl = int(pulse(now, 0.8) * 10)
        meter = "THREAT " + "".join("▰" if i < lvl else "▱" for i in range(10))
        s.text((w - len(meter)) // 2, 0, meter, blend(YELLOW, PINK, lvl / 10))

    def draw_tagline(self, s, now, glitch):
        txt, full = self.typer.current(now)
        x = (self.w - len(full)) // 2
        y = self.tag_y
        plate = (12, 2, 22)
        for i in range(max(0, x - 4), min(self.w, x + len(full) + 3)):
            s.bg[y][i] = plate
            s.ch[y][i] = " "
            s.pt[y][i] = s.pb[y][i] = None
        self.typer.draw(s, y, now, glitch=glitch)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "spray", "DEDSEC / PAINT CLEARED", PINK)

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        beat, level = DATA.beat, DATA.level
        self.bump = max(beat, self.bump - dt * 4)
        self.orb_t += dt * (0.8 + 1.4 * level + 1.5 * self.bump)
        self.floor_t += dt * (1.6 + 4 * level)
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
        self.rain.draw(s)
        # rain belongs to the sky outside the logo; wipe it from the box and the floor
        bx, by, bw, bh = self.box
        for y in range(max(0, by), min(self.h, by + bh)):
            s.ch[y][bx:bx + bw] = [" "] * bw
        for y in range(self.hz, self.h):
            s.ch[y] = [" "] * self.w
        if self.bolt:
            self.draw_bolt(s, now)
        self.draw_sun(s, now)
        self.draw_skyline(s, now)
        self.draw_floor(s, now, dt)
        self.draw_palms(s, now)
        for g in self.graffiti:
            g.update(s, now, dt, self.particles, self.sky)
        for st in self.stickers:
            st.step(s, dt, self.particles)
        self.panels.draw(s, now)

        self.set_view(now)
        self.draw_orbit(s, now, front=False)

        age = now - self.phase_t
        if self.phase == "in":
            t = ease_out(age / 1.6)
            pal = self.skull_palette(now, 1.0)
            for (x, y, k), (sx, sy, sz) in zip(self.skull, self.skull_starts):
                px, py = self.proj_px(sx + (x - sx) * t, sy + (y - sy) * t, sz * (1 - t))
                s.pixel(px, py, pal[k] if t > 0.9 else blend(CYAN, pal[k], t))
            for (x, y, ch, kind), (sx, sy, sz) in zip(self.cells, self.starts):
                px, py = self.proj(sx + (x - sx) * t, sy + (y - sy) * t, sz * (1 - t))
                s.put(px, py, ch, self.color(x, y, kind, now, glitch) if t > 0.95 else blend(CYAN, PINK, t))
            if age > 1.6:
                self.phase, self.phase_t = "hold", now
                self.particles.burst(self.center[0], self.center[1], 60, speed=25)
        elif self.phase == "hold":
            self.draw_skull(s, now, glitch)
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

        self.draw_tagline(s, now, glitch)
        self.draw_orbit(s, now, front=True)
        self.particles.step(s, dt)
        self.draw_hud(s, now)
        self.ticker.draw(s, self.h - 1, now)
        if self.flash > 0.6:
            for y in range(self.hz + 1):
                tint_row(s, y, WHITE, round((self.flash - 0.6) * 0.5, 2))
        post_fx(s, now, glitch)
        self.frame += 1

"""DEDSEC: DedSec hijacks the ctOS public broadcast.

A 40 second loop: the calm official ctOS feed, interference, a pink scan line
reveals the DedSec skull and the wordmark slams in, the DedSec broadcast holds
(halftone poster backdrop, chromatic split, typed manifesto, followers), then
the signal collapses like an old CRT and ctOS reboots.

SKULL and make_skull are also used by mode_tower.py.
"""
import math
import random
import time

from lib import BLACK, CYAN, DIM_PINK, GREY, PINK, WHITE, blend, line_points
from sysdata import DATA
from widgets import Particles, Ticker

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

SOCKET, OUTLINE, EYE = 8, 9, 10


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




# ------------------------------------------------------------------ wordmark
# 6 x 7 bitmap letters, scaled up in half-block pixels and slanted.
_FONT = {
    "D": ("#####.", "##..##", "##..##", "##..##", "##..##", "##..##", "#####."),
    "E": ("######", "##....", "##....", "#####.", "##....", "##....", "######"),
    "S": (".#####", "##....", "##....", ".####.", "....##", "....##", "#####."),
    "C": (".#####", "##....", "##....", "##....", "##....", "##....", ".#####"),
    "T": ("######", "..##..", "..##..", "..##..", "..##..", "..##..", "..##.."),
    "O": (".####.", "##..##", "##..##", "##..##", "##..##", "##..##", ".####."),
}

BG = (7, 5, 12)
BONE = [(70, 58, 78), (98, 84, 104), (126, 112, 130), (156, 142, 158), (186, 172, 186),
        (210, 198, 210), (230, 222, 232), (246, 242, 248)]
EYE_COL = (255, 30, 120)
SOCKET_COL = (14, 6, 18)
OUTLINE_COL = (30, 10, 34)
CTOS_BLUE = (40, 140, 220)
CTOS_DIM = (16, 46, 80)

TAGLINES = [
    "WE ARE DEDSEC.",
    "ctOS IS WATCHING YOU. NOW WE WATCH THEM.",
    "YOUR DATA IS NOT THEIR PROPERTY.",
    "INFORMATION WANTS TO BE FREE.",
    "JOIN US.",
]
NEWS = [
    "#DEDSEC trending worldwide", "Blume stock -14% after ctOS outage", "#HACKTHEPLANET",
    "Skull logo appears on every billboard in SF", "Nudle CEO: 'we take privacy very seriously'",
    "#JOINUS", "Police baffled by dancing traffic lights", "Invite Only party crashed by unknown hackers",
]

# Loop timeline (seconds)
LOOP = 40.0
CTOS_END = 7.0          # official ctOS broadcast
HIJACK_END = 9.0        # interference
REVEAL_END = 11.6       # skull scan + wordmark slam
HOLD_END = 35.0         # the DedSec broadcast
LOST_END = 36.8         # CRT collapse
DARK_END = 38.2         # no signal; then ctOS reboots until the loop wraps


def _sm(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _put_px(s, x, py, col):
    if 0 <= x < s.w and 0 <= py < 2 * s.h:
        y = py >> 1
        (s.pb if py & 1 else s.pt)[y][x] = col
        s.ch[y][x] = " "                         # pixels win over background halftone text


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.start = None
        self.last = None
        self.particles = Particles()
        self.ticker = Ticker("DEDSEC", NEWS)
        self.followers = random.randint(1_200_000, 1_900_000)
        self.glitch_until = 0.0
        self.next_glitch = 0.0
        big = w >= 150 and h >= 40
        self.scale = 3 if big else 2 if w >= 86 and h >= 22 else 1
        self._layout()
        self._halftone()

    # ------------------------------------------------------------- layout
    def _layout(self):
        w, h = self.w, self.h
        sc = self.scale
        # wordmark pixels: (x, py, shade 0..1)
        lw, lh = 6 * sc, 7 * sc
        gap = 2 * sc if sc == 3 else sc + 1
        total = 6 * lw + 5 * gap
        word_rows = (lh + 1) // 2
        skull_px = max(14, int(2 * h * 0.40))           # skull height in pixel rows
        if h < 30:
            skull_px = max(12, 2 * h - 2 * word_rows - 16)
        block = skull_px // 2 + 1 + word_rows + 3       # rows: skull, gap, word, tagline
        top = max(2, (h - block) // 2 - 1)
        sw = int(skull_px * 1.08) // 2 * 2
        self.skull_x0 = (w - sw) // 2
        self.skull_y0 = 2 * top
        self.skull = []
        for (u, v, k) in make_skull(sw, skull_px):
            if k == OUTLINE:
                col = OUTLINE_COL
            elif k == EYE:
                col = None                               # animated
            elif k == SOCKET:
                col = SOCKET_COL
            else:
                col = BONE[k]
            self.skull.append((self.skull_x0 + u, self.skull_y0 + v, col, k))
        self.skull_h = skull_px
        self.word_py0 = self.skull_y0 + skull_px + 2
        self.word_x0 = (w - total) // 2 + lh // 6
        self.word = []
        for n, ch in enumerate("DEDSEC"):
            rows = _FONT[ch]
            for r, line in enumerate(rows):
                for c, px in enumerate(line):
                    if px != "#":
                        continue
                    for dy in range(sc):
                        for dx in range(sc):
                            yy = r * sc + dy
                            slant = -(yy * 2) // 7                # italic lean
                            x = self.word_x0 + n * (lw + gap) + c * sc + dx + slant
                            self.word.append((x, self.word_py0 + yy, yy / max(1, lh - 1), n))
        self.word_set = {(x, y) for x, y, _, _ in self.word}
        self.word_total = total
        self.word_rows = word_rows
        self.tag_y = (self.word_py0 + lh) // 2 + 2
        self.center = (w / 2, self.skull_y0 / 2 + skull_px / 4)

    def _halftone(self):
        # a pitch-2 grid of potential halftone dots behind everything
        self.ht = [(x, y) for y in range(1, self.h - 2) for x in range(y % 2, self.w, 2)]

    # ------------------------------------------------------------- pieces
    def draw_halftone(self, s, now, glow, tint=(150, 16, 92)):
        # poster halftone: a big radial glow behind the skull, gently breathing
        if not hasattr(self, "_htd"):
            cx, cy = self.center
            self._htd = [(x, y, math.hypot((x - cx) * 0.5, (y - cy) * 1.1)) for x, y in self.ht]
            self._htc = [blend(BG, tint, i / 31) for i in range(32)]
        rad = max(self.w * 0.30, 16) * (1 + 0.06 * math.sin(now * 0.9))
        inv = 1.0 / rad
        cols = self._htc
        chs, fgs = s.ch, s.fg
        for x, y, d in self._htd:
            k = (1 - d * inv) * glow
            if k <= 0.08:
                continue
            chs[y][x] = "●" if k > 0.62 else "•" if k > 0.36 else "·"
            fgs[y][x] = cols[min(31, int((0.25 + k * 0.75) * 31))]

    def draw_skull(self, s, now, reveal_py=None, split=1, eye=1.0, bob=0):
        pulse = 0.65 + 0.35 * math.sin(now * 3.1) + 0.4 * DATA.level
        eye_col = blend((90, 0, 40), EYE_COL, min(1.0, pulse * eye))
        eye_hot = blend(EYE_COL, WHITE, max(0.0, min(1.0, (pulse - 0.9) * 2)) * eye)
        pts = self.skull
        if reveal_py is not None:
            pts = [p for p in pts if p[1] < reveal_py]
        if split:
            for dx, col in ((-split, (0, 150, 190)), (split, (210, 20, 110))):
                for (x, py, c, k) in pts:
                    if k != OUTLINE and k != SOCKET:
                        _put_px(s, x + dx, py + bob, blend(BG, col, 0.55))
        for (x, py, c, k) in pts:
            if c is None:
                c = eye_hot if (x - self.skull_x0) % 3 == 1 and (py - self.skull_y0) % 2 == 0 else eye_col
            _put_px(s, x, py + bob, c)

    def draw_word(self, s, now, zoom=1.0, split=2, flicker=-1, alpha=1.0):
        if self.scale < 3:
            split = max(1, split // 2)                # thinner chromatic split on small letters
        cx = self.w / 2
        cy = self.word_py0 + 7 * self.scale / 2
        layers = ((-split, (0, 200, 235)), (split, (255, 20, 120)), (0, None)) if split else ((0, None),)
        sweep = ((now * 0.45) % 1.6) - 0.3
        if not hasattr(self, "_wcol"):
            self._wcol = [blend((255, 255, 255), (255, 120, 190), v ** 1.6) for (_, _, v, _) in self.word]
        wcol = self._wcol
        for dx, tint in layers:
            tcol = blend(BG, tint, 0.85 * alpha) if tint is not None else None
            for i, (x, py, v, n) in enumerate(self.word):
                if zoom != 1.0:
                    x = int(cx + (x - cx) * zoom)
                    py = int(cy + (py - cy) * zoom)
                if tcol is not None:
                    col = tcol
                elif n == flicker:
                    col = blend(BG, PINK, 0.9)
                else:
                    col = wcol[i]
                    u = (x - self.word_x0) / self.word_total
                    if abs(u - sweep + v * 0.08) < 0.03:
                        col = WHITE
                    if alpha < 1.0:
                        col = blend(BG, col, alpha)
                _put_px(s, x + dx, py, col)

    def draw_hud(self, s, now, live=True):
        s.text(2, 0, "DEDSEC // BROADCAST HIJACK", PINK)
        s.text(2, 1, "CH 04  //  ctOS PUBLIC FEED  //  %s" % time.strftime("%H:%M:%S"), GREY)
        if live:
            dot = "●" if int(now * 2) % 2 else " "
            s.text(self.w - 9, 0, dot + " LIVE", PINK)
        self.followers += random.randint(0, 9)
        fol = "FOLLOWERS %s" % format(self.followers, ",")
        s.text(self.w - len(fol) - 2, 1, fol, WHITE)
        # viewfinder corners
        for (x, y, a, b) in ((1, 3, "┌", "─"), (self.w - 2, 3, "┐", "─"),
                             (1, self.h - 4, "└", "─"), (self.w - 2, self.h - 4, "┘", "─")):
            s.put(x, y, a, DIM_PINK)

    def draw_sides(self, s, now):
        """Slow vertical marquees down both edges."""
        text = "  WE ARE DEDSEC  //  JOIN US  //  HACK THE PLANET  //"
        n = len(text)
        off = int(now * 3)
        for side, x in ((0, 4), (1, self.w - 5)):
            for y in range(4, self.h - 4):
                c = text[(y - off * (1 if side else -1) + side * 17) % n]
                if c != " ":
                    s.put(x, y, c, blend(BG, PINK, 0.32))

    def draw_tagline(self, s, now, t_hold):
        i = int(t_hold / 4.6) % len(TAGLINES)
        line = TAGLINES[i]
        tt = t_hold % 4.6
        n = min(len(line), int(tt * 28))
        x = (self.w - len(line)) // 2
        if self.tag_y < self.h - 3:
            s.text(x - 2, self.tag_y, "> ", PINK)
            s.text(x, self.tag_y, line[:n], WHITE)
            if n < len(line) or int(now * 3) % 2:
                s.put(x + n, self.tag_y, "█", PINK)

    def glitch_bands(self, s, now, strength=1.0):
        for _ in range(random.randint(1, 3)):
            y0 = random.randrange(2, max(3, self.h - 3))
            dx = random.choice((-1, 1)) * random.randint(2, int(2 + 5 * strength))
            for y in range(y0, min(self.h - 2, y0 + random.randint(1, 2))):
                s.shift_row(y, dx)
                s.tint_row(y, random.choice((PINK, CYAN)), 0.35)

    # ------------------------------------------------------------- phases
    def ctos(self, s, now, fade=1.0):
        s.gradient_bg(blend(BG, (4, 14, 30), fade), blend(BG, (8, 26, 48), fade), 0, self.h)
        cx, cy = int(self.w / 2), int(self.h * 0.42)
        r = min(self.w * 0.12, self.h * 0.32)
        col = blend(BG, CTOS_BLUE, fade)
        dim = blend(BG, CTOS_DIM, fade)
        for i in range(72):
            a = i / 72 * math.tau
            ring_on = (i + int(now * 10)) % 12 < 9
            for rr, c in ((r, col if ring_on else dim), (r * 0.72, dim)):
                _put_px(s, int(cx + math.cos(a) * rr * 2), int(2 * cy + math.sin(a) * rr * 2), c)
        # big pixel "ctOS" in the middle of the emblem
        sc = 2 if self.w >= 200 and self.h >= 50 else 1
        word = "CTOS"
        lw = 6 * sc + sc
        x0 = cx - (len(word) * lw - sc) // 2
        y0 = 2 * cy - (7 * sc) // 2
        white = blend(BG, (220, 236, 255), fade)
        for n, ch in enumerate(word):
            for row, line in enumerate(_FONT[ch]):
                for c, px in enumerate(line):
                    if px == "#":
                        for dy in range(sc):
                            for dx in range(sc):
                                _put_px(s, x0 + n * lw + c * sc + dx, y0 + row * sc + dy, white)
        s.center(cy + int(r) + 2, "CITY OPERATING SYSTEM 2.0", blend(BG, CTOS_BLUE, fade))
        s.center(cy + int(r) + 3, "ALL SYSTEMS NOMINAL  ●", blend(BG, (80, 200, 140), fade))
        # calm waveform
        y0 = 2 * (cy + int(r) + 6)
        for x in range(self.w // 4, 3 * self.w // 4):
            v = math.sin(x * 0.18 + now * 2.0) * math.sin(x * 0.05 - now * 0.7)
            _put_px(s, x, int(y0 + v * 3), dim if abs(v) < 0.5 else col)
        s.text(2, 0, "ctOS 2.0 // BLUME CORPORATION", blend(BG, CTOS_BLUE, fade))
        s.text(self.w - 22, 0, "PUBLIC SERVICE FEED", blend(BG, CTOS_DIM, fade))

    def hijack(self, s, now, k):
        self.ctos(s, now, 1.0)
        # interference grows: tears, static bands, pink takeover
        for _ in range(int(2 + 18 * k)):
            y = random.randrange(self.h)
            s.shift_row(y, random.randint(-int(4 + 30 * k), int(4 + 30 * k)))
        for _ in range(int(1 + 8 * k)):
            y = random.randrange(self.h)
            for x in range(0, self.w, random.randint(1, 3)):
                s.put(x, y, random.choice("░▒▓"), blend(GREY, PINK, random.random() * k))
        for y in range(self.h):
            if random.random() < 0.5 * k:
                s.tint_row(y, PINK, 0.4 * k)
        if int(now * 12) % 3:
            msg = " SIGNAL INTERRUPTED " if k < 0.6 else " ░░ OVERRIDE ░░ "
            s.center(self.h // 2, msg, WHITE if k > 0.5 else CTOS_BLUE)

    def reveal(self, s, now, k):
        s.gradient_bg(BG, (16, 4, 20), 0, self.h)
        scan = int(self.skull_y0 + (self.skull_h + 4) * _sm(k / 0.55))
        self.draw_halftone(s, now, 0.6 * _sm((k - 0.3) / 0.7))
        self.draw_skull(s, now, reveal_py=scan, split=1, eye=_sm((k - 0.35) / 0.3))
        if k < 0.6:
            for x in range(self.w):
                _put_px(s, x, scan, PINK)
                _put_px(s, x, scan - 1, blend(BG, PINK, 0.5))
        if k > 0.55:
            q = _sm((k - 0.55) / 0.18)
            zoom = 1.0 + 0.9 * (1 - q)
            self.draw_word(s, now, zoom=zoom, split=int(2 + 6 * (1 - q)), alpha=min(1.0, q * 1.5))
            if 0.73 < k < 0.82:                         # impact: shake + flash
                for y in range(self.h):
                    s.shift_row(y, random.choice((-2, -1, 1, 2)))
                s.gradient_bg((60, 10, 40), (30, 4, 24), 0, self.h)
                cx, cy = self.w / 2, self.word_py0 / 2
                if not getattr(self, "_burst", False):
                    self._burst = True
                    self.particles.burst(cx, cy, 70, (PINK, WHITE, CYAN), speed=26, chars="▀▄■·")

    def hold(self, s, now, th, dt):
        s.gradient_bg(BG, (18, 4, 22), 0, self.h)
        beat = DATA.beat
        self.draw_halftone(s, now, 0.8 + 0.25 * beat)
        if self.w >= 120:
            self.draw_sides(s, now)
        bob = 1 if (now % 2.4) > 1.2 else 0
        glitch = now < self.glitch_until
        if now > self.next_glitch:
            self.glitch_until = now + random.uniform(0.08, 0.16)
            self.next_glitch = now + random.uniform(4.5, 9.0)
        self.draw_skull(s, now, split=1 + (1 if glitch or beat > 0.6 else 0), bob=bob)
        flicker = random.randrange(6) if glitch and random.random() < 0.5 else -1
        self.draw_word(s, now, split=2 + (3 if glitch else 0) + int(beat * 2), flicker=flicker)
        self.draw_tagline(s, now, th)
        self.particles.step(s, dt)
        if random.random() < 0.08:
            x = random.uniform(self.w * 0.2, self.w * 0.8)
            self.particles.add(x, self.h - 3, random.uniform(-2, 2), random.uniform(-5, -2), 2.5, "·•", PINK)
        if glitch:
            self.glitch_bands(s, now, 0.6)

    def lost(self, s, now, k, th):
        self.hold(s, now, th, 0.0)
        snap = s.snapshot()
        cy = self.h / 2
        sq = max(0.03, 1 - _sm(k / 0.7))
        s.clear()
        sch, sfg, sbg, spt, spb = snap
        for y in range(self.h):
            sy = int(cy + (y - cy) / sq)
            if 0 <= sy < self.h:
                s.ch[y], s.fg[y], s.bg[y] = sch[sy][:], sfg[sy][:], sbg[sy][:]
                s.pt[y], s.pb[y] = spt[sy][:], spb[sy][:]
        if k > 0.6:
            w = int(self.w * max(0.0, 1 - (k - 0.6) / 0.4))
            s.clear()
            if w > 0:
                s.text((self.w - w) // 2, int(cy), "━" * w, WHITE)

    def dark(self, s, now):
        if int(now * 2) % 2:
            s.center(self.h // 2, "NO SIGNAL", GREY)
        for _ in range(40):
            s.put(random.randrange(self.w), random.randrange(self.h), "·", (40, 40, 48))

    # ------------------------------------------------------------- main
    def step(self, s, now):
        if self.start is None:
            self.start = now
            self.next_glitch = now + 6
        dt = 0.0 if self.last is None else min(0.1, now - self.last)
        self.last = now
        t = (now - self.start) % LOOP
        if t < CTOS_END:
            self._burst = False
            self.ctos(s, now, 1.0)
        elif t < HIJACK_END:
            self.hijack(s, now, (t - CTOS_END) / (HIJACK_END - CTOS_END))
        elif t < REVEAL_END:
            self.reveal(s, now, (t - HIJACK_END) / (REVEAL_END - HIJACK_END))
            self.particles.step(s, dt)
        elif t < HOLD_END:
            self.hold(s, now, t - REVEAL_END, dt)
            self.draw_hud(s, now)
            self.ticker.draw(s, self.h - 1, now)
        elif t < LOST_END:
            self.lost(s, now, (t - HOLD_END) / (LOST_END - HOLD_END), t - REVEAL_END)
        elif t < DARK_END:
            self.dark(s, now)
        else:
            self.ctos(s, now, _sm((t - DARK_END) / 1.2))

    def farewell(self, s, now, t):
        t = max(0.0, min(1.0, t))
        self.lost(s, now, t, 0.0)

"""WRENCH: the LED mask in 3D, eyes cycling through animated emoticons, surrounded by chaos."""

import math
import random
import time

from engine3d import Rotator, Starfield, fill_poly
from lib import (BLACK, CYAN, DARK, DIM_PURPLE, GREEN, GREY, PINK, PURPLE, WHITE, YELLOW,
                 ORANGE, Glitch, Typer, blend, ease_out, pulse)
from sysdata import DATA
from widgets import Panels, Particles, PostFX, Sticker, Ticker

NAME = "WRENCH"

# 7x7 LED patterns: "X" lit, "o" half, "x" dim, "." off
X = ["X.....X", ".X...X.", "..X.X..", "...X...", "..X.X..", ".X...X.", "X.....X"]
PLUS = ["...X...", "...X...", "...X...", "XXXXXXX", "...X...", "...X...", "...X..."]
CARET = [".......", "...X...", "..X.X..", ".X...X.", "X.....X", ".......", "......."]
CARET_HALF = [".......", ".......", ".......", "..XXX..", "XX...XX", ".......", "......."]
GT = ["X......", ".XX....", "...XX..", ".....XX", "...XX..", ".XX....", "X......"]
LT = [row[::-1] for row in GT]
RING = ["..XXX..", ".X...X.", "X.....X", "X.....X", "X.....X", ".X...X.", "..XXX.."]
RING_SMALL = [".......", "..XXX..", ".X...X.", ".X...X.", ".X...X.", "..XXX..", "......."]
HEART = [".XX.XX.", "XXXXXXX", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."]
HEART_SMALL = [".......", "..X.X..", ".XXXXX.", ".XXXXX.", "..XXX..", "...X...", "......."]
DASH = [".......", ".......", ".......", "XXXXXXX", ".......", ".......", "......."]
QUESTION = ["..XXX..", ".X...X.", ".....X.", "....X..", "...X...", ".......", "...X..."]
DOLLAR = ["...X...", ".XXXXX.", "X..X...", ".XXXXX.", "...X..X", ".XXXXX.", "...X..."]
BANG = ["...X...", "...X...", "...X...", "...X...", "...X...", ".......", "...X..."]
SAD = [".......", ".......", "X.....X", ".X...X.", "..XXX..", ".......", "......."]
SKULL = [".XXXXX.", "XXXXXXX", "X.XXX.X", "XXXXXXX", ".XX.XX.", ".XXXXX.", ".X.X.X."]
PUPIL = [".......", "..XXX..", ".XXXXX.", ".XXXXX.", ".XXXXX.", "..XXX..", "......."]
BLANK = ["......."] * 7


def scroll(pattern, k):
    k %= 7
    return pattern[k:] + pattern[:k]


def grid():
    return [["."] * 7 for _ in range(7)]


def rows(g):
    return ["".join(r) for r in g]


# ------------------------------------------------------------------ animated eyes: fn(t, right) -> pattern
def a_dead(t, right):
    return X if int(t * 2.5) % 2 == 0 else PLUS


def a_love(t, right):
    big = DATA.beat > 0.45 or (t * 1.8) % 1 < 0.35
    return HEART if big else HEART_SMALL


def a_money(t, right):
    # slot machine: reels spin, then lock on $
    if t < 1.4:
        return scroll(DOLLAR, int(t * 18) + (3 if right else 0))
    return DOLLAR


def a_alert(t, right):
    return BANG if int(t * 5) % 2 == 0 else BLANK


def a_shocked(t, right):
    return RING if int(t * 3) % 3 else RING_SMALL


def a_bored(t, right):
    return scroll(DASH, -1 if (t % 3) > 2.2 else 0)


def a_confused(t, right):
    q = QUESTION if not right else [r[::-1] for r in QUESTION]
    return scroll(q, 1) if (t * 2) % 1 < 0.5 and right else q


def a_wink(t, right):
    if not right:
        return CARET
    c = t % 2.2
    if c < 1.2:
        return CARET
    if c < 1.3 or c > 2.0:
        return CARET_HALF
    return DASH


def a_roll(t, right):
    g = [list(r) for r in RING]
    a = t * 5.0 + (0.0 if right else 0.25)
    px, py = 3 + 1.6 * math.cos(a), 3 + 1.6 * math.sin(a)
    for y in range(1, 6):
        for x in range(1, 6):
            d = (x - px) ** 2 + (y - py) ** 2
            if d < 0.7:
                g[y][x] = "X"
            elif d < 1.6:
                g[y][x] = "o"
    return rows(g)


SPIN_PTS = [(3 + round(2.6 * math.cos(i / 12 * math.tau)), 3 + round(2.6 * math.sin(i / 12 * math.tau))) for i in range(12)]


def a_loading(t, right):
    g = grid()
    head = int(t * 14) % 12
    for i, (x, y) in enumerate(SPIN_PTS):
        lag = (head - i) % 12
        g[y][x] = "X" if lag == 0 else "o" if lag < 3 else "x"
    if right:
        # progress fills from the bottom of the right eye's centre
        p = (t / 3.5) % 1
        for k in range(int(p * 3) + 1):
            g[4 - k][3] = "X"
    return rows(g)


def a_glitch(t, right):
    r = random.Random(int(t * 12) * 2 + right)
    base = r.choice((X, SKULL, RING, CARET, QUESTION, PUPIL, HEART))
    out = []
    for row in base:
        sh = r.randint(-2, 2) if r.random() < 0.4 else 0
        row = row[-sh:] + row[:-sh] if sh else row
        out.append("".join(("X" if c == "." else ".") if r.random() < 0.12 else c for c in row))
    return out


def teary(t, right):
    """T_T eyes with a tear LED sliding down the stem."""
    g = [list(r) for r in (["XXXXXXX", "..XXX..", "...X...", "...X..."] + ["......."] * 3)]
    k = 3 + int(t * 14) % 4
    g[k][3] = "o"
    if k > 3:
        g[k - 1][3] = "x"
    return rows(g)


def a_static(p, q=None):
    return lambda t, right: (q if (right and q) else p)


# name, eye fn, colour, particle chars, particle colours
EXPRESSIONS = [
    ("DEAD", a_dead, PINK, "x*", (PINK, WHITE)),
    ("HAPPY", a_static(CARET), CYAN, "^*+", (CYAN, WHITE)),
    ("ANGRY", a_static(GT, LT), ORANGE, "#%&", (ORANGE, YELLOW)),
    ("SHOCKED", a_shocked, WHITE, "!", (WHITE, CYAN)),
    ("LOVE", a_love, PINK, "♥", (PINK,)),
    ("BORED", a_bored, CYAN, "z", (GREY,)),
    ("CONFUSED", a_confused, YELLOW, "?", (YELLOW,)),
    ("$$$", a_money, GREEN, "$", (GREEN,)),
    ("ALERT", a_alert, PINK, "!", (PINK, YELLOW)),
    ("SAD", a_static(SAD), CYAN, "·", (CYAN,)),
    ("DEDSEC", a_static(SKULL), PURPLE, "+*", (PURPLE, PINK)),
    ("WATCHING", a_static(PUPIL), WHITE, "·", (WHITE,)),
    ("WINK", a_wink, YELLOW, "*+", (YELLOW, PINK)),
    ("ROLLING EYES", a_roll, CYAN, "·", (CYAN, GREY)),
    ("LOADING", a_loading, GREEN, "·", (GREEN, CYAN)),
    ("GL1TCH", a_glitch, PINK, "#%▓░", (PINK, CYAN, YELLOW)),
]
GAZE_FREE = ("ROLLING EYES", "LOADING", "GL1TCH", "$$$")

QUOTES = [
    "hey hey hey. miss me?", "ctOS? more like ctOWNED.", "i put the 'fun' in 'dysfunctional'.",
    "nobody touch my mask.", "rule #1: don't get caught. rule #2: see rule #1.",
    "your password is your dog's name. lol.", "blume can suck my LEDs.",
    "we're gonna burn it all down. ethically.", "#DEDSEC FOREVER", "i'm not antisocial, i'm anti-surveillance.",
]
BYES = ["ok bye :(", "¿ya te vas? :(", "wait... come back :(", "fine. leave. see if i care :("]
STICKERS = ["(>_<)", "[x_x]", "\\(^o^)/", "<3 <3", "(-_-) zzz", "(o_O)", "$_$", "#WRENCH"]
LEVEL = {"X": 1.0, "o": 0.6, "x": 0.3}


def shift(pattern, gx, gy):
    out = []
    for r in range(7):
        row = ""
        for c in range(7):
            sr, sc = r - gy, c - gx
            row += pattern[sr][sc] if 0 <= sr < 7 and 0 <= sc < 7 else "."
        out.append(row)
    return out


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.stars = Starfield(w, h, n=120, colors=(DIM_PURPLE, PURPLE, PINK))
        self.glitch = Glitch(0.012)
        self.fx = PostFX()
        self.particles = Particles()
        self.typer = Typer(QUOTES, cps=16, hold=3.5)
        self.ticker = Ticker("WRENCH RADIO", QUOTES, color=PURPLE)
        self.stickers = [Sticker(w, h, random.choice(STICKERS)) for _ in range(2)]
        self.expr = random.choice(EXPRESSIONS)
        self.prev_expr = self.expr
        self.changed = 0
        self.next_change = 0
        self.blink_until = 0
        self.gaze = (0, 0)
        self.next_gaze = 0
        self.jolt = 0.0
        self.last = time.time()
        self.bye = None
        self.eq = []

        self.s = 3 if w >= 220 and h >= 56 else 2 if w >= 120 and h >= 38 else 1
        self.led_w = (2, 6, 8)[self.s - 1]
        self.led_h = self.s
        self.eye_w = 7 * self.led_w
        self.gap = self.eye_w // 2
        self.mask_w = self.eye_w * 2 + self.gap + 12
        self.mask_h = 7 * self.led_h + (6, 9, 11)[self.s - 1]
        self.mx = (w - self.mask_w) // 2
        self.my = max(3, (h - self.mask_h - 6) // 2)
        self.rot = Rotator(w / 2, self.my + self.mask_h / 2, dist=240)
        self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0
        x0, y0, x1, y1 = self.mx, self.my, self.mx + self.mask_w, self.my + self.mask_h
        ct, cb, rt = 4 * self.s, 7 * self.s, self.s + 1
        # chamfered helmet outline (convex, clockwise on screen)
        self.outline = [(x0 + ct, y0), (x1 - ct, y0), (x1, y0 + rt), (x1, y1 - 2 * rt - 1), (x1 - cb, y1),
                        (x0 + cb, y1), (x0, y1 - 2 * rt - 1), (x0, y0 + rt)]
        self.depth = 5.0 + 2 * self.s
        # Surface samples live in mask coordinates: grain and seams rotate with
        # the helmet instead of becoming a screen-space noise overlay.
        self.skin = []
        self.skin_palette = [blend((9, 11, 18), (78, 73, 96), k / 15) for k in range(16)]
        for py in range(self.mask_h * 2):
            yy = (py + 0.5) / 2
            cut = ct * max(0, 1 - yy / rt)
            cut = max(cut, cb * max(0, (yy - self.mask_h + 2 * rt + 1) / (2 * rt + 1)))
            for xx in range(math.ceil(cut), self.mask_w - math.ceil(cut)):
                hash_ = (xx * 73 + py * 151) % 137
                grain = 3 + ((xx // 2 + py // 2) & 1) + (hash_ < 9)
                if abs(xx - self.mask_w / 2) < 2:
                    grain += 3
                if py > (self.mask_h - 6) * 2 and xx % 4 == 0:
                    grain = 1
                self.skin.append((self.mx + xx, self.my + yy, grain))
        keep = (self.mx - 8, self.my - 3, self.mask_w + 16, self.mask_h + 9)
        self.panels = Panels(w, h, keepout=[keep], max_panels=6, kinds=["eq", "wave", "spark", "cube", "bars", "radar", "cam", "decrypt"])

    # ------------------------------------------------------------ projection
    def P(self, x, y, z=0.0):
        X, Y, Z = self.rot.rot(x, y, z)
        k = self.rot.dist / max(1.0, self.rot.dist + Z) * self.zoom
        return self.rot.cx + X * 2 * k + self.ox, self.rot.cy + Y * k + self.oy, Z

    def eye_origin(self, right):
        return self.mx + 6 + (self.eye_w + self.gap if right else 0), self.my + 3 + (0, 1, 2)[self.s - 1]

    # ------------------------------------------------------------ mask
    def draw_mask(self, s, now, rim_col):
        front = [self.P(x, y, 0) for (x, y) in self.outline]
        back = [self.P(x, y, self.depth) for (x, y) in self.outline]
        n = len(front)
        sides = []
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = front[i], front[j], back[j], back[i]
            # screen-space winding: only sides that face the viewer
            cross = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
            if cross >= 0:
                continue
            ex, ey = self.outline[j][0] - self.outline[i][0], self.outline[j][1] - self.outline[i][1]
            ln = math.hypot(ex * 0.5, ey) or 1
            nx, ny = ey / ln, -ex * 0.5 / ln
            lit = max(0.0, -0.5 * nx - 0.85 * ny)
            col = blend(blend(PURPLE, BLACK, 0.8), blend(PURPLE, WHITE, 0.1), lit * 0.75)
            sides.append(((a[2] + b[2] + c[2] + d[2]) / 4, [(p[0], p[1]) for p in (a, b, c, d)], col))
        for _, quad, col in sorted(sides, key=lambda q: -q[0]):
            fill_poly(s, quad, "█", col)
        fill_poly(s, [(p[0], p[1]) for p in front], "█", (18, 14, 28))
        highlight = self.mx + self.mask_w * (0.35 + 0.25 * math.sin(now * 0.4))
        project, palette = self.P, self.skin_palette
        for x, y, material in self.skin:
            spec = max(0, 4 - int(abs(x - highlight) / max(1, self.s * 2)))
            px, py, _ = project(x, y, -0.04)
            ix, iy = int(px), int(py * 2)
            if 0 <= ix < s.w and 0 <= iy < s.ph:
                s.pixel(ix, iy, palette[min(15, material + spec)])
                s.ch[iy // 2][ix] = " "
        # Recessed cheek panels, seam stitching and little brushed-metal screws.
        for right in (False, True):
            ax = self.mx + (self.mask_w - 5 if right else 5)
            for row in range(3):
                a = project(ax - 2, self.my + self.mask_h - 5 + row, -0.12)
                b = project(ax + 2, self.my + self.mask_h - 5 + row, -0.12)
                s.line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), "─", (94, 78, 116))
            for dy in (2, self.mask_h - 7):
                p = project(ax, self.my + dy, -0.15)
                s.put(int(p[0]), int(p[1]), "⊕", (120, 130, 148))
        for i in range(n):
            a, b = front[i], front[(i + 1) % n]
            s.line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), "█", rim_col)
        # bolts on the sides of the mask
        cy = self.my + self.mask_h // 2
        for side in (self.mx - 1, self.mx + self.mask_w + 1):
            for dy in (-1, 0, 1):
                x, y, _ = self.P(side, cy + dy, 1.5)
                s.put(int(x), int(y), "█", GREY)

    def draw_eye(self, s, right, pattern, old, reveal, color, glitch, dim=0.0):
        ox, oy = self.eye_origin(right)
        o = self.P(ox, oy, -0.6)
        u = self.P(ox + self.led_w, oy, -0.6)
        v = self.P(ox, oy + self.led_h, -0.6)
        ux, uy = u[0] - o[0], u[1] - o[1]
        vx, vy = v[0] - o[0], v[1] - o[1]
        dw = (self.led_w - (1, 2, 3)[self.s - 1]) / self.led_w
        off = (60, 45, 80)
        hi = blend(color, WHITE, 0.25)
        for r in range(7):
            pat = pattern if r < reveal else old
            for c in range(7):
                ch = pat[r][c]
                lvl = LEVEL.get(ch, 0.0)
                if glitch and random.random() < 0.05:
                    lvl = 0.0 if lvl else 1.0
                bx, by = o[0] + ux * c + vx * r, o[1] + uy * c + vy * r
                if lvl <= 0:
                    s.put(int(bx + ux * 0.4 + vx * 0.5), int(by + uy * 0.4 + vy * 0.5), "·", off)
                    continue
                col = hi if (r + c) % 3 == 0 else color
                if lvl < 1 or dim:
                    col = blend(off, col, lvl * (1 - dim))
                ax, ay = ux * dw, uy * dw
                fill_poly(s, [(bx, by), (bx + ax, by + ay), (bx + ax + vx, by + ay + vy), (bx + vx, by + vy)], "█", col)
                if self.s > 1:
                    # LED lens bevel: a white upper glint and a dim lower lip.
                    s.line(int(bx), int(by), int(bx + ax), int(by + ay), "▀", blend(col, WHITE, 0.4))
                    s.put(int(bx + ax + vx), int(by + ay + vy), "·", blend(col, BLACK, 0.55))

    def draw_mouth(self, s, now, color, talking):
        bars = self.mask_w // 4
        vy = self.my + self.mask_h - 3
        if len(self.eq) != bars:
            self.eq = [0.0] * bars
        lvl_all = DATA.level
        for i in range(bars):
            band = DATA.band(i, bars)
            target = (band * 3.2 + 0.4) if talking else band * (1.2 + lvl_all) * 1.4
            self.eq[i] += (target - self.eq[i]) * 0.5
            lvl = self.eq[i]
            x = self.mx + 6 + i * ((self.mask_w - 12) // bars)
            for k in range(int(lvl) + 1):
                px, py, _ = self.P(x, vy - k + 1, -0.3)
                if talking:
                    col = blend(color, WHITE, 0.4) if k == int(lvl) and k else blend(color, BLACK, 0.15 + k * 0.15)
                else:
                    col = blend(GREY, color, min(1.0, lvl * 0.5)) if k else GREY
                s.put(int(px), int(py), "▬", col)

    # ------------------------------------------------------------ main loop
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)

        if now > self.next_change:
            self.prev_expr = self.expr
            self.prev_t = now - self.changed
            self.expr = random.choice([e for e in EXPRESSIONS if e is not self.expr])
            self.changed = now
            self.next_change = now + random.uniform(3, 5.5)
            self.jolt = 1.0
            self.glitch.trigger(now, 0.12)
        if now > self.next_gaze:
            self.gaze = random.choice(((0, 0), (0, 0), (-1, 0), (1, 0), (0, -1), (1, 1), (-1, 1)))
            self.next_gaze = now + random.uniform(0.6, 2.0)
        if now > self.blink_until + 3 and random.random() < 0.01:
            self.blink_until = now + 0.15
        self.jolt = max(0.0, self.jolt - dt * 3)
        self.jolt = max(self.jolt, DATA.beat * 0.25)

        name, fn, color, pch, pcol = self.expr
        gx, gy = self.gaze if name not in GAZE_FREE else (0, 0)
        yaw = math.sin(now * 0.6) * 0.35 + gx * 0.1 + math.sin(now * 25) * 0.03 * self.jolt
        pitch = math.sin(now * 0.4) * 0.12 + gy * 0.06 - 0.1 * self.jolt
        roll = math.sin(now * 0.3) * 0.03 + 0.04 * self.jolt * math.sin(now * 18)
        if name == "CONFUSED":
            roll += 0.08 * math.sin(now * 2)
        self.rot.set(yaw, pitch, roll)

        self.stars.draw(s, dt, speed=6 + 10 * DATA.level)
        for st in self.stickers:
            st.step(s, dt, self.particles)
        self.panels.draw(s, now)

        rim = blend(GREY, PURPLE, 0.4 + 0.3 * pulse(now, 1.5))
        rim = blend(rim, color, DATA.beat * 0.5)
        self.draw_mask(s, now, rim)

        t = now - self.changed
        if name == "GL1TCH":
            color = random.choice((PINK, CYAN, YELLOW)) if random.random() < 0.3 else color
        pn, pfn = self.prev_expr[0], self.prev_expr[1]
        lp, rp = fn(t, False), fn(t, True)
        olp, orp = pfn(t + 5, False), pfn(t + 5, True)
        if now < self.blink_until and name not in GAZE_FREE:
            lp = rp = olp = orp = DASH
        lp, rp = shift(lp, gx, gy), shift(rp, gx, gy)
        olp, orp = shift(olp, gx, gy), shift(orp, gx, gy)
        reveal = min(7, int(t * 35))
        g = glitch or (name == "GL1TCH" and random.random() < 0.5)
        self.draw_eye(s, False, lp, olp, reveal, color, g)
        self.draw_eye(s, True, rp, orp, reveal, color, g)

        if random.random() < 0.25:
            falls = name in ("$$$", "SAD")
            for right in (False, True):
                ox, oy = self.eye_origin(right)
                px, py, _ = self.P(ox + self.eye_w / 2, oy, -1)
                vy = random.uniform(2, 6) if falls else -random.uniform(3, 8)
                self.particles.add(px + random.uniform(-6, 6), py, random.uniform(-4, 4), vy,
                                   random.uniform(1, 2), random.choice(pch), random.choice(pcol),
                                   gravity=4 if falls else -1)

        # mouth vent: an equalizer driven by the music, louder when Wrench is talking
        talking = self.typer.typing(now)
        self.draw_mouth(s, now, color, talking)

        self.particles.step(s, dt)
        label = "[ MOOD: %s ]" % name
        if name == "LOADING":
            label = "[ MOOD: LOADING %02d%% ]" % min(99, int(t / 3.5 % 1 * 100))
        s.center(self.my + self.mask_h + 2, label, color)
        self.typer.draw(s, self.my + self.mask_h + 4, now, color=WHITE, prompt="wrench> ", glitch=glitch)

        s.text(2, 0, "DEDSEC // WRENCH.EXE", PINK)
        s.text(2, 1, "LED MATRIX 2x49 // YAW %+04d°" % math.degrees(yaw), GREY)
        sig = "SIGNAL " + "▮" * random.randint(3, 5) + "▯" * 2
        s.text(self.w - len(sig) - 2, 0, sig, CYAN)
        self.ticker.draw(s, self.h - 1, now)
        self.fx.apply(s, now, glitch)

    # ------------------------------------------------------------ goodbye
    def farewell(self, s, now, t):
        """Sad mask with tears that shrinks and falls away (t: 0..1 over 0.8 s)."""
        dt, self.last = min(0.1, max(0.0, now - self.last)), now
        if self.bye is None or t < 0.05 and getattr(self, "bye_t", 1) > 0.5:
            self.bye = random.choice(BYES)
            self.particles = Particles()
        self.bye_t = t
        e = ease_out(max(0.0, (t - 0.25) / 0.75))
        self.zoom = 1 - 0.8 * e
        self.oy = (max(0.0, t - 0.3) / 0.7) ** 2 * self.h * 0.75
        self.ox = math.sin(t * 9) * 1.5 * (1 - t)
        self.rot.set(math.sin(t * 4) * 0.2, -0.15 + 0.5 * e, 0.5 * e * e)
        self.stars.draw(s, dt, speed=-14)
        self.draw_mask(s, now, blend(GREY, CYAN, 0.3))
        for right in (False, True):
            eye = teary(t * 0.8, right)
            self.draw_eye(s, right, eye, eye, 7, CYAN, False)
        # tears roll out of the eyes
        for right in (False, True):
            if random.random() < 0.7:
                ox, oy = self.eye_origin(right)
                px, py, _ = self.P(ox + self.eye_w * 0.5, oy + 7 * self.led_h, -1)
                self.particles.add(px + random.uniform(-1, 1), py, random.uniform(-2, 2), random.uniform(2, 5), 0.8,
                                   random.choice("•●"), blend(CYAN, WHITE, 0.4), gravity=40)
        self.particles.step(s, dt)
        # mouth: a sad little wobble
        bars = self.mask_w // 4
        vy = self.my + self.mask_h - 3
        for i in range(bars):
            x = self.mx + 6 + i * ((self.mask_w - 12) // bars)
            curve = int(round(1.5 * math.sin(math.pi * (i + 0.5) / bars)))
            px, py, _ = self.P(x, vy - curve + 1, -0.3)
            s.put(int(px), int(py), "▬", CYAN)
        # speech bubble typed out above the mask
        txt = self.bye[:max(1, int(len(self.bye) * min(1.0, t * 2.5)))]
        bw = len(self.bye) + 4
        top, _, _ = self.P(self.mx + self.mask_w * 0.7, self.my, 0)
        bx = max(1, min(self.w - bw - 1, int(top) - bw // 2))
        by = max(0, int(self.P(self.mx, self.my, 0)[1]) - 4)
        s.box(bx, by, bw, 3, WHITE)
        s.text(bx + 2, by + 1, txt, YELLOW if int(t * 8) % 2 else WHITE)
        s.put(bx + bw // 3, by + 3, "\\", WHITE)
        self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0

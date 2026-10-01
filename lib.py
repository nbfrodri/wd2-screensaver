"""Shared drawing helpers for the DedSec screensavers."""

import math
import random
from functools import lru_cache

PINK = (255, 15, 123)
CYAN = (0, 229, 255)
YELLOW = (245, 230, 10)
GREEN = (57, 255, 20)
WHITE = (240, 240, 255)
PURPLE = (138, 43, 226)
ORANGE = (255, 120, 0)
DIM_PINK = (90, 10, 50)
DIM_CYAN = (0, 70, 85)
DIM_PURPLE = (45, 15, 75)
GREY = (70, 70, 90)
DARK = (30, 30, 42)
BLACK = (0, 0, 0)

NEON = (PINK, CYAN, YELLOW, GREEN, PURPLE)
RAIN_CHARS = "0101ABCDEF<>/\\#$%&*+=?"
NOISE_CHARS = "▀▄█▌▐░▒▓"


@lru_cache(maxsize=4096)
def _dim_color(rgb):
    return (rgb[0] * 4 // 5, rgb[1] * 4 // 5, rgb[2] * 4 // 5)


@lru_cache(maxsize=8192)
def _color_escape(fg, bg):
    parts = []
    if fg is not None:
        parts.append("38;2;%d;%d;%d" % fg)
    if bg != -1:
        parts.append("49" if bg is None else "48;2;%d;%d;%d" % bg)
    return "\033[" + ";".join(parts) + "m"


def blend(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def pulse(now, speed=2.0, phase=0.0):
    return (1 + math.sin(now * speed + phase)) / 2


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def overlaps(a, b, margin=1):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + margin <= bx or bx + bw + margin <= ax or ay + ah + margin <= by or by + bh + margin <= ay)


class Screen:
    """Cell canvas with three layers per cell, rendered with diffing.

    - text:   ch / fg      (put, text, box, ...)
    - pixels: pt / pb      half-block pixels, 2 per cell vertically (pixel, pixel_line, ...)
    - bg:     bg           background colour per cell (set_bg, gradient_bg)
    Text wins over pixels; pixels win over plain background.
    """

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = h * 2
        self.prev = None
        self.clear()

    def clear(self):
        w, h = self.w, self.h
        self.ch = [[" "] * w for _ in range(h)]
        self.fg = [[None] * w for _ in range(h)]
        self.bg = [[None] * w for _ in range(h)]
        self.pt = [[None] * w for _ in range(h)]
        self.pb = [[None] * w for _ in range(h)]

    def invalidate(self):
        """Force a full repaint on the next render."""
        self.prev = None

    # ------------------------------------------------------------ snapshots
    def snapshot(self):
        return tuple([row[:] for row in layer] for layer in (self.ch, self.fg, self.bg, self.pt, self.pb))

    def restore(self, snap):
        self.ch, self.fg, self.bg, self.pt, self.pb = ([row[:] for row in layer] for layer in snap)

    # ------------------------------------------------------------ text layer
    def put(self, x, y, c, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ch[y][x] = c
            self.fg[y][x] = color
            if c == " ":
                self.pt[y][x] = self.pb[y][x] = None

    def text(self, x, y, s, color):
        if 0 <= y < self.h:
            rc, rf = self.ch[y], self.fg[y]
            for i, c in enumerate(s):
                if 0 <= x + i < self.w:
                    rc[x + i] = c
                    rf[x + i] = color

    def center(self, y, s, color):
        self.text((self.w - len(s)) // 2, y, s, color)

    def fill(self, x0, y0, w, h, c=" ", color=None):
        for y in range(max(0, y0), min(self.h, y0 + h)):
            rc, rf, rt, rb = self.ch[y], self.fg[y], self.pt[y], self.pb[y]
            for x in range(max(0, x0), min(self.w, x0 + w)):
                rc[x] = c
                rf[x] = color
                rt[x] = rb[x] = None

    def box(self, x, y, w, h, color, title=None, double=False, title_color=None):
        tl, tr, bl, br, hz, vt = "╔╗╚╝═║" if double else "┌┐└┘─│"
        self.fill(x, y, w, h)
        self.text(x, y, tl + hz * (w - 2) + tr, color)
        for i in range(1, h - 1):
            self.put(x, y + i, vt, color)
            self.put(x + w - 1, y + i, vt, color)
        self.text(x, y + h - 1, bl + hz * (w - 2) + br, color)
        if title and w > len(title) + 4:
            self.text(x + 2, y, " " + title + " ", title_color or color)

    def brackets(self, x, y, w, h, color, arm=2):
        """Targeting corner brackets."""
        for cx, cy, a, b in ((x, y, "┌", "─"), (x + w - 1, y, "┐", "─"), (x, y + h - 1, "└", "─"), (x + w - 1, y + h - 1, "┘", "─")):
            self.put(cx, cy, a, color)
            d = 1 if cx == x else -1
            for i in range(1, arm + 1):
                self.put(cx + d * i, cy, b, color)

    def line(self, x0, y0, x1, y1, c, color):
        pts = line_points(x0, y0, x1, y1)
        for x, y in pts:
            self.put(x, y, c, color)
        return pts

    def sprite(self, lines, left, top, color, glitch=False):
        self.sprite_fn(lines, left, top, lambda x, y: color, glitch)

    def sprite_fn(self, lines, left, top, colfn, glitch=False):
        """Draw text art coloured per cell; with glitch, offsets rows and splits RGB."""
        offsets = [random.randint(-6, 6) if glitch and random.random() < 0.35 else 0 for _ in lines]
        if glitch:
            for dx, col in ((-2, CYAN), (2, PINK)):
                for i, line in enumerate(lines):
                    for j, c in enumerate(line):
                        if c != " ":
                            self.put(left + j + dx + offsets[i], top + i, c, col)
        for i, line in enumerate(lines):
            for j, c in enumerate(line):
                if c != " ":
                    self.put(left + j + offsets[i], top + i, c, colfn(j, i))

    def noise_lines(self, count=None):
        for _ in range(count or random.randint(1, 3)):
            y = random.randrange(self.h)
            x0 = random.randrange(self.w)
            col = random.choice((PINK, CYAN, YELLOW))
            for x in range(x0, min(self.w, x0 + random.randint(5, max(6, self.w // 3)))):
                self.put(x, y, random.choice(NOISE_CHARS), col)

    # ------------------------------------------------------------ pixel layer (w x 2h)
    def pixel(self, x, py, color):
        if 0 <= x < self.w and 0 <= py < self.ph:
            if py & 1:
                self.pb[py >> 1][x] = color
            else:
                self.pt[py >> 1][x] = color

    def get_pixel(self, x, py):
        if 0 <= x < self.w and 0 <= py < self.ph:
            return (self.pb if py & 1 else self.pt)[py >> 1][x]
        return None

    def pixel_line(self, x0, y0, x1, y1, color):
        for x, y in line_points(int(x0), int(y0), int(x1), int(y1)):
            self.pixel(x, y, color)

    def pixel_rect(self, x0, y0, w, h, color):
        for py in range(max(0, int(y0)), min(self.ph, int(y0 + h))):
            layer = (self.pb if py & 1 else self.pt)[py >> 1]
            for x in range(max(0, int(x0)), min(self.w, int(x0 + w))):
                layer[x] = color

    def pixel_circle(self, cx, cy, r, color, fill=True):
        """Circle in pixel space (pixels are ~square: 1 col x 1 half-row)."""
        r2 = r * r
        for py in range(max(0, int(cy - r)), min(self.ph, int(cy + r) + 1)):
            dy = py - cy
            if dy * dy > r2:
                continue
            span = math.sqrt(r2 - dy * dy)
            if fill:
                for x in range(max(0, int(cx - span)), min(self.w, int(cx + span) + 1)):
                    self.pixel(x, py, color)
            else:
                self.pixel(int(cx - span), py, color)
                self.pixel(int(cx + span), py, color)

    def pixel_poly(self, pts, color):
        """Scanline fill of a convex polygon given in pixel coordinates."""
        ys = [p[1] for p in pts]
        n = len(pts)
        for py in range(max(0, int(min(ys))), min(self.ph - 1, int(max(ys))) + 1):
            yc = py + 0.5
            xs = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
            if len(xs) >= 2:
                layer = (self.pb if py & 1 else self.pt)[py >> 1]
                for x in range(max(0, int(min(xs))), min(self.w - 1, int(max(xs))) + 1):
                    layer[x] = color

    # ------------------------------------------------------------ background layer
    def set_bg(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.bg[y][x] = color

    def gradient_bg(self, top, bottom, y0=0, y1=None):
        y1 = self.h if y1 is None else y1
        span = max(1, y1 - y0 - 1)
        for y in range(max(0, y0), min(self.h, y1)):
            col = blend(top, bottom, (y - y0) / span)
            self.bg[y] = [col] * self.w
            # pixels default to the sky colour so half-blocks blend in
        return

    # ------------------------------------------------------------ post effects
    def shift_row(self, y, dx):
        if 0 <= y < self.h and dx:
            for layer, blank in ((self.ch, " "), (self.fg, None), (self.bg, None), (self.pt, None), (self.pb, None)):
                row = layer[y]
                if dx > 0:
                    layer[y] = [blank] * dx + row[:-dx]
                else:
                    layer[y] = row[-dx:] + [blank] * -dx

    def tint_row(self, y, color, t, x0=0, x1=None):
        if 0 <= y < self.h:
            x1 = self.w if x1 is None else min(self.w, x1)
            for layer in (self.fg, self.pt, self.pb, self.bg):
                row = layer[y]
                for x in range(max(0, x0), x1):
                    if row[x] is not None:
                        row[x] = blend(row[x], color, t)

    # ------------------------------------------------------------ output
    def render(self, crt=True):
        """Return the escape sequence that turns the previous frame into this one."""
        out = []
        prev = self.prev
        new = []
        last_fg = last_bg = 0  # sentinel: unknown terminal state
        cur = None
        w = self.w
        for y in range(self.h):
            rc, rf, rbg, rt, rb = self.ch[y], self.fg[y], self.bg[y], self.pt[y], self.pb[y]
            prow = prev[y] if prev is not None else None
            dim = crt and (y & 1)
            row = [None] * w
            for x in range(w):
                c = rc[x]
                bg = rbg[x]
                if c != " ":
                    fg = rf[x] or WHITE
                else:
                    t, b = rt[x], rb[x]
                    if t is not None:
                        c, fg = "▀", t
                        if b is not None:
                            bg = b
                    elif b is not None:
                        c, fg = "▄", b
                    else:
                        fg = None
                if dim:
                    if fg is not None:
                        fg = _dim_color(fg)
                    if bg is not None:
                        bg = _dim_color(bg)
                cell = (c, fg, bg)
                row[x] = cell
                if prow is not None and prow[x] == cell:
                    continue
                if cur != (x, y):
                    out.append("\033[%d;%dH" % (y + 1, x + 1))
                change_fg, change_bg = None, -1
                if fg is not None and fg != last_fg:
                    change_fg = fg
                    last_fg = fg
                if bg != last_bg:
                    change_bg = bg
                    last_bg = bg
                if change_fg is not None or change_bg != -1:
                    out.append(_color_escape(change_fg, change_bg))
                out.append(c)
                cur = (x + 1, y)
            new.append(row)
        self.prev = new
        return "".join(out)


def line_points(x0, y0, x1, y1):
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class Rain:
    """Sparse falling data streams in the background."""

    def __init__(self, w, h, step=3, colors=(DIM_PINK, DIM_CYAN, DIM_CYAN), chars=RAIN_CHARS):
        self.w, self.h, self.colors, self.chars = w, h, colors, chars
        self.drops = [self.new(x, True) for x in range(0, w, step)]

    def new(self, x, anywhere=False):
        return {
            "x": x,
            "y": random.uniform(-self.h, self.h) if anywhere else random.uniform(-self.h * 1.5, 0),
            "speed": random.uniform(0.3, 1.2),
            "len": random.randint(4, 16),
            "color": random.choice(self.colors),
        }

    def draw(self, scr):
        for i, d in enumerate(self.drops):
            d["y"] += d["speed"]
            head = int(d["y"])
            for k in range(d["len"]):
                col = blend(d["color"], WHITE, 0.35) if k == 0 else blend(d["color"], BLACK, k / d["len"])
                scr.put(d["x"], head - k, random.choice(self.chars), col)
            if head - d["len"] > self.h:
                self.drops[i] = self.new(d["x"])


class Typer:
    """Cycles through lines, typing each one out character by character."""

    def __init__(self, lines, cps=18, hold=4.0, shuffle=True):
        self.lines = list(lines)
        if shuffle:
            random.shuffle(self.lines)
        self.cps, self.hold = cps, hold
        self.idx, self.start = 0, None

    def current(self, now):
        if self.start is None:
            self.start = now
        line = self.lines[self.idx]
        elapsed = now - self.start
        if elapsed > len(line) / self.cps + self.hold:
            self.idx = (self.idx + 1) % len(self.lines)
            self.start = now
            return "", self.lines[self.idx]
        return line[: int(elapsed * self.cps)], line

    def typing(self, now):
        txt, full = self.current(now)
        return len(txt) < len(full)

    def draw(self, scr, y, now, color=WHITE, prompt="> ", glitch=False):
        txt, full = self.current(now)
        if glitch:
            txt = "".join(random.choice("#$%&@!?") if random.random() < 0.2 else c for c in txt)
        x = (scr.w - len(full)) // 2
        scr.text(x - len(prompt), y, prompt, YELLOW)
        scr.text(x, y, txt, color)
        scr.text(x + len(txt), y, "█" if int(now * 3) % 2 == 0 else " ", YELLOW)


class Glitch:
    """Random short glitch bursts."""

    def __init__(self, chance=0.02):
        self.chance, self.until = chance, 0

    def active(self, now):
        if now >= self.until and random.random() < self.chance:
            self.until = now + random.uniform(0.1, 0.45)
        return now < self.until

    def trigger(self, now, duration=0.4):
        self.until = max(self.until, now + duration)

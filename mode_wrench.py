"""WRENCH: Wrench's LED mask in 3D inside his neon-lit garage: hooded, riveted face plate with
animated emoticon eyes, a welding bench throwing sparks, hologram emoticons and wall graffiti."""

import math
import random
import time
from functools import lru_cache

from engine3d import Rotator, Starfield
from lib import (BLACK, CYAN, DIM_PURPLE, GREEN, GREY, PINK, PURPLE, WHITE, YELLOW,
                 ORANGE, Glitch, Screen, Typer, blend, ease_out, line_points, pulse)
from sysdata import DATA
from widgets import Particles, PostFX, Ticker

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


SPARK = [(255, 255, 235), (255, 240, 160), (255, 205, 70), (255, 150, 30), (230, 90, 10), (150, 40, 5)]
EMOTES = ["(^_^)", "x_x", "<3", "^_^", "$_$", "(o_O)", "T_T", ">:)", "\\o/", ":P", "[x_x]", "#WRENCH", ":3", "o7", "(-_-)"]

# 5x5 spray-tag letters for the wall graffiti
TAG = {
    "W": ["X...X", "X...X", "X.X.X", "XX.XX", "X...X"],
    "R": ["XXXX.", "X...X", "XXXX.", "X..X.", "X...X"],
    "E": ["XXXXX", "X....", "XXXX.", "X....", "XXXXX"],
    "N": ["X...X", "XX..X", "X.X.X", "X..XX", "X...X"],
    "C": [".XXXX", "X....", "X....", "X....", ".XXXX"],
    "H": ["X...X", "X...X", "XXXXX", "X...X", "X...X"],
}


def _stops(stops, n):
    out = []
    for i in range(n):
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= i <= b:
                out.append(blend(ca, cb, (i - a) / max(1, b - a)))
                break
    return out


METAL = _stops([(0, (4, 4, 8)), (8, (20, 20, 30)), (16, (44, 46, 60)), (24, (88, 92, 110)),
                (32, (165, 170, 190)), (39, (226, 230, 242))], 40)
FIXED = [(2, 2, 4), (215, 220, 232), (118, 122, 140), (7, 7, 11), (3, 3, 6), (28, 29, 38), (60, 18, 40)]
GLASS = (4, 5, 9)


@lru_cache(maxsize=16384)
def _fade(color, level):
    return (color[0] * level // 24, color[1] * level // 24, color[2] * level // 24)


def tint(s, x, py, col, f):
    """Blend one pixel toward col (used for light and translucent projections)."""
    if 0 <= x < s.w and 0 <= py < s.ph:
        layer = (s.pb if py & 1 else s.pt)[py >> 1]
        c = layer[x]
        layer[x] = blend(c, col, f) if c is not None else blend(BLACK, col, f)


def pfill(s, pts, col):
    """Convex polygon fill in pixel space with centre sampling (no fat edges)."""
    ys = [p[1] for p in pts]
    n = len(pts)
    for py in range(max(0, int(min(ys) + 0.5)), min(s.ph - 1, int(max(ys) + 0.5)) + 1):
        yc = py + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
        if len(xs) >= 2:
            xa, xb = int(min(xs) + 0.5), int(max(xs) - 0.5)
            if xb < xa:
                xb = xa
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            left, right = max(0, xa), min(s.w - 1, xb) + 1
            if left < right:
                layer[left:right] = [col] * (right - left)


def solve_homography(src, dst):
    """Projective map src(x, y) -> dst(u, v) from four point pairs, or None."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    for i in range(8):
        p = max(range(i, 8), key=lambda r: abs(A[r][i]))
        if abs(A[p][i]) < 1e-9:
            return None
        A[i], A[p] = A[p], A[i]
        piv = A[i][i]
        row = [a / piv for a in A[i]]
        A[i] = row
        for r in range(8):
            if r != i and A[r][i]:
                f = A[r][i]
                A[r] = [a - f * b for a, b in zip(A[r], row)]
    return [A[r][8] for r in range(8)]


def backfill(s):
    """Give text cells the colour of the pixels they cover, so glyphs never punch black holes."""
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


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.stars = Starfield(w, h, n=120, colors=(DIM_PURPLE, PURPLE, PINK))
        self.glitch = Glitch(0.012)
        self.fx = PostFX()
        self.particles = Particles()
        self.typer = Typer(QUOTES, cps=16, hold=3.5)
        self.ticker = Ticker("WRENCH RADIO", QUOTES, color=PURPLE)
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
        self.led_w = (2, 5, 7)[self.s - 1]
        self.led_h = self.s
        self.eye_w = 7 * self.led_w
        self.gap = self.eye_w // 2
        self.mask_w = self.eye_w * 2 + self.gap + 12
        self.mask_h = 7 * self.led_h + (7, 15, 19)[self.s - 1]
        self.mx = (w - self.mask_w) // 2
        self.my = max(3, (h - self.mask_h - 7) // 2)
        self.rot = Rotator(w / 2, self.my + self.mask_h / 2, dist=240)
        self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0
        self.depth = 5.0 + 2 * self.s
        self.bench = (h - 5 if h < 34 else h - 6) * 2          # bench top, pixel row
        self.side = max(4, int(w / 2 - (self.mask_w / 2 + 2 + 2 * self.s)))
        nb = max(5, int(self.mask_w * 0.36) // 2)
        self.mouth_n = nb
        self.mouth_x0 = self.mx + (self.mask_w - (nb * 2 - 1)) // 2

        mw, mh = self.mask_w, self.mask_h
        self.outline = []
        steps = 14
        for i in range(steps + 1):
            ny = i / steps
            self.outline.append((mw / 2 + self.hw(ny) * mw / 2, ny * mh))
        for i in range(steps, -1, -1):
            ny = i / steps
            self.outline.append((mw / 2 - self.hw(ny) * mw / 2, ny * mh))
        # hood: rounded cowl behind the plate, opening onto the shoulders
        rx, ry, hc = mw / 2 + 2 + 2 * self.s, mh * 0.56 + 1.5 + 0.7 * self.s, mh * 0.55
        self.hood = [(mw / 2 + rx * 0.93, mh + 1.5)]
        for i in range(17):
            a = -i / 16 * math.pi
            self.hood.append((mw / 2 + math.cos(a) * rx, hc + math.sin(a) * ry))
        self.hood.append((mw / 2 - rx * 0.93, mh + 1.5))
        self.folds = [[(mw / 2 + math.cos(-a / 10 * math.pi) * rx * k, hc + math.sin(-a / 10 * math.pi) * ry * k)
                       for a in range(2, 9)] for k in (0.8, 0.9)]
        self.build_texture()
        self.build_backdrop()
        self.sparks = []
        self.weld_on, self.weld_until = False, 0.0
        self.holos = []
        self.next_holo = [0.0, 1.5]
        self.sign_flicker = 0.0

    # ------------------------------------------------------------ mask geometry
    @staticmethod
    def hw(ny):
        """Half width of the face plate (0..1) at relative height ny."""
        if ny < 0.18:
            return 0.8 + 0.2 * math.sqrt(max(0.0, 1 - ((0.18 - ny) / 0.18) ** 2))
        if ny < 0.62:
            return 1.0
        if ny < 0.92:
            return 1 - 0.38 * ((ny - 0.62) / 0.3) ** 1.3
        return 0.62 * (0.55 + 0.45 * math.sqrt(max(0.0, 1 - ((ny - 0.92) / 0.08) ** 2)))

    def inside(self, u, v):
        if v < 0 or v > self.mask_h:
            return False
        return abs(u - self.mask_w / 2) <= self.hw(v / self.mask_h) * self.mask_w / 2

    def build_texture(self):
        """Face plate texture in mask space (cols x half-rows). Codes: <64 metal level (gets sheen),
        100+k fixed colour, 1000+ visor glass (glow cell * 3 + reflection)."""
        mw, mh, s = self.mask_w, self.mask_h, self.s
        tw, th = mw, mh * 2
        ins = self.inside
        eyes = []
        for right in (False, True):
            ex, ey = self.eye_origin(right)
            eyes.append((ex - self.mx, ey - self.my))
        vis_y0, vis_y1 = eyes[0][1] - 0.5, eyes[0][1] + 7 * self.led_h + 0.25
        rivets = {}
        for nx in (-0.62, -0.31, 0.0, 0.31, 0.62):
            rivets[(int(mw / 2 + nx * mw / 2), int(0.07 * th) + 1)] = 1
        for ny in (0.3, 0.5, 0.68):
            for sgn in (-1, 1):
                rivets[(int(mw / 2 + sgn * (mw / 2 - 2.6)), int(ny * th))] = 1
        jaw = eyes[0][1] + 7 * self.led_h + 1.2
        mouth_l = self.mouth_x0 - self.mx - 1.5
        mouth_r = mouth_l + self.mouth_n * 2 + 2
        mouth_t = mh - 2.6 - max(1, int(mh * 0.2))
        rnd = random.Random(7)
        scratches = [(rnd.uniform(4, mw - 4), rnd.uniform(1, mh - 2), rnd.choice((-1, 1)), rnd.randint(3, 6)) for _ in range(5)]
        tex = []
        for pv in range(th):
            v = (pv + 0.5) / 2
            ny = v / mh
            row = []
            for u_ in range(tw):
                u = u_ + 0.5
                if not ins(u, v):
                    row.append(-1)
                    continue
                nx = (u - mw / 2) / (mw / 2)
                L = 7 + 6 * math.cos(nx * 1.3) + 3 * (1 - ny) - 2 * nx
                code = None
                # visor glass and its recessed frame
                for e, (ex, ey) in enumerate(eyes):
                    x0, x1 = ex - 1.0, ex + self.eye_w + 0.3
                    if x0 <= u < x1 and vis_y0 <= v < vis_y1:
                        corner = (u - x0 < 1 or x1 - u < 1) and (v - vis_y0 < 0.5 or vis_y1 - v < 0.5)
                        if not corner:
                            gc = max(-1, min(7, math.floor((u - ex) / self.led_w)))
                            gr = max(-1, min(7, math.floor((v - ey) / self.led_h)))
                            diag = (u - ex) - (v - ey) * 2.2
                            refl = 2 if 6 < diag < 7.5 else 1 if 3.5 < diag < 10 else 0
                            code = 1000 + (e * 81 + (gr + 1) * 9 + gc + 1) * 3 + refl
                            break
                    if x0 - 1 <= u < x1 + 1 and vis_y0 - 0.5 <= v < vis_y1 + 0.5:
                        L = 2 if (u < x0 or v < vis_y0) else 21
                if code is None:
                    if v > jaw and not (mouth_l <= u < mouth_r and v > mouth_t - 0.5):
                        # side vents on the cheeks: angled slots with a lit lower lip
                        k = (pv - int(jaw * 2) - 1) % 3
                        inner = abs(nx) > 0.42 and abs(nx) < self.hw(ny) - 0.12 and v < mh - 1.2
                        if inner and pv > jaw * 2 + 1:
                            if k == 0:
                                code = 100
                            elif k == 1:
                                L = 20
                    if mouth_l <= u < mouth_r and mouth_t <= v < mh - 0.6:
                        code = 103 if (u_ - int(mouth_l)) % 2 else 105
                    elif abs(v - jaw) < 0.5:
                        L = 3                               # seam between visor block and jaw
                    elif abs(v - jaw - 0.5) < 0.5:
                        L += 6
                    if code is None and v > jaw and abs(u - mw / 2) < 0.6 and v < mouth_t:
                        L = 4
                if code is None:
                    # bevelled rim: light from the upper left
                    if not ins(u - 1.1, v - 0.5) or not ins(u, v - 0.6):
                        L = 27
                    elif not ins(u + 1.1, v + 0.5) or not ins(u, v + 0.6):
                        L = 2
                    elif not ins(u - 2.2, v - 1.0):
                        L += 5
                    elif not ins(u + 2.2, v + 1.0):
                        L -= 4
                    for sx, sy, d, ln in scratches:
                        if 0 <= (u - sx) < ln and abs((v - sy) - d * (u - sx) * 0.25) < 0.26:
                            L += 6
                    rv = (u_, pv)
                    if rv in rivets:
                        code = 101
                    elif (u_ - 1, pv) in rivets or (u_, pv - 1) in rivets:
                        code = 102
                    elif (u_ - 1, pv - 1) in rivets:
                        code = 104
                if code is None:
                    code = max(1, min(31, int(L)))
                row.append(code)
            tex.append(row)
        self.tex, self.tw, self.th = tex, tw, th

    # ------------------------------------------------------------ backdrop (static, baked once)
    def build_backdrop(self):
        w, h = self.w, self.h
        b = Screen(w, h)
        ph, bt, side = b.ph, self.bench, self.side
        rnd = random.Random(11)
        self.sign_c = (w - side / 2, 3 + max(4, min(int(side * 0.27), 6 + 3 * self.s)) + 2)
        rs = max(4, min(int(side * 0.27), 6 + 3 * self.s))
        self.sign_r = rs
        wx, wy = 0.12 * w, bt - 4
        # cinder-block wall, lit by the neon smiley (pink, right) and the welding bench (cool, left)
        bwid, bhei = 12, 6
        shade = {}
        for py in range(ph):
            r = py // bhei
            off = (r & 1) * bwid // 2
            layer = (b.pb if py & 1 else b.pt)[py >> 1]
            for x in range(w):
                bx = (x + off) // bwid
                if py % bhei == 0 or (x + off) % bwid == 0:
                    base = (8, 8, 12)
                else:
                    key = (r, bx)
                    if key not in shade:
                        shade[key] = rnd.randint(-3, 3)
                    k = shade[key] + ((x * 7 + py * 13) % 11 == 0) * 2
                    base = (17 + k, 16 + k, 24 + k)
                dsx, dsy = (x - self.sign_c[0]) / (rs * 3.5), (py - self.sign_c[1]) / (rs * 3.0)
                pink = math.exp(-(dsx * dsx + dsy * dsy)) * 0.55
                dwx, dwy = (x - wx) / (side * 1.2), (py - wy) / (ph * 0.45)
                cool = math.exp(-(dwx * dwx + dwy * dwy)) * 0.35
                top = max(0.0, 1 - py / (ph * 0.9))
                c = blend(base, (0, 0, 0), 0.35 * (1 - top) * (abs(x - w / 2) > w * 0.3))
                if pink > 0.02:
                    c = blend(c, (120, 10, 70), pink)
                if cool > 0.02:
                    c = blend(c, (20, 60, 110), cool)
                layer[x] = c
        self.draw_tag(b, rnd)
        self.draw_pegboard(b, rnd)
        self.draw_torso(b)
        self.draw_bench(b, rnd)
        self.static = (b.pt, b.pb)
        # neon smiley tube pixels (+ halo tints pre-blended against the wall)
        cx, cy = self.sign_c
        tube = set()
        for i in range(int(rs * 7)):
            a = i / (rs * 7) * math.tau
            tube.add((int(cx + math.cos(a) * rs), int(cy + math.sin(a) * rs), 0))
        for i in range(int(rs * 3) + 1):
            a = math.radians(25 + 130 * i / (rs * 3))
            tube.add((int(cx + math.cos(a) * rs * 0.55), int(cy + math.sin(a) * rs * 0.5), 1))
        for sx in (-1, 1):
            ex, ey = cx + sx * rs * 0.38, cy - rs * 0.25
            for d in range(-2, 3):
                tube.add((int(ex + d * rs / 9), int(ey - (2 - abs(d)) * rs / 9), 2))
        self.tube = sorted(tube)
        halo = {}
        pts = {(x, y) for x, y, _ in tube}
        for x, y, _ in tube:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    q = (x + dx, y + dy)
                    if q not in pts and 0 <= q[0] < w and 0 <= q[1] < ph:
                        f = 0.45 / (1 + dx * dx + dy * dy)
                        halo[q] = max(halo.get(q, 0), f)
        self.halo = [(x, y, blend(b.get_pixel(x, y) or BLACK, (255, 30, 140), f)) for (x, y), f in halo.items()]
        # weld glow: three pre-blended intensities around the torch tip
        tx, ty = self.torch_tip
        R = 6 + 3 * self.s
        self.weld_glow = []
        for lvl in (0.25, 0.45, 0.7):
            lst = []
            for dy in range(-R, R + 1):
                for dx in range(-R * 2, R * 2 + 1):
                    d = math.hypot(dx / 2, dy) / R
                    x, y = tx + dx, ty + dy
                    if d < 1 and 0 <= x < w and 0 <= y < ph:
                        base = b.get_pixel(x, y) or BLACK
                        lst.append((x, y, blend(base, (140, 200, 255), lvl * (1 - d) ** 2)))
            self.weld_glow.append(lst)

    def draw_tag(self, b, rnd):
        """Vertical pink WRENCH throw-up on the left wall, plus a cyan X_X stencil."""
        side, bt = self.side, self.bench
        avail = bt - 6
        sc = 1
        for k in (3, 2):
            if 6 * 5 * k + 5 * k <= avail and side >= 5 * k + 4:
                sc = k
                break
        gap = sc
        total = 6 * 5 * sc + 5 * gap
        x0 = max(1, int(side * 0.1))
        y0 = max(4, (bt - 2 - total) // 2)
        paint, edge = (225, 25, 120), (40, 6, 34)
        cells = set()
        for i, ch in enumerate("WRENCH"):
            jx = int(round(math.sin(i * 1.7) * sc * 0.8))
            for r, row in enumerate(TAG[ch]):
                for c, v in enumerate(row):
                    if v == "X":
                        for a in range(sc):
                            for d in range(sc):
                                cells.add((x0 + jx + c * sc + a, y0 + i * (5 * sc + gap) + r * sc + d))
        for x, y in cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1)):
                if (x + dx, y + dy) not in cells:
                    b.pixel(x + dx, y + dy, edge)
        for x, y in cells:
            k = rnd.randint(-18, 12)
            b.pixel(x, y, (min(255, paint[0] + k), paint[1] + k // 3, max(0, paint[2] + k)))
        for x, y in cells:
            if (x, y + 1) not in cells and rnd.random() < 0.3:
                for d in range(1, rnd.randint(2, 3 + 2 * sc)):
                    b.pixel(x, y + d, blend(paint, BLACK, 0.25 + d * 0.06))
            if rnd.random() < 0.25:
                ox, oy = x + rnd.randint(-2, 2), y + rnd.randint(-2, 2)
                if (ox, oy) not in cells:
                    c = b.get_pixel(ox, oy) or BLACK
                    b.pixel(ox, oy, blend(c, paint, 0.35))
        # highlight dots: the classic white shine on a throw-up
        for x, y in list(cells)[::23]:
            b.pixel(x, y, (255, 200, 230))
        self.tag_right = x0 + 5 * sc + sc + 1
        # stencilled X_X face between the tag and the hood
        room = side - self.tag_right
        r = min(room // 2 - 1, 4 + 2 * self.s)
        if r >= 4:
            cx, cy = self.tag_right + room / 2, y0 + total * 0.35
            cyan = (0, 170, 200)
            for i in range(int(r * 8)):
                a = i / (r * 8) * math.tau
                if (i // 3) % 5 == 4:
                    continue                                   # stencil bridges
                b.pixel(int(cx + math.cos(a) * r), int(cy + math.sin(a) * r), cyan)
            for sx in (-1, 1):
                ex, ey = cx + sx * r * 0.42, cy - r * 0.2
                for d in range(-max(1, r // 4), max(1, r // 4) + 1):
                    b.pixel(int(ex + d), int(ey + d), cyan)
                    b.pixel(int(ex + d), int(ey - d), cyan)
            for d in range(-r // 2, r // 2 + 1):
                b.pixel(int(cx + d), int(cy + r * 0.45), cyan)
            for _ in range(r * 2):
                a = rnd.uniform(0, math.tau)
                d = r * rnd.uniform(1.05, 1.5)
                px, py = int(cx + math.cos(a) * d), int(cy + math.sin(a) * d)
                b.pixel(px, py, blend(b.get_pixel(px, py) or BLACK, cyan, 0.3))
            for k in range(3):
                x = int(cx + (k - 1) * r * 0.5)
                y = int(cy + r * 0.45) + 1
                for d in range(rnd.randint(2, 2 + r // 2)):
                    b.pixel(x, y + d, blend(cyan, BLACK, 0.3 + d * 0.08))

    def draw_pegboard(self, b, rnd):
        """Pegboard of hanging tools on the right wall, under the neon sign."""
        side, bt, w = self.side, self.bench, self.w
        x0, x1 = w - side + 2, w - 2
        y0 = int(self.sign_c[1] + self.sign_r + 4)
        y1 = bt - 6
        self.peg = None
        if x1 - x0 < 8 or y1 - y0 < 10:
            return
        self.peg = (x0, y0, x1, y1)
        b.pixel_rect(x0, y0, x1 - x0, y1 - y0, (30, 24, 20))
        b.pixel_line(x0, y0, x1 - 1, y0, (52, 44, 36))
        b.pixel_line(x0, y1 - 1, x1 - 1, y1 - 1, (14, 11, 10))
        for y in range(y0 + 2, y1 - 1, 4):
            for x in range(x0 + 1, x1, 3):
                b.pixel(x, y, (12, 9, 8))
        L = min(y1 - y0 - 5, 10 + 6 * self.s)
        tools = (self.t_wrench, self.t_screwdriver, self.t_hammer, self.t_pliers, self.t_wrench)
        n = max(1, min(len(tools), (x1 - x0 - 2) // 6))
        step = (x1 - x0) / n
        for i in range(n):
            x = int(x0 + step * i + step / 2 - 2)
            y = y0 + 3
            b.pixel(x + 2, y - 1, (150, 150, 160))
            tools[i](b, x, y, L - (i % 2) * 2)

    METAL_HI, METAL_MID, METAL_LO = (205, 210, 222), (130, 135, 150), (60, 62, 74)

    def t_wrench(self, b, x, y, L):
        for py in range(y + 3, y + L - 2):
            b.pixel(x + 1, py, self.METAL_HI)
            b.pixel(x + 2, py, self.METAL_MID)
            b.pixel(x + 3, py, (8, 6, 6))
        for dx in range(-1, 5):
            for dy in range(0, 4):
                if abs(dx - 1.5) + abs(dy - 1.5) * 0.9 <= 2.6 and not (1 <= dx <= 2 and dy < 2):
                    b.pixel(x + dx, y + dy, self.METAL_MID if dx > 1 else self.METAL_HI)
        for dx in range(0, 4):
            for dy in range(L - 3, L + 1):
                if (dx - 1.5) ** 2 + (dy - L + 1.5) ** 2 <= 2.6:
                    b.pixel(x + dx, y + dy, self.METAL_MID)
        b.pixel(x + 1, y + L - 2, (10, 8, 8))

    def t_screwdriver(self, b, x, y, L):
        hl = max(3, L // 3)
        for py in range(y, y + hl):
            b.pixel(x + 1, py, (250, 210, 40))
            b.pixel(x + 2, py, (210, 160, 20))
            b.pixel(x + 3, py, (150, 105, 10))
        for py in range(y + hl, y + L):
            b.pixel(x + 2, py, self.METAL_HI if py < y + L - 1 else self.METAL_LO)

    def t_hammer(self, b, x, y, L):
        for py in range(y + 2, y + L):
            b.pixel(x + 2, py, (120, 78, 42))
            b.pixel(x + 3, py, (80, 50, 26))
        for dx in range(-1, 6):
            b.pixel(x + dx, y, self.METAL_HI)
            b.pixel(x + dx, y + 1, self.METAL_MID)
        b.pixel(x + 5, y + 2, self.METAL_LO)
        b.pixel(x - 1, y + 2, self.METAL_LO)

    def t_pliers(self, b, x, y, L):
        piv = y + L // 3
        b.pixel_line(x + 1, y, x + 2, piv, self.METAL_HI)
        b.pixel_line(x + 3, y, x + 2, piv, self.METAL_MID)
        b.pixel_line(x + 2, piv, x, y + L, (200, 30, 40))
        b.pixel_line(x + 2, piv, x + 4, y + L, (160, 20, 30))
        b.pixel(x + 2, piv, (240, 240, 250))

    def draw_torso(self, b):
        """Hoodie shoulders under the mask (the hood itself moves with the head)."""
        cx, mw = self.w / 2, self.mask_w
        neck = (self.my + self.mask_h - 2) * 2
        sh = (self.my + self.mask_h + 3) * 2
        bt = self.bench
        pts = [(cx - mw * 0.28, neck), (cx + mw * 0.28, neck), (cx + mw * 0.58, sh), (cx + mw * 0.64, bt + 2),
               (cx - mw * 0.64, bt + 2), (cx - mw * 0.58, sh)]
        pfill(b, pts, (28, 24, 38))
        inner = [(cx - mw * 0.2, neck + 2), (cx + mw * 0.2, neck + 2), (cx + mw * 0.34, bt + 2), (cx - mw * 0.34, bt + 2)]
        pfill(b, inner, (34, 30, 46))
        for i in range(len(pts) - 1):
            (ax, ay), (bx_, by) = pts[i], pts[i + 1]
            if ay == by:
                continue
            col = (130, 20, 80) if ax < cx else (0, 110, 130)
            b.pixel_line(int(ax), int(ay), int(bx_), int(by), col)
        b.pixel_line(int(cx), int(neck + 3), int(cx), bt + 1, (52, 50, 64))
        for sx in (-1, 1):
            x = int(cx + sx * mw * 0.1)
            b.pixel_line(x, int(neck + 2), x + sx, int(neck + 8), (96, 92, 110))
            b.pixel(x + sx, int(neck + 9), (180, 180, 196))
            # studded shoulders, Wrench's punk jacket
            for k in range(5):
                f = 0.3 + k * 0.06
                px = int(cx + sx * mw * (f + 0.03))
                py = int(neck + (sh - neck) * (f - 0.28) / 0.3)
                b.pixel(px, py, (190, 190, 205))
                b.pixel(px, py + 1, (40, 38, 50))
        # yellow smiley patch on the chest
        px, py = int(cx - mw * 0.3), int(sh + 4)
        if py + 5 < bt:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx * dx + dy * dy <= 5:
                        b.pixel(px + dx, py + dy, (220, 200, 20))
            for q in ((-1, -1), (1, -1), (-1, 1), (0, 1), (1, 1)):
                b.pixel(px + q[0], py + q[1], (30, 25, 5))

    def draw_bench(self, b, rnd):
        w, h, bt, side = self.w, self.h, self.bench, self.side
        b.pixel_rect(0, bt, w, 1, (120, 110, 100))
        b.pixel_rect(0, bt + 1, w, 1, (70, 60, 52))
        b.pixel_rect(0, bt + 2, w, (h - 2) * 2 - bt - 2, (26, 22, 22))
        bottom = (h - 2) * 2
        for x in range(0, w, max(14, w // 9)):
            b.pixel_rect(x, bt + 2, 1, bottom - bt - 2, (14, 12, 12))
            if bottom - bt > 5:
                b.pixel_rect(x + 5, bt + 4, 4, 1, (90, 86, 90))
        # welding station on the left: workpiece, torch and hose
        tx = int(min(max(self.tag_right + 4, side * 0.55), side - 3)) if side > 12 else max(3, side // 2)
        b.pixel_rect(tx - 4, bt - 3, 9, 3, (64, 66, 76))
        b.pixel_rect(tx - 4, bt - 3, 9, 1, (110, 114, 126))
        tip = (tx + 1, bt - 5)
        b.pixel_line(tip[0] + 1, tip[1] - 1, tip[0] + 6, tip[1] - 8, (170, 130, 60))
        b.pixel_line(tip[0] + 2, tip[1] - 1, tip[0] + 7, tip[1] - 8, (110, 84, 40))
        b.pixel_line(tip[0] + 6, tip[1] - 8, tip[0] + 9, tip[1] - 12, (50, 50, 58))
        b.pixel_line(tip[0] + 7, tip[1] - 8, tip[0] + 10, tip[1] - 12, (36, 36, 42))
        for i in range(12):
            a = i / 11
            b.pixel(int(tip[0] + 10 + a * 6), int(tip[1] - 12 + math.sin(a * math.pi) * -3 + a * 16), (20, 20, 24))
        self.torch_tip = tip
        self.puck = [(max(2, int(side * 0.12) + 3), bt - 1), (w - max(3, int(side * 0.2)), bt - 1)]
        # toolbox on the right bench
        tbw = max(6, min(14, side // 3))
        bx = w - int(side * 0.62) - tbw // 2
        if side >= 14:
            b.pixel_rect(bx, bt - 6, tbw, 6, (150, 22, 32))
            b.pixel_rect(bx, bt - 6, tbw, 1, (200, 50, 60))
            b.pixel_rect(bx, bt - 4, tbw, 1, (90, 10, 18))
            b.pixel_rect(bx + tbw // 2 - 1, bt - 4, 2, 1, (230, 200, 40))
            b.pixel_line(bx + 2, bt - 8, bx + tbw - 3, bt - 8, (70, 70, 80))
            b.pixel(bx + 2, bt - 7, (70, 70, 80))
            b.pixel(bx + tbw - 3, bt - 7, (70, 70, 80))
        for px, py in self.puck:
            b.pixel_rect(px - 2, py - 1, 5, 1, (60, 64, 76))
            b.pixel_rect(px - 3, py, 7, 1, (34, 36, 44))

    # ------------------------------------------------------------ projection
    def P(self, x, y, z=0.0):
        X, Y, Z = self.rot.rot(x, y, z)
        k = self.rot.dist / max(1.0, self.rot.dist + Z) * self.zoom
        return self.rot.cx + X * 2 * k + self.ox, self.rot.cy + Y * k + self.oy, Z

    def eye_origin(self, right):
        return self.mx + 6 + (self.eye_w + self.gap if right else 0), self.my + 3 + (0, 1, 2)[self.s - 1]

    def PP(self, u, v, z):
        p = self.P(self.mx + u, self.my + v, z)
        return p[0], p[1] * 2

    # ------------------------------------------------------------ backdrop animation
    def draw_static(self, s, level=24):
        pt, pb = self.static
        if level >= 24:
            for y in range(s.h):
                s.pt[y] = pt[y][:]
                s.pb[y] = pb[y][:]
        elif level > 0:
            for y in range(s.h):
                s.pt[y] = [_fade(c, level) for c in pt[y]]
                s.pb[y] = [_fade(c, level) for c in pb[y]]

    def draw_scene(self, s, now, dt, color):
        # neon smiley: steady glow with the occasional dying-tube stutter
        if now > self.sign_flicker + 6 and random.random() < 0.012:
            self.sign_flicker = now
        fl = now - self.sign_flicker
        on = not (fl < 0.35 and int(fl * 26) % 3 == 0)
        smile_on = on and not (fl < 0.6 and int(fl * 17) % 2)
        if on:
            for x, y, c in self.halo:
                s.pixel(x, y, c)
        core, tube = (255, 170, 220), (255, 40, 150)
        for x, y, part in self.tube:
            if part == 1 and not smile_on:
                s.pixel(x, y, (70, 20, 50))
            elif on:
                s.pixel(x, y, core if (x + y) % 3 else tube)
            else:
                s.pixel(x, y, (60, 18, 44))
        # welding: bursts of arc light and sparks that bounce on the bench
        if now > self.weld_until:
            self.weld_on = not self.weld_on
            self.weld_until = now + (random.uniform(1.4, 3.5) if self.weld_on else random.uniform(0.8, 2.2))
        tx, ty = self.torch_tip
        bt = self.bench
        if self.weld_on:
            lvl = random.randrange(3)
            for x, y, c in self.weld_glow[lvl]:
                s.pixel(x, y, c)
            s.pixel_rect(tx - 2, bt - 3, 4, 1, (255, 150, 40))
            s.pixel(tx, ty, WHITE)
            s.pixel(tx - 1, ty + 1, (180, 230, 255))
            s.pixel(tx + 1, ty, (180, 230, 255))
            for _ in range(random.randint(2, 6)):
                self.sparks.append([tx + random.uniform(-0.5, 0.5), ty + 1, random.uniform(-26, 26),
                                    random.uniform(-45, -6), 0.0, random.uniform(0.35, 1.0)])
        else:
            s.pixel_rect(tx - 2, bt - 3, 4, 1, (150, 50, 20))
        alive = []
        for p in self.sparks:
            p[4] += dt
            if p[4] >= p[5]:
                continue
            ox, oy = p[0], p[1]
            p[3] += 140 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if p[1] >= bt - 0.5 and p[3] > 0:
                p[1], p[3], p[2] = bt - 0.5, -p[3] * 0.35, p[2] * 0.6
            a = p[4] / p[5]
            col = SPARK[min(len(SPARK) - 1, int(a * len(SPARK)))]
            s.pixel(int(ox), int(oy), blend(col, BLACK, 0.5))
            s.pixel(int(p[0]), int(p[1]), col)
            alive.append(p)
        self.sparks = alive[-220:]
        # hologram emitters: emoticons rise from the bench pucks and fade out
        for i, (px, py) in enumerate(self.puck):
            pulse_c = blend((0, 60, 80), CYAN, pulse(now, 3, i))
            s.pixel(px - 1, py - 2, pulse_c)
            s.pixel(px, py - 2, pulse_c)
            s.pixel(px + 1, py - 2, pulse_c)
            if now > self.next_holo[i]:
                self.next_holo[i] = now + random.uniform(2.6, 4.2)
                txt = random.choice(EMOTES)
                self.holos.append([i, txt, now, random.uniform(2.2, 3.4), random.uniform(0, 6)])
        top = max(3, int(self.bench / 2 * 0.3))
        keep = []
        for hd in self.holos:
            i, txt, t0, sp, ph = hd
            age = now - t0
            px, py = self.puck[i]
            y = py / 2 - 2 - age * sp
            if y < top:
                continue
            keep.append(hd)
            x = px + math.sin(age * 1.3 + ph) * 1.5 - len(txt) / 2
            lo, hi = (0, self.side - len(txt)) if i == 0 else (self.w - self.side, self.w - len(txt))
            x = int(max(lo, min(hi, x)))
            life = min(1.0, age / 0.4, (y - top) / 6)
            base = CYAN if i else blend(PINK, WHITE, 0.2)
            yy = int(y)
            if age < 1.6:
                beam = 0.22 * life * (1 - age / 1.6)
                for k in (0, len(txt)):
                    for q in line_points(px, py - 2, x + k, yy * 2 + 2):
                        tint(s, q[0], q[1], base, beam)
            scan = 0.55 if (yy + int(now * 6)) % 3 == 0 else 0.0
            col = blend(BLACK, base, life * (0.95 - scan * 0.5))
            for j, c in enumerate(txt):
                if random.random() < 0.05:
                    continue
                s.put(x + j, yy, c, col)
        self.holos = keep

    # ------------------------------------------------------------ mask
    def glow_grid(self, pats):
        g = [0] * 162
        for e, pat in enumerate(pats):
            L = [[LEVEL.get(ch, 0.0) for ch in row] for row in pat]
            base = e * 81
            for r in range(-1, 8):
                for c in range(-1, 8):
                    v = L[r][c] * 0.55 if 0 <= r < 7 and 0 <= c < 7 else 0.0
                    for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                        if 0 <= rr < 7 and 0 <= cc < 7:
                            v += L[rr][cc] * 0.12
                    g[base + (r + 1) * 9 + c + 1] = min(6, int(v * 7))
        return g

    def draw_hood(self, s, now):
        PP, D = self.PP, self.depth
        hood = [PP(u, v, D + 2) for u, v in self.hood]
        pfill(s, hood, (30, 26, 42))
        cx = sum(p[0] for p in hood) / len(hood)
        for i in range(len(hood) - 1):
            (ax, ay), (bx, by) = hood[i], hood[i + 1]
            col = (150, 24, 92) if (ax + bx) / 2 < cx else (0, 120, 140)
            s.pixel_line(int(ax), int(ay), int(bx), int(by), col)
        for fold in self.folds:
            pts = [PP(u, v, D + 1.5) for u, v in fold]
            for a, b in zip(pts, pts[1:]):
                s.pixel_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), (46, 40, 62))
        opening = [PP(self.mask_w / 2 + (u - self.mask_w / 2) * 1.04, v - 0.4, D + 1) for u, v in self.outline]
        pfill(s, opening, (5, 4, 8))

    def draw_mask(self, s, now, rim_col, glow=None, gcol=CYAN):
        self.draw_hood(s, now)
        PP, D = self.PP, self.depth
        outline = self.outline
        front = [PP(u, v, 0) for u, v in outline]
        back = [PP(u, v, D) for u, v in outline]
        n = len(front)
        sides = []
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = front[i], front[j], back[j], back[i]
            cross = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
            if cross >= 0 or (a[0] == b[0] and a[1] == b[1]):
                continue
            ex, ey = outline[j][0] - outline[i][0], outline[j][1] - outline[i][1]
            ln = math.hypot(ex * 0.5, ey) or 1
            nx, ny = ey / ln, -ex * 0.5 / ln
            lit = max(0.0, -0.5 * nx - 0.85 * ny)
            col = blend((14, 13, 20), (70, 66, 88), lit)
            sides.append((a, b, c, d, col))
        for a, b, c, d, col in sides:
            pfill(s, [a, b, c, d], col)
        # side "ear" vent modules
        mw, mh = self.mask_w, self.mask_h
        for sx in (-1, 1):
            u0 = mw / 2 + sx * (mw / 2 + 0.2)
            u1 = u0 + sx * (1.5 + self.s)
            v0, v1 = mh * 0.3, mh * 0.62
            quad = [PP(u0, v0, D * 0.4), PP(u1, v0 + 0.6, D * 0.5), PP(u1, v1 - 0.6, D * 0.5), PP(u0, v1, D * 0.4)]
            pfill(s, quad, (34, 34, 44))
            for k in range(1, 4):
                vv = v0 + (v1 - v0) * k / 4
                a, b = PP(u0, vv, D * 0.3), PP(u1, vv, D * 0.45)
                s.pixel_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), (8, 8, 12))
        self.warp(s, now, front, glow, gcol)
        for i in range(n):
            a, b = front[i], front[(i + 1) % n]
            if outline[i][1] > mh * 0.5:
                s.pixel_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), rim_col)

    def warp(self, s, now, front, glow, gcol):
        """Perspective-correct texture map of the face plate (inverse homography per pixel)."""
        mw, mh = self.mask_w, self.mask_h
        corners = [(0, 0), (mw, 0), (mw, mh), (0, mh)]
        src = [self.PP(u, v, -0.04) for u, v in corners]
        H = solve_homography(src, [(u, v * 2) for u, v in corners])
        if H is None:
            return
        a, b, c, d, e, f, g, h = H
        hl = mw * (0.3 + 0.4 * (0.5 + 0.5 * math.sin(now * 0.45))) - self.rot.yaw * mw * 0.6
        bw = 3 + 3 * self.s
        sheen = [max(0, int(8 * (1 - abs(i - hl) / bw))) for i in range(mw + self.th // 4 + 2)]
        q = glow or [0] * 162
        gt = [blend(blend(GLASS, gcol, k * 0.12), (70, 80, 105), r * 0.14) for k in range(7) for r in range(3)]
        tex, TW, TH, metal, fixed = self.tex, self.tw, self.th, METAL, FIXED
        ys = [p[1] for p in front]
        npt = len(front)
        W, PH = s.w, s.ph
        for py in range(max(0, int(min(ys))), min(PH - 1, int(max(ys)) + 1) + 1):
            yc = py + 0.5
            xs = []
            for i in range(npt):
                ax, ay = front[i]
                bx, by = front[(i + 1) % npt]
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
            if len(xs) < 2:
                continue
            xa, xb = max(0, int(min(xs)) - 1), min(W - 1, int(max(xs)) + 1)
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            chrow = s.ch[py >> 1]
            x0 = xa + 0.5
            U = a * x0 + b * yc + c
            V = d * x0 + e * yc + f
            Wd = g * x0 + h * yc + 1
            for x in range(xa, xb + 1):
                u = U / Wd
                v = V / Wd
                U += a
                V += d
                Wd += g
                if u < 0 or v < 0:
                    continue
                iu, iv = int(u), int(v)
                if iu >= TW or iv >= TH:
                    continue
                code = tex[iv][iu]
                if code < 0:
                    continue
                if code < 64:
                    col = metal[code + sheen[iu + (iv >> 2)]]
                elif code < 1000:
                    col = fixed[code - 100]
                else:
                    code -= 1000
                    col = gt[q[code // 3] * 3 + code % 3]
                layer[x] = col
                chrow[x] = " "

    def draw_eye(self, s, right, pattern, old, reveal, color, glitch, dim=0.0):
        """LEDs on the pixel layer: lit squares with a glint row, dead LEDs as dim dots."""
        ox, oy = self.eye_origin(right)
        o = self.P(ox, oy, -0.6)
        u = self.P(ox + self.led_w, oy, -0.6)
        v = self.P(ox, oy + self.led_h, -0.6)
        ux, uy = u[0] - o[0], (u[1] - o[1]) * 2
        vx, vy = v[0] - o[0], (v[1] - o[1]) * 2
        ox_, oy_ = o[0], o[1] * 2
        dw = (self.led_w - (1, 1, 2)[self.s - 1]) / self.led_w
        dh = 1 - 1 / (2 * self.led_h) if self.s > 1 else 1.0
        off = (36, 26, 46)
        hi = blend(color, WHITE, 0.3)
        ax, ay = ux * dw, uy * dw
        hx, hy = vx * dh, vy * dh
        for r in range(7):
            pat = pattern if r < reveal else old
            for c in range(7):
                lvl = LEVEL.get(pat[r][c], 0.0)
                if glitch and random.random() < 0.05:
                    lvl = 0.0 if lvl else 1.0
                bx, by = ox_ + ux * c + vx * r, oy_ + uy * c + vy * r
                if lvl <= 0:
                    s.pixel(int(bx + ax * 0.5), int(by + ay * 0.5 + hy * 0.5), off)
                    continue
                col = hi if (r + c) % 3 == 0 else color
                if lvl < 1 or dim:
                    col = blend(off, col, lvl * (1 - dim))
                pfill(s, [(bx, by), (bx + ax, by + ay), (bx + ax + hx, by + ay + hy), (bx + hx, by + hy)], col)
                if self.s > 1:
                    s.pixel_line(int(bx + 0.5), int(by + 0.5), int(bx + ax - 0.5), int(by + ay + 0.5), blend(col, WHITE, 0.45))

    def mouth_xy(self, i):
        return self.mouth_x0 + i * 2, self.my + self.mask_h - 3

    def draw_mouth(self, s, now, color, talking):
        bars = self.mouth_n
        if len(self.eq) != bars:
            self.eq = [0.0] * bars
        lvl_all = DATA.level
        cap = max(1, int(self.mask_h * 0.2))
        for i in range(bars):
            band = DATA.band(i, bars)
            target = (band * 3.2 + 0.4) if talking else band * (1.2 + lvl_all) * 1.4
            self.eq[i] += (target - self.eq[i]) * 0.5
            lvl = min(cap, self.eq[i])
            x, vy = self.mouth_xy(i)
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

        self.draw_static(s)
        self.draw_scene(s, now, dt, color)

        t = now - self.changed
        if name == "GL1TCH":
            color = random.choice((PINK, CYAN, YELLOW)) if random.random() < 0.3 else color
        pfn = self.prev_expr[1]
        lp, rp = fn(t, False), fn(t, True)
        olp, orp = pfn(t + 5, False), pfn(t + 5, True)
        if now < self.blink_until and name not in GAZE_FREE:
            lp = rp = olp = orp = DASH
        lp, rp = shift(lp, gx, gy), shift(rp, gx, gy)
        olp, orp = shift(olp, gx, gy), shift(orp, gx, gy)
        reveal = min(7, int(t * 35))
        shown = [[(p if r < reveal else o)[r] for r in range(7)] for p, o in ((lp, olp), (rp, orp))]

        rim = blend(GREY, PURPLE, 0.4 + 0.3 * pulse(now, 1.5))
        rim = blend(rim, color, DATA.beat * 0.5)
        self.draw_mask(s, now, rim, self.glow_grid(shown), color)

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
        backfill(s)
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
        # the garage lights go out while Wrench says goodbye
        self.draw_static(s, int(24 * max(0.0, 1 - t / 0.45)))
        self.stars.draw(s, dt, speed=-14)
        eyes = [teary(t * 0.8, right) for right in (False, True)]
        self.draw_mask(s, now, blend(GREY, CYAN, 0.3), self.glow_grid(eyes), CYAN)
        for right in (False, True):
            self.draw_eye(s, right, eyes[right], eyes[right], 7, CYAN, False)
        # tears roll out of the eyes
        for right in (False, True):
            if random.random() < 0.7:
                ox, oy = self.eye_origin(right)
                px, py, _ = self.P(ox + self.eye_w * 0.5, oy + 7 * self.led_h, -1)
                self.particles.add(px + random.uniform(-1, 1), py, random.uniform(-2, 2), random.uniform(2, 5), 0.8,
                                   random.choice("•●"), blend(CYAN, WHITE, 0.4), gravity=40)
        self.particles.step(s, dt)
        # mouth: a sad little wobble
        bars = self.mouth_n
        for i in range(bars):
            x, vy = self.mouth_xy(i)
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
        backfill(s)
        self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0

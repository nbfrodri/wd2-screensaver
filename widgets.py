"""Moving elements shared by all modes: floating panels, particles, tickers, 3D, FX."""

import math
import random

from sysdata import DATA
from lib import (BLACK, CYAN, DARK, DIM_CYAN, DIM_PINK, GREEN, GREY, NEON, NOISE_CHARS,
                 PINK, PURPLE, WHITE, YELLOW, blend, line_points, overlaps)

PARTIAL = " ▁▂▃▄▅▆▇█"
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# ---------------------------------------------------------------- particles

class Particles:
    def __init__(self, limit=700):
        self.p, self.limit = [], limit

    def add(self, x, y, vx, vy, life, ch, color, gravity=0.0, fade=True):
        self.p.append([x, y, vx, vy, 0.0, life, ch, color, gravity, fade])

    def burst(self, x, y, n, colors=NEON, speed=12.0, chars="*+·•", life=(0.4, 1.4), gravity=0.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(0.3, 1.0) * speed
            self.add(x, y, math.cos(a) * v * 2, math.sin(a) * v, random.uniform(*life),
                     random.choice(chars), random.choice(colors), gravity)

    def step(self, s, dt):
        alive = []
        for p in self.p:
            p[4] += dt
            if p[4] >= p[5]:
                continue
            p[3] += p[8] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            t = p[4] / p[5]
            ch = p[6] if len(p[6]) == 1 else p[6][min(len(p[6]) - 1, int(t * len(p[6])))]
            s.put(int(round(p[0])), int(round(p[1])), ch, blend(p[7], BLACK, t * t) if p[9] else p[7])
            alive.append(p)
        self.p = alive[-self.limit:]


# ---------------------------------------------------------------- ticker / stickers

class Ticker:
    def __init__(self, label, items, color=PINK, speed=16):
        self.label, self.color, self.speed = label, color, speed
        self.items = list(items)
        self.text = "  ///  ".join(items) + "  ///  "

    def live_items(self):
        items = []
        np_ = DATA.now_playing()
        if np_:
            items.append("#NOWPLAYING %s" % np_)
        if DATA.notifications:
            items.append("NOTIFICATIONS: %d" % DATA.notifications)
        items.append("USER AWAY %s" % DATA.idle_clock())
        if DATA.weather:
            items.append("LOCAL WEATHER %d°C %s" % (DATA.weather["temp_c"], DATA.weather["desc"].strip().upper()))
        return items

    def draw(self, s, y, now):
        if now > getattr(self, "_refresh", 0):
            self._refresh = now + 5
            self.text = "  ///  ".join(self.items + self.live_items()) + "  ///  "
        s.fill(0, y - 1, s.w, 2)
        s.text(0, y - 1, "▁" * s.w, DIM_PINK)
        lab = " " + self.label + " "
        off = int(now * self.speed) % len(self.text)
        need = s.w - len(lab)
        line = (self.text * (need // len(self.text) + 2))[off:off + need]
        s.text(len(lab), y, line, GREY)
        for i, c in enumerate(line):
            if c == "#":
                j = i
                while j < len(line) and line[j] != " ":
                    s.put(len(lab) + j, y, line[j], self.color)
                    j += 1
        col = self.color if int(now * 2) % 2 else blend(self.color, WHITE, 0.4)
        s.text(0, y, "▐" + lab[1:-1] + "▌", col)


class Sticker:
    """DVD-style bouncing text block."""

    def __init__(self, w, h, art, top=3, bottom=3):
        self.lines = art.split("\n")
        self.bw = max(len(l) for l in self.lines)
        self.bh = len(self.lines)
        self.w, self.h, self.top, self.bottom = w, h, top, bottom
        self.x = random.uniform(1, max(1, w - self.bw - 1))
        self.y = random.uniform(top, max(top, h - bottom - self.bh))
        self.vx = random.choice((-1, 1)) * random.uniform(8, 16)
        self.vy = random.choice((-1, 1)) * random.uniform(3, 7)
        self.color = random.choice(NEON)

    def step(self, s, dt, particles=None):
        self.x += self.vx * dt
        self.y += self.vy * dt
        bounced = False
        if self.x < 0 or self.x > self.w - self.bw:
            self.vx = -self.vx
            self.x = max(0, min(self.w - self.bw, self.x))
            bounced = True
        if self.y < self.top or self.y > self.h - self.bottom - self.bh:
            self.vy = -self.vy
            self.y = max(self.top, min(self.h - self.bottom - self.bh, self.y))
            bounced = True
        if bounced:
            self.color = random.choice([c for c in NEON if c != self.color])
            if particles:
                particles.burst(self.x + self.bw / 2, self.y + self.bh / 2, 14, (self.color,), speed=8)
        for i, l in enumerate(self.lines):
            for j, c in enumerate(l):
                if c != " ":
                    s.put(int(self.x) + j, int(self.y) + i, c, self.color)


# ---------------------------------------------------------------- 3D

def rot(v, ax, ay, az=0.0):
    x, y, z = v
    cy, sy = math.cos(ay), math.sin(ay)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cx, sx = math.cos(ax), math.sin(ax)
    y, z = y * cx - z * sx, y * sx + z * cx
    if az:
        cz, sz = math.cos(az), math.sin(az)
        x, y = x * cz - y * sz, x * sz + y * cz
    return x, y, z


def edge_char(dx, dy):
    if dx == 0 and dy == 0:
        return "•"
    a = math.atan2(dy * 2, dx) % math.pi
    if a < math.pi / 8 or a > 7 * math.pi / 8:
        return "─"
    if a < 3 * math.pi / 8:
        return "\\"
    if a < 5 * math.pi / 8:
        return "│"
    return "/"


CUBE_V = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
CUBE_E = [(a, b) for a in range(8) for b in range(a + 1, 8)
          if sum(CUBE_V[a][i] != CUBE_V[b][i] for i in range(3)) == 1]
OCTA_V = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
OCTA_E = [(a, b) for a in range(6) for b in range(a + 1, 6) if a // 2 != b // 2]
_P = (1 + 5 ** 0.5) / 2
_ICO = [(0, a, b * _P) for a in (-1, 1) for b in (-1, 1)] + \
       [(a, b * _P, 0) for a in (-1, 1) for b in (-1, 1)] + \
       [(b * _P, 0, a) for a in (-1, 1) for b in (-1, 1)]
ICO_V = [tuple(c / 1.9 for c in v) for v in _ICO]
ICO_E = [(a, b) for a in range(12) for b in range(a + 1, 12)
         if abs(math.dist(ICO_V[a], ICO_V[b]) - 2 / 1.9) < 0.05]
SHAPES = [(CUBE_V, CUBE_E), (OCTA_V, OCTA_E), (ICO_V, ICO_E)]


def project(v, cx, cy, size, dist=3.5):
    x, y, z = v
    k = dist / max(0.2, dist + z)
    return cx + x * size * 2 * k, cy + y * size * k, z


def draw_wire(s, verts, edges, cx, cy, size, ax, ay, az=0.0, near=PINK, far=DIM_CYAN, dist=3.5):
    pts = [project(rot(v, ax, ay, az), cx, cy, size, dist) for v in verts]
    for a, b in edges:
        x0, y0, z0 = pts[a]
        x1, y1, z1 = pts[b]
        ch = edge_char(x1 - x0, y1 - y0)
        col = blend(near, far, ((z0 + z1) / 2 + 1) / 2)
        for x, y in line_points(int(x0), int(y0), int(x1), int(y1)):
            s.put(x, y, ch, col)
    for x, y, z in pts:
        s.put(int(x), int(y), "●", blend(WHITE, far, (z + 1) / 2))


# ---------------------------------------------------------------- panel contents
# Each draws inside the rectangle (x, y, w, h) and keeps its own state in `st`.

def p_hexdump(s, x, y, w, h, now, st):
    if now > st.get("next", 0):
        n = max(1, (w - 6) // 3)
        addr = st.get("addr", random.randint(0, 0xFFFF))
        st.setdefault("rows", []).append((addr, [random.randint(0, 255) for _ in range(n)]))
        st["addr"] = (addr + n) & 0xFFFF
        st["rows"] = st["rows"][-h:]
        st["next"] = now + 0.09
    rows = st.get("rows", [])
    for i, (addr, data) in enumerate(rows):
        s.text(x, y + i, "%04X" % addr, DIM_CYAN)
        for j, b in enumerate(data):
            hot = b > 245
            s.text(x + 6 + j * 3, y + i, "%02X" % b, PINK if hot else (CYAN if i == len(rows) - 1 else GREY))


def p_equalizer(s, x, y, w, h, now, st):
    n = w // 2
    lv = st.setdefault("lv", [0.0] * n)
    tg = st.setdefault("tg", [0.0] * n)
    pk = st.setdefault("pk", [0.0] * n)
    for i in range(n):
        tg[i] = min(1.0, DATA.band(i, n) * random.uniform(0.85, 1.1)) * h
        lv[i] += (tg[i] - lv[i]) * 0.45
        pk[i] = max(pk[i] - 0.15, lv[i])
        full = int(lv[i])
        for r in range(h):
            yy = y + h - 1 - r
            if r < full:
                ch = "█"
            elif r == full:
                ch = PARTIAL[int((lv[i] - full) * 8)]
            else:
                ch = " "
            if ch != " ":
                s.put(x + i * 2, yy, ch, blend(CYAN, PINK, r / max(1, h - 1)))
        py = y + h - 1 - int(pk[i])
        if pk[i] > 0.5 and py >= y:
            s.put(x + i * 2, py, "▔", WHITE)


def p_wave(s, x, y, w, h, now, st):
    mid = y + h / 2
    for k, (col, f, sp, amp) in enumerate(((CYAN, 0.31, 4.0, 0.9), (PINK, 0.17, -2.6, 0.6))):
        prev = None
        for i in range(w):
            v = math.sin(i * f + now * sp) * amp * math.sin(now * 0.7 + k)
            v += math.sin(i * f * 2.7 - now * sp * 1.3) * 0.25
            yy = int(mid + v * (h / 2 - 0.5))
            yy = max(y, min(y + h - 1, yy))
            if prev is not None:
                for t in range(min(prev, yy), max(prev, yy) + 1):
                    s.put(x + i, t, "│" if t != yy else "•", col)
            s.put(x + i, yy, "•", blend(col, WHITE, 0.3))
            prev = yy


def p_spark(s, x, y, w, h, now, st):
    hist = st.setdefault("hist", [random.random() for _ in range(w)])
    if now > st.get("next", 0):
        live = (DATA.net_rx + DATA.net_tx) / 1.5e6
        val = min(1, 0.05 + live) if live > 0.002 else hist[-1] + random.uniform(-0.25, 0.25)
        hist.append(max(0.05, min(1, val)))
        del hist[:-w]
        st["next"] = now + 0.08
    for i, v in enumerate(hist):
        hh = v * h
        full = int(hh)
        for r in range(h):
            yy = y + h - 1 - r
            ch = "█" if r < full else (PARTIAL[int((hh - full) * 8)] if r == full else " ")
            if ch != " ":
                s.put(x + i, yy, ch, blend(GREEN, YELLOW, v) if i < w - 1 else WHITE)
    s.text(x, y, "%5.1f%%" % (hist[-1] * 100), WHITE)


def p_radar(s, x, y, w, h, now, st):
    cx, cy = x + w // 2, y + h // 2
    r = min(h // 2, w // 4)
    for i in range(48):
        a = i / 48 * math.tau
        s.put(int(cx + math.cos(a) * r * 2), int(cy + math.sin(a) * r), "·", DIM_CYAN)
        s.put(int(cx + math.cos(a) * r), int(cy + math.sin(a) * r / 2), "·", DARK)
    for i in range(-r * 2, r * 2 + 1):
        s.put(cx + i, cy, "─", DARK)
    for i in range(-r, r + 1):
        s.put(cx, cy + i, "│", DARK)
    blips = st.setdefault("blips", [(random.uniform(0, math.tau), random.uniform(0.2, 0.95)) for _ in range(5)])
    sweep = (now * 2.2) % math.tau
    for k in range(7):
        a = sweep - k * 0.09
        col = blend(GREEN, BLACK, k / 7)
        for d in range(1, r + 1):
            s.put(int(cx + math.cos(a) * d * 2), int(cy + math.sin(a) * d), "•" if k == 0 else "·", col)
    for i, (a, d) in enumerate(blips):
        since = (sweep - a) % math.tau
        if since < 2.5:
            s.put(int(cx + math.cos(a) * d * r * 2), int(cy + math.sin(a) * d * r), "◆", blend(PINK, BLACK, since / 2.5))
        if since > 6.1 and random.random() < 0.05:
            blips[i] = (random.uniform(0, math.tau), random.uniform(0.2, 0.95))
    s.put(cx, cy, "◉", WHITE)


def p_cube(s, x, y, w, h, now, st):
    verts, edges = st.setdefault("shape", random.choice(SHAPES))
    sp = st.setdefault("sp", random.uniform(0.6, 1.4))
    size = min(h / 2 - 1, w / 4 - 1) * 0.95
    draw_wire(s, verts, edges, x + w / 2, y + h / 2, size, now * 0.7 * sp, now * sp, now * 0.3,
              near=random.choice((PINK,)), far=DIM_CYAN)


def p_loaders(s, x, y, w, h, now, st):
    tasks = st.setdefault("tasks", [])
    names = ["ctOS uplink", "drone sync", "botnet relay", "mesh route", "cam feed", "dedsec cloud",
             "signal boost", "node map", "proxy chain", "packet mixer"]
    while len(tasks) < h:
        tasks.append({"name": random.choice(names), "p": 0.0, "sp": random.uniform(0.08, 0.5), "done": 0})
    bw = max(4, w - 22)
    for i, t in enumerate(tasks[:h]):
        if t["done"]:
            if now > t["done"]:
                tasks[i] = {"name": random.choice(names), "p": 0.0, "sp": random.uniform(0.08, 0.5), "done": 0}
            status = "DONE"
        else:
            t["p"] = min(1.0, t["p"] + t["sp"] / 24)
            if t["p"] >= 1:
                t["done"] = now + 1.2
            status = SPIN[int(now * 12 + i) % len(SPIN)]
        filled = int(bw * t["p"])
        s.text(x, y + i, t["name"][:12].ljust(12), GREY)
        s.text(x + 13, y + i, "█" * filled, CYAN if not t["done"] else GREEN)
        s.text(x + 13 + filled, y + i, "░" * (bw - filled), DARK)
        s.text(x + 14 + bw, y + i, status if t["done"] else "%s%3d%%" % (status, t["p"] * 100), GREEN if t["done"] else YELLOW)


def p_cam(s, x, y, w, h, now, st):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if random.random() < 0.18:
                s.put(xx, yy, random.choice("░▒·"), DARK)
    # a walking figure crossing the frame
    fx = x + int((now * 4 + st.setdefault("ph", random.uniform(0, 50))) % (w + 6)) - 3
    fy = y + h - 4
    leg = "/ \\" if int(now * 6) % 2 else " |\\"
    for i, l in enumerate((" o ", "/|\\", leg)):
        s.text(fx, fy + i, l, GREY)
    if x <= fx + 1 < x + w:
        s.brackets(fx - 1, fy - 1, 5, 5, PINK, arm=1)
    s.text(x, y, "CAM %02d" % st.setdefault("n", random.randint(1, 99)), WHITE)
    if int(now * 2) % 2:
        s.text(x + w - 5, y, "● REC", PINK)
    s.text(x, y + h - 1, "%05.1f" % (now % 1000), DIM_CYAN)


def p_decrypt(s, x, y, w, h, now, st):
    if "key" not in st or now > st["reset"]:
        st["key"] = "-".join("".join(random.choice("0123456789ABCDEF") for _ in range(4)) for _ in range(max(1, (w - 2) // 5)))
        st["start"] = now
        st["reset"] = now + 4.5
    key = st["key"]
    solved = int((now - st["start"]) * 7)
    for row in range(h):
        line = "".join(c if (row == h // 2 and i < solved) or c == "-" else random.choice("0123456789ABCDEF")
                       for i, c in enumerate(key))
        col = GREEN if row == h // 2 else DARK
        s.text(x, y + row, line[:w], col)
        if row == h // 2:
            s.text(x, y + row, line[:min(solved, w)], WHITE if solved >= len(key) else GREEN)
    if solved >= len(key):
        s.text(x, y + h - 1, "KEY FOUND", PINK if int(now * 6) % 2 else YELLOW)


def p_bars(s, x, y, w, h, now, st):
    labels = ["CPU", "MEM", "NET", "AUD", "SIG", "HEAT", "PWR"]
    real = [DATA.cpu, DATA.mem, min(1.0, (DATA.net_rx + DATA.net_tx) / 2e6), DATA.level]
    for i in range(h):
        v = real[i] if i < len(real) else (math.sin(now * (1 + i * 0.37) + i) * 0.5 + 0.5) * 0.8 + random.random() * 0.2
        bw = w - 10
        filled = int(bw * v)
        s.text(x, y + i, labels[i % len(labels)].ljust(5), GREY)
        s.text(x + 5, y + i, "▮" * filled, blend(GREEN, PINK, v))
        s.text(x + 5 + filled, y + i, "▯" * (bw - filled), DARK)
        s.text(x + w - 4, y + i, "%3d" % (v * 100), WHITE)


def p_minimap(s, x, y, w, h, now, st):
    """Abstract scrolling 'editor minimap': coloured blocks, no text."""
    rows = st.setdefault("rows", [])
    depth = st.setdefault("depth", 0)
    while len(rows) < h + 1:
        if random.random() < 0.25:
            depth = max(0, min(4, depth + random.choice((-1, 1))))
        segs, cx = [], depth * 2
        for _ in range(random.randint(0, 4)):
            ln = random.randint(2, 9)
            if cx + ln > w:
                break
            segs.append((cx, ln, random.choice((PINK, CYAN, YELLOW, GREEN, PURPLE, GREY, GREY))))
            cx += ln + 1
        rows.append(segs)
        st["depth"] = depth
    st["off"] = st.get("off", 0.0) + 0.25
    while st["off"] >= 1:
        st["off"] -= 1
        rows.pop(0)
    hl = int(now * 3) % h
    for i, segs in enumerate(rows[:h]):
        for sx, ln, col in segs:
            s.text(x + sx, y + i, "▬" * ln, blend(col, BLACK, 0.45) if i != hl else col)
    s.put(x + w - 1, y + hl, "◀", WHITE)


PANEL_KINDS = {
    "minimap": (30, 10, "INJECT", p_minimap),
    "hexdump": (40, 9, "MEMORY DUMP", p_hexdump),
    "eq": (28, 8, "AUDIO TAP", p_equalizer),
    "wave": (34, 7, "SIGNAL", p_wave),
    "spark": (30, 7, "BANDWIDTH", p_spark),
    "radar": (27, 11, "PROXIMITY", p_radar),
    "cube": (26, 12, "OBJ.3D", p_cube),
    "loaders": (42, 6, "TASKS", p_loaders),
    "cam": (28, 10, "SURVEILLANCE", p_cam),
    "decrypt": (36, 5, "DECRYPTING", p_decrypt),
    "bars": (28, 6, "SYSTEM", p_bars),
}


class Panels:
    """Floating windows that pop open, live a few seconds and collapse again."""

    def __init__(self, w, h, keepout=(), max_panels=6, kinds=None, top=3, bottom=3):
        self.w, self.h = w, h
        self.keepout = list(keepout)
        self.max = max_panels
        self.kinds = kinds or list(PANEL_KINDS)
        self.top, self.bottom = top, bottom
        self.items = []
        self.next = 0

    def spawn(self, now):
        kind = random.choice(self.kinds)
        pw, ph, title, fn = PANEL_KINDS[kind]
        for _ in range(40):
            x = random.randint(1, max(1, self.w - pw - 1))
            y = random.randint(self.top, max(self.top, self.h - self.bottom - ph))
            r = (x, y, pw, ph)
            if x + pw > self.w or y + ph > self.h - self.bottom + 1:
                continue
            if any(overlaps(r, k, 2) for k in self.keepout) or any(overlaps(r, p["r"], 1) for p in self.items):
                continue
            self.items.append({"r": r, "title": title, "fn": fn, "st": {}, "born": now,
                               "life": random.uniform(5, 11), "color": random.choice((CYAN, PINK, PURPLE, YELLOW))})
            return

    def draw(self, s, now):
        if now > self.next and len(self.items) < self.max:
            self.spawn(now)
            self.next = now + random.uniform(0.4, 1.8)
        keep = []
        for p in self.items:
            age = now - p["born"]
            f = min(1.0, (age + 0.04) / 0.3, (p["life"] - age) / 0.3)
            if f <= 0:
                continue
            keep.append(p)
            x, y, w, h = p["r"]
            vw = max(4, int(w * min(1.0, f * 1.6)))
            vh = max(2, int(h * f))
            bx, by = x + (w - vw) // 2, y + (h - vh) // 2
            col = p["color"]
            if age < 0.5 and random.random() < 0.3:
                col = WHITE
            # drop shadow gives the windows some depth
            for i in range(1, vh + 1):
                s.put(bx + vw, by + i, "▒", DARK)
            s.text(bx + 1, by + vh, "▒" * vw, DARK)
            s.box(bx, by, vw, vh, blend(col, BLACK, 0.35), title=p["title"] if f >= 1 else None, title_color=col)
            if f >= 1:
                p["fn"](s, x + 2, y + 1, w - 4, h - 2, now, p["st"])
                if random.random() < 0.01:
                    s.text(x + w - 6, y + h - 1, " !! ", PINK)
        self.items = keep


# ---------------------------------------------------------------- post effects

class PostFX:
    """CRT scan band and row tearing on glitch."""

    def __init__(self, band_speed=7.0):
        self.band_speed = band_speed

    def apply(self, s, now, glitch=False):
        span = s.h + 16
        by = int((now * self.band_speed) % span) - 8
        for k, t in ((0, 0.45), (-1, 0.25), (1, 0.25), (-2, 0.1)):
            s.tint_row(by + k, WHITE, t)
        if glitch:
            for _ in range(random.randint(2, 5)):
                y0 = random.randrange(s.h)
                dx = random.randint(-14, 14)
                for y in range(y0, min(s.h, y0 + random.randint(1, 4))):
                    s.shift_row(y, dx)
                    s.tint_row(y, random.choice((PINK, CYAN)), 0.5)
            if random.random() < 0.3:
                s.noise_lines(2)

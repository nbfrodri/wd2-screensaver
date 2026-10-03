"""PROFILER: ctOS citizen profiler over a night-time surveillance view of the city."""

import math
from types import SimpleNamespace
import random
import time

import numpy as np

from engine3d import NEAR, Camera
from lib import (BLACK, CYAN, DIM_CYAN, GREEN, GREY, PINK, WHITE, YELLOW, Glitch, blend,
                 line_points)
from widgets import Particles, Ticker

NAME = "PROFILER"

FIRST = ["Marcus", "Sitara", "Josh", "Horatio", "Ray", "Lenni", "Dusan", "Tyler", "Maria", "Kevin",
         "Ana", "Jordan", "Priya", "Lucas", "Chloe", "Diego", "Wei", "Fatima", "Noah", "Elena"]
LAST = ["Holloway", "Dhillon", "Sauer", "Carlisle", "Kenney", "Brooks", "Nguyen", "Garcia", "Okafor",
        "Kowalski", "Tanaka", "Silva", "Novak", "Rossi", "Fischer", "Moreau", "Ivanova", "Hughes"]
JOBS = ["Barista", "Tech Bro", "Uber Driver", "Blume Engineer", "Podcaster", "Crypto Investor",
        "Dog Walker", "Influencer", "Software Tester", "Street Musician", "Nudle Intern", "Lawyer",
        "Food Truck Owner", "Yoga Instructor", "Security Guard", "Startup CEO", "Pastry Chef"]
INTEL = [
    "Password is 'password123'",
    "Owes $12,450 in parking tickets",
    "Searched 'how to delete browser history'",
    "Believes birds are government drones",
    "Has 47 unread voicemails from mom",
    "Secretly loves pineapple pizza",
    "Cried during a car commercial",
    "Has 3,204 open browser tabs",
    "Followed by 2 FBI agents (bored)",
    "Owns 14 identical black t-shirts",
    "Allergic to Mondays",
    "Lied about reading the terms of service",
    "Pays for 6 streaming services, uses 1",
    "Googled own name 41 times this week",
    "Talks to houseplants. Plants reply.",
    "Mining crypto on a smart fridge",
    "Has a Blume tattoo. Regrets it.",
    "Uses the same PIN for everything",
    "Thinks DedSec is a cereal brand",
    "Wanted for jaywalking in 3 states",
]
ACTIONS = ["STEAL $%d", "DOWNLOAD SONG", "DISABLE PHONE", "READ TEXTS", "ADD TO BOTNET", "SPOOF ID"]
STATUS = [("CITIZEN", CYAN), ("HIGH RISK", PINK), ("BLUME ASSET", YELLOW), ("DEDSEC SYMPATHIZER", GREEN)]
DISTRICTS = ["MISSION", "SOMA", "NOB HILL", "CHINATOWN", "TENDERLOIN", "MARINA"]

# ---------------------------------------------------------------- city layout
BLOCK, STREET = 12.0, 6.0
CELL = BLOCK + STREET
SPAN = 4                      # blocks -SPAN..SPAN-1 on both axes; streets at k * CELL
EDGE = SPAN * CELL
WALK = STREET / 2 + 0.55      # sidewalk lane offset from the street centre
SETBACK = 1.2                 # sidewalk width inside the block

SKY_TOP, SKY_LOW = (3, 6, 16), (20, 26, 52)
GROUND_FAR = (8, 11, 22)
HAZE = (22, 16, 46)
ASPHALT, SIDEWALK, PARK = (3, 5, 10), (34, 42, 60), (12, 34, 28)
MARK = (62, 60, 46)
CROSS = (70, 76, 96)
RIM = (96, 112, 150)
PANEL_BG = (4, 7, 13)
# wall (lit), roof per palette; faces are shaded from the lit colour
# dark night towers: indigo / slate walls, roofs only a little lighter
PALETTES = [((40, 50, 88), (92, 104, 150)), ((48, 42, 84), (104, 94, 146)),
            ((34, 54, 86), (84, 112, 150)), ((52, 48, 78), (110, 104, 140))]
SHADOW = (0.22, 0.5)                          # shadow wall: darker + bluer than the lit wall
WINDOW = (255, 204, 128)
WIN_SCHEMES = [((190, 140, 70), (255, 214, 150)), ((200, 150, 80), (255, 226, 170)),
               ((190, 140, 70), (150, 200, 235))]
NEONS = [PINK, CYAN, (255, 120, 0), (170, 90, 255)]
CAR_COLS = [(190, 40, 60), (60, 90, 150), (205, 205, 215), (60, 60, 72), (230, 170, 40), (40, 140, 120)]
CLOTHES = [(220, 80, 100), (80, 150, 240), (230, 200, 90), (160, 160, 175), (90, 210, 150), (200, 120, 230)]
SKIN = (235, 205, 175)
XRAY = (0, 120, 140)
# corner indices: 0..3 ground (x0z0, x1z0, x1z1, x0z1), 4..7 the same at the roof
FACES = ((0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5))


class Mode:
    def __init__(self, w, h):
        self.w, self.h, self.ph = w, h, h * 2
        self.glitch = Glitch(0.01)
        self.scanned = random.randint(2000, 9000)
        self.history = []
        self.tints = {}
        self.particles = Particles()
        self.last = time.time()
        self.cam = SimpleNamespace(cx=w * 0.4 if w > 140 else w * 0.3, cy=h * 0.58)
        self.district = random.choice(DISTRICTS)
        self.cam_no = random.randint(2, 48)
        self.colcache = {}
        self.lrects = []
        self.build_city(random.Random(random.randint(0, 10 ** 6)))
        self.bake_city()
        self.peds = [self.new_ped() for _ in range(64)]
        self.cars = [self.new_car() for _ in range(34)]
        self.reticles = [{"target": None, "x": w / 2, "y": h / 2, "lock": 0.0, "until": 0.0, "primary": i == 0}
                         for i in range(3)]
        self.ticker = Ticker("ctOS INTEL", ["%s: %s" % (random.choice(FIRST), i) for i in random.sample(INTEL, 10)], color=CYAN)
        self.city_frame = None
        self.city_stamp = -1
        self.zoom = 0.0
        self.focus = [0.0, 0.0]
        self.orbit = random.uniform(0, math.tau)
        self.view = [(self.Wc - w) / 2, (self.Hc - self.ph) / 2]
        self.card_rect = None
        self.link = None
        self.profile = None
        self.new_profile(time.time())
        self.build_minimap()

    # ------------------------------------------------------------ world
    def build_city(self, r):
        self.boxes = []          # x0, z0, x1, z1, y0, y1, wall, roof, parent
        self.extras = {}         # box index -> dict(neon, beacon)
        self.trees = []
        self.blocks = []
        parks = set(r.sample([(gx, gz) for gx in range(-SPAN, SPAN) for gz in range(-SPAN, SPAN)
                              if max(abs(gx + 0.5), abs(gz + 0.5)) > 1.6], 2))
        levels = (3.0, 4.5, 6.0, 8.5, 11.0, 13.5)
        towers = 0
        for gx in range(-SPAN, SPAN):
            for gz in range(-SPAN, SPAN):
                bx0, bz0 = gx * CELL + STREET / 2, gz * CELL + STREET / 2
                park = (gx, gz) in parks
                self.blocks.append((bx0, bz0, bx0 + BLOCK, bz0 + BLOCK, park))
                if park:
                    for tx in (0.3, 0.7):
                        for tz in (0.3, 0.7):
                            self.trees.append((bx0 + BLOCK * tx, bz0 + BLOCK * tz))
                    continue
                ix0, iz0 = bx0 + SETBACK, bz0 + SETBACK
                inner = BLOCK - 2 * SETBACK
                layout = r.choice(("one", "one", "one", "two_x", "two_z"))
                if layout == "one":
                    lots = [(ix0, iz0, ix0 + inner, iz0 + inner)]
                elif layout == "two_x":
                    m = ix0 + inner / 2
                    lots = [(ix0, iz0, m - 0.5, iz0 + inner), (m + 0.5, iz0, ix0 + inner, iz0 + inner)]
                else:
                    m = iz0 + inner / 2
                    lots = [(ix0, iz0, ix0 + inner, m - 0.5), (ix0, m + 0.5, ix0 + inner, iz0 + inner)]
                # downtown core in the middle, low-rise towards the edges
                core = max(0.0, 1.0 - math.hypot(bx0 + BLOCK / 2, bz0 + BLOCK / 2) / 62)
                for x0, z0, x1, z1 in lots:
                    tower = layout == "one" and towers < 8 and r.random() < 0.75 * core
                    if tower:
                        towers += 1
                    hgt = r.uniform(19, 28) if tower else r.choice(levels[:3 + (core > 0.3) + (core > 0.5) + (core > 0.7)])
                    pal = r.choice(PALETTES)
                    idx = len(self.boxes)
                    self.boxes.append((x0, z0, x1, z1, 0.0, hgt, pal[0], pal[1], -1))
                    self.extras[idx] = {"rows": r.random(), "seed": r.random(),
                                        # roof-edge neon: always on towers, on some mid-rises
                                        "neon": (r.choice(NEONS) if tower else
                                                 blend(r.choice(NEONS), BLACK, 0.45) if hgt >= 8 and r.random() < 0.18
                                                 else None)}
                    if tower:
                        self.extras[idx]["beacon"] = True
                        # one setback crown + thin mast: recognisable skyscraper silhouette
                        cx_, cz_ = (x0 + x1) / 2, (z0 + z1) / 2
                        hw, hd = (x1 - x0) * 0.28, (z1 - z0) * 0.28
                        self.boxes.append((cx_ - hw, cz_ - hd, cx_ + hw, cz_ + hd, hgt, hgt + 3.5,
                                           pal[0], pal[1], idx))
                        self.boxes.append((cx_ - 0.15, cz_ - 0.15, cx_ + 0.15, cz_ + 0.15, hgt + 3.5, hgt + 7.5,
                                           (150, 150, 170), (200, 200, 220), idx))
        corners = []
        for x0, z0, x1, z1, y0, y1 in (b[:6] for b in self.boxes):
            corners.append(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                            (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)))
        self.corners = np.array(corners, dtype=float)
        self.block_quads = np.array([((a, 0, b), (c, 0, b), (c, 0, d), (a, 0, d)) for a, b, c, d, _ in self.blocks], dtype=float)
        # window grid per face: regular rows/columns, whole floors lit or dark
        pts, owner, normal, cols = [], [], [], []
        for i, b in enumerate(self.boxes):
            if b[8] >= 0 or b[5] < 3.6:
                continue
            x0, z0, x1, z1, _, y1 = b[:6]
            ex = self.extras[i]
            wr = random.Random(ex["seed"])
            ends = (((x0, z0 - 0.05), (x1, z0 - 0.05), (0, -1)), ((x1, z1 + 0.05), (x0, z1 + 0.05), (0, 1)),
                    ((x0 - 0.05, z1), (x0 - 0.05, z0), (-1, 0)), ((x1 + 0.05, z0), (x1 + 0.05, z1), (1, 0)))
            for (ax, az), (bx, bz), nrm in ends:
                span = math.hypot(bx - ax, bz - az)
                ncol = max(1, int(span / 2.4))
                for fy in np.arange(1.6, y1 - 1.0, 2.2):
                    if wr.random() < 0.55:
                        continue
                    for c in range(ncol):
                        t = (c + 0.5) / ncol
                        pts.append((ax + (bx - ax) * t, fy, az + (bz - az) * t))
                        owner.append(i)
                        normal.append(nrm)
                        cols.append(WINDOW)
        self.win_pts = np.array(pts, dtype=float).reshape(-1, 3)
        self.win_owner = np.array(owner, dtype=int)
        self.win_normal = np.array(normal, dtype=float).reshape(-1, 2)
        self.win_col = np.array(cols, dtype=float).reshape(-1, 3)
        # lane markings: dashed centre lines between intersections
        marks = []
        for k in range(-SPAN, SPAN + 1):
            for v in np.arange(-EDGE, EDGE, 0.5):
                if abs((v + CELL / 2) % CELL - CELL / 2) > STREET / 2 + 0.4 and v % 3.0 < 1.5:
                    marks.append((k * CELL, 0.0, v))
                    marks.append((v, 0.0, k * CELL))
        self.marks = np.array(marks, dtype=float)
        cw = []
        for k in range(-SPAN, SPAN + 1):
            for m in range(-SPAN, SPAN + 1):
                cx0, cz0 = k * CELL, m * CELL
                for off in (STREET / 2 + 0.5, -STREET / 2 - 0.5):
                    for u in np.arange(-STREET / 2 + 0.4, STREET / 2, 0.55):
                        cw.append((cx0 + u, 0.0, cz0 + off))
                        cw.append((cx0 + off, 0.0, cz0 + u))
        self.cross = np.array(cw, dtype=float)
        self.lamps = [(k * CELL + WALK - 0.3, m * CELL + WALK - 0.3)
                      for k in range(-SPAN, SPAN + 1) for m in range(-SPAN, SPAN + 1)]
        mid = CELL / 2
        for k in range(-SPAN, SPAN):
            for m in range(-SPAN, SPAN + 1):
                self.lamps.append((k * CELL + mid, m * CELL + WALK - 0.3))
                self.lamps.append((m * CELL + WALK - 0.3, k * CELL + mid))
        self.lamp_pts = np.array([(x, 3.2, z) for x, z in self.lamps], dtype=float)
        # distant skyline ring
        rr = random.Random(7)
        self.skyline = []
        hgt = 3.0
        for i in range(720):
            if rr.random() < 0.12:
                hgt = rr.choice((1.5, 2.5, 3.5, 5, 6.5, 9)) if rr.random() < 0.9 else rr.uniform(12, 18)
            self.skyline.append(hgt)
        self.sky_lights = {}
        self.stars = [(rr.uniform(0, math.tau), rr.uniform(0.02, 0.5), rr.random()) for _ in range(40)]

    def build_minimap(self):
        self.mm = None
        if self.w < 120 or self.h < 34:
            return
        mw, mh = 30, 14
        iw, ih = mw - 2, (mh - 2) * 2
        scale = 2 * (EDGE + 2) / min(iw, ih)
        ox, oy = (iw - 2 * (EDGE + 2) / scale) / 2, (ih - 2 * (EDGE + 2) / scale) / 2
        base = []
        for py in range(ih):
            for px in range(iw):
                wx = (px + 0.5 - ox) * scale - EDGE - 2
                wz = (py + 0.5 - oy) * scale - EDGE - 2
                if abs(wx) > EDGE + 2 or abs(wz) > EDGE + 2:
                    continue
                col = (10, 14, 22)
                for bx0, bz0, bx1, bz1, park in self.blocks:
                    if bx0 <= wx < bx1 and bz0 <= wz < bz1:
                        col = (16, 52, 32) if park else (22, 34, 46)
                        break
                for b in self.boxes:
                    if b[8] < 0 and b[0] - 0.6 <= wx < b[2] + 0.6 and b[1] - 0.6 <= wz < b[3] + 0.6:
                        col = (34, 78, 96) if b[5] < 10 else (60, 130, 150)
                        break
                base.append((px, py, col))
        self.mm = {"w": mw, "h": mh, "scale": scale, "ox": ox, "oy": oy, "base": base}

    def new_ped(self):
        along_x = random.random() < 0.5
        k = random.randint(-SPAN, SPAN)
        side = random.choice((-1, 1))
        return {"ax": along_x, "lane": k * CELL + side * WALK + random.uniform(-0.25, 0.25),
                "pos": random.uniform(-EDGE * 0.9, EDGE * 0.9), "v": random.choice((-1, 1)) * random.uniform(0.9, 1.8),
                "name": "%s %s" % (random.choice(FIRST), random.choice(LAST)), "age": random.randint(18, 80),
                "body": random.choice(CLOTHES), "flee_until": 0.0, "screen": None}

    def new_car(self):
        along_x = random.random() < 0.5
        k = random.randint(-SPAN + 1, SPAN - 1)
        d = random.choice((-1, 1))
        # right-hand traffic: the lane side follows the driving direction
        lane = k * CELL + (1.3 * d if along_x else -1.3 * d)
        return {"ax": along_x, "lane": lane, "dir": d, "pos": random.uniform(-EDGE, EDGE),
                "v": random.uniform(5.5, 8.5), "spd": 0.0, "col": random.choice(CAR_COLS), "screen": None}

    @staticmethod
    def world(o, y=0.0):
        return (o["pos"], y, o["lane"]) if o["ax"] else (o["lane"], y, o["pos"])

    def update_traffic(self, now, dt):
        green_x = lambda k, m: int(now / 4 + k * 0.5 + m * 0.5) % 2 == 0
        lanes = {}
        for c in self.cars:
            lanes.setdefault((c["ax"], round(c["lane"], 1)), []).append(c)
        for lane in lanes.values():
            lane.sort(key=lambda c: c["pos"] * c["dir"])
            for j, c in enumerate(lane):
                target = c["v"]
                p, d = c["pos"], c["dir"]
                ahead = (math.floor(p / CELL) + 1) * CELL if d > 0 else (math.ceil(p / CELL) - 1) * CELL
                stop = ahead - d * (STREET / 2 + 1.4)
                gap = (stop - p) * d
                k = round(c["lane"] / CELL)
                m = round(ahead / CELL)
                green = green_x(m, k) if c["ax"] else not green_x(k, m)
                if not green and 0 < gap < 4.5:
                    target = c["v"] * max(0.0, (gap - 0.4) / 4.1)
                if j + 1 < len(lane):
                    nxt = (lane[j + 1]["pos"] - p) * d
                    if 0 < nxt < 6:
                        target = min(target, lane[j + 1]["spd"] * 0.9 if nxt < 3.2 else target)
                c["spd"] += (target - c["spd"]) * min(1, dt * 3)
                c["pos"] += c["spd"] * d * dt
                if c["pos"] * d > EDGE + 3:
                    c["pos"] = -d * (EDGE + 2.5)
        for p in self.peds:
            spd = p["v"] * (3.2 if now < p["flee_until"] else 1)
            p["pos"] += spd * dt
            if abs(p["pos"]) > EDGE:
                p["v"] = -p["v"]
                p["pos"] = math.copysign(EDGE, p["pos"])

    # ------------------------------------------------------------ isometric city
    # The city is baked once into a large pixel-art canvas seen from a fixed
    # isometric angle (x runs right-down, z left-down, y up). Each frame the view
    # pans across it; cars, people and lights are drawn on top with occlusion.

    def iso(self, x, y, z):
        """World -> canvas pixel (float)."""
        K = self.K
        return self.iox + (x - z) * K, self.ioy + (x + z) * K * 0.5 - y * K * 0.82

    def bake_city(self):
        K = self.K = 1.6 if self.w >= 150 else 1.25
        lim = EDGE + 3
        self.iox = lim * K + 4
        self.ioy = 30 * K * 0.82 + 6
        Wc = int(2 * lim * K + 8)
        Hc = int(self.ioy + 2 * lim * K * 0.5 + 6)
        self.Wc, self.Hc = Wc, Hc
        img = np.zeros((Hc, Wc, 3), np.float32)
        img[:] = (20, 22, 34)                               # asphalt
        key = np.full((Hc, Wc), -1e9, np.float32)          # depth key of building pixels
        self._img, self._key = img, key

        def poly(pts, col, k=None):
            ys = [p[1] for p in pts]
            y0, y1 = max(0, int(math.floor(min(ys)))), min(Hc - 1, int(math.ceil(max(ys))))
            n = len(pts)
            for y in range(y0, y1 + 1):
                yc = y + 0.5
                xs = []
                for i in range(n):
                    ax, ay = pts[i]
                    bx, by = pts[(i + 1) % n]
                    if (ay <= yc < by) or (by <= yc < ay):
                        xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
                if len(xs) >= 2:
                    xa, xb = max(0, int(round(min(xs)))), min(Wc - 1, int(round(max(xs))) - 1)
                    if xb >= xa:
                        img[y, xa:xb + 1] = col
                        if k is not None:
                            key[y, xa:xb + 1] = k

        def px(x, y, col):
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < Wc and 0 <= yi < Hc:
                img[yi, xi] = col

        def seg(a, b, col):
            for x, y in line_points(int(round(a[0])), int(round(a[1])), int(round(b[0])), int(round(b[1]))):
                if 0 <= x < Wc and 0 <= y < Hc:
                    img[y, x] = col

        iso = self.iso
        # --- ground: blocks (sidewalk ring), parks, streets with markings
        for bx0, bz0, bx1, bz1, park in self.blocks:
            corners = [iso(bx0, 0, bz0), iso(bx1, 0, bz0), iso(bx1, 0, bz1), iso(bx0, 0, bz1)]
            poly(corners, (52, 56, 76))                     # sidewalk ring
            inner = [iso(bx0 + 0.6, 0, bz0 + 0.6), iso(bx1 - 0.6, 0, bz0 + 0.6),
                     iso(bx1 - 0.6, 0, bz1 - 0.6), iso(bx0 + 0.6, 0, bz1 - 0.6)]
            poly(inner, (22, 60, 40) if park else (30, 32, 48))
        for k in range(-SPAN, SPAN + 1):
            c = k * CELL
            for t in np.arange(-EDGE, EDGE, 2.4):
                if abs(((t + CELL / 2) % CELL) - CELL / 2) < STREET / 2 + 0.3:
                    continue                                   # no dashes inside crossings
                seg(iso(c, 0, t), iso(c, 0, t + 1.1), (120, 110, 70))
                seg(iso(t, 0, c), iso(t + 1.1, 0, c), (120, 110, 70))
        for k in range(-SPAN, SPAN + 1):
            for m in range(-SPAN, SPAN + 1):
                cx_, cz_ = k * CELL, m * CELL
                for i in range(-2, 3):                         # zebra crossings
                    o = i * 1.0
                    for dz in (-STREET / 2 - 0.2, STREET / 2 + 0.2):
                        seg(iso(cx_ + o - 0.25, 0, cz_ + dz), iso(cx_ + o + 0.25, 0, cz_ + dz), (96, 102, 124))
                    for dx in (-STREET / 2 - 0.2, STREET / 2 + 0.2):
                        seg(iso(cx_ + dx, 0, cz_ + o - 0.25), iso(cx_ + dx, 0, cz_ + o + 0.25), (96, 102, 124))
        # trees
        for tx, tz in self.trees:
            gx, gy = iso(tx, 0, tz)
            for dy in range(-int(3 * K), 1):
                for dx in range(-int(2 * K), int(2 * K) + 1):
                    if dx * dx / (2 * K) ** 2 + (dy + 1.5 * K) ** 2 / (1.6 * K) ** 2 <= 1:
                        lit = dx < 0 and dy < -1.5 * K
                        px(gx + dx, gy + dy, (38, 92, 56) if lit else (20, 58, 38))
        # street lamp pools
        for p in self.lamp_pts:
            gx, gy = iso(p[0], 0, p[2])
            for dy in range(-2, 3):
                for dx in range(-4, 5):
                    d = (dx / 4.0) ** 2 + (dy / 2.0) ** 2
                    if d < 1:
                        xi, yi = int(gx + dx), int(gy + dy)
                        if 0 <= xi < Wc and 0 <= yi < Hc:
                            img[yi, xi] = img[yi, xi] + (np.array((255, 190, 110), np.float32) - img[yi, xi]) * 0.32 * (1 - d)

        # --- buildings, painter's order (far to near)
        order = sorted(range(len(self.boxes)), key=lambda i: (self.boxes[i][2] + self.boxes[i][3], self.boxes[i][4]))
        rng = random.Random(11)
        self.win_lights = []
        for i in order:
            x0, z0, x1, z1, y0, y1, wall, roof, parent = self.boxes[i]
            root = i if parent < 0 else parent
            ex = self.extras.get(root, {})
            kf = x1 + z1
            lit = blend(wall, WHITE, 0.10)
            shade = blend(blend(wall, (6, 8, 30), 0.45), BLACK, 0.45)
            # left face (z = z1) is lit, right face (x = x1) in shadow
            fl = [iso(x0, y0, z1), iso(x1, y0, z1), iso(x1, y1, z1), iso(x0, y1, z1)]
            fr = [iso(x1, y0, z1), iso(x1, y0, z0), iso(x1, y1, z0), iso(x1, y1, z1)]
            top = [iso(x0, y1, z0), iso(x1, y1, z0), iso(x1, y1, z1), iso(x0, y1, z1)]
            poly(fl, lit, kf)
            poly(fr, shade, kf)
            poly(top, roof, kf)
            # windows: neat floor rows on both walls
            if parent < 0 and y1 - y0 > 2.5:
                warm = rng.choice(((255, 200, 120), (255, 214, 150), (255, 190, 110), (190, 220, 255)))
                for face, (ax, az, bx, bz) in ((0, (x0, z1, x1, z1)), (1, (x1, z1, x1, z0))):
                    span = math.hypot(bx - ax, bz - az)
                    ncol = max(1, int(span / 1.45))
                    floor = y0 + 1.0
                    while floor < y1 - 0.9:
                        on_floor = rng.random() < 0.55
                        for j in range(ncol):
                            t = (j + 0.5) / ncol
                            wx, wz = ax + (bx - ax) * t, az + (bz - az) * t
                            p = iso(wx, floor, wz)
                            on = on_floor and rng.random() < 0.8
                            col = warm if on else (blend(lit, BLACK, 0.45) if face == 0 else blend(shade, BLACK, 0.3))
                            if on and face == 1:
                                col = blend(warm, BLACK, 0.25)
                            px(p[0], p[1], col)
                            if K >= 2.0:
                                px(p[0], p[1] - 1, col)
                            if on:
                                self.win_lights.append((int(round(p[0])), int(round(p[1])), col))
                        floor += 1.5
            # outlines: dark ink on the silhouette, a light rim on the roof's back edges
            ink = (4, 4, 12)
            for a, b in ((fl[0], fl[3]), (fr[1], fr[2])):
                seg(a, b, ink)
            seg(top[0], top[1], blend(roof, WHITE, 0.35))
            seg(top[0], top[3], blend(roof, WHITE, 0.35))
            seg(top[1], top[2], ink)
            seg(top[3], top[2], ink)
            seg(fl[2], fl[1], blend(lit, WHITE, 0.25))                # lit corner edge
            neon = ex.get("neon") if ex.get("beacon") and parent < 0 else None
            if neon:
                seg(top[3], top[2], neon)
                seg(top[2], top[1], neon)
            # rooftop clutter on low buildings
            if parent < 0 and not ex.get("beacon") and y1 - y0 < 12 and (x1 - x0) > 4:
                for _ in range(rng.randint(1, 3)):
                    ux = rng.uniform(x0 + 1, x1 - 2)
                    uz = rng.uniform(z0 + 1, z1 - 2)
                    a = [iso(ux, y1, uz), iso(ux + 1, y1, uz), iso(ux + 1, y1, uz + 1), iso(ux, y1, uz + 1)]
                    b = [iso(ux, y1 + 0.8, uz), iso(ux + 1, y1 + 0.8, uz), iso(ux + 1, y1 + 0.8, uz + 1), iso(ux, y1 + 0.8, uz + 1)]
                    poly([a[3], a[2], b[2], b[3]], blend(roof, BLACK, 0.2))
                    poly([a[2], a[1], b[1], b[2]], blend(roof, BLACK, 0.45))
                    poly(b, blend(roof, WHITE, 0.15))
        # beacons
        self.beacons = []
        for i, b in enumerate(self.boxes):
            if b[8] < 0 and self.extras.get(i, {}).get("beacon"):
                tallest = max((bb for bb in self.boxes if bb[8] == i), key=lambda bb: bb[5], default=b)
                self.beacons.append(iso((tallest[0] + tallest[2]) / 2, tallest[5] + 0.3, (tallest[1] + tallest[3]) / 2))
        # quantise to a small palette of tuples per row, ready to slice into the screen
        q = (np.clip(img, 0, 255).astype(np.int32) >> 2) << 2
        self.canvas = [[tuple(c) for c in row.tolist()] for row in q]
        self.key = key

    def canvas_view(self, now, dt):
        """Pan offset (integer canvas pixels) for this frame."""
        w, ph = self.w, self.ph
        locked = self.reticles[0]["target"] if self.reticles[0]["lock"] >= 1 else None
        self.orbit += dt * 0.035
        # a slow Lissajous drift across the middle of the city
        ax = (self.Wc - w) / 2
        ay = (self.Hc - ph) / 2
        gx = ax + math.sin(self.orbit) * ax * 0.55
        gy = ay + math.sin(self.orbit * 0.77 + 1.3) * ay * 0.45
        if locked:
            tx, ty = self.iso(*self.world(locked))
            gx, gy = tx - self.cam.cx, ty - self.ph * 0.55
        k = min(1.0, dt * 0.9)
        self.view[0] += (gx - self.view[0]) * k
        self.view[1] += (gy - self.view[1]) * k
        self.view[0] = max(0.0, min(self.Wc - w - 1.0, self.view[0]))
        self.view[1] = max(0.0, min(self.Hc - ph - 1.0, self.view[1]))
        return int(self.view[0]), int(self.view[1])

    def blit_city(self, s, vx, vy):
        cv = self.canvas
        w = self.w
        for y in range(self.h):
            s.pt[y] = cv[vy + 2 * y][vx:vx + w]
            s.pb[y] = cv[vy + 2 * y + 1][vx:vx + w]

    def occluded(self, cx, cy, kobj):
        """Is canvas pixel (cx, cy) covered by a building standing in front of kobj?"""
        if 0 <= cy < self.Hc and 0 <= cx < self.Wc:
            return self.key[cy, cx] > kobj + 0.5
        return False

    def put_world(self, s, vx, vy, cx, cy, col):
        x, py = cx - vx, cy - vy
        if 0 <= x < self.w and 0 <= py < self.ph:
            (s.pb if py & 1 else s.pt)[py >> 1][x] = col

    def draw_dynamic(self, s, now, vx, vy):
        iso = self.iso
        # twinkling windows: a few lights switch per frame
        if self.win_lights:
            rnd = random.Random(int(now * 2))
            for _ in range(min(40, len(self.win_lights) // 30)):
                x, y, col = self.win_lights[rnd.randrange(len(self.win_lights))]
                self.put_world(s, vx, vy, x, y, blend(col, BLACK, 0.6) if rnd.random() < 0.5 else WHITE)
        # cars: head and tail light pairs plus a body pixel
        for c in self.cars:
            x, _, z = self.world(c)
            d = c["dir"]
            fx, fz = (d, 0) if c["ax"] else (0, d)
            kobj = x + z
            body = iso(x, 0.5, z)
            c["screen"] = ((body[0] - vx), (body[1] - vy) / 2, 0)
            bx, by = int(round(body[0])), int(round(body[1]))
            if self.occluded(bx, by, kobj):
                continue
            for t in (-0.8, 0.0, 0.8):
                p = iso(x + fx * t, 0.5, z + fz * t)
                self.put_world(s, vx, vy, int(round(p[0])), int(round(p[1])), c["col"])
            h = iso(x + fx * 1.3, 0.5, z + fz * 1.3)
            tl = iso(x - fx * 1.3, 0.5, z - fz * 1.3)
            self.put_world(s, vx, vy, int(round(h[0])), int(round(h[1])), (255, 246, 214))
            brake = c["spd"] < c["v"] * 0.3
            self.put_world(s, vx, vy, int(round(tl[0])), int(round(tl[1])), (255, 40, 50) if brake else (190, 40, 50))
        # people
        marked = {id(r["target"]): r for r in self.reticles if r["target"] is not None}
        for p in self.peds:
            x, _, z = self.world(p)
            foot = iso(x, 0, z)
            fx_, fy_ = int(round(foot[0])), int(round(foot[1]))
            p["screen"] = ((foot[0] - vx), (foot[1] - vy - 2) / 2, 0)
            hid = self.occluded(fx_, fy_ - 2, x + z)
            p["hidden"] = hid
            tr = marked.get(id(p))
            if hid and tr is None:
                continue
            body = blend(p["body"], WHITE, 0.25)
            if tr is not None:
                hc = self.profile["color"] if tr["lock"] >= 1 else YELLOW
                hc = blend(BLACK, hc, 0.6 + 0.3 * math.sin(now * 8))
                for dy in range(-4, 2):
                    self.put_world(s, vx, vy, fx_ - 1, fy_ + dy, hc)
                    self.put_world(s, vx, vy, fx_ + 1, fy_ + dy, hc)
            self.put_world(s, vx, vy, fx_, fy_ - 3, (255, 228, 196))
            self.put_world(s, vx, vy, fx_, fy_ - 2, body)
            self.put_world(s, vx, vy, fx_, fy_ - 1, body)
            self.put_world(s, vx, vy, fx_, fy_, blend(body, BLACK, 0.5) if int(now * 4 + p["pos"]) % 2 else body)
        # roof beacons
        if int(now * 1.5) % 2:
            for bx, by in self.beacons:
                self.put_world(s, vx, vy, int(round(bx)), int(round(by)), (255, 40, 40))

    # ------------------------------------------------------------ overlays
    def label(self, s, x, y, text, col, bg=PANEL_BG, claim=False):
        x = max(0, min(self.w - len(text), x))
        rect = (x - 1, y, x + len(text) + 1, y + 1)
        for q in self.lrects:
            if rect[0] < q[2] and q[0] < rect[2] and rect[1] < q[3] and q[1] < rect[3]:
                if claim:
                    break
                return
        if claim:
            self.lrects.append(rect)
        if 0 <= y < self.h:
            s.text(x, y, text, col)
            row = s.bg[y]
            for i in range(x, min(self.w, x + len(text))):
                row[i] = bg

    def panel(self, s, x, y, w, h, col, title):
        s.box(x, y, w, h, col, title=title)
        for yy in range(max(0, y + 1), min(self.h, y + h - 1)):
            row = s.bg[yy]
            for xx in range(max(0, x + 1), min(self.w, x + w - 1)):
                row[xx] = PANEL_BG

    def in_card(self, x, y):
        r = self.card_rect
        return r and r[0] - 3 <= x < r[0] + r[2] + 2 and r[1] - 2 <= y < r[1] + r[3] + 2

    def draw_reticles(self, s, now):
        w, h = self.w, self.h
        taken = {id(r["target"]) for r in self.reticles if r["target"] is not None}
        visible = [p for p in self.peds if p.get("screen") and not p.get("hidden")
                   and 6 < p["screen"][0] < w - 8 and 5 < p["screen"][1] < h - 5
                   and not self.in_card(p["screen"][0], p["screen"][1]) and id(p) not in taken
                   and not (self.mm and p["screen"][0] < self.mm["w"] + 4 and p["screen"][1] < self.mm["h"] + 5)]
        self.link = None
        self.lrects = []
        for r in sorted(self.reticles, key=lambda q: not q["primary"]):
            tgt = r["target"]
            lost = tgt is None or not tgt.get("screen") or (r["lock"] < 1 and tgt.get("hidden"))
            if lost or now > r["until"]:
                if visible:
                    pick = min(visible, key=lambda p: abs(p["screen"][0] - self.cam.cx) * 0.5 + abs(p["screen"][1] - h * 0.62) * 2
                               + random.random() * 12) \
                        if r["primary"] else random.choice(visible)
                    visible.remove(pick)
                    r["target"], r["lock"] = pick, 0.0
                    r["until"] = now + (12 if r["primary"] else random.uniform(3, 5))
                else:
                    r["target"] = None
                continue
            tx, ty = tgt["screen"][0], tgt["screen"][1]
            r["x"] += (tx - r["x"]) * 0.22
            r["y"] += (ty - r["y"]) * 0.22
            near = abs(tx - r["x"]) < 1.5 and abs(ty - r["y"]) < 1
            old = r["lock"]
            r["lock"] = min(1.0, r["lock"] + (0.03 if r["primary"] else 0.05)) if near else max(0.0, r["lock"] - 0.05) if old < 1 else 1.0
            x, y = int(round(r["x"])), int(round(r["y"]))
            if r["primary"]:
                if old < 1 <= r["lock"]:
                    tgt["flee_until"] = now + 4
                    self.particles.burst(tx, ty, 10, (GREEN, CYAN), speed=6)
                    self.new_profile(now, tgt)
                    r["until"] = now + 6.5
                self.primary_reticle(s, now, r, tgt, x, y)
            else:
                size = int(round(6 - 3 * r["lock"]))
                col = blend(YELLOW, BLACK, 0.1) if r["lock"] < 1 else (200, 200, 120)
                self.bracket_box(s, x, y, size, max(1, size // 2 + 1), col, 1, 0)
                if r["lock"] >= 1:
                    self.label(s, x + size + 2, y - 1, tgt["name"].upper(), (210, 210, 220), claim=True)
                    self.label(s, x + size + 2, y, "AGE %d // RISK %d%%" % (tgt["age"], hash(tgt["name"]) % 100), GREY, claim=True)
                else:
                    self.label(s, x + size + 2, y, "SCAN %3d%%" % (r["lock"] * 100), YELLOW, claim=True)

    @staticmethod
    def bracket_box(s, cx, cy, hw, hh, col, arm_x, arm_y):
        """Crisp corner brackets centred on (cx, cy) with half sizes hw/hh."""
        for sx, sy, ch in ((-1, -1, "┏"), (1, -1, "┓"), (-1, 1, "┗"), (1, 1, "┛")):
            x, y = cx + sx * hw, cy + sy * hh
            s.put(x, y, ch, col)
            for i in range(1, arm_x + 1):
                s.put(x - sx * i, y, "━", col)
            for i in range(1, arm_y + 1):
                s.put(x, y - sy * i, "┃", col)

    def primary_reticle(self, s, now, r, tgt, x, y):
        lock = r["lock"]
        hw = int(round(11 - 7 * lock))          # brackets close in as the lock builds
        hh = max(2, int(round(hw / 2.2)))
        col = self.profile["color"] if lock >= 1 else YELLOW
        top = y - hh
        self.bracket_box(s, x, y, hw, hh, col, 2 if hw > 5 else 1, 1)
        if lock < 1:
            sy = top + 1 + int((now * 9) % max(1, 2 * hh - 1))
            s.tint_row(sy, CYAN, 0.35, x - hw + 1, x + hw)
            dim = blend(YELLOW, BLACK, 0.3)
            for dx in (-hw - 3, hw + 3):
                s.put(x + dx, y, "─", dim)
                s.put(x + dx + (1 if dx < 0 else -1), y, "─", dim)
            s.put(x, top - 2, "│", dim)
            n = int(lock * 6)
            self.lrects.append((x - hw - 1, top - 3, x + hw + 2, y + hh + 1))
            self.label(s, x - 7, top - 3, "ACQUIRING " + "█" * n + "░" * (6 - n), YELLOW, claim=True)
        else:
            pulse = 0.55 + 0.45 * math.sin(now * 7)
            s.put(x, top - 2, "▼", blend(col, WHITE, 0.3 * pulse))
            for dx in (-hw - 2, hw + 2):
                s.put(x + dx, y, "◆", col)
            name = tgt["name"].upper()
            self.lrects.append((x - hw - 1, top - 3, x + hw + 2, y + hh + 1))
            self.label(s, x - len(name) // 2, top - 3, " " + name + " ", WHITE, blend(col, BLACK, 0.7), claim=True)
            self.link = (x + hw + 3, y, col)

    def draw_link(self, s, now):
        if not self.link or not self.card_rect:
            return
        x0, y0, col = self.link
        cx, cy, cw, ch = self.card_rect
        if cx <= x0 < cx + cw:
            return
        side = -1 if x0 < cx else 1
        x1, y1 = (cx - 1 if side < 0 else cx + cw), max(cy + 1, min(cy + ch - 2, y0))
        elbow = x1 + side * max(4, abs(x1 - x0) // 3)
        pts = line_points(x0, y0, elbow, y0) + line_points(elbow, y0, x1, y1)[1:]
        head = int(now * 30) % max(1, len(pts))
        for i, (x, y) in enumerate(pts):
            k = (head - i) % len(pts)
            horiz = i == 0 or pts[i - 1][1] == y == (pts[i + 1][1] if i + 1 < len(pts) else y)
            if k < 3:
                s.put(x, y, "●", blend(WHITE, col, k / 3))
            else:
                s.put(x, y, "━" if horiz else "•", blend(col, BLACK, 0.2))
        s.put(x1, y1, "◆", col)

    def draw_minimap(self, s, now):
        mm = self.mm
        if not mm:
            return
        x0, y0 = 2, 3
        self.panel(s, x0, y0, mm["w"], mm["h"], blend(CYAN, BLACK, 0.4), "CITY GRID // %s" % self.district)
        ix, iy = x0 + 1, (y0 + 1) * 2
        for px, py, col in mm["base"]:
            s.pixel(ix + px, iy + py, col)
        sc, ox, oy = mm["scale"], mm["ox"], mm["oy"]
        mp = lambda wx, wz: (int(ix + ox + (wx + EDGE + 2) / sc), int(iy + oy + (wz + EDGE + 2) / sc))
        for c in self.cars:
            x, _, z = self.world(c)
            s.pixel(*mp(x, z), (150, 130, 60))
        # the area currently on screen (screen corners back-projected to the ground)
        K = self.K
        vx, vy = self.view
        pts = []
        for sx, sy in ((0, 0), (self.w, 0), (self.w, self.ph), (0, self.ph)):
            a = (vx + sx - self.iox) / K
            b = (vy + sy - self.ioy) / (K * 0.5)
            pts.append(mp((a + b) / 2, (b - a) / 2))
        for (ax_, ay_), (bx_, by_) in zip(pts, pts[1:] + pts[:1]):
            for x, y in line_points(ax_, ay_, bx_, by_):
                if ix <= x < ix + mm["w"] - 2 and iy <= y < iy + (mm["h"] - 2) * 2:
                    s.pixel(x, y, (150, 50, 100))
        for r in self.reticles:
            if r["target"] is not None:
                x, _, z = self.world(r["target"])
                col = (self.profile["color"] if r["lock"] >= 1 else YELLOW) if r["primary"] else (200, 200, 120)
                if r["primary"] or int(now * 4) % 2:
                    px, py = mp(x, z)
                    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)) if r["primary"] else ((0, 0),):
                        s.pixel(px + dx, py + dy, col)

    # ------------------------------------------------------------ profile card
    def new_profile(self, now, ped=None):
        name = ped["name"] if ped else "%s %s" % (random.choice(FIRST), random.choice(LAST))
        status = random.choice(STATUS)
        self.profile = {
            "name": name,
            "age": ped["age"] if ped else random.randint(18, 79),
            "job": random.choice(JOBS),
            "income": "$%s" % format(random.randint(8, 420) * 1000, ","),
            "status": status,
            "intel": random.sample(INTEL, 2),
            "action": random.choice(ACTIONS).replace("%d", str(random.randint(20, 900))),
            "color": random.choice((PINK, CYAN, YELLOW, GREEN)),
        }
        self.profile["portrait"] = self.citizen_portrait(
            name, self.profile["age"], ped["body"] if ped else None)
        self.started = now
        self.history = ([name] + self.history)[:6]
        self.scanned += 1
        self.glitch.trigger(now, 0.25)

    @staticmethod
    def citizen_portrait(name, age, clothes=None):
        """Offline fictional booking portrait, stable for the same identity."""
        rng = random.Random(sum((i + 1) * ord(c) for i, c in enumerate(name)) + age * 97)
        skin = rng.choice(((212, 173, 142), (170, 124, 94), (111, 77, 61), (231, 197, 165)))
        hair = rng.choice(((27, 25, 29), (64, 43, 32), (100, 75, 46))) if age < 60 else (112, 115, 118)
        cloth = clothes or rng.choice(CLOTHES)
        fringe = rng.randrange(3)
        glasses = rng.random() < 0.3
        beard = age > 24 and rng.random() < 0.3
        rows = []
        for y in range(16):
            row = []
            for x in range(16):
                col = blend((9, 26, 32), (3, 10, 18), y / 20)
                dx = x - 7.5
                if 12 <= y and abs(dx) <= 3 + (y - 12) * 1.4:
                    col = blend(cloth, BLACK, 0.48 + max(0, dx) * 0.035)
                    if abs(dx) < 1 and y >= 13:
                        col = blend(col, BLACK, 0.4)
                if 10 <= y <= 12 and 6 <= x <= 9:
                    col = blend(skin, BLACK, 0.32)
                if ((dx / 4.2) ** 2 + ((y - 6) / 5.0) ** 2 <= 1):
                    col = blend(skin, BLACK, 0.12 + max(0, dx) * 0.065)
                    if y <= 3 or (y == 4 and (x < 6 + fringe or x > 10)) or (x in (4, 11) and y < 8):
                        col = blend(hair, WHITE, 0.12 if dx < 0 else 0)
                    if y == 6 and x in (6, 9):
                        col = (20, 27, 31)
                    if glasses and ((y in (5, 7) and x in (5, 6, 9, 10)) or
                                    (y == 6 and x in (4, 5, 7, 8, 10, 11))):
                        col = (36, 53, 62)
                    if x == 8 and 7 <= y <= 8:
                        col = blend(skin, WHITE if y == 7 else BLACK, 0.2)
                    if y == 9 and 6 <= x <= 9:
                        col = blend(skin, (48, 25, 29), 0.65)
                    elif beard and y >= 9:
                        col = blend(col, hair, 0.55)
                row.append(blend(col, CYAN, 0.10))
            rows.append(row)
        return rows

    def draw_card(self, s, now):
        elapsed = now - self.started
        p = self.profile
        card_w = min(64, self.w - 6)
        card_h = 16 if self.w <= 110 else 18
        slide = (1 - min(1.0, elapsed / 0.4)) ** 3
        cx = self.w - card_w - 3 + int(slide * (card_w + 6))
        cy = min(self.h - card_h - 3, max(3, (self.h - card_h) // 2 + 4))
        self.card_rect = (cx, cy, card_w, card_h)
        col = p["color"]
        s.box(cx, cy, card_w, card_h, col, title="ctOS PROFILER", double=True)
        for yy in range(cy + 1, min(self.h, cy + card_h - 1)):
            row = s.bg[yy]
            for xx in range(max(0, cx + 1), min(self.w, cx + card_w - 1)):
                row[xx] = PANEL_BG
                s.ch[yy][xx] = " "
                s.pt[yy][xx] = s.pb[yy][xx] = None

        reveal = min(16, int(elapsed * 12))
        for r in range(16):
            for c in range(16):
                color = p["portrait"][r][c] if r < reveal else (11, 23, 31)
                if r == reveal - 1 and reveal < 16:
                    color = blend(color, col, 0.55)
                elif r % 2:
                    color = blend(color, BLACK, 0.12)
                s.pixel(cx + 3 + c, 2 * (cy + 2) + r, color)
        s.text(cx + 3, cy + 11, "ID#%08X" % (hash(p["name"]) & 0xFFFFFFFF), GREY)

        def typed(text, start):
            return text[:max(0, int((elapsed - start) * 30))]

        fx = cx + 22
        fields = [("NAME", p["name"], WHITE), ("AGE", str(p["age"]), WHITE), ("OCCUPATION", p["job"], WHITE),
                  ("INCOME", p["income"], GREEN), ("STATUS", p["status"][0], p["status"][1])]
        for i, (k, v, c) in enumerate(fields):
            s.text(fx, cy + 2 + i, k.ljust(11), (112, 125, 142))
            s.text(fx + 11, cy + 2 + i, typed(v, 0.3 + i * 0.25)[:card_w - 35], c)
        width = card_w - 25
        for i, line in enumerate(p["intel"]):
            s.text(fx, cy + 8 + i, typed("» " + line, 1.8 + i * 0.8)[:width], YELLOW)
        if elapsed > 3.2:
            s.text(fx, cy + 11, ("[ HACK: %s ]" % p["action"])[:width], PINK if int(now * 4) % 2 else WHITE)
        bar_w = card_w - 6
        prog = min(1.0, elapsed / 4.5)
        bar_y = cy + card_h - 4
        s.text(cx + 3, bar_y, "ANALYZING ", GREY)
        filled = int((bar_w - 10) * prog)
        s.text(cx + 13, bar_y, "█" * filled + "░" * (bar_w - 10 - filled), col)
        if prog >= 1:
            s.text(cx + 3, bar_y + 1, "PROFILE COMPLETE // UPLOADED TO DEDSEC"[:bar_w], GREEN)

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        if now - self.started > 14:
            self.new_profile(now)        # nobody visible for a while: keep the card alive

        self.update_traffic(now, dt)
        vx, vy = self.canvas_view(now, dt)
        self.blit_city(s, vx, vy)
        self.draw_dynamic(s, now, vx, vy)
        self.draw_reticles(s, now)
        self.lrects = []
        self.draw_minimap(s, now)
        self.draw_link(s, now)
        self.draw_card(s, now)

        w, h = self.w, self.h
        head = ("ctOS 2.0 // CITIZEN SURVEILLANCE  //  " if w > 110 else "ctOS // PROFILER  ") + time.strftime("%H:%M:%S")
        self.label(s, 2, 0, head, CYAN, BLACK)
        tot = "PROFILES SCANNED: {:,}".format(self.scanned)
        self.label(s, w - len(tot) - 2, 0, tot, YELLOW, BLACK)
        s.text(2, 1, "─" * (w - 4), DIM_CYAN)
        if w > 110:
            view = sum(1 for p in self.peds if p.get("screen") and 0 <= p["screen"][0] < w and 0 <= p["screen"][1] < h)
            info = " CAM %02d // ORBIT %03d // CITIZENS IN VIEW %d " % (self.cam_no, math.degrees(self.orbit) % 360, view)
            self.label(s, (w - len(info)) // 2, 1, info, blend(CYAN, BLACK, 0.2), BLACK)
        if w > 140:
            ry = h - 11
            self.panel(s, 2, ry - 1, 26, 9, blend(CYAN, BLACK, 0.5), "RECENT TARGETS")
            for i, n in enumerate(self.history):
                s.text(4, ry + 1 + i, (("▸ " if i == 0 else "  ") + n)[:22], CYAN if i == 0 else GREY)

        self.particles.step(s, dt)
        self.ticker.draw(s, h - 1, now)
        self.post(s, now, glitch)

    def tint(self, c, k):
        key = (c, k)
        v = self.tints.get(key)
        if v is None:
            if len(self.tints) > 20000:
                self.tints.clear()
            v = self.tints[key] = blend(c, WHITE, k)
        return v

    def post(self, s, now, glitch):
        """CRT scan band (cached tints) and short row tears on glitch."""
        by = int((now * 6) % (s.h + 16)) - 8
        for k, amt in ((0, 0.16), (-1, 0.07), (1, 0.07)):
            y = by + k
            if 0 <= y < s.h:
                for layer in (s.fg, s.pt, s.pb, s.bg):
                    layer[y] = [None if c is None else self.tint(c, amt) for c in layer[y]]
        if glitch:
            for _ in range(random.randint(2, 4)):
                y0 = random.randrange(s.h)
                dx = random.randint(-10, 10)
                for y in range(y0, min(s.h, y0 + random.randint(1, 3))):
                    s.shift_row(y, dx)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "scan", "ctOS // TARGETS RELEASED", CYAN)
        if .08 < t < .75:
            for r in self.reticles:
                x, y = int(r["x"]), int(r["y"])
                radius = 1 + int(t * 6)
                s.put(x - radius, y, "[", blend(CYAN, (0, 0, 0), t))
                s.put(x + radius, y, "]", blend(CYAN, (0, 0, 0), t))

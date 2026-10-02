"""PROFILER: ctOS citizen profiler over a night-time surveillance view of the city."""

import math
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
BLOCK, STREET = 8.0, 4.0
CELL = BLOCK + STREET
SPAN = 5                      # blocks -SPAN..SPAN-1 on both axes; streets at k * CELL
EDGE = SPAN * CELL
WALK = STREET / 2 + 0.55      # sidewalk lane offset from the street centre
SETBACK = 1.2                 # sidewalk width inside the block

SKY_TOP, SKY_LOW = (2, 4, 12), (30, 24, 54)
GROUND_FAR = (7, 8, 15)
HAZE = (20, 20, 40)
ASPHALT, SIDEWALK, PARK = (9, 10, 17), (24, 27, 38), (12, 36, 24)
MARK = (78, 70, 34)
RIM = (80, 200, 225)
PANEL_BG = (4, 7, 13)
# wall (lit), roof per palette; faces are shaded from the lit colour
PALETTES = [((62, 84, 118), (78, 100, 128)), ((74, 64, 108), (92, 82, 122)),
            ((44, 90, 102), (62, 106, 116)), ((80, 78, 92), (98, 96, 110))]
FACE_SHADE = (1.0, 0.55, 0.68, 0.84)         # faces -z, +z, -x, +x (moonlight from -z/+x)
WIN_SCHEMES = [((190, 140, 70), (255, 214, 150)), ((90, 160, 205), (200, 240, 255)),
               ((190, 140, 70), (120, 200, 240))]
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
        self.cam = Camera(w, h, fov=1.0)
        self.cam.cx = w * 0.4 if w > 140 else w / 2
        self.cam.cy = h * 0.58
        self.district = random.choice(DISTRICTS)
        self.cam_no = random.randint(2, 48)
        self.colcache = {}
        self.build_city(random.Random(random.randint(0, 10 ** 6)))
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
        parks = set(r.sample([(gx, gz) for gx in range(-SPAN, SPAN) for gz in range(-SPAN, SPAN)], 3))
        for gx in range(-SPAN, SPAN):
            for gz in range(-SPAN, SPAN):
                bx0, bz0 = gx * CELL + STREET / 2, gz * CELL + STREET / 2
                park = (gx, gz) in parks
                self.blocks.append((bx0, bz0, bx0 + BLOCK, bz0 + BLOCK, park))
                if park:
                    for _ in range(9):
                        self.trees.append((bx0 + r.uniform(1.5, BLOCK - 1.5), bz0 + r.uniform(1.5, BLOCK - 1.5)))
                    continue
                ix0, iz0 = bx0 + SETBACK, bz0 + SETBACK
                inner = BLOCK - 2 * SETBACK
                layout = r.choice(("one", "one", "two_x", "two_z", "two_x", "two_z", "four"))
                if layout == "one":
                    lots = [(ix0, iz0, ix0 + inner, iz0 + inner)]
                elif layout == "two_x":
                    m = ix0 + inner * r.uniform(0.4, 0.6)
                    lots = [(ix0, iz0, m - 0.3, iz0 + inner), (m + 0.3, iz0, ix0 + inner, iz0 + inner)]
                elif layout == "two_z":
                    m = iz0 + inner * r.uniform(0.4, 0.6)
                    lots = [(ix0, iz0, ix0 + inner, m - 0.3), (ix0, m + 0.3, ix0 + inner, iz0 + inner)]
                else:
                    mx, mz = ix0 + inner / 2, iz0 + inner / 2
                    lots = [(ix0, iz0, mx - 0.3, mz - 0.3), (mx + 0.3, iz0, ix0 + inner, mz - 0.3),
                            (ix0, mz + 0.3, mx - 0.3, iz0 + inner), (mx + 0.3, mz + 0.3, ix0 + inner, iz0 + inner)]
                # downtown core in the middle, low-rise towards the edges where the camera flies
                core = max(0.0, min(1.0, 1.2 - math.hypot(bx0 + BLOCK / 2, bz0 + BLOCK / 2) / 40))
                for x0, z0, x1, z1 in lots:
                    tower = r.random() < 0.28 * core
                    hgt = r.uniform(11, 19) if tower else r.uniform(2.2, 3.5 + 7 * core)
                    pal = r.choice(PALETTES)
                    idx = len(self.boxes)
                    self.boxes.append((x0, z0, x1, z1, 0.0, hgt, pal[0], pal[1], -1))
                    ex = {"scheme": r.choice(WIN_SCHEMES), "density": r.uniform(0.12, 0.42), "seed": r.random()}
                    if r.random() < 0.18:
                        ex["neon"] = (r.randrange(4), r.choice(NEONS), r.uniform(0.25, 0.75))
                    if hgt > 11:
                        ex["beacon"] = True
                    self.extras[idx] = ex
                    if hgt > 5 and r.random() < 0.3:
                        cw, cd = (x1 - x0) * r.uniform(0.3, 0.5), (z1 - z0) * r.uniform(0.3, 0.5)
                        ox, oz = x0 + r.uniform(0.2, x1 - x0 - cw - 0.2), z0 + r.uniform(0.2, z1 - z0 - cd - 0.2)
                        self.boxes.append((ox, oz, ox + cw, oz + cd, hgt, hgt + r.uniform(0.8, 2.2),
                                           blend(pal[0], BLACK, 0.15), pal[1], idx))
        corners = []
        for x0, z0, x1, z1, y0, y1 in (b[:6] for b in self.boxes):
            corners.append(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                            (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)))
        self.corners = np.array(corners, dtype=float)
        self.block_quads = np.array([((a, 0, b), (c, 0, b), (c, 0, d), (a, 0, d)) for a, b, c, d, _ in self.blocks], dtype=float)
        # window grid per face, one pixel each; drawn after the buildings with an id-buffer test
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
                ncol = max(1, int((span - 0.6) / 1.35))
                for fy in np.arange(1.3, y1 - 0.7, 1.7):
                    for c in range(ncol):
                        if wr.random() < ex["density"]:
                            t = (c + 0.5) / ncol
                            pts.append((ax + (bx - ax) * t, fy, az + (bz - az) * t))
                            owner.append(i)
                            normal.append(nrm)
                            cols.append(ex["scheme"][wr.random() < 0.3])
        self.win_pts = np.array(pts, dtype=float).reshape(-1, 3)
        self.win_owner = np.array(owner, dtype=int)
        self.win_normal = np.array(normal, dtype=float).reshape(-1, 2)
        self.win_col = np.array(cols, dtype=float).reshape(-1, 3)
        # lane markings: dashed centre lines between intersections
        marks = []
        for k in range(-SPAN, SPAN + 1):
            for v in np.arange(-EDGE, EDGE, 0.5):
                if abs((v + CELL / 2) % CELL - CELL / 2) > STREET / 2 + 0.4 and v % 2.0 < 1.0:
                    marks.append((k * CELL, 0.0, v))
                    marks.append((v, 0.0, k * CELL))
        self.marks = np.array(marks, dtype=float)
        sub, scol = [], []
        sr = random.Random(11)
        while len(sub) < 450:
            x, z = sr.uniform(-EDGE - 70, EDGE + 70), sr.uniform(-EDGE - 70, EDGE + 70)
            if max(abs(x), abs(z)) > EDGE + 3:
                sub.append((x, sr.uniform(0.5, 3), z))
                scol.append(sr.choice(((150, 110, 60), (110, 80, 50), (80, 110, 140))))
        self.suburbs, self.suburb_cols = np.array(sub, dtype=float), np.array(scol, dtype=float)
        self.lamps = [(k * CELL + WALK - 0.3, m * CELL + WALK - 0.3)
                      for k in range(-SPAN, SPAN + 1) for m in range(-SPAN, SPAN + 1)]
        self.lamp_pts = np.array([(x, 3.2, z) for x, z in self.lamps], dtype=float)
        # distant skyline ring
        rr = random.Random(7)
        self.skyline = []
        hgt = 3.0
        for i in range(720):
            if rr.random() < 0.12:
                hgt = rr.choice((1.5, 2.5, 3.5, 5, 6.5, 9)) if rr.random() < 0.9 else rr.uniform(12, 18)
            self.skyline.append(hgt)
        self.sky_lights = {i: rr.random() for i in range(720) if rr.random() < 0.2}
        self.stars = [(rr.uniform(0, math.tau), rr.uniform(0.02, 0.5), rr.random()) for _ in range(70)]

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
        lane = k * CELL + (1.0 * d if along_x else -1.0 * d)
        return {"ax": along_x, "lane": lane, "dir": d, "pos": random.uniform(-EDGE, EDGE),
                "v": random.uniform(5.5, 8.5), "spd": 0.0, "col": random.choice(CAR_COLS), "screen": None}

    @staticmethod
    def world(o, y=0.0):
        return (o["pos"], y, o["lane"]) if o["ax"] else (o["lane"], y, o["pos"])

    def fog(self, col, z):
        q = max(0, min(12, int((z - 28) / 7)))
        key = (col, q)
        c = self.colcache.get(key)
        if c is None:
            c = blend(col, HAZE, q / 12 * 0.8)
            if len(self.colcache) > 8000:
                self.colcache.clear()
            self.colcache[key] = c
        return c

    def view_np(self, P):
        cam = self.cam
        cy_, sy_ = math.cos(-cam.yaw), math.sin(-cam.yaw)
        cp, sp = math.cos(-cam.pitch), math.sin(-cam.pitch)
        x, y, z = P[..., 0] - cam.pos[0], P[..., 1] - cam.pos[1], P[..., 2] - cam.pos[2]
        x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
        y, z = y * cp - z * sp, y * sp + z * cp
        return x, y, z

    def proj_np(self, P):
        vx, vy, vz = self.view_np(P)
        zc = np.maximum(vz, NEAR)
        cam = self.cam
        return cam.cx + vx / zc * cam.f * 2, (cam.cy - vy / zc * cam.f) * 2, vz

    def to_px(self, v):
        cam = self.cam
        return cam.cx + v[0] / v[2] * cam.f * 2, (cam.cy - v[1] / v[2] * cam.f) * 2

    def poly(self, vpts, col, bid=None):
        """Clip a view-space polygon to the near plane and fill it in pixel space."""
        if min(v[2] for v in vpts) < NEAR:
            out = []
            n = len(vpts)
            for i in range(n):
                a, b = vpts[i], vpts[(i + 1) % n]
                if a[2] >= NEAR:
                    out.append(a)
                if (a[2] >= NEAR) != (b[2] >= NEAR):
                    t = (NEAR - a[2]) / (b[2] - a[2])
                    out.append(tuple(a[j] + (b[j] - a[j]) * t for j in range(3)))
            if len(out) < 3:
                return
            vpts = out
        self.fill([self.to_px(v) for v in vpts], col, bid)

    def fill(self, pts, col, bid=None):
        ys = [p[1] for p in pts]
        y0, y1 = max(0, int(min(ys) + 0.5)), min(self.ph - 1, int(max(ys) - 0.5))
        if y0 > y1:
            return
        edges = []
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[i - 1]
            if ay == by:
                continue
            if ay > by:
                ax, ay, bx, by = bx, by, ax, ay
            edges.append((ay, by, ax, (bx - ax) / (by - ay)))
        rows, ids, w = self.rows, self.ids, self.w
        for py in range(y0, y1 + 1):
            yc = py + 0.5
            lo, hi = 1e9, -1e9
            for ay, by, ax, k in edges:
                if ay <= yc < by:
                    x = ax + (yc - ay) * k
                    if x < lo:
                        lo = x
                    if x > hi:
                        hi = x
            xa, xb = max(0, int(lo + 0.5)), min(w, int(hi + 0.5))
            if xb > xa:
                rows[py][xa:xb] = [col] * (xb - xa)
                if bid is not None:
                    ids[py][xa:xb] = [bid] * (xb - xa)

    def pline(self, a, b, col):
        rows, w, ph = self.rows, self.w, self.ph
        for x, y in line_points(int(a[0]), int(a[1]), int(b[0]), int(b[1])):
            if 0 <= x < w and 0 <= y < ph:
                rows[y][x] = col

    def seg(self, a, b, col):
        """Near-clipped world line in pixel space, fogged by its midpoint."""
        cam = self.cam
        va, vb = cam.to_view(a), cam.to_view(b)
        if va[2] < NEAR and vb[2] < NEAR:
            return
        if va[2] < NEAR or vb[2] < NEAR:
            if va[2] < NEAR:
                va, vb = vb, va
            k = (va[2] - NEAR) / (va[2] - vb[2])
            vb = tuple(va[i] + (vb[i] - va[i]) * k for i in range(3))
        pa, pb = self.to_px(va), self.to_px(vb)
        if max(pa[0], pb[0]) < 0 or min(pa[0], pb[0]) >= self.w or max(pa[1], pb[1]) < 0 or min(pa[1], pb[1]) >= self.ph:
            return
        from engine3d import clip2d
        c = clip2d(pa[0], pa[1], pb[0], pb[1], self.w, self.ph)
        if not c:
            return
        (t0, t1), dx, dy = c, pb[0] - pa[0], pb[1] - pa[1]
        self.pline((pa[0] + dx * t0, pa[1] + dy * t0), (pa[0] + dx * t1, pa[1] + dy * t1), col)

    def dot(self, x, py, col):
        if 0 <= x < self.w and 0 <= py < self.ph:
            self.rows[py][x] = col

    # ------------------------------------------------------------ static scene (refreshed at 12 Hz)
    def draw_world(self, s, now):
        cam, w, h = self.cam, self.w, self.h
        self.rows = [layer[py >> 1] for py in range(self.ph) for layer in ((s.pt, s.pb)[py & 1],)]
        self.ids = [[-1] * w for _ in range(self.ph)]
        # sky, stars, moon and distant skyline
        horizon = (cam.cy - math.tan(cam.pitch) * cam.f) * 2
        hrow = int(horizon / 2)
        for y in range(h):
            s.bg[y] = [blend(SKY_TOP, SKY_LOW, (y + 1) / max(1, hrow + 1)) if y <= hrow else GROUND_FAR] * w
        for az, el, tw in self.stars:
            dx = math.atan2(math.sin(az - cam.yaw), math.cos(az - cam.yaw))
            if abs(dx) < 1.3:
                x = int(cam.cx + math.tan(dx) * cam.f * 2)
                py = int(horizon - math.tan(el) * cam.f * 2 * 1.4)
                if 0 <= py < horizon - 3:
                    self.dot(x, py, blend((90, 90, 130), WHITE, tw * (0.6 + 0.4 * math.sin(now * 2 + tw * 9))))
        dx = math.atan2(math.sin(2.2 - cam.yaw), math.cos(2.2 - cam.yaw))
        if abs(dx) < 1.2:
            mx, my = cam.cx + math.tan(dx) * cam.f * 2, horizon - cam.f * 0.55
            for py in range(int(my) - 3, int(my) + 4):
                for x in range(int(mx) - 3, int(mx) + 4):
                    d = math.hypot(x - mx, py - my)
                    if d < 2.6 and py < horizon:
                        self.dot(x, py, blend((250, 240, 215), (150, 150, 170), max(0, (x - mx) / 3)))
        for x in range(w):
            az = cam.yaw + math.atan((x - cam.cx) / (cam.f * 2))
            i = int(az / math.tau * 720) % 720
            hp = int(self.skyline[i] / 140 * cam.f * 2 * 1.4)
            col = (14, 14, 30) if self.skyline[i] < 10 else (20, 20, 40)
            for py in range(int(horizon) - hp, int(horizon) + 1):
                self.dot(x, py, col)
            if i in self.sky_lights and hp > 2:
                self.dot(x, int(horizon) - int(hp * self.sky_lights[i]) - 1, (120, 90, 50))
        # ground: city slab, blocks, markings and lamp pools
        V = lambda p: tuple(float(c) for c in self.view_np(np.array(p, dtype=float)))
        # outskirts: dim street grid and scattered house lights beyond the downtown slab
        far = EDGE + 70
        for k in range(-SPAN - 5, SPAN + 6, 2):
            v = k * CELL
            for a, b in (((v, 0, -far), (v, 0, far)), ((-far, 0, v), (far, 0, v))):
                self.seg(a, b, (22, 24, 40))
        self.splat(self.suburbs, self.suburb_cols)
        e = EDGE + STREET / 2
        self.poly([V((-e, 0, -e)), V((e, 0, -e)), V((e, 0, e)), V((-e, 0, e))], ASPHALT)
        BX, BY, BZ = self.view_np(self.block_quads)
        bsx = cam.cx + BX / np.maximum(BZ, NEAR) * cam.f * 2
        bsy = (cam.cy - BY / np.maximum(BZ, NEAR) * cam.f) * 2
        bkeep = (BZ.max(axis=1) > NEAR) & (bsx.max(axis=1) >= 0) & (bsx.min(axis=1) < w) & (bsy.max(axis=1) >= 0) & (bsy.min(axis=1) < self.ph)
        BXl, BYl, BZl, BC = BX.tolist(), BY.tolist(), BZ.tolist(), BZ.mean(axis=1).tolist()
        bfast = (BZ.min(axis=1) > NEAR).tolist()
        bsxl, bsyl = bsx.tolist(), bsy.tolist()
        for i in np.nonzero(bkeep)[0].tolist():
            col = self.fog(PARK if self.blocks[i][4] else SIDEWALK, BC[i])
            if bfast[i]:
                self.fill(list(zip(bsxl[i], bsyl[i])), col)
            else:
                self.poly(list(zip(BXl[i], BYl[i], BZl[i])), col)
        self.splat(self.marks, np.array(MARK, dtype=float), self.view_np(self.marks)[2] < 60)
        # buildings, painter's order
        VX, VY, VZ = self.view_np(self.corners)
        SX = cam.cx + VX / np.maximum(VZ, NEAR) * cam.f * 2
        SY = (cam.cy - VY / np.maximum(VZ, NEAR) * cam.f) * 2
        keep = (VZ.max(axis=1) > NEAR) & (SX.max(axis=1) >= 0) & (SX.min(axis=1) < w) & (SY.max(axis=1) >= 0) & (SY.min(axis=1) < self.ph)
        ZC = VZ.mean(axis=1)
        self.bdepth = ZC.tolist()
        px, py_, pz = cam.pos
        order = []
        for i in np.nonzero(keep)[0].tolist():
            b = self.boxes[i]
            root = i if b[8] < 0 else b[8]
            rb = self.boxes[root]
            d = ((rb[0] + rb[2]) / 2 - px) ** 2 + ((rb[1] + rb[3]) / 2 - pz) ** 2
            order.append((-d, i != root, i))
        order.sort()
        VXl, VYl, VZl = VX.tolist(), VY.tolist(), VZ.tolist()
        SXl, SYl = SX.tolist(), SY.tolist()
        beacons = []
        FAST = (VZ.min(axis=1) > NEAR).tolist()
        for _, _, i in order:
            x0, z0, x1, z1, y0, y1, wall, roof, parent = self.boxes[i]
            fast = FAST[i]
            vs = list(zip(SXl[i], SYl[i])) if fast else list(zip(VXl[i], VYl[i], VZl[i]))
            draw = self.fill if fast else self.poly
            zc = ZC[i]
            vis = (pz < z0, pz > z1, px < x0, px > x1)
            root = i if parent < 0 else parent
            for fi in range(4):
                if not vis[fi]:
                    continue
                f = FACES[fi]
                draw([vs[j] for j in f], self.facecol(wall, fi, zc), root)
                if parent < 0 and zc < 75:
                    neon = self.extras[i].get("neon")
                    if neon and neon[0] == fi:
                        ax, az, bx, bz = ((x0, z0, x1, z0), (x1, z1, x0, z1), (x0, z1, x0, z0), (x1, z0, x1, z1))[fi]
                        t = neon[2]
                        nx, nz = ax + (bx - ax) * t, az + (bz - az) * t
                        q0, q1 = cam.project((nx, 1.2, nz)), cam.project((nx, min(y1 - 0.5, 6.5), nz))
                        if q0 and q1 and (int(now * 1.3 + i) % 7):
                            self.pline((q0[0], q0[1] * 2), (q1[0], q1[1] * 2), neon[1])
            if fast or vs[4][2] > NEAR:
                draw([vs[4], vs[5], vs[6], vs[7]], self.fog(roof, zc), root)
            # silhouette: roof rim plus the corner edge facing the camera
            if fast and zc < 110:
                rim = self.fog(blend(RIM, BLACK, 0.25 if parent < 0 else 0.5), zc + 10)
                for a, b in ((4, 5), (5, 6), (6, 7), (7, 4)):
                    self.pline((SXl[i][a], SYl[i][a]), (SXl[i][b], SYl[i][b]), rim)
                c = None
                if vis[0] and vis[2]:
                    c = 0
                elif vis[0] and vis[3]:
                    c = 1
                elif vis[1] and vis[3]:
                    c = 2
                elif vis[1] and vis[2]:
                    c = 3
                if c is not None and parent < 0:
                    self.pline((SXl[i][c], SYl[i][c]), (SXl[i][c + 4], SYl[i][c + 4]), self.fog(blend(RIM, BLACK, 0.55), zc + 10))
            if parent < 0 and self.extras[i].get("beacon"):
                beacons.append(((x0 + x1) / 2, y1 + 0.4, (z0 + z1) / 2))
        self.beacons = beacons
        if len(self.win_pts):
            ids = np.array(self.ids)
            facing = ((px - self.win_pts[:, 0]) * self.win_normal[:, 0] + (pz - self.win_pts[:, 2]) * self.win_normal[:, 1]) > 0
            self.splat(self.win_pts, self.win_col, facing, ids=ids, owner=self.win_owner, bias=-6)
        # trees in parks (low, drawn with occlusion)
        for tx, tz in self.trees:
            self.occluded_blob(tx, tz)
        # street lamps
        X, PY, Z = self.proj_np(self.lamp_pts)
        for x, py, z in zip(X.astype(int).tolist(), PY.astype(int).tolist(), Z.tolist()):
            if NEAR < z < 48 and not self.hidden(x, py, z):
                self.dot(x, py, self.fog((230, 200, 150), z))

    def facecol(self, wall, fi, z):
        q = max(0, min(12, int((z - 28) / 7)))
        key = (wall, fi, q)
        c = self.colcache.get(key)
        if c is None:
            c = self.colcache[key] = blend(blend(wall, BLACK, 1 - FACE_SHADE[fi]), HAZE, q / 12 * 0.8)
        return c

    def splat(self, P, rgb, extra=None, ids=None, owner=None, bias=0.0):
        """Vectorised projection + fog of single-pixel lights; optional id-buffer visibility."""
        X, PY, Z = self.proj_np(P)
        xi, yi = X.astype(int), PY.astype(int)
        m = (Z > NEAR) & (xi >= 0) & (xi < self.w) & (yi >= 0) & (yi < self.ph)
        if extra is not None:
            m &= extra
        if ids is not None:
            m[m] &= ids[yi[m], xi[m]] == owner[m]
        if not m.any():
            return
        k = np.clip((Z[m] + bias - 28) / 84, 0, 0.8)[:, None]
        base = rgb[m] if rgb.ndim == 2 else rgb[None, :]
        col = (base * (1 - k) + np.array(HAZE, dtype=float) * k).astype(int).tolist()
        rows = self.rows
        for x, y, c in zip(xi[m].tolist(), yi[m].tolist(), col):
            rows[y][x] = tuple(c)

    def hidden(self, x, py, z):
        if 0 <= x < self.w and 0 <= py < self.ph:
            b = self.ids[py][x]
            return b >= 0 and self.bdepth[b] < z - 0.5
        return True

    def occluded_blob(self, tx, tz):
        q = self.cam.project((tx, 1.3, tz))
        if not q:
            return
        x, py, z = int(q[0]), int(q[1] * 2), q[2]
        if self.hidden(x, py, z):
            return
        dark, light = self.fog((20, 70, 40), z), self.fog((40, 110, 60), z)
        for dx, dy, c in ((0, 0, dark), (-1, 0, dark), (1, 0, dark), (0, -1, light), (0, 1, (40, 30, 24))):
            self.dot(x + dx, py + dy, c)

    # ------------------------------------------------------------ moving things
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

    def draw_traffic(self, s, now):
        cam = self.cam
        rows = self.rows
        for c in self.cars:
            d = c["dir"]
            fwd = (d, 0) if c["ax"] else (0, d)
            x, _, z = self.world(c)
            f = cam.project((x + fwd[0] * 1.0, 0.45, z + fwd[1] * 1.0))
            b = cam.project((x - fwd[0] * 1.0, 0.45, z - fwd[1] * 1.0))
            if not f or not b:
                c["screen"] = None
                continue
            c["screen"] = f
            fx, fy, bx, by = int(f[0]), int(f[1] * 2), int(b[0]), int(b[1] * 2)
            hid = self.hidden(fx, fy, f[2]) and self.hidden(bx, by, b[2])
            if hid:
                continue
            for k in (2.2, 3.4):
                q = cam.project((x + fwd[0] * k, 0.0, z + fwd[1] * k))
                if q and not self.hidden(int(q[0]), int(q[1] * 2), q[2]):
                    self.dot(int(q[0]), int(q[1] * 2), self.fog((120, 110, 70) if k < 3 else (70, 64, 46), q[2]))
            self.pline((bx, by), (fx, fy), self.fog(c["col"], f[2]))
            self.dot(fx, fy, (255, 250, 225))
            self.dot(bx, by, (255, 40, 50) if c["spd"] > c["v"] * 0.3 else (255, 90, 90))
        for p in self.peds:
            x, _, z = self.world(p)
            foot = cam.project((x, 0.0, z))
            head = cam.project((x, 1.9, z))
            if not foot or not head:
                p["screen"] = None
                continue
            hx, hy, fy = int(head[0]), int(head[1] * 2), int(foot[1] * 2)
            p["screen"] = (head[0], (head[1] + foot[1]) / 2, foot[2])
            if not (0 <= hx < self.w and 0 <= hy < self.ph):
                continue
            hid = self.hidden(hx, max(hy, fy - 1), foot[2])
            p["hidden"] = hid
            body = XRAY if hid else self.fog(p["body"], foot[2])
            for yy in range(hy + 1, max(hy + 2, fy + 1)):
                self.dot(hx, yy, body)
            self.dot(hx, hy, blend(XRAY, WHITE, 0.2) if hid else self.fog(SKIN, foot[2]))
        # signals and roof beacons
        for k in range(-SPAN, SPAN + 1):
            for m in range(-SPAN, SPAN + 1):
                q = cam.project((k * CELL - WALK + 0.3, 2.4, m * CELL - WALK + 0.3))
                if q and q[2] < 42 and not self.hidden(int(q[0]), int(q[1] * 2), q[2]):
                    gx = int(now / 4 + k * 0.5 + m * 0.5) % 2 == 0
                    self.dot(int(q[0]), int(q[1] * 2), (60, 255, 120) if gx else (255, 50, 60))
        if int(now * 1.5) % 2:
            for bpos in self.beacons:
                q = cam.project(bpos)
                if q:
                    self.dot(int(q[0]), int(q[1] * 2), (255, 40, 40))

    # ------------------------------------------------------------ camera
    def update_camera(self, now, dt):
        locked = self.reticles[0]["target"] if self.reticles[0]["lock"] >= 1 else None
        self.zoom += ((1.0 if locked else 0.0) - self.zoom) * min(1, dt * 1.2)
        tx, tz = (self.world(locked)[0], self.world(locked)[2]) if locked else (0.0, 0.0)
        self.focus[0] += (tx - self.focus[0]) * min(1, dt * 1.2)
        self.focus[1] += (tz - self.focus[1]) * min(1, dt * 1.2)
        self.orbit += dt * 0.07

    def place_camera(self, now):
        cam = self.cam
        R = 50 - self.zoom * 8
        hgt = 30 + math.sin(now * 0.11) * 3 - self.zoom * 4
        fx, fz = self.focus
        cam.pos = [fx + math.sin(self.orbit) * R, hgt, fz - math.cos(self.orbit) * R]
        cam.yaw = math.atan2(fx - cam.pos[0], fz - cam.pos[2])
        cam.pitch = math.atan2(hgt - 1.0, R) * 0.95
        cam.roll = 0.0

    # ------------------------------------------------------------ overlays
    def label(self, s, x, y, text, col, bg=PANEL_BG):
        x = max(0, min(self.w - len(text), x))
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
        for r in self.reticles:
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
                size = int(5 - 2.5 * r["lock"])
                col = blend(YELLOW, BLACK, 0.15) if r["lock"] < 1 else (200, 200, 120)
                s.brackets(x - size, y - size // 2 - 1, size * 2 + 1, size + 2, col, arm=1)
                if r["lock"] >= 1:
                    self.label(s, x + size + 2, y - 1, tgt["name"].upper(), (210, 210, 220))
                    self.label(s, x + size + 2, y, "AGE %d // RISK %d%%" % (tgt["age"], hash(tgt["name"]) % 100), GREY)
                else:
                    self.label(s, x + size + 2, y, "SCAN %3d%%" % (r["lock"] * 100), YELLOW)

    def primary_reticle(self, s, now, r, tgt, x, y):
        lock = r["lock"]
        size = int(9 - 6 * lock)
        col = self.profile["color"] if lock >= 1 else YELLOW
        top, bot = y - size // 2 - 1, y + size // 2 + 1
        s.brackets(x - size, top, size * 2 + 1, bot - top + 1, col, arm=2 if lock < 1 else 1)
        if lock < 1:
            # sweep line scanning the subject
            sy = top + 1 + int((now * 9) % max(1, bot - top - 1))
            s.tint_row(sy, CYAN, 0.3, x - size + 1, x + size)
            for dx in (-size - 2, size + 2):
                s.put(x + dx, y, "─", blend(YELLOW, BLACK, 0.3))
            s.put(x, top - 1, "│", blend(YELLOW, BLACK, 0.3))
            self.label(s, x - 7, top - 2, "PROFILING " + "▮" * int(lock * 6) + "▯" * (6 - int(lock * 6)), YELLOW)
        else:
            s.put(x, top - 1, "▼", col)
            name = tgt["name"].upper()
            self.label(s, x - len(name) // 2, top - 2, name, WHITE)
            self.link = (x + size + 1, y, col)

    def draw_link(self, s, now):
        if not self.link or not self.card_rect:
            return
        x0, y0, col = self.link
        cx, cy, cw, ch = self.card_rect
        if x0 >= cx:
            return
        x1, y1 = cx - 1, max(cy + 1, min(cy + ch - 2, y0))
        elbow = x1 - max(4, (x1 - x0) // 3)
        pts = line_points(x0, y0, elbow, y0) + line_points(elbow, y0, x1, y1)[1:]
        head = int(now * 30) % max(1, len(pts))
        for i, (x, y) in enumerate(pts):
            k = (head - i) % len(pts)
            c = blend(WHITE, col, k / 3) if k < 3 else blend(col, BLACK, 0.45)
            s.put(x, y, "·" if k >= 3 else "•", c)
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
        cam = self.cam
        cxp, czp = mp(cam.pos[0], cam.pos[2])
        for da in (-0.6, 0.6):
            a = cam.yaw + da
            ex, ez = mp(cam.pos[0] + math.sin(a) * 26, cam.pos[2] + math.cos(a) * 26)
            for x, y in line_points(cxp, czp, ex, ez):
                if ix <= x < ix + mm["w"] - 2 and iy <= y < iy + (mm["h"] - 2) * 2:
                    s.pixel(x, y, (120, 40, 80))
        s.pixel(cxp, czp, PINK)
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
            "portrait": self.identicon(),
            "color": random.choice((PINK, CYAN, YELLOW, GREEN)),
        }
        self.started = now
        self.history = ([name] + self.history)[:6]
        self.scanned += 1
        self.glitch.trigger(now, 0.25)

    @staticmethod
    def identicon():
        rows = []
        for _ in range(8):
            half = [random.random() < 0.5 for _ in range(4)]
            rows.append(half + half[::-1])
        return rows

    def draw_card(self, s, now):
        elapsed = now - self.started
        p = self.profile
        card_w = min(64, self.w - 6)
        card_h = 18
        slide = (1 - min(1.0, elapsed / 0.4)) ** 3
        cx = self.w - card_w - 3 + int(slide * (card_w + 6)) if self.w > 140 else (self.w - card_w) // 2
        cy = min(self.h - card_h - 3, max(3, (self.h - card_h) // 2 + 4))
        self.card_rect = (cx, cy, card_w, card_h)
        col = p["color"]
        s.box(cx, cy, card_w, card_h, col, title="ctOS PROFILER", double=True)
        for yy in range(cy + 1, min(self.h, cy + card_h - 1)):
            row = s.bg[yy]
            for xx in range(max(0, cx + 1), min(self.w, cx + card_w - 1)):
                row[xx] = PANEL_BG

        reveal = min(8, int(elapsed * 6))
        for r in range(8):
            for c in range(8):
                if r < reveal:
                    ch = "██" if p["portrait"][r][c] else "  "
                else:
                    ch = random.choice(("▒▒", "░░", "  "))
                s.text(cx + 3 + c * 2, cy + 2 + r, ch, col if r < reveal else GREY)
        s.text(cx + 3, cy + 11, "ID#%08X" % (hash(p["name"]) & 0xFFFFFFFF), GREY)

        def typed(text, start):
            return text[:max(0, int((elapsed - start) * 30))]

        fx = cx + 22
        fields = [("NAME", p["name"], WHITE), ("AGE", str(p["age"]), WHITE), ("OCCUPATION", p["job"], WHITE),
                  ("INCOME", p["income"], GREEN), ("STATUS", p["status"][0], p["status"][1])]
        for i, (k, v, c) in enumerate(fields):
            s.text(fx, cy + 2 + i, k.ljust(11), GREY)
            s.text(fx + 11, cy + 2 + i, typed(v, 0.3 + i * 0.25), c)
        width = card_w - 25
        for i, line in enumerate(p["intel"]):
            s.text(fx, cy + 8 + i, typed("» " + line, 1.8 + i * 0.8)[:width], YELLOW)
        if elapsed > 3.2:
            s.text(fx, cy + 11, "[ HACK: %s ]" % p["action"], PINK if int(now * 4) % 2 else WHITE)
        bar_w = card_w - 6
        prog = min(1.0, elapsed / 4.5)
        s.text(cx + 3, cy + 14, "ANALYZING ", GREY)
        filled = int((bar_w - 10) * prog)
        s.text(cx + 13, cy + 14, "█" * filled + "░" * (bar_w - 10 - filled), col)
        if prog >= 1:
            s.text(cx + 3, cy + 15, "PROFILE COMPLETE // UPLOADED TO DEDSEC", GREEN)

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        if now - self.started > 14:
            self.new_profile(now)        # nobody visible for a while: keep the card alive

        self.update_camera(now, dt)
        self.update_traffic(now, dt)
        stamp = int(now * 8)
        if stamp != self.city_stamp or self.city_frame is None:
            self.place_camera(now)
            self.draw_world(s, now)
            self.city_frame = (s.snapshot(), self.ids, self.bdepth, self.beacons)
            self.city_stamp = stamp
        else:
            snap, self.ids, self.bdepth, self.beacons = self.city_frame
            s.restore(snap)
            self.rows = [layer[py >> 1] for py in range(self.ph) for layer in ((s.pt, s.pb)[py & 1],)]
        self.draw_traffic(s, now)
        self.draw_reticles(s, now)
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

"""TRAFFIC CHAOS: a wet ctOS intersection that DedSec hijacks on a loop.

Cycle (40 s): NOMINAL signals -> BREACH (link to the signal heads) -> CHAOS
(all green, rushing cars, near misses and skid marks, bollards, a flipped car
with sparks, a burst hydrant and steam, horns, a jam, an SFPD cruiser) ->
RESTORE (signals resync, wreck towed, marks washed) -> NOMINAL.

Vehicles and pedestrians keep persistent positions with acceleration, braking
and spacing. Cars are cached per lane slot as depth-tested pixel sprites, so the
scene stays solid without rasterising every face on every frame.
"""
import math
import random
from engine3d import Camera
from lib import BLACK, CYAN, PINK, YELLOW, GREEN, WHITE, ORANGE, blend

NAME = 'TRAFFIC'
RED = (245, 58, 45)
BLUE = (50, 110, 255)
ASPHALT = (36, 43, 50)
SKID = (21, 25, 30)
CYCLE = 40.0
PHASES = (("NOMINAL", 0, 13), ("BREACH", 13, 16), ("CHAOS", 16, 29), ("RESTORE", 29, 35), ("NOMINAL", 35, 40))
CAR_COLS = [(168, 62, 63), (56, 113, 142), (191, 157, 79), (139, 146, 145), (92, 70, 128), (214, 178, 52)]
GLASS = (35, 64, 77)
TYRE = (17, 22, 25)
HEAD = (239, 224, 165)
STOP_V = -11.2          # car centre at the stop line (front stays off the zebra)
HALF = 1.9              # car half length
BOLLARD_V = 15.0        # along lane (0, +1), after the junction
WRECK_V = 20.6
LIGHT = (0.25, 0.85, -0.45)
_ln = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _ln for c in LIGHT)

# Local car boxes: (f0, f1, s0, s1, y0, y1, part)
CAR_BOXES = [
    (-1.9, 1.9, -.88, .88, .22, .87, 'body'),
    (-1.0, 1.0, -.46, .46, .87, 1.47, 'glass'),
    (-.92, .92, -.42, .42, 1.47, 1.57, 'roof'),
    (1.86, 1.95, -.7, -.42, .5, .68, 'head'), (1.86, 1.95, .42, .7, .5, .68, 'head'),
    (-1.95, -1.86, -.7, -.42, .5, .66, 'tail'), (-1.95, -1.86, .42, .7, .5, .66, 'tail'),
]
for _f in (-1.33, 1.33):
    for _s in (-.9, .9):
        CAR_BOXES.append((_f - .3, _f + .3, _s - .1, _s + .1, .05, .45, 'tyre'))


def _norm_shade(col, n):
    k = .55 + .45 * max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
    c = blend(col, BLACK, 1 - k)
    return blend(c, WHITE, .1) if n[1] > .9 else c


def _fill(buf, pts, col, dep, w, ph):
    """Scanline fill of a convex polygon (pixel coords) into a {(x, py): (col, dep)} dict."""
    ys = [p[1] for p in pts]
    n = len(pts)
    for py in range(max(0, int(min(ys))), min(ph - 1, int(max(ys))) + 1):
        yc = py + .5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
        if len(xs) >= 2:
            for x in range(max(0, int(min(xs) + .5)), min(w - 1, int(max(xs) + .5)) + 1):
                buf[(x, py)] = (col, dep)


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = Camera(w, h, 1.55)
        self.cam.pos = [25, 32, -37]
        self.cam.yaw = -math.atan2(25, 37)
        self.cam.pitch = math.atan2(32, math.hypot(25, 37))
        self.cam.cy = h * .52
        self.start = None
        self.static = self.clean = None
        self.z = None
        self.record = False
        self.rng = random.Random(7)
        self.sprites = {}
        self.last = None
        self.cycle_n = -1
        self.reset_traffic()

    # ------------------------------------------------------------ static scene
    def quad(self, s, pts, col):
        pp = [self.cam.project(p) for p in pts]
        if not all(pp):
            return
        depth = sum(p[2] for p in pp) / len(pp)
        pts = [(p[0], p[1] * 2) for p in pp]
        ax, ay = pts[0]; bx, by = pts[1]; cx, cy = pts[2]
        det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(det) < 1e-7:
            return
        da, db, dc = 1 / pp[0][2], 1 / pp[1][2], 1 / pp[2][2]
        ux = ((db - da) * (cy - ay) - (dc - da) * (by - ay)) / det
        uy = ((bx - ax) * (dc - da) - (cx - ax) * (db - da)) / det
        uz = da - ux * ax - uy * ay
        ys = [p[1] for p in pts]
        for py in range(max(4, int(min(ys))), min(self.h * 2 - 4, int(max(ys)) + 1)):
            xs = []; yc = py + .5
            for i, (ax, ay) in enumerate(pts):
                bx, by = pts[(i + 1) % len(pts)]
                if ay <= yc < by or by <= yc < ay:
                    xs.append(ax + (yc - ay) / (by - ay) * (bx - ax))
            if len(xs) < 2:
                continue
            row = (s.pb if py & 1 else s.pt)[py >> 1]
            zr = self.z[py]
            for x in range(max(0, int(min(xs))), min(self.w, int(max(xs)) + 1)):
                inv = ux * (x + .5) + uy * yc + uz
                dep = 1 / inv if inv > 0 else depth
                if dep <= zr[x] + .12:
                    row[x] = col
                    if self.record:
                        zr[x] = dep

    def plane(self, s, x, z, wx, wz, col, y=.02):
        self.quad(s, [(x - wx, y, z - wz), (x + wx, y, z - wz), (x + wx, y, z + wz), (x - wx, y, z + wz)], col)

    def box(self, s, x, z, wx, wz, height, col, base=0):
        p = [(x - wx, base, z - wz), (x + wx, base, z - wz), (x + wx, base, z + wz), (x - wx, base, z + wz)]
        p += [(a, base + height, c) for a, _, c in p]
        for face, c in [((0, 1, 5, 4), blend(col, BLACK, .22)), ((1, 2, 6, 5), blend(col, BLACK, .4)), ((4, 5, 6, 7), blend(col, WHITE, .12))]:
            self.quad(s, [p[i] for i in face], c)

    def building(self, s, x, z, wx, wz, hh, col, sign):
        self.box(s, x, z, wx, wz, hh, col, .2)
        self.box(s, x, z, wx + .15, wz + .15, .22, (87, 83, 87), hh + .2)
        self.box(s, x + .8, z + .8, wx * .4, wz * .4, .7, (53, 61, 65), hh + .45)
        for y in range(1, int(hh)):
            self.quad(s, [(x - wx, y, z - wz - .04), (x + wx, y, z - wz - .04), (x + wx, y + .035, z - wz - .04), (x - wx, y + .035, z - wz - .04)], blend(col, BLACK, .32))
        for side in (0, 1):
            span = wx if side == 0 else wz
            for yy in range(3, int(hh), 2):
                for j in range(-int(span) + 1, int(span), 2):
                    lit = (j + yy + int(x)) % 5 < 2
                    c = ((119, 104, 77) if x < 0 else (89, 115, 128)) if lit else (39, 49, 58)
                    if side == 0:
                        pts = [(x + j - .58, yy, z - wz - .08), (x + j + .58, yy, z - wz - .08), (x + j + .58, yy + 1.25, z - wz - .08), (x + j - .58, yy + 1.25, z - wz - .08)]
                    else:
                        pts = [(x + wx + .08, yy, z + j - .58), (x + wx + .08, yy, z + j + .58), (x + wx + .08, yy + 1.25, z + j + .58), (x + wx + .08, yy + 1.25, z + j - .58)]
                    self.quad(s, pts, c)
        for j in range(-int(wx) + 1, int(wx), 2):
            self.quad(s, [(x + j - .7, .4, z - wz - .12), (x + j + .7, .4, z - wz - .12), (x + j + .7, 2.3, z - wz - .12), (x + j - .7, 2.3, z - wz - .12)], (37, 83, 94))
            self.quad(s, [(x + j - .65, .5, z - wz - .14), (x + j - .35, .5, z - wz - .14), (x + j + .5, 2.2, z - wz - .14), (x + j + .2, 2.2, z - wz - .14)], (67, 112, 118))
        for j in range(int(wx * 2)):
            self.quad(s, [(x - wx + j, 2.6, z - wz), (x - wx + j + 1, 2.6, z - wz), (x - wx + j + 1, 2.15, z - wz - 1.1), (x - wx + j, 2.15, z - wz - 1.1)], (161, 65, 61) if j % 2 else (180, 158, 121))
        neon = PINK if x < 0 else CYAN
        self.quad(s, [(x - wx, 2.7, z - wz - .15), (x + wx, 2.7, z - wz - .15), (x + wx, 2.86, z - wz - .15), (x - wx, 2.86, z - wz - .15)], neon)
        for k in range(7):
            rz = z - wz - 1.4 - k * .8
            self.plane(s, x + math.sin(k * 3) * .4, rz, wx * (.45 - k * .035), .055, blend(neon, BLACK, .65 + k * .045), .015)
        q = self.cam.project((x, 2.9, z - wz - .2))
        if q and self.w >= 120:
            s.text(int(q[0]) - len(sign) // 2, int(q[1]), sign, (222, 185, 128))

    def scenery(self, s):
        s.gradient_bg((13, 18, 29), (26, 30, 39))
        self.z = [[1e8] * self.w for _ in range(self.h * 2)]
        self.record = True
        self.plane(s, 0, 0, 33, 30, ASPHALT, -.1)
        rng = random.Random(77)
        for _ in range(700):
            x, z = rng.uniform(-32, 32), rng.uniform(-29, 29)
            self.plane(s, x, z, rng.uniform(.07, .45), rng.uniform(.05, .24), rng.choice([(40, 47, 54), (32, 39, 46), (43, 50, 57), (35, 43, 51)]), -.09)
        for x in (-19, 19):
            for z in (-18, 18):
                self.box(s, x, z, 12, 11, .3, (76, 79, 78))
                for a in range(-11, 12, 2):
                    for b in range(-10, 11, 2):
                        self.plane(s, x + a, z + b, .94, .94, (79 + (a + b) % 3, 81 + (a + b) % 3, 78 + (a + b) % 3), .32)
        for v in range(-29, 30, 4):
            if abs(v) > 9:
                self.plane(s, v, 0, 1, .09, (185, 155, 69))
                self.plane(s, 0, v, .09, 1, (185, 155, 69))
                self.plane(s, v, 5.7, 1.6, .07, (148, 156, 153))
                self.plane(s, 5.7, v, .07, 1.6, (148, 156, 153))
        # Stop bars in front of each zebra.
        for side in (-1, 1):
            self.plane(s, side * 9.6, -side * 3.5, .12, 3.4, (200, 204, 198))
            self.plane(s, side * 3.5, side * 9.6, 3.4, .12, (200, 204, 198))
        for i in range(-5, 6, 2):
            for side in (-1, 1):
                self.plane(s, i, side * 8, .55, 1.1, (175, 182, 177))
                self.plane(s, side * 8, i, 1.1, .55, (175, 182, 177))
        for i in range(26):
            x = -29 + i * 2.2
            self.plane(s, x, 4.6, .65, .08, (56, 76, 84), .01)
            self.plane(s, -4.6, x, .08, .5, (73, 60, 67), .01)
        for x, z in [(-8, -12), (8, 12), (-12, 8), (12, -8)]:
            self.plane(s, x, z, .65, .65, (39, 45, 46), .34)
            for d in range(-3, 4):
                self.plane(s, x + d * .15, z, .03, .55, (108, 113, 109), .35)
        # Steam manhole on the near carriageway.
        self.plane(s, -15, -5.2, .75, .75, (52, 56, 58), .0)
        self.plane(s, -15, -5.2, .5, .5, (30, 34, 37), .01)
        for a in [(-17, 18, 7, 7, 12, (99, 75, 66), 'CAFE 24'), (17, 18, 7, 7, 15, (71, 81, 91), 'RECORDS'), (-22, -19, 7, 6, 5, (109, 93, 76), 'MARKET'), (22, -20, 6, 6, 6, (89, 77, 82), 'LAUNDRY')]:
            self.building(s, *a)
        for x, z in [(-8, -7), (8, 7), (-8, 7), (8, -7)]:
            self.box(s, x, z, .12, .12, 4.6, (98, 105, 106), .3)
            self.box(s, x - 1, z, .95, .13, .13, (124, 130, 129), 4.75)
            self.box(s, x - 1.8, z, .35, .28, .18, (213, 199, 137), 4.55)
            self.box(s, x, z, .33, .28, 1.05, (20, 27, 29), 3.2)
        for x, z in [(-10, -5), (10, 5), (-10, 5), (10, -5)]:
            self.box(s, x, z, .45, .45, .95, (42, 77, 64), .35)
        for x, z in [(-12, -9), (12, 9)]:
            self.box(s, x, z, 1.2, .4, .2, (131, 92, 58), .9)
            self.box(s, x - 1, z, .09, .1, .9, (54, 60, 62), .3)
            self.box(s, x + 1, z, .09, .1, .9, (54, 60, 62), .3)
        # Fire hydrant on the near corner.
        hx, hz = self.HYDRANT
        self.box(s, hx, hz, .28, .28, .75, (196, 40, 36), .32)
        self.box(s, hx, hz, .4, .14, .14, (160, 30, 30), .72)
        self.box(s, hx, hz, .2, .2, .18, (220, 190, 70), 1.07)
        self.record = False
        self.clean = s.snapshot()
        self.static = self.clean

    HYDRANT = (8.7, -14.5)
    MANHOLE = (-15, -5.2)

    # ------------------------------------------------------------ simulation
    def reset_traffic(self):
        self.cars = []
        self.cid = 0
        for axis in (0, 1):
            for d in (-1, 1):
                for i in range(3 if (axis + d) % 2 else 4):
                    self.spawn((axis, d), -30 + i * 17 + axis * 4 + (d + 1) * 2.5, 5)
        self.peds = []
        cross = [('z', 8), ('z', -8), ('x', 8), ('x', -8)]
        pal = [(214, 96, 70), (80, 160, 210), (226, 200, 96), (190, 110, 200), (90, 200, 130)]
        for i in range(10):
            c = cross[i % 4]
            side = -1 if (i // 4) % 2 else 1
            self.peds.append({'c': c, 'u': side * (8.4 + (i % 3) * .5), 'dir': -side, 'state': 'wait',
                              'delay': (i % 3) * .5 + i * .07, 'lat': ((i % 3) - 1) * .45, 'col': pal[i % len(pal)],
                              'speed': 1.3 + (i % 4) * .12, 'panic': False})
        self.skids = []
        self.pending_skids = []
        self.particles = []
        self.bubbles = []
        self.callouts = []
        self.wreck = None
        self.victim = None
        self.police = None
        self.stats = {'near': 0, 'horn': 0, 'wreck': 0, 'jam': 0}
        self.bollard_h = 0.0
        self.water = 0.0
        self.steam = 0.0
        self.flags = set()

    def spawn(self, lane, v, sp, kind='car'):
        self.cid += 1
        car = {'lane': lane, 'v': v, 'sp': sp, 'col': self.rng.randrange(len(CAR_COLS)), 'id': self.cid,
               'kind': kind, 'vmax': self.rng.uniform(5.0, 6.4), 'honk': 0.0, 'skid': False,
               'near_cd': 0.0, 'target': None}
        self.cars.append(car)
        return car

    @staticmethod
    def world(lane, v):
        axis, d = lane
        return (v * d, -d * 2.6) if axis == 0 else (d * 2.6, v * d)

    def phase_of(self, p):
        for name, a, b in PHASES:
            if a <= p < b:
                return name, (p - a) / (b - a)
        return 'NOMINAL', 0.0

    def signals(self, p):
        """Per-axis signal state: 'G', 'Y' or 'R'; plus 'X' (scrambled) during breach."""
        name, _ = self.phase_of(p)
        if name == 'CHAOS':
            return {0: 'G', 1: 'G'}
        if name == 'BREACH':
            return {0: 'X', 1: 'X'}
        if name == 'RESTORE':
            return {0: 'R', 1: 'R'} if p < 32 else self._normal(p - 32)
        local = p if p < 13 else p - 35
        return self._normal(local)

    @staticmethod
    def _normal(t):
        t %= 13
        if t < 5:
            return {0: 'G', 1: 'R'}
        if t < 6:
            return {0: 'Y', 1: 'R'}
        if 6.5 <= t < 11.5:
            return {0: 'R', 1: 'G'}
        if 11.5 <= t < 12.5:
            return {0: 'R', 1: 'Y'}
        return {0: 'R', 1: 'R'}

    def sim(self, dt, p, sig):
        name, _ = self.phase_of(p)
        chaos = name == 'CHAOS'
        by_lane = {}
        for c in self.cars:
            by_lane.setdefault(c['lane'], []).append(c)
        for lane_cars in by_lane.values():
            lane_cars.sort(key=lambda c: -c['v'])
        stopped = 0
        for lane, lane_cars in by_lane.items():
            axis, d = lane
            for idx, c in enumerate(lane_cars):
                if c is self.victim and c.get('flip') is not None:
                    continue
                v, sp = c['v'], c['sp']
                vmax = c['vmax'] * (1.85 if chaos else 1.0)
                if c is self.victim:
                    vmax = 12.5
                limit = 1e9      # nearest stop position for the car centre
                hard_ok = False
                # Car ahead.
                if idx > 0:
                    ahead = lane_cars[idx - 1]
                    limit = min(limit, ahead['v'] - 2 * HALF - 1.1)
                # Signal.
                st = 'G' if c['kind'] == 'police' else sig[axis]
                if st != 'G' and v < STOP_V - .05:
                    dist = STOP_V - v
                    need = sp * sp / (2 * max(.1, dist))
                    if st in 'RX' or need < 5.5:
                        if need < 16 or st == 'X':
                            limit = min(limit, STOP_V)
                # Obstacles: bollards and wreck on lane (0, +1); police stop.
                if lane == (0, 1) and c is not self.victim:
                    if self.bollard_h > .15 and v < BOLLARD_V:
                        limit = min(limit, BOLLARD_V - .5 - HALF)
                    if self.wreck is not None and v < WRECK_V:
                        limit = min(limit, WRECK_V - 2.6 - HALF)
                if c['target'] is not None:
                    limit = min(limit, c['target'])
                # Cross-traffic conflicts inside the box.
                if c.get('commit') and abs(v) > 9:
                    c['commit'] = False
                if c is not self.victim and not c.get('commit'):
                    for vc_sign in (-1, 1):
                        vc = vc_sign * 2.6
                        dc = vc - v
                        if dc < 3.4 or dc > 14:
                            continue
                        dp = vc_sign * d       # perpendicular lane direction whose path crosses here
                        for o in by_lane.get((1 - axis, dp), ()):
                            if o is self.victim and o.get('flip') is not None:
                                continue
                            ovc = -d * 2.6 * dp
                            odc = ovc - o['v']
                            inside = abs(odc) < 3.4
                            sooner = 0 < odc < 14 and (odc / max(.5, o['sp']) < dc / max(.5, sp) - .05 or
                                                      (abs(odc / max(.5, o['sp']) - dc / max(.5, sp)) <= .05 and o['id'] < c['id']))
                            if inside or sooner:
                                limit = min(limit, vc - 3.4)
                                hard_ok = True
                                if sp < .3:
                                    # Gridlock breaker: after a long wait ctOS waves the car through.
                                    c['wait'] = c.get('wait', 0) + dt
                                    if c['wait'] > (2.5 if name != 'CHAOS' else 5.0):
                                        c['commit'] = True
                                        c['wait'] = 0
                                if inside and dc < 7 and sp > 4 and c['near_cd'] <= 0:
                                    c['near_cd'] = 3.0
                                    self.stats['near'] += 1
                                    self.honk(c, 1.2)
                                    self.honk(o, .8)
                                break
                c['near_cd'] -= dt
                # Speed control: brake towards the limit, else accelerate to vmax.
                gap = limit - v
                if gap <= .02:
                    want = 0.0
                else:
                    want = min(vmax, math.sqrt(2 * 6.0 * gap))
                if want < sp:
                    dec = (sp - want) / max(dt, 1e-3)
                    hard = dec > 9 and sp > 3.5
                    dec = min(dec, 18 if (hard_ok or hard) else 9)
                    c['skid'] = hard or (hard_ok and dec > 8 and sp > 3)
                    sp = max(0.0, sp - dec * dt)
                else:
                    c['skid'] = False
                    sp = min(want, sp + (6.5 if chaos else 3.2) * dt)
                nv = min(v + sp * dt, limit if limit > v else v)
                if c['skid']:
                    self.pending_skids.append((lane, v, nv))
                c['v'], c['sp'] = nv, sp
                if sp < .3 and (chaos or name == 'RESTORE'):
                    stopped += 1
                    if self.rng.random() < dt * .5:
                        self.honk(c, .9)
                c['honk'] -= dt
        self.stats['jam'] = stopped
        # Recycle cars that left the scene.
        keep = []
        for c in self.cars:
            if c['v'] > 36:
                if c['kind'] == 'police':
                    self.police = None
                    continue
                lane_min = min((o['v'] for o in self.cars if o['lane'] == c['lane'] and o is not c), default=0)
                if lane_min > -32:
                    c['v'] = -36.0
                    c['sp'] = c['vmax']
                    c['col'] = self.rng.randrange(len(CAR_COLS))
                    c['target'] = None
                else:
                    c['v'] = 36.0
                    c['sp'] = 0
                    continue
            keep.append(c)
        self.cars = keep
        while sum(1 for c in self.cars if c['kind'] == 'car') < 13:
            lanes = [(a, b) for a in (0, 1) for b in (-1, 1)]
            lane = min(lanes, key=lambda l: sum(1 for c in self.cars if c['lane'] == l))
            lm = min((o['v'] for o in self.cars if o['lane'] == lane), default=0)
            if lm < -30:
                break
            self.spawn(lane, -36.0, 5)

    def honk(self, c, dur):
        if c['honk'] <= 0:
            self.stats['horn'] += 1
        c['honk'] = max(c['honk'], dur)

    def callout(self, text, col, now):
        self.callouts.append((text, col, now))

    def events(self, p, now, dt):
        """Scripted DedSec hack beats keyed to the cycle position."""
        f = self.flags

        def once(key, at):
            if p >= at and key not in f:
                f.add(key)
                return True
            return False
        if once('breach', 13):
            self.callout('INTRUSION // ctOS SIGNAL BUS', PINK, now)
        if once('green', 16):
            self.callout('ALL SIGNALS GREEN', GREEN, now)
        if once('steam', 17.2):
            self.callout('STEAM MAIN VENTING', (190, 200, 205), now)
        if once('victim', 17.9):
            # The front-most car still short of the bollard line takes the hit.
            cand = [c for c in self.cars if c['lane'] == (0, 1) and -30 < c['v'] < BOLLARD_V - HALF - .6 and c['kind'] == 'car']
            if not cand:
                cand = [self.spawn((0, 1), -24.0, 9)]
            self.victim = max(cand, key=lambda c: c['v'])
        if once('bollards', 18.0):
            self.callout('BOLLARDS DEPLOYED', YELLOW, now)
        if once('hydrant', 19.6):
            self.callout('HYDRANT BREACHED', CYAN, now)
        if once('police', 20.5):
            pc = self.spawn((0, -1), -37.0, 9, 'police')
            pc['vmax'] = 7.5
            pc['target'] = -21.5
            self.police = pc
            self.callout('SFPD UNIT DISPATCHED', BLUE, now)
        if once('restore', 29):
            self.callout('ctOS RESYNC // ORDER RESTORED', CYAN, now)
        if once('tow', 31.0):
            if self.wreck is not None:
                self.callout('WRECK CLEARED', (200, 200, 210), now)
            self.wreck = None
        if once('leave', 32.2) and self.police is not None:
            self.police['target'] = None
            self.police['vmax'] = 9
        if once('wash', 35):
            self.static = self.clean
            self.skids = []
        # Continuous props.
        bt = 1.0 if 18 <= p < 29.5 else 0.0
        self.bollard_h += (bt - self.bollard_h) * min(1, dt * (5 if bt else 2.5))
        wt = 1.0 if 19.6 <= p < 30 else 0.0
        self.water += (wt - self.water) * min(1, dt * (4 if wt else 1.2))
        stt = 1.0 if 17.2 <= p < 31 else 0.0
        self.steam += (stt - self.steam) * min(1, dt * (3 if stt else 1.0))
        # Victim: launch over the bollards, flip and land on its roof.
        vc = self.victim
        if vc is not None and vc in self.cars and vc.get('flip') is None:
            if self.bollard_h > .5 and vc['v'] + HALF >= BOLLARD_V - .35:
                vc['flip'] = now
                vc['v0'] = vc['v']
                self.stats['wreck'] += 1
                self.callout('COLLISION // VEHICLE FLIPPED', ORANGE, now)
                self.sparks(self.world((0, 1), BOLLARD_V), .5, 40)
        if vc is not None and vc.get('flip') is not None:
            u = (now - vc['flip']) / 1.25
            if u >= 1:
                self.cars = [c for c in self.cars if c is not vc]
                self.wreck = {'col': vc['col'], 't': now}
                self.victim = None
                self.sparks(self.world((0, 1), WRECK_V), .3, 30)
            elif self.rng.random() < .6:
                x, z = self.world((0, 1), vc['v0'] + (WRECK_V - vc['v0']) * u)
                self.sparks((x, z), .3, 4)

    # ------------------------------------------------------------ particles (pixel space)
    def proj_px(self, p):
        q = self.cam.project(p)
        return (q[0], q[1] * 2, q[2]) if q else None

    def sparks(self, xz, y, n):
        q = self.proj_px((xz[0], y, xz[1]))
        if not q:
            return
        r = self.rng
        for _ in range(n):
            a = r.uniform(math.pi * 1.05, math.pi * 1.95)
            sp = r.uniform(8, 30) * self.h / 45
            self.particles.append([q[0], q[1], math.cos(a) * sp * 1.6, math.sin(a) * sp, 0.0, r.uniform(.25, .7),
                                   r.choice(((255, 236, 140), (255, 190, 60), ORANGE, WHITE)), 60.0, 'spark'])

    def emit(self, dt, now):
        r = self.rng
        P = self.particles
        k = self.h / 45
        if self.water > .05:
            q = self.proj_px((self.HYDRANT[0], 1.2, self.HYDRANT[1]))
            if q:
                for _ in range(int(self.water * 70 * dt * 6) + 1):
                    a = -math.pi / 2 + r.uniform(-.16, .16)
                    sp = r.uniform(24, 38) * self.water * k
                    P.append([q[0] + r.uniform(-.6, .6), q[1], math.cos(a) * sp * .9, math.sin(a) * sp, 0.0,
                              r.uniform(1.0, 1.7), r.choice(((180, 225, 245), (120, 190, 230), (230, 245, 255))), 42.0 * k, 'water'])
        if self.steam > .05:
            q = self.proj_px((self.MANHOLE[0], .1, self.MANHOLE[1]))
            if q:
                for _ in range(int(self.steam * 30 * dt * 6) + 1):
                    P.append([q[0] + r.uniform(-1.5, 1.5), q[1], r.uniform(-2, 4) * k, -r.uniform(8, 16) * self.steam * k, 0.0,
                              r.uniform(1.0, 2.2), (150, 160, 168), -2.0, 'steam'])
        if self.wreck is not None and r.random() < dt * 14:
            q = self.proj_px((WRECK_V, 1.0, -2.6))
            if q:
                P.append([q[0] + r.uniform(-2, 2), q[1], r.uniform(-1, 2), -r.uniform(4, 8), 0.0, r.uniform(1.2, 2.4),
                          (88, 92, 98), -1.0, 'steam'])
        if len(P) > 900:
            del P[:len(P) - 900]

    def draw_particles(self, s, dt):
        alive = []
        w, ph = self.w, self.h * 2
        for p in self.particles:
            p[4] += dt
            if p[4] >= p[5]:
                continue
            p[3] += p[7] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            t = p[4] / p[5]
            x, py = int(p[0]), int(p[1])
            if not (0 <= x < w and 4 <= py < ph - 4):
                if p[1] < ph:
                    alive.append(p)
                continue
            kind = p[8]
            if kind == 'steam':
                base = s.get_pixel(x, py) or s.bg[py >> 1][x] or ASPHALT
                c = blend(base, p[6], .55 * (1 - t))
                s.pixel(x, py, c)
                if t < .6:
                    s.pixel(x + 1, py, blend(base, p[6], .35 * (1 - t)))
            elif kind == 'water':
                s.pixel(x, py, blend(p[6], (60, 90, 110), t * .7))
            else:
                c = blend(p[6], (120, 40, 10), t)
                s.pixel(x, py, c)
                if t < .3:
                    s.put(x, py >> 1, '*' if t < .12 else '+', blend(p[6], WHITE, .3))
            alive.append(p)
        self.particles = alive

    # ------------------------------------------------------------ car sprites
    def car_geom(self, x, z, lane, kind, colidx, pitch=0.0, lift=0.0, yc=.55):
        """Visible shaded faces [(pixel pts, col, depth)] of a car pose."""
        axis, d = lane
        fv = (d, 0, 0) if axis == 0 else (0, 0, d)
        sv = (0, 0, 1) if axis == 0 else (1, 0, 0)
        cp, spn = math.cos(pitch), math.sin(pitch)
        if kind == 'police':
            cols = {'body': (226, 228, 236), 'glass': GLASS, 'roof': (32, 34, 44), 'head': HEAD, 'tail': RED, 'tyre': TYRE}
        else:
            col = CAR_COLS[colidx]
            cols = {'body': col, 'glass': GLASS, 'roof': blend(col, WHITE, .2), 'head': HEAD, 'tail': RED, 'tyre': TYRE}
        cam = self.cam
        cpos = cam.pos
        faces = []

        def P(f, y, sd):
            f2 = f * cp - (y - yc) * spn
            y2 = yc + f * spn + (y - yc) * cp + lift
            return (x + fv[0] * f2 + sv[0] * sd, y2, z + fv[2] * f2 + sv[2] * sd)

        def N(nf, ny, ns):
            nf2 = nf * cp - ny * spn
            ny2 = nf * spn + ny * cp
            return (fv[0] * nf2 + sv[0] * ns, ny2, fv[2] * nf2 + sv[2] * ns)
        for f0, f1, s0, s1, y0, y1, part in CAR_BOXES:
            if kind == 'police' and part == 'body':
                pass
            col = cols[part]
            fm, ym, sm = (f0 + f1) / 2, (y0 + y1) / 2, (s0 + s1) / 2
            for n, quad in (((0, 1, 0), ((f0, y1, s0), (f1, y1, s0), (f1, y1, s1), (f0, y1, s1))),
                            ((0, -1, 0), ((f0, y0, s0), (f1, y0, s0), (f1, y0, s1), (f0, y0, s1))),
                            ((1, 0, 0), ((f1, y0, s0), (f1, y1, s0), (f1, y1, s1), (f1, y0, s1))),
                            ((-1, 0, 0), ((f0, y0, s0), (f0, y1, s0), (f0, y1, s1), (f0, y0, s1))),
                            ((0, 0, 1), ((f0, y0, s1), (f1, y0, s1), (f1, y1, s1), (f0, y1, s1))),
                            ((0, 0, -1), ((f0, y0, s0), (f1, y0, s0), (f1, y1, s0), (f0, y1, s0)))):
                nw = N(n[0], n[1], n[2])
                ctr = P(fm + n[0] * (f1 - f0) / 2, ym + n[1] * (y1 - y0) / 2, sm + n[2] * (s1 - s0) / 2)
                if nw[0] * (cpos[0] - ctr[0]) + nw[1] * (cpos[1] - ctr[1]) + nw[2] * (cpos[2] - ctr[2]) <= 0:
                    continue
                pp = [cam.project(P(a, b, c)) for a, b, c in quad]
                if not all(pp):
                    continue
                c = col if part in ('head', 'tail') else _norm_shade(col, nw)
                if kind == 'police' and part == 'body' and abs(n[2]) > .5:
                    c = blend((22, 24, 34), c, .25)      # black-and-white door panels
                faces.append(([(q[0], q[1] * 2) for q in pp], c, sum(q[2] for q in pp) / 4))
        faces.sort(key=lambda f: -f[2])
        return faces

    def raster_faces(self, faces):
        buf = {}
        w, ph = self.w, self.h * 2
        for pts, col, dep in faces:
            _fill(buf, pts, col, dep, w, ph)
        return buf

    def sprite(self, lane, v, kind, colidx):
        b = int(round(v / 1.5))
        key = (lane, b, kind, colidx)
        sp = self.sprites.get(key)
        if sp is None:
            bv = b * 1.5
            x, z = self.world(lane, bv)
            q = self.proj_px((x, .55, z))
            if q is None:
                return None
            buf = self.raster_faces(self.car_geom(x, z, lane, kind, colidx))
            ox, oy = int(round(q[0])), int(round(q[1]))
            sp = ([(px - ox, py - oy, c, dd - q[2]) for (px, py), (c, dd) in buf.items()], q[2])
            if len(self.sprites) > 1500:
                self.sprites.clear()
            self.sprites[key] = sp
        return sp

    def blit(self, s, pix, cx, cy, cdep, tol=.6):
        w, lo, hi = self.w, 4, self.h * 2 - 4
        Z = self.z
        pt, pb = s.pt, s.pb
        for dx, dy, c, dd in pix:
            x, py = cx + dx, cy + dy
            if 0 <= x < w and lo <= py < hi and cdep + dd <= Z[py][x] + tol:
                (pb if py & 1 else pt)[py >> 1][x] = c

    def draw_car(self, s, c, now):
        lane = c['lane']
        x, z = self.world(lane, c['v'])
        q = self.proj_px((x, .55, z))
        if not q:
            return
        if c.get('flip') is not None:
            u = min(1.0, (now - c['flip']) / 1.25)
            v = c['v0'] + (WRECK_V - c['v0']) * (1 - (1 - u) ** 2)
            x, z = self.world(lane, v)
            lift = 2.6 * math.sin(math.pi * min(1, u * 1.05)) + .47 * u
            faces = self.car_geom(x, z, lane, c['kind'], c['col'], pitch=-math.pi * min(1, u * 1.1), lift=lift)
            buf = self.raster_faces(faces)
            self.blit(s, [(px, py, cc, dd) for (px, py), (cc, dd) in buf.items()], 0, 0, 0, 3)
            return
        sp = self.sprite(lane, c['v'], c['kind'], c['col'])
        if not sp:
            return
        pix, ref = sp
        cx, cy = int(round(q[0])), int(round(q[1]))
        # Shadow first, then body.
        self.blit(s, pix, cx, cy, q[2])
        if c['sp'] > 8:
            # Motion streaks behind rushing cars.
            axis, d = lane
            for k, lat in ((1, -.5), (2, .5)):
                xa, za = self.world(lane, c['v'] - HALF - .3)
                xb, zb = self.world(lane, c['v'] - HALF - 1.6 * k)
                if axis == 0:
                    za += lat; zb += lat
                else:
                    xa += lat; xb += lat
                pa, pb2 = self.proj_px((xa, .5, za)), self.proj_px((xb, .5, zb))
                if pa and pb2:
                    s.pixel_line(pa[0], pa[1], pb2[0], pb2[1], blend(CAR_COLS[c['col']], ASPHALT, .55))
        if c['kind'] == 'police':
            on = int(now * 8) % 2
            for k, col in ((-1, RED), (1, BLUE)):
                lit = (k < 0) == bool(on)
                pp = self.proj_px((x + (0 if lane[0] else 0), 1.68, z + .4 * k))
                if pp:
                    cc = col if lit else blend(col, BLACK, .7)
                    s.pixel(int(pp[0]), int(pp[1]), cc)
                    s.pixel(int(pp[0]) + 1, int(pp[1]), cc)
                    s.pixel(int(pp[0]), int(pp[1]) - 1, blend(cc, WHITE, .3) if lit else cc)

    def draw_wreck(self, s, now):
        wk = self.wreck
        x, z = self.world((0, 1), WRECK_V)
        if 'buf' not in wk:
            faces = self.car_geom(x, z, (0, 1), 'car', wk['col'], pitch=-math.pi * .93, lift=.5)
            wk['buf'] = self.raster_faces([(pts, blend(c, (40, 30, 28), .35), d) for pts, c, d in faces])
        self.blit(s, [(px, py, cc, dd) for (px, py), (cc, dd) in wk['buf'].items()], 0, 0, 0, 3)
        q = self.cam.project((x, 1.4, z))
        if q and int(now * 3) % 2 and self.w >= 100:
            s.text(int(q[0]) - 3, int(q[1]) - 2, 'WRECK', ORANGE)

    def draw_police_glow(self, s, now):
        pc = self.police
        if pc is None:
            return
        x, z = self.world(pc['lane'], pc['v'])
        q = self.proj_px((x, 0, z))
        if not q:
            return
        on = int(now * 8) % 2
        cx, cy = q[0], q[1]
        rx, ry = 14 * self.w / 175, 9 * self.h / 45
        for py in range(int(cy - ry), int(cy + ry) + 1):
            if not 4 <= py < self.h * 2 - 4:
                continue
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            dy = (py - cy) / ry
            for x_ in range(max(0, int(cx - rx)), min(self.w, int(cx + rx) + 1)):
                dx = (x_ - cx) / rx
                r2 = dx * dx + dy * dy
                if r2 < 1 and layer[x_] is not None:
                    col = RED if (dx < 0) == bool(on) else BLUE
                    layer[x_] = blend(layer[x_], col, .32 * (1 - r2))

    def draw_puddle(self, s, now):
        if self.water < .05:
            return
        q = self.proj_px((self.HYDRANT[0] - 1.5, 0, self.HYDRANT[1] + 2.5))
        if not q:
            return
        cx, cy = q[0], q[1]
        rx, ry = 13 * self.water * self.w / 175, 6 * self.water * self.h / 45
        for py in range(int(cy - ry), int(cy + ry) + 1):
            if not 4 <= py < self.h * 2 - 4:
                continue
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            dy = (py - cy) / max(1, ry)
            for x in range(max(0, int(cx - rx)), min(self.w, int(cx + rx) + 1)):
                dx = (x - cx) / max(1, rx)
                r2 = dx * dx + dy * dy + .25 * math.sin(x * .9 + py * 1.3)
                if r2 < 1 and layer[x] is not None:
                    shimmer = .12 * math.sin(now * 6 + x * .7 + py)
                    layer[x] = blend(layer[x], (70, 140, 180), .35 + shimmer)

    def draw_bollards(self, s, now):
        hgt = self.bollard_h
        if hgt < .03:
            return
        bx = BOLLARD_V
        warn = PINK if int(now * 4) % 2 else blend(PINK, BLACK, .45)
        self.plane(s, bx - .75, -3.6, .1, 3.4, blend(warn, ASPHALT, .3), .01)
        self.plane(s, bx + .75, -3.6, .1, 3.4, blend(warn, ASPHALT, .3), .01)
        for zz in (-.9, -2.25, -3.6, -4.95, -6.3):
            top = .02 + hgt * 1.6
            self.box(s, bx, zz, .32, .32, top, (232, 192, 42))
            if hgt > .4:
                self.box(s, bx, zz, .34, .34, .22, (34, 34, 38), top * .55)
            p = self.proj_px((bx, top + .05, zz))
            if p and int(now * 6) % 2:
                s.pixel(int(p[0]), int(p[1]) - 1, RED)
                s.pixel(int(p[0]) + 1, int(p[1]) - 1, RED)
        if self.w >= 100 and hgt > .5:
            q = self.cam.project((bx, 1.6, -7.2))
            if q:
                s.text(int(q[0]) - 4, int(q[1]) - 1, 'BOLLARDS', YELLOW)

    def quad_dyn(self, s, x, z, wx, wz, height, col):
        self.box(s, x, z, wx, wz, height, col)

    def draw_peds(self, s, sig, dt, now, chaos):
        cam = self.cam
        Z = self.z
        for pd in self.peds:
            axis_road = 1 if pd['c'][0] == 'z' else 0   # zebra at z=+-8 crosses the axis-1 road
            walk = sig[axis_road] == 'R' and sig[1 - axis_road] in 'GY'
            if pd['state'] == 'wait':
                if walk:
                    pd['delay'] -= dt
                    if pd['delay'] <= 0:
                        pd['state'] = 'cross'
                        pd['panic'] = False
            else:
                spd = pd['speed'] * (2.6 if (chaos or pd['panic']) else 1.0)
                if chaos:
                    pd['panic'] = True
                pd['u'] += pd['dir'] * spd * dt
                if abs(pd['u']) >= 8.4 and pd['u'] * pd['dir'] > 0:
                    pd['u'] = pd['dir'] * 8.4
                    pd['dir'] = -pd['dir']
                    pd['state'] = 'wait'
                    pd['delay'] = 1.0 + self.rng.random() * 4
            u, lat = pd['u'], pd['lat']
            k, c = pd['c']
            x, z = (u, c + lat) if k == 'z' else (c + lat, u)
            base = .34 if abs(u) > 7 else .02
            foot = cam.project((x, base, z))
            head = cam.project((x, base + 1.75, z))
            if not foot or not head:
                continue
            fx, fy, dep = int(foot[0]), int(foot[1] * 2), foot[2]
            hy = int(head[1] * 2)
            if not (0 <= fx < self.w - 1 and 6 <= hy and fy < self.h * 2 - 4):
                continue
            hpx = max(3, fy - hy)
            moving = pd['state'] == 'cross'
            step = int(now * (10 if pd['panic'] else 5) + u) % 2 if moving else 0
            for i in range(hpx + 1):
                py = hy + i
                if dep > Z[py][fx] + .8:
                    continue
                if i == 0:
                    col = (196, 156, 124)
                elif i < hpx - 1 or hpx < 4:
                    col = pd['col']
                else:
                    col = (39, 44, 54)
                s.pixel(fx + (step if i == hpx and moving else 0), py, col)
            if pd['panic'] and moving and int(now * 4) % 3 == 0 and self.w >= 120:
                s.put(fx, (hy >> 1) - 1, '!', YELLOW)

    def draw_signals(self, s, sig, now, p):
        name, prog = self.phase_of(p)
        for i, (x, z) in enumerate([(-8, -7), (8, 7), (-8, 7), (8, -7)]):
            axis = 0 if i % 2 == 0 else 1
            st = sig[axis]
            if st == 'X':
                st = 'RYG'[int(now * 9 + i * 2) % 3]
            for j, col in enumerate((RED, YELLOW, GREEN)):
                active = 'RYG'[j] == st
                q = self.proj_px((x, 4.11 - j * .29, z - .38))
                if not q:
                    continue
                c = col if active else blend(col, BLACK, .82)
                qx, qy = int(q[0]), int(q[1])
                s.pixel(qx, qy, c)
                s.pixel(qx + 1, qy, c if active else blend(col, BLACK, .88))
                if active and name == 'CHAOS' and int(now * 4 + i) % 2:
                    s.pixel(qx - 1, qy, blend(col, BLACK, .4))
                    s.pixel(qx + 2, qy, blend(col, BLACK, .4))

    def bake_skids(self, s):
        if not self.pending_skids:
            return
        s.restore(self.static)
        for lane, v0, v1 in self.pending_skids:
            if v1 - v0 < .02:
                continue
            axis, d = lane
            for lat in (-.62, .62):
                a0, a1 = v0 - 1.33, v1 - 1.33
                xa, za = self.world(lane, (a0 + a1) / 2)
                hl = max(.08, (a1 - a0) / 2 + .06)
                if axis == 0:
                    self.plane(s, xa, za + lat, hl, .09, SKID, .005)
                else:
                    self.plane(s, xa + lat, za, .09, hl, SKID, .005)
        self.pending_skids = []
        self.static = s.snapshot()

    # ------------------------------------------------------------ HUD
    def hud(self, s, now, p, sig):
        w, h = self.w, self.h
        name, prog = self.phase_of(p)
        hacked = name == 'CHAOS'
        small = w < 120 or h < 34
        s.fill(0, 0, w, 2)
        s.text(2, 0, 'ctOS TRAFFIC CONTROL // INTERSECTION 07', CYAN if not hacked else blend(CYAN, PINK, .5))
        if hacked:
            tag = '// HACKED //'
            s.text(2 + 41, 0, tag, PINK if int(now * 3) % 2 else WHITE) if w >= 70 else None
        state = {'NOMINAL': 'SYSTEM NOMINAL', 'BREACH': 'INTRUSION %3d%%' % int(prog * 100),
                 'CHAOS': 'SIGNALS OVERRIDDEN', 'RESTORE': 'RESTORING ORDER'}[name]
        scol = {'NOMINAL': CYAN, 'BREACH': PINK, 'CHAOS': YELLOW, 'RESTORE': GREEN}[name]
        s.text(max(2, w - len(state) - 2), 0, state, scol)
        cam_txt = 'CAM 04  REC %02d:%02d' % (int(now // 60) % 60, int(now) % 60)
        s.text(max(2, w - len(cam_txt) - 2), 1, cam_txt, (110, 124, 132))
        s.text(2, 1, 'DEDSEC OWNS THE RIGHT OF WAY' if hacked else 'WET ASPHALT / NIGHT SHIFT', PINK if hacked else (110, 124, 132))
        # Counters panel.
        st = self.stats
        sigtxt = {'G': 'GRN', 'Y': 'YEL', 'R': 'RED', 'X': '???'}
        lines = [('SIGNALS', 'ALL GREEN' if hacked else 'SCRAMBLED' if name == 'BREACH' else ('EW %s  NS %s' % (sigtxt[sig[0]][0], sigtxt[sig[1]][0]) if small else 'EW %s  NS %s' % (sigtxt[sig[0]], sigtxt[sig[1]])),
                  YELLOW if hacked else PINK if name == 'BREACH' else CYAN),
                 ('NEAR MISS', '%03d' % st['near'], ORANGE if st['near'] else WHITE),
                 ('HORNS', '%03d' % st['horn'], YELLOW if st['horn'] else WHITE),
                 ('WRECKS', '%03d' % st['wreck'], RED if self.wreck else WHITE),
                 ('JAM', '%02d CARS' % st['jam'], RED if st['jam'] > 5 else WHITE),
                 ('SFPD', 'CLEARING' if self.police and self.police['target'] is None else 'ON SCENE' if self.police and self.police['target'] is not None and self.police['sp'] < .5
                  else 'EN ROUTE' if self.police else '--', BLUE if self.police else (110, 124, 132))]
        if small:
            lines = lines[:1] + lines[1:5:2] + lines[4:5]
        pw = 22 if small else 26
        ph = len(lines) + 2
        px, py = 1, 3
        s.box(px, py, pw, ph, blend(PINK, BLACK, .3) if hacked else blend(CYAN, BLACK, .45), 'DEDSEC // CTRL', title_color=PINK)
        for i, (k, v, c) in enumerate(lines):
            s.text(px + 2, py + 1 + i, k, (130, 140, 150))
            s.text(px + pw - 2 - len(v), py + 1 + i, v, c)
        # Hack links from the panel to every signal head during the breach.
        if name == 'BREACH':
            for i, (x, z) in enumerate([(-8, -7), (8, 7), (-8, 7), (8, -7)]):
                q = self.cam.project((x, 4.0, z - .38))
                if not q:
                    continue
                ax, ay, bx, by = px + pw, py + 2, int(q[0]), int(q[1])
                n = max(1, int(math.hypot(bx - ax, (by - ay) * 2)))
                head = (now * 1.6 + i * .25) % 1
                for k in range(0, n, 2):
                    t = k / n
                    if t > prog * 1.4:
                        break
                    xx, yy = int(ax + (bx - ax) * t), int(ay + (by - ay) * t)
                    if 0 <= yy < h and 0 <= xx < w and s.ch[yy][xx] == ' ':
                        s.put(xx, yy, '·', blend(PINK, WHITE, .7) if abs(t - head) < .04 else blend(PINK, BLACK, .3))
        # Phase indicator.
        s.fill(0, h - 2, w, 2)
        x = 2
        order = ('NOMINAL', 'BREACH', 'CHAOS', 'RESTORE')
        for i, nm in enumerate(order):
            on = nm == name
            label = ' %s ' % nm
            col = {'NOMINAL': CYAN, 'BREACH': PINK, 'CHAOS': YELLOW, 'RESTORE': GREEN}[nm]
            s.text(x, h - 2, label, BLACK if on else blend(col, BLACK, .5))
            if on:
                for k in range(len(label)):
                    s.set_bg(x + k, h - 2, col)
            x += len(label)
            if i < 3:
                s.text(x, h - 2, ' > ', (90, 98, 106))
                x += 3
        bar_w = max(8, min(30, w - x - 16))
        if x + bar_w + 4 < w:
            fill = int(prog * bar_w)
            s.text(x + 2, h - 2, '[' + '=' * fill + '-' * (bar_w - fill) + ']', (120, 130, 140))
        cyc = 'HACK CYCLE %02d / %02d' % (int(p), int(CYCLE))
        if w - len(cyc) - 2 > x + bar_w + 6:
            s.text(w - len(cyc) - 2, h - 2, cyc, (110, 124, 132))
        msg = {'NOMINAL': 'ctOS 2.0 // SIGNAL CYCLE NOMINAL // PEDESTRIAN PHASE ACTIVE',
               'BREACH': 'UPLOADING SIGNAL OVERRIDE // HANDSHAKE SPOOFED',
               'CHAOS': 'ALL GREEN. THANK YOU FOR YOUR COOPERATION.',
               'RESTORE': 'ctOS FAILSAFE ENGAGED // TOW AND WATER CREWS NOTIFIED'}[name]
        s.text(2, h - 1, msg[:w - 4], PINK if hacked else CYAN)
        # Event callouts.
        self.callouts = [c for c in self.callouts if now - c[2] < 2.4]
        if self.callouts:
            text, col, t0 = self.callouts[-1]
            if (now - t0) > .2 or int(now * 12) % 2:
                text = text[:w - 6]
                bw = len(text) + 4
                bx = (w - bw) // 2
                by = 3 if not small else 2
                s.box(bx, by, bw, 3, col, double=True)
                s.text(bx + 2, by + 1, text, WHITE)

    def bubbles_draw(self, s, now):
        for c in self.cars:
            if c['honk'] > 0 and c.get('flip') is None and c['kind'] != 'police':
                x, z = self.world(c['lane'], c['v'])
                q = self.cam.project((x, 2.2, z))
                if q:
                    bx, by = int(q[0]) - 1, int(q[1]) - 1
                    if 2 <= by < self.h - 2:
                        txt = 'HONK' if (c['id'] + int(now)) % 5 == 0 and self.w >= 120 else '!!'
                        s.text(bx, by, txt, YELLOW if int(now * 6 + c['id']) % 2 else WHITE)
                        for k in range(len(txt)):
                            s.set_bg(bx + k, by, (60, 40, 20))

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        if self.start is None:
            self.start = now
        if self.last is None:
            self.last = now
        dt = max(0.0, min(.1, now - self.last))
        self.last = now
        t = now - self.start
        if self.static is None:
            self.scenery(s)
        n = int(t // CYCLE)
        if n != self.cycle_n:
            self.cycle_n = n
            if n > 0:
                self.flags = set()
                self.static = self.clean
                self.wreck = None
                self.victim = None
                self.cars = [c for c in self.cars if c['kind'] == 'car' and c.get('flip') is None]
                for c in self.cars:
                    c['target'] = None
                self.police = None
                self.stats = {'near': 0, 'horn': 0, 'wreck': 0, 'jam': 0}
        p = t % CYCLE
        name, _ = self.phase_of(p)
        sig = self.signals(p)
        self.events(p, now, dt)
        self.sim(dt, p, sig)
        self.bake_skids(s)
        s.restore(self.static)
        # Depth-sorted dynamic objects.
        objs = []
        cam = self.cam
        for c in self.cars:
            x, z = self.world(c['lane'], c['v'])
            objs.append((cam.to_view((x, 0, z))[2], 0, c))
        if self.bollard_h > .03:
            objs.append((cam.to_view((BOLLARD_V, 0, -3.5))[2], 1, None))
        if self.wreck is not None:
            objs.append((cam.to_view((WRECK_V, 0, -2.6))[2], 2, None))
        objs.sort(key=lambda o: -o[0])
        self.draw_puddle(s, now)
        self.draw_police_glow(s, now)
        self.draw_peds(s, sig, dt, now, name == 'CHAOS')
        for _, kind, c in objs:
            if kind == 0:
                self.draw_car(s, c, now)
            elif kind == 1:
                self.draw_bollards(s, now)
            else:
                self.draw_wreck(s, now)
        self.draw_signals(s, sig, now, p)
        self.emit(dt, now)
        self.draw_particles(s, dt)
        if self.water > .3:
            q = self.cam.project((self.HYDRANT[0], 0, self.HYDRANT[1]))
            if q and self.w >= 120:
                s.text(int(q[0]) + 3, int(q[1]), 'H2O MAIN', CYAN)
        if self.police is not None and self.w >= 100:
            x, z = self.world(self.police['lane'], self.police['v'])
            q = self.cam.project((x, 2.4, z))
            if q:
                s.text(int(q[0]) - 3, int(q[1]) - 1, 'SFPD-07', RED if int(now * 8) % 2 else BLUE)
        self.bubbles_draw(s, now)
        drift = round(math.sin(t * .16) * 1.2)
        if name == 'BREACH' and self.rng.random() < .15:
            y0 = self.rng.randrange(3, self.h - 3)
            for y in range(y0, min(self.h - 2, y0 + 2)):
                s.shift_row(y, self.rng.choice((-3, -2, 2, 3)))
                s.tint_row(y, PINK, .25)
        if drift:
            for row in range(2, self.h - 2):
                s.shift_row(row, drift)
        self.hud(s, now, p, sig)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, 'pullback', 'ALL SIGNALS OFFLINE', RED)
        if t < .65:
            for x, z in [(-8, -7), (8, 7), (-8, 7), (8, -7)]:
                q = self.cam.project((x, 4, z))
                if q:
                    s.put(int(q[0]), int(q[1]), 'x', blend(RED, BLACK, t))

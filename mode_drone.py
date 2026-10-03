"""DRONE: FPV flight above a San Francisco avenue at dusk.

The scene is ray-cast with NumPy into an RGB pixel buffer (two pixels per
text cell).  Everything is opaque and depth-tested against one z-buffer, so
geometry can never interpenetrate: facade planes, roofs, set-back tiers, the
street, a gradient sky with clouds, a distant skyline and the bay bridge.
Sprites (cars, lamps, pedestrians, police drone) and lighting are added after.
"""

import math
import random
import time

import numpy as np

from lib import BLACK, CYAN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW, Glitch, blend
from sysdata import DATA

NAME = "DRONE"

CALLOUTS = ["TARGET ACQUIRED", "ctOS TOWER IN RANGE", "SIGNAL HIJACKED", "UPLOADING FOOTAGE",
            "THERMAL SCAN", "AUTOPILOT OVERRIDE", "NUDLE MAPS SPOOFED"]

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
SKULL_NP = np.array([[c == "X" for c in row] for row in SKULL])

RED = (255, 30, 40)
BLUE = (40, 90, 255)
f32 = np.float32

# ---------------------------------------------------------------- world layout
PER = 88.0            # length of one block + cross street along z
GAP = 14.0            # cross street width
WF = 16.0             # facade planes at x = +-WF (avenue is 32 m wide)
D0 = 18.0             # frontage depth
ALLEY = 6.0
D1 = 26.0
X1 = WF + D0 + ALLEY  # second row facade
ROAD = 10.2           # asphalt half width
TMAX = 340.0
TUN_H = 7.2
TUN_W = 8.5
MASS_H = 20.0
BOARD_W, BOARD_H, BOARD_Y0 = 24.0, 13.5, 8.75

PALETTE = np.array([(150, 140, 128), (104, 112, 128), (128, 82, 70), (168, 154, 128), (58, 78, 100),
                    (92, 88, 102), (124, 130, 130), (176, 166, 148)], f32)
# Office light: warm amber and warm white, one cool fluorescent in eight.
LIT = np.array([(255, 205, 130), (255, 226, 176), (255, 205, 130), (190, 220, 245), (255, 192, 118),
                (255, 226, 176), (255, 214, 150), (255, 198, 128)], f32)
LIT_T = np.ascontiguousarray(LIT.T)
SIGNS = ["NUDLE", "TIDIS", "RAMEN", "HOTEL", "SUSHI", "BAR", "24H", "CAFE", "BLUME", "OPEN"]
NEONS = [(255, 15, 123), (0, 229, 255), (245, 230, 10), (255, 90, 60), (170, 90, 255), (57, 255, 20)]
NEON_T = np.ascontiguousarray(np.array([(255, 15, 123), (0, 229, 255), (245, 230, 10), (255, 90, 60), (170, 90, 255), (57, 255, 20)], f32).T)
NEON_ARR = NEON_T.T
CAR_COLS = [(60, 60, 72), (110, 30, 40), (200, 200, 205), (30, 50, 90), (40, 40, 44), (150, 130, 40)]

_KEYS = [  # daylight keyframes
    (0.0, dict(top=(5, 7, 24), mid=(30, 16, 62), hor=(150, 54, 104), fog=(52, 30, 66), amb=(0.34, 0.33, 0.48),
               sun=(0, 0, 0), sunb=0.0, glass=(26, 38, 62), cloud=(120, 60, 110), ground=(30, 30, 40))),
    (0.30, dict(top=(24, 26, 78), mid=(118, 58, 118), hor=(255, 128, 88), fog=(140, 82, 108), amb=(0.50, 0.46, 0.62),
                sun=(255, 150, 90), sunb=0.55, glass=(46, 60, 96), cloud=(255, 140, 110), ground=(46, 42, 54))),
    (0.70, dict(top=(58, 108, 190), mid=(120, 168, 225), hor=(238, 196, 176), fog=(150, 150, 172),
                amb=(0.74, 0.76, 0.86), sun=(255, 224, 180), sunb=0.85, glass=(56, 74, 100), cloud=(255, 240, 230),
                ground=(70, 70, 78))),
    (1.0, dict(top=(48, 118, 212), mid=(112, 172, 236), hor=(204, 226, 246), fog=(146, 164, 190),
               amb=(0.84, 0.88, 0.96), sun=(255, 244, 220), sunb=0.95, glass=(60, 82, 112), cloud=(255, 255, 255),
               ground=(80, 82, 90))),
]


def theme_at(d):
    for (d0, a), (d1, b) in zip(_KEYS, _KEYS[1:]):
        if d <= d1:
            t = (d - d0) / (d1 - d0)
            break
    else:
        a = b = _KEYS[-1][1]
        t = 0.0
    th = {}
    for k, v in a.items():
        if isinstance(v, tuple):
            th[k] = np.array([x + (y - x) * t for x, y in zip(v, b[k])], f32)
        else:
            th[k] = v + (b[k] - v) * t
    th["day"] = d
    return th


def hash32(a, b, seed):
    """Cheap integer hash on float cell indices -> int array in [0, 65535]."""
    h = (a.astype(np.int32) * 73856093) ^ (b.astype(np.int32) * 19349663) ^ seed
    h = h ^ (h >> 13)
    h = h * 1274126177
    return (h ^ (h >> 16)) & 0xFFFF


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- city generation
_PERIODS = {}


def is_tunnel(p):
    return p % 6 == 2


def has_board(p):
    return p % 4 == 1


def tunnel_range(p):
    return p * PER + 18.0, p * PER + PER - GAP


def board_z(p):
    return p * PER + 34.0


def gen_period(p):
    """Buildings of period p: dict (side,row) -> entries, plus signs / kit / roofs."""
    if p in _PERIODS:
        return _PERIODS[p]
    out = {"ent": {(s, r): [] for s in (-1, 1) for r in (0, 1)}, "signs": [], "kit": [], "ant": []}
    z_base = p * PER
    for side in (-1, 1):
        for row in (0, 1):
            rng = random.Random(p * 9973 + side * 131 + row * 17 + 5)
            ents = out["ent"][(side, row)]
            z = z_base
            end = z_base + PER - GAP
            tun = is_tunnel(p) and row == 0
            while z < end - 0.5:
                if tun and abs(z - (z_base + 18.0)) < 0.01:
                    width = end - z
                    h, tier = MASS_H, None
                    style = 4
                else:
                    width = rng.uniform(11, 26)
                    if tun and z + width > z_base + 18.0 - 3:
                        width = z_base + 18.0 - z
                        if width < 4:
                            width = z_base + 18.0 - z
                    if end - (z + width) < 9:
                        width = end - z
                    if row == 0:
                        pick = rng.random()
                        h = rng.uniform(11, 21) if pick < 0.28 else rng.uniform(22, 42) if pick < 0.76 else rng.uniform(46, 76)
                    else:
                        h = rng.uniform(44, 120)
                    tier = None
                    if h > 28 and rng.random() < 0.45:
                        tier = (rng.uniform(0.5, 0.68), rng.uniform(3.0, 5.0))
                    style = rng.choices((0, 1, 2, 3), (6, 2, 2, 2))[0]
                z1 = min(end, z + width)
                col = rng.randrange(len(PALETTE))
                fw = rng.uniform(1.9, 2.8)
                fh = rng.choice((3.0, 3.2, 3.4, 3.6, 4.0))
                wa, vlo, vhi = 0.28 + rng.random() * 0.08, 0.28, 0.74
                if style == 1:
                    wa, vlo, vhi = 0.0, 0.3, 0.7
                elif style == 2:
                    wa, vlo, vhi = 0.04, 0.1, 0.96
                    col = 4
                elif style == 3:
                    wa, fw = 0.34, 1.7
                elif style == 4:
                    wa, col = 1.0, 1
                hfull = h
                h_lo = h
                if tier:
                    h_lo = h * tier[0]
                seed = rng.randrange(1, 900000)
                litp = rng.uniform(0.18, 0.55)
                ents.append((z, z1, h_lo, col, fw, fh, wa, vlo, vhi, litp, seed, style, hfull, tier))
                if row == 0 and style != 4:
                    kit_n = rng.choice((0, 1, 1, 2))
                    for _ in range(kit_n):
                        kx = rng.uniform(1.0, D0 - 5.0)
                        kz = rng.uniform(z + 1.0, max(z + 1.1, z1 - 4.0))
                        kind = rng.choice(("tank", "ac", "ac", "shed"))
                        out["kit"].append((side, kx, kz, hfull, kind, rng.randrange(1000)))
                    if rng.random() < 0.7:
                        out["ant"].append((side, rng.uniform(2, D0 - 2), rng.uniform(z + 1, z1 - 1), hfull,
                                           rng.uniform(4, 11)))
                    if h > 12 and rng.random() < 0.5 and z1 - z > 8:
                        sw = rng.uniform(4.0, 6.5)
                        zc = rng.uniform(z + sw / 2 + 0.5, z1 - sw / 2 - 0.5)
                        sh = rng.uniform(1.4, 2.0)
                        vc = rng.uniform(6.0, min(11.0, h_lo - 2))
                        out["signs"].append((side, zc - sw / 2, zc + sw / 2, vc - sh / 2, vc + sh / 2,
                                             NEONS[rng.randrange(len(NEONS))], rng.choice(SIGNS)))
                z = z1
            ents.append((end, z_base + PER, 0.0, 0, 2.0, 3.0, 1.0, 0.2, 0.8, 0.0, 1, 0, 0.0, None))
    _PERIODS[p] = out
    if len(_PERIODS) > 40:
        for k in sorted(_PERIODS)[:-30]:
            del _PERIODS[k]
    return out


# ---------------------------------------------------------------- skyline lookup (azimuth -> elevation)
def _make_skyline(n=1024):
    rng = random.Random(77)
    lim = np.zeros(n, f32)
    i = 0
    while i < n:
        w = rng.randint(3, 9)
        az = (i + w / 2) / n * math.tau - math.pi
        hgt = 0.006 + rng.random() * 0.026
        if rng.random() < 0.12:
            hgt += rng.random() * 0.04
        side = abs(az)
        hgt *= smooth(0.17, 0.42, side) * 1.0 + 0.0
        lim[i:i + w] = hgt
        i += w
    return lim


SKY_LIM = _make_skyline()


class WallTex:
    """Deferred facade texture; faces using it are shaded together in one batch."""
    __slots__ = ("swap", "base", "light", "hh", "fw", "fh", "wa", "vlo", "vhi", "litp", "seed", "shops")

    def __init__(self, swap, base, light, hh, p, seed, shops):
        self.swap, self.base, self.light, self.hh = swap, base, light, hh
        self.fw, self.fh, self.wa, self.vlo, self.vhi, self.litp = p["fw"], p["fh"], p["wa"], p["vlo"], p["vhi"], p["litp"]
        self.seed, self.shops = seed, shops


class _ColorLut(dict):
    def __missing__(self, k):
        if len(self) > 120000:
            self.clear()
        v = self[k] = ((k >> 16) & 255, (k >> 8) & 255, k & 255)
        return v


# ====================================================================== mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = h * 2
        self.F = float(self.ph) * 1.0
        self.cxp, self.cyp = w / 2.0, self.ph / 2.0
        self.xs = ((np.arange(w) + 0.5 - self.cxp) / self.F).astype(f32)
        self.ys = ((self.cyp - (np.arange(self.ph) + 0.5)) / self.F).astype(f32)
        self.col = np.zeros((3, self.ph, w), f32)       # planar RGB
        self.colf = self.col.reshape(3, -1)
        self.shown = None
        self.zb = np.full((self.ph, w), 1e9, f32)
        self.zbf = self.zb.reshape(-1)
        self.dx = np.zeros((self.ph, w), f32)
        self.dy = np.zeros((self.ph, w), f32)
        self.dz = np.zeros((self.ph, w), f32)
        self.dxf, self.dyf, self.dzf = self.dx.reshape(-1), self.dy.reshape(-1), self.dz.reshape(-1)
        self.glitch = Glitch(0.006)
        self.parts = []
        self.fxcache = {}
        self.last = time.time()
        self.t0 = self.last
        self.pos = np.array([0.0, 17.0, 0.0])
        self.yaw = self.pitch = self.roll = 0.0
        self.speed = 15.0
        self.alt = 17.0
        self.dist = 0.0
        self.battery = random.uniform(70, 99)
        self.zoom_t = None
        self.zoom_hit = False
        self.zoom_z0 = 0.0
        self.bz = None
        self.next_zoom = self.last + 3.2
        self.flash = None
        self.callout = (random.choice(CALLOUTS), self.last)
        self.police = None
        self.next_police = self.last + random.uniform(16, 20)
        self.rain = False
        self.weather_check = 0.0
        self.th = theme_at(DATA.daylight())
        self.theme_t = 0.0
        self.strip_p = None
        self.rng = random.Random(5)
        rr = random.Random(11)
        self.cars = [(rr.choice((-1, 1)), rr.uniform(0, 400), rr.uniform(8, 14), rr.randrange(len(CAR_COLS)), rr.random())
                     for _ in range(26)]
        self.peds = [(rr.choice((-1, 1)), rr.uniform(0, 300), rr.uniform(0.9, 1.6) * rr.choice((-1, 1)), rr.uniform(11.2, 14.8),
                      rr.randrange(5)) for _ in range(14)]
        self.stars = np.array([(rr.uniform(-1, 1), rr.uniform(0.05, 1), rr.uniform(-1, 1), rr.random())
                               for _ in range(90)], f32)
        self.stars /= np.linalg.norm(self.stars[:, :3], axis=1, keepdims=True).astype(f32) + 1e-6
        self.drops = np.array([[rr.uniform(0, w), rr.uniform(0, self.ph), rr.uniform(0.8, 1.6)]
                               for _ in range(int(w * 0.9))], f32)
        self.sign_proj = []
        self.wq = []
        self.car_arr = tuple(np.array(c, float) for c in zip(*self.cars))
        self.tk = np.arange(512, dtype=f32)
        self.lut = _ColorLut()
        self.prev_img = None
        self.board_proj = None

    # ------------------------------------------------------------ environment
    def update_theme(self, now):
        if now > self.theme_t:
            self.theme_t = now + 2
            wx = DATA.weather
            if wx is not None and now > self.weather_check:
                self.rain = bool(wx.get("rain"))
                self.weather_check = now + 60
            th = theme_at(DATA.daylight())
            if wx and (wx.get("clouds") or wx.get("rain")):
                for k in ("top", "mid", "hor", "fog"):
                    g = float(th[k].mean())
                    th[k] = th[k] * 0.45 + np.array([g, g, g + 6], f32) * 0.55
            if self.rain:
                th["ground"] = th["ground"] * 0.6
            th["fogk"] = 0.55 if wx and wx.get("fog") else 1.0
            self.th = th
            d = th["day"]
            # sun direction (warm, low, ahead-right); moon at night
            self.body_dir = np.array([0.30, 0.10 + 0.25 * d, 1.0], f32)
            self.body_dir /= np.linalg.norm(self.body_dir)
            sd = self.body_dir if d > 0.06 else np.array([-0.35, 0.45, 0.8], f32) / 0.98
            self.sun_vec = sd
            self.lights = {}

    def light(self, n):
        """Light colour (3,) for a face normal tuple."""
        got = self.lights.get(n)
        if got is None:
            th = self.th
            dif = max(0.0, float(np.dot(n, self.sun_vec))) if th["day"] > 0.06 else 0.0
            col = th["amb"] + th["sun"] / 255.0 * (th["sunb"] * dif)
            if n[1] > 0.5:
                col = col * 1.1 + 0.03
            night = max(0.0, 1.0 - th["day"] * 4)
            if n[0] > 0.5:
                col = col + np.array([0.0, 0.09, 0.11], f32) * night
            elif n[0] < -0.5:
                col = col + np.array([0.13, 0.0, 0.06], f32) * night
            got = self.lights[n] = col.astype(f32)
        return got

    # ------------------------------------------------------------ camera
    def set_camera(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        f = np.array([sy * cp, -sp, cy * cp])
        r = np.array([cy, 0.0, -sy])
        u = np.cross(f, r)
        # roll: rotate right/up around the forward axis
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        r2 = r * cr + u * sr
        u2 = u * cr - r * sr
        self.fv, self.rv, self.uv = f, r2, u2
        self.cp = (float(self.pos[0]), float(self.pos[1]), float(self.pos[2]))
        self.dx[:] = (self.ys * u2[0])[:, None] + (f[0] + self.xs * r2[0])[None, :]
        self.dy[:] = (self.ys * u2[1])[:, None] + (f[1] + self.xs * r2[1])[None, :]
        self.dz[:] = (self.ys * u2[2])[:, None] + (f[2] + self.xs * r2[2])[None, :]
        with np.errstate(all='ignore'):
            self.rdx = (1.0 / self.dx).astype(f32)
        self.invn = (1.0 / np.sqrt(self.dx * self.dx + self.dy * self.dy + self.dz * self.dz)).astype(f32)
        self.horizon_y = self.cyp - math.tan(self.pitch) * self.F

    def proj(self, p):
        """World point -> (px, py in pixel rows, depth) ."""
        d = np.asarray(p, float) - self.pos
        vz = d @ self.fv
        if vz < 0.2:
            return None
        return (self.cxp + (d @ self.rv) / vz * self.F, self.cyp - (d @ self.uv) / vz * self.F, vz)

    def proj_many(self, P):
        d = P - self.pos
        vz = d @ self.fv
        vzs = np.maximum(vz, 0.2)
        return self.cxp + (d @ self.rv) / vzs * self.F, self.cyp - (d @ self.uv) / vzs * self.F, vz

    # ------------------------------------------------------------ sky
    def draw_sky(self, now):
        """Sky, clouds, sun/moon, stars, skyline and bay bridge on the pixels no geometry covered."""
        th = self.th
        sp = np.flatnonzero(self.zbf > 1e8)
        if sp.size == 0:
            return
        dxs, dys, dzs = self.dxf.take(sp), self.dyf.take(sp), self.dzf.take(sp)
        inv = self.invn.reshape(-1).take(sp)
        hor, mid, top = th["hor"][:, None], th["mid"][:, None], th["top"][:, None]
        el = dys * inv
        k = np.minimum(np.maximum(el * 1.9 + 0.03, 0), 1)
        k1 = np.minimum(k * 2.6, 1.0)[None, :]
        k2 = np.minimum(np.maximum((k - 0.15) * 1.25, 0), 1)[None, :]
        c = hor + (mid - hor) * k1
        c = c + (top - c) * k2
        d = th["day"]
        # clouds: two sine layers projected on a plane above the viewer
        up = el > 0.02
        if up.any():
            dyv = dys + 0.1
            cu = dxs / dyv
            cv = dzs / dyv
            tt = now * 0.03
            p = (0.5 + 0.25 * np.sin(cu * 1.7 + 0.9 * np.sin(cv * 1.3 + 2.0) + tt)
                 + 0.25 * np.sin(cv * 2.1 - cu * 0.6 + 0.8 * np.sin(cu * 0.9 + tt * 0.7)))
            a = smooth(0.50, 0.82, p) * np.minimum(np.maximum(dys * 7, 0), 1) * 0.62 * up
            shade = (th["cloud"] * 0.9 + 0.1 * th["top"])[:, None]
            c = c + (shade - c) * a[None, :]
        # sun / moon
        bd = self.body_dir if d > 0.06 else self.sun_vec
        dotv = (dxs * bd[0] + dys * bd[1] + dzs * bd[2]) * inv
        ang = np.flatnonzero(dotv > 0.9)
        if ang.size:
            dv = dotv.take(ang)
            if d > 0.06:
                r_in = 0.045 + 0.02 * (1 - d)
                glow = np.exp(-(1 - dv) * 38) * 0.75
                c[:, ang] += th["sun"][:, None] * (glow * 0.6)[None, :]
                disc = dv > math.cos(r_in)
                c[:, ang[disc]] = (th["sun"] * 0.3 + np.array([255, 235, 190], f32) * 0.8)[:, None]
            else:
                glow = np.exp(-(1 - dv) * 120) * 0.5
                c[:, ang] += np.array([60, 70, 120], f32)[:, None] * glow[None, :]
                disc = dv > math.cos(0.05)
                c[:, ang[disc]] = np.array([232, 232, 214], f32)[:, None]
                crater = disc & (dv < math.cos(0.032)) & ((ang % 3) == 0)
                c[:, ang[crater]] = np.array([200, 200, 190], f32)[:, None]
        # skyline, haze and the bay bridge near the horizon
        bi = np.flatnonzero((el < 0.16) & (el > -0.2))
        if bi.size:
            dxb, dzb, dyb = dxs.take(bi), dzs.take(bi), dys.take(bi)
            hyp = np.sqrt(dxb * dxb + dzb * dzb) + 1e-6
            elb = dyb / hyp
            az = np.arctan2(dxb, dzb)
            lim = SKY_LIM[((az + math.pi) * (1024 / math.tau)).astype(np.int32) % 1024]
            fogc = th["fog"]
            water = elb < 0
            c0 = c[:, bi].T.copy()
            wcol = hor.T * 0.8 + np.array([-10, 0, 14], f32) + (2.4 * np.sin(az * 90.0 + now))[:, None]
            c0 = np.where(water[:, None], wcol, c0)
            sil = (elb < lim) & (elb >= -0.02)
            silc = fogc * 0.55 + np.array([10, 8, 24], f32) * 0.5
            lit = ((hash32(np.floor(az * 260), np.floor(elb * 400), 7) & 15) == 0) & (d < 0.4)
            silc2 = np.where(lit[:, None], np.array([255, 205, 140], f32) * 0.7, silc)
            c0 = np.where(sil[:, None], silc2, c0)
            F = self.F
            ay = np.abs(az)
            tower = ((np.abs(ay - 0.10) < 1.1 / F) & (elb < 0.052) & (elb > 0.004))
            deck = (ay < 0.21) & (np.abs(elb - 0.010) < 0.8 / F)
            ecab = 0.010 + 0.040 * np.minimum(1.0, (ay / 0.10)) ** 2
            ecab = np.where(ay > 0.10, 0.052 - (ay - 0.10) / 0.11 * 0.042, ecab)
            cab = (ay < 0.21) & (np.abs(elb - ecab) < 0.7 / F) & (elb > 0.008)
            br = tower | deck | cab
            bcol = fogc * 0.30 + np.array([12, 10, 26], f32)
            bl = deck & ((np.floor(az * 600).astype(np.int32) % 3) == 0)
            bc2 = np.where(bl[:, None], np.array([255, 190, 120], f32) * 0.8, bcol)
            c0 = np.where(br[:, None], bc2, c0)
            tl = tower & (elb > 0.047) & (int(now * 1.2) % 2 == 0)
            c0 = np.where(tl[:, None], np.array([255, 40, 40], f32), c0)
            c[:, bi] = c0.T
        self.put(sp, c)
        # stars (only where the sky shows through)
        if d < 0.3:
            st = self.stars
            pts = st[:, :3]
            vz = pts @ self.fv
            ok = vz > 0.05
            px = self.cxp + (pts @ self.rv) / np.maximum(vz, 0.05) * self.F
            py = self.cyp - (pts @ self.uv) / np.maximum(vz, 0.05) * self.F
            tw = 0.55 + 0.45 * np.sin(now * (1.5 + st[:, 3] * 3) + st[:, 3] * 40)
            for i in np.flatnonzero(ok):
                x, y = int(px[i]), int(py[i])
                if 0 <= x < self.w and 0 <= y < self.ph and self.zb[y, x] > 1e8:
                    v = 200 * tw[i] * (1 - d * 3)
                    base = self.col[:, y, x]
                    if base.mean() < 120:
                        self.col[:, y, x] = base + v * np.array([0.9, 0.9, 1.0], f32)

    # ------------------------------------------------------------ strips
    def build_strips(self, z):
        p0 = int(math.floor(z / PER))
        if p0 == self.strip_p:
            return
        self.strip_p = p0
        self.strips = {}
        self.signs, self.kits, self.ants, self.boxes_static = [], [], [], []
        self.tunnel = None
        self.board_list = []
        for p in range(p0 - 1, p0 + 5):
            g = gen_period(p)
            for key, ents in g["ent"].items():
                self.strips.setdefault(key, []).extend(ents)
            self.signs += [(p,) + s for s in g["signs"]]
            self.kits += g["kit"]
            self.ants += g["ant"]
            if is_tunnel(p):
                tz0, tz1 = tunnel_range(p)
                if self.tunnel is None or tz1 > z - 5 and tz0 < self.tunnel[0] + 1e9 and self.tunnel[1] < z - 5:
                    self.tunnel = (tz0, tz1)
            if has_board(p):
                self.board_list.append(board_z(p))
        # keep a tunnel list for altitude planning
        self.tunnels = [tunnel_range(p) for p in range(p0 - 1, p0 + 5) if is_tunnel(p)]
        self.arr = {}
        self.ents = {}
        zo = (p0 - 1) * PER
        self.zo = zo
        for key, ents in self.strips.items():
            ents.sort(key=lambda e: e[0])
            self.ents[key] = ents
            tbl = np.zeros(int(6 * PER * 4) + 8, np.int16)
            for i, e in enumerate(ents):
                tbl[max(0, int((e[0] - zo) * 4)):max(0, int((e[1] - zo) * 4))] = i
            col = lambda k: np.array([e[k] for e in ents], f32)
            soa = dict(h=col(2), base=np.ascontiguousarray(PALETTE[[e[3] for e in ents]].astype(f32).T), fw=col(4), fh=col(5), wa=col(6),
                       vlo=col(7), vhi=col(8), litp=col(9), seed=np.array([e[10] for e in ents], np.int32))
            self.arr[key] = (tbl, soa)

    # ------------------------------------------------------------ textures
    def wall_tex(self, u, v, t, hh, base, fw, fh, wa, vlo, vhi, litp, seed, light, shops=True):
        """Planar colour (3, n) for a facade; base is (3, n) or (3, 1), light (3,)."""
        th = self.th
        F = self.F
        day = th["day"]
        if light.ndim == 1:
            light = light[:, None]
        a = u / fw
        ix = np.floor(a)
        fu = a - ix
        b = v / fh
        iy = np.floor(b)
        fv = b - iy
        hs = hash32(ix, iy, seed)
        r1 = (hs & 255).astype(f32) * f32(1 / 255.0)
        pitch = (fw * F) / np.maximum(t, 1.0)
        inwin = (fu > wa) & (fu < 1 - wa) & (fv > vlo) & (fv < vhi)
        if pitch.max() > 28.0:
            nr = pitch > 28.0
            pane = fu * 2.0
            pane = pane - np.floor(pane)
            inwin &= ~(nr & (np.abs(pane - 0.5) > 0.465))
            inwin &= ~(nr & (np.abs(fv - 0.5 * (vlo + vhi)) > 0.5 * (vhi - vlo) - 0.03))
        litprob = litp * (1.0 - day * 0.85)
        lm = (r1 < litprob).astype(f32)
        q = np.minimum(r1 / np.maximum(litprob, 1e-3), 1.0)
        bright = 0.6 + 0.55 * q
        ridx = ((hs >> 8).astype(f32) * f32(7.999 / 255.0)).astype(np.int32)
        wl = np.take(LIT_T, ridx, axis=1)
        # dark reflective glass: a soft vertical sky reflection, darker at the bottom of each pane
        gl = (th["glass"][:, None] * light) * (0.55 + 0.6 * fv)[None, :]
        win = gl + (wl * bright[None, :] - gl) * lm[None, :]
        wall = (base * light) * (1.0 - 0.2 * (fv < 0.07).astype(f32))[None, :]
        aa = np.minimum(np.maximum((pitch - 1.6) * f32(1 / 2.2), 0), 1)
        m = (inwin.astype(f32) - f32(0.28)) * aa
        col = wall * 0.72 + win * 0.28 + (win - wall) * m[None, :]
        top = hh - v
        fac = 1.0 + 0.2 * (top < 1.1).astype(f32) - 0.18 * ((top >= 1.1) & (top < 1.7)).astype(f32)
        col = col * fac[None, :]
        if shops is not False:
            sh = np.flatnonzero((v < 4.6) & shops)
            if sh.size:
                us, vs = u.take(sh), v.take(sh)
                sd = seed.take(sh) if isinstance(seed, np.ndarray) else seed
                si = np.floor(us * f32(1 / 5.2))
                sf = us * f32(1 / 5.2) - si
                sr = hash32(si, si * 0 + 3, sd) & 255
                sw = ((sf > 0.07) & (sf < 0.93) & (vs > 0.45) & (vs < 3.3)).astype(f32)
                awn = ((vs >= 3.3) & (vs < 4.1)).astype(f32)
                nl = max(0.18, 1.0 - day * 0.8)
                bi = np.take(np.array([0, 1, 3], np.int64), np.remainder(sr, 3))  # pink, cyan, orange awnings
                srf = sr.astype(f32)
                shopc = np.take(LIT_T, bi, axis=1) * ((0.5 + srf * f32(0.5 / 255.0)) * nl)[None, :] \
                    + gl.take(sh, axis=1) * (day * 0.8)
                awc = np.take(NEON_T, bi, axis=1) * (0.45 + 0.4 * (1 - day))
                wsub = col.take(sh, axis=1) * 0.8
                sc = wsub + (shopc - wsub) * sw[None, :]
                sc = sc + (awc - sc) * awn[None, :]
                col[:, sh] = sc
        return col

    # ------------------------------------------------------------ primitives
    def hit_face(self, axis, val, ra, rb, bbox, texfn, hole=None):
        """Axis-aligned rectangle (axis plane at val; ra,rb ranges of the other two coords)."""
        y0, y1, x0, x1 = bbox
        if y1 <= y0 or x1 <= x0:
            return 0
        dsl = (self.dx, self.dy, self.dz)
        da = dsl[axis][y0:y1, x0:x1]
        t = (val - self.cp[axis]) / da
        zbv = self.zb[y0:y1, x0:x1]
        ok = (t > 0.4) & (t < zbv) & (t < TMAX)
        if not ok.any():
            return 0
        ia, ib = (1, 2) if axis == 0 else (0, 2) if axis == 1 else (0, 1)
        a = self.cp[ia] + t * dsl[ia][y0:y1, x0:x1]
        b = self.cp[ib] + t * dsl[ib][y0:y1, x0:x1]
        ok &= (a >= ra[0]) & (a <= ra[1]) & (b >= rb[0]) & (b <= rb[1])
        if hole is not None:
            ok &= ~((a > hole[0]) & (a < hole[1]) & (b > hole[2]) & (b < hole[3]))
        if not ok.any():
            return 0
        tv, av, bv = t[ok], a[ok], b[ok]
        zbv[ok] = tv
        if isinstance(texfn, WallTex):
            ys, xs = np.nonzero(ok)
            self.wq.append(((ys + y0) * self.w + (xs + x0), tv, av, bv, texfn))
            return tv.size
        c = texfn(av, bv, tv)
        for k in range(3):
            self.col[k, y0:y1, x0:x1][ok] = c[k]
        return tv.size

    def flush_walls(self):
        q = self.wq
        if not q:
            return
        self.wq = []
        fidx = np.concatenate([e[0] for e in q])
        t = np.concatenate([e[1] for e in q])
        keep = np.flatnonzero(self.zbf.take(fidx) == t)
        if keep.size == 0:
            return
        a = np.concatenate([e[2] for e in q])
        b = np.concatenate([e[3] for e in q])
        cnt = [e[0].size for e in q]
        T = [e[4] for e in q]

        def rep(vals, dt=f32):
            return np.repeat(np.array(vals, dt), cnt).take(keep)

        sw = rep([x.swap for x in T], bool)
        a, b, t, fidx = a.take(keep), b.take(keep), t.take(keep), fidx.take(keep)
        u = np.where(sw, b, a)
        v = np.where(sw, a, b)
        base = np.repeat(np.stack([x.base for x in T], 1), cnt, axis=1).take(keep, axis=1)
        light = np.repeat(np.stack([x.light for x in T], 1), cnt, axis=1).take(keep, axis=1)
        col = self.wall_tex(u, v, t, rep([x.hh for x in T]), base, rep([x.fw for x in T]), rep([x.fh for x in T]),
                            rep([x.wa for x in T]), rep([x.vlo for x in T]), rep([x.vhi for x in T]),
                            rep([x.litp for x in T]), rep([x.seed for x in T], np.int32), light,
                            shops=rep([x.shops for x in T], bool))
        self.put(fidx, col)

    def box_bbox(self, B):
        """Screen bboxes (n,4) = y0,y1,x0,x1 for boxes x0,x1,y0,y1,z0,z1."""
        n = len(B)
        xs = np.stack([B[:, 0], B[:, 1]], 1)
        ys = np.stack([B[:, 2], B[:, 3]], 1)
        zs = np.stack([B[:, 4], B[:, 5]], 1)
        pts = np.empty((n, 8, 3))
        k = 0
        for i in range(2):
            for j in range(2):
                for m in range(2):
                    pts[:, k, 0] = xs[:, i]
                    pts[:, k, 1] = ys[:, j]
                    pts[:, k, 2] = zs[:, m]
                    k += 1
        px, py, vz = self.proj_many(pts.reshape(-1, 3))
        px, py, vz = px.reshape(n, 8), py.reshape(n, 8), vz.reshape(n, 8)
        near = (vz < 0.3).any(1)
        far = (vz < 0.3).all(1)
        x0 = np.floor(px.min(1)).clip(0, self.w).astype(int)
        x1 = (np.ceil(px.max(1)) + 1).clip(0, self.w).astype(int)
        y0 = np.floor(py.min(1)).clip(0, self.ph).astype(int)
        y1 = (np.ceil(py.max(1)) + 1).clip(0, self.ph).astype(int)
        x0[near], y0[near], x1[near], y1[near] = 0, 0, self.w, self.ph
        x1[far], y1[far] = 0, 0
        return np.stack([y0, y1, x0, x1], 1)

    def fbox(self, axis, val, ra, rb, within=None):
        """Screen bbox (y0, y1, x0, x1) of an axis-aligned rectangle, clipped to `within`."""
        ia, ib = (1, 2) if axis == 0 else (0, 2) if axis == 1 else (0, 1)
        pts = np.empty((4, 3))
        pts[:, axis] = val
        pts[:, ia] = (ra[0], ra[1], ra[0], ra[1])
        pts[:, ib] = (rb[0], rb[0], rb[1], rb[1])
        px, py, vz = self.proj_many(pts)
        wy0, wy1, wx0, wx1 = within or (0, self.ph, 0, self.w)
        if (vz < 0.3).all():
            return (0, 0, 0, 0)
        if (vz < 0.3).any():
            return (wy0, wy1, wx0, wx1)
        return (max(wy0, int(math.floor(py.min()))), min(wy1, int(math.ceil(py.max())) + 1),
                max(wx0, int(math.floor(px.min()))), min(wx1, int(math.ceil(px.max())) + 1))

    def draw_boxes(self, boxes):
        """boxes: dicts with b=(x0,x1,y0,y1,z0,z1), faces and texture closures."""
        if not boxes:
            return
        B = np.array([b["b"] for b in boxes], float)
        bb = self.box_bbox(B)
        cam = self.pos
        for bx, bbx in zip(boxes, bb):
            x0, x1, y0, y1, z0, z1 = bx["b"]
            if bbx[1] <= bbx[0] or bbx[3] <= bbx[2]:
                continue
            bbox = tuple(int(v) for v in bbx)
            big = (bbox[1] - bbox[0]) * (bbox[3] - bbox[2]) > 500
            faces = bx["f"]
            if "top" in faces and cam[1] > y1:
                bf = self.fbox(1, y1, (x0, x1), (z0, z1), bbox) if big else bbox
                self.hit_face(1, y1, (x0, x1), (z0, z1), bf, bx["tex_top"])
            if "x" in faces:
                xv = x0 if cam[0] < x0 else x1 if cam[0] > x1 else None
                if xv is not None:
                    bf = self.fbox(0, xv, (y0, y1), (z0, z1), bbox) if big else bbox
                    self.hit_face(0, xv, (y0, y1), (z0, z1), bf, bx["tex_x"](-1 if xv == x0 else 1))
            if "z" in faces and cam[2] < z0:
                bf = self.fbox(2, z0, (x0, x1), (y0, y1), bbox) if big else bbox
                self.hit_face(2, z0, (x0, x1), (y0, y1), bf, bx["tex_z"], bx.get("hole"))
        self.flush_walls()

    def plain_tex(self, color, n):
        base = np.array(color, f32) * self.light(n)
        return lambda a, b, t, base=base: np.broadcast_to(base, (t.size, 3)).T

    def roof_tex(self, base, bounds, seed):
        light = self.light((0, 1, 0))
        base = np.array(base, f32)
        x0, x1, z0, z1 = bounds

        def tex(x, z, t):
            h = hash32(np.floor(x * 0.8), np.floor(z * 0.8), seed)
            r = (h & 255) * f32(1 / 255.0)
            c = base * light * (0.78 + 0.34 * r)[:, None]
            edge = np.minimum(np.minimum(x - x0, x1 - x), np.minimum(z - z0, z1 - z)) < 0.6
            c = np.where(edge[:, None], c * 1.25 + 8, c)
            sk = (r > 0.965)
            c = np.where(sk[:, None], np.array([110, 150, 190], f32) * light * 1.1, c)
            return c.T
        return tex

    # ------------------------------------------------------------ facade planes
    def draw_walls(self, row, now):
        cx, cy, cz = self.cp
        for side in (-1, 1):
            tbl, soa = self.arr[(side, row)]
            X = side * (WF if row == 0 else X1)
            t = (X - cx) * self.rdx
            ok = (t > 0.5) & (t < TMAX) & (t < self.zb)
            pos = np.flatnonzero(ok)
            if pos.size == 0:
                continue
            tv = t.reshape(-1).take(pos)
            yv = cy + tv * self.dyf.take(pos)
            zv = cz + tv * self.dzf.take(pos)
            q = np.minimum(np.maximum(((zv - self.zo) * 4.0).astype(np.int32), 0), tbl.size - 1)
            idx = tbl.take(q)
            good = np.flatnonzero((yv > 0) & (yv < soa["h"].take(idx)))
            if good.size == 0:
                continue
            pos, tv, yv, zv, idx = pos.take(good), tv.take(good), yv.take(good), zv.take(good), idx.take(good)
            light = self.light((-side, 0, 0))
            if row == 1:
                light = light * 0.88
            g = soa
            col = self.wall_tex(zv, yv, tv, g["h"].take(idx), np.take(g["base"], idx, axis=1), g["fw"].take(idx),
                                g["fh"].take(idx), g["wa"].take(idx), g["vlo"].take(idx), g["vhi"].take(idx),
                                g["litp"].take(idx), g["seed"].take(idx), light, shops=(row == 0))
            if row == 0:
                col = self.apply_signs(col, side, zv, yv, tv)
            self.put(pos, col)
            self.zbf[pos] = tv

    def apply_signs(self, col, side, z, y, t):
        for sg in self.sign_cache:
            if sg[0] != side:
                continue
            _, z0, z1, v0, v1, neon, text = sg
            m = (z >= z0) & (z <= z1) & (y >= v0) & (y <= v1)
            if not m.any():
                continue
            zz, yy = z[m], y[m]
            inner = (zz > z0 + 0.22) & (zz < z1 - 0.22) & (yy > v0 + 0.22) & (yy < v1 - 0.22)
            nc = np.array(neon, f32)[:, None]
            zs = zz - z0
            strip = ((zs * 2.3 - np.floor(zs * 2.3)) < 0.5) & (yy > v0 + 0.5) & (yy < v1 - 0.5)
            k = np.where(inner, 0.55, 0.15).astype(f32)
            c = nc * k[None, :]
            si = strip & inner
            c = np.where(si[None, :], nc * 1.15 + 40, c)
            col[:, m] = c
        return col

    # ------------------------------------------------------------ ground
    def draw_ground(self, now, tun):
        th = self.th
        F = self.F
        cx, cy, cz = self.cp
        pos = np.flatnonzero((self.zbf > 1e8) & (self.dyf < -1e-3))
        if pos.size == 0:
            return
        t = (-cy) / self.dyf.take(pos)
        keep = np.flatnonzero(t < TMAX)
        pos, t = pos.take(keep), t.take(keep)
        x = cx + t * self.dxf.take(pos)
        z = cz + t * self.dzf.take(pos)
        ax = np.abs(x)
        pw = t * f32(1 / F)
        pwz = np.maximum(pw, t * t * f32(1 / (F * max(cy, 1.0))))
        G = th["ground"]
        fl = np.floor
        n = (hash32(fl(x * 1.6), fl(z * 1.6), 9) & 255).astype(f32) * f32(1 / 255.0)
        asph = G[:, None] * (0.9 + 0.2 * n)[None, :]
        zz = z - PER * fl(z * f32(1 / PER))
        cross = zz >= PER - GAP
        road = (ax < ROAD) | (cross & (ax < 60))
        walk = (~road) & (ax < WF) & (~cross)
        kerb = ((ax >= ROAD) & (ax < ROAD + 0.35) & (~cross)).astype(f32)
        dark = ((~road) & (~walk)).astype(f32)
        conc = (th["ground"] * 1.35 + 14)[:, None]
        z24, a24 = z * f32(1 / 2.4), ax * f32(1 / 2.4)
        joint = ((((z24 - fl(z24)) < 0.05) | ((a24 - fl(a24)) < 0.04)) & (pw < 0.8)).astype(f32)
        walkc = conc * ((0.94 + 0.12 * n) * (1 - 0.2 * joint))[None, :]
        col = asph * (1 - 0.45 * dark)[None, :]
        col = col + (walkc - col) * walk.astype(f32)[None, :]
        col = col + (conc * 1.25 - col) * kerb[None, :]

        def la(c, w):
            return np.minimum(np.maximum((w * 0.5 + pw * 0.5 - np.abs(c)) / pw, 0), 1) * \
                np.minimum(np.maximum(w / pw + 0.2, 0), 1)
        z9 = z * f32(1 / 9.0)
        dashz = ((z9 - fl(z9)) < 0.4667).astype(f32)
        aadash = np.minimum(np.maximum((pwz - 0.8) * f32(1 / 1.8), 0), 1)
        dash = dashz * (1 - aadash) + 0.47 * aadash
        mark = np.maximum(np.maximum(la(ax - 3.6, 0.16) * dash, la(ax - 7.2, 0.16) * dash), la(ax - 9.7, 0.18))
        cw = (((zz > 71.8) & (zz < 73.8)) | (zz > PER - 2.3)).astype(f32)
        x95 = x * 0.95
        zeb = ((np.abs(x95 - fl(x95) - 0.5) < 0.28 + 0.3 * aadash) & (ax < ROAD - 0.3)).astype(f32)
        mark = np.maximum(mark, cw * zeb * 0.9)
        in_road = (road & ~(cross & (ax > ROAD))).astype(f32)
        mcol = np.array([205, 205, 210], f32)[:, None] * 0.8
        col = col + (mcol - col) * (np.minimum(mark, 1) * in_road * 0.85)[None, :]
        yel = la(ax - 0.28, 0.15)
        ycol = np.array([226, 190, 40], f32)[:, None] * 0.9
        col = col + (ycol - col) * (np.minimum(yel, 1) * in_road * 0.9)[None, :]
        day = th["day"]
        night = max(0.0, 1.0 - day * 3.2)
        zl = (z + 12.0) * f32(1 / 24.0)
        dzl = (zl - fl(zl)) * 24.0 - 12.0
        dxl = ax - 14.2
        pool = np.exp(-(dxl * dxl * 0.09 + dzl * dzl * 0.07))
        lampc = np.array([255, 170, 90], f32)[:, None]
        col = col + lampc * (pool * (0.5 * (0.25 + 0.75 * night)))[None, :]
        spill = np.minimum(np.maximum((ax - 12.5) * f32(1 / 3.5), 0), 1) * walk.astype(f32)
        col = col + np.array([70, 45, 20], f32)[:, None] * (spill * (0.3 + night))[None, :]
        if self.rain:
            sky = th["hor"][:, None] * 0.55
            wet = 0.42
            col = col * (1 - wet) + (sky + lampc * pool[None, :] * 0.8) * (wet * 0.8)
            smear = (hash32(fl(x * 0.9), fl(z * 0.12), 21) & 255).astype(f32) * f32(1 / 255.0)
            ni = np.remainder(hash32(fl(x * 0.5), z * 0 + 4, 3), 5)
            nc = np.take(NEON_T, ni, axis=1)
            col = col + nc * (np.minimum(np.maximum(smear - 0.82, 0), 1) * 2.5 * (0.2 + night) * in_road)[None, :]
        if tun is not None:
            inn = ((z > tun[0]) & (z < tun[1]) & (ax < TUN_W)).astype(f32)
            zr = (z - tun[0]) * f32(1 / 7.0)
            ring = ((zr - fl(zr)) < 0.14).astype(f32)
            warm = np.array([255, 190, 110], f32)[:, None]
            col = col + ((col * 0.7 + warm * (0.1 + 0.15 * ring)[None, :] * 0.8) - col) * inn[None, :]
        self.put(pos, col)
        self.zbf[pos] = t

    # ------------------------------------------------------------ sprites
    def add_glow(self, px, py, color, r, a=1.0):
        x0, x1 = int(px - r), int(px + r) + 1
        y0, y1 = int(py - r), int(py + r) + 1
        if x1 <= 0 or y1 <= 0 or x0 >= self.w or y0 >= self.ph:
            return
        x0c, x1c, y0c, y1c = max(0, x0), min(self.w, x1), max(0, y0), min(self.ph, y1)
        yy = (np.arange(y0c, y1c) + 0.5 - py)[:, None]
        xx = (np.arange(x0c, x1c) + 0.5 - px)[None, :]
        g = np.exp(-(xx * xx + yy * yy) / (r * r * 0.35)) * a
        self.col[:, y0c:y1c, x0c:x1c] += g[None] * np.array(color, f32)[:, None, None]

    def visible(self, px, py, depth):
        x, y = int(px), int(py)
        return 0 <= x < self.w and 0 <= y < self.ph and self.zb[y, x] > depth - 0.6

    def add_line(self, p0, p1, color, a0, a1, mode_add=True):
        x0, y0, x1, y1 = p0[0], p0[1], p1[0], p1[1]
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        if n > 400:
            return
        tt = self.tk[:n] * (1.0 / max(n - 1, 1))
        xs = (x0 + (x1 - x0) * tt).astype(np.int32)
        ys = (y0 + (y1 - y0) * tt).astype(np.int32)
        m = (xs >= 0) & (xs < self.w) & (ys >= 0) & (ys < self.ph)
        if not m.any():
            return
        al = (a0 + (a1 - a0) * tt)[m][None, :].astype(f32)
        xs, ys = xs[m], ys[m]
        c = np.array(color, f32)[:, None]
        if mode_add:
            self.col[:, ys, xs] += c * al
        else:
            self.col[:, ys, xs] = self.col[:, ys, xs] * (1 - al) + c * al

    def rect(self, cx, y_bottom, w, h, color):
        x0, x1 = int(round(cx - w / 2)), int(round(cx + w / 2))
        y0, y1 = int(round(y_bottom - h)), int(round(y_bottom))
        if x1 <= x0:
            x1 = x0 + 1
        if y1 <= y0:
            y0 = y1 - 1
        x0c, x1c, y0c, y1c = max(0, x0), min(self.w, x1), max(0, y0), min(self.ph, y1)
        if x1c > x0c and y1c > y0c:
            self.col[:, y0c:y1c, x0c:x1c] = np.asarray(color, f32)[:, None, None]

    def draw_cars(self, now, tun):
        th = self.th
        night = max(0.0, 1.0 - th["day"] * 3.2)
        cz = self.pos[2]
        F = self.F
        dirn, z0, v, ci, r = self.car_arr
        z = cz - 40 + ((z0 + v * dirn * now - (cz - 40)) % 320.0)
        lane = np.where(dirn < 0, -1.0, 1.0) * (2.0 + 3.4 * np.floor(r * 3)) + (r - 0.5) * 0.5
        P = np.stack([lane, np.full_like(z, 0.75), z], 1)
        px, py, vz = self.proj_many(P)
        Q = np.stack([lane, np.full_like(z, 0.5), np.where(dirn > 0, z - 9.0, z + 9.0)], 1)
        qx, qy, qz = self.proj_many(Q)
        ok = np.flatnonzero((vz > 7) & (vz < 230) & (px > -10) & (px < self.w + 10))
        for i in ok:
            x, y, d = float(px[i]), float(py[i]), float(vz[i])
            if not self.visible(x, y, d):
                continue
            s = F / d
            fogk = 1 - math.exp(-(d / (150.0 * th["fogk"])) ** 1.5)
            body = np.array(CAR_COLS[int(ci[i])], f32) * (0.4 + float(th["amb"].mean()) * 0.8)
            body = body * (1 - fogk) + th["fog"] * fogk
            self.rect(x, y + 0.75 * s, 1.9 * s, 1.3 * s, body)
            if d < 90:
                self.rect(x, y - 0.1 * s, 1.33 * s, 0.52 * s, body * 1.25 + 10)
            fac = dirn[i] > 0
            lc = np.array((255, 30, 30) if fac else (255, 244, 214), f32)
            lcd = lc * (1 - fogk * 0.4)
            for lx in (-0.7, 0.7):
                self.rect(x + lx * s, y + 0.45 * s, max(1.0, 0.34 * s), max(1.0, 0.24 * s), lcd)
            if d < 130:
                self.add_glow(x, y + 0.2 * s, lc, max(2.0, 1.6 * s), 0.5 + 0.4 * night)
            if qz[i] > 0.5 and d < 150 and (night > 0.05 or th["day"] < 0.5):
                self.add_line((x, y + 0.35 * s), (float(qx[i]), float(qy[i])), lc * 0.55, 0.9 * (0.3 + night), 0.0)

    def draw_lamps(self, now):
        th = self.th
        night = max(0.0, 1.0 - th["day"] * 3.2)
        cz = self.pos[2]
        k0 = int(math.floor((cz - 5) / 24.0))
        lampc = np.array([255, 190, 110], f32)
        ks = np.arange(k0, k0 + 7) * 24.0
        zs = np.concatenate([ks, ks])
        sd = np.concatenate([np.full(7, -1.0), np.full(7, 1.0)])
        n = zs.size
        xb = sd * 14.4
        B = np.stack([xb, np.zeros(n), zs], 1)
        T = np.stack([xb, np.full(n, 9.0), zs], 1)
        H = np.stack([xb - sd * 2.8, np.full(n, 9.3), zs], 1)
        bx, by, bz = self.proj_many(B)
        tx, ty, tz = self.proj_many(T)
        hx, hy, hz = self.proj_many(H)
        on = 0.25 + 0.75 * night
        for i in np.flatnonzero((bz > 1) & (bz < 150) & (bx > -30) & (bx < self.w + 30)):
            d = float(bz[i])
            near = d < 48
            fogk = 1 - math.exp(-(d / (140.0 * th["fogk"])) ** 1.5)
            if near:
                pole = th["amb"] * 70 * (1 - fogk) + th["fog"] * fogk
                self.add_line((bx[i], by[i]), (tx[i], ty[i]), pole, 1.0, 1.0, mode_add=False)
                self.add_line((tx[i], ty[i]), (hx[i], hy[i]), pole, 1.0, 1.0, mode_add=False)
            if self.visible(hx[i], hy[i], float(hz[i])):
                if d < 70:
                    self.add_glow(hx[i], hy[i], lampc, max(2.0, 1.8 * self.F / float(hz[i]) * 1.2 + 1.2), 0.9 * on)
                x, y = int(hx[i]), int(hy[i])
                if 0 <= x < self.w and 0 <= y < self.ph:
                    self.col[:, y, x] = (255, 240, 200)
                    if d >= 70 and x + 1 < self.w:
                        self.col[:, y, x + 1] = (255, 200, 130)
                if on > 0.4 and d < 30:
                    for dxg in (-2.0, 2.0):
                        g = self.proj((xb[i] - sd[i] * (5.5 + dxg), 0.0, zs[i] + dxg))
                        if g is not None:
                            self.add_line((hx[i], hy[i]), (g[0], g[1]), lampc, 0.12 * on, 0.02 * on)

    def draw_peds(self, now):
        th = self.th
        cz = self.pos[2]
        for side, z0, v, xo, ci in self.peds:
            z = cz - 10 + ((z0 + v * now - (cz - 10)) % 90.0)
            p = self.proj((side * xo, 0.0, z))
            if p is None or p[2] < 8 or p[2] > 85:
                continue
            px, py, vz = p
            if not self.visible(px, py, vz):
                continue
            s = self.F / vz
            c = np.array(NEONS[ci], f32) * 0.35 + th["amb"] * 40
            self.rect(px, py, max(1.0, 0.5 * s), 1.2 * s, c)
            self.rect(px, py - 1.2 * s, max(1.0, 0.3 * s), max(1.0, 0.3 * s), (210, 170, 150))

    # ------------------------------------------------------------ police drone
    def police_pos(self, now):
        pt = now - self.police
        z = self.pos[2] + 13.0 + 2.5 * math.sin(pt * 0.9)
        x = self.pos[0] * 0.5 + 4.5 * math.sin(pt * 0.7)
        y = max(7.0, self.pos[1] - 3.2 + 1.0 * math.sin(pt * 1.6))
        return np.array([x, y, z])

    def police_light(self, now):
        """Red/blue strobe lighting on facades, roofs and the street."""
        pp = self.police_pos(now)
        ph = (now - self.police) * 5.0
        a = max(0.0, math.sin(ph * math.pi / 2))
        b = max(0.0, math.sin(ph * math.pi / 2 + math.pi))
        a, b = a ** 0.7, b ** 0.7
        fin = self.zbf < 1e8
        pos = np.flatnonzero(fin)
        t = self.zbf[pos]
        px = self.cp[0] + t * self.dxf[pos] - pp[0]
        py = self.cp[1] + t * self.dyf[pos] - pp[1]
        pz = self.cp[2] + t * self.dzf[pos] - pp[2]
        d2 = px * px + py * py + pz * pz
        att = 1.0 / (1.0 + d2 / 260.0)
        lc = np.array(RED, f32) * a + np.array((60, 110, 255), f32) * b
        side_w = np.where(px < 0, 1.0 - 0.4 * (b > a), 1.0)
        for k in range(3):
            self.colf[k][pos] += lc[k] * (att * 0.95)
        return pp, a, b

    def draw_police(self, now):
        pp, a, b = self.police_pos(now), 0, 0
        ph = (now - self.police) * 5.0
        a = max(0.0, math.sin(ph * math.pi / 2)) ** 0.7
        b = max(0.0, math.sin(ph * math.pi / 2 + math.pi)) ** 0.7
        p = self.proj(pp)
        if p is None:
            return
        px, py, vz = p
        s = self.F / vz
        body = np.array((26, 28, 38), f32)
        rim = np.array((150, 160, 190), f32)
        self.rect(px, py + 0.3 * s, 3.2 * s, 0.9 * s, body)
        self.rect(px, py + 0.0 * s, 1.8 * s, 0.35 * s, rim)
        for sx in (-1, 1):
            rx = px + sx * 3.0 * s
            ry = py - 0.2 * s
            self.add_line((px + sx * 1.2 * s, py), (rx, ry), body, 1.0, 1.0, mode_add=False)
            x0, x1 = int(rx - 1.6 * s), int(rx + 1.6 * s) + 1
            yy = int(ry - 0.15 * s)
            if 0 <= yy < self.ph:
                x0c, x1c = max(0, x0), min(self.w, x1)
                if x1c > x0c:
                    self.col[:, yy, x0c:x1c] = self.col[:, yy, x0c:x1c] * 0.5 + np.array((120, 126, 150), f32)[:, None] * 0.5
            self.rect(rx, ry + 0.25 * s, 0.5 * s, 0.35 * s, body)
        self.add_glow(px - 1.4 * s, py + 0.35 * s, RED, max(2.5, 1.8 * s), 0.35 + 0.9 * a)
        self.add_glow(px + 1.4 * s, py + 0.35 * s, (70, 120, 255), max(2.5, 1.8 * s), 0.35 + 0.9 * b)
        self.rect(px - 1.4 * s, py + 0.45 * s, max(1.0, 0.35 * s), max(1.0, 0.25 * s), (255, 40, 40) if a > 0.3 else (90, 20, 20))
        self.rect(px + 1.4 * s, py + 0.45 * s, max(1.0, 0.35 * s), max(1.0, 0.25 * s), (80, 130, 255) if b > 0.3 else (20, 30, 90))

    # ------------------------------------------------------------ billboard
    def board_tex(self, now, zb_):
        day = self.th["day"]
        k = 1.0 - 0.15 * day
        pulse = 0.92 + 0.08 * math.sin(now * 3.0)
        ccell = 0.64
        sw, sh = 22 * ccell, 15 * ccell
        sx0, sy_top = -sw / 2, BOARD_Y0 + BOARD_H / 2 + sh / 2 + 0.4

        def tex(x, y, t):
            u = (x - sx0) / ccell
            v = (sy_top - y) / ccell
            iu, iv = np.floor(u).astype(np.int32), np.floor(v).astype(np.int32)
            inb = (iu >= 0) & (iu < 22) & (iv >= 0) & (iv < 15)
            sk = np.zeros(x.shape, bool)
            sk[inb] = SKULL_NP[iv[inb], iu[inb]]
            vv = (BOARD_Y0 + BOARD_H - y) / BOARD_H
            bg = np.array([170, 12, 90], f32) * (1.0 - 0.55 * vv)[:, None] + np.array([20, 0, 60], f32) * vv[:, None]
            scan = (np.floor(y * 3.0) % 2 == 0)
            bg = bg * np.where(scan, 1.0, 0.82)[:, None]
            edge = (np.abs(x) > BOARD_W / 2 - 0.55) | (y < BOARD_Y0 + 0.55) | (y > BOARD_Y0 + BOARD_H - 0.55)
            skc = np.array([255, 224, 240], f32)
            c = np.where(sk[:, None], skc, bg)
            # eye glow inside the sockets
            c = np.where(edge[:, None], np.array([0, 229, 255], f32) * 0.95, c)
            return (c * (k * pulse)).T
        return tex

    # ------------------------------------------------------------ main draw
    def render_world(self, now, tun_cur, inside):
        cam = self.pos
        z = cam[2]
        th = self.th
        self.set_camera()
        self.zb.fill(1e9)
        self.build_strips(z)
        self.sign_cache = [(s[1], s[2], s[3], s[4], s[5], s[6], s[7]) for s in self.signs
                           if abs((s[2] + s[3]) / 2 - z) < 140]
        self.draw_walls(0, now)
        boxes = []
        # tunnel structure
        if tun_cur is not None:
            tz0, tz1 = tun_cur
            ceil_col = np.array((60, 64, 76), f32)
            self.draw_tunnel(now, tz0, tz1)
        # billboard
        for bz_ in self.board_list:
            if -5 < bz_ - z < TMAX:
                self.draw_billboard(now, bz_, boxes)
        # roofs and set-backs of the frontage
        near_boxes = self.collect_boxes(z, now)
        self.draw_boxes(boxes + near_boxes)
        self.draw_walls(1, now)
        self.draw_ground(now, tun_cur if tun_cur and tun_cur[0] - 1 < z + 300 else None)
        self.draw_sky(now)

    def draw_tunnel(self, now, tz0, tz1):
        light = self.light((1, 0, 0))
        ribs_col = np.array((90, 220, 255), f32)
        warm = np.array((255, 196, 120), f32)

        def wall(side):
            def tex(y, z, t):
                zz = (z - tz0) % 7.0
                rib = zz < 0.9
                strip = (y > 5.0) & (y < 5.6)
                c = np.broadcast_to(np.array((86, 90, 104), f32) * 0.62 * light, (t.size, 3)).copy()
                c[rib] = (140, 150, 168)
                c[rib & (y > 6.2)] = ribs_col * 0.9
                c[strip & ~rib] = warm
                c[(y < 0.5)] = (60, 62, 72)
                fall = (1.0 - np.clip((t - 12) / 90.0, 0, 0.7))[:, None]
                return (c * fall).T
            return tex
        for side in (-1, 1):
            self.hit_face(0, side * TUN_W, (0, TUN_H), (tz0, tz1), self.fbox(0, side * TUN_W, (0, TUN_H), (tz0, tz1)), wall(side))

        def ceil(x, z, t):
            zz = (z - tz0) % 7.0
            rib = zz < 0.9
            c = np.broadcast_to(np.array((70, 74, 88), f32) * 0.6, (t.size, 3)).copy()
            c[np.abs(x) < 0.3] = (200, 215, 235)
            c[rib] = ribs_col * 0.9
            c[rib & (np.abs(x) < 0.3)] = (255, 255, 255)
            fall = (1.0 - np.clip((t - 12) / 90.0, 0, 0.7))[:, None]
            return (c * fall).T
        self.hit_face(1, TUN_H, (-TUN_W, TUN_W), (tz0, tz1), self.fbox(1, TUN_H, (-TUN_W, TUN_W), (tz0, tz1)), ceil)

    def draw_billboard(self, now, bz_, boxes):
        cx = BOARD_W / 2
        tex = self.board_tex(now, bz_)
        bb = self.fbox(2, bz_, (-cx, cx), (BOARD_Y0, BOARD_Y0 + BOARD_H))
        steel = (52, 56, 70)
        # panel
        self.hit_face(2, bz_, (-cx, cx), (BOARD_Y0, BOARD_Y0 + BOARD_H), bb, tex)
        y1 = BOARD_Y0 + BOARD_H
        frame = {"b": (-cx - 0.7, cx + 0.7, BOARD_Y0 - 0.5, y1 + 0.6, bz_ + 0.15, bz_ + 1.8), "f": ("top", "z", "x")}
        frame["tex_top"] = self.plain_tex(steel, (0, 1, 0))
        frame["tex_z"] = self.plain_tex(steel, (0, 0, -1))
        frame["tex_x"] = lambda s, st=steel: self.plain_tex(st, (s, 0, 0))
        boxes.append(frame)
        for lx in (-10.5, 10.5):
            leg = {"b": (lx - 0.45, lx + 0.45, 0.0, BOARD_Y0 - 0.4, bz_ + 0.4, bz_ + 1.3), "f": ("x", "z", "top")}
            leg["tex_top"] = self.plain_tex(steel, (0, 1, 0))
            leg["tex_z"] = self.plain_tex(steel, (0, 0, -1))
            leg["tex_x"] = lambda s, st=steel: self.plain_tex(st, (s, 0, 0))
            boxes.append(leg)

    def collect_boxes(self, z, now):
        """Roof tops, set-back tiers, z-facing facades at cross streets, roof kit, tunnel mass."""
        boxes = []
        cam = self.pos
        for (side, row), ents in self.ents.items():
            xa = WF if row == 0 else X1
            depth = D0 if row == 0 else D1
            prev_h = 0.0
            for e in ents:
                ez0, ez1, hlo, ci, fw, fh, wa, vlo, vhi, litp, seed, style, hfull, tier = e
                ph_, prev_h = prev_h, hlo
                if hlo <= 0 or ez1 < z - 3 or ez0 > z + (210 if row == 0 else 140):
                    continue
                xs = (xa, xa + depth) if side > 0 else (-xa - depth, -xa)
                base = PALETTE[ci]
                parm = dict(base=base, fw=fw, fh=fh, wa=wa, vlo=vlo, vhi=vhi, litp=litp, seed=seed)
                faces = []
                # roof of the lower part
                roof_vis = cam[1] > hlo and ez0 - z < 130
                zface = cam[2] < ez0 and ph_ < hlo - 0.5 and (row == 0 or ph_ == 0.0)
                if tier:
                    ins = tier[1]
                    tx = (xs[0] + (0 if side > 0 else 0), xs[1] - ins) if side < 0 else (xs[0] + ins, xs[1])
                    tx = (xs[0], xs[1] - ins) if side < 0 else (xs[0] + ins, xs[1])
                    # lower roof (full footprint), the tier stands on its far part
                    if roof_vis:
                        b0 = {"b": (xs[0], xs[1], 0.0, hlo, ez0, ez1), "f": ("top",)}
                        b0["tex_top"] = self.roof_tex((98, 98, 108), (xs[0], xs[1], ez0, ez1), seed)
                        boxes.append(b0)
                    tzf = ("top", "x", "z") if (cam[2] < ez0 and ph_ < hfull - 0.5) else ("top", "x")
                    tb = {"b": (tx[0], tx[1], max(hlo, ph_) if tzf[-1] == "z" else hlo, hfull, ez0, ez1), "f": tzf}
                    tb["tex_top"] = self.roof_tex((98, 98, 108), (tx[0], tx[1], ez0, ez1), seed + 1)
                    tb["tex_x"] = lambda sgn, p=parm, tbb=tb: self.make_wall_tex_x(p, tbb, sgn)
                    tb["tex_z"] = self.make_wall_tex_z(parm, (tx[0], tx[1]), hfull)
                    boxes.append(tb)
                    if zface:
                        b1 = {"b": (xs[0], xs[1], ph_, hlo, ez0, ez1), "f": ("z",)}
                        b1["tex_z"] = self.make_wall_tex_z(parm, (xs[0], xs[1]), hlo)
                        boxes.append(b1)
                else:
                    f = []
                    if roof_vis:
                        f.append("top")
                    if zface:
                        f.append("z")
                    if f:
                        b0 = {"b": (xs[0], xs[1], ph_ if f == ["z"] else 0.0, hlo, ez0, ez1), "f": tuple(f)}
                        if style == 4:
                            b0["f"] = tuple(f)
                        b0["tex_top"] = self.roof_tex((98, 98, 108), (xs[0], xs[1], ez0, ez1), seed)
                        b0["tex_z"] = self.make_wall_tex_z(parm, (xs[0], xs[1]), hlo)
                        boxes.append(b0)
                if style == 4 and row == 0 and side == -1:
                    # the tunnel's top mass over the avenue
                    m = {"b": (-WF, WF, TUN_H, MASS_H, ez0, ez1), "f": ("top", "z")}
                    m["tex_top"] = self.roof_tex((98, 98, 108), (-WF, WF, ez0, ez1), seed)
                    m["tex_z"] = self.make_portal_tex(ez0, parm)
                    m["hole"] = (-TUN_W, TUN_W, 0.0, TUN_H)
                    m["b"] = (-WF, WF, 0.0, MASS_H, ez0, ez1)
                    boxes.append(m)
        # roof kit
        ncount = 0
        for side, kx, kz, hh, kind, r in self.kits:
            if abs(kz - z) > 70 or kz < z - 2:
                continue
            if ncount > 5:
                break
            ncount += 1
            xr = WF + kx
            x0, x1 = (xr, xr + 3.2) if side > 0 else (-xr - 3.2, -xr)
            hk = {"tank": 3.6, "ac": 1.3, "shed": 2.4}[kind]
            col = {"tank": (110, 78, 58), "ac": (128, 132, 138), "shed": (92, 94, 108)}[kind]
            k = {"b": (x0, x1, hh, hh + hk, kz, kz + 3.2), "f": ("top", "x", "z")}
            k["tex_top"] = self.plain_tex(col, (0, 1, 0))
            k["tex_z"] = self.plain_tex(col, (0, 0, -1))
            k["tex_x"] = lambda s, c=col: self.plain_tex(c, (s, 0, 0))
            boxes.append(k)
        return boxes

    def make_wall_tex_x(self, p, tb, sgn):
        return WallTex(True, np.asarray(p["base"], f32), self.light((sgn, 0, 0)), tb["b"][3], p, p["seed"], False)

    def make_wall_tex_z(self, p, xr, hh):
        return WallTex(False, np.asarray(p["base"], f32), self.light((0, 0, -1)), hh, p, p["seed"] + 7, True)

    def make_portal_tex(self, tz0, p):
        light = self.light((0, 0, -1))
        arch = np.array((90, 220, 255), f32)
        day = self.th["day"]

        def tex(x, y, t):
            ax = np.abs(x)
            # cast concrete: panels with dark joints, lighter pilasters beside the arch
            joint = ((y - np.floor(y / 2.6) * 2.6) < 0.12) | ((ax - np.floor(ax / 3.4) * 3.4) < 0.1)
            base = np.where(joint, 0.62, 1.0).astype(f32)
            pil = (ax > TUN_W + 1.8) & (ax < TUN_W + 2.8)
            base = base * np.where(pil, 1.18, 1.0).astype(f32)
            c = (np.array((74, 76, 88), f32)[:, None] * light[:, None]) * base[None, :]
            c = c * (1.0 - 0.25 * np.clip((y - TUN_H) / 12.0, 0, 1))[None, :]
            # hazard chevrons framing the opening
            ring = (ax < TUN_W + 0.9) & (y < TUN_H + 0.9)
            stripe = ((np.floor((x + y) * 1.4)).astype(np.int64) & 1) == 0
            haz = np.where(stripe, np.array((235, 190, 20), f32)[:, None] * (0.7 + 0.3 * light[:, None]),
                           np.array((18, 18, 22), f32)[:, None])
            c = np.where(ring[None, :], haz, c)
            # glowing inner lip of the arch
            glow = (ax < TUN_W + 0.35) & (y < TUN_H + 0.35)
            c = np.where(glow[None, :], arch[:, None] * 1.05, c)
            # lit sign panel above the arch
            band = (ax < TUN_W - 0.6) & (y > TUN_H + 1.5) & (y < TUN_H + 3.1)
            edge = band & ((np.abs(y - (TUN_H + 1.5)) < 0.18) | (np.abs(y - (TUN_H + 3.1)) < 0.18))
            dash = band & (((x * 1.1) - np.floor(x * 1.1)) < 0.62) & (np.abs(y - (TUN_H + 2.3)) < 0.32)
            amber = np.array((255, 170, 40), f32)[:, None]
            c = np.where(band[None, :], np.array((20, 14, 10), f32)[:, None], c)
            c = np.where(dash[None, :], amber * (0.9 - 0.5 * day), c)
            c = np.where(edge[None, :], amber, c)
            # a row of flood lights over the sign
            lamp = (np.abs(y - (TUN_H + 4.2)) < 0.3) & (((ax + 1.0) - np.floor((ax + 1.0) / 2.6) * 2.6) < 0.45) & (ax < TUN_W + 2)
            c = np.where(lamp[None, :], np.array((255, 236, 200), f32)[:, None], c)
            return c
        return tex

    # ------------------------------------------------------------ post
    def finish(self, s, now, dt, police_t, inside, tun_cur):
        th = self.th
        col = self.col
        fin = self.zb < 1e8
        tt = np.minimum(self.zb, 1e5)
        # fog based on true distance, a little lighter low down
        td = tt * (1.0 / self.invn)
        fogd = (190.0 + 110.0 * th["day"]) * th["fogk"]     # clearer air by day
        if inside:
            fogd = 80.0
        f = 1.0 - np.exp(-(td / fogd) ** 1.35)
        f = np.where(fin, f, 0.0).astype(f32)
        fog = th["fog"] if not inside else np.array((12, 14, 26), f32)
        if police_t is not None:
            self.police_light(now)
        # board glow onto the street canyon
        col += (fog[:, None, None] - col) * f[None]
        # emissive halos for neon signs
        for sg in self.sign_cache:
            side, z0, z1, v0, v1, neon, text = sg
            zc = (z0 + z1) / 2
            p = self.proj((side * (WF - 0.2), (v0 + v1) / 2, zc))
            if p is None or p[2] > 120:
                continue
            if -20 < p[0] < self.w + 20:
                r = min(8.0, max(2.5, 3.0 * (z1 - z0) / p[2] * self.F / 6.0))
                fk = math.exp(-(p[2] / 120.0) ** 1.5)
                self.add_glow(p[0], p[1], neon, r, 0.38 * fk)
        # roof antennas and beacons
        for side, ax_, az_, hh, ln in self.ants:
            if az_ < self.pos[2] + 3 or az_ - self.pos[2] > 130:
                continue
            xr = side * (WF + ax_)
            b = self.proj((xr, hh, az_))
            tp = self.proj((xr, hh + ln, az_))
            if b is None or tp is None:
                continue
            if not (-5 < b[0] < self.w + 5) or not self.visible(tp[0], tp[1], tp[2]):
                continue
            fk = math.exp(-(b[2] / 150.0) ** 1.5)
            pole = th["fog"] * (1 - fk) + th["amb"] * 90 * fk
            self.add_line((b[0], b[1]), (tp[0], tp[1]), pole, 1.0, 1.0, mode_add=False)
            if int(now * 1.1 + az_) % 2 == 0:
                self.add_glow(tp[0], tp[1], (255, 40, 40), 2.5, 0.9)
        self.draw_lamps(now)
        self.draw_cars(now, tun_cur)
        self.draw_peds(now)
        if police_t is not None and not inside:
            self.draw_police(now)
        if self.rain and not inside:
            self.draw_rain(dt)

    def draw_rain(self, dt):
        d = self.drops
        d[:, 1] += dt * 80 * d[:, 2]
        d[:, 0] -= dt * 14 * d[:, 2]
        d[:, 1] %= self.ph
        d[:, 0] %= self.w
        rc = np.array((190, 205, 235), f32)
        for k in range(4):
            xs = (d[:, 0] + k * 0.4).astype(np.int32) % self.w
            ys = (d[:, 1] - k).astype(np.int32) % self.ph
            self.col[:, ys, xs] = self.col[:, ys, xs] * (1 - 0.28 + 0.05 * k) + rc[:, None] * (0.28 - 0.05 * k)

    def draw_parts(self, dt):
        alive = []
        for p in self.parts:
            p[5] += dt
            if p[5] >= p[4]:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            x, y = int(p[0]), int(p[1])
            k = (1 - p[5] / p[4]) * 0.9
            if 0 <= x < self.w - 1 and 0 <= y < self.ph:
                self.col[:, y, x:x + 2] += np.array(p[6], f32)[:, None] * k
            alive.append(p)
        self.parts = alive

    def put(self, pos, c):
        """Scatter planar colours (3, n) into the pixel buffer."""
        cf = self.colf
        cf[0][pos] = c[0]
        cf[1][pos] = c[1]
        cf[2][pos] = c[2]

    def to_screen(self, s):
        img = np.minimum(np.maximum(self.col, 0), 255)
        sh = self.shown
        w = self.w
        if sh is None:
            self.shown = img
            q = (img.astype(np.int32) & 0xF0) | 8
            packed = ((q[0] << 16) | (q[1] << 8) | q[2]).reshape(-1).tolist()
            self.flat = list(map(self.lut.__getitem__, packed))
        else:
            d = np.abs(img[0] - sh[0])
            np.maximum(d, np.abs(img[1] - sh[1]), out=d)
            np.maximum(d, np.abs(img[2] - sh[2]), out=d)
            chg = d > 14
            self.shown = np.where(chg[None], img, sh)
            idx = np.flatnonzero(chg)
            if idx.size:
                q = (img.reshape(3, -1).take(idx, axis=1).astype(np.int32) & 0xF0) | 8
                packed = ((q[0] << 16) | (q[1] << 8) | q[2]).tolist()
                flat, lut = self.flat, self.lut
                for i, c in zip(idx.tolist(), packed):
                    flat[i] = lut[c]
        flat = self.flat
        for y in range(self.h):
            s.pt[y] = flat[(2 * y) * w:(2 * y + 1) * w]
            s.pb[y] = flat[(2 * y + 1) * w:(2 * y + 2) * w]

    # ------------------------------------------------------------ HUD
    def htext(self, s, x, y, txt, color, dim=0.55):
        if not (0 <= y < s.h):
            return
        for i, ch in enumerate(txt):
            cx = x + i
            if 0 <= cx < s.w:
                a, b = s.pt[y][cx], s.pb[y][cx]
                if a is not None and b is not None:
                    bg = ((a[0] + b[0]) * dim * 0.5, (a[1] + b[1]) * dim * 0.5, (a[2] + b[2]) * dim * 0.5)
                    s.bg[y][cx] = (int(bg[0]), int(bg[1]), int(bg[2]))
                s.put(cx, y, ch, color)

    def hud(self, s, now, zoom, police_t, tun_inside):
        w, h = s.w, s.h
        t = now - self.t0
        line = (120, 215, 230)
        dim = (90, 160, 178)
        self.htext(s, 1, 0, "DRONE // DEDSEC QUAD-04", dim)
        if int(now * 1.6) % 2 == 0:
            self.htext(s, 25, 0, "● LIVE", (255, 70, 90))
        else:
            self.htext(s, 25, 0, "  LIVE", (150, 60, 70))
        clock = time.strftime("%H:%M", time.localtime(now))
        rain = " RAIN" if self.rain else ""
        right = "BAT %d%%  %s%s" % (self.battery - t * 0.01, clock, rain)
        self.htext(s, w - len(right) - 1, 0, right, dim)
        hdg = int((math.degrees(self.yaw) + 360) % 360)
        self.htext(s, w // 2 - 3, 0, "▾%03d°" % hdg, line)
        alt = "ALT %02dm" % self.pos[1]
        spd = "%03d km/h" % (self.speed * 3.6)
        if h > 24:
            self.htext(s, 1, h // 2, alt, dim)
            self.htext(s, w - len(spd) - 1, h // 2, spd, dim)
        self.htext(s, 1, h - 1, "DIST %.2f km" % (self.dist / 1000.0), dim)
        gps = "37.7749N 122.4194W"
        self.htext(s, w - len(gps) - 1, h - 1, gps, dim)
        cx, cy = w // 2, h // 2
        if not zoom:
            s.put(cx - 4, cy, "─", dim)
            s.put(cx + 4, cy, "─", dim)
            s.put(cx, cy, "+", dim)
        txt, t0 = self.callout
        if now - t0 < 2.8 and not tun_inside:
            self.htext(s, cx - len(txt) // 2 - 1, h - 3, "[%s]" % txt, (230, 230, 245), 0.4)
        if police_t is not None and police_t < 11:
            msg = " POLICE DRONE // EVADE "
            self.htext(s, cx - len(msg) // 2, 2, msg, RED if int(now * 4) % 2 else (255, 150, 150), 0.35)

    def zoom_lock(self, s, now, u):
        z = self.bz
        a = self.proj((-BOARD_W / 2, BOARD_Y0 + BOARD_H, z))
        b = self.proj((BOARD_W / 2, BOARD_Y0, z))
        if not a or not b:
            return
        x0, y0 = int(max(1, a[0])), int(max(2, a[1] / 2))
        x1, y1 = int(min(s.w - 2, b[0])), int(min(s.h - 3, b[1] / 2))
        if x1 - x0 < 8 or y1 - y0 < 4:
            return
        col = PINK if int(now * 8) % 2 else WHITE
        s.brackets(x0, y0, x1 - x0 + 1, y1 - y0 + 1, col, arm=3)
        self.htext(s, x0 + 1, max(1, y0 - 1), "LOCK // BILLBOARD %d m" % max(0, int(z - self.pos[2])), col, 0.3)

    # ------------------------------------------------------------ effects
    def tint_row(self, s, y, col, t):
        if not 0 <= y < s.h:
            return
        cache = self.fxcache
        for layer in (s.fg, s.pt, s.pb, s.bg):
            row = layer[y]
            for x, c in enumerate(row):
                if c is not None:
                    k = (c, col, t)
                    v = cache.get(k)
                    if v is None:
                        v = cache[k] = blend(c, col, t)
                    row[x] = v

    def post_fx(self, s, now, glitch):
        if len(self.fxcache) > 20000:
            self.fxcache.clear()
        if glitch:
            for _ in range(random.randint(1, 2)):
                y0 = random.randrange(s.h)
                s.shift_row(y0, random.randint(-3, 3))
                self.tint_row(s, y0, random.choice((PINK, CYAN)), 0.14)

    # ------------------------------------------------------------ step
    ZOOM_T = 2.4

    def tunnel_near(self, z):
        for a, b in getattr(self, "tunnels", ()):
            if b > z - 5:
                return (a, b)
        return None

    def step(self, s, now):
        dt, self.last = min(0.1, max(0.0, now - self.last)), now
        t = now - self.t0
        self.update_theme(now)
        z = self.pos[2]
        self.build_strips(z)
        glitch = self.glitch.active(now)
        tun = self.tunnel_near(z)
        in_tun = tun is not None and tun[0] - 1 < z < tun[1]
        # --- events
        if self.police is None and now > self.next_police and self.zoom_t is None:
            clear = tun is None or tun[0] - z > 200 or z > tun[1] + 20
            near_board = any(-20 < b_ - z < 60 for b_ in self.board_list)
            if clear and not near_board:
                self.police = now
        if self.police is not None and now - self.police > 13:
            self.police = None
            self.next_police = now + random.uniform(22, 32)
        police_t = None if self.police is None else now - self.police
        if self.zoom_t is None and self.police is None and now > self.next_zoom and not in_tun:
            ahead = [b_ for b_ in self.board_list if 55 < b_ - z < 160]
            if ahead and (tun is None or tun[0] > ahead[0] or tun[1] < z):
                self.zoom_t = now
                self.zoom_z0 = z
                self.bz = ahead[0]
                self.zoom_hit = False
                self.glitch.trigger(now, 0.15)
                self.callout = ("ACQUIRING BILLBOARD", now)
        zoom_u = None
        boost = 0.0
        if self.zoom_t is not None:
            zt = now - self.zoom_t
            boost = math.sin(min(1, zt / self.ZOOM_T) * math.pi * 0.5)
            if zt < self.ZOOM_T:
                zoom_u = zt / self.ZOOM_T
            elif zt < self.ZOOM_T + 0.08 and not self.zoom_hit:
                self.zoom_hit = True
                self.callout = ("BILLBOARD HIJACKED", now)
                self.flash = now
                self.glitch.trigger(now, 0.2)
                for _ in range(70):
                    ang = random.uniform(0, math.tau)
                    spd = random.uniform(15, 90)
                    self.parts.append([self.w / 2, self.ph / 2, math.cos(ang) * spd, math.sin(ang) * spd * 0.8,
                                       random.uniform(0.3, 0.9), 0.0, random.choice((PINK, WHITE, CYAN))])
            if zt > self.ZOOM_T + 0.6:
                self.zoom_t = None
                self.next_zoom = now + random.uniform(20, 28)
        chase = 0.0 if police_t is None else min(1.0, police_t / 1.5, max(0.0, (13 - police_t) / 1.5))
        if zoom_u is not None:
            # frame the whole panel, then punch through
            fit = max(BOARD_W * self.F / (0.62 * self.w), BOARD_H * self.F / (0.70 * self.ph)) + 3.0
            acquire = min(1.0, zoom_u / 0.66)
            acquire = acquire * acquire * (3 - 2 * acquire)
            nz = self.zoom_z0 + (self.bz - fit - self.zoom_z0) * acquire
            if zoom_u > 0.9:
                nz += (fit - 0.62 * fit) * ((zoom_u - 0.9) / 0.1) ** 2
            self.speed = max(15.0, (nz - z) / max(dt, 1e-3)) if dt > 0 else self.speed
            self.pos[2] = nz
        else:
            self.speed = 15 + chase * 6
            self.pos[2] += self.speed * dt
        self.dist += max(0.0, self.speed * dt)
        z = self.pos[2]
        # --- flight path
        alt = 17.5 + math.sin(t * 0.23) * 2.8 + math.sin(t * 0.09) * 1.6
        if tun is not None and tun[0] - 55 < z < tun[1] + 8:
            low = min(1.0, (z - tun[0] + 55) / 28.0) * (1.0 if z < tun[1] else max(0.0, 1 - (z - tun[1]) / 8.0))
            alt += (3.6 - alt) * low
        self.alt += (alt - self.alt) * min(1.0, dt * 1.8)
        cross = (z % PER)
        tunnel_clamp = 0.3 if tun is not None and tun[0] - 25 < z < tun[1] else 1.0
        dodge = chase * math.sin(t * 2.2) * 1.5
        self.pos[0] = (math.sin(t * 0.37) * 1.8 + dodge) * tunnel_clamp
        self.pos[1] = self.alt
        self.yaw = (math.sin(t * 0.41 + 0.6) * 0.10 + chase * math.cos(t * 2.2) * 0.05) * tunnel_clamp
        self.roll = (-math.cos(t * 0.41) * 0.10 - chase * math.cos(t * 2.2) * 0.14) * tunnel_clamp
        self.pitch = (0.02 + 0.0045 * max(0.0, self.alt - 4) + math.sin(t * 0.31 + 1.5) * 0.025)
        if zoom_u is not None:
            e = min(1.0, zoom_u * 2.2)
            e = e * e * (3 - 2 * e)
            cy_t = BOARD_Y0 + BOARD_H / 2
            self.pos[1] = self.alt = self.alt + (cy_t - self.alt) * e
            self.pos[0] *= 1 - e
            self.yaw *= 1 - e
            self.roll = self.roll * (1 - e) + random.uniform(-0.012, 0.012) * zoom_u
            dz = max(4.0, self.bz - z)
            self.pitch = self.pitch * (1 - e) + math.atan2(self.pos[1] - cy_t, dz) * e
        inside = tun is not None and tun[0] + 2 < z < tun[1] - 1 and self.pos[1] < TUN_H - 0.4
        tun_draw = tun if tun is not None and tun[0] - 320 < z else None
        if inside:
            self.pitch = 0.0
            self.pos[1] = min(self.pos[1], TUN_H - 1.0)
        # --- render
        # Very large screens redraw the 3D world every other frame (HUD, particles
        # and effects stay at full rate) to stay inside the 24 fps budget.
        self._wf = getattr(self, "_wf", 0) + 1
        if self.w * self.h <= 10000 or self._wf % 2 or getattr(self, "_world", None) is None:
            with np.errstate(all="ignore"):
                self.render_world(now, tun_draw, inside)
                self.finish(s, now, dt, police_t, inside, tun_draw)
            self._world = self.col.copy()
        else:
            self.col = self._world.copy()
        if self.flash is not None:
            ft = (now - self.flash) / 0.4
            if ft >= 1:
                self.flash = None
            else:
                self.col += np.array(blend(WHITE, PINK, ft), f32)[:, None, None] * ((1 - ft) * 0.35)
        self.draw_parts(dt)
        self.to_screen(s)
        self.board_text(s, now)
        self.sign_text(s)
        if zoom_u is not None and zoom_u > 0.15:
            self.zoom_lock(s, now, zoom_u)
        if self.flash is not None and (now - self.flash) < 0.28:
            self.htext(s, (s.w - 28) // 2, s.h // 2, " BILLBOARD HIJACKED // DEDSEC ", PINK, 0.3)
        self.hud(s, now, zoom_u is not None, police_t, inside)
        if random.random() < 0.004:
            self.callout = (random.choice(CALLOUTS), now)
        self.post_fx(s, now, glitch)

    def board_text(self, s, now):
        for bz_ in self.board_list:
            d = bz_ - self.pos[2]
            if not (5 < d < 160):
                continue
            a = self.proj((-BOARD_W / 2 + 2, BOARD_Y0 + 1.5, bz_))
            b = self.proj((BOARD_W / 2 - 2, BOARD_Y0 + 1.5, bz_))
            if not a or not b:
                continue
            x0, x1 = int(a[0]), int(b[0])
            y = int((a[1] + b[1]) / 4)
            label = "D E D S E C"
            if x1 - x0 >= len(label) + 4 and 1 <= y < s.h - 1:
                x = (x0 + x1) // 2 - len(label) // 2
                self.htext(s, x, y, label, (255, 235, 250), 0.35)

    def sign_text(self, s):
        for sg in self.sign_cache:
            side, z0, z1, v0, v1, neon, text = sg
            zc = (z0 + z1) / 2
            a = self.proj((side * (WF - 0.1), v1 - 0.3, z0))
            b = self.proj((side * (WF - 0.1), v0 + 0.3, z1))
            if not a or not b or a[2] > 70:
                continue
            xa, xb = sorted((int(a[0]), int(b[0])))
            ya, yb = sorted((int(a[1]) // 2, int(b[1]) // 2))
            if xb - xa >= len(text) + 1 and yb - ya >= 1 and 0 <= ya and yb < s.h and xa >= 0 and xb < s.w:
                y = (ya + yb) // 2
                x = (xa + xb) // 2 - len(text) // 2
                for i, ch in enumerate(text):
                    cx = x + i
                    if 0 <= cx < s.w:
                        s.bg[y][cx] = tuple(int(c * 0.28) for c in neon)
                        s.put(cx, y, ch, (255, 255, 255) if i % 2 == 0 else tuple(min(255, int(c * 1.1 + 40)) for c in neon))

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "pullback", "DRONE // RETURN TO HOME", CYAN)
        if .08 < t < .88:
            radius = max(2, int((1 - t) * min(s.w / 5, s.h / 3)))
            cx, cy = s.w // 2, s.h // 2
            s.text(cx - radius, cy, "[", blend(CYAN, BLACK, t))
            s.text(cx + radius, cy, "]", blend(CYAN, BLACK, t))
            if t > .4:
                s.text(cx - 4, cy + 1, "RTH LOCK", blend(CYAN, BLACK, t))

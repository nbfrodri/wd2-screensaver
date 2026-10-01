"""DRONE: FPV flight through a 3D San Francisco with live time of day, weather and police."""

import math
from functools import lru_cache
import random
import time

import numpy as np

from engine3d import NEAR, Camera, Starfield, clip2d
from lib import (BLACK, CYAN, DARK, DIM_CYAN, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, blend, pulse)
from sysdata import DATA
from widgets import Particles, edge_char

NAME = "DRONE"

CALLOUTS = ["TARGET ACQUIRED", "ctOS TOWER IN RANGE", "SIGNAL HIJACKED", "UPLOADING FOOTAGE",
            "BILLBOARD HACKED", "THERMAL SCAN", "AUTOPILOT OVERRIDE", "NUDLE MAPS SPOOFED"]

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
SKULL_PTS = [(c, r) for r, row in enumerate(SKULL) for c, px in enumerate(row) if px == "X"]

RED = (255, 30, 40)
BLUE = (40, 90, 255)
BRIDGE = (235, 75, 35)
TUNNEL = (120, 120, 140)


# ====================================================================== fast box renderer
# Shared with mode_profiler. Boxes are (x0, z0, x1, z1, y0, y1, col, windows?).
# Vertices: bottom 0..3 = (x0,z0) (x1,z0) (x1,z1) (x0,z1), top 4..7 the same.

F_Z0, F_Z1, F_X0, F_X1 = (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)
F_TOP, F_BOT = (4, 5, 6, 7), (3, 2, 1, 0)
_COMBO = {}


def face_combo(zs, xs, vs):
    """Visible faces + edges for a camera side combination (cached)."""
    key = (zs, xs, vs)
    if key not in _COMBO:
        faces = []
        if zs:
            faces.append(("front", F_Z0 if zs < 0 else F_Z1))
        if xs:
            faces.append(("side", F_X0 if xs < 0 else F_X1))
        if vs:
            faces.append(("top" if vs > 0 else "bot", F_TOP if vs > 0 else F_BOT))
        edges = {}
        for kind, f in faces:
            for i in range(4):
                e = tuple(sorted((f[i], f[(i + 1) % 4])))
                dim = kind == "side"
                edges[e] = edges.get(e, True) and dim
        _COMBO[key] = (faces, [(a, b, d) for (a, b), d in edges.items()])
    return _COMBO[key]


def view_np(cam, P):
    """World -> view coordinates for an (..., 3) array (same maths as Camera.to_view)."""
    cy_, sy_ = math.cos(-cam.yaw), math.sin(-cam.yaw)
    cp, sp = math.cos(-cam.pitch), math.sin(-cam.pitch)
    x = P[..., 0] - cam.pos[0]
    y = P[..., 1] - cam.pos[1]
    z = P[..., 2] - cam.pos[2]
    x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
    y, z = y * cp - z * sp, y * sp + z * cp
    if cam.roll:
        cr, sr = math.cos(-cam.roll), math.sin(-cam.roll)
        x, y = x * cr - y * sr, x * sr + y * cr
    return x, y, z


def seg(s, x0, y0, x1, y1, ch, col):
    """Clipped 2D segment written straight into the text layer."""
    w1, h1 = s.w - 1, s.h - 1
    # Most city edges are wholly visible or trivially outside. Avoid the
    # general clipper in those cases; crossing edges still use exact clipping.
    if max(x0, x1) < 0 or min(x0, x1) > w1 or max(y0, y1) < 0 or min(y0, y1) > h1:
        return
    if 0 <= x0 <= w1 and 0 <= x1 <= w1 and 0 <= y0 <= h1 and 0 <= y1 <= h1:
        t0, t1 = 0.0, 1.0
    else:
        c = clip2d(x0, y0, x1, y1, s.w, s.h)
        if not c:
            return
        t0, t1 = c
    dx, dy = x1 - x0, y1 - y0
    ax, ay = x0 + dx * t0, y0 + dy * t0
    bx, by = x0 + dx * t1, y0 + dy * t1
    n = int(max(abs(bx - ax), abs(by - ay))) + 1
    sx, sy = (bx - ax) / n, (by - ay) / n
    rc, rf = s.ch, s.fg
    w1, h1 = s.w - 1, s.h - 1
    for i in range(n + 1):
        x, y = int(ax + sx * i), int(ay + sy * i)
        if x > w1:
            x = w1
        if y > h1:
            y = h1
        rc[y][x] = ch
        rf[y][x] = col


@lru_cache(maxsize=2048)
def _fill_vectors(ch, bg, width):
    return [ch] * width, [bg] * width, [None] * width


def fill_conv(s, pts, bg, ch=" ", clear_px=True):
    """Convex polygon fill with row slices (edge walking); sets ch + bg, clears pixels."""
    h = s.h
    xs = [p[0] for p in pts]
    if max(xs) < 0 or min(xs) >= s.w:
        return
    ys = [p[1] for p in pts]
    y0, y1 = max(0, int(min(ys))), min(h - 1, int(max(ys)))
    if y1 < y0:
        return
    nrow = y1 - y0 + 1
    lo = [1e9] * nrow
    hi = [-1e9] * nrow
    for i in range(len(pts)):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        if ay > by:
            ax, ay, bx, by = bx, by, ax, ay
        # rows whose centre yc = y + 0.5 satisfies ay <= yc < by
        ra = max(y0, int(math.ceil(ay - 0.5)))
        rb = min(y1, int(math.ceil(by - 0.5)) - 1)
        if rb < ra:
            continue
        k = (bx - ax) / (by - ay)
        x = ax + (ra + 0.5 - ay) * k
        for r in range(ra - y0, rb - y0 + 1):
            if x < lo[r]:
                lo[r] = x
            if x > hi[r]:
                hi[r] = x
            x += k
    w1 = s.w - 1
    S_ch, S_bg, S_pt, S_pb = s.ch, s.bg, s.pt, s.pb
    for r in range(nrow):
        a, b = lo[r], hi[r]
        if b < a:
            continue
        xa = int(a) if a > 0 else 0
        xb = int(b) if b < w1 else w1
        if xb < xa:
            continue
        y = y0 + r
        k = xb - xa + 1
        chars, colors, empty = _fill_vectors(ch, bg, k)
        S_ch[y][xa:xb + 1] = chars
        S_bg[y][xa:xb + 1] = colors
        if clear_px:
            S_pt[y][xa:xb + 1] = S_pb[y][xa:xb + 1] = empty


def clip_poly_near(vs):
    """Sutherland-Hodgman clip of a view-space polygon against z >= NEAR."""
    out = []
    n = len(vs)
    for i in range(n):
        a, b = vs[i - 1], vs[i]
        ina, inb = a[2] >= NEAR, b[2] >= NEAR
        if inb:
            if not ina:
                t = (NEAR - a[2]) / (b[2] - a[2])
                out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
            out.append(b)
        elif ina:
            t = (NEAR - a[2]) / (b[2] - a[2])
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    return out


SKULL_NP = np.array([[px == "X" for px in row] for row in SKULL])


def raster_board(s, tl, tr, bl, bg, fg):
    """Affine raster of the skull board; tl/tr/bl are projected corners (cell coords)."""
    ox, oy = tl[0], tl[1] * 2
    ex, ey = tr[0] - ox, tr[1] * 2 - oy
    fx, fy = bl[0] - ox, bl[1] * 2 - oy
    det = ex * fy - ey * fx
    if abs(det) < 1e-6:
        return
    xs = (ox, ox + ex, ox + fx, ox + ex + fx)
    ys = (oy, oy + ey, oy + fy, oy + ey + fy)
    x0, x1 = max(0, int(min(xs))), min(s.w - 1, int(max(xs)))
    y0, y1 = max(0, int(min(ys))), min(s.ph - 1, int(max(ys)))
    if x1 < x0 or y1 < y0:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5 - ox, np.arange(y0, y1 + 1) + 0.5 - oy)
    u = (gx * fy - gy * fx) / det
    v = (ex * gy - ey * gx) / det
    inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
    rows, cols = SKULL_NP.shape
    r = ((v - 0.1) / 0.8 * rows).astype(int)
    c = ((u - 0.1) / 0.8 * cols).astype(int)
    ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
    sk = np.zeros_like(inside)
    sk[ok] = SKULL_NP[r[ok], c[ok]]
    val = inside.astype(np.int8) + (inside & sk)
    V = val.tolist()
    cols_ = (None, bg, fg)
    for j, row in enumerate(V):
        py = y0 + j
        layer = (s.pb if py & 1 else s.pt)[py >> 1]
        rc = s.ch[py >> 1]
        for i, k in enumerate(row):
            if k:
                layer[x0 + i] = cols_[k]
                rc[x0 + i] = " "


class BoxCity:
    """Procedural city like engine3d.City, rendered with numpy projection + slice fills."""

    def __init__(self, block=8.0, street=4.0, seed=0, hscale=1.0):
        self.block, self.street = block, street
        self.cell = block + street
        self.seed, self.hscale = seed, hscale
        self.cache = {}
        self.wcache = {}
        self.colcache = {}

    def buildings(self, gx, gz):
        key = (gx, gz)
        if key not in self.cache:
            r = random.Random(gx * 73856093 ^ gz * 19349663 ^ self.seed)
            out = []
            n = r.choice((1, 2, 2, 4))
            sub = self.block / (2 if n > 1 else 1)
            for i in range(n):
                ox, oz = (i % 2) * sub, (i // 2) * sub
                h = (r.uniform(2, 14) if r.random() < 0.85 else r.uniform(16, 30)) * self.hscale
                x0 = gx * self.cell + ox + 0.4
                z0 = gz * self.cell + oz + 0.4
                out.append((x0, z0, x0 + sub - 0.8, z0 + (sub if n == 4 else self.block) - 0.8, 0.0, h,
                            r.choice((CYAN, CYAN, PINK, PURPLE)), True))
            self.cache[key] = out
            if len(self.cache) > 3000:
                self.cache.clear()
                self.wcache.clear()
        return self.cache[key]

    def windows(self, b, fi, face):
        key = (b[0], b[1], b[5], fi)
        if key not in self.wcache:
            r = random.Random(int(b[0] * 7 + b[1] * 13) + fi)
            x0, z0, x1, z1 = b[0], b[1], b[2], b[3]
            corners = ((x0, z0), (x1, z0), (x1, z1), (x0, z1))
            a, c = corners[face[0]], corners[face[1]]
            span = max(1, int(math.dist(a, c) * 1.5))
            pts, base = [], []
            for wy in range(1, int(b[5]), 2):
                for wx in range(1, span):
                    if r.random() < 0.4:
                        t = wx / span
                        pts.append((a[0] + (c[0] - a[0]) * t, wy + 0.5, a[1] + (c[1] - a[1]) * t))
                        base.append((r.random(), wx * 3 + wy))
            self.wcache[key] = (np.array(pts, dtype=float).reshape(-1, 3), base)
        return self.wcache[key]

    @staticmethod
    @lru_cache(maxsize=4096)
    def corners(b):
        x0, z0, x1, z1, y0, y1 = b[:6]
        return ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))

    def fogged(self, col, q, fog_col, k=1.0):
        key = (col, q, fog_col, k)
        c = self.colcache.get(key)
        if c is None:
            c = blend(col, fog_col, min(0.94, q / 12 * k))
            if len(self.colcache) > 6000:
                self.colcache.clear()
            self.colcache[key] = c
        return c

    def draw(self, s, cam, boxes, fog=80.0, theme=None, extras=(), win_dist=36.0, tick=0.0):
        """Painter's draw of boxes plus extra drawables [(dist2, fn(s))], far to near."""
        th = theme or {}
        fog_col = th.get("fog", BLACK)
        faces_c = th.get("front", (10, 6, 20)), th.get("side", (6, 4, 14)), th.get("top", (16, 10, 30))
        edge_k = th.get("edge_k", 1.0)
        lit_p = th.get("lit", 0.45)
        lit_c, dark_c = th.get("lit_col", YELLOW), th.get("win_col", DIM_CYAN)
        n = len(boxes)
        items = list(extras)
        if n:
            V = np.array([self.corners(b) for b in boxes], dtype=float)
            vx, vy, vz = view_np(cam, V)
            zc = np.maximum(vz, NEAR)
            sx = cam.cx + vx / zc * (cam.f * 2)
            sy = cam.cy - vy / zc * cam.f
            zmin, zmax = vz.min(axis=1), vz.max(axis=1)
            fast = zmin >= NEAR
            off = fast & ((sx.max(axis=1) < 0) | (sx.min(axis=1) >= s.w) | (sy.max(axis=1) < 0) | (sy.min(axis=1) >= s.h))
            keep = (zmax >= NEAR) & (zmin < fog) & ~off
            SX, SY, VZ = sx.tolist(), sy.tolist(), vz.tolist()
            VX, VY = vx.tolist(), vy.tolist()
            FAST = fast.tolist()
            ZC = vz.mean(axis=1).tolist()
            px, py, pz = cam.pos
            win_jobs = []
            for i in np.nonzero(keep)[0].tolist():
                b = boxes[i]
                cx_, cz_ = (b[0] + b[2]) / 2 - px, (b[1] + b[3]) / 2 - pz
                d2 = cx_ * cx_ + cz_ * cz_
                items.append((d2, i))
                if b[7] and d2 < win_dist * win_dist:
                    win_jobs.append(i)
            # windows of near buildings: one batched projection
            wslices = {}
            if win_jobs:
                arrs, meta, o = [], [], 0
                for i in win_jobs:
                    b = boxes[i]
                    zs = -1 if pz < b[1] else (1 if pz > b[3] else 0)
                    xs = -1 if px < b[0] else (1 if px > b[2] else 0)
                    for fi, face in ((0, F_Z0) if zs < 0 else (1, F_Z1) if zs > 0 else (None, None),
                                     (2, F_X0) if xs < 0 else (3, F_X1) if xs > 0 else (None, None)):
                        if face is None:
                            continue
                        P, base = self.windows(b, fi, face)
                        if len(base):
                            arrs.append(P)
                            meta.append((i, o, base))
                            o += len(base)
                if arrs:
                    wx_, wy_, wz_ = view_np(cam, np.concatenate(arrs))
                    ok = wz_ >= NEAR
                    wzc = np.maximum(wz_, NEAR)
                    wsx = (cam.cx + wx_ / wzc * (cam.f * 2)).astype(int)
                    wsy = (cam.cy - wy_ / wzc * cam.f).astype(int)
                    ok &= (wsx >= 0) & (wsx < s.w) & (wsy >= 0) & (wsy < s.h)
                    WSX, WSY, OK = wsx.tolist(), wsy.tolist(), ok.tolist()
                    for i, o0, base in meta:
                        wslices.setdefault(i, []).append((o0, base))
        items.sort(key=lambda it: -it[0])
        rc, rf = s.ch, s.fg
        for d2, it in items:
            if not isinstance(it, int):
                it(s)
                continue
            b = boxes[it]
            x0, z0, x1, z1, y0, y1, col = b[:7]
            px, py, pz = cam.pos
            faces, edges = face_combo(-1 if pz < z0 else (1 if pz > z1 else 0),
                                      -1 if px < x0 else (1 if px > x1 else 0),
                                      1 if py > y1 else (-1 if py < y0 else 0))
            q = min(12, max(0, int(ZC[it] / fog * 12)))
            ecol = self.fogged(blend(col, BLACK, 0.28), q, fog_col, edge_k)
            dcol = self.fogged(blend(col, BLACK, 0.58), q, fog_col, edge_k)
            fcols = th.get("box_faces", {}).get(col, faces_c)
            if FAST[it]:
                X, Y = SX[it], SY[it]
                for kind, f in faces:
                    fc = fcols[0] if kind == "front" else fcols[1] if kind == "side" else fcols[2]
                    fill_conv(s, [(X[k], Y[k]) for k in f], self.fogged(blend(fc, col, 0.10), q, fog_col))
                # Courses, mullions and roof seams belong to each projected face.
                # Skip distant/subcell faces rather than laying noise over the camera.
                if b[7] and d2 < 900:
                    for kind, face in faces:
                        A, B, C, D = [(X[k], Y[k]) for k in face]
                        width = math.dist(A, B)
                        height = math.dist(B, C)
                        if width < 7 or height < 4:
                            continue
                        tc = self.fogged(blend(col, BLACK, 0.78), q, fog_col)
                        if kind == "top":
                            for u in (0.25, 0.65):
                                seg(s, A[0]+(B[0]-A[0])*u, A[1]+(B[1]-A[1])*u,
                                    D[0]+(C[0]-D[0])*u, D[1]+(C[1]-D[1])*u, ":", tc)
                        else:
                            floors = min(10, max(2, int(height / 3)), max(2, int((y1-y0)/2)))
                            for j in range(1, floors):
                                u = j/floors
                                seg(s, A[0]+(D[0]-A[0])*u, A[1]+(D[1]-A[1])*u,
                                    B[0]+(C[0]-B[0])*u, B[1]+(C[1]-B[1])*u, "-", tc)
                            for u in (0.25, 0.5, 0.75):
                                seg(s, A[0]+(B[0]-A[0])*u, A[1]+(B[1]-A[1])*u,
                                    D[0]+(C[0]-D[0])*u, D[1]+(C[1]-D[1])*u, ":", tc)
                for a, bb, dim in edges:
                    xa, ya, xb, yb = X[a], Y[a], X[bb], Y[bb]
                    seg(s, xa, ya, xb, yb, edge_char(xb - xa, yb - ya), dcol if dim else ecol)
            else:
                Vv = list(zip(VX[it], VY[it], VZ[it]))
                f2 = cam.f * 2
                ccx, ccy, f1 = cam.cx, cam.cy, cam.f
                for kind, f in faces:
                    poly = clip_poly_near([Vv[k] for k in f])
                    if len(poly) >= 3:
                        fc = fcols[0] if kind == "front" else fcols[1] if kind == "side" else fcols[2]
                        fill_conv(s, [(ccx + p[0] / p[2] * f2, ccy - p[1] / p[2] * f1) for p in poly],
                                  self.fogged(blend(fc, col, 0.10), q, fog_col))
                for a, bb, dim in edges:
                    va, vb = Vv[a], Vv[bb]
                    if va[2] < NEAR and vb[2] < NEAR:
                        continue
                    if va[2] < NEAR or vb[2] < NEAR:
                        if va[2] < NEAR:
                            va, vb = vb, va
                        t = (va[2] - NEAR) / (va[2] - vb[2])
                        vb = tuple(va[k] + (vb[k] - va[k]) * t for k in range(3))
                    xa, ya = ccx + va[0] / va[2] * f2, ccy - va[1] / va[2] * f1
                    xb, yb = ccx + vb[0] / vb[2] * f2, ccy - vb[1] / vb[2] * f1
                    seg(s, xa, ya, xb, yb, edge_char(xb - xa, yb - ya), dcol if dim else ecol)
            ws = wslices.get(it) if n else None
            if ws:
                lcs = [self.fogged(c, q, fog_col, 0.8) for c in th.get("lit_cols", (lit_c,))]
                nl = len(lcs)
                dc = self.fogged(blend(dark_c, BLACK, 0.55), q, fog_col)
                tk = int(tick)
                for o0, base in ws:
                    for j, (rv, ph) in enumerate(base):
                        k = o0 + j
                        if OK[k] and (s.h >= 40 or ph % 3 == 0):
                            lit = rv < lit_p or (lit_p > 0.2 and (tk + ph) % 11 == 0)
                            y_, x_ = WSY[k], WSX[k]
                            rc[y_][x_] = "▪"
                            rf[y_][x_] = lcs[ph % nl] if lit else dc
        return items


class FastFX:
    """widgets.PostFX look (scan band + glitch tearing) with cached colour blends."""

    def __init__(self, band_speed=7.0):
        self.band_speed = band_speed
        self.cache = {}

    def tint(self, s, y, col, t):
        if not 0 <= y < s.h:
            return
        cache = self.cache
        get = cache.get
        for layer in (s.fg, s.pt, s.pb, s.bg):
            row = layer[y]
            for x, c in enumerate(row):
                if c is not None:
                    k = (c, col, t)
                    v = get(k)
                    if v is None:
                        v = cache[k] = blend(c, col, t)
                    row[x] = v

    def apply(self, s, now, glitch=False):
        if len(self.cache) > 30000:
            self.cache.clear()
        span = s.h + 16
        by = int((now * self.band_speed) % span) - 8
        for k, t in ((0, 0.45), (-1, 0.25), (1, 0.25), (-2, 0.1)):
            self.tint(s, by + k, WHITE, t)
        if glitch:
            for _ in range(random.randint(2, 5)):
                y0 = random.randrange(s.h)
                dx = random.randint(-14, 14)
                col = random.choice((PINK, CYAN))
                for y in range(y0, min(s.h, y0 + random.randint(1, 4))):
                    s.shift_row(y, dx)
                    self.tint(s, y, col, 0.5)
            if random.random() < 0.3:
                s.noise_lines(2)


# ====================================================================== time of day

# keyframes over DATA.daylight(): night, dusk/dawn, day
THEMES = [
    (0.0, {"sky_top": (12, 3, 30), "sky_hor": (115, 22, 105), "ground_far": (45, 12, 55), "ground": (8, 4, 14),
           "front": (12, 8, 26), "side": (7, 5, 16), "top": (20, 12, 38), "fog": (55, 12, 65),
           "edge_k": 1.0, "lit": 0.45, "lit_col": YELLOW, "win_col": DIM_CYAN, "sun": (230, 230, 255)}),
    (0.28, {"sky_top": (40, 20, 90), "sky_hor": (255, 120, 50), "ground_far": (90, 45, 50), "ground": (20, 10, 22),
            "front": (60, 30, 55), "side": (38, 18, 40), "top": (80, 45, 70), "fog": (190, 90, 70),
            "edge_k": 0.9, "lit": 0.25, "lit_col": (255, 200, 90), "win_col": (120, 60, 70), "sun": (255, 150, 60)}),
    (0.7, {"sky_top": (40, 110, 200), "sky_hor": (175, 205, 235), "ground_far": (120, 125, 140), "ground": (60, 62, 72),
           "front": (110, 120, 145), "side": (80, 88, 110), "top": (140, 150, 170), "fog": (170, 195, 225),
           "edge_k": 0.85, "lit": 0.05, "lit_col": (255, 240, 180), "win_col": (165, 200, 230), "sun": (255, 250, 220)}),
]


def theme_at(d, cloudy=False):
    for (d0, a), (d1, b) in zip(THEMES, THEMES[1:]):
        if d <= d1:
            t = (d - d0) / (d1 - d0)
            break
    else:
        a = b = THEMES[-1][1]
        t = 0.0
    th = {}
    for k, v in a.items():
        th[k] = blend(v, b[k], t) if isinstance(v, tuple) else v + (b[k] - v) * t
    if cloudy:
        for k in ("sky_top", "sky_hor", "fog"):
            g = sum(th[k]) // 3
            th[k] = blend(th[k], (g, g, g + 8), 0.55)
    th["day"] = d
    if d < 0.15:
        th["lit_cols"] = (th["lit_col"], th["lit_col"], (255, 230, 170), PINK, CYAN)
    return th


# ====================================================================== mode

class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = Camera(w, h, fov=0.85)
        self.city = BoxCity()
        self.stars = Starfield(w, h, n=70, colors=(PURPLE, CYAN, WHITE))
        self.stars.cam = self.cam
        self.glitch = Glitch(0.01)
        self.fx = FastFX(band_speed=11)
        self.particles = Particles()
        self.last = time.time()
        self.t0 = self.last
        cell = self.city.cell
        self.lane = cell - self.city.street / 2
        self.cam.pos = [self.lane, 6.0, 0.0]
        self.speed = 14.0
        self.zoom_t = None
        self.next_zoom = self.last + random.uniform(8, 14)
        self.callout = (random.choice(CALLOUTS), self.last)
        self.board_z = None
        self.dist = 0.0
        self.battery = random.uniform(70, 99)
        self.alt = 6.0
        # weather: live if known, else rain on ~25% of runs
        self.rain = bool(DATA.weather["rain"]) if DATA.weather else random.random() < 0.25
        self.weather_check = self.last + 5
        self.drops = [[random.uniform(0, w), random.uniform(0, h), random.uniform(0.6, 1.4)] for _ in range(int(w * 0.7))]
        self.theme_t = 0
        self.theme = None
        # set pieces
        self.tunnel = None      # (z_start, z_end)
        self.bridge = None      # z centre
        self.police = None      # start time
        self.next_piece = self.last + random.uniform(6, 12)
        self.next_police = self.last + random.uniform(14, 26)
        self.refl_cache = {}

    # ------------------------------------------------------------ environment
    def update_theme(self, now):
        if now > self.theme_t:
            self.theme_t = now + 2
            wx = DATA.weather
            if wx is not None and now > self.weather_check:
                self.rain = bool(wx.get("rain"))
                self.weather_check = now + 60
            self.theme = theme_at(DATA.daylight(), cloudy=bool(wx and (wx.get("clouds") or wx.get("rain"))) or self.rain)
            if self.rain:
                self.theme["ground"] = blend(self.theme["ground"], BLACK, 0.4)
            self.fog_dist = 55.0 if wx and wx.get("fog") else 80.0
            self.refl_cache = {}

    def sky(self, s, now):
        th, cam = self.theme, self.cam
        hy = int(max(1, min(self.h - 1, cam.cy - math.tan(cam.pitch) * cam.f)))
        self.hy = hy
        s.gradient_bg(th["sky_top"], th["sky_hor"], 0, hy)
        s.gradient_bg(th["ground_far"], th["ground"], hy, self.h)
        self.ground_rows = {y: s.bg[y][0] for y in range(hy, self.h)}
        d = th["day"]
        # sun / moon, roughly anchored to the world heading
        sx = self.w * 0.68 - cam.yaw * cam.f * 2
        if d > 0.08:
            sy = (hy - d * hy * 0.85) * 2
            r = 3 + self.h * 0.07 * (1.3 - d)
            glow = blend(th["sun"], th["sky_hor"], 0.6)
            s.pixel_circle(sx, sy, r * 1.6, glow)
            s.pixel_circle(sx, sy, r, th["sun"])
        else:
            s.pixel_circle(self.w * 0.22 - cam.yaw * cam.f * 2, hy * 0.5, 3.2, (220, 220, 240))
            s.pixel_circle(self.w * 0.22 - cam.yaw * cam.f * 2 + 1.6, hy * 0.5 - 1, 2.6, th["sky_top"])

    def reflections(self, s, now):
        """Wet street: mirror the scene above the horizon into empty ground cells."""
        hy, h, w = self.hy, self.h, self.w
        gnd = self.theme["ground"]
        cache = self.refl_cache
        rows = self.ground_rows
        for y in range(hy + 1, h):
            sy = 2 * hy - y
            if sy < 0:
                break
            g = rows[y]
            rc, rbg, rt, rb = s.ch[y], s.bg[y], s.pt[y], s.pb[y]
            src_c, src_f, src_b = s.ch[sy], s.fg[sy], s.bg[sy]
            q = min(7, (y - hy) * 8 // max(1, h - hy))
            dx = int(math.sin(y * 1.7 + now * 5) * 1.5)
            for x in range(w):
                if rbg[x] is not g or rc[x] != " " or rt[x] is not None or rb[x] is not None:
                    continue
                xs = x + dx
                if not 0 <= xs < w:
                    continue
                src = src_f[xs] if src_c[xs] != " " else src_b[xs]
                if src is None:
                    continue
                key = (src, q)
                c = cache.get(key)
                if c is None:
                    c = cache[key] = blend(src, gnd, 0.45 + q * 0.07)
                rbg[x] = c

    def rain_fx(self, s, dt):
        col = blend(self.theme["sky_hor"], (150, 170, 220), 0.6)
        col2 = blend(col, BLACK, 0.45)
        slant = self.cam.roll * 1.5 + 0.35
        ch = "/" if slant > 0.15 else ("\\" if slant < -0.15 else "│")
        sp = self.speed / 14
        for d in self.drops:
            d[1] += (38 + 20 * sp) * d[2] * dt
            d[0] -= slant * 30 * d[2] * dt
            if d[1] >= self.h:
                if random.random() < 0.3:
                    s.put(int(d[0]), self.h - 1 - random.randint(0, 4), "·", col2)
                d[0], d[1] = random.uniform(-5, self.w + 5), random.uniform(-6, 0)
            x, y = int(d[0]), int(d[1])
            s.put(x, y, ch, col if d[2] > 1 else col2)
            s.put(x + (1 if slant > 0.15 else -1 if slant < -0.15 else 0), y - 1, ch, col2)

    # ------------------------------------------------------------ set pieces
    def plan_pieces(self, now):
        z = self.cam.pos[2]
        if self.tunnel and z > self.tunnel[1] + 4:
            self.tunnel = None
        if self.bridge and z > self.bridge + 40:
            self.bridge = None
        if now > self.next_piece and not self.tunnel and not self.bridge:
            if random.random() < 0.5:
                start = z + 110
                self.tunnel = (start, start + random.choice((60, 80, 100)))
            else:
                self.bridge = z + 150
            self.next_piece = now + random.uniform(16, 26)
        if self.police is None and now > self.next_police:
            self.police = now
            self.callout = ("POLICE DRONE // EVADE", now)
            self.glitch.trigger(now, 0.3)
        if self.police is not None and now - self.police > 13:
            self.police = None
            self.next_police = now + random.uniform(25, 45)

    def blocked(self, b):
        if self.bridge is not None and b[3] > self.bridge - 24 and b[1] < self.bridge + 24:
            return True
        return False

    def bridge_parts(self, now, th):
        zb = self.bridge
        boxes = []
        dk = blend(BRIDGE, BLACK, 0.55 if th["day"] < 0.3 else 0.25)
        faces = (dk, blend(dk, BLACK, 0.3), blend(dk, WHITE, 0.15))
        self.city_faces[BRIDGE] = faces
        boxes.append((-70.0, zb - 1.6, 90.0, zb + 1.6, 12.0, 13.0, BRIDGE, False))
        towers = (self.lane - 22, self.lane + 22)
        for tx in towers:
            for dz in (-1.5, 1.1):
                boxes.append((tx - 0.5, zb + dz - 0.2, tx + 0.5, zb + dz + 0.6, 0.0, 40.0, BRIDGE, False))
            for yb in (24.0, 34.0, 39.0):
                boxes.append((tx - 0.45, zb - 1.5, tx + 0.45, zb + 1.7, yb, yb + 0.8, BRIDGE, False))

        def cables(s):
            cam = self.cam
            fog = self.fog_dist * 2
            col = blend(BRIDGE, WHITE, 0.15)
            for side in (-1.6, 1.6):
                z = zb + side
                pts = []
                a, b = towers
                for i in range(25):
                    t = i / 24
                    x = a + (b - a) * t
                    pts.append((x, 13.5 + 26 * (2 * t - 1) ** 2, z))
                for p0, p1 in zip(pts, pts[1:]):
                    cam.line(s, p0, p1, col, fog=fog)
                for p in pts[2:-2:2]:
                    cam.line(s, p, (p[0], 13.0, z), blend(col, BLACK, 0.4), fog=fog, char="│")
                for x_end, tx in ((a - 40, a), (b + 40, b)):
                    for i in range(8):
                        t0, t1 = i / 8, (i + 1) / 8
                        q0 = (tx + (x_end - tx) * t0, 13 + 26 * (1 - t0) ** 2, z)
                        q1 = (tx + (x_end - tx) * t1, 13 + 26 * (1 - t1) ** 2, z)
                        cam.line(s, q0, q1, col, fog=fog)
            # water under the span
            for k in range(-4, 5):
                zz = zb + k * 5 + (now * 2) % 5
                cam.line(s, (self.lane - 30, 0.05, zz), (self.lane + 30, 0.05, zz),
                         blend(CYAN, BLACK, 0.5), fog=fog, char="~")

        dz = zb - self.cam.pos[2]
        return boxes, (dz * dz, cables)

    TUN_HW, TUN_TOP = 2.0, 7.5

    def tunnel_parts(self, now, th):
        """Concrete tube filling the street; returns (inside, boxes, extras)."""
        z0, z1 = self.tunnel
        cz = self.cam.pos[2]
        if z0 <= cz <= z1:
            return True, [], []
        if cz > z1:
            return False, [], []
        wall = blend(th["front"], (90, 90, 110), 0.25)
        self.city_faces[TUNNEL] = (wall, blend(wall, BLACK, 0.3), blend(wall, WHITE, 0.1))
        box = (7.6, z0, 12.4, z1, 0.0, 10.5, TUNNEL, False)
        dz = z0 - cz
        return False, [box], [(dz * dz * 0.98, lambda s: self.tunnel_view(s, now, False))]

    def tunnel_view(self, s, now, inside):
        z0, z1 = self.tunnel
        cam = self.cam
        cz = cam.pos[2]
        hw, top, lx = self.TUN_HW, self.TUN_TOP, self.lane
        fog = self.fog_dist
        th = self.theme
        wall = blend(th["front"], BLACK, 0.3)
        if inside:
            blank = [" "] * self.w
            for y in range(self.h):
                s.ch[y] = blank[:]
                s.bg[y] = [wall] * self.w
                s.pt[y] = [None] * self.w
                s.pb[y] = [None] * self.w
            # light at the end of the tunnel
            ze = z1
            if ze - cz < fog * 1.5:
                q = [cam.project(p) for p in ((lx - hw, 0, ze), (lx + hw, 0, ze), (lx + hw, top, ze), (lx - hw, top, ze))]
                if all(q):
                    fill_conv(s, [(p[0], p[1]) for p in q], blend(th["fog"], WHITE, 0.35))
        else:
            q = [cam.project(p) for p in ((lx - hw, 0, z0), (lx + hw, 0, z0), (lx + hw, top, z0), (lx - hw, top, z0))]
            if all(q):
                fill_conv(s, [(p[0], p[1]) for p in q], wall)
        k0 = max(0, int((cz - z0) / 4) + 1)
        nk = int((z1 - z0) / 4)
        kmax = min(nk, k0 + int(fog / 4))
        tick = int(now * 8)
        for k in range(kmax, k0 - 1, -1):
            z = z0 + k * 4
            if z - cz < 0.3:
                continue
            col = (PINK, CYAN, PURPLE)[k % 3] if 0 < k < nk else YELLOW
            c = ((lx - hw, 0, z), (lx + hw, 0, z), (lx + hw, top, z), (lx - hw, top, z))
            for i in range(4):
                cam.line(s, c[i], c[(i + 1) % 4], col, fog=fog)
            if (tick + k) % 4 == 0:
                cam.point(s, (lx, top - 0.3, z), "●", WHITE, fog=fog)
        zs, ze = max(z0, cz + 0.4), min(z1, cz + fog)
        if ze > zs:
            for x, y in ((lx - hw, 0), (lx + hw, 0), (lx - hw, top), (lx + hw, top)):
                cam.line(s, (x, y, zs), (x, y, ze), DIM_CYAN, fog=fog)
            for x in (lx - hw + 0.1, lx + hw - 0.1):  # strip lights rushing past
                zz = math.floor(zs / 2) * 2 + 2
                while zz < min(ze, zs + 30):
                    cam.line(s, (x, top * 0.55, zz), (x, top * 0.55, zz + 0.8), YELLOW, fog=30)
                    zz += 2
        if not inside and all(q):
            for i in range(4):
                seg(s, q[i][0], q[i][1], q[i - 1][0], q[i - 1][1], "█" if i % 2 else "▀", YELLOW)

    def police_pos(self, now):
        t = now - self.police
        cam = self.cam
        if t < 3:
            rel = (math.sin(t * 2) * 1.0, -1.5, -8 + t)
        elif t < 5.5:
            u = (t - 3) / 2.5
            rel = (math.sin(t * 2) * 1.2, -1.5 + u * 3.2, -5 + u * u * 27)
        elif t < 11:
            rel = (math.sin(t * 1.3) * 2.4, 1.7 + math.sin(t * 2.1) * 0.8, 22 + math.sin(t * 0.7) * 3)
        else:
            u = (t - 11) / 2
            rel = (math.sin(t * 1.3) * 2.4, 1.7 + u * u * 18, 22 + u * 25)
        return t, (cam.pos[0] + rel[0], cam.pos[1] + rel[1], cam.pos[2] + rel[2]), rel[2]

    def police_draw(self, now):
        t, p, rz = self.police_pos(now)
        cam = self.cam

        def draw(s):
            fog = 90
            red_on = int(now * 8) % 2 == 0
            x, y, z = p
            for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                cam.line(s, (x, y, z), (x + dx * 1.1, y + 0.15, z + dz * 1.1), GREY, fog=fog)
                spin = "─" if int(now * 20 + dx) % 2 else "│"
                cam.point(s, (x + dx * 1.1, y + 0.25, z + dz * 1.1), "═" if spin == "─" else "╪", WHITE, fog=fog)
            cam.point(s, (x, y, z), "█", (30, 30, 50), fog=fog)
            cam.point(s, (x - 0.35, y + 0.35, z), "●", RED if red_on else blend(RED, BLACK, 0.7), fog=fog)
            cam.point(s, (x + 0.35, y + 0.35, z), "●", blend(BLUE, BLACK, 0.7) if red_on else BLUE, fog=fog)
            if 5.5 < t < 11:
                # sweeping searchlight onto the street ahead
                gx = x + math.sin(now * 1.7) * 3
                for k in range(3):
                    cam.line(s, (x, y - 0.3, z), (gx + k - 1, 0, z - 6), blend(WHITE, BLACK, 0.55), fog=fog, char="·")
                q = cam.project((x, y, z))
                if q and 0 <= q[0] < s.w:
                    s.text(int(q[0]) + 3, int(q[1]) - 1, "SFPD-%02d" % (int(self.police) % 97), RED if red_on else BLUE)
        dz = rz
        return t, (dz * dz, draw)

    def billboard(self, s, now):
        """A giant DedSec skull billboard over the street, rasterised in half-block pixels."""
        cx, cy = self.lane, 12.0
        w2, h2 = 11.0, 8.0
        z = self.board_z
        cam = self.cam
        col = blend(PINK, PURPLE, pulse(now, 3))
        corners = [(cx - w2, cy - h2, z), (cx + w2, cy - h2, z), (cx + w2, cy + h2, z), (cx - w2, cy + h2, z)]
        cam.line(s, (cx - w2 * 0.6, 0, z), (cx - w2 * 0.6, cy - h2, z), GREY, fog=150)
        cam.line(s, (cx + w2 * 0.6, 0, z), (cx + w2 * 0.6, cy - h2, z), GREY, fog=150)
        pts = [cam.project(c) for c in corners]
        if all(pts):
            fog = min(0.85, pts[0][2] / 150)
            raster_board(s, pts[3], pts[2], pts[0], blend(blend(col, BLACK, 0.8), BLACK, fog),
                         blend(blend(WHITE, PINK, 0.25 + 0.2 * pulse(now, 7)), BLACK, fog))
        for i in range(4):
            cam.line(s, corners[i], corners[(i + 1) % 4], col, fog=150)

    # ------------------------------------------------------------ HUD
    def hud(self, s, now, boost, police_t):
        w, h = self.w, self.h
        cx, cy = w // 2, h // 2
        small = h < 32
        roll = self.cam.roll
        ladder = 5 if small else 6
        for k in (-2, -1, 1, 2):
            off = k * ladder + self.cam.pitch * 30
            for i in range(-14, 15):
                if abs(i) < 4:
                    continue
                x = cx + i * math.cos(roll) - off * math.sin(roll) * 2
                y = cy + i * math.sin(roll) * 0.5 + off * math.cos(roll)
                s.put(int(x), int(y), "─", DIM_CYAN)
            s.text(int(cx + 16 - off * math.sin(roll) * 2), int(cy + off * math.cos(roll)), "%+d" % (-k * 10), DIM_CYAN)
        s.text(cx - 6, cy, "──┤", GREEN)
        s.text(cx + 4, cy, "├──", GREEN)
        s.put(cx, cy, "◇", GREEN if not boost else PINK)
        bh = 11 if small else 17
        s.brackets(cx - 20, cy - bh // 2, 41, bh, blend(GREEN, BLACK, 0.4), arm=3)
        alt = self.cam.pos[1] * 3.2
        spd = self.speed * 3.6
        tape = 4 if small else 6
        for i in range(-tape, tape + 1):
            s.text(3, cy + i, ("%4d ─" % (int(alt) + i * 5)) if i % 2 == 0 else "     ·", GREY if i else WHITE)
            s.text(w - 10, cy + i, ("─ %4d" % (int(spd) - i * 10)) if i % 2 == 0 else "·", GREY if i else WHITE)
        s.text(2, cy - tape - 2, "ALT m", CYAN)
        s.text(w - 9, cy - tape - 2, "SPD km/h", CYAN)
        s.text(2, 0, "DEDSEC // QUADCOPTER #04  ● LIVE", PINK if int(now * 2) % 2 else WHITE)
        self.battery = max(5, self.battery - 0.002)
        bat = "BAT [" + "█" * int(self.battery / 10) + "░" * (10 - int(self.battery / 10)) + "] %d%%" % self.battery
        s.text(w - len(bat) - 2, 0, bat, GREEN if self.battery > 30 else PINK)
        hd = int(math.degrees(self.cam.yaw)) % 360
        comp = "".join("N" if (hd + i) % 360 == 0 else "E" if (hd + i) % 360 == 90 else "S" if (hd + i) % 360 == 180
                       else "W" if (hd + i) % 360 == 270 else ("|" if (hd + i) % 10 == 0 else "·") for i in range(-20, 21))
        s.center(1, comp, GREY)
        s.center(2, "▼ %03d°" % hd, WHITE)
        # environment readout
        th = self.theme
        hr = DATA.hour()
        wx = DATA.weather
        env = "%02d:%02d LOCAL  //  %s" % (int(hr), int(hr * 60) % 60,
                                          "RAIN" if self.rain else ("FOG" if wx and wx.get("fog") else
                                                                    "NIGHT" if th["day"] < 0.1 else "DUSK" if th["day"] < 0.4 else "CLEAR"))
        if wx:
            env += "  %d°C" % wx["temp_c"]
        s.text(w - len(env) - 2, 1, env, CYAN)
        s.text(2, h - 2, "DIST %.2f km   GPS 37.7%04dN 122.4%04dW" % (self.dist / 1000, int(self.dist) % 9999, int(now * 10) % 9999), GREY)
        if self.tunnel and self.tunnel[0] - 30 < self.cam.pos[2] < self.tunnel[1]:
            s.text(2, h - 3, "[ TUNNEL // GPS LOST ]" if self.cam.pos[2] > self.tunnel[0] else "[ TUNNEL AHEAD ]", YELLOW)
        if self.bridge and abs(self.bridge - self.cam.pos[2]) < 80:
            s.text(2, h - 3, "[ GOLDEN GATE // LOW PASS ]", ORANGE)
        msg, t = self.callout
        if police_t is not None:
            red_on = int(now * 8) % 2 == 0
            col = RED if red_on else BLUE
            box = " POLICE DRONE // EVADE "
            bw = len(box) + 4
            bx, by = cx - bw // 2, cy - bh // 2 - 4
            s.box(bx, by, bw, 3, col, double=True)
            s.text(bx + 2, by + 1, box, WHITE if red_on else col)
            if police_t < 3.2:
                s.center(by + 3, "▼ REAR CONTACT ▼", col)
            else:
                rng = max(3, int(22 + math.sin(police_t * 0.7) * 3)) if police_t < 11 else int(22 + (police_t - 11) * 30)
                s.center(by + 3, "RANGE %3dm  //  JAMMING %d%%" % (rng, min(99, int(police_t * 9))), col)
        elif now - t < 2.5:
            col = YELLOW if int(now * 5) % 2 else PINK
            s.center(cy + bh // 2 + 2 if not small else cy + bh // 2 + 1, "[ %s ]" % msg, col)
        if boost:
            s.center(cy - bh // 2 - 2, ">>> CRASH ZOOM <<<", PINK if int(now * 8) % 2 else WHITE)

    def siren(self, s, now, t):
        """Red/blue strobes on the screen edges."""
        env = min(1.0, t / 0.5, max(0.0, (13 - t) / 1.0))
        on = int(now * 8) % 2
        left, right = (RED, BLUE) if on else (BLUE, RED)
        bw = max(2, self.w // 40)
        cache = self.refl_cache
        for k, a in enumerate((0.42, 0.25, 0.12)):
            a = round(a * env, 2)
            if a <= 0:
                continue
            for col, xa, xb in ((left, k * bw, (k + 1) * bw), (right, self.w - (k + 1) * bw, self.w - k * bw)):
                for y in range(self.h):
                    for layer in (s.bg, s.fg):
                        row = layer[y]
                        for x in range(xa, xb):
                            c = row[x]
                            key = (c, col, a)
                            v = cache.get(key)
                            if v is None:
                                v = cache[key] = blend(c or BLACK, col, a)
                            row[x] = v
        for y in (0, self.h - 1):
            s.tint_row(y, left if y else right, 0.25 * env)

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        t = now - self.t0
        self.update_theme(now)
        th = self.theme
        self.plan_pieces(now)

        boost = 0.0
        if self.zoom_t is None and now > self.next_zoom and self.police is None:
            self.zoom_t = now
            self.glitch.trigger(now, 0.3)
            self.callout = (random.choice(CALLOUTS), now)
        if self.zoom_t is not None:
            zt = now - self.zoom_t
            boost = math.sin(min(1, zt / 2.2) * math.pi)
            if zt > 2.2:
                self.zoom_t = None
                self.next_zoom = now + random.uniform(9, 15)
                self.particles.burst(self.w / 2, self.h / 2, 80, speed=30)
        police_t = None
        if self.police is not None:
            police_t = now - self.police
        chase = 0.0 if police_t is None else min(1.0, police_t / 1.5, max(0.0, (13 - police_t) / 1.5))
        self.speed = 14 + boost * 60 + chase * 10
        self.cam.f = self.h * (0.85 + boost * 0.9)

        cam = self.cam
        cam.pos[2] += self.speed * dt
        self.dist += self.speed * dt
        z = cam.pos[2]
        alt = 5.5 + math.sin(t * 0.37) * 3.5 + math.sin(t * 0.11) * 2
        if self.tunnel and self.tunnel[0] - 25 < z < self.tunnel[1] + 2:
            alt = 3.6 + math.sin(t * 0.9) * 0.6
        if self.bridge and abs(self.bridge - z) < 45:
            alt = min(alt, 6.5)
        self.alt += (alt - self.alt) * min(1, dt * 2.5)
        cam.pos[1] = self.alt
        dodge = chase * math.sin(t * 2.3) * 1.0
        tun = 0.5 if self.tunnel and self.tunnel[0] - 20 < z < self.tunnel[1] else 1.0
        weave = (math.sin(t * 0.5) * 1.1 + dodge) * tun
        cam.pos[0] = self.lane + weave
        cam.yaw = math.sin(t * 0.5 + 0.6) * 0.18 + chase * math.cos(t * 2.3) * 0.08
        cam.roll = -math.cos(t * 0.5) * 0.22 - chase * math.cos(t * 2.3) * 0.3 + \
            (random.uniform(-0.03, 0.03) if boost > 0.3 else 0)
        cam.pitch = -0.08 + math.sin(t * 0.37 + 1.5) * 0.12

        self.sky(s, now)
        if th["day"] < 0.3:
            self.stars.draw(s, dt, speed=self.speed * 0.6, streak=boost > 0.2)
            hy = self.hy
            blank = [" "] * self.w
            for y in range(hy, self.h):  # stars only in the sky
                s.ch[y] = blank[:]
        # street centre line
        fog = self.fog_dist
        z0 = math.floor(z / 6) * 6
        dash = blend(YELLOW, th["ground"], 0.5)
        for k in range(1, 12):
            zz = z0 + k * 6
            cam.line(s, (self.lane, 0, zz), (self.lane, 0, zz + 2.5), dash, fog=fog, char="│")

        # Road expansion seams, curb lines and drainage grates in world space.
        asphalt = blend(th["ground"], GREY, 0.19)
        for k in range(1, 17):
            zz = z0 + k * 4
            cam.line(s, (self.lane-1.8, .015, zz), (self.lane+1.8, .015, zz), asphalt, fog=fog, char=".")
            if k % 3 == 0:
                cam.line(s, (self.lane+1.4, .03, zz), (self.lane+1.8, .03, zz+.7), asphalt, fog=fog, char="=")
        for side in (-1, 1):
            cam.line(s, (self.lane+side*2, .025, z+1), (self.lane+side*2, .025, z+fog), asphalt, fog=fog, char="/")

        cell = self.city.cell
        gx0 = int(cam.pos[0] // cell)
        gz0 = int(z // cell)
        boxes = [b for gx in range(gx0, gx0 + 2) for gz in range(gz0 - 1, gz0 + int(fog // cell) + 2)
                 for b in self.city.buildings(gx, gz) if b[3] > z - 2 and not self.blocked(b)]
        extras = [(1e6, self.billboard_fn(now))]
        theme = dict(th)
        self.city_faces = {}
        theme["box_faces"] = self.city_faces
        inside = False
        if self.bridge is not None:
            bb, cab = self.bridge_parts(now, th)
            boxes += bb
            extras.append(cab)
        if self.tunnel is not None:
            inside, bb, ex = self.tunnel_parts(now, th)
            boxes += bb
            extras += ex
        bz = self.board_z - z if self.board_z else 100
        extras[0] = (bz * bz, extras[0][1])
        if inside:
            self.tunnel_view(s, now, True)
            boxes, extras = [], []
        if police_t is not None:
            police_t, pe = self.police_draw(now)
            extras.append(pe)
        self.city.draw(s, cam, boxes, fog=fog, theme=theme, extras=extras, tick=now * 2)
        if self.rain:
            self.reflections(s, now)
            self.rain_fx(s, dt)
        self.particles.step(s, dt)
        if boost > 0.4:
            for _ in range(int(boost * 25)):
                a = random.uniform(0, math.tau)
                r0 = random.uniform(8, 20)
                x0, y0 = self.w / 2 + math.cos(a) * r0 * 2, self.h / 2 + math.sin(a) * r0
                x1, y1 = self.w / 2 + math.cos(a) * (r0 + 12) * 2, self.h / 2 + math.sin(a) * (r0 + 12)
                s.line(int(x0), int(y0), int(x1), int(y1), "·", blend(WHITE, BLACK, 0.4))
        if police_t is not None:
            self.siren(s, now, police_t)
        self.hud(s, now, boost > 0.2, police_t)
        if random.random() < 0.004:
            self.callout = (random.choice(CALLOUTS), now)
        self.fx.apply(s, now, glitch)

    def billboard_fn(self, now):
        if self.board_z is None or self.board_z < self.cam.pos[2] - 2:
            self.board_z = self.cam.pos[2] + random.uniform(90, 140)
        return lambda s: self.billboard(s, now)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "pullback", "DRONE // RETURN TO HOME", CYAN)
        if .08 < t < .88:
            radius = max(2, int((1-t)*min(s.w/5,s.h/3)))
            cx,cy=s.w//2,s.h//2
            s.text(cx-radius,cy,"[",blend(CYAN,BLACK,t))
            s.text(cx+radius,cy,"]",blend(CYAN,BLACK,t))
            if t > .4:
                s.text(cx-4,cy+1,"RTH LOCK",blend(CYAN,BLACK,t))

"""DRONE: FPV flight through a 3D San Francisco with live time of day, weather and police."""

import math
from functools import lru_cache
import random
import time

import numpy as np

from engine3d import NEAR, Camera, Starfield, clip2d
from lib import (BLACK, CYAN, DARK, DIM_CYAN, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW,
                 Glitch, blend, line_points, pulse)
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
        pcache = {}
        box_faces = th.get("box_faces", {})
        for d2, it in items:
            if not isinstance(it, int):
                it(s)
                continue
            b = boxes[it]
            x0, z0, x1, z1, y0, y1, col = b[:7]
            px, py, pz = cam.pos
            xside = -1 if px < x0 else (1 if px > x1 else 0)
            faces, edges = face_combo(-1 if pz < z0 else (1 if pz > z1 else 0), xside,
                                      1 if py > y1 else (-1 if py < y0 else 0))
            q = min(12, max(0, int(ZC[it] / fog * 12)))
            key = (col, q, xside > 0)
            pal = pcache.get(key)
            if pal is None:
                fcols = box_faces.get(col, faces_c)
                # West faces catch the light, east faces sit in shadow.
                side_c = fcols[3] if xside > 0 and len(fcols) > 3 else fcols[1]
                pal = pcache[key] = {
                    "front": self.fogged(blend(fcols[0], col, 0.10), q, fog_col),
                    "side": self.fogged(blend(side_c, col, 0.10), q, fog_col),
                    "top": self.fogged(blend(fcols[2], col, 0.10), q, fog_col),
                    "bot": self.fogged(blend(fcols[2], col, 0.10), q, fog_col),
                    "deck": self.fogged(blend(fcols[2], BLACK, 0.3), q, fog_col),
                    "e": self.fogged(blend(col, BLACK, 0.28), q, fog_col, edge_k),
                    "d": self.fogged(blend(col, BLACK, 0.58), q, fog_col, edge_k)}
            ecol, dcol = pal["e"], pal["d"]
            if FAST[it]:
                X, Y = SX[it], SY[it]
                for kind, f in faces:
                    pts = [(X[k], Y[k]) for k in f]
                    fill_conv(s, pts, pal[kind])
                    if kind == "top" and q < 9:
                        # Parapet: darker inset roof deck keeps flat roofs from reading as blobs.
                        mx, my = sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4
                        inset = [(mx + (p[0] - mx) * .8, my + (p[1] - my) * .8) for p in pts]
                        if abs(inset[0][0] - inset[2][0]) + abs(inset[0][1] - inset[2][1]) > 3:
                            fill_conv(s, inset, pal["deck"])
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
                if q < 8:
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
                        fill_conv(s, [(ccx + p[0] / p[2] * f2, ccy - p[1] / p[2] * f1) for p in poly], pal[kind])
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
        for k, t in ((0, 0.16), (-1, 0.08), (1, 0.08)):
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


# ====================================================================== drone city dressing
# PROFILER shares BoxCity, so the drone's materials, facades, roofs and signs
# live in this subclass and in painter "extras" drawn straight after each block.

MATERIALS = [(150, 140, 126), (72, 104, 138), (138, 82, 64), (78, 84, 98), (64, 118, 124), (172, 152, 118)]
SIGNS = ["HOTEL", "BAR", "24H", "NUDLE", "TIDIS", "RAMEN", "CAFE", "OPEN", "BLUME", "SUSHI"]
NEONS = [PINK, CYAN, YELLOW, (255, 90, 60), (160, 90, 255)]
SODIUM = (255, 168, 70)


def square_to_quad(p):
    """3x3 homography mapping the unit square (0,0) (1,0) (1,1) (0,1) to quad p."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p
    sx, sy = x0 - x1 + x2 - x3, y0 - y1 + y2 - y3
    if abs(sx) < 1e-9 and abs(sy) < 1e-9:
        return np.array([[x1 - x0, x3 - x0, x0], [y1 - y0, y3 - y0, y0], [0, 0, 1.0]])
    dx1, dx2, dy1, dy2 = x1 - x2, x3 - x2, y1 - y2, y3 - y2
    den = dx1 * dy2 - dx2 * dy1
    if abs(den) < 1e-9:
        return None
    g = (sx * dy2 - dx2 * sy) / den
    h = (dx1 * sy - sx * dy1) / den
    return np.array([[x1 - x0 + g * x1, x3 - x0 + h * x3, x0],
                     [y1 - y0 + g * y1, y3 - y0 + h * y3, y0],
                     [g, h, 1.0]])


class DroneCity(BoxCity):
    """BoxCity with real materials (no ▪ dot windows or dashed seams) plus per-block decor."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.decor = {}

    def buildings(self, gx, gz):
        key = (gx, gz)
        if key not in self.cache:
            r = random.Random(gx * 73856093 ^ gz * 19349663 ^ self.seed)
            out = []
            n = r.choice((1, 2, 2, 4))
            sub = self.block / (2 if n > 1 else 1)
            for i in range(n):
                ox, oz = (i % 2) * sub, (i // 2) * sub
                h = (r.uniform(3, 14) if r.random() < 0.85 else r.uniform(16, 30)) * self.hscale
                x0 = gx * self.cell + ox + 0.4
                z0 = gz * self.cell + oz + 0.4
                mat = r.choice(MATERIALS)
                b = (x0, z0, x0 + sub - 0.8, z0 + (sub if n == 4 else self.block) - 0.8, 0.0, round(h, 2), mat, False)
                out.append(b)
                self.decor[b] = {
                    "seed": r.randrange(1 << 20),
                    "fw": r.choice((1.6, 2.0, 2.4)),           # window module width
                    "fh": r.choice((2.4, 2.8, 3.2)),           # floor height
                    "roof": r.choice(("tank", "ac", "mast", "ac", None)),
                    "sign": r.choice(SIGNS) if r.random() < 0.42 else None,
                    "neon": r.choice(NEONS),
                    "shop": r.random() < 0.7,
                }
            self.cache[key] = out
            if len(self.cache) > 3000:
                self.cache.clear()
                self.decor.clear()
        return self.cache[key]


def material_faces(th):
    """(front, side, top) per material for the current light."""
    day = th["day"]
    out = {}
    for m in MATERIALS:
        base = blend(blend(m, BLACK, 0.62 - 0.5 * day), th["sky_hor"], 0.10)
        front = blend(base, th.get("sun", WHITE), 0.10 * day)
        out[m] = (front, blend(front, BLACK, 0.45), blend(front, WHITE, 0.10 + 0.12 * day),
                  blend(front, th.get("sun", WHITE), 0.08 + 0.1 * day))
    return out


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
        self.city = DroneCity(block=10.0, street=12.0, hscale=1.05)
        self.facade_x = (np.arange(w) + 0.5)[None, :]
        self.facade_y = (np.arange(h * 2) + 0.5)[:, None]
        self.stars = Starfield(w, h, n=70, colors=(PURPLE, CYAN, WHITE))
        self.stars.cam = self.cam
        self.glitch = Glitch(0.01)
        self.fx = FastFX(band_speed=11)
        self.particles = Particles()
        self.last = time.time()
        self.t0 = self.last
        cell = self.city.cell
        self.lane = cell - self.city.street / 2
        self.road_hw = 4.4                      # asphalt half width; sidewalks run to the facades
        self.street_x0 = self.city.block - 0.4
        self.street_x1 = self.city.cell + 0.4
        self.cam.pos = [self.lane, 15.0, 0.0]
        self.speed = 14.0
        self.zoom_t = None
        self.next_zoom = self.last + random.uniform(8, 14)
        self.callout = (random.choice(CALLOUTS), self.last)
        self.board_z = None
        self.dist = 0.0
        self.battery = random.uniform(70, 99)
        self.alt = 15.0
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
        self.flash = None
        self.zoom_hit = False
        self.zoom_z0 = 0.0

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
            self.mat_faces = material_faces(self.theme)

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
                if (rbg[x] is not g and rbg[x] != self.road_color) or rc[x] != " " or rt[x] is not None or rb[x] is not None:
                    continue
                xs = x + dx
                if not 0 <= xs < w:
                    continue
                src = src_f[xs] if src_c[xs] != " " else src_b[xs]
                if src is None:
                    continue
                base = self.road_color if rbg[x] == self.road_color else gnd
                key = (src, q, base)
                c = cache.get(key)
                if c is None:
                    c = cache[key] = blend(src, base, 0.45 + q * 0.07)
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

    # ------------------------------------------------------------ street life
    CAR_COLS = [(150, 30, 40), (200, 200, 205), (30, 32, 40), (40, 70, 130), (170, 150, 60), (90, 94, 104)]

    def street_props(self, s, now, t):
        """Sodium lamps with light pools and traffic with light trails, seen from above."""
        cam, th = self.cam, self.theme
        cz = cam.pos[2]
        fog = self.fog_dist
        zmax = cz + fog * 0.85
        if self.tunnel and self.tunnel[0] > cz:
            zmax = min(zmax, self.tunnel[0] - 0.5)
        night = th["day"] < 0.35
        lx, rh = self.lane, self.road_hw
        fogc = th["fog"]
        proj = cam.project
        road = self.road_color
        # Lamp posts every 16 units, staggered on both curbs.
        lamps = []
        k0 = int(cz // 16)
        for k in range(k0, k0 + int(fog // 16) + 2):
            for side in (-1, 1):
                z = k * 16 + (8 if side > 0 else 0)
                if not cz + 1.5 < z < zmax:
                    continue
                lamps.append((z, side))
        if night:
            for z, side in lamps:
                fk = min(0.9, (z - cz) / fog)
                hx = lx + side * (rh - 0.9)
                pool = blend(blend(road, SODIUM, 0.22), fogc, fk)
                self.fill_world(s, [(hx - 1.5, .02, z - 1.6), (hx + 1.5, .02, z - 1.6),
                                    (hx + 1.5, .02, z + 1.6), (hx - 1.5, .02, z + 1.6)], pool)
        for z, side in lamps:
            fk = min(0.9, (z - cz) / fog)
            px_ = lx + side * (rh + 0.6)
            hx = lx + side * (rh - 0.9)
            a, b, c = proj((px_, 0, z)), proj((px_, 5.2, z)), proj((hx, 5.0, z))
            if not (a and b and c):
                continue
            pole = blend((70, 72, 82), fogc, fk)
            s.pixel_line(a[0], a[1] * 2, b[0], b[1] * 2, pole)
            s.pixel_line(b[0], b[1] * 2, c[0], c[1] * 2, pole)
            head = blend(blend(SODIUM, WHITE, 0.4) if night else (150, 150, 140), fogc, fk * 0.7)
            hx_, hy_ = int(c[0]), int(c[1] * 2) + 1
            s.pixel(hx_, hy_, head)
            if night and c[2] < 30:
                s.pixel(hx_ - 1, hy_, blend(head, BLACK, 0.4))
                s.pixel(hx_ + 1, hy_, blend(head, BLACK, 0.4))
        # Traffic: one lane away from the camera, one oncoming.
        for lane_x, v, red, spacing in ((lx + 2.0, 9.0, True, 13.0), (lx - 2.0, -12.0, False, 17.0)):
            base = v * t
            i0 = int((cz - base) // spacing) - 1
            for i in range(i0, i0 + int(fog // spacing) + 3):
                hsh = (i * 2654435761) & 0xffff
                if hsh % 5 == 0:
                    continue
                z0 = i * spacing + base + (hsh % 7) * 0.8
                z1 = z0 + 3.6
                if z0 < cz + 2.0 or z1 > zmax:
                    continue
                fk = min(0.9, (z0 - cz) / fog)
                body = self.CAR_COLS[hsh % len(self.CAR_COLS)]
                if night:
                    body = blend(body, BLACK, 0.55)
                x0, x1 = lane_x - 0.8, lane_x + 0.8
                self.fill_world(s, [(x0, 0, z0), (x1, 0, z0), (x1, 1.0, z0), (x0, 1.0, z0)],
                                blend(blend(body, BLACK, 0.3), fogc, fk))
                self.fill_world(s, [(x0, 1.0, z0), (x1, 1.0, z0), (x1, 1.0, z1), (x0, 1.0, z1)],
                                blend(body, fogc, fk))
                self.fill_world(s, [(x0 + .2, 1.45, z0 + 1.0), (x1 - .2, 1.45, z0 + 1.0),
                                    (x1 - .2, 1.45, z1 - .9), (x0 + .2, 1.45, z1 - .9)],
                                blend(blend(body, WHITE, 0.15), fogc, fk))
                lc = (255, 40, 50) if red else (255, 245, 210)
                lc = blend(lc, fogc, fk * 0.6)
                trail_z = z0 - 5.0 if red else z1 + 9.0
                tz = z0 if red else z1
                for ox in (-0.55, 0.55):
                    p0 = proj((lane_x + ox, .55, z0))
                    if p0:
                        s.pixel(int(p0[0]), int(p0[1] * 2), lc)
                    if night or red:
                        # Long-exposure streak behind the car.
                        q0, q1 = proj((lane_x + ox, .5, tz)), proj((lane_x + ox, .5, trail_z))
                        if q0 and q1:
                            pts = line_points(int(q0[0]), int(q0[1] * 2), int(q1[0]), int(q1[1] * 2))
                            n = len(pts)
                            grad = [blend(lc, road, 0.3 + 0.18 * g) for g in range(4)]
                            for j, (qx, qy) in enumerate(pts[1:], 1):
                                s.pixel(qx, qy, grad[j * 4 // (n + 1)])

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

    TUN_HW, TUN_TOP = 3.4, 8.6
    TUN_RING = 3.0
    VOID = (12, 11, 17)

    def fill_world(self, s, pts, col):
        """Near-clipped convex world polygon filled into the cell/bg layer."""
        cam = self.cam
        vs = [cam.to_view(p) for p in pts]
        if min(v[2] for v in vs) < NEAR:
            vs = clip_poly_near(vs)
            if len(vs) < 3:
                return False
        f2, f1, cx, cy = cam.f * 2, cam.f, cam.cx, cam.cy
        fill_conv(s, [(cx + v[0] / v[2] * f2, cy - v[1] / v[2] * f1) for v in vs], col)
        return True

    def arch(self, grow=0.0):
        """Tunnel cross-section (x, y): straight walls and a semicircular vault."""
        hw = self.TUN_HW + grow
        lx = self.lane
        spring = self.TUN_TOP - self.TUN_HW
        pts = [(lx - hw, 0.0), (lx - hw, spring)]
        for i in range(1, 6):
            a = math.pi - math.pi * i / 6
            pts.append((lx + hw * math.cos(a), spring + hw * math.sin(a)))
        pts += [(lx + hw, spring), (lx + hw, 0.0)]
        return pts

    def tunnel_parts(self, now, th):
        """Concrete tube filling the street; returns (inside, boxes, extras)."""
        z0, z1 = self.tunnel
        cz = self.cam.pos[2]
        if z0 <= cz <= z1:
            return True, [], []
        if cz > z1:
            return False, [], []
        wall = blend(blend(th["front"], (150, 150, 160), 0.35), BLACK, 0.1)
        self.city_faces[TUNNEL] = (wall, blend(wall, BLACK, 0.35), blend(wall, WHITE, 0.12))
        box = (self.street_x0, z0, self.street_x1, z1, 0.0, 11.5, TUNNEL, False)
        dz = z0 - cz
        return False, [box], [(dz * dz * 0.98, lambda s: self.tunnel_view(s, now, False))]

    def tunnel_view(self, s, now, inside):
        """Clean tube: alternating concrete segments, ribs, sodium lamps rushing past."""
        z0, z1 = self.tunnel
        cam = self.cam
        cz = cam.pos[2]
        th = self.theme
        lx = self.lane
        arch = self.arch()
        ring = self.TUN_RING
        view = 42.0
        if inside:
            # Keep the actual street beyond the exit, rather than a flat light card.
            portal_scene = None
            if z1 - cz < view + ring:
                portal_scene = tuple([[row[:] for row in layer] for layer in
                                      (s.ch, s.fg, s.bg, s.pt, s.pb)])
            # Nested cross-sections painted near -> far: each farther ring projects
            # inside the nearer one, so the visible annuli are the wall segments.
            concrete = (70, 68, 80)
            led = (255, 226, 170)
            k_far = min(int((z1 - z0) / ring), int((cz + view - z0) / ring) + 1)
            k_near = max(0, int((cz - z0) / ring) + 1)
            near_col = blend(concrete, self.VOID, 0.05)
            bgrow = [near_col] * self.w
            blank = [" "] * self.w
            for y in range(self.h):
                s.ch[y] = blank[:]
                s.bg[y] = bgrow[:]
                s.pt[y] = [None] * self.w
                s.pb[y] = [None] * self.w
            road_y = 0.0
            for k in range(k_near, k_far + 1):
                za = z0 + k * ring
                d = za - cz
                if d <= NEAR * 2:
                    continue
                fade = min(0.93, 0.15 + (d / view) ** 0.8)
                lit = k % 2 == 0
                if lit:
                    # Thin LED arch: bright section, then the wall just behind it.
                    self.fill_world(s, [(x, y, za) for x, y in arch], blend(led, self.VOID, fade * 0.85))
                    self.fill_world(s, [(x, y, za + 0.3) for x, y in self.arch(-0.22)],
                                    blend(blend(concrete, led, 0.18), self.VOID, fade))
                shade = concrete if k % 2 else blend(concrete, BLACK, 0.12)
                self.fill_world(s, [(x, y, za + (0.32 if lit else 0)) for x, y in self.arch(-0.22 if lit else 0)],
                                blend(shade, self.VOID, fade))
                zb_ = za + ring
                road = (40, 40, 46) if k % 2 else (34, 34, 40)
                self.fill_world(s, [(lx - self.TUN_HW + .3, road_y, za), (lx + self.TUN_HW - .3, road_y, za),
                                    (lx + self.TUN_HW - .3, road_y, zb_), (lx - self.TUN_HW + .3, road_y, zb_)],
                                blend(road, self.VOID, fade))
                if lit:
                    self.fill_world(s, [(lx - .08, .01, za + .4), (lx + .08, .01, za + .4), (lx + .08, .01, za + 1.8),
                                        (lx - .08, .01, za + 1.8)], blend((210, 180, 60), self.VOID, fade))
            # Low curbs and a continuous service rail give the vault a stable
            # road level and material scale as its arches move past the camera.
            za, zb = cz + 0.8, min(z1, cz + view)
            for side in (-1, 1):
                wall_x = lx + side * (self.TUN_HW - .08)
                self.fill_world(s, [(wall_x, 1.15, za), (wall_x, 1.23, za),
                                    (wall_x, 1.23, zb), (wall_x, 1.15, zb)], (100, 104, 112))
                curb_x = lx + side * (self.TUN_HW - .25)
                self.fill_world(s, [(curb_x, .12, za), (wall_x, .12, za),
                                    (wall_x, .12, zb), (curb_x, .12, zb)], (88, 87, 92))
            if z1 - cz < view + ring:
                # Daylight at the far portal, framed by the last segment.
                marker = (-1, -1, -1)
                self.fill_world(s, [(x, y, z1) for x, y in self.arch(-0.1)], marker)
                if portal_scene is not None:
                    for y, row in enumerate(s.bg):
                        for x, color in enumerate(row):
                            if color == marker:
                                for layer, saved in zip((s.ch, s.fg, s.bg, s.pt, s.pb), portal_scene):
                                    layer[y][x] = saved[y][x]
        else:
            frame = (150, 146, 150) if th["day"] > 0.3 else (90, 88, 96)
            if not self.fill_world(s, [(x, y, z0 - 0.05) for x, y in self.arch(0.45)], frame):
                return
            self.fill_world(s, [(x, y, z0 - 0.06) for x, y in arch], self.VOID)
            # Lamps inside the bore, receding into the dark.
            for k in range(0, 14, 2):
                zz = z0 + k * ring + 1.3
                for sx in (lx - 1.9, lx + 1.9):
                    q = cam.project((sx, self.TUN_TOP - self.TUN_HW - .4, zz))
                    if q:
                        col = blend(SODIUM, self.VOID, min(0.85, k / 16))
                        s.pixel(int(q[0]), int(q[1] * 2), col)
            q = cam.project((lx, self.TUN_TOP + 0.9, z0 - 0.1))
            q2 = cam.project((lx + self.TUN_HW, self.TUN_TOP + 0.9, z0 - 0.1))
            if q and q2:
                label = "BROADWAY TUNNEL" if (q2[0] - q[0]) * 2 > 19 else "TUNNEL"
                if (q2[0] - q[0]) * 2 > len(label) + 2:
                    x = int(q[0]) - len(label) // 2
                    y = int(q[1])
                    for k in range(len(label) + 2):
                        s.set_bg(x - 1 + k, y, (20, 70, 45))
                    s.text(x, y, label, WHITE)

    def police_pos(self, now):
        t = now - self.police
        cam = self.cam
        if t < 3:
            rel = (math.sin(t * 2) * 1.0, -1.5, -8 + t)
        elif t < 5.5:
            u = (t - 3) / 2.5
            rel = (math.sin(t * 2) * 1.2, -1.5 + u * 3.2, -5 + u * u * 23)
        elif t < 11:
            rel = (math.sin(t * 1.3) * 2.0, 1.4 + math.sin(t * 2.1) * 0.6, 14 + math.sin(t * 0.7) * 2.5)
        else:
            u = (t - 11) / 2
            rel = (math.sin(t * 1.3) * 2.0, 1.4 + u * u * 18, 14 + u * 25)
        return t, (cam.pos[0] + rel[0], cam.pos[1] + rel[1], cam.pos[2] + rel[2]), rel[2]

    def police_draw(self, now):
        t, p, rz = self.police_pos(now)
        cam = self.cam

        def draw(s):
            q = cam.project(p)
            if not q or q[2] < 0.8:
                return
            cx, cy, z = q[0], q[1] * 2, q[2]
            k = cam.f * 2 / z                       # pixels per world unit
            red_on = int(now * 8) % 2 == 0
            # Light halo, painted under the airframe.
            r = max(3.0, k * 1.5)
            hc = self.refl_cache
            for py in range(max(0, int(cy - r)), min(s.ph, int(cy + r) + 1)):
                dy = (py - cy) / r
                layer = (s.pb if py & 1 else s.pt)[py >> 1]
                brow = s.bg[py >> 1]
                for x in range(max(0, int(cx - r * 1.6)), min(s.w, int(cx + r * 1.6) + 1)):
                    dx = (x - cx) / (r * 1.6)
                    d2 = dx * dx + dy * dy
                    if d2 < 1:
                        col = RED if (dx < 0) == red_on else BLUE
                        base = layer[x] or brow[x] or BLACK
                        key = (base, col, int((1 - d2) * 6))
                        v = hc.get(key)
                        if v is None:
                            v = hc[key] = blend(base, col, 0.075 * key[2])
                        layer[x] = v
            # Arms and rotors.
            body = (28, 32, 52)
            for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                rq = cam.project((p[0] + dx * 1.1, p[1] + 0.1, p[2] + dz * 1.1))
                if not rq:
                    continue
                rx, ry = rq[0], rq[1] * 2
                s.pixel_line(cx, cy, rx, ry, (70, 76, 96))
                rr = max(1.0, k * 0.55)
                blur = (150, 160, 180) if int(now * 30 + dx) % 2 else (110, 118, 140)
                for i in range(int(-rr), int(rr) + 1):
                    s.pixel(int(rx + i), int(ry - 1), blur)
                s.pixel(int(rx), int(ry), (40, 44, 60))
            bw, bh = max(2, int(k * 0.9)), max(1, int(k * 0.45))
            s.pixel_rect(cx - bw / 2, cy - bh / 2, bw, bh, body)
            s.pixel_rect(cx - bw / 2, cy - bh / 2, bw, max(1, bh // 3), (215, 220, 235))
            s.pixel(int(cx), int(cy + bh / 2), (255, 255, 255) if int(now * 3) % 2 else (90, 200, 255))
            # Light bar.
            lw = max(1, bw // 2)
            s.pixel_rect(cx - lw, cy - bh / 2 - 1, lw, 1, RED if red_on else blend(RED, BLACK, 0.7))
            s.pixel_rect(cx, cy - bh / 2 - 1, lw, 1, blend(BLUE, BLACK, 0.7) if red_on else BLUE)
            if 5.5 < t < 11:
                gx = p[0] + math.sin(now * 1.7) * 2.5
                for kk in (-0.6, 0, 0.6):
                    cam.line(s, (p[0], p[1] - 0.3, p[2]), (gx + kk, 0, p[2] - 5), blend(WHITE, BLACK, 0.6), fog=90, char="·")
            # Target box with tag.
            half = max(3, int(k * 1.3))
            x0, y0 = int(cx) - half, int(cy / 2) - max(2, half // 3)
            col = RED if red_on else BLUE
            s.brackets(x0, y0, half * 2 + 1, max(3, half * 2 // 3) + 1, col, arm=1)
            s.text(x0, y0 - 1, "SFPD UAV-%02d" % (int(self.police) % 97), col)
        return t, (rz * rz, draw)

    def billboard(self, s, now):
        """A giant DedSec skull billboard over the street, rasterised in half-block pixels."""
        cx, cy = self.lane, 12.0
        w2, h2 = 11.0, 8.0
        z = self.board_z
        cam = self.cam
        col = blend(PINK, PURPLE, pulse(now, 3))
        corners = [(cx - w2, cy - h2, z), (cx + w2, cy - h2, z), (cx + w2, cy + h2, z), (cx - w2, cy + h2, z)]
        for lx in (cx - w2 * 0.6, cx + w2 * 0.6):
            self.fill_world(s, [(lx - .3, 0, z + .2), (lx + .3, 0, z + .2), (lx + .3, cy - h2, z + .2), (lx - .3, cy - h2, z + .2)],
                            blend((60, 62, 74), self.theme["fog"], min(0.8, (z - cam.pos[2]) / 150)))
        pts = [cam.project(c) for c in corners]
        if all(pts):
            fog = min(0.85, pts[0][2] / 150)
            # Frame first, then the skull panel inset.
            fr = [cam.project((cx + dx * (w2 + .7), cy + dy * (h2 + .7), z + .05)) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            if all(fr):
                fill_conv(s, [(p[0], p[1]) for p in fr], blend((30, 20, 40), BLACK, fog))
            raster_board(s, pts[3], pts[2], pts[0], blend(blend(col, BLACK, 0.55), BLACK, fog),
                         blend(blend(WHITE, PINK, 0.15 + 0.2 * pulse(now, 7)), BLACK, fog))
            width = pts[1][0] - pts[0][0]
            if width > 34:
                label = "D E D S E C" if width > 60 else "DEDSEC"
                bq = cam.project((cx, cy - h2 - .25, z))
                if bq and 0 < bq[1] < s.h - 1:
                    x = int(bq[0]) - len(label) // 2
                    y = int(bq[1])
                    for k in range(-2, len(label) + 2):
                        s.set_bg(x + k, y, (30, 20, 40))
                    s.text(x, y, label, PINK if int(now * 4) % 2 else WHITE)
        for i in range(4):
            cam.line(s, corners[i], corners[(i + 1) % 4], col, fog=150)

    def prepare_facades(self, s, blocks):
        """Batched window raster for all decorated facades (one numpy pass per frame).

        Returns {block: [(xa, ya, rows)]} with rows of global palette indices;
        painting happens later in painter order inside decorate()."""
        cam = self.cam
        th = self.theme
        px, py_, pz = cam.pos
        fog = self.fog_dist
        f2, f1, ccx, ccy = cam.f * 2, cam.f, cam.cx, cam.cy
        day = th["day"]
        lit_p = th.get("lit", 0.3)
        fc = th["fog"]
        to_view = cam.to_view
        params, meta, pal = [], [], []
        sky_glass = blend(th["sky_hor"], (30, 40, 60), 0.45 if day > .5 else 0.8)
        warm0 = (188, 169, 128) if day < .5 else (215, 211, 192)
        shop0 = (155, 138, 112) if day < .5 else (90, 140, 150)
        for b in blocks:
            dec = self.city.decor.get(b)
            if dec is None:
                continue
            x0, z0, x1, z1, _, y1 = b[:6]
            faces = []
            if pz < z0:
                faces.append(((x0, z0), (x1, z0)))
            if px < x0:
                faces.append(((x0, z1), (x0, z0)))
            elif px > x1:
                faces.append(((x1, z0), (x1, z1)))
            for (ax, az), (bx, bz) in faces:
                va = to_view((ax, 0, az)); vb = to_view((bx, 0, bz))
                vat = to_view((ax, y1, az)); vbt = to_view((bx, y1, bz))
                # Clip the face along u to the part safely in front of the camera.
                lim = 0.6
                u0, u1 = 0.0, 1.0
                for za, zb in ((va[2], vb[2]), (vat[2], vbt[2])):
                    if za < lim and zb < lim:
                        u0, u1 = 1.0, 0.0
                        break
                    if za < lim:
                        u0 = max(u0, (lim - za) / (zb - za))
                    elif zb < lim:
                        u1 = min(u1, (lim - za) / (zb - za))
                if u1 - u0 < 0.02:
                    continue
                P = []
                for u, yy in ((u0, 0), (u1, 0), (u1, y1), (u0, y1)):
                    v = to_view((ax + (bx - ax) * u, yy, az + (bz - az) * u))
                    P.append((ccx + v[0] / v[2] * f2, (ccy - v[1] / v[2] * f1) * 2))
                xs = [p[0] for p in P]
                ys = [p[1] for p in P]
                xa, xb = max(0, int(min(xs))), min(s.w - 1, int(max(xs)))
                ya, yb = max(0, int(min(ys))), min(s.ph - 1, int(max(ys)))
                if xb - xa < 3 or yb - ya < 4:
                    continue
                floors = y1 / dec["fh"]
                fph = (abs(P[3][1] - P[0][1]) + abs(P[2][1] - P[1][1])) / (2 * max(1, floors))
                if fph < 2.6:
                    continue
                # LOD: near facades subdivide into more, smaller window modules so a
                # pane never grows into a screen-filling block.
                sub = min(8, max(1, int(fph / 8)))
                H = square_to_quad(P)
                if H is None:
                    continue
                (a, b_, c), (d, e, f), (g, h, i) = H.tolist()
                A, B, C = e * i - f * h, c * h - b_ * i, b_ * f - c * e
                D, E, F = f * g - d * i, a * i - c * g, c * d - a * f
                G, J, K = d * h - e * g, b_ * g - a * h, a * e - b_ * d
                if abs(a * A + b_ * D + c * G) < 1e-9:
                    continue
                L = math.hypot(bx - ax, bz - az)
                fk = min(0.9, (va[2] + vb[2]) / 2 / fog)
                glass = blend(blend(sky_glass, fc, fk), self.mat_faces[b[6]][1], 0.25)
                fid = len(meta)
                pal.extend((None, glass, blend(glass, WHITE, 0.06), blend(warm0, fc, fk * 0.8),
                            blend((150, 210, 255), fc, fk * 0.8), blend(shop0, fc, fk)))
                params.append((A, B, C, D, E, F, G, J, K, u0 * L / dec["fw"], (u1 - u0) * L / dec["fw"], floors, sub,
                               dec["seed"], 1.0 if dec["shop"] else 0.0, fid * 6))
                meta.append((b, xa, ya, xb - xa + 1, yb - ya + 1))
        out = {}
        if not meta:
            return out, pal
        f32 = np.float32
        bw = np.array([m[3] for m in meta], dtype=f32)
        counts = np.array([m[3] * m[4] for m in meta])
        total = int(counts.sum())
        starts = np.cumsum(counts) - counts
        rep = lambda vals: np.repeat(np.asarray(vals, dtype=f32), counts)
        # Contiguous per-face columns; integer division/modulo avoided (slow in numpy).
        local = np.arange(total, dtype=f32) - rep(starts)
        W = rep(bw)
        row = np.floor((local + 0.5) / W)
        X = rep([m[1] + 0.5 for m in meta]) + (local - row * W)
        Y = rep([m[2] + 0.5 for m in meta]) + row
        cols = list(zip(*params))
        cA, cE, cG, cJ = rep(cols[0]), rep(cols[4]), rep(cols[6]), rep(cols[7])
        den = cG * X + cJ * Y + rep(cols[8])
        nu = cA * X + rep(cols[1]) * Y + rep(cols[2])
        nv = rep(cols[3]) * X + cE * Y + rep(cols[5])
        inv = 1 / den
        u, v = nu * inv, nv * inv
        inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        flo = rep(cols[11])
        uscale = rep(cols[10])
        wu0 = rep(cols[9]) + u * uscale
        wv0 = v * flo
        # Per-pixel LOD from the local projective scale: module width and floor
        # height in pixels decide pane subdivision; grazing (aliasing) areas stay plain.
        inv2 = inv * inv
        mod_px = 1 / (np.abs((cA * den - nu * cG) * inv2 * uscale) + 1e-6)
        floor_px = 1 / (np.abs((cE * den - nv * cJ) * inv2 * flo) + 1e-6)
        inside &= (mod_px > 2.4) & (floor_px > 2.6)
        # A facade uses one physical module size. Changing subdivision per
        # pixel tears individual panes into L-shapes as perspective varies.
        sub = rep(cols[12])
        wu, wv = wu0 * sub, wv0 * sub
        iu, iv = np.floor(wu), np.floor(wv)
        fu, fv = wu - iu, wv - iv
        upper = inside & (wv0 >= 1) & (wv0 < flo - 0.25) & (fu > .28) & (fu < .70) & (fv > .34) & (fv < .70)
        gu, gv = wu0 - np.floor(wu0), wv0 - np.floor(wv0)
        shop = inside & (rep(cols[14]) > 0) & (wv0 < 1) & (gv > .12) & (gv < .72) & (gu > .18) & (gu < .78)
        hsh = iu.astype(np.int32) * 7919 + iv.astype(np.int32) * 104729 + np.repeat(np.array(cols[13], dtype=np.int32), counts)
        hsh = ((hsh * 40503) >> 6) & 1023
        room = (np.floor(wu0).astype(np.int32) * 7919 + np.floor(wv0).astype(np.int32) * 104729
                + np.repeat(np.array(cols[13], dtype=np.int32), counts))
        room = ((room * 40503) >> 6) & 1023
        lit = upper & (room < lit_p * 1024)
        k = np.where(upper, np.where(lit, np.where((room & 7) == 0, 4, 3), np.where((hsh & 3) == 0, 2, 1)), 0)
        k = np.where(shop, 5, k)
        k = np.where(k > 0, k + np.repeat(np.array(cols[15], dtype=np.int32), counts), 0)
        flat = k.tolist()
        for (b, xa, ya, w_, h_), o in zip(meta, starts.tolist()):
            rows = [flat[o + r * w_:o + (r + 1) * w_] for r in range(h_)]
            out.setdefault(b, []).append((xa, ya, w_, rows))
        return out, pal

    def decorate(self, s, b, now):
        """Facade windows (precomputed), roof kit and neon signs for one block."""
        dec = self.city.decor.get(b)
        if dec is None:
            return
        cam = self.cam
        th = self.theme
        px, py_, pz = cam.pos
        x0, z0, x1, z1, _, y1 = b[:6]
        fog = self.fog_dist
        seed = dec["seed"]
        pal = self.facade_pal
        pt, pb = s.pt, s.pb
        for xa, ya, w_, rows in self.facades.get(b, ()):
            xb = xa + w_
            for j, row in enumerate(rows):
                if not any(row):
                    continue
                py = ya + j
                layer = (pb if py & 1 else pt)[py >> 1]
                layer[xa:xb] = [pal[k] if k else o for k, o in zip(row, layer[xa:xb])]
        cx_, cz_ = (x0 + x1) / 2 - px, (z0 + z1) / 2 - pz
        d2 = cx_ * cx_ + cz_ * cz_
        if d2 > 55 * 55:
            return
        fk = min(0.9, math.sqrt(d2) / fog)
        fc = th["fog"]
        roof = dec["roof"]
        if roof == "tank":
            tx, tz = x0 + 1.2, z0 + 1.2
            wood = blend((120, 84, 58), fc, fk)
            for lx in (tx - .5, tx + .5):
                self.fill_world(s, [(lx - .06, y1, tz - .6), (lx + .06, y1, tz - .6), (lx + .06, y1 + .8, tz - .6), (lx - .06, y1 + .8, tz - .6)], blend((60, 60, 66), fc, fk))
            self.fill_world(s, [(tx - .7, y1 + .8, tz - .7), (tx + .7, y1 + .8, tz - .7), (tx + .7, y1 + 2.2, tz - .7), (tx - .7, y1 + 2.2, tz - .7)], wood)
            self.fill_world(s, [(tx - .7, y1 + 2.2, tz - .7), (tx + .7, y1 + 2.2, tz - .7), (tx, y1 + 2.8, tz)], blend(wood, BLACK, .3))
        elif roof == "ac":
            ax_, az_ = x1 - 1.6, z0 + 1.0
            grey = blend((150, 152, 158), fc, fk)
            self.fill_world(s, [(ax_ - .8, y1, az_ - .5), (ax_ + .8, y1, az_ - .5), (ax_ + .8, y1 + .7, az_ - .5), (ax_ - .8, y1 + .7, az_ - .5)], grey)
            self.fill_world(s, [(ax_ - .8, y1 + .7, az_ - .5), (ax_ + .8, y1 + .7, az_ - .5), (ax_ + .8, y1 + .7, az_ + .5), (ax_ - .8, y1 + .7, az_ + .5)], blend(grey, WHITE, .2))
            q = cam.project((ax_, y1 + .45, az_ - .5))
            if q and q[2] < 30 and 0 <= q[0] < s.w and 0 <= q[1] < s.h:
                s.put(int(q[0]), int(q[1]), "@" if int(now * 6) % 2 else "*", blend((60, 60, 70), fc, fk))
        elif roof == "mast":
            mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
            a = cam.project((mx, y1, mz))
            t = cam.project((mx, y1 + 4.5, mz))
            if a and t:
                seg(s, a[0], a[1], t[0], t[1], "│", blend((120, 124, 134), fc, fk))
                if int(now * 1.5 + seed) % 2 and 0 <= t[0] < s.w and 0 <= t[1] < s.h:
                    s.put(int(t[0]), int(t[1]), "●", RED)
        sign = dec["sign"]
        if sign and pz < z0:
            neon = dec["neon"]
            on = not (int(now * 7 + seed) % 23 == 0)       # occasional flicker
            if y1 < 11:
                # Rooftop board facing the street.
                mx = (x0 + x1) / 2
                bl = cam.project((mx - 2.2, y1 + .4, z0 + .3))
                br = cam.project((mx + 2.2, y1 + 1.9, z0 + .3))
                if bl and br:
                    self.fill_world(s, [(mx - 2.2, y1 + .4, z0 + .3), (mx + 2.2, y1 + .4, z0 + .3), (mx + 2.2, y1 + 1.9, z0 + .3), (mx - 2.2, y1 + 1.9, z0 + .3)],
                                    blend(blend(neon, BLACK, .78), fc, fk))
                    wcell = br[0] - bl[0]
                    y = int((bl[1] + br[1]) / 2)
                    if wcell > len(sign) + 1 and 0 <= y < s.h:
                        x = int((bl[0] + br[0]) / 2) - len(sign) // 2
                        s.text(x, y, sign, blend(neon if on else blend(neon, BLACK, .6), fc, fk * .7))
                    elif wcell > 1 and 0 <= y < s.h:
                        xa, xb = max(0, int(bl[0]) + 1), min(s.w, int(br[0]))
                        if xb > xa:
                            s.bg[y][xa:xb] = [blend(neon, fc, fk)] * (xb - xa)
            else:
                # Vertical blade on the corner nearest the street.
                sx = x1 - .5 if self.lane > x1 else x0 + .5
                top, bot = 3.0 + len(sign) * 1.0, 2.6
                pts = [(sx - .35, bot, z0 - .2), (sx + .35, bot, z0 - .2), (sx + .35, top, z0 - .2), (sx - .35, top, z0 - .2)]
                if self.fill_world(s, pts, blend(blend(neon, BLACK, .72), fc, fk)):
                    qt, qb = cam.project((sx, top, z0 - .2)), cam.project((sx, bot, z0 - .2))
                    if qt and qb:
                        hcell = qb[1] - qt[1]
                        col = blend(neon if on else blend(neon, BLACK, .6), fc, fk * .7)
                        if hcell >= len(sign) + 1:
                            step = hcell / len(sign)
                            for i, ch in enumerate(sign):
                                s.put(int(qt[0]), int(qt[1] + (i + .5) * step), ch, col)
                        else:
                            for y in range(max(0, int(qt[1]) + 1), min(s.h, int(qb[1]))):
                                if 0 <= y < s.h and 0 <= int(qt[0]) < s.w:
                                    s.bg[y][int(qt[0])] = col

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
            self.fx.tint(s, y, left if y else right, round(0.25 * env, 2))

    # ------------------------------------------------------------ frame
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        t = now - self.t0
        self.update_theme(now)
        th = self.theme
        self.plan_pieces(now)

        boost = 0.0
        cam = self.cam
        z = cam.pos[2]
        clear_ahead = not (self.tunnel and self.tunnel[0] - z < 160) and not self.bridge
        if self.zoom_t is None and now > self.next_zoom and self.police is None and clear_ahead:
            # Crash zoom: lock onto a DedSec billboard ahead and dive straight at it.
            self.zoom_t = now
            self.zoom_z0 = z
            self.board_z = z + 70
            self.glitch.trigger(now, 0.15)
            self.callout = ("BILLBOARD HACKED", now)
        zoom_u = None
        if self.zoom_t is not None:
            zt = now - self.zoom_t
            boost = math.sin(min(1, zt / self.ZOOM_T) * math.pi * 0.5)
            if zt < self.ZOOM_T:
                zoom_u = zt / self.ZOOM_T
            elif zt < self.ZOOM_T + 0.06 and not self.zoom_hit:
                self.zoom_hit = True
                self.flash = now
                self.glitch.trigger(now, 0.35)
                self.particles.burst(self.w / 2, self.h / 2, 90, colors=(PINK, WHITE, CYAN), speed=34)
            if zt > self.ZOOM_T + 0.5:
                self.zoom_t = None
                self.zoom_hit = False
                self.board_z = cam.pos[2] + random.uniform(110, 150)
                self.next_zoom = now + random.uniform(11, 17)
        police_t = None
        if self.police is not None:
            police_t = now - self.police
        chase = 0.0 if police_t is None else min(1.0, police_t / 1.5, max(0.0, (13 - police_t) / 1.5))
        if zoom_u is not None:
            # Ease-in dive that stops just short of the panel, then punches through.
            target = self.board_z - 4.0
            nz = self.zoom_z0 + (target - self.zoom_z0) * zoom_u ** 2.4
            self.speed = max(14.0, (nz - cam.pos[2]) / max(dt, 1e-3)) if dt > 0 else self.speed
            cam.pos[2] = nz
            self.dist += max(0.0, self.speed * dt)
        else:
            self.speed = 14 + boost * 40 + chase * 10
            cam.pos[2] += self.speed * dt
            self.dist += self.speed * dt
        self.cam.f = self.h * (0.85 + (0.25 * zoom_u if zoom_u is not None else 0.0))
        z = cam.pos[2]
        # Cruise above the street canyon, looking down at traffic; dive for set pieces.
        alt = 21.0 + math.sin(t * 0.23) * 3.5 + math.sin(t * 0.09) * 2.0
        low = 0.0
        if self.tunnel and self.tunnel[0] - 45 < z < self.tunnel[1] + 2:
            low = min(1.0, (z - self.tunnel[0] + 45) / 20)
            alt = alt + (3.8 + math.sin(t * 0.9) * 0.4 - alt) * low
        if self.bridge and abs(self.bridge - z) < 60:
            low = min(1.0, (60 - abs(self.bridge - z)) / 20)
            alt = alt + (min(alt, 7.0) - alt) * low
        self.alt += (alt - self.alt) * min(1, dt * 1.6)
        cam.pos[1] = self.alt
        dodge = chase * math.sin(t * 2.3) * 1.4
        tun = 0.35 if self.tunnel and self.tunnel[0] - 20 < z < self.tunnel[1] else 1.0
        weave = (math.sin(t * 0.43) * 1.6 + dodge) * tun
        cam.pos[0] = self.lane + weave
        cam.yaw = math.sin(t * 0.43 + 0.6) * 0.13 + chase * math.cos(t * 2.3) * 0.07
        cam.roll = -math.cos(t * 0.43) * 0.16 - chase * math.cos(t * 2.3) * 0.25 + \
            (random.uniform(-0.03, 0.03) if boost > 0.3 else 0)
        # Positive pitch looks down; flatten it as the drone drops to street level.
        look = 0.07 + 0.016 * max(0.0, self.alt - 4)
        cam.pitch = look + math.sin(t * 0.31 + 1.5) * 0.05
        if zoom_u is not None:
            # Aim the airframe at the billboard: climb to its centre, level the horizon.
            e = min(1.0, zoom_u * 2.2)
            e = e * e * (3 - 2 * e)
            cam.pos[1] = self.alt = self.alt + (12.0 - self.alt) * e
            cam.pos[0] = cam.pos[0] + (self.lane - cam.pos[0]) * e
            dz = max(4.0, self.board_z - z)
            cam.yaw *= 1 - e
            cam.roll = cam.roll * (1 - e) + random.uniform(-0.015, 0.015) * zoom_u
            cam.pitch = cam.pitch * (1 - e) + math.atan2(cam.pos[1] - 12.0, dz) * e

        self.sky(s, now)
        if th["day"] < 0.3:
            self.stars.draw(s, dt, speed=self.speed * 0.6, streak=boost > 0.2)
            hy = self.hy
            blank = [" "] * self.w
            for y in range(hy, self.h):  # stars only in the sky
                s.ch[y] = blank[:]
        fog = self.fog_dist
        # Keep the street floor and curbs legible in rain as well as dry weather.
        self.road_color = blend(th["ground"], (70, 72, 80), 0.25)
        curb = blend(th["ground"], (150, 150, 158), 0.35 + 0.2 * th["day"])
        lx, rh = self.lane, self.road_hw
        walk = blend(th["ground"], (120, 120, 128), 0.18 + 0.12 * th["day"])
        for xa, xb in ((self.street_x0, lx - rh), (lx + rh, self.street_x1)):
            self.fill_world(s, [(xa, 0, z + .5), (xb, 0, z + .5), (xb, 0, z + fog), (xa, 0, z + fog)], walk)
        self.fill_world(s, [(lx - rh, 0, z + .5), (lx + rh, 0, z + .5), (lx + rh, 0, z + fog), (lx - rh, 0, z + fog)], self.road_color)
        for xa, xb in ((lx - rh - .3, lx - rh), (lx + rh, lx + rh + .3)):
            self.fill_world(s, [(xa, .05, z + .5), (xb, .05, z + .5), (xb, .05, z + fog), (xa, .05, z + fog)], curb)
        # street centre line
        z0 = math.floor(z / 6) * 6
        dash = blend(YELLOW, th["ground"], 0.5)
        for k in range(1, 12):
            zz = z0 + k * 6
            cam.line(s, (self.lane, 0, zz), (self.lane, 0, zz + 2.5), dash, fog=fog, char="│")

        if not (self.tunnel and self.tunnel[0] <= z <= self.tunnel[1]):
            self.street_props(s, now, t)
        # Road expansion seams, curb lines and drainage grates in world space.
        asphalt = blend(th["ground"], GREY, 0.19)
        for k in range(3, 17, 3):
            zz = z0 + k * 4
            cam.line(s, (self.lane+1.4, .03, zz), (self.lane+1.8, .03, zz+.7), asphalt, fog=fog, char="=")

        cell = self.city.cell
        gx0 = int(cam.pos[0] // cell)
        gz0 = int(z // cell)
        zfar = gz0 + int(fog // cell) + 2
        boxes = [b for gx in range(gx0, gx0 + 2) for gz in range(gz0 - 1, zfar)
                 for b in self.city.buildings(gx, gz) if b[3] > z - 2 and not self.blocked(b)]
        # Rows behind the street frontage only matter where they rise above it.
        back = [b for gx in (gx0 - 1, gx0 + 2) for gz in range(gz0, zfar)
                for b in self.city.buildings(gx, gz) if not self.blocked(b)]
        # Only the city beyond the exit belongs in the tunnel's portal view.
        in_tunnel = self.tunnel is not None and self.tunnel[0] <= z <= self.tunnel[1]
        if in_tunnel:
            boxes = [b for b in boxes if b[1] >= self.tunnel[1]]
            back = [b for b in back if b[1] >= self.tunnel[1]]
        self.front_rows = set(boxes)
        boxes += back
        extras = [(1e6, self.billboard_fn(now))]
        px_, pz_ = cam.pos[0], cam.pos[2]
        # Decoration is expensive: skip blocks whose facade and roof kit are
        # completely outside the view. Keep near-plane straddlers conservatively.
        visible_decor = boxes
        if boxes and any(b in self.front_rows for b in boxes):
            # Decoration is limited to 70 world units, so distant blocks need
            # no roof-expanded projection at all; the city still renders them.
            front = self.front_rows
            decor_boxes = [b for b in boxes if b in front and ((b[0] + b[2]) / 2 - px_) ** 2 +
                           ((b[1] + b[3]) / 2 - pz_) ** 2 < 70 * 70]
            bounds = np.array([self.city.corners(b) for b in decor_boxes], dtype=float).reshape(-1, 8, 3)
            bounds[:, 4:, 1] += 5.0
            vx, vy, vz = view_np(cam, bounds)
            zsafe = np.maximum(vz, NEAR)
            sx = cam.cx + vx / zsafe * (cam.f * 2)
            sy = cam.cy - vy / zsafe * cam.f
            off = (vz.min(axis=1) >= NEAR) & ((sx.max(axis=1) < -3) | (sx.min(axis=1) >= self.w + 3) | (sy.max(axis=1) < -3) | (sy.min(axis=1) >= self.h + 3))
            visible_decor = [decor_boxes[i] for i in np.nonzero((vz.max(axis=1) >= NEAR) & ~off)[0]]
        self.facades, self.facade_pal = self.prepare_facades(s, visible_decor)
        for b in visible_decor:
            cx_, cz_ = (b[0] + b[2]) / 2 - px_, (b[1] + b[3]) / 2 - pz_
            d2 = cx_ * cx_ + cz_ * cz_
            if d2 < 70 * 70:
                extras.append((d2 - 1e-3, lambda s, b=b: self.decorate(s, b, now)))
        theme = dict(th)
        self.city_faces = dict(self.mat_faces)
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
        if inside and self.board_z < self.tunnel[1]:
            extras[0] = (0, lambda s: None)
        if police_t is not None:
            police_t, pe = self.police_draw(now)
            if not inside:
                extras.append(pe)
        if not inside or self.tunnel[1] - z < 42.0 + self.TUN_RING:
            self.city.draw(s, cam, boxes, fog=fog, theme=theme, extras=extras, tick=now * 2, win_dist=0.0)
        if inside:
            self.tunnel_view(s, now, True)
            if police_t is not None:
                pe[1](s)
        if self.rain and not inside:
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
        if zoom_u is not None and zoom_u > 0.15:
            self.zoom_lock(s, now, zoom_u)
        if self.flash is not None:
            ft = (now - self.flash) / 0.45
            if ft >= 1:
                self.flash = None
            else:
                a = round((1 - ft) * 0.85, 2)
                for y in range(self.h):
                    self.fx.tint(s, y, blend(WHITE, PINK, ft), a)
                if ft < 0.7:
                    s.center(self.h // 2, "  BILLBOARD HIJACKED // DEDSEC  ", PINK)
        self.hud(s, now, zoom_u is not None, police_t)
        if random.random() < 0.004:
            self.callout = (random.choice(CALLOUTS), now)
        self.fx.apply(s, now, glitch)

    ZOOM_T = 2.3

    def zoom_lock(self, s, now, u):
        """Target brackets around the billboard during the dive."""
        cam = self.cam
        z = self.board_z
        a = cam.project((self.lane - 11.7, 20.7, z))
        b = cam.project((self.lane + 11.7, 3.3, z))
        if not a or not b:
            return
        x0, y0 = int(max(1, a[0])), int(max(3, a[1]))
        x1, y1 = int(min(s.w - 2, b[0])), int(min(s.h - 4, b[1]))
        if x1 - x0 < 8 or y1 - y0 < 4:
            return
        col = PINK if int(now * 8) % 2 else WHITE
        s.brackets(x0, y0, x1 - x0 + 1, y1 - y0 + 1, col, arm=3)
        label = "LOCK // BILLBOARD %d m" % max(0, int((z - cam.pos[2]) * 1.0))
        s.text(x0 + 1, max(3, y0 - 1), label, col)

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

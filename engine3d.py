"""Tiny perspective 3D engine for terminal cells (2:1 aspect)."""

import math
import random

from lib import BLACK, CYAN, DIM_CYAN, DIM_PINK, PINK, PURPLE, WHITE, YELLOW, blend, line_points
from widgets import edge_char

NEAR = 0.15


def clip2d(x0, y0, x1, y1, w, h):
    """Liang-Barsky clip of a segment to the screen rectangle."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, w - 1 - x0), (-dy, y0), (dy, h - 1 - y0)):
        if p == 0:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return None
                t0 = max(t0, t)
            else:
                if t < t0:
                    return None
                t1 = min(t1, t)
    return t0, t1


class Camera:
    def __init__(self, w, h, fov=1.0):
        self.w, self.h = w, h
        self.cx, self.cy = w / 2, h / 2
        self.f = h * fov
        self.pos = [0.0, 0.0, 0.0]
        self.yaw = self.pitch = self.roll = 0.0

    def to_view(self, p):
        key = (self.yaw, self.pitch, self.roll)
        if key != getattr(self, "_key", None):
            self._key = key
            self._t = (math.cos(-self.yaw), math.sin(-self.yaw), math.cos(-self.pitch), math.sin(-self.pitch),
                       math.cos(-self.roll), math.sin(-self.roll))
        cy_, sy_, cp, sp, cr, sr = self._t
        x, y, z = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
        y, z = y * cp - z * sp, y * sp + z * cp
        if self.roll:
            x, y = x * cr - y * sr, x * sr + y * cr
        return x, y, z

    def project_view(self, v):
        x, y, z = v
        return self.cx + x / z * self.f * 2, self.cy - y / z * self.f, z

    def project(self, p):
        v = self.to_view(p)
        if v[2] < NEAR:
            return None
        return self.project_view(v)

    def line(self, s, a, b, color, fog=40.0, char=None):
        va, vb = self.to_view(a), self.to_view(b)
        if va[2] < NEAR and vb[2] < NEAR:
            return
        if va[2] < NEAR or vb[2] < NEAR:
            # clip against the near plane
            if va[2] < NEAR:
                va, vb = vb, va
            t = (va[2] - NEAR) / (va[2] - vb[2])
            vb = tuple(va[i] + (vb[i] - va[i]) * t for i in range(3))
        x0, y0, z0 = self.project_view(va)
        x1, y1, z1 = self.project_view(vb)
        c = clip2d(x0, y0, x1, y1, s.w, s.h)
        if not c:
            return
        ch = char or edge_char(x1 - x0, y1 - y0)
        ta, tb = c
        ax, ay, az = x0 + (x1 - x0) * ta, y0 + (y1 - y0) * ta, z0 + (z1 - z0) * ta
        bx, by, bz = x0 + (x1 - x0) * tb, y0 + (y1 - y0) * tb, z0 + (z1 - z0) * tb
        pts = line_points(int(ax), int(ay), int(bx), int(by))
        # colour in a few depth steps instead of per cell
        n = len(pts)
        steps = max(1, min(6, n // 4))
        for k in range(steps):
            z = az + (bz - az) * (k + 0.5) / steps
            col = blend(color, BLACK, min(0.92, z / fog))
            for x, y in pts[k * n // steps:(k + 1) * n // steps]:
                s.put(x, y, ch, col)

    def point(self, s, p, ch, color, fog=40.0):
        q = self.project(p)
        if q:
            s.put(int(q[0]), int(q[1]), ch, blend(color, BLACK, min(0.92, q[2] / fog)))
        return q


class Floor:
    """Synthwave neon grid scrolling towards the viewer."""

    def __init__(self, w, h, horizon=0.55, color=PURPLE, spacing=2.0):
        self.cam = Camera(w, h, fov=0.9)
        self.cam.pos = [0.0, 3.2, 0.0]
        self.cam.cy = h * horizon
        self.color, self.spacing = color, spacing

    def draw(self, s, now, speed=4.0, sway=0.0):
        cam = self.cam
        cam.roll = sway
        off = (now * speed) % self.spacing
        far = 36
        z = self.spacing - off + 0.5
        last_row = None
        while z < far:
            row = int(cam.cy + cam.pos[1] / z * cam.f)
            if row != last_row:
                cam.line(s, (-80, 0, z), (80, 0, z), self.color, fog=far, char="─")
                last_row = row
            z *= 1.0 + 0.35 * self.spacing / 2 if z > 6 else 1
            z += self.spacing if z <= 6 else 0
        for i in range(-30, 31):
            x = i * self.spacing * 0.9
            cam.line(s, (x, 0, 0.6), (x, 0, far), self.color, fog=far)


class Starfield:
    """3D star tunnel; speed > 0 flies forward."""

    def __init__(self, w, h, n=160, chars="·•*", colors=(WHITE, CYAN, PINK)):
        self.cam = Camera(w, h)
        self.stars = [[random.uniform(-20, 20), random.uniform(-12, 12), random.uniform(1, 40), random.choice(colors)] for _ in range(n)]
        self.chars = chars

    def draw(self, s, dt, speed=10.0, streak=False):
        for st in self.stars:
            st[2] -= speed * dt
            if st[2] < 0.5:
                st[0], st[1], st[2] = random.uniform(-20, 20), random.uniform(-12, 12), 40
            p = self.cam.project(st[:3])
            if not p:
                continue
            k = 1 - min(1, st[2] / 40)
            ch = self.chars[min(len(self.chars) - 1, int(k * len(self.chars)))]
            col = blend(BLACK, st[3], k)
            if streak and speed > 15:
                self.cam.line(s, st[:3], (st[0], st[1], st[2] + speed * 0.06), st[3], fog=40)
            s.put(int(p[0]), int(p[1]), ch, col)


class Rotator:
    """Rotates screen-space art (cells + depth) around a pivot, with weak perspective."""

    def __init__(self, cx, cy, dist=70.0):
        self.cx, self.cy, self.dist = cx, cy, dist
        self.set(0, 0, 0)

    def set(self, yaw, pitch, roll=0.0):
        self.yaw, self.pitch, self.roll = yaw, pitch, roll
        self.t = (math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll))

    def rot(self, x, y, z):
        cy_, sy_, cp, sp, cr, sr = self.t
        X, Y, Z = (x - self.cx) * 0.5, y - self.cy, z
        X, Z = X * cy_ + Z * sy_, -X * sy_ + Z * cy_
        Y, Z = Y * cp - Z * sp, Y * sp + Z * cp
        X, Y = X * cr - Y * sr, X * sr + Y * cr
        return X, Y, Z

    def proj(self, x, y, z=0.0):
        X, Y, Z = self.rot(x, y, z)
        k = self.dist / max(1.0, self.dist + Z)
        return int(self.cx + X * 2 * k), int(self.cy + Y * k), Z


class City:
    """Procedural wireframe city on a grid; blocks are generated around the camera."""

    def __init__(self, block=8.0, street=4.0, seed=None):
        self.block, self.street = block, street
        self.cell = block + street
        self.rng = random.Random(seed)
        self.cache = {}

    def buildings(self, gx, gz):
        key = (gx, gz)
        if key not in self.cache:
            r = random.Random(hash(key) ^ 0x5EED)
            out = []
            n = r.choice((1, 2, 2, 4))
            sub = self.block / (2 if n > 1 else 1)
            for i in range(n):
                ox = (i % 2) * sub
                oz = (i // 2) * sub
                h = r.uniform(2, 14) if r.random() < 0.85 else r.uniform(16, 30)
                x0 = gx * self.cell + ox + 0.4
                z0 = gz * self.cell + oz + 0.4
                out.append((x0, z0, x0 + sub - 0.8, z0 + (sub if n == 4 else self.block) - 0.8, h,
                            r.choice((CYAN, CYAN, PINK, PURPLE))))
            self.cache[key] = out
            if len(self.cache) > 4000:
                self.cache.clear()
        return self.cache[key]

    def draw(self, s, cam, radius=5, fog=60.0, windows=True, tick=0.0, lateral=3):
        gx0 = int(cam.pos[0] // self.cell)
        gz0 = int(cam.pos[2] // self.cell)
        items = []
        for gx in range(gx0 - lateral, gx0 + lateral + 1):
            for gz in range(gz0 - radius, gz0 + radius + 1):
                for b in self.buildings(gx, gz):
                    cx = (b[0] + b[2]) / 2 - cam.pos[0]
                    cz = (b[1] + b[3]) / 2 - cam.pos[2]
                    vz = cam.to_view(((b[0] + b[2]) / 2, b[4] / 2, (b[1] + b[3]) / 2))[2]
                    if vz < -self.cell or vz > fog:
                        continue
                    items.append((cx * cx + cz * cz, b))
        items.sort(key=lambda it: -it[0])
        px, py, pz = cam.pos
        for d2, (x0, z0, x1, z1, h, col) in items:
            faces = []
            if pz < z0:
                faces.append(("front", [(x0, 0, z0), (x1, 0, z0), (x1, h, z0), (x0, h, z0)]))
            elif pz > z1:
                faces.append(("front", [(x1, 0, z1), (x0, 0, z1), (x0, h, z1), (x1, h, z1)]))
            if px < x0:
                faces.append(("side", [(x0, 0, z1), (x0, 0, z0), (x0, h, z0), (x0, h, z1)]))
            elif px > x1:
                faces.append(("side", [(x1, 0, z0), (x1, 0, z1), (x1, h, z1), (x1, h, z0)]))
            if py > h:
                faces.append(("top", [(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)]))
            for kind, quad in faces:
                pts = [cam.project(q) for q in quad]
                if all(pts):
                    if kind == "top":
                        fill_poly(s, [(p[0], p[1]) for p in pts], "░", blend(col, BLACK, min(0.95, 0.75 + pts[0][2] / fog * 0.25)))
                    else:
                        fill_poly(s, [(p[0], p[1]) for p in pts], " ", None)
            for kind, quad in faces:
                ecol = col if kind != "side" else blend(col, BLACK, 0.35)
                for i in range(4):
                    cam.line(s, quad[i], quad[(i + 1) % 4], ecol, fog=fog)
                if windows and kind != "top" and d2 < (self.cell * 3) ** 2:
                    r = random.Random(int(x0 * 7 + z0 * 13) + (kind == "side"))
                    a, b = quad[0], quad[1]
                    span = max(1, int(math.dist((a[0], a[2]), (b[0], b[2])) * 1.5))
                    for wy in range(1, int(h), 2):
                        for wx in range(1, span):
                            if r.random() < 0.4:
                                t = wx / span
                                p3 = (a[0] + (b[0] - a[0]) * t, wy + 0.5, a[2] + (b[2] - a[2]) * t)
                                lit = r.random() < 0.45 or int(tick + wx * 3 + wy) % 11 == 0
                                cam.point(s, p3, "▪", YELLOW if lit else DIM_CYAN, fog=fog)


def fill_poly(s, pts, ch, color):
    """Scanline fill of a convex polygon in screen space."""
    ys = [p[1] for p in pts]
    y0, y1 = max(0, int(min(ys))), min(s.h - 1, int(max(ys)))
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
            xa, xb = max(0, int(min(xs))), min(s.w - 1, int(max(xs)))
            row_c, row_f, row_t, row_b = s.ch[y], s.fg[y], s.pt[y], s.pb[y]
            for x in range(xa, xb + 1):
                row_c[x] = ch
                row_f[x] = color
                row_t[x] = row_b[x] = None

"""HOLOGRAM: voxel DedSec skull spinning over a projector, orbit rings, dolly zoom, trails."""

import math
import random
import time

from lib import (BLACK, CYAN, DIM_CYAN, GREY, PINK, PURPLE, WHITE, YELLOW, Glitch, blend,
                 pulse)
from mode_logo import FONT, SKULL
from sysdata import DATA
from widgets import SHAPES, Panels, Particles, PostFX, rot

NAME = "HOLOGRAM"


def extrude(filled, accent=(), depth=2):
    """Grid cells -> hollow voxel slab: both faces plus the side walls. Voxel = (x, y, z, kind)
    with kind 0 = wall, 1 = face, 2 = accent (eyes)."""
    cs = [c for c, r in filled]
    rs = [r for c, r in filled]
    mx, my = (min(cs) + max(cs)) / 2, (min(rs) + max(rs)) / 2
    vox = []
    for (c, r) in filled:
        edge = any((c + dx, r + dy) not in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for z in range(-depth, depth + 1):
            if abs(z) == depth or edge:
                vox.append((c - mx, r - my, z * 0.9, 1 if abs(z) == depth else 0))
    for (c, r) in accent:
        for z in (-(depth + 1), depth + 1):
            vox.append((c - mx, r - my, z * 0.9, 2))
    return vox


def build_skull():
    return extrude({(c, r) for r, row in enumerate(SKULL) for c, ch in enumerate(row) if ch == "X"})


EYE = ["X...X", ".X.X.", "..X..", ".X.X.", "X...X"]


def build_mask():
    """Wrench's LED mask: chamfered plate with two X_X eyes and a grille mouth popping out."""
    w, h = 25, 13
    filled = set()
    for r in range(h):
        cut = (2 - r) if r < 2 else (r - (h - 4)) * 2 if r > h - 4 else 0
        for c in range(cut, w - cut):
            filled.add((c, r))
    accent = []
    for ox in (3, w - 8):
        for r, row in enumerate(EYE):
            for c, ch in enumerate(row):
                if ch == "X":
                    accent.append((ox + c, 2 + r))
    for c in range(7, w - 7, 2):
        accent.append((c, h - 3))
    return extrude(filled, accent, depth=1)


def build_letters(word="DS", scale=2):
    filled = set()
    x0 = 0
    for letter in word:
        for r, row in enumerate(FONT[letter]):
            for c, ch in enumerate(row):
                if ch != " ":
                    for i in range(scale):
                        for j in range(scale):
                            filled.add((x0 + c * scale + i, r * scale + j))
        x0 += (len(FONT[letter][0]) + 1) * scale
    vox = extrude(filled)
    # second letter glows pink on its faces, like the DedSec logo colours
    split = (len(FONT[word[0]][0]) + 0.5) * scale - x0 / 2
    return [(x, y, z, 2 if (k == 1 and x > split) else k) for (x, y, z, k) in vox]


MORPH = 2.6
SHAPE_NAMES = ["DEDSEC.OBJ", "WRENCH.OBJ", "DS_LOGO.OBJ"]


def pad(vox, n):
    """Order voxels top-to-bottom and stretch the list to n entries (duplicates flagged)."""
    vox = sorted(vox, key=lambda v: (round(v[1]), v[0], v[2]))
    m = len(vox)
    out, last = [], -1
    for i in range(n):
        j = int(i * m / n)
        out.append(vox[j] + (j == last,))
        last = j
    return out


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.glitch = Glitch(0.012)
        self.fx = PostFX(band_speed=5)
        self.particles = Particles()
        shapes = [build_skull(), build_mask(), build_letters()]
        self.counts = [len(v) for v in shapes]
        n = max(self.counts)
        self.shapes = [pad(v, n) for v in shapes]
        self.cur, self.nxt = 0, 1
        self.morph_t = None
        self.next_morph = time.time() + random.uniform(7, 10)
        self.delay = [random.uniform(0, 0.45) for _ in range(n)]
        self.bump = 0.0
        self.ring_t = 0.0
        self.nvox = self.counts[0]
        self.scale = 1.45 if h >= 40 and w >= 120 else 1.0
        self.bw, self.bh = math.ceil(2 * self.scale), math.ceil(self.scale)
        self.cx, self.cy = w / 2, h / 2 - 2
        rw = int(15 * self.scale * 2 + 4)
        self.panels = Panels(w, h, keepout=[(int(self.cx - rw), 2, rw * 2, h - 4)], max_panels=4, kinds=["eq", "radar", "cube", "bars", "spark", "cam"])
        self.prev = None
        self.last = time.time()
        self.sats = [(random.choice(SHAPES), random.uniform(0, math.tau), random.uniform(0.4, 0.9)) for _ in range(3)]
        self.ghosts = []
        self.voxel_palette = [[blend(BLACK, col, (k + 3) / 18) for k in range(16)]
                              for col in (blend(CYAN, PURPLE, 0.5), CYAN, PINK)]

    def project(self, x, y, z, D):
        k = D / max(1.0, D + z)
        return self.cx + x * 2 * k * self.zoom, self.cy + y * k * self.zoom, z

    def ring(self, s, radius, tilt, spin, color, front, D, dots=3, now=0.0):
        bump = self.bump
        dim = (0.55 if front else 0.8) - 0.3 * bump
        dot_col = blend(color, BLACK, dim)
        for i in range(90):
            a = i / 90 * math.tau
            p = rot((math.cos(a) * radius, 0, math.sin(a) * radius), tilt, spin)
            if (p[2] < 0) == front:
                x, y, z = self.project(*p, D)
                s.put(int(x), int(y), "·", dot_col)
        head = blend(color, WHITE, bump * 0.6)
        trail = 6 + int(bump * 6)
        for d in range(dots):
            a = self.ring_t * 1.2 + d * math.tau / dots
            for k in range(trail):
                p = rot((math.cos(a - k * 0.06) * radius, 0, math.sin(a - k * 0.06) * radius), tilt, spin)
                if (p[2] < 0) == front:
                    x, y, z = self.project(*p, D)
                    s.put(int(x), int(y), "●" if k == 0 else "•", blend(head, BLACK, k / trail))

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        self.bump = max(DATA.beat, self.bump - dt * 3.5)
        self.ring_t += dt * (1 + 1.2 * DATA.level + 1.5 * self.bump)

        # motion trails: fade the previous frame into this one
        if self.prev:
            pch, pfg = self.prev
            for y in range(s.h):
                rc, rf, qc, qf = s.ch[y], s.fg[y], pch[y], pfg[y]
                for x in range(s.w):
                    c = qf[x]
                    ch = qc[x]
                    if c is not None and ch in "█▓▒●" and (c[0] + c[1] + c[2]) > 90:
                        rc[x] = "▒" if ch in "█▓" else "░"
                        rf[x] = (c[0] * 40 // 100, c[1] * 40 // 100, c[2] * 40 // 100)

        # dolly zoom: perspective strength changes while the size is compensated
        dz = pulse(now, 0.35)
        D = 25 + dz * 140
        self.zoom = self.scale * (0.85 + 0.25 * (1 - dz))

        yaw = now * 0.9
        pitch = math.sin(now * 0.5) * 0.35
        roll = math.sin(now * 0.23) * 0.12

        base_y = 11
        self.panels.draw(s, now)
        # projector base and light cone, pumping with the beat
        base_col = blend(blend(CYAN, BLACK, 0.3), WHITE, self.bump * 0.5)
        cone_col = blend(blend(DIM_CYAN, BLACK, 0.4), CYAN, self.bump * 0.6)
        for i in range(36):
            a = i / 36 * math.tau + now * 0.4
            bx, bz = math.cos(a) * 9, math.sin(a) * 9
            p0 = rot((bx, base_y, bz), pitch * 0.3, 0)
            x0, y0, _ = self.project(*p0, D)
            s.put(int(x0), int(y0), "▄" if i % 2 else "▀", base_col)
            if i % 6 == 0:
                p1 = rot((bx * 1.6, -9, bz * 1.6), pitch * 0.3, 0)
                x1, y1, _ = self.project(*p1, D)
                s.line(int(x0), int(y0), int(x1), int(y1), "·", cone_col)
        # Machined projector housing: layered decks, cooling fins and concentric
        # calibration marks follow the same perspective as the floating object.
        rings = []
        for yy, rr, col in ((base_y + 1.6, 9.6, (24, 34, 48)),
                            (base_y + 0.8, 10.0, (58, 72, 86)),
                            (base_y + 0.25, 9.2, (26, 48, 58))):
            ring = []
            for k in range(48):
                a = k / 48 * math.tau
                px, py, z = self.project(math.cos(a) * rr, yy, math.sin(a) * rr, D)
                ring.append((px, py, z))
                if k:
                    b = ring[k - 1]
                    s.pixel_line(int(b[0]), int(b[1] * 2), int(px), int(py * 2), col)
            rings.append(ring)
        for k in range(0, 48, 3):
            a, b = rings[0][k], rings[2][k]
            s.pixel_line(int(a[0]), int(a[1] * 2), int(b[0]), int(b[1] * 2), (90, 110, 122))
        for x, py, col in self.ghosts:
            s.pixel(x, py, blend(col, BLACK, 0.75))
        for _ in range(1 + int(self.bump * 3)):
            if random.random() > 0.6:
                continue
            a = random.uniform(0, math.tau)
            x, y, _ = self.project(math.cos(a) * 7, base_y, math.sin(a) * 7, D)
            self.particles.add(x, y, 0, -random.uniform(4, 9) * (1 + self.bump), random.uniform(1, 2.5), "·•+", CYAN)

        self.ring(s, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, False, D, now=now)
        self.ring(s, 16, 0.4, -now * 0.2, PURPLE, False, D, dots=2, now=now)

        # voxel model (morphing between shapes), painter-sorted back to front
        mt = None
        if self.morph_t is None and now > self.next_morph:
            self.morph_t = now
            self.glitch.trigger(now, 0.25)
        if self.morph_t is not None:
            mt = (now - self.morph_t) / MORPH
            if mt >= 1:
                self.cur, self.nxt = self.nxt, (self.nxt + 1) % len(self.shapes)
                self.morph_t, mt = None, None
                self.next_morph = now + random.uniform(8, 12)
                self.particles.burst(self.cx, self.cy, 40, (CYAN, PINK, WHITE), speed=18)
        cyw, syw = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        pts = []
        src_v = self.shapes[self.cur]
        if mt is None:
            for (x, y, z, kind, dup) in src_v:
                if dup:
                    continue
                x, z = x * cyw + z * syw, -x * syw + z * cyw
                y, z = y * cp - z * sp, y * sp + z * cp
                pts.append((z, x * cr - y * sr, x * sr + y * cr, kind, 0.0))
        else:
            dst_v = self.shapes[self.nxt]
            delay = self.delay
            for i, (a_, b_) in enumerate(zip(src_v, dst_v)):
                # each voxel flies on its own schedule: scanline-ish sweep plus noise
                q = (mt * 1.6 - delay[i] - (b_[1] + 8) / 16 * 0.4) / 0.75
                q = 0.0 if q < 0 else 1.0 if q > 1 else q
                if (a_[4] and q < 0.5) or (b_[4] and q >= 0.5):
                    continue
                e = q * q * (3 - 2 * q)
                arc = math.sin(q * math.pi)
                x = a_[0] + (b_[0] - a_[0]) * e
                y = a_[1] + (b_[1] - a_[1]) * e - arc * 2.5
                z = a_[2] + (b_[2] - a_[2]) * e + arc * (delay[i] - 0.22) * 18
                x, z = x * cyw + z * syw, -x * syw + z * cyw
                y, z = y * cp - z * sp, y * sp + z * cp
                pts.append((z, x * cr - y * sr, x * sr + y * cr, a_[3] if q < 0.5 else b_[3], arc))
        pts.sort(key=lambda t: -t[0])
        self.nvox = len(pts)
        flick = 0.85 + 0.15 * random.random() + 0.2 * self.bump
        tear = {}
        bw, bh = self.bw, self.bh
        hx, hy = bw // 2, bh // 2
        chs, fgs = s.ch, s.fg
        W, H = s.w, s.h
        kz = self.zoom
        cx0, cy0 = self.cx, self.cy
        body = blend(CYAN, PURPLE, 0.5)
        ghosts = []
        for Z, X, Y, kind, arc in pts:
            k = D / max(1.0, D + Z) * kz
            light = (1 - (Z + 12) / 24) * flick
            if arc > 0.05:
                # in transit: glitchy, flickering, half dissolved
                if random.random() < arc * 0.35:
                    continue
                col = blend(PINK, WHITE, random.random()) if random.random() < 0.3 else blend(CYAN, PINK, arc)
                ch = "▒" if arc > 0.5 else "▓"
            elif kind == 2:
                col = blend(blend(PINK, BLACK, 0.5), PINK, light)
                ch = "█"
            else:
                col = blend(DIM_CYAN, CYAN if kind else body, light)
                ch = "█" if kind else "▓"
            if Z < -9:
                col = blend(col, WHITE, 0.3)
            if arc <= 0.05:
                level = max(0, min(15, int(light * 12)))
                col = self.voxel_palette[min(2, kind)][level]
            ix, iy = int(cx0 + X * 2 * k) - hx, int(cy0 + Y * k) - hy
            if glitch:
                if iy not in tear:
                    tear[iy] = random.randint(-6, 6) if random.random() < 0.25 else 0
                ix += tear[iy]
            for yy in range(max(0, iy), min(H, iy + bh)):
                rc, rf = chs[yy], fgs[yy]
                for xx in range(max(0, ix), min(W, ix + bw)):
                    # Each voxel has a little bevel and a recessed seam: pixel
                    # top/bottom shading adds relief instead of flat cell blocks.
                    rc[xx] = " "
                    s.pt[yy][xx] = blend(col, WHITE, 0.18) if yy == iy else col
                    s.pb[yy][xx] = blend(col, BLACK, 0.3) if xx == ix + bw - 1 else col
            if len(ghosts) < 300 and kind != 0:
                ghosts.append((ix, iy * 2, col))
        self.ghosts = ghosts

        self.ring(s, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, True, D, now=now)
        self.ring(s, 16, 0.4, -now * 0.2, PURPLE, True, D, dots=2, now=now)

        # wireframe satellites
        for i, ((verts, edges), ph, sp) in enumerate(self.sats):
            a = now * sp + ph
            c = rot((math.cos(a) * 24, math.sin(a * 1.3) * 4, math.sin(a) * 24), 0.25, 0)
            x, y, z = self.project(*c, D)
            size = 2.2 * self.zoom * (1.2 if z < 0 else 0.8)
            for va, vb in edges:
                pa = rot(verts[va], now * 1.3, now * 0.9 + i)
                pb = rot(verts[vb], now * 1.3, now * 0.9 + i)
                s.line(int(x + pa[0] * size * 2), int(y + pa[1] * size), int(x + pb[0] * size * 2), int(y + pb[1] * size),
                       "·", YELLOW if z < 0 else blend(YELLOW, BLACK, 0.6))

        self.particles.step(s, dt)

        s.text(2, 0, "HOLO-PROJECTOR // " + SHAPE_NAMES[self.cur], CYAN)
        s.text(2, 1, "VOXELS %d   YAW %03d°   FOCAL %3dmm" % (self.nvox, math.degrees(yaw) % 360, D), GREY)
        if mt is not None:
            bar = int(mt * 16)
            msg = "MORPH > %s  %s%s %3d%%" % (SHAPE_NAMES[self.nxt], "▓" * bar, "░" * (16 - bar), mt * 100)
            s.text(2, 2, msg, PINK if int(now * 8) % 2 else YELLOW)
        st = "● TRANSMITTING" if int(now * 2) % 2 else "○ TRANSMITTING"
        s.text(self.w - len(st) - 2, 0, st, PINK)
        s.center(self.h - 2, "> WE ARE DEDSEC. WE SEE EVERYTHING. <", blend(PINK, WHITE, pulse(now, 3) * 0.5))
        self.fx.apply(s, now, glitch)

        self.prev = ([row[:] for row in s.ch], [row[:] for row in s.fg])

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "scan", "PROJECTOR // VOXELS RECALLED", CYAN)
        if t >= 1:
            return
        # Projected particles are sucked into the emitter before its final blink.
        if t < 0.85:
            for i in range(48):
                a = i * 2.39996 + t * 5
                radius = (1 - t) ** 2 * min(s.w / 3, s.h)
                x = s.w / 2 + math.cos(a) * radius * 2
                y = s.h * 0.7 + math.sin(a) * radius * 0.5
                s.pixel(int(x), int(y * 2), blend(CYAN, WHITE, i % 3 / 4))
        else:
            s.put(s.w // 2, int(s.h * 0.7), "·", blend(CYAN, BLACK, t))

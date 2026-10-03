"""HOLOGRAM: a translucent, normal-shaded point-cloud object (DedSec skull, Wrench mask, DS logo)
projected by an emitter standing on a glowing floor in a dark lab.

Each object is a surface cloud with normals (rounded relief from a distance field): key light,
cyan fresnel rim, scanlines and a sweeping beam give it volume, and thin parts stay see-through.
Between objects a glowing slice rises from the base: the old shape dissolves above it into
motes that spiral away on arcs with trails, the new one is printed below it, so a recognisable
shape is always on screen.  The room has data columns, a light cone with dust, floor rings that
answer DATA.beat and a squashed floor reflection of the hologram.  All pixel work is numpy.
"""

import math
import random
import time

import numpy as np

from lib import (BLACK, CYAN, DIM_CYAN, GREY, PINK, PURPLE, WHITE, YELLOW, Glitch, blend,
                 pulse)
from sysdata import DATA
from widgets import SHAPES, Particles, rot

NAME = "HOLOGRAM"

FONT = {
    "D": ["█████ ", "██  ██", "██  ██", "██  ██", "█████ "],
    "S": [" █████", "██    ", " ████ ", "    ██", "█████ "],
}

SHAPE_NAMES = ["DEDSEC.OBJ", "WRENCH.OBJ", "DS_LOGO.OBJ"]
SHAPE_INFO = ["SKULL // EMBLEM", "LED MASK // WRENCH", "LOGOTYPE // DS"]

CYCLE = 13.0          # seconds per object
MORPH_AT = 9.0        # the slice print starts here
MORPH = 4.0
S = 3                 # surface samples per world unit (set per screen size)


# ------------------------------------------------------------------ cloud building (init only)

def _box(a, r, axis):
    if r <= 0:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    hi = np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, range(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def _blur(a, r, n=2):
    for _ in range(n):
        a = _box(_box(a, r, 0), r, 1)
    return a


def _erode(m, diag):
    p = np.pad(m, 1)
    e = m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    if diag:
        e &= p[:-2, :-2] & p[:-2, 2:] & p[2:, :-2] & p[2:, 2:]
    return e


def _dist(mask, kmax):
    d = np.zeros(mask.shape, np.float32)
    cur = mask
    for k in range(kmax):
        d += cur
        cur = _erode(cur, k & 1)
    return d


def _grid(wu, hu):
    W, H = int(wu * S), int(hu * S)
    jj, ii = np.mgrid[0:H, 0:W]
    return (ii + 0.5 - W / 2) / S, (jj + 0.5 - H / 2) / S


def _soft(v, k=1.0):
    return np.clip(v * k, 0, 1)


def make_cloud(X, Y, mask, T, R, recess=None, drop=0.0, bulge=None, tone=None, emis=None,
               base=1.0, alpha=0.8, eye=None):
    """Distance-field relief -> surface samples (front, back and a thin side rim) with normals."""
    H, W = mask.shape
    zero = np.zeros((H, W), np.float32)
    tone = zero if tone is None else tone.astype(np.float32)
    emis = zero if emis is None else emis.astype(np.float32)
    recess = zero if recess is None else recess.astype(np.float32)
    d = _blur(np.maximum(_dist(mask, int(R * S) + 3) - 0.5, 0) / S, 1, 2)
    t = np.clip(d / R, 0, 1)
    h = T * np.sqrt(t * (2 - t))
    if bulge is not None:
        h = h * bulge
    h = np.maximum(h - drop * recess, 0.25)
    hs = np.maximum(_blur(h, 1, 1), 0.2)
    gy, gx = np.gradient(hs, 1.0 / S)
    nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    ao_f = (base * (1 - 0.92 * _soft(_blur(recess, 1, 1), 1.4))).astype(np.float32)
    jj, ii = np.nonzero(mask)
    x, y = X[jj, ii], Y[jj, ii]
    z = hs[jj, ii]
    nf = nrm[jj, ii]
    nb = nf * np.array([1, 1, -1], np.float32)
    tn, em = tone[jj, ii], emis[jj, ii]
    kb = (jj + ii) % 3 == 0                      # the back skin is only ever seen through gaps
    P = [np.stack([x, y, z], 1), np.stack([x[kb], y[kb], -z[kb]], 1)]
    N = [nf, nb[kb]]
    TN = [tn, tn[kb]]
    EM = [em, em[kb] * 0]
    AO = [ao_f[jj, ii], np.full(int(kb.sum()), base, np.float32)]
    # side rim: z-sweep along the outline so the object keeps a skin when it turns
    edge = mask & ~_erode(mask, 0)
    ej, ei = np.nonzero(edge)
    m = 9
    fr = np.linspace(-0.92, 0.92, m)[None, :]
    ez = hs[ej, ei][:, None] * fr
    mg = _blur(mask.astype(np.float32), 1, 2)
    my, mx = np.gradient(mg)
    ox, oy = -mx[ej, ei], -my[ej, ei]
    nn = np.sqrt(ox * ox + oy * oy) + 1e-6
    ex = np.repeat(X[ej, ei], m)
    ey = np.repeat(Y[ej, ei], m)
    P.append(np.stack([ex, ey, ez.ravel()], 1))
    N.append(np.stack([np.repeat(ox / nn, m), np.repeat(oy / nn, m), np.zeros(len(ex))], 1))
    TN.append(np.repeat(tone[ej, ei], m))
    EM.append(np.zeros(len(ex), np.float32))
    AO.append(np.full(len(ex), base * 0.9, np.float32))
    P = np.concatenate(P).astype(np.float32)
    # centre on the bounding box
    cxm, cym = (P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2
    P[:, 0] -= cxm
    P[:, 1] -= cym
    n = len(P)
    rng = np.random.RandomState(7 + n % 97)
    rk = np.concatenate([np.ones(len(x) + int(kb.sum()), np.float32), np.full(len(ex), 0.4, np.float32)])
    cloud = dict(rk=rk, P=P, N=np.concatenate(N).astype(np.float32),
                 tone=np.concatenate(TN).astype(np.float32), emis=np.concatenate(EM).astype(np.float32),
                 ao=np.concatenate(AO).astype(np.float32), alp=np.full(n, alpha, np.float32),
                 rnd=rng.rand(n).astype(np.float32), sw=(rng.choice([-1, 1], n) * rng.uniform(1.2, 3.0, n)).astype(np.float32))
    cloud["Y"] = np.ascontiguousarray(P[:, 1])
    cloud["ymin"], cloud["ymax"] = float(P[:, 1].min()), float(P[:, 1].max())
    # silhouette half-width per world row (for the print ring)
    rows = Y[:, 0] - cym
    hw = np.array([np.abs(X[j][mask[j]] - cxm).max() if mask[j].any() else 0.0 for j in range(H)])
    cloud["rows"], cloud["hw"] = rows, hw
    cloud["zmax"] = float(hs.max())
    # eye anchors for the glow bloom
    anchors = []
    if eye is not None:
        for side in (X < cxm, X >= cxm):
            sel = eye & side
            if sel.any():
                jy, ix = np.nonzero(sel)
                anchors.append((float(X[jy, ix].mean() - cxm), float(Y[jy, ix].mean() - cym),
                                float(hs[jy, ix].max()) + 0.4))
    cloud["anchors"] = anchors
    tn_, em_ = cloud["tone"][:, None], cloud["emis"][:, None]
    cloud["alb"] = ((ALB0 + (ALB1 - ALB0) * tn_) * cloud["ao"][:, None]).astype(np.float32)
    cloud["ecl"] = ((EM0 + (EM1 - EM0) * tn_) * em_ * 1.25).astype(np.float32)
    cloud["emk"] = (1 - 0.85 * cloud["emis"]).astype(np.float32)
    cloud["ema"] = (cloud["emis"] * 0.95).astype(np.float32)
    cloud["thumb"] = ((mask & (recess < 0.6)) | (emis > 0.5), np.maximum(tone * (tone > 0.5), (emis > 0.5) * 1.0), emis)
    return cloud


def build_skull():
    X, Y = _grid(22, 22)
    ax = np.abs(X)
    cran = (X / 8.0) ** 2 + ((Y + 3.0) / 7.6) ** 2 < 1
    mid = (Y > -1.0) & (Y < 5.4) & (ax < 6.3 - 0.32 * np.maximum(0, Y - 1.5))
    jaw = (Y >= 4.6) & ((X / 4.7) ** 2 + ((Y - 4.6) / 4.4) ** 2 < 1)
    nose = (Y > 1.7) & (Y < 4.3) & (ax < 0.35 + 0.55 * (Y - 1.7))
    mask = (cran | mid | jaw) & ~nose
    rec = np.zeros(X.shape, np.float32)
    eye = np.zeros(X.shape, bool)
    for sgn in (-1, 1):
        ex, ey = sgn * 3.1, -0.4
        c, s_ = math.cos(0.22 * sgn), math.sin(0.22 * sgn)
        u = ((X - ex) * c + (Y - ey) * s_) / 2.6
        v = (-(X - ex) * s_ + (Y - ey) * c) / 2.2
        e = u * u + v * v
        rec = np.maximum(rec, np.clip((1 - e) * 2.5, 0, 1))
        eye |= (u / 0.34) ** 2 + (v / 0.36) ** 2 < 1
    for k in range(-3, 4):
        rec = np.maximum(rec, ((np.abs(X - k * 1.3) < 0.2) & (Y > 5.3) & (Y < 8.2)).astype(np.float32) * 0.8)
    rec = np.maximum(rec, ((np.abs(Y - 5.05) < 0.25) & (ax < 4.4)).astype(np.float32) * 0.7)
    bulge = 1 + 0.25 * np.exp(-(((ax - 5.2) / 1.7) ** 2 + ((Y - 1.8) / 1.6) ** 2)) \
        + 0.04 * np.exp(-(((Y + 2.9) / 1.4) ** 2)) * (ax < 6.4)
    return make_cloud(X, Y, mask, 6.2, 4.2, rec, 4.6, bulge, tone=eye * 1.0, emis=eye, alpha=0.8, eye=eye)


def build_mask():
    X, Y = _grid(26, 15)
    ax, ay = np.abs(X), np.abs(Y)
    mask = (ax < 12) & (ay < 6.5) & (ax * 0.55 + ay < 11.1) & (ax < 12 - np.maximum(0, Y - 3) * 1.3)
    rec = (((ax < 10.3) & (ay < 4.9)) * 0.45).astype(np.float32)
    rec = np.maximum(rec, ((ax > 7.4) & (ax < 10.0) & ((np.abs(Y - 2.0) < 0.2) | (np.abs(Y - 3.0) < 0.2)
                                                      | (np.abs(Y - 4.0) < 0.2))) * 0.8)
    eye = np.zeros(X.shape, bool)
    for sgn in (-1, 1):
        ex, ey = sgn * 5.4, -1.4
        dx, dy = X - ex, Y - ey
        box = (np.abs(dx) < 2.3) & (np.abs(dy) < 2.3)
        eye |= box & ((np.abs(dx - dy) < 0.85) | (np.abs(dx + dy) < 0.85))
    bars = (np.abs(((X + 6.75) % 1.5) - 0.75) < 0.5) & (np.abs(X) < 6.7) & (Y > 2.9) & (Y < 4.3)
    rec = np.maximum(rec, eye * 0.9)
    rec = np.maximum(rec, ((np.abs(X) < 7.2) & (Y > 2.5) & (Y < 4.7)) * 0.35)
    emis = (eye | bars).astype(np.float32)
    tone = eye.astype(np.float32) * 1.0
    return make_cloud(X, Y, mask, 2.4, 2.2, rec, 0.7, None, tone=tone, emis=emis, base=0.8, alpha=0.88, eye=eye)


def build_letters():
    X, Y = _grid(33, 17)
    ras = np.zeros(X.shape, np.float32)
    tone = np.zeros(X.shape, np.float32)
    # D: flat spine on the left, round bowl on the right
    dx0, dxc, hr = -13.8, -8.0, 7.5
    outer = (X >= dx0) & (np.abs(Y) <= hr) & ((X <= dxc) | (((X - dxc) / 5.8) ** 2 + (Y / hr) ** 2 < 1))
    inner = (X >= dx0 + 3.9) & (np.abs(Y) <= hr - 3.7) & ((X <= dxc) | (((X - dxc) / 1.9) ** 2 + (Y / (hr - 3.7)) ** 2 < 1))
    ras[outer & ~inner] = 1
    # S: the blocky logo glyph, rounded by the blur below
    cw, ch = 2.3, 3.0
    x0 = 0.4
    for r, row in enumerate(FONT["S"]):
        for c, g in enumerate(row):
            if g != " ":
                xa, ya = x0 + c * cw, -2.5 * ch + r * ch
                sel = (X >= xa - 0.15) & (X < xa + cw + 0.15) & (Y >= ya - 0.15) & (Y < ya + ch + 0.15)
                ras[sel] = 1
                tone[sel] = 1
    mask = _blur(ras, 2, 2) > 0.5
    rec = np.zeros(X.shape, np.float32)
    return make_cloud(X, Y, mask, 2.6, 1.3, rec, 0, None, tone=tone, base=1.5, alpha=0.97)


def make_thumb(cloud, maxh, maxw):
    mask, tone, emis = cloud["thumb"]
    H, W = mask.shape
    f = max(1, int(math.ceil(max(H / maxh, W / maxw))))
    h2, w2 = H // f, W // f
    mm = mask[:h2 * f, :w2 * f].reshape(h2, f, w2, f).mean((1, 3)) > 0.4
    tn = tone[:h2 * f, :w2 * f].reshape(h2, f, w2, f).max((1, 3))
    out = [(int(c), int(r), 2 if tn[r, c] > 0.5 else 1) for r, c in zip(*np.nonzero(mm))]
    return out, w2, h2


class _Lut(dict):
    def __missing__(self, key):
        v = self[key] = ((key >> 16) & 255, (key >> 8) & 255, key & 255)
        return v


_LUT = _Lut()

LIGHT = np.array([-0.45, -0.55, 0.70], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
_HALF = LIGHT + np.array([0, 0, 1], np.float32)
_HALF /= np.linalg.norm(_HALF)
ALB0 = np.array([135, 228, 250], np.float32)     # cyan material
ALB1 = np.array([255, 120, 205], np.float32)     # pink material
EM0 = np.array([190, 255, 255], np.float32)
EM1 = np.array([255, 120, 190], np.float32)
RIM = np.array([40, 215, 255], np.float32)
SWEEPC = np.array([170, 255, 255], np.float32)
OUTLINE = np.array([95, 235, 255], np.float32)
WHITEC = np.array([210, 255, 255], np.float32)
_RIMSPEC = np.stack([RIM, np.array([255, 255, 255], np.float32)]).astype(np.float32)


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        W, PH = w, h * 2
        self.PH = PH
        self.glitch = Glitch(0.012)
        self.particles = Particles()
        global S
        S = 2 if PH < 70 else 3
        self.clouds = [build_skull(), build_mask(), build_letters()]
        self.nvox = len(self.clouds[0]["P"])
        self.started = time.time()
        self.last = self.started
        self.cx = W / 2
        self.ppu = 0.58 * PH / 20
        self.ocy = 0.36 * PH
        self.hz = int(0.50 * PH)
        self.lens = int(0.72 * PH)
        self.rx = max(8.0, min(0.16 * W, 0.3 * PH))
        self.ry = self.rx * 0.28
        self.base = self.lens + max(4, int(0.065 * PH))
        self.ctop = max(6, int(self.ocy - 11 * self.ppu))
        self.rb = self.rx * 0.8
        self.rt = 0.30 * W
        self.panel_w = 28 if w >= 140 and h >= 34 else 0
        slot = 10 if h >= 40 else 8
        self.thumbs = [make_thumb(c, (slot - 3) * 2, self.panel_w - 6 if self.panel_w else 20) for c in self.clouds]
        self.zoom = 1.0
        self.bump = 0.0
        self.ring_t = 0.0
        self.beat_prev = 0.0
        self.shocks = []
        self.cur, self.nxt, self.last_k = 0, 1, 0
        self.was_morph = False
        self.flick_hist = [0.5] * 24
        self.flick_tick, self.flick_v = 0, 1.0
        self.prev_pack, self.flat = None, None
        self.qmask = 0xF8 if PH < 100 else 0xF0
        self.tick, self.H_cache = 0, None
        self.sats = [(random.choice(SHAPES), random.uniform(0, math.tau), random.uniform(0.4, 0.9)) for _ in range(3)]
        rnd = random.Random(5)
        step = 12 if w >= 140 else 9
        self.columns = []
        for x in range(4, W - 3, step):
            packets = [[rnd.uniform(0, 1), rnd.uniform(0.15, 0.45), rnd.randint(3, 7), rnd.random() < 0.15]
                       for _ in range(rnd.randint(2, 3))]
            self.columns.append((x, packets))
        pw = self.panel_w
        self.near_cols = []
        for x in ((pw + 5, W - pw - 7) if pw else (3, W - 5)):
            self.near_cols.append((x, [[rnd.uniform(0, 1), rnd.uniform(0.2, 0.5), rnd.randint(6, 12), rnd.random() < 0.25]
                                       for _ in range(3)]))
        self.build_room()
        self.build_fx()
        self.prep_packets()
        self.haze3 = (self.haze[..., None] * np.array((0, 55, 75), np.float32)).astype(np.float32)
        self.matrix = None
        # dust motes inside the cone
        r = np.random.RandomState(3)
        n = 70 if W >= 140 else 40
        self.dust = (r.uniform(-1, 1, n), r.uniform(0, 1, n), r.uniform(0.02, 0.07, n), r.uniform(0, 6.3, n))
        self.glow_k = np.exp(-(np.add.outer(np.arange(-6, 7) ** 2, np.arange(-6, 7) ** 2)) / 9.0).astype(np.float32)
        self.glow_c = np.exp(-(np.add.outer(np.arange(-6, 7) ** 2, np.arange(-6, 7) ** 2)) / 1.5).astype(np.float32)

    # ------------------------------------------------------------ static room
    def build_room(self):
        W, PH, hz, cx = self.w, self.PH, self.hz, self.cx
        yy, xx = np.mgrid[0:PH, 0:W].astype(np.float32)
        f = np.clip(yy / hz, 0, 1)[..., None]
        wall = np.array((3, 5, 11), np.float32) * (1 - f) + np.array((9, 15, 26), np.float32) * f
        seam = ((yy % 16 == 0) | (xx % 24 == 0))[..., None]
        light = (((xx % 24 == 1) | (yy % 16 == 1)) & ~seam[..., 0])[..., None]
        wall = np.where(seam, wall * 0.6, wall)
        wall = np.where(light, wall * 0.88 + np.array((40, 60, 80), np.float32) * 0.12, wall)
        fl = np.clip((yy - hz) / max(1, PH - hz), 0, 1)[..., None]
        floor = np.array((7, 12, 20), np.float32) * (1 - fl) + np.array((2, 3, 7), np.float32) * fl
        depth = (yy - hz + 1)
        gx = (xx - cx) / np.maximum(depth, 1)
        line = np.abs(gx - np.round(gx / 3) * 3) < 0.6 / np.maximum(depth, 1) + 0.06
        gcol = np.array((20, 50, 66), np.float32)
        floor = np.where(line[..., None], floor * (1 - 0.6 * (1 - fl * 0.5)) + gcol * 0.6 * (1 - fl * 0.5), floor)
        rowm = np.isin(depth, (1, 2, 4, 7, 11, 17, 25, 35, 48))[..., None]
        floor = np.where(rowm, floor * 0.55 + gcol * 0.45, floor)
        room = np.where((yy < hz)[..., None], wall, floor)
        for k, a in ((0, 0.35), (1, 0.18), (-1, 0.18)):
            if 0 <= hz + k < PH:
                room[hz + k] = room[hz + k] * (1 - a) + np.array((0, 90, 110), np.float32) * a
        tube = np.array((8, 22, 30), np.float32)
        self.top = 4
        for x, _ in self.columns:
            room[self.top:hz - 1, x] = tube
            room[hz, x] = (0, 70, 90)
            room[hz + 1, x] = (0, 40, 52)
            n = min(14, PH - hz - 2)
            for kk in range(n):
                room[hz + 2 + kk, x] = room[hz + 2 + kk, x] * (1 - 0.4 * (1 - kk / n)) + np.array((0, 60, 80), np.float32) * 0.4 * (1 - kk / n)
        for x, _ in self.near_cols:
            for dx, col in ((0, (34, 90, 110)), (1, (12, 36, 46)), (2, (6, 20, 28))):
                room[self.top - 2:hz, x + dx] = col
                n = min(18, PH - hz - 2)
                for kk in range(n):
                    a = 0.5 * (1 - kk / n)
                    room[hz + kk, x + dx] = room[hz + kk, x + dx] * (1 - a) + np.array(col, np.float32) * a
        vig = 1 - 0.42 * ((xx - cx) / (W / 2)) ** 2 - 0.18 * ((yy - PH / 2) / PH) ** 2
        self.room = (room * np.clip(vig, 0.3, 1)[..., None]).astype(np.float32)
        self.haze3 = None
        self.haze = np.exp(-(((xx - cx) / (0.30 * W)) ** 2 + ((yy - self.ocy) / (0.34 * PH)) ** 2)).astype(np.float32)

    def build_fx(self):
        W, PH, cx = self.w, self.PH, self.cx
        # light cone
        ct, lens = self.ctop, self.lens
        xa, xb = max(0, int(cx - self.rt) - 1), min(W, int(cx + self.rt) + 2)
        self.cone_box = (ct, lens + 1, xa, xb)
        yy, xx = np.mgrid[ct:lens + 1, xa:xb].astype(np.float32)
        f = (yy - ct) / max(1, lens - ct)
        hw = self.rt + (self.rb - self.rt) * f
        e = np.abs(xx - cx) / np.maximum(hw, 1)
        a = np.where(e < 1, (0.04 + 0.26 * e ** 5 + 0.08 * (1 - e) * f ** 2) * (0.15 + 0.85 * f ** 1.3), 0)
        self.cone_a = a.astype(np.float32)
        self.cone_x = (xx - cx).astype(np.float32)
        self.cone_y = yy
        # floor rings
        hz, base = self.hz, self.base
        self.rmax = 0.46 * W
        fr0 = hz + 1
        fa, fb = max(0, int(cx - self.rmax)), min(W, int(cx + self.rmax) + 1)
        self.floor_box = (fr0, PH, fa, fb)
        yy, xx = np.mgrid[fr0:PH, fa:fb].astype(np.float32)
        self.floor_r = np.sqrt((xx - cx) ** 2 + ((yy - base) / 0.3) ** 2).astype(np.float32)
        self.floor_fade = np.clip(1 - self.floor_r / self.rmax, 0, 1) ** 0.7
        # projector housing sprite
        rx, ry = self.rx, self.ry
        y0, y1 = int(lens - ry) - 2, min(PH, int(base + ry) + 3)
        x0, x1 = max(0, int(cx - rx) - 2), min(W, int(cx + rx) + 3)
        self.hbox = (y0, y1, x0, x1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        u = np.clip((xx - cx) / rx, -1, 1)
        top_e = ((xx - cx) / rx) ** 2 + ((yy - lens) / ry) ** 2
        bot_e = ((xx - cx) / rx) ** 2 + ((yy - base) / ry) ** 2
        body = (np.abs(xx - cx) < rx) & (yy >= lens) & (yy <= base)
        mask = (top_e < 1) | body | ((bot_e < 1) & (yy >= base))
        lit = 0.4 + 0.6 * np.clip(0.7 * np.sqrt(1 - u * u) - 0.5 * u, 0, 1)
        col = np.array((62, 78, 92), np.float32)[None, None, :] * lit[..., None]
        fin = ((np.arcsin(u) * 7 / math.pi) % 1 < 0.14)
        col = np.where(fin[..., None], col * 0.55, col)
        band = (np.abs(yy - (base - 1)) < 1)
        col = np.where(band[..., None], np.array((26, 48, 58), np.float32) * lit[..., None] * 1.4, col)
        plate = np.array((34, 44, 58), np.float32)
        col = np.where((top_e < 1)[..., None], plate[None, None, :] * (0.8 + 0.4 * lit[..., None]), col)
        rim = (top_e > 0.82) & (top_e < 1)
        col = np.where(rim[..., None], np.array((120, 145, 160), np.float32), col)
        inner = top_e < 0.5
        col = np.where(inner[..., None], np.array((6, 16, 22), np.float32), col)
        self.h_col, self.h_mask = col.astype(np.float32), mask
        self.lens_e = np.sqrt(((xx - cx) / (rx * 0.75)) ** 2 + ((yy - lens) / (ry * 0.75)) ** 2).astype(np.float32)
        # drop shadow ring under the housing, baked into the room
        yy2, xx2 = np.mgrid[base - 2:min(PH, int(base + ry * 2.4)), max(0, int(cx - rx * 1.5)):min(W, int(cx + rx * 1.5))].astype(np.float32)
        d = ((xx2 - cx) / (rx * 1.35)) ** 2 + ((yy2 - base) / (ry * 1.7)) ** 2
        k = np.clip(1 - d, 0, 1)[..., None] * 0.7
        ys, xs = slice(base - 2, base - 2 + yy2.shape[0]), slice(max(0, int(cx - rx * 1.5)), max(0, int(cx - rx * 1.5)) + yy2.shape[1])
        self.room[ys, xs] *= (1 - k)

    # ------------------------------------------------------------ helpers
    def project(self, x, y, z, D):
        k = D / max(1.0, D + z)
        return self.cx + x * self.ppu * k * self.zoom, self.ocy * 0.5 + y * self.ppu * k * self.zoom * 0.5, z

    def rotm(self, yaw, pitch, roll):
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
        Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], np.float32)
        return Rz @ Rx @ Ry

    # ------------------------------------------------------------ cloud selection (incl. slice print)
    def gather(self, cur, nxt, mt):
        A = self.clouds[cur]
        keys = ("P", "N", "alb", "ecl", "emk", "ao", "alp", "ema", "rk")
        if mt is None:
            return [A[k] for k in keys] + [None], A["anchors"], None, None
        B = self.clouds[nxt]
        ylo = min(A["ymin"], B["ymin"])
        yhi = max(A["ymax"], B["ymax"])
        bo, bn = 2.4, 1.3                          # dissolve zone (old) / print zone (new)
        bw = bo
        p = (yhi + bo) - ((yhi + bo) - (ylo - bn)) * _ease(mt)
        parts = {k: [] for k in keys + ("boost",)}

        def add(src, sel, P, boost, am):
            for k in keys:
                parts[k].append(P if k == "P" else src[k][sel])
            parts["alp"][-1] = src["alp"][sel] * am
            parts["boost"].append(boost)

        # old shape above the plane: its lower edge thins into a few fine motes that drift upward
        y = A["Y"]
        sel = y < p - bo
        add(A, sel, A["P"][sel], np.zeros(sel.sum(), np.float32), 1.0)
        bi = np.nonzero((y >= p - bo) & (y < p))[0]
        f = (y[bi] - (p - bo)) / bo
        keep = A["rnd"][bi] > f ** 0.9 * 0.8
        for t in range(3):
            ft = f - 0.12 * t
            kk = keep & (ft > 0.2) & (A["rnd"][bi] < (1.0 if t == 0 else 0.4)) if t else keep
            idx, ff = bi[kk], np.clip(ft[kk], 0, 1)
            if not len(idx):
                continue
            Pq = A["P"][idx]
            ang = ff * A["sw"][idx] * 0.6
            ca, sa = np.cos(ang), np.sin(ang)
            sp = 1 + 0.25 * ff * ff
            Pn = np.stack([(Pq[:, 0] * ca + Pq[:, 2] * sa) * sp, Pq[:, 1] - ff * ff * 5.0,
                           (-Pq[:, 0] * sa + Pq[:, 2] * ca) * sp], 1).astype(np.float32)
            add(A, idx, Pn, (0.2 + 0.6 * ff).astype(np.float32), (1 - ff ** 1.3 * 0.65) * (1.0 if t == 0 else 0.4 / t))
        # new shape below the plane: crisp, with a bright freshly printed edge
        y = B["Y"]
        sel = y >= p + bn
        add(B, sel, B["P"][sel], np.zeros(sel.sum(), np.float32), 1.0)
        bi = np.nonzero((y >= p) & (y < p + bn))[0]
        g = 1 - (y[bi] - p) / bn
        add(B, bi, B["P"][bi], (0.12 + 0.7 * g ** 1.3).astype(np.float32), 1.0)
        # the glowing print ring
        rad = float(max(np.interp(p, A["rows"], A["hw"]), np.interp(p, B["rows"], B["hw"]))) * 1.06 + 0.5
        th = np.linspace(0, math.tau, 260, endpoint=False)
        ring = np.stack([np.cos(th) * rad, np.full_like(th, p), np.sin(th) * rad * 0.3], 1).astype(np.float32)
        n = len(th)
        parts["P"].append(ring)
        parts["N"].append(np.zeros((n, 3), np.float32))
        parts["alb"].append(np.zeros((n, 3), np.float32))
        parts["ecl"].append(np.tile(EM0 * 1.25, (n, 1)).astype(np.float32))
        parts["emk"].append(np.full(n, 0.15, np.float32))
        parts["ao"].append(np.ones(n, np.float32))
        parts["alp"].append(np.full(n, 0.8, np.float32))
        parts["ema"].append(np.full(n, 1.0, np.float32))
        parts["rk"].append(np.ones(n, np.float32))
        parts["boost"].append(np.full(n, 0.85, np.float32))
        arrs = [np.concatenate(parts[k]) for k in keys + ("boost",)]
        anchors = [a for a in A["anchors"] if a[1] < p - bo] + [a for a in B["anchors"] if a[1] >= p + bn]
        return arrs, anchors, p, bw

    # ------------------------------------------------------------ hologram layer
    def render_holo(self, now, cur, nxt, mt, D, M, flick, glitch):
        W, PH = self.w, self.PH
        (P, Nn, alb, ecl, emk, ao, alp, ema, rk, boost), anchors, p, bw = self.gather(cur, nxt, mt)
        self.nvox = len(P)
        Pr = P @ M.T
        Nr = Nn @ M.T
        zc = Pr[:, 2]
        k = D / np.maximum(1.0, D - zc) * (self.ppu * self.zoom)
        ix = np.clip(self.cx + Pr[:, 0] * k, 0, W - 1).astype(np.int32)
        iy = np.clip(self.ocy + Pr[:, 1] * k, 0, PH - 1).astype(np.int32)
        x0, x1, y0, y1 = max(0, ix.min() - 1), min(W, ix.max() + 2), max(0, iy.min() - 1), min(PH, iy.max() + 2)
        ww, hh = x1 - x0, y1 - y0
        # --- shading (key light + glassy highlight + cyan fresnel rim)
        nx, ny, nz = Nr[:, 0], Nr[:, 1], Nr[:, 2]
        front = nz >= 0
        diff = np.maximum(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0)
        fres = (1 - np.abs(nz)) ** 2
        spec = np.maximum(nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2], 0) ** 18
        extra = np.stack([fres * (1.0 * rk), spec * (0.45 * ao)], 1) @ _RIMSPEC
        col = (alb * (0.22 + 0.80 * diff)[:, None] + extra) * emk[:, None] + ecl
        if boost is not None:
            col += (WHITEC - col) * boost[:, None]
        cue = (0.88 + 0.12 * np.clip(zc * 0.125, -1, 1)) * np.where(front, 1.0, 0.55)
        col = (255.0 * np.tanh(col * (cue * (1 / 215.0))[:, None])).astype(np.float32)
        al = alp * (0.55 + 0.45 * np.minimum(1.0, fres * 1.5 + 0.2 * diff + 0.15)) * flick
        al = np.minimum(np.maximum(al, ema), 1.0) * np.where(front, 1.0, 0.38)
        col *= al[:, None]
        order = np.argsort(zc)
        idx = ((iy - y0) * ww + (ix - x0))[order]
        pm, al, fo = col[order], al[order], front[order]
        layers = []
        for sel in (~fo, fo):
            Pb = np.zeros((hh * ww, 3), np.float32)
            Ab = np.zeros(hh * ww, np.float32)
            ii = idx[sel]
            Pb[ii] = pm[sel]
            Ab[ii] = al[sel]
            layers.append((Pb.reshape(hh, ww, 3), Ab.reshape(hh, ww)))
        # close pin-holes in the front layer
        Pf, Af = layers[1]
        m = Af > 0
        cnt = m[:-2, 1:-1] * 1.0 + m[2:, 1:-1] + m[1:-1, :-2] + m[1:-1, 2:]
        fill = (~m[1:-1, 1:-1]) & ((cnt >= 3) | (m[1:-1, :-2] & m[1:-1, 2:]) | (m[:-2, 1:-1] & m[2:, 1:-1]))
        if fill.any():
            c = np.maximum(cnt, 1)
            avgA = (Af[:-2, 1:-1] + Af[2:, 1:-1] + Af[1:-1, :-2] + Af[1:-1, 2:]) / c
            avgP = (Pf[:-2, 1:-1] + Pf[2:, 1:-1] + Pf[1:-1, :-2] + Pf[1:-1, 2:]) / c[..., None]
            Af[1:-1, 1:-1][fill] = avgA[fill]
            Pf[1:-1, 1:-1][fill] = avgP[fill]
        # clean bright outline on the outer edge of the projection
        m = Af > 0.05
        nb = m[:-2, 1:-1] * 1 + m[2:, 1:-1] + m[1:-1, :-2] + m[1:-1, 2:]
        edge = m[1:-1, 1:-1] & (nb >= 2) & (nb <= 3)
        if edge.any():
            ea = Af[1:-1, 1:-1]
            ea[edge] = np.minimum(1.0, ea[edge] + 0.3)
            Pf[1:-1, 1:-1][edge] += OUTLINE * 0.55
        # scanlines + sweeping beam (rows of the layer)
        rows = np.arange(y0, y1)
        lines = np.where(rows % 3 == 0, 0.9, 1.0).astype(np.float32)
        sweepy = y0 + ((now * 0.5) % 1.25 - 0.12) * hh
        sweep = np.exp(-((rows - sweepy) / 1.1) ** 2).astype(np.float32)
        band = np.nonzero(sweep > 0.03)[0]
        for Pl, Al in layers:
            Pl *= lines[:, None, None]
            Al *= lines[:, None]
            if len(band):
                sl = slice(band[0], band[-1] + 1)
                hit = (Al[sl] > 0)
                Pl[sl] += (SWEEPC * (0.22 * sweep[sl])[:, None, None]) * hit[..., None]
                Al[sl] += 0.06 * sweep[sl, None] * hit
        if glitch:
            for _ in range(2):
                r0 = random.randrange(0, max(1, hh - 3))
                dx = random.choice((-4, -3, 3, 4))
                for Pl, Al in layers:
                    Pl[r0:r0 + 3] = np.roll(Pl[r0:r0 + 3], dx, axis=1)
                    Al[r0:r0 + 3] = np.roll(Al[r0:r0 + 3], dx, axis=1)
        anchor_px = []
        for (ax, ay, az) in anchors:
            v = M @ np.array((ax, ay, az), np.float32)
            if v[2] > -0.5:
                kk = D / max(1.0, D - float(v[2])) * self.ppu * self.zoom
                anchor_px.append((int(self.cx + v[0] * kk), int(self.ocy + v[1] * kk), min(1.0, 0.5 + v[2] * 0.2 + 0.4)))
        return x0, y0, layers, anchor_px

    # ------------------------------------------------------------ pieces
    def prep_packets(self):
        """Flatten every data packet into index tables so one fancy-index pass draws them all."""
        rows = []
        for cols, w_ in ((self.columns, 1), (self.near_cols, 3)):
            for x, packets in cols:
                for pos, speed, ln, hot in packets:
                    for dx in range(w_):
                        rows.append((x + dx, pos, speed, ln, hot, 1.0 if dx == 0 or w_ == 1 else 0.6))
        n = len(rows)
        L = max(r[3] for r in rows)
        self.pk_x = np.array([r[0] for r in rows], np.int32)
        self.pk_pos = np.array([r[1] for r in rows], np.float32)
        self.pk_spd = np.array([r[2] for r in rows], np.float32) * 0.35
        kk = np.arange(L)[None, :]
        ln = np.array([r[3] for r in rows])[:, None]
        self.pk_k = np.broadcast_to(kk, (n, L))
        self.pk_valid = kk < ln
        self.pk_a = (np.clip(1 - kk / ln * 0.85, 0, 1) * 0.9 * np.array([r[5] for r in rows])[:, None]).astype(np.float32)
        hot = np.array([r[4] for r in rows])[:, None, None]
        self.pk_col = np.where(hot, np.array((255, 60, 160), np.float32), np.array((0, 229, 255), np.float32)).astype(np.float32)

    def draw_columns(self, out, now):
        hz, top = self.hz, self.top
        span = hz - top - 2
        head = hz - 2 - (((self.pk_pos + now * self.pk_spd) % 1.0) * span).astype(np.int32)
        py = head[:, None] + self.pk_k
        ok = self.pk_valid & (py >= top) & (py < hz - 1)
        xs = np.broadcast_to(self.pk_x[:, None], py.shape)[ok]
        pyy = py[ok]
        a = self.pk_a[ok][:, None]
        col = np.broadcast_to(self.pk_col, py.shape + (3,))[ok]
        out[pyy, xs] = out[pyy, xs] * (1 - a) + col * a

    def draw_floor(self, out, now):
        r0, r1, a0, a1 = self.floor_box
        r = self.floor_r
        rm = self.rmax
        acc = np.zeros_like(r)
        for i, R in enumerate((0.26, 0.42, 0.62, 0.86)):
            Rr = R * rm
            wave = max(0.0, math.cos((Rr - now * 9) / 3.2)) ** 3
            lvl = 0.16 + 0.5 * wave + 0.45 * self.bump
            acc += np.exp(-((r - Rr) / 1.3) ** 2) * lvl
        pink = np.zeros_like(r)
        for tb, amp in self.shocks:
            age = now - tb
            rad = age * 62.0
            pink += np.exp(-((r - rad) / (1.6 + age * 3)) ** 2) * amp * math.exp(-age * 1.1)
        acc *= self.floor_fade
        pink *= np.clip(1 - r / (rm * 1.25), 0, 1)
        sub = out[r0:r1, a0:a1]
        sub += np.array((0, 200, 255), np.float32) * acc[..., None] * 0.95
        sub += np.array((255, 60, 150), np.float32) * pink[..., None] * 0.85
        # glow pool under the emitter
        pool = np.exp(-(r / (0.22 * rm)) ** 2) * (0.22 + 0.3 * self.bump)
        sub += np.array((0, 120, 160), np.float32) * pool[..., None]

    def draw_cone(self, out, now, boost):
        y0, y1, x0, x1 = self.cone_box
        a = self.cone_a
        streak = 0.72 + 0.28 * np.sin(self.cone_x * 0.85 + now * 2.6 + self.cone_y * 0.07)
        a = a * streak * boost * 2.4
        sub = out[y0:y1, x0:x1]
        cone = np.array((60, 225, 255), np.float32)
        sub += (cone - sub) * a[..., None]

    def draw_dust(self, out, now):
        u, v0, sp, ph = self.dust
        v = (v0 + now * sp) % 1.0
        py = (self.lens - v * (self.lens - self.ctop)).astype(np.int32)
        hw = self.rb + (self.rt - self.rb) * v
        px = (self.cx + u * hw * 0.88 + np.sin(now * 0.6 + ph) * 2.0).astype(np.int32)
        b = (0.3 + 0.5 * np.abs(np.sin(now * 2.0 + ph * 5))) * (1 - v * 0.5)
        ok = (px >= 0) & (px < self.w - 1) & (py >= 0) & (py < self.PH)
        px, py, b = px[ok], py[ok], b[ok]
        col = np.array((170, 245, 255), np.float32)
        out[py, px] += col * b[:, None]
        big = ph[ok] > 4.2
        out[py[big], px[big] + 1] += col * (b[big, None] * 0.6)

    def draw_lens(self, out, now):
        y0, y1, x0, x1 = self.hbox
        sub = out[y0:y1, x0:x1]
        m = self.h_mask[..., None]
        sub[...] = np.where(m, self.h_col, sub)
        e = self.lens_e
        glow = np.clip(1 - e * 1.1, 0, 1) * (0.6 + 0.4 * pulse(now, 2) + 0.9 * self.bump)
        ring = np.exp(-((e - 0.86) / 0.07) ** 2) * (0.7 + 0.5 * self.bump)
        sub += np.array((0, 230, 255), np.float32) * (glow + ring)[..., None] * (self.h_mask & (e < 1.2))[..., None]

    def orbit(self, out, now, D, front, radius, tilt, spin, color, dots):
        """Dotted ring plus bright heads with trails; `front` picks the half nearer the viewer."""
        n = 150
        th = np.concatenate([np.linspace(0, math.tau, n, endpoint=False),
                             (self.ring_t * 1.2 + np.arange(dots)[:, None] * math.tau / dots
                              - np.arange(9)[None, :] * 0.06).ravel()])
        ct, st = math.cos(tilt), math.sin(tilt)
        cs, ss = math.cos(spin), math.sin(spin)
        px0, pz0 = np.cos(th) * radius, np.sin(th) * radius
        x = px0 * cs + pz0 * ss
        z = -px0 * ss + pz0 * cs
        y = -z * st
        zc = -z * ct                              # toward the viewer
        k = D / np.maximum(1.0, D - zc) * self.ppu * self.zoom
        px, py = self.cx + x * k, self.ocy + y * k
        ok = ((zc >= 0) == front) & (px >= 0) & (px < self.w) & (py >= 0) & (py < self.PH)
        w = np.zeros(len(th), np.float32)
        w[:n] = (0.32 if front else 0.2) + 0.2 * self.bump
        w[n:] = np.tile(1 - np.arange(9) / 9, dots) * (1.0 + self.bump * 0.4)
        col = np.empty((len(th), 3), np.float32)
        col[:n] = np.array(color, np.float32) * 0.8
        col[n:] = np.array(color, np.float32) * 0.6 + 140
        ix, iy = px[ok].astype(int), py[ok].astype(int)
        out[iy, ix] += col[ok] * w[ok, None]

    def draw_reflection(self, out, H, now):
        if H is None:
            return
        x0, y0, layers, _ = H
        (Pb, Ab), (Pf, Af) = layers
        hh, ww = Af.shape
        ry0 = int(self.base + self.ry) + 2
        RR = self.PH - 2 - ry0
        if RR < 3:
            return
        src = hh - 1 - (np.arange(RR) * hh // RR)
        Am = 1 - (1 - Ab[src]) * (1 - Af[src])
        Pm = Pb[src] * (1 - Af[src])[..., None] + Pf[src]
        shift = (1.6 * np.sin(np.arange(RR) * 1.1 + now * 3)).astype(int)
        cols = np.clip(np.arange(ww)[None, :] - shift[:, None], 0, ww - 1)
        Pm = np.take_along_axis(Pm, cols[..., None], axis=1)
        Am = np.take_along_axis(Am, cols, axis=1)
        fade = (1 - np.arange(RR) / RR) ** 1.4 * 0.5
        fade = fade * np.where(np.arange(RR) % 2 == 0, 1.0, 0.65)
        sub = out[ry0:ry0 + RR, x0:x0 + ww]
        sub *= (1 - np.minimum(Am, 1) * fade[:, None])[..., None]
        sub += Pm * fade[:, None, None] * np.array((0.7, 1.0, 1.0), np.float32)

    # ------------------------------------------------------------ main loop
    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        beat = DATA.beat
        if beat > 0.85 and self.beat_prev <= 0.85:
            self.shocks.append((now, 1.0))
        self.beat_prev = beat
        self.shocks = [(t, a) for t, a in self.shocks if now - t < 2.2][-4:]
        self.bump = max(beat, self.bump - dt * 3.5)
        self.ring_t += dt * (1 + 1.2 * DATA.level + 1.5 * self.bump)

        dz = pulse(now, 0.35)
        D = 90 + dz * 110
        self.zoom = 0.95 + 0.1 * (1 - dz)

        age = max(0.0, now - self.started)
        k = int(age // CYCLE)
        loc = age - k * CYCLE
        cur, nxt = k % 3, (k + 1) % 3
        self.cur, self.nxt = cur, nxt
        mt = None if loc < MORPH_AT else min(0.999, (loc - MORPH_AT) / MORPH)
        if mt is not None and not self.was_morph:
            self.was_morph = True
            self.glitch.trigger(now, 0.2)
        elif mt is None and self.was_morph:
            self.was_morph = False
            self.particles.burst(self.cx, self.ocy / 2, 30, (CYAN, PINK, WHITE), speed=14)
        u = _ease((loc - 3.0) / 4.0) if 3.0 <= loc < 7.0 else 0.0
        yaw = 1.0 * math.sin(math.tau * u) + 0.16 * math.sin(age * 0.5)
        pitch = 0.1 * math.sin(now * 0.5)
        roll = 0.04 * math.sin(now * 0.23)
        M = self.rotm(yaw, pitch, roll)

        if int(now * 4) != self.flick_tick:
            self.flick_tick = int(now * 4)
            self.flick_v = 0.95 + 0.05 * random.random()
            if random.random() < 0.04:
                self.flick_v *= 0.7
        flick = min(1.1, self.flick_v + 0.15 * self.bump)
        self.flick_hist = self.flick_hist[1:] + [flick]

        out = self.room.copy()
        out += self.haze3 * (0.5 + 0.25 * pulse(now, 0.6) + 0.5 * self.bump)
        self.draw_columns(out, now)
        # the projection refreshes at half rate (a hologram shimmer, and half the cost)
        self.tick += 1
        if self.tick & 1 or self.H_cache is None:
            self.H_cache = self.render_holo(now, cur, nxt, mt, D, M, min(flick, 1.0), glitch)
        H = self.H_cache
        self.draw_floor(out, now)
        self.draw_reflection(out, H, now)
        self.draw_lens(out, now)
        self.draw_cone(out, now, flick * (1 + 0.6 * self.bump))
        self.draw_dust(out, now)
        self.orbit(out, now, D, False, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, 3)
        self.orbit(out, now, D, False, 16, 0.4, -now * 0.2, PURPLE, 2)
        if H is not None:
            x0, y0, layers, anchors = H
            (Pb, Ab), (Pf, Af) = layers
            hh, ww = Af.shape
            sub = out[y0:y0 + hh, x0:x0 + ww]
            sub *= (1 - np.minimum(Ab, 1))[..., None]
            sub += Pb
            sub *= (1 - np.minimum(Af, 1))[..., None]
            sub += Pf
            gk, gc = self.glow_k, self.glow_c
            for ex, ey, vis in anchors:
                ya, yb, xa, xb = ey - 6, ey + 7, ex - 6, ex + 7
                ca, cb, da, db = max(0, ya), min(self.PH, yb), max(0, xa), min(self.w, xb)
                if ca >= cb or da >= db:
                    continue
                kk = gk[ca - ya:cb - ya, da - xa:db - xa] * (0.6 + 0.25 * pulse(now, 1.7)) * vis
                cc = gc[ca - ya:cb - ya, da - xa:db - xa] * vis
                out[ca:cb, da:db] += np.array((255, 70, 160), np.float32) * kk[..., None] + 130 * cc[..., None]
        self.orbit(out, now, D, True, 13, 1.2 + math.sin(now * 0.3) * 0.2, now * 0.3, PINK, 3)
        self.orbit(out, now, D, True, 16, 0.4, -now * 0.2, PURPLE, 2)

        q = np.clip(out, 0, 255).astype(np.int32) & self.qmask
        packed = ((q[..., 0] << 16) | (q[..., 1] << 8) | q[..., 2]).ravel()
        if self.prev_pack is None:
            self.flat = [_LUT[v] for v in packed.tolist()]
        else:
            ch = np.flatnonzero(packed != self.prev_pack)
            flat, lut = self.flat, _LUT
            for i, v in zip(ch.tolist(), packed[ch].tolist()):
                flat[i] = lut[v]
        self.prev_pack = packed
        flat = self.flat
        W = self.w
        for y in range(self.h):
            s.pt[y] = flat[2 * y * W:(2 * y + 1) * W]
            s.pb[y] = flat[(2 * y + 1) * W:(2 * y + 2) * W]

        # wireframe satellites, kept inside the space between the panels
        orbit = 19 if self.panel_w else 17
        for i, ((verts, edges), ph, sp_) in enumerate(self.sats):
            a = now * sp_ + ph
            c = rot((math.cos(a) * orbit, math.sin(a * 1.3) * 4, math.sin(a) * orbit), 0.25, 0)
            x, y, z = self.project(*c, D)
            size = 1.6 * self.zoom * (1.2 if z < 0 else 0.8)
            for va, vb in edges:
                pa = rot(verts[va], now * 1.3, now * 0.9 + i)
                pb = rot(verts[vb], now * 1.3, now * 0.9 + i)
                s.line(int(x + pa[0] * size * 2), int(y + pa[1] * size), int(x + pb[0] * size * 2), int(y + pb[1] * size),
                       "·", YELLOW if z < 0 else blend(YELLOW, BLACK, 0.6))
        self.particles.step(s, dt)

        if self.panel_w:
            self.draw_library(s, now, mt)
            self.draw_telemetry(s, now, D, yaw, flick)
        s.text(2, 0, "HOLO-PROJECTOR // " + SHAPE_NAMES[cur], CYAN)
        s.text(2, 1, "VOXELS %d   YAW %03d°   FOCAL %3dmm" % (self.nvox, math.degrees(yaw) % 360, D), GREY)
        if mt is not None:
            bar = int(mt * 16)
            msg = "MORPH > %s  %s%s %3d%%" % (SHAPE_NAMES[nxt], "▓" * bar, "░" * (16 - bar), mt * 100)
            s.center(2, msg, PINK if int(now * 8) % 2 else YELLOW)
        st = "● TRANSMITTING" if int(now * 2) % 2 else "○ TRANSMITTING"
        s.text(self.w - len(st) - 2, 0, st, PINK)
        s.center(self.h - 2, "> WE ARE DEDSEC. WE SEE EVERYTHING. <", blend(PINK, WHITE, pulse(now, 3) * 0.5))
        self.backfill(s)

    # ------------------------------------------------------------ side panels
    def panel_box(self, s, x, y, w, h, title, col):
        for yy in range(max(0, y), min(s.h, y + h)):
            for xx in range(max(0, x), min(s.w, x + w)):
                s.ch[yy][xx] = " "
                s.pt[yy][xx] = s.pb[yy][xx] = None
                s.bg[yy][xx] = (3, 10, 15)
        s.text(x, y, "┌" + "─" * (w - 2) + "┐", col)
        for i in range(1, h - 1):
            s.put(x, y + i, "│", col)
            s.put(x + w - 1, y + i, "│", col)
        s.text(x, y + h - 1, "└" + "─" * (w - 2) + "┘", col)
        s.text(x + 2, y, " " + title + " ", blend(col, WHITE, 0.4))

    def draw_library(self, s, now, mt):
        pw = self.panel_w
        x0, y0 = 1, 3
        slot = 10 if self.h >= 40 else 8
        hgt = 3 * slot + 2
        self.panel_box(s, x0, y0, pw, hgt, "OBJECT LIBRARY", DIM_CYAN)
        for i, (cells, tw, th) in enumerate(self.thumbs):
            y = y0 + 1 + i * slot
            active = i == self.cur
            target = mt is not None and i == self.nxt
            if active:
                col, tag = CYAN, "LIVE"
            elif target:
                col, tag = PINK if int(now * 6) % 2 else blend(PINK, WHITE, 0.4), "LOAD"
            else:
                col, tag = (40, 70, 90), "IDLE"
            s.text(x0 + 2, y, SHAPE_NAMES[i], col)
            s.text(x0 + pw - 2 - len(tag), y, tag, col)
            s.text(x0 + 2, y + 1, SHAPE_INFO[i][:pw - 4], GREY if active or target else (40, 50, 62))
            # pixel silhouette, scanlined like the projection
            tx = x0 + (pw - tw) // 2
            ty = (y + 2) * 2 + 1
            maxr = (slot - 3) * 2
            ry = 1 if th <= maxr else th / maxr
            scan = int(now * 10)
            for c, r, k in cells:
                py = ty + int(r / ry)
                base = col if k == 1 else (blend(col, WHITE, 0.5) if active else blend(col, PINK, 0.6))
                if (py + scan) % 3 == 0:
                    base = blend(base, BLACK, 0.55)
                if target and mt is not None and r / th > mt:
                    base = blend(base, BLACK, 0.7)
                s.pixel(tx + c, py, base)
            if target and mt is not None:
                bar = int(mt * (pw - 4))
                s.text(x0 + 2, y + slot - 1, "▰" * bar + "▱" * (pw - 4 - bar), PINK)

    def draw_telemetry(self, s, now, D, yaw, flick):
        pw = self.panel_w
        x0, y0 = self.w - pw - 1, 3
        rows = 16 if self.h >= 40 else 12
        self.panel_box(s, x0, y0, pw, rows + 2, "EMITTER", DIM_CYAN)
        x = x0 + 2
        inner = pw - 4

        def bar(y, label, v, col):
            n = inner - 9
            k = int(max(0.0, min(1.0, v)) * n)
            s.text(x, y, label.ljust(8), GREY)
            s.text(x + 8, y, "█" * k + "░" * (n - k), col)

        y = y0 + 1
        live = "● LIVE" if int(now * 2) % 2 else "○ LIVE"
        s.text(x, y, "STATUS", GREY)
        s.text(x + inner - len(live), y, live, PINK)
        y += 1
        temp = 41 + DATA.cpu * 24 + self.bump * 3 + math.sin(now * 0.3)
        s.text(x, y, "LENS", GREY)
        s.text(x + inner - 6, y, "%4.1f°C" % temp, YELLOW if temp > 55 else CYAN)
        y += 1
        s.text(x, y, "FOCAL", GREY)
        s.text(x + inner - 5, y, "%3dmm" % D, CYAN)
        y += 1
        s.text(x, y, "YAW", GREY)
        s.text(x + inner - 4, y, "%03d°" % (math.degrees(yaw) % 360), CYAN)
        y += 1
        bar(y, "POWER", 0.55 + 0.35 * DATA.level + 0.1 * self.bump, CYAN)
        y += 1
        bar(y, "CPU", DATA.cpu, (0, 160, 190))
        y += 1
        bar(y, "MEM", DATA.mem, (0, 160, 190))
        y += 2
        s.text(x, y, "BEAM STABILITY", GREY)
        y += 1
        # sparkline of the projector flicker (pixel bars, 2 rows high)
        hist = self.flick_hist[-inner:]
        base_py = (y + 2) * 2
        for i, v in enumerate(hist):
            hgt = 1 + int(max(0.0, min(1.0, (v - 0.75) / 0.5)) * 3)
            for k in range(hgt):
                s.pixel(x + i, base_py - 1 - k, blend(DIM_CYAN, CYAN, k / 3))
        y += 2
        if y + 3 < y0 + rows + 1:
            y += 1
            s.text(x, y, "AUDIO SYNC", GREY)
            y += 1
            base_py = (y + 2) * 2
            nb = min(16, inner // 2)
            for i in range(nb):
                v = DATA.band(i, nb)
                hgt = 1 + int(v * 3)
                for k in range(hgt):
                    s.pixel(x + i * 2, base_py - 1 - k, blend(PURPLE, PINK, k / 3))

    @staticmethod
    def backfill(s):
        """Text cells take the colour of the pixels beneath, so glyphs don't punch black holes."""
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

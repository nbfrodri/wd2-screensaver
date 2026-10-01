"""Cinematic transitions between modes. Each takes the old frame snapshot, the
freshly drawn new frame (already on `s`) and progress t in 0..1, and edits `s`."""

import random

from lib import BLACK, CYAN, PINK, WHITE, YELLOW, blend

LAYERS = 5  # ch, fg, bg, pt, pb


def _remap(s, snap, fn):
    """Fill s from snapshot `snap`: fn(x, y) -> (sx, sy) or None for blank."""
    sch, sfg, sbg, spt, spb = snap
    for y in range(s.h):
        rc, rf, rb, rt, rp = s.ch[y], s.fg[y], s.bg[y], s.pt[y], s.pb[y]
        for x in range(s.w):
            src = fn(x, y)
            if src is None:
                rc[x], rf[x], rb[x], rt[x], rp[x] = " ", None, None, None, None
            else:
                sx, sy = src
                rc[x], rf[x], rb[x], rt[x], rp[x] = sch[sy][sx], sfg[sy][sx], sbg[sy][sx], spt[sy][sx], spb[sy][sx]


def glitch(s, old, t, label):
    s.noise_lines(int(s.h * (1 - t) * 1.5) + 1)
    for _ in range(int(6 * (1 - t)) + 1):
        s.shift_row(random.randrange(s.h), random.randint(-20, 20))
    s.center(s.h // 2, label, random.choice((PINK, CYAN, YELLOW, WHITE)))


def crt(s, old, t, label):
    """Old TV switching off (first half) and the new feed switching on."""
    cy = s.h / 2
    if t < 0.5:
        k = max(0.02, 1 - t * 2)
        snap = old
    else:
        k = max(0.02, (t - 0.5) * 2)
        snap = s.snapshot()

    def fn(x, y):
        sy = int(cy + (y - cy) / k)
        return (x, sy) if 0 <= sy < s.h else None

    _remap(s, snap, fn)
    if k < 0.15:
        w = int(s.w * (0.3 + k * 4))
        x0 = (s.w - w) // 2
        y = int(cy)
        s.text(x0, y, "━" * w, WHITE)
        s.tint_row(y, WHITE, 0.6)
    if t < 0.5 and k < 0.06:
        s.fill(0, 0, s.w, s.h)
        s.put(s.w // 2, int(cy), "●", WHITE)


def vhs(s, old, t, label):
    """Tracking error: rows slide, a noise band rolls through, colours split."""
    strength = 1 - t
    band = int((t * 3 % 1) * s.h)
    for y in range(s.h):
        if random.random() < 0.5 * strength:
            s.shift_row(y, random.randint(-int(30 * strength) - 1, int(30 * strength) + 1))
        if abs(y - band) < 3:
            s.tint_row(y, WHITE, 0.5)
            for x in range(0, s.w, random.randint(2, 6)):
                s.put(x, y, random.choice("▒░▓"), blend(WHITE, BLACK, random.random()))
    s.text(2, 1, "▶ PLAY", WHITE)
    s.text(s.w - 14, 1, "TRACKING %02d" % int(strength * 99), WHITE)
    if t < 0.6:
        s.center(s.h // 2, label, YELLOW)


def datamosh(s, old, t, label):
    """Old frame melts down into the new one, block by block."""
    sch, sfg, sbg, spt, spb = old
    drop = int(t * t * 12)
    keep = 1 - t
    for y in range(s.h):
        sy = y - drop
        if not 0 <= sy < s.h:
            continue
        for x in range(0, s.w):
            if random.random() < keep and ((x // 4 + y // 2) % 3 or t < 0.3):
                s.ch[y][x], s.fg[y][x], s.bg[y][x] = sch[sy][x], sfg[sy][x], sbg[sy][x]
                s.pt[y][x], s.pb[y][x] = spt[sy][x], spb[sy][x]
    if t > 0.3:
        for _ in range(3):
            s.shift_row(random.randrange(s.h), random.randint(-8, 8))


def zoom(s, old, t, label):
    """Crash zoom into the old frame, then out of the new one."""
    cx, cy = s.w / 2, s.h / 2
    if t < 0.5:
        z = 1 + (t * 2) ** 2 * 6
        snap = old
    else:
        z = 1 + (1 - (t - 0.5) * 2) ** 2 * 6
        snap = s.snapshot()

    def fn(x, y):
        sx, sy = int(cx + (x - cx) / z), int(cy + (y - cy) / z)
        return (sx, sy) if 0 <= sx < s.w and 0 <= sy < s.h else None

    _remap(s, snap, fn)
    # speed lines
    for _ in range(int(40 * (z - 1) / 6)):
        y = random.randrange(s.h)
        x = random.randrange(s.w)
        s.put(x, y, "─" if abs(y - cy) < abs(x - cx) / 2 else "│", blend(WHITE, BLACK, 0.3))


ALL = {"glitch": glitch, "crt": crt, "vhs": vhs, "datamosh": datamosh, "zoom": zoom}

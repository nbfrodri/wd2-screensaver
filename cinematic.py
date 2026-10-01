"""Short scene-based exits shared by the modes; no desktop or data access."""

import math
from functools import lru_cache

from lib import BLACK, CYAN, WHITE, blend


@lru_cache(maxsize=8192)
def _fade(color, level):
    return tuple(v * level // 24 for v in color)


def exit_scene(mode, s, now, t, style="blackout", label="FEED CLOSED", color=CYAN):
    """Animate the runner's mode._exit_snapshot. Modes may add their own props.

    Styles: blackout (lights off), pullback (camera retreats), scan (erase feed
    bottom-up), scatter (tiles depart), shutter (camera iris), spray (paint sweep).
    Progress is 0..1 over 0.8 seconds; this never calls mode.step or reads data.
    """
    t = max(0.0, min(1.0, t))
    old = getattr(mode, "_exit_snapshot", None)
    if old is None:
        mode.step(s, now)
        old = mode._exit_snapshot = s.snapshot()
    if t >= 1:
        return
    w, h = s.w, s.h
    cx, cy = (w - 1) / 2, (h - 1) / 2
    e = t * t * (3 - 2 * t)
    level = max(0, int(24 * (1 - max(0, t - 0.25) / 0.75)))
    layers = (s.ch, s.fg, s.bg, s.pt, s.pb)
    for y in range(h):
        for x in range(w):
            sx, sy = x, y
            visible = True
            if style == "pullback":
                scale = max(0.08, 1 - e * 0.92)
                sx, sy = round(cx + (x - cx) / scale), round(cy + (y - cy) / scale)
            elif style == "scan":
                visible = y < h * (1 - e)
                sx += round(math.sin(y * 1.7 + t * 30) * t * 3)
            elif style == "shutter":
                radius = max(0.01, 1 - e)
                dx, dy = (x - cx) / max(1, w * 0.53), (y - cy) / max(1, h * 0.53)
                # Six blades close as a real camera aperture rather than a wipe.
                a = math.atan2(dy, dx)
                visible = math.hypot(dx, dy) < radius * (0.86 + 0.14 * math.cos(6 * a))
            elif style == "spray":
                edge = w * e + math.sin(y * 1.7) * 3
                visible = x > edge
            elif style == "scatter":
                bx, by = x // 6, y // 3
                delay = ((bx * 17 + by * 29) % 19) / 55
                q = max(0, (t - delay) / max(0.1, 1 - delay))
                sx = x - round((bx * 6 - cx) * q * 1.6)
                sy = y - round((by * 3 - cy) * q * 1.3 + q * q * h * 0.35)
                visible = q < 0.95
            elif style == "blackout":
                delay = ((x // 8 * 7 + y // 4 * 13) % 17) / 22
                visible = t < delay + 0.23
            if not visible or not (0 <= sx < w and 0 <= sy < h):
                continue
            layers[0][y][x] = old[0][sy][sx]
            for n in range(1, 5):
                c = old[n][sy][sx]
                if c is not None:
                    layers[n][y][x] = _fade(c, level)
    if style == "scan":
        row = int(h * (1 - e))
        if 0 <= row < h:
            s.text(0, row, "━" * w, blend(color, WHITE, 0.35))
    elif style == "spray":
        for y in range(h):
            x = int(w * e + math.sin(y * 1.7) * 3)
            s.put(x, y, "▓", blend(color, BLACK, t * 0.6))
            if (y * 7) % 5 == 0:
                s.put(x + 2, y, "·", color)
    # A brief scene-specific sign-off, kept away from the central artwork.
    if 0.1 < t < 0.85 and label:
        text = label[:max(0, w - 6)]
        x, y = (w - len(text)) // 2, max(0, h - 3)
        s.fill(x - 1, y, len(text) + 2, 1)
        s.text(x, y, text, _fade(color, max(0, int(24 * (1 - t)))))

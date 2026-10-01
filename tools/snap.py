#!/usr/bin/env python3
"""Headless test for a mode: python3 tools/snap.py mode_x [W H FRAMES] [--show] [--colors]

Runs FRAMES frames at 24 fps of simulated time, reports ms/frame (mode + render),
and with --show prints the final frame as plain text (pixels shown as ▀/▄)."""
import importlib, os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import lib

args = [a for a in sys.argv[1:] if not a.startswith("--")]
name = args[0]
W, H, N = (int(args[1]), int(args[2]), int(args[3])) if len(args) >= 4 else (175, 45, 240)
m = importlib.import_module(name)
s = lib.Screen(W, H)
md = m.Mode(W, H)
t = time.time()
real = time.time
for i in range(N):
    now = t + i / 24
    time.time = lambda now=now: now
    s.clear(); md.step(s, now); s.render()
time.time = real
t0 = real()
for i in range(48):
    now = t + (N + i) / 24
    s.clear(); md.step(s, now); out = s.render()
print("%s %dx%d: %.1f ms/frame" % (name, W, H, (real() - t0) / 48 * 1000), file=sys.stderr)
if "--show" in sys.argv:
    s.invalidate(); full = s.render(crt=False)
    rows = []
    for y in range(H):
        row = ""
        for x in range(W):
            c = s.ch[y][x]
            if c == " ":
                c = "▀" if s.pt[y][x] else ("▄" if s.pb[y][x] else (":" if s.bg[y][x] and sum(s.bg[y][x]) > 60 else " "))
            row += c
        rows.append(row)
    print("\n".join(rows))
if "--colors" in sys.argv:
    print("bytes per full frame:", len(full) if "--show" in sys.argv else "n/a", file=sys.stderr)

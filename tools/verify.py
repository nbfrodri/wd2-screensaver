#!/usr/bin/python3
"""Headless smoke checks; --full also checks 80 simulated seconds per mode."""
import argparse
import importlib
from pathlib import Path
import sys
import time
import unicodedata
import random

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib import Screen


def check_cells(screen):
    for row in screen.ch:
        for char in row:
            assert len(char) == 1
            assert unicodedata.east_asian_width(char) not in ("W", "F"), repr(char)
            assert unicodedata.category(char)[0] not in ("C", "M"), repr(char)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--mode", help="Module name, for example mode_dotmatrix")
    parser.add_argument("--seed", type=int, default=24, help="repeatable procedural scene seed")
    args = parser.parse_args()
    paths = sorted(ROOT.glob("mode_*.py"))
    if args.mode:
        paths = [p for p in paths if p.stem == args.mode]
        if not paths:
            parser.error("Unknown mode module")
    real_time = time.time
    for path in paths:
        module = importlib.import_module(path.stem)
        for width, height in ((90, 26), (175, 45), (240, 60)):
            random.seed(args.seed)
            base = real_time()
            now = base
            time.time = lambda: now
            try:
                mode = module.Mode(width, height)
                screen = Screen(width, height)
                frames, dt = (101, .8) if args.full else (24, 1 / 24)
                for index in range(frames):
                    now = base + index * dt
                    screen.clear()
                    mode.step(screen, now)
                    screen.render()
                    check_cells(screen)
                mode._exit_snapshot = screen.snapshot()
                for progress in (0, .1, .2, .35, .5, .65, .8, .95, 1):
                    screen.clear()
                    mode.farewell(screen, now + progress * .8, progress)
                    screen.render()
                    check_cells(screen)
            finally:
                time.time = real_time
            print(f"{path.stem} {width}x{height}: OK", flush=True)
    print("All checks passed. No live data sources or desktop actions started.")


if __name__ == "__main__":
    main()

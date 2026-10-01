#!/usr/bin/python3
"""PNG contact sheet of simulated terminal frames (optional Pillow required)."""
import argparse
import importlib
import math
from pathlib import Path
import random
import sys
import time

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib import Screen, WHITE


def raster(screen, font):
    # This is a review approximation, not a screenshot of the real terminal.
    cw, ch = 10, 16
    result = Image.new("RGB", (screen.w * cw, screen.h * ch))
    draw = ImageDraw.Draw(result)
    for y in range(screen.h):
        for x in range(screen.w):
            left, top = x * cw, y * ch
            char = screen.ch[y][x]
            draw.rectangle((left, top, left + cw - 1, top + ch - 1),
                           fill=screen.bg[y][x] or (0, 0, 0))
            color = screen.fg[y][x] or WHITE
            if 0x2800 <= ord(char) <= 0x28ff:
                bits = ord(char) - 0x2800
                for dy, row in enumerate(((1, 8), (2, 16), (4, 32), (64, 128))):
                    for dx, bit in enumerate(row):
                        if bits & bit:
                            draw.ellipse((left + dx * 5 + 1, top + dy * 4 + 1,
                                          left + dx * 5 + 3, top + dy * 4 + 3), fill=color)
            elif char != " ":
                draw.text((left, top - 2), char, font=font, fill=color)
            else:
                for dy, pixel in ((0, screen.pt[y][x]), (8, screen.pb[y][x])):
                    if pixel is not None:
                        draw.rectangle((left, top + dy, left + cw - 1, top + dy + 7), fill=pixel)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="mode_dotmatrix", help="module name or all")
    parser.add_argument("--times", type=float, nargs="+", default=[0, 2.6, 6, 12, 26, 31])
    parser.add_argument("--width", type=int, default=90)
    parser.add_argument("--height", type=int, default=26)
    parser.add_argument("--output", type=Path, default=Path("/tmp/wd2-preview.png"))
    parser.add_argument("--font", default="/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf")
    args = parser.parse_args()
    if min(args.times) < 0 or args.width < 10 or args.height < 5:
        parser.error("nonnegative times and a usable screen size are required")
    paths = sorted(ROOT.glob("mode_*.py"))
    if args.mode != "all":
        paths = [p for p in paths if p.stem == args.mode]
        if not paths:
            parser.error("unknown mode module")
    font = ImageFont.truetype(args.font, 16)
    panels = []
    real_time = time.time
    for path in paths:
        random.seed(24)
        module = importlib.import_module(path.stem)
        base, now = 1700000000., 1700000000.
        time.time = lambda: now
        try:
            mode = module.Mode(args.width, args.height)
            screen = Screen(args.width, args.height)
            previous = 0
            for target in sorted(args.times):
                for frame in range(previous, math.ceil(target * 24) + 1):
                    now = base + frame / 24
                    screen.clear()
                    mode.step(screen, now)
                previous = math.ceil(target * 24) + 1
                panels.append((f"{module.NAME} / {target:g}s", raster(screen, font)))
        finally:
            time.time = real_time
    columns = min(3, len(panels))
    pw, ph = args.width * 10, args.height * 16 + 28
    sheet = Image.new("RGB", (pw * columns, ph * math.ceil(len(panels) / columns)), (12, 12, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, panel) in enumerate(panels):
        x, y = index % columns * pw, index // columns * ph
        draw.text((x + 8, y + 3), label, font=font, fill=WHITE)
        sheet.paste(panel, (x, y + 28))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()

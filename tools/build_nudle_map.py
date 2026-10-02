#!/usr/bin/python3
"""Bake NUDLE's deterministic artwork; run after changing its map builder."""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mode_nudle


def main():
    world = mode_nudle.build_world()
    arrays = {f"mip_{i}": mip for i, mip in enumerate(world["mips"])}
    arrays.update({key: world[key] for key in ("land", "water", "park", "soma")})
    arrays["signature"] = np.asarray(mode_nudle.map_signature())
    target = ROOT / "assets" / "nudle_map.npz"
    np.savez_compressed(target, **arrays)
    print(target)


if __name__ == "__main__":
    main()

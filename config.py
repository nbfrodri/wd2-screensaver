"""User configuration: ~/.config/wd2-screensaver/config.toml (created on first run)."""

import copy
import os
import tomllib

PATH = os.path.expanduser("~/.config/wd2-screensaver/config.toml")

DEFAULTS = {
    "general": {
        "modes": [],          # empty = all modes
        "exclude": [],
        "rotate": 45,
        "fps": 24,
        "crt": True,
        "transitions": ["glitch", "crt", "vhs", "datamosh", "zoom"],
        "transition_time": 1.0,
    },
    "data": {
        "stats": True,
        "music": True,
        "audio": True,
        "notifications": True,
        "weather": True,
    },
}

TEMPLATE = """# DedSec / Watch Dogs 2 screensaver

[general]
# Modes to rotate through (empty = all). Names: dedsec, wrench, profiler, botnet,
# drone, hologram, plus any newer mode_*.py in ~/.local/share/wd2-screensaver.
modes = []
exclude = []
# Seconds per mode before switching
rotate = 45
fps = 24
# Slight scanline dimming on every other row
crt = true
# Transitions between modes, picked at random: glitch, crt, vhs, datamosh, zoom
transitions = ["glitch", "crt", "vhs", "datamosh", "zoom"]
transition_time = 1.0

[data]
# CPU / RAM / network in the panels
stats = true
# Now playing (MPRIS, e.g. Spotify) in tickers
music = true
# Audio-reactive visuals: analyses the sound you are playing, in memory only
audio = true
# Number of notifications (count only, never their content)
notifications = true
# Real weather and time of day (same source and location as the Omarchy bar)
weather = true
"""


def load():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        if not os.path.exists(PATH):
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            with open(PATH, "w") as f:
                f.write(TEMPLATE)
        with open(PATH, "rb") as f:
            user = tomllib.load(f)
        for section, values in user.items():
            if section in cfg and isinstance(values, dict):
                cfg[section].update(values)
    except Exception:
        pass
    return cfg


CFG = load()

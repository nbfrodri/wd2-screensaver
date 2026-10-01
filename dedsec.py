#!/usr/bin/python3
"""DedSec // Watch Dogs 2 style terminal screensaver.

Usage: dedsec.py [mode]      (mode = any mode NAME, e.g. dedsec, wrench, drone...)
       dedsec.py --list
Without an argument it starts on a mode no other monitor is showing and rotates.
Modes are discovered automatically: every mode_*.py with NAME and Mode(w, h).
"""

import fcntl
import glob
import importlib
import importlib.util
import json
import os
import random
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty

# Omarchy launches this with the system Python, which has the installed NumPy
# package. A shell may resolve python3 to mise or a virtual environment instead.
# Keep manual invocations working without changing that environment.
if __name__ == "__main__" and importlib.util.find_spec("numpy") is None:
    system_python = "/usr/bin/python3"
    if os.path.realpath(sys.executable) != os.path.realpath(system_python):
        os.execv(system_python, [system_python, os.path.abspath(__file__), *sys.argv[1:]])

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config
import transitions
from lib import Screen
from sysdata import DATA

CFG = config.CFG["general"]
CLASS = "org.omarchy.screensaver"
CLAIMS = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "wd2-screensaver-claims.json")


def discover(filtered=True):
    mods = []
    for path in sorted(glob.glob(os.path.join(HERE, "mode_*.py"))):
        try:
            m = importlib.import_module(os.path.basename(path)[:-3])
            if hasattr(m, "NAME") and hasattr(m, "Mode"):
                mods.append(m)
        except Exception as e:
            print("skipping %s: %s" % (path, e), file=sys.stderr)
    if not filtered:
        return mods
    want = [n.lower() for n in CFG.get("modes") or []]
    skip = [n.lower() for n in CFG.get("exclude") or []]
    sel = [m for m in mods if (not want or m.NAME.lower() in want) and m.NAME.lower() not in skip]
    return sel or mods


def claim_start(modes):
    """Pick a starting mode that other monitors haven't just claimed."""
    try:
        with open(CLAIMS, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            try:
                claims = json.loads(f.read() or "{}")
            except ValueError:
                claims = {}
            now = time.time()
            claims = {k: v for k, v in claims.items() if now - v < 15}
            free = [m for m in modes if m.NAME not in claims] or modes
            pick = random.choice(free)
            claims[pick.NAME] = now
            f.seek(0)
            f.truncate()
            f.write(json.dumps(claims))
            return pick
    except Exception:
        return random.choice(modes)


def screensaver_in_focus():
    try:
        out = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=1).stdout
        return json.loads(out).get("class") == CLASS
    except Exception:
        return True


def set_cursor_invisible(value):
    v = "true" if value else "false"
    subprocess.run(
        "hyprctl eval 'hl.config({ cursor = { invisible = %s } })' &>/dev/null || hyprctl keyword cursor:invisible %s &>/dev/null" % (v, v),
        shell=True, executable="/bin/bash")


def wait_for_resize():
    deadline = time.time() + 2
    while time.time() < deadline and shutil.get_terminal_size() == (80, 24):
        time.sleep(0.02)


class Saver:
    def __init__(self, modes, forced=None):
        self.forced = forced
        if forced:
            self.order = [forced]
        else:
            first = claim_start(modes)
            rest = [m for m in modes if m is not first]
            random.shuffle(rest)
            self.order = [first] + rest
        self.idx = 0
        self.size = None
        self.mode = None
        self.mode_start = time.time()
        self.trans = None

    def frame(self, now):
        size = shutil.get_terminal_size()
        if size != self.size:
            self.size = size
            self.trans = None
            self.scr = Screen(size.columns, size.lines)
            self.mode = self.order[self.idx].Mode(size.columns, size.lines)

        if not self.forced and len(self.order) > 1 and now - self.mode_start > CFG["rotate"]:
            old = self.scr.snapshot()
            self.idx = (self.idx + 1) % len(self.order)
            self.mode = self.order[self.idx].Mode(self.scr.w, self.scr.h)
            self.mode_start = now
            kinds = [k for k in CFG["transitions"] if k in transitions.ALL] or ["glitch"]
            self.trans = (transitions.ALL[random.choice(kinds)], old, now)

        self.scr.clear()
        self.mode.step(self.scr, now)
        if self.trans:
            fn, old, t0 = self.trans
            t = (now - t0) / CFG["transition_time"]
            if t >= 1:
                self.trans = None
            else:
                fn(self.scr, old, t, "// SWITCHING FEED: %s //" % self.order[self.idx].NAME)
        return self.scr.render(crt=CFG["crt"])


def farewell(saver, fd):
    """Let the current mode play a short goodbye (Mode.farewell(s, now, t)) before exiting."""
    mode = saver.mode
    if mode is None or not hasattr(mode, "farewell"):
        return
    mode._exit_snapshot = saver.scr.snapshot()
    sys.stdout.write("\033[?1003l\033[?1000l")
    sys.stdout.flush()
    t0 = time.time()
    while True:
        now = time.time()
        t = (now - t0) / 0.8
        if t >= 1:
            return
        saver.scr.clear()
        try:
            mode.farewell(saver.scr, now, t)
        except Exception:
            return
        sys.stdout.write(saver.scr.render(crt=CFG["crt"]))
        sys.stdout.flush()
        time.sleep(1 / 30)


def main():
    modes = discover()
    forced = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            print("\n".join(m.NAME.lower() for m in modes))
            return
        names = {m.NAME.lower(): m for m in discover(filtered=False)}
        forced = names.get(sys.argv[1].lower())
        if not forced:
            sys.exit("unknown mode %r, choose from: %s" % (sys.argv[1], ", ".join(names)))

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    managed = screensaver_in_focus()

    def cleanup(*_):
        sys.stdout.write("\033[?1003l\033[?1000l\033[0m\033[2J\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if managed:
            set_cursor_invisible(False)
        DATA.stop()
        if managed:
            subprocess.run(["pkill", "-f", "[o]rg.omarchy.screensaver"])
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, cleanup)

    tty.setcbreak(fd)
    sys.stdout.write("\033]11;rgb:00/00/00\007\033[?25l\033[2J")
    sys.stdout.flush()
    if managed:
        set_cursor_invisible(True)
    DATA.start()
    wait_for_resize()

    saver = Saver(modes, forced)
    fps = max(5, int(CFG["fps"]))
    start = time.time()
    armed_mouse = False
    last_focus_check = start
    while True:
        frame_start = time.time()
        sys.stdout.write(saver.frame(frame_start))
        sys.stdout.flush()

        # Enable mouse motion reporting after a short grace period so the
        # launch itself doesn't immediately dismiss the screensaver.
        if not armed_mouse and frame_start - start > 1.5:
            termios.tcflush(fd, termios.TCIFLUSH)
            sys.stdout.write("\033[?1000h\033[?1003h")
            armed_mouse = True

        if managed and frame_start - last_focus_check > 1:
            last_focus_check = frame_start
            if not screensaver_in_focus():
                farewell(saver, fd)
                cleanup()

        timeout = max(0, 1 / fps - (time.time() - frame_start))
        r, _, _ = select.select([fd], [], [], timeout)
        if r and frame_start - start > 0.5:
            farewell(saver, fd)
            cleanup()


if __name__ == "__main__":
    main()

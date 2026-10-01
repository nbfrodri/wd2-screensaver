"""PROFILER: ctOS citizen profiler with an identicon portrait and silly intel."""

import math
import random
import time

from engine3d import Camera
from mode_drone import BoxCity as City
from widgets import Panels, Particles, PostFX, Ticker

from lib import (CYAN, DARK, DIM_CYAN, GREEN, GREY, PINK, WHITE, YELLOW, Glitch,
                 blend)

NAME = "PROFILER"

FIRST = ["Marcus", "Sitara", "Josh", "Horatio", "Ray", "Lenni", "Dusan", "Tyler", "Maria", "Kevin",
         "Ana", "Jordan", "Priya", "Lucas", "Chloe", "Diego", "Wei", "Fatima", "Noah", "Elena"]
LAST = ["Holloway", "Dhillon", "Sauer", "Carlisle", "Kenney", "Brooks", "Nguyen", "Garcia", "Okafor",
        "Kowalski", "Tanaka", "Silva", "Novak", "Rossi", "Fischer", "Moreau", "Ivanova", "Hughes"]
JOBS = ["Barista", "Tech Bro", "Uber Driver", "Blume Engineer", "Podcaster", "Crypto Investor",
        "Dog Walker", "Influencer", "Software Tester", "Street Musician", "Nudle Intern", "Lawyer",
        "Food Truck Owner", "Yoga Instructor", "Security Guard", "Startup CEO", "Pastry Chef"]
INTEL = [
    "Password is 'password123'",
    "Owes $12,450 in parking tickets",
    "Searched 'how to delete browser history'",
    "Believes birds are government drones",
    "Has 47 unread voicemails from mom",
    "Secretly loves pineapple pizza",
    "Cried during a car commercial",
    "Has 3,204 open browser tabs",
    "Followed by 2 FBI agents (bored)",
    "Owns 14 identical black t-shirts",
    "Allergic to Mondays",
    "Lied about reading the terms of service",
    "Pays for 6 streaming services, uses 1",
    "Googled own name 41 times this week",
    "Talks to houseplants. Plants reply.",
    "Mining crypto on a smart fridge",
    "Has a Blume tattoo. Regrets it.",
    "Uses the same PIN for everything",
    "Thinks DedSec is a cereal brand",
    "Wanted for jaywalking in 3 states",
]
ACTIONS = ["STEAL $%d", "DOWNLOAD SONG", "DISABLE PHONE", "READ TEXTS", "ADD TO BOTNET", "SPOOF ID"]
STATUS = [("CITIZEN", CYAN), ("HIGH RISK", PINK), ("BLUME ASSET", YELLOW), ("DEDSEC SYMPATHIZER", GREEN)]


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.glitch = Glitch(0.01)
        self.scan_x = 0
        self.scanned = random.randint(2000, 9000)
        self.history = []
        self.new_profile(time.time())
        # dim street grid for the city map background
        self.cam = Camera(w, h, fov=0.8)
        self.city = City(block=8.0, street=4.0)
        self.fx = PostFX(band_speed=6)
        self.particles = Particles()
        self.last = time.time()
        self.peds = []
        cell = self.city.cell
        for _ in range(40):
            self.peds.append(self.new_ped(cell))
        self.reticles = [{"target": None, "x": w / 2, "y": h / 2, "lock": 0.0, "until": 0} for _ in range(3)]
        self.ticker = Ticker("ctOS INTEL", ["%s: %s" % (random.choice(FIRST), i) for i in random.sample(INTEL, 10)], color=CYAN)
        self.city_frame = None
        self.city_stamp = -1
        self.zoom = 0.0
        self.focus = [0.0, 0.0]
        self.lights = [(gx * cell - 2, gz * cell - 2) for gx in range(-3, 4) for gz in range(-3, 4)]
        self.card_rect = None
        self.panels = None

    def new_ped(self, cell):
        # walk along a street line (x = const or z = const) in the city grid
        along_x = random.random() < 0.5
        lane = (random.randint(-4, 4) + 1) * cell - self.city.street / 2 + random.uniform(-1.2, 1.2)
        pos = random.uniform(-4 * cell, 4 * cell)
        return {"ax": along_x, "lane": lane, "pos": pos, "v": random.choice((-1, 1)) * random.uniform(0.8, 2.2),
                "car": random.random() < 0.3, "name": "%s %s" % (random.choice(FIRST), random.choice(LAST)),
                "age": random.randint(18, 80), "flee_until": 0.0}

    def ped_world(self, p):
        return (p["pos"], 0.3, p["lane"]) if p["ax"] else (p["lane"], 0.3, p["pos"])

    def draw_city(self, s, now, dt):
        t = now * 0.08
        locked = next((r["target"] for r in self.reticles if r["lock"] >= 1 and r["target"]), None)
        self.zoom += ((1.0 if locked else 0.0) - self.zoom) * min(1, dt * 2)
        if locked:
            world = self.ped_world(locked)
            self.focus[0] += (world[0] - self.focus[0]) * min(1, dt * 2)
            self.focus[1] += (world[2] - self.focus[1]) * min(1, dt * 2)
        R = 40 - self.zoom * 14
        cam = self.cam
        # Geometry refreshes at 8 Hz; citizens and lock tracking run every frame.
        stamp = int(now * 8)
        if stamp != self.city_stamp:
            cam.pos = [self.focus[0] * self.zoom + math.sin(t) * R,
                       28 + math.sin(now * 0.13) * 6 - self.zoom * 8,
                       self.focus[1] * self.zoom - math.cos(t) * R]
            cam.yaw = -t
            cam.pitch = 0.55
            cam.roll = 0.0
            cell = self.city.cell
            gx0, gz0 = int(cam.pos[0]//cell), int(cam.pos[2]//cell)
            # Solid architecture carries the map's surfaces beneath tracking markers.
            boxes = [b for gx in range(gx0-3, gx0+4) for gz in range(gz0-3, gz0+4)
                     for b in self.city.buildings(gx, gz)]
            for gx in range(-4, 5):
                for gz in range(-4, 5):
                    x, z = gx*cell-2, gz*cell-2
                    cam.line(s, (x-1.2, .02, z), (x+1.2, .02, z), DIM_CYAN, fog=75, char="=")
            self.city.draw(s, cam, boxes, fog=75, win_dist=42, tick=now,
                           theme={"front": (10,23,30), "side": (6,13,22), "top": (19,29,35),
                                  "lit": .25, "lit_col": CYAN, "win_col": (20,49,62)})
            self.city_frame = s.snapshot()
            self.city_stamp = stamp
        else:
            s.restore(self.city_frame)
        cell = self.city.cell
        for i, (lx, lz) in enumerate(self.lights):
            green = int(now / 3 + i) % 2 == 0
            cam.point(s, (lx, 1.5, lz), "●", GREEN if green else PINK, fog=85)
        for p in self.peds:
            spd = p["v"] * (4 if p["car"] else 1)
            if p["car"]:
                # Signal phases alternate the two crossing directions.
                crossing = round((p["pos"] + 2) / cell) * cell - 2
                phase = int(now / 3 + round((p["lane"] + 2) / cell) + round((crossing + 2) / cell)) % 2
                if phase != int(p["ax"]) and 0 < (crossing - p["pos"]) * math.copysign(1, spd) < 3:
                    spd = 0
            elif now < p["flee_until"]:
                spd *= 3.5
            p["pos"] += spd * dt
            if abs(p["pos"]) > 5 * cell:
                p["v"] = -p["v"]
            q = cam.point(s, self.ped_world(p), "■" if p["car"] else "•", YELLOW if p["car"] else WHITE, fog=140)
            p["screen"] = q
            if p["car"] and q:
                back = list(self.ped_world(p))
                if p["ax"]:
                    back[0] -= math.copysign(1.5, spd)
                else:
                    back[2] -= math.copysign(1.5, spd)
                cam.line(s, self.ped_world(p), tuple(back), PINK, fog=140, char="·")

    def draw_reticles(self, s, now):
        visible = [p for p in self.peds if p.get("screen") and not p["car"]
                   and 4 < p["screen"][0] < self.w - 5 and 4 < p["screen"][1] < self.h - 4]
        for r in self.reticles:
            tgt = r["target"]
            if tgt is None or now > r["until"] or not tgt.get("screen"):
                if visible:
                    r["target"] = random.choice(visible)
                    r["until"] = now + random.uniform(2.5, 5)
                    r["lock"] = 0.0
                continue
            tx, ty = tgt["screen"][0], tgt["screen"][1]
            r["x"] += (tx - r["x"]) * 0.18
            r["y"] += (ty - r["y"]) * 0.18
            near = abs(tx - r["x"]) < 1.5 and abs(ty - r["y"]) < 1
            old_lock = r["lock"]
            r["lock"] = min(1.0, r["lock"] + 0.04) if near else 0.0
            if old_lock < 1 <= r["lock"]:
                tgt["flee_until"] = now + 4
                self.particles.burst(tx, ty, 8, (GREEN,), speed=6)
            size = int(10 - 6 * r["lock"])
            col = GREEN if r["lock"] >= 1 else YELLOW
            x, y = int(r["x"]), int(r["y"])
            s.brackets(x - size, y - size // 2 - 1, size * 2 + 1, size + 3, col, arm=1)
            if r["lock"] >= 1:
                s.text(x + size + 2, y - 1, tgt["name"], WHITE)
                s.text(x + size + 2, y + 1, "SIGNAL LOCK // SUBJECT FLEEING", PINK)
                s.text(x + size + 2, y, "AGE %d  //  RISK %d%%" % (tgt["age"], hash(tgt["name"]) % 100), GREY)
                if random.random() < 0.03:
                    self.particles.burst(x, y, 8, (GREEN,), speed=6)
            else:
                s.text(x + size + 2, y, "SCANNING " + "▮" * int(r["lock"] * 8), YELLOW)

    def new_profile(self, now):
        name = "%s %s" % (random.choice(FIRST), random.choice(LAST))
        status = random.choice(STATUS)
        self.profile = {
            "name": name,
            "age": random.randint(18, 79),
            "job": random.choice(JOBS),
            "income": "$%s" % format(random.randint(8, 420) * 1000, ","),
            "status": status,
            "intel": random.sample(INTEL, 2),
            "action": random.choice(ACTIONS).replace("%d", str(random.randint(20, 900))),
            "portrait": self.identicon(),
            "color": random.choice((PINK, CYAN, YELLOW, GREEN)),
        }
        self.started = now
        self.history = ([name] + self.history)[:6]
        self.scanned += 1
        self.glitch.trigger(now, 0.25)

    @staticmethod
    def spaced(lo, hi, gap_min, gap_max):
        out, v = [], lo + random.randint(0, gap_min)
        while v < hi:
            out.append(v)
            v += random.randint(gap_min, gap_max)
        return out or [lo]

    @staticmethod
    def identicon():
        rows = []
        for _ in range(8):
            half = [random.random() < 0.5 for _ in range(4)]
            rows.append(half + half[::-1])
        return rows

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        elapsed = now - self.started
        if elapsed > 6:
            self.new_profile(now)
            elapsed = 0

        self.draw_city(s, now, dt)
        self.draw_reticles(s, now)
        if self.panels:
            self.panels.draw(s, now)

        p = self.profile
        card_w = min(64, self.w - 6)
        card_h = 18
        slide = (1 - min(1.0, elapsed / 0.4)) ** 3
        cx = self.w - card_w - 3 + int(slide * (card_w + 6)) if self.w > 140 else (self.w - card_w) // 2
        cy = min(self.h - card_h - 3, max(3, (self.h - card_h) // 2 + 4))
        if self.panels is None:
            self.panels = Panels(self.w, self.h, keepout=[(self.w - card_w - 4, cy - 1, card_w + 4, card_h + 2),
                                                         (self.w // 2 - 30, 4, 60, self.h - 8)],
                                 max_panels=3, kinds=["cam", "radar", "spark", "bars", "decrypt", "eq"])
        col = p["color"]
        s.box(cx, cy, card_w, card_h, col, title="ctOS PROFILER", double=True)

        # portrait (identicon) – revealed row by row
        reveal = min(8, int(elapsed * 6))
        for r in range(8):
            for c in range(8):
                if r < reveal:
                    ch = "██" if p["portrait"][r][c] else "  "
                else:
                    ch = random.choice(("▒▒", "░░", "  "))
                s.text(cx + 3 + c * 2, cy + 2 + r, ch, col if r < reveal else GREY)
        s.text(cx + 3, cy + 11, "ID#%08X" % (hash(p["name"]) & 0xFFFFFFFF), GREY)

        def typed(text, start):
            n = max(0, int((elapsed - start) * 30))
            return text[:n]

        fx = cx + 22
        fields = [
            ("NAME", p["name"], WHITE),
            ("AGE", str(p["age"]), WHITE),
            ("OCCUPATION", p["job"], WHITE),
            ("INCOME", p["income"], GREEN),
            ("STATUS", p["status"][0], p["status"][1]),
        ]
        for i, (k, v, c) in enumerate(fields):
            s.text(fx, cy + 2 + i, k.ljust(11), GREY)
            s.text(fx + 11, cy + 2 + i, typed(v, 0.3 + i * 0.25), c)
        width = card_w - 25
        for i, line in enumerate(p["intel"]):
            text = typed("» " + line, 1.8 + i * 0.8)[:width]
            s.text(fx, cy + 8 + i, text, YELLOW)

        if elapsed > 3.2:
            act = "[ HACK: %s ]" % p["action"]
            s.text(fx, cy + 11, act, PINK if int(now * 4) % 2 else WHITE)

        # analysis bar
        bar_w = card_w - 6
        prog = min(1.0, elapsed / 4.5)
        s.text(cx + 3, cy + 14, "ANALYZING ", GREY)
        filled = int((bar_w - 10) * prog)
        s.text(cx + 13, cy + 14, "█" * filled + "░" * (bar_w - 10 - filled), col)
        if prog >= 1:
            s.text(cx + 3, cy + 15, "PROFILE COMPLETE // UPLOADED TO DEDSEC", GREEN)

        # side panels
        s.text(2, 0, ("ctOS 2.0 // CITIZEN SURVEILLANCE  //  " if self.w > 110 else "ctOS // PROFILER  ") + time.strftime("%H:%M:%S"), CYAN)
        tot = "PROFILES SCANNED: {:,}".format(self.scanned)
        s.text(self.w - len(tot) - 2, 0, tot, YELLOW)
        s.text(2, 1, "─" * (self.w - 4), DIM_CYAN)
        ry = self.h - 11
        if self.w > 140:
            s.text(2, ry, "RECENT TARGETS", GREY)
            for i, n in enumerate(self.history):
                s.text(2, ry + 2 + i, ("▸ " if i == 0 else "  ") + n, CYAN if i == 0 else GREY)

        self.particles.step(s, dt)
        self.ticker.draw(s, self.h - 1, now)
        self.fx.apply(s, now, glitch)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "scan", "ctOS // TARGETS RELEASED", CYAN)
        if .08 < t < .75:
            for r in self.reticles:
                x,y=int(r["x"]),int(r["y"])
                radius=1+int(t*6)
                s.put(x-radius,y,"[",blend(CYAN,(0,0,0),t))
                s.put(x+radius,y,"]",blend(CYAN,(0,0,0),t))

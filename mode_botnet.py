"""BOTNET: DedSec botnet spreading over a spinning 3D globe, packets racing along arcs."""

import math
import random
import time

import numpy as np

from lib import (BLACK, CYAN, DARK, DIM_CYAN, DIM_PINK, GREEN, GREY, PINK, PURPLE, WHITE,
                 YELLOW, Glitch, blend, overlaps, pulse)
from widgets import Panels, Particles, PostFX, Ticker
from sysdata import DATA

NAME = "BOTNET"

DEVICES = ["PHONE", "LAPTOP", "SMART TV", "FRIDGE", "CAR", "CAMERA", "DRONE", "ATM", "TOASTER",
           "SPEAKER", "ROUTER", "TRAFFIC LIGHT", "VAPE", "SMARTWATCH", "CONSOLE", "BILLBOARD"]
CITIES = ["SAN FRANCISCO", "OAKLAND", "CHICAGO", "LONDON", "TOKYO", "BERLIN", "SAO PAULO", "SEOUL",
          "MADRID", "LAGOS", "SYDNEY", "TORONTO", "MUMBAI", "PARIS", "MEXICO CITY"]


def sph(lat, lon):
    return (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))


def slerp(a, b, t):
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    om = math.acos(dot)
    if om < 1e-4:
        return a
    sa, sb = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
    return tuple(sa * x + sb * y for x, y in zip(a, b))


# Deliberately low-detail geographic outlines: land is visual context, not labels.
LAND = [
    [(-168,70),(-125,72),(-55,50),(-80,25),(-100,15),(-125,35),(-165,55)],
    [(-80,12),(-50,5),(-35,-10),(-55,-55),(-75,-30)],
    [(-18,35),(10,37),(40,12),(30,-30),(15,-35),(-5,0)],
    [(-10,36),(-10,60),(35,72),(150,65),(175,50),(140,30),(100,5),(65,25),(40,40)],
    [(112,-12),(145,-10),(155,-30),(130,-40),(113,-28)],
    [(-55,60),(-20,70),(-40,83),(-60,78)],
]


def inside(x, y, polygon):
    hit = False
    ax, ay = polygon[-1]
    for bx, by in polygon:
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
        ax, ay = bx, by
    return hit


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.glitch = Glitch(0.008)
        self.fx = PostFX()
        self.particles = Particles()
        self.ticker = Ticker("BOTNET FEED", ["#DEDSEC botnet growing in %s" % c for c in random.sample(CITIES, 8)] +
                             ["#BLUME servers under pressure", "#ctOS response time +900%"])
        self.R = min(h * 0.38, w * 0.19)
        self.cx, self.cy = w / 2, h / 2
        rw = int(self.R * 2.2) + 4
        self.panels = Panels(w, h, keepout=[(int(self.cx - rw), 3, rw * 2, h - 6)], max_panels=4,
                             kinds=["spark", "bars", "hexdump", "loaders", "radar", "minimap", "eq"])
        self.land_color = blend(DIM_CYAN, GREEN, 0.3)
        self.land = [sph(math.radians(lat), math.radians(lon))
                     for lat in range(-56, 84, 3) for lon in range(-177, 180, 3)
                     if any(inside(lon, lat, outline) for outline in LAND)]
        self.grid = [sph(math.radians(lat), i / 72 * math.tau)
                     for lat in range(-60, 90, 30) for i in range(72)]
        self.grid += [sph(-math.pi / 2 + i / 47 * math.pi, math.radians(lon))
                      for lon in range(0, 360, 30) for i in range(48)]
        # Geographic lookup is baked once; inverse sphere raster gives continuous material.
        self.geography = np.array([[any(inside(lon, lat, outline) for outline in LAND)
                                    for lon in range(-180, 180, 2)]
                                   for lat in range(-90, 91, 2)], dtype=bool)
        self.gx0 = max(0, int(self.cx-self.R*2)-1)
        self.gy0 = max(0, int(self.cy*2-self.R*2)-1)
        gx1 = min(w, int(self.cx+self.R*2)+2)
        gy1 = min(h*2, int(self.cy*2+self.R*2)+2)
        yy, xx = np.mgrid[self.gy0:gy1, self.gx0:gx1]
        self.sx = (xx - self.cx) / (self.R * 2)
        self.sy = -(yy - self.cy * 2) / (self.R * 2)
        self.surface = self.sx**2 + self.sy**2 < 1
        self.spans = [(int(xs[0]), int(xs[-1])+1) if len(xs) else (0,0)
                      for xs in (np.flatnonzero(row) for row in self.surface)]
        self.sz = -np.sqrt(np.maximum(0, 1-self.sx**2-self.sy**2))
        self.light_levels = 24
        # A directional terminator keeps the nightside dark without hard bands.
        illumination = -.52*self.sx + .26*self.sy - .81*self.sz
        self.sunlight = np.rint(np.clip(.08+.9*np.maximum(0, illumination),0,1)*self.light_levels).astype(np.int16)
        self.surface_palette = []
        materials = [(12,45,95)] + [tuple(v*(.76+.24*r/3) for v in (43,122,91)) for r in range(4)] + [(180,180,205)]
        for material in materials:
            for cloud in (0,1):
                base = tuple(v*(1-cloud*.58)+c*cloud*.58 for v,c in zip(material,(190,210,224)))
                self.surface_palette.extend(tuple(int(v*l/self.light_levels) for v in base)
                                            for l in range(self.light_levels+1))
        self.last = time.time()
        self.reset(self.last)

    def reset(self, now):
        self.hub = sph(math.radians(37.7), math.radians(-122.4))
        self.nodes = [{"p": self.hub, "label": "DEDSEC", "born": now, "hub": True}]
        self.links = []
        self.packets = []
        self.next_node = now
        self.complete_until = None
        self.max_nodes = 46

    def add_node(self, now):
        lat = math.asin(random.uniform(-0.85, 0.9))
        lon = random.uniform(-math.pi, math.pi)
        p = sph(lat, lon)
        parent = min(self.nodes, key=lambda n: -sum(a * b for a, b in zip(n["p"], p)) + random.random() * 0.6)
        node = {"p": p, "label": random.choice(DEVICES), "city": random.choice(CITIES), "born": now, "hub": False}
        self.nodes.append(node)
        path = []
        for i in range(25):
            t = i / 24
            lift = 1 + 0.18 * math.sin(t * math.pi)
            path.append(tuple(c * lift for c in slerp(parent["p"], p, t)))
        self.links.append((parent, node, now, path))

    def view(self, p):
        x, y, z = p
        c, s, ct, st = self.rotation
        x, z = x * c + z * s, -x * s + z * c
        y, z = y * ct - z * st, y * st + z * ct
        k = 4.0 / (4.0 + z)
        return self.cx + x * self.R * 2 * k, self.cy - y * self.R * k, z

    def draw_globe(self, s, now):
        c, sn, ct, st = self.rotation
        # Reverse the two camera rotations to sample fixed continents and moving clouds.
        vy = self.sy * ct + self.sz * st
        vz = -self.sy * st + self.sz * ct
        vx = self.sx * c - vz * sn
        vz = self.sx * sn + vz * c
        lat = np.degrees(np.arcsin(np.clip(vy, -1, 1)))
        lon = np.degrees(np.arctan2(vz, vx))
        land = self.geography[np.clip(((lat + 90)/2).astype(int), 0, 90),
                              ((lon + 180)/2).astype(int) % 180]
        relief = np.rint((.5+.5*np.sin(lon*.19+np.sin(lat*.14)*3)*np.cos(lat*.31))*3).astype(np.int16)
        clouds = (np.sin(lon*.105+now*.06+np.sin(lat*.15)*2)+np.cos(lat*.22+lon*.04)) > 1.48
        material = np.where(land, relief+1, 0)
        material = np.where(np.abs(lat)>72, 5, material)
        levels = self.light_levels+1
        indices = material*(levels*2) + clouds*levels + self.sunlight
        get = self.surface_palette.__getitem__
        for rownum, row in enumerate(indices.tolist()):
            py = rownum+self.gy0
            layer = (s.pb if py & 1 else s.pt)[py>>1]
            x0, x1 = self.spans[rownum]
            layer[self.gx0+x0:self.gx0+x1] = map(get, row[x0:x1])
        for p in self.grid:
            x, y, z = self.view(p)
            if z < 0.2:
                s.pixel(int(x), int(y * 2), DIM_CYAN if z < -0.3 else DARK)
        # Relays orbit outside the surface; far-side relays fade behind it.
        for i in range(3):
            a = now * 0.35 + i * math.tau / 3
            p = (math.cos(a) * 1.35, math.sin(a * 0.7 + i) * 0.55, math.sin(a) * 1.35)
            x, y, z = self.view(p)
            if z < 0.2:
                s.text(int(x) - 2, int(y), "[=◆=]", WHITE)
                s.put(int(x), int(y) - 1, "┬", CYAN)
                s.put(int(x) - 3, int(y), "▦", CYAN)
                s.put(int(x) + 3, int(y), "▦", CYAN)
                if z < -0.5:
                    hx, hy, hz = self.view(self.hub)
                    if hz < 0:
                        s.pixel_line(int(x), int(y * 2), int(hx), int(hy * 2), DIM_PINK)
        # A fine half-pixel atmosphere follows the limb, leaving the surface clear.
        for i in range(120):
            a, b = i / 120 * math.tau, (i+1) / 120 * math.tau
            col = blend((24,65,103), CYAN, .15+.25*max(0, -math.cos(a)))
            s.pixel_line(int(self.cx+math.cos(a)*self.R*2), int((self.cy+math.sin(a)*self.R)*2),
                         int(self.cx+math.cos(b)*self.R*2), int((self.cy+math.sin(b)*self.R)*2), col)

    def panel_status(self, s, now):
        for panel in self.panels.items:
            if panel['title'] != 'AUDIO TAP':
                continue
            age = now-panel['born']
            if age < .3 or panel['life']-age < .3:
                continue
            if not DATA.audio_live or DATA.level < .005:
                x,y,w,h = panel['r']
                label = 'MONITOR OFFLINE' if not DATA.audio_live else 'SILENCE / WAITING'
                s.text(x+(w-len(label))//2, y+h//2, label, DIM_CYAN)

    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "scan", "RELAY NETWORK / DISCONNECTED", CYAN)
        if 0 < t < 0.82:
            hx, hy, hz = self.view(self.hub)
            for i, node in enumerate(self.nodes[1:]):
                x, y, z = self.view(node["p"])
                if z >= 0:
                    continue
                q = min(1, max(0, (t - i % 7 * 0.035) / 0.55))
                px, py = x + (hx - x) * q, y + (hy - y) * q
                s.pixel(int(px), int(py * 2), blend(CYAN, WHITE, q * 0.5))
                s.put(int(x), int(y), "·", blend(GREEN, BLACK, min(1, t * 2)))

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        self.spin = now * 0.25
        self.tilt = 0.35 + math.sin(now * 0.2) * 0.15
        self.rotation = (math.cos(self.spin), math.sin(self.spin), math.cos(self.tilt), math.sin(self.tilt))

        self.panels.draw(s, now)
        self.panel_status(s, now)

        if self.complete_until is not None:
            if now > self.complete_until:
                self.reset(now)
            else:
                self.draw_globe(s, now)
                self.particles.step(s, dt)
                self.draw_complete(s, now)
                self.ticker.draw(s, self.h - 1, now)
                self.fx.apply(s, now, True)
                return
        elif len(self.nodes) >= self.max_nodes:
            self.complete_until = now + 3.5
            for _ in range(4):
                self.particles.burst(self.cx, self.cy, 60, speed=random.uniform(15, 35), life=(0.8, 2.2))

        if now > self.next_node:
            self.add_node(now)
            self.next_node = now + random.uniform(0.25, 0.8)

        self.draw_globe(s, now)

        # arcs: lifted great circles that grow from parent to child
        arcs = []
        for a, b, born, world_path in self.links:
            grow = min(1.0, (now - born) * 1.8)
            n = 24
            pts = [self.view(p) for p in world_path[:int(n * grow) + 1]]
            for i in range(len(pts) - 1):
                x0, y0, z0 = pts[i]
                x1, y1, z1 = pts[i + 1]
                col = blend(PINK, BLACK, 0.25) if z0 < 0 else blend(DIM_PINK, BLACK, 0.5)
                s.line(int(x0), int(y0), int(x1), int(y1), "·", col)
            if grow >= 1:
                arcs.append(pts)
        if arcs and random.random() < 0.5:
            path = random.choice(arcs)
            self.packets.append({"path": path if random.random() < 0.5 else path[::-1], "i": 0.0,
                                 "color": random.choice((CYAN, YELLOW, GREEN, WHITE))})
        alive = []
        for pk in self.packets:
            pk["i"] += 14.4 * dt
            i = int(pk["i"])
            if i < len(pk["path"]):
                for k in range(4):
                    if 0 <= i - k < len(pk["path"]):
                        x, y, z = pk["path"][i - k]
                        col = blend(pk["color"], BLACK, k / 4 + (0.5 if z > 0 else 0))
                        s.put(int(x), int(y), "●" if k == 0 else "•", col)
                alive.append(pk)
        self.packets = alive[-120:]

        labels = []
        for n in self.nodes:
            x, y, z = self.view(n["p"])
            age = now - n["born"]
            front = z < 0
            if n["hub"]:
                col = blend(PINK, WHITE, pulse(now, 4))
                if front:
                    for r in range(1, 4):
                        rr = (now * 3 + r) % 4
                        for i in range(16):
                            a = i / 16 * math.tau
                            s.put(int(x + math.cos(a) * rr * 2), int(y + math.sin(a) * rr), "·", blend(PINK, BLACK, rr / 4))
                    s.text(int(x) - 3, int(y) - 1, "▄▀▀▀▄", col)
                    s.text(int(x) - 3, int(y), "█ ◆ █", col)
                    s.text(int(x) + 3, int(y) + 1, "DEDSEC HQ", WHITE)
                    labels.append((int(x)+3,int(y)+1,9,1))
                continue
            if not front:
                s.put(int(x), int(y), "∙", DARK)
                continue
            if age < 0.8:
                rr = age * 6
                for i in range(12):
                    a = i / 12 * math.tau
                    s.put(int(x + math.cos(a) * rr * 2), int(y + math.sin(a) * rr), "+", blend(YELLOW, BLACK, age / 0.8))
                if age < dt * 2:
                    self.particles.burst(x, y, 10, (YELLOW, GREEN), speed=8)
            col = GREEN if int(now * 3 + x) % 9 else WHITE
            s.put(int(x), int(y), "◉", col)
            rect = (int(x)+2,int(y),max(len(n['label']),len(n.get('city',''))),2)
            visible = rect[0]+rect[2] < self.w-2 and 2 < rect[1] < self.h-5
            if visible and len(labels)<3 and not any(overlaps(rect,r,1) for r in labels) and ((age < 1.5 and n in self.nodes[-2:]) or (z < -0.85 and int(x) % 3 == 0)):
                s.text(int(x) + 2, int(y), n["label"], YELLOW if age < 3 else GREY)
                if age < 3:
                    s.text(int(x) + 2, int(y) + 1, n["city"], DIM_CYAN)
                labels.append(rect)

        self.particles.step(s, dt)

        count = len(self.nodes) - 1
        total = self.max_nodes - 1
        s.text(2, 0, "DEDSEC BOTNET // %s" % time.strftime("%H:%M:%S"), PINK)
        s.text(2, 1, "DEVICES OWNED: %d / %d" % (count, total), YELLOW)
        bar_w = min(40, self.w // 3)
        filled = int(bar_w * count / total)
        bar = "PROCESSING POWER [" + "█" * filled + "░" * (bar_w - filled) + "]"
        s.text(self.w - len(bar) - 2, 0, bar, CYAN)
        tf = "%.1f TFLOPS" % (count * 3.7 + random.random())
        s.text(self.w - len(tf) - 2, 1, tf, GREEN)
        self.ticker.draw(s, self.h - 1, now)
        self.fx.apply(s, now, glitch)

    def draw_complete(self, s, now):
        remaining = self.complete_until - now
        target_x = int(self.cx + self.R * 1.5)
        target_y = int(self.cy - self.R * 0.6)
        if remaining < 2.5:
            for node in self.nodes[::3]:
                x, y, z = self.view(node["p"])
                if z < 0:
                    s.pixel_line(int(x), int(y * 2), target_x, target_y * 2, PINK if int(now * 12) % 2 else CYAN)
            s.brackets(target_x - 3, target_y - 2, 7, 5, YELLOW, arm=1)
            s.text(target_x - 5, target_y - 3, "BLUME CORE", YELLOW)
        if remaining < 1.2:
            impact = 1-remaining/1.2
            for ring in (0, .16):
                radius = max(0,impact-ring)*self.R*1.5
                col = blend(WHITE,CYAN,impact)
                for i in range(48):
                    a = i/48*math.tau
                    s.pixel(int(target_x+math.cos(a)*radius*2),
                            int((target_y+math.sin(a)*radius)*2),blend(col,BLACK,impact))
        msg = ["CORE ISOLATED" if remaining < 1.2 else "BEAM ATTACK" if remaining < 2.5 else "BOTNET READY", "%d DEVICES UNDER DEDSEC CONTROL" % (len(self.nodes) - 1), "TARGET: BLUME ctOS CORE"]
        y = self.h - 8
        bw = max(len(m) for m in msg) + 8
        col = PINK if int(now * 6) % 2 else YELLOW
        s.box((self.w - bw) // 2, y - 1, bw, 5, col, double=True)
        for i, m in enumerate(msg):
            s.center(y + i, m, WHITE if i else col)

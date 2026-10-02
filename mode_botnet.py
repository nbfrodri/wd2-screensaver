"""BOTNET: DedSec botnet spreading over a spinning 3D globe, packets racing along arcs."""

import math
import random
import time

import numpy as np

from lib import (BLACK, CYAN, DARK, DIM_CYAN, DIM_PINK, GREEN, GREY, PINK, PURPLE, WHITE,
                 YELLOW, Glitch, blend, line_points, overlaps, pulse)
from widgets import Particles, PostFX, Ticker
from sysdata import DATA

NAME = "BOTNET"

DEVICES = ["PHONE", "LAPTOP", "SMART TV", "FRIDGE", "CAR", "CAMERA", "DRONE", "ATM", "TOASTER",
           "SPEAKER", "ROUTER", "TRAFFIC LIGHT", "VAPE", "SMARTWATCH", "CONSOLE", "BILLBOARD"]
CITIES = ["SAN FRANCISCO", "OAKLAND", "CHICAGO", "LONDON", "TOKYO", "BERLIN", "SAO PAULO", "SEOUL",
          "MADRID", "LAGOS", "SYDNEY", "TORONTO", "MUMBAI", "PARIS", "MEXICO CITY"]
REGIONS = ["N.AMERICA", "S.AMERICA", "EUROPE", "AFRICA", "ASIA", "OCEANIA"]


def sph(lat, lon):
    return (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))


def slerp(a, b, t):
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    om = math.acos(dot)
    if om < 1e-4:
        return a
    sa, sb = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
    return tuple(sa * x + sb * y for x, y in zip(a, b))


def region_of(lat, lon):
    if lon < -30:
        return 0 if lat > 12 else 1
    if lon < 60:
        if lat > 35:
            return 4 if lon > 45 else 2
        return 3
    return 5 if lat < -10 else 4


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


def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def add_glow(base, col, t):
    """Additive light over an existing pixel; keeps the surface colour visible."""
    return (min(255, int(base[0] + col[0] * t)), min(255, int(base[1] + col[1] * t)),
            min(255, int(base[2] + col[2] * t)))


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
        self.pr = self.R * 2  # globe radius in pixels (columns and half-rows are ~square)
        self.grid = np.array([sph(math.radians(lat), i / 96 * math.tau)
                              for lat in range(-60, 90, 30) for i in range(96)] +
                             [sph(-math.pi / 2 + i / 63 * math.pi, math.radians(lon))
                              for lon in range(0, 360, 30) for i in range(64)])
        # Geographic lookup is baked once; inverse sphere raster gives continuous material.
        self.geography = np.array([[any(inside(lon, lat, outline) for outline in LAND)
                                    for lon in range(-180, 180, 2)]
                                   for lat in range(-90, 91, 2)], dtype=bool)
        self.gx0 = max(0, int(self.cx-self.R*2)-1)
        self.gy0 = max(0, int(self.cy*2-self.R*2)-1)
        gx1 = min(w, int(self.cx+self.R*2)+2)
        gy1 = min(h*2, int(self.cy*2+self.R*2)+2)
        self.gx1, self.gy1 = gx1, gy1
        yy, xx = np.mgrid[self.gy0:gy1, self.gx0:gx1]
        self.sx = (xx + .5 - self.cx) / (self.R * 2)
        self.sy = -(yy + .5 - self.cy * 2) / (self.R * 2)
        self.surface = self.sx**2 + self.sy**2 < 1
        self.spans = [(int(xs[0]), int(xs[-1])+1) if len(xs) else (0,0)
                      for xs in (np.flatnonzero(row) for row in self.surface)]
        self.sz = -np.sqrt(np.maximum(0, 1-self.sx**2-self.sy**2))
        self.light_levels = 24
        # A directional terminator keeps the nightside dark without hard bands.
        illumination = -.52*self.sx + .26*self.sy - .81*self.sz
        self.sunlight = np.rint(np.clip(.1+.88*np.maximum(0, illumination),0,1)*self.light_levels).astype(np.int16)
        self.night = illumination < -.05
        self.surface_palette = []
        materials = [(12,45,95)] + [tuple(v*(.76+.24*r/3) for v in (43,122,91)) for r in range(4)] + [(180,180,205)]
        for material in materials:
            for cloud in (0,1):
                base = tuple(v*(1-cloud*.62)+c*cloud*.62 for v,c in zip(material,(196,214,228)))
                self.surface_palette.extend(tuple(int(v*l/self.light_levels) for v in base)
                                            for l in range(self.light_levels+1))
        self.city_light = (150, 120, 40)
        self.layout()
        self.last = time.time()
        self.reset(self.last)

    # ------------------------------------------------------------------ layout
    def layout(self):
        w, h = self.w, self.h
        gl = int(self.cx - self.pr) - 2
        gr = int(self.cx + self.pr) + 3
        pw = min(46, gl - 2, w - gr - 2)
        self.side = pw >= 20
        if not self.side:
            return
        top, bottom = 3, h - 2
        avail = bottom - top
        mrows = max(3, min((pw - 4) // 4, avail - 10))
        mh = mrows + 3
        lx = max(1, (gl - pw) // 2)
        rx = gr + max(0, (w - gr - pw) // 2)
        self.p_nodes = (lx, top, pw, avail - mh - 1)
        self.p_map = (lx, top + avail - mh, pw, mh)
        th = max(7, avail // 2)
        self.p_traffic = (rx, top, pw, th)
        self.p_regions = (rx, top + th + 1, pw, avail - th - 1)
        mw = pw - 4
        mph = mrows * 2
        self.map_size = (mw, mph)
        ocean, land = (5, 14, 32), (22, 74, 54)
        self.map_rows = []
        for j in range(mph):
            lat = 90 - (j + .5) / mph * 180
            row = []
            for i in range(mw):
                lon = -180 + (i + .5) / mw * 360
                g = self.geography[min(90, max(0, int((lat + 90) / 2))), int((lon + 180) / 2) % 180]
                row.append(land if g else ocean)
            self.map_rows.append(row)
        self.history = [0] * (pw - 4)
        self.hist_next = 0.0

    def reset(self, now):
        self.hub = sph(math.radians(37.7), math.radians(-122.4))
        self.nodes = [{"p": self.hub, "label": "DEDSEC", "city": "SAN FRANCISCO", "born": now, "hub": True,
                       "lat": 37.7, "lon": -122.4, "id": 0, "phase": 0.0, "rtt": 1}]
        self.links = []
        self.packets = []
        self.next_node = now
        self.complete_until = None
        self.max_nodes = 46
        self.sent = 0
        self.rate = 0.0

    def add_node(self, now):
        for _ in range(24):
            lat = math.degrees(math.asin(random.uniform(-0.8, 0.9)))
            lon = random.uniform(-180, 180)
            if self.geography[int((lat + 90) / 2), int((lon + 180) / 2) % 180]:
                break
        p = sph(math.radians(lat), math.radians(lon))
        parent = min(self.nodes, key=lambda n: -sum(a * b for a, b in zip(n["p"], p)) + random.random() * 0.6)
        node = {"p": p, "label": random.choice(DEVICES), "city": random.choice(CITIES), "born": now, "hub": False,
                "lat": lat, "lon": lon, "id": len(self.nodes), "phase": random.random(),
                "rtt": random.randint(12, 180)}
        self.nodes.append(node)
        dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(parent["p"], p))))
        height = 0.06 + 0.16 * math.acos(dot) / math.pi
        path = []
        for i in range(25):
            t = i / 24
            lift = 1 + height * math.sin(t * math.pi)
            path.append(tuple(c * lift for c in slerp(parent["p"], p, t)))
        col = CYAN if random.random() < 0.35 else PINK
        self.links.append((parent, node, now, np.array(path), col))

    # ------------------------------------------------------------------ projection
    def matrix(self):
        c, s, ct, st = self.rotation
        return np.array([[c, 0, s], [s * st, ct, -c * st], [-s * ct, st, c * ct]])

    def view(self, p):
        """Orthographic view: (column, row, depth); depth < 0 faces the camera."""
        x, y, z = p
        c, s, ct, st = self.rotation
        x, z = x * c + z * s, -x * s + z * c
        y, z = y * ct - z * st, y * st + z * ct
        return self.cx + x * self.R * 2, self.cy - y * self.R, z

    def project(self, pts):
        """Pixel coordinates and visibility for an (..., 3) array of world points."""
        v = pts @ self.matrix().T
        px = self.cx + v[..., 0] * self.pr
        py = self.cy * 2 - v[..., 1] * self.pr
        vis = (v[..., 2] < 0) | (v[..., 0] ** 2 + v[..., 1] ** 2 > 1.0)
        return px, py, v[..., 2], vis

    def tint(self, s, x, py, col, t):
        if 0 <= x < self.w and 0 <= py < s.ph:
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            base = layer[x]
            layer[x] = add_glow(base, col, t) if base is not None else mix(BLACK, col, t)

    # ------------------------------------------------------------------ globe
    def draw_globe(self, s, now):
        m = self.matrix()
        # Reverse the camera rotation to sample fixed continents and moving clouds.
        vx = m[0, 0] * self.sx + m[1, 0] * self.sy + m[2, 0] * self.sz
        vy = m[0, 1] * self.sx + m[1, 1] * self.sy + m[2, 1] * self.sz
        vz = m[0, 2] * self.sx + m[1, 2] * self.sy + m[2, 2] * self.sz
        lat = np.degrees(np.arcsin(np.clip(vy, -1, 1)))
        lon = np.degrees(np.arctan2(vz, vx))
        land = self.geography[np.clip(((lat + 90)/2).astype(int), 0, 90),
                              ((lon + 180)/2).astype(int) % 180]
        relief = np.rint((.5+.5*np.sin(lon*.19+np.sin(lat*.14)*3)*np.cos(lat*.31))*3).astype(np.int16)
        # Blobby drifting weather cells instead of latitude bands.
        lr, ar = np.radians(lon), np.radians(lat)
        n = (np.sin(lr * 3 + now * .05 + 2.2 * np.sin(ar * 4)) * np.sin(ar * 5 + 1.4 * np.cos(lr * 2 - now * .03))
             + .55 * np.sin(lr * 7 + ar * 6 + now * .07))
        clouds = n > .62
        material = np.where(land, relief+1, 0)
        material = np.where(np.abs(lat)>74, 5, material)
        levels = self.light_levels+1
        indices = material*(levels*2) + clouds*levels + self.sunlight
        # Sparse city lights on the nightside land make the terminator readable.
        lights = land & self.night & ~clouds & ((np.floor(lon * .9) * 7 + np.floor(lat * .9) * 13) % 11 == 0)
        get = self.surface_palette.__getitem__
        light_rows = lights.any(axis=1).tolist()
        for rownum, row in enumerate(indices.tolist()):
            py = rownum+self.gy0
            layer = (s.pb if py & 1 else s.pt)[py>>1]
            x0, x1 = self.spans[rownum]
            layer[self.gx0+x0:self.gx0+x1] = map(get, row[x0:x1])
            if light_rows[rownum]:
                for x in np.flatnonzero(lights[rownum, x0:x1]).tolist():
                    layer[self.gx0 + x0 + x] = self.city_light
        # Faint graticule as additive light, never opaque dots.
        px, py, z, vis = self.project(self.grid)
        for x, y, zz in zip(px.astype(int).tolist(), py.astype(int).tolist(), z.tolist()):
            if zz < -0.15:
                self.tint(s, x, y, (0, 90, 120), 0.24)
        # A fine half-pixel atmosphere follows the limb, leaving the surface clear.
        for i in range(120):
            a, b = i / 120 * math.tau, (i+1) / 120 * math.tau
            col = blend((24,65,103), CYAN, .15+.25*max(0, -math.cos(a)))
            s.pixel_line(int(self.cx+math.cos(a)*self.pr), int(self.cy*2+math.sin(a)*self.pr),
                         int(self.cx+math.cos(b)*self.pr), int(self.cy*2+math.sin(b)*self.pr), col)

    def draw_satellites(self, s, now):
        hx, hy, hz = self.view(self.hub)
        for i in range(3):
            a = now * 0.35 + i * math.tau / 3
            p = (math.cos(a) * 1.35, math.sin(a * 0.7 + i) * 0.55, math.sin(a) * 1.35)
            x, y, z = self.view(p)
            ux, uy = (x - self.cx) / self.pr, (self.cy - y) / self.R
            if z >= 0 and ux * ux + uy * uy < 1:
                continue
            col = WHITE if z < 0 else GREY
            s.text(int(x) - 2, int(y), "[=◆=]", col)
            s.put(int(x), int(y) - 1, "┬", CYAN if z < 0 else DIM_CYAN)
            if hz < -0.1 and z < 0:
                pts = line_points(int(x), int(y) * 2 + 1, int(hx), int(hy * 2))
                k = int(now * 20)
                for j, (qx, qy) in enumerate(pts[1:-2]):
                    if (j + k) % 4 == 0:
                        self.tint(s, qx, qy, CYAN, 0.6)

    # ------------------------------------------------------------------ network
    def draw_arcs(self, s, now):
        if not self.links:
            return []
        paths = np.stack([l[3] for l in self.links])
        px, py, z, vis = self.project(paths)
        px, py, vis = px.astype(int).tolist(), py.astype(int).tolist(), vis.tolist()
        z = z.tolist()
        halo, core = [], []
        live = []
        for li, (a, b, born, _, col) in enumerate(self.links):
            age = now - born
            grow = min(1.0, age * 1.8)
            n = int(24 * grow)
            bright = mix(col, WHITE, max(0.0, 1 - age / 1.5) * 0.6)
            back = mix(col, BLACK, 0.62)
            xs, ys, vs, zs = px[li], py[li], vis[li], z[li]
            for i in range(n):
                if not (vs[i] and vs[i + 1]):
                    continue
                c = bright if zs[i] < 0 else back
                seg = line_points(xs[i], ys[i], xs[i + 1], ys[i + 1])
                core.append((seg, c))
                if zs[i] < 0:
                    halo.append((seg, col))
            if grow < 1 and vs[n]:
                s.pixel(xs[n], ys[n], WHITE)
                halo.append(([(xs[n], ys[n])], WHITE))
            if grow >= 1:
                live.append(li)
        tint = self.tint
        for seg, col in halo:
            for x, y in seg:
                tint(s, x, y - 1, col, 0.13)
                tint(s, x, y + 1, col, 0.13)
        pix = s.pixel
        for seg, col in core:
            for x, y in seg:
                pix(x, y, col)
        self.frame_paths = (px, py, vis, z)
        return live

    def draw_packets(self, s, now, dt, live):
        boost = DATA.level if DATA.audio_live else 0.0
        if live and random.random() < 0.55 + boost:
            li = random.choice(live)
            self.packets.append({"l": li, "t": 0.0, "dir": random.random() < 0.5, "v": random.uniform(.5, .9),
                                 "color": random.choice((CYAN, YELLOW, WHITE, GREEN))})
            self.sent += 1
        if not self.links:
            return
        px, py, vis, z = self.frame_paths
        alive = []
        for pk in self.packets:
            pk["t"] += pk["v"] * dt
            if pk["t"] >= 1 or pk["l"] >= len(self.links):
                continue
            alive.append(pk)
            li = pk["l"]
            for k in range(4):
                t = pk["t"] - k * 0.03
                if t < 0:
                    break
                f = (1 - t if pk["dir"] else t) * 24
                i = min(23, int(f))
                if not vis[li][i]:
                    continue
                q = f - i
                x = int(px[li][i] + (px[li][i + 1] - px[li][i]) * q)
                y = int(py[li][i] + (py[li][i + 1] - py[li][i]) * q)
                col = pk["color"] if z[li][i] < 0 else mix(pk["color"], BLACK, .6)
                if k == 0:
                    s.pixel(x, y, mix(col, WHITE, .5))
                    self.tint(s, x - 1, y, col, .5)
                    self.tint(s, x + 1, y, col, .5)
                else:
                    self.tint(s, x, y, col, .7 - k * .17)
        self.packets = alive[-160:]

    def draw_nodes(self, s, now, dt):
        pts = np.array([n["p"] for n in self.nodes])
        px, py, z, vis = self.project(pts)
        px, py, z = px.tolist(), py.tolist(), z.tolist()
        labels = []
        tint = self.tint
        for k, n in enumerate(self.nodes):
            if z[k] >= -0.04:
                continue
            x, y = int(px[k]), int(py[k])
            age = now - n["born"]
            edge = min(1.0, -z[k] / 0.3)
            if n["hub"]:
                col = mix(PINK, WHITE, pulse(now, 4) * .4)
                for r in (0, .5):
                    ph = (now * .7 + r) % 1
                    rad = 3 + ph * 7
                    for i in range(28):
                        a = i / 28 * math.tau
                        tint(s, int(x + math.cos(a) * rad), int(y + math.sin(a) * rad), PINK, (1 - ph) * .7)
                s.pixel_circle(x, y, 2, col)
                s.pixel(x, y, WHITE)
                cx, cy = x + 3, (y >> 1) - 1
                s.text(cx, cy, "DEDSEC HQ", WHITE)
                labels.append((cx, cy, 9, 1))
                continue
            if age < 0.9:
                rad = 1 + age * 11
                for i in range(20):
                    a = i / 20 * math.tau
                    tint(s, int(x + math.cos(a) * rad), int(y + math.sin(a) * rad), YELLOW, (1 - age / .9) * .9)
            else:
                ph = (now * .55 + n["phase"]) % 1
                rad = 1.5 + ph * 3.5
                for i in range(12):
                    a = i / 12 * math.tau
                    tint(s, int(x + math.cos(a) * rad), int(y + math.sin(a) * rad), GREEN, (1 - ph) * .45 * edge)
            col = YELLOW if age < 2 else (WHITE if int(now * 3 + n["id"]) % 11 == 0 else GREEN)
            col = mix(BLACK, col, .35 + .65 * edge)
            s.pixel(x, y, mix(col, WHITE, .5))
            s.pixel(x - 1, y, col)
            s.pixel(x + 1, y, col)
            s.pixel(x, y - 1, col)
            s.pixel(x, y + 1, col)
            cx, cy = x + 3, y >> 1
            rect = (cx, cy, max(len(n['label']), len(n['city'])), 2)
            visible = rect[0]+rect[2] < self.w-2 and 2 < rect[1] < self.h-5
            if (visible and len(labels) < 4 and not any(overlaps(rect, r, 1) for r in labels)
                    and ((age < 2 and n in self.nodes[-2:]) or (z[k] < -0.85 and n["id"] % 3 == 0))):
                s.text(cx, cy, n["label"], YELLOW if age < 3 else GREY)
                if age < 3:
                    s.text(cx, cy + 1, n["city"], CYAN)
                labels.append(rect)

    def underlay(self, s):
        """Text over the globe keeps a darkened copy of the surface as cell background."""
        for y in range(self.gy0 >> 1, min(self.h, (self.gy1 >> 1) + 1)):
            rc, rb, top, bot = s.ch[y], s.bg[y], s.pt[y], s.pb[y]
            for x in range(self.gx0, self.gx1):
                if rc[x] != " " and rb[x] is None:
                    p = top[x] or bot[x]
                    if p is not None:
                        rb[x] = (p[0] * 2 // 5, p[1] * 2 // 5, p[2] * 2 // 5)

    # ------------------------------------------------------------------ side panels
    def frame(self, s, rect, title, col):
        x, y, w, h = rect
        s.box(x, y, w, h, mix(col, BLACK, .45), title=title, title_color=col)
        s.put(x + w - 3, y, "■", col)

    def draw_side(self, s, now):
        if not self.side:
            return
        # Node list: newest captures first, abstract round-trip times.
        x, y, w, h = self.p_nodes
        self.frame(s, self.p_nodes, "NODE LIST", CYAN)
        iw = w - 4
        rows = h - 3
        if rows > 0:
            wide = iw >= 34
            head = ("ID   DEVICE        LOCATION" if wide else "ID   DEVICE").ljust(iw - 4) + " RTT"
            s.text(x + 2, y + 1, head[:iw], DIM_CYAN)
            for j, n in enumerate(reversed(self.nodes[-rows:])):
                age = now - n["born"]
                rtt = n["rtt"] + int(6 * math.sin(now * 1.7 + n["id"]))
                if n["hub"]:
                    rtt = 1
                if wide:
                    body = "%03d  %-13.13s %-*.*s" % (n["id"], n["label"], iw - 28, iw - 28, n["city"])
                else:
                    body = "%03d  %-*.*s" % (n["id"], iw - 10, iw - 10, n["label"])
                body = body.ljust(iw - 4)[:iw - 4] + "%3dms" % max(1, rtt)
                col = PINK if n["hub"] else YELLOW if age < 1.5 else GREEN if age < 6 else GREY
                s.text(x + 2, y + 2 + j, body[:iw], col)
            if self.complete_until is None and int(now * 2) % 2:
                s.put(x + 1, y + 2, ">", WHITE)
        # Mini world map with the hemisphere currently facing the camera.
        x, y, w, h = self.p_map
        self.frame(s, self.p_map, "WORLD MAP", PURPLE)
        mw, mph = self.map_size
        c, sn, ct, st = self.rotation
        face = math.degrees(math.atan2(-c, sn))
        for j, row in enumerate(self.map_rows):
            py = (y + 1) * 2 + j
            layer = (s.pb if py & 1 else s.pt)[py >> 1]
            layer[x + 2:x + 2 + mw] = row
        for edge in (-90, 90):
            col_x = x + 2 + int(((face + edge + 180) % 360) / 360 * mw)
            for j in range(0, mph, 2):
                s.pixel(col_x, (y + 1) * 2 + j, DIM_CYAN)
        cx_ = x + 2 + int(((face + 180) % 360) / 360 * mw)
        s.put(cx_, y + h - 2, "^", CYAN)
        for n in self.nodes:
            mx = x + 2 + min(mw - 1, int((n["lon"] + 180) / 360 * mw))
            my = (y + 1) * 2 + min(mph - 1, int((90 - n["lat"]) / 180 * mph))
            if n["hub"]:
                s.pixel(mx, my, PINK if int(now * 4) % 2 else WHITE)
            else:
                s.pixel(mx, my, YELLOW if now - n["born"] < 1.5 else GREEN)
        lab = "VIEW %+04d" % int(face)
        s.text(x + w - 2 - len(lab), y + h - 2, lab, GREY)
        # Traffic: in-flight packet history as a pixel bar chart.
        x, y, w, h = self.p_traffic
        self.frame(s, self.p_traffic, "TRAFFIC", PINK)
        if now > self.hist_next:
            self.hist_next = now + 0.2
            self.history = self.history[1:] + [len(self.packets)]
        self.rate += (len(self.packets) * 1.4 - self.rate) * 0.1
        stats = [("PKT/S", "%5d" % int(self.rate)), ("ARCS", "%5d" % len(self.links)),
                 ("SENT", "%5d" % self.sent)]
        for j, (k, v) in enumerate(stats):
            s.text(x + 2, y + 1 + j, k, GREY)
            s.text(x + w - 2 - len(v), y + 1 + j, v, WHITE if j else YELLOW)
        ch = (h - 5) * 2
        if ch > 1:
            base = (y + h - 1) * 2
            top = max(8, max(self.history))
            for i, v in enumerate(self.history):
                bh = int(v / top * ch)
                for k in range(bh):
                    s.pixel(x + 2 + i, base - 1 - k, mix(DIM_PINK, PINK, k / max(1, ch)))
                if bh:
                    s.pixel(x + 2 + i, base - bh, WHITE)
        # Regions: owned devices per continent.
        x, y, w, h = self.p_regions
        self.frame(s, self.p_regions, "REGIONS", YELLOW)
        counts = [0] * 6
        for n in self.nodes[1:]:
            counts[region_of(n["lat"], n["lon"])] += 1
        bw = w - 4 - 14
        most = max(1, max(counts))
        for j, name in enumerate(REGIONS[:max(0, h - 2)]):
            yy = y + 1 + j
            s.text(x + 2, yy, name, CYAN if j == 0 else GREY)
            f = int(bw * counts[j] / most)
            s.text(x + 12, yy, "▮" * f, mix(GREEN, PINK, counts[j] / most))
            s.text(x + 12 + f, yy, "▯" * (bw - f), DARK)
            s.text(x + w - 4, yy, "%2d" % counts[j], WHITE)

    def scanband(self, s, now):
        # Shared PostFX band reads as a cloud stripe across the globe; keep it faint.
        by = int((now * 7) % (s.h + 16)) - 8
        for k, t in ((0, .14), (-1, .07), (1, .07)):
            s.tint_row(by + k, WHITE, t)

    # ------------------------------------------------------------------ frame
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

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        self.spin = now * 0.25
        self.tilt = 0.35 + math.sin(now * 0.2) * 0.15
        self.rotation = (math.cos(self.spin), math.sin(self.spin), math.cos(self.tilt), math.sin(self.tilt))

        complete = False
        if self.complete_until is not None:
            if now > self.complete_until:
                self.reset(now)
            else:
                complete = True
        elif len(self.nodes) >= self.max_nodes:
            self.complete_until = now + 3.5
            complete = True

        if not complete and now > self.next_node:
            self.add_node(now)
            self.next_node = now + random.uniform(0.25, 0.8)

        self.draw_globe(s, now)
        live = self.draw_arcs(s, now)
        self.draw_packets(s, now, dt, [] if complete else live)
        self.draw_satellites(s, now)
        self.draw_nodes(s, now, dt)
        self.particles.step(s, dt)
        self.draw_side(s, now)
        if complete:
            self.draw_complete(s, now)

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
        self.underlay(s)
        self.ticker.draw(s, self.h - 1, now)
        self.scanband(s, now)
        if glitch or (complete and random.random() < 0.12):
            self.fx.apply(s, now, True)

    def draw_complete(self, s, now):
        remaining = self.complete_until - now
        target_x = int(self.cx + self.R * 1.5)
        target_y = int(self.cy - self.R * 0.6)
        if remaining < 2.5:
            reach = min(1.0, (2.5 - remaining) / 0.6)
            for k, node in enumerate(self.nodes[::2]):
                x, y, z = self.view(node["p"])
                if z < 0:
                    col = PINK if (k + int(now * 12)) % 2 else CYAN
                    pts = line_points(int(x), int(y * 2), target_x, target_y * 2)
                    for qx, qy in pts[:max(1, int(len(pts) * reach))]:
                        self.tint(s, qx, qy, col, .8)
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

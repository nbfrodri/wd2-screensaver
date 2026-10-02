"""NUDLE: Nudle Maps, a night-mode 3D navigation app over a recognisable San Francisco.

The bay, the peninsula, Golden Gate Park, Market Street and both bridges are baked once
into a mip-mapped RGB texture (km coordinates).  Each scene parks the camera over a
district, types a silly query, drops pins, draws a route that a little arrow drives along,
and every few scenes DedSec hijacks the map.  Scenes change with a camera flight or with
map tiles flipping over like cards.  While the camera is still, the rendered map layer is
cached, so only overlays cost time.
"""

import hashlib
import math
from pathlib import Path
import random
import time
from zipfile import BadZipFile

import numpy as np

from lib import BLACK, CYAN, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE, YELLOW, Glitch, blend, ease_out, pulse
from widgets import Particles, PostFX, Ticker

NAME = "NUDLE"

# ---------------------------------------------------------------- map geometry (km; x east, z north)
TPK = 40                                   # texels per km
MX0, MZ0, MX1, MZ1 = -4.0, -4.0, 24.0, 20.0
TW, TH = int((MX1 - MX0) * TPK), int((MZ1 - MZ0) * TPK)
NL = 6                                     # mip levels
EXAG = 1.5                                 # vertical exaggeration of bridges
BEXAG = 2.3                                # ... and of downtown towers
R2 = math.sqrt(0.5)

SF_POLY = [(1.2, -4.5), (0.9, 0.0), (0.6, 3.0), (0.35, 6.0), (0.15, 7.8), (0.05, 8.6), (0.4, 9.1), (1.2, 8.95),
           (2.0, 9.15), (2.8, 9.6), (3.15, 10.6), (3.35, 11.45), (4.2, 11.0), (5.2, 10.95), (6.2, 11.0),
           (7.2, 11.15), (7.8, 11.05), (8.0, 11.2), (8.3, 11.05), (8.6, 11.15), (9.1, 11.3), (9.7, 11.1),
           (10.2, 10.7), (10.65, 9.7), (11.0, 9.0), (11.0, 7.8), (11.35, 6.4), (11.5, 5.4), (11.35, 3.9),
           (12.6, 3.3), (13.8, 2.1), (13.0, 1.2), (11.7, 0.3), (12.2, -1.0), (13.5, -2.5), (14.5, -4.5)]
MARIN_POLY = [(-4.5, 13.6), (-1.0, 13.4), (0.8, 12.9), (2.0, 13.15), (3.25, 13.0), (3.7, 13.5), (4.3, 14.3),
              (3.9, 15.0), (3.4, 15.6), (3.6, 16.4), (4.4, 17.3), (5.2, 17.9), (5.8, 18.6), (6.6, 19.5),
              (6.2, 20.5), (-4.5, 20.5)]
EAST_POLY = [(18.0, 20.5), (18.3, 16.5), (18.6, 14.8), (18.8, 13.0), (17.6, 11.6), (17.0, 10.2), (16.2, 8.6),
             (17.2, 7.6), (19.0, 7.0), (21.5, 5.8), (23.0, 2.5), (24.5, -4.5), (24.5, 20.5)]
ESTUARY_POLY = [(16.6, 8.9), (19.0, 8.25), (21.6, 6.6), (21.75, 6.95), (19.1, 8.7), (16.8, 9.35)]
TI_POLY = [(12.0, 12.2), (13.0, 12.3), (13.3, 13.5), (12.3, 13.6)]

# (x, z, rx, rz)
PARK_ELLIPSES = [(5.9, 4.9, 0.6, 0.7), (5.25, 5.85, 0.45, 0.4), (4.7, 3.6, 0.35, 0.35), (8.4, 1.2, 0.9, 0.7),
                 (6.3, 6.6, 0.2, 0.18), (7.0, 7.3, 0.12, 0.12), (8.9, 3.5, 0.3, 0.28), (13.3, 11.3, 0.45, 0.4),
                 (7.3, 17.0, 0.9, 0.8)]
PARK_RECTS = [(0.4, 6.38, 5.35, 7.2), (5.35, 7.0, 6.95, 7.18), (0.1, 8.5, 1.5, 9.2), (7.55, 5.52, 7.82, 5.75),
              (1.6, 2.4, 3.2, 2.75), (7.3, 10.75, 7.8, 11.1), (6.2, 10.75, 7.2, 10.98)]
PRESIDIO_POLY = [(2.9, 9.5), (3.2, 10.6), (3.35, 11.45), (4.2, 11.0), (5.6, 10.95), (5.9, 10.6), (5.9, 9.0),
                 (4.8, 8.9), (3.6, 8.95)]
HILLS = [(5.9, 4.9, 0.28, 0.6), (5.25, 5.85, 0.26, 0.4), (4.7, 3.6, 0.28, 0.45), (9.2, 9.5, 0.11, 0.35),
         (8.7, 10.4, 0.1, 0.3), (9.55, 10.6, 0.08, 0.22), (7.3, 9.4, 0.1, 0.6), (8.9, 3.5, 0.13, 0.35),
         (10.1, 5.6, 0.09, 0.4), (8.4, 1.2, 0.15, 0.6), (1.5, 15.0, 0.35, 2.0), (4.5, 16.5, 0.3, 1.2),
         (7.3, 17.0, 0.22, 0.6), (13.3, 11.3, 0.1, 0.3), (24.0, 13.0, 0.4, 2.5), (-2.0, 17.5, 0.4, 2.0)]

HIGHWAYS = [
    [(3.25, 13.0), (3.5, 14.2), (3.9, 15.0), (3.3, 16.2), (3.6, 17.5), (4.0, 20.5)],
    [(3.35, 11.2), (3.9, 10.85), (5.0, 10.75), (5.9, 10.55), (6.1, 10.4)],
    [(10.95, 7.3), (10.3, 5.5), (9.7, 4.2), (8.6, 2.8), (6.6, 1.2), (5.3, -0.6), (4.5, -4.5)],
    [(8.0, 7.15), (8.9, 6.9), (9.25, 6.0), (9.6, 4.6), (9.9, 3.3), (10.5, 1.6), (11.2, 0.2), (11.6, -1.5),
     (12.3, -4.5)],
    [(9.25, 6.0), (9.9, 7.1), (10.55, 8.3), (11.0, 8.95)],
    [(13.25, 11.15), (13.45, 11.35)],
    [(18.85, 12.95), (19.5, 13.1), (19.3, 15.5), (18.9, 20.5)],
    [(19.5, 13.1), (19.8, 11.0), (19.5, 9.0), (21.5, 7.2), (24.5, 4.5)],
    [(19.5, 13.1), (21.5, 13.0), (24.5, 12.0)],
]
MARKET = [(10.65, 9.68), (6.95, 6.05), (6.5, 5.6), (6.1, 5.0)]
PRIMARIES = [
    MARKET,
    [(8.6, 11.05), (9.1, 11.18), (9.7, 11.0), (10.2, 10.62), (10.62, 9.7), (10.95, 9.0), (10.95, 7.8),
     (11.25, 6.4)],
    [(0.3, 8.6), (9.55, 8.6)],                         # Geary
    [(8.0, 7.15), (8.0, 11.05)],                       # Van Ness
    [(6.1, 10.4), (8.5, 10.4)],                        # Lombard
    [(8.5, 7.5), (8.5, 3.4), (7.6, 1.5), (6.5, -1.0)],  # Mission
    [(6.8, 4.55), (11.3, 4.55)],                       # Cesar Chavez
    [(0.45, 6.35), (5.4, 6.35)],                       # Lincoln
    [(1.0, -1.0), (0.75, 3.0), (0.5, 6.0), (0.32, 7.8)],  # Great Highway
    [(6.5, 6.6), (6.5, 10.5)],                         # Divisadero
    [(9.75, 9.75), (8.9, 10.95)],                      # Columbus
    [(10.7, 8.1), (10.75, 5.0), (10.9, 2.5), (11.3, 0.3)],  # 3rd St
    [(3.3, 11.0), (2.95, 10.2), (2.5, 9.3), (2.5, 7.2), (2.5, 0.0), (3.2, -0.3), (4.2, -1.5), (5.0, -4.5)],
]
PARK_ROADS = [[(0.5, 6.85), (2.0, 6.95), (3.5, 6.8), (5.3, 6.9)], [(1.2, 6.45), (1.6, 7.1)],
              [(3.9, 6.45), (4.3, 7.15)]]
GG_S, GG_N = (3.35, 11.42), (3.25, 13.0)
BB_W, BB_YBI, BB_E = (11.0, 8.95), (13.25, 11.15), (18.85, 12.95)

LANDMARKS = [  # x, z, half size, height km, taper, rotation, kind
    (10.3, 9.17, 0.03, 0.326, 0.82, 0.785, "salesforce"),
    (9.77, 9.78, 0.032, 0.26, 0.0, 0.0, "pyramid"),
    (9.85, 9.48, 0.035, 0.237, 1.0, 0.0, "tower"),
    (10.38, 9.27, 0.026, 0.245, 0.9, 0.785, "tower"),
    (9.53, 10.62, 0.012, 0.09, 1.0, 0.0, "coit"),
    (10.12, 9.0, 0.03, 0.2, 1.0, 0.785, "tower"),
]
DOWNTOWN = (10.05, 9.3)

DISTRICTS = [("FINANCIAL DISTRICT", 10.05, 9.45), ("CHINATOWN", 9.55, 9.95), ("NORTH BEACH", 9.3, 10.6),
             ("NOB HILL", 9.0, 9.4), ("RUSSIAN HILL", 8.55, 10.3), ("MARINA", 6.9, 10.55),
             ("PRESIDIO", 4.5, 9.9), ("PACIFIC HEIGHTS", 7.2, 9.35), ("RICHMOND", 2.2, 8.1),
             ("SUNSET", 2.2, 4.6), ("HAIGHT", 6.0, 6.75), ("CASTRO", 6.7, 5.6), ("MISSION", 8.15, 5.0),
             ("SOMA", 9.9, 7.9), ("TENDERLOIN", 8.85, 8.7), ("DOGPATCH", 11.05, 5.3), ("BAYVIEW", 10.6, 2.5),
             ("TWIN PEAKS", 5.9, 4.9), ("BERNAL HTS", 8.9, 3.5), ("POTRERO HILL", 10.1, 5.75),
             ("MISSION BAY", 10.6, 6.9), ("JAPANTOWN", 7.4, 8.8), ("GOLDEN GATE PARK", 2.9, 6.8),
             ("TREASURE ISLAND", 12.6, 12.9), ("OAKLAND", 20.5, 11.6), ("SAUSALITO", 3.3, 16.3),
             ("ALCATRAZ", 8.0, 13.25), ("ANGEL ISLAND", 7.3, 17.0), ("GOLDEN GATE BRIDGE", 3.3, 12.25),
             ("BAY BRIDGE", 15.6, 12.0), ("EXCELSIOR", 7.6, 1.8), ("NOE VALLEY", 7.0, 4.9)]
WATER_LABELS = [("SAN FRANCISCO BAY", 13.8, 15.8), ("PACIFIC OCEAN", -2.2, 6.0), ("SAN FRANCISCO BAY", 14.5, 5.0)]

# scene: name, target x, z, distance, pitch, yaw, grid snap multiplier
SCENES = [
    ("FINANCIAL DISTRICT", 9.9, 9.55, 1.55, 0.43, 0.62, 1),
    ("GOLDEN GATE", 4.9, 11.25, 2.7, 0.32, -1.22, 1),
    ("MISSION", 8.1, 5.4, 2.7, 0.60, 0.22, 1),
    ("GOLDEN GATE PARK", 4.3, 7.4, 4.4, 0.47, -1.42, 1),
    ("SOMA", 10.05, 8.35, 2.2, 0.47, 0.85, 1),
    ("SAN FRANCISCO", 7.2, 7.4, 13.0, 0.88, 0.10, 4),
]

# ---------------------------------------------------------------- jokes
QUERIES = [
    ("best taco near me", ["TACO LOCO", "EL GUAPO", "TACOS 24/7", "SALSA SAM'S", "BURRITO BOB"]),
    ("how to hide from ctOS", ["SAFE HOUSE", "HACKERSPACE", "TINFOIL HATS", "NO-CAM ALLEY"]),
    ("cat cafe open now", ["WHISKERS", "PURR BREW", "MEOW & CO", "LITTER LOUNGE"]),
    ("parking under $40", ["NOPE", "STILL NOPE", "MYTHICAL SPOT", "TOW ZONE"]),
    ("vegan donuts", ["HOLE FOODS", "DOUGH-NOT", "GLAZE ME", "SPRINKLE LAB"]),
    ("drone charging station", ["ZAP SPOT", "BATTERY BAR", "VOLT CAFE", "PROP SHOP"]),
    ("karaoke tonight", ["MIC DROP", "OFF KEY", "SING SING", "ECHO ROOM"]),
    ("retro arcade", ["8-BIT BAR", "INSERT COIN", "HIGH SCORE", "PIXEL PALACE"]),
    ("boba with no line", ["TAPIOCA TOM", "BOBA FETT-UCCINE", "PEARL JAM", "BUBBLE HUB"]),
    ("where did i park", ["HERE?", "MAYBE HERE", "DEFINITELY NOT", "IMPOUND LOT"]),
    ("is blume watching me", ["YES", "ALSO YES", "BLUME HQ", "CAMERA #4471"]),
    ("free wifi no tracking", ["LOL", "DEDSEC NODE", "OPEN NET", "LIBRARY"]),
    ("emotional support burrito", ["BURRITO HUG", "FOIL & FEELS", "GUAC THERAPY", "EXTRA CHEESE"]),
    ("why is my car in a tree", ["HACKED, SORRY", "TOW TREE", "BRANCH OFFICE", "ARBORIST"]),
    ("dog that looks like me", ["PUG PARLOR", "MIRROR MUTT", "DOPPELDOGGER", "SHELTER"]),
    ("sunset spot no tourists", ["TWIN PEAKS", "LOL NO", "ROOFTOP 9", "PIER 7"]),
    ("24h laundromat w/ arcade", ["SPIN CYCLE", "WASH & BASH", "SUDS'N'SCORE", "LINT LAB"]),
    ("sourdough emergency", ["CRUST FUND", "YEAST WING", "LOAF ME", "BREAD PITT"]),
    ("fog-free picnic spot", ["KARL'S DAY OFF", "MISSION SUN", "DOLORES PARK", "INDOORS"]),
    ("hoodie store open late", ["HOOD RICH", "ZIP CITY", "THREAD COUNT", "DEDSEC MERCH"]),
]
NS_NAMES = ["LAGUNA ST", "GOUGH ST", "FRANKLIN ST", "POLK ST", "LARKIN ST", "HYDE ST", "LEAVENWORTH ST",
            "JONES ST", "TAYLOR ST", "MASON ST", "POWELL ST", "STOCKTON ST", "GRANT AVE", "KEARNY ST",
            "MONTGOMERY ST", "SANSOME ST", "BATTERY ST", "FILLMORE ST", "STEINER ST", "MASONIC AVE",
            "STANYAN ST", "ARGUELLO BLVD", "SUNSET BLVD", "GUERRERO ST", "VALENCIA ST", "FOLSOM ST",
            "POTRERO AVE", "CHURCH ST", "DOLORES ST", "CASTRO ST"]
EW_NAMES = ["CALIFORNIA ST", "SACRAMENTO ST", "CLAY ST", "WASHINGTON ST", "PACIFIC AVE", "BROADWAY",
            "GREEN ST", "UNION ST", "FILBERT ST", "BAY ST", "NORTH POINT ST", "PINE ST", "BUSH ST", "SUTTER ST",
            "POST ST", "ELLIS ST", "EDDY ST", "TURK ST", "FELL ST", "OAK ST", "HAIGHT ST", "16TH ST", "18TH ST",
            "20TH ST", "24TH ST", "JUDAH ST", "IRVING ST", "NORIEGA ST", "TARAVAL ST", "CLEMENT ST"]
SOMA_A = ["MARKET ST", "MISSION ST", "HOWARD ST", "FOLSOM ST", "HARRISON ST", "BRYANT ST", "BRANNAN ST",
          "TOWNSEND ST", "KING ST"]
SOMA_B = ["11TH ST", "10TH ST", "9TH ST", "8TH ST", "7TH ST", "6TH ST", "5TH ST", "4TH ST", "3RD ST", "2ND ST",
          "1ST ST", "FREMONT ST", "MAIN ST", "SPEAR ST"]
NEWS = ["#NUDLE Maps now 3% less creepy", "Traffic heavy on HWY 101, as always", "#ctOS sync complete",
        "New: Street View for your fridge", "Reroute: Lombard St still curvy",
        "Nudle CEO: 'we only know where you are'", "#BLUME partners with Nudle for 'safety'",
        "Bay Bridge: 14 min delay", "Report a pothole, win a pothole", "Karl the Fog: 87% chance, as usual",
        "Golden Gate Bridge still orange, experts confirm"]
ETA_NOTES = ["2 CAMERAS ON ROUTE", "TOLL: YOUR DATA", "SCENIC (MORE ADS)", "AVOIDS 1 POTHOLE",
             "BLUME-SPONSORED ROUTE", "FASTEST-ISH", "VIA 4 COFFEE SHOPS", "0 PARKING EXPECTED"]

SKULL_BIG = [
    "......XXXXXXXXXX......",
    "....XXXXXXXXXXXXXX....",
    "...XXXXXXXXXXXXXXXX...",
    "..XXXXXXXXXXXXXXXXXX..",
    ".XXXXXXXXXXXXXXXXXXXX.",
    ".XXXX.X...XX...X.XXXX.",
    ".XXXXX.X.XXXX.X.XXXXX.",
    ".XXXX.X...XX...X.XXXX.",
    ".XXXXXXXXX..XXXXXXXXX.",
    "..XXXXXXXX..XXXXXXXX..",
    "...XXXXXX....XXXXXX...",
    "....XXXXXXXXXXXXXX....",
    ".....X.X.X.X.X.X.X....",
    ".....XXXXXXXXXXXXX....",
    "......XXXXXXXXXXX.....",
]
SKULL_PX = ["..XXXXX..", ".XXXXXXX.", "XXXXXXXXX", "XX..X..XX", "XX..X..XX", "XXXXXXXXX",
            ".XXX.XXX.", "..X.X.X..", "..XXXXX.."]

# ---------------------------------------------------------------- palette (night UI)
PANEL = (16, 20, 32)
PANEL_EDGE = (58, 74, 104)
ROUTE = (66, 150, 255)
ROUTE_CORE = (150, 205, 255)
NAV_GREEN = (0, 112, 92)
FOG = (30, 22, 50)
GLOW = (78, 38, 92)
SKY_TOP = (3, 4, 14)
TRAFFIC = ((60, 220, 110), (255, 196, 40), (255, 50, 60))


# ---------------------------------------------------------------- texture construction
def _poly_mask(pts):
    m = np.zeros((TH, TW), bool)
    P = [((x - MX0) * TPK, (z - MZ0) * TPK) for x, z in pts]
    n = len(P)
    zs = [p[1] for p in P]
    for r in range(max(0, int(min(zs))), min(TH, int(max(zs)) + 1)):
        zc = r + 0.5
        xs = []
        for i in range(n):
            ax, az = P[i]
            bx, bz = P[(i + 1) % n]
            if (az <= zc < bz) or (bz <= zc < az):
                xs.append(ax + (zc - az) / (bz - az) * (bx - ax))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            a, b = max(0, int(a + 0.5)), min(TW, int(b + 0.5))
            if b > a:
                m[r, a:b] = True
    return m


def _bbox(x0, z0, x1, z1):
    i0, i1 = max(0, int((x0 - MX0) * TPK)), min(TW, int((x1 - MX0) * TPK) + 2)
    j0, j1 = max(0, int((z0 - MZ0) * TPK)), min(TH, int((z1 - MZ0) * TPK) + 2)
    return i0, i1, j0, j1


def _ellipse(m, xs, zs, cx, cz, rx, rz):
    i0, i1, j0, j1 = _bbox(cx - rx, cz - rz, cx + rx, cz + rz)
    if i1 > i0 and j1 > j0:
        X, Z = xs[None, i0:i1], zs[j0:j1, None]
        m[j0:j1, i0:i1] |= ((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2 <= 1


def _blur(a, r):
    k = 2 * r + 1
    p = np.pad(a, ((r + 1, r), (0, 0)), mode="edge")
    c = np.cumsum(p, 0, dtype=np.float32)
    a = (c[k:] - c[:-k]) / k
    p = np.pad(a, ((0, 0), (r + 1, r)), mode="edge")
    c = np.cumsum(p, 1, dtype=np.float32)
    return (c[:, k:] - c[:, :-k]) / k


def _polyline_dist(D, xs, zs, pts, rad):
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        i0, i1, j0, j1 = _bbox(min(ax, bx) - rad, min(az, bz) - rad, max(ax, bx) + rad, max(az, bz) + rad)
        if i1 <= i0 or j1 <= j0:
            continue
        X, Z = xs[None, i0:i1], zs[j0:j1, None]
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz or 1e-9
        u = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
        d = np.hypot(X - ax - u * dx, Z - az - u * dz)
        np.minimum(D[j0:j1, i0:i1], d, out=D[j0:j1, i0:i1])


def _paint(rgb, mask, col, alpha=1.0):
    c = np.asarray(col, np.float32)
    if np.isscalar(alpha):
        rgb[mask] = rgb[mask] * (1 - alpha) + c * alpha
    else:
        a = alpha[mask][:, None]
        rgb[mask] = rgb[mask] * (1 - a) + c * a


def _soma(X, Z):
    a = (X - Z) * R2
    b = (X + Z) * R2
    return (a > 0.66) & (a < 1.95) & (b > 10.9) & (b < 15.2)


def build_world():
    xs = (MX0 + (np.arange(TW, dtype=np.float32) + 0.5) / TPK)
    zs = (MZ0 + (np.arange(TH, dtype=np.float32) + 0.5) / TPK)[:, None]
    X = np.broadcast_to(xs[None, :], (TH, TW))
    Z = np.broadcast_to(zs, (TH, TW))
    xs = xs
    zs1 = zs[:, 0]
    land = _poly_mask(SF_POLY) | _poly_mask(MARIN_POLY) | _poly_mask(EAST_POLY) | _poly_mask(TI_POLY)
    _ellipse(land, xs, zs1, 13.3, 11.3, 0.45, 0.4)
    _ellipse(land, xs, zs1, 7.3, 17.0, 0.9, 0.8)
    _ellipse(land, xs, zs1, 8.0, 13.22, 0.22, 0.1)
    # Embarcadero piers poke into the bay
    shore = [(8.9, 11.22), (9.7, 11.1), (10.2, 10.7), (10.65, 9.7), (11.0, 9.0), (11.0, 7.9)]
    piers = np.zeros((TH, TW), bool)
    for (ax, az), (bx, bz) in zip(shore, shore[1:]):
        L = math.hypot(bx - ax, bz - az)
        nx, nz = (bz - az) / L, -(bx - ax) / L
        for k in range(int(L / 0.17)):
            u = (k + 0.5) * 0.17 / L
            px, pz = ax + (bx - ax) * u, az + (bz - az) * u
            tx, tz = (bx - ax) / L * 0.025, (bz - az) / L * 0.025
            ln = 0.3 if k % 3 else 0.22
            piers |= _poly_mask([(px - tx, pz - tz), (px + tx, pz + tz), (px + tx + nx * ln, pz + tz + nz * ln),
                                 (px - tx + nx * ln, pz - tz + nz * ln)])
    land |= piers
    lake = np.zeros((TH, TW), bool)
    _ellipse(lake, xs, zs1, 2.0, 1.3, 0.5, 0.75)
    land &= ~(lake | _poly_mask(ESTUARY_POLY))
    water = ~land
    # parks
    park = np.zeros((TH, TW), bool)
    for cx, cz, rx, rz in PARK_ELLIPSES:
        _ellipse(park, xs, zs1, cx, cz, rx, rz)
    for x0, z0, x1, z1 in PARK_RECTS:
        i0, i1, j0, j1 = _bbox(x0, z0, x1, z1)
        park[j0:j1 - 1, i0:i1 - 1] = True
    park |= _poly_mask(PRESIDIO_POLY)
    marin = _poly_mask(MARIN_POLY)
    sausalito = np.zeros((TH, TW), bool)
    _ellipse(sausalito, xs, zs1, 3.2, 16.2, 0.45, 0.6)
    park |= marin & ~sausalito
    park |= (X > 22.3) & (Z > 9.5)
    park &= land & ~piers
    # elevation -> hillshade
    elev = np.zeros((TH, TW), np.float32)
    for cx, cz, hgt, sg in HILLS:
        i0, i1, j0, j1 = _bbox(cx - 3 * sg, cz - 3 * sg, cx + 3 * sg, cz + 3 * sg)
        Xs, Zs = xs[None, i0:i1], zs1[j0:j1, None]
        elev[j0:j1, i0:i1] += hgt * np.exp(-((Xs - cx) ** 2 + (Zs - cz) ** 2) / (2 * sg * sg))
    gz, gx = np.gradient(elev * TPK)
    shade = np.clip(-(gx * -0.6 + gz * 0.8) * 1.6, -0.45, 0.45)
    # urban texture
    ix = np.arange(TW)[None, :]
    iz = np.arange(TH)[:, None]
    soma = _soma(X, Z) & land
    a = (X - Z) * R2 - 0.66
    b = (X + Z) * R2
    minor_ax = (ix % 5 == 0) | (iz % 9 == 0)
    fa, fb = (a / 0.15) % 1.0, (b / 0.15) % 1.0
    minor_so = (fa < 0.17) | (fb < 0.17)
    minor = np.where(soma, minor_so, minor_ax)
    cell_ax = (ix // 5) * 7919 + (iz // 9) * 104729
    cell_so = np.floor(a / 0.15).astype(np.int64) * 7919 + np.floor(b / 0.15).astype(np.int64) * 104729
    cell = np.where(soma, cell_so, cell_ax)
    hsh = ((cell * 2654435761) >> 7) % 997 / 997.0
    rgb = np.empty((TH, TW, 3), np.float32)
    rgb[:] = (19, 23, 37)
    rgb += ((hsh - 0.5) * 7)[..., None]
    dens = np.exp(-((X - DOWNTOWN[0]) ** 2 + (Z - DOWNTOWN[1]) ** 2) / 1.3) + \
        0.6 * np.exp(-((X - 19.6) ** 2 + (Z - 11.0) ** 2) / 1.0)
    rgb += dens[..., None] * np.array((8, 10, 18), np.float32)
    _paint(rgb, minor & land, (30, 35, 54), 0.9)
    # arterial grid (every 4 x 2 blocks; SoMa every 2 x 2)
    da_ax = np.minimum((ix % 20), 20 - (ix % 20)) / TPK
    db_ax = np.minimum((iz % 18), 18 - (iz % 18)) / TPK
    ga, gb = (a / 0.3) % 1.0, (b / 0.3) % 1.0
    da_so = np.minimum(ga, 1 - ga) * 0.3
    db_so = np.minimum(gb, 1 - gb) * 0.3
    dart = np.where(soma, np.minimum(da_so, db_so), np.minimum(da_ax, db_ax))
    art = land & (dart < 0.02)
    _paint(rgb, land & (dart < 0.05), (36, 44, 66), np.clip(1 - dart / 0.05, 0, 1) * 0.6)
    _paint(rgb, art, (56, 70, 102), 1.0)
    # parks (no streets) with clumped trees
    tree = ((((ix // 2) * 37 + (iz // 2) * 91) * 2654435761) >> 9) % 7
    pcol = np.where(tree[..., None] < 2, np.array((12, 40, 27), np.float32),
                    np.where(tree[..., None] == 6, np.array((22, 60, 38), np.float32),
                             np.array((15, 50, 32), np.float32)))
    rgb[park] = pcol[park]
    edge = park & (_blur(park.astype(np.float32), 1) < 0.99)
    _paint(rgb, edge, (30, 74, 48), 0.8)
    # hillshade on land
    rgb[land] *= (1 + shade[land])[:, None]
    # roads with glow
    D = np.full((TH, TW), 9.0, np.float32)
    for pl in PARK_ROADS:
        _polyline_dist(D, xs, zs1, pl, 0.05)
    _paint(rgb, land & (D < 0.018), (40, 78, 58), 1.0)
    D[:] = 9.0
    for pl in PRIMARIES:
        _polyline_dist(D, xs, zs1, pl, 0.12)
    _paint(rgb, land & (D < 0.1), (78, 66, 52), np.clip(1 - D / 0.1, 0, 1) ** 2 * 0.55)
    _paint(rgb, land & (D < 0.022), (196, 172, 118), 1.0)
    Dm = np.full((TH, TW), 9.0, np.float32)
    _polyline_dist(Dm, xs, zs1, MARKET, 0.12)
    _paint(rgb, land & (Dm < 0.028), (236, 206, 140), 1.0)
    D[:] = 9.0
    for pl in HIGHWAYS:
        _polyline_dist(D, xs, zs1, pl, 0.22)
    _paint(rgb, land & (D < 0.2), (150, 72, 18), np.clip(1 - D / 0.2, 0, 1) ** 2 * 0.7)
    _paint(rgb, land & (D < 0.036), (255, 168, 56), 1.0)
    _paint(rgb, land & (D < 0.012), (255, 226, 160), 1.0)
    # water: deep -> shallow, glowing coastline
    lf = land.astype(np.float32)
    near = _blur(_blur(lf, 3), 3)
    far = _blur(_blur(lf, 24), 24)
    wcol = np.array((4, 12, 32), np.float32) * (1 - far[..., None] * 1.5).clip(0, 1) + \
        np.array((9, 30, 62), np.float32) * (far[..., None] * 1.5).clip(0, 1)
    wcol += np.array((0, 70, 100), np.float32) * (near[..., None] * 1.8).clip(0, 1) ** 1.5
    rgb[water] = wcol[water]
    coast = land & (_blur(lf, 1) < 0.99)
    _paint(rgb, coast, (60, 150, 170), 0.85)
    # bridge decks (3D superstructure is drawn per view)
    D[:] = 9.0
    _polyline_dist(D, xs, zs1, [GG_S, GG_N], 0.15)
    _paint(rgb, water & (D < 0.08), (90, 30, 30), np.clip(1 - D / 0.08, 0, 1) ** 2 * 0.35)
    _paint(rgb, D < 0.03, (238, 82, 46), 1.0)
    D[:] = 9.0
    _polyline_dist(D, xs, zs1, [BB_W, BB_YBI, (13.45, 11.35), BB_E], 0.15)
    _paint(rgb, water & (D < 0.08), (50, 60, 100), np.clip(1 - D / 0.08, 0, 1) ** 2 * 0.35)
    _paint(rgb, D < 0.03, (200, 210, 235), 1.0)
    np.clip(rgb, 0, 255, out=rgb)
    mips = [rgb.astype(np.uint8)]
    cur = rgb
    for _ in range(1, NL):
        cur = (cur[0::2, 0::2] + cur[1::2, 0::2] + cur[0::2, 1::2] + cur[1::2, 1::2]) * 0.25
        mips.append(cur.astype(np.uint8))
    return {"mips": mips, "land": land, "water": water, "park": park, "soma": soma}


def make_buildings(world):
    """Downtown footprints: (corners[4][2], height km, taper, kind)."""
    rng = random.Random(11)
    out = []
    land, park = world["land"], world["park"]

    def ok(x, z):
        i, j = int((x - MX0) * TPK), int((z - MZ0) * TPK)
        return 0 <= i < TW and 0 <= j < TH and land[j, i] and not park[j, i]

    def add(quad, h, taper=1.0, kind="b"):
        if all(ok(x, z) for x, z in quad):
            out.append((quad, h, taper, kind))

    lm = [(x, z) for x, z, *_ in LANDMARKS]
    # north-of-Market grid blocks (5 x 9 texels)
    for bi in range(int((9.0 - MX0) * TPK) // 5, int((10.9 - MX0) * TPK) // 5):
        for bj in range(int((8.4 - MZ0) * TPK) // 9, int((10.9 - MZ0) * TPK) // 9):
            x0 = MX0 + (bi * 5 + 1.5) / TPK
            x1 = MX0 + (bi * 5 + 4.5) / TPK
            z0 = MZ0 + (bj * 9 + 1.3) / TPK
            z1 = MZ0 + (bj * 9 + 8.7) / TPK
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            if (cx - cz) * R2 > 0.6:
                continue
            d = math.hypot(cx - DOWNTOWN[0], cz - DOWNTOWN[1])
            dens = math.exp(-(d / 0.55) ** 2)
            zm = (z0 + z1) / 2
            parts = ([(zm - 0.05, zm + 0.05)] if rng.random() < 0.5 else
                     [(z0 + 0.01, zm - 0.02), (zm + 0.02, z1 - 0.01)])
            for za, zb in parts:
                h = 0.02 + 0.2 * dens * rng.uniform(0.35, 1.0)
                if rng.random() < 0.15 * dens:
                    h *= 1.4
                if h < 0.06 or any(math.hypot(lx - cx, lz - (za + zb) / 2) < 0.08 for lx, lz in lm):
                    continue
                add([(x0, za), (x1, za), (x1, zb), (x0, zb)], h)
    # SoMa blocks, rotated with Market St
    for ai in range(0, 6):
        for bj in range(int(12.4 / 0.15), int(14.6 / 0.15)):
            a0, a1 = 0.66 + ai * 0.15 + 0.045, 0.66 + (ai + 1) * 0.15 - 0.02
            b0, b1 = bj * 0.15 + 0.045, (bj + 1) * 0.15 - 0.02
            q = [((aa + bb) * R2, (bb - aa) * R2) for aa, bb in ((a1, b0), (a1, b1), (a0, b1), (a0, b0))]
            cx, cz = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
            d = math.hypot(cx - 10.25, cz - 9.1)
            dens = math.exp(-(d / 0.6) ** 2)
            h = 0.02 + 0.2 * dens * rng.uniform(0.3, 1.0)
            if h < 0.06 or any(math.hypot(lx - cx, lz - cz) < 0.08 for lx, lz in lm):
                continue
            add(q, h)
    for x, z, hs, h, taper, rot, kind in LANDMARKS:
        c, s_ = math.cos(rot), math.sin(rot)
        q = [(x + (u * c - v * s_) * hs, z + (u * s_ + v * c) * hs) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        out.append((q, h, taper, kind))
    return out


_WORLD = {}
_LUT = []


def map_signature():
    """Invalidate the baked map when its geometry or texture builder changes."""
    source = Path(__file__).read_bytes().split(b"\n_WORLD = {}", 1)[0]
    return hashlib.sha256(source).hexdigest()


def load_baked_world():
    """Load only deterministic artwork, never machine or live user data."""
    try:
        path = Path(__file__).parent / "assets" / "nudle_map.npz"
        with np.load(path, allow_pickle=False) as data:
            if str(data["signature"].item()) != map_signature():
                return None
            mips = [data[f"mip_{level}"] for level in range(NL)]
            masks = {key: data[key] for key in ("land", "water", "park", "soma")}
            if any(m.dtype != np.uint8 or m.shape != (TH // 2**i, TW // 2**i, 3)
                   for i, m in enumerate(mips)):
                return None
            if any(m.dtype != np.bool_ or m.shape != (TH, TW) for m in masks.values()):
                return None
            return {"mips": mips, **masks}
    except (OSError, ValueError, KeyError, EOFError, BadZipFile):
        return None


def world():
    if not _WORLD:
        baked = load_baked_world()
        _WORLD.update(baked if baked is not None else build_world())
        _WORLD["buildings"] = make_buildings(_WORLD)
    if not _LUT:
        _LUT.extend((r * 8 + (r >> 2), g * 8 + (g >> 2), b * 8 + (b >> 2))
                    for r in range(32) for g in range(32) for b in range(32))
    return _WORLD


def to_rows(rgb):
    """uint8 (ph, w, 3) -> list of rows of quantised colour tuples (5 bits per channel)."""
    c = rgb.astype(np.int32) >> 3
    code = (c[..., 0] << 10) | (c[..., 1] << 5) | c[..., 2]
    g = _LUT.__getitem__
    return [list(map(g, row)) for row in code.tolist()]


def pline(s, x0, y0, x1, y1, col):
    """Pixel line clipped to the canvas first (Liang-Barsky), so off-screen spans cost nothing."""
    w, h = s.w - 1, s.ph - 1
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if p == 0:
            if q < 0:
                return
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return
                if r < t1:
                    t1 = r
    ax, ay = int(x0 + dx * t0 + 0.5), int(y0 + dy * t0 + 0.5)
    bx, by = int(x0 + dx * t1 + 0.5), int(y0 + dy * t1 + 0.5)
    ax, bx = min(max(ax, 0), w), min(max(bx, 0), w)
    ay, by = min(max(ay, 0), h), min(max(by, 0), h)
    pt, pb = s.pt, s.pb
    n = max(abs(bx - ax), abs(by - ay))
    if n == 0:
        (pb if ay & 1 else pt)[ay >> 1][ax] = col
        return
    sx, sy = (bx - ax) / n, (by - ay) / n
    x, y = ax + 0.5, ay + 0.5
    for _ in range(n + 1):
        iy = int(y)
        (pb if iy & 1 else pt)[iy >> 1][int(x)] = col
        x += sx
        y += sy


def _smooth(v):
    v = max(0.0, min(1.0, v))
    return v * v * v * (v * (v * 6 - 15) + 10)


class Grid:
    """Street grid used for snapping pins and routing (one axis-aligned, one rotated with Market)."""

    def __init__(self, ox, oz, e1, e2, s1, s2, names1, names2):
        self.o, self.e1, self.e2, self.s1, self.s2 = (ox, oz), e1, e2, s1, s2
        self.names1, self.names2 = names1, names2

    def to_grid(self, x, z):
        dx, dz = x - self.o[0], z - self.o[1]
        return (dx * self.e1[0] + dz * self.e1[1]) / self.s1, (dx * self.e2[0] + dz * self.e2[1]) / self.s2

    def to_world(self, i, j):
        return (self.o[0] + self.e1[0] * i * self.s1 + self.e2[0] * j * self.s2,
                self.o[1] + self.e1[1] * i * self.s1 + self.e2[1] * j * self.s2)

    def name(self, axis, k):
        names = self.names1 if axis == 0 else self.names2
        return names[int(k) % len(names)]


AXIS_GRID = Grid(MX0, MZ0, (1, 0), (0, 1), 0.5, 0.45, NS_NAMES, EW_NAMES)
SOMA_GRID = Grid(0.66 * R2, -0.66 * R2, (R2, -R2), (R2, R2), 0.3, 0.3, SOMA_A, SOMA_B)


class Pin:
    def __init__(self, wx, wz, label, col, now, kind="poi", delay=0.0):
        self.wx, self.wz, self.label, self.col = wx, wz, label, col
        self.born = now + delay
        self.kind = kind
        self.rating = "%.1f" % random.uniform(2.1, 5.0)
        self.dying = None
        self.popped = False


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = 2 * h
        self.W = world()
        self.buildings = self.W["buildings"]
        self.prep_buildings()
        self.last = time.time()
        self.glitch = Glitch(0.003)
        self.fx = PostFX(band_speed=5)
        self.particles = Particles()
        self.ticker = Ticker("NUDLE", NEWS, color=CYAN)
        self.top = 3
        self.F = self.ph * 1.1
        self.cxp = w / 2
        self.cyp = self.ph * 0.54
        self.A = ((np.arange(w) - self.cxp + 0.5) / self.F).astype(np.float32)
        self.B = (-(np.arange(self.ph) - self.cyp + 0.5) / self.F).astype(np.float32)
        rng = random.Random(5)
        self.stars = [(rng.uniform(0, 2 * math.pi), rng.uniform(0.02, 0.5), rng.random()) for _ in range(90)]
        self.layer_key = None
        self.layer_rows = None
        self.layer_rgb = None
        self.water_px = None
        self.pins, self.route, self.eta, self.targets, self.here = [], None, None, [], None
        self.trans = None
        self.reframe = None
        self.hack_start = self.hack_until = -1e9
        self.cycle = 0
        self.order = list(range(len(QUERIES)))
        random.shuffle(self.order)
        self.scene_i = random.randrange(len(SCENES))
        self.query, self.results = "", []
        self.prev_query = ""
        sc = SCENES[self.scene_i]
        self.cam = self.scene_cam(sc)
        self.set_cam(self.cam)
        self.cars = []
        self.traffic = []
        self.new_cycle(self.last, first=True)

    # ------------------------------------------------------------ camera
    @staticmethod
    def scene_cam(sc):
        return (sc[1], sc[2], sc[3], sc[4], sc[5])

    def set_cam(self, cam):
        tx, tz, dist, pitch, yaw = cam
        self.cam = cam
        self.c, self.s = math.cos(yaw), math.sin(yaw)
        self.cp, self.sp = math.cos(pitch), math.sin(pitch)
        self.Hc = dist * self.sp
        back = dist * self.cp
        self.px, self.pz = tx - self.s * back, tz - self.c * back
        self.dist = dist
        self.key = tuple(round(v, 5) for v in cam)

    def proj(self, x, z, y=0.0):
        dx, dz = x - self.px, z - self.pz
        lx = dx * self.c - dz * self.s
        lz = dx * self.s + dz * self.c
        vy = y - self.Hc
        d = -vy * self.sp + lz * self.cp
        if d < 0.03:
            return None
        b = vy * self.cp + lz * self.sp
        return self.cxp + self.F * lx / d, self.cyp - self.F * b / d, d

    def unproj(self, sx, sy):
        A = (sx - self.cxp) / self.F
        B = -(sy - self.cyp) / self.F
        dy = B * self.cp - self.sp
        if dy > -1e-4:
            return None
        t = self.Hc / -dy
        lz = (B * self.sp + self.cp) * t
        lx = A * t
        return self.px + lx * self.c + lz * self.s, self.pz - lx * self.s + lz * self.c

    def fog_k(self, depth):
        f0, f1 = self.dist * 1.4, self.dist * 7 + 6
        return min(0.92, max(0.0, (depth - f0) / (f1 - f0)) ** 0.9 * 0.92)

    # ------------------------------------------------------------ ground raster
    def ground(self):
        W = self.W
        ph, w = self.ph, self.w
        B = self.B
        dy = B * self.cp - self.sp
        dz = B * self.sp + self.cp
        hit = dy < -1e-4
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(hit, self.Hc / -dy, np.inf)
        tmax = 90.0
        hit &= t < tmax
        out = np.empty((ph, w, 3), np.float32)
        # sky with stars and a horizon glow
        hy = self.cyp - self.F * (self.sp / self.cp)
        el = np.clip((hy - np.arange(ph)) / self.F, 0, None)
        skyc = (np.array(GLOW, np.float32)[None, :] * np.exp(-el * 9)[:, None] +
                np.array(SKY_TOP, np.float32)[None, :] * (1 - np.exp(-el * 9))[:, None])
        out[:] = skyc[:, None, :]
        rows = np.nonzero(hit)[0]
        self.water_px = None
        if rows.size:
            tr = t[rows]
            lz = dz[rows] * tr
            lx = self.A[None, :] * tr[:, None]
            U = self.px + lx * self.c + (lz * self.s)[:, None]
            V = self.pz - lx * self.s + (lz * self.c)[:, None]
            fu = (U - MX0) * TPK
            fv = (V - MZ0) * TPK
            fh = tr / self.F * TPK
            fvv = np.abs(np.gradient(lz)) * TPK if rows.size > 1 else fh
            fp = fh * np.minimum(1.6, np.sqrt(np.maximum(fvv / np.maximum(fh, 1e-9), 1.0)))
            lev = np.clip(np.floor(np.log2(np.maximum(fp, 1e-6)) + 0.1), 0, NL - 1).astype(np.int32)
            col = np.empty((rows.size, w, 3), np.float32)
            for lv in np.unique(lev):
                sel = lev == lv
                m = W["mips"][lv]
                hl, wl = m.shape[:2]
                sc = 1.0 / (1 << int(lv))
                xi = np.clip((fu[sel] * sc).astype(np.int32), 0, wl - 1)
                zi = np.clip((fv[sel] * sc).astype(np.int32), 0, hl - 1)
                col[sel] = m[zi, xi]
            # fog by depth, warmer near the horizon
            f0, f1 = self.dist * 1.4, self.dist * 7 + 6
            k = (np.clip((tr - f0) / (f1 - f0), 0, 1) ** 0.9 * 0.94)[:, None, None]
            el_r = np.clip((rows - hy) / self.F, 0, None)
            fogc = (np.array(GLOW, np.float32)[None, :] * np.exp(-el_r * 6)[:, None] +
                    np.array(FOG, np.float32)[None, :] * (1 - np.exp(-el_r * 6))[:, None])[:, None, :]
            col = col * (1 - k) + fogc * k
            out[rows] = col
            # remember nearby water pixels for animated glints
            near = tr < self.dist * 5
            if near.any():
                wi = np.clip(fu.astype(np.int32), 0, TW - 1)
                zi = np.clip(fv.astype(np.int32), 0, TH - 1)
                wm = W["water"][zi, wi] & near[:, None]
                yy, xx = np.nonzero(wm)
                if yy.size:
                    if yy.size > 5000:
                        sel = np.random.default_rng(1).choice(yy.size, 5000, replace=False)
                        yy, xx = yy[sel], xx[sel]
                    self.water_px = (rows[yy], xx, U[yy, xx], V[yy, xx], tr[yy])
        return out

    def draw_sky_details(self, s):
        hy = self.cyp - self.F * (self.sp / self.cp)
        yaw = math.atan2(self.s, self.c)
        for ang, el, br in self.stars:
            x = self.cxp + math.tan(((ang - yaw + math.pi) % (2 * math.pi)) - math.pi) * self.F
            if not 0 <= x < s.w or abs(((ang - yaw + math.pi) % (2 * math.pi)) - math.pi) > 1.2:
                continue
            y = hy - el * self.F
            if 0 <= y < hy - 2:
                s.pixel(int(x), int(y), blend((30, 30, 52), (150, 150, 190), br * br))

    # ------------------------------------------------------------ 3D: bridges + buildings
    def prep_buildings(self):
        b = self.buildings
        n = len(b)
        q = np.array([bb[0] for bb in b], np.float32)              # (n,4,2)
        hgt = np.array([bb[1] * BEXAG for bb in b], np.float32)
        tap = np.array([bb[2] for bb in b], np.float32)
        cen = q.mean(1, keepdims=True)
        top = cen + (q - cen) * tap[:, None, None]
        self.bx = np.concatenate([q[:, :, 0], top[:, :, 0]], 1)
        self.bz = np.concatenate([q[:, :, 1], top[:, :, 1]], 1)
        self.by = np.concatenate([np.zeros((n, 4), np.float32), np.repeat(hgt[:, None], 4, 1)], 1)
        self.bkind = [bb[3] for bb in b]
        self.bh = hgt
        self.bseed = [(i * 2654435761) & 0xFFFF for i in range(n)]
        nrm = []
        for quad, *_ in b:
            ns = []
            for i in range(4):
                (ax, az), (cx, cz) = quad[i], quad[(i + 1) % 4]
                ex, ez = cx - ax, cz - az
                ln = math.hypot(ex, ez) or 1
                ns.append((ez / ln, -ex / ln))
            nrm.append(ns)
        self.bnorm = nrm

    def fill_poly(self, s, pts, col, grad=None):
        """Convex polygon fill in pixel space: per-edge spans, then one slice write per row."""
        ys = [p[1] for p in pts]
        y0, y1 = max(0, int(min(ys) + 0.5)), min(s.ph - 1, int(max(ys) + 0.5))
        if y1 < y0:
            return
        xs = [p[0] for p in pts]
        if max(xs) < 0 or min(xs) >= s.w:
            return
        n = y1 - y0 + 1
        lo = [1e9] * n
        hi = [-1e9] * n
        ceil = math.ceil
        for i in range(len(pts)):
            ax, ay = pts[i]
            bx, by = pts[i - 1]
            if ay == by:
                continue
            if ay > by:
                ax, ay, bx, by = bx, by, ax, ay
            r0 = max(y0, ceil(ay - 0.5))
            r1 = min(y1, ceil(by - 0.5) - 1)
            if r1 < r0:
                continue
            sl = (bx - ax) / (by - ay)
            x = ax + (r0 + 0.5 - ay) * sl
            for r in range(r0 - y0, r1 - y0 + 1):
                if x < lo[r]:
                    lo[r] = x
                if x > hi[r]:
                    hi[r] = x
                x += sl
        w = s.w
        pt, pb = s.pt, s.pb
        ng = len(grad) if grad else 0
        for r in range(n):
            a, b = int(lo[r] + 0.5), int(hi[r] + 0.5)
            if a < 0:
                a = 0
            if b > w:
                b = w
            if b <= a:
                continue
            py = y0 + r
            c = col if not ng else grad[min(ng - 1, r * ng // n)]
            (pb if py & 1 else pt)[py >> 1][a:b] = [c] * (b - a)

    def draw_buildings(self, s):
        dx = self.bx - self.px
        dz = self.bz - self.pz
        lx = dx * self.c - dz * self.s
        lz = dx * self.s + dz * self.c
        vy = self.by - self.Hc
        d = -vy * self.sp + lz * self.cp
        ok = (d > 0.05).all(1)
        if not ok.any():
            return
        with np.errstate(divide="ignore", invalid="ignore"):
            sx = self.cxp + self.F * lx / d
            sy = self.cyp - self.F * (vy * self.cp + lz * self.sp) / d
        ok &= (sx.max(1) >= 0) & (sx.min(1) < s.w) & (sy.max(1) >= 0) & (sy.min(1) < s.ph)
        idx = np.nonzero(ok)[0]
        if not idx.size:
            return
        depth = d[idx, :4].mean(1)
        order = idx[np.argsort(-depth)]
        SX, SY, DD = sx.tolist(), sy.tolist(), d.tolist()
        lwx, lwz = 0.55, -0.83
        wall = (70, 78, 140)
        roofc = (104, 112, 170)
        rim = (170, 222, 255)
        fogc = FOG
        px_per_km = self.F / self.dist
        cache = self.__dict__.setdefault("_bcol", {})
        if len(cache) > 4000:
            cache.clear()

        def face_cols(kind, kq, fq):
            key = (kind, kq, fq)
            v = cache.get(key)
            if v is None:
                fk = fq / 16
                base = tuple(int(c * kq / 16) for c in (wall if kind != "salesforce" else (80, 92, 140)))
                topc = blend(base, fogc, fk)
                botc = blend(blend(base, (8, 8, 18), 0.6), fogc, fk)
                v = cache[key] = (topc, [blend(topc, botc, q / 3) for q in range(4)])
            return v

        def win_col(hs, fq):
            key = ("w", hs, fq)
            v = cache.get(key)
            if v is None:
                wc = (255, 206, 120) if hs % 3 else (150, 220, 255)
                v = cache[key] = blend(blend(wc, BLACK, 0.2 + hs / 40), fogc, fq / 16)
            return v

        def roof_col(c, fq, extra=0.0):
            key = ("r", c, fq, extra)
            v = cache.get(key)
            if v is None:
                v = cache[key] = blend(c, fogc, min(0.95, fq / 16 + extra))
            return v
        pixel = s.pixel
        for i in order.tolist():
            X, Y, Dd = SX[i], SY[i], DD[i]
            dep = (Dd[0] + Dd[1] + Dd[2] + Dd[3]) / 4
            fq = int(self.fog_k(dep) * 16 + 0.5)
            kind = self.bkind[i]
            hpx = abs(Y[0] - Y[4])
            wpx = max(X) - min(X)
            if wpx < 2.5 and kind == "b":
                # far away: a single shaded column is enough
                topc, grad = face_cols(kind, 11, fq)
                xm = int((X[0] + X[2]) / 2)
                for py in range(int(min(Y[4:])), int(max(Y[:4])) + 1):
                    pixel(xm, py, grad[0])
                continue
            g = list(zip(X[:4], Y[:4]))
            t = list(zip(X[4:], Y[4:]))
            nrm = self.bnorm[i]
            for e in range(4):
                j = (e + 1) % 4
                ga, gb, ta, tb = g[e], g[j], t[e], t[j]
                if kind == "pyramid":
                    cross = (gb[0] - ga[0]) * ((ta[1] + tb[1]) / 2 - ga[1]) - (gb[1] - ga[1]) * ((ta[0] + tb[0]) / 2 - ga[0])
                else:
                    cross = (gb[0] - ga[0]) * (ta[1] - ga[1]) - (gb[1] - ga[1]) * (ta[0] - ga[0])
                if cross <= 0:
                    continue
                nx, nz = nrm[e]
                kq = int((0.42 + 0.5 * max(0.0, nx * lwx + nz * lwz)) * 16)
                topc, grad = face_cols(kind, kq, fq)
                self.fill_poly(s, [ga, gb, tb, ta], topc, grad if hpx > 4 else None)
                # lit windows on the near facades
                if hpx > 7 and dep < self.dist * 2.2 and abs(gb[0] - ga[0]) > 2.5:
                    seed = self.bseed[i] + e * 97
                    cols_ = max(1, min(6, int(abs(gb[0] - ga[0]) / 2.2)))
                    rows_ = max(1, min(16, int(hpx / 2.2)))
                    for r_ in range(rows_):
                        v = (r_ + 0.7) / (rows_ + 0.5)
                        for q in range(cols_):
                            hs = (seed * 31 + r_ * 13 + q * 7) % 61
                            if hs > 17:
                                continue
                            u = (q + 0.5) / cols_
                            yb = ga[1] + (gb[1] - ga[1]) * u
                            yt = ta[1] + (tb[1] - ta[1]) * u
                            pixel(int(ga[0] + (gb[0] - ga[0]) * u), int(yt + (yb - yt) * v), win_col(hs, fq))
            if kind == "pyramid":
                ax, ay = sum(p[0] for p in t) / 4, min(p[1] for p in t)
                pixel(int(ax), int(ay) - 1, (255, 50, 60))
                continue
            if kind == "salesforce":
                rc = (210, 222, 255)
            else:
                rc = roofc if hpx > 10 else (87, 95, 155)
            self.fill_poly(s, t, roof_col(rc, fq))
            if hpx > 14:
                ec = roof_col(rim, fq, 0.45)
                for e in range(4):
                    a, b = t[e], t[(e + 1) % 4]
                    pline(s, a[0], a[1], b[0], b[1], ec)
            if kind == "salesforce":
                cx, cy = sum(p[0] for p in t) / 4, min(p[1] for p in t)
                pixel(int(cx), int(cy) - 1, (255, 255, 255))
            elif self.bh[i] > 0.5 and px_per_km > 20:
                cx, cy = sum(p[0] for p in t) / 4, min(p[1] for p in t)
                pixel(int(cx), int(cy) - 1, (255, 40, 60))

    def line3(self, s, a, b, col, thick=0):
        pa = self.proj(*a)
        pb = self.proj(*b)
        if pa is None or pb is None:
            return
        pline(s, pa[0], pa[1], pb[0], pb[1], col)
        if thick:
            pline(s, pa[0], pa[1] + 1, pb[0], pb[1] + 1, blend(col, BLACK, 0.35))

    def draw_bridges(self, s):
        # Golden Gate: two art-deco towers + catenary cables, International Orange
        (sx0, sz0), (sx1, sz1) = GG_S, GG_N
        q = self.proj((sx0 + sx1) / 2, (sz0 + sz1) / 2)
        ppk = self.F / q[2] if q else 0                 # pixels per km at the bridge
        deck, top = 0.07 * EXAG, 0.227 * EXAG
        u1, u2 = 0.22, 0.78
        L = math.hypot(sx1 - sx0, sz1 - sz0)
        ox, oz = -(sz1 - sz0) / L * 0.016, (sx1 - sx0) / L * 0.016

        def gp(u, side=0):
            return sx0 + (sx1 - sx0) * u + ox * side, sz0 + (sz1 - sz0) * u + oz * side

        def gh(u):
            if u < u1:
                return deck + (top - deck) * (u / u1) ** 1.6
            if u > u2:
                return deck + (top - deck) * ((1 - u) / (1 - u2)) ** 1.6
            m = (u - 0.5) / (u2 - 0.5)
            return deck + 0.012 + (top - deck - 0.012) * m * m
        orange, cable = (236, 82, 44), (255, 128, 80)
        if ppk > 6:
            self.line3(s, (*gp(0), deck), (*gp(1), deck), orange, thick=ppk > 40)
            sides = (-1, 1) if ppk > 70 else (0,)
            for side in sides:
                prev = None
                n = 40 if ppk > 30 else 16
                for k in range(n + 1):
                    u = k / n
                    x, z = gp(u, side)
                    p = (x, z, gh(u))
                    if prev:
                        self.line3(s, prev, p, cable)
                    if ppk > 80 and k % 2 == 0 and u1 < u < u2:
                        self.line3(s, (x, z, deck), p, blend(orange, BLACK, 0.55))
                    prev = p
            for u in (u1, u2):
                for side in sides:
                    x, z = gp(u, side)
                    self.line3(s, (x, z, 0), (x, z, top + 0.01), orange)
                if ppk > 70:
                    for hh in (0.45, 0.75, 1.0):
                        a, b = gp(u, -1), gp(u, 1)
                        self.line3(s, (a[0], a[1], top * hh + 0.005), (b[0], b[1], top * hh + 0.005), cable)
                x, z = gp(u)
                q = self.proj(x, z, top + 0.02)
                if q:
                    s.pixel(int(q[0]), int(q[1]), (255, 60, 60))
        # Bay Bridge west span: four towers, centre anchorage, a necklace of white lights
        (wx0, wz0), (wx1, wz1) = BB_W, BB_YBI
        q = self.proj((wx0 + wx1) / 2, (wz0 + wz1) / 2)
        ppk = self.F / q[2] if q else 0
        bdeck, btop = 0.06 * EXAG, 0.16 * EXAG
        silver, light = (150, 160, 190), (240, 246, 255)

        def bp(u):
            return wx0 + (wx1 - wx0) * u, wz0 + (wz1 - wz0) * u

        def bh(u):
            pts = [(0, bdeck), (0.18, btop), (0.29, bdeck + 0.01), (0.4, btop), (0.5, bdeck + 0.04),
                   (0.6, btop), (0.71, bdeck + 0.01), (0.82, btop), (1.0, bdeck)]
            for (ua, ha), (ub, hb) in zip(pts, pts[1:]):
                if ua <= u <= ub:
                    v = (u - ua) / (ub - ua)
                    if hb < ha:
                        return hb + (ha - hb) * (1 - v) ** 2
                    return ha + (hb - ha) * v * v
            return bdeck
        if ppk > 6:
            self.line3(s, (*bp(0), bdeck), (*bp(1), bdeck), silver)
            for u in (0.18, 0.4, 0.6, 0.82):
                x, z = bp(u)
                self.line3(s, (x, z, 0), (x, z, btop), silver)
            n = int(min(90, max(20, ppk * 3)))
            for k in range(n + 1):
                u = k / n
                x, z = bp(u)
                p = self.proj(x, z, bh(u))
                if p:
                    s.pixel(int(p[0]), int(p[1]), light if k % 2 == 0 else blend(light, BLACK, 0.4))
        # east span: single self-anchored tower near Yerba Buena
        (ex0, ez0), (ex1, ez1) = (13.45, 11.35), BB_E
        q = self.proj(ex0, ez0)
        ppk = self.F / q[2] if q else 0
        if ppk > 4:
            self.line3(s, (ex0, ez0, bdeck), (ex1, ez1, bdeck), silver)
            tx, tz = ex0 + (ex1 - ex0) * 0.08, ez0 + (ez1 - ez0) * 0.08
            self.line3(s, (tx, tz, 0), (tx, tz, btop * 1.05), light)
            if ppk > 20:
                for u in (0.03, 0.13):
                    x, z = ex0 + (ex1 - ex0) * u, ez0 + (ez1 - ez0) * u
                    self.line3(s, (tx, tz, btop), (x, z, bdeck), blend(silver, BLACK, 0.3))

    def render_layer(self, s):
        """Ground raster + bridges + towers into s.pt/s.pb for the current camera."""
        rgb = self.ground()
        rows = to_rows(rgb.astype(np.uint8))
        pt, pb = s.pt, s.pb
        for y in range(self.h):
            pt[y] = rows[2 * y]
            pb[y] = rows[2 * y + 1]
        self.draw_sky_details(s)
        self.draw_bridges(s)
        self.draw_buildings(s)

    def layer_array(self, s):
        return np.array([pt_row for y in range(s.h) for pt_row in (s.pt[y], s.pb[y])], np.uint8)

    def capture(self, cam):
        tmp = _Canvas(self.w, self.h)
        keep = self.cam
        self.set_cam(cam)
        self.render_layer(tmp)
        arr = self.layer_array(tmp)
        self.set_cam(keep)
        return arr

    # ------------------------------------------------------------ story
    def new_cycle(self, now, first=False):
        self.cycle += 1
        prev_cam = self.cam
        if not first:
            self.scene_i = (self.scene_i + 1 + (1 if random.random() < 0.3 else 0)) % len(SCENES)
        sc = SCENES[self.scene_i]
        self.scene = sc
        target = self.scene_cam(sc)
        yaw_j = random.uniform(-0.25, 0.25)
        target = (target[0], target[1], target[2] * random.uniform(0.92, 1.1), target[3], target[4] + yaw_j)
        self.prev_query = self.query
        qi = self.order[self.cycle % len(self.order)]
        self.query, self.results = QUERIES[qi]
        self.t0 = now
        if first:
            hi = (target[0] - 1.5, target[1] - 2.5, target[2] * 3.2, 0.95, target[4] - 0.6)
            self.trans = {"kind": "fly", "start": now, "dur": 3.4, "a": hi, "b": target}
        elif self.cycle % 2 == 0:
            self.trans = {"kind": "flip", "start": now + 0.2, "dur": 2.8, "a": prev_cam, "b": target}
        else:
            self.trans = {"kind": "fly", "start": now, "dur": 3.6, "a": prev_cam, "b": target}
        self.scene_cam_now = target
        self.reframe = None
        self.q_start = now + 0.45
        self.keys = self.keystrokes(self.query)
        self.q_done = self.q_start + self.keys[-1][0]
        tend = self.trans["start"] + self.trans["dur"]
        self.pins_at = max(self.q_done + 0.3, tend + 0.3)
        self.route_at = self.pins_at + 1.9
        self.travel_at = self.route_at + 2.9
        self.travel = 8.5
        self.cycle_end = self.travel_at + self.travel + 2.4
        for p in self.pins:
            p.dying = now
        self.route = None
        self.eta = None
        self.hack_planned = (self.cycle % 3 == 2)
        if self.hack_planned:
            self.hack_start = self.travel_at + 2.2
            self.hack_until = self.hack_start + 6.0
        self.traffic = []
        self.cars = []

    @staticmethod
    def keystrokes(q):
        out, t, typed = [(0.0, "")], 0.0, ""
        typo = random.randrange(3, len(q)) if len(q) > 5 and random.random() < 0.6 else -1
        near = "qwertyuiopasdfghjklzxcvbnm"
        for i, ch in enumerate(q):
            if i == typo and ch != " ":
                t += random.uniform(0.04, 0.08)
                typed += random.choice(near)
                out.append((t, typed))
                t += 0.4
                typed = typed[:-1]
                out.append((t, typed))
            t += random.uniform(0.04, 0.1) + (0.15 if ch == " " and random.random() < 0.4 else 0)
            typed += ch
            out.append((t, typed))
        return out

    def typed_at(self, now):
        if now < self.q_start:
            return None
        el = now - self.q_start
        txt = ""
        for t, s_ in self.keys:
            if t > el:
                break
            txt = s_
        return txt

    def grid_at(self, x, z):
        return SOMA_GRID if _soma(np.float32(x), np.float32(z)) else AXIS_GRID

    def land_ok(self, x, z, park_ok=False):
        i, j = int((x - MX0) * TPK), int((z - MZ0) * TPK)
        if not (0 <= i < TW and 0 <= j < TH):
            return False
        return bool(self.W["land"][j, i]) and (park_ok or not self.W["park"][j, i])

    def snap(self, x, z, grid, m):
        i, j = grid.to_grid(x, z)
        i, j = round(i / m) * m, round(j / m) * m
        return (i, j), grid.to_world(i, j)

    def visible(self, x, z, margin=8):
        q = self.proj(x, z)
        return q and margin < q[0] < self.w - margin and self.top * 2 + 10 < q[1] < self.ph - 10

    def drop_pins(self, now):
        m = self.scene[6]
        here = None
        for fy in (0.82, 0.76, 0.7, 0.88, 0.64):
            for fx in (0.5, 0.42, 0.58, 0.34, 0.66):
                p = self.unproj(self.w * fx, self.ph * fy)
                if not p:
                    continue
                g = self.grid_at(*p)
                ij, (x, z) = self.snap(p[0], p[1], g, m)
                if self.land_ok(x, z) and self.visible(x, z) and self.grid_at(x, z) is g:
                    here = (x, z, g, ij)
                    break
            if here:
                break
        if not here:
            return
        self.here = here
        g = here[2]
        spots = []
        tries = 0
        rng = random.Random(self.cycle * 31)
        while len(spots) < len(self.results) and tries < 160:
            tries += 1
            p = self.unproj(self.w * rng.uniform(0.12, 0.84), self.ph * rng.uniform(0.3, 0.66))
            if not p:
                continue
            ij, (x, z) = self.snap(p[0], p[1], g, m)
            if ij == here[3] or not self.land_ok(x, z) or self.grid_at(x, z) is not g or not self.visible(x, z, 14):
                continue
            q = self.proj(x, z)
            if any(abs(q[0] - a) < 22 and abs(q[1] - b) < 12 for a, b, *_ in spots):
                continue
            spots.append((q[0], q[1], x, z, ij))
        cols = [PINK, YELLOW, GREEN, ORANGE, CYAN]
        for i, (_, _, x, z, ij) in enumerate(spots):
            p = Pin(x, z, self.results[i], cols[i % len(cols)], now, delay=0.15 + i * 0.28)
            p.ij = ij
            self.pins.append(p)
        self.pins.append(Pin(here[0], here[1], "YOU", CYAN, now, kind="here"))
        self.targets = spots
        self.make_traffic()

    def route_path(self, g, a, b, rng):
        (i0, j0), (i1, j1) = a, b
        opts = [[(i0, j0), (i1, j0), (i1, j1)], [(i0, j0), (i0, j1), (i1, j1)]]
        if abs(j1 - j0) > 1:
            jm = j0 + (j1 - j0) // 2
            opts.append([(i0, j0), (i0, jm), (i1, jm), (i1, j1)])
        rng.shuffle(opts)
        for path in opts:
            pts = [g.to_world(i, j) for i, j in path]
            good = True
            for (ax, az), (bx, bz) in zip(pts, pts[1:]):
                n = max(1, int(math.hypot(bx - ax, bz - az) / 0.04))
                for k in range(n + 1):
                    if not self.land_ok(ax + (bx - ax) * k / n, az + (bz - az) * k / n, park_ok=True):
                        good = False
                        break
                if not good:
                    break
            if good:
                out = [path[0]]
                for p in path[1:]:
                    if p != out[-1]:
                        out.append(p)
                return out
        return None

    def make_route(self, now):
        if not self.targets or not self.here:
            return
        rng = random.Random(self.cycle * 7 + 3)
        g = self.here[2]
        order = list(range(len(self.targets)))
        rng.shuffle(order)
        for k in order:
            sx, sy, tx, tz, ij = self.targets[k]
            path = self.route_path(g, self.here[3], ij, rng)
            if not path or len(path) < 2:
                continue
            pts = [g.to_world(i, j) for i, j in path]
            segs = []
            total = 0.0
            for (ax, az), (bx, bz) in zip(pts, pts[1:]):
                L = math.hypot(bx - ax, bz - az)
                segs.append(L)
                total += L
            dest = "DESTINATION"
            for p in self.pins:
                if p.kind == "poi" and abs(p.wx - tx) < 1e-6 and abs(p.wz - tz) < 1e-6:
                    p.kind = "dest"
                    dest = p.label
            names = []
            for (ia, ja), (ib, jb) in zip(path, path[1:]):
                names.append(g.name(0, ia) if ia == ib else g.name(1, ja))
            self.route = {"path": path, "pts": pts, "segs": segs, "len": total, "start": now, "draw": 1.3,
                          "names": names, "grid": g}
            self.eta = {"start": now + 1.3, "min": max(2, int(total * 4.2 + 1)), "mi": total / 1.609,
                        "via": max(zip(segs, names))[1], "dest": dest, "end": pts[-1],
                        "traffic": random.choice((("LIGHT", TRAFFIC[0]), ("MEH", TRAFFIC[1]), ("UGH", TRAFFIC[2]))),
                        "note": random.choice(ETA_NOTES)}
            # camera reframes so the whole route sits in view
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
            tx0, tz0, d0, p0, y0 = self.cam
            ext = max(max(xs) - min(xs), max(zs) - min(zs))
            d1 = max(d0 * 0.92, min(d0 * 1.25, ext * 1.9))
            b = (tx0 + (cx - tx0) * 0.55, tz0 + (cz - tz0) * 0.55, d1, p0 + 0.04, y0 + rng.choice((-0.16, 0.16)))
            self.reframe = {"start": now, "dur": 1.7, "a": self.cam, "b": b}
            return

    def make_traffic(self):
        """Coloured flow segments on nearby arterials and highways."""
        rng = random.Random(self.cycle * 13)
        tr = []
        overview = self.dist > 6
        for pl in (HIGHWAYS if overview else HIGHWAYS + PRIMARIES):
            for (ax, az), (bx, bz) in zip(pl, pl[1:]):
                L = math.hypot(bx - ax, bz - az)
                n = max(1, int(L / 0.6))
                for k in range(n):
                    u0, u1 = k / n, (k + 1) / n
                    a = (ax + (bx - ax) * u0, az + (bz - az) * u0)
                    b = (ax + (bx - ax) * u1, az + (bz - az) * u1)
                    mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                    if math.hypot(mx - self.cam[0], mz - self.cam[1]) > self.dist * 2.4:
                        continue
                    if not self.land_ok(mx, mz, park_ok=True):
                        continue
                    if rng.random() < (0.6 if overview else 0.45):
                        continue
                    lvl = rng.choices((0, 1, 2), (5, 3, 2))[0]
                    tr.append((a, b, lvl, rng.random()))
        g = self.here[2] if self.here else AXIS_GRID
        ci, cj = g.to_grid(self.cam[0], self.cam[1])
        for _ in range(0 if overview else 5):
            i, j = int(ci) + rng.randint(-4, 4), int(cj) + rng.randint(-4, 4)
            if rng.random() < 0.5:
                a, b = g.to_world(i, j), g.to_world(i + 1, j)
            else:
                a, b = g.to_world(i, j), g.to_world(i, j + 1)
            if self.land_ok(*a, park_ok=False) and self.land_ok(*b, park_ok=False):
                tr.append((a, b, rng.choices((0, 1, 2), (3, 3, 2))[0], rng.random()))
        self.traffic = tr
        self.cars = []
        for _ in range(26):
            a, b, _, _ = rng.choice(tr) if tr else ((0, 0), (0, 0), 0, 0)
            self.cars.append([a, b, rng.random(), rng.uniform(0.05, 0.18) * rng.choice((-1, 1))])

    # ------------------------------------------------------------ overlays
    def shadow(self, s, x, y, rx, k):
        for py in (y - 1, y, y + 1):
            if not 0 <= py < s.ph:
                continue
            row = (s.pb if py & 1 else s.pt)[py >> 1]
            span = rx if py == y else rx * 0.6
            for px in range(int(x - span), int(x + span) + 1):
                if 0 <= px < s.w and row[px] is not None:
                    row[px] = blend(row[px], BLACK, k * (0.8 if py == y else 0.5))

    def label(self, s, x, y, txt, col, avoid=False, bg=None):
        if not (self.top <= y < s.h - 1):
            return False
        r = (x - 1, y, len(txt) + 2, 1)
        if avoid and any(r[1] == o[1] and not (r[0] + r[2] <= o[0] or o[0] + o[2] <= r[0]) for o in self.occ):
            return False
        self.occ.append(r)
        for i, ch in enumerate(txt):
            xx = x + i
            if 0 <= xx < s.w:
                if bg is not None:
                    s.bg[y][xx] = bg
                else:
                    under = s.pt[y][xx] or (0, 0, 0)
                    s.bg[y][xx] = blend(under, BLACK, 0.72)
                s.ch[y][xx] = ch
                s.fg[y][xx] = col
                s.pt[y][xx] = s.pb[y][xx] = None
        return True

    def draw_traffic(self, s, now, hacked):
        if not self.traffic:
            return
        for a, b, lvl, ph in self.traffic:
            pa, pb = self.proj(*a), self.proj(*b)
            if not pa or not pb:
                continue
            if max(pa[0], pb[0]) < 0 or min(pa[0], pb[0]) >= s.w:
                continue
            col = TRAFFIC[lvl] if not hacked else (PINK, CYAN, YELLOW)[lvl]
            k = pulse(now, 2 + lvl, ph * 6)
            dim = blend(col, BLACK, 0.62 - k * 0.22)
            pline(s, pa[0], pa[1], pb[0], pb[1], dim)
            n = max(2, int(math.hypot(pb[0] - pa[0], pb[1] - pa[1]) / 7))
            off = (now * (0.9 - lvl * 0.3) + ph) % 1
            for i in range(n):
                u = (i + off) / n
                if u > 1:
                    continue
                x, y = pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u
                s.pixel(int(x), int(y), blend(col, WHITE, 0.25))

    def draw_cars(self, s, dt, hacked):
        for car in self.cars:
            a, b, u, v = car
            L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            u = (u + v * dt / L) % 1.0
            car[2] = u
            x, z = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
            q = self.proj(x, z, 0.003)
            if q and 0 <= q[0] < s.w and self.top * 2 <= q[1] < s.ph:
                col = (CYAN if hacked else ((255, 250, 225) if v > 0 else (255, 50, 50)))
                s.pixel(int(q[0]), int(q[1]), col)

    def draw_labels(self, s, now, hacked):
        cands = []
        for nm, x, z in DISTRICTS:
            q = self.proj(x, z)
            if not q or q[2] > self.dist * 4.5:
                continue
            cands.append((q[2], q, nm))
        cands.sort()
        lim = 9 if s.w >= 150 else 5
        placed = 0
        for dep, (sx, sy, d), nm in cands:
            if placed >= lim:
                break
            lead = 5 if dep < self.dist * 1.6 else 3
            ty = int(sy - lead) // 2 - 1
            name = nm if not hacked else ("OWNED BY DEDSEC" if placed % 2 == 0 else "#DEDSEC")
            left = int(sx) - len(name) // 2
            if left < 1 or left + len(name) > s.w - 6 or not (self.top + 1 <= ty < s.h - 3):
                continue
            if any(abs(ty - oy) <= 1 and left < ox + ow + 2 and left + len(name) > ox - 2 for ox, oy, ow, _ in self.occ):
                continue
            far = min(1.0, dep / (self.dist * 4.5))
            col = blend((236, 236, 250), (130, 120, 160), far) if not hacked else PINK
            lc = blend((150, 170, 215), BLACK, 0.45 + far * 0.3) if not hacked else blend(PINK, BLACK, 0.4)
            pline(s, int(sx), int(sy) - 1, int(sx), int(ty * 2 + 2), lc)
            s.pixel(int(sx), int(sy), WHITE if not hacked else PINK)
            if self.label(s, left, ty, name, col, avoid=True):
                placed += 1
        for nm, x, z in WATER_LABELS:
            q = self.proj(x, z)
            if not q or q[2] > self.dist * 6:
                continue
            y = int(q[1]) // 2
            left = int(q[0]) - len(nm) // 2
            if left < 1 or left + len(nm) > s.w - 6 or not (self.top + 1 <= y < s.h - 3):
                continue
            txt = " ".join(nm) if len(nm) * 2 < s.w // 3 else nm
            left = int(q[0]) - len(txt) // 2
            if left >= 1 and left + len(txt) < s.w - 6:
                self.label(s, left, y, txt, (90, 150, 210) if not hacked else PINK, avoid=True)

    def draw_pin(self, s, p, now, hacked, order=0):
        age = now - p.born
        if age < 0:
            return
        q = self.proj(p.wx, p.wz)
        if not q:
            return
        sx, sy, depth = q
        if not (-10 < sx < s.w + 10 and self.top * 2 < sy < s.ph + 10):
            return
        scale = max(0.6, min(1.25, self.dist * 1.05 / depth)) * (s.h / 45) ** 0.35
        if p.dying is not None:
            k = 1 - (now - p.dying) / 0.5
            if k <= 0:
                return
            scale *= k
        T0 = 0.42
        squash = 0.0
        if age < T0:
            off = 60 * (1 - (age / T0) ** 2)
        else:
            u = age - T0
            off = 10 * abs(math.sin(u * 7.5)) * math.exp(-u * 4.0)
            squash = max(0.0, 1 - u / 0.12) * 0.45
        x, y = int(sx), int(sy)
        near = 1 - min(1.0, off / 50)
        self.shadow(s, sx, y, (1.5 + 2.2 * near) * scale + 0.5, 0.25 + 0.5 * near)
        if p.kind == "here":
            if self.route and self.travel_at <= now and p.dying is None:
                s.pixel_circle(sx, sy, 1.5, (40, 90, 170))
                return
            r = (now * 1.4) % 1
            s.pixel_circle(sx, sy, 2 + r * 7 * scale, blend(CYAN if not hacked else PINK, BLACK, r), fill=False)
            s.pixel_circle(sx, sy, 2.4 * scale + 0.6, WHITE)
            s.pixel_circle(sx, sy, 1.6 * scale, (40, 130, 255) if not hacked else PINK)
            return
        top = y - int(off)
        col = p.col
        if p.kind == "dest":
            col = blend(PINK, WHITE, 0.3 * pulse(now, 6))
        flip_at = self.hack_start + 0.35 + order * 0.22
        if hacked and now >= flip_at:
            pop = now - flip_at
            if not p.popped:
                p.popped = True
                self.particles.burst(sx, top / 2 - 2, 14, (PINK, WHITE, PURPLE), speed=9, chars="*+x.")
            k = max(1, int(round(scale * (1.6 if pop < 0.18 else 1.0))))
            hgt = len(SKULL_PX)
            flash = pop < 0.12
            for j, row in enumerate(SKULL_PX):
                for i, ch in enumerate(row):
                    if ch == "X":
                        c = WHITE if flash else (PINK if j < 3 else blend(PINK, WHITE, 0.45))
                        for a_ in range(k):
                            for b_ in range(k):
                                s.pixel(x - 4 * k + i * k + a_, top - (hgt - j) * k - 2 + b_, c)
            pline(s, x, top - 2, x, top, PINK)
            if p.dying is None and s.w > 100 and pop > 0.3:
                self.label(s, x - 3, (top - (hgt + 2) * k) // 2 - 1, " PWND ", BLACK, bg=PINK, avoid=True)
            return
        if not hacked:
            p.popped = False
        r = 3.0 * scale
        sq = 1 - squash
        cy = top - (r + 3 * scale) * sq
        for k in range(int(3 * scale * sq) + 1):
            hw = int((1 - k / (3 * scale * sq + 1)) * r * 0.75)
            for dx in range(-hw, hw + 1):
                s.pixel(x + dx, top - k, blend(col, BLACK, 0.25))
        rw = r * (1 + squash * 0.5)
        for py in range(int(cy - r * sq), int(cy + r * sq) + 1):
            dy = (py - cy) / max(0.5, r * sq)
            if abs(dy) > 1:
                continue
            span = rw * math.sqrt(1 - dy * dy)
            for px in range(int(sx - span), int(sx + span) + 1):
                s.pixel(px, py, col if dy > -0.55 or px > sx - span * 0.3 else blend(col, WHITE, 0.35))
        s.pixel_circle(sx, cy, max(0.8, r * 0.38), WHITE)
        if age > 0.6 and p.dying is None:
            ly = int(cy - r) // 2 - 1
            lab = " " + p.label + " "
            if p.kind == "dest":
                lab = " > " + p.label + " "
            if ly > self.top:
                lx0 = x - len(lab) // 2
                if p.kind == "dest":
                    self.label(s, lx0, ly, lab, BLACK, bg=blend(PINK, WHITE, 0.15))
                else:
                    self.label(s, lx0, ly, lab, BLACK, avoid=True, bg=blend(col, BLACK, 0.1))
                if p.kind == "dest" or (age < 4 and s.w > 120):
                    stars = int(float(p.rating) + 0.5)
                    rt = "*" * stars + "." * (5 - stars) + " " + p.rating
                    ry = ly - 1 if ly - 1 > self.top else ly + 1
                    self.label(s, x - len(rt) // 2, ry, rt, YELLOW, avoid=p.kind != "dest")

    def route_state(self, now):
        rt = self.route
        prog = max(0.0, min(1.0, (now - self.travel_at) / self.travel))
        d = prog * rt["len"]
        acc = 0.0
        for i, L in enumerate(rt["segs"]):
            if d <= acc + L or i == len(rt["segs"]) - 1:
                u = (d - acc) / L if L else 0
                (ax, az), (bx, bz) = rt["pts"][i], rt["pts"][i + 1]
                return prog, i, min(1.0, u), (ax + (bx - ax) * u, az + (bz - az) * u), acc + L - d
            acc += L
        return prog, 0, 0, rt["pts"][0], 0

    def draw_route(self, s, now, hacked):
        rt = self.route
        if not rt:
            return
        age = now - rt["start"]
        pts = rt["pts"]
        total = rt["len"]
        drawn = total * _smooth(age / rt["draw"])
        prog, si, su, pos, _ = self.route_state(now)
        done_d = prog * total if now >= self.travel_at else 0.0
        base = PINK if hacked else ROUTE
        core = YELLOW if hacked else ROUTE_CORE
        casing = (10, 20, 50) if not hacked else (40, 0, 30)
        acc = 0.0
        for i, ((ax, az), (bx, bz)) in enumerate(zip(pts, pts[1:])):
            L = rt["segs"][i]
            if acc >= drawn:
                break
            u1 = min(1.0, (drawn - acc) / L)
            ends = (ax + (bx - ax) * u1, az + (bz - az) * u1)
            # split into travelled (grey) and remaining
            ud = max(0.0, min(u1, (done_d - acc) / L))
            mid = (ax + (bx - ax) * ud, az + (bz - az) * ud)
            for (p0, p1, col, cc) in (((ax, az), mid, (70, 80, 110), (110, 120, 150)), (mid, ends, base, core)):
                qa, qb = self.proj(*p0), self.proj(*p1)
                if not qa or not qb or (abs(qa[0] - qb[0]) < 0.5 and abs(qa[1] - qb[1]) < 0.5 and p0 == p1):
                    continue
                pline(s, qa[0], qa[1] + 1, qb[0], qb[1] + 1, casing)
                pline(s, qa[0] - 1, qa[1], qb[0] - 1, qb[1], col)
                pline(s, qa[0] + 1, qa[1], qb[0] + 1, qb[1], col)
                pline(s, qa[0], qa[1] - 1, qb[0], qb[1] - 1, col)
                pline(s, qa[0], qa[1], qb[0], qb[1], cc)
            acc += L
        # pulse travelling along the remaining route
        if age > rt["draw"]:
            k = ((now * 0.35) % 1) * total
            if k > done_d:
                acc = 0.0
                for i, L in enumerate(rt["segs"]):
                    if k <= acc + L:
                        u = (k - acc) / L
                        (ax, az), (bx, bz) = pts[i], pts[i + 1]
                        q = self.proj(ax + (bx - ax) * u, az + (bz - az) * u)
                        if q:
                            s.pixel(int(q[0]), int(q[1]), WHITE)
                            s.pixel(int(q[0]) + 1, int(q[1]), WHITE)
                        break
                    acc += L
        if age < rt["draw"]:
            acc = 0.0
            for i, L in enumerate(rt["segs"]):
                if drawn <= acc + L:
                    u = (drawn - acc) / L
                    (ax, az), (bx, bz) = pts[i], pts[i + 1]
                    q = self.proj(ax + (bx - ax) * u, az + (bz - az) * u)
                    if q:
                        self.particles.add(q[0], q[1] / 2, random.uniform(-4, 4), random.uniform(-2, 1), 0.4, ".", core)
                    break
                acc += L
        if prog >= 1 and not rt.get("arrived"):
            rt["arrived"] = True
            q = self.proj(*pts[-1])
            if q:
                self.particles.burst(q[0], q[1] / 2, 30, (PINK, YELLOW, CYAN, WHITE), speed=9)

    def draw_car(self, s, now, hacked):
        rt = self.route
        if not rt:
            return
        prog, si, su, pos, _ = self.route_state(now)
        pts = rt["pts"]
        if now >= self.travel_at and prog < 1:
            (ax, az), (bx, bz) = pts[si], pts[si + 1]
            qa, qb = self.proj(*pos), self.proj(pos[0] + (bx - ax) * 0.02, pos[1] + (bz - az) * 0.02)
            if qa and qb:
                self.draw_arrow(s, qa[0], qa[1], qb[0] - qa[0], qb[1] - qa[1], now, hacked)

    def draw_arrow(self, s, cx, cy, dx, dy, now, hacked):
        """Navigation chevron with a soft halo, pointing along the route on screen."""
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx / ln, dy / ln
        vx, vy = -uy, ux
        sz = 4.2 * (s.h / 45) ** 0.4
        halo = (60, 140, 255) if not hacked else PINK
        r = sz + 2 + 1.5 * pulse(now, 5)
        s.pixel_circle(cx, cy, r, blend(halo, BLACK, 0.55), fill=False)
        tip = (cx + ux * sz * 1.3, cy + uy * sz * 1.3)
        lft = (cx - ux * sz + vx * sz, cy - uy * sz + vy * sz)
        rgt = (cx - ux * sz - vx * sz, cy - uy * sz - vy * sz)
        notch = (cx - ux * sz * 0.35, cy - uy * sz * 0.35)
        body = WHITE
        inner = (50, 140, 255) if not hacked else PINK
        self.fill_poly(s, [tip, lft, notch], body)
        self.fill_poly(s, [tip, notch, rgt], body)
        m = 0.55
        tip2 = (cx + ux * sz * 1.3 * m, cy + uy * sz * 1.3 * m)
        l2 = (cx + (-ux + vx) * sz * m, cy + (-uy + vy) * sz * m)
        r2 = (cx + (-ux - vx) * sz * m, cy + (-uy - vy) * sz * m)
        n2 = (cx - ux * sz * 0.35 * m, cy - uy * sz * 0.35 * m)
        self.fill_poly(s, [tip2, l2, n2], inner)
        self.fill_poly(s, [tip2, n2, r2], inner)

    # ------------------------------------------------------------ UI panels
    def panel(self, s, x, y, w, h, bg=PANEL, edge=PANEL_EDGE, rounded=True):
        x0, x1 = max(0, x), min(s.w, x + w)
        for yy in range(max(0, y), min(s.h, y + h)):
            rc, rf, rb = s.ch[yy], s.fg[yy], s.bg[yy]
            rt, rbb = s.pt[yy], s.pb[yy]
            for xx in range(x0, x1):
                rc[xx] = " "
                rf[xx] = None
                rb[xx] = bg
                rt[xx] = rbb[xx] = None
        if edge is None or h < 2:
            return
        tl, tr, bl, br = ("╭", "╮", "╰", "╯") if rounded else ("┌", "┐", "└", "┘")
        s.text(x, y, tl + "─" * (w - 2) + tr, edge)
        s.text(x, y + h - 1, bl + "─" * (w - 2) + br, edge)
        for yy in range(y + 1, y + h - 1):
            s.put(x, yy, "│", edge)
            s.put(x + w - 1, yy, "│", edge)

    def draw_search(self, s, now, hacked):
        bw = min(66, s.w - 16)
        x0 = 2
        edge = PINK if hacked else ((90, 140, 200) if self.q_start <= now < self.q_done else PANEL_EDGE)
        self.panel(s, x0, 0, bw, 3, edge=edge)
        logo = [("N", (66, 133, 244)), ("U", (234, 67, 53)), ("D", (251, 188, 5)), ("L", (66, 133, 244)),
                ("E", (52, 168, 83))]
        if hacked:
            logo = [(c, random.choice((PINK, CYAN, YELLOW))) for c in "DEDSEC"]
        for i, (c, cc) in enumerate(logo):
            s.put(x0 + 2 + i, 1, c, cc)
        tx = x0 + 3 + len(logo) + 1
        s.put(tx - 1, 1, "│", (60, 70, 96))
        room = bw - (tx - x0) - 6
        typed = self.typed_at(now)
        if hacked:
            q = "dedsec was here"
            typed = "".join(random.choice("#$%&!") if random.random() < 0.15 else ch for ch in q)
            s.text(tx + 1, 1, typed[:room], PINK)
        elif typed is None:
            # the previous query is selected, about to be replaced
            old = self.prev_query or "Search Nudle Maps"
            for i, ch in enumerate(old[:room]):
                s.put(tx + 1 + i, 1, ch, WHITE)
                s.set_bg(tx + 1 + i, 1, (40, 80, 150))
        else:
            s.text(tx + 1, 1, typed[:room], WHITE)
            if now < self.q_done + 0.8 and int(now * 3) % 2 == 0:
                s.put(tx + 1 + min(room, len(typed)), 1, "▏", YELLOW)
        s.put(x0 + bw - 4, 1, "×" if not hacked else "!", (120, 130, 160))
        s.put(x0 + bw - 2, 1, "◉", YELLOW if self.q_start <= now < self.q_done else (66, 133, 244))
        # suggestions while typing
        if (not hacked and typed and self.q_start < now < self.q_done and len(typed) > 2 and s.h > 30):
            sug = [self.query, self.query + " open now", self.query + " (no cameras)"]
            sw = min(bw - 4, max(len(t) for t in sug) + 6)
            self.panel(s, tx - 1, 2, sw, len(sug) + 2, edge=(50, 64, 92))
            s.put(tx - 1, 2, "├", edge)
            for i, t in enumerate(sug):
                s.text(tx + 1, 3 + i, "o ", (110, 120, 150))
                s.text(tx + 3, 3 + i, typed[:sw - 5], WHITE)
                s.text(tx + 3 + len(typed), 3 + i, t[len(typed):sw - 5], (120, 130, 160))
        elif not hacked and self.q_done < now < self.q_done + 6 and s.h > 24:
            info = " About %d results (0.%02d s) - %d cameras nearby " % (
                len(self.results), 13 + (self.cycle * 37) % 80, 3 + self.cycle % 9)
            if self.route and now > self.route["start"]:
                info = " %s  -  %d results " % (self.scene[0], len(self.results))
            if len(info) < bw - 2:
                self.panel(s, x0 + 2, 3, len(info), 1, bg=(12, 15, 26), edge=None)
                s.text(x0 + 2, 3, info, (120, 170, 210))

    def draw_compass(self, s, now, hacked):
        cx, cy = s.w - 6, 5.5
        r = 4.5
        s.pixel_circle(cx, cy, r, (14, 18, 30))
        s.pixel_circle(cx, cy, r, (70, 90, 130), fill=False)
        nx, ny = -self.s, -self.c                  # screen direction of north
        tip = (cx + nx * (r - 0.8), cy + ny * (r - 0.8))
        tail = (cx - nx * (r - 0.8), cy - ny * (r - 0.8))
        pline(s, cx, cy, tip[0], tip[1], PINK if hacked else (255, 70, 70))
        pline(s, cx, cy, tail[0], tail[1], (220, 220, 235))
        s.pixel(int(cx), int(cy), WHITE)
        lx, ly = int(round(cx + nx * (r + 2.5))), int(round(cy + ny * (r + 2.5))) // 2
        if 0 <= ly < s.h and lx < s.w:
            s.put(lx, max(0, ly), "N", YELLOW if not hacked else PINK)

    def draw_controls(self, s, now, hacked):
        x = s.w - 5
        y = max(self.top + 5, s.h // 2 - 3)
        zooming = 0
        mv = self.reframe or (self.trans if self.trans and self.trans["kind"] == "fly" else None)
        if mv and mv["start"] <= now < mv["start"] + mv["dur"]:
            zooming = 1 if mv["b"][2] < mv["a"][2] else -1
        col = PANEL_EDGE if not hacked else PINK
        self.panel(s, x, y, 3, 5, edge=None)
        s.text(x, y, "┌─┐", col)
        s.text(x, y + 1, "│+│", col)
        s.text(x, y + 2, "├─┤", col)
        s.text(x, y + 3, "│-│", col)
        s.text(x, y + 4, "└─┘", col)
        if zooming:
            yy = y + (1 if zooming > 0 else 3)
            s.put(x + 1, yy, "+" if zooming > 0 else "-", BLACK)
            s.set_bg(x + 1, yy, YELLOW)
        else:
            s.put(x + 1, y + 1, "+", WHITE)
            s.put(x + 1, y + 3, "-", WHITE)
        if s.h > 30:
            self.panel(s, x, y + 6, 3, 1, bg=(30, 40, 66), edge=None)
            s.text(x, y + 6, "3D ", CYAN if not hacked else PINK)
            self.panel(s, x, y + 8, 3, 1, bg=(30, 40, 66), edge=None)
            s.text(x + 1, y + 8, "o", (66, 133, 244))

    def draw_scale(self, s, hacked):
        km_px = self.dist / self.F                 # km per pixel (cell width) at the centre
        best = None
        for mi, lab in ((0.025, "150 ft"), (0.05, "250 ft"), (0.1, "500 ft"), (0.25, "0.25 mi"), (0.5, "0.5 mi"),
                        (1, "1 mi"), (2, "2 mi"), (5, "5 mi")):
            n = mi * 1.609 / km_px
            if 6 <= n <= 16:
                best = (int(n), lab)
                break
        if not best:
            return
        n, lab = best
        y = s.h - 2
        txt = "├" + "─" * n + "┤ " + lab
        x = s.w - len(txt) - 2
        self.panel(s, x - 1, y, len(txt) + 2, 1, bg=(10, 12, 20), edge=None)
        s.text(x, y, txt, (150, 160, 190) if not hacked else PINK)

    def draw_eta(self, s, now, hacked):
        e = self.eta
        if not e or now < e["start"]:
            return
        k = ease_out((now - e["start"]) / 0.4)
        wide = s.w >= 120
        cw = 46 if wide else min(s.w - 22, 38)
        ch_ = 5
        x = 2
        y = s.h - 1 - ch_ + int((1 - k) * (ch_ + 1))
        col = PINK if hacked else PANEL_EDGE
        self.panel(s, x, y, cw, ch_, edge=col)
        if k < 1:
            return
        prog = max(0.0, min(1.0, (now - self.travel_at) / self.travel)) if now > self.travel_at else 0.0
        mins = max(0, int(round(e["min"] * (1 - prog))))
        inner = cw - 4
        if hacked:
            glitchy = "".join(random.choice("#%&") if random.random() < 0.2 else c for c in e["dest"])
            s.text(x + 2, y + 1, "??? min", PINK)
            s.text(x + 10, y + 1, "ROUTE BY #DEDSEC", YELLOW)
            s.text(x + 2, y + 2, ("> " + glitchy)[:inner], WHITE)
            s.text(x + 2, y + 3, "ctOS CAN'T SEE YOU"[:inner], PINK)
            return
        lt = time.localtime(now + mins * 60)
        head = (("%d min" % mins) if mins else "<1 min") if prog < 1 else "Arrived"
        s.text(x + 2, y + 1, head, (80, 230, 140))
        dist = "(%.1f mi)" % (e["mi"] * (1 - prog))
        s.text(x + 3 + len(head), y + 1, dist, (170, 180, 205))
        arr = "%02d:%02d" % (lt.tm_hour, lt.tm_min)
        tr, tc = e["traffic"]
        right = "o " + tr + "  " + arr
        if 6 + len(head) + len(dist) + len(right) < cw:
            s.text(x + cw - 2 - len(right), y + 1, "o " + tr, tc)
            s.text(x + cw - 2 - len(arr), y + 1, arr, WHITE)
        line2 = "> " + e["dest"] + "  via " + e["via"]
        s.text(x + 2, y + 2, line2[:inner], WHITE)
        fill = int((inner - 1) * prog)
        s.text(x + 2, y + 3, "━" * fill, (66, 150, 255))
        s.put(x + 2 + fill, y + 3, ">", YELLOW)
        rest = inner - fill - 1
        note = " " + e["note"] + " "
        bar = "─" * rest
        if rest > len(note) + 4 and wide:
            bar = bar[:rest - len(note) - 1] + note + "─"
        s.text(x + 3 + fill, y + 3, bar[:rest], (60, 72, 100))

    def draw_nav(self, s, now, hacked):
        rt = self.route
        if not rt or now < self.travel_at or hacked:
            return
        prog, si, su, pos, left = self.route_state(now)
        if prog >= 1:
            title, sub = "ARRIVED", self.eta["dest"] if self.eta else ""
            arrow = "*"
        elif si + 1 < len(rt["pts"]) - 1:
            (ax, az), (bx, bz), (cx, cz) = rt["pts"][si], rt["pts"][si + 1], rt["pts"][si + 2]
            cr = (bx - ax) * (cz - bz) - (bz - az) * (cx - bx)
            arrow = "←" if cr > 0 else "→"
            title = "%s  %s" % (arrow, self.fmt_dist(left))
            sub = ("LEFT ONTO " if cr > 0 else "RIGHT ONTO ") + rt["names"][si + 1]
        elif left < 0.04:
            title, sub = "↑  ARRIVING", "DESTINATION ON THE RIGHT"
        else:
            title = "↑  %s" % self.fmt_dist(left)
            sub = "DESTINATION AHEAD"
        w = max(len(title), len(sub)) + 4
        w = min(w, s.w // 2)
        y = 4 if s.h > 30 else 3
        self.panel(s, 2, y, w, 2, bg=NAV_GREEN, edge=None)
        s.text(4, y, title[:w - 3], WHITE)
        s.text(4, y + 1, sub[:w - 3], (200, 245, 225))

    @staticmethod
    def fmt_dist(km):
        mi = km / 1.609
        if mi < 0.15:
            return "%d ft" % (int(mi * 5280 / 50 + 0.5) * 50)
        return "%.1f mi" % mi

    def draw_scene_title(self, s, now):
        tr = self.trans
        if not tr:
            return
        u = now - tr["start"]
        if not (0.3 < u < tr["dur"] + 1.6):
            return
        name = self.scene[0]
        txt = " " + "  ".join(name.split(" ")) + " "
        txt = " ".join(txt) if len(txt) * 2 < s.w - 10 else txt
        n = min(len(txt), int((u - 0.3) * 40))
        y = s.h // 2 - (6 if s.h > 30 else 4)
        x = (s.w - len(txt)) // 2
        a = 1.0 if u < tr["dur"] + 1.0 else max(0.0, 1 - (u - tr["dur"] - 1.0) / 0.6)
        col = blend((40, 40, 60), WHITE, a)
        self.panel(s, x - 2, y, len(txt) + 4, 1, bg=(6, 7, 16), edge=None)
        for i, ch in enumerate(txt[:n]):
            s.put(x + i, y, ch, col)
        sub = "SAN FRANCISCO, CA  -  NUDLE 3D" if name != "SAN FRANCISCO" else "BAY AREA  -  NUDLE 3D"
        if s.w > 60 and u > 0.8:
            sx = (s.w - len(sub)) // 2
            for i, ch in enumerate(sub):
                s.put(sx + i, y + 1, ch, blend((40, 40, 60), (120, 170, 220), a))
                s.set_bg(sx + i, y + 1, (8, 8, 16))
                s.pt[y + 1][sx + i] = s.pb[y + 1][sx + i] = None

    # ------------------------------------------------------------ hack look
    def hack_rgb(self, rgb, now, hk, restore_row=None):
        lum = (rgb[..., 0] * 0.3 + rgb[..., 1] * 0.55 + rgb[..., 2] * 0.15) / 255.0
        l = np.clip(lum * 2.2, 0, 1)[..., None]
        dark = np.array((14, 0, 20), np.float32)
        mid = np.array((235, 20, 120), np.float32)
        hi = np.array((255, 210, 240), np.float32)
        out = np.where(l < 0.5, dark + (mid - dark) * (l * 2), mid + (hi - mid) * (l * 2 - 1))
        out[1::4] *= 0.72
        rng = np.random.default_rng(int(now * 7))
        for _ in range(3):
            y0 = int(rng.integers(0, rgb.shape[0] - 4))
            hgt = int(rng.integers(2, 7))
            out[y0:y0 + hgt] = np.roll(out[y0:y0 + hgt], int(rng.integers(-9, 9)), axis=1)
        if int(now * 5) % 3 == 0:
            out[..., 2] = np.roll(out[..., 2], 2, axis=1)
        mask = None
        if hk < 0.9 and self.here:
            q = self.proj(self.here[0], self.here[1])
            cx, cy = (q[0], q[1]) if q else (self.w / 2, self.ph * 0.75)
            rad = 4 + (hk / 0.9) ** 1.4 * self.w * 1.1
            yy, xx = np.ogrid[:rgb.shape[0], :rgb.shape[1]]
            dd = np.hypot(xx - cx, yy - cy)
            mask = dd < rad
            ring = (dd >= rad) & (dd < rad + 2.5)
            out = np.where(mask[..., None], out, rgb)
            out[ring] = (255, 230, 245)
        if restore_row is not None:
            out[:restore_row] = rgb[:restore_row]
            r0 = max(0, restore_row)
            out[r0:r0 + 2] = (240, 250, 255)
        return np.clip(out, 0, 255).astype(np.uint8)

    def draw_big_skull(self, s, now, hk):
        rows, cols = len(SKULL_BIG), len(SKULL_BIG[0])
        avail = (s.h - self.top - 4) * 2
        k = max(1, min(int(avail * 0.62 / rows), int(s.w * 0.4 / cols)))
        left = (s.w - cols * k) // 2
        top = self.top * 2 + (avail - rows * k) // 2 + 2
        a = min(1.0, (hk - 0.5) / 0.6) * (0.22 + 0.1 * pulse(now, 5))
        pr, pg, pbb = PINK
        odd = int(now * 12) & 1
        for j, row in enumerate(SKULL_BIG):
            for yy in range(top + j * k, top + j * k + k):
                if (yy & 1) == odd or not 0 <= yy < s.ph:
                    continue
                layer = (s.pb if yy & 1 else s.pt)[yy >> 1]
                for i, ch in enumerate(row):
                    if ch != "X":
                        continue
                    for xx in range(max(0, left + i * k), min(s.w, left + i * k + k)):
                        c = layer[xx]
                        if c is not None:
                            layer[xx] = (int(c[0] + (pr - c[0]) * a), int(c[1] + (pg - c[1]) * a),
                                         int(c[2] + (pbb - c[2]) * a))

    def draw_hack_banner(self, s, now, hk):
        msg = ["NUDLE MAPS // HACKED BY DEDSEC", "YOUR ROUTE IS OURS NOW  -  #DEDSEC"]
        bw = max(len(m) for m in msg) + 8
        x = (s.w - bw) // 2
        y = s.h // 2 - 2
        if hk < 0.6:
            return
        if (hk % 1.6) < 1.3:
            col = PINK if int(now * 6) % 2 else YELLOW
            self.panel(s, x, y, bw, 4, bg=(20, 0, 16), edge=col, rounded=False)
            s.text(x, y, "╔" + "═" * (bw - 2) + "╗", col)
            s.text(x, y + 3, "╚" + "═" * (bw - 2) + "╝", col)
            s.put(x, y + 1, "║", col)
            s.put(x, y + 2, "║", col)
            s.put(x + bw - 1, y + 1, "║", col)
            s.put(x + bw - 1, y + 2, "║", col)
            for i, m in enumerate(msg):
                mx = (s.w - len(m)) // 2
                if i == 0 and random.random() < 0.15:
                    m = "".join(random.choice("#%&@") if random.random() < 0.25 else c for c in m)
                s.text(mx, y + 1 + i, m, WHITE if i else col)

    def draw_restore_toast(self, s, now, t):
        msg = " NUDLE MAPS RESTORED  -  NOTHING HAPPENED. KEEP DRIVING. "
        if t > 0.9 and len(msg) + 4 < s.w:
            n = min(len(msg), int((t - 0.9) * 60))
            x = (s.w - len(msg)) // 2
            yy = s.h // 2 - 1
            self.panel(s, x, yy, n, 1, bg=blend(CYAN, WHITE, 0.25), edge=None)
            s.text(x, yy, msg[:n], BLACK)

    # ------------------------------------------------------------ flip transition
    def flip_rgb(self, old, new, u):
        """Map tiles flip up (around their horizontal axis) like cards to reveal the next view."""
        ph, w = old.shape[:2]
        y0 = self.top * 2
        nc = max(3, round(w / 36))
        nr = max(2, round((ph - y0) / 28))
        tw = w / nc
        th = (ph - y0) / nr
        yy = np.arange(ph)[:, None].astype(np.float32)
        xx = np.arange(w)[None, :].astype(np.float32)
        ty = np.clip(((yy - y0) // th).astype(np.int32), 0, nr - 1)
        tx = np.clip((xx // tw).astype(np.int32), 0, nc - 1)
        # a diagonal wave from the bottom-left; each card takes half of the transition to turn over
        delay = (tx / max(1, nc - 1)) * 0.32 + ((nr - 1 - ty) / max(1, nr - 1)) * 0.16
        a = np.clip((u - delay) / 0.5, 0, 1)
        a = a * a * (3 - 2 * a) * np.pi
        ca, sa = np.cos(a), np.sin(a)
        ycen = y0 + (ty + 0.5) * th
        xcen = (tx + 0.5) * tw
        v = (yy - ycen) / (th / 2)
        aca = np.maximum(np.abs(ca), 1e-3)
        vs = v / aca
        sc = 1 + 0.22 * sa * (-vs)                 # the edge tipping toward us gets wider
        xs = xcen + (xx - xcen) / np.maximum(sc, 0.2)
        valid = (np.abs(vs) <= 1) & (np.abs(xs - xcen) <= tw / 2 - 0.5) & (yy >= y0)
        sy = np.clip(ycen + vs * th / 2, 0, ph - 1).astype(np.int32)
        sx = np.clip(xs, 0, w - 1).astype(np.int32)
        src = np.where((ca >= 0)[..., None], old[sy, sx], new[sy, sx]).astype(np.float32)
        lit = (0.25 + 0.75 * aca) * (1 - 0.3 * sa * (vs + 1) / 2)
        out = src * lit[..., None]
        # card edge: a thin bright lip while the card is close to edge-on
        edge = valid & (aca < 0.35) & (np.abs(np.abs(vs) - 1) * th * aca / 2 < 0.8)
        lip = np.array((90, 170, 220), np.float32)
        out[edge] = out[edge] * 0.4 + lip * 0.6
        bg = np.empty_like(out)
        bg[:] = (4, 5, 12)
        gl = ((xx % tw) < 1) | (((yy - y0) % th) < 1)
        bg[np.broadcast_to(gl, (ph, w))] = (16, 26, 44)
        out = np.where(valid[..., None], out, bg)
        out[:y0] = np.where(u < 0.5, old[:y0], new[:y0])
        return np.clip(out, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------ main
    def current_cam(self, now):
        tr = self.trans
        if tr and tr["kind"] == "fly" and now < tr["start"] + tr["dur"]:
            v = _smooth((now - tr["start"]) / tr["dur"])
            a, b = tr["a"], tr["b"]
            span = math.hypot(b[0] - a[0], b[1] - a[1])
            dy = (b[4] - a[4] + math.pi) % (2 * math.pi) - math.pi
            bump = math.sin(math.pi * v) * min(1.6, span / max(a[2], b[2]) * 0.9)
            d = (a[2] + (b[2] - a[2]) * v) * (1 + bump)
            p = a[3] + (b[3] - a[3]) * v + 0.25 * math.sin(math.pi * v) * min(1.0, span / 4)
            return (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, d, min(1.25, p), a[4] + dy * v)
        if tr and tr["kind"] == "flip" and now < tr["start"] + tr["dur"]:
            return tr["a"] if now < tr["start"] else tr["b"]
        rf = self.reframe
        if rf:
            v = _smooth((now - rf["start"]) / rf["dur"])
            a, b = rf["a"], rf["b"]
            return tuple(a[i] + (b[i] - a[i]) * v for i in range(5))
        return tr["b"] if tr else self.cam

    def step(self, s, now):
        dt, self.last = min(0.1, max(0.0, now - self.last)), now
        if now > self.cycle_end:
            self.new_cycle(now)
        hacked = self.hack_start <= now < self.hack_until
        hk = now - self.hack_start
        glitch = self.glitch.active(now) or (hacked and hk < 0.5)

        # story beats
        if self.pins_at and now >= self.pins_at:
            self.pins = [p for p in self.pins if p.dying is None]
            self.drop_pins(now)
            self.pins_at = None
        if self.route_at and now >= self.route_at:
            self.make_route(now)
            self.route_at = None
        if hacked and not getattr(self, "_hack_burst", False):
            self._hack_burst = True
            self.glitch.trigger(now, 0.6)
        if not hacked:
            self._hack_burst = False
        if hacked and hk > 0.9 and (hk % 1.3) < 0.05:
            self.glitch.trigger(now, 0.12)
        self.pins = [p for p in self.pins if p.dying is None or now - p.dying < 0.6]

        cam = self.current_cam(now)
        self.set_cam(cam)
        tr = self.trans
        flipping = tr and tr["kind"] == "flip" and tr["start"] <= now < tr["start"] + tr["dur"]
        restoring = 0 <= now - self.hack_until < 0.9
        if flipping:
            if "old" not in tr:
                if self.layer_rows is not None and self.layer_key == tuple(round(v, 5) for v in tr["a"]):
                    tr["old"] = np.array(self.layer_rows, np.uint8)
                else:
                    tr["old"] = self.capture(tr["a"])
                tr["new"] = self.capture(tr["b"])
                self.layer_key = None
            u = (now - tr["start"]) / tr["dur"]
            rows = to_rows(self.flip_rgb(tr["old"], tr["new"], u))
            for y in range(s.h):
                s.pt[y] = rows[2 * y]
                s.pb[y] = rows[2 * y + 1]
        else:
            if tr and "old" in tr:
                tr.pop("old")
                tr.pop("new")
            moving = self.key != self.layer_key or self.layer_rows is None
            still = not (tr and tr["kind"] == "fly" and now < tr["start"] + tr["dur"]) and not (
                self.reframe and now < self.reframe["start"] + self.reframe["dur"])
            if moving:
                self.render_layer(s)
                if still:
                    self.layer_key = self.key
                    self.layer_rows = [r[:] for y in range(s.h) for r in (s.pt[y], s.pb[y])]
                    self.layer_rgb = None
                    self.layer_water = self.water_px
                else:
                    self.layer_key = None
                    self.layer_rows = None
            else:
                lr = self.layer_rows
                if hacked or restoring:
                    if self.layer_rgb is None:
                        self.layer_rgb = np.array(lr, np.uint8)
                    rr = None
                    if restoring:
                        rr = int((now - self.hack_until) / 0.9 * self.ph)
                    hkey = (int(now * 12), self.layer_key)
                    if getattr(self, "_hack_key", None) != hkey:
                        self._hack_key = hkey
                        self._hack_rows = to_rows(self.hack_rgb(self.layer_rgb.astype(np.float32), now, hk, rr))
                    lr = self._hack_rows
                    for y in range(s.h):
                        s.pt[y] = lr[2 * y][:]
                        s.pb[y] = lr[2 * y + 1][:]
                else:
                    for y in range(s.h):
                        s.pt[y] = lr[2 * y][:]
                        s.pb[y] = lr[2 * y + 1][:]
                    self.water_px = self.layer_water
                    self.draw_glints(s, now)
        if self.reframe and now >= self.reframe["start"] + self.reframe["dur"]:
            self.cam = self.reframe["b"]
            self.trans = None
            self.reframe = None
        elif self.trans and not flipping and now >= self.trans["start"] + self.trans["dur"] and not self.reframe:
            self.cam = self.trans["b"]

        self.occ = []
        if not flipping:
            if hacked and hk > 0.5:
                self.draw_big_skull(s, now, hk)
            self.draw_traffic(s, now, hacked)
            self.draw_cars(s, dt, hacked)
            self.draw_route(s, now, hacked)
            self.draw_labels(s, now, hacked)
            pins = sorted(self.pins, key=lambda p: -(self.proj(p.wx, p.wz) or (0, 0, 0))[2])
            for i, p in enumerate(pins):
                self.draw_pin(s, p, now, hacked, i)
            self.draw_car(s, now, hacked)
        self.particles.step(s, dt)
        self.draw_scene_title(s, now)
        self.draw_compass(s, now, hacked)
        self.draw_controls(s, now, hacked)
        self.draw_scale(s, hacked)
        self.draw_eta(s, now, hacked)
        self.draw_nav(s, now, hacked)
        self.draw_search(s, now, hacked)
        if hacked:
            self.draw_hack_banner(s, now, hk)
        elif 0 <= now - self.hack_until < 3.2:
            self.draw_restore_toast(s, now, now - self.hack_until)
        self.ticker.draw(s, s.h - 1, now)
        if glitch:
            self.fx.apply(s, now, True)

    def draw_glints(self, s, now):
        wp = self.water_px
        if wp is None:
            return
        rows, xs, U, V, T = wp
        v = np.sin(U * 31.0 + now * 1.7 + np.sin(V * 9.0)) * np.sin(V * 23.0 - now * 1.3)
        sel = np.nonzero(v > 0.93)[0]
        if not sel.size:
            return
        pt, pb = s.pt, s.pb
        for r, x, k in zip(rows[sel].tolist(), xs[sel].tolist(), v[sel].tolist()):
            row = (pb if r & 1 else pt)[r >> 1]
            c = row[x]
            if c is not None:
                a = (k - 0.93) * 6
                row[x] = (min(255, c[0] + int(60 * a)), min(255, c[1] + int(110 * a)), min(255, c[2] + int(150 * a)))

    def farewell(self, s, now, t):
        # The paper map folds into three hinged panels and is put away.
        old = getattr(self, "_exit_snapshot", None)
        if old is None:
            self.step(s, now)
            old = self._exit_snapshot = s.snapshot()
        t = max(0, min(1, t))
        if t >= 1:
            return
        k = max(.025, math.cos(t * math.pi / 2))
        panel = s.w / 3
        width = panel * k
        left = (s.w - 3 * width) / 2
        layers = (s.ch, s.fg, s.bg, s.pt, s.pb)
        for y in range(s.h):
            dy = int(y * (1 - t * .35) + s.h * t * .175)
            for x in range(int(left), int(left + 3 * width)):
                j = min(2, max(0, int((x - left) / width)))
                u = ((x - left) / width - j)
                sx = min(s.w - 1, max(0, int((j + u) * panel)))
                shade = (1 - t * .6) * (1 - .35 * math.sin(t * math.pi / 2) if j == 1 else 1)
                layers[0][dy][x] = old[0][y][sx]
                for n in range(1, 5):
                    col = old[n][y][sx]
                    if col is not None:
                        layers[n][dy][x] = tuple(int(c * shade) for c in col)
        for j in (1, 2):
            x = int(left + j * width)
            pline(s, x, int(s.h * t * .35), x, int(s.h * 2 * (1 - t * .175)), blend(CYAN, BLACK, t))
        if .1 < t < .85:
            s.center(s.h - 3, "NUDLE MAP / FOLDED", blend(CYAN, BLACK, t))


class _Canvas:
    """Minimal pixel target for off-screen captures (same layout as lib.Screen's pixel layer)."""

    def __init__(self, w, h):
        self.w, self.h, self.ph = w, h, 2 * h
        self.pt = [[None] * w for _ in range(h)]
        self.pb = [[None] * w for _ in range(h)]

    def pixel(self, x, py, color):
        if 0 <= x < self.w and 0 <= py < self.ph:
            (self.pb if py & 1 else self.pt)[py >> 1][x] = color

    def pixel_line(self, x0, y0, x1, y1, color):
        from lib import line_points
        for x, y in line_points(int(x0), int(y0), int(x1), int(y1)):
            self.pixel(x, y, color)

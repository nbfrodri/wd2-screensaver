"""SCOUTX: the ScoutX photo feed - tilted 3D grid of pixel-art SF photos, likes, hearts, filters, zoom."""

import math
import random
import time

import numpy as np

from lib import (BLACK, CYAN, DIM_CYAN, DIM_PINK, GREEN, GREY, ORANGE, PINK, PURPLE, WHITE,
                 YELLOW, Glitch, blend, ease_out, pulse)
from widgets import Particles, PostFX, Ticker

NAME = "SCOUTX"

# ------------------------------------------------------------------ palette
BASE = []


def C(rgb):
    rgb = tuple(int(max(0, min(255, c))) for c in rgb)
    if rgb in BASE:
        return BASE.index(rgb)
    BASE.append(rgb)
    return len(BASE) - 1


def G(a, b, n):
    return [C(blend(a, b, i / max(1, n - 1))) for i in range(n)]


BG = C((10, 6, 18))
BGLINE = C((26, 14, 42))
FRAME = C((226, 222, 236))
FRAME_HOT = C((255, 120, 190))
CAP = C((24, 18, 38))
SWEEP = C((255, 255, 255))
SWEEP2 = C((0, 229, 255))
SHADOW = C((4, 2, 8))

FILTERS = ["NORMAL", "NEON", "VHS", "INVERT", "DEDSEC"]
NVAR = 6   # normal, neon, vhs, vhs-dark, invert, dedsec


def lum(c):
    return (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]) / 255


def variants(c):
    L = lum(c)
    if L < 0.5:
        neon = blend((25, 0, 45), PINK, L / 0.5)
    else:
        neon = blend(PINK, CYAN, min(1, (L - 0.5) / 0.35)) if L < 0.85 else blend(CYAN, WHITE, (L - 0.85) / 0.15)
    # Retain source hues and continuous shading so landmarks survive the tint.
    neon = blend(c, neon, 0.38)
    g = int(L * 255)
    v = blend((g, g, g), c, 0.55)
    vhs = (v[0] * 0.85 + 30, v[1] * 0.8 + 18, v[2] * 0.9 + 40)
    vhs = tuple(min(255, int(x)) for x in vhs)
    vhsd = tuple(int(x * 0.62) for x in vhs)
    inv = (255 - c[0], 255 - c[1], 255 - c[2])
    ded = blend((12, 5, 22), (232, 110, 188), L)
    ded = blend(ded, c, 0.38)
    return [c, neon, vhs, vhsd, inv, ded]


# ------------------------------------------------------------------ scenes (index arrays)
def grid(w, h):
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    return u / max(1, w - 1), v / max(1, h - 1), w / h


def bands(v, idxs, v0=0.0, v1=1.0):
    k = np.clip((v - v0) / (v1 - v0), 0, 0.9999)
    return np.array(idxs, np.int16)[(k * len(idxs)).astype(np.int64)]


def ellipse(u, v, A, cu, cv, ru, rv=None):
    rv = ru if rv is None else rv
    return ((u - cu) * A / ru) ** 2 + ((v - cv) / rv) ** 2 < 1


SUNSET = G((40, 10, 70), (120, 30, 110), 3) + G((200, 50, 110), (255, 130, 60), 3) + [C((255, 190, 90))]
NIGHT = G((4, 4, 20), (30, 20, 70), 5)
DUSK = G((60, 40, 120), (240, 120, 150), 6)
SEA = G((10, 30, 70), (30, 70, 130), 4)


def sc_golden_gate(w, h):
    u, v, A = grid(w, h)
    img = bands(v, SUNSET, 0, 0.62)
    sun = ellipse(u, v, A, 0.62, 0.55, 0.13)
    img[sun] = C((255, 220, 120))
    img[sun & (v > 0.5) & ((v * h).astype(int) % 3 == 0)] = SUNSET[4]
    sea = v > 0.62
    img[sea] = bands(v, SEA, 0.62, 1)[sea]
    img[sea & ((((u * 37 + v * 91) * 7).astype(int) % 11) == 0)] = C((255, 160, 90))
    # hills
    img[(v > 0.5 + 0.25 * (u - 0.0) ** 0.5 * 0.4) & (u < 0.16) & (v < 0.66)] = C((30, 18, 40))
    img[(v > 0.42 + (1 - u) * 0.4) & (u > 0.82) & (v < 0.66)] = C((30, 18, 40))
    bridge = C((210, 60, 40))
    dark = C((120, 30, 30))
    deck = 0.6
    for tu in (0.3, 0.72):
        img[(np.abs(u - tu) < 0.02) & (v > 0.12) & (v < 0.7)] = bridge
        img[(np.abs(u - tu) < 0.025) & ((np.abs(v - 0.2) < 0.012) | (np.abs(v - 0.34) < 0.012))] = bridge
    mid = (0.3 + 0.72) / 2
    half = (0.72 - 0.3) / 2
    vc = np.where(np.abs(u - mid) < half, 0.13 + (deck - 0.02 - 0.13) * (1 - ((u - mid) / half) ** 2),
                  np.where(u < 0.3, 0.13 + (0.3 - u) / 0.3 * (deck - 0.13), 0.13 + (u - 0.72) / 0.28 * (deck - 0.13)))
    img[np.abs(v - vc) < 0.012] = bridge
    hang = ((u * w).astype(int) % 3 == 0) & (v > vc) & (v < deck)
    img[hang] = dark
    img[(v >= deck) & (v < deck + 0.035)] = bridge
    img[(v >= deck + 0.035) & (v < deck + 0.05)] = dark
    return img


def sc_ladies(w, h):
    u, v, A = grid(w, h)
    img = bands(v, DUSK, 0, 0.5)
    # skyline behind
    sk = ((np.sin(u * 40) > 0) * 0.04 + (np.sin(u * 17 + 1) > 0.3) * 0.06)
    img[v > 0.42 - sk] = C((50, 30, 80))
    img[(v > 0.42 - sk) & ((u * w).astype(int) % 4 == 1) & ((v * h).astype(int) % 3 == 0)] = C((240, 200, 90))
    cols = [(255, 150, 190), (150, 230, 200), (250, 220, 120), (190, 160, 240), (130, 200, 255)]
    n = 5
    for i in range(n):
        x0, x1 = 0.04 + i * 0.185, 0.04 + i * 0.185 + 0.17
        c = C(cols[i])
        trim = C(blend(cols[i], WHITE, 0.6))
        shade = C(blend(cols[i], BLACK, 0.35))
        body = (u >= x0) & (u < x1) & (v > 0.42) & (v < 0.82)
        mid = (x0 + x1) / 2
        roof = (v > 0.26 + np.abs(u - mid) / ((x1 - x0) / 2) * 0.16) & (v <= 0.42) & (u >= x0) & (u < x1)
        img[body | roof] = c
        img[roof & (v > 0.4)] = trim
        img[body & (u - x0 < 0.012)] = shade
        for wy in (0.48, 0.62):
            for wx in (0.25, 0.6):
                wm = (u > x0 + (x1 - x0) * wx) & (u < x0 + (x1 - x0) * (wx + 0.18)) & (v > wy) & (v < wy + 0.08)
                img[wm] = C((255, 240, 180)) if (i + int(wy * 10)) % 2 else C((40, 30, 60))
        img[(u > x0 + (x1 - x0) * 0.4) & (u < x0 + (x1 - x0) * 0.6) & (v > 0.72) & (v < 0.82)] = C((70, 40, 50))
        img[roof & ellipse(u, v, A, mid, 0.36, 0.015)] = C((255, 255, 255))
    park = v > 0.8 + 0.06 * np.sin(u * 3.3 + 0.4)
    img[park] = C((40, 140, 70))
    img[park & (((u * 53 + v * 37) * 3).astype(int) % 7 == 0)] = C((80, 190, 90))
    return img


def sc_alcatraz(w, h):
    u, v, A = grid(w, h)
    img = bands(v, NIGHT, 0, 0.6)
    rng = np.random.RandomState(4)
    stars = rng.rand(h, w) > 0.985
    img[stars & (v < 0.55)] = C((230, 230, 255))
    img[ellipse(u, v, A, 0.8, 0.16, 0.07)] = C((250, 245, 210))
    img[ellipse(u, v, A, 0.83, 0.14, 0.06)] = NIGHT[0]
    sea = v > 0.6
    img[sea] = bands(v, G((10, 20, 50), (20, 40, 90), 4), 0.6, 1)[sea]
    refl = sea & (np.abs(u - 0.78) < 0.02 + (v - 0.6) * 0.1) & ((v * h).astype(int) % 2 == 0)
    img[refl] = C((200, 200, 160))
    rock = (v > 0.6 - 0.12 * np.clip(1 - ((u - 0.42) / 0.3) ** 2, 0, 1)) & (v < 0.66) & (np.abs(u - 0.42) < 0.3)
    img[rock] = C((60, 45, 50))
    blds = (np.abs(u - 0.42) < 0.17) & (v > 0.45) & (v < 0.55)
    img[blds] = C((150, 150, 160))
    img[blds & ((u * w).astype(int) % 3 == 0) & ((v * h).astype(int) % 2 == 0)] = C((255, 220, 120))
    img[(np.abs(u - 0.31) < 0.012) & (v > 0.3) & (v < 0.5)] = C((235, 235, 235))
    img[(np.abs(u - 0.31) < 0.02) & (v > 0.28) & (v < 0.32)] = C((255, 240, 150))
    beam = (v > 0.27) & (v < 0.33) & (u > 0.31) & (np.abs(v - 0.3) < (u - 0.31) * 0.12) & (u < 0.75)
    img[beam & ((u * w).astype(int) % 2 == 0)] = C((120, 110, 80))
    return img


def sc_transamerica(w, h):
    u, v, A = grid(w, h)
    img = bands(v, G((0, 90, 120), (255, 120, 150), 6), 0, 1)
    sk = 0.55 + 0.1 * (np.sin(u * 23) > 0.2) + 0.08 * (np.sin(u * 51 + 2) > 0)
    city = v > sk
    img[city] = C((40, 25, 60))
    img[city & ((u * w).astype(int) % 3 == 0) & ((v * h).astype(int) % 3 == 1)] = C((255, 210, 100))
    half = 0.11 * (v - 0.08) / 0.92
    pyr = (np.abs(u - 0.5) < half) & (v > 0.08)
    img[pyr] = C((215, 215, 225))
    img[pyr & (u > 0.5)] = C((170, 170, 190))
    img[pyr & ((v * h).astype(int) % 3 == 0)] = C((120, 120, 140))
    img[(np.abs(u - 0.5) < 0.006) & (v > 0.02) & (v < 0.1)] = C((240, 240, 240))
    wing = (v > 0.4) & (v < 0.72) & (np.abs(u - 0.5) < half + 0.035) & ~pyr & (np.abs(u - 0.5) > half)
    img[wing] = C((150, 150, 170))
    img[(v > 0.92)] = C((20, 12, 30))
    return img


def sc_coit(w, h):
    u, v, A = grid(w, h)
    img = bands(v, SUNSET[::-1][2:] + SUNSET[:2], 0, 0.8)
    img = bands(v, G((255, 170, 90), (110, 40, 120), 6), 0, 0.85)
    hill = ellipse(u, v, A, 0.5, 1.15, 0.85 / A * 1.0, 0.55)
    img[hill] = C((30, 80, 50))
    img[hill & (((u * 41 + v * 29) * 5).astype(int) % 6 == 0)] = C((50, 120, 60))
    tower = (np.abs(u - 0.5) < 0.06) & (v > 0.18) & (v < 0.64)
    img[tower] = C((240, 225, 190))
    img[tower & (u > 0.52)] = C((200, 185, 150))
    img[(np.abs(u - 0.5) < 0.075) & (v > 0.16) & (v < 0.2)] = C((240, 225, 190))
    arches = tower & (v > 0.2) & (v < 0.27) & ((u * w).astype(int) % 3 == 0)
    img[arches] = C((60, 40, 50))
    img[(np.abs(u - 0.5) < 0.04) & (v > 0.12) & (v < 0.16)] = C((220, 205, 170))
    for tx in (0.2, 0.32, 0.7, 0.82):
        img[ellipse(u, v, A, tx, 0.7, 0.05)] = C((20, 60, 35))
    return img


def sc_cablecar(w, h):
    u, v, A = grid(w, h)
    img = bands(v, G((120, 180, 255), (250, 200, 220), 5), 0, 0.4)
    bay = (v > 0.3) & (v < 0.42)
    img[bay] = C((40, 90, 160))
    img[bay & ellipse(u, v, A, 0.72, 0.34, 0.05, 0.03)] = C((90, 80, 70))
    slope = 0.42 + (1 - u) * 0.12
    img[v > slope] = C((90, 90, 100))
    img[(v > slope) & (np.abs(v - slope - 0.18) < 0.012)] = C((160, 160, 170))
    img[(v > slope) & (np.abs(v - slope - 0.3) < 0.012)] = C((160, 160, 170))
    for x0, x1, c in ((0.0, 0.14, (180, 120, 140)), (0.86, 1.0, (120, 150, 190))):
        b = (u >= x0) & (u < x1) & (v > 0.12)
        img[b] = C(c)
        img[b & ((u * w).astype(int) % 4 == 1) & ((v * h).astype(int) % 4 == 1)] = C((255, 240, 200))
    # the car (sheared along slope)
    cu0, cu1 = 0.3, 0.68
    base = 0.42 + 0.5 * 0.12 + 0.24
    car = (u > cu0) & (u < cu1) & (v < base) & (v > base - 0.3)
    img[car] = C((200, 30, 40))
    img[car & (v < base - 0.22)] = C((240, 220, 170))
    img[car & (v > base - 0.2) & (v < base - 0.1) & (((u - cu0) * w).astype(int) % 5 > 0)] = C((255, 230, 150))
    img[(u > cu0 - 0.02) & (u < cu1 + 0.02) & (v < base - 0.3) & (v > base - 0.33)] = C((90, 20, 30))
    for wu in (0.36, 0.62):
        img[ellipse(u, v, A, wu, base + 0.01, 0.03)] = C((20, 20, 25))
    img[(np.abs(u - 0.49) < 0.003) & (v < base - 0.33) & (v > 0)] = C((40, 40, 40))
    return img


def sc_beach(w, h):
    u, v, A = grid(w, h)
    img = bands(v, G((60, 0, 90), (255, 60, 120), 6), 0, 0.55)
    sun = ellipse(u, v, A, 0.5, 0.5, 0.22)
    sb = bands(v, G((255, 230, 80), (255, 60, 140), 5), 0.28, 0.55)
    img[sun] = sb[sun]
    cut = sun & (v > 0.36) & (((v - 0.36) * h).astype(int) % 4 == 0)
    img[cut] = DUSK[1]
    sea = v > 0.55
    img[sea] = C((30, 10, 70))
    refl = sea & (np.abs(u - 0.5) < 0.18 - (v - 0.55) * 0.2) & ((v * h).astype(int) % 2 == 0)
    img[refl] = C((255, 120, 120))
    sand = v > 0.8 + 0.04 * np.sin(u * 5)
    img[sand] = C((90, 50, 80))
    # palm
    trunk = (np.abs(u - (0.17 + (0.9 - v) * 0.12)) < 0.012) & (v > 0.3) & (v < 0.9)
    img[trunk] = C((20, 5, 25))
    for ang in np.linspace(0, math.pi, 6):
        du, dv = math.cos(ang) * 0.14, -math.sin(ang) * 0.1 + 0.05
        for t in np.linspace(0, 1, 14):
            pu = 0.244 + du * t
            pv = 0.3 + dv * t + 0.08 * t * t
            img[ellipse(u, v, A, pu, pv, 0.012)] = C((20, 5, 25))
    return img


def sc_cat(w, h):
    u, v, A = grid(w, h)
    img = bands(v, G((255, 120, 180), (140, 60, 200), 5), 0, 1)
    img[((u * 7 + v * 5).astype(int) % 2 == 0) & (v > 0.85)] = C((120, 40, 160))
    fur = C((250, 150, 50))
    dark = C((190, 90, 30))
    head = ellipse(u, v, A, 0.5, 0.58, 0.3, 0.32)
    s = 0.3 / A
    for side in (-1, 1):
        cx = 0.5 + side * s * 0.62 * A / A
        ear = (v > 0.18) & (v < 0.42) & (np.abs(u - (0.5 + side * 0.18 * 0.3 / 0.3 * 0.62 / A * 1.0)) < (v - 0.18) * 0.5 / A)
        img[ear] = fur
        inner = ear & (np.abs(u - (0.5 + side * 0.186 / A)) < (v - 0.25) * 0.28 / A) & (v > 0.25)
        img[inner] = C((255, 160, 190))
    img[head] = fur
    img[head & (((u * A * 30).astype(int) % 5 == 0) & (v < 0.42))] = dark
    for side in (-1, 1):
        ex = 0.5 + side * 0.12 / A * 1.0
        img[ellipse(u, v, A, ex, 0.55, 0.06, 0.07)] = C((120, 230, 90))
        img[ellipse(u, v, A, ex, 0.55, 0.02, 0.06)] = C((10, 10, 10))
        img[ellipse(u, v, A, ex + 0.012 / A, 0.52, 0.012)] = C((255, 255, 255))
    muzzle = ellipse(u, v, A, 0.5, 0.74, 0.12, 0.09)
    img[muzzle] = C((255, 235, 220))
    img[ellipse(u, v, A, 0.5, 0.68, 0.03, 0.025)] = C((255, 110, 150))
    img[(np.abs(u - 0.5) < 0.004 * 3 / A) & (v > 0.69) & (v < 0.76)] = C((90, 40, 30))
    for side in (-1, 1):
        for dv in (-0.03, 0.0, 0.03):
            wl = (np.abs(v - (0.72 + dv + (np.abs(u - 0.5) - 0.12 / A) * 0.2 * dv * 20)) < 0.008) & \
                 (np.abs(u - 0.5) > 0.1 / A) & (np.abs(u - 0.5) < 0.32 / A) & ((u - 0.5) * side > 0)
            img[wl] = C((255, 255, 255))
    return img


def sc_billboard(w, h):
    u, v, A = grid(w, h)
    img = bands(v, NIGHT, 0, 1)
    sk = 0.5 + 0.12 * (np.sin(u * 19) > 0) + 0.1 * (np.sin(u * 47 + 1) > 0.4)
    city = v > sk
    img[city] = C((20, 14, 36))
    img[city & ((u * w).astype(int) % 3 == 1) & ((v * h).astype(int) % 3 == 0)] = C((0, 160, 200))
    bb = (np.abs(u - 0.5) < 0.26) & (v > 0.1) & (v < 0.6)
    img[bb] = C((20, 0, 24))
    img[bb & ((np.abs(u - 0.5) > 0.245) | (v < 0.115) | (v > 0.585))] = C((255, 15, 123))
    sk_ = ["..XXXXX..", ".XXXXXXX.", "XXXXXXXXX", "XX..X..XX", "XX..X..XX", "XXXXXXXXX", ".XXX.XXX.", "..X.X.X..",
           "..XXXXX.."]
    gu = (u - 0.5) / (0.42 / A) * 9 + 4.5
    gv = ((v - 0.14) / 0.42 * 9)
    gi, gj = gu.astype(int), gv.astype(int)
    mask = np.zeros_like(img, bool)
    arr = np.array([[c == "X" for c in r] for r in sk_])
    ok = (gi >= 0) & (gi < 9) & (gj >= 0) & (gj < 9) & bb & (gu >= 0) & (gv >= 0)
    mask[ok] = arr[gj[ok], gi[ok]]
    img[mask] = C((255, 15, 123))
    img[(np.abs(u - 0.38) < 0.008) & (v > 0.6) & (v < 0.9)] = C((40, 30, 50))
    img[(np.abs(u - 0.62) < 0.008) & (v > 0.6) & (v < 0.9)] = C((40, 30, 50))
    return img


SCENES = [("goldengate", sc_golden_gate), ("paintedladies", sc_ladies), ("alcatraz", sc_alcatraz),
          ("transamerica", sc_transamerica), ("coittower", sc_coit), ("cablecar", sc_cablecar),
          ("sunsetbeach", sc_beach), ("mr_whiskers", sc_cat), ("dedsec_billboard", sc_billboard)]

USERS = ["@retr0", "@sitara_art", "@wrench", "@josh_codes", "@horatio", "@ray_t-bone", "@marcus_h",
         "@scout_sf", "@not_blume", "@cat_lady_99", "@tidis_intern", "@dusan_n"]
COMMENTS = ["#DEDSEC was here", "nice pic!!", "who took this?? ctOS?", "filter on point",
            "first", "i was there", "blume is watching ->", "10/10 would hack again", "so aesthetic",
            "#HACKTHEPLANET", "that cat runs this city", "#NoFilter (lie)", "where is this", "follow back pls",
            "my fridge liked this", "#SanFrancisco", "this is art", "the fog tho"]
HEART = [".X.X.", "XXXXX", "XXXXX", ".XXX.", "..X.."]
BIG_HEART = ["..XX...XX..", ".XXXX.XXXX.", "XXXXXXXXXXX", "XXXXXXXXXXX", "XXXXXXXXXXX", ".XXXXXXXXX.",
             "..XXXXXXX..", "...XXXXX...", "....XXX....", ".....X....."]


def material_photo(fn, w, h):
    img = fn(w, h)
    yy, xx = np.mgrid[0:h, 0:w]
    original = img.copy()
    # Sparse horizontal glints for water; masonry seams for neutral building faces.
    for idx in np.unique(original):
        r, g, b = BASE[int(idx)]
        mask = original == idx
        if b > r*1.45 and g > r*1.25 and g < 100:
            detail = mask & ((yy % 4 == 0) & ((xx + yy*3) % 9 < 4))
            img[detail] = C(blend((r,g,b), (95,140,177), .28))
        elif min(r,g,b)>90 and max(r,g,b)-min(r,g,b)<65:
            seam = mask & ((yy % 6 == 0) | ((xx + (yy//6%2)*3)%9 == 0))
            img[seam] = C(blend((r,g,b), BLACK, .14))
        elif g > r*1.25 and g > b*1.15:
            foliage = mask & (((xx//2)*17+(yy//2)*13)%11 < 3)
            img[foliage] = C(blend((r,g,b), (133,165,79), .25))
    return img


def fmt(n):
    return "{:,}".format(int(n))


class Card:
    def __init__(self, r, c):
        rng = random.Random(r * 7919 + c * 104729)
        self.sid = rng.randrange(len(SCENES))
        self.filt = rng.choice((0, 0, 0, 0, 0, 1, 2, 4))
        self.newf = None
        self.sweep = None
        self.likes = rng.randint(80, 9000)
        self.rate = rng.choice((0.5, 1, 2, 4, 12))
        self.user = rng.choice(USERS)
        self.comment = rng.choice(COMMENTS)
        self.acc = 0.0
        self.pop = None


class Mode:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ph = 2 * h
        self.last = time.time()
        self.glitch = Glitch(0.005)
        self.fx = PostFX()
        self.particles = Particles()
        self.ticker = Ticker("SCOUTX", ["%s: %s" % (random.choice(USERS), c) for c in random.sample(COMMENTS, 10)] +
                             ["#DEDSEC trending in SF", "#TOPSCOUT of the week: you"], color=PINK)
        self.top = 3
        self.bottom = h - 2
        # card geometry (pixels in feed space)
        self.ncols = max(2, min(5, w // 46))
        self.gap = 4
        self.pw = int((w * 0.92) / self.ncols) - self.gap - 2
        self.phh = max(12, int(self.pw * 0.6))
        self.cap = 7
        self.pitchX = self.pw + 2 + self.gap
        self.pitchY = self.phh + 2 + self.cap + self.gap
        self.feedW = self.pitchX * self.ncols - self.gap
        # scene atlases
        self.atlas = np.stack([material_photo(fn, self.pw, self.phh) for _, fn in SCENES])
        self.full_h = (self.bottom - self.top) * 2
        self.full = None
        self.N = len(BASE)
        self.make_palettes()
        # camera
        self.f = self.ph * 1.7
        self.cx, self.cy = w / 2, (self.top * 2 + self.bottom * 2) / 2
        xs = (np.arange(w) - self.cx) / self.f
        ys = (np.arange(self.ph) - self.cy) / self.f
        self.dx = np.ascontiguousarray(np.broadcast_to(xs[None, :], (self.ph, w)), np.float32)
        self.dy = np.ascontiguousarray(np.broadcast_to(ys[:, None], (self.ph, w)), np.float32)
        self.scroll = 0.0
        self.cards = {}
        self.hearts = []
        self.followers = random.randint(1_200_000, 1_400_000)
        self.next_filter = self.last + 2.0
        self.next_zoom = self.last + 9.0
        self.zoom = None
        self.flash = 0.0

    def make_palettes(self):
        N = len(BASE)
        pal = []
        for var in range(NVAR):
            pal += [variants(c)[var] for c in BASE]
        self.pal = pal
        self.flash_pals = [[blend(c, WHITE, k) for c in pal] for k in (0.25, 0.5, 0.75, 0.95)]
        self.dim_pal = [blend(c, BLACK, 0.55) for c in pal]

    def card(self, r, c):
        k = (r, c)
        cd = self.cards.get(k)
        if cd is None:
            cd = self.cards[k] = Card(r, c)
            if len(self.cards) > 200:
                for kk in sorted(self.cards)[:60]:
                    del self.cards[kk]
        return cd

    # ------------------------------------------------------------ geometry
    def plane(self, now):
        a = 0.42 + 0.06 * math.sin(now * 0.21)
        b = 0.16 * math.sin(now * 0.13)
        D = self.f
        eX = np.array([math.cos(b), 0.0, -math.sin(b)])
        eY = np.array([-math.sin(a) * math.sin(b), math.cos(a), -math.sin(a) * math.cos(b)])
        P0 = np.array([0.0, 0.0, D])
        return P0, eX, eY

    def forward(self, X, Y):
        """feed-plane point (centred coords) -> screen pixel (x, py) and scale"""
        P0, eX, eY = self._geo
        px = P0[0] + X * eX[0] + Y * eY[0]
        py = P0[1] + X * eX[1] + Y * eY[1]
        pz = P0[2] + X * eX[2] + Y * eY[2]
        if pz < 10:
            return None
        return self.cx + self.f * px / pz, self.cy + self.f * py / pz, self.f / pz

    def feed_to_screen(self, fx, fy):
        return self.forward(fx - self.feedW / 2, fy - self.scroll)

    # ------------------------------------------------------------ raster
    def raster(self, s, now):
        P0, eX, eY = self._geo
        n = np.cross(eX, eY)
        dx, dy = self.dx, self.dy
        den = n[0] * dx + n[1] * dy + n[2]
        t = (n @ P0) / den
        hx, hy, hz = t * dx - P0[0], t * dy - P0[1], t - P0[2]
        X = hx * eX[0] + hy * eX[1] + hz * eX[2]
        Y = hx * eY[0] + hy * eY[1] + hz * eY[2]
        Xf = X + self.feedW / 2
        Yf = Y + self.scroll
        col = np.floor(Xf / self.pitchX).astype(np.int64)
        row = np.floor(Yf / self.pitchY).astype(np.int64)
        lx = (Xf - col * self.pitchX).astype(np.int64)
        ly = (Yf - row * self.pitchY).astype(np.int64)
        r0, r1 = int(row.min()), int(row.max())
        nr = r1 - r0 + 1
        nc = self.ncols
        sid = np.zeros((nr, nc), np.int64)
        filt = np.zeros((nr, nc), np.int64)
        newf = np.zeros((nr, nc), np.int64)
        swp = np.full((nr, nc), -999, np.int64)
        hot = np.zeros((nr, nc), bool)
        for r in range(r0, r1 + 1):
            for c in range(nc):
                cd = self.card(r, c)
                sid[r - r0, c] = cd.sid
                filt[r - r0, c] = cd.filt
                if cd.sweep is not None:
                    newf[r - r0, c] = cd.newf
                    swp[r - r0, c] = int(cd.sweep)
                hot[r - r0, c] = cd.pop is not None and now - cd.pop < 0.6
        inside = (col >= 0) & (col < nc)
        cc = np.clip(col, 0, nc - 1)
        rr = row - r0
        pw, phh = self.pw, self.phh
        photo = inside & (lx >= 1) & (lx <= pw) & (ly >= 1) & (ly <= phh)
        cardm = inside & (lx < pw + 2) & (ly < phh + 2 + self.cap)
        capm = cardm & (ly >= phh + 2)
        img = np.full(lx.shape, BG, np.int64)
        # background grid
        img[((Yf.astype(np.int64) % 12) == 0) | ((Xf.astype(np.int64) % 16) == 0)] = BGLINE
        # drop shadow
        sh = inside & (lx >= 2) & (lx < pw + 4) & (ly >= 2) & (ly < phh + 4 + self.cap) & ~cardm
        img[sh] = SHADOW
        img[cardm] = np.where(hot[rr, cc], FRAME_HOT, FRAME)[cardm]
        img[capm] = CAP
        ix = np.clip(lx - 1, 0, pw - 1)
        iy = np.clip(ly - 1, 0, phh - 1)
        base = self.atlas[sid[rr, cc], iy, ix]
        sw = swp[rr, cc]
        var = np.where(lx - 1 < sw, newf[rr, cc], filt[rr, cc])
        var = np.where(var == 2, 2 + (ly & 1), np.where(var >= 3, var + 1, var))
        pix = var * self.N + base
        img = np.where(photo, pix, img)
        band = photo & (np.abs(lx - 1 - sw) < 2)
        img = np.where(band, np.where((ly % 3) == 0, SWEEP2, SWEEP), img)
        if swp.max() > -999:
            nz = np.nonzero(band)
            if nz[0].size:
                keep = np.random.rand(nz[0].size) < 0.3
                img[nz[0][keep], nz[1][keep]] = PINK_IDX
        return img, (r0, r1)

    def blit(self, s, img):
        k = self.flash
        if k > 0.05:
            pal = self.flash_pals[min(3, int(k * 4))]
        elif self.zoom is not None and self.zoom["phase"] != "out":
            pal = self.pal
        else:
            pal = self.pal
        g = pal.__getitem__
        L = img.tolist()
        for y in range(self.top, self.bottom):
            s.pt[y] = list(map(g, L[2 * y]))
            s.pb[y] = list(map(g, L[2 * y + 1]))

    # ------------------------------------------------------------ overlays
    def draw_captions(self, s, now, rows):
        r0, r1 = rows
        for r in range(r0, r1 + 1):
            for c in range(self.ncols):
                cd = self.card(r, c)
                fx = c * self.pitchX + 1
                fy = r * self.pitchY + self.phh + 2
                q = self.feed_to_screen(fx + 1, fy + 2.6)
                if not q:
                    continue
                x, py, k = q
                y = int(py) // 2
                if not (self.top <= y < self.bottom - 1):
                    continue
                q2 = self.feed_to_screen(fx + self.pw, fy + 2.6)
                maxw = int(q2[0] - x) if q2 else self.pw
                x = int(round(x))
                capc = self.pal[CAP]
                like = "<3 " + fmt(cd.likes)
                hotc = PINK if (cd.pop and now - cd.pop < 0.5) else blend(PINK, WHITE, 0.2)
                self.ctext(s, x, y, like[:maxw], hotc, capc)
                if maxw > len(like) + len(cd.user) + 4:
                    self.ctext(s, x + maxw - len(cd.user) - 2, y, "◉", PINK, capc)
                    self.ctext(s, x + maxw - len(cd.user), y, cd.user, CYAN, capc)
                if y + 1 < self.bottom and k > 0.93:
                    cm = cd.comment[:maxw]
                    self.ctext(s, x, y + 1, cm, YELLOW if cm.startswith("#") else (200, 190, 220), capc)
                # filter name tag during sweep
                if cd.sweep is not None:
                    qq = self.feed_to_screen(fx + self.pw / 2, r * self.pitchY + self.phh / 2)
                    if qq:
                        tag = " FILTER: %s " % FILTERS[[0, 1, 2, 3, 4][min(4, cd.newf)]]
                        ty = int(qq[1]) // 2
                        if self.top <= ty < self.bottom:
                            self.ctext(s, int(qq[0]) - len(tag) // 2, ty, tag, BLACK, YELLOW)

    def ctext(self, s, x, y, txt, col, bg):
        if not 0 <= y < s.h:
            return
        rc, rf, rb, rt, rp = s.ch[y], s.fg[y], s.bg[y], s.pt[y], s.pb[y]
        for i, ch in enumerate(txt):
            xx = x + i
            if 0 <= xx < s.w:
                rc[xx] = ch
                rf[xx] = col
                rb[xx] = bg
                rt[xx] = rp[xx] = None

    def draw_hearts(self, s, dt, now):
        alive = []
        for hz in self.hearts:
            hz[4] += dt
            if hz[4] > hz[5]:
                continue
            hz[0] += hz[2] * dt + math.sin(hz[4] * 6 + hz[6]) * 0.4
            hz[1] += hz[3] * dt
            t = hz[4] / hz[5]
            col = blend(hz[7], BLACK, max(0, t - 0.5) * 1.6)
            x, y = int(hz[0]), int(hz[1])
            if y < self.top * 2 + 1:
                continue
            for j, row in enumerate(HEART):
                for i, ch in enumerate(row):
                    if ch == "X":
                        s.pixel(x + i - 2, y + j, col if j else blend(col, WHITE, 0.4))
            alive.append(hz)
        self.hearts = alive[-80:]

    def spawn_heart(self, x, py, big=False):
        self.hearts.append([x, py, random.uniform(-4, 4), random.uniform(-18, -10) * (1.5 if big else 1), 0.0,
                            random.uniform(1.2, 2.2), random.uniform(0, 6),
                            random.choice((PINK, (255, 60, 90), (255, 120, 200), PURPLE, (255, 40, 160)))])

    def draw_header(self, s, now):
        s.fill(0, 0, s.w, self.top)
        for x in range(s.w):
            s.set_bg(x, 0, (18, 8, 30))
            s.set_bg(x, 1, (18, 8, 30))
        logo = "ScoutX"
        for i, ch in enumerate(logo):
            s.put(2 + i, 0, ch, blend(PINK, CYAN, i / 5))
            s.set_bg(2 + i, 0, (18, 8, 30))
        s.text(9, 0, "◉", YELLOW if int(now * 2) % 2 else PINK)
        s.text(2, 1, "@retr0", CYAN)
        fol = "FOLLOWERS %s" % fmt(self.followers)
        fx = (s.w - len(fol) - 4) // 2
        s.text(fx, 0, fol, WHITE)
        s.text(fx + len(fol) + 1, 0, "▲", GREEN)
        gain = "+%d today" % (int(self.followers) % 9973)
        s.text(fx + (len(fol) - len(gain)) // 2, 1, gain, GREEN)
        # badge
        badge = " TOP SCOUT "
        bx = s.w - len(badge) - 3
        col = blend(YELLOW, ORANGE, pulse(now, 3))
        s.text(bx, 1, badge, BLACK)
        for i in range(len(badge)):
            s.set_bg(bx + i, 1, col)
        crown = "▲▲▲" if int(now * 2) % 2 else "▲ ▲"
        s.text(bx + len(badge) // 2 - 1, 0, crown, YELLOW)
        if s.w > 110:
            tabs = ["FEED", "TRENDING", "#DEDSEC", "NEARBY", "SAVED"]
            cur = int(now / 6) % len(tabs)
            x = 2
            for i, t in enumerate(tabs):
                s.text(x, 2, t, PINK if i == cur else GREY)
                if i == cur:
                    s.text(x, 2, t, WHITE)
                x += len(t) + 3
            s.text(x, 2, "▁" * max(0, (s.w - x - 2)), DIM_PINK)
            if s.w > 145:
                stories = "STORIES  ◉ M  ◉ W  ◉ S"
                sx = s.w - len(stories) - 3
                s.text(sx, 2, stories, DIM_PINK)
                for off in (9, 14, 19):
                    s.put(sx + off, 2, "◉", CYAN if off == 14 else PINK)
        else:
            s.text(0, 2, "▁" * s.w, DIM_PINK)

    # ------------------------------------------------------------ main
    def farewell(self, s, now, t):
        from cinematic import exit_scene
        exit_scene(self, s, now, t, "shutter", "SCOUTX / SHUTTER CLOSED", PINK)

    def step(self, s, now):
        dt, self.last = min(0.1, now - self.last), now
        glitch = self.glitch.active(now)
        speed = 9.0 if self.zoom is None else 2.0
        self.scroll += speed * dt
        self.followers += random.random() * 30 * dt * (8 if self.zoom else 1)
        self._geo = self.plane(now)

        if self.zoom is not None and self.zoom["phase"] == "hold" and getattr(self, "_img", None) is not None:
            img, rows = self._img
        else:
            img, rows = self.raster(s, now)
            self._img = (img, rows)
        r0, r1 = rows

        # likes ticking + hearts
        for r in range(r0, r1 + 1):
            for c in range(self.ncols):
                cd = self.card(r, c)
                cd.acc += cd.rate * dt * random.uniform(0.3, 1.7)
                if cd.acc >= 1:
                    n = int(cd.acc)
                    cd.likes += n
                    cd.acc -= n
                    if random.random() < 0.35:
                        q = self.feed_to_screen(c * self.pitchX + 3, r * self.pitchY + self.phh + 3)
                        if q and self.top * 2 < q[1] < self.bottom * 2:
                            self.spawn_heart(q[0] + 1, q[1] - 2)
                    if cd.rate >= 4 and random.random() < 0.01:
                        cd.pop = now
                if cd.sweep is not None:
                    cd.sweep += dt * self.pw / 0.9
                    if cd.sweep > self.pw + 3:
                        cd.filt, cd.sweep = cd.newf, None

        # filter sweeps
        if now > self.next_filter:
            self.next_filter = now + random.uniform(1.5, 3.0)
            r = random.randint(r0 + 1, max(r0 + 1, r1 - 1))
            cd = self.card(r, random.randrange(self.ncols))
            if cd.sweep is None:
                cd.newf = random.choice([f for f in (0, 0, 1, 1, 2, 3, 4) if f != cd.filt])
                cd.sweep = 0.0

        self.update_zoom(now, rows)
        if self.zoom is not None:
            self.draw_zoom(s, now, img)
        else:
            self.blit(s, img)
            self.draw_captions(s, now, rows)
        self.draw_hearts(s, dt, now)
        self.particles.step(s, dt)
        if self.zoom is not None:
            self.draw_zoom_ui(s, now)
        self.draw_header(s, now)
        self.ticker.draw(s, s.h - 1, now)
        if glitch:
            self.fx.apply(s, now, True)
        self.flash = max(0.0, self.flash - dt * 2.2)

    # ------------------------------------------------------------ zoom
    def update_zoom(self, now, rows):
        z = self.zoom
        if z is None:
            if now > self.next_zoom:
                r0, r1 = rows
                best = None
                for r in range(r0, r1 + 1):
                    for c in range(self.ncols):
                        q = self.feed_to_screen(c * self.pitchX + 1 + self.pw / 2, r * self.pitchY + 1 + self.phh / 2)
                        if q:
                            d = abs(q[0] - self.cx) + abs(q[1] - self.cy) * 2
                            if best is None or d < best[0]:
                                best = (d, r, c)
                if best:
                    _, r, c = best
                    self.zoom = {"r": r, "c": c, "start": now, "phase": "in", "likes0": self.card(r, c).likes}
                    cd = self.card(r, c)
                    if self.full is None or self.full[0] != cd.sid:
                        self.full = (cd.sid, material_photo(SCENES[cd.sid][1], self.w, self.full_h))
                        if len(BASE) != self.N:
                            self.N = len(BASE)
                            self.make_palettes()
            return
        age = now - z["start"]
        if z["phase"] == "in" and age > 0.5:
            z["phase"], z["start"] = "hold", now
            self.flash = 1.0
            for _ in range(10):
                self.spawn_heart(random.uniform(self.w * 0.3, self.w * 0.7), self.bottom * 2 - 4, big=True)
        elif z["phase"] == "hold" and age > 5.0:
            z["phase"], z["start"] = "out", now
        elif z["phase"] == "out" and age > 0.45:
            self.zoom = None
            self.next_zoom = now + random.uniform(10, 16)

    def card_rect(self, r, c):
        a = self.feed_to_screen(c * self.pitchX + 1, r * self.pitchY + 1)
        b = self.feed_to_screen(c * self.pitchX + 1 + self.pw, r * self.pitchY + 1 + self.phh)
        if not a or not b:
            return (self.w / 2 - 10, self.ph / 2 - 6, self.w / 2 + 10, self.ph / 2 + 6)
        return (a[0], a[1], b[0], b[1])

    def draw_zoom(self, s, now, img):
        z = self.zoom
        age = now - z["start"]
        if z["phase"] == "in":
            k = ease_out(age / 0.5)
        elif z["phase"] == "out":
            k = 1 - ease_out(age / 0.45)
        else:
            k = 1.0
        x0, y0, x1, y1 = self.card_rect(z["r"], z["c"])
        fx0, fy0, fx1, fy1 = 0, self.top * 2, self.w, self.bottom * 2
        X0 = int(x0 + (fx0 - x0) * k)
        Y0 = int(y0 + (fy0 - y0) * k)
        X1 = int(x1 + (fx1 - x1) * k)
        Y1 = int(y1 + (fy1 - y1) * k)
        X0, X1 = max(0, X0), min(self.w, X1)
        Y0, Y1 = max(self.top * 2, Y0), min(self.bottom * 2, Y1)
        cd = self.card(z["r"], z["c"])
        out = np.where(True, img, img)
        dimmed = True
        if X1 - X0 > 2 and Y1 - Y0 > 2:
            hi = self.full[1]
            Hh, Wh = hi.shape
            ys = np.clip(((np.arange(Y0, Y1) - Y0) / (Y1 - Y0) * Hh).astype(np.int64), 0, Hh - 1)
            xs = np.clip(((np.arange(X0, X1) - X0) / (X1 - X0) * Wh).astype(np.int64), 0, Wh - 1)
            sub = hi[ys][:, xs]
            var = cd.filt
            if var == 2:
                varr = (2 + (np.arange(Y0, Y1) & 1))[:, None]
            else:
                varr = var + 1 if var >= 3 else var
            out = out.copy()
            out[Y0:Y1, X0:X1] = varr * self.N + sub
            # frame
            out[max(self.top * 2, Y0 - 1), X0:X1] = FRAME
            if Y1 < self.bottom * 2:
                out[Y1, X0:X1] = FRAME
            if X0 > 0:
                out[Y0:Y1, X0 - 1] = FRAME
            if X1 < self.w:
                out[Y0:Y1, X1 - 1] = FRAME
        k_flash = self.flash
        L = out.tolist()
        if k_flash > 0.05:
            base = self.flash_pals[min(3, int(k_flash * 4))]
            dimp = base
        else:
            base = self.pal
            dimp = self.dim_pal
        gb, gd = base.__getitem__, dimp.__getitem__
        for y in range(self.top, self.bottom):
            r1, r2 = L[2 * y], L[2 * y + 1]
            if Y0 <= 2 * y < Y1 or Y0 <= 2 * y + 1 < Y1:
                full = X0 == 0 and X1 >= self.w
                t = list(map(gb if full and Y0 <= 2 * y < Y1 else gd, r1))
                b = list(map(gb if full and Y0 <= 2 * y + 1 < Y1 else gd, r2))
                if not full:
                    if Y0 <= 2 * y < Y1:
                        t[X0:X1] = map(gb, r1[X0:X1])
                    if Y0 <= 2 * y + 1 < Y1:
                        b[X0:X1] = map(gb, r2[X0:X1])
                s.pt[y], s.pb[y] = t, b
            else:
                s.pt[y] = list(map(gd, r1))
                s.pb[y] = list(map(gd, r2))

    def draw_zoom_ui(self, s, now):
        z = self.zoom
        if z["phase"] != "hold":
            return
        age = now - z["start"]
        cd = self.card(z["r"], z["c"])
        cd.likes += int(random.uniform(20, 160) * min(1, age))
        if random.random() < 0.5:
            self.spawn_heart(random.uniform(s.w * 0.75, s.w - 6), self.bottom * 2 - 6)
        # big double-tap heart
        if age < 1.2:
            sc = max(1, int(1 + ease_out(age / 0.4) * (3 if s.h > 30 else 2)))
            col = blend(WHITE, PINK, age / 1.2)
            hw, hh = len(BIG_HEART[0]) * sc, len(BIG_HEART) * sc
            ox, oy = s.w // 2 - hw // 2, (self.top + self.bottom) - hh // 2
            for j, row in enumerate(BIG_HEART):
                for i, ch in enumerate(row):
                    if ch == "X":
                        s.pixel_rect(ox + i * sc, oy + j * sc, sc, sc, col)
        # info panel
        name = SCENES[cd.sid][0]
        lines = [(cd.user, CYAN), ("#" + name, YELLOW), ("<3 " + fmt(cd.likes), PINK)]
        pw = max(len(t) for t, _ in lines) + 4
        x, y = 2, self.bottom - 6
        s.box(x, y, pw, 5, PINK)
        for i, (t, c) in enumerate(lines):
            s.text(x + 2, y + 1 + i, t, c)
        # comments sliding in on the right
        n = min(int(age * 1.6) + 1, 4 if s.h > 30 else 2)
        rng = random.Random(z["r"] * 31 + z["c"])
        for i in range(n):
            u = rng.choice(USERS)
            cmt = rng.choice(COMMENTS)
            t = "%s %s" % (u, cmt)
            slide = ease_out((age - i / 1.6) / 0.4)
            tx = int(s.w - (len(t) + 3) * slide)
            ty = self.top + 1 + i * 2
            self.ctext(s, tx - 1, ty, " " * (len(t) + 2), WHITE, (20, 8, 34))
            self.ctext(s, tx, ty, u, CYAN, (20, 8, 34))
            self.ctext(s, tx + len(u) + 1, ty, cmt, YELLOW if cmt.startswith("#") else WHITE, (20, 8, 34))
        # TOP SCOUT stamp
        if age > 1.5:
            st = ease_out((age - 1.5) / 0.3)
            badge = ["╔═══════════════╗", "║  TOP  SCOUT   ║", "║  ▲  #1 SF  ▲  ║", "╚═══════════════╝"]
            bx = s.w - len(badge[0]) - 3
            by = self.bottom - 6
            if st > 0.2:
                col = YELLOW if int(now * 4) % 2 else ORANGE
                for i, l in enumerate(badge):
                    self.ctext(s, bx, by + i, l, col, (30, 10, 0))
                if st < 0.6:
                    self.particles.burst(bx + 8, by + 2, 6, (YELLOW, ORANGE, WHITE), speed=10)
        if age < 0.3:
            s.center((self.top + self.bottom) // 2 + 4, " * SNAP * ", BLACK)


PINK_IDX = C(PINK)

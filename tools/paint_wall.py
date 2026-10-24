"""
paint_wall.py — Mur de ruelle japonaise peint pixel par pixel (32 px = 1 m).

Produit dans assets/env/ :
  wall.png         couleurs (palette limitée, ombres de contact peintes, pas de lumière directionnelle)
  wall_normal.png  normal map (OpenGL) calculée depuis une carte de hauteur peinte en même temps
  wall_emit.png    parties lumineuses (lanternes, néons, distributeurs, vitrines)
  wall_lights.json lumières 3D à placer devant les éléments lumineux + portes + fenêtres

Usage : python3 tools/paint_wall.py assets/env
"""
import sys, os, json, math
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/env"
PX = 32                      # pixels par mètre
W, H = 46 * PX, 5 * PX       # 1472 x 160
WALL_X0 = -3.0               # position monde du bord gauche du mur
rng = np.random.default_rng(1987)

def hexc(s):
    s = s.lstrip("#"); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)

P = {k: hexc(v) for k, v in {
    # béton (bleu-gris froid)
    "c0": "1b1d26", "c1": "262935", "c2": "313543", "c3": "3d4252", "c4": "4c5264", "c5": "5f6679",
    # bois
    "w0": "24160f", "w1": "3a2418", "w2": "513322", "w3": "6b452d", "w4": "88593a", "w5": "a8744c",
    # métal
    "m0": "16191e", "m1": "252a31", "m2": "353c45", "m3": "4b545f", "m4": "66717d", "m5": "8b96a1", "m6": "b4bec6",
    # tissus
    "r0": "3d0d14", "r1": "6b1620", "r2": "9a2330", "r3": "c8374a",
    "b0": "10152e", "b1": "1c284f", "b2": "2c3d76", "b3": "4560a8",
    # lumière chaude (émissif)
    "y0": "5a2e10", "y1": "a85d22", "y2": "e89a40", "y3": "ffd387", "y4": "fff2cf",
    # lanternes
    "l0": "5c120c", "l1": "a8241a", "l2": "e8452a", "l3": "ff8a4a", "l4": "ffc890",
    # végétation
    "g0": "0e1c13", "g1": "17301e", "g2": "234a2b", "g3": "33673a", "g4": "4b8a4c",
    # sacs poubelle, papier, terre cuite
    "k0": "0b0c10", "k1": "16181e", "k2": "242730", "k3": "3a3f4c",
    "p0": "6e6658", "p1": "948a76", "p2": "b8ad94",
    "t0": "4a2216", "t1": "7a3a22", "t2": "a35532",
    # néons / écrans
    "np": "ff3d8b", "npd": "6b1a3d", "nc": "3de8ff", "ncd": "15596b", "ng": "7dff6a", "ngd": "2a5e28",
    "vw": "e8f0f8", "vb": "2a6fd4", "vbd": "173a73",
    "white": "f2efe6", "black": "07080b",
}.items()}

ALB = np.zeros((H, W, 3), np.uint8)
ALPHA = np.full((H, W), 255, np.uint8)
HGT = np.zeros((H, W), np.float32)
EMI = np.zeros((H, W, 3), np.uint8)
LIGHTS = []                  # (x monde, y monde, couleur, énergie, portée)
DOORS, WINDOWS = [], []

def wx(px): return WALL_X0 + px / PX          # pixel → mètres monde
def wy(py): return (H - py) / PX

# ---------------------------------------------------------------- outils de peinture
def rect(x, y, w, h, col, hgt=None, emi=None):
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0: return
    ALB[y0:y1, x0:x1] = P[col] if isinstance(col, str) else col
    if hgt is not None: HGT[y0:y1, x0:x1] = hgt
    if emi is not None: EMI[y0:y1, x0:x1] = P[emi] if isinstance(emi, str) else emi

def px(x, y, col, hgt=None, emi=None):
    if 0 <= x < W and 0 <= y < H:
        ALB[y, x] = P[col] if isinstance(col, str) else col
        if hgt is not None: HGT[y, x] = hgt
        if emi is not None: EMI[y, x] = P[emi] if isinstance(emi, str) else emi

def hline(x, y, w, col, hgt=None, emi=None): rect(x, y, w, 1, col, hgt, emi)
def vline(x, y, h, col, hgt=None, emi=None): rect(x, y, 1, h, col, hgt, emi)

def frame(x, y, w, h, col, hgt=None):
    hline(x, y, w, col, hgt); hline(x, y + h - 1, w, col, hgt)
    vline(x, y, h, col, hgt); vline(x + w - 1, y, h, col, hgt)

def bevel(x, y, w, h, light, dark):
    """Arête haute/gauche claire, basse/droite sombre (lecture du volume)."""
    hline(x, y, w, light); vline(x, y, h, light)
    hline(x, y + h - 1, w, dark); vline(x + w - 1, y, h, dark)

def contact_shadow(x, y, w, depth=2):
    """Ombre de contact sous un objet en saillie (occlusion ambiante peinte)."""
    for i in range(depth):
        for xx in range(x, x + w):
            if 0 <= xx < W and 0 <= y + i < H and (i == 0 or (xx + i) % 2 == 0):
                ALB[y + i, xx] = (ALB[y + i, xx] * 0.6).astype(np.uint8)

def dither(x, y, w, h, c1, c2, k=0.5):
    """Dithering ordonné 2x2 entre deux couleurs (k = proportion de c2)."""
    bayer = np.array([[0, 2], [3, 1]]) / 4 + 0.125
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(xx, yy, c2 if bayer[yy % 2, xx % 2] < k else c1)

def cylinder_v(x, y, h, width, ramp, hmax=3.0):
    """Tuyau vertical : rampe de couleurs + profil de hauteur arrondi."""
    for i in range(width):
        t = i / max(1, width - 1)
        idx = int(round((1 - abs(t - 0.35) * 1.6) * (len(ramp) - 1)))
        idx = max(0, min(len(ramp) - 1, idx))
        vline(x + i, y, h, ramp[idx], hgt=hmax * math.sin(math.pi * (i + 0.5) / width))

def cylinder_h(x, y, w, width, ramp, hmax=2.5):
    for i in range(width):
        t = i / max(1, width - 1)
        idx = int(round((1 - abs(t - 0.3) * 1.6) * (len(ramp) - 1)))
        idx = max(0, min(len(ramp) - 1, idx))
        hline(x, y + i, w, ramp[idx], hgt=hmax * math.sin(math.pi * (i + 0.5) / width))

def glyph(x, y, rows, col, hgt=3.5, emi=None, halo=None):
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == "#":
                px(x + i, y + j, col, hgt, emi)
    if halo:
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch == "#":
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + i + dx, y + j + dy
                        if 0 <= xx < W and 0 <= yy < H and EMI[yy, xx].sum() == 0:
                            EMI[yy, xx] = (P[halo] * 0.35).astype(np.uint8)

KATA = {
    "ra": [".#####.", ".......", "#######", ".....#.", "....#..", "...#...", ".##...."],
    "-v": ["...#...", "...#...", "...#...", "...#...", "...#...", "...#...", "...#..."],
    "me": [".....#.", ".....#.", ".#..#..", "..##...", "...##..", "..#..#.", "##....."],
    "n":  ["#......", ".#.....", ".....#.", ".....#.", "....#..", "..##...", "##....."],
    "sa": ["..#.#..", "#######", "..#.#..", "..#.#..", "....#..", "...#...", ".##...."],
    "ke": [".#.....", ".######", "#...#..", "....#..", "....#..", "...#...", "..#...."],
}
LATIN = {
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
}

def light(px_x, px_y, col, energy, rng_m=4.0, z=-2.0, flicker=False):
    LIGHTS.append(dict(x=round(wx(px_x), 3), y=round(wy(px_y), 3), z=z,
                       color=[round(c / 255, 3) for c in P[col]], energy=energy, range=rng_m, flicker=flicker))

# ---------------------------------------------------------------- 1. béton
def concrete():
    # bruit basse fréquence → variations de teinte par plaques
    lo = rng.random((H // 8 + 2, W // 8 + 2))
    lo = np.kron(lo, np.ones((8, 8)))[:H, :W]
    fine = rng.random((H, W))
    v = lo * 0.6 + fine * 0.4
    ramp = ["c1", "c2", "c2", "c3", "c3", "c4"]
    idx = np.clip((v * len(ramp)).astype(int), 0, len(ramp) - 1)
    for i, k in enumerate(ramp):
        ALB[idx == i] = P[k]
    # joints de banches (dalles 64 x 40) + trous de coffrage
    for y in range(0, H, 40):
        hline(0, y, W, "c1", -1); hline(0, y + 1, W, "c4")
    for row, y in enumerate(range(0, H, 40)):
        off = 32 if row % 2 else 0
        for x in range(off, W, 64):
            vline(x, y, 40, "c1", -1); vline(x + 1, y, 40, "c4")
            for hx, hy in ((x + 12, y + 10), (x + 52, y + 10), (x + 12, y + 30), (x + 52, y + 30)):
                px(hx, hy, "c0", -1); px(hx + 1, hy, "c1", -0.5)
    # coulures (sous le bord supérieur et sous les dalles)
    for _ in range(260):
        x = int(rng.integers(0, W)); y = int(rng.choice([0, 40, 80])) + 2
        L = int(rng.integers(6, 34))
        for i in range(L):
            if rng.random() < 0.8 - i / L * 0.5:
                ALB[y + i, x] = (ALB[y + i, x] * 0.78).astype(np.uint8)
    # fissures
    for _ in range(14):
        x, y = int(rng.integers(0, W)), int(rng.integers(10, H - 30))
        for _ in range(int(rng.integers(8, 22))):
            px(x, y, "c0", -1.2)
            x += int(rng.integers(-1, 2)); y += 1
    # crasse et humidité en pied de mur
    for y in range(H - 18, H):
        k = (y - (H - 18)) / 18
        for x in range(W):
            if rng.random() < k * 0.9:
                ALB[y, x] = (ALB[y, x] * (0.55 + 0.2 * rng.random())).astype(np.uint8)
    # acrotère (rebord du toit)
    rect(0, 0, W, 4, "c4", 3); hline(0, 0, W, "c5", 3); hline(0, 4, W, "c0", 0); contact_shadow(0, 5, W, 2)

# ---------------------------------------------------------------- 2. éléments
def pipe_v(x, y0=4, y1=H, width=6, brackets=True):
    cylinder_v(x, y0, y1 - y0, width, ["m1", "m2", "m3", "m4", "m5"])
    if brackets:
        for y in range(y0 + 14, y1 - 6, 34):
            rect(x - 2, y, width + 4, 3, "m2", 4); hline(x - 2, y, width + 4, "m5", 4)
            px(x - 1, y + 1, "m0", 4); px(x + width, y + 1, "m0", 4)

def ac_unit(x, y, w=30, h=22):
    rect(x, y, w, h, "m4", 4)
    bevel(x, y, w, h, "m6", "m2")
    # grille du ventilateur
    cx, cy, r = x + w * 0.62, y + h / 2, h * 0.38
    for yy in range(y + 2, y + h - 2):
        for xx in range(x + 2, x + w - 2):
            d = math.hypot(xx - cx, yy - cy)
            if d < r:
                ring = int(d) % 2 == 0
                px(xx, yy, "m1" if ring else "m3", 3)
                if d < 2: px(xx, yy, "m5", 4)
    # ouïes latérales
    for yy in range(y + 3, y + h - 3, 2):
        hline(x + 3, yy, int(w * 0.28), "m2", 3.5)
    # pieds/équerres + évacuation
    rect(x + 2, y + h, 3, 3, "m2", 2); rect(x + w - 5, y + h, 3, 3, "m2", 2)
    contact_shadow(x, y + h, w, 3)
    hx = x + 4
    cylinder_v(hx, y + h, int(rng.integers(20, 50)), 2, ["m2", "m4"], 1.5)

def meter_box(x, y):
    rect(x, y, 10, 14, "m3", 3); bevel(x, y, 10, 14, "m5", "m1")
    rect(x + 2, y + 3, 6, 5, "p2", 3.5); px(x + 4, y + 5, "black", 3.5); px(x + 5, y + 5, "r2", 3.5)
    contact_shadow(x, y + 14, 10, 2)

def window_upper(x, y, w=40, h=28, mode="dark"):
    rect(x - 2, y - 2, w + 4, h + 5, "c3", 1)            # encadrement béton
    hline(x - 3, y + h + 1, w + 6, "c5", 2); hline(x - 3, y + h + 2, w + 6, "c1", 2)  # appui
    contact_shadow(x - 3, y + h + 3, w + 6, 2)
    if mode == "dark":
        rect(x, y, w, h, "b0", -1)
        for i in range(0, w, 3): px(x + i, y + int(rng.integers(0, h)), "b1", -1)
        dither(x, y, w // 3, h // 2, "b0", "b1", 0.3)     # reflet du ciel
    elif mode in ("warm", "blinds", "frost"):
        base = {"warm": "y2", "blinds": "y1", "frost": "y2"}[mode]
        rect(x, y, w, h, base, -1, base)
        if mode == "warm":
            dither(x, y + h - 8, w, 8, "y2", "y1", 0.5); EMI[y + h - 8:y + h, x:x + w] = P["y1"]
            # silhouette de plante + rideau
            for i in range(10):
                px(x + 4 + int(rng.integers(0, 7)), y + h - 3 - i, "g1", -1, "y0")
            rect(x + w - 9, y, 7, h, "r1", -0.5, "r0")
        if mode == "blinds":
            for yy in range(y, y + h, 3):
                hline(x, yy, w, "y3", -0.5, "y3"); hline(x, yy + 1, w, "y2", -0.5, "y2"); hline(x, yy + 2, w, "y0", -0.5, "y0")
        if mode == "frost":
            dither(x, y, w, h, "y2", "y3", 0.5)
            EMI[y:y + h, x:x + w] = (P["y2"] * 0.85).astype(np.uint8)
        WINDOWS.append([round(wx(x + w / 2), 3), round(wy(y + h / 2), 3)])
    frame(x, y, w, h, "m1", 1)
    vline(x + w // 2, y, h, "m1", 1)

def shutter(x, y, w, h):
    rect(x - 4, y - 10, w + 8, 10, "m2", 3)              # caisson
    bevel(x - 4, y - 10, w + 8, 10, "m4", "m0")
    for yy in range(y, y + h):
        k = (yy - y) % 4
        col = ["m4", "m3", "m2", "m1"][k]
        hline(x, yy, w, col, [2, 1.5, 1, 0.5][k])
    vline(x - 2, y, h, "m1", 3); vline(x - 1, y, h, "m3", 3)
    vline(x + w, y, h, "m3", 3); vline(x + w + 1, y, h, "m1", 3)
    rect(x, y + h - 4, w, 4, "m2", 2); hline(x, y + h - 4, w, "m5", 2)
    rect(x + w // 2 - 4, y + h - 3, 8, 2, "m0", 2)       # poignée
    # rouille
    for _ in range(140):
        rx, ry = x + int(rng.integers(0, w)), y + h - 1 - int(abs(rng.normal(0, h * 0.25)))
        if y <= ry < y + h: px(rx, ry, "t0" if rng.random() < 0.6 else "t1")
    # tag bombé : trait épais rose cerné de noir
    tx, ty = x + 16, y + h // 2 - 6
    pts = [(tx + i * 3, ty + 6 + int(6 * math.sin(i * 0.9)) + int(rng.integers(-1, 2))) for i in range(26)]
    for (ax, ay) in pts:
        for dy in range(-3, 4):
            for dx in range(-2, 3):
                px(ax + dx, ay + dy, "black")
    for (ax, ay) in pts:
        for dy in range(-2, 3):
            for dx in range(-1, 2):
                px(ax + dx, ay + dy, "np" if dy < 1 else "npd")
    for (ax, ay) in pts[::5]:
        px(ax, ay - 1, "white")
    for i in range(6):                                   # coulures de peinture
        dx_ = tx + 6 + i * 12
        vline(dx_, ty + 12, int(rng.integers(3, 9)), "npd")
    contact_shadow(x - 4, y, w + 8, 3)

def lightbox_sign(x, y, w, h, text, col, ink="black"):
    rect(x, y, w, h, "m1", 3); frame(x, y, w, h, "m3", 3.5)
    rect(x + 2, y + 2, w - 4, h - 4, col, 3, (P[col] * 0.55).astype(np.uint8))
    cx = x + (w - len(text) * 6) // 2 + 1
    for i, ch in enumerate(text):
        glyph(cx + i * 6, y + (h - 7) // 2, LATIN[ch], ink, 3.2, "black")
    light(x + w / 2, y + h / 2, col, 1.2, 3.5)

def neon_vertical(x, y, glyphs, col, dim):
    n = len(glyphs)
    w, h = 13, n * 10 + 4
    rect(x, y, w, h, "m0", 3); frame(x, y, w, h, "m2", 3.5)
    for i, g in enumerate(glyphs):
        glyph(x + 3, y + 3 + i * 10, KATA[g], col, 4, col, halo=col)
    rect(x + w // 2 - 1, y - 5, 2, 5, "m2", 2); rect(x + w // 2 - 1, y + h, 2, 4, "m2", 2)
    light(x + w / 2, y + h / 2, col, 2.6, 6.0, z=-1.6, flicker=True)

def lantern(x, y):
    """Akachōchin : lanterne en papier rouge."""
    w, h = 11, 15
    vline(x + w // 2, y - 6, 6, "black", 1)
    rect(x + 1, y, w - 2, 2, "black", 5); rect(x + 1, y + h - 2, w - 2, 2, "black", 5)
    for yy in range(y + 2, y + h - 2):
        t = (yy - y - 2) / (h - 5)
        half = int(round((w / 2) * math.sin(math.pi * (0.15 + 0.7 * t)) + 0.5))
        cx = x + w // 2
        for xx in range(cx - half, cx + half + 1):
            u = (xx - cx) / max(1, half)
            col = "l4" if abs(u) < 0.25 else ("l3" if abs(u) < 0.6 else "l2")
            if (yy - y) % 3 == 0: col = "l1"
            px(xx, yy, col, 5 * math.cos(u * 1.2), col)
    vline(x + w // 2, y + 5, 5, "black", 5); px(x + w // 2 - 1, y + 6, "black", 5); px(x + w // 2 + 1, y + 8, "black", 5)
    EMI[y + 5:y + 10, x + w // 2] = P["l1"]
    light(x + w / 2, y + h / 2, "l3", 2.2, 4.0, z=-2.1, flicker=False)

def noren(x, y, w, h):
    """Rideau de tissu au-dessus de l'entrée : 3 pans indigo, motif blanc."""
    rect(x - 3, y - 3, w + 6, 3, "w1", 3); hline(x - 3, y - 3, w + 6, "w4", 3)
    pan = w // 3
    for i in range(3):
        px0 = x + i * pan
        for yy in range(y, y + h):
            for xx in range(px0, px0 + pan - 1):
                col = "b2" if (xx - px0) > 1 else "b3"
                if yy == y + h - 1: col = "b1"
                px(xx, yy, col, 2); ALPHA[yy, xx] = 255
        # cercle blanc
        cx, cy = px0 + pan // 2, y + h // 2
        for yy in range(cy - 4, cy + 5):
            for xx in range(cx - 4, cx + 5):
                d = math.hypot(xx - cx, yy - cy)
                if 2.5 < d < 4.3: px(xx, yy, "white", 2.2)
    contact_shadow(x, y + h, w, 0)

def vending(x, y, body="vw"):
    w, h = 34, 62
    rect(x, y, w, h, body, 5)
    bevel(x, y, w, h, "white", "m3")
    vline(x + w - 3, y, h, "m4", 5); vline(x + w - 2, y, h, "m3", 5)
    rect(x + 3, y + 3, w - 8, 7, "vb", 5, "vb")              # bandeau lumineux
    for i in range(0, w - 10, 4): px(x + 5 + i, y + 6, "white", 5, "white")
    # vitrine éclairée : 3 rangées de bouteilles
    vx, vy, vw, vh = x + 3, y + 12, w - 8, 30
    rect(vx, vy, vw, vh, "vw", 4, (P["vw"] * 0.38).astype(np.uint8))
    cols = ["r2", "b3", "ng", "y2", "np", "nc", "l2", "g4"]
    for r in range(3):
        by = vy + 2 + r * 10
        hline(vx, by + 8, vw, "m4", 4, "m5")
        for c in range(6):
            bx = vx + 1 + c * 4
            colb = cols[(r * 3 + c * 5) % len(cols)]
            rect(bx, by + 2, 3, 6, colb, 4.5, (P[colb] * 0.7).astype(np.uint8))
            px(bx + 1, by + 1, "m6", 4.5, "m6")
            px(bx, by + 3, "white", 4.5, "white")
            rect(bx, by + 9, 3, 1, "black", 4, None)
            EMI[by + 9, bx + 1] = P["ng"]                     # voyants
    # fente, trappe
    rect(x + 3, y + 46, w - 8, 3, "m3", 4); rect(x + 18, y + 47, 6, 1, "black", 3)
    rect(x + 3, y + 52, w - 8, 7, "m1", 3); hline(x + 3, y + 52, w - 8, "m5", 3)
    contact_shadow(x, y + h, w, 0)
    light(x + w / 2, y + 28, "vw", 1.3, 4.0, z=-1.9)

def ramen_shop(x0, door_c):
    """Façade bois de l'échoppe, porte (ouverte) centrée sur door_c."""
    w, top = 210, 58
    # bardage bois horizontal
    for yy in range(top, H - 2):
        k = (yy - top) % 5
        col = ["w4", "w3", "w3", "w2", "w0"][k]
        hline(x0, yy, w, col, [1.5, 1.2, 1.0, 0.8, -0.5][k])
    for _ in range(90):
        gx, gy = x0 + int(rng.integers(0, w)), top + int(rng.integers(0, H - top))
        px(gx, gy, "w1")
    rect(x0, top - 4, w, 4, "w1", 3); hline(x0, top - 4, w, "w5", 3)  # corniche
    contact_shadow(x0, top, w, 2)
    # auvent en tuiles
    for yy in range(top - 14, top - 4):
        k = (yy - (top - 14))
        for xx in range(x0 - 6, x0 + w + 6):
            col = "m2" if (xx // 4 + yy // 3) % 2 else "m1"
            if k == 0: col = "m4"
            px(xx, yy, col, 4 + k * 0.2)
    hline(x0 - 6, top - 4, w + 12, "m0", 4); contact_shadow(x0 - 6, top - 3, w + 12, 3)
    # enseigne horizontale bois au-dessus de l'auvent
    sx, sy = door_c - 34, top - 30
    rect(sx, sy, 68, 14, "w1", 3); bevel(sx, sy, 68, 14, "w4", "w0")
    rect(sx + 2, sy + 2, 64, 10, "p2", 3)
    for i, g in enumerate(["ra", "-v", "me", "n"]):
        rows = KATA[g] if g != "-v" else KATA["-v"]
        if g == "-v": rows = [".......", ".......", ".......", "#######", ".......", ".......", "......."]
        glyph(sx + 5 + i * 15, sy + 3, rows, "black", 3.4)
    light(sx + 34, sy + 7, "y3", 0.8, 3.0)
    # porte ouverte (transparente) + encadrement
    dw, dh = 44, 84
    dx = door_c - dw // 2
    rect(dx - 4, H - dh - 4, dw + 8, dh + 4, "w1", 2)
    bevel(dx - 4, H - dh - 4, dw + 8, dh + 4, "w4", "w0")
    ALPHA[H - dh:H, dx:dx + dw] = 0
    HGT[H - dh:H, dx:dx + dw] = -2
    DOORS.append([round(wx(door_c), 3), round(dh / PX, 3)])
    noren(dx, H - dh, dw, 26)
    # vitrine à gauche : intérieur chaud, comptoir, bols, silhouettes
    vx, vy, vw, vh = x0 + 14, top + 22, 70, 48
    rect(vx - 3, vy - 3, vw + 6, vh + 6, "w0", 2); bevel(vx - 3, vy - 3, vw + 6, vh + 6, "w4", "w0")
    rect(vx, vy, vw, vh, "y2", -1, "y2")
    dither(vx, vy, vw, 16, "y2", "y3", 0.35); EMI[vy:vy + 16, vx:vx + vw] = P["y3"]
    rect(vx, vy + 34, vw, 14, "w2", -0.5, "y0"); hline(vx, vy + 34, vw, "w5", -0.5, "y1")   # comptoir
    for i in range(4):                                        # bols fumants
        bx = vx + 8 + i * 16
        rect(bx, vy + 30, 8, 4, "white", -0.5, "y3"); hline(bx + 1, vy + 33, 6, "p1", -0.5, "y1")
        for s in range(5):
            px(bx + 3 + (s % 2), vy + 28 - s * 2, "y4", -0.5, "y4")
    for i, (sx_, hh) in enumerate(((vx + 12, 20), (vx + 44, 22))):  # clients de dos
        rect(sx_, vy + 34 - hh, 10, hh, "k1", -0.8, "y0")
        for yy in range(5):
            for xx in range(8):
                if math.hypot(xx - 3.5, yy - 2.5) < 3.6:
                    px(sx_ + 1 + xx, vy + 34 - hh - 6 + yy, "k1", -0.8, "y0")
    for xx in range(vx, vx + vw, 18): vline(xx, vy, vh, "w0", 1)           # montants
    for yy in (vy + 12,): hline(vx, yy, vw, "w0", 1)
    LIGHTS.append(dict(x=round(wx(vx + vw / 2), 3), y=round(wy(vy + vh / 2), 3), z=-1.8,
                       color=[1.0, 0.68, 0.36], energy=2.6, range=5.0, flicker=False))
    # menu à droite de la porte
    mx, my = door_c + 30, top + 26
    rect(mx, my, 22, 30, "k1", 2); frame(mx, my, 22, 30, "w3", 2.5)
    for r in range(5):
        hline(mx + 3, my + 4 + r * 5, int(rng.integers(8, 16)), "white", 2.2, "p0")
    rect(mx + 3, my + 4 + 5 * 5 - 1, 6, 1, "np", 2.2, "np")
    # lanternes de part et d'autre de la porte
    lantern(dx - 20, top + 2); lantern(dx + dw + 9, top + 2)
    # tabouret / caisse de bières
    bx = x0 + w - 40
    rect(bx, H - 16, 20, 14, "r1", 3); bevel(bx, H - 16, 20, 14, "r3", "r0")
    for i in range(4): px(bx + 3 + i * 4, H - 18, "y2", 3.2)

def trash_bags(x, y):
    for i, (bw, bh) in enumerate(((16, 12), (14, 10), (12, 13))):
        bx = x + i * 11
        for yy in range(bh):
            for xx in range(bw):
                d = ((xx - bw / 2) / (bw / 2)) ** 2 + ((yy - bh * 0.6) / (bh * 0.7)) ** 2
                if d < 1:
                    col = "k2" if d < 0.35 else "k1"
                    if xx < bw * 0.4 and yy < bh * 0.45 and d < 0.6: col = "k3"
                    px(bx + xx, y - bh + yy, col, 4 * (1 - d))
        rect(bx + bw // 2 - 1, y - bh - 2, 2, 3, "k2", 3)

def plant_pot(x, y, size=1.0):
    pw, ph = int(12 * size), int(9 * size)
    for yy in range(ph):
        inset = yy // 4
        hline(x + inset, y - ph + yy, pw - 2 * inset, "t1" if yy > 1 else "t2", 3)
    vline(x + 1, y - ph + 2, ph - 3, "t2", 3)
    hline(x - 1, y - ph, pw + 2, "t2", 3.5); contact_shadow(x, y, pw, 0)
    for _ in range(int(28 * size)):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95); L = rng.uniform(5, 16) * size
        cx, cy = x + pw / 2, y - ph
        for s in range(int(L)):
            t = s / L
            lx = int(cx + math.cos(a) * L * t * 0.9); ly = int(cy + math.sin(a) * L * t)
            col = "g3" if t > 0.6 else "g2"
            if s == int(L) - 1: col = "g4"
            px(lx, ly, col, 3 + t)

def poster(x, y, w, h, scheme):
    for yy in range(h):
        cut = int(rng.integers(0, 2)) if yy > h * 0.7 else 0
        hline(x + cut, y + yy, w - cut - int(rng.integers(0, 2)), "p1", 0.4)
    a, b = scheme
    rect(x + 2, y + 2, w - 4, h // 3, a, 0.4)
    rect(x + 2, y + 2 + h // 3 + 1, (w - 4) // 2, 3, b, 0.4)
    for r in range(3): hline(x + 2, y + h // 3 + 7 + r * 3, int(rng.integers(4, w - 4)), "k2", 0.4)
    px(x + 1, y + 1, "m5", 0.6); px(x + w - 2, y + 1, "m5", 0.6)
    contact_shadow(x, y + h, w, 1)

def back_door(xc):
    """Porte métallique de service, ouverte, avec ampoule nue au-dessus."""
    dw, dh = 44, 84
    dx = xc - dw // 2
    rect(dx - 5, H - dh - 5, dw + 10, dh + 5, "m2", 3); bevel(dx - 5, H - dh - 5, dw + 10, dh + 5, "m5", "m0")
    ALPHA[H - dh:H, dx:dx + dw] = 0
    HGT[H - dh:H, dx:dx + dw] = -2
    DOORS.append([round(wx(xc), 3), round(dh / PX, 3)])
    # battant ouvert contre le mur (vu de biais)
    for i in range(10):
        vline(dx + dw + 5 + i, H - dh + i // 3, dh - i // 3 * 2, "m3" if i < 2 else "m2", 4 - i * 0.3)
    vline(dx + dw + 14, H - dh, dh, "m1", 1)
    # ampoule + protection
    bx, by = xc - 3, H - dh - 16
    rect(bx - 2, by - 3, 10, 3, "m2", 4)
    rect(bx, by, 6, 6, "y4", 5, "y4"); px(bx + 2, by + 2, "white", 5, "white")
    for i in range(0, 6, 2): vline(bx + i, by, 6, "m1", 5)
    light(bx + 3, by + 3, "y4", 2.8, 5.5, z=-2.0)
    # enseigne néon BAR
    sx, sy = xc - 22, H - dh - 40
    rect(sx, sy, 44, 15, "m0", 3); frame(sx, sy, 44, 15, "m2", 3.5)
    for i, ch in enumerate("BAR"):
        glyph(sx + 8 + i * 10, sy + 4, LATIN[ch], "nc", 4, "nc", halo="nc")
    light(sx + 22, sy + 7, "nc", 2.4, 5.5, z=-1.6, flicker=True)
    # marches
    rect(dx - 8, H - 4, dw + 16, 4, "c4", 4); hline(dx - 8, H - 4, dw + 16, "c5", 4)
    # caisses empilées
    for (cx, cy, s) in ((xc + 36, H - 16, 16), (xc + 52, H - 16, 16), (xc + 42, H - 32, 16)):
        rect(cx, cy, s, s, "w2", 4); bevel(cx, cy, s, s, "w4", "w0")
        hline(cx + 1, cy + s // 2, s - 2, "w1", 3.5); vline(cx + s // 2, cy + 1, s - 2, "w1", 3.5)

def bicycle(x, y):
    """Vélo garé, roues de 9 px de rayon (y = sol)."""
    for cx in (x + 9, x + 37):
        cy = y - 10
        for a in range(0, 360, 4):
            r = math.radians(a)
            px(int(round(cx + 9 * math.cos(r))), int(round(cy + 9 * math.sin(r))), "black", 3)
            px(int(round(cx + 8 * math.cos(r))), int(round(cy + 8 * math.sin(r))), "m2", 3)
        for a in range(0, 360, 45):
            r = math.radians(a)
            for t in range(1, 8):
                px(int(round(cx + t * math.cos(r))), int(round(cy + t * math.sin(r))), "m3", 2.5)
    def seg(x0, y0, x1, y1, col):
        n = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(n + 1):
            px(int(round(x0 + (x1 - x0) * i / n)), int(round(y0 + (y1 - y0) * i / n)), col, 3.5)
    bx, by = x + 22, y - 10
    seg(x + 9, y - 10, bx, by, "r2"); seg(bx, by, x + 16, y - 26, "r2"); seg(x + 16, y - 26, x + 32, y - 25, "r2")
    seg(x + 32, y - 25, bx, by, "r2"); seg(x + 32, y - 25, x + 37, y - 10, "r2"); seg(x + 16, y - 26, x + 9, y - 10, "r3")
    rect(x + 12, y - 29, 9, 2, "k1", 4); seg(x + 32, y - 25, x + 33, y - 31, "m4"); rect(x + 30, y - 32, 8, 2, "m4", 4)
    rect(x + 37, y - 30, 8, 6, "m2", 4); frame(x + 37, y - 30, 8, 6, "m4", 4)   # panier

def gachapon(x, y, col):
    """Distributeur de capsules (y = sol)."""
    rect(x, y - 14, 16, 14, col, 4); bevel(x, y - 14, 16, 14, "white", "r0")
    rect(x + 5, y - 10, 6, 6, "m5", 4.5); px(x + 7, y - 8, "m1", 4.5); px(x + 8, y - 8, "m1", 4.5)
    rect(x + 1, y - 30, 14, 16, "vw", 3.5, None)
    frame(x + 1, y - 30, 14, 16, "m4", 4)
    caps = ["np", "nc", "ng", "y2", "l2", "b3"]
    for j in range(4):
        for i in range(4):
            if rng.random() < 0.85:
                c = caps[int(rng.integers(0, len(caps)))]
                rect(x + 2 + i * 3, y - 18 - j * 3, 2, 2, c, 4, (P[c] * 0.5).astype(np.uint8))
    EMI[y - 30:y - 28, x + 1:x + 15] = P["vw"]
    rect(x, y - 32, 16, 2, col, 4)
    contact_shadow(x, y, 16, 0)

def cables(y_base):
    """Câbles qui pendent entre les éléments, en haut du mur."""
    anchors = sorted(rng.uniform(0, W, 22))
    for a, b in zip(anchors[:-1], anchors[1:]):
        if b - a < 30: continue
        ya, yb = y_base + rng.uniform(-3, 6), y_base + rng.uniform(-3, 6)
        sag = (b - a) * rng.uniform(0.04, 0.09)
        for xx in range(int(a), int(b)):
            t = (xx - a) / (b - a)
            yy = int(ya + (yb - ya) * t + sag * 4 * t * (1 - t))
            px(xx, yy, "black", 2)

# ---------------------------------------------------------------- composition
concrete()
DOOR_A = int(round((9.6875 - WALL_X0) * PX))   # portes alignées sur la scène existante
DOOR_B = int(round((31.6875 - WALL_X0) * PX))

# étage : fenêtres et climatiseurs
modes = ["dark", "warm", "blinds", "dark", "frost", "dark", "warm", "dark", "blinds", "dark", "frost", "dark", "warm"]
for i, x in enumerate(range(30, W - 60, 112)):
    window_upper(x, 12, 40, 26, modes[i % len(modes)])
    if i % 2 == 0:
        ac_unit(x + 54, 14)
    else:
        meter_box(x + 58, 20); meter_box(x + 72, 20)

# tuyaux verticaux
for x in (8, 112, 590, 930, 1240, 1460):
    pipe_v(x)
cylinder_h(0, 46, W, 3, ["m1", "m3", "m2"])            # conduit horizontal
for x in range(20, W, 140):
    rect(x, 45, 3, 5, "m4", 3)

# rez-de-chaussée
shutter(150, 86, 130, 72)
lightbox_sign(152, 64, 66, 14, "OPEN", "y3")
ramen_shop(DOOR_A - 150, DOOR_A)
neon_vertical(DOOR_A - 150 - 22, 56, ["ra", "-v", "me", "n"], "np", "npd")
vending(DOOR_A + 70, H - 64)
vending(DOOR_A + 106, H - 64, body="vb")
EMI[H - 64:H - 58, DOOR_A + 109:DOOR_A + 137] = (P["vw"] * 0.5).astype(np.uint8)
poster(DOOR_A + 160, 70, 18, 24, ("np", "nc"))
poster(DOOR_A + 182, 76, 16, 20, ("y2", "r2"))
poster(DOOR_A + 168, 98, 20, 26, ("nc", "y3"))
ac_unit(DOOR_A + 220, 70, 34, 24)
plant_pot(DOOR_A + 216, H - 2, 1.2); plant_pot(DOOR_A + 236, H - 2, 0.9)
trash_bags(DOOR_A + 250, H - 1)
window_upper(DOOR_A + 300, 80, 56, 34, "blinds")      # izakaya
neon_vertical(DOOR_A + 372, 64, ["sa", "ke"], "ng", "ngd")
lantern(DOOR_A + 292, 74)
back_door(DOOR_B)
shutter(DOOR_B + 120, 92, 110, 66)
poster(DOOR_B + 130, 70, 18, 16, ("np", "white"))
plant_pot(DOOR_B + 250, H - 2, 1.1)
trash_bags(DOOR_B + 90, H - 1)
trash_bags(30, H - 1)
for i in range(3): meter_box(60 + i * 14, 70)
cables(52)
# milieu de la ruelle : climatiseurs empilés, vélo, flèche néon vers le bar
ac_unit(DOOR_A + 470, 64, 30, 22); ac_unit(DOOR_A + 470, 92, 30, 22)
bicycle(DOOR_A + 520, H - 1)
for i in range(4):
    poster(DOOR_A + 590 + i * 20, 84 + (i % 2) * 6, 16, 22, [("np", "nc"), ("y2", "r2"), ("nc", "y3"), ("ng", "white")][i])
ax, ay = DOOR_B - 64, 72
for i in range(18):
    px(ax + i, ay, "np", 4, "np")
for i in range(5):
    px(ax + 17 - i, ay - i, "np", 4, "np"); px(ax + 17 - i, ay + i, "np", 4, "np")
light(ax + 9, ay, "np", 1.4, 3.5, z=-1.8, flicker=True)
plant_pot(DOOR_A + 640, H - 2, 1.3)
# fond de ruelle : distributeurs de capsules
gachapon(DOOR_B + 252, H - 1, "r2"); gachapon(DOOR_B + 270, H - 1, "vb"); gachapon(DOOR_B + 288, H - 1, "ng")
light(DOOR_B + 278, H - 24, "vw", 1.2, 3.0, z=-1.9)

# ---------------------------------------------------------------- export
os.makedirs(OUT, exist_ok=True)
Image.fromarray(np.dstack([ALB, ALPHA]), "RGBA").save(os.path.join(OUT, "wall.png"))
Image.fromarray(EMI, "RGB").save(os.path.join(OUT, "wall_emit.png"))
gx = np.zeros_like(HGT); gy = np.zeros_like(HGT)
gx[:, 1:-1] = (HGT[:, 2:] - HGT[:, :-2]) * 0.5
gy[1:-1, :] = (HGT[2:, :] - HGT[:-2, :]) * 0.5
n = np.dstack([-gx, gy, np.full_like(HGT, 1.2)])
n /= np.linalg.norm(n, axis=2, keepdims=True)
Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB").save(os.path.join(OUT, "wall_normal.png"))
with open(os.path.join(OUT, "wall_lights.json"), "w") as f:
    json.dump(dict(lights=LIGHTS, doors=DOORS, windows=WINDOWS), f, indent=1)
print(f"mur {W}x{H} — {len(LIGHTS)} lumières, {len(DOORS)} portes, {len(WINDOWS)} fenêtres éclairées")

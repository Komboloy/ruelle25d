"""
paint_foreground.py — Premier plan (z = +4) : silhouettes à contre-jour qui encadrent l'image.

Le plan est entre la caméra et le personnage : les lumières de la ruelle sont derrière lui,
il reste donc sombre (comme dans les références), avec juste quelques reflets colorés.
Il est flouté par la profondeur de champ proche.

Usage : python3 tools/paint_foreground.py assets/env
"""
import sys, json, math, os
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pixlib import Canvas, PALETTE

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/env"
PXM = 42.89                    # pixels par mètre à z = +4
W_M, H_M, Y0 = 44.0, 6.0, -1.5
W, H = int(W_M * PXM), int(H_M * PXM)
c = Canvas(W, H, seed=2024)
R = c.rng

def X(m): return int(round(m * PXM))
def Y(m): return int(round(H - (m - Y0) * PXM))      # hauteur monde (m) → ligne de l'image

INK = "black"; INK2 = "n0"; INK3 = "n1"; LEAF = "q0"; LEAF2 = "q1"

# ---------------------------------------------------------------- éléments
def railing(x0_m, x1_m, top_m=0.95):
    """Garde-corps à motif de grecque (comme dans la ruelle de la référence)."""
    x0, x1, top, base = X(x0_m), X(x1_m), Y(top_m), Y(-0.1)
    c.rect(x0, top, x1 - x0, 4, INK); c.hline(x0, top, x1 - x0, INK3)
    c.rect(x0, base - 4, x1 - x0, 4, INK)
    step = 22
    for x in range(x0, x1 - step + 1, step):
        c.rect(x, top, 3, base - top, INK)
        m = 5                                            # motif de grecque
        pts = [(x + m, top + m), (x + step - m, top + m), (x + step - m, base - m),
               (x + m + 4, base - m), (x + m + 4, top + m + 6), (x + step - m - 5, top + m + 6),
               (x + step - m - 5, base - m - 6)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            for t in range(2):
                c.line(ax + t, ay, bx + t, by, INK)
    c.rect(x1 - 3, top, 3, base - top, INK)

def bollard(x_m):
    x, top, base = X(x_m), Y(0.85), Y(-0.1)
    c.rect(x, top, 10, base - top, INK); c.rect(x - 1, top, 12, 4, INK2)
    c.hline(x + 1, top + 10, 8, "np", (PALETTE["np"] * 0.35).astype(np.uint8))   # bande réfléchissante
    c.hline(x + 1, top + 12, 8, "np", (PALETTE["np"] * 0.35).astype(np.uint8))

def cone(x_m):
    x, base = X(x_m), Y(-0.1)
    hgt = 30
    for i in range(hgt):
        half = 2 + i // 3
        col = INK if (i // 6) % 2 == 0 else "wrd"
        c.hline(x - half, base - hgt + i, half * 2 + 1, col)
    c.rect(x - 14, base - 3, 29, 3, INK)

def fern(x_m, size=1.0, base_m=-0.1):
    """Touffe de fougère : frondes arquées avec folioles."""
    bx, by = X(x_m), Y(base_m)
    for _ in range(int(9 * size)):
        a = R.uniform(math.pi * 1.1, math.pi * 1.9)
        L = R.uniform(40, 85) * size
        bend = R.uniform(0.3, 0.9) * (1 if math.cos(a) > 0 else -1)
        prev = (bx, by)
        n = 18
        for k in range(1, n + 1):
            t = k / n
            ang = a + bend * t * 0.9
            x = bx + math.cos(ang) * L * t
            y = by + math.sin(ang) * L * t
            c.line(prev[0], prev[1], x, y, INK)
            if k % 2 == 0 and t < 0.95:                  # folioles
                ll = (1 - t) * 10 * size + 2
                for s in (-1, 1):
                    pa = ang + s * 1.2
                    c.line(x, y, x + math.cos(pa) * ll, y + math.sin(pa) * ll, LEAF)
            prev = (x, y)

def grass(x_m, width_m, height_m=0.7):
    x0, x1, by = X(x_m), X(x_m + width_m), Y(-0.1)
    for _ in range(int((x1 - x0) * 0.6)):
        x = R.uniform(x0, x1)
        h = R.uniform(0.3, 1.0) * height_m * PXM
        lean = R.uniform(-0.4, 0.4)
        pts = [(x + lean * h * t * t, by - h * t) for t in np.linspace(0, 1, 7)]
        for (ax, ay), (bx2, by2) in zip(pts, pts[1:]):
            c.line(ax, ay, bx2, by2, INK if R.random() < 0.7 else LEAF)

def planter(x_m, w_m):
    x, w, top, base = X(x_m), X(w_m), Y(0.45), Y(-0.1)
    c.rect(x, top, w, base - top, INK); c.hline(x, top, w, INK3)
    fern(x_m + w_m * 0.3, 0.8, 0.45); fern(x_m + w_m * 0.7, 0.9, 0.45)
    grass(x_m + 0.05, w_m - 0.1, 0.5)

def pole(x_m, top_m=4.4):
    """Poteau électrique au tout premier plan (coupé par le haut de l'image)."""
    x, top, base = X(x_m), Y(top_m), Y(-0.1)
    c.rect(x, top, 16, base - top, INK); c.vline(x + 15, top, base - top, INK2)
    for yy in range(top + 40, base - 30, 34):                      # échelons
        c.rect(x - 7, yy, 7, 3, INK); c.rect(x + 16, yy + 17, 7, 3, INK)
    c.rect(x - 2, base - 70, 20, 26, INK2)                         # plaque / affiche
    c.rect(x + 1, base - 67, 14, 20, "wy0", (PALETTE["wy0"] * 0.3).astype(np.uint8))
    for k in range(4):
        c.hline(x + 3, base - 63 + k * 4, 10, INK2)
    c.rect(x - 30, top + 6, 76, 5, INK)                            # traverse
    for ix in (x - 26, x - 12, x + 26, x + 40):
        c.rect(ix, top - 1, 4, 7, INK)
    return x + 8, top + 8

def bike_rack(x_m, n=3):
    x0, base = X(x_m), Y(-0.1)
    for i in range(n):
        x = x0 + i * 30
        for a in range(0, 181, 6):
            r = math.radians(a)
            c.rect(x + 12 + 12 * math.cos(r), base - 26 - 12 * math.sin(r) + 12, 3, 3, INK)
        c.rect(x, base - 14, 3, 14, INK); c.rect(x + 24, base - 14, 3, 14, INK)

# ---------------------------------------------------------------- composition
railing(-1.5, 6.0)
fern(1.2, 1.1); grass(0.0, 3.0)
bollard(7.2); bollard(8.4)
planter(10.5, 2.2)
cone(14.0)
grass(15.0, 2.5, 0.6); fern(16.3, 1.2)
p1 = pole(18.8)
railing(20.5, 27.0)
fern(22.5, 0.9); grass(24.0, 2.5)
bike_rack(28.0)
planter(31.5, 2.4)
bollard(34.6); bollard(35.8)
p2 = pole(37.5)
fern(39.2, 1.3); grass(38.5, 3.5, 0.8)
railing(40.0, 44.0)

# câbles tendus entre les poteaux, et qui sortent du cadre
for k, dy in enumerate((0, 4, 9)):
    c.catenary(p1[0], p1[1] + dy, p2[0], p2[1] + dy, 30 + k * 8, INK)
    c.catenary(-40, Y(4.9) + dy, p1[0], p1[1] + dy, 24 + k * 6, INK)
    c.catenary(p2[0], p2[1] + dy, W + 40, Y(4.8) + dy, 20 + k * 6, INK)

c.save(OUT, "foreground", emi_scale=1.0)

# mise à jour de la description du plan dans layers.json
meta_path = os.path.join(OUT, "layers.json")
meta = json.load(open(meta_path))
for l in meta["layers"]:
    if l["name"] == "foreground":
        l.update(x=-2.0, y=Y0, w=W_M, h=H_M, emissive=True, emit_energy=2.0)
json.dump(meta, open(meta_path, "w"), indent=1)
print("premier plan", (W, H))

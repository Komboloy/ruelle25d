"""
paint_city.py — Ville japonaise de nuit en deux plans, peinte pixel par pixel.

  city_mid  (z = -16, ~16 px/m) : immeubles proches, toits détaillés, enseignes empilées, câbles
  city_far  (z = -40,  ~9 px/m) : skyline dense, tour en treillis, feux rouges d'obstacle

Seule une bande de chaque plan est visible au-dessus du mur de la ruelle : la composition
concentre les détails (toits, enseignes, réservoirs) dans cette bande.

Usage : python3 tools/paint_city.py assets/env
"""
import sys, math
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pixlib import Canvas, PALETTE

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/env"

# ======================================================================== plan moyen
MID_W, MID_H, MID_PX = 1142, 349, 15.86       # dimensions imposées par layers.json
c = Canvas(MID_W, MID_H, seed=7)
R = c.rng
def m2px(meters): return int(round(meters * MID_PX))
GROUND = MID_H                                 # y = -1 m au bas de l'image

BODIES = [("n2", "n3", "n1"), ("t1", "t2", "t0"), ("q1", "q2", "q0"), ("n3", "n4", "n2")]
SIGN_COLS = ["np", "nc", "ng", "no", "nv", "ny"]

def water_tank(x, y):
    """Réservoir cylindrique sur pieds, posé sur un toit (y = niveau du toit)."""
    w, h = 16, 12
    for i in range(3):
        c.vline(x + 2 + i * 6, y - 6, 6, "m2")
    c.hline(x, y - 6, w, "m3")
    for yy in range(h):
        for xx in range(w):
            t = xx / (w - 1)
            col = "m4" if 0.2 < t < 0.4 else ("m3" if t < 0.7 else "m2")
            if yy in (2, h - 3): col = "m1"
            c.px(x + xx, y - 6 - h + yy, col)
    for xx in range(2, w - 2):                                   # couvercle bombé
        c.px(x + xx, y - 6 - h - 1, "m3")
    c.hline(x + 4, y - 6 - h - 2, w - 8, "m4")

def billboard(x, y, w, h, col):
    """Panneau publicitaire sur structure en treillis (y = niveau du toit)."""
    leg = 10
    for i in range(0, w, 8):
        c.vline(x + i, y - leg, leg, "m2")
        c.line(x + i, y - leg, x + i + 8, y, "m1")
    c.hline(x, y - leg, w, "m3")
    by = y - leg - h
    c.rect(x, by, w, h, "m1")
    c.rect(x + 1, by + 1, w - 2, h - 2, col, emi=(PALETTE[col] * 0.55).astype(np.uint8))
    # visuel : bande + texte
    c.rect(x + 2, by + 2, w // 3, h - 4, "nw", emi=(PALETTE["nw"] * 0.5).astype(np.uint8))
    for i in range(3):
        c.glyph_random(x + w // 3 + 5 + i * 9, by + (h - 7) // 2, 7, 7, "black", "black", 0.45)
    for i in range(0, w, 6):                                     # spots éclairant le panneau
        c.px(x + i + 2, by - 1, "wy3", "wy3")

def rooftop_sign(x, y, n, col):
    """Grandes lettres néon sur le toit (y = niveau du toit)."""
    c.hline(x - 2, y - 3, n * 12 + 2, "m2")
    for i in range(n):
        c.vline(x + i * 12 + 4, y - 3, 3, "m1")
        c.glyph_random(x + i * 12, y - 15, 10, 11, col, col, 0.42)

def vertical_signs(x, y_top, y_bot, side_w=11):
    """Pile d'enseignes verticales sur la façade (typique des zakkyo biru)."""
    y = y_top
    while y < y_bot - 16:
        h = int(R.integers(14, 30))
        col = SIGN_COLS[int(R.integers(0, len(SIGN_COLS)))]
        style = R.random()
        c.rect(x, y, side_w, h, "m0")
        if style < 0.5:                                          # caisson lumineux
            c.rect(x + 1, y + 1, side_w - 2, h - 2, col, emi=(PALETTE[col] * 0.7).astype(np.uint8))
            for k in range(max(1, (h - 4) // 6)):
                c.glyph_random(x + 3, y + 3 + k * 6, 5, 5, "black", "black", 0.45)
        else:                                                    # tubes néon sur fond sombre
            c.frame(x, y, side_w, h, col)
            for ex in (x, x + side_w - 1):
                if 0 <= ex < c.W:
                    c.emi[y:y + h, ex] = PALETTE[col]
            for k in range(max(1, (h - 4) // 6)):
                c.glyph_random(x + 3, y + 3 + k * 6, 5, 5, col, col, 0.4)
        y += h + int(R.integers(1, 4))

def apartment(x, w, top):
    body, light, dark = BODIES[int(R.integers(0, len(BODIES)))]
    c.rect(x, top, w, GROUND - top, body)
    c.vline(x, top, GROUND - top, light); c.vline(x + w - 1, top, GROUND - top, dark)
    floor_h = 16
    for fy in range(top + 6, GROUND - 8, floor_h):
        c.hline(x, fy + floor_h - 4, w, light)                   # dalle de balcon
        c.hline(x, fy + floor_h - 3, w, dark)
        for bx in range(x + 2, x + w - 2, 2):                    # garde-corps
            c.px(bx, fy + floor_h - 6, dark); c.px(bx, fy + floor_h - 5, dark)
        c.hline(x + 1, fy + floor_h - 7, w - 2, dark)
        for ux in range(x + 4, x + w - 12, 14):                  # fenêtres / baies
            lit = R.random() < 0.38
            col = ("wy2" if R.random() < 0.7 else "wc1") if lit else "n1"
            emi = (PALETTE[col] * R.uniform(0.6, 1.0)).astype(np.uint8) if lit else None
            c.rect(ux, fy + 2, 9, 7, col, emi=emi)
            if lit and R.random() < 0.5:                         # rideau
                c.rect(ux + 6, fy + 2, 3, 7, "wy1", emi=(PALETTE["wy1"] * 0.6).astype(np.uint8))
            if R.random() < 0.35:                                # clim sur le balcon
                c.rect(ux + 10, fy + floor_h - 9, 3, 3, "m4")
            if R.random() < 0.15:                                # linge
                for k in range(4):
                    c.px(ux + 1 + k * 2, fy + floor_h - 8, ["np", "wc2", "white", "ny"][k % 4])
    roof(x, w, top, light, dark)

def office(x, w, top):
    body, light, dark = BODIES[int(R.integers(0, len(BODIES)))]
    c.rect(x, top, w, GROUND - top, body)
    c.vline(x, top, GROUND - top, light)
    band = 11
    for fy in range(top + 5, GROUND - 6, band):
        on = R.random() < 0.55
        cool = R.random() < 0.7
        for wx in range(x + 3, x + w - 3):
            if (wx - x) % 7 == 6:
                c.px(wx, fy + 3, dark); c.px(wx, fy + 4, dark); c.px(wx, fy + 5, dark); c.px(wx, fy + 6, dark)
                continue
            if on and R.random() < 0.92:
                colk = "wc2" if cool else "wy2"
                c.rect(wx, fy + 3, 1, 4, colk, emi=(PALETTE[colk] * 0.62).astype(np.uint8))
            else:
                c.rect(wx, fy + 3, 1, 4, "n1")
        c.hline(x, fy + 8, w, dark)
    if R.random() < 0.8:
        vertical_signs(x + w - 2 if R.random() < 0.5 else x - 9, top + 10, GROUND)
    roof(x, w, top, light, dark)

def old_house(x, w, top):
    """Maison basse à toit de tuiles, rez-de-chaussée éclairé."""
    c.rect(x, top + 10, w, GROUND - top - 10, "t1")
    for yy in range(top, top + 10):                              # toit en tuiles
        inset = (top + 10 - yy) // 2
        for xx in range(x - 4 + inset, x + w + 4 - inset):
            c.px(xx, yy, "m2" if (xx // 3 + yy) % 2 else "m1")
    c.hline(x - 4, top + 9, w + 8, "m0")
    for wx in range(x + 4, x + w - 10, 16):
        lit = R.random() < 0.7
        c.rect(wx, top + 16, 10, 8, "wy1" if lit else "n1", emi=PALETTE["wy1"] if lit else None)
        c.vline(wx + 5, top + 16, 8, "t0")

def roof(x, w, top, light, dark):
    c.hline(x - 1, top - 2, w + 2, light); c.hline(x - 1, top - 1, w + 2, dark)   # acrotère
    for fx in range(x, x + w, 3):                                # grillage de toit
        c.vline(fx, top - 7, 5, dark)
    c.hline(x, top - 7, w, dark)
    r = R.random()
    if r < 0.35 and w > 40:
        water_tank(x + int(R.integers(4, max(5, w - 20))), top - 2)
    elif r < 0.55 and w > 50:
        billboard(x + 4, top - 2, min(w - 8, 64), 22, SIGN_COLS[int(R.integers(0, len(SIGN_COLS)))])
    elif r < 0.75 and w > 50:
        rooftop_sign(x + 6, top - 2, min(4, (w - 10) // 12), SIGN_COLS[int(R.integers(0, len(SIGN_COLS)))])
    if R.random() < 0.6:                                         # cage d'escalier
        sx = x + int(R.integers(2, max(3, w - 16)))
        c.rect(sx, top - 14, 14, 12, dark); c.hline(sx, top - 14, 14, light)
        c.rect(sx + 3, top - 10, 4, 7, "wy2", emi=(PALETTE["wy2"] * 0.5).astype(np.uint8))
    for _ in range(int(R.integers(1, 4))):                       # antennes
        ax = x + int(R.integers(2, max(3, w - 2))); ah = int(R.integers(8, 26))
        c.vline(ax, top - 2 - ah, ah, dark)
        for k in range(int(R.integers(1, 4))):
            ky = top - 2 - ah + 3 + k * 4
            c.hline(ax - 3, ky, 7, dark)
        if R.random() < 0.4:
            c.px(ax, top - 3 - ah, "wr", "wr")                   # feu d'obstacle

def utility_pole(x):
    top = GROUND - m2px(7.2)
    c.rect(x, top, 3, GROUND - top, "m1"); c.vline(x, top, GROUND - top, "m2")
    for k, cy in enumerate((top + 6, top + 14)):
        c.hline(x - 12, cy, 27, "m1")
        for ix in (x - 11, x - 4, x + 6, x + 13):
            c.px(ix, cy - 1, "m3")
    c.rect(x + 4, top + 22, 9, 12, "m2"); c.frame(x + 4, top + 22, 9, 12, "m3")   # transformateur
    c.rect(x - 9, top + 24, 6, 9, "m2")
    return top

# composition : immeubles de gauche à droite
x = -10
kinds = ["apartment", "office", "old", "office", "apartment", "office", "apartment", "old", "office"]
i = 0
while x < MID_W:
    kind = kinds[i % len(kinds)] if R.random() < 0.8 else kinds[int(R.integers(0, len(kinds)))]
    if kind == "old":
        w = int(R.integers(50, 80)); top = GROUND - m2px(R.uniform(4.6, 5.6))
        old_house(x, w, top)
    elif kind == "office":
        w = int(R.integers(54, 96)); top = GROUND - m2px(R.uniform(6.2, 9.0))
        office(x, w, top)
    else:
        w = int(R.integers(70, 130)); top = GROUND - m2px(R.uniform(5.6, 7.8))
        apartment(x, w, top)
    x += w + int(R.integers(-4, 10))
    i += 1

# poteaux électriques et faisceaux de câbles devant les immeubles
poles = [int(p) for p in np.arange(40, MID_W, 190) + R.integers(-20, 20, size=len(np.arange(40, MID_W, 190)))]
tops = [utility_pole(p) for p in poles]
for (pa, ta), (pb, tb) in zip(zip(poles, tops), zip(poles[1:], tops[1:])):
    for k, dy in enumerate((5, 7, 13, 15, 26)):
        c.catenary(pa + 1, ta + dy, pb + 1, tb + dy, 8 + k * 3 + R.uniform(0, 4), "black")
c.save(OUT, "city_mid", emi_scale=0.85)

# ======================================================================== plan lointain
FAR_W, FAR_H = 904, 379
f = Canvas(FAR_W, FAR_H, seed=11)
FR = f.rng
FPX = 9.04
FG = FAR_H

def far_tower(x, w, top, body):
    f.rect(x, top, w, FG - top, body)
    f.vline(x, top, FG - top, "n3")
    for wy in range(top + 3, FG, 4):
        if FR.random() < 0.45:
            for wx in range(x + 2, x + w - 2, 3):
                if FR.random() < 0.35:
                    colk = "wy2" if FR.random() < 0.6 else "wc2"
                    f.px(wx, wy, colk, (PALETTE[colk] * FR.uniform(0.3, 0.7)).astype(np.uint8))
    if FR.random() < 0.5:
        f.px(x + w // 2, top - 1, "wr", "wr")
    if FR.random() < 0.25:                                       # toit à gradins
        f.rect(x + w // 4, top - 6, w // 2, 6, body)
    if FR.random() < 0.3:                                        # enseigne de toit lointaine
        colk = ["np", "nc", "no", "nv"][int(FR.integers(0, 4))]
        f.rect(x + 2, top - 5, max(4, w - 4), 4, colk, (PALETTE[colk] * 0.6).astype(np.uint8))

# skyline : couches de profondeur (plus claires = plus loin, comme dans la brume)
for layer, (body, hmin, hmax) in enumerate((("n4", 10, 15.5), ("n3", 7.5, 12.5), ("n2", 6, 10))):
    x = int(FR.integers(-20, 0))
    while x < FAR_W:
        w = int(FR.integers(14, 40))
        top = FG - int(FR.uniform(hmin, hmax) * FPX)
        far_tower(x, w, top, body)
        x += w + int(FR.integers(0, 8))

# tour en treillis (silhouette éclairée en orange)
tx, base_w, ttop = 610, 54, FG - int(14.0 * FPX)
for yy in range(ttop, FG):
    t = (yy - ttop) / (FG - ttop)
    half = int(2 + (base_w / 2) * t ** 1.6)
    for side in (-1, 1):
        f.px(tx + side * half, yy, "no", (PALETTE["no"] * 0.8).astype(np.uint8))
    if (yy - ttop) % 6 == 0:
        for xx in range(tx - half, tx + half + 1):
            f.px(xx, yy, "no", (PALETTE["no"] * 0.55).astype(np.uint8))
    if (yy - ttop) % 6 < 6:
        k = (yy - ttop) % 6
        f.px(tx - half + k * half // 3, yy, "no", (PALETTE["no"] * 0.45).astype(np.uint8))
        f.px(tx + half - k * half // 3, yy, "no", (PALETTE["no"] * 0.45).astype(np.uint8))
for (dy, dw) in ((int((FG - ttop) * 0.45), 16), (int((FG - ttop) * 0.22), 10)):   # plateformes
    f.rect(tx - dw // 2, ttop + dy, dw, 4, "nw", (PALETTE["wy3"] * 0.9).astype(np.uint8))
f.vline(tx, ttop - 12, 12, "nw", (PALETTE["wy3"]).astype(np.uint8))
f.px(tx, ttop - 13, "wr", "wr")
f.save(OUT, "city_far", emi_scale=1.0)
print("ville peinte : city_mid", (MID_W, MID_H), "city_far", (FAR_W, FAR_H))

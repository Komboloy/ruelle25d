"""pixlib.py — petite bibliothèque de peinture pixel art (couleur + hauteur + émission)."""
import math, os
import numpy as np
from PIL import Image

def hexc(s):
    s = s.lstrip("#"); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)

PALETTE = {k: hexc(v) for k, v in {
    # nuit urbaine (silhouettes bleutées)
    "n0": "070a14", "n1": "0c1222", "n2": "131b31", "n3": "1c2642", "n4": "263355", "n5": "33436b", "n6": "475a86",
    # variantes teintées
    "t0": "0e0f22", "t1": "16183a", "t2": "211f4a",          # violacé
    "q0": "081418", "q1": "0e2026", "q2": "162f36",          # sarcelle
    # métal / béton nocturne
    "m0": "0b0e14", "m1": "151a24", "m2": "202836", "m3": "2e384a", "m4": "44506a",
    # fenêtres (émissif)
    "wy0": "4a2a10", "wy1": "a35e22", "wy2": "e09a48", "wy3": "ffd492",
    "wc0": "123a4a", "wc1": "2f8ca8", "wc2": "8fe3f2", "wc3": "e6fbff",
    "wr": "ff3b2a", "wrd": "5a1410",
    # néons
    "np": "ff3d8b", "nc": "3de8ff", "ng": "7dff6a", "no": "ffa23a", "nv": "b46bff", "ny": "fff06a", "nw": "f4f0ff",
    "black": "05060a", "white": "f2efe6",
}.items()}

class Canvas:
    def __init__(self, w, h, seed=0, transparent=True):
        self.W, self.H = w, h
        self.alb = np.zeros((h, w, 3), np.uint8)
        self.alpha = np.zeros((h, w), np.uint8) if transparent else np.full((h, w), 255, np.uint8)
        self.hgt = np.zeros((h, w), np.float32)
        self.emi = np.zeros((h, w, 3), np.uint8)
        self.rng = np.random.default_rng(seed)

    @staticmethod
    def col(c):
        return PALETTE[c] if isinstance(c, str) else np.asarray(c, np.uint8)

    def rect(self, x, y, w, h, c, emi=None, hgt=None, opaque=True):
        x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(self.W, int(x + w)), min(self.H, int(y + h))
        if x1 <= x0 or y1 <= y0: return
        self.alb[y0:y1, x0:x1] = self.col(c)
        if opaque: self.alpha[y0:y1, x0:x1] = 255
        if emi is not None: self.emi[y0:y1, x0:x1] = self.col(emi)
        if hgt is not None: self.hgt[y0:y1, x0:x1] = hgt

    def px(self, x, y, c, emi=None):
        x, y = int(x), int(y)
        if 0 <= x < self.W and 0 <= y < self.H:
            self.alb[y, x] = self.col(c); self.alpha[y, x] = 255
            if emi is not None: self.emi[y, x] = self.col(emi)

    def hline(self, x, y, w, c, emi=None): self.rect(x, y, w, 1, c, emi)
    def vline(self, x, y, h, c, emi=None): self.rect(x, y, 1, h, c, emi)

    def line(self, x0, y0, x1, y1, c, emi=None):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) or 1
        for i in range(n + 1):
            self.px(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), c, emi)

    def frame(self, x, y, w, h, c):
        self.hline(x, y, w, c); self.hline(x, y + h - 1, w, c); self.vline(x, y, h, c); self.vline(x + w - 1, y, h, c)

    def dim(self, x, y, w, h, k):
        x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(self.W, int(x + w)), min(self.H, int(y + h))
        if x1 > x0 and y1 > y0:
            self.alb[y0:y1, x0:x1] = (self.alb[y0:y1, x0:x1] * k).astype(np.uint8)

    def glyph_random(self, x, y, w, h, c, emi=None, density=0.5):
        g = self.rng.random((h, w)) < density
        g[h // 2, :] |= self.rng.random() < 0.6
        g[:, w // 2] |= self.rng.random() < 0.6
        for j in range(h):
            for i in range(w):
                if g[j, i]: self.px(x + i, y + j, c, emi)

    def catenary(self, xa, ya, xb, yb, sag, c):
        for x in range(int(xa), int(xb) + 1):
            t = (x - xa) / max(1, xb - xa)
            self.px(x, ya + (yb - ya) * t + sag * 4 * t * (1 - t), c)

    def save(self, out_dir, name, normal=False, emi_scale=1.0):
        os.makedirs(out_dir, exist_ok=True)
        Image.fromarray(np.dstack([self.alb, self.alpha]), "RGBA").save(os.path.join(out_dir, f"{name}.png"))
        e = np.clip(self.emi.astype(np.float32) * emi_scale, 0, 255).astype(np.uint8)
        Image.fromarray(np.dstack([e, np.full((self.H, self.W), 255, np.uint8)]), "RGBA").save(os.path.join(out_dir, f"{name}_emit.png"))
        if normal:
            h = self.hgt
            gx = np.zeros_like(h); gy = np.zeros_like(h)
            gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
            gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
            n = np.dstack([-gx, gy, np.full_like(h, 1.2)])
            n /= np.linalg.norm(n, axis=2, keepdims=True)
            Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB").save(os.path.join(out_dir, f"{name}_normal.png"))

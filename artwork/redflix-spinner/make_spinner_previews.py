"""Generate 3 animated preview GIFs of the Red Light neon icon.

A: smooth pulse   B: neon flicker   C: rotating glow sweep
Previews are composited on dark background (final Kodi frames stay transparent).
"""
import math
import numpy as np
from PIL import Image, ImageFilter

import pathlib
HERE = pathlib.Path(__file__).resolve().parent
SRC = str(HERE / "icon.png")
OUT = str(HERE)
N_FRAMES = 36
DUR_MS = 50
BG = (17, 17, 17)

base = Image.open(SRC).convert("RGBA")
W, H = base.size
arr = np.asarray(base).astype(np.float32)
R, G, B, A = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

# mask of neon (saturated red) pixels, softened
neon = ((R > 110) & (R > G * 1.45) & (R > B * 1.45) & (A > 40)).astype(np.float32)
neon_img = Image.fromarray((neon * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(2))
neon_soft = np.asarray(neon_img).astype(np.float32) / 255.0

# outer glow layer: neon pixels blurred wide
glow_src = arr.copy()
glow_src[..., 3] = glow_src[..., 3] * neon_soft
glow_img = Image.fromarray(glow_src.astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(14))
glow = np.asarray(glow_img).astype(np.float32)

# pixel angle around center (for sweep)
yy, xx = np.mgrid[0:H, 0:W]
ang = np.arctan2(yy - H / 2, xx - W / 2)  # -pi..pi


def render(intensity, sweep_angle=None):
    """intensity 1.0 = original. Returns RGB frame on dark bg."""
    out = arr.copy()
    # scale neon brightness toward intensity, leave rim alone
    for c in range(3):
        out[..., c] = out[..., c] * (1 + (intensity - 1) * neon_soft)
    if sweep_angle is not None:
        d = np.abs(np.arctan2(np.sin(ang - sweep_angle), np.cos(ang - sweep_angle)))
        band = np.clip(1 - d / 0.55, 0, 1) ** 2  # bright band ~63deg wide
        boost = band * neon_soft
        for c in range(3):
            out[..., c] = out[..., c] + 90 * boost
    out = np.clip(out, 0, 255)
    # composite additive glow scaled by intensity
    frame = Image.new("RGBA", (W, H), BG + (255,))
    g = glow.copy()
    g[..., 3] = np.clip(g[..., 3] * (0.55 * intensity), 0, 255)
    frame.alpha_composite(Image.fromarray(g.astype(np.uint8), "RGBA"))
    frame.alpha_composite(Image.fromarray(out.astype(np.uint8), "RGBA"))
    return frame.convert("RGB")


def save(name, frames):
    frames[0].save(
        str(HERE / f"{name}.gif"), save_all=True, append_images=frames[1:],
        duration=DUR_MS, loop=0, optimize=False)
    print(name, "done")


# A: smooth pulse 0.72..1.18
save("a_pulse", [render(0.95 + 0.23 * math.sin(2 * math.pi * i / N_FRAMES))
                 for i in range(N_FRAMES)])

# B: flicker — pulse baseline with deterministic sharp dips
rng = np.random.default_rng(7)
levels = [0.95 + 0.18 * math.sin(2 * math.pi * i / N_FRAMES) for i in range(N_FRAMES)]
for i in (5, 6, 14, 23, 24, 25, 31):
    levels[i] *= rng.uniform(0.45, 0.7)
save("b_flicker", [render(l) for l in levels])

# C: rotating glow sweep, steady base
save("c_sweep", [render(1.0, sweep_angle=2 * math.pi * i / N_FRAMES - math.pi)
                 for i in range(N_FRAMES)])

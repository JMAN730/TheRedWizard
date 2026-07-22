"""D upgraded: coin spin with real thickness.

Coin = front face + back face + stack of edge slices between them,
each perspective-projected at its own depth. Drawn back-to-front.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import pathlib
HERE = pathlib.Path(__file__).resolve().parent
SRC = str(HERE / "icon.png")
OUT = str(HERE)
BG = (17, 17, 17)
S = 512
C = S / 2
F = 900.0
T = 40          # coin thickness px
SLICE_STEP = 4  # px between edge slices
DUR_MS = 40
N = 40

front = Image.open(SRC).convert("RGBA")
alpha = front.split()[3]
back = front.transpose(Image.FLIP_LEFT_RIGHT)
back = Image.merge("RGBA", [ch.point(lambda v: int(v * 0.55)) for ch in back.split()[:3]] + [back.split()[3]])

# edge slice: metal disc using icon silhouette, vertical cylinder shading
grad = np.tile(np.linspace(120, 45, S).reshape(S, 1), (1, S))  # bright top -> dark bottom
edge_rgb = np.stack([grad, grad, grad], axis=-1).astype(np.uint8)
edge_slice = Image.fromarray(edge_rgb, "RGB").convert("RGBA")
edge_slice.putalpha(alpha.filter(ImageFilter.MaxFilter(3)))


def find_coeffs(target, source):
    A = []
    for (x, y), (X, Y) in zip(target, source):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
    b = np.array(target, dtype=np.float64).reshape(8)
    return np.linalg.solve(np.array(A, dtype=np.float64), b)


def project_quad(theta, d):
    """Corners of face plane rotated theta about vertical axis, offset d along normal."""
    ct, st = math.cos(theta), math.sin(theta)
    pts = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = sx * C, sy * C
        wx = x * ct - d * st
        wy = y
        wz = x * st + d * ct
        p = F / (F + wz)
        pts.append((C + wx * p, C + wy * p))
    return pts


def place(img, theta, d, mirror):
    quad = project_quad(theta, d)
    src = [(0, 0), (S, 0), (S, S), (0, S)]
    if mirror:
        src = [(S, 0), (0, 0), (0, S), (S, S)]
    inv = find_coeffs(src, quad)
    return img.transform((S, S), Image.PERSPECTIVE, inv, Image.BICUBIC)


def render(theta):
    ct = math.cos(theta)
    frame = Image.new("RGBA", (S, S), BG + (255,))
    half = T / 2
    depths = np.arange(-half, half + 0.1, SLICE_STEP)
    # far to near
    order = depths[::-1] if ct >= 0 else depths
    for d in order:
        # shade edge by how far toward the back it sits
        shade = 0.75 + 0.25 * (-d / half if ct >= 0 else d / half)
        sl = edge_slice.copy()
        px = np.asarray(sl).astype(np.float32)
        px[..., :3] *= shade
        sl = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8), "RGBA")
        frame.alpha_composite(place(sl, theta, d, mirror=False))
    if ct >= 0:
        frame.alpha_composite(place(front, theta, -half, mirror=False))
    else:
        frame.alpha_composite(place(back, theta, half, mirror=True))
    return frame.convert("RGB")


frames = [render(2 * math.pi * i / N) for i in range(N)]
frames[0].save(f"{OUT}\\g_spin3d.gif", save_all=True, append_images=frames[1:],
               duration=DUR_MS, loop=0, optimize=False)
frames[6].save(f"{OUT}\\chk3d_6.png")
frames[12].save(f"{OUT}\\chk3d_12.png")
print("done")

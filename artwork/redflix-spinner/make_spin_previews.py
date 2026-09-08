"""Coin-flip / spin previews of the Red Light icon.

D: continuous Y-axis spin
E: flip 180, pause, flip again
F: vertical tumble (X-axis)
Back face = mirrored + darkened. Perspective-warped, composited on dark bg.
"""
import math
import numpy as np
from PIL import Image

import pathlib
HERE = pathlib.Path(__file__).resolve().parent
SRC = str(HERE / "icon.png")
OUT = str(HERE)
BG = (17, 17, 17)
S = 512
C = S / 2
F = 900.0  # perspective focal length
DUR_MS = 40

front = Image.open(SRC).convert("RGBA")
back = front.transpose(Image.FLIP_LEFT_RIGHT)
back = Image.merge("RGBA", [ch.point(lambda v: int(v * 0.55)) for ch in back.split()[:3]] + [back.split()[3]])
back_v = front.transpose(Image.FLIP_TOP_BOTTOM)
back_v = Image.merge("RGBA", [ch.point(lambda v: int(v * 0.55)) for ch in back_v.split()[:3]] + [back_v.split()[3]])


def find_coeffs(target, source):
    A = []
    for (x, y), (X, Y) in zip(target, source):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
    A = np.array(A, dtype=np.float64)
    b = np.array(target, dtype=np.float64).reshape(8)
    return np.linalg.solve(A, b)


def frame_y(theta):
    """Rotation around vertical axis by theta."""
    c, s = math.cos(theta), math.sin(theta)
    img = front if c >= 0 else back
    c_abs = max(abs(c), 0.04)
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):  # TL TR BR BL of source
        z = sx * s * C
        p = F / (F + z)
        corners.append((C + sx * c_abs * C * p, C + sy * C * p))
    src = [(0, 0), (S, 0), (S, S), (0, S)]
    if c < 0:  # back face: mirrored image, swap left/right mapping
        src = [(S, 0), (0, 0), (0, S), (S, S)]
    coeffs = find_coeffs(corners, src)
    # PIL PERSPECTIVE wants inverse mapping (output->input)
    inv = find_coeffs(src, corners)
    return img.transform((S, S), Image.PERSPECTIVE, inv, Image.BICUBIC)


def frame_x(theta):
    """Tumble around horizontal axis."""
    c, s = math.cos(theta), math.sin(theta)
    img = front if c >= 0 else back_v
    c_abs = max(abs(c), 0.04)
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        z = sy * s * C
        p = F / (F + z)
        corners.append((C + sx * C * p, C + sy * c_abs * C * p))
    src = [(0, 0), (S, 0), (S, S), (0, S)]
    if c < 0:
        src = [(0, S), (S, S), (S, 0), (0, 0)]
    inv = find_coeffs(src, corners)
    return img.transform((S, S), Image.PERSPECTIVE, inv, Image.BICUBIC)


def on_bg(im):
    f = Image.new("RGBA", (S, S), BG + (255,))
    f.alpha_composite(im)
    return f.convert("RGB")


def save(name, frames):
    frames[0].save(str(HERE / f"{name}.gif"), save_all=True, append_images=frames[1:],
                   duration=DUR_MS, loop=0, optimize=False)
    print(name, "done")


def ease(t):
    return t * t * (3 - 2 * t)  # smoothstep


# D: continuous spin, 40 frames = 1.6s per revolution
N = 40
save("d_spin", [on_bg(frame_y(2 * math.pi * i / N)) for i in range(N)])

# E: flip 180 (14 frames eased), hold 12, flip back 14, hold 12
frames = []
for i in range(14):
    frames.append(on_bg(frame_y(math.pi * ease(i / 13))))
frames += [frames[-1]] * 12
for i in range(14):
    frames.append(on_bg(frame_y(math.pi + math.pi * ease(i / 13))))
frames += [frames[-1]] * 12
save("e_flip_pause", frames)

# F: vertical tumble, continuous
save("f_tumble", [on_bg(frame_x(2 * math.pi * i / N)) for i in range(N)])

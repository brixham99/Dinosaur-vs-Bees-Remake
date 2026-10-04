"""Asset loading, tinting and per-theme art."""
import json
import os

import numpy as np
import pygame

from .settings import ASSET_DIR, FONT_PATH

_font_cache = {}


def path(name):
    return os.path.join(ASSET_DIR, name)


def load(name, alpha=True):
    img = pygame.image.load(path(name))
    return img.convert_alpha() if alpha else img.convert()


def load_meta():
    try:
        with open(path("meta.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def font(size):
    if size not in _font_cache:
        try:
            _font_cache[size] = pygame.font.Font(FONT_PATH, size)
        except (OSError, FileNotFoundError):
            _font_cache[size] = pygame.font.Font(None, int(size * 1.25))
    return _font_cache[size]


def tint(surface, mul=(1, 1, 1), add=(0, 0, 0)):
    """Return a colour-graded copy: rgb * mul + add (alpha untouched)."""
    if tuple(mul) == (1, 1, 1) and tuple(add) == (0, 0, 0):
        return surface.copy()
    s = surface.copy()
    rgb = pygame.surfarray.pixels3d(s)
    arr = rgb.astype(np.float32)
    arr *= np.asarray(mul, np.float32)
    arr += np.asarray(add, np.float32)
    rgb[...] = np.clip(arr, 0, 255).astype(np.uint8)
    del rgb
    return s


def additive_glow(radius, colour, peak=1.0, power=2.0):
    """A premultiplied radial glow (black = no effect) for BLEND_RGB_ADD."""
    surf = pygame.Surface((radius * 2, radius * 2)).convert()
    surf.fill((0, 0, 0))
    for r in range(radius, 0, -2):
        k = peak * (1 - r / radius) ** power
        pygame.draw.circle(surf, tuple(int(c * k) for c in colour), (radius, radius), r)
    return surf


def tint_colour(c, mul=(1, 1, 1), add=(0, 0, 0)):
    return tuple(int(max(0, min(255, c[i] * mul[i] + add[i]))) for i in range(3))


def scale(surface, factor):
    w, h = surface.get_size()
    return pygame.transform.smoothscale(surface, (max(1, round(w * factor)), max(1, round(h * factor))))


# ------------------------------------------------------------------ themes
# Each theme grades every layer in code; the art itself is the daytime set.
THEMES = [
    {
        "name": "Day",
        "sky": ((1, 1, 1), (0, 0, 0)),
        "mountains": ((1, 1, 1), (0, 0, 0)),
        "hills": ((1, 1, 1), (0, 0, 0)),
        "ground": ((1, 1, 1), (0, 0, 0)),
        "sprite": ((1, 1, 1), (0, 0, 0)),
        "stars": False, "volcano": False, "sun": "day",
        "clear": (120, 190, 235),
    },
    {
        "name": "Sunset",
        "sky": ((1.06, 0.70, 0.60), (38, 6, 22)),
        "mountains": ((0.92, 0.66, 0.74), (34, 4, 14)),
        "hills": ((0.98, 0.76, 0.58), (18, 2, 0)),
        "ground": ((0.98, 0.80, 0.66), (10, 0, 0)),
        "sprite": ((1.0, 0.88, 0.78), (10, 2, 0)),
        "stars": False, "volcano": False, "sun": "sunset",
        "clear": (230, 140, 110),
    },
    {
        "name": "Night",
        "sky": ((0.20, 0.25, 0.46), (4, 8, 26)),
        "mountains": ((0.34, 0.38, 0.62), (4, 6, 20)),
        "hills": ((0.30, 0.40, 0.55), (0, 4, 16)),
        "ground": ((0.36, 0.40, 0.56), (0, 2, 14)),
        "sprite": ((0.66, 0.72, 0.92), (0, 4, 18)),
        "stars": True, "volcano": False, "sun": "moon",
        "clear": (14, 20, 48),
    },
    {
        "name": "Volcano Glow",
        "sky": ((0.78, 0.36, 0.30), (46, 4, 0)),
        "mountains": ((0.62, 0.34, 0.40), (44, 0, 0)),
        "hills": ((0.62, 0.44, 0.38), (26, 0, 0)),
        "ground": ((0.72, 0.52, 0.44), (22, 0, 0)),
        "sprite": ((0.98, 0.80, 0.70), (16, 0, 0)),
        "stars": False, "volcano": True, "sun": "red",
        "clear": (120, 40, 30),
    },
]


def theme_index_for_level(level):
    return (level - 1) % len(THEMES)

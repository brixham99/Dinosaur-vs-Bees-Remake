"""Text and HUD drawing helpers."""
import math
from collections import OrderedDict

import pygame

from . import assets

_cache = OrderedDict()


def text(msg, size, colour=(255, 255, 255), shadow=True, outline=0, outline_colour=(40, 28, 20)):
    """Render text with an optional soft shadow and outline (cached)."""
    key = (msg, size, colour, shadow, outline, outline_colour)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    f = assets.font(size)
    base = f.render(msg, True, colour)
    w, h = base.get_size()
    pad = outline + (4 if shadow else 0)
    surf = pygame.Surface((w + pad * 2 + 2, h + pad * 2 + 2), pygame.SRCALPHA)
    if shadow:
        sh = f.render(msg, True, (10, 14, 30))
        sh.set_alpha(110)
        off = max(2, size // 16)
        for dx, dy in ((off, off), (off + 1, off + 1)):
            surf.blit(sh, (pad + dx, pad + dy))
    if outline:
        ol = f.render(msg, True, outline_colour)
        steps = 16
        for i in range(steps):
            a = math.tau * i / steps
            surf.blit(ol, (pad + round(math.cos(a) * outline), pad + round(math.sin(a) * outline)))
    surf.blit(base, (pad, pad))
    _cache[key] = surf
    if len(_cache) > 400:
        _cache.popitem(last=False)
    return surf


def blit_text(surf, msg, size, pos, colour=(255, 255, 255), anchor="topleft", **kw):
    img = text(msg, size, colour, **kw)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def make_heart(size, filled=True):
    ss = 4
    s = pygame.Surface((size * ss, size * ss), pygame.SRCALPHA)
    pts = []
    for i in range(80):
        t = math.tau * i / 80
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x, y))
    def tr(scale, ox=0, oy=0):
        return [(size * ss / 2 + (x * scale + ox) * size * ss / 36, size * ss / 2 + (y * scale + oy + 1) * size * ss / 36) for x, y in pts]
    pygame.draw.polygon(s, (60, 10, 20), tr(1.06))
    if filled:
        pygame.draw.polygon(s, (226, 40, 60), tr(0.92))
        pygame.draw.polygon(s, (250, 90, 100), tr(0.55, -3, -3))
        pygame.draw.ellipse(s, (255, 210, 210), pygame.Rect(size * ss * 0.24, size * ss * 0.22, size * ss * 0.16, size * ss * 0.12))
    else:
        pygame.draw.polygon(s, (90, 70, 80), tr(0.92))
        pygame.draw.polygon(s, (60, 45, 55), tr(0.6))
    return pygame.transform.smoothscale(s, (size, size))


def panel(size, alpha=150, radius=18):
    s = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(s, (16, 22, 44, alpha), s.get_rect(), border_radius=radius)
    pygame.draw.rect(s, (255, 255, 255, 40), s.get_rect(), width=2, border_radius=radius)
    return s

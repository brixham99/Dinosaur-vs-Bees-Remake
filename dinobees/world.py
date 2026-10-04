"""The scrolling world: sky, mountains, hills, ground and a near foreground."""
import math
import numpy as np
import pygame

from . import assets
from .assets import THEMES
from .settings import (FOREGROUND_FACTOR, GROUND_FACTOR, HEIGHT, HILL_FACTOR,
                       MOUNTAIN_FACTOR, SKY_DRIFT, SKY_FACTOR, WIDTH)


def _grass_row(surface):
    """First row of the ground strip that is (almost) fully opaque."""
    alpha = pygame.surfarray.array_alpha(surface)  # (w, h)
    cover = (alpha > 200).mean(axis=0)
    rows = np.where(cover > 0.92)[0]
    return int(rows[0]) if len(rows) else surface.get_height() // 4


def _crater(surface):
    """Locate the glowing volcano crater (orange pixels) in the mountains."""
    rgb = pygame.surfarray.array3d(surface).astype(int)
    a = pygame.surfarray.array_alpha(surface)
    m = (rgb[..., 0] > 200) & (rgb[..., 1] > 90) & (rgb[..., 1] < 200) & (rgb[..., 2] < 120) & (a > 200)
    xs, ys = np.where(m)
    if len(xs) < 5:
        return surface.get_width() // 2, surface.get_height() // 3
    return int(np.median(xs)), int(np.median(ys))


class World:
    def __init__(self, rng):
        self.rng = rng
        base = {
            "sky": assets.load("layer_sky.png", alpha=False),
            "mountains": assets.load("layer_mountains.png"),
            "hills": assets.load("layer_hills.png"),
            "ground": assets.load("layer_ground.png"),
        }
        self.grass_in_strip = _grass_row(base["ground"])
        self.ground_y = HEIGHT - base["ground"].get_height()
        self.grass_y = self.ground_y + self.grass_in_strip + 6   # where feet land
        hills_h = base["hills"].get_height()
        self.hills_y = self.ground_y + self.grass_in_strip + 34 - hills_h
        self.mountains_y = self.hills_y + 150 - base["mountains"].get_height()
        self.crater = _crater(base["mountains"])
        self.mountains_h = base["mountains"].get_height()

        ferns = [assets.scale(assets.load(f"fern{i}.png"), 1.3) for i in range(2)]
        self.fg_base = ferns + [pygame.transform.flip(f, True, False) for f in ferns]
        # colour of the foot of the mountains, used to fill any gaps between hills
        m = base["mountains"]
        self.mountain_base_rgb = tuple(int(v) for v in np.median(
            pygame.surfarray.array3d(m)[:, -3, :], axis=0))

        # pre-grade every layer for every theme
        self.layers = []
        for th in THEMES:
            d = {}
            for k, surf in base.items():
                mul, add = th[k]
                d[k] = self._split(assets.tint(surf, mul, add))
            mul, add = th["ground"]
            d["fg"] = [assets.tint(s, mul, add) for s in self.fg_base]
            mul, add = th["mountains"]
            d["mountain_fill"] = assets.tint_colour(self.mountain_base_rgb, mul, add)
            d["sun"] = self._make_sun(th)
            self.layers.append(d)

        self.scroll = 0.0
        self.time = 0.0
        self.theme = 0
        self.prev_theme = 0
        self.fade = 1.0            # 0..1 progress of a theme cross-fade
        self.star_alpha = 0.0
        self.volcano_amt = 0.0
        self.stars = [(rng.uniform(0, WIDTH), rng.uniform(4, self.mountains_y + 190),
                       rng.uniform(0, math.tau), rng.choice((1, 1, 1, 2, 2, 3)))
                      for _ in range(130)]
        self.embers = []
        self.foreground = []
        x = 300.0
        while x < WIDTH + 600:
            self.foreground.append(self._new_fg(x))
            x += rng.uniform(380, 900)
        self.glows = [assets.additive_glow(200, (255, 110, 30), 0.35 + 0.65 * i / 7) for i in range(8)]
        self.star_imgs = {}
        for size in (1, 2, 3):
            for lv in range(8):
                k = (lv + 1) / 8
                r = 4 if size == 3 else 2
                img = pygame.Surface((r * 2 + 1, r * 2 + 1)).convert()
                img.fill((0, 0, 0))
                c = (int(255 * k), int(255 * k), int(min(255, 275 * k)))
                if size == 1:
                    img.fill(c, (r, r, 2, 2))
                elif size == 2:
                    pygame.draw.circle(img, c, (r, r), 1.5)
                else:
                    pygame.draw.circle(img, c, (r, r), 2)
                    img.fill(c, (0, r, r * 2 + 1, 1))
                    img.fill(c, (r, 0, 1, r * 2 + 1))
                self.star_imgs[(size, lv)] = img

    # ---------------------------------------------------------------- utils
    def _new_fg(self, screen_x):
        idx = self.rng.randrange(len(self.fg_base))
        world_x = screen_x + self.scroll * FOREGROUND_FACTOR
        depth = self.rng.uniform(16, 34)
        return [world_x, idx, depth]

    @staticmethod
    def _make_sun(th):
        """A soft sun (or moon) drawn per theme; returns (surface, centre)."""
        kind = th.get("sun", "day")
        if kind == "moon":
            r, glow, col, gcol, pos = 38, 120, (238, 240, 255), (150, 170, 255), (1010, 120)
        elif kind == "sunset":
            r, glow, col, gcol, pos = 66, 220, (255, 196, 120), (255, 120, 60), (300, 262)
        elif kind == "red":
            r, glow, col, gcol, pos = 52, 190, (255, 120, 70), (255, 60, 20), (230, 170)
        else:
            r, glow, col, gcol, pos = 50, 170, (255, 238, 170), (255, 220, 120), (220, 150)
        size = glow * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for rr in range(glow, r, -2):
            a = int(120 * (1 - (rr - r) / (glow - r)) ** 2.2)
            pygame.draw.circle(surf, (*gcol, a), (glow, glow), rr)
        ss = 4
        disc = pygame.Surface((r * 2 * ss + 8, r * 2 * ss + 8), pygame.SRCALPHA)
        c = (r * ss + 4, r * ss + 4)
        rim = tuple(int(v * 0.93) for v in col)
        for i in range(r * ss, 0, -2):      # soft radial shading, brighter in the middle
            f = (i / (r * ss)) ** 2
            cc = tuple(int(rim[j] * f + min(255, col[j] + 25) * (1 - f)) for j in range(3))
            pygame.draw.circle(disc, (*cc, 255), c, i)
        if kind == "moon":
            for ox, oy, cr in ((-0.3, -0.2, 0.22), (0.25, 0.1, 0.16), (-0.05, 0.4, 0.12), (0.35, -0.35, 0.1)):
                pygame.draw.circle(disc, (205, 210, 232, 255), (c[0] + ox * r * ss, c[1] + oy * r * ss), cr * r * ss)
        disc = pygame.transform.smoothscale(disc, (r * 2 + 2, r * 2 + 2))
        surf.blit(disc, disc.get_rect(center=(glow, glow)))
        return surf, pos

    def set_theme(self, idx, instant=False):
        if idx == self.theme and self.fade >= 1.0:
            return
        self.prev_theme = self.theme if not instant else idx
        self.theme = idx
        self.fade = 1.0 if instant else 0.0
        if instant:
            self.star_alpha = 1.0 if THEMES[idx]["stars"] else 0.0
            self.volcano_amt = 1.0 if THEMES[idx]["volcano"] else 0.0

    @property
    def sprite_theme(self):
        """Theme used for sprites (switches half-way through a fade)."""
        return self.theme if self.fade >= 0.5 else self.prev_theme

    # --------------------------------------------------------------- update
    def update(self, dt, speed):
        self.scroll += speed * dt
        self.time += dt
        if self.fade < 1.0:
            self.fade = min(1.0, self.fade + dt / 1.6)
            if self.fade >= 1.0:
                for parts in self.layers[self.theme].values():
                    if isinstance(parts, list) and parts and isinstance(parts[0], tuple):
                        for layer, _ in parts:
                            if layer.get_alpha() not in (None, 255):
                                layer.set_alpha(None)
        th = THEMES[self.theme]
        target = 1.0 if th["stars"] else 0.0
        self.star_alpha += (target - self.star_alpha) * min(1.0, dt * 1.2)
        target = 1.0 if th["volcano"] else 0.0
        self.volcano_amt += (target - self.volcano_amt) * min(1.0, dt * 1.2)

        # foreground ferns
        right_edge = max(o[0] - self.scroll * FOREGROUND_FACTOR for o in self.foreground)
        self.foreground = [o for o in self.foreground
                           if o[0] - self.scroll * FOREGROUND_FACTOR > -200]
        if right_edge < WIDTH + 100:
            self.foreground.append(self._new_fg(right_edge + self.rng.uniform(420, 1000)))

        # volcano embers
        if self.volcano_amt > 0.05:
            if self.rng.random() < 0.6 * self.volcano_amt:
                self.embers.append([self.rng.uniform(0, WIDTH), HEIGHT + 5,
                                    self.rng.uniform(-30, 10), self.rng.uniform(-70, -30),
                                    self.rng.uniform(3, 6)])
        for e in self.embers:
            e[0] += (e[2] - speed * 0.4) * dt
            e[1] += e[3] * dt
            e[4] -= dt
        self.embers = [e for e in self.embers if e[4] > 0 and e[1] > -10]

    # ----------------------------------------------------------------- draw
    @staticmethod
    def _split(surf):
        """Split a layer into a translucent top and a fully opaque bottom
        (blitting opaque pixels is much cheaper than alpha blending)."""
        if surf.get_flags() & pygame.SRCALPHA == 0:
            return [(surf, 0)]
        a = pygame.surfarray.array_alpha(surf)
        solid_rows = (a == 255).all(axis=0)
        h = surf.get_height()
        cut = h
        while cut > 0 and solid_rows[cut - 1]:
            cut -= 1
        if cut >= h - 8:
            return [(surf, 0)]
        w = surf.get_width()
        top = surf.subsurface((0, 0, w, cut)).copy() if cut > 0 else None
        bottom = surf.subsurface((0, cut, w, h - cut)).convert()
        parts = [(bottom, cut)]
        if top is not None:
            parts.insert(0, (top, 0))
        return parts

    @staticmethod
    def _tile(surf, parts, offset, y, alpha=None):
        tw = parts[0][0].get_width()
        x0 = -(offset % tw)
        for layer, dy in parts:
            if alpha is not None and layer.get_alpha() != alpha:
                layer.set_alpha(alpha)   # left set; cleared once the fade ends
            x = x0
            while x < WIDTH:
                surf.blit(layer, (round(x), y + dy))
                x += tw

    def draw_background(self, surf):
        """Sky, mountains, hills and ground (everything behind the dino)."""
        s = self.scroll
        offsets = {
            "sky": s * SKY_FACTOR + self.time * SKY_DRIFT,
            "mountains": s * MOUNTAIN_FACTOR,
            "hills": s * HILL_FACTOR,
            "ground": s * GROUND_FACTOR,
        }
        ys = {"sky": 0, "mountains": self.mountains_y, "hills": self.hills_y, "ground": self.ground_y}
        cur = self.layers[self.theme]
        prev = self.layers[self.prev_theme]
        fading = self.fade < 1.0
        a = int(255 * self.fade)
        for k in ("sky", "mountains", "hills", "ground"):
            if fading:
                # opaque layer parts take the fast constant-alpha path
                self._tile(surf, prev[k], offsets[k], ys[k])
                self._tile(surf, cur[k], offsets[k], ys[k], alpha=a)
            else:
                self._tile(surf, cur[k], offsets[k], ys[k])
            if k == "sky":
                self._draw_stars(surf)
                self._draw_sun(surf, prev, cur, a if fading else None)
            elif k == "mountains":
                self._draw_volcano_glow(surf, offsets[k])
                bottom = self.mountains_y + self.mountains_h
                surf.fill(cur["mountain_fill"], (0, bottom, WIDTH, self.ground_y + 80 - bottom))

    def _draw_sun(self, surf, prev, cur, alpha):
        drift = math.sin(self.time * 0.05) * 20
        if alpha is not None:
            img, pos = prev["sun"]
            surf.blit(img, img.get_rect(center=(pos[0] + drift, pos[1])))
            img, pos = cur["sun"]
            img.set_alpha(alpha)
            surf.blit(img, img.get_rect(center=(pos[0] + drift, pos[1])))
            img.set_alpha(None)
        else:
            img, pos = cur["sun"]
            surf.blit(img, img.get_rect(center=(pos[0] + drift, pos[1])))

    def _draw_stars(self, surf):
        if self.star_alpha < 0.02:
            return
        off = (self.scroll * SKY_FACTOR * 0.5) % WIDTH
        imgs = self.star_imgs
        for x, y, ph, size in self.stars:
            tw = 0.55 + 0.45 * math.sin(self.time * (1.5 + size * 0.7) + ph)
            lv = int(8 * self.star_alpha * tw) - 1
            if lv < 0:
                continue
            img = imgs[(size, min(7, lv))]
            r = img.get_width() // 2
            surf.blit(img, (int((x - off) % WIDTH) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_volcano_glow(self, surf, offset):
        if self.volcano_amt < 0.02:
            return
        tw = self.layers[0]["mountains"][0][0].get_width()
        cx, cy = self.crater
        pulse = 0.72 + 0.2 * math.sin(self.time * 2.3) + 0.08 * math.sin(self.time * 7.1)
        level = int(round(7 * max(0.0, min(1.0, self.volcano_amt * pulse))))
        g = self.glows[level]
        x = cx - (offset % tw)
        while x < WIDTH + tw:
            if -300 < x < WIDTH + 300:
                surf.blit(g, (round(x - g.get_width() / 2), self.mountains_y + cy - g.get_height() / 2),
                          special_flags=pygame.BLEND_RGB_ADD)
            x += tw

    def draw_foreground(self, surf):
        d = self.layers[self.sprite_theme]["fg"]
        for wx, idx, depth in self.foreground:
            img = d[idx]
            x = wx - self.scroll * FOREGROUND_FACTOR
            y = self.grass_y + depth - img.get_height()
            surf.blit(img, (round(x), round(y)))
        if self.embers:
            for x, y, vx, vy, life in self.embers:
                a = min(1.0, life / 2.0) * self.volcano_amt
                c = (255, int(110 + 120 * a), int(40 + 60 * a))
                surf.fill(c, (int(x), int(y), 3 if a > 0.5 else 2, 3 if a > 0.5 else 2))

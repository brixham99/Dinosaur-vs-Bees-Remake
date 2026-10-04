"""Bees: art, flight patterns and the level-driven spawner."""
import math

import pygame

from . import assets
from .assets import THEMES
from .settings import WIDTH

BEE_SCALE = 0.21
ANGLES = (-16, -8, 0, 8, 16)
KINDS = ("yellow", "red", "gold")


def _red_flap_frame(red):
    """The red bee art has a single frame: make a wings-lowered frame by
    squashing the wing area towards the body."""
    w, h = red.get_size()
    out = red.copy()
    wing_x, wing_y = int(w * 0.42), int(h * 0.47)
    wings = red.subsurface((wing_x, 0, w - wing_x, wing_y)).copy()
    # only the pale wing pixels (not body/antennae) move
    rgb = pygame.surfarray.pixels3d(wings)
    al = pygame.surfarray.pixels_alpha(wings)
    pale = (rgb[..., 2] > 150) & (rgb[..., 1] > 150)
    al[~pale] = 0
    del rgb, al
    orgb = pygame.surfarray.pixels3d(out)
    oal = pygame.surfarray.pixels_alpha(out)
    region_rgb = orgb[wing_x:, :wing_y]
    region_al = oal[wing_x:, :wing_y]
    pale_o = (region_rgb[..., 2] > 150) & (region_rgb[..., 1] > 150)
    region_al[pale_o] = 0
    del orgb, oal, region_rgb, region_al
    squashed = pygame.transform.smoothscale(wings, (wings.get_width(), int(wing_y * 0.62)))
    out.blit(squashed, (wing_x, wing_y - squashed.get_height() + 6))
    return out


def _sparkle(r):
    """A small four-pointed additive glint."""
    s = pygame.Surface((2 * r + 1, 2 * r + 1))
    for i in range(r, 0, -1):
        v = int(255 * (1 - i / (r + 1)) ** 1.5)
        c = (v, int(v * 0.9), int(v * 0.55))
        pygame.draw.line(s, c, (r - i, r), (r + i, r))
        pygame.draw.line(s, c, (r, r - i), (r, r + i))
    pygame.draw.circle(s, (255, 240, 190), (r, r), 2)
    return s


def _gold(surface):
    # a rich metallic gold: warm the whole bee (wings included) so it reads
    # as clearly different from an ordinary yellow bee, even at night
    s = assets.tint(surface, (1.12, 0.90, 0.30), (45, 30, 0))
    return s


class BeeArt:
    def __init__(self):
        up = assets.load("bee_up.png")
        down = assets.load("bee_down.png")
        red = assets.load("bee_red.png")
        red2 = _red_flap_frame(red)
        base = {
            "yellow": [up, down],
            "red": [red, red2],
            "gold": [_gold(up), _gold(down)],
        }
        # body centre (relative to sprite) measured on the art: about
        # 40 % across and 62 % down, i.e. ignoring the wings above
        self.frames = {}   # (theme, kind) -> [frame][angle] surfaces
        self.centres = {}
        for ti, th in enumerate(THEMES):
            mul, add = th["sprite"]
            if th["stars"]:   # keep the bees readable at night
                mul = tuple(min(1.0, m * 1.25) for m in mul)
            for kind, imgs in base.items():
                frames = []
                for img in imgs:
                    sc = assets.tint(assets.scale(img, BEE_SCALE * (1.08 if kind == "red" else 1.0)), mul, add)
                    frames.append([pygame.transform.rotozoom(sc, a, 1.0) for a in ANGLES])
                self.frames[(ti, kind)] = frames
        for kind, imgs in base.items():
            w, h = imgs[0].get_size()
            k = BEE_SCALE * (1.08 if kind == "red" else 1.0)
            self.centres[kind] = (w * k * 0.42 - w * k / 2, h * k * 0.64 - h * k / 2)
        self.halo = assets.additive_glow(62, (255, 210, 90), 0.9, 1.5)
        self.sparkle = _sparkle(9)


class Bee:
    RADIUS = {"yellow": 21.0, "red": 23.0, "gold": 21.0}

    def __init__(self, kind, x, y, vx, amp=0.0, freq=0.0, phase=0.0, pattern="straight", delay=0.0):
        self.kind = kind
        self.x = x
        self.base_y = y
        self.y = y
        self.vx = vx              # screen px/s (negative)
        self.amp = amp
        self.freq = freq
        self.phase = phase
        self.pattern = pattern
        self.t = -delay
        self.home = 0.0           # vertical homing offset (red bees)
        self.state = "fly"        # fly | flee | eaten
        self.flee_t = 0.0
        self.touch = 0.0          # grace timer when touching the head
        self.flap = (x * 0.37 + y * 0.11) % 2.0
        self.vy = 0.0
        self.counted = False
        self.y = self._path_y(max(self.t, 0))

    @property
    def radius(self):
        return self.RADIUS[self.kind]

    def _path_y(self, t):
        if self.pattern == "sine":
            return self.base_y + self.amp * math.sin(math.tau * self.freq * t + self.phase)
        if self.pattern == "zigzag":
            p = (self.freq * t + self.phase / math.tau) % 1.0
            tri = 4 * abs(p - 0.5) - 1
            return self.base_y + self.amp * tri
        if self.pattern == "dip":
            return self.base_y + self.amp * math.sin(math.tau * self.freq * t * 0.5 + self.phase) ** 2
        return self.base_y + self.amp * 0.15 * math.sin(math.tau * 1.3 * t + self.phase)

    def predict_y(self, ahead):
        return self._path_y(max(self.t, 0) + ahead) + self.home

    def update(self, dt, target_y=None, homing=0.0):
        self.flap += dt * 14.0
        if self.t < 0:
            self.t += dt
            return
        if self.state == "flee":
            self.flee_t += dt
            self.x += 120 * dt
            self.y -= 260 * dt
            return
        old_y = self.y
        self.t += dt
        self.x += self.vx * dt
        if homing and target_y is not None and self.x > 760:
            d = target_y - (self._path_y(self.t) + self.home)
            self.home += max(-homing, min(homing, d)) * dt
        self.y = self._path_y(self.t) + self.home
        self.vy = (self.y - old_y) / dt if dt > 0 else 0.0

    @property
    def active(self):
        return self.t >= 0

    def draw(self, surf, art, theme, time):
        if not self.active:
            return
        frames = art.frames[(theme, self.kind)]
        fi = int(self.flap) % 2
        if self.state == "flee":
            ai = int(self.flee_t * 20) % len(ANGLES)
        else:
            ang = max(-16, min(16, self.vy * 0.06))
            ai = min(range(len(ANGLES)), key=lambda i: abs(ANGLES[i] - ang))
        img = frames[fi][ai]
        if self.kind == "gold":
            halo = art.halo
            s = 1.0 + 0.12 * math.sin(time * 6)
            hs = pygame.transform.smoothscale(halo, (int(halo.get_width() * s), int(halo.get_height() * s)))
            surf.blit(hs, hs.get_rect(center=(round(self.x), round(self.y))), special_flags=pygame.BLEND_RGB_ADD)
        cx, cy = art.centres[self.kind]
        if self.kind == "gold" and self.state != "flee":
            for i in range(3):           # little glints circling the bee
                a = time * 2.2 + i * math.tau / 3
                tw = 0.5 + 0.5 * math.sin(time * 9 + i * 2.1)
                sp = art.sparkle if tw > 0.35 else None
                if sp:
                    surf.blit(sp, sp.get_rect(center=(round(self.x + math.cos(a) * 38),
                                                      round(self.y + math.sin(a) * 30 - 4))),
                              special_flags=pygame.BLEND_RGB_ADD)
        if self.state == "flee":
            img = img.copy()
            img.set_alpha(max(0, int(255 * (1 - self.flee_t / 0.9))))
        surf.blit(img, img.get_rect(center=(round(self.x - cx), round(self.y - cy))))


class Spawner:
    """Feeds bees in according to the level."""

    def __init__(self, rng, top, bottom, red_bottom):
        self.rng = rng
        self.top = top              # highest bee path (screen y)
        self.bottom = bottom        # lowest yellow bee path
        self.red_bottom = red_bottom  # red bees stay above this so they can be avoided
        self.reset(1)

    def reset(self, level):
        self.level = level
        self.timer = 1.2
        self.last_y = None
        self.gold_cooldown = 6.0

    def params(self):
        lv = self.level
        cycle = (lv - 1) // 4         # each lap round the themes ramps harder
        speed = 230 + 16 * (lv - 1) + 30 * cycle
        interval = max(0.42, 1.25 * (0.9 ** (lv - 1)) - 0.06 * cycle)
        red = min(0.42, 0.1 + 0.045 * (lv - 1) + 0.04 * cycle)
        swarm = 0.0 if lv < 3 else min(0.4, 0.14 + 0.035 * (lv - 3))
        gold = 0.0 if lv < 3 else 0.05
        homing = 0.0 if lv < 4 else min(55.0, 18 + 6 * (lv - 4))
        return speed, interval, red, swarm, gold, homing

    def _y(self, lo, hi):
        y = self.rng.uniform(lo, hi)
        if self.last_y is not None and abs(y - self.last_y) < 50:
            y = self.rng.uniform(lo, hi)
        self.last_y = y
        return y

    def update(self, dt, bees_on_screen):
        """Return a list of new bees to add."""
        self.timer -= dt
        self.gold_cooldown -= dt
        if self.timer > 0:
            return []
        speed, interval, red_p, swarm_p, gold_p, _ = self.params()
        self.timer = interval * self.rng.uniform(0.75, 1.3)
        rng = self.rng
        x = WIDTH + 70
        if rng.random() < swarm_p:
            self.timer += interval * 1.6
            return self._swarm(x, speed, red_p)
        kind = "yellow"
        r = rng.random()
        if gold_p and self.gold_cooldown <= 0 and r < gold_p:
            kind = "gold"
            self.gold_cooldown = 14.0
        elif r < gold_p + red_p:
            kind = "red"
        pattern = rng.choice(("straight", "straight", "sine", "sine", "zigzag", "dip"))
        amp = rng.uniform(18, 60) if pattern != "straight" else rng.uniform(5, 25)
        freq = rng.uniform(0.35, 0.9)
        lo = self.top + amp
        hi = (self.red_bottom if kind == "red" else self.bottom) - amp
        if pattern == "dip":
            hi -= amp
        y = self._y(lo, max(lo + 1, hi))
        vx = -speed * rng.uniform(0.85, 1.2) * (1.08 if kind == "red" else 1.0)
        return [Bee(kind, x, y, vx, amp, freq, rng.uniform(0, math.tau), pattern)]

    def _swarm(self, x, speed, red_p):
        rng = self.rng
        shape = rng.choice(("line", "v", "wave") if self.level >= 4 else ("line", "wave"))
        vx = -speed * 0.95
        bees = []
        allow_red = self.level >= 5
        if shape == "line":
            n = rng.randint(4, 6)
            y = rng.uniform(self.top + 40, self.bottom - 20)
            for i in range(n):
                kind = "red" if allow_red and i == n - 1 and rng.random() < red_p and y < self.red_bottom else "yellow"
                bees.append(Bee(kind, x + i * 85, y, vx, 6, 1.0, i * 0.7, "straight"))
        elif shape == "v":
            # a "<" formation: the tip leads, the arms trail above and below
            y = rng.uniform(self.top + 130, self.bottom - 130)
            for i in range(5):
                off = i - 2
                yy = max(self.top, min(self.bottom, y + off * 65))
                kind = "yellow"
                if allow_red and abs(off) == 2 and rng.random() < red_p and yy < self.red_bottom:
                    kind = "red"
                bees.append(Bee(kind, x + abs(off) * 80, yy, vx, 6, 1.0, i, "straight"))
        else:  # sine wave: a snake of bees following one path
            n = rng.randint(5, 7)
            amp = rng.uniform(60, 110)
            y = rng.uniform(self.top + amp, self.bottom - amp)
            freq = rng.uniform(0.35, 0.55)
            spacing = 0.28
            for i in range(n):
                kind = "red" if allow_red and i == n // 2 and rng.random() < red_p and y + amp < self.red_bottom else "yellow"
                # every bee enters at the same x, later bees delayed: a true snake
                bees.append(Bee(kind, x, y, vx, amp, freq, 0.0, "sine", delay=i * spacing))
        return bees

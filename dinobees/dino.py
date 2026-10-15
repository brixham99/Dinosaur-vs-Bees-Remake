"""The long-necked dinosaur: sprite body with swinging legs, a procedural
neck and a sprite head."""
import math

import numpy as np
import pygame

from . import assets
from .assets import THEMES
from .settings import (CHOMP_COOLDOWN, CHOMP_TIME, DINO_BELLY, DINO_BELLY_SHADE,
                       DINO_GREEN, DINO_GREEN_LIGHT, DINO_OUTLINE, DINO_PLATE,
                       DINO_SPOT_RIM,
                       INVULNERABLE_TIME, WIDTH)

TURN_TIME = 0.42                  # seconds for a full about-turn
TURN_MIN_SCALE = 0.2              # thinnest he gets, edge-on mid-turn
BUF_LEFT, BUF_RIGHT = 230, 560    # model-space reach behind / in front of the body centre
BODY_SCALE = 0.36
HEAD_SCALE = 0.30
WALK_FRAMES = 24

# Geometry measured on the cropped full-resolution art (see tools/prep_assets.py)
STUMP = (906.0, 133.0)            # centre of the neck stump on dino_body.png
STUMP_REGION = (890, 92, 938, 182)  # stump cross-section that gets painted over
LEG_HINGE_Y = 318                 # legs are separate below this row
LEGS = [  # (x0, x1, phase offset, is_far)
    (473, 640, 0.5, True),
    (800, 938, 0.0, True),
    (296, 473, 0.0, False),
    (640, 800, 0.5, False),
]
LEG_SWING = 22.0                  # source px at the foot
LEG_LIFT = 14.0
ROOT_T = 0.1                      # parameter span of the hidden root segment
ROOT_LEN = 15.0                   # px the root reaches back into the shoulder
HEAD_ANCHOR = (70.0, 228.0)       # where the neck enters the closed head
CHOMP_EYE_SHIFT = (-19.0, -15.0)  # chomp head eye offset vs closed head
MOUTH = (330.0, 228.0)            # mouth centre (closed head coords)
HEAD_CENTRE = (200.0, 165.0)
# body hit circles (source coords, radius)
BODY_CIRCLES = [(470, 190, 105), (650, 175, 100), (815, 150, 62), (300, 215, 66),
                (160, 240, 34), (370, 390, 50), (530, 390, 46), (712, 390, 50), (870, 390, 46)]


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rot(vx, vy, deg):
    """Rotate a screen-space vector the way pygame.transform.rotate does
    (positive = counter-clockwise on screen)."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return vx * c + vy * s, -vx * s + vy * c


def bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    mt = 1 - t
    pts = (mt ** 3) * p0 + 3 * (mt ** 2) * t * p1 + 3 * mt * (t ** 2) * p2 + (t ** 3) * p3
    der = 3 * (mt ** 2) * (p1 - p0) + 6 * mt * t * (p2 - p1) + 3 * (t ** 2) * (p3 - p2)
    return t[:, 0], pts, der


# --------------------------------------------------------------- body frames
def _paint_over_stump(rgb, alpha):
    """Replace the open stump cross-section with plain body colours so the
    procedural neck can grow out of the shoulder without a visible ring."""
    x0, y0, x1, y1 = STUMP_REGION
    # belly stripe boundary just left of the stump, extrapolated
    xs = np.array([870, 880, 890])
    tops = []
    for x in xs:
        col = rgb[x, 60:260]
        ys = np.where((col[:, 0] > 150) & (alpha[x, 60:260] > 200))[0]
        tops.append(60 + ys[0] if len(ys) else 170)
    k, c = np.polyfit(xs, tops, 1)
    for x in range(x0, x1):
        belly_y = k * x + c
        for y in range(y0, y1):
            if alpha[x, y] < 10:
                continue
            rgb[x, y] = DINO_BELLY if y > belly_y else DINO_GREEN
            alpha[x, y] = 255


def _leg_offsets(phase):
    """Foot displacement (dx, lift) for a gait phase in [0, 1)."""
    stance = 0.6
    if phase < stance:
        return LEG_SWING - 2 * LEG_SWING * (phase / stance), 0.0
    s = (phase - stance) / (1 - stance)
    return -LEG_SWING + 2 * LEG_SWING * (0.5 - 0.5 * math.cos(math.pi * s)), math.sin(math.pi * s) * LEG_LIFT


def _build_walk_frames(body):
    rgb0 = pygame.surfarray.array3d(body).astype(np.float32)
    a0 = pygame.surfarray.array_alpha(body).astype(np.float32)
    _paint_over_stump(rgb0, a0)
    w, h = a0.shape
    frames = []
    for i in range(WALK_FRAMES):
        phase = i / WALK_FRAMES
        rgb = rgb0.copy()
        a = a0.copy()
        for x0, x1, _, _ in LEGS:
            a[x0:x1, LEG_HINGE_Y:] = 0
        rows = np.arange(LEG_HINGE_Y, h)
        frac = (rows - LEG_HINGE_Y) / float(h - LEG_HINGE_Y)
        for x0, x1, off, far in LEGS:
            dx, lift = _leg_offsets((phase + off) % 1.0)
            pad = int(LEG_SWING) + 2
            dst_x = np.arange(max(0, x0 - pad), min(w, x1 + pad))
            # inverse map: destination (x, y) samples source (x - dx*f, y + lift*f)
            sx = np.rint(dst_x[:, None] - dx * frac[None, :]).astype(int)
            sy = np.rint(rows[None, :] + lift * frac[None, :]).astype(int)
            valid = (sx >= x0) & (sx < x1) & (sy < h)
            sx = np.clip(sx, 0, w - 1)
            sy = np.clip(sy, 0, h - 1)
            src_a = np.where(valid, a0[sx, sy], 0) / 255.0
            src_rgb = rgb0[sx, sy]
            dst_a = a[dst_x[:, None], rows[None, :]] / 255.0
            out_a = src_a + dst_a * (1 - src_a)
            blend = (src_rgb * src_a[..., None] + rgb[dst_x[:, None], rows[None, :]] * (dst_a * (1 - src_a))[..., None])
            blend = np.where(out_a[..., None] > 0, blend / np.maximum(out_a[..., None], 1e-6), 0)
            rgb[dst_x[:, None], rows[None, :]] = blend
            a[dst_x[:, None], rows[None, :]] = out_a * 255
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.blit_array(surf, np.clip(rgb, 0, 255).astype(np.uint8))
        pa = pygame.surfarray.pixels_alpha(surf)
        pa[...] = np.clip(a, 0, 255).astype(np.uint8)
        del pa
        frames.append(assets.scale(surf, BODY_SCALE))
    return frames


class DinoArt:
    """All dinosaur sprites, pre-graded for every theme."""

    def __init__(self):
        body = assets.load("dino_body.png")
        self.src_size = body.get_size()
        base_frames = _build_walk_frames(body)
        head = assets.scale(assets.load("dino_head.png"), HEAD_SCALE)
        chomp = assets.scale(assets.load("dino_head_chomp.png"), HEAD_SCALE)
        self.frames, self.heads, self.chomps, self.neck_cols = [], [], [], []
        for th in THEMES:
            mul, add = th["sprite"]
            self.frames.append([assets.tint(f, mul, add) for f in base_frames])
            self.heads.append(assets.tint(head, mul, add))
            self.chomps.append(assets.tint(chomp, mul, add))
            self.neck_cols.append({k: assets.tint_colour(c, mul, add) for k, c in {
                "green": DINO_GREEN, "light": DINO_GREEN_LIGHT, "belly": DINO_BELLY,
                "belly_shade": DINO_BELLY_SHADE, "outline": DINO_OUTLINE, "plate": DINO_PLATE,
                "spot_rim": DINO_SPOT_RIM,
            }.items()})
        self.frame_size = base_frames[0].get_size()


class Dino:
    def __init__(self, art, x, feet_y):
        self.art = art
        self.x = x
        self.feet_y = feet_y
        fw, fh = art.frame_size
        sw, sh = art.src_size
        k = fw / sw
        # stump offset from frame centre
        self.stump_off = ((STUMP[0] - sw / 2) * k, (STUMP[1] - sh / 2) * k)
        self.body_circles = [((cx - sw / 2) * k, (cy - sh / 2) * k, r * k * 0.85) for cx, cy, r in BODY_CIRCLES]
        self.k = k
        self.ss = 2
        self.ss_buf = pygame.Surface((900 * self.ss, 760 * self.ss), pygame.SRCALPHA)
        self.mask_buf = pygame.Surface((900 * self.ss, 760 * self.ss), pygame.SRCALPHA)
        self.reset()
        self._setup_reach()

    def reset(self):
        self.h = 0.45
        self.h_target = 0.45
        self.h_vel = 0.0
        self.walk_phase = 0.0
        self.chomp_t = 0.0
        self.chomp_cd = 0.0
        self.wobble = 0.0
        self.wobble_v = 0.0
        self.invuln = 0.0
        self.fainted = 0.0     # >0 once out of hearts (droop animation)
        self.facing = 1        # 1 = right, -1 = left (where he is heading)
        self.turn = 0.0        # 0 = facing right ... 1 = facing left
        self.pivot = float(self.x)
        self.time = 0.0
        self._geom = None

    def _setup_reach(self):
        p0x, p0y = self.x + self.stump_off[0], self.feet_y - self.art.frame_size[1] / 2 + self.stump_off[1]
        low = (p0x + 210, self.feet_y - 52)
        high = (p0x + 115, 128)
        self.reach_low = (math.atan2(-(low[1] - p0y), low[0] - p0x), math.hypot(low[0] - p0x, low[1] - p0y))
        self.reach_high = (math.atan2(-(high[1] - p0y), high[0] - p0x), math.hypot(high[0] - p0x, high[1] - p0y))

    # ------------------------------------------------------------ control
    @property
    def chomping(self):
        return self.chomp_t > 0

    def try_chomp(self):
        if self.chomp_t <= 0 and self.chomp_cd <= 0 and self.fainted <= 0:
            self.chomp_t = CHOMP_TIME
            return True
        return False

    def face(self, direction):
        """Ask him to face left (-1) or right (1); he turns round smoothly."""
        if self.fainted <= 0 and direction in (-1, 1):
            self.facing = direction

    @property
    def xscale(self):
        """Horizontal scale of the turn: 1 facing right, -1 facing left,
        passing through edge-on (about 0) half-way round."""
        return math.cos(math.pi * smoothstep(self.turn))

    @property
    def turning(self):
        return 0.0 < self.turn < 1.0

    def faces(self):
        """1 or -1 once he is mostly round, 0 while edge-on mid-turn."""
        s = self.xscale
        return 1 if s > 0.35 else (-1 if s < -0.35 else 0)

    def from_behind(self, vx):
        """True if something moving at vx is catching him up from behind
        (travelling the same way he is facing)."""
        f = self.faces()
        return f != 0 and vx * f > 0

    def home_x(self, facing=None):
        f = self.facing if facing is None else facing
        return float(self.x) if f > 0 else float(WIDTH - self.x)

    def to_screen(self, p):
        return (self.pivot + (p[0] - self.x) * self.xscale, p[1])

    def sting(self, from_above):
        self.invuln = INVULNERABLE_TIME
        self.wobble_v += -160.0 if from_above else 160.0

    def update(self, dt, up, down, walk_speed):
        self.time += dt
        stride = 150.0
        self.walk_phase = (self.walk_phase + abs(walk_speed) * dt / stride) % 1.0
        goal = 0.0 if self.facing > 0 else 1.0
        if self.turn != goal:
            step = dt / TURN_TIME
            self.turn = min(goal, self.turn + step) if goal > self.turn else max(goal, self.turn - step)
        # he strolls across to the other side of the screen as he turns, so
        # his head always has room in front of him
        self.pivot += (self.home_x() - self.pivot) * min(1.0, dt * 3.2)
        if abs(self.pivot - self.home_x()) < 0.3:
            self.pivot = self.home_x()
        if self.fainted > 0:
            self.fainted += dt
            self.h_target = max(0.0, self.h_target - dt * 0.8)
        else:
            rate = 1.05
            if up and not down:
                self.h_target = min(1.0, self.h_target + rate * dt)
            elif down and not up:
                self.h_target = max(0.0, self.h_target - rate * dt)
        # critically damped spring towards the target: smooth with easing
        k = 90.0
        c = 2 * math.sqrt(k)
        acc = k * (self.h_target - self.h) - c * self.h_vel
        self.h_vel += acc * dt
        self.h += self.h_vel * dt
        self.h = max(-0.05, min(1.05, self.h))
        # knock-back wobble (damped spring, degrees)
        acc = -140.0 * self.wobble - 7.0 * self.wobble_v
        self.wobble_v += acc * dt
        self.wobble += self.wobble_v * dt
        if self.chomp_t > 0:
            self.chomp_t -= dt
            if self.chomp_t <= 0:
                self.chomp_cd = CHOMP_COOLDOWN
        elif self.chomp_cd > 0:
            self.chomp_cd -= dt
        if self.invuln > 0:
            self.invuln -= dt
        self._geom = None

    # ----------------------------------------------------------- geometry
    def frame_index(self):
        return int(self.walk_phase * WALK_FRAMES) % WALK_FRAMES

    def body_pose(self):
        """(centre x, centre y, tilt degrees)"""
        ph = self.walk_phase * math.tau
        bob = 1.6 * math.cos(2 * ph)
        tilt = 0.9 * math.sin(ph)
        if self.fainted > 0:
            tilt -= min(1.0, self.fainted) * 2.0
        fh = self.art.frame_size[1]
        return self.x, self.feet_y - fh / 2 + bob, tilt

    def geometry(self, h=None):
        """Neck curve and head transform for the current state."""
        if h is None and self._geom is not None:
            return self._geom
        hh = self.h if h is None else h
        cx, cy, tilt = self.body_pose()
        ox, oy = rot(*self.stump_off, tilt)
        p0 = np.array([cx + ox, cy + oy])
        e = smoothstep(hh) * 0.6 + hh * 0.4
        wob = self.wobble
        ang = lerp(self.reach_low[0], self.reach_high[0], e) + math.radians(wob)
        reach = lerp(self.reach_low[1], self.reach_high[1], e)
        # a little life: the head sways as he walks
        sway = math.sin(self.walk_phase * math.tau * 2) * 2.0
        p3 = p0 + np.array([math.cos(ang) * reach, -math.sin(ang) * reach + sway])
        a0 = math.radians(lerp(14, 64, e) + tilt)
        a1 = math.radians(lerp(-14, 24, e) + wob * 0.6)
        c1 = p0 + np.array([math.cos(a0), -math.sin(a0)]) * reach * 0.42
        c2 = p3 - np.array([math.cos(a1), -math.sin(a1)]) * reach * 0.36
        head_angle = lerp(-14, 9, e) + wob * 0.7
        if self.fainted > 0:
            head_angle -= min(1.0, self.fainted) * 18
        ts, pts, der = bezier(p0, c1, c2, p3, 34)
        # the neck root continues a little way back into the shoulder, where it
        # is faded out so it melts into the body art
        d0 = np.array([math.cos(a0), -math.sin(a0)])
        back = np.linspace(-ROOT_T, -ROOT_T / 4, 4)
        root_pts = p0[None, :] + d0[None, :] * (back[:, None] / ROOT_T) * ROOT_LEN
        ts = np.concatenate([back, ts])
        pts = np.vstack([root_pts, pts])
        der = np.vstack([np.repeat(d0[None, :] * 100.0, 4, axis=0), der])
        g = {"p0": p0, "p3": p3, "ts": ts, "pts": pts, "der": der, "head_angle": head_angle}
        g.update(self._head_points(p3, head_angle))
        if h is None:
            self._geom = g
        return g

    def _head_point(self, p3, angle, pt):
        vx = (pt[0] - HEAD_ANCHOR[0]) * HEAD_SCALE
        vy = (pt[1] - HEAD_ANCHOR[1]) * HEAD_SCALE
        rx, ry = rot(vx, vy, angle)
        return p3[0] + rx, p3[1] + ry

    def _head_points(self, p3, angle):
        return {
            "mouth": self._head_point(p3, angle, MOUTH),
            "head_centre": self._head_point(p3, angle, HEAD_CENTRE),
        }

    @staticmethod
    def neck_width(t):
        t = max(0.0, t)
        w = 43.0 + (33.0 - 43.0) * t
        if t < 0.1:
            w += 6.0 * (1 - t / 0.1) ** 2
        return w

    # --------------------------------------------------------- hit shapes
    MOUTH_R = 30.0
    HEAD_R = 36.0

    def mouth_circle(self):
        g = self.geometry()
        return self.to_screen(g["mouth"]), self.MOUTH_R

    def head_circle(self):
        g = self.geometry()
        return self.to_screen(g["head_centre"]), self.HEAD_R

    def neck_circles(self):
        g = self.geometry()
        out = []
        for i in range(0, len(g["ts"]) - 2, 3):
            t = g["ts"][i]
            if t < 0.15:
                continue
            out.append((self.to_screen(g["pts"][i]), self.neck_width(t) * 0.5 * 0.85))
        return out

    def body_hit_circles(self):
        cx, cy, tilt = self.body_pose()
        out = []
        for ox, oy, r in self.body_circles:
            rx, ry = rot(ox, oy, tilt)
            out.append((self.to_screen((cx + rx, cy + ry)), r))
        return out

    # ----------------------------------------------------------------- draw
    def draw(self, surf, theme):
        if self.turn == 0.0 and self.pivot == self.x:
            self._draw_model(surf, theme, 0)
            return
        # draw him facing right into a buffer, then turn it: a horizontal
        # squash through edge-on (smooth-scaled, so antialiased) with a touch
        # of shade while he is side-on to the light, mirrored past half-way
        if not hasattr(self, "turn_buf"):
            self.turn_buf = pygame.Surface((BUF_LEFT + BUF_RIGHT, surf.get_height()), pygame.SRCALPHA)
        buf = self.turn_buf
        buf.fill((0, 0, 0, 0))
        ox = self.x - BUF_LEFT
        self._draw_model(buf, theme, ox)
        s = self.xscale
        k = max(TURN_MIN_SCALE, abs(s))
        bw, bh = buf.get_size()
        if k < 0.999:
            img = pygame.transform.smoothscale(buf, (max(2, int(round(bw * k))), bh))
            shade = int(255 * (1.0 - 0.28 * (1.0 - k)))
            img.fill((shade, shade, shade), special_flags=pygame.BLEND_RGB_MULT)
        else:
            img = buf
        if s < 0:
            img = pygame.transform.flip(img, True, False)
        sign = 1 if s >= 0 else -1
        left = self.pivot + min(-BUF_LEFT * k * sign, BUF_RIGHT * k * sign)
        surf.blit(img, (round(left), 0))

    def _draw_model(self, surf, theme, ox):
        g = self.geometry()
        cols = self.art.neck_cols[theme]
        blink = self.invuln > 0 and int(self.invuln * 12) % 2 == 0
        alpha = 110 if blink else None

        cx, cy, tilt = self.body_pose()
        frame = self.art.frames[theme][self.frame_index()]
        img = pygame.transform.rotate(frame, tilt) if abs(tilt) > 0.05 else frame
        if alpha:
            img = img.copy() if img is frame else img
            img.set_alpha(alpha)
        surf.blit(img, img.get_rect(center=(round(cx - ox), round(cy))))

        neck = self._render_neck(g, cols)
        if neck is not None:
            ns, pos = neck
            if alpha:
                ns.set_alpha(alpha)
            surf.blit(ns, (pos[0] - ox, pos[1]))

        head = (self.art.chomps if self.chomping else self.art.heads)[theme]
        anchor = HEAD_ANCHOR if not self.chomping else (HEAD_ANCHOR[0] + CHOMP_EYE_SHIFT[0],
                                                        HEAD_ANCHOR[1] + CHOMP_EYE_SHIFT[1])
        himg = pygame.transform.rotozoom(head, g["head_angle"], 1.0)
        hw, hh = head.get_size()
        vx = anchor[0] * HEAD_SCALE - hw / 2
        vy = anchor[1] * HEAD_SCALE - hh / 2
        rx, ry = rot(vx, vy, g["head_angle"])
        rw, rh = himg.get_size()
        if alpha:
            himg.set_alpha(alpha)
        surf.blit(himg, (round(g["p3"][0] - rx - rw / 2 - ox), round(g["p3"][1] - ry - rh / 2)))

    def _render_neck(self, g, cols):
        ss = self.ss
        pts = g["pts"]
        der = g["der"]
        ts = g["ts"]
        n = len(ts)
        tang = der / np.maximum(np.linalg.norm(der, axis=1, keepdims=True), 1e-6)
        nup = np.stack([tang[:, 1], -tang[:, 0]], axis=1)   # dorsal side
        widths = np.array([self.neck_width(t) for t in ts])
        pad = 34
        x0 = int(pts[:, 0].min() - pad)
        y0 = int(pts[:, 1].min() - pad)
        x1 = int(pts[:, 0].max() + pad)
        y1 = int(pts[:, 1].max() + pad)
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0 or w * ss > self.ss_buf.get_width() or h * ss > self.ss_buf.get_height():
            return None
        buf = self.ss_buf.subsurface((0, 0, w * ss, h * ss))
        buf.fill((0, 0, 0, 0))
        origin = np.array([x0, y0])
        P = (pts - origin) * ss
        half = widths[:, None] * 0.5 * ss
        outline = 2.6 * ss

        def edge(offset):
            return P + nup * offset

        def poly(a_off, b_off, colour, start=0, end=None):
            end = n if end is None else end
            a = edge(a_off)[start:end]
            b = edge(b_off)[start:end][::-1]
            pygame.draw.polygon(buf, colour, np.vstack([a, b]).tolist())

        # dorsal plates, like the ones along the body's back
        for t in (0.16, 0.3, 0.44, 0.58, 0.72):
            i = int(t * (n - 1))
            r = (9.5 - 5.0 * t) * ss
            c = P[i] + nup[i] * (half[i, 0] - r * 0.15)
            pygame.draw.circle(buf, cols["outline"], c.tolist(), r + outline)
            pygame.draw.circle(buf, cols["plate"], c.tolist(), r)
            hl = c + nup[i] * r * 0.35 - tang[i] * r * 0.2
            pygame.draw.circle(buf, assets.tint_colour(cols["plate"], (1.25, 1.18, 1.2)), hl.tolist(), r * 0.4)

        ramp = np.clip((ts + ROOT_T) / 0.06, 0, 1)[:, None] * outline
        poly(half + ramp, -half - ramp, cols["outline"])
        poly(half, -half, cols["green"])
        # soft darker shade along the back, lighter rim just under the outline
        poly(half * 0.92, half * 0.55, assets.tint_colour(cols["green"], (1.08, 1.05, 1.1)))
        # belly stripe on the throat side, matching the body's underside
        poly(-half * 0.3, -half, cols["belly"])
        poly(-half * 0.8, -half, cols["belly_shade"])
        # light spots like the ones on his back
        for t, rr in ((0.24, 6.5), (0.4, 5.0), (0.55, 4.0), (0.33, 3.0)):
            i = int(t * (n - 1))
            c = P[i] + nup[i] * half[i, 0] * (0.42 if rr != 3.0 else 0.05) + tang[i] * (rr * 1.6 * ss if rr == 3.0 else 0)
            pygame.draw.circle(buf, cols["spot_rim"], c.tolist(), rr * ss + ss * 0.8)
            pygame.draw.circle(buf, cols["light"], c.tolist(), rr * ss)
        # a couple of throat creases near the head
        for t in (0.82, 0.88):
            i = int(t * (n - 1))
            a = P[i] - nup[i] * half[i, 0] * 0.95
            b = P[i] - nup[i] * half[i, 0] * 0.45 + tang[i] * 3 * ss
            pygame.draw.line(buf, cols["belly_shade"], a.tolist(), b.tolist(), max(1, int(1.5 * ss)))
        # fade the hidden root in from nothing (multiplying the alpha); only
        # the small region around the root is touched
        reach = half.max() + 12 * ss
        quads = []
        for i in range(n - 1):
            if ts[i] >= -0.02:
                break
            a = int(255 * max(0.0, min(1.0, (ts[i] + ROOT_T) / (ROOT_T - 0.02))))
            j = i + 1
            ext = -tang[i] * 30 * ss if i == 0 else 0
            quads.append((a, [P[i] + nup[i] * reach + ext, P[j] + nup[j] * reach,
                              P[j] - nup[j] * reach, P[i] - nup[i] * reach + ext]))
        if quads:
            allp = np.array([q for _, qs in quads for q in qs])
            rx0 = max(0, int(allp[:, 0].min()) - 2)
            ry0 = max(0, int(allp[:, 1].min()) - 2)
            rx1 = min(w * ss, int(allp[:, 0].max()) + 3)
            ry1 = min(h * ss, int(allp[:, 1].max()) + 3)
            if rx1 > rx0 and ry1 > ry0:
                mask = self.mask_buf.subsurface((0, 0, rx1 - rx0, ry1 - ry0))
                mask.fill((255, 255, 255, 255))
                off = np.array([rx0, ry0])
                for a, quad in quads:
                    pygame.draw.polygon(mask, (255, 255, 255, a), [(q - off).tolist() for q in quad])
                buf.blit(mask, (rx0, ry0), special_flags=pygame.BLEND_RGBA_MULT)
        out = pygame.transform.smoothscale(buf, (w, h))
        return out, (x0, y0)

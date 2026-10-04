"""A demo autopilot: steers the neck towards yellow bees, keeps the head
under angry red ones and chomps at the right moment. Used by --autoplay."""
import numpy as np


class AutoPilot:
    def __init__(self, dino, rng):
        self.dino = dino
        self.rng = rng
        self.hs = np.linspace(0.0, 1.0, 41)
        self.desired_h = 0.45
        self.think = 0.0
        self._table()

    def _table(self):
        ys = [self.dino.geometry(h)["mouth"][1] for h in self.hs]
        self.mouth_ys = np.array(ys)          # decreasing as h rises

    def h_for_mouth_y(self, y):
        ys = self.mouth_ys[::-1]
        hs = self.hs[::-1]
        return float(np.interp(y, ys, hs))

    def decide(self, bees, dt):
        d = self.dino
        g = d.geometry()
        mx, my = g["mouth"]
        neck_x = d.x + d.stump_off[0]
        self.think -= dt
        if self.think <= 0:
            self.think = 0.05
            reds, yellows = [], []
            for b in bees:
                if not b.active or b.state != "fly" or b.x < neck_x - 40:
                    continue
                spd = max(1.0, -b.vx)
                t_head = max(0.0, (b.x - mx) / spd)
                if b.kind == "red":
                    t_neck = max(t_head, (b.x - neck_x) / spd)
                    ys = [b.predict_y(t) for t in np.linspace(t_head, t_neck, 5)]
                    reds.append((t_head, max(ys)))
                else:
                    if b.x < mx - 25:
                        continue
                    yellows.append((t_head, b.predict_y(t_head)))
            target = None
            lo_y, hi_y = self.mouth_ys[-1], self.mouth_ys[0]
            for t, y in sorted(yellows):
                if t > 2.6:
                    break
                if y < lo_y - 30 or y > hi_y + 30:
                    continue
                if any(abs(tr - t) < 0.8 and y < yr + 105 for tr, yr in reds):
                    continue
                target = y
                break
            imminent = [yr for tr, yr in reds if tr < 1.5]
            if target is None:
                target = max(imminent) + 125 if imminent else 330.0
            if imminent:
                target = max(target, max(imminent) + 110)
            self.desired_h = self.h_for_mouth_y(target)
        up = d.h_target < self.desired_h - 0.02
        down = d.h_target > self.desired_h + 0.02
        chomp = False
        for b in bees:
            if b.active and b.state == "fly" and b.kind != "red":
                dist = ((b.x - mx) ** 2 + (b.y - my) ** 2) ** 0.5
                if dist < d.MOUTH_R + b.radius + 14 and b.x > mx - 20:
                    chomp = True
                    break
        return up, down, chomp

"""Render the sky with a cloud crossing the sun (parallax order check)."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from dinobees.world import World
from dinobees.settings import SKY_DRIFT

out = sys.argv[1] if len(sys.argv) > 1 else "sky_check.png"
w = World(random.Random(1))
clouds = w.layers[0]["clouds"]
sun_img, (sx, sy) = w.layers[0]["sun"]
# find a sky offset where the most cloud covers the sun's disc
best, best_off = -1, 0
tw = clouds[0][0].get_width()
import numpy as np
a = np.zeros((tw, 720))
for layer, dy in clouds:
    al = pygame.surfarray.array_alpha(layer)
    a[:, dy:dy + al.shape[1]] = al
for off in range(0, tw, 4):
    xs = (np.arange(sx - 45, sx + 45) + off) % tw
    v = a[xs, sy - 45:sy + 45].mean()
    if v > best:
        best, best_off = v, off
w.time = best_off / SKY_DRIFT
s = pygame.Surface((1280, 720))
w.draw_background(s)
pygame.image.save(s.subsurface((0, 0, 640, 330)), out)
print("cloud cover over sun", round(best / 255, 2), "time", w.time, "saved", out)

#!/usr/bin/env python3
"""Stage specific moments of the game and save screenshots (headless).

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/capture_shots.py [OUT_DIR]
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

import game  # noqa: E402
from dinobees.bees import Bee  # noqa: E402
from dinobees.settings import DT  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)


def make(seed=5, level=1, autoplay=False):
    argv = ["--seed", str(seed), "--mute", "--highscore-file", "/tmp/dvb_shots_hs.json", "--level", str(level)]
    if autoplay:
        argv.append("--autoplay")
    args = game.parse_args(argv)
    return game.Game(args)


def step(g, n=1):
    for _ in range(n):
        g.update(DT)
    g.draw()


def shot(g, name):
    path = os.path.join(OUT, name)
    pygame.image.save(g.screen, path)
    print("saved", path)


def hold_neck(g, h):
    g.dino.h = g.dino.h_target = h
    g.dino.h_vel = 0.0


def add_bee(g, kind, x, y, vx=-240, pattern="straight", amp=4):
    b = Bee(kind, x, y, vx, amp, 0.6, 0.0, pattern)
    g.bees.append(b)
    return b


def no_spawns(g):
    g.spawner.timer = 999


# 1. title
g = make(seed=2)
step(g, 150)
shot(g, "01_title.png")

# 2. neck high, mid-chomp, bee about to be eaten
g.start_game()
g.score, g.combo, g.eaten_this_level = 340, 7, 8
no_spawns(g)
step(g, 160)
hold_neck(g, 1.0)
step(g, 30)
(mx, my), _ = g.dino.mouth_circle()
add_bee(g, "yellow", mx + 80, my, vx=-200)
add_bee(g, "yellow", mx + 420, my + 60, vx=-200)
add_bee(g, "red", mx + 650, my + 220, vx=-220)
add_bee(g, "yellow", mx + 300, my + 300, vx=-200, pattern="sine", amp=30)
g.dino.try_chomp()
step(g, 6)
shot(g, "02_chomp_high.png")
step(g, 6)
shot(g, "02b_after_eat.png")

# 3. neck low, grazing a low bee
g = make(seed=3)
g.start_game()
no_spawns(g)
g.score, g.combo = 120, 3
step(g, 120)
hold_neck(g, 0.0)
step(g, 40)
(mx, my), _ = g.dino.mouth_circle()
add_bee(g, "yellow", mx + 140, my - 5, vx=-200)
add_bee(g, "red", mx + 380, 230, vx=-230, pattern="sine", amp=30)
add_bee(g, "yellow", mx + 700, my - 160, vx=-200)
step(g, 8)
shot(g, "03_neck_low.png")

# 4. sting flash: a red bee flies into the neck
g = make(seed=4)
g.start_game()
no_spawns(g)
g.score = 260
step(g, 120)
hold_neck(g, 0.7)
step(g, 20)
geo = g.dino.geometry()
px, py = geo["pts"][len(geo["pts"]) // 2]
add_bee(g, "red", px + 60, py, vx=-260)
for _ in range(40):
    step(g)
    if g.flash > 0.8:
        break
step(g, 2)
shot(g, "04_sting.png")

# 5. night (level 3) and 6. volcano glow (level 4)
for lvl, name in ((3, "05_night.png"), (4, "06_volcano.png"), (2, "07_sunset.png")):
    g = make(seed=10 + lvl, level=lvl, autoplay=True)
    g.start_game()
    g.world.set_theme(g.world.theme, instant=True)
    g.score = 900 * lvl
    step(g, 420)
    shot(g, name)

# 8. pause
g.state = "paused"
step(g)
shot(g, "08_paused.png")

# 9. game over
g = make(seed=9)
g.high_score = 1000
g.start_game()
g.score = 1530
g.hearts = 1
no_spawns(g)
step(g, 90)
hold_neck(g, 0.5)
geo = g.dino.geometry()
hx, hy = geo["head_centre"]
add_bee(g, "red", hx + 60, hy, vx=-260)
step(g, 60)
shot(g, "09a_fainting.png")
step(g, 260)
shot(g, "09_game_over.png")

# 10. golden bee about to be eaten for a heart (level 3)
g = make(seed=21, level=3)
g.start_game()
g.world.set_theme(g.world.theme, instant=True)
g.hearts = 2
no_spawns(g)
step(g, 100)
hold_neck(g, 0.55)
step(g, 20)
(mx, my), _ = g.dino.mouth_circle()
add_bee(g, "gold", mx + 220, my, vx=-200)
add_bee(g, "yellow", mx + 330, my - 120, vx=-200, pattern="sine", amp=30)
step(g, 10)
shot(g, "10_golden.png")

# 11. swarms at level 6 under autoplay
g = make(seed=6, level=6, autoplay=True)
g.start_game()
g.world.set_theme(g.world.theme, instant=True)
g.spawner.timer = 0
for i in range(8):
    step(g, 75)
    shot(g, f"11_level6_{i}.png")

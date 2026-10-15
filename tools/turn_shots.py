"""Headless check of the about-turn: a strip of tween frames, an in-game shot
facing left, and a red bee bouncing off his back. Usage: turn_shots.py OUTDIR"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
import game as G
from dinobees.bees import Bee
from dinobees.settings import DT, WIDTH, HEIGHT

out = sys.argv[1] if len(sys.argv) > 1 else "."
args = G.parse_args(["--seed", "5", "--mute", "--offline", "--highscore-file", "/tmp/dvb_turn_hs.json"])
g = G.Game(args)
g.start_game()
g.spawner.update = lambda dt, n: []        # no random bees: a clean stage
for _ in range(60):
    g.update(DT)

# 1) tween strip: crop round the dino at points through the turn
g.dino.face(-1)
crops = []
t_marks = [0.0, 0.1, 0.2, 0.3, 0.42]
t = 0.0
for target in t_marks:
    while t < target - 1e-6:
        g.update(DT)
        t += DT
    g.draw()
    rect = pygame.Rect(0, 150, WIDTH, HEIGHT - 150)
    crops.append(g.screen.subsurface(rect).copy())
cw, ch = 640, 285
strip = pygame.Surface((cw, ch * len(crops)))
for i, c in enumerate(crops):
    strip.blit(pygame.transform.smoothscale(c, (cw, ch)), (0, i * ch))
pygame.image.save(strip, os.path.join(out, "dvb_turn_frames.png"))

# 2) settled facing left, a red bee coming in from behind
for _ in range(90):
    g.update(DT)
bee = Bee("red", WIDTH + 40, g.dino.head_circle()[0][1] + 120, -260)
g.bees.append(bee)
hearts = g.hearts
bonked = False
for i in range(400):
    g.update(DT)
    if bee.state == "flee" and not bonked:
        bonked = True
        for _ in range(8):
            g.update(DT)
        g.draw()
        pygame.image.save(g.screen, os.path.join(out, "dvb_red_bonk.png"))
        break
print("bonked", bonked, "hearts before", hearts, "after", g.hearts)
g.draw()
pygame.image.save(g.screen, os.path.join(out, "dvb_facing_left.png"))

"""Contact sheet of the turn frames (0..180 deg) on a plain backdrop, plus an
in-game mid-turn shot. Usage: turn_sheet.py SHEET.png INGAME.png"""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
import game as G
from dinobees.dino import smoothstep
from dinobees.settings import DT

sheet_path, ingame_path = sys.argv[1], sys.argv[2]
g = G.Game(G.parse_args(["--seed", "5", "--mute", "--offline", "--highscore-file", "/tmp/dvb_ts.json"]))
g.start_game()
g.spawner.update = lambda dt, n: []
for _ in range(40):
    g.update(DT)
d = g.dino
d.h = d.h_target = 0.45   # neck at rest
d._geom = None

def turn_for(u):
    """turn value giving pose position u (0..4)."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if 4 * smoothstep(mid) < u:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

layers = []
NAMES = {0: "side right", 1: "3/4 right", 2: "front", 3: "3/4 left", 4: "side left"}
for step in (0, 0.8, 1, 1.8, 2, 2.8, 3, 3.8, 4):
    s = pygame.Surface((1280, 720), pygame.SRCALPHA)
    d.turn = turn_for(step) if step not in (0, 4) else (0.0 if step == 0 else 1.0)
    d.pivot = 640.0
    t0 = time.perf_counter()
    d.draw(s, 0)
    print(f"{step}: {(time.perf_counter() - t0) * 1000:.1f} ms")
    layers.append((step, s))
box = layers[0][1].get_bounding_rect()
for _, s in layers:
    box.union_ip(s.get_bounding_rect())
box.inflate_ip(16, 16)
pygame.font.init()
f = pygame.font.Font(None, 44)
zoom = 1.6
cw, ch = int(box.w * zoom), int(box.h * zoom)
cols = 5
rows = 2
sheet = pygame.Surface((cw * cols, ch * rows))
sheet.fill((255, 255, 255))
for i, (step, s) in enumerate(layers):
    cell = pygame.Surface(box.size)
    cell.fill((200, 224, 240))
    pygame.draw.rect(cell, (150, 200, 110), (0, d.feet_y - 6 - box.top, box.w, box.h))
    cell.blit(s, (-box.left, -box.top))
    cell = pygame.transform.smoothscale(cell, (cw - 6, ch - 6))
    label = NAMES.get(step, "crossfade")
    cell.blit(f.render(label, True, (30, 30, 50)), (12, 10))
    sheet.blit(cell, ((i % cols) * cw + 3, (i // cols) * ch + 3))
pygame.image.save(sheet, sheet_path)

# in game: start a turn and grab the front-on moment
d.turn = 0.0
d.pivot = float(d.x)
d.facing = 1
for _ in range(20):
    g.update(DT)
d.face(-1)
for _ in range(200):
    g.update(DT)
    if d.turn_view() == (2, 0.0):
        break
g.draw()
pygame.image.save(g.screen, ingame_path)
print("saved", sheet_path, ingame_path)

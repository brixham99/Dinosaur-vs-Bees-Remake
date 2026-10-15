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
d.h = d.h_target = 0.75
d._geom = None

def turn_for(step):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if 180 * smoothstep(mid) < step:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

layers = []
for step in range(0, 181, 30):
    s = pygame.Surface((1280, 720), pygame.SRCALPHA)
    d.turn = turn_for(step) if step not in (0, 180) else (0.0 if step == 0 else 1.0)
    d.pivot = 640.0
    d.turn_cache = {}
    t0 = time.perf_counter()
    d.draw(s, 0)
    print(f"{step:3d} deg: {(time.perf_counter() - t0) * 1000:.1f} ms")
    layers.append((step, s))
box = layers[0][1].get_bounding_rect()
for _, s in layers:
    box.union_ip(s.get_bounding_rect())
box.inflate_ip(16, 16)
pygame.font.init()
f = pygame.font.Font(None, 44)
zoom = 1.6
cw, ch = int(box.w * zoom), int(box.h * zoom)
cols = 4
rows = 2
sheet = pygame.Surface((cw * cols, ch * rows))
sheet.fill((255, 255, 255))
for i, (step, s) in enumerate(layers):
    cell = pygame.Surface(box.size)
    cell.fill((200, 224, 240))
    pygame.draw.rect(cell, (150, 200, 110), (0, d.feet_y - 6 - box.top, box.w, box.h))
    cell.blit(s, (-box.left, -box.top))
    cell = pygame.transform.smoothscale(cell, (cw - 6, ch - 6))
    label = {0: "0\u00b0 side", 90: "90\u00b0 front", 180: "180\u00b0 side"}.get(step, f"{step}\u00b0")
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
    if d.turn_view()[0] == 90:
        break
g.draw()
pygame.image.save(g.screen, ingame_path)
print("saved", sheet_path, ingame_path)

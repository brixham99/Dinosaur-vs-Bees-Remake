"""Contact sheet of a real turn started with the neck fully raised: the neck
settles, then he turns. Usage: neck_turn_sheet.py OUT.png [start_h]"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
import game as G
from dinobees.settings import DT

out = sys.argv[1]
h0 = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
g = G.Game(G.parse_args(["--seed", "5", "--mute", "--offline", "--highscore-file", "/tmp/dvb_nts.json"]))
g.start_game()
g.spawner.update = lambda dt, n: []
g.banner = 0
d = g.dino
d.h = d.h_target = h0
for _ in range(10):
    g.update(DT)
g.banner = 0
d.face(-1)
shots = []
t = 0.0
for i in range(48):
    if i % 3 == 0:
        layer = pygame.Surface((1280, 720), pygame.SRCALPHA)
        d.draw(layer, 0)
        state = "settling neck" if d.settle is not None else ("turning" if 0 < d.turn < 1 else ("done" if d.turn == 1 else "start"))
        shots.append((t, state, layer))
    g.update(DT)
    t += DT
box = shots[0][2].get_bounding_rect()
for _, _, s in shots:
    box.union_ip(s.get_bounding_rect())
box.inflate_ip(16, 16)
pygame.font.init()
f = pygame.font.Font(None, 30)
cols = 4
rows = (len(shots) + cols - 1) // cols
zoom = 0.62
cw, ch = int(box.w * zoom), int(box.h * zoom)
sheet = pygame.Surface((cw * cols, ch * rows))
sheet.fill((255, 255, 255))
for i, (tt, state, s) in enumerate(shots):
    cell = pygame.Surface(box.size)
    cell.fill((200, 224, 240))
    pygame.draw.rect(cell, (150, 200, 110), (0, d.feet_y - 6 - box.top, box.w, box.h))
    cell.blit(s, (-box.left, -box.top))
    cell = pygame.transform.smoothscale(cell, (cw - 4, ch - 4))
    cell.blit(f.render(f"{tt:.2f} s  {state}", True, (30, 30, 50)), (8, 6))
    sheet.blit(cell, ((i % cols) * cw + 2, (i // cols) * ch + 2))
pygame.image.save(sheet, out)
print("saved", out)

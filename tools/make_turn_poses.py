#!/usr/bin/env python3
"""Cut the three turn poses out of tools/art/dino_turnaround_v2.jpg (or the file named
on the command line; white
background, grey ground line) into assets/:
  dino_turn_34_right.png  three-quarter, facing right-front
  dino_turn_front.png     facing the camera
  dino_turn_34_left.png   three-quarter, facing left-front
Each PNG is cropped to the figure; the feet sit on the bottom edge."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout_white import cutout  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "art", sys.argv[1] if len(sys.argv) > 1 else "dino_turnaround_v2.jpg")
NAMES = ["dino_turn_34_right.png", "dino_turn_front.png", "dino_turn_34_left.png"]
GROUND = (540, 566)          # rows holding the grey ground line

im = np.asarray(Image.open(SRC).convert("RGB")).copy()
band = im[GROUND[0]:GROUND[1]].astype(int)
grey = (band.max(axis=2) - band.min(axis=2) < 40) & (band.min(axis=2) > 90)
band[grey] = 255
im[GROUND[0]:GROUND[1]] = band.astype(np.uint8)
# split at the two widest empty column gaps between the figures
occ = ((255 - im.astype(int)).max(axis=2) > 30).any(axis=0)
gaps, start = [], None
for x, o in enumerate(list(occ) + [True]):
    if not o and start is None:
        start = x
    elif o and start is not None:
        if start > 0 and x < len(occ):
            gaps.append((x - start, (start + x) // 2))
        start = None
cuts = sorted(c for _, c in sorted(gaps)[-2:])
SPLITS = [(0, cuts[0]), (cuts[0], cuts[1]), (cuts[1], im.shape[1])]
print("splits", SPLITS)
for (x0, x1), name in zip(SPLITS, NAMES):
    part = Image.fromarray(im[:, x0:x1])
    out = cutout(part)
    out.save(os.path.join(ROOT, "assets", name))
    print(name, out.size)

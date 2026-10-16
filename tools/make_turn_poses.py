#!/usr/bin/env python3
"""Cut the three turn poses out of tools/art/dino_turnaround.jpg (white
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
SRC = os.path.join(ROOT, "tools", "art", "dino_turnaround.jpg")
SPLITS = [(0, 495), (495, 785), (785, 1280)]
NAMES = ["dino_turn_34_right.png", "dino_turn_front.png", "dino_turn_34_left.png"]
GROUND = (540, 566)          # rows holding the grey ground line

im = np.asarray(Image.open(SRC).convert("RGB")).copy()
band = im[GROUND[0]:GROUND[1]].astype(int)
grey = (band.max(axis=2) - band.min(axis=2) < 40) & (band.min(axis=2) > 90)
band[grey] = 255
im[GROUND[0]:GROUND[1]] = band.astype(np.uint8)
for (x0, x1), name in zip(SPLITS, NAMES):
    part = Image.fromarray(im[:, x0:x1])
    out = cutout(part)
    out.save(os.path.join(ROOT, "assets", name))
    print(name, out.size)

#!/usr/bin/env python3
"""Render keyed assets on contrasting backgrounds and parallax layers tiled
twice (the join is marked with small ticks) for visual inspection."""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets")
out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots")
os.makedirs(out_dir, exist_ok=True)

sprites = ["dino_body.png", "dino_head.png", "dino_head_chomp.png", "bee_up.png",
           "bee_down.png", "bee_red.png", "fern0.png", "fern1.png"]
for bg_name, bg in [("dark", (25, 30, 70)), ("light", (245, 240, 230)), ("red", (200, 40, 60))]:
    sheet = Image.new("RGB", (2000, 520), bg)
    x = 10
    for s in sprites:
        im = Image.open(os.path.join(A, s))
        if im.height > 470:
            im = im.resize((im.width * 470 // im.height, 470), Image.LANCZOS)
        sheet.paste(im, (x, 10), im)
        x += im.width + 10
    sheet.save(os.path.join(out_dir, f"preview_sprites_{bg_name}.png"))

for name in ["layer_sky.png", "layer_mountains.png", "layer_hills.png", "layer_ground.png"]:
    im = Image.open(os.path.join(A, name)).convert("RGBA")
    w, h = im.size
    sheet = Image.new("RGBA", (w * 2, h + 12), (30, 40, 90, 255))
    sheet.alpha_composite(im, (0, 0))
    sheet.alpha_composite(im, (w, 0))
    d = ImageDraw.Draw(sheet)
    d.rectangle([w - 2, h + 2, w + 2, h + 11], fill=(255, 0, 0, 255))
    # crop around the join for a close look
    sheet.save(os.path.join(out_dir, f"preview_{name}"))
    sheet.crop((w - 300, 0, w + 300, h + 12)).save(os.path.join(out_dir, f"preview_join_{name}"))
print("written to", out_dir)

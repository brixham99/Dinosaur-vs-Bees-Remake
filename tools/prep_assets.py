#!/usr/bin/env python3
"""Reproducible asset preparation for Dinosaur vs Bees (remake).

Takes the raw generated JPG artwork (1280x720, flat chroma-key backgrounds)
and produces the clean, cropped, alpha-keyed PNGs that the game loads from
``assets/``.

Usage:
    python3 tools/prep_assets.py [RAW_DIR]

RAW_DIR must contain body.jpg, heads.jpg, bees.jpg, sky.jpg, mountains.jpg,
hills.jpg and ground.jpg (defaults to ./raw).  Only Pillow and numpy are
needed.

Keying approach
---------------
* Green-screen art (the dinosaur is itself green!) is keyed on *green
  dominance*  m = G - max(R, B).  The pure key sits at m ~ 225-250 while the
  darkest/most saturated dino green never exceeds m ~ 105, so a soft ramp
  between those values removes the screen without touching the dino's own
  greens.
* Magenta art is keyed on magenta dominance  m = min(R, B) - G.
* Fringe pixels (partially transparent) get their colour replaced by the
  colour of the nearest fully opaque neighbours (an iterative colour
  dilation).  That completely removes key-colour spill from anti-aliased
  edges - the "despill" step - and it only ever touches edge pixels.
* Single-pixel specks are removed with a small morphological opening.

Seamless parallax layers
------------------------
Each layer is made to tile horizontally with an image-quilting style
minimum-cost seam: the right end of the image is overlapped with the left
start over a band, a vertical seam of least colour difference is found with
dynamic programming, and the two are blended across that seam with a narrow
feather.  The result wraps with no visible join or jump.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
SCREEN_W, SCREEN_H = 1280, 720


# ---------------------------------------------------------------- helpers
def load(raw_dir, name):
    return np.asarray(Image.open(os.path.join(raw_dir, name)).convert("RGB")).astype(np.float32)


def key_alpha(rgb, mode, key_lo=None, fg_hi=None):
    """Return alpha in 0..1 from a dominance metric of the key colour."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    if mode == "green":
        m = g - np.maximum(r, b)
    else:  # magenta
        m = np.minimum(r, b) - g
    # Estimate the key's metric from the image border (always background
    # on these sheets except the bottom rows of the layer strips).
    border = np.concatenate([m[:6].ravel(), m[:, :6].ravel(), m[:, -6:].ravel()])
    bg_level = np.percentile(border[border > 60], 25)
    lo = key_lo if key_lo is not None else bg_level - 18      # fully transparent at/above
    hi = fg_hi if fg_hi is not None else 110 if mode == "green" else 25  # fully opaque at/below
    a = (lo - m) / (lo - hi)
    return np.clip(a, 0.0, 1.0)


def shift(arr, dy, dx):
    out = np.roll(arr, (dy, dx), axis=(0, 1))
    return out


def clean_alpha(a):
    """Remove isolated specks / pinholes with a tiny opening+closing."""
    img = Image.fromarray((a * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))  # opening
    img = img.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))  # closing
    opened = np.asarray(img).astype(np.float32) / 255.0
    # keep the soft original edge where the opening agrees there is content
    return np.minimum(a, np.maximum(opened, (a > 0.98) * opened))


def despill_colours(rgb, a, iterations=10, solid=0.97, rim=0):
    """Replace colours of non-solid pixels with an average of solid
    neighbours, growing outwards. Removes any key-colour contamination.
    Fully transparent pixels far from the art get the median edge colour, so
    no key colour survives anywhere (matters for non-premultiplied scaling
    such as pygame.transform.smoothscale)."""
    rgb = rgb.copy()
    known = a >= solid
    if rim:
        # also re-colour an opaque rim of `rim` px: JPEG chroma bleed reaches
        # a couple of pixels inside the edge on fine foliage
        known = known & ~edge_band(a, width=rim, solid=solid)
        iterations += rim
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for _ in range(iterations):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(a.shape, np.float32)
        for dy, dx in offsets:
            k = shift(known, dy, dx)
            acc += shift(rgb, dy, dx) * k[..., None]
            cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][..., None]
        known = known | grow
    edge = known & ~(a >= solid)
    fill = np.median(rgb[edge], axis=0) if edge.any() else np.array([0, 0, 0], np.float32)
    rgb[~known] = fill
    return rgb


def edge_band(a, width=3, solid=0.97):
    """Opaque pixels within `width` px of transparency."""
    img = Image.fromarray(((a >= solid) * 255).astype(np.uint8))
    eroded = np.asarray(img.filter(ImageFilter.MinFilter(2 * width + 1))) > 0
    return (a >= solid) & ~eroded


def suppress_spill(rgb, a, mode, green_limit=90.0):
    """Classic spill suppression, applied only to the thin opaque rim so the
    art's own greens/pinks inside are never touched."""
    rgb = rgb.copy()
    band = edge_band(a)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    if mode == "green":
        limit = np.maximum(r, b) + green_limit   # dino's richest green is ~ +85
        g_new = np.minimum(g, limit)
        rgb[..., 1] = np.where(band, g_new, g)
    else:
        excess = np.maximum(np.minimum(r, b) - g, 0.0)
        rgb[..., 0] = np.where(band, r - excess, r)
        rgb[..., 2] = np.where(band, b - excess, b)
    return rgb


def remove_islands(a, min_size, thr=0.05):
    """Drop connected blobs of content smaller than min_size pixels."""
    mask = a > thr
    h, w = mask.shape
    seen = np.zeros_like(mask)
    flat_mask, flat_seen = mask.ravel(), seen.ravel()
    for start in np.flatnonzero(mask):
        if flat_seen[start]:
            continue
        stack, comp = [start], []
        flat_seen[start] = True
        while stack:
            i = stack.pop()
            comp.append(i)
            y, x = divmod(i, w)
            for j in (i - 1 if x > 0 else -1, i + 1 if x < w - 1 else -1,
                      i - w if y > 0 else -1, i + w if y < h - 1 else -1):
                if j >= 0 and flat_mask[j] and not flat_seen[j]:
                    flat_seen[j] = True
                    stack.append(j)
        if len(comp) < min_size:
            a.ravel()[comp] = 0.0
    return a


def key_image(rgb, mode, green_limit=90.0, min_island=60, rim=0, **kw):
    a = key_alpha(rgb, mode, **kw)
    a = clean_alpha(a)
    if min_island:
        a = remove_islands(a, min_island)
    rgb = suppress_spill(rgb, a, mode, green_limit)
    rgb = despill_colours(rgb, a, rim=rim)
    a[a < 0.03] = 0.0
    return rgb, a


def box_blur(x, r):
    """Separable box blur (edge-clamped) of a 2-D or 3-D float array."""
    for axis in (0, 1):
        pad = [(0, 0)] * x.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(x, pad, mode="edge"), axis=axis)
        n = x.shape[axis]
        x = (np.take(c, np.arange(2 * r + 1, n + 2 * r + 1), axis=axis)
             - np.take(c, np.arange(0, n), axis=axis)) / (2 * r + 1)
    return x


def unmix_soft(src, rgb, a, mode, solid=0.97):
    """Recover the true colour of see-through parts (volcano smoke) by
    un-mixing the key colour: C = a*F + (1-a)*K  ->  F = (C - (1-a)*K) / a.
    The neighbour-grown despill colours are fine for crisp edges but turn a
    large soft plume into flat blocks; this keeps the smoke's own shading.
    Faint pixels, where the division is unreliable, take an alpha-weighted
    smooth of their neighbours instead."""
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    m = g - np.maximum(r, b) if mode == "green" else np.minimum(r, b) - g
    border = np.concatenate([src[:6].reshape(-1, 3), src[:, :6].reshape(-1, 3), src[:, -6:].reshape(-1, 3)])
    mb = np.concatenate([m[:6].ravel(), m[:, :6].ravel(), m[:, -6:].ravel()])
    key = np.median(border[mb > 60], axis=0)
    soft = (a > 0.0) & (a < solid)
    f = (src - (1 - a[..., None]) * key) / np.maximum(a, 0.05)[..., None]
    f = np.clip(f, 0, 255)
    if mode == "green":                       # no key-coloured cast may survive
        f[..., 1] = np.minimum(f[..., 1], np.maximum(f[..., 0], f[..., 2]))
        # over-subtracting green at faint pixels swings them pink; hold them
        # to the plume's own cool lavender (core is about (190, 189, 225))
        f[..., 0] = np.minimum(f[..., 0], f[..., 1] + 8)
        f[..., 2] = np.minimum(f[..., 2], f[..., 1] + 40)
    else:
        lim = f[..., 1] + 10
        f[..., 0] = np.minimum(f[..., 0], np.maximum(lim, f[..., 2] * 0 + lim))
        f[..., 2] = np.minimum(f[..., 2], lim)
    w = np.clip((a - 0.08) / 0.3, 0, 1) ** 2     # trust in the un-mixed colour
    wf = np.where(soft, w, 0.0) + (a >= solid)
    base = np.where(soft[..., None], f, rgb)
    smooth = box_blur(base * wf[..., None], 5) / np.maximum(box_blur(wf, 5), 1e-3)[..., None]
    smooth = np.where((box_blur(wf, 5) > 1e-3)[..., None], smooth, rgb)
    out = f * w[..., None] + smooth * (1 - w[..., None])
    # crisp ridge edges (within a few px of solid art) keep the grown despill
    # colour; only the loose see-through plume uses the un-mixed colour
    near = np.asarray(Image.fromarray(((a >= solid) * 255).astype(np.uint8))
                      .filter(ImageFilter.MaxFilter(7))) > 0
    blend = np.clip(box_blur((~near).astype(np.float32), 2), 0, 1)[..., None]
    out = out * blend + rgb * (1 - blend)
    return np.where(soft[..., None], out, rgb)


def to_rgba(rgb, a):
    return np.dstack([np.clip(rgb, 0, 255), np.clip(a * 255, 0, 255)]).astype(np.uint8)


def bbox(a, thr=0.05, pad=2):
    ys, xs = np.where(a > thr)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, a.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, a.shape[1])
    return x0, y0, x1, y1


def split_columns(a, n, thr=0.05):
    """Split a sheet into n sprites using empty column gaps."""
    col = (a > thr).sum(axis=0) > 0
    runs, start = [], None
    for x, v in enumerate(col):
        if v and start is None:
            start = x
        elif not v and start is not None:
            runs.append([start, x])
            start = None
    if start is not None:
        runs.append([start, len(col)])
    # merge tiny runs into neighbours until we have n
    runs = [r for r in runs if r[1] - r[0] > 3]
    while len(runs) > n:
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        i = int(np.argmin(gaps))
        runs[i] = [runs[i][0], runs[i + 1][1]]
        del runs[i + 1]
    return runs


def save_sprite(rgb, a, x0, x1, name, pad=2):
    sub_a = np.zeros_like(a)
    sub_a[:, x0:x1] = a[:, x0:x1]
    bx0, by0, bx1, by1 = bbox(sub_a, pad=pad)
    img = to_rgba(rgb[by0:by1, bx0:bx1], sub_a[by0:by1, bx0:bx1])
    Image.fromarray(img, "RGBA").save(os.path.join(OUT, name), optimize=True)
    print(f"  {name:18s} {img.shape[1]}x{img.shape[0]}")
    return bx0, by0, bx1, by1


# --------------------------------------------------------- seamless tiling
def min_cut_seam(cost, margin, max_step=4):
    """Vertical least-cost seam through cost[h, w], confined to
    [margin, w - margin). The seam may move up to max_step px per row so it
    can thread between tree crowns."""
    h, w = cost.shape
    big = 1e12
    c = cost.copy()
    c[:, :margin] = big
    c[:, w - margin:] = big
    acc = c.copy()
    back = np.zeros((h, w), np.int32)
    steps = list(range(-max_step, max_step + 1))
    for y in range(1, h):
        prev = acc[y - 1]
        cands = []
        for d in steps:   # candidate comes from column x + d of previous row
            shifted = np.full(w, big)
            if d >= 0:
                shifted[:w - d] = prev[d:]
            else:
                shifted[-d:] = prev[:w + d]
            cands.append(shifted + abs(d) * 0.5)
        stack = np.vstack(cands)
        idx = np.argmin(stack, axis=0)
        acc[y] += stack[idx, np.arange(w)]
        back[y] = np.array(steps)[idx]
    seam = np.zeros(h, np.int32)
    seam[-1] = int(np.argmin(acc[-1]))
    for y in range(h - 1, 0, -1):
        seam[y - 1] = seam[y] + back[y, seam[y]]
    return seam


def make_seamless(rgba, band, feather=10):
    """Return an image of width (w - band) that wraps seamlessly."""
    img = rgba.astype(np.float32)
    h, w, _ = img.shape
    a = img[..., 3:4] / 255.0
    pre = np.concatenate([img[..., :3] * a, img[..., 3:4]], axis=2)  # premultiplied
    right = pre[:, w - band:]   # continues the end of the output
    left = pre[:, :band]        # leads into the rest of the output
    diff = np.abs(right - left).sum(axis=2) + 4.0 * np.abs(right[..., 3] - left[..., 3])
    # smooth the cost a little so the seam avoids high-detail areas
    for ax in (0, 1):
        diff = sum(np.roll(diff, d, axis=ax) for d in range(-2, 3)) / 5.0
    seam = min_cut_seam(diff, feather + 2)
    xs = np.arange(band)[None, :]
    # weight of 'left' (original start) rises from 0 to 1 across the seam
    wgt = np.clip((xs - seam[:, None]) / feather + 0.5, 0, 1)[..., None]
    blend = right * (1 - wgt) + left * wgt
    out = pre[:, :w - band].copy()
    out[:, :band] = blend
    alpha = out[..., 3:4]
    rgb = np.where(alpha > 0, out[..., :3] / np.maximum(alpha / 255.0, 1e-6), 0)
    return np.concatenate([rgb, alpha], axis=2).clip(0, 255).astype(np.uint8)


def resize(rgba, w, h):
    mode = "RGBA" if rgba.shape[2] == 4 else "RGB"
    img = Image.fromarray(rgba, mode)
    if mode == "RGBA":
        # resize premultiplied to avoid dark fringes
        arr = rgba.astype(np.float32)
        arr[..., :3] *= arr[..., 3:4] / 255.0
        chans = [np.asarray(Image.fromarray(arr[..., i]).resize((w, h), Image.LANCZOS)) for i in range(4)]
        out = np.dstack(chans)
        al = np.clip(out[..., 3:4], 0, 255)
        out[..., :3] = np.where(al > 0.5, out[..., :3] / np.maximum(al / 255.0, 1e-6), 0)
        out[..., 3:4] = al
        return out.clip(0, 255).astype(np.uint8)
    return np.asarray(img.resize((w, h), Image.LANCZOS))


def seam_check(rgba):
    """Mean abs difference between last and first column vs. typical
    neighbouring-column difference (should be similar)."""
    f = rgba.astype(np.float32)
    wrap = np.abs(f[:, -1] - f[:, 0]).mean()
    typical = np.abs(f[:, 1:] - f[:, :-1]).mean()
    return wrap, typical


def remove_sun(rgb):
    """Paint the sun out of the sky (the game draws its own sun or moon per
    theme). Each row is filled with that row's clear-sky colour, blended in
    with a soft radial mask that leaves the clouds alone."""
    rgb = rgb.copy()
    h, w, _ = rgb.shape
    k = w / 1280.0
    sub = rgb[:int(350 * k), :int(450 * k)]
    m = (sub[..., 0] > 240) & (sub[..., 1] > 200) & (sub[..., 2] < 190)
    ys, xs = np.where(m)
    cy, cx = ys.mean(), xs.mean()
    clear = np.zeros((h, 3), np.float32)
    for y in range(h):
        row = rgb[y, int(450 * k):]
        ok = row.min(axis=1) < 215          # not cloud
        clear[y] = np.median(row[ok], axis=0) if ok.sum() > 10 else np.median(row, axis=0)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(yy - cy, xx - cx)
    r0, r1 = 150 * k, 215 * k
    mask = np.clip((r1 - r) / (r1 - r0), 0, 1)
    mask = mask * mask * (3 - 2 * mask)
    cloud = (rgb.min(axis=2) > 215) & (r > 110 * k)
    mask[cloud] *= 0.0
    rgb = rgb * (1 - mask[..., None]) + clear[:, None, :] * mask[..., None]
    return rgb


def layer(raw, name, mode, out_name, scale, band, trim=4, top_pad=6, opaque_bottom=True,
          fg_hi=None, green_limit=90.0, rim=0, sky=False, solid=False, unmix=False):
    rgb = load(raw, name)[:, trim:-trim]
    src = rgb.copy()
    if sky:
        # no sun, and twice as wide (a mirrored copy) so clouds repeat rarely
        rgb = remove_sun(rgb)
        rgb = np.concatenate([rgb, rgb[:, ::-1]], axis=1)
    if mode is None:
        a = np.ones(rgb.shape[:2], np.float32)
    else:
        rgb, a = key_image(rgb, mode, green_limit=green_limit, fg_hi=fg_hi, min_island=0, rim=rim)
        if opaque_bottom:
            # the strips run off the bottom of the frame: keep it solid
            a[-4:] = 1.0
        if solid:
            # everything joined to the bottom of the strip is solid ground, so
            # earthy pinks in the soil never turn slightly see-through; loose
            # bits above it (smoke, fronds) keep their soft alpha
            joined = np.minimum.accumulate((a > 0.5)[::-1], axis=0)[::-1]
            dense = np.where(a.mean(axis=1) > 0.6)[0]    # rows of the main mass
            if len(dense):
                joined[:dense[0]] = False
            a = np.where(joined, 1.0, a)
        if unmix:
            rgb = unmix_soft(src, rgb, a, mode)
    rows = np.where((a > 0.05).any(axis=1))[0]
    y0 = max(rows.min() - top_pad, 0)
    rgba = to_rgba(rgb[y0:], a[y0:])
    tile = make_seamless(rgba, band)
    if mode is not None:
        # the seam may leave a sliver of a cut tree crown: drop it
        al = remove_islands(tile[..., 3].astype(np.float32) / 255.0, 400)
        tile[..., 3] = (al * 255).astype(np.uint8)
    h, w = tile.shape[:2]
    tw, th = int(round(w * scale)), int(round(h * scale))
    tile = resize(tile, tw, th)
    if mode is None:
        tile = tile[..., :3]
        Image.fromarray(tile, "RGB").save(os.path.join(OUT, out_name), optimize=True)
    else:
        Image.fromarray(tile, "RGBA").save(os.path.join(OUT, out_name), optimize=True)
    wrap, typ = seam_check(tile)
    print(f"  {out_name:18s} {tw}x{th}  wrap diff {wrap:.2f} vs neighbour {typ:.2f}")
    return tw, th


# -------------------------------------------------------------------- main
def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "raw")
    os.makedirs(OUT, exist_ok=True)
    meta = {}

    print("Dino body")
    rgb, a = key_image(load(raw, "body.jpg"), "green")
    x0, y0, x1, y1 = save_sprite(rgb, a, 0, a.shape[1], "dino_body.png", pad=3)
    meta["body_crop_origin"] = [int(x0), int(y0)]

    print("Dino heads")
    rgb, a = key_image(load(raw, "heads.jpg"), "green")
    runs = split_columns(a, 2)
    for (cx0, cx1), nm in zip(runs, ["dino_head.png", "dino_head_chomp.png"]):
        save_sprite(rgb, a, cx0, cx1, nm, pad=3)

    print("Bees")
    rgb, a = key_image(load(raw, "bees.jpg"), "magenta")
    runs = split_columns(a, 3)
    for (cx0, cx1), nm in zip(runs, ["bee_up.png", "bee_down.png", "bee_red.png"]):
        save_sprite(rgb, a, cx0, cx1, nm, pad=3)

    print("Foreground ferns (from the ground strip)")
    g = load(raw, "ground.jpg")
    k = g.shape[1] / 1024.0          # art may be 1024 or 1280 wide
    rgb, a = key_image(g, "magenta", fg_hi=-15, rim=2)
    grass_top = int(414 * k)
    for i, (fx0, fx1) in enumerate([(8, 90), (840, 925)]):
        fx0, fx1 = int(fx0 * k), int(fx1 * k)
        sub = np.zeros_like(a)
        sub[int(300 * k):grass_top + 6, fx0:fx1] = a[int(300 * k):grass_top + 6, fx0:fx1]
        # fade the base so it melts into the grass it is drawn on
        fade = np.clip((grass_top + 6 - np.arange(a.shape[0])) / (10.0 * k), 0, 1)
        sub *= fade[:, None]
        bx0, by0, bx1, by1 = bbox(sub, pad=2)
        img = to_rgba(rgb[by0:by1, bx0:bx1], sub[by0:by1, bx0:bx1])
        Image.fromarray(img, "RGBA").save(os.path.join(OUT, f"fern{i}.png"), optimize=True)
        print(f"  fern{i}.png          {img.shape[1]}x{img.shape[0]}")

    print("Parallax layers")
    k = load(raw, "sky.jpg").shape[1] / 1280.0   # scale factors relative to 1280-wide art
    meta["sky"] = layer(raw, "sky.jpg", None, "layer_sky.png", 1.0 / k, band=int(170 * k), trim=4, top_pad=0,
                         sky=True)
    # mountains/hills/ground contain no key-like colours, so they get much
    # stricter opacity thresholds than the (green!) dinosaur
    meta["mountains"] = layer(raw, "mountains.jpg", "green", "layer_mountains.png", 1.0 / k,
                              band=int(220 * k), fg_hi=-35, green_limit=0.0, solid=True,
                              unmix=True)
    meta["hills"] = layer(raw, "hills.jpg", "magenta", "layer_hills.png", 0.92 / k,
                          band=int(300 * k), fg_hi=-15, rim=2, solid=True)
    meta["ground"] = layer(raw, "ground.jpg", "magenta", "layer_ground.png", 0.8 / k,
                           band=int(260 * k), fg_hi=-15, rim=2, solid=True)

    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("done ->", OUT)


if __name__ == "__main__":
    main()

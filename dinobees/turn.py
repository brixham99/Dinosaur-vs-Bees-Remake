"""Solid-looking about-turn frames for the dinosaur.

The side-on dinosaur is drawn into a buffer, then rebuilt as a 2.5D model:
every thin vertical slice of the body, tail and neck becomes a tube slice
whose front-on width is its depth (as for a round body) and whose colour
bands are the art's own (back on top, belly underneath). The slices are
rotated about the vertical axis, given a little perspective and drawn far to
near, so the tail swings round behind him and the neck comes towards the
camera. The legs are lifted out separately and pushed to their own near and
far sides, so they separate and overlap as he turns. Cylinder shading darkens
the side turned from the light. The head is drawn last: a softened profile at
three-quarters, and a purpose-built front face (two eyes taken from the head
art) when he looks at the camera."""
import math

import numpy as np
import pygame

from . import assets

STRIP = 4              # slice width in px
PERSPECTIVE = 0.00055  # scale change per px of depth towards the camera
SHADE_LEVELS = 12


def _gradients():
    """Horizontal cylinder shading strips (multiply), lit from the left."""
    out = []
    for lv in range(SHADE_LEVELS):
        amount = lv / (SHADE_LEVELS - 1)
        g = pygame.Surface((32, 1))
        for i in range(32):
            u = (i + 0.5) / 32 * 2 - 1                 # -1 .. 1 across the tube
            lit = 0.5 + 0.5 * (-0.55 * u + 0.83 * math.sqrt(max(0.0, 1 - u * u)))
            v = 1.0 - amount * (1.0 - (0.62 + 0.42 * lit))
            c = int(max(0, min(255, 255 * v)))
            g.set_at((i, 0), (c, c, c))
        out.append(g)
    return out


_GRAD = None
_MASKS = {}


def _round_mask(w, h, rnd):
    """Alpha mask that rounds a widened slice into a tube's end-on section
    (a superellipse: squarer when only a little of the width is depth)."""
    q = int(rnd * 4)
    key = (w, h, q)
    m = _MASKS.get(key)
    if m is None:
        n = 2.0 + (4 - q) * 2.5
        u = np.abs((np.arange(w) + 0.5) / w * 2 - 1)[:, None]
        v = np.abs((np.arange(h) + 0.5) / h * 2 - 1)[None, :]
        # only round the top and bottom: the slice keeps its full height in the middle
        edge = (1 - u ** n) ** (1 / n)
        a = np.clip((edge - v) * h * 0.5 + 0.5, 0, 1)
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        m.fill((255, 255, 255, 255))
        pa = pygame.surfarray.pixels_alpha(m)
        pa[...] = (a * 255).astype(np.uint8)
        del pa
        if len(_MASKS) > 3000:
            _MASKS.clear()
        _MASKS[key] = m
    return m


def _draw_neck(out, neck, cx, feet_y, c, s, pad_l):
    """The neck as a solid tube: discs along its curve, rotated with the
    body and drawn far to near (all outlines first, then the fills, so the
    tube has one clean outline), with the throat's yellow stripe facing the
    way the throat faces."""
    pts, widths, nup, ts, cols = neck
    # many more discs than the neck's own samples, so no rings show
    m = len(pts)
    f = np.linspace(0, m - 1, m * 5)
    idx = np.arange(m)
    pts = np.stack([np.interp(f, idx, pts[:, 0]), np.interp(f, idx, pts[:, 1])], axis=1)
    nup = np.stack([np.interp(f, idx, nup[:, 0]), np.interp(f, idx, nup[:, 1])], axis=1)
    widths = np.interp(f, idx, widths)
    ts = np.interp(f, idx, ts)
    ss = 2
    xs, ys, rs, bx, by, dep = [], [], [], [], [], []
    for (x, y), w, (nx, ny), t in zip(pts, widths, nup, ts):
        X = x - cx
        depth = X * s
        p = 1.0 + depth * PERSPECTIVE
        xs.append(pad_l + X * c * p)
        ys.append(feet_y + (y - feet_y) * p)
        rs.append(w * 0.5 * p)
        # throat normal (opposite the back) projected to the screen
        bx.append(-nx * c)
        by.append(-ny)
        dep.append(depth)
    x0 = int(min(xs) - max(rs) - 12)
    y0 = int(min(ys) - max(rs) - 12)
    x1 = int(max(xs) + max(rs) + 12)
    y1 = int(max(ys) + max(rs) + 12)
    layer = pygame.Surface(((x1 - x0) * ss, (y1 - y0) * ss), pygame.SRCALPHA)
    order = sorted(range(len(xs)), key=lambda i: dep[i])
    o = 2.4
    P = lambda i: ((xs[i] - x0) * ss, (ys[i] - y0) * ss)
    # dorsal plates poking up along the back
    plate_light = assets.tint_colour(cols["plate"], (1.25, 1.18, 1.2))
    n = len(xs)
    for t in (0.16, 0.3, 0.44, 0.58, 0.72):
        i = min(n - 1, int(t * (n - 1)))
        r = (9.5 - 5.0 * t)
        cxp = (xs[i] - bx[i] * rs[i] * 0.85 - x0) * ss
        cyp = (ys[i] - by[i] * rs[i] * 0.85 - y0) * ss
        pygame.draw.circle(layer, cols["outline"], (cxp, cyp), (r + o) * ss)
        pygame.draw.circle(layer, cols["plate"], (cxp, cyp), r * ss)
        pygame.draw.circle(layer, plate_light, (cxp - r * 0.2 * ss, cyp - r * 0.3 * ss), r * 0.4 * ss)
    for i in order:
        pygame.draw.circle(layer, cols["outline"], P(i), (rs[i] + o) * ss)
    for i in order:
        pygame.draw.circle(layer, cols["green"], P(i), rs[i] * ss)
    for i in order:
        r = rs[i]
        k = math.hypot(bx[i], by[i])
        px, py = P(i)
        # the yellow throat: a disc pushed towards the throat side; the more
        # the throat faces us, the more of it shows
        pygame.draw.circle(layer, cols["belly_shade"], (px + bx[i] * r * 0.42 * ss, py + by[i] * r * 0.42 * ss),
                           r * (0.5 + 0.25 * (1 - k)) * ss)
        pygame.draw.circle(layer, cols["belly"], (px + bx[i] * r * 0.36 * ss, py + by[i] * r * 0.36 * ss),
                           r * (0.42 + 0.25 * (1 - k)) * ss)
    for t, rr in ((0.24, 6.5), (0.4, 5.0), (0.55, 4.0)):
        i = min(n - 1, int(t * (n - 1)))
        px, py = P(i)
        q = (px - bx[i] * rs[i] * 0.45 * ss, py - by[i] * rs[i] * 0.45 * ss)
        pygame.draw.circle(layer, cols["spot_rim"], q, (rr + 0.8) * ss)
        pygame.draw.circle(layer, cols["light"], q, rr * ss)
    layer = pygame.transform.smoothscale(layer, (x1 - x0, y1 - y0))
    out.blit(layer, (x0, y0))


def _cropped(fn):
    """Run an in-place effect on just the silhouette's bounding box."""
    def run(surf, *a, pad=6, **k):
        r = surf.get_bounding_rect(min_alpha=1)
        if r.w == 0:
            return
        r = r.inflate(pad * 2, pad * 2).clip(surf.get_rect())
        fn(surf.subsurface(r), *a, **k)
    return run


def _outline(surf, colour, width=2):
    """Antialiased outline round a silhouette, drawn behind it."""
    a = pygame.surfarray.array_alpha(surf).astype(np.float32) / 255.0
    d = a.copy()
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width + 1 and (dx or dy):
                d = np.maximum(d, np.roll(np.roll(a, dx, axis=0), dy, axis=1))
    ring = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    ring.fill((*colour, 0))
    pa = pygame.surfarray.pixels_alpha(ring)
    pa[...] = (np.clip(d, 0, 1) * 255).astype(np.uint8)
    del pa
    ring.blit(surf, (0, 0))
    surf.fill((0, 0, 0, 0))
    surf.blit(ring, (0, 0))


def _round_shade_full(surf, amount):
    """Shade a flat silhouette as a rounded form: pixels near the outline
    are darker (turning away from us), the middle stays bright, and the light
    comes a little from the left."""
    w, h = surf.get_size()
    a = pygame.surfarray.array_alpha(surf)
    mask = pygame.Surface((w, h))
    m = (a > 60).astype(np.uint8) * 255
    pygame.surfarray.blit_array(mask, np.repeat(m[:, :, None], 3, axis=2))
    small = pygame.transform.smoothscale(mask, (max(1, w // 10), max(1, h // 10)))
    small = pygame.transform.smoothscale(small, (max(1, w // 5), max(1, h // 5)))
    blur = pygame.transform.smoothscale(small, (w, h))
    b = pygame.surfarray.array3d(blur)[:, :, 0].astype(np.float32) / 255.0
    # light from the left: compare with the blur a little to the right
    shifted = np.roll(b, -10, axis=0)
    inner = np.clip((b - 0.5) * 2.2, 0, 1)
    lit = np.clip(0.5 + (b - shifted) * 2.5, 0, 1)
    v = 1.0 - amount * (1.0 - inner) - amount * 0.45 * (1.0 - lit) + amount * 0.25 * lit * inner
    v = np.clip(v, 0.55, 1.12)
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[...] = np.clip(rgb.astype(np.float32) * v[:, :, None], 0, 255).astype(np.uint8)
    del rgb


_outline_full = _outline
_outline = _cropped(_outline_full)
_round_shade = _cropped(_round_shade_full)


def build_front_head(head_art, scale, cols):
    """A front-on face in the style of the profile head: green dome, yellow
    lower jaw, nostrils, a smile and two eyes cropped from the head art."""
    ss = 4
    W, H = int(300 * scale), int(330 * scale)
    big = pygame.Surface((W * ss, H * ss), pygame.SRCALPHA)
    o = 2.8 * ss
    cx = W * ss / 2

    def ell(colour, x, y, rx, ry):
        pygame.draw.ellipse(big, colour, pygame.Rect(x - rx, y - ry, 2 * rx, 2 * ry))

    S = scale * ss
    # head plates along the top, like the back of the profile head
    for dx, dy, r in ((0, 18, 26), (-62, 34, 22), (62, 34, 22)):
        ell(cols["outline"], cx + dx * S, dy * S + 26 * S, r * S + o, r * S + o)
        ell(cols["plate"], cx + dx * S, dy * S + 26 * S, r * S, r * S)
    dome = (cx, 150 * S, 128 * S, 118 * S)
    muzzle = (cx, 228 * S, 112 * S, 82 * S)
    ell(cols["outline"], dome[0], dome[1], dome[2] + o, dome[3] + o)
    ell(cols["outline"], muzzle[0], muzzle[1], muzzle[2] + o, muzzle[3] + o)
    ell(cols["green"], *dome)
    ell(cols["green"], *muzzle)
    # yellow lower jaw: the muzzle's lower half
    jaw = pygame.Surface(big.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(jaw, cols["belly"], pygame.Rect(muzzle[0] - muzzle[2], muzzle[1] - muzzle[3],
                                                         2 * muzzle[2], 2 * muzzle[3]))
    jaw.fill((0, 0, 0, 0), pygame.Rect(0, 0, W * ss, int(muzzle[1] + 6 * S)))
    big.blit(jaw, (0, 0))
    # smile along the top of the jaw
    pygame.draw.arc(big, cols["outline"], pygame.Rect(cx - 70 * S, muzzle[1] - 40 * S, 140 * S, 60 * S),
                    math.pi * 1.08, math.pi * 1.92, int(2.6 * ss))
    # darker spots on the dome, as on the profile head
    for dx, dy, r in ((-86, 120, 14), (-70, 160, 9), (88, 128, 12), (76, 168, 8), (-30, 70, 10), (34, 66, 8)):
        ell(cols["dark"], cx + dx * S, dy * S, r * S, r * S * 0.85)
    # soft highlight upper left
    hl = pygame.Surface(big.get_size(), pygame.SRCALPHA)
    ell_rect = pygame.Rect(cx - 100 * S, 60 * S, 120 * S, 80 * S)
    pygame.draw.ellipse(hl, (255, 255, 255, 34), ell_rect)
    big.blit(hl, (0, 0))
    # nostrils
    for dx in (-26, 26):
        ell(cols["outline"], cx + dx * S, 214 * S, 9 * S, 6 * S)
    face = pygame.transform.smoothscale(big, (W, H))
    # eyes from the art (white, iris and lid line), mirrored for the other side
    eye = head_art.subsurface(pygame.Rect(156, 78, 88, 102)).copy()
    eye = pygame.transform.smoothscale(eye, (max(1, int(88 * scale)), max(1, int(102 * scale))))
    ew, eh = eye.get_size()
    # feather the crop to an oval so no square patch shows round the eye
    fm = pygame.Surface((ew * 4, eh * 4), pygame.SRCALPHA)
    for i in range(8):
        a = int(255 * (i + 1) / 8)
        inset = (8 - i) * 2
        pygame.draw.ellipse(fm, (255, 255, 255, a), pygame.Rect(inset, inset, ew * 4 - 2 * inset, eh * 4 - 2 * inset))
    fm = pygame.transform.smoothscale(fm, (ew, eh))
    eye.blit(fm, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    ey = int(122 * scale) - eh // 2
    face.blit(eye, (int(W / 2 + 46 * scale - ew / 2), ey))
    face.blit(pygame.transform.flip(eye, True, False), (int(W / 2 - 46 * scale - ew / 2), ey))
    return face


def build_frame(buf, cx, feet_y, body_rect, hinge_y, legs, phi, head, neck=None):
    """Render the turned dinosaur.

    buf      SRCALPHA buffer with the side-on dino (no head), facing right
    cx       model x of the body centre in buffer coordinates (the pivot)
    feet_y   ground line (perspective is anchored there)
    body_rect  body frame rectangle in the buffer
    hinge_y  buffer row where the legs separate from the body
    legs     [(x0, x1, is_far)] leg column ranges in buffer coordinates
    phi      yaw in degrees: 0 side-on facing right, 90 facing the camera
    head     (images_by_view, model centre (x, y)) - see Dino._turn_head
    Returns (surface, left_x_offset relative to the pivot)."""
    global _GRAD
    if _GRAD is None:
        _GRAD = _gradients()
    r = math.radians(phi)
    c, s = math.cos(r), math.sin(r)
    bw, bh = buf.get_size()
    alpha = pygame.surfarray.array_alpha(buf)
    # take the dark outline out of the slices (stacked slices would turn it
    # into stripes); a clean outline goes round the finished silhouette
    rgb = pygame.surfarray.array3d(buf).astype(np.int32)
    lum = (rgb[..., 0] * 3 + rgb[..., 1] * 6 + rgb[..., 2]) // 10
    clean = buf.copy()
    ca = pygame.surfarray.pixels_alpha(clean)
    dark = lum < 66
    ca[dark] = 0
    soft = (lum >= 66) & (lum < 88)
    ca[soft] = (ca[soft].astype(np.int32) * (lum[soft] - 66) // 22).astype(np.uint8)
    del ca
    outline_rgb = tuple(int(v) for v in np.median(rgb[dark & (alpha > 200)], axis=0)) if (dark & (alpha > 200)).any() else (4, 66, 6)
    solid = alpha > 100
    leg_mask = np.zeros_like(solid)
    bx0, bx1 = max(0, body_rect.left), min(bw, body_rect.right)
    hy = int(hinge_y)
    for x0, x1, _ in legs:
        leg_mask[max(0, int(x0)):min(bw, int(x1)), hy:] = True
    upper = solid & ~leg_mask
    counts = upper.sum(axis=1).astype(np.float32)
    body_t = body_rect.height * 0.78
    thick = np.clip(counts * 1.25, 6, body_t)
    kern = np.ones(17) / 17
    thick = np.convolve(thick, kern, mode="same")

    items = []                       # (x, y0, y1, z, depth thickness, kind)
    for x in range(0, bw, STRIP):
        col = upper[x:x + STRIP].any(axis=0)
        ys = np.where(col)[0]
        if len(ys) == 0:
            continue
        X = x + STRIP / 2 - cx
        # the tail curls away to his far side, so it shows beside him front-on
        z = -0.0045 * (X + 70) ** 2 if X < -70 else 0.0
        items.append((x, ys[0], ys[-1] + 1, z, float(thick[x:x + STRIP].mean()), 0))
    leg_z = body_t * 0.34
    for x0, x1, far in legs:
        lw = max(1.0, x1 - x0)
        for x in range(int(x0), int(x1), STRIP):
            col = (solid[x:x + STRIP, hy:] & leg_mask[x:x + STRIP, hy:]).any(axis=0)
            ys = np.where(col)[0]
            if len(ys) == 0:
                continue
            u = ((x + STRIP / 2) - (x0 + x1) / 2) / (lw / 2)
            t = lw * 0.55 * math.sqrt(max(0.05, 1 - min(1.0, u * u)))   # round leg
            items.append((x, hy + ys[0], hy + ys[-1] + 1, -leg_z if far else leg_z, t, 1 if far else 2))

    draw = []
    for x, y0, y1, z, t, kind in items:
        X = x + STRIP / 2 - cx
        depth = X * s + z * c
        p = 1.0 + depth * PERSPECTIVE
        sx = (X * c - z * s) * p
        w = (STRIP * abs(c) + t * abs(s)) * p
        draw.append((depth, x, y0, y1, sx, w, p, kind))
    draw.sort(key=lambda d: d[0])

    pad_l, pad_r = 260, 560
    out_w = pad_l + pad_r
    out = pygame.Surface((out_w, bh), pygame.SRCALPHA)
    far_layer = pygame.Surface((out_w, bh), pygame.SRCALPHA)
    for depth, x, y0, y1, sx, w, p, kind in draw:
        h = y1 - y0
        ww = max(1, int(math.ceil(w)) + 1)
        hh = max(1, int(round(h * p)))
        piece = clean.subsurface(pygame.Rect(x, y0, min(STRIP, bw - x), h))
        piece = pygame.transform.smoothscale(piece, (ww, hh))
        rnd = (w - STRIP * abs(c) * p) / max(w, 1e-6)      # how much of the width is the round depth
        if kind == 0 and rnd > 0.25 and ww > 6:
            piece.blit(_round_mask(ww, hh, rnd), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        top = feet_y + (y0 - feet_y) * p
        # far legs go on their own layer, shaded as in the body's shadow
        (far_layer if kind == 1 else out).blit(piece, (round(pad_l + sx - ww / 2), round(top)))
    if abs(s) > 0.01:
        v = int(255 * (1 - 0.3 * abs(s)))
        far_layer.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
    _outline(far_layer, outline_rgb)
    _outline(out, outline_rgb)
    if neck is not None:
        _draw_neck(out, neck, cx, feet_y, c, s, pad_l)
    if abs(s) > 0.01:
        _round_shade(out, 0.3 * abs(s))
    far_layer.blit(out, (0, 0))
    out = far_layer

    # head, nearest of all once he looks round
    imgs, (hx, hy_) = head
    X = hx - cx
    depth = X * s
    p = 1.0 + depth * PERSPECTIVE
    sx = X * c * p
    if phi >= 75:
        img = imgs["front"]
    else:
        img = imgs["side"]
        sq = 0.62 + 0.38 * c          # rounder, slightly foreshortened profile
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * sq)), img.get_height()))
    img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * p)), max(1, int(img.get_height() * p))))
    img = img.copy()
    _round_shade(img, 0.18 if phi < 75 else 0.12)
    hy2 = feet_y + (hy_ - feet_y) * p
    out.blit(img, img.get_rect(center=(round(pad_l + sx), round(hy2))))
    return out, -pad_l

#!/usr/bin/env python3
"""Dinosaur vs Bees - a pygame remake.

Raise and lower the dinosaur's long neck, chomp the yellow bees and keep
clear of the angry red ones.

Run:  python3 game.py            (see --help for testing options)
"""
import argparse
import json
import math
import os
import random
import sys
import time

import numpy as np
import pygame

from dinobees import assets, ui
from dinobees.ai import AutoPilot
from dinobees.assets import THEMES, theme_index_for_level
from dinobees.bees import Bee, BeeArt, Spawner
from dinobees.dino import Dino, DinoArt
from dinobees.settings import (BASE_WALK_SPEED, BEES_PER_LEVEL, DINO_X, DT, FPS,
                               HEIGHT, HIGHSCORE_FILE, MAX_HEARTS, MAX_WALK_SPEED,
                               TITLE, WALK_SPEED_PER_LEVEL, WIDTH)
from dinobees.scores import NAME_MAX, TOP_N, Flags, Leaderboard, clean_name
from dinobees.settings import ASSET_DIR
from dinobees.sfx import Sound
from dinobees.world import World

MUSIC_FILE = os.path.join(ASSET_DIR, "music", "game_music.ogg")
TITLE_PANEL_TIME = 7.0       # title alternates: how to play <-> Top 10, 7 s each
BOARD_REFRESH = 3600.0       # re-fetch the Top 10 (and retry unsent scores) hourly
DEMO_SCORES = [("Archie", 2480, "GB"), ("Holly", 2210, "GB"), ("Rex", 1890, "US"), ("Nathan", 1650, "GB"),
               ("Kai", 1400, "AU"), ("Lena", 1220, "DE"), ("Sean", 980, "IE"), ("Zoe", 760, "FR"),
               ("Marco", 540, "IT"), ("Pip", 320, "GB")]
GOLD = (255, 214, 90)
CREAM = (255, 248, 225)


def load_high_score(path):
    try:
        with open(path) as f:
            return int(json.load(f).get("high_score", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def save_high_score(path, score):
    try:
        with open(path, "w") as f:
            json.dump({"high_score": int(score)}, f)
    except OSError as exc:
        print(f"Could not save high score: {exc}")


class Game:
    def __init__(self, args):
        self.args = args
        self.headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(TITLE)
        flags = pygame.SCALED if not self.headless else 0
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=0)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.clock = pygame.time.Clock()
        self.rng = random.Random(args.seed)
        np.random.seed(args.seed if args.seed is not None else None)

        self.world = World(self.rng)
        self.dino_art = DinoArt()
        self.bee_art = BeeArt()
        icon = pygame.transform.smoothscale(self.dino_art.heads[0], (64, 51))
        pygame.display.set_icon(icon)
        self.dino = Dino(self.dino_art, DINO_X, self.world.grass_y + 8)
        self.pilot = AutoPilot(self.dino, self.rng)
        self.sound = Sound(enabled=not args.mute)
        if args.mute and self.sound.ok:
            self.sound.muted = True

        self.heart_full = ui.make_heart(40, True)
        self.heart_empty = ui.make_heart(40, False)
        self.red_flash = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.red_flash.fill((220, 20, 30))
        self.title_panel = ui.panel((540, 287))
        self.dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.dim.fill((8, 10, 24, 150))

        self.hs_path = args.highscore_file or HIGHSCORE_FILE
        online = not (args.offline or args.frames)
        self.board = Leaderboard(online=online, **({"path": args.scores_file} if args.scores_file else {}))
        if args.demo_scores:
            self.board.entries = list(DEMO_SCORES)   # shown only, never sent
        self.flags = Flags(download=not args.offline)
        self.board.refresh()
        self.board_t = 0.0
        self.high_score = max(load_high_score(self.hs_path), self.board.high_score())
        self.entry_active = False
        self.entry_name = ""
        self.entry_note = ""
        self.title_t = 0.0
        # bees fly between just under the top of the screen and just above the grass;
        # red ones stay high enough that the neck can always be lowered beneath them
        self.spawner = Spawner(self.rng, top=70, bottom=self.world.grass_y - 55,
                               red_bottom=self.world.grass_y - 175)
        self.state = "title"
        self.frame = 0
        self.stats = {"games": 0, "max_level": 1, "max_score": 0, "eaten": 0, "stings": 0}
        self.frame_times = []
        self.reset_game(level=1)
        self.title_bees = []
        self.world.set_theme(0, instant=True)
        # the title screen is silent; the music starts with each game

    # ------------------------------------------------------------ lifecycle
    def reset_game(self, level=1):
        self.level = level
        self.score = 0
        self.hearts = MAX_HEARTS
        self.combo = 0
        self.best_combo = 0
        self.eaten = 0
        self.eaten_this_level = 0
        self.bees = []
        self.particles = []
        self.floaters = []
        self.flash = 0.0
        self.shake = 0.0
        self.banner = 0.0
        self.dying = 0.0
        self.new_high = False
        self.walk_speed = self.target_walk_speed()
        self.over_timer = 0.0
        self.dino.reset()
        self.spawner.reset(level)

    def target_walk_speed(self):
        return min(MAX_WALK_SPEED, BASE_WALK_SPEED + WALK_SPEED_PER_LEVEL * (self.level - 1))

    def start_game(self):
        self.reset_game(level=self.args.level)
        self.state = "play"
        self.world.set_theme(theme_index_for_level(self.level))
        self.banner = 2.6
        self.stats["games"] += 1
        self.sound.play("start", 0.7)
        self.sound.start_music(MUSIC_FILE)   # from the top; paused while the sound is off
        self.log(f"game {self.stats['games']} started at level {self.level}")

    def log(self, msg):
        if self.args.frames:
            print(f"[frame {self.frame:6d}] {msg}")

    # --------------------------------------------------------------- events
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if self.entry_active:
                if ev.type == pygame.TEXTINPUT:
                    self.entry_text(ev.text)
                elif ev.type == pygame.KEYDOWN:
                    self.entry_key(ev.key)
                continue
            if ev.type != pygame.KEYDOWN:
                continue
            k = ev.key
            if k == pygame.K_m:
                muted = self.sound.toggle_mute()
                self.floaters.append([ui.text("Sound off" if muted else "Sound on", 26), WIDTH - 120, HEIGHT - 40, 1.2])
            if self.state == "title":
                if k == pygame.K_ESCAPE:
                    return False
                if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.start_game()
            if k == pygame.K_F3:
                self.args.hitboxes = not self.args.hitboxes
            elif self.state == "play":
                if k in (pygame.K_p, pygame.K_ESCAPE):
                    self.state = "paused"
                    self.sound.hold_music(True)
                elif k == pygame.K_SPACE:
                    if self.dino.try_chomp():
                        self.sound.play("chomp", 0.6)
            elif self.state == "paused":
                if k in (pygame.K_p, pygame.K_ESCAPE):
                    self.state = "play"
                    self.sound.hold_music(False)
            elif self.state == "gameover":
                if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.start_game()
                elif k == pygame.K_ESCAPE:
                    self.state = "title"
                    self.sound.stop_music()
                    self.title_t = 0.0
                    self.board.refresh()
                    self.world.set_theme(0)
        return True

    # ----------------------------------------------------------- name entry
    def entry_text(self, text):
        for ch in text:
            if ch.isascii() and (ch.isalnum() or ch == " ") and len(self.entry_name) < NAME_MAX:
                if ch == " " and (not self.entry_name or self.entry_name.endswith(" ")):
                    continue
                self.entry_name += ch

    def entry_key(self, key):
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            name = clean_name(self.entry_name)
            if not name:
                return          # type a name first (Esc skips)
            self.entry_active = False
            self.entry_note = name
            self.board.submit(name, self.score)
            pygame.key.stop_text_input()
            self.over_timer = min(self.over_timer, 0.8)
        elif key == pygame.K_ESCAPE:
            self.entry_active = False
            self.entry_note = ""
            pygame.key.stop_text_input()
        elif key == pygame.K_BACKSPACE:
            self.entry_name = self.entry_name[:-1]

    def entry_status(self):
        name = self.entry_note
        if self.score <= 0:
            return ""
        if not name:
            return "Score not sent"
        if not self.board.online:
            return f"Saved as {name}"
        if (name, self.score) in self.board.pending:
            return f"Sending as {name}…" if self.board.busy else "Offline – will send later"
        return f"Score sent as {name}"

    # --------------------------------------------------------------- update
    def update(self, dt):
        self.frame += 1
        if self.state == "paused":
            return
        keys = pygame.key.get_pressed()
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        if self.state == "play" and self.dying <= 0 and not self.args.autoplay:
            left = keys[pygame.K_LEFT] or keys[pygame.K_a]
            right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
            if left != right:
                self.dino.face(-1 if left else 1)

        self.board_t += dt
        if self.board_t > BOARD_REFRESH:
            self.board_t = 0.0
            self.board.refresh()
        if self.state == "title":
            self.title_t += dt
            self.update_title(dt)
            if self.args.autoplay and self.frame > 40:
                self.start_game()
            return

        if self.state == "play" and self.args.autoplay and self.dying <= 0:
            up, down, chomp = self.pilot.decide(self.bees, dt)
            if chomp and self.dino.try_chomp():
                self.sound.play("chomp", 0.6)

        # walking speed eases to the level's pace, or to a halt when he faints
        target = 0.0 if self.dying > 0 or self.state == "gameover" else self.target_walk_speed()
        self.walk_speed += (target - self.walk_speed) * min(1.0, dt * (1.2 if target == 0 else 2.0))
        # the world scrolls the way he is walking: it slows to a stop as he
        # turns edge-on and runs backwards once he is facing left
        heading = self.walk_speed * self.dino.xscale
        self.world.update(dt, heading)
        self.dino.update(dt, up and self.state == "play", down and self.state == "play", heading)

        if self.state == "play" and self.dying <= 0:
            for b in self.spawner.update(dt, len(self.bees)):
                self.bees.append(b)
        g = self.dino.geometry()
        homing = self.spawner.params()[5]
        for b in self.bees:
            b.update(dt, g["head_centre"][1], homing if b.kind == "red" else 0.0)
        if self.state == "play" and self.dying <= 0:
            self.collide(dt)
        self.cull_bees()
        self.update_effects(dt)

        if self.dying > 0:
            self.dying += dt
            if self.dying > 2.2 and self.state == "play":
                self.game_over()
        if self.state == "gameover":
            self.over_timer += dt
            if self.args.autoplay and self.over_timer > 3.0:
                self.start_game()

        near = sum(1 for b in self.bees if b.active and b.state == "fly" and 0 < b.x < WIDTH)
        self.sound.set_buzz(min(1.0, near / 6.0) if self.state == "play" else 0.0)

    def update_title(self, dt):
        self.walk_speed += (BASE_WALK_SPEED - self.walk_speed) * min(1.0, dt * 2)
        self.world.update(dt, self.walk_speed)
        # neck idly browsing up and down
        t = self.world.time
        self.dino.h_target = 0.66 + 0.3 * math.sin(t * 0.7) * math.sin(t * 0.23 + 1)
        self.dino.update(dt, False, False, self.walk_speed)
        if self.rng.random() < dt * 0.9 and len(self.title_bees) < 6:
            self.title_bees.append(Bee("yellow" if self.rng.random() < 0.8 else "red", WIDTH + 60,
                                       self.rng.uniform(80, 300), -self.rng.uniform(150, 230),
                                       self.rng.uniform(15, 40), self.rng.uniform(0.3, 0.7),
                                       self.rng.uniform(0, 6.28), "sine"))
        for b in self.title_bees:
            b.update(dt)
        self.title_bees = [b for b in self.title_bees if b.x > -100]
        self.update_effects(dt)

    def collide(self, dt):
        d = self.dino
        (mx, my), mr = d.mouth_circle()
        (hx, hy), hr = d.head_circle()
        neck = d.neck_circles()
        body = d.body_hit_circles()
        for b in self.bees:
            if not b.active or b.state != "fly":
                continue
            br = b.radius
            if d.from_behind(b.vx) and self.touches(b, mx, my, mr, hx, hy, hr, neck, body):
                self.bounce(b)
                continue
            dm = math.hypot(b.x - mx, b.y - my)
            dh = math.hypot(b.x - hx, b.y - hy)
            on_head = dm < mr + br or dh < hr + br
            if b.kind != "red" and d.chomping and (dm < mr + br + 8 or dh < hr + br):
                self.eat(b)
                continue
            hit = False
            if on_head:
                if b.kind == "red":
                    hit = True
                else:
                    # a moment's grace so a slightly late chomp still counts
                    b.touch += dt
                    hit = b.touch > 0.09
            else:
                b.touch = 0.0
                for (cx, cy), r in neck:
                    if (b.x - cx) ** 2 + (b.y - cy) ** 2 < (r + br * 0.8) ** 2:
                        hit = True
                        break
                if not hit:
                    for (cx, cy), r in body:
                        if (b.x - cx) ** 2 + (b.y - cy) ** 2 < (r + br * 0.8) ** 2:
                            hit = True
                            break
            if hit and d.invuln <= 0:
                self.sting(b)

    @staticmethod
    def touches(b, mx, my, mr, hx, hy, hr, neck, body):
        br = b.radius
        if math.hypot(b.x - mx, b.y - my) < mr + br or math.hypot(b.x - hx, b.y - hy) < hr + br:
            return True
        for (cx, cy), r in neck + body:
            if (b.x - cx) ** 2 + (b.y - cy) ** 2 < (r + br * 0.8) ** 2:
                return True
        return False

    def bounce(self, b):
        """A bee catching him up from behind glances off the armoured plates
        along his back: no sting, but he can't eat it either."""
        b.state = "flee"
        self.sound.play("bonk", 0.7)
        self.burst(b.x, b.y, [(255, 255, 255), (200, 220, 255), (255, 240, 160)], 10, 160)
        if b.kind == "red":
            self.stats["bonks"] = self.stats.get("bonks", 0) + 1
            self.floaters.append([ui.text("Bonk!", 32, (180, 220, 255), outline=2), b.x, b.y - 40, 0.9])
            self.log("a red bee bounced off his back")
        elif self.combo:
            self.combo = 0   # a yellow bee that gets away still breaks the combo

    def eat(self, b):
        b.state = "eaten"
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        mult = self.multiplier()
        (mx, my), _ = self.dino.mouth_circle()
        if b.kind == "gold":
            pts = 50 * mult
            if self.hearts < MAX_HEARTS:
                self.hearts += 1
                msg = f"+{pts}  +1 heart!"
            else:
                pts += 200
                msg = f"+{pts}  Bonus!"
            self.sound.play("gold", 0.8)
            colours = [(255, 230, 120), (255, 255, 255), (255, 190, 60)]
            n = 34
        else:
            pts = 10 * mult
            msg = f"+{pts}"
            self.sound.play("eat", 0.7)
            colours = [(255, 220, 60), (255, 255, 200), (40, 30, 20)]
            n = 18
        self.score += pts
        self.eaten += 1
        self.eaten_this_level += 1
        self.stats["eaten"] += 1
        self.burst(b.x, b.y, colours, n, 220)
        self.floaters.append([ui.text(msg, 30 if b.kind != "gold" else 34, GOLD if b.kind == "gold" else CREAM,
                                      outline=2), mx, my - 50, 1.0])
        if self.eaten_this_level >= BEES_PER_LEVEL:
            self.level_up()

    def multiplier(self):
        return min(5, 1 + self.combo // 5)

    def sting(self, b):
        b.state = "flee"
        d = self.dino
        self.hearts -= 1
        self.combo = 0
        self.flash = 1.0
        self.shake = 0.35
        self.stats["stings"] += 1
        (mx, my), _ = d.mouth_circle()
        d.sting(from_above=b.y < my)
        self.sound.play("sting", 0.8)
        self.burst(b.x, b.y, [(255, 80, 60), (255, 200, 200), (200, 20, 20)], 16, 180)
        self.floaters.append([ui.text("Ouch!", 34, (255, 120, 110), outline=2), b.x, b.y - 40, 0.9])
        self.log(f"stung by a {b.kind} bee, hearts left {self.hearts}")
        if self.hearts <= 0:
            self.dying = 0.001
            d.fainted = 0.001
            d.invuln = 0.0

    def level_up(self):
        self.level += 1
        self.eaten_this_level = 0
        self.spawner.level = self.level
        self.world.set_theme(theme_index_for_level(self.level))
        self.banner = 2.6
        self.sound.play("level", 0.7)
        self.stats["max_level"] = max(self.stats["max_level"], self.level)
        self.log(f"level up -> {self.level} ({THEMES[theme_index_for_level(self.level)]['name']}), score {self.score}")

    def game_over(self):
        self.state = "gameover"
        self.over_timer = 0.0
        self.sound.play("gameover", 0.7)
        self.sound.set_buzz(0.0)
        self.sound.stop_music(fade_ms=1500)
        self.stats["max_score"] = max(self.stats["max_score"], self.score)
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_high = True
            save_high_score(self.hs_path, self.score)
        self.board.record_local(self.score)
        self.entry_note = ""
        if self.score > 0 and not self.args.autoplay:
            self.entry_active = True
            self.entry_name = self.board.last_name
            pygame.key.start_text_input()
        self.log(f"game over: score {self.score}, level {self.level}, eaten {self.eaten}"
                 f"{' (new high score)' if self.new_high else ''}")

    def cull_bees(self):
        keep = []
        for b in self.bees:
            if b.state == "eaten":
                continue
            if b.state == "flee" and b.flee_t > 0.9:
                continue
            if b.x < -90:
                if b.state == "fly" and b.kind != "red" and self.state == "play" and self.dying <= 0:
                    if self.combo >= 3:
                        self.floaters.append([ui.text("Combo lost", 24, (255, 230, 200), outline=2), 110, 150, 0.9])
                    self.combo = 0
                continue
            keep.append(b)
        self.bees = keep

    def burst(self, x, y, colours, n, speed):
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            s = self.rng.uniform(0.3, 1.0) * speed
            life = self.rng.uniform(0.35, 0.7)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, life, life,
                                   self.rng.choice(colours), self.rng.uniform(2.5, 5.5)])

    def update_effects(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 380 * dt
            p[2] *= 0.98
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for f in self.floaters:
            f[2] -= 45 * dt
            f[3] -= dt
        self.floaters = [f for f in self.floaters if f[3] > 0]
        self.flash = max(0.0, self.flash - dt * 2.8)
        self.shake = max(0.0, self.shake - dt)
        self.banner = max(0.0, self.banner - dt)

    # ----------------------------------------------------------------- draw
    def draw(self):
        shaking = self.shake > 0 and self.state != "paused"
        c = self.canvas if shaking else self.screen
        w = self.world
        w.draw_background(c)
        th = w.sprite_theme
        self.dino.draw(c, th)
        bees = self.title_bees if self.state == "title" else self.bees
        for b in bees:
            b.draw(c, self.bee_art, th, w.time)
        w.draw_foreground(c)
        for x, y, vx, vy, life, maxl, col, size in self.particles:
            r = max(1, int(size * (life / maxl) ** 0.5))
            pygame.draw.circle(c, col, (int(x), int(y)), r)
        for img, x, y, life in self.floaters:
            img.set_alpha(int(255 * min(1.0, life * 2.5)))
            c.blit(img, img.get_rect(center=(int(x), int(y))))
            img.set_alpha(None)
        if self.args.hitboxes:
            self.draw_hitboxes(c)
        if self.flash > 0:
            self.red_flash.set_alpha(int(105 * self.flash))
            c.blit(self.red_flash, (0, 0))

        if shaking:
            amp = 9 * self.shake / 0.35
            ox = int(self.rng.uniform(-amp, amp))
            oy = int(self.rng.uniform(-amp, amp))
            self.screen.fill(THEMES[w.theme]["clear"])
            self.screen.blit(c, (ox, oy))

        if self.state == "title":
            self.draw_title()
        else:
            self.draw_hud()
            if self.banner > 0 and self.state == "play":
                self.draw_banner()
            if self.state == "paused":
                self.draw_pause()
            elif self.state == "gameover":
                self.draw_game_over()

    def draw_hitboxes(self, c):
        d = self.dino
        (mx, my), mr = d.mouth_circle()
        pygame.draw.circle(c, (255, 255, 0) if d.chomping else (255, 160, 0), (int(mx), int(my)), int(mr), 2)
        (hx, hy), hr = d.head_circle()
        pygame.draw.circle(c, (255, 80, 80), (int(hx), int(hy)), int(hr), 2)
        for (x, y), r in d.neck_circles() + d.body_hit_circles():
            pygame.draw.circle(c, (255, 60, 200), (int(x), int(y)), int(r), 1)
        for b in self.bees:
            if b.active:
                pygame.draw.circle(c, (60, 220, 255), (int(b.x), int(b.y)), int(b.radius), 1)

    def draw_hud(self):
        s = self.screen
        for i in range(MAX_HEARTS):
            img = self.heart_full if i < self.hearts else self.heart_empty
            y = 16
            if i == self.hearts - 1 and self.hearts == 1 and self.state == "play":
                y += int(2 * math.sin(self.world.time * 12))   # the last heart trembles
            s.blit(img, (20 + i * 46, y))
        ui.blit_text(s, f"{self.score:,}", 46, (18, 56), outline=2)
        if self.combo >= 2:
            mult = self.multiplier()
            col = GOLD if mult > 1 else CREAM
            label = f"Combo {self.combo}" + (f"  \u00d7{mult}" if mult > 1 else "")
            ui.blit_text(s, label, 26, (20, 110), col, outline=2)
        name = THEMES[theme_index_for_level(self.level)]["name"]
        ui.blit_text(s, f"Level {self.level}", 34, (WIDTH - 20, 8), anchor="topright", outline=2)
        ui.blit_text(s, name, 22, (WIDTH - 20, 48), (255, 236, 200), anchor="topright", outline=2)
        # progress towards the next level
        frac = self.eaten_this_level / BEES_PER_LEVEL
        bar = pygame.Rect(WIDTH - 180, 80, 160, 10)
        pygame.draw.rect(s, (20, 24, 40), bar.inflate(4, 4), border_radius=6)
        pygame.draw.rect(s, (90, 90, 110), bar, border_radius=5)
        if frac > 0:
            pygame.draw.rect(s, (255, 210, 70), (bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=5)
        ui.blit_text(s, f"Best {max(self.high_score, self.score):,}", 22, (WIDTH - 20, 94), (255, 236, 200),
                     anchor="topright", outline=2)
        if self.sound.muted:
            ui.blit_text(s, "Sound off (M)", 20, (WIDTH - 16, HEIGHT - 12), (230, 230, 240), anchor="bottomright")

    def draw_banner(self):
        t = 2.6 - self.banner
        a = min(1.0, t / 0.3, self.banner / 0.5)
        y = HEIGHT * 0.3 - 30 * (1 - min(1.0, t / 0.4)) ** 2
        img = ui.text(f"Level {self.level}", 84, GOLD, outline=4)
        sub = ui.text(THEMES[theme_index_for_level(self.level)]["name"], 40, CREAM, outline=3)
        for im, yy in ((img, y), (sub, y + 70)):
            im.set_alpha(int(255 * a))
            self.screen.blit(im, im.get_rect(center=(WIDTH // 2, int(yy))))
            im.set_alpha(None)

    def draw_title(self):
        s = self.screen
        t = self.world.time
        bob = math.sin(t * 2) * 4
        cx = 968
        ui.blit_text(s, "Dinosaur", 100, (cx - 70, 22 + bob), GOLD, anchor="midtop", outline=6)
        ui.blit_text(s, "vs Bees", 78, (cx + 120, 120 - bob), (255, 236, 120), anchor="midtop", outline=5)
        pw, ph = 540, 287
        px, py = cx - pw // 2, 230
        s.blit(self.title_panel, (px, py))
        if int(self.title_t / TITLE_PANEL_TIME) % 2 == 1 or self.args.show_top10:
            self.draw_top10(px, py, pw, ph)
        else:
            self.draw_how_to(px, py)
        pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 4))
        img = ui.text("Press Enter to start", 46, (255, 255, 255), outline=3)
        img.set_alpha(int(255 * pulse))
        s.blit(img, img.get_rect(center=(cx, py + ph + 46)))
        img.set_alpha(None)
        self.high_score = max(self.high_score, self.board.high_score())
        if self.high_score:
            ui.blit_text(s, f"Best {self.high_score:,}", 28, (cx, py + ph + 78), (255, 236, 200), anchor="midtop",
                         outline=2)
        ui.blit_text(s, "A remake of Dinosaur vs Bees by brixham99", 18, (WIDTH - 14, HEIGHT - 10),
                     (240, 240, 240), anchor="bottomright", outline=1)

    def draw_top10(self, px, py, pw, ph):
        s = self.screen
        cx = px + pw // 2
        ui.blit_text(s, "Top 10 Scores", 30, (cx, py + 10), GOLD, anchor="midtop")
        rows = self.board.top(TOP_N)
        if not rows:
            msg = {"loading": "Fetching the scores…", "offline": "Scores unavailable offline"}.get(
                self.board.status, "No scores yet – be the first!")
            ui.blit_text(s, msg, 24, (cx, py + ph // 2), CREAM, anchor="center")
            return
        for i, (name, score, country) in enumerate(rows):
            y = py + 52 + i * 23
            col = GOLD if i == 0 else CREAM
            ui.blit_text(s, f"{i + 1}.", 21, (px + 120, y), col, anchor="topright", shadow=False)
            flag = self.flags.get(country) if country else None
            if flag:
                s.blit(flag, (px + 134, y + 5))
            ui.blit_text(s, name, 21, (px + 172, y), col, shadow=False)
            ui.blit_text(s, f"{score:,}", 21, (px + pw - 120, y), col, anchor="topright", shadow=False)

    def draw_how_to(self, px, py):
        s = self.screen
        cx = px + 270
        ui.blit_text(s, "Eat the yellow bees. Dodge the angry red ones!", 25, (cx, py + 16), CREAM, anchor="midtop")
        lines = [
            ("Up / W", "raise the neck"),
            ("Down / S", "lower the neck"),
            ("Left / Right", "turn round"),
            ("Space", "chomp!"),
            ("P / Esc", "pause"),
            ("M", "sound on / off"),
        ]
        for i, (k, v) in enumerate(lines):
            y = py + 58 + i * 33
            ui.blit_text(s, k, 26, (px + 228, y), GOLD, anchor="topright")
            ui.blit_text(s, v, 26, (px + 250, y), CREAM)
        ui.blit_text(s, "Red bees bounce off his back: turn round!", 21, (cx, py + 58 + len(lines) * 33 + 2),
                     (200, 225, 255), anchor="midtop")

    def draw_pause(self):
        s = self.screen
        s.blit(self.dim, (0, 0))
        ui.blit_text(s, "Paused", 96, (WIDTH // 2, HEIGHT // 2 - 60), GOLD, anchor="center", outline=5)
        ui.blit_text(s, "Press P or Esc to carry on", 34, (WIDTH // 2, HEIGHT // 2 + 20), CREAM, anchor="center", outline=2)
        ui.blit_text(s, "M turns the sound on or off", 26, (WIDTH // 2, HEIGHT // 2 + 64), (220, 220, 235), anchor="center")

    def draw_game_over(self):
        s = self.screen
        a = min(1.0, self.over_timer / 0.6)
        self.dim.set_alpha(int(255 * a))
        s.blit(self.dim, (0, 0))
        self.dim.set_alpha(None)
        cy = HEIGHT // 2 - 40
        ui.blit_text(s, "Game Over", 104, (WIDTH // 2, cy - 120), (255, 120, 100), anchor="center", outline=6)
        ui.blit_text(s, f"Score {self.score:,}", 54, (WIDTH // 2, cy - 20), CREAM, anchor="center", outline=3)
        if self.new_high:
            pulse = 1.0 + 0.06 * math.sin(self.over_timer * 6)
            img = ui.text("New high score!", 44, GOLD, outline=3)
            img = pygame.transform.rotozoom(img, 0, pulse)
            s.blit(img, img.get_rect(center=(WIDTH // 2, cy + 45)))
        else:
            ui.blit_text(s, f"Best {self.high_score:,}", 36, (WIDTH // 2, cy + 45), (255, 236, 200), anchor="center", outline=2)
        ui.blit_text(s, f"Bees eaten {self.eaten}    Best combo {self.best_combo}    Level {self.level}", 28,
                     (WIDTH // 2, cy + 100), (230, 230, 240), anchor="center", outline=2)
        if self.entry_active:
            caret = "_" if int(self.over_timer * 2.5) % 2 == 0 else " "
            ui.blit_text(s, "Type your name for the Top 10:", 30, (WIDTH // 2, cy + 150), CREAM, anchor="center",
                         outline=2)
            ui.blit_text(s, (self.entry_name + caret) if self.entry_name or caret != " " else " ", 46,
                         (WIDTH // 2, cy + 200), GOLD, anchor="center", outline=3)
            ui.blit_text(s, "Enter to send  ·  Esc to skip", 24, (WIDTH // 2, cy + 245), (220, 220, 235),
                         anchor="center")
            return
        note = self.entry_status()
        if note:
            ui.blit_text(s, note, 26, (WIDTH // 2, cy + 135), (200, 225, 255), anchor="center", outline=2)
        if self.over_timer > 0.8:
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.over_timer * 4))
            img = ui.text("Press Enter to play again", 42, (255, 255, 255), outline=3)
            img.set_alpha(int(255 * pulse))
            s.blit(img, img.get_rect(center=(WIDTH // 2, cy + 175)))
            img.set_alpha(None)
            ui.blit_text(s, "Esc for the title screen", 24, (WIDTH // 2, cy + 220), (220, 220, 235), anchor="center")

    # ------------------------------------------------------------------ run
    def save_screenshot(self, path):
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        pygame.image.save(self.screen, path)
        print(f"screenshot saved: {path}")

    def run(self):
        shots = {}
        if self.args.shots:
            for item in self.args.shots.split(","):
                f, p = item.split(":", 1)
                shots[int(f)] = p
        running = True
        acc = 0.0
        last = time.perf_counter()
        while running:
            running = self.handle_events()
            if not running:
                break
            if self.headless or self.args.frames:
                steps = 1
            else:
                now = time.perf_counter()
                acc += min(0.1, now - last)
                last = now
                steps = 0
                while acc >= DT and steps < 4:
                    acc -= DT
                    steps += 1
            t0 = time.perf_counter()
            for _ in range(steps):
                self.update(DT)
            self.draw()
            self.frame_times.append((time.perf_counter() - t0) * 1000.0)
            pygame.display.flip()
            if self.frame in shots:
                self.save_screenshot(shots[self.frame])
            if self.args.frames and self.frame >= self.args.frames:
                break
            if not self.headless:
                self.clock.tick(FPS)
        if self.args.screenshot:
            self.save_screenshot(self.args.screenshot)
        if self.args.frames:
            ft = np.array(self.frame_times[30:] or [0])
            print(f"frames {self.frame}  frame time avg {ft.mean():.2f} ms  p95 {np.percentile(ft, 95):.2f} ms  "
                  f"max {ft.max():.2f} ms")
            print(f"stats {self.stats}  current state {self.state} level {self.level} score {self.score}")
        pygame.quit()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Dinosaur vs Bees - eat the bees, dodge the stingers.")
    p.add_argument("--seed", type=int, default=None, help="random seed for a repeatable run")
    p.add_argument("--screenshot", metavar="PATH", help="save a screenshot when the run ends")
    p.add_argument("--shots", metavar="F:PATH,...", help="save screenshots at the given frame numbers")
    p.add_argument("--frames", type=int, default=0, help="quit after N frames (runs flat out when headless)")
    p.add_argument("--autoplay", action="store_true", help="let the demo AI play")
    p.add_argument("--level", type=int, default=1, help="starting level (testing)")
    p.add_argument("--mute", action="store_true", help="start with the sound off")
    p.add_argument("--hitboxes", action="store_true", help="draw the collision shapes (F3 toggles)")
    p.add_argument("--highscore-file", metavar="PATH", help="where to keep the high score")
    p.add_argument("--scores-file", metavar="PATH", help="where to keep the Top 10 cache and unsent scores")
    p.add_argument("--offline", action="store_true", help="never touch the network (no Top 10 updates)")
    p.add_argument("--demo-scores", action="store_true",
                   help="debug: fill the Top 10 with sample names (shown only, never sent)")
    p.add_argument("--show-top10", action="store_true", help="debug: keep the Top 10 on the title screen")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    args.level = max(1, args.level)
    Game(args).run()


if __name__ == "__main__":
    main()

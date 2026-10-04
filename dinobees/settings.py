"""Global constants for Dinosaur vs Bees."""
import os

TITLE = "Dinosaur vs Bees"
WIDTH, HEIGHT = 1280, 720
FPS = 60
DT = 1.0 / FPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets")
FONT_PATH = os.path.join(ASSET_DIR, "fonts", "LilitaOne-Regular.ttf")
HIGHSCORE_FILE = os.path.join(ROOT, "highscore.json")

# Parallax speed factors relative to the ground
SKY_FACTOR = 0.03
SKY_DRIFT = 7.0          # px/s extra cloud drift
MOUNTAIN_FACTOR = 0.125
HILL_FACTOR = 0.33
GROUND_FACTOR = 1.0
FOREGROUND_FACTOR = 1.45

BASE_WALK_SPEED = 170.0  # ground px/s at level 1
WALK_SPEED_PER_LEVEL = 9.0
MAX_WALK_SPEED = 290.0

DINO_X = int(WIDTH * 0.27)   # body centre

MAX_HEARTS = 3
INVULNERABLE_TIME = 1.5
CHOMP_TIME = 0.25
CHOMP_COOLDOWN = 0.12
BEES_PER_LEVEL = 12

# Colours sampled from the body art
DINO_GREEN = (103, 187, 50)
DINO_GREEN_DARK = (62, 145, 40)
DINO_GREEN_LIGHT = (166, 214, 80)
DINO_SPOT_RIM = (86, 164, 44)
DINO_BELLY = (210, 224, 87)
DINO_BELLY_SHADE = (183, 203, 55)
DINO_OUTLINE = (4, 66, 6)
DINO_PLATE = (42, 128, 62)

WHITE = (255, 255, 255)
SHADOW = (20, 24, 40)

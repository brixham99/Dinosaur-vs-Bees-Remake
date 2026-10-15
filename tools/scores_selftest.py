"""Headless checks for the high score flow (no real network: dreamlo is faked).
Saves dvb_name_entry.png and dvb_score_sent.png into OUTDIR if given."""
import os, sys, json, tempfile, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
import game as G
from dinobees import scores
from dinobees.settings import DT

out = sys.argv[1] if len(sys.argv) > 1 else None
ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1

tmp = tempfile.mkdtemp()
# --- Leaderboard: offline keeps the score, online sends it with the country
calls = []
def offline_get(url):
    calls.append(url); raise OSError("offline")
board = scores.Leaderboard(online=True, path=os.path.join(tmp, "s.json"))
board._get = offline_get
scores.lookup_country = lambda: "GB"
board.submit("Nathan", 420)
for _ in range(50):
    if not board.busy: break
    time.sleep(0.05)
check(board.status == "offline", "offline status")
check(("Nathan", 420) in board.pending, "kept for later")
check(board.top()[0] == ("Nathan", 420, "GB"), "unsent score shows in the Top 10 with its flag")
check(json.load(open(os.path.join(tmp, "s.json")))["pending"] == [["Nathan", 420]], "saved to disk")
fake = {"dreamlo": {"leaderboard": {"entry": [{"name": "Nathan", "score": "420", "text": "GB"},
                                               {"name": "Rex", "score": "99", "text": "US"}]}}}
def online_get(url):
    calls.append(url)
    return "OK" if "/add/" in url else json.dumps(fake)
board._get = online_get
board.refresh()
for _ in range(100):
    if not board.busy: break
    time.sleep(0.05)
check(any(u.endswith("/add/Nathan/420/0/GB") for u in calls), "add URL carries the country code")
check(board.pending == [] and board.status == "online", "sent and online")
check(board.top() == [("Nathan", 420, "GB"), ("Rex", 99, "US")], "Top 10 parsed")
check(scores.clean_name("  Al!ce   Smith-Jones ") == "Alce Smi", "name cleaning")
check(scores.clean_country("gb\n") == "GB" and scores.clean_country("Error") == "", "country cleaning")

# --- in game: name entry after game over
args = G.parse_args(["--seed", "3", "--mute", "--offline", "--scores-file", os.path.join(tmp, "g.json"),
                     "--highscore-file", os.path.join(tmp, "hs.json")])
g = G.Game(args)
g.start_game()
g.score = 340
g.game_over()
check(g.entry_active, "name entry opens for a score")
for ch in "Rex!":
    pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=ch))
for _ in range(30):
    g.handle_events(); g.update(DT)
check(g.entry_name == "Rex", "typed name")
g.draw()
if out: pygame.image.save(g.screen, os.path.join(out, "dvb_name_entry.png"))
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r", scancode=0))
g.handle_events()
check(not g.entry_active and g.entry_note == "Rex", "submitted")
check(g.board.top()[0][:2] == ("Rex", 340), "score in the Top 10")
check(g.state == "gameover", "still on the game over screen (Enter does not restart straight away)")
for _ in range(80):
    g.update(DT)
g.draw()
if out: pygame.image.save(g.screen, os.path.join(out, "dvb_score_sent.png"))
check(g.entry_status() == "Saved as Rex", "status line")
print(f"scores self-test: {ok} checks passed")

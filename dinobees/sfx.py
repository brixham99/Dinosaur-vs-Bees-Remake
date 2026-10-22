"""Tiny sound effects synthesised with numpy at start-up."""
import numpy as np
import pygame

RATE = 44100


def _env(n, attack=0.005, release=None):
    t = np.arange(n) / RATE
    env = np.minimum(1.0, t / max(attack, 1e-4))
    if release is None:
        release = n / RATE
    env *= np.exp(-t / max(release / 4.0, 1e-4))
    return env


def _tone(freq, dur, wave="sine", vol=0.5, attack=0.005, release=None):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    if callable(freq):
        phase = np.cumsum(freq(t)) / RATE * 2 * np.pi
    else:
        phase = 2 * np.pi * freq * t
    if wave == "sine":
        w = np.sin(phase)
    elif wave == "tri":
        w = 2 / np.pi * np.arcsin(np.sin(phase))
    elif wave == "square":
        w = np.tanh(4 * np.sin(phase))
    else:  # saw
        w = 2 * ((phase / (2 * np.pi)) % 1.0) - 1
    return w * _env(n, attack, release) * vol


def _concat(*parts, gap=0.0):
    g = np.zeros(int(RATE * gap))
    out = []
    for p in parts:
        out += [p, g]
    return np.concatenate(out)


def _mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def synth_all():
    rng = np.random.RandomState(7)
    s = {}
    # chomp: a snappy click and a low thump
    n = int(RATE * 0.05)
    noise = rng.uniform(-1, 1, n) * _env(n, 0.001, 0.03) * 0.5
    thump = _tone(lambda t: 170 - 900 * t, 0.09, "sine", 0.6, 0.001, 0.08)
    s["chomp"] = _mix(noise, thump)
    # eat: a happy rising blip and a little chime
    blip = _tone(lambda t: 520 + 2600 * t, 0.12, "tri", 0.35, 0.002, 0.12)
    chime = np.concatenate([np.zeros(int(RATE * 0.06)), _tone(1568, 0.25, "sine", 0.18, 0.002, 0.25)])
    s["eat"] = _mix(blip, chime)
    # golden bee: sparkly arpeggio
    s["gold"] = _concat(*[_tone(f, 0.09, "tri", 0.3, 0.002, 0.12) for f in (988, 1319, 1568, 1976, 2637)])
    # sting: a nasty descending buzz
    buzz = _tone(lambda t: 330 - 400 * t + 25 * np.sin(2 * np.pi * 30 * t), 0.4, "saw", 0.28, 0.003, 0.4)
    n = int(RATE * 0.08)
    hit = rng.uniform(-1, 1, n) * _env(n, 0.001, 0.06) * 0.35
    s["sting"] = _mix(buzz, hit)
    # level up: bright arpeggio
    s["level"] = _concat(*[_tone(f, 0.11, "tri", 0.32, 0.003, 0.16) for f in (523, 659, 784, 1047)],
                         _tone(1319, 0.35, "tri", 0.3, 0.003, 0.4))
    # game over: sad descending notes
    s["gameover"] = _concat(*[_tone(f, 0.3, "tri", 0.34, 0.005, 0.32) for f in (392, 330, 262)],
                            _tone(196, 0.8, "tri", 0.34, 0.005, 0.9))
    s["start"] = _concat(_tone(659, 0.08, "tri", 0.3), _tone(988, 0.16, "tri", 0.3))
    # gentle buzz loop: 1 s with whole cycles so it loops seamlessly
    t = np.arange(RATE) / RATE
    hum = (2 * ((180 * t) % 1.0) - 1) * 0.5 + np.sin(2 * np.pi * 360 * t) * 0.3
    hum *= 0.6 + 0.4 * np.sin(2 * np.pi * 6 * t)
    s["buzz"] = hum * 0.12
    # bonk: a bee glancing off his armoured back, a hollow knock and a ting
    knock = _tone(lambda t: 260 - 500 * t, 0.12, "tri", 0.5, 0.001, 0.1)
    ting = _tone(1320, 0.18, "sine", 0.18, 0.002, 0.16)
    s["bonk"] = _mix(knock, ting)
    return s


class Sound:
    def __init__(self, enabled=True):
        self.ok = False
        self.muted = False
        self.sounds = {}
        self.buzz_channel = None
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            freq, size, channels = pygame.mixer.get_init()
            for name, wave in synth_all().items():
                if freq != RATE:
                    idx = np.linspace(0, len(wave) - 1, int(len(wave) * freq / RATE))
                    wave = np.interp(idx, np.arange(len(wave)), wave)
                data = (np.clip(wave, -1, 1) * 32767).astype(np.int16)
                if channels > 1:
                    data = np.repeat(data[:, None], channels, axis=1)
                self.sounds[name] = pygame.sndarray.make_sound(np.ascontiguousarray(data))
            pygame.mixer.set_num_channels(16)
            self.ok = True
        except Exception as exc:  # no audio device or mixer: run silently
            print(f"Sound disabled ({exc})")
            self.ok = False

    def play(self, name, volume=1.0):
        if not self.ok or self.muted or name not in self.sounds:
            return
        snd = self.sounds[name]
        snd.set_volume(volume)
        snd.play()

    def set_buzz(self, level):
        """level 0..1 - how loud the background buzz of nearby bees is."""
        if not self.ok:
            return
        if self.muted:
            level = 0.0
        if self.buzz_channel is None and level > 0:
            self.buzz_channel = self.sounds["buzz"].play(loops=-1)
        if self.buzz_channel is not None:
            self.buzz_channel.set_volume(max(0.0, min(1.0, level)) * 0.5)

    def start_music(self, path, volume=0.4):
        """Loop the in-game music from the top (gameplay only; the title is silent)."""
        self.music_path = path
        self.music_on = True
        self.music_held = False
        if not self.ok:
            return False
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=-1)
            if self.muted:
                pygame.mixer.music.pause()
            return True
        except Exception as exc:
            print(f"Music disabled ({exc})")
            self.music_on = False
            return False

    def stop_music(self, fade_ms=0):
        """Stop the music, fading it out over fade_ms if given."""
        self.music_on = False
        self.music_held = False
        if not self.ok:
            return
        try:
            if fade_ms > 0 and pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(fade_ms)
            else:
                pygame.mixer.music.stop()
        except Exception:
            pass

    def hold_music(self, held):
        """Pause (held=True) or resume the music, e.g. for the pause screen."""
        self.music_held = held
        if not self.ok or not getattr(self, "music_on", False):
            return
        try:
            if held or self.muted:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
        except Exception:
            pass

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            if self.muted:
                pygame.mixer.stop()
                self.buzz_channel = None
            try:
                if self.muted or getattr(self, "music_held", False):
                    pygame.mixer.music.pause()
                elif getattr(self, "music_on", False):
                    pygame.mixer.music.unpause()
            except Exception:
                pass
        return self.muted

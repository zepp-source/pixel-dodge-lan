import math
import random
import time

import pygame


class AudioSystem:
    def __init__(self) -> None:
        self.enabled = False
        self.music_channel = None
        self.pattern = []
        self.step = 0
        self.last_tick = 0.0
        self.sfx_hit = None
        self.sfx_spawn = None
        self.sfx_score = None

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
                self.enabled = True
            except Exception:
                self.enabled = False

        if self.enabled:
            self._build_sfx()
            self._start_music()

    def _tone(self, frequency: float, duration: float = 0.08, volume: float = 0.18) -> bytes:
        sample_rate = 44100
        frames = int(sample_rate * duration)
        data = []
        for i in range(frames):
            t = i / sample_rate
            wave = math.sin(2 * math.pi * frequency * t)
            wave += 0.35 * math.sin(2 * math.pi * (frequency * 0.5) * t)
            value = max(-1.0, min(1.0, wave)) * 32767 * volume
            data.append(int(value))
            data.append(int(value))
        return (pygame.mixer.Sound(buffer=bytes([0])) if False else b"").__class__

    def _build_sfx(self) -> None:
        self.sfx_spawn = self._make_sound(660, 0.07, 0.18)
        self.sfx_hit = self._make_sound(180, 0.18, 0.28)
        self.sfx_score = self._make_sound(440, 0.10, 0.22)

    def _make_sound(self, frequency: float, duration: float, volume: float):
        sample_rate = 44100
        frames = int(sample_rate * duration)
        raw = bytearray()
        for i in range(frames):
            t = i / sample_rate
            wave = math.sin(2 * math.pi * frequency * t)
            wave += 0.45 * math.sin(2 * math.pi * frequency * 2 * t)
            sample = int(max(-1.0, min(1.0, wave)) * 32767 * volume)
            raw.extend(int(sample).to_bytes(2, byteorder="little", signed=True))
            raw.extend(int(sample).to_bytes(2, byteorder="little", signed=True))
        return pygame.mixer.Sound(buffer=raw)

    def _start_music(self):
        self.pattern = [220, 277, 330, 392, 330, 277, 220, 196]
        self.step = 0
        self.last_tick = time.monotonic()
        self.music_channel = pygame.mixer.Channel(0)
        self.music_channel.set_volume(0.12)
        self._tick_music()

    def _tick_music(self):
        if not self.enabled or self.music_channel is None:
            return
        if self.step >= len(self.pattern):
            self.step = 0
        f = self.pattern[self.step]
        self.music_channel.play(self._make_sound(f, 0.18, 0.08), loops=0)
        self.step += 1

    def update(self):
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self.last_tick >= 0.18:
            self.last_tick = now
            self._tick_music()

    def play_spawn(self):
        if self.enabled and self.sfx_spawn:
            self.sfx_spawn.play()

    def play_hit(self):
        if self.enabled and self.sfx_hit:
            self.sfx_hit.play()

    def play_score(self):
        if self.enabled and self.sfx_score:
            self.sfx_score.play()


if __name__ == "__main__":
    pygame.init()
    audio = AudioSystem()
    print("audio ready")

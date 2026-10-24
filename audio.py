"""音频：程序化合成的音效与循环背景音乐。

没有音频设备时全部自动降级为静音，不会崩溃。
"""
from __future__ import annotations

import math
import random
from array import array

import pygame

SAMPLE_RATE = 22050
_BUFFER = 512


def note(name: str, octave: int) -> float:
    """音名 -> 频率，例如 note('A', 4) == 440。"""
    table = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    semis = table[name] + (octave - 4) * 12 - 9
    return 440.0 * (2.0 ** (semis / 12.0))


def _square(t: float, f: float, duty: float = 0.5) -> float:
    return 1.0 if (t * f) % 1.0 < duty else -1.0


def _tri(t: float, f: float) -> float:
    p = (t * f) % 1.0
    return 4.0 * abs(p - 0.5) - 1.0


def _noise(rng: random.Random) -> float:
    return rng.uniform(-1.0, 1.0)


def _render(duration: float, gen) -> array:
    n = int(SAMPLE_RATE * duration)
    buf = array("h")
    for i in range(n):
        v = gen(i / SAMPLE_RATE, i, n)
        v = max(-1.0, min(1.0, v))
        buf.append(int(v * 26000))
    return buf


def _tone(freq: float, duration: float, vol: float = 0.5, wave: str = "square",
          duty: float = 0.5, decay: float = 4.0) -> array:
    def gen(t: float, _i: int, n: int) -> float:
        env = math.exp(-decay * t / max(duration, 1e-6))
        w = _square(t, freq, duty) if wave == "square" else _tri(t, freq)
        return w * vol * env
    return _render(duration, gen)


def _sweep(f0: float, f1: float, duration: float, vol: float = 0.5,
           wave: str = "square", duty: float = 0.5) -> array:
    def gen(t: float, _i: int, n: int) -> float:
        p = t / max(duration, 1e-6)
        f = f0 + (f1 - f0) * p
        env = (1.0 - p) ** 1.4
        w = _square(t, f, duty) if wave == "square" else _tri(t, f)
        return w * vol * env
    return _render(duration, gen)


def _silence(duration: float) -> array:
    return array("h", bytes(int(SAMPLE_RATE * duration) * 2))


def _sequence(chunks: list[array]) -> array:
    out = array("h")
    for c in chunks:
        out.extend(c)
    return out


def _mix(a: array, b: array, gain: float = 1.0) -> array:
    n = max(len(a), len(b))
    out = array("h", bytes(n * 2))
    for i in range(n):
        va = a[i] if i < len(a) else 0
        vb = int((b[i] if i < len(b) else 0) * gain)
        out[i] = max(-32000, min(32000, va + vb))
    return out


def _sound_from_buffer(buf: array) -> pygame.mixer.Sound:
    """按当前混音器格式（有符号 16 位）直接构造 Sound。"""
    return pygame.mixer.Sound(buffer=buf.tobytes())


# --------------------------------------------------------------------------
# 音效定义
# --------------------------------------------------------------------------
def _sfx_jump() -> array:
    return _sweep(300, 620, 0.13, vol=0.40, duty=0.5)


def _sfx_double_jump() -> array:
    return _sweep(420, 820, 0.12, vol=0.36, duty=0.25)


def _sfx_coin() -> array:
    n1 = note("E", 6)
    n2 = note("B", 6)
    return _sequence([
        _tone(n1, 0.045, vol=0.32, duty=0.25, decay=6),
        _tone(n2, 0.10, vol=0.32, duty=0.25, decay=7),
    ])


def _sfx_gem() -> array:
    return _sequence([
        _tone(note("C", 6), 0.05, vol=0.30, wave="tri", decay=6),
        _tone(note("E", 6), 0.05, vol=0.30, wave="tri", decay=6),
        _tone(note("G", 6), 0.14, vol=0.30, wave="tri", decay=6),
    ])


def _sfx_hurt() -> array:
    rng = random.Random(7)

    def gen(t: float, i: int, n: int) -> float:
        p = i / n
        env = (1.0 - p) ** 2
        return (_noise(rng) * 0.5 + _square(t, 220 - 140 * p, 0.35) * 0.5) * 0.5 * env
    return _render(0.26, gen)


def _sfx_stomp() -> array:
    rng = random.Random(11)

    def gen(t: float, i: int, n: int) -> float:
        p = i / n
        env = math.exp(-9 * p)
        return (_noise(rng) * 0.55 + _tri(t, 180 - 120 * p) * 0.45) * 0.45 * env
    return _render(0.14, gen)


def _sfx_spring() -> array:
    return _sweep(260, 900, 0.18, vol=0.36, duty=0.35)


def _sfx_door() -> array:
    return _sequence([
        _tone(note("G", 4), 0.09, vol=0.32, duty=0.25, decay=5),
        _tone(note("C", 5), 0.09, vol=0.32, duty=0.25, decay=5),
        _tone(note("E", 5), 0.09, vol=0.32, duty=0.25, decay=5),
        _tone(note("G", 5), 0.22, vol=0.34, duty=0.25, decay=4),
    ])


def _sfx_win() -> array:
    seq = [("C", 5), ("E", 5), ("G", 5), ("C", 6), ("E", 6), ("G", 6)]
    chunks = [_sequence([_tone(note(n, o), 0.1, vol=0.30, duty=0.25, decay=5)])
              for n, o in seq]
    tail = _tone(note("C", 6), 0.5, vol=0.32, wave="tri", decay=3)
    return _sequence(chunks + [tail])


def _sfx_die() -> array:
    chunks = []
    for i, (n, o) in enumerate([("C", 5), ("A", 4), ("F", 4), ("D", 4)]):
        chunks.append(_tone(note(n, o), 0.16, vol=0.32, duty=0.5, decay=3))
    chunks.append(_sweep(220, 70, 0.5, vol=0.34, duty=0.5))
    return _sequence(chunks)


def _sfx_select() -> array:
    return _tone(note("A", 5), 0.06, vol=0.28, duty=0.25, decay=8)


def _sfx_pause() -> array:
    return _tone(note("D", 5), 0.09, vol=0.26, duty=0.5, decay=6)


# --------------------------------------------------------------------------
# 背景音乐（8 小节芯片音乐，无缝循环）
# --------------------------------------------------------------------------
def _track(theme: str) -> array:
    if theme == "calm":
        prog = [("C", 3), ("A", 2), ("F", 2), ("G", 2)]
        arp = [
            ["C", "E", "G", "E"], ["A", "C", "E", "C"],
            ["F", "A", "C", "A"], ["G", "B", "D", "B"],
        ]
        bpm = 96
    else:  # adventure
        prog = [("C", 3), ("G", 2), ("A", 2), ("F", 2)]
        arp = [
            ["C", "E", "G", "C"], ["G", "B", "D", "G"],
            ["A", "C", "E", "A"], ["F", "A", "C", "F"],
        ]
        bpm = 112

    beat = 60.0 / bpm
    chunks: list[array] = []
    for bar in range(4):
        root_name, root_oct = prog[bar]
        # 贝斯：每小节两下
        for half in range(2):
            bass = _tone(note(root_name, root_oct), beat * 0.9, vol=0.30,
                         wave="tri", decay=4)
            chunks.append(bass)
            chunks.append(_silence(beat * 0.1))
        # 琶音：8 个八分音符
        for k in range(8):
            nm = arp[bar][k % 4]
            oct_shift = 1 if k % 4 == 2 else 0
            mel = _tone(note(nm, 5 + oct_shift), beat * 0.44, vol=0.16,
                        duty=0.125, decay=6)
            chunks.append(mel)
            chunks.append(_silence(beat * 0.06))
    return _sequence(chunks)


class Audio:
    """封装所有音频；任何一步失败都会静默降级。"""

    def __init__(self, enabled: bool = True) -> None:
        self.ok = False
        self.muted = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.tracks: dict[str, pygame.mixer.Sound] = {}
        self._music_channel: pygame.mixer.Channel | None = None
        self._current_track: str | None = None
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, _BUFFER)
                pygame.mixer.init(SAMPLE_RATE, -16, 1, _BUFFER)
            pygame.mixer.set_num_channels(24)
        except Exception:
            return

        try:
            raw = {
                "jump": _sfx_jump(),
                "double_jump": _sfx_double_jump(),
                "coin": _sfx_coin(),
                "gem": _sfx_gem(),
                "hurt": _sfx_hurt(),
                "stomp": _sfx_stomp(),
                "spring": _sfx_spring(),
                "door": _sfx_door(),
                "win": _sfx_win(),
                "die": _sfx_die(),
                "select": _sfx_select(),
                "pause": _sfx_pause(),
            }
            for k, buf in raw.items():
                self.sounds[k] = _sound_from_buffer(buf)
            for theme in ("adventure", "calm"):
                self.tracks[theme] = _sound_from_buffer(_track(theme))
            self.ok = True
        except Exception:
            self.sounds.clear()
            self.tracks.clear()
            self.ok = False
            return

        try:
            self._music_channel = pygame.mixer.Channel(0)
            pygame.mixer.set_reserved(1)
            for s in self.tracks.values():
                s.set_volume(0.55)
            for k, s in self.sounds.items():
                s.set_volume(0.85 if k in ("coin", "jump", "stomp") else 1.0)
        except Exception:
            self._music_channel = None

    # -- 接口 -------------------------------------------------------------
    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.ok or self.muted:
            return
        s = self.sounds.get(name)
        if s is None:
            return
        try:
            ch = pygame.mixer.find_channel(True)
            if ch is not None and ch is not self._music_channel:
                ch.set_volume(volume)
                ch.play(s)
        except Exception:
            pass

    def music(self, theme: str) -> None:
        if not self.ok or self._music_channel is None:
            return
        if self._current_track == theme and self._music_channel.get_busy():
            return
        self._current_track = theme
        s = self.tracks.get(theme)
        try:
            if self.muted:
                self._music_channel.stop()
                return
            self._music_channel.stop()
            self._music_channel.play(s, loops=-1)
        except Exception:
            pass

    def stop_music(self) -> None:
        if self.ok and self._music_channel is not None:
            try:
                self._music_channel.stop()
            except Exception:
                pass
        self._current_track = None

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted:
            try:
                if self._music_channel is not None:
                    self._music_channel.stop()
            except Exception:
                pass
            self._current_track = None
        return self.muted

"""Laptop alarm: loud generated alarm sounds through the speaker.

winsound.Beep plays a soft pure tone. Instead, the PATTERNS from base.py are
rendered once into WAV files at full scale with a harsh square-like waveform
around 3 kHz (where human hearing is most sensitive). CRITICAL alternates two
pitches like a siren. Sounds loop asynchronously, so a level change switches the
sound instantly. Loudness is still limited by the system volume: turn it up."""
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

from ..utils import Level
from .base import ARMED, PATTERNS, Alarm

RATE = 44100
AMPLITUDE = 0.95                       # of full scale
TONES = {Level.WARNING: (3000,), Level.CRITICAL: (2900, 3500)}  # Hz; several = siren


def _tone(freq, seconds):
    """Square-like wave (sine + odd harmonics, soft-clipped): far louder to the ear than a pure sine."""
    n = int(RATE * seconds)
    ramp = int(RATE * 0.003)           # 3 ms fade in/out: no clicks
    out = []
    for i in range(n):
        t = i / RATE
        x = sum(math.sin(2 * math.pi * k * freq * t) / k for k in (1, 3, 5))
        x = math.tanh(2.5 * x)
        env = min(1.0, i / ramp, (n - 1 - i) / ramp) if ramp else 1.0
        out.append(AMPLITUDE * env * x)
    return out


def render(pattern, freqs):
    samples, pulse = [], 0
    for on, seconds in pattern:
        if on:
            samples += _tone(freqs[pulse % len(freqs)], seconds)
            pulse += 1
        else:
            samples += [0.0] * int(RATE * seconds)
    return samples


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


class SpeakerAlarm(Alarm):
    def __init__(self):
        self.windows = sys.platform == "win32"
        self.files = {}
        if self.windows:
            folder = Path(tempfile.gettempdir()) / "drowsy_alarm"
            folder.mkdir(exist_ok=True)
            # CRITICAL pattern repeated so the siren alternates pitch across the loop.
            sounds = {Level.WARNING: render(PATTERNS[Level.WARNING], TONES[Level.WARNING]),
                      Level.CRITICAL: render(PATTERNS[Level.CRITICAL] * 2, TONES[Level.CRITICAL]),
                      "armed": render(ARMED, (3000,))}
            for key, samples in sounds.items():
                path = folder / f"{getattr(key, 'name', key).lower()}.wav"
                write_wav(path, samples)
                self.files[key] = str(path)
        super().__init__()

    def set_level(self, level, reasons=()):
        changed = level != self.level
        super().set_level(level, reasons)
        if changed and self.windows:
            import winsound
            if level in self.files:
                winsound.PlaySound(self.files[level], winsound.SND_FILENAME | winsound.SND_ASYNC
                                   | winsound.SND_LOOP | winsound.SND_NODEFAULT)
            else:
                winsound.PlaySound(None, 0)  # stop

    def beep_armed(self):
        if self.windows:
            import winsound
            winsound.PlaySound(self.files["armed"], winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        else:
            super().beep_armed()

    def _sound(self, on, seconds):
        # Windows: the looping WAV does the work, the pattern thread only waits.
        if on and not self.windows:
            sys.stdout.write("\a")
            sys.stdout.flush()
        self._wait(seconds)

    def close(self):
        super().close()
        if self.windows:
            import winsound
            winsound.PlaySound(None, 0)

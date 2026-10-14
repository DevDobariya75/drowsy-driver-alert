"""Alarm interface. Every implementation plays the same patterns:

  OK        silent
  WARNING   3 fast beeps, short pause (repeats while the warning lasts)
  CRITICAL  rapid pulsing alarm (5 pulses / s) until the level drops;
            pulsing grabs attention better than a steady tone

Patterns run in a background thread so the alarm never slows the vision loop."""
import logging
import threading
from abc import ABC, abstractmethod

from ..utils import Level

log = logging.getLogger("alarm")

# (sound_on, seconds) steps, looped while the level is active.
PATTERNS = {
    Level.WARNING: [(True, 0.12), (False, 0.06), (True, 0.12), (False, 0.06), (True, 0.12), (False, 0.5)],
    Level.CRITICAL: [(True, 0.15), (False, 0.05)],
}
ARMED = [(True, 0.15), (False, 0.08), (True, 0.15)]


class Alarm(ABC):
    def __init__(self):
        self.level = Level.OK
        self._changed = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @abstractmethod
    def _sound(self, on: bool, seconds: float):
        """Turn the sound on/off for `seconds`. Should return early if the level changes."""

    def _wait(self, seconds: float) -> bool:
        """Sleep up to `seconds`; returns True if interrupted by a level change."""
        return self._changed.wait(seconds)

    def set_level(self, level: Level, reasons=()):
        if level != self.level:
            log.info("Alarm %s -> %s %s", self.level.name, level.name, ", ".join(reasons))
            self.level = level
            self._changed.set()

    def beep_armed(self):
        """Two short beeps at startup: system is armed."""
        for on, seconds in ARMED:
            self._sound(on, seconds)
        self._sound(False, 0.0)

    def _run(self):
        while not self._stop:
            self._changed.clear()
            pattern = PATTERNS.get(self.level)
            if not pattern:
                self._sound(False, 0.0)
                self._changed.wait()
                continue
            for on, seconds in pattern:
                self._sound(on, seconds)
                if self._changed.is_set() or self._stop:
                    break

    def close(self):
        self._stop = True
        self._changed.set()
        self._thread.join(timeout=2)
        self._sound(False, 0.0)

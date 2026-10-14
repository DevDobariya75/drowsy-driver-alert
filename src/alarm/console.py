"""Silent alarm that only records level changes (used by automated tests)."""
from ..utils import Level
from .base import Alarm


class ConsoleAlarm(Alarm):
    def __init__(self):
        self.history = []  # (level, reasons) on every change
        super().__init__()

    def set_level(self, level: Level, reasons=()):
        if level != self.level:
            self.history.append((level, tuple(reasons)))
        super().set_level(level, reasons)

    def _sound(self, on, seconds):
        self._wait(seconds)

"""Small shared helpers: alert levels, EMA filter, timers, FPS counter, logging."""
import logging
import time
from collections import deque
from enum import IntEnum


class Level(IntEnum):
    OK = 0
    WARNING = 1
    CRITICAL = 2


class EMA:
    """Exponential moving average: value = alpha * new + (1 - alpha) * old."""

    def __init__(self, alpha: float):
        self.alpha = alpha
        self.value = None

    def update(self, x):
        if x is None:
            return self.value
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


class ConditionTimer:
    """Tracks how long a boolean condition has been continuously true."""

    def __init__(self):
        self.since = None

    def update(self, condition: bool, t: float) -> float:
        if condition:
            if self.since is None:
                self.since = t
            return t - self.since
        self.since = None
        return 0.0

    def duration(self, t: float) -> float:
        return 0.0 if self.since is None else t - self.since


class FPSCounter:
    def __init__(self, window: int = 30):
        self.times = deque(maxlen=window)

    def tick(self, t: float | None = None) -> float:
        self.times.append(time.perf_counter() if t is None else t)
        return self.fps

    @property
    def fps(self) -> float:
        if len(self.times) < 2:
            return 0.0
        span = self.times[-1] - self.times[0]
        return (len(self.times) - 1) / span if span > 0 else 0.0


class StageTimer:
    """Accumulates per-stage processing time (ms) to find bottlenecks."""

    def __init__(self):
        self.totals = {}
        self.frames = 0
        self._t = None

    def start(self):
        self._t = time.perf_counter()

    def lap(self, name: str):
        now = time.perf_counter()
        self.totals[name] = self.totals.get(name, 0.0) + (now - self._t) * 1000
        self._t = now

    def end_frame(self):
        self.frames += 1

    def averages(self) -> dict:
        n = max(self.frames, 1)
        return {k: v / n for k, v in self.totals.items()}

    def reset(self):
        self.totals.clear()
        self.frames = 0


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

"""Per-driver calibration: learns the driver's normal open-eye EAR (per eye),
head pose, and checks whether the eye model is trustworthy for this driver.

Run while the driver looks straight ahead with eyes open. Using the driver's
own baseline handles different eye shapes, spectacles and the current
lighting far better than a fixed threshold."""
from dataclasses import dataclass

import numpy as np


@dataclass
class Baseline:
    ear_left: float
    ear_right: float
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    brightness: float = 120.0
    model_ok: bool = True        # False: eye model disagrees with open eyes -> don't use it
    model_open_p: float | None = None

    @property
    def ear(self) -> float:
        return (self.ear_left + self.ear_right) / 2


def _open_median(values):
    v = np.asarray(values, dtype=np.float64)
    # Blinks during calibration pull EAR down; ignore clearly-closed samples.
    keep = v[v > 0.7 * np.median(v)]
    return float(np.median(keep if keep.size else v))


class Calibrator:
    def __init__(self, seconds=10.0, min_samples=30, model_max_open_p=0.35):
        self.seconds = seconds
        self.min_samples = min_samples
        self.model_max_open_p = model_max_open_p
        self.reset()

    def reset(self):
        self.start_t = None
        self.samples = []   # (ear_l, ear_r, pitch, yaw, roll, brightness)
        self.model_p = []   # P(closed) of open eyes

    def add(self, t, ear_left, ear_right, pitch, yaw, roll, brightness, p_closed=None):
        """Feed one frame (face visible). Returns a Baseline when finished, else None."""
        if self.start_t is None:
            self.start_t = t
        self.samples.append((ear_left, ear_right, pitch, yaw, roll, brightness))
        if p_closed is not None:
            self.model_p.append(p_closed)
        if t - self.start_t >= self.seconds and len(self.samples) >= self.min_samples:
            return self.finish()
        return None

    def progress(self, t) -> float:
        if self.start_t is None:
            return 0.0
        return min(1.0, (t - self.start_t) / self.seconds)

    def finish(self) -> Baseline:
        d = np.array(self.samples, dtype=np.float64)
        pitch, yaw, roll, brightness = (float(np.median(d[:, i])) for i in range(2, 6))
        b = Baseline(_open_median(d[:, 0]), _open_median(d[:, 1]), pitch, yaw, roll, brightness)
        if self.model_p:
            # Median over the frames: blinks are a minority and don't move it.
            b.model_open_p = float(np.median(self.model_p))
            b.model_ok = b.model_open_p <= self.model_max_open_p
        return b

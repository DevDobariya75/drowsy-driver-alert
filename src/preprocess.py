"""Light-adaptive preprocessing so detection works from dim cabins to direct sun.

1. Measure frame brightness (smoothed so the correction doesn't flicker).
2. Pick a mode with hysteresis:
     dark   -> denoise FIRST, then gamma brighten + gentle CLAHE
               (brightening first amplifies sensor noise; tests showed face
               detection at 5-7% brightness went from 0% to ~100% of frames)
     normal -> CLAHE only (fixes shadows / uneven light)
     bright -> gamma darken  + CLAHE
CLAHE runs on the L channel of LAB, boosting local contrast around the eyes
without shifting colours. Gamma uses a precomputed lookup table (very cheap)."""
import cv2
import numpy as np

from .utils import EMA

DARK, NORMAL, BRIGHT = "dark", "normal", "bright"


def gamma_lut(gamma: float):
    x = np.arange(256, dtype=np.float32) / 255.0
    return np.clip((x ** gamma) * 255.0, 0, 255).astype(np.uint8)


class LightNormalizer:
    def __init__(self, enabled=True, dark_below=60, bright_above=180, hysteresis=8,
                 gamma_dark=0.5, gamma_bright=1.5, clahe_clip=2.0, clahe_clip_dark=1.0,
                 clahe_grid=8, dark_blur=5, brightness_ema_alpha=0.1, very_dark_below=25, **_):
        self.enabled = enabled
        self.dark_below = dark_below
        self.bright_above = bright_above
        self.hysteresis = hysteresis
        self.very_dark_below = very_dark_below
        self.lut_dark = gamma_lut(gamma_dark)
        self.lut_bright = gamma_lut(gamma_bright)
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(clahe_grid, clahe_grid))
        self.clahe_dark = cv2.createCLAHE(clipLimit=clahe_clip_dark, tileGridSize=(clahe_grid, clahe_grid))
        self.dark_blur = dark_blur
        self.brightness = EMA(brightness_ema_alpha)
        self.mode = NORMAL

    @staticmethod
    def measure(frame) -> float:
        # Subsample 4x in each direction: same mean, 16x less work.
        return float(cv2.cvtColor(frame[::4, ::4], cv2.COLOR_BGR2GRAY).mean())

    def _pick_mode(self, b: float) -> str:
        h = self.hysteresis
        if self.mode == DARK:
            return DARK if b < self.dark_below + h else (BRIGHT if b > self.bright_above else NORMAL)
        if self.mode == BRIGHT:
            return BRIGHT if b > self.bright_above - h else (DARK if b < self.dark_below else NORMAL)
        if b < self.dark_below - h:
            return DARK
        if b > self.bright_above + h:
            return BRIGHT
        return NORMAL

    @property
    def very_dark(self) -> bool:
        return self.brightness.value is not None and self.brightness.value < self.very_dark_below

    def process(self, frame):
        """Return (corrected_frame, info dict)."""
        raw = self.measure(frame)
        b = self.brightness.update(raw)
        self.mode = self._pick_mode(b)
        info = {"brightness": b, "raw_brightness": raw, "light_mode": self.mode}
        if not self.enabled:
            return frame, info

        clahe = self.clahe
        if self.mode == DARK:
            if self.dark_blur:
                frame = cv2.GaussianBlur(frame, (self.dark_blur, self.dark_blur), 0)
            frame = cv2.LUT(frame, self.lut_dark)
            clahe = self.clahe_dark
        elif self.mode == BRIGHT:
            frame = cv2.LUT(frame, self.lut_bright)

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), info

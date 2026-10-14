"""Detects lens reflections (glare) over each eye.

Reflections on spectacles cover the eye with near-white pixels. Then neither
the eye landmarks (EAR) nor the eye model can be trusted for that eye. The
natural catch-light in a pupil is tiny; lens glare covers a much larger part of
the eye, so we measure the fraction of saturated pixels inside the eye box.
Computed on the ORIGINAL frame, before light correction changes the highlights."""
import cv2
import numpy as np

from .metrics import LEFT_EYE, RIGHT_EYE

# Wider eye outline (MediaPipe) so the box covers the whole eye opening.
EYE_OUTLINE = {
    "left": LEFT_EYE + [384, 386, 388, 466, 390, 374, 381, 382, 398],
    "right": RIGHT_EYE + [161, 159, 157, 173, 246, 7, 145, 163, 154],
}


def glare_fraction(gray, pts, idx, pad=0.3, min_level=225, above_median=60, max_level=245):
    """Fraction (0..1) of very bright pixels in the box around one eye."""
    p = pts[idx]
    x0, y0 = p.min(axis=0)
    x1, y1 = p.max(axis=0)
    px, py = (x1 - x0) * pad, max((y1 - y0) * pad, (x1 - x0) * 0.15)
    h, w = gray.shape[:2]
    x0, x1 = int(max(0, x0 - px)), int(min(w, x1 + px + 1))
    y0, y1 = int(max(0, y0 - py)), int(min(h, y1 + py + 1))
    box = gray[y0:y1, x0:x1]
    if box.size < 20:
        return 0.0
    # "Bright" = well above this eye's typical brightness, but capped: a large reflection
    # raises the median itself and would otherwise push the level above 255.
    level = min(max(min_level, float(np.median(box)) + above_median), max_level)
    return float((box >= level).mean())


def eye_glare(frame, pts, threshold=0.06):
    """(left_has_glare, right_has_glare, left_fraction, right_fraction)."""
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    fl = glare_fraction(gray, pts, EYE_OUTLINE["left"])
    fr = glare_fraction(gray, pts, EYE_OUTLINE["right"])
    return fl >= threshold, fr >= threshold, fl, fr

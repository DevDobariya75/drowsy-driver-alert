"""Drowsiness measurements computed from face landmarks.

All durations use timestamps (not frame counts), so results are the same at
30 FPS on a laptop and 15 FPS on a Raspberry Pi."""
from collections import deque

import numpy as np

# MediaPipe Face Mesh indices, ordered p1..p6 for the EAR formula.
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
MOUTH = [13, 14, 78, 308]  # upper lip, lower lip, left corner, right corner


def _dist(a, b) -> float:
    return float(np.linalg.norm(a - b))


def eye_aspect_ratio(pts, idx) -> float:
    """EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)."""
    p1, p2, p3, p4, p5, p6 = (pts[i] for i in idx)
    width = _dist(p1, p4)
    if width < 1e-6:
        return 0.0
    return (_dist(p2, p6) + _dist(p3, p5)) / (2.0 * width)


def eye_ears(pts):
    """(left EAR, right EAR)."""
    return eye_aspect_ratio(pts, LEFT_EYE), eye_aspect_ratio(pts, RIGHT_EYE)


def average_ear(pts) -> float:
    return sum(eye_ears(pts)) / 2.0


class EyeClosureDetector:
    """Decides open / closed robustly, scoring each eye against its own calibrated baseline.

    Per eye:  ratio = EAR / baseline EAR   (1.0 = normally open)
              ear_score = how closed, 0 (open) .. 1 (fully closed)
              score = ear_score, or blended with the eye model's P(closed) if available
    Closed-ness = the LESS closed of the two eyes, so a landmark glitch on one
    eye cannot fake a closure; real closures close both. If a lens reflection
    covers exactly one eye, that eye is ignored and the clear eye decides, so
    the glare can neither fake a closure nor hide one.
    A 3-frame median removes single-frame glitches without stretching blinks
    (an EMA would stretch them). Hysteresis (separate close / reopen levels)
    stops flicker around the threshold. Looking down naturally lowers the
    eyelids, so the close level is raised as the head pitches down."""

    def __init__(self, open_ref=0.85, closed_ref=0.35, close_score=0.6, open_score=0.4,
                 look_down_start=5.0, look_down_full=20.0, look_down_extra=0.15,
                 model_weight=0.4, median_frames=3):
        self.open_ref = open_ref
        self.closed_ref = closed_ref
        self.close_score = close_score
        self.open_score = open_score
        self.look_down_start = look_down_start
        self.look_down_full = look_down_full
        self.look_down_extra = look_down_extra
        self.model_weight = model_weight
        self.history = deque(maxlen=median_frames)
        self.base_left = self.base_right = 0.30
        self.closed = False
        self.score = 0.0

    def set_baseline(self, left: float, right: float):
        self.base_left, self.base_right = max(left, 1e-3), max(right, 1e-3)
        self.reset()

    def reset(self):
        self.history.clear()
        self.closed = False
        self.score = 0.0

    def _ear_score(self, ear, base):
        ratio = ear / base
        return float(np.clip((self.open_ref - ratio) / (self.open_ref - self.closed_ref), 0.0, 1.0))

    def eye_score(self, ear, base, p_closed=None):
        s = self._ear_score(ear, base)
        if p_closed is not None and self.model_weight > 0:
            s = (1 - self.model_weight) * s + self.model_weight * p_closed
        return s

    def look_down_amount(self, d_pitch: float) -> float:
        span = self.look_down_full - self.look_down_start
        return float(np.clip((d_pitch - self.look_down_start) / span, 0.0, 1.0))

    def update(self, ear_left, ear_right, d_pitch=0.0, p_left=None, p_right=None,
               glare=(False, False)) -> bool:
        left = self.eye_score(ear_left, self.base_left, p_left)
        right = self.eye_score(ear_right, self.base_right, p_right)
        if glare[0] and not glare[1]:
            raw = right   # reflection on the left lens: trust the clear right eye
        elif glare[1] and not glare[0]:
            raw = left
        else:
            raw = min(left, right)
        self.history.append(raw)
        self.score = float(np.median(self.history))
        extra = self.look_down_extra * self.look_down_amount(d_pitch)
        if self.closed:
            self.closed = self.score > self.open_score + extra
        else:
            self.closed = self.score >= self.close_score + extra
        return self.closed


def mouth_aspect_ratio(pts) -> float:
    """MAR = |upper lip - lower lip| / |left corner - right corner|."""
    top, bottom, left, right = (pts[i] for i in MOUTH)
    width = _dist(left, right)
    return 0.0 if width < 1e-6 else _dist(top, bottom) / width


class BlinkDetector:
    """Times each eye closure and classifies it when the eye reopens.

    closure < blink_min           -> ignored (noise)
    blink_min .. blink_max        -> normal blink
    > blink_max                   -> long (slow) blink, a fatigue sign
    The caller checks `closed_duration` against the micro-sleep threshold live."""

    def __init__(self, blink_min=0.10, blink_max=0.40, window=60.0):
        self.blink_min = blink_min
        self.blink_max = blink_max
        self.window = window
        self.closed_since = None
        self.blinks = deque()       # timestamps of all blinks (normal + long)
        self.long_blinks = deque()  # timestamps of long blinks
        self.started = None

    def update(self, closed: bool, t: float):
        """Returns 'blink', 'long_blink' or None (event fires when the eye reopens)."""
        if self.started is None:
            self.started = t
        event = None
        if closed:
            if self.closed_since is None:
                self.closed_since = t
        elif self.closed_since is not None:
            duration = t - self.closed_since
            self.closed_since = None
            if duration >= self.blink_min:
                self.blinks.append(t)
                event = "blink"
                if duration > self.blink_max:
                    self.long_blinks.append(t)
                    event = "long_blink"
        self._trim(t)
        return event

    def closed_duration(self, t: float) -> float:
        return 0.0 if self.closed_since is None else t - self.closed_since

    def _trim(self, t):
        for q in (self.blinks, self.long_blinks):
            while q and t - q[0] > self.window:
                q.popleft()

    def blink_rate(self, t: float):
        """Blinks per minute, or None until a full window has been observed."""
        if self.started is None or t - self.started < self.window:
            return None
        return len(self.blinks) * 60.0 / self.window

    def long_blink_count(self) -> int:
        return len(self.long_blinks)

    def reset_closure(self):
        self.closed_since = None


class Perclos:
    """PERCentage of eye CLOSure over a sliding time window (time-weighted)."""

    def __init__(self, window=60.0, min_coverage=0.5):
        self.window = window
        self.min_coverage = min_coverage
        self.samples = deque()  # (t, dt, closed)
        self.closed_time = 0.0
        self.total_time = 0.0
        self.last_t = None

    def update(self, closed: bool, t: float):
        if self.last_t is not None:
            dt = min(t - self.last_t, 0.5)  # cap gaps (e.g. face lost) so they don't dominate
            if dt > 0:
                self.samples.append((t, dt, closed))
                self.total_time += dt
                self.closed_time += dt if closed else 0.0
        self.last_t = t
        while self.samples and t - self.samples[0][0] > self.window:
            _, dt, was_closed = self.samples.popleft()
            self.total_time -= dt
            self.closed_time -= dt if was_closed else 0.0

    def pause(self):
        """Call when no measurement is available (face lost) so the gap isn't counted."""
        self.last_t = None

    @property
    def value(self):
        """Fraction 0..1, or None until enough of the window is filled."""
        if self.total_time < self.window * self.min_coverage:
            return None
        return max(0.0, self.closed_time) / self.total_time


class YawnDetector:
    """Counts a yawn when MAR stays above threshold for at least min_duration."""

    def __init__(self, mar_threshold=0.6, min_duration=1.5, window=300.0):
        self.mar_threshold = mar_threshold
        self.min_duration = min_duration
        self.window = window
        self.open_since = None
        self.counted = False
        self.yawns = deque()

    def update(self, mar: float, t: float) -> bool:
        """Returns True on the frame a new yawn is counted."""
        new_yawn = False
        if mar > self.mar_threshold:
            if self.open_since is None:
                self.open_since, self.counted = t, False
            elif not self.counted and t - self.open_since >= self.min_duration:
                self.yawns.append(t)
                self.counted = new_yawn = True
        else:
            self.open_since = None
        while self.yawns and t - self.yawns[0] > self.window:
            self.yawns.popleft()
        return new_yawn

    @property
    def mouth_open(self) -> bool:
        return self.open_since is not None

    def count(self) -> int:
        return len(self.yawns)

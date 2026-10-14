import numpy as np
import pytest

from src.metrics import (LEFT_EYE, MOUTH, RIGHT_EYE, BlinkDetector, Perclos, YawnDetector,
                         average_ear, eye_aspect_ratio, mouth_aspect_ratio)


def eye_points(pts, idx, cx, opening):
    """Place an eye 60 px wide with the given vertical opening (px)."""
    p1, p2, p3, p4, p5, p6 = idx
    pts[p1] = (cx - 30, 100)
    pts[p4] = (cx + 30, 100)
    pts[p2] = (cx - 10, 100 - opening / 2)
    pts[p3] = (cx + 10, 100 - opening / 2)
    pts[p6] = (cx - 10, 100 + opening / 2)
    pts[p5] = (cx + 10, 100 + opening / 2)


def face(opening):
    pts = np.zeros((478, 2), np.float32)
    eye_points(pts, LEFT_EYE, 300, opening)
    eye_points(pts, RIGHT_EYE, 150, opening)
    return pts


def test_ear_open_vs_closed():
    assert average_ear(face(18)) == pytest.approx(0.30, abs=1e-6)  # 18 / 60
    assert average_ear(face(3)) == pytest.approx(0.05, abs=1e-6)


def test_ear_degenerate_eye_is_zero():
    assert eye_aspect_ratio(np.zeros((478, 2), np.float32), LEFT_EYE) == 0.0


def test_mar():
    pts = np.zeros((478, 2), np.float32)
    top, bottom, left, right = MOUTH
    pts[left], pts[right] = (0, 0), (100, 0)
    pts[top], pts[bottom] = (50, -35), (50, 35)
    assert mouth_aspect_ratio(pts) == pytest.approx(0.7)


def run_closure(det, start, duration, fps=30):
    """Eyes closed from start for duration, then open; returns events."""
    events, t = [], start
    while t < start + duration:
        events.append(det.update(True, t))
        t += 1 / fps
    events.append(det.update(False, t))
    return [e for e in events if e]


def test_blink_classification():
    det = BlinkDetector(0.10, 0.40)
    assert run_closure(det, 0.0, 0.05) == []                # noise
    assert run_closure(det, 1.0, 0.20) == ["blink"]         # normal
    assert run_closure(det, 2.0, 0.70) == ["long_blink"]    # slow
    assert det.long_blink_count() == 1
    assert len(det.blinks) == 2


def test_closed_duration_is_time_based():
    for fps in (10, 15, 30):
        det = BlinkDetector()
        t = 0.0
        while t < 1.2:
            det.update(True, t)
            t += 1 / fps
        assert det.closed_duration(t) >= 1.2


def test_blink_rate_needs_full_window():
    det = BlinkDetector(window=60)
    t = 0.0
    for _ in range(20):  # one blink every 3 s
        run_closure(det, t, 0.2)
        t += 3
    assert det.blink_rate(30) is None
    det.update(False, 60.5)
    assert det.blink_rate(60.5) == pytest.approx(20, abs=1)


def test_perclos():
    p = Perclos(window=60, min_coverage=0.5)
    t = 0.0
    while t < 60:
        p.update(closed=(t % 10) < 2, t=t)  # closed 2 s of every 10 s -> 20%
        t += 1 / 30
    assert p.value == pytest.approx(0.20, abs=0.02)


def test_perclos_needs_coverage():
    p = Perclos(window=60, min_coverage=0.5)
    for i in range(300):  # 10 s only
        p.update(False, i / 30)
    assert p.value is None


def test_yawn_detector():
    y = YawnDetector(0.6, 1.5, 300)
    counted = [y.update(0.8, i / 30) for i in range(60)]  # 2 s mouth wide open
    assert sum(counted) == 1
    y.update(0.2, 3.0)
    assert [y.update(0.8, 4 + i / 30) for i in range(30)].count(True) == 0  # only 1 s
    assert y.count() == 1


# ---------------------------------------------------------------- EyeClosureDetector
from src.metrics import EyeClosureDetector  # noqa: E402


def make_eyes(**kw):
    e = EyeClosureDetector(**kw)
    e.set_baseline(0.30, 0.30)
    return e


def test_eye_scores():
    e = make_eyes()
    assert e.eye_score(0.30, 0.30) == 0.0          # normally open
    assert e.eye_score(0.09, 0.30) == 1.0          # fully closed
    assert 0.4 < e.eye_score(0.18, 0.30) < 0.6     # half closed
    assert e.eye_score(0.30, 0.30, p_closed=1.0) == pytest.approx(0.4)  # model alone: not closed
    assert e.eye_score(0.09, 0.30, p_closed=0.0) == pytest.approx(0.6)  # closed lids win alone


def test_hysteresis_no_flicker():
    e = make_eyes(median_frames=1)
    states = [e.update(ear, ear) for ear in [0.30, 0.15, 0.17, 0.16, 0.17, 0.30]]
    # 0.15 -> score 0.70 closes; 0.16-0.17 (score ~0.6) stays closed; only 0.30 reopens
    assert states == [False, True, True, True, True, False]


def test_median_removes_single_frame_glitch():
    e = make_eyes()
    states = [e.update(ear, ear) for ear in [0.30, 0.30, 0.05, 0.30, 0.30]]
    assert not any(states)


def test_both_eyes_must_close():
    e = make_eyes(median_frames=1)
    assert not e.update(0.05, 0.30)
    assert e.update(0.05, 0.05)


def test_looking_down_needs_more_closure():
    e = make_eyes(median_frames=1)
    assert e.update(0.15, 0.15, d_pitch=0)        # straight ahead: closed
    e.reset()
    assert not e.update(0.15, 0.15, d_pitch=20)   # looking down: same lids are not "closed"
    assert e.update(0.10, 0.10, d_pitch=20)       # really closed: still detected


def test_glare_on_one_eye_uses_the_clear_eye():
    e = make_eyes(median_frames=1)
    # Left lens glare makes the left EAR read "open" while both eyes are really closed.
    assert not e.update(0.30, 0.05)                         # normal rule: both must close
    assert e.update(0.30, 0.05, glare=(True, False))        # left ignored: closure detected
    e.reset()
    assert not e.update(0.05, 0.30, glare=(True, False))    # glare can't fake a closure either


def test_glare_on_both_eyes_keeps_normal_rule():
    e = make_eyes(median_frames=1)
    assert not e.update(0.30, 0.05, glare=(True, True))

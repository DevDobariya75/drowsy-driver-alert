from pathlib import Path

import numpy as np
import pytest

from src.calibration import Baseline
from src.config import load_config
from src.state_machine import DriverStateMachine, Observation
from src.utils import Level

CFG = load_config(Path(__file__).parent.parent / "config" / "base.yaml")
FPS = 15
OPEN, CLOSED = 0.30, 0.08      # baseline open EAR is 0.30
LOOK_DOWN_EAR = 0.20           # eyelids drop when looking down at a keyboard / phone


def machine(pitch=0.0, model_ok=True):
    m = DriverStateMachine(CFG["thresholds"], CFG["eyes"])
    m.set_baseline(Baseline(OPEN, OPEN, pitch, 0.0, 0.0, 120.0, model_ok))
    return m


@pytest.fixture
def sm():
    return machine()


class Driver:
    """Feeds the state machine a scripted sequence at a fixed FPS."""

    def __init__(self, sm, seed=0):
        self.sm, self.t = sm, 0.0
        self.levels, self.reasons, self.notes = [], set(), set()
        self.rng = np.random.default_rng(seed)

    def run(self, seconds, face=True, ear=OPEN, ear_right=None, mar=0.1, pitch=0.0, yaw=0.0,
            roll=0.0, dark=False, jitter=0.0, p=None, glare=(False, False)):
        s = None
        for _ in range(int(round(seconds * FPS))):
            el = ear + self.rng.normal(0, jitter) if jitter else ear
            er = (ear_right if ear_right is not None else ear) + (self.rng.normal(0, jitter) if jitter else 0)
            o = Observation(self.t, face, el if face else None, er if face else None, mar,
                            pitch, yaw, roll, dark, p, p, *glare)
            s = self.sm.update(o)
            self.levels.append(s.level)
            self.reasons.update(s.reasons)
            self.notes.update(s.notes)
            self.t += 1 / FPS
        return s

    def blink(self, seconds=0.2):
        return self.run(seconds, ear=CLOSED)

    def normal_minutes(self, minutes, blink_every=4.0, jitter=0.0):
        for _ in range(int(minutes * 60 / blink_every)):
            self.run(blink_every - 0.2, jitter=jitter)
            self.blink(0.2)


# ------------------------------------------------------------------ no false alarms
def test_normal_driving_with_blinks_is_ok(sm):
    d = Driver(sm)
    d.normal_minutes(3)
    assert max(d.levels) == Level.OK
    assert not d.notes


def test_noisy_ear_does_not_create_blinks_or_beeps(sm):
    """Landmark jitter (e.g. glasses glare) must not count as blinks / closures."""
    d = Driver(sm)
    d.normal_minutes(3, jitter=0.03)  # +-10% EAR noise every frame
    assert max(d.levels) == Level.OK
    assert "HIGH_BLINK_RATE" not in d.notes
    assert sm.blinks.blink_rate(d.t) < 20  # true rate is 15/min


def test_noise_on_one_eye_only_never_closes(sm):
    """Glare on one lens: that eye's EAR collapses, the other stays open."""
    d = Driver(sm)
    d.run(2)
    d.run(3, ear=CLOSED, ear_right=OPEN)
    assert max(d.levels) == Level.OK


def test_normal_blinks_are_not_long_blinks(sm):
    d = Driver(sm)
    d.normal_minutes(2, blink_every=3)
    assert sm.blinks.long_blink_count() == 0
    assert "SLOW_BLINKS" not in d.notes


def test_looking_down_at_keyboard_is_not_closure(sm):
    """Looking down lowers the eyelids; that is not sleep and not PERCLOS."""
    d = Driver(sm)
    d.run(2)
    for _ in range(12):
        d.run(3, pitch=12, ear=LOOK_DOWN_EAR)   # glance down at the keyboard
        d.run(2)
    assert max(d.levels) == Level.OK
    assert not d.notes


def test_looking_down_with_open_eyes_is_not_head_nod(sm):
    d = Driver(sm)
    d.run(2)
    s = d.run(3, pitch=25, ear=LOOK_DOWN_EAR)
    assert Level.CRITICAL not in d.levels
    assert s.level == Level.OK                   # < looking_down_duration
    s = d.run(2, pitch=25, ear=LOOK_DOWN_EAR)
    assert s.level == Level.WARNING and s.reasons == ["LOOKING_DOWN"]


def test_single_weak_sign_shows_note_without_beep(sm):
    d = Driver(sm)
    for _ in range(20):           # 3 long blinks per 60 s, otherwise normal
        d.run(5)
        d.blink(0.2)
        d.run(5)
        d.blink(0.7)
    assert "SLOW_BLINKS" in d.notes
    assert max(d.levels) == Level.OK


def test_half_second_closure_is_not_an_alarm(sm):
    d = Driver(sm)
    d.run(2)
    d.run(0.5, ear=CLOSED)
    assert d.run(1).level == Level.OK
    assert max(d.levels) == Level.OK


def test_mirror_check_is_ok(sm):
    d = Driver(sm)
    d.run(1.5, yaw=40)
    d.run(1)
    d.run(1.5, yaw=-40)
    assert max(d.levels) == Level.OK


def test_low_ear_while_looking_away_is_not_microsleep(sm):
    d = Driver(sm)
    d.run(1.9, yaw=40, ear=CLOSED)
    assert max(d.levels) == Level.OK


def test_short_head_tilt_is_ok(sm):
    d = Driver(sm)
    d.run(0.7, roll=35)            # shorter than tilt_duration (1 s)
    d.run(1)
    assert max(d.levels) == Level.OK


def test_yawn_squint_is_not_microsleep(sm):
    d = Driver(sm)
    d.run(3)
    d.run(3, mar=0.8, ear=CLOSED)
    assert Level.CRITICAL not in d.levels


# ------------------------------------------------------------------ real detections
def test_microsleep_triggers_critical(sm):
    d = Driver(sm)
    d.run(2)
    s = d.run(1.2, ear=CLOSED)
    assert s.level == Level.CRITICAL and "MICROSLEEP" in s.reasons


def test_microsleep_with_noise_still_detected(sm):
    d = Driver(sm)
    d.run(2, jitter=0.03)
    s = d.run(1.4, ear=CLOSED, jitter=0.03)
    assert s.level == Level.CRITICAL and "MICROSLEEP" in s.reasons


def test_microsleep_alarm_latency(sm):
    """Alarm fires within 300 ms of the 1 s threshold (includes the median filter)."""
    d = Driver(sm)
    d.run(2)
    start = d.t
    while sm.level != Level.CRITICAL:
        d.run(1 / FPS, ear=CLOSED)
        assert d.t - start < 1.0 + 0.3
    assert d.t - start >= 1.0


def test_microsleep_while_head_drops(sm):
    d = Driver(sm)
    d.run(2)
    s = d.run(1.5, ear=CLOSED, pitch=12)
    assert s.level == Level.CRITICAL


def test_critical_clears_only_after_eyes_open(sm):
    d = Driver(sm)
    d.run(2)
    d.run(1.5, ear=CLOSED)
    assert d.run(1.0).level == Level.CRITICAL   # eyes just opened: still alarming
    assert d.run(1.5).level == Level.OK         # awake for > 2 s: cleared


def test_head_nod_with_eyelids_down(sm):
    d = Driver(sm)
    d.run(2)
    s = d.run(1.3, pitch=25, ear=0.14)
    assert s.level == Level.CRITICAL and "HEAD_NOD" in s.reasons


def test_head_hanging_down(sm):
    d = Driver(sm)
    d.run(2)
    s = d.run(2.2, pitch=40, ear=LOOK_DOWN_EAR)
    assert s.level == Level.CRITICAL and "HEAD_NOD" in s.reasons


def test_head_tilt_triggers_critical(sm):
    d = Driver(sm)
    s = d.run(2.2, roll=35)
    assert s.level == Level.CRITICAL and "HEAD_TILT" in s.reasons


def test_looking_away(sm):
    d = Driver(sm)
    s = d.run(2.5, yaw=40)
    assert s.level == Level.WARNING and "DISTRACTION" in s.reasons


def test_three_yawns_warn(sm):
    d = Driver(sm)
    for _ in range(3):
        d.run(5)
        d.run(2.5, mar=0.8)
    assert "YAWNING" in d.reasons
    assert Level.CRITICAL not in d.levels


def test_two_weak_signs_together_warn(sm):
    d = Driver(sm)
    for _ in range(2):             # 2 yawns -> YAWNS note
        d.run(5)
        d.run(2.5, mar=0.8)
    for _ in range(8):             # long blinks -> SLOW_BLINKS note
        d.run(4)
        d.blink(0.7)
    assert "FATIGUE" in d.reasons


def test_perclos_levels(sm):
    d = Driver(sm)
    for _ in range(20):            # each closure < 1 s, so no microsleep
        d.run(2.3)
        d.run(0.9, ear=CLOSED)     # ~28% closed
    assert "PERCLOS" in d.reasons
    assert "PERCLOS_HIGH" not in d.reasons

    d2 = Driver(machine())
    for _ in range(30):
        d2.run(1.2)
        d2.run(0.9, ear=CLOSED)    # ~43% closed
    assert "PERCLOS_HIGH" in d2.reasons


def test_no_face_warning(sm):
    d = Driver(sm)
    d.run(1)
    d.run(1.0, face=False)
    assert max(d.levels) == Level.OK
    s = d.run(1.5, face=False)
    assert s.level == Level.WARNING and s.reasons == ["NO_FACE"]


def test_low_visibility_when_dark(sm):
    d = Driver(sm)
    s = d.run(3, face=False, dark=True)
    assert s.reasons == ["LOW_VISIBILITY"]


def test_alarm_stays_on_if_driver_slumps_out_of_view(sm):
    d = Driver(sm)
    d.run(2)
    d.run(1.2, ear=CLOSED)
    assert d.run(3, face=False).level == Level.CRITICAL


# ------------------------------------------------------------------ eye model fusion
def test_model_rescues_glasses_closure():
    """Spectacles: EAR only drops to ratio ~0.6 on real closure; model sees closed eyes."""
    d = Driver(machine())
    d.run(2, p=0.05)
    s = d.run(1.3, ear=0.18, p=0.97)
    assert s.level == Level.CRITICAL


def test_model_vetoes_ear_glitch():
    d = Driver(machine())
    d.run(2, p=0.05)
    d.run(1.5, ear=0.17, p=0.02)    # EAR dips (glare) but the model clearly sees open eyes
    assert max(d.levels) == Level.OK


def test_untrusted_model_is_ignored():
    d = Driver(machine(model_ok=False))
    d.run(2, p=0.9)
    d.run(2, p=0.9)                 # model wrongly says closed; EAR says open
    assert max(d.levels) == Level.OK


def test_new_baseline_clears_state_from_old_baseline():
    m = DriverStateMachine(CFG["thresholds"], CFG["eyes"])   # default baseline: pitch 0
    d = Driver(m)
    d.run(3, pitch=40)                                      # natural posture is 40 deg
    assert m.level == Level.CRITICAL                        # looks like a hanging head vs 0
    m.set_baseline(Baseline(OPEN, OPEN, 40.0, 0, 0, 120))
    assert d.run(1 / FPS, pitch=40).level == Level.OK


def test_closed_lids_alarm_even_if_model_disagrees():
    """A wrong 'open' from the model must never hide a real micro-sleep."""
    d = Driver(machine())
    d.run(2, p=0.05)
    s = d.run(1.4, ear=CLOSED, p=0.0)
    assert s.level == Level.CRITICAL


def test_microsleep_detected_through_reflection_on_one_lens(sm):
    """Glare on the left lens hides that eye (its EAR reads 'open'); the right eye shows sleep."""
    d = Driver(sm)
    d.run(2, glare=(True, False))
    s = d.run(1.3, ear=OPEN, ear_right=CLOSED, glare=(True, False))
    assert s.level == Level.CRITICAL and "MICROSLEEP" in s.reasons


def test_reflection_on_one_lens_does_not_fake_closure(sm):
    d = Driver(sm)
    d.run(3, ear=CLOSED, ear_right=OPEN, glare=(True, False))
    assert max(d.levels) == Level.OK


# ------------------------------------------------------------------ head down, eyes not visible
def test_face_lost_while_head_drops_is_critical(sm):
    d = Driver(sm)
    d.run(3)
    d.run(0.5, pitch=10)
    d.run(0.3, pitch=18)            # head dropping ...
    s = d.run(0.2, face=False)      # ... and the face vanishes (camera sees top of head)
    assert s.level != Level.CRITICAL
    s = d.run(0.2, face=False)      # alarm within 0.4 s of losing the face
    assert s.level == Level.CRITICAL and "HEAD_DOWN" in s.reasons


def test_face_lost_with_head_up_is_only_a_warning(sm):
    d = Driver(sm)
    d.run(3)
    s = d.run(4, face=False)        # e.g. hand in front of the camera
    assert s.level == Level.WARNING and "NO_FACE" in s.reasons
    assert Level.CRITICAL not in d.levels


def test_head_down_with_eyes_not_visible_to_model(sm):
    d = Driver(sm)
    d.run(3)
    s = d.run(0.4, pitch=18, p=0.9)  # landmarks guess open eyes, model sees no eye
    assert s.level != Level.CRITICAL
    s = d.run(0.2, pitch=18, p=0.9)  # alarm within 0.6 s
    assert s.level == Level.CRITICAL and "HEAD_DOWN" in s.reasons


def test_head_down_reading_phone_with_visible_eyes_is_not_critical(sm):
    d = Driver(sm)
    d.run(3)
    d.run(6, pitch=25, ear=LOOK_DOWN_EAR, p=0.3)
    assert Level.CRITICAL not in d.levels
    assert "LOOKING_DOWN" in d.reasons


def test_head_down_alarm_stays_until_driver_is_back(sm):
    d = Driver(sm)
    d.run(3)
    d.run(0.5, pitch=20)
    d.run(3, face=False)
    s = d.run(1.0)                   # back up, but not yet for critical_clear_after
    assert s.level == Level.CRITICAL
    s = d.run(2.5)
    assert s.level == Level.OK


def test_head_down_with_lids_down_is_fast(sm):
    d = Driver(sm)
    d.run(3)
    s = d.run(0.7, pitch=18, ear=CLOSED)   # 0.5 s + 3-frame median
    assert s.level == Level.CRITICAL and "HEAD_DOWN" in s.reasons


def test_blink_while_looking_down_is_not_head_down(sm):
    d = Driver(sm)
    d.run(3)
    for _ in range(5):
        d.run(1.0, pitch=25, ear=LOOK_DOWN_EAR)
        d.run(0.25, pitch=25, ear=CLOSED)   # normal blink while reading the dashboard
    assert Level.CRITICAL not in d.levels


def test_head_down_detected_when_tracking_flickers(sm):
    """Head down: the tracker alternates between losing the face and garbage landmarks
    that look like open eyes. That must not keep restarting the alarm timer."""
    d = Driver(sm)
    d.run(3)
    d.run(0.3, pitch=25)
    for _ in range(4):
        d.run(0.13, face=False)
        d.run(0.07, pitch=40, ear=OPEN)
    assert "HEAD_DOWN" in d.reasons


def test_tilt_is_fast(sm):
    d = Driver(sm)
    d.run(3)
    s = d.run(1.1, roll=28)
    assert s.level == Level.CRITICAL and "HEAD_TILT" in s.reasons


def test_tilt_with_eyes_shut_is_faster(sm):
    d = Driver(sm)
    d.run(3)
    s = d.run(0.7, roll=18, ear=CLOSED)
    assert s.level == Level.CRITICAL and "HEAD_TILT" in s.reasons


def test_small_tilt_with_open_eyes_is_ok(sm):
    d = Driver(sm)
    d.run(3)
    d.run(5, roll=18)
    assert Level.CRITICAL not in d.levels

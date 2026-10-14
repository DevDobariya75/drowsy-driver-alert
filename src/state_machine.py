"""Turns per-frame measurements into a driver state: OK / WARNING / CRITICAL.

CRITICAL (continuous alarm): strong, direct evidence of sleep
  * MICROSLEEP    both eyes closed >= 1 s
  * HEAD_NOD      head dropped >= 20 deg for 1 s with the eyelids down,
                  or head hanging >= 35 deg for 2 s
  * HEAD_TILT     head on a shoulder >= 25 deg for 1 s, or >= 15 deg for 0.5 s with
                  the eyes shut / not visible
  * HEAD_DOWN     head down and the eyes cannot be seen: the face vanished (0.3 s)
                  while the head was dropping (camera sees the top of the head), or
                  the face is tracked but neither eye is visibly open (0.5 s)
  * PERCLOS_HIGH  eyes closed >= 40% of the last minute
  Stays latched until the driver is clearly awake again for critical_clear_after s.

WARNING (short beeps)
  * PERCLOS       eyes closed >= 25% of the last minute
  * YAWNING       3 yawns within 5 min (one-off pulse)
  * FATIGUE       two or more weak signs at the same time (one-off pulse)
  * DISTRACTION / LOOKING_DOWN   looking away / down for a while
  * NO_FACE / LOW_VISIBILITY

NOTES (shown on screen, NO beep): single weak signs on their own:
  SLOW_BLINKS, HIGH_BLINK_RATE, PERCLOS_RISING, YAWNS. Blink-rate changes are
  weak evidence of drowsiness, so on their own they never sound the alarm.

False-alarm guards
  * eye closure is ignored while yawning or looking far to the side
  * blink / PERCLOS statistics pause while looking clearly down or up
  * both eyes must be closed (see EyeClosureDetector)"""
from collections import deque
from dataclasses import dataclass, field

from .metrics import BlinkDetector, EyeClosureDetector, Perclos, YawnDetector
from .utils import ConditionTimer, Level


@dataclass
class Observation:
    t: float
    face: bool
    ear_left: float | None = None
    ear_right: float | None = None
    mar: float | None = None
    pitch: float | None = None
    yaw: float | None = None
    roll: float | None = None
    very_dark: bool = False
    p_left: float | None = None    # eye model P(closed), optional
    p_right: float | None = None
    glare_left: bool = False       # lens reflection over that eye
    glare_right: bool = False


@dataclass
class DriverState:
    level: Level
    reasons: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class DriverStateMachine:
    def __init__(self, th: dict, eyes: dict | None = None):
        self.th = th
        self.base_pitch = self.base_yaw = self.base_roll = 0.0
        self.use_model = True

        self.eyes = EyeClosureDetector(**(eyes or {}))
        self.blinks = BlinkDetector(th["blink_min"], th["blink_max"], 60.0)
        self.perclos = Perclos(th["perclos_window"], th["perclos_min_coverage"])
        self.yawns = YawnDetector(th["mar_yawn"], th["yawn_min_duration"], th["yawn_window"])

        self.closed_timer = ConditionTimer()
        self.nod = ConditionTimer()
        self.hang = ConditionTimer()
        self.tilt = ConditionTimer(grace=0.2)
        self.tilt_eyes = ConditionTimer(grace=0.2)   # tilted with eyes shut / not visible
        self.away = ConditionTimer()
        self.down = ConditionTimer()
        self.no_face = ConditionTimer()
        self.awake = ConditionTimer()
        self.fatigue = ConditionTimer()
        # Head down with the eyes not visible. One timer for both ways it shows up
        # (face lost while dropping / face tracked but eyes hidden): with the head
        # down the tracker flickers between the two, which must not restart it.
        self.head_down = ConditionTimer(grace=th.get("head_down_grace", 0.3))
        self.recent_pitch = deque()         # (t, d_pitch) of the last seconds with a face
        self.lost_while_down = None         # decided once, when the face disappears

        self.critical_latched = False
        self.critical_reasons = []
        self.pulses = {}      # reason -> active until t
        self.last_fired = {}  # reason -> t of last pulse (cooldown)
        self.level = Level.OK

    def set_baseline(self, baseline):
        self.eyes.set_baseline(baseline.ear_left, baseline.ear_right)
        self.use_model = baseline.model_ok
        self.base_pitch, self.base_yaw, self.base_roll = baseline.pitch, baseline.yaw, baseline.roll
        # Timers measured against the old baseline are meaningless now.
        for timer in (self.closed_timer, self.nod, self.hang, self.tilt, self.away, self.down,
                      self.awake, self.fatigue, self.head_down, self.tilt_eyes):
            timer.since = None
        self.recent_pitch.clear()
        self.lost_while_down = None
        self.blinks.reset_closure()
        self.critical_latched = False
        self.critical_reasons = []

    def _pulse(self, reason: str, t: float):
        if t - self.last_fired.get(reason, -1e9) >= self.th["warning_cooldown"]:
            self.last_fired[reason] = t
            self.pulses[reason] = t + self.th["warning_pulse"]

    def _pause_eye_stats(self):
        self.blinks.reset_closure()
        self.perclos.pause()

    def update(self, o: Observation) -> DriverState:
        th, t = self.th, o.t
        critical, warning, notes = [], [], []
        metrics = {}

        if not o.face:
            self._pause_eye_stats()
            self.eyes.reset()
            for timer in (self.closed_timer, self.nod, self.hang, self.tilt, self.away,
                          self.down, self.awake, self.fatigue, self.tilt_eyes):
                timer.update(False, t)
            if self.lost_while_down is None:   # was the head going down just before?
                self.lost_while_down = any(dp >= th["head_down_lost_pitch"] for _, dp in self.recent_pitch)
            if (self.head_down.update(self.lost_while_down, t) >= th["head_down_lost_duration"]
                    and self.lost_while_down):
                critical.append("HEAD_DOWN")
            if self.no_face.update(True, t) >= th["no_face_warning"]:
                warning.append("LOW_VISIBILITY" if o.very_dark else "NO_FACE")
            keep_latched = True  # driver slumped out of view during an alarm: keep alarming
        else:
            self.no_face.update(False, t)
            self.lost_while_down = None
            d_pitch = o.pitch - self.base_pitch
            self.recent_pitch.append((t, d_pitch))
            while t - self.recent_pitch[0][0] > th["head_down_memory"]:
                self.recent_pitch.popleft()
            d_yaw = o.yaw - self.base_yaw
            d_roll = o.roll - self.base_roll

            # ---- eyes
            p_l, p_r = (o.p_left, o.p_right) if self.use_model else (None, None)
            closed = self.eyes.update(o.ear_left, o.ear_right, d_pitch, p_l, p_r,
                                      (o.glare_left, o.glare_right))
            yawning = self.yawns.update(o.mar, t) or self.yawns.mouth_open
            eyes_unreliable = yawning or abs(d_yaw) >= th["eye_gate_yaw"]
            stats_paused = (eyes_unreliable or d_pitch >= th["stats_gate_pitch_down"]
                            or d_pitch <= -th["stats_gate_pitch_up"])
            if eyes_unreliable:
                closed = False
                self.eyes.reset()
            if stats_paused:
                self._pause_eye_stats()
            else:
                self.blinks.update(closed, t)
                self.perclos.update(self.eyes.score >= th["perclos_score"], t)

            closed_for = self.closed_timer.update(closed, t)
            if closed_for >= th["microsleep"]:
                critical.append("MICROSLEEP")

            # ---- head
            lids_down = self.eyes.score >= th["nod_eye_score"]
            if self.nod.update(d_pitch >= th["nod_pitch_delta"] and lids_down, t) >= th["nod_duration"]:
                critical.append("HEAD_NOD")
            if self.hang.update(d_pitch >= th["hang_pitch_delta"], t) >= th["hang_duration"]:
                critical.append("HEAD_NOD")
            # Eyes not visible with the head down: lids look shut, or the eye model
            # sees no open eye on either side (brow / lid / hair instead of an eye).
            no_open_eye = (p_l is not None and p_r is not None
                           and min(p_l, p_r) >= th["hidden_model_p"])
            eyes_hidden = self.eyes.score >= th["nod_eye_score"] or no_open_eye
            hidden_down = d_pitch >= th["hidden_pitch_delta"] and eyes_hidden and not yawning
            # The grace period only bridges tracking flicker; the alarm itself needs the
            # condition right now (so a blink while looking down is not stretched into one).
            if self.head_down.update(hidden_down, t) >= th["head_down_duration"] and hidden_down:
                critical.append("HEAD_DOWN")
            tilted = abs(d_roll) >= th["tilt_roll_delta"]
            if self.tilt.update(tilted, t) >= th["tilt_duration"] and tilted:
                critical.append("HEAD_TILT")
            tilted_eyes = abs(d_roll) >= th["tilt_eyes_roll_delta"] and eyes_hidden and not yawning
            if self.tilt_eyes.update(tilted_eyes, t) >= th["tilt_eyes_duration"] and tilted_eyes:
                critical.append("HEAD_TILT")
            if self.away.update(abs(d_yaw) >= th["distraction_yaw_delta"], t) >= th["distraction_duration"]:
                warning.append("DISTRACTION")
            if self.down.update(d_pitch >= th["nod_pitch_delta"], t) >= th["looking_down_duration"]:
                warning.append("LOOKING_DOWN")

            # ---- fatigue statistics
            perclos = self.perclos.value
            rate = self.blinks.blink_rate(t)
            signs = []
            if perclos is not None:
                if perclos >= th["perclos_critical"]:
                    critical.append("PERCLOS_HIGH")
                elif perclos >= th["perclos_warning"]:
                    warning.append("PERCLOS")
                elif perclos >= th["perclos_notice"]:
                    signs.append("PERCLOS_RISING")
            if self.blinks.long_blink_count() >= th["long_blinks_notice"]:
                signs.append("SLOW_BLINKS")
            if rate is not None and rate > th["blink_rate_high"]:
                signs.append("HIGH_BLINK_RATE")
            if self.yawns.count() >= th["yawns_warning"]:
                self._pulse("YAWNING", t)
            elif self.yawns.count() >= th["yawns_notice"]:
                signs.append("YAWNS")
            notes.extend(signs)
            many = len(signs) >= th["fatigue_signs_for_warning"]
            if self.fatigue.update(many, t) >= th["fatigue_confirm"]:
                self._pulse("FATIGUE", t)

            # Awake = eyes open and head in a normal position.
            normal = (not closed and d_pitch < th["nod_pitch_delta"]
                      and abs(d_roll) < th["tilt_roll_delta"])
            keep_latched = self.awake.update(normal, t) < th["critical_clear_after"]

            metrics.update(ear=(o.ear_left + o.ear_right) / 2, eye_score=self.eyes.score,
                           closed=closed, closed_for=closed_for, mar=o.mar,
                           pitch=d_pitch, yaw=d_yaw, roll=d_roll, perclos=perclos,
                           blink_rate=rate, long_blinks=self.blinks.long_blink_count(),
                           yawns=self.yawns.count(), stats_paused=stats_paused,
                           model_used=self.use_model and o.p_left is not None,
                           glare=(o.glare_left, o.glare_right))

        for reason, until in list(self.pulses.items()):
            if t < until:
                warning.append(reason)
            else:
                del self.pulses[reason]

        if critical:
            prior = self.critical_reasons if self.critical_latched else []
            self.critical_reasons = list(dict.fromkeys(prior + critical))
            self.critical_latched = True
        if critical or (self.critical_latched and keep_latched):
            self.level = Level.CRITICAL
            reasons = list(self.critical_reasons)
        else:
            self.critical_latched = False
            self.critical_reasons = []
            self.level = Level.WARNING if warning else Level.OK
            reasons = list(dict.fromkeys(warning))
        return DriverState(self.level, reasons, notes, metrics)

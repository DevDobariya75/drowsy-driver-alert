"""The full detection pipeline, independent of camera and alarm hardware.

frame -> light normalization -> landmarks -> EAR (per eye) / MAR / head pose
      -> (optional) eye model -> calibration (first N seconds) -> state machine"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .calibration import Calibrator
from .glare import eye_glare
from .head_pose import HeadPoseEstimator
from .landmarks import FaceLandmarker
from .metrics import eye_ears, mouth_aspect_ratio
from .preprocess import LightNormalizer
from .state_machine import DriverState, DriverStateMachine, Observation
from .utils import EMA, ConditionTimer, Level, StageTimer

log = logging.getLogger("pipeline")


@dataclass
class FrameResult:
    state: DriverState
    calibrating: bool
    calibration_progress: float = 0.0
    landmarks: object = None
    frame: object = None          # preprocessed frame (for display)
    info: dict = field(default_factory=dict)


class DrowsinessPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        w, h = cfg.get("resolution", (640, 480))
        self.light = LightNormalizer(**cfg.get("preprocess", {}))
        self.landmarker = FaceLandmarker(**cfg.get("landmarks", {}))
        self.pose = HeadPoseEstimator(w, h)
        a = cfg["smoothing"]["alpha"]
        # EAR is deliberately NOT smoothed here: an EMA stretches blinks.
        self.ema = {k: EMA(a) for k in ("mar", "pitch", "yaw", "roll")}

        c = cfg["calibration"]
        self.calibrator = Calibrator(c["seconds"], c["min_samples"], c.get("model_max_open_p", 0.35))
        self.state_machine = DriverStateMachine(cfg["thresholds"], cfg.get("eyes"))
        self.calibrating = True
        self.baseline = None
        self.light_changed = ConditionTimer()
        self.timer = StageTimer()

        self.eye_model = None
        em = cfg.get("eye_model", {})
        if em.get("enabled"):
            from .eye_classifier import EyeStateClassifier
            path = Path(em["path"])
            if not path.is_absolute():  # relative to the project folder, not the cwd
                path = Path(__file__).resolve().parent.parent / path
            self.eye_model = EyeStateClassifier(path)
            log.info("Eye-state model loaded: %s", path.name)

    def recalibrate(self):
        self.calibrator.reset()
        self.calibrating = True

    def process(self, frame, t: float) -> FrameResult:
        self.timer.start()
        raw = frame  # glare is measured before light correction alters the highlights
        frame, info = self.light.process(frame)
        self.timer.lap("preprocess")

        pts = self.landmarker.process(frame, t)
        self.timer.lap("landmarks")

        obs = Observation(t=t, face=False, very_dark=self.light.very_dark)
        if pts is not None:
            angles = self.pose.estimate(self.landmarker.last_3d)
            if angles is not None:
                ear_l, ear_r = eye_ears(pts)
                mar = self.ema["mar"].update(mouth_aspect_ratio(pts))
                pitch, yaw, roll = (self.ema[k].update(v) for k, v in zip(("pitch", "yaw", "roll"), angles))
                p_l = p_r = None
                if self.eye_model is not None:
                    p_l, p_r = self.eye_model.closed_probabilities(frame, pts)
                    info["p_closed"] = max((p for p in (p_l, p_r) if p is not None), default=None)
                    info["p_eyes"] = (p_l, p_r)
                gl, gr, fl, fr = eye_glare(raw, pts, self.cfg.get("glare_threshold", 0.06))
                info["glare"], info["glare_fraction"] = (gl, gr), (fl, fr)
                obs = Observation(t, True, ear_l, ear_r, mar, pitch, yaw, roll,
                                  self.light.very_dark, p_l, p_r, gl, gr)
        if not obs.face:
            pts = None
            self.pose.reset()
            for e in self.ema.values():
                e.reset()
        self.timer.lap("metrics")

        result = FrameResult(DriverState(Level.OK), self.calibrating, landmarks=pts, frame=frame, info=info)
        if self.calibrating:
            if obs.face:
                p_mean = None
                if obs.p_left is not None and obs.p_right is not None:
                    p_mean = (obs.p_left + obs.p_right) / 2
                baseline = self.calibrator.add(t, obs.ear_left, obs.ear_right, obs.pitch, obs.yaw,
                                               obs.roll, info["brightness"], p_mean)
                if baseline:
                    self._apply_baseline(baseline)
            result.calibration_progress = self.calibrator.progress(t)
        else:
            self._check_light_change(info["brightness"], t)

        # Until the first calibration finishes there is no baseline to compare
        # against, so no decisions are made. During a later recalibration the
        # previous baseline stays in use and the driver remains protected.
        if self.baseline is not None:
            result.state = self.state_machine.update(obs)
        result.calibrating = self.calibrating
        self.timer.lap("decision")
        self.timer.end_frame()
        return result

    def _apply_baseline(self, b):
        first = self.baseline is None
        self.baseline = b
        self.calibrating = False
        self.state_machine.set_baseline(b)
        log.info("%s: open EAR left %.3f right %.3f | pitch %.1f yaw %.1f roll %.1f | brightness %.0f",
                 "Calibrated" if first else "Recalibrated", b.ear_left, b.ear_right,
                 b.pitch, b.yaw, b.roll, b.brightness)
        if b.model_open_p is not None:
            if b.model_ok:
                log.info("Eye model check OK (P(closed) for open eyes = %.2f): model in use", b.model_open_p)
            else:
                log.warning("Eye model thinks your OPEN eyes look closed (P=%.2f), e.g. glare on "
                            "spectacles: using EAR only for this session", b.model_open_p)

    def _check_light_change(self, brightness, t):
        """Lighting changed a lot for a while (e.g. day -> night): recalibrate quietly."""
        c = self.cfg["calibration"]
        changed = abs(brightness - self.baseline.brightness) >= c["recalibrate_brightness_delta"]
        ok = self.state_machine.level == Level.OK
        if self.light_changed.update(changed and ok, t) >= c["recalibrate_after_seconds"]:
            log.info("Lighting changed (%.0f -> %.0f): recalibrating", self.baseline.brightness, brightness)
            self.light_changed.update(False, t)
            self.recalibrate()

    def close(self):
        self.landmarker.close()

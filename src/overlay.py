"""Debug display: landmarks, live metrics and driver state drawn on the frame.

mirror=True shows a selfie view (raise your left hand -> it appears on the left).
Only the DISPLAY is mirrored: detection always runs on the original camera image,
because head-pose maths needs the true left/right positions of the face points."""
import cv2

from .metrics import LEFT_EYE, MOUTH, RIGHT_EYE
from .utils import Level

COLORS = {Level.OK: (0, 200, 0), Level.WARNING: (0, 200, 255), Level.CRITICAL: (0, 0, 255)}


def _fmt(v, spec=".2f"):
    return "--" if v is None else format(v, spec)


def draw(frame, result, fps: float, mirror: bool = True):
    out = cv2.flip(frame, 1) if mirror else frame.copy()
    h, w = out.shape[:2]
    pts = result.landmarks
    if pts is not None:
        glare = result.info.get("glare", (False, False))
        for eye, idx in ((0, LEFT_EYE), (1, RIGHT_EYE), (None, MOUTH)):
            color = (0, 0, 255) if eye is not None and glare[eye] else (255, 255, 0)
            for i in idx:
                x = w - 1 - pts[i][0] if mirror else pts[i][0]
                cv2.circle(out, (int(x), int(pts[i][1])), 2, color, -1)

    state, m, info = result.state, result.state.metrics, result.info
    color = COLORS[state.level]
    flip = -1 if mirror else 1  # angles shown as seen in the mirror view

    if result.calibrating:
        label = f"CALIBRATING {int(result.calibration_progress * 100)}% - look straight ahead"
        cv2.rectangle(out, (0, 0), (w, 34), (80, 80, 80), -1)
        cv2.putText(out, label, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    else:
        cv2.rectangle(out, (0, 0), (w, 34), color, -1)
        label = state.level.name + (": " + ", ".join(state.reasons) if state.reasons else "")
        cv2.putText(out, label, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    eye_state = "CLOSED" if m.get("closed") else "open"
    lines = [
        f"FPS {fps:.1f}   light {info.get('light_mode', '-')} ({_fmt(info.get('brightness'), '.0f')})",
        f"eyes {eye_state}  score {_fmt(m.get('eye_score'))}  EAR {_fmt(m.get('ear'))}  "
        f"closed {_fmt(m.get('closed_for'), '.1f')}s",
        f"MAR {_fmt(m.get('mar'))}   yawns {m.get('yawns', '--')}",
        f"pitch {_fmt(m.get('pitch'), '+.0f')}  "
        f"yaw {_fmt(None if m.get('yaw') is None else flip * m['yaw'], '+.0f')}  "
        f"roll {_fmt(None if m.get('roll') is None else flip * m['roll'], '+.0f')}",
        f"PERCLOS {_fmt(m.get('perclos'))}  blinks/min {_fmt(m.get('blink_rate'), '.0f')}  "
        f"long blinks {m.get('long_blinks', '--')}" + ("  (paused)" if m.get("stats_paused") else ""),
    ]
    if info.get("p_closed") is not None:
        used = "in use" if m.get("model_used") else "NOT used (failed calibration check)"
        pl, pr = info.get("p_eyes", (None, None))
        if mirror:  # subject's left eye is on the left of the mirrored view
            lines.append(f"model P(closed)  L {_fmt(pl)}  R {_fmt(pr)}  [{used}]")
        else:
            lines.append(f"model P(closed)  R {_fmt(pr)}  L {_fmt(pl)}  [{used}]")
    glare = info.get("glare", (False, False))
    if all(glare):
        lines.append("lens reflection on both eyes (red)")
    elif any(glare):
        side = "left" if glare[0] else "right"
        lines.append(f"lens reflection on {side} eye (red) -> using the clear eye")
    if state.notes and not result.calibrating:
        lines.append("notes (no beep): " + ", ".join(state.notes))
    for i, text in enumerate(lines):
        y = h - 12 - (len(lines) - 1 - i) * 22
        cv2.putText(out, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(out, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return out

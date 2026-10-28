"""MediaPipe Face Landmarker wrapper: BGR frame -> (478, 2) landmark pixel coordinates.

The matching 3D points (x, y, depth z, all in pixels) are kept in `last_3d` for head pose.

Uses the MediaPipe Tasks API (FaceLandmarker + models/face_landmarker.task). It gives
the same 478-point mesh as the old `mp.solutions.face_mesh` (with refine_landmarks=True),
so every landmark index in the project is unchanged. The old API was removed from
MediaPipe 1.x (the only version for Python 3.13, e.g. Raspberry Pi OS Trixie). The Pi runs
Raspberry Pi OS (Legacy, 64-bit) = Bookworm, Python 3.11, MediaPipe 0.10.18 (laptop: 0.10.21);
the Tasks API exists in both 0.10.x and 1.x, so the code works either way."""
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "face_landmarker.task"


def _tasks_api():
    """(BaseOptions, vision module), wherever this MediaPipe version keeps them."""
    try:
        return mp.tasks.BaseOptions, mp.tasks.vision
    except AttributeError:
        from mediapipe.tasks.python import BaseOptions, vision
        return BaseOptions, vision


class FaceLandmarker:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5,
                 model_path=None, min_presence_confidence=None):
        path = Path(model_path) if model_path else DEFAULT_MODEL
        if not path.is_absolute():  # relative to the project folder, not the cwd
            path = Path(__file__).resolve().parent.parent / path
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Copy models/face_landmarker.task from the repository, or download "
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task")
        BaseOptions, vision = _tasks_api()
        options = vision.FaceLandmarkerOptions(
            # Passing the bytes (not the path) avoids MediaPipe path problems on Windows.
            base_options=BaseOptions(model_asset_buffer=path.read_bytes()),
            # VIDEO mode: after the first detection the face is tracked between frames
            # instead of re-detected, which is much cheaper (like static_image_mode=False).
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=(min_presence_confidence if min_presence_confidence is not None
                                          else min_tracking_confidence),
            min_tracking_confidence=min_tracking_confidence,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.last_3d = None
        self._last_ms = -1

    def _timestamp_ms(self, t):
        # VIDEO mode needs strictly increasing timestamps in milliseconds.
        ms = int(round((time.monotonic() if t is None else t) * 1000))
        ms = max(ms, self._last_ms + 1)
        self._last_ms = ms
        return ms

    def process(self, frame_bgr, t=None):
        """Return an (N, 2) float32 array of pixel coordinates, or None if no face.

        t: frame time in seconds (camera / video timestamp); defaults to now."""
        h, w = frame_bgr.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, self._timestamp_ms(t))
        self.last_3d = None
        if not result.face_landmarks:
            return None
        lm = result.face_landmarks[0]
        pts = np.fromiter((c for p in lm for c in (p.x, p.y, p.z)), dtype=np.float32, count=len(lm) * 3)
        # MediaPipe z uses roughly the same scale as x (normalized by image width).
        self.last_3d = pts.reshape(-1, 3) * np.array([w, h, w], dtype=np.float32)
        return self.last_3d[:, :2].copy()

    def close(self):
        self.landmarker.close()

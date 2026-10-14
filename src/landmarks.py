"""MediaPipe Face Mesh wrapper: BGR frame -> (478, 2) landmark pixel coordinates."""
import cv2
import mediapipe as mp
import numpy as np


class FaceLandmarker:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        # static_image_mode=False: after the first detection, MediaPipe tracks the
        # face between frames instead of re-detecting it, which is much cheaper.
        self.mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process(self, frame_bgr):
        """Return an (N, 2) float32 array of pixel coordinates, or None if no face."""
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self.mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        lm = result.multi_face_landmarks[0].landmark
        pts = np.fromiter((c for p in lm for c in (p.x, p.y)), dtype=np.float32, count=len(lm) * 2)
        return pts.reshape(-1, 2) * np.array([w, h], dtype=np.float32)

    def close(self):
        self.mesh.close()

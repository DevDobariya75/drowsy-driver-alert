"""Head pose (pitch / yaw / roll in degrees) from 6 landmarks using solvePnP.

Angle convention (camera looking at the driver):
  pitch > 0  head tilts DOWN (nodding)     pitch < 0  head tilts up
  yaw        head turns left/right
  roll       head tilts toward a shoulder
Absolute values depend on the camera mounting, so the decision logic always
compares against the baseline measured during calibration."""
import cv2
import numpy as np

# MediaPipe indices: nose tip, chin, eye outer corners, mouth corners
# (33 / 61 are on the image-left side of a non-mirrored frame).
POSE_LANDMARKS = [1, 152, 33, 263, 61, 291]

# Generic 3D face model (mm-ish), in camera-style axes: x right, y DOWN,
# z AWAY from the camera. A face looking straight at the camera gives R = I.
MODEL_POINTS = np.array([
    (0.0, 0.0, 0.0),         # nose tip
    (0.0, 330.0, 65.0),      # chin
    (-225.0, -170.0, 135.0), # eye outer corner (image left)
    (225.0, -170.0, 135.0),  # eye outer corner (image right)
    (-150.0, 150.0, 125.0),  # mouth corner (image left)
    (150.0, 150.0, 125.0),   # mouth corner (image right)
], dtype=np.float64)


def rotation_to_euler(R):
    """Rotation matrix -> (pitch, yaw, roll) in degrees (rotations about x, y, z)."""
    angles, *_ = cv2.RQDecomp3x3(R)
    return float(angles[0]), float(angles[1]), float(angles[2])


class HeadPoseEstimator:
    def __init__(self, frame_width: int, frame_height: int):
        f = float(frame_width)  # approximate focal length = image width
        self.camera_matrix = np.array(
            [[f, 0, frame_width / 2], [0, f, frame_height / 2], [0, 0, 1]], dtype=np.float64
        )
        self.dist = np.zeros((4, 1))
        self.rvec = None
        self.tvec = None

    def estimate(self, pts):
        """Return (pitch, yaw, roll) or None if solvePnP fails."""
        image_points = pts[POSE_LANDMARKS].astype(np.float64)
        use_guess = self.rvec is not None
        ok, rvec, tvec = cv2.solvePnP(
            MODEL_POINTS, image_points, self.camera_matrix, self.dist,
            rvec=self.rvec.copy() if use_guess else None,
            tvec=self.tvec.copy() if use_guess else None,
            useExtrinsicGuess=use_guess, flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok or tvec[2, 0] <= 0:  # face must be in front of the camera
            self.reset()
            return None
        self.rvec, self.tvec = rvec, tvec
        R, _ = cv2.Rodrigues(rvec)
        return rotation_to_euler(R)

    def reset(self):
        """Forget the previous solution (call when the face is lost)."""
        self.rvec = self.tvec = None

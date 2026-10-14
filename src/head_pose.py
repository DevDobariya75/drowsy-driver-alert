"""Head pose (pitch / yaw / roll in degrees) from MediaPipe's 3D face landmarks.

MediaPipe gives every landmark a depth (z) as well as x, y, so the head's
orientation can be read directly from the face's own axes, with no solver:
  x axis  eye corner -> eye corner and cheek -> cheek (left to right across the face)
  y axis  forehead -> chin (down the face)
  z axis  x cross y (out of the back of the head)
Unlike a 6-point solvePnP fit to a generic face model, this cannot jump to a
mirrored solution or fail, and the sign of each angle is fixed by geometry.

Angle convention (camera axes: x right, y down, z away from the camera):
  pitch > 0  head tilts DOWN (chin moves away from the camera)
  yaw        head turns left/right
  roll       head tilts toward a shoulder
Absolute values depend on the camera mounting and the face, so the decision
logic always compares against the baseline measured during calibration."""
import cv2
import numpy as np

# MediaPipe indices (33 / 234 / 61 are on the image-left side of a non-mirrored frame).
EYE_L, EYE_R = 33, 263       # outer eye corners
CHEEK_L, CHEEK_R = 234, 454  # face edges at eye level
FOREHEAD, CHIN = 10, 152


def rotation_to_euler(R):
    """Rotation matrix -> (pitch, yaw, roll) in degrees, for R = Rz @ Ry @ Rx."""
    angles, *_ = cv2.RQDecomp3x3(R)
    return float(angles[0]), float(angles[1]), float(angles[2])


def face_rotation(pts3d):
    """3x3 rotation whose columns are the face's x, y, z axes in camera coordinates."""
    p = np.asarray(pts3d, dtype=np.float64)
    xv = (p[EYE_R] - p[EYE_L]) + (p[CHEEK_R] - p[CHEEK_L])
    yv = p[CHIN] - p[FOREHEAD]
    nx = np.linalg.norm(xv)
    if nx < 1e-6:
        return None
    x = xv / nx
    yv = yv - (yv @ x) * x            # make y exactly perpendicular to x
    ny = np.linalg.norm(yv)
    if ny < 1e-6:
        return None
    y = yv / ny
    return np.column_stack([x, y, np.cross(x, y)])


class HeadPoseEstimator:
    def __init__(self, frame_width: int = 0, frame_height: int = 0):
        pass  # no camera model needed

    def estimate(self, pts3d):
        """(N, 3) landmarks in pixels (x, y, z) -> (pitch, yaw, roll), or None."""
        if pts3d is None or np.shape(pts3d)[1] < 3:
            return None
        R = face_rotation(pts3d)
        return None if R is None else rotation_to_euler(R)

    def reset(self):
        pass  # stateless

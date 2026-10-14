import numpy as np
import pytest

from src.head_pose import CHEEK_L, CHEEK_R, CHIN, EYE_L, EYE_R, FOREHEAD, HeadPoseEstimator

# A face looking straight at the camera (camera axes: x right, y down, z away).
FACE = {EYE_L: (-45, 0, 10), EYE_R: (45, 0, 10), CHEEK_L: (-70, 0, 40), CHEEK_R: (70, 0, 40),
        FOREHEAD: (0, -90, 20), CHIN: (0, 110, 20)}


def rotation(pitch, yaw, roll):
    x, y, z = np.radians([pitch, yaw, roll])
    Rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def face(angles):
    pts = np.zeros((478, 3))
    R = rotation(*angles)
    for i, p in FACE.items():
        pts[i] = R @ np.array(p, float) + (320, 240, 0)
    return pts


@pytest.mark.parametrize("angles", [(0, 0, 0), (20, 0, 0), (45, 0, 0), (-15, 0, 0), (0, 30, 0),
                                    (0, 0, 25), (10, -20, 5), (30, 0, 20)])
def test_recovers_known_angles(angles):
    assert HeadPoseEstimator().estimate(face(angles)) == pytest.approx(angles, abs=0.01)


def test_positive_pitch_means_head_down():
    # Head down: the chin moves away from the camera, the forehead towards it.
    pts = face((30, 0, 0))
    assert pts[CHIN, 2] > pts[FOREHEAD, 2]
    assert HeadPoseEstimator().estimate(pts)[0] > 25


def test_needs_depth():
    assert HeadPoseEstimator().estimate(np.zeros((478, 2))) is None

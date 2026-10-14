import cv2
import numpy as np
import pytest

from src.head_pose import MODEL_POINTS, POSE_LANDMARKS, HeadPoseEstimator


def rotation(pitch, yaw, roll):
    x, y, z = np.radians([pitch, yaw, roll])
    Rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def project(est, angles):
    rvec, _ = cv2.Rodrigues(rotation(*angles))
    img, _ = cv2.projectPoints(MODEL_POINTS, rvec, np.array([0.0, 0.0, 2000.0]),
                               est.camera_matrix, est.dist)
    pts = np.zeros((478, 2), np.float32)
    pts[POSE_LANDMARKS] = img.reshape(-1, 2)
    return pts


@pytest.mark.parametrize("angles", [(0, 0, 0), (20, 0, 0), (-15, 0, 0), (0, 30, 0),
                                    (0, 0, 25), (10, -20, 5)])
def test_recovers_known_angles(angles):
    est = HeadPoseEstimator(640, 480)
    assert est.estimate(project(est, angles)) == pytest.approx(angles, abs=0.5)


def test_positive_pitch_means_head_down():
    # Head tilting down brings the forehead (above the nose, y < 0) toward the camera.
    forehead = rotation(20, 0, 0) @ np.array([0, -300, 0])
    assert forehead[2] < 0

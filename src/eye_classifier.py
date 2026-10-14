"""Optional eye-state model (open / closed), run with OpenCV's DNN module.

The model is a tiny CNN trained in training/train_eye_model.py and exported to
ONNX. OpenCV runs it on both the laptop and the Pi, so no extra runtime is needed.
Eye crops are made with crop_eye(), which training/collect_eye_samples.py also
uses, so training and inference see identical crops."""
import cv2
import numpy as np

from .metrics import LEFT_EYE, RIGHT_EYE

INPUT_SIZE = 48
CROP_SCALE = 1.8  # crop side = 1.8 x eye width: matches the framing of the MRL training images


def crop_eye(gray, pts, idx, size=INPUT_SIZE):
    """Square grayscale crop centred on the eye, resized to size x size (or None)."""
    p1, p4 = pts[idx[0]], pts[idx[3]]
    cx, cy = (p1 + p4) / 2
    half = max(np.linalg.norm(p1 - p4) * CROP_SCALE / 2, 4)
    h, w = gray.shape[:2]
    x0, x1 = int(round(cx - half)), int(round(cx + half))
    y0, y1 = int(round(cy - half)), int(round(cy + half))
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h or x1 - x0 < 8:
        return None
    return cv2.resize(gray[y0:y1, x0:x1], (size, size), interpolation=cv2.INTER_AREA)


def to_gray(frame):
    return frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


class EyeStateClassifier:
    def __init__(self, path):
        from pathlib import Path
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} not found. Train it first (training/README.md) "
                                    "or set eye_model.enabled: false")
        self.net = cv2.dnn.readNetFromONNX(str(path))

    def closed_probabilities(self, frame, pts):
        """(P(closed) left eye, P(closed) right eye); None for an eye that can't be cropped."""
        gray = to_gray(frame)
        crops = [crop_eye(gray, pts, LEFT_EYE), crop_eye(gray, pts, RIGHT_EYE)]
        valid = [c for c in crops if c is not None]
        if not valid:
            return None, None
        blob = cv2.dnn.blobFromImages(valid, scalefactor=1 / 255.0, size=(INPUT_SIZE, INPUT_SIZE))
        self.net.setInput(blob)
        probs = iter(self.net.forward()[:, 1].tolist())  # softmax output: [open, closed]
        left, right = (None if c is None else next(probs) for c in crops)
        return left, right

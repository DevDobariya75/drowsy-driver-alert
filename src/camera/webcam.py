"""Laptop webcam or USB camera via OpenCV."""
import sys

import cv2

from .base import ThreadedCamera


class WebcamCamera(ThreadedCamera):
    def __init__(self, index: int = 0, resolution=(640, 480)):
        super().__init__()
        self.index = index
        self.resolution = resolution
        self.cap = None

    def _open(self):
        # DirectShow opens much faster than the default backend on Windows.
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(self.index, backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {self.index}")
        w, h = self.resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _grab(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def _close(self):
        if self.cap:
            self.cap.release()

"""Plays a recorded video as if it were a camera (for repeatable testing).

Timestamps come from the video itself (frame_index / fps), so time-based
detection gives the same result no matter how fast the computer is."""
import time

import cv2

from .base import Camera


class VideoFileCamera(Camera):
    def __init__(self, path, resolution=None, realtime=False, transform=None):
        self.path = str(path)
        self.resolution = tuple(resolution) if resolution else None
        self.realtime = realtime
        self.transform = transform  # optional fn(frame) -> frame, e.g. darken
        self.cap = None
        self.fps = 30.0
        self.index = 0
        self.finished = False
        self._t0 = None

    def start(self):
        self.cap = cv2.VideoCapture(self.path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video {self.path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._t0 = time.monotonic()

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            self.finished = True
            return None
        stamp = self.index / self.fps
        self.index += 1
        if self.resolution and (frame.shape[1], frame.shape[0]) != self.resolution:
            frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_AREA)
        if self.transform:
            frame = self.transform(frame)
        if self.realtime:
            delay = self._t0 + stamp - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        return frame, stamp

    def stop(self):
        if self.cap:
            self.cap.release()

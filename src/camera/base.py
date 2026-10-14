"""Camera interface. The pipeline only talks to this, never to hardware directly."""
import threading
import time
from abc import ABC, abstractmethod


class Camera(ABC):
    """read() returns (frame_bgr, timestamp_seconds), or None if no new frame.
    `finished` becomes True when a finite source (video file) runs out."""

    finished = False

    @abstractmethod
    def start(self): ...

    @abstractmethod
    def read(self): ...

    @abstractmethod
    def stop(self): ...

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


class ThreadedCamera(Camera):
    """A background thread grabs frames continuously and keeps only the latest,
    so the slow processing loop never works on stale, queued-up frames."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._stamp = 0.0
        self._new = threading.Event()
        self._running = False
        self._thread = None

    @abstractmethod
    def _open(self): ...

    @abstractmethod
    def _grab(self):
        """Return one BGR frame, or None on failure."""

    @abstractmethod
    def _close(self): ...

    def start(self):
        self._open()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            frame = self._grab()
            if frame is None:
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame, self._stamp = frame, time.monotonic()
            self._new.set()

    def read(self, timeout: float = 1.0):
        if not self._new.wait(timeout):
            return None
        with self._lock:
            self._new.clear()
            return self._frame, self._stamp

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._close()

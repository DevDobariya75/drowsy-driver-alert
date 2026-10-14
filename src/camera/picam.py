"""Raspberry Pi camera module via Picamera2 (only imported on the Pi)."""
from .base import ThreadedCamera


class PiCamera(ThreadedCamera):
    def __init__(self, resolution=(640, 480), min_fps: int = 15):
        super().__init__()
        self.resolution = tuple(resolution)
        self.min_fps = min_fps
        self.picam = None

    def _open(self):
        from picamera2 import Picamera2  # Pi-only dependency
        from libcamera import controls

        self.picam = Picamera2()
        # "RGB888" in Picamera2 is laid out as BGR in memory: exactly what OpenCV expects.
        config = self.picam.create_video_configuration(
            main={"size": self.resolution, "format": "RGB888"}, buffer_count=2
        )
        self.picam.configure(config)
        self.picam.set_controls({
            "AeEnable": True,
            "AwbEnable": True,
            # Allow longer exposure in low light, but never drop below min_fps.
            "FrameDurationLimits": (int(1e6 / 30), int(1e6 / self.min_fps)),
            "AeExposureMode": controls.AeExposureModeEnum.Long,
        })
        self.picam.start()

    def _grab(self):
        return self.picam.capture_array("main")

    def _close(self):
        if self.picam:
            self.picam.stop()
            self.picam.close()

"""Camera factory: the config decides which implementation is used."""
from .base import Camera


def make_camera(cfg: dict, transform=None) -> Camera:
    kind = cfg.get("camera", "webcam")
    res = tuple(cfg.get("resolution", (640, 480)))
    if kind == "webcam":
        from .webcam import WebcamCamera
        return WebcamCamera(cfg.get("camera_index", 0), res)
    if kind == "picamera2":
        from .picam import PiCamera
        return PiCamera(res)
    if kind == "video":
        from .video_file import VideoFileCamera
        if not cfg.get("video_path"):
            raise ValueError("camera: video needs video_path (or --video)")
        return VideoFileCamera(cfg["video_path"], res, cfg.get("video_realtime", False), transform)
    raise ValueError(f"Unknown camera type: {kind}")

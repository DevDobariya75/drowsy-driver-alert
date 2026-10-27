"""Entry point.

    python src/main.py --config config/laptop.yaml           # laptop webcam + speaker
    python src/main.py --config config/pi.yaml               # Raspberry Pi + USB webcam + buzzer
    python src/main.py --config config/laptop.yaml --max-fps 15 --cpu-cores 1   # simulate a Pi
    python src/main.py --config config/laptop.yaml --video tests/videos/clip.mp4

Keys (when the window is shown): q = quit, c = recalibrate."""
import argparse
import csv
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.alarm import make_alarm  # noqa: E402
from src.camera import make_camera  # noqa: E402
from src.config import load_config  # noqa: E402
from src.pipeline import DrowsinessPipeline  # noqa: E402
from src.utils import FPSCounter, Level, setup_logging  # noqa: E402

log = logging.getLogger("main")
CSV_FIELDS = ["t", "level", "reasons", "notes", "calibrating", "ear", "eye_score", "closed",
              "closed_for", "p_closed", "mar", "pitch", "yaw", "roll", "perclos", "blink_rate",
              "long_blinks", "yawns", "stats_paused", "glare", "brightness", "light_mode"]


def parse_args():
    p = argparse.ArgumentParser(description="Driver drowsiness detection")
    p.add_argument("--config", default=str(ROOT / "config" / "laptop.yaml"))
    p.add_argument("--video", help="run on a recorded video instead of the camera")
    p.add_argument("--max-fps", type=float, help="cap processing FPS (15 simulates a Pi 4)")
    p.add_argument("--cpu-cores", type=int, help="restrict to N CPU cores (simulates a Pi)")
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--csv", help="write per-frame metrics to this CSV file")
    return p.parse_args()


def limit_cpu(cores: int):
    try:
        import psutil
        psutil.Process().cpu_affinity(list(range(cores)))
        log.info("Restricted to %d CPU core(s)", cores)
    except Exception as e:  # not supported on every OS
        log.warning("Could not restrict CPU cores: %s", e)


def main():
    args = parse_args()
    overrides = {}
    if args.video:
        overrides.update(camera="video", video_path=args.video, video_realtime=True)
    if args.max_fps is not None:
        overrides["max_fps"] = args.max_fps
    if args.no_window:
        overrides["show_window"] = False
    if args.csv:
        overrides["csv_log"] = args.csv
    cfg = load_config(args.config, overrides)
    setup_logging(cfg.get("log_level", "INFO"))
    if args.cpu_cores:
        limit_cpu(args.cpu_cores)

    show = cfg.get("show_window", False)
    if show:
        import cv2
        from src.overlay import draw

    pipeline = DrowsinessPipeline(cfg)
    alarm = make_alarm(cfg)
    camera = make_camera(cfg)
    fps = FPSCounter()
    max_fps = cfg.get("max_fps") or 0
    csv_file = writer = None
    if cfg.get("csv_log"):
        csv_file = open(cfg["csv_log"], "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(csv_file, CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()

    last_level, last_reasons = Level.OK, []
    last_stats = time.monotonic()
    try:
        camera.start()
        alarm.beep_armed()
        log.info("Armed. Calibrating for %ss - look straight ahead.", cfg["calibration"]["seconds"])
        while True:
            loop_start = time.perf_counter()
            item = camera.read()
            if item is None:
                if camera.finished:
                    break
                log.warning("No frame from camera")
                continue
            frame, t = item
            result = pipeline.process(frame, t)
            state = result.state
            alarm.set_level(state.level, state.reasons)
            if state.level != last_level or state.reasons != last_reasons:
                log.info("State %s %s", state.level.name, state.reasons)
                last_level, last_reasons = state.level, state.reasons
            fps.tick()

            if writer:
                writer.writerow({"t": round(t, 3), "level": state.level.name,
                                 "reasons": "|".join(state.reasons), "notes": "|".join(state.notes),
                                 "calibrating": result.calibrating,
                                 **state.metrics, **result.info})

            now = time.monotonic()
            if now - last_stats >= 10:
                stages = ", ".join(f"{k} {v:.1f}" for k, v in pipeline.timer.averages().items())
                log.info("FPS %.1f | ms/frame: %s", fps.fps, stages)
                pipeline.timer.reset()
                last_stats = now

            if show:
                cv2.imshow("Drowsiness Monitor", draw(result.frame, result, fps.fps, cfg.get("mirror_display", True)))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("c"):
                    pipeline.recalibrate()

            if max_fps:
                delay = 1.0 / max_fps - (time.perf_counter() - loop_start)
                if delay > 0:
                    time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        alarm.close()
        pipeline.close()
        if csv_file:
            csv_file.close()
        if show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""Runs labelled clips through the full pipeline and prints a pass/fail table.

    python tests/run_video_tests.py                   # clips as recorded
    python tests/run_video_tests.py --lighting        # + dark / very dark / bright / shadow versions
    python tests/run_video_tests.py --cpu-cores 1     # check behaviour under Pi-like CPU limits

Labels live in tests/videos/labels.yaml (see the example there). Each clip
should start with ~5 s of looking straight ahead (used for calibration)."""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.camera.video_file import VideoFileCamera  # noqa: E402
from src.config import load_config  # noqa: E402
from src.pipeline import DrowsinessPipeline  # noqa: E402
from src.utils import Level  # noqa: E402

VIDEO_DIR = ROOT / "tests" / "videos"
_rng = np.random.default_rng(0)


def _noisy(frame, scale):
    noise = _rng.normal(0, 6, frame.shape).astype(np.float32)
    return np.clip(frame.astype(np.float32) * scale + noise, 0, 255).astype(np.uint8)


def _shadow(frame):
    out = frame.copy()
    half = out.shape[1] // 2
    out[:, :half] = (out[:, :half] * 0.35).astype(np.uint8)
    return out


LIGHTING = {
    "original": None,
    "dark": lambda f: _noisy(f, 0.25),
    "very_dark": lambda f: _noisy(f, 0.08),
    "bright": lambda f: cv2.convertScaleAbs(f, alpha=1.8, beta=40),
    "side_shadow": _shadow,
}


def run_clip(cfg, path, transform):
    pipeline = DrowsinessPipeline(cfg)
    cam = VideoFileCamera(path, cfg["resolution"], transform=transform)
    cam.start()
    worst, reasons, frames, faces, calibrated = Level.OK, set(), 0, 0, False
    try:
        while (item := cam.read()) is not None:
            r = pipeline.process(*item)
            frames += 1
            faces += r.landmarks is not None
            calibrated |= not r.calibrating
            worst = max(worst, r.state.level)
            reasons.update(r.state.reasons)
    finally:
        cam.stop()
        pipeline.close()
    return worst, reasons, faces / max(frames, 1), calibrated


def check(clip, worst, reasons):
    expect = Level[clip["expect"].upper()]
    if worst != expect:
        return False
    want = set(clip.get("reasons", []))
    return want <= reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(VIDEO_DIR / "labels.yaml"))
    ap.add_argument("--lighting", action="store_true", help="also test synthetic lighting variants")
    ap.add_argument("--cpu-cores", type=int)
    ap.add_argument("--only", help="run only clips whose file name contains this text")
    args = ap.parse_args()

    if args.cpu_cores:
        import psutil
        psutil.Process().cpu_affinity(list(range(args.cpu_cores)))

    with open(args.labels, encoding="utf-8") as f:
        clips = (yaml.safe_load(f) or {}).get("clips", [])
    clips = [c for c in clips if not args.only or args.only in c["file"]]
    if not clips:
        print(f"No clips listed in {args.labels}. Record some (see tests/videos/README.md).")
        return 1

    cfg = load_config(ROOT / "config" / "test.yaml")
    variants = LIGHTING if args.lighting else {"original": None}
    rows, passed = [], 0
    for clip in clips:
        path = VIDEO_DIR / clip["file"]
        if not path.exists():
            rows.append((clip["file"], "-", clip["expect"], "MISSING", "", "", "FAIL"))
            continue
        for name, tf in variants.items():
            worst, reasons, face_ratio, calibrated = run_clip(cfg, path, tf)
            ok = check(clip, worst, reasons)
            passed += ok
            rows.append((clip["file"], name, clip["expect"].upper(), worst.name,
                         ",".join(sorted(reasons)) or "-", f"{face_ratio:.0%}",
                         ("PASS" if ok else "FAIL") + ("" if calibrated else " (not calibrated)")))

    headers = ("clip", "lighting", "expected", "got", "reasons", "face", "result")
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line + "\n" + "-" * len(line))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    print(f"\n{passed}/{len(rows)} passed")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Collects your own open / closed eye crops from the webcam, using exactly the
same cropping as the live system. Adds real webcam images (RGB sensor, your
lighting, your glasses) to the infrared-heavy MRL dataset.

    python training/collect_eye_samples.py --person dev

Hold  O  while your eyes are open, hold  C  while they are closed
(peek at the counter between bursts), q to quit. Vary the lighting, glasses,
distance and head angle while collecting. Saves to training/data/own/<person>/{open,closed}/."""
import argparse
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eye_classifier import crop_eye, to_gray  # noqa: E402
from src.landmarks import FaceLandmarker  # noqa: E402
from src.metrics import LEFT_EYE, RIGHT_EYE  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", required=True, help="name used to group your samples")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    out = ROOT / "training" / "data" / "own" / args.person
    dirs = {"o": out / "open", "c": out / "closed"}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    counts = {k: len(list(d.glob("*.png"))) for k, d in dirs.items()}

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(args.camera, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    lm = FaceLandmarker()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (640, 480))
        pts = lm.process(frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        label = chr(key) if key < 128 else ""
        if pts is not None and label in dirs:
            gray = to_gray(frame)
            for side, idx in (("L", LEFT_EYE), ("R", RIGHT_EYE)):
                crop = crop_eye(gray, pts, idx)
                if crop is not None:
                    cv2.imwrite(str(dirs[label] / f"{time.time_ns()}_{side}.png"), crop)
                    counts[label] += 1
        shown = cv2.flip(frame, 1)  # mirror view only; saved images are not flipped
        status = "face OK" if pts is not None else "NO FACE"
        cv2.putText(shown, f"{status}   open: {counts['o']}   closed: {counts['c']}   (hold O / C, q quit)",
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        cv2.imshow("collect eye samples", shown)
    cap.release()
    lm.close()
    cv2.destroyAllWindows()
    print(f"Saved to {out}: {counts['o']} open, {counts['c']} closed")


if __name__ == "__main__":
    main()

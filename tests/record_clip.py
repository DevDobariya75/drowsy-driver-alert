"""Records a webcam clip for the video tests.

    python tests/record_clip.py microsleep.mp4 --seconds 15

Press SPACE to start/stop recording early, q to quit. Saved to tests/videos/."""
import argparse
import sys
import time
from pathlib import Path

import cv2

VIDEO_DIR = Path(__file__).resolve().parent / "videos"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="output file name, e.g. microsleep.mp4")
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--fps", type=float, default=15)
    args = ap.parse_args()

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(args.camera, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    VIDEO_DIR.mkdir(exist_ok=True)
    out_path = VIDEO_DIR / args.name
    writer, start, next_frame = None, None, 0.0
    print("SPACE = start recording, q = quit")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (640, 480))
        now = time.monotonic()
        if writer is not None and now >= next_frame:
            writer.write(frame)  # fixed FPS so video timestamps match real time
            next_frame += 1 / args.fps
        shown = cv2.flip(frame, 1)  # mirror view only; saved images are not flipped
        if writer is not None:
            elapsed = now - start
            cv2.circle(shown, (20, 20), 8, (0, 0, 255), -1)
            cv2.putText(shown, f"REC {elapsed:4.1f}s  (first 5 s: look straight ahead)", (36, 27),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
            if elapsed >= args.seconds:
                break
        cv2.imshow("record", shown)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            if writer is None:
                writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (640, 480))
                start = next_frame = time.monotonic()
            else:
                break
    if writer:
        writer.release()
        print(f"Saved {out_path}")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

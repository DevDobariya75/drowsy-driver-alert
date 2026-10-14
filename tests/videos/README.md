# Test clips

Record each clip with:

```
python tests/record_clip.py <name>.mp4 --seconds 15
```

Rules for every clip:
1. **First 5 seconds:** sit normally, look straight at the camera with your eyes open (this is used for calibration).
2. Then do the action described in `labels.yaml`.
3. Uncomment the clip's entry in `labels.yaml`.

Record the same set with a friend and with spectacles, and in real lighting (near a window, lights off with only the monitor on, a window behind you).

Then run:

```
python tests/run_video_tests.py              # as recorded
python tests/run_video_tests.py --lighting   # + synthetic dark / very dark / bright / shadow versions
```

# Drowsy Driver Alert

An edge-AI driver drowsiness monitor. A camera watches the driver's eyes and head, and a buzzer
sounds on micro-sleep (eyes closed ≥ 1 s), head nodding or tilting. It gives warning beeps for
fatigue signs: PERCLOS, yawning, slow blinks and looking away. Everything runs offline.

The **same code** runs on a laptop and on a Raspberry Pi; only the config file changes.

The trained eye-state model (`models/eye_state.onnx`, ~290 KB) is included, so no training is needed to run it.
The full project plan is in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).

## Quick start (laptop)

```powershell
git clone <your-repo-url> drowsy-driver-alert
cd drowsy-driver-alert
py -3.11 -m venv venv            # Python 3.11 (MediaPipe 0.10.21 needs <= 3.12)
venv\Scriptsctivate
pip install -r requirements.txt

python src/main.py --config config/laptop.yaml
```
1. A double beep means the system is armed. The window is a **mirror** view (your left hand appears on the left).
2. **Look straight at the camera for 10 s** (calibration).
3. Try it: close your eyes for 2 s and you'll hear a loud, fast siren-like alarm (turn the system volume up). Nod your head, yawn, or look away.

Keys: **q** quit, **c** recalibrate.

### Useful options
| Command | Purpose |
|---|---|
| `--max-fps 15 --cpu-cores 1` | Simulate a Raspberry Pi's speed |
| `--video tests/videos/clip.mp4` | Run on a recorded video |
| `--csv logs/run.csv` | Save per-frame EAR / MAR / angles / state (graphs for the report) |
| `--no-window` | Headless, as on the Pi |

## How it works

```
camera ─▶ light normalization ─▶ MediaPipe Face Mesh ─▶ EAR, MAR, head pose ─▶ smoothing
       ─▶ per-driver calibration ─▶ state machine (OK / WARNING / CRITICAL) ─▶ alarm
```

**CRITICAL: continuous alarm** (strong, direct evidence of sleep)
| Reason | Rule |
|---|---|
| MICROSLEEP | both eyes closed ≥ 1.0 s |
| HEAD_NOD | head ≥ 20° down for 1 s **with eyelids down**, or head hanging ≥ 35° for 2 s |
| HEAD_TILT | head ≥ 30° towards a shoulder for 2 s |
| PERCLOS_HIGH | eyes closed ≥ 40% of the last minute |

**WARNING: short beeps**
| Reason | Rule |
|---|---|
| PERCLOS | eyes closed ≥ 25% of the last minute |
| YAWNING | 3 yawns within 5 min |
| FATIGUE | 2 or more weak signs (below) at the same time |
| DISTRACTION / LOOKING_DOWN | looking ≥ 30° to the side for 2 s / ≥ 20° down for 4 s |
| NO_FACE / LOW_VISIBILITY | no face for 2 s |

**Notes: on screen only, never beep** (weak signs on their own):
SLOW_BLINKS (3 blinks of 0.5–1 s within a minute), HIGH_BLINK_RATE (> 30/min),
PERCLOS_RISING (≥ 12%), YAWNS (2 within 5 min).

### How eye closure is decided (no false triggers)
* Each eye is compared with **its own** calibrated open EAR, giving a 0 (open) to 1 (closed) score.
* **Both eyes must look closed.** The less-closed eye counts, so glare on one lens can't fake a closure.
* **Lens reflections** (`src/glare.py`): the share of near-white pixels around each eye is measured on the raw
  frame. If one lens has glare (drawn red), that eye is ignored and the clear eye decides, so a reflection can
  neither fake nor hide a closure. Threshold: `glare_threshold` in `config/base.yaml`.
* A 3-frame median removes single-frame glitches. EAR is **not** smoothed, because smoothing stretches blinks into fake "slow blinks".
* **Hysteresis:** the eye closes at score 0.6 and reopens at 0.4, so it can't flicker.
* **Looking down** lowers the eyelids, so the closing level rises with head pitch.
  Blink and PERCLOS statistics pause while you look clearly down or up.
* PERCLOS uses the standard **P80** definition: it only counts eyes about 80% closed.
* Eye closure is ignored while yawning (squint) or with the head turned far to the side.
* With the **eye model** enabled, each eye's score is 60% EAR and 40% model (v3, trained with spectacle reflections). This rescues
  spectacle wearers whose EAR barely drops, and vetoes EAR glitches from glare. During calibration
  the model is checked on your open eyes. If it disagrees (P(closed) > 0.35), it is switched off for that session.

### Lighting
`src/preprocess.py` measures brightness and switches modes (with hysteresis):
* **dark:** denoise first, then gamma brighten, then gentle CLAHE
* **normal:** CLAHE only
* **bright:** gamma darken, then CLAHE

Measured on a test face (synthetic darkening + sensor noise), the face was found in this many frames out of 90:

| Condition | No correction | With correction |
|---|---|---|
| 10% brightness | 82 | 89 |
| 7% brightness | 66 | 90 |
| 5% brightness | 0 | 86 |

Lighting changes of more than 60 levels that last 30 s trigger a quiet recalibration.
Complete darkness needs IR illumination; no software can see without light.

## Project layout

```
config/        base.yaml (all thresholds), laptop.yaml, pi.yaml, test.yaml
src/
  main.py            entry point
  pipeline.py        whole detection chain (hardware independent)
  camera/            webcam.py, picam.py (Pi), video_file.py (tests)
  alarm/             speaker.py (laptop), gpio_buzzer.py (Pi), console.py (tests)
  preprocess.py      light normalization
  landmarks.py       MediaPipe Face Mesh
  metrics.py         EAR, MAR, blinks, PERCLOS, yawns
  head_pose.py       solvePnP -> pitch / yaw / roll
  calibration.py     per-driver baseline
  state_machine.py   OK / WARNING / CRITICAL decisions
  eye_classifier.py  optional CNN (OpenCV DNN)
  overlay.py         debug display
tests/         unit tests, video test runner, clip recorder
training/      optional eye-model training (see training/README.md)
```

## Testing

```powershell
python -m pytest -q                              # unit tests, no camera needed
python tests/record_clip.py microsleep.mp4       # record labelled clips (see tests/videos/README.md)
python tests/run_video_tests.py --lighting       # pass/fail table, 5 lighting variants per clip
```

## Moving to the Raspberry Pi (Phase 3)

```bash
sudo apt install -y python3-picamera2 python3-gpiozero python3-venv
python3 -m venv --system-site-packages venv && source venv/bin/activate
pip install -r requirements.txt
python src/main.py --config config/pi.yaml
```
Buzzer module: VCC to pin 2 (5 V), GND to pin 6, I/O to pin 12 (GPIO18).
If it beeps when it should be silent, set `buzzer_active_high: false` in `pi.yaml`.

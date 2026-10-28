# Driver Drowsiness Detection System — Implementation Plan

> **Project:** "Asleep at the Wheel": an edge-AI drowsiness monitor
> **Idea:** A Raspberry Pi with a camera watches the driver's eyes and head. If it detects micro-sleep (eyes closed too long or the head nodding), it sounds a loud buzzer.

The project is built in **4 phases**:

| Phase | Name | Hardware needed? | Output |
|---|---|---|---|
| **1** | Requirements, calculations and component gathering | ❌ No (only buying) | Requirements doc, formulas, thresholds, components in hand |
| **2** | Build and test the model on the laptop | ❌ No | Working, tested, hardware-ready software |
| **3** | Hardware assembly and prototype | ✅ Yes | Working Raspberry Pi prototype |
| **4** | Testing and documentation | ✅ Yes | Test results, report, demo |

```
 ┌──────────┐   frames   ┌──────────────────────────────────┐   alert   ┌────────┐
 │  Camera  │ ─────────▶ │  Raspberry Pi (runs model)       │ ────────▶ │ Buzzer │
 └──────────┘            │  Preprocess → Landmarks → Metrics│  (GPIO)   └────────┘
                         │  → Decision (state machine)      │
                         └──────────────────────────────────┘
```

---

# PHASE 1: Requirements, Calculations and Component Gathering

> **Goal:** Understand the problem fully, decide *how* drowsiness will be measured, and collect the components.
> **No hardware work happens in this phase.** You only buy the parts and keep them ready.

## 1.1 Problem understanding

- **Micro-sleep** is a brief (0.5–10 s) involuntary loss of attention. The eyes close and the head often drops.
- Normal blinks last **100–400 ms**. Eye closure of **≥ 1 second** is dangerous.
- The system must react **before** the vehicle drifts, so detection plus alarm must take **under ~300 ms** after the 1 s threshold.

## 1.2 Requirements

### Functional requirements
| ID | Requirement |
|---|---|
| FR1 | Detect the driver's face and eyes in real time from the camera |
| FR2 | Detect **eye closure ≥ 1.0 s** (micro-sleep) and trigger the buzzer |
| FR3 | Detect **head nodding / tilting** for ≥ 1 s and trigger the buzzer |
| FR4 | Count **blink rate** and **PERCLOS** to detect growing fatigue (warning beeps) |
| FR5 | Detect **yawning** as an early fatigue warning |
| FR6 | Warn if **no face is visible** for more than 2 s |
| FR7 | Work across **different light conditions**: bright daylight, shadows, dim cabin, night with street lights |
| FR8 | Work fully **offline** (no internet needed) |

### Non-functional requirements
| ID | Requirement |
|---|---|
| NFR1 | **≥ 15 FPS** on Raspberry Pi 4 (≥ 25 FPS on Pi 5) |
| NFR2 | Alarm latency **< 300 ms** after the threshold is crossed |
| NFR3 | False alarms **< 1 per hour** of normal driving |
| NFR4 | Starts automatically on power-up |
| NFR5 | Same code runs on the laptop and the Pi, with only a config change |

## 1.3 How things are calculated

All calculations use **facial landmarks**: 468 3D points on the face, given by **MediaPipe Face Mesh**.

### (a) Eye Aspect Ratio (EAR): is the eye open or closed?

```
      p2   p3
  p1 ●──────────● p4          EAR = ( |p2 − p6| + |p3 − p5| ) / ( 2 × |p1 − p4| )
      p6   p5
```
- MediaPipe indices. **Left eye:** `[362, 385, 387, 263, 373, 380]`. **Right eye:** `[33, 160, 158, 133, 153, 144]`.
- Final EAR is the average of both eyes.
- **Open eye ≈ 0.25–0.35**, **closed eye ≈ < 0.20**.
- **Threshold** is set per driver: `EAR_THRESHOLD = 0.75 × baseline_EAR`, where the baseline is measured in a 10 s calibration at startup.

### (b) Blink and micro-sleep detection (time based, not frame based)
| Eye closed duration | Meaning | Action |
|---|---|---|
| < 100 ms | Noise | Ignore |
| 100–400 ms | Normal blink | Count blink |
| 400 ms – 1 s | Long / slow blink (fatigue sign) | Count, raise fatigue score |
| **≥ 1 s** | **Micro-sleep** | 🔊 **ALARM** |

Durations are measured with timestamps, so the result is correct even if the FPS changes between laptop and Pi.

### (c) Blink rate
- Number of blinks in the last 60 s (sliding window).
- Normal is **15–20 / min**. More than **25 / min** or many long blinks indicates fatigue.

### (d) PERCLOS: percentage of eye closure
```
PERCLOS = (time eyes were closed in last 60 s) / 60 s
```
- **< 0.15**: alert
- **0.15–0.30**: drowsy, gives a warning beep
- **> 0.30**: very drowsy, triggers the alarm

### (e) Mouth Aspect Ratio (MAR): yawning
```
MAR = |upper lip(13) − lower lip(14)| / |left corner(78) − right corner(308)|
```
- **MAR > 0.6 for ≥ 1.5 s** counts as a yawn. **3 yawns in 5 min** gives a warning.

### (f) Head pose: nodding and tilting
- Take 6 landmarks: nose tip (1), chin (152), eye corners (33, 263), and mouth corners (61, 291).
- Read the **pitch** (nod), **yaw** (turn) and **roll** (tilt) angles directly from MediaPipe's 3D landmarks (forehead→chin and eye→eye axes). This replaced an earlier `solvePnP` fit, which underestimated angles and sometimes flipped sign.

| Condition | Meaning | Action |
|---|---|---|
| Pitch drops > 20° below baseline for ≥ 1 s | Head nodding down | 🔊 ALARM |
| \|Roll\| > 25° for ≥ 1.5 s | Head tilted / slumped | 🔊 ALARM |
| \|Yaw\| > 30° for ≥ 2 s | Looking away | Warning beep |

### (g) Smoothing
- An **Exponential Moving Average** removes jitter from EAR, MAR and the angles: `value = α·new + (1−α)·old`, with α ≈ 0.4.

### (h) Final decision: 3 levels
| Level | Trigger | Buzzer |
|---|---|---|
| 🟢 **OK** | Everything normal | Silent |
| 🟡 **WARNING** | PERCLOS 0.15–0.30, 3+ yawns, high blink rate, looking away, no face | Short beeps |
| 🔴 **CRITICAL** | Eyes closed ≥ 1 s, head nod ≥ 1 s, PERCLOS > 0.30 | **Continuous loud beep** |

## 1.4 Components to gather (buy only, no assembly yet)

| # | Component | Recommended model | Purpose | Approx. cost (₹) |
|---|---|---|---|---|
| 1 | **Raspberry Pi** | Raspberry Pi 4 Model B (4 GB) or Raspberry Pi 5 (4 GB), **with its official power adapter** | Runs the model | 5,000–8,000 |
| 2 | **Storage** | 32 GB microSD card (Class 10 / A1, SanDisk or Samsung) + card reader | OS + code + model | 400–600 |
| 3 | **Camera** | **USB webcam** (720p or 1080p, plug-and-play). *(A Pi ribbon camera also works with `camera: picamera2`)* | Captures the driver's face | 800–2,000 |
| 4 | **Buzzer** | **Active buzzer module (5 V, 3-pin: VCC, GND, I/O)**. The module has a built-in transistor, so it connects directly to GPIO | Alarm | 50–100 |
| 5 | **Connectors** | Female-to-female jumper wires (pack of 10–20) | Connects the buzzer to the GPIO pins | 50–100 |

> **Note:** We use a **USB webcam**, so no camera ribbon cable or camera drivers are needed. The same webcam works on the laptop and the Pi.

## 1.5 Phase 1 deliverables
- ✅ Requirements document (sections 1.1–1.2)
- ✅ Formulas and threshold table (section 1.3)
- ✅ System block diagram
- ✅ All 5 components purchased and kept aside

---

# PHASE 2: Build and Test the Model on the Laptop (No Hardware)

> **Goal:** Build the **complete** drowsiness detection software on the laptop using its webcam and recorded videos. Write it so that it:
> 1. **Behaves exactly the same on the Raspberry Pi**: only a config setting changes.
> 2. **Runs efficiently** on the Pi's limited CPU.
> 3. **Works in any light intensity**: bright, dark, uneven, backlit.

## 2.1 Laptop environment setup

```bash
# Python 3.11 recommended (same version as Raspberry Pi OS (Legacy, 64-bit) / Bookworm)
python -m venv venv
venv\Scripts\activate            # Windows
pip install mediapipe opencv-python numpy pyyaml pytest
pip freeze > requirements.txt
```

> Use **Python 3.11** on the laptop. The Pi runs **Raspberry Pi OS (Legacy, 64-bit)** (Bookworm), which also has Python 3.11, so both install the same package versions. (Trixie / 3.13 also works; `requirements.txt` handles it.)

## 2.2 Project structure (hardware-independent design)

```
IOT_PROJECT/
├── config/
│   ├── laptop.yaml          # camera: webcam, alarm: speaker, debug display ON
│   └── pi.yaml              # camera: webcam (USB), alarm: gpio buzzer, display OFF
├── src/
│   ├── main.py              # entry point: python src/main.py --config config/laptop.yaml
│   ├── camera/
│   │   ├── base.py          # Camera interface: start(), read(), stop()
│   │   ├── webcam.py        # OpenCV VideoCapture (laptop webcam + USB webcam on the Pi)
│   │   ├── picam.py         # Picamera2 (only for a ribbon camera; not used)
│   │   └── video_file.py    # Plays recorded .mp4 (for testing)
│   ├── alarm/
│   │   ├── base.py          # Alarm interface: set_level(OK/WARNING/CRITICAL)
│   │   ├── speaker.py       # Laptop: plays beep sound
│   │   ├── console.py       # Prints alarm (for automated tests)
│   │   └── gpio_buzzer.py   # Raspberry Pi: gpiozero Buzzer on GPIO18
│   ├── preprocess.py        # Light normalization (section 2.4)
│   ├── landmarks.py         # MediaPipe Face Mesh wrapper
│   ├── metrics.py           # EAR, MAR, PERCLOS, blink counter
│   ├── head_pose.py         # 3D landmarks → pitch, yaw, roll
│   ├── calibration.py       # 10 s baseline capture
│   ├── state_machine.py     # OK / WARNING / CRITICAL logic
│   └── utils.py             # EMA filter, timers, FPS counter, logger
├── tests/
│   ├── test_metrics.py
│   ├── test_state_machine.py
│   └── videos/              # Recorded test clips + labels
├── models/                  # (optional) eye_state.tflite
├── requirements.txt
└── README.md
```

### The key principle: hardware abstraction
The main logic **never** talks to the hardware directly. It only uses `Camera` and `Alarm` interfaces, and the config file decides which implementation is loaded:

```yaml
# config/laptop.yaml               # config/pi.yaml
camera: webcam                      camera: webcam   (USB webcam)
alarm:  speaker                     alarm:  gpio_buzzer
buzzer_pin: null                    buzzer_pin: 18
resolution: [640, 480]              resolution: [640, 480]
show_window: true                   show_window: false
```

```python
# main.py (simplified)
cam   = make_camera(cfg)     # webcam.py on both laptop and Pi (USB webcam)
alarm = make_alarm(cfg)      # speaker.py on laptop, gpio_buzzer.py on Pi
```

Imports such as `picamera2` and `gpiozero` are placed **inside** `picam.py` / `gpio_buzzer.py`, so the laptop never needs them installed.

**Result:** The detection code, thresholds and decisions are **100% identical** on the laptop and the Pi.

## 2.3 Step-by-step build order

| Step | Build | Test it by |
|---|---|---|
| 1 | `camera/webcam.py` + `video_file.py`: show live frames, FPS counter | See video with FPS on screen |
| 2 | `landmarks.py`: MediaPipe Face Landmarker, Tasks API (`num_faces=1`, VIDEO mode, 478 points) | Draw eye/mouth points on the face |
| 3 | `metrics.py`: EAR calculation | Print EAR, then blink and watch it drop below 0.2 |
| 4 | Blink and micro-sleep timer (time based) | Close eyes 1.5 s, see "MICRO-SLEEP" printed |
| 5 | `calibration.py`: 10 s baseline EAR + head angles | Threshold adapts to different people / glasses |
| 6 | Blink rate + PERCLOS (60 s sliding window) | Values shown on screen |
| 7 | MAR / yawn detection | Yawn, see yawn counter increase |
| 8 | `head_pose.py`: pitch / yaw / roll | Nod and tilt, angles change correctly |
| 9 | `utils.py`: EMA smoothing | Values stop jittering |
| 10 | `state_machine.py`: OK / WARNING / CRITICAL | Correct level shown for each action |
| 11 | `alarm/speaker.py`: beep on laptop | Hear short beeps (warning) / continuous beep (critical) |
| 12 | `preprocess.py`: light handling (section 2.4) | Works in dark and bright room |
| 13 | Optimization for the Pi (section 2.5) | FPS stays high under Pi-like limits |
| 14 | Unit + video tests (section 2.7) | All tests pass |

## 2.4 Making it work in any light intensity

Lighting is the biggest real-world problem: sun glare, shadows, tunnels, night driving. Handle it in `preprocess.py` before the frame goes to MediaPipe.

### (a) Measure the frame brightness
```python
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
mean_brightness = gray.mean()          # 0 (black) → 255 (white)
```

### (b) Adaptive correction based on brightness
| Brightness (mean) | Condition | Correction applied |
|---|---|---|
| < 60 | **Dark** (night, tunnel) | **Gamma correction** (γ ≈ 0.5) to brighten + **CLAHE** + light denoise |
| 60–180 | **Normal** | **CLAHE** only (fixes uneven light / shadows) |
| > 180 | **Very bright** (sun, glare) | **Gamma correction** (γ ≈ 1.5) to darken + CLAHE |

- **CLAHE** (Contrast Limited Adaptive Histogram Equalization) is applied on the **L channel of LAB** colour space. It boosts local contrast around the eyes without blowing out the image.
  ```python
  lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
  l, a, b = cv2.split(lab)
  l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
  frame = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
  ```
- **Gamma correction** uses a precomputed lookup table (`cv2.LUT`), which costs almost no CPU.
- Use **smoothing on brightness** (EMA) so the correction doesn't flicker frame to frame.

### (c) Camera-level settings
- Laptop: keep auto-exposure on.
- Pi (USB webcam): the webcam's own auto-exposure is used. In dim light some webcams lower their FPS to get a brighter image; this can be turned off with `v4l2-ctl` (see `docs/PHASE3.md`, troubleshooting).

### (d) Light-independent decisions
- **Per-driver calibration** (EAR threshold = 75% of the baseline) means the threshold adapts to how the eyes look in *current* lighting. Re-run calibration automatically if the brightness changes a lot for more than 30 s (e.g., day to night).
- If **face detection confidence is low** (very dark), fall back on **head pose** and give a "Low visibility" warning instead of false alarms.

### (e) Test across lights *without* special hardware
Create a **lighting test set** from your own recorded videos by synthetically changing the brightness:
```python
dark      = cv2.convertScaleAbs(frame, alpha=0.3, beta=0)    # very dark
bright    = cv2.convertScaleAbs(frame, alpha=1.8, beta=40)   # overexposed
noisy     = np.clip(frame + np.random.normal(0, 15, frame.shape), 0, 255).astype(np.uint8)  # low-light sensor noise
half_shad = frame.copy(); half_shad[:, :w//2] = (half_shad[:, :w//2] * 0.4).astype(np.uint8)  # side shadow
```
Also record real clips in: daylight near a window, a room with lights off and only a phone/monitor glow, backlight (window behind you), and yellow warm light.

> **Honest limit:** In **complete darkness** a normal camera can't see anything, so no software can fix that. Software handles dim, uneven and bright conditions. For pitch-black use, a later upgrade is a NoIR camera + IR LEDs (listed in Future Scope).

## 2.5 Making it efficient enough for the Raspberry Pi

The laptop is 3–5× faster than a Pi, so **design for the Pi from day one**:

| Technique | Why |
|---|---|
| Resolution **640×480** (or 480×360) | Fewer pixels to process |
| **Threaded camera capture**: grabber thread keeps only the latest frame | Never processes stale/queued frames |
| MediaPipe `max_num_faces=1`, **tracking mode** (`static_image_mode=False`) | Doesn't rerun full face detection every frame |
| Only compute what is needed (a few landmark indices) | Less math per frame |
| Gamma using **LUT**; CLAHE on one channel only | Cheap preprocessing |
| **No `imshow` on the Pi** (`show_window: false`) | Drawing windows is expensive |
| Avoid per-frame object allocation / logging | Lower CPU and memory |
| Time-based logic (timestamps) | Same behaviour at 15 FPS (Pi) or 30 FPS (laptop) |

### Simulate Pi performance on the laptop
- Run with `--max-fps 15` (sleep to cap FPS) and confirm the detection is still correct at that rate.
- Limit the process to **1–2 CPU cores** (Windows Task Manager → Set affinity, or `psutil.Process().cpu_affinity([0])`) and check the FPS stays acceptable.
- Log the **per-stage time** (preprocess / landmarks / metrics / decision). The total should be **< 30 ms per frame** on the laptop to be safe on the Pi.

## 2.6 (Optional) Custom eye-state model for extra robustness

If EAR alone fails in some conditions (glasses, very dim light), add a tiny CNN:
1. **Dataset:** MRL Eye Dataset (open/closed eye crops, includes IR and low-light images).
2. **Augmentation:** random brightness, contrast, gamma, blur and noise, which trains the model for **all light intensities**.
3. **Model:** a small CNN or MobileNetV3-Small with **48×48 grayscale** eye-crop input that outputs open/closed.
4. **Train** on the laptop or Google Colab, then **convert to TensorFlow Lite with int8 quantization** (≈ 100–500 KB, very fast on the Pi).
5. **Fuse** the signals: "eye closed" only if EAR is below the threshold **and** the CNN closed probability is above 0.6. Fewer false alarms.
6. Report accuracy, precision, recall, F1 and the confusion matrix.

## 2.7 Testing on the laptop

### Unit tests (`pytest`)
- EAR / MAR on known landmark coordinates give the expected values.
- The state machine, fed a synthetic EAR sequence (e.g., 1.2 s of low EAR), gives CRITICAL. 0.3 s of low EAR gives a blink only.
- Preprocessing: a dark frame brightens and a bright frame darkens.

### Video tests
Record **10–20 short clips** (yourself + friends), label them, and run the pipeline using `video_file.py` + `console.py` alarm:

| Clip | Expected |
|---|---|
| Normal driving posture, normal blinks | OK, no alarm |
| Eyes closed 1.5 s | CRITICAL |
| Slow blinks repeatedly | WARNING |
| Head nod down | CRITICAL |
| Yawning 3 times | WARNING |
| Turn head to side > 2 s | WARNING |
| With spectacles | Same results as without |
| Dark / bright / shadow versions (section 2.4e) | Same results as normal light |

Automate this with a script that prints a **pass/fail table**, and re-run it after every change.

## 2.8 Phase 2 deliverables
- ✅ Complete working software running on the laptop
- ✅ Two config files (`laptop.yaml`, `pi.yaml`), so the code is ready for hardware
- ✅ Light-adaptive preprocessing tested in dark / normal / bright
- ✅ All unit and video tests passing
- ✅ FPS / latency measurements under Pi-like limits
- ✅ (Optional) `eye_state.tflite` model + accuracy report

---

# PHASE 3: Hardware Assembly and Prototype

> **Goal:** Assemble the components, set up the Raspberry Pi, deploy the Phase 2 software, and get a working prototype.
>
> **Detailed, up-to-date steps (USB webcam, pendrive boot, buzzer): [`PHASE3.md`](PHASE3.md).** This section is the short overview.

## 3.1 Prepare the Raspberry Pi (storage + OS)
1. Insert the microSD card into the laptop. Open **Raspberry Pi Imager**.
2. Choose **Raspberry Pi OS (other)** → **Raspberry Pi OS (Legacy, 64-bit)** (Debian 12 Bookworm, Python 3.11, same as the laptop).
3. In settings (⚙): set the hostname (`drowsy-pi`), **enable SSH**, set the username/password, and Wi-Fi.
4. Flash, insert the card into the Pi, and power on.
5. Connect from the laptop: `ssh pi@drowsy-pi.local`
6. Update:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   ```

## 3.2 Connect the camera (USB webcam)
1. Plug the USB webcam into a **black USB 2.0 port** on the Pi (keep the blue ports for the boot pendrive).
2. Check it is detected:
   ```bash
   lsusb                        # webcam brand is listed
   ls /dev/video*               # /dev/video0 = the webcam
   sudo apt install -y fswebcam
   fswebcam -r 640x480 -S 30 --no-banner test.jpg   # take a test photo
   ```
   No drivers or config changes are needed. Full steps: `docs/PHASE3.md`.

## 3.3 Connect the buzzer (with jumper wires)

Use the **active buzzer module (3 pins)**:

| Buzzer module pin | Raspberry Pi pin |
|---|---|
| **VCC** | Pin 2 (5 V) *(or Pin 1 = 3.3 V if the module is 3.3 V)* |
| **GND** | Pin 6 (GND) |
| **I/O (signal)** | Pin 12 (**GPIO18**) |

```
 Raspberry Pi GPIO header (top-left part)
   Pin 1 (3V3)  ● ●  Pin 2 (5V)   ──── Buzzer VCC
   Pin 3        ● ●  Pin 4
   Pin 5        ● ●  Pin 6 (GND)  ──── Buzzer GND
   Pin 7        ● ●  Pin 8
   Pin 9        ● ●  Pin 10
   Pin 11       ● ●  Pin 12 (GPIO18) ── Buzzer I/O
```

> Some buzzer modules are **active-LOW** (they beep when the pin is LOW). If yours beeps at startup and goes silent when triggered, set `active_high=False` in `gpiozero.Buzzer`.

**Test the buzzer:**
```bash
python3 -c "from gpiozero import Buzzer; from time import sleep; b=Buzzer(18); b.on(); sleep(1); b.off()"
```

## 3.4 Install the software on the Pi
```bash
sudo apt install -y python3-gpiozero python3-lgpio python3-venv
git clone <your-repo-url> ~/IOT_PROJECT        # or copy with scp / WinSCP
cd ~/IOT_PROJECT
python3 -m venv --system-site-packages venv    # lets venv use apt's gpiozero
source venv/bin/activate
pip install -r requirements.txt                # mediapipe, numpy, pyyaml ...
```
> `requirements.txt` installs MediaPipe 0.10.21 on Python 3.11 (Bookworm Legacy, our Pi OS) and MediaPipe 1.1.1 on Python 3.13 (Trixie, fallback only). `landmarks.py` uses the MediaPipe **Tasks** FaceLandmarker (`models/face_landmarker.task`), which both versions support; the old `mp.solutions.face_mesh` API no longer exists in 1.x.
> If `mediapipe` fails to install on the Pi, check that you're using the 64-bit OS. As a fallback, use **TFLite Face Mesh** or **dlib 68-landmarks** behind the same `landmarks.py` interface, so no other code changes.

## 3.5 Run the prototype
```bash
python src/main.py --config config/pi.yaml
```
- The **only** difference from the laptop is the config file. The camera stays `webcam.py` (USB webcam) and the alarm becomes `gpio_buzzer.py`.
- On start: 1 short beep means the system is armed. Then the 10 s calibration runs (look straight ahead).
- Check the logs for **FPS (target ≥ 15)**, CPU usage, and temperature (`vcgencmd measure_temp`).

### If the FPS is too low on the Pi
1. Reduce the resolution to 480×360 or 320×240.
2. Run head pose every 2nd frame (EAR still every frame).
3. Make sure `show_window: false`.
4. Check for thermal throttling (`vcgencmd get_throttled`). A small heatsink helps.

## 3.6 Auto-start on boot (makes it a real device)
```ini
# /etc/systemd/system/drowsy.service
[Unit]
Description=Driver Drowsiness Detection
After=multi-user.target

[Service]
User=pi
WorkingDirectory=/home/pi/IOT_PROJECT
ExecStart=/home/pi/IOT_PROJECT/venv/bin/python src/main.py --config config/pi.yaml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now drowsy.service
journalctl -u drowsy -f          # view live logs
```
Now the Pi powers on and runs detection automatically, with no laptop needed.

## 3.7 Physical prototype setup
- Mount the camera **in front of the driver, slightly below eye level, tilted up ~15°**, with the face filling ~30–50% of the frame.
- Keep the Pi in a case or box. Route the buzzer where it is clearly audible.
- Power with the official adapter (bench) or a good car USB-C adapter (in vehicle, 5 V 3 A).

## 3.8 Phase 3 deliverables
- ✅ Raspberry Pi with OS, USB webcam and buzzer connected
- ✅ Phase 2 software running on the Pi using `pi.yaml`
- ✅ Auto-start on boot
- ✅ Working prototype: closing eyes for 1 s sounds the buzzer

---

# PHASE 4: Testing and Documentation

> **Goal:** Prove the prototype works reliably and document everything.

## 4.1 Functional testing on the prototype

| # | Test scenario | Expected result | Pass/Fail |
|---|---|---|---|
| 1 | Normal posture, normal blinking (5 min) | No alarm | |
| 2 | Eyes closed 0.5 s | No alarm (blink) | |
| 3 | Eyes closed 1.5 s | 🔊 Continuous alarm | |
| 4 | Repeated slow blinks | Warning beeps | |
| 5 | Head nods forward | 🔊 Alarm | |
| 6 | Head tilts to side and stays | 🔊 Alarm | |
| 7 | 3 yawns within 5 min | Warning beeps | |
| 8 | Looks away > 2 s | Warning beeps | |
| 9 | Checks mirror < 2 s | No alarm | |
| 10 | Face leaves the frame | "No face" warning | |
| 11 | Wearing spectacles | Same as without | |
| 12 | Eyes open again after alarm | Alarm stops after ~2 s | |
| 13 | Power cut and restart | Auto-starts, beeps "armed" | |
| 14 | Wi-Fi off | Works normally (offline) | |

## 4.2 Lighting tests (real conditions)

| Light condition | How to create it | Expected |
|---|---|---|
| Bright daylight | Near a window / outdoors in shade | Works |
| Direct sun on face | Sunlight / strong lamp from side | Works (gamma + CLAHE) |
| Backlight | Window behind the driver | Works |
| Normal indoor | Room light | Works |
| Dim | Lights off, only a phone screen / street light | Works |
| Changing light | Switch lights on/off during a run | Recovers within a few seconds, no false alarm |

## 4.3 Measurements to report

| Metric | How to measure | Target |
|---|---|---|
| **FPS** on Pi | Logged by FPS counter | ≥ 15 |
| **Alarm latency** | Log timestamp at eye close → buzzer on (minus 1 s threshold) | < 300 ms |
| **Detection accuracy** | Run labelled test clips: precision, recall, F1 | > 90% |
| **False alarm rate** | 30–60 min normal sitting/driving simulation | < 1 / hour |
| **CPU usage / temperature** | `top`, `vcgencmd measure_temp` | < 80 °C |
| **Boot-to-ready time** | Power on → "armed" beep | < 60 s |
| **Different users** | Test on 5+ people (glasses, skin tones, eye shapes) | Consistent results |

> ⚠️ **Safety:** Never test by actually driving while drowsy. Test in a **parked car** or at a desk while watching a driving video.

## 4.4 Documentation

### Project report structure
1. **Abstract**
2. **Introduction and Problem Statement**: road accidents due to drowsiness, who is affected
3. **Literature Review**: EAR paper, PERCLOS, existing systems
4. **Requirements** (from Phase 1)
5. **System Architecture**: block diagram, flowchart, state diagram
6. **Hardware Design**: component list, wiring diagram (draw it in **Fritzing**), photos
7. **Software Design**: module structure, hardware abstraction, config files
8. **Algorithms**: EAR, blink/micro-sleep timing, PERCLOS, MAR, head pose, light-adaptive preprocessing
9. **Implementation**: key code snippets
10. **Testing and Results**: test tables, accuracy, FPS, latency, lighting results, graphs (EAR vs time showing a blink and a micro-sleep)
11. **Limitations**: complete darkness, sunglasses, extreme head angles
12. **Future Scope**
13. **Conclusion**
14. **References**

### Other documentation
- **README.md**: setup steps for the laptop and the Pi, how to run, how to change the config
- **Code comments + docstrings** on every module
- **Demo video (2–3 min):** live overlay on the laptop (EAR, angles, state) + Pi prototype buzzing on eye closure
- **Presentation slides** for the viva

## 4.5 Phase 4 deliverables
- ✅ Filled test tables with results
- ✅ Performance and accuracy measurements
- ✅ Final project report
- ✅ README, demo video, presentation

---

## Suggested Timeline

| Week | Phase | Work |
|---|---|---|
| 1 | Phase 1 | Requirements, formulas, thresholds, order components |
| 2 | Phase 2 | Environment setup, camera + landmarks + EAR + blink/micro-sleep |
| 3 | Phase 2 | Calibration, PERCLOS, MAR, head pose, state machine, alarm |
| 4 | Phase 2 | Light-adaptive preprocessing, Pi-efficiency optimization, (optional) CNN |
| 5 | Phase 2 | Unit + video + lighting tests, bug fixes |
| 6 | Phase 3 | Pi setup, camera + buzzer wiring, deploy, auto-start, prototype |
| 7 | Phase 4 | Prototype testing, measurements, threshold tuning |
| 8 | Phase 4 | Report, README, demo video, presentation |

---

## Future Scope
- **NoIR camera + 850 nm IR LEDs** for driving in complete darkness
- **MQTT + cloud dashboard** (Node-RED / Grafana) for fleet companies to monitor drivers remotely
- **GPS** to log where drowsiness events happen
- **Telegram / SMS alert** to the fleet manager on critical events
- Vibration motor in the seat / steering for haptic alerts
- Face recognition for per-driver profiles

## References
1. T. Soukupová and J. Čech, "Real-Time Eye Blink Detection using Facial Landmarks," CVWW 2016.
2. W. Wierwille et al., "Research on Vehicle-Based Driver Status/Performance Monitoring" (PERCLOS), NHTSA.
3. Google MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
4. Raspberry Pi Picamera2 manual: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
5. gpiozero documentation: https://gpiozero.readthedocs.io
6. MRL Eye Dataset: http://mrl.cs.vsb.cz/eyedataset

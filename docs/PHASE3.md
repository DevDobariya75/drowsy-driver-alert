# Phase 3: Build the Hardware Prototype (step by step)

> **Goal:** run our drowsiness software on a **Raspberry Pi 4** with a **USB webcam** and a
> **buzzer**. When the driver gets sleepy, the buzzer beeps. **No laptop is needed** at the end.
>
> **How to use this guide:** do the steps **in order**. Each step ends with a ✅ **Check**.
> Only go to the next step when the check is OK.

**Time needed:** about 2–3 hours the first time (most of it is waiting for downloads).

---

## Contents

1. [Parts list](#1-parts-list)
2. [Safety rules](#2-safety-rules)
3. [Test the webcam on the laptop first (optional)](#3-test-the-webcam-on-the-laptop-first-optional)
4. [Install the OS on the pendrive](#4-install-the-os-on-the-pendrive)
5. [Connect the buzzer](#5-connect-the-buzzer)
6. [Plug everything in and power on](#6-plug-everything-in-and-power-on)
7. [Connect to the Pi from the laptop (SSH)](#7-connect-to-the-pi-from-the-laptop-ssh)
8. [Update the Pi and check Python](#8-update-the-pi-and-check-python)
9. [Test the USB webcam](#9-test-the-usb-webcam)
10. [Test the buzzer](#10-test-the-buzzer)
11. [Copy the project to the Pi](#11-copy-the-project-to-the-pi)
12. [Install the software](#12-install-the-software)
13. [Place the webcam](#13-place-the-webcam)
14. [Run the system and test every alarm](#14-run-the-system-and-test-every-alarm)
15. [Measure performance (for the report)](#15-measure-performance-for-the-report)
16. [Start automatically on power-on](#16-start-automatically-on-power-on)
17. [Build the final prototype](#17-build-the-final-prototype)
18. [Shut down and update code](#18-shut-down-and-update-code)
19. [Troubleshooting](#19-troubleshooting)
20. [Checklist and deliverables](#20-checklist-and-deliverables)

---

## 1. Parts list

### 1.1 Main parts

| Part | What it does | Notes |
|---|---|---|
| **Raspberry Pi 4 Model B (8 GB)** | The "brain". Runs our program | Our program uses less than 1 GB RAM |
| **USB webcam** | The "eye". Watches the driver's face | Any normal USB webcam (720p or 1080p). It just plugs into a USB port |
| **Buzzer module (3 pins: `S`, middle, `-`)** | The "voice". Beeps when the driver is sleepy | Connects to the Pi's GPIO pins |

### 1.2 Extra items

| Item | Spec | Why |
|---|---|---|
| **Power supply** | **5 V, 3 A, USB-C** (official Raspberry Pi adapter is best) | A phone charger is often too weak → crashes and slow speed |
| **USB pendrive** | **32 GB**, USB 3.0 if possible | The Pi starts from it. It holds the OS and our project. **It will be fully erased**, so back up its files first |
| **3 jumper wires** | **Female-to-female**, ~20 cm | Buzzer → Pi pins |
| **Wi-Fi** | Home Wi-Fi or **phone hotspot** (2.4 GHz is safest) | Laptop and Pi must be on the **same** Wi-Fi |
| **Heatsinks or a case with fan** | Any Pi 4 set | The Pi gets hot when it works hard. Hot = slow |
| *(Only if USB boot fails)* microSD card | Any size ≥ 8 GB | Used **once** to update the Pi (step 4.3) |
| *(For a car)* Car USB-C adapter | **5 V 3 A** | Power in a vehicle |

**Software on the laptop (Windows 11):**
- **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>
- **PowerShell** (already on Windows). It has `ssh` and `scp` built in.

### 1.3 Which port is which on the Pi

Hold the Pi with the **40 GPIO pins along the top edge**:

```
              40 GPIO pins  (TOP edge)
   ┌─[Pin1]●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●───────────┐
   │                                                  ┌──────┤
   │                                                  │ ETH  │  ← Ethernet (not used)
   │        ┌────────┐                                ├──────┤
   │        │  CPU   │   [RAM]                        │USB3.0│  ← BLUE ports  → pendrive
   │        └────────┘                                ├──────┤
   │                                                  │USB2.0│  ← BLACK ports → webcam
   │                                                  └──────┤
   │   [USB-C]  [HDMI0] [HDMI1]  [CAMERA]  (A/V)             │
   └──────────────────────────────────────────────────────────┘
      POWER IN                 (not used)   (BOTTOM edge)
```

- **Blue USB ports (USB 3.0)** → put the **pendrive** here (it is faster).
- **Black USB ports (USB 2.0)** → put the **webcam** here. Webcams are USB 2.0 devices, so they lose nothing.
- **USB-C** → power.
- The flat **CAMERA** and **DISPLAY** connectors are **not used** (they are for ribbon cameras).

### 1.4 About the buzzer

There are two kinds of this buzzer module. They look the same but need different code:

| Kind | When you switch it ON | What to do |
|---|---|---|
| **Active** | Loud **beeeep** | Nothing. Our code already works |
| **Passive** | Only a small **click** | Small code change (step 10.3) |

You will find out which one you have in **step 10**.

---

## 2. Safety rules

1. **Unplug the power** before you connect or remove any wire on the GPIO pins.
2. **Never connect a 5 V pin (pin 2 or 4) to another pin.** It can kill the Pi. GPIO pins are **3.3 V only**.
3. **Never touch 5 V or 3.3 V to GND.**
4. Touch something metal before you hold the Pi (removes static).
5. Hold the board by its **edges**.
6. Put the Pi on wood, plastic or cardboard, **never on metal**.
7. **Never pull out the power or the pendrive while the Pi is on.** Shut down first (step 18).

USB devices (webcam, pendrive) are safe to plug in at any time, but it's best to plug them in before power-on.

---

## 3. Test the webcam on the laptop first (optional)

This takes 2 minutes and proves the webcam works before you touch the Pi.

1. Plug the USB webcam into the laptop.
2. Open the Windows **Camera** app. Choose the USB webcam (the switch-camera button). You should see your face.
3. To test it with our program, open `config/laptop.yaml` and add one line:
   ```yaml
   camera_index: 1      # 0 = built-in laptop camera, 1 = USB webcam
   ```
4. Run:
   ```powershell
   cd "E:\Sem\Sem 7\IOT LAB\IOT_PROJECT\drowsy-driver-alert"
   venv\Scripts\activate
   python src/main.py --config config/laptop.yaml
   ```
5. **Remove the `camera_index: 1` line** again when you are done.

✅ **Check:** the window shows the picture from the USB webcam and the alarm works when you close your eyes.

---

## 4. Install the OS on the pendrive

The Pi will start from the **USB pendrive** (no microSD card needed).

### 4.1 Write the OS

1. Install and open **Raspberry Pi Imager** on the laptop.
2. Back up the pendrive, then plug it into the laptop.
3. **CHOOSE DEVICE** → **Raspberry Pi 4**.
4. **CHOOSE OS** → **Raspberry Pi OS (64-bit)**. Both versions work:
   - **Debian 13 "Trixie"** (Python 3.13): the current default. Installs MediaPipe 1.1.1.
   - **Debian 12 "Bookworm"** (Python 3.11): under *Raspberry Pi OS (other)* → *Legacy, 64-bit*. Installs MediaPipe 0.10.21.
   - `requirements.txt` picks the right package versions by itself. **It must be the 64-bit OS** (32-bit has no MediaPipe).
   - **Lite** (no desktop) is best. It is faster, and we control the Pi from the laptop anyway.
5. **CHOOSE STORAGE** → select the **pendrive** (about 32 GB). Check the size so you don't erase another drive.
6. **NEXT** → **EDIT SETTINGS**:
   - **General** tab:
     - Hostname: `drowsy-pi`
     - Username: `pi`, Password: something you will remember (**write it down**)
     - Wireless LAN: your Wi-Fi / hotspot name and password, country **IN**
     - Time zone `Asia/Kolkata`, keyboard `us`
   - **Services** tab: ✅ **Enable SSH** → *Use password authentication*
   - **SAVE**.
7. **YES** → **YES** (erases the pendrive).
8. Wait for **"Write Successful"** (5–20 minutes). Remove the pendrive.
   If Windows says *"You need to format the disk"*, click **Cancel**. This is normal.

✅ **Check:** Imager says **Write Successful**.

> **Phone hotspot tip:** turn on **"Maximise compatibility" / 2.4 GHz**, and use a simple name and password (no emojis).

### 4.2 Does the Pi start from USB?

Most Pi 4 boards made after 2020 start from USB automatically when no microSD card is inserted.
**Just try it** in step 6. Only if it does not start, do step 4.3.

### 4.3 Only if the Pi does not start from the pendrive

Signs: the green light blinks in a **repeating pattern**, or nothing happens, and the Pi never shows up after 5 minutes.

1. In Raspberry Pi Imager: **CHOOSE DEVICE** → Raspberry Pi 4 → **CHOOSE OS** → **Misc utility images** →
   **Bootloader (Pi 4 family)** → **USB Boot**.
2. **CHOOSE STORAGE** → a **microSD card** (it gets erased) → **Write**.
3. Put the microSD card in the Pi (no pendrive), power on, wait ~10 s until the green light blinks fast and steadily.
4. Unplug power, **remove the microSD card**, plug in the pendrive, and power on again.
   This is a one-time fix.

---

## 5. Connect the buzzer

> Pi **unplugged**.

### 5.1 Find the pins

With the GPIO pins along the **top edge**:

- **Pin 1** is at the **left end**, in the **lower row** (the row closer to the middle of the board).
- Lower row = **odd** pins: 1, 3, 5, 7 …
- Upper row (along the board edge) = **even** pins: 2, 4, 6, 8 …

```
                     board edge (top)
 upper row (even):   2    4    6    8   10   12
                    5V   5V  GND             GPIO18
                     ●    ●    ●    ●    ●    ●   ...
                     ●    ●    ●    ●    ●    ●   ...
 lower row (odd):    1    3    5    7    9   11
                   3.3V
                 ◀ left end
```

### 5.2 Wiring

| Buzzer pin | Wire colour (suggestion) | Pi pin | Where |
|---|---|---|---|
| **`S`** (signal) | Yellow | **Pin 12** (GPIO18) | upper row, **6th** from left |
| **middle** (`+`) | Red | **Pin 1** (3.3 V) | lower row, **1st** from left |
| **`-`** (GND) | Black | **Pin 6** (GND) | upper row, **3rd** from left |

```
   Buzzer module                       Raspberry Pi 4
  ┌─────────────┐
  │  S  ●───────┼──── yellow ──────▶  Pin 12  (GPIO18)
  │ (+) ●───────┼──── red ─────────▶  Pin 1   (3.3 V)
  │  -  ●───────┼──── black ───────▶  Pin 6   (GND)
  └─────────────┘
```

- We use **3.3 V** (not 5 V) because it is always safe for the Pi. The buzzer is still loud enough.
- "GPIO18" is the name the chip uses for **physical pin 12**. Our config says `buzzer_pin: 18`, which means GPIO18, **not** pin 18.

Count the pins **twice** with your finger. Make sure no wire touches the next pin.

✅ **Check:** S → pin 12, middle → pin 1, − → pin 6. **Nothing on pin 2 or pin 4.**

---

## 6. Plug everything in and power on

1. **No microSD card** in the slot under the board.
2. Plug the **pendrive** into a **blue** USB port.
3. Plug the **USB webcam** into a **black** USB port.
4. Plug the **5 V 3 A** power supply into **USB-C**.
5. Watch the lights:
   - **Red** = power OK (stays on).
   - **Green** = the Pi is reading the pendrive (flickers).
6. Wait **2–4 minutes**. The first start takes longer (it sets itself up and joins Wi-Fi).
   If nothing happens after 5 minutes, see step **4.3**.

✅ **Check:** red light on, green light flickered for a while.

---

## 7. Connect to the Pi from the laptop (SSH)

SSH lets you type commands on the Pi from the laptop. Open **PowerShell** on the laptop:

```powershell
ping drowsy-pi.local
ssh pi@drowsy-pi.local
```

- First time: type `yes` and press Enter.
- Type your password. **Nothing shows while you type.** That is normal. Press Enter.

✅ **Check:** the prompt changes to `pi@drowsy-pi:~ $`. You are now typing **on the Pi**.

> **In the rest of this guide:**
> `bash` boxes = type **on the Pi** (inside SSH).
> `powershell` boxes = type **on the laptop**.
> Type `exit` to leave SSH.

**If `drowsy-pi.local` is not found:**
1. Wait 2 more minutes and try again.
2. Check the laptop is on the **same** Wi-Fi / hotspot.
3. Open your router page or the phone hotspot's *Connected devices* list. Find `drowsy-pi` and its IP
   (for example `192.168.43.57`). Then use `ssh pi@192.168.43.57`.
4. Still nothing → the Wi-Fi name or password was wrong. Write the OS again (step 4).

---

## 8. Update the Pi and check Python

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```
The connection closes. Wait 1 minute, connect again (`ssh pi@drowsy-pi.local`), then:

```bash
python3 --version
uname -m
cat /etc/os-release | grep VERSION_CODENAME
lsblk
```

✅ **Check:**
- `Python 3.13.x` (Trixie) or `Python 3.11.x` (Bookworm). Both are fine
- `aarch64` (means 64-bit). **Must be aarch64**: if you see `armv7l`, write the 64-bit OS again (step 4)
- `VERSION_CODENAME=trixie` or `bookworm`
- `lsblk` shows the pendrive as **`sda`** (~29 G). This means the Pi is running from the pendrive.

---

## 9. Test the USB webcam

### 9.1 Is the webcam detected?

```bash
lsusb
ls /dev/video*
```

✅ **Check:**
- `lsusb` shows a line with your webcam's brand (e.g. *Logitech*, *Microdia*, *Sonix*, or *"USB Camera"*).
- `ls /dev/video*` shows **`/dev/video0`** (often also `/dev/video1`).

> The Pi also has its own `/dev/video10`, `/dev/video11` … These are **not** cameras; ignore them.
> If you see **no** `/dev/video0`, unplug the webcam, plug it into another black port, and try again.

### 9.2 Get more details (optional but useful)

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext | grep -E "MJPG|YUYV|640x480"
```

✅ **Check:** your webcam is listed under `/dev/video0`, and `640x480` is in the list.
Our program uses **640 × 480**. Almost every webcam supports it.

> If your webcam is on a different number (e.g. `/dev/video2`), write that number in
> `config/pi.yaml` as `camera_index: 2` later (step 11).

### 9.3 Take a test photo

```bash
sudo apt install -y fswebcam
fswebcam -d /dev/video0 -r 640x480 -S 30 --no-banner ~/test.jpg
```
(`-S 30` skips the first 30 frames, so the webcam has time to adjust brightness.)

Copy the photo to the laptop and open it:
```powershell
scp pi@drowsy-pi.local:~/test.jpg .
start test.jpg
```

✅ **Check:**
- Sit where the driver sits, about **50–70 cm** from the webcam.
- Your face is **clear and sharp**. Both eyes can be seen.
- The picture is **the right way up**. If it's upside down, turn the webcam over.
- The picture is not too dark. If it is dark, add light in front of the face (not behind).

### 9.4 Low-light check

Turn off the room light (keep a small lamp or phone screen on) and take the photo again.
- If the face is still visible → our software (gamma + CLAHE) can handle it.
- If the photo is black → this webcam has no night vision. Add a small cabin light.
  Write this down for the Phase 4 lighting tests.

---

## 10. Test the buzzer

### 10.1 Simple ON/OFF test

```bash
python3 -c "from gpiozero import Buzzer; from time import sleep; b = Buzzer(18); b.on(); sleep(2); b.off(); print('done')"
```

| What you hear | Meaning | What to do |
|---|---|---|
| Loud **beeeep** for 2 s | **Active** buzzer | ✅ Nothing. Go to step 11 |
| Beeps **all the time**, goes **quiet** during the test | **Active-LOW** buzzer | Do step 10.2 |
| Only a **click**, no tone | **Passive** buzzer | Do step 10.3 |
| Nothing at all | Wiring problem | Check step 5 again (S on **pin 12**) |

### 10.2 Active-LOW buzzer (only if needed)

After step 11, add this line to `config/pi.yaml`:
```yaml
buzzer_active_high: false
```

### 10.3 Passive buzzer (only if needed)

A passive buzzer needs a fast ON/OFF signal (a tone) to make sound. Test 4 tones:

```bash
python3 -c "
from gpiozero import PWMOutputDevice
from time import sleep
b = PWMOutputDevice(18, frequency=2000)
for f in (1000, 2000, 2700, 3500):
    b.frequency = f; b.value = 0.5; print('tone', f, 'Hz'); sleep(0.7)
b.off(); b.close()
"
```

✅ **Check:** you hear 4 tones. Note which one is the **loudest** (usually 2000–2700 Hz).

Our code only switches the buzzer ON/OFF, so a passive buzzer would only click. Make these
**3 small changes on the laptop**:

**(a)** Replace `src/alarm/gpio_buzzer.py` with:

```python
"""Raspberry Pi alarm: buzzer module on a GPIO pin (gpiozero, Pi-only).

buzzer_type: active  -> simple ON/OFF (module has its own oscillator)
buzzer_type: passive -> square wave at buzzer_freq Hz (KY-006 style modules)"""
from .base import Alarm


class GpioBuzzerAlarm(Alarm):
    def __init__(self, pin: int = 18, active_high: bool = True,
                 buzzer_type: str = "active", freq: int = 2500):
        self.passive = buzzer_type == "passive"
        if self.passive:
            from gpiozero import PWMOutputDevice  # Pi-only dependency
            self.buzzer = PWMOutputDevice(pin, active_high=active_high, frequency=freq)
        else:
            from gpiozero import Buzzer  # Pi-only dependency
            # Some modules beep when the pin is LOW: set buzzer_active_high: false.
            self.buzzer = Buzzer(pin, active_high=active_high)
        super().__init__()

    def _sound(self, on, seconds):
        if self.passive:
            self.buzzer.value = 0.5 if on else 0  # 50% duty = loudest square wave
        elif on:
            self.buzzer.on()
        else:
            self.buzzer.off()
        self._wait(seconds)

    def close(self):
        super().close()
        self.buzzer.close()
```

**(b)** In `src/alarm/__init__.py`, change the `gpio_buzzer` part to:

```python
    if kind == "gpio_buzzer":
        from .gpio_buzzer import GpioBuzzerAlarm
        return GpioBuzzerAlarm(cfg.get("buzzer_pin", 18), cfg.get("buzzer_active_high", True),
                               cfg.get("buzzer_type", "active"), cfg.get("buzzer_freq", 2500))
```

**(c)** Add to `config/pi.yaml` (use your loudest tone):

```yaml
buzzer_type: passive
buzzer_freq: 2500
```

Then run `python -m pytest -q` on the laptop to make sure nothing broke, and copy the files in step 11.

---

## 11. Copy the project to the Pi

### 11.1 What to copy

| Copy | Why |
|---|---|
| `src/` | The program code |
| `config/` | Settings. `pi.yaml` already says **camera: webcam** and **alarm: gpio_buzzer** |
| `models/eye_state.onnx` | The trained eye model (~288 KB) |
| `models/face_landmarker.task` | MediaPipe's face model (~3.7 MB). **Required**: finds the 478 face points |
| `models/eye_state.report.json` | Model accuracy numbers (optional) |
| `requirements.txt` | List of Python packages |
| `tests/` | To run the tests on the Pi |
| `README.md`, `docs/` | Documentation (optional) |

**Do not copy:** `venv/` (Windows only), `training/` (very big, not needed on the Pi),
`logs/`, `__pycache__/`, `.pytest_cache/`, old models `models/eye_state_v1/v2/v3.*`.

### 11.2 Copy with `scp`

On the **Pi**:
```bash
mkdir -p ~/drowsy-driver-alert/models ~/drowsy-driver-alert/logs
```

On the **laptop**:
```powershell
cd "E:\Sem\Sem 7\IOT LAB\IOT_PROJECT\drowsy-driver-alert"
scp -r src config tests docs requirements.txt README.md pi@drowsy-pi.local:~/drowsy-driver-alert/
scp models/eye_state.onnx models/eye_state.report.json models/face_landmarker.task pi@drowsy-pi.local:~/drowsy-driver-alert/models/
```
(It asks for the Pi password each time.)

On the **Pi**, delete the Windows cache files:
```bash
find ~/drowsy-driver-alert -name "__pycache__" -type d -exec rm -rf {} +
```

> **Other way:** if the project is on GitHub: `git clone https://github.com/<you>/drowsy-driver-alert.git ~/drowsy-driver-alert`

✅ **Check (on the Pi):**
```bash
cd ~/drowsy-driver-alert
ls
ls -lh models
grep camera config/pi.yaml
```
You should see the folders `config docs logs models src tests`, the files `eye_state.onnx` and
`face_landmarker.task`, and **`camera: webcam`**.

---

## 12. Install the software

```bash
sudo apt install -y python3-gpiozero python3-lgpio python3-venv python3-pip libportaudio2
cd ~/drowsy-driver-alert
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

What this does, in simple words:
- `python3-gpiozero` + `python3-lgpio` → control the buzzer pins. These **must come from apt** (not pip).
- `venv` → a separate box for our Python packages.
- `--system-site-packages` → lets the box also see the apt packages (gpiozero).
- `libportaudio2` → a sound library that MediaPipe 1.x loads (via `sounddevice`). Harmless on Bookworm.
- `pip install -r requirements.txt` → installs MediaPipe, OpenCV, NumPy and the rest. Takes **5–15 minutes**.
  It picks MediaPipe 1.1.1 + NumPy 2 on Python 3.13 (Trixie) and MediaPipe 0.10.21 + NumPy 1.26 on Python 3.11 (Bookworm).
- The webcam needs **nothing extra**: OpenCV talks to it directly.

> **Every time you log in again**, run: `cd ~/drowsy-driver-alert && source venv/bin/activate`.
> You'll see `(venv)` at the start of the line.

✅ **Check:**
```bash
python -c "import mediapipe, cv2, numpy, yaml; print('mediapipe', mediapipe.__version__, '| opencv', cv2.__version__, '| numpy', numpy.__version__)"
python -c "from gpiozero import Buzzer; print('buzzer lib OK')"
python -c "import cv2; n = cv2.dnn.readNetFromONNX('models/eye_state.onnx'); print('eye model OK')"
python -c "from src.landmarks import FaceLandmarker; FaceLandmarker().close(); print('face model OK')"
python -c "import cv2; c = cv2.VideoCapture(0); ok, f = c.read(); print('webcam OK', f.shape if ok else 'NO FRAME'); c.release()"
python -m pytest -q
```
Expected:
```
mediapipe 1.1.1 | opencv 4.11.0 | numpy 2.x          (Bookworm: mediapipe 0.10.21 | ... | numpy 1.26.4)
buzzer lib OK
eye model OK
face model OK
webcam OK (480, 640, 3)
79 passed
```

If the webcam line says `NO FRAME`, see step 19.

### 12.1 Video test (no webcam needed)

This checks the whole program on the Pi using a recorded clip:
```bash
python src/main.py --config config/pi.yaml --video tests/videos/WIN_20261013_18_27_52_Pro.mp4 --csv logs/pi_video.csv
```
✅ **Check:** the log shows `Armed. Calibrating ...`, then `Calibrated`, then `FPS ...` lines.
The buzzer beeps at the sleepy parts of the clip. Press **Ctrl + C** to stop.

---

## 13. Place the webcam

Good placement matters more than any setting. A bad angle = false alarms.

| Rule | Value |
|---|---|
| Distance from face | **50–70 cm** |
| Height | **A little below eye level** (on the dashboard or a small stand) |
| Angle | Tilted **up a little** (10–15°) towards the face |
| Direction | **Straight in front** of the driver, not from the side |
| Framing | Face fills about **⅓ of the picture**. Both eyes visible |
| Light | **No bright window or lamp behind** the driver. Light from the front is best |

How to mount it:
1. Most webcams have a **clip**. Clip it on the laptop screen, a box, or a phone holder on the dashboard.
   If it has a tripod screw hole, a small tripod works well.
2. Keep the USB cable loose (no sharp bends). Tape it down so it can't be pulled out.
3. Take a test photo (step 9.3) and adjust until the face is in the middle and sharp.

✅ **Check:** from the driver's seat: face in the middle, sharp, both eyes clear, no bright light behind.

---

## 14. Run the system and test every alarm

```bash
cd ~/drowsy-driver-alert
source venv/bin/activate
python src/main.py --config config/pi.yaml --csv logs/pi_run.csv
```

### 14.1 What happens when it starts

1. **Double beep** → the system is ready (and the buzzer works).
2. Log: `Armed. Calibrating for 10s - look straight ahead.`
   → **Sit normally and look straight ahead for 10 seconds.** Blink normally.
3. Log: `Calibrated: ...` → the system has learned **your** normal eyes and head position.
4. Every few seconds: `FPS 15.3 | ms/frame: ...` → how fast it is running.

There is **no video window** on the Pi. Everything is in the log.

### 14.2 Alarm sounds

| Level | Sound | Meaning |
|---|---|---|
| OK | Silent | Driver is alert |
| **WARNING** | 3 fast beeps, pause, repeat | Early tiredness or not looking at the road |
| **CRITICAL** | Fast pulsing beeps until you recover | Eyes closed, head dropped, head tilted |

### 14.3 Test each case (in this order)

Wait ~10 s in the normal position between tests. Write the results in the table in step 15.3.

| # | What you do | Expected alarm | After about |
|---|---|---|---|
| 1 | Sit normally, blink normally for 60 s | **Silent** (no false alarm) | — |
| 2 | **Close both eyes** and keep them closed | CRITICAL | **1 s** |
| 3 | Open your eyes | Alarm stops | 2 s |
| 4 | **Drop your head forward** (chin to chest), eyes closed | CRITICAL | **0.5 s** |
| 5 | Head **hanging** forward, eyes open | CRITICAL | 1 s |
| 6 | **Tilt your head to a shoulder** | CRITICAL | 1 s |
| 7 | **Turn your head to the side** (look out of the side window) | WARNING | 2 s |
| 8 | **Leave the camera view** or cover the webcam | WARNING | 2 s |
| 9 | Look **down at your lap** with eyes open (like using a phone) | WARNING | 4 s |
| 10 | **Yawn** widely 3 times within 5 minutes | WARNING | after the 3rd yawn |
| 11 | Wear **glasses** and repeat test 2 | CRITICAL | 1 s |
| 12 | Repeat tests 1–2 with the room lights **dimmed** | Same as above | — |

Stop with **Ctrl + C**. The buzzer turns off.

✅ **Check:** tests 1–8 work as in the table. If test 1 gives false alarms, see step 19.

---

## 15. Measure performance (for the report)

### 15.1 Speed (FPS)
Read the `FPS ... | ms/frame: ...` lines in the log. Target: **15 FPS or more** (12 is OK).

### 15.2 Temperature and power
While the program runs, open a **second** PowerShell window → `ssh pi@drowsy-pi.local`, then:
```bash
watch -n 2 'vcgencmd measure_temp; vcgencmd get_throttled; uptime'
```
(Ctrl + C to stop.)

| Reading | Good | Problem |
|---|---|---|
| `temp=` | below **75 °C** | above 80 °C → the Pi slows down → add heatsink / fan |
| `throttled=` | **0x0** | anything else → weak power supply or too hot |

For CPU and RAM use: `sudo apt install -y htop`, then `htop` (press `q` to quit).

### 15.3 Results table (for the Phase 4 report)

| Measurement | Value |
|---|---|
| Webcam model and resolution | ……… / 640×480 |
| Average FPS | |
| Average ms per frame | |
| CPU usage (%) | |
| RAM used (MB) | |
| CPU temperature after 15 min (°C) | |
| `get_throttled` after 15 min | |
| Eyes closed → alarm delay (s) | |
| Head down → alarm delay (s) | |
| False alarms in 5 min of normal sitting | |

Copy the per-frame log to the laptop for graphs:
```powershell
scp pi@drowsy-pi.local:~/drowsy-driver-alert/logs/pi_run.csv .\logs\
```

### 15.4 If the FPS is low (below 12)
1. Check temperature and power (15.2). This is the most common cause.
2. Use the **Lite** OS (no desktop).
3. Close other programs (check with `htop`).
4. Add more light. In the dark, many webcams **slow themselves down** to get a brighter picture.
   You can turn this off (step 19, "FPS drops only in dim light").
5. Last option: add `resolution: [480, 360]` to `config/pi.yaml`.

---

## 16. Start automatically on power-on

This makes it a real device: plug in power → it starts by itself. No laptop.

### 16.1 Create the service

```bash
sudo nano /etc/systemd/system/drowsy.service
```
Paste this (right-click pastes in PowerShell). If your username is not `pi`, change it in the 3 places:

```ini
[Unit]
Description=Drowsy Driver Alert
After=multi-user.target

[Service]
User=pi
WorkingDirectory=/home/pi/drowsy-driver-alert
ExecStart=/home/pi/drowsy-driver-alert/venv/bin/python src/main.py --config config/pi.yaml
Environment=PYTHONUNBUFFERED=1
KillSignal=SIGINT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
Save: **Ctrl + O**, **Enter**. Exit: **Ctrl + X**.

| Line | What it means |
|---|---|
| `User=pi` | Runs as your user (allowed to use the webcam and pins) |
| `WorkingDirectory` | So it can find `config/` and `models/` |
| `PYTHONUNBUFFERED=1` | Log lines show up right away |
| `KillSignal=SIGINT` | Stopping works like Ctrl + C, so the buzzer turns off cleanly |
| `Restart=always` | If it crashes (or the webcam isn't ready yet at boot), it starts again after 3 s |

### 16.2 Turn it on

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now drowsy.service
systemctl status drowsy.service
journalctl -u drowsy -f
```
- `status` should say **active (running)**. Press `q` to leave.
- You should hear the **double beep**.
- `journalctl -f` shows the live log. Ctrl + C only stops *watching* the log.

### 16.3 Test it like a real device

1. `sudo poweroff`, wait for the green light to stop, unplug the power.
2. **Close the laptop** (or turn off its Wi-Fi).
3. Make sure the webcam is plugged in, then plug in the Pi's power.
4. In **30–60 s**: double beep → look straight for 10 s → close your eyes → alarm.

✅ **Check:** it works with **no laptop at all**.

### 16.4 Useful commands

```bash
sudo systemctl stop drowsy        # stop it (needed before testing the webcam by hand)
sudo systemctl start drowsy       # start it
sudo systemctl restart drowsy     # after changing code or config
sudo systemctl disable drowsy     # don't start on boot anymore
journalctl -u drowsy -n 100       # last 100 log lines
```

> ⚠️ While the service is running, it is using the webcam. If you run `fswebcam` or `main.py`
> by hand, you get *"Device or resource busy"*. Stop the service first.

---

## 17. Build the final prototype

### 17.1 Layout

```
              driver's face
                   ▲  50–70 cm, webcam tilted up a little
                   │
          ┌────────┴────────┐
          │   USB webcam    │  (on the dashboard / stand, a little below eye level)
          └────────┬────────┘
                   │ USB cable  → black USB port
          ┌────────┴──────────────────────┐
          │ Raspberry Pi 4 in a case      │──── 3 jumper wires ──── buzzer (near the driver)
          │  (pendrive in blue USB port)  │
          └────────┬──────────────────────┘
                   │ USB-C
            5 V 3 A power supply / car adapter
```

### 17.2 Assembly tips
1. Put the Pi in a **case with air holes** (or open with heatsinks). Don't close it in a box with no air.
2. Fix the webcam firmly so it **doesn't move**. If it moves, restart the program to calibrate again.
3. Tape the webcam's USB cable to the case so it can't be pulled out.
4. Put the buzzer where the driver can hear it clearly. **Don't cover its sound hole.**
5. Tape the jumper wires to the case so they can't come off the pins (loose wire = no alarm).
6. Label the wires (S / + / −) for the demo.
7. Desk demo: use the wall adapter. In a car: a **5 V 3 A** car USB-C adapter, then check
   `vcgencmd get_throttled` shows `0x0`.
8. Take **photos** of the wiring and the finished prototype for the report.

---

## 18. Shut down and update code

**Always shut down properly** (protects the pendrive):
```bash
sudo poweroff
```
Wait until the green light stops (~10 s), then unplug.

**After changing code on the laptop**, copy it again and restart:
```powershell
cd "E:\Sem\Sem 7\IOT LAB\IOT_PROJECT\drowsy-driver-alert"
scp -r src config tests requirements.txt pi@drowsy-pi.local:~/drowsy-driver-alert/
scp models/eye_state.onnx models/face_landmarker.task pi@drowsy-pi.local:~/drowsy-driver-alert/models/
```
```bash
cd ~/drowsy-driver-alert && source venv/bin/activate
pip install -r requirements.txt      # only does something if requirements.txt changed
sudo systemctl restart drowsy
```

### 18.1 Pi already set up with the OLD code? (mediapipe 0.10.21 error on Trixie)

If `pip install` failed with *"No matching distribution found for mediapipe==0.10.21"*, you do **not**
need to re-flash. The new code works on Trixie / Python 3.13:

1. On the **laptop**, copy the new files (the two `scp` lines above).
2. On the **Pi**, make a fresh venv (removes half-installed packages) and install:
   ```bash
   sudo apt install -y python3-gpiozero python3-lgpio python3-venv libportaudio2
   cd ~/drowsy-driver-alert
   find . -name "__pycache__" -type d -exec rm -rf {} +
   rm -rf venv
   python3 -m venv --system-site-packages venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Do the **✅ Check** of step 12. It must say `mediapipe 1.1.1` and `79 passed`.

---

## 19. Troubleshooting

### Webcam problems

| Problem | Likely cause | Fix |
|---|---|---|
| `ls /dev/video*` shows no `video0` | Webcam not detected | Try another USB port / cable; check `lsusb`; try the webcam on the laptop |
| `RuntimeError: Cannot open webcam 0` | Wrong number, or webcam busy | Check `v4l2-ctl --list-devices`; set the right `camera_index` in `config/pi.yaml`; stop the service |
| `Device or resource busy` | The service is already using the webcam | `sudo systemctl stop drowsy` |
| `webcam OK NO FRAME` / `No frame from camera` in the log | Webcam needs more power, or a bad USB cable | Use the official power supply; plug the webcam directly into the Pi (no USB hub); try another port |
| Picture very dark | Not enough light | Add light in front of the face; no light behind the driver |
| Picture blurry | Too close / dirty lens | Move to 50–70 cm; clean the lens with a soft cloth |
| Picture upside down | Webcam mounted upside down | Turn the webcam the right way up |
| Webcam stops after some time | Loose cable / power | Tape the cable; check `vcgencmd get_throttled` is `0x0` |
| FPS drops **only in dim light** | Webcam makes exposure longer and lowers its own FPS | Add light, or run `v4l2-ctl -d /dev/video0 -l` and set `exposure_auto_priority=0` (on some webcams it's called `exposure_dynamic_framerate=0`) with `v4l2-ctl -d /dev/video0 -c exposure_auto_priority=0` |

### Pi and setup problems

| Problem | Likely cause | Fix |
|---|---|---|
| `Could not resolve hostname drowsy-pi.local` | Still starting / different Wi-Fi | Wait; use the same Wi-Fi; use the IP address (step 7) |
| Red light off or blinking | Weak power supply | Use the official 5 V 3 A adapter |
| Pi doesn't start from the pendrive | Old bootloader, or a microSD card is inserted | Remove any microSD card; do step **4.3** |
| Windows asks to "format the disk" | Windows can't read Linux drives | Click **Cancel**. The pendrive is fine |
| mediapipe "no matching distribution" for `0.10.21` | Old `requirements.txt` (pinned 0.10.21 for every Python) | Step **18.1** (copy the new files, fresh venv). No re-flash needed |
| mediapipe "no matching distribution" for any version | 32-bit OS (`uname -m` says `armv7l`) | Write the **64-bit** OS (step 4) |
| `OSError: PortAudio library not found` | Missing sound library (MediaPipe 1.x) | `sudo apt install -y libportaudio2` |
| `AttributeError: module 'mediapipe' has no attribute 'solutions'` | Old `src/landmarks.py` | Copy the new `src/` from the laptop |
| `FileNotFoundError ... face_landmarker.task` | Face model not copied | Copy `models/face_landmarker.task` (step 11) |
| `ModuleNotFoundError: gpiozero` inside venv | venv made without `--system-site-packages` | `rm -rf venv`, then repeat step 12 |
| `FileNotFoundError ... eye_state.onnx` | Model not copied | Copy `models/eye_state.onnx` (step 11) |
| `FileNotFoundError: logs/...csv` | No logs folder | `mkdir -p ~/drowsy-driver-alert/logs` |
| `throttled=0x50005` / random reboots | Low power | Better power supply and a short, thick USB-C cable |
| FPS below 12 | Too hot / weak power / too dark | Step 15.4 |

### Buzzer problems

| Problem | Likely cause | Fix |
|---|---|---|
| Only **clicks** | Passive buzzer | Step **10.3** |
| Beeps **all the time** | Active-LOW buzzer | `buzzer_active_high: false` in `config/pi.yaml` |
| Never beeps | Wrong pin | S must be on **physical pin 12** (GPIO18), − on pin 6. Test again (10.1) |
| `GPIO busy` error | The service is using the pin | `sudo systemctl stop drowsy` |

### Detection problems

| Problem | Likely cause | Fix |
|---|---|---|
| Alarms while sitting normally | Bad calibration / bad webcam angle | Restart and look straight for the full 10 s; fix the webcam position (step 13) |
| No alarm when eyes are closed | Face not found (too far, too dark, light behind) | Check the log for "no face"; move the webcam closer; add light |

---

## 20. Checklist and deliverables

### Checklist
- [ ] Have: Pi 4, USB webcam, buzzer, 5 V 3 A USB-C supply, 32 GB pendrive, 3 jumper wires, heatsinks
- [ ] (Optional) Webcam tested on the laptop first
- [ ] Pendrive written with **Raspberry Pi OS 64-bit** (Trixie or Bookworm; hostname `drowsy-pi`, SSH, Wi-Fi)
- [ ] Pi starts from the pendrive (blue port), no microSD card (`lsblk` shows `sda`)
- [ ] Buzzer: S → pin 12, middle → pin 1, − → pin 6
- [ ] Webcam in a black USB port; `ls /dev/video*` shows `/dev/video0`
- [ ] `ssh pi@drowsy-pi.local` works
- [ ] `python3 --version` → 3.13 or 3.11, `uname -m` → aarch64
- [ ] Test photo (`fswebcam`) is sharp and the right way up
- [ ] Buzzer type found (active / active-LOW / passive) and setting done
- [ ] Project copied; `config/pi.yaml` has `camera: webcam`
- [ ] `pip install -r requirements.txt` done in a `--system-site-packages` venv
- [ ] `webcam OK (480, 640, 3)` and `79 passed` on the Pi
- [ ] Video test runs on the Pi
- [ ] Live run: double beep → calibration → FPS ≥ 15
- [ ] All 12 alarm tests done and written down (step 14.3)
- [ ] FPS / temperature / throttling written down (step 15.3)
- [ ] Auto-start works after reboot **with no laptop**
- [ ] Prototype built; photos taken

### Deliverables
- ✅ Raspberry Pi 4 with OS, **USB webcam** and buzzer connected and working
- ✅ Phase 2 software running on the Pi with `config/pi.yaml` (only the config is different from the laptop)
- ✅ Auto-start on power-on (systemd service)
- ✅ Working prototype: eyes closed ≥ 1 s, head down or head tilt → buzzer alarm
- ✅ Measurements (FPS, delay, temperature) and the alarm test table for the Phase 4 report
- ✅ Photos of the wiring and the finished prototype

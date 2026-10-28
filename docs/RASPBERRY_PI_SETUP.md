# Raspberry Pi Setup, From Scratch (Phase 3)

> ⚠️ **Old guide.** This file was written for the **Arducam ribbon camera** and a **microSD card**.
> The project now uses a **USB webcam** and boots from a **USB pendrive**.
> **Follow [`PHASE3.md`](PHASE3.md) instead.** With a USB webcam, skip every Arducam / `rpicam` /
> `dtoverlay` / ribbon step below, and you don't need `python3-picamera2`. `config/pi.yaml` already says `camera: webcam`.
> OS: use **Raspberry Pi OS (Legacy, 64-bit)** (Debian 12 Bookworm, Python 3.11), as below.
> (Its warnings that Trixie will not work are out of date, Trixie now works too, but we use Bookworm Legacy.)
> Expected test count is now **79 passed**.

This guide assumes you have **never used a Raspberry Pi**. Follow the steps in order. Each step
ends with a **check** so you know it worked before moving on.

You will not need a monitor, keyboard or mouse for the Pi. You control it from your laptop over
Wi-Fi with **SSH** (a remote terminal). The laptop and the Pi must be on the **same Wi-Fi network**
(a phone hotspot works).

> **Our hardware:** **Raspberry Pi 4 Model B, 8 GB RAM** + **Arducam 16 MP fixed-focus camera**
> (CSI ribbon camera, most likely the **Sony IMX519** sensor). This guide is written for exactly these two parts.

---

## 0. What you need

| Item | Notes |
|---|---|
| **Raspberry Pi 4 Model B (8 GB)** ✅ have it | Quad-core Cortex-A72, 64-bit. 8 GB is more than enough (the project uses < 1 GB) |
| **5 V 3 A USB-C power supply** | Printed on the box: *"5V/3A USB-C power supply required"*. The official Pi 4 adapter is best. A phone charger often gives too little current, which causes random crashes |
| microSD card, 32 GB (Class 10 / A1) + card reader | The Pi's "hard disk" |
| **Arducam 16 MP fixed-focus camera + its white ribbon cable** ✅ have it | The included 15-pin cable fits the Pi 4 directly (no adapter cable needed) |
| Active buzzer module, 3 pins (VCC, GND, I/O) | The alarm |
| 3 female-to-female jumper wires | Buzzer to Pi |
| Your laptop (Windows) | To flash the card and control the Pi |
| *(Optional)* heatsink / case with fan | Prevents slowdown when hot |

---

## 1. Understand what goes where

```
┌───────── Laptop (Windows) ─────────┐           ┌──────────── Raspberry Pi ────────────┐
│ 1. Flash OS onto microSD card       │           │ OS: RPi OS (Legacy, 64-bit) Bookworm │
│ 2. Copy project files ──────────────┼── Wi-Fi ─▶│ ~/drowsy-driver-alert/               │
│ 3. Control the Pi with SSH          │           │   src/  config/  models/  ...        │
└─────────────────────────────────────┘           │ Camera (ribbon) ── CSI port          │
                                                  │ Buzzer (3 wires) ── GPIO pins        │
                                                  └──────────────────────────────────────┘
```

The **same code** runs on the laptop and the Pi. Only the config changes: `config/pi.yaml`
says *camera = Pi camera, alarm = GPIO buzzer, no window*.

---

## 2. Install the operating system on the microSD card (on your laptop)

1. Download and install **Raspberry Pi Imager** from <https://www.raspberrypi.com/software/>.
2. Put the microSD card in the card reader and plug it into the laptop.
3. Open Raspberry Pi Imager:
   - **Device:** choose **Raspberry Pi 4**.
   - **Operating System:** choose **Raspberry Pi OS (Legacy, 64-bit)**: Debian 12 "Bookworm".

   > ⚠️ **Most important choice in this guide.** We use **Python 3.11** and MediaPipe 0.10.21 on the Pi,
   > exactly like the laptop. Bookworm ships Python 3.11.
   > The main list shows the newer "Trixie" (Python 3.13). Instead go to **Raspberry Pi OS (other)** →
   > **Raspberry Pi OS (Legacy, 64-bit)** ("A port of Debian Bookworm with security updates and desktop environment").
   > Use the full version with desktop or the **Lite** version; both work. Lite is lighter and faster.

   - **Storage:** choose your microSD card (double-check it's the card, not another drive!).
4. Click **Next**. When asked *"Would you like to apply OS customisation settings?"*, click **Edit Settings**:
   - **General** tab:
     - Hostname: `drowsy-pi`
     - Username: `pi`, and choose a password **you will remember**
     - **Configure wireless LAN:** your Wi-Fi name (SSID) + password. Wireless LAN country: `IN`
     - Locale: your time zone, keyboard `us`
   - **Services** tab: ✅ **Enable SSH** → *Use password authentication*
   - Save → **Yes** → **Yes** (this erases the card). Wait until it says *Write Successful*.
5. Remove the card from the laptop.

---

## 3. Connect the hardware (Pi **unplugged**!)

> Always unplug the power before connecting or removing the camera or wires.

### 3.1 Camera (Arducam 16 MP → Pi 4)

Hold the Pi 4 the same way as in your photo: **USB and Ethernet ports at the bottom**, **power (USB-C)
and the two micro-HDMI ports on the left edge**, GPIO pins on the right edge.

```
   ┌──────────────── [DISPLAY] ─────────── (top) ──────┐
   │ USB-C POWER            ⚠ NOT this one             ║ ← 40 GPIO pins
   │ HDMI0                                             ║   (right edge)
   │ HDMI1                                             ║
   │ ══[CAMERA]══   ← USE THIS (labelled "CAMERA",     ║
   │ A/V jack          between HDMI1 and the A/V jack) ║
   │                                                   │
   │   [USB 2.0]  [USB 3.0]  [ETHERNET]   (bottom)     │
   └───────────────────────────────────────────────────┘
```

1. Use the connector printed **CAMERA** (next to "J3"), between **HDMI1** and the **A/V** jack.
   ⚠️ **Do not** use the connector at the top printed **DISPLAY**. It looks the same but is for screens,
   and the camera will not work there.
2. Gently **pull up the dark plastic latch** on both ends of the CAMERA connector (it lifts about 2 mm and doesn't come off).
3. Push the Arducam ribbon straight down into the slot, all the way:
   - The cable's **silver/gold metal contacts face the HDMI ports** (towards the top / left of the photo).
   - The **blue (or plain) stiffener strip faces the A/V jack and the USB ports**.
4. Press the latch back down. A light pull on the cable should not move it.
5. At the camera end, the cable is already connected on your Arducam board. If it ever comes out,
   the contacts face the **camera board** (the green PCB) and the latch is pushed in the same way.
6. Remove the **protective film** from the lens if there is one.

> The camera lens is **fixed-focus**: it cannot focus closer than a certain distance. Keep the face
> **at least ~40–50 cm** from the lens, and check the sharpness with the test photo in step 6.

### 3.2 Buzzer (active buzzer module, 3 pins)

The 40 GPIO pins are the double row on the **right edge** of the board in your photo (marked "GPIO").
With the USB/Ethernet ports at the bottom, **Pin 1 is at the TOP of the header, in the inner row**
(the row nearer the centre of the board; it has a **square solder pad** underneath). Odd pins (1, 3, 5 …)
are the inner row and even pins (2, 4, 6 …) are the outer row along the board edge:

```
              (top, near the DISPLAY connector)
           inner ┐ ┌ outer row (board edge)
     3V3  Pin 1  ● ●  Pin 2   5V     ◀── Buzzer VCC
          Pin 3  ● ●  Pin 4   5V
          Pin 5  ● ●  Pin 6   GND    ◀── Buzzer GND
          Pin 7  ● ●  Pin 8
     GND  Pin 9  ● ●  Pin 10
          Pin 11 ● ●  Pin 12  GPIO18 ◀── Buzzer I/O (signal)
                 ...  ...
```

| Buzzer pin | Pi pin |
|---|---|
| **VCC** (or +) | **Pin 2** (5 V). Use Pin 1 (3.3 V) only if your module says 3.3 V |
| **GND** (or −) | **Pin 6** (GND) |
| **I/O** (or S / SIG / IN) | **Pin 12** (GPIO18) |

> ⚠️ Never connect 5 V (pin 2/4) directly to a GPIO pin, and never short 5 V to GND. Check twice before powering on.
> A **bare 2-pin buzzer** (no module board) must not be driven straight from a GPIO pin. It needs a
> transistor (e.g. BC547 + 1 kΩ resistor). The 3-pin module already has one.

### 3.3 Power on
Insert the microSD card into the slot on the **underside** of the board, at the top end (opposite the
USB ports), with the card's contacts facing the board. Then plug the 5 V 3 A supply into **USB-C POWER IN**.
The red LED lights up and the green LED flickers. **The first boot takes 1–3 minutes** (it resizes the card).

---

## 4. Connect to the Pi from your laptop (SSH)

Open **PowerShell** on the laptop (Windows 11 already includes SSH):

```powershell
ping drowsy-pi.local
ssh pi@drowsy-pi.local
```
- First time: type `yes` to trust the Pi, then type your password (nothing shows while typing; that's normal).
- ✅ **Check:** the prompt changes to `pi@drowsy-pi:~ $`. You are now typing **on the Pi**.

**If `drowsy-pi.local` is not found:**
- Wait 2 more minutes (first boot) and try again.
- Check the laptop is on the **same Wi-Fi**.
- Find the Pi's IP address in your router / phone-hotspot "connected devices" list, then use `ssh pi@192.168.x.x`.
- If Wi-Fi details were wrong, re-flash the card (step 2).

> From here on, commands in **`bash`** boxes run **on the Pi** (inside SSH).
> Commands in **`powershell`** boxes run **on the laptop**.
> Type `exit` to leave SSH.

---

## 5. Update the Pi and check Python

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```
Wait 1 minute, reconnect with `ssh pi@drowsy-pi.local`, then:

```bash
python3 --version
uname -m
```
✅ **Check:** `Python 3.11.x` and `aarch64` (64-bit). If you see Python 3.13, you flashed
Trixie. Go back to step 2 and choose **Raspberry Pi OS (Legacy, 64-bit)**.

---

## 6. Set up and test the Arducam camera (before any of our code)

### 6.1 First, see if it's detected automatically
```bash
rpicam-hello --list-cameras
```
If it prints a camera such as `imx519 [4656x3496 ...]`, go straight to **6.3**.
If it says **"No cameras available!"**, do 6.2. This is normal for Arducam cameras, because the Pi only
auto-detects the official Raspberry Pi camera models.

### 6.2 Tell the Pi which camera sensor is connected
1. Find the **sensor name** of your camera. It is printed on the Arducam box / product page
   (look for "IMX…"). The Arducam **16 MP** Pi camera uses the **Sony IMX519**, so the steps below use
   `imx519`. If your box shows a different sensor, use that name instead.
2. Open the boot configuration file:
   ```bash
   sudo nano /boot/firmware/config.txt
   ```
3. Find the line `camera_auto_detect=1` and change it to:
   ```
   camera_auto_detect=0
   ```
4. Go to the very end of the file. Under the `[all]` line (add `[all]` if it's missing), add:
   ```
   dtoverlay=imx519
   ```
5. Save (**Ctrl + O**, **Enter**), exit (**Ctrl + X**), and reboot:
   ```bash
   sudo reboot
   ```
6. Reconnect with SSH and check again:
   ```bash
   rpicam-hello --list-cameras
   ```
   ✅ **Check:** it lists `imx519` (with modes like 1280x720, 1920x1080, 2328x1748, 4656x3496).

> **Still "No cameras available"?** Check the ribbon (step 3.1: the **CAMERA** connector, not DISPLAY,
> contacts facing the HDMI ports). Also check that the overlay line is spelled exactly right.
> If it is still missing, Arducam's own installer adds support:
> ```bash
> wget -O install_pivariety_pkgs.sh https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
> chmod +x install_pivariety_pkgs.sh
> ./install_pivariety_pkgs.sh -p libcamera_dev
> ./install_pivariety_pkgs.sh -p libcamera_apps
> sudo reboot
> ```
> Then check again with `rpicam-hello --list-cameras` (or `libcamera-hello --list-cameras`).

### 6.3 Take a test photo and view it on the laptop
```bash
rpicam-still -n -o ~/test.jpg
```
```powershell
scp pi@drowsy-pi.local:~/test.jpg .
start test.jpg
```

✅ **Check:** sit where the driver will sit (about 50–80 cm away) and take the photo. Your face
should be **sharp** (the lens is fixed-focus). If it's blurry, move the camera a bit farther away.

**If no camera is listed after 6.2:** power off (`sudo poweroff`, wait for the green LED to stop, unplug),
re-seat the ribbon at **both ends** with the correct side facing, and make sure it is in **CAMERA**, not DISPLAY.

> Our program uses the camera through **Picamera2**, which uses the same camera system as `rpicam-hello`.
> **If `rpicam-hello` works, our code will work too**, with no code changes for the Arducam.
> It asks for 640×480, and the Pi scales the 16 MP image down automatically.

---

## 7. Test the buzzer (before any of our code)

```bash
python3 -c "from gpiozero import Buzzer; from time import sleep; b = Buzzer(18); b.on(); sleep(1); b.off()"
```
✅ **Check:** the buzzer beeps for 1 second.

- **No sound:** check the 3 wires (especially I/O on **pin 12**, not GPIO12) and VCC/GND.
- **It beeps all the time and goes silent on the test:** your module is *active-LOW*.
  Add this line to `config/pi.yaml` (on the Pi, after copying in step 8):
  `buzzer_active_high: false`

---

## 8. Copy the project to the Pi: exactly what to upload

### Upload these (needed to run)

| Upload | Why |
|---|---|
| `src/` (whole folder) | All the program code |
| `config/` (whole folder) | `base.yaml` (thresholds) + `pi.yaml` (Pi settings) |
| `models/eye_state.onnx` | The trained eye model (286 KB) |
| `models/eye_state.report.json` | *(optional)* model metrics |
| `requirements.txt` | List of Python packages to install |
| `tests/` | *(optional, recommended)* to run the 77 tests on the Pi |
| `README.md`, `docs/` | *(optional)* documentation |

### Do NOT upload

| Don't upload | Why |
|---|---|
| `venv/` | It is built for Windows and **will not work** on the Pi. We create a new one on the Pi |
| `training/` (especially `training/data/`) | The dataset is huge and training is never done on the Pi |
| `logs/`, `__pycache__/`, `.pytest_cache/` | Laptop-only temporary files |
| `models/eye_state_v1/v2/v3.onnx` | Old copies, not used |

### Option A: copy from the laptop with `scp` (no GitHub needed)

On the **Pi**, create the folder:
```bash
mkdir -p ~/drowsy-driver-alert/models
```
On the **laptop** (PowerShell), go to the project folder and copy:
```powershell
cd "E:\Sem\Sem 7\IOT LAB\IOT_PROJECT\drowsy-driver-alert"
scp -r src config tests requirements.txt README.md pi@drowsy-pi.local:~/drowsy-driver-alert/
scp models/eye_state.onnx models/eye_state.report.json pi@drowsy-pi.local:~/drowsy-driver-alert/models/
```

### Option B: from GitHub (if you pushed the repository)
The repo's `.gitignore` already leaves out `venv/`, the dataset and old models, and **includes** `models/eye_state.onnx`.
```bash
cd ~
git clone https://github.com/<your-username>/drowsy-driver-alert.git
```

✅ **Check (on the Pi):**
```bash
cd ~/drowsy-driver-alert
ls
ls models
```
You should see `config  requirements.txt  src  tests ...` and `eye_state.onnx`.

---

## 9. Install the software on the Pi

```bash
sudo apt install -y python3-picamera2 python3-gpiozero python3-venv python3-pip
cd ~/drowsy-driver-alert
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
- `python3-picamera2` and `python3-gpiozero` come from **apt**, not pip. They are made for the Pi's camera and pins.
- `--system-site-packages` lets our virtual environment (`venv`) see those apt packages.
- `pip install -r requirements.txt` installs MediaPipe, OpenCV, NumPy, PyYAML, psutil and pytest.
  It can take **5–15 minutes**.
- After every new SSH login, run `cd ~/drowsy-driver-alert && source venv/bin/activate` again.
  The prompt shows `(venv)` when it's active.

✅ **Check:**
```bash
python -c "import mediapipe, cv2, numpy, yaml; print('mediapipe', mediapipe.__version__, '| opencv', cv2.__version__)"
python -c "from picamera2 import Picamera2; from gpiozero import Buzzer; print('pi libs OK')"
python -m pytest -q
```
Expected: `mediapipe 0.10.21 | opencv 4.11.0`, `pi libs OK`, and **77 passed**.

---

## 10. Position the camera

- Put the camera **in front of the driver, slightly below eye level, tilted up about 15°**, about 50–80 cm from the face.
- The face should fill roughly **⅓ of the picture**, with both eyes clearly visible.
- Avoid a bright window or lamp **behind** the driver's head.
- Check the framing with a photo (step 6: `rpicam-still -n -o ~/test.jpg`, then copy it to the laptop).

---

## 11. Run the drowsiness detector

```bash
cd ~/drowsy-driver-alert
source venv/bin/activate
python src/main.py --config config/pi.yaml --csv logs/pi_run.csv
```
(`mkdir -p logs` first if the logs folder doesn't exist.)

What happens:
1. **Double beep** → the system is armed.
2. **Look straight at the camera for 10 seconds** (calibration). The log prints `Calibrated: ...`.
3. Every few seconds the log prints the **FPS** and time per step. **Target: ≥ 15 FPS.**
4. Test: close your eyes for 2 s, and the buzzer pulses fast. Drop your head forward, and it beeps within about half a second.
5. Stop with **Ctrl + C**.

There is no video window on the Pi (`show_window: false`). Everything shows in the log text.
To recalibrate, stop and start the program again.

✅ **Check:** the buzzer sounds for eyes closed ≥ 1 s, head down and head tilt, and stays silent during normal blinking.

### Check temperature and power while it runs
Open a second PowerShell window → `ssh pi@drowsy-pi.local`, then:
```bash
vcgencmd measure_temp
vcgencmd get_throttled
```
- Temperature should stay **below about 80 °C**. If it's higher, add a heatsink or fan.
- `throttled=0x0` is good. Any other value means **weak power supply or overheating**: use the official adapter.

### If the FPS is low (below 12)
- Make sure no other heavy program is running (`top`, press `q` to quit).
- Lower the camera resolution: in `config/pi.yaml`, add `resolution: [480, 360]`.
- Use the Lite OS (no desktop), and add a heatsink.

---

## 12. Start automatically when the Pi powers on

This makes it a real device: plug in the power and it starts protecting the driver, with no laptop needed.

Create the service file:
```bash
sudo nano /etc/systemd/system/drowsy.service
```
Paste this (right-click pastes in PowerShell). If your username isn't `pi`, change it in all 3 places:
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
Save: **Ctrl + O**, **Enter**, then exit with **Ctrl + X**. Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now drowsy.service
systemctl status drowsy.service
journalctl -u drowsy -f
```
- `status` should say **active (running)**. Press `q` to leave the status view.
- `journalctl -f` shows the live log. Press Ctrl + C to stop *viewing*; the service keeps running.
- `KillSignal=SIGINT` makes a stop behave like Ctrl + C, so the program switches the buzzer off cleanly.

✅ **Check:** `sudo reboot`. About 30–60 s after power-on you should hear the **double beep** with no laptop connected.

Useful service commands:
```bash
sudo systemctl stop drowsy
sudo systemctl start drowsy
sudo systemctl restart drowsy
sudo systemctl disable drowsy
```
> ⚠️ While the service is running, the camera is busy. **Stop the service** before running
> `src/main.py` by hand or `rpicam-still`, or you'll get *"Device or resource busy"*.

**Always shut down properly** before unplugging, to avoid corrupting the SD card:
```bash
sudo poweroff
```

---

## 13. Updating the code later

After changing code on the laptop, copy only what changed, for example:
```powershell
scp -r src config pi@drowsy-pi.local:~/drowsy-driver-alert/
```
Then restart the service on the Pi: `sudo systemctl restart drowsy`.

---

## 14. Using a USB webcam (now the default)

`config/pi.yaml` already uses `camera: webcam`. Plug the webcam in and check `ls /dev/video*` shows `/dev/video0`.
To go back to a ribbon camera, change it to `camera: picamera2` and install `python3-picamera2`. See `PHASE3.md` for the webcam steps.

---

## 15. Troubleshooting

| Problem | Fix |
|---|---|
| `ssh: Could not resolve hostname` | Wait for the first boot, use the same Wi-Fi, or use the IP address instead (step 4) |
| `pip install` fails on **mediapipe** (*"no matching distribution"*) | Wrong Python. Check `python3 --version` is 3.11 and `uname -m` is `aarch64`. Re-flash with **Raspberry Pi OS (Legacy, 64-bit)** (step 2) |
| `ModuleNotFoundError: picamera2` inside venv | The venv was made without `--system-site-packages`. Delete it (`rm -rf venv`) and repeat step 9 |
| `rpicam-hello` lists no cameras | Add `camera_auto_detect=0` + `dtoverlay=imx519` to `/boot/firmware/config.txt` (step 6.2). Check the ribbon is in **CAMERA** (not DISPLAY), contacts facing the HDMI ports |
| Test photo is blurry | Fixed-focus lens: move the camera farther from the face (≥ 50 cm) |
| Image is upside down | Doesn't affect detection much, but the camera should be mounted the right way up (ribbon coming out of the bottom of the camera) |
| `Device or resource busy` (camera) | The service is already using the camera: `sudo systemctl stop drowsy` |
| Buzzer beeps constantly | Active-LOW module: add `buzzer_active_high: false` to `config/pi.yaml` |
| Buzzer never beeps | Signal wire must be on **physical pin 12** (GPIO18). Re-test with step 7 |
| `FileNotFoundError ... eye_state.onnx` | `models/eye_state.onnx` was not copied (step 8) |
| Random reboots / `throttled` not `0x0` | Use the official power supply, and add cooling |
| Low FPS | See step 11 "If the FPS is low" |
| Alarm while driving normally | Recalibrate (restart) while looking straight ahead, and check the camera position (step 10) |

---

## 16. Phase 3 checklist

- [ ] microSD flashed with **Raspberry Pi OS (Legacy, 64-bit)** (Bookworm) (SSH + Wi-Fi set)
- [ ] SSH works: `ssh pi@drowsy-pi.local`
- [ ] `python3 --version` → 3.11
- [ ] Arducam on the **CAMERA** connector; `dtoverlay=imx519` added if needed
- [ ] Camera detected (`rpicam-hello --list-cameras` shows `imx519`) and test photo sharp
- [ ] Buzzer beeps with the gpiozero test
- [ ] Project copied (`src`, `config`, `models/eye_state.onnx`, `requirements.txt`, `tests`)
- [ ] venv created with `--system-site-packages`; `pip install -r requirements.txt` done
- [ ] `python -m pytest -q` → 77 passed on the Pi
- [ ] `python src/main.py --config config/pi.yaml` → double beep, calibration, FPS ≥ 15
- [ ] Eyes closed 1 s / head down / head tilt → buzzer
- [ ] Auto-start service enabled, and it works after reboot with no laptop
- [ ] Note the FPS, CPU temperature and alarm tests for the Phase 4 report

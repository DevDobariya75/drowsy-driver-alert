# Eye-state model

**Status:** trained (v3) and enabled. `models/eye_state.onnx` (= `eye_state_v3.onnx`) was trained on
the full MRL Eye Dataset for 20 epochs. Accuracy on 7 people who were left out of training,
with v2 on the same images for comparison:

| Test | v2 | **v3** |
|---|---|---|
| Overall | 95.9% | **96.1%** |
| With glasses | 93.2% | **93.4%** |
| Glasses, small reflections | 88.1% | **90.0%** |
| Glasses, big reflections | 87.7% | **88.1%** |
| **Synthetic lens glare** (spots, veil, streaks, frame line) | 79.1% | **89.8%** |
| Darkened to 30% | 94.2% | 94.0% |
| Darkened to 12% + noise | 89.0% | 88.6% |
| Darkened to 7% + noise | 82.3% | **83.1%** |

v1 added nothing for the dark (76% at 12%). v2 added per-image brightness normalization and night
augmentation. v3 adds realistic spectacle-reflection augmentation (`add_glare`), balanced sampling
over (glasses, reflection, open/closed), and picks the epoch that is best on clean *and* glare images.
Full numbers: `models/eye_state.report.json`, log: `logs/train_eye_model_v3.log`.
Compare any new model with: `--compare models/eye_state_v3.onnx`.

The model takes a 40% share of each eye's closed score; eye openness (EAR) takes 60%. So the model alone can
never trigger an alarm, and fully closed eyelids always do.

To retrain (e.g. after collecting your own samples, step 3), follow the steps below.

The system already works with EAR alone. This small CNN (open / closed eye) is an
extra check that reduces false alarms with spectacles and in very dim light.

* Trained with **PyTorch**, exported to **ONNX**, run with **OpenCV DNN**.
  OpenCV is already installed on the laptop and the Pi, so the Pi needs no extra packages.
* ~72k parameters, ~290 KB, ~0.5 ms per frame (both eyes).
* Validation uses **people the model has never seen**.

## 1. Install the training packages (laptop only)

```powershell
cd "E:\Sem\Sem 7\IOT LAB\IOT_PROJECT\drowsy-driver-alert"
venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install onnx==1.17.0 "protobuf>=4.25.3,<5"   # newer onnx breaks mediapipe
```
(If you have an NVIDIA GPU, install the CUDA build of torch from pytorch.org instead. CPU is fine too.)

## 2. Download the MRL Eye Dataset (84,898 eye images of 37 people, a few hundred MB)

```powershell
mkdir training\data
curl.exe -L -o training\data\mrlEyes.zip http://mrl.cs.vsb.cz/data/eyedataset/mrlEyes_2018_01.zip
tar -xf training\data\mrlEyes.zip -C training\data
```
You should now have `training\data\mrlEyes_2018_01\s0001\...png`.
If the link is down, download "MRL Eye Dataset" from Kaggle. Folder layouts like
`.../Open_Eyes/*.png` and `.../Closed_Eyes/*.png` are also understood.

## 3. (Recommended) Collect your own eye samples

MRL images are mostly infrared. Adding a few hundred crops from **your own webcam**
helps the model a lot:

```powershell
python training/collect_eye_samples.py --person dev
```
Hold **O** with eyes open, hold **C** with eyes closed. Aim for 500+ of each.
Change the lighting (lights on/off, near window), wear/remove glasses, and move closer/further
while collecting. Ask 1–2 friends to do the same with their own `--person` name.

## 4. Train

Quick trial run (a few minutes, just to check everything works):
```powershell
python training/train_eye_model.py --data training/data/mrlEyes_2018_01 --limit 8000 --epochs 2
```

Full training:
```powershell
python training/train_eye_model.py --data training/data/mrlEyes_2018_01 --extra training/data/own --epochs 12
```
(Leave out `--extra ...` if you skipped step 3.)

Outputs:
* `models/eye_state.onnx`: the model
* `models/eye_state.report.json`: accuracy, precision, recall, F1 and confusion matrix,
  including dark / very dark / glasses / bad-light breakdowns (use these in the report)

**Share the full console output (epoch lines + the final validation table) so we can check it.**

## 5. Turn it on / off

`eye_model.enabled` in `config/base.yaml`. The display shows `model P(closed)` and whether
the model passed the calibration check.

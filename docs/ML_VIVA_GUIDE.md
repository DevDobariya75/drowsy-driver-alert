# Machine Learning in "Asleep at the Wheel": Viva Guide

This guide explains the ML side of the Drowsy Driver Alert project: what we used, why we used it,
how the model was trained and how well it works. It ends with a list of likely viva questions and short answers.

---

## 1. The project in one paragraph

A camera watches the driver's face. For every frame we find **478 face landmarks**, measure how open
the eyes and mouth are and which way the head is pointing, and run a small **CNN that classifies
each eye as open or closed**. A **rule-based state machine** combines these signals over time. If
the eyes stay closed for 1 s, the head drops or the head tilts, a loud alarm sounds. Everything runs
**offline on the device** (edge AI): first on a laptop (Phase 2), then on a Raspberry Pi (Phase 3).

---

## 2. What type of ML problem is it?

| Part | ML problem type |
|---|---|
| Eye-state model (the model **we trained**) | **Supervised learning**, **binary image classification** (classes: *open*, *closed*). The output is a probability P(closed). |
| Face landmarks (MediaPipe Face Mesh) | **Regression**: it predicts 478 (x, y, z) points. We use it **pre-trained** and did not train it. |
| Drowsiness decision | **Not learned.** It is a **rule-based / expert system** (a finite-state machine with time thresholds) on top of the ML outputs. |

So the whole system is a **hybrid AI pipeline**:
**pre-trained deep model** (landmarks) + **custom-trained CNN** (eye state) + **hand-crafted
geometric features** (EAR, MAR, head angles) + **rule-based temporal reasoning**.

**Why not train one end-to-end "drowsy / not drowsy" network?**
1. There is no large public labelled dataset of real drivers falling asleep, and it would be unsafe to record one.
2. Rules are **explainable**: we can say exactly *why* the alarm sounded (e.g. "eyes closed 1.2 s").
   This matters for a safety system.
3. Rules **adapt to each driver** through calibration, without retraining.
4. Small models plus rules run fast on a Raspberry Pi.

---

## 3. Tools and technologies

| Tool | Version | What we used it for |
|---|---|---|
| **Python** | 3.11 (laptop) / 3.13 (Pi, Trixie) | Whole project, same code on both |
| **PyTorch** | ≥ 2.2 (CPU) | Building and training the eye-state CNN |
| **ONNX** | 1.17.0 (opset 13) | Exporting the trained model to a portable format |
| **OpenCV** (`cv2`) | 4.11.0.86 | Camera capture, image processing, **running the ONNX model (`cv2.dnn`)**, drawing |
| **MediaPipe Face Landmarker** (Face Mesh model, Tasks API) | 0.10.21 (laptop) / 1.1.1 (Pi, Python 3.13) | Pre-trained face landmark model `face_landmarker.task` (478 points incl. iris) |
| **NumPy** | 1.26.4 | All numeric computation |
| **PyYAML** | 6.0.3 | Config files (`base.yaml`, `laptop.yaml`, `pi.yaml`) |
| **pytest** | 9.1.1 | 77 automated unit tests |
| **psutil** | 7.2.2 | Restricting to 1 CPU core to simulate a Raspberry Pi |
| **gpiozero** | apt package | Buzzer on the Pi's GPIO pins (Pi only). The USB webcam is read by OpenCV on both laptop and Pi |

**Why ONNX + OpenCV DNN, and not PyTorch, on the Pi?**
PyTorch is large (hundreds of MB) and slow to install on a Pi. OpenCV is already needed for the
camera, and it can run ONNX models directly. So the Pi needs **no extra ML library** for our model.
We checked that OpenCV and PyTorch give the same output: the maximum difference was **0.00001**.

---

## 4. The full pipeline (per camera frame)

```
camera frame
  → light normalization (gamma + CLAHE, picked automatically for dark / normal / bright)
  → MediaPipe Face Mesh → 478 landmarks (x, y, z)
  → features:
       EAR  (Eye Aspect Ratio)     per eye   → how open each eye is
       MAR  (Mouth Aspect Ratio)             → yawning
       head pitch / yaw / roll               → nodding, turning, tilting
       eye crops → CNN → P(closed) per eye   → our trained model
       glare check (lens reflections)        → ignore an eye hidden by glare
  → calibration (first 10 s: learns THIS driver's normal open eyes and head position)
  → state machine (timers) → OK / WARNING / CRITICAL → buzzer
```

### Key formulas (often asked)

**EAR (Eye Aspect Ratio)**, from Soukupová & Čech (2016), using 6 points around the eye:

```
EAR = (|p2 − p6| + |p3 − p5|) / (2 · |p1 − p4|)
```

Open eye ≈ 0.25–0.35, closed eye ≈ 0.05–0.1. We compare each eye with **its own calibrated open
value** (ratio = EAR / baseline), so people with naturally small eyes are handled.

**MAR (Mouth Aspect Ratio)** = vertical lip gap / mouth width. MAR > 0.6 for 1.5 s counts as a yawn.

**PERCLOS** = percentage of time the eyes are ≥ 80 % closed over the last 60 s (the standard
"P80" definition used in driver-fatigue research).

**Head pose**: from MediaPipe's 3D landmarks we build the face's own axes (eye-to-eye and
forehead-to-chin). The rotation matrix is decomposed into **pitch** (nod), **yaw** (turn) and **roll** (tilt).

**Eye score (fusion)**: per eye, `score = 0.6 · EAR_score + 0.4 · P(closed from CNN)`.
The CNN alone can never trigger the alarm (max 0.4 < 0.6 threshold), and fully closed lids always do.

---

## 5. The dataset

**MRL Eye Dataset (2018)**, from the Media Research Lab, VŠB – Technical University of Ostrava
(Czech Republic). It is free for academic use.

| Property | Value |
|---|---|
| Images | **84,898** cropped eye images |
| People | **37** (different subjects) |
| Image type | Grayscale, mostly **infrared** (captured by several different sensors), small low-resolution crops |
| Labels used | **eye state** (open / closed) |
| Extra annotations | glasses (yes/no), reflections (none / small / big), lighting (good / bad), gender, sensor |

**How labels are read:** each file name holds its annotations, e.g.
`s0001_00001_0_0_1_0_0_01.png` = subject, image id, gender, **glasses**, **eye state**,
**reflections**, **lighting**, sensor. Our script reads field 5 for the label (0 = closed, 1 = open).

**Why this dataset?** It is large, has many people, and includes **glasses, reflections and
bad lighting**, the exact hard cases we care about.

**Known gap (be honest in the viva):** MRL images are mostly infrared, but our camera is a normal
colour camera. We reduce this gap by converting to grayscale, normalizing brightness per image,
and using heavy augmentation. The tool `training/collect_eye_samples.py` can also collect the
driver's own eye images for fine-tuning (`--extra`).

---

## 6. Data preparation

1. **Load** every image as grayscale and resize it to **48 × 48** pixels.
2. **Split by person, not by image.** 30 people are used for training and **7 people are never seen
   in training** (validation). This is a *subject-held-out* (group) split.
   - Train: **73,864** images, 48 % closed.
   - Validation: **11,034** images, 59 % closed, **7 unseen people**.
   - *Why:* images of the same person look almost identical. A random split would leak the same
     person into both sets and give a fake high score. Our score shows how the model does on a
     **new driver**.
3. **Balanced sampling.** In each group of (glasses, reflection level), open and closed eyes are
   sampled equally often. Glasses with reflections are sampled 1.5× more. *Why:* the raw data has
   about 2× more closed than open eyes for people with glasses, which would teach the model
   "glasses → closed".
4. **At run time** the eye is cropped from the camera frame using the landmarks (1.8 × the eye
   width, square), converted to grayscale and resized to 48 × 48, matching the training data.

---

## 7. Data augmentation (applied randomly to every training batch)

| Augmentation | Simulates |
|---|---|
| Zoom 0.85–1.2×, rotation ±15°, shift ±8 %, horizontal flip | Crops that are never perfectly centred, head tilt, left vs right eye |
| Gamma, contrast 0.6–1.4×, brightness 0.4–1.6× | Different cameras and lighting |
| **30 % of images darkened to 6–30 %**, half of these brightened again like the live pipeline does | **Night driving** |
| **Synthetic lens glare (40 %)**: bright spots, a soft veil, streaks, a dark glasses-frame line | **Reflections on spectacles** |
| Blur (30 %) and Gaussian noise | Motion blur, cheap sensors, night noise |

Augmentation is done **on the GPU/CPU in PyTorch** for each batch, so every epoch sees new variations.

---

## 8. The model (EyeNet, a small CNN)

```
Input 1×48×48 grayscale
 → per-image normalization (subtract mean, divide by std)   ← inside the model
 → Block 1: [Conv3×3 → BatchNorm → ReLU] ×2, 16 filters → MaxPool   (48 → 24)
 → Block 2: [Conv3×3 → BatchNorm → ReLU] ×2, 32 filters → MaxPool   (24 → 12)
 → Block 3: [Conv3×3 → BatchNorm → ReLU] ×2, 64 filters → MaxPool   (12 → 6)
 → Global Average Pooling → 64 values
 → Dropout 0.3 → Fully connected 64 → 2
 → Softmax → [P(open), P(closed)]
```

| Property | Value |
|---|---|
| Parameters | **≈ 72,000** |
| File size (ONNX) | **286 KB** |
| Speed | **0.49 ms for both eyes** on the laptop CPU |

**Design choices:**
- **Per-image normalization inside the model**: the model sees the eye's *shape*, not how bright
  the photo is. This was the key change that made night-time accuracy go from 76 % (v1) to 89 % (v2).
  Because it is inside the model, it is exported to ONNX too, so it also runs on the Pi.
- **Small network:** a 48×48 eye crop doesn't need a big model, and it must run in real time on a Pi.
- **Global Average Pooling** instead of big dense layers means far fewer parameters and less overfitting.
- **BatchNorm** gives faster, more stable training. **Dropout** reduces overfitting.

---

## 9. Training

| Setting | Value |
|---|---|
| Loss | **Cross-entropy** with **label smoothing 0.05** |
| Optimizer | **AdamW** (Adam with decoupled weight decay 1e-4) |
| Learning rate | **OneCycle** schedule, max LR 0.002 |
| Batch size | 256 |
| Epochs | 20 |
| Hardware | Laptop **CPU** (no GPU needed). About 1–4 min per epoch, plus about 12 min to load the images |
| Random seeds | Fixed (0), so the run is reproducible |
| Model selection | After each epoch we check validation **F1 (closed)** on clean images **and** on glare images, and keep the epoch with the best average |
| Export | `torch.onnx.export` (opset 13). The ONNX model is then re-run in OpenCV to check it matches PyTorch |

**Command used:**
```
python training/train_eye_model.py --data training/data/mrlEyes_2018_01 --epochs 20 --out models/eye_state_v3.onnx --compare models/eye_state_v2.onnx
```

**Label smoothing:** the targets become 0.975 / 0.025 instead of 1 / 0. This stops the model from
being over-confident, which is useful because some dataset labels are ambiguous (half-closed eyes).

**OneCycle LR:** the learning rate warms up, then decays. This gives fast convergence and a good final minimum.

---

## 10. Results (7 people the model never saw)

### Final model v3, which is in use (`models/eye_state.onnx`)

| Test | Accuracy | F1 (closed) |
|---|---|---|
| **Overall** | **96.1 %** | **0.967** |
| Precision / Recall (closed) | 94.8 % / **98.7 %** | |
| Without glasses | 97.9 % | 0.982 |
| With glasses | 93.4 % | 0.948 |
| Glasses, no reflection | 97.5 % | 0.984 |
| Glasses, small / big reflections | 90.0 % / 88.1 % | 0.893 / 0.877 |
| **Synthetic lens glare** | **89.8 %** | 0.917 |
| Bad lighting (dataset label) | 95.0 % | 0.959 |
| Darkened to 30 % | 94.0 % | 0.951 |
| Darkened to 12 % + noise | 88.6 % | 0.909 |
| Darkened to 7 % + noise | 83.1 % | 0.867 |

**Confusion matrix** (rows = truth):

|            | predicted open | predicted closed |
|---|---|---|
| **open**   | 4,142 | 351 |
| **closed** | 84    | 6,457 |

Only **84 of 6,541 closed eyes were missed (1.3 %)**. For a safety system, **recall on "closed" matters most**.
The 351 open eyes wrongly called closed don't cause false alarms, because the CNN is only 40 % of the
decision. EAR must also agree, and the closure must last 1 s.

### Model versions (why we retrained)

| Version | What changed | Overall | Dark 12 % | Lens glare |
|---|---|---|---|---|
| v1 | Baseline CNN | 96.4 % | 76 % | – |
| v2 | + per-image normalization, night augmentation | 95.9 % | 89.0 % | 79.1 % |
| **v3** | + glare augmentation, balanced sampling, glare-aware model selection | **96.1 %** | 88.6 % | **89.8 %** |

### Whole-system tests (not only the CNN)
- **77 unit tests** (pytest): metrics, head pose, light correction, and the state machine. These include
  "must NOT alarm" cases (normal blinks, looking at the dashboard, noise, glare on one lens) and
  "must alarm" cases (micro-sleep, head drop, tilt, flickering face tracking).
- **Video tests** in 5 lighting variants (original, dark, very dark, bright, side shadow): 5/5 pass.
- **Speed**: about 9.4 ms per frame on **1 laptop CPU core** (to simulate a Pi).
- **Alarm latency**: micro-sleep after 1.0 s of closed eyes. Head down out of view: 0.3 s. Head down
  with eyes hidden: 0.5 s. Head tilt: 1 s (0.5 s with eyes shut). On a recorded clip, the head-down alarm fired **0.27 s** after the head dropped.

---

## 11. How we avoid false alarms (the other half of accuracy)

- **Both eyes must look closed** (the less-closed eye counts), so a glitch on one eye can't fake it.
- **Glare check:** if one lens is covered by reflection, that eye is ignored and the clear eye decides.
- **3-frame median filter** removes single-frame errors without stretching blinks.
- **Hysteresis:** an eye "closes" at score 0.6 and "reopens" at 0.4, so it never flickers.
- **Per-driver calibration** (10 s) learns that driver's normal eyes and head position.
- **Gating:** eyes are ignored while yawning or looking far to the side, and blink statistics pause while looking down.
- Weak signs on their own (blink rate, a few yawns) are **shown on screen only**, never beeped.
- **Model self-check:** during calibration, if the CNN thinks the driver's open eyes look closed
  (e.g. unusual glasses), it is switched off for that session and EAR alone is used.

---

## 12. Limitations (say these honestly)

1. The training data is mostly **infrared**, while our camera is visible-light. Collecting the driver's own samples improves this.
2. **Pitch-black** conditions: a normal camera sees nothing. Fixing that needs a NoIR camera + IR LEDs (future scope).
3. **Sunglasses** hide the eyes completely. Head-pose rules still work, but eye rules can't.
4. Validation is on 7 people from one dataset. A larger real-car test is Phase 4 work.
5. The best epoch was chosen using the validation set, so validation scores are slightly optimistic.
   There was no separate third test set.
6. The rule thresholds were tuned by hand and tested, not learned from real drowsy-driving data.

## 13. Future scope
- Fine-tune on own camera's images (`collect_eye_samples.py` → `--extra`).
- **INT8 quantization** of the CNN for even faster Pi inference.
- NoIR camera + IR LEDs for night driving.
- A small temporal model (e.g. LSTM/GRU) over the feature stream, if real drowsy-driving data becomes available.
- Run on a Coral TPU / Hailo AI accelerator for higher FPS.

---

## 14. Likely viva questions, with short answers

**Q1. What is your project in one line?**
An edge-AI system that watches the driver's eyes and head with a camera and sounds an alarm on micro-sleep, head drop or head tilt, fully offline on a Raspberry Pi.

**Q2. Is this supervised or unsupervised learning?**
Supervised. Every training image has a label (open/closed).

**Q3. Classification or regression?**
The model we trained is binary classification. MediaPipe (pre-trained) does landmark regression.

**Q4. Which algorithm / model did you use?**
A custom Convolutional Neural Network (3 conv blocks, global average pooling, ≈ 72k parameters), plus MediaPipe Face Mesh for landmarks and a rule-based state machine for the final decision.

**Q5. Why a CNN?**
CNNs learn spatial patterns (eyelid edges, iris, eyelashes) directly from pixels, and they are robust to small shifts thanks to convolution and pooling.

**Q6. Why not use only EAR, without ML?**
EAR fails with glasses, reflections, small eyes and some head angles. The CNN looks at the actual eye appearance and backs up EAR. We fuse both: 60 % EAR, 40 % CNN.

**Q7. Why not a big pre-trained model (ResNet, MobileNet) with transfer learning?**
The input is a tiny 48×48 grayscale eye, and a small CNN already reaches 96 %. A big model would be slower on the Pi with little gain. Transfer learning is a valid alternative (future scope).

**Q8. Which dataset? How big?**
MRL Eye Dataset: 84,898 eye images of 37 people, with labels for eye state, glasses, reflections and lighting.

**Q9. How did you split the data? Why?**
By person: 30 people for training, 7 unseen people for validation. A random split would put the same person in both sets and inflate the accuracy.

**Q10. What is overfitting and how did you prevent it?**
Overfitting is when a model memorizes the training data and fails on new data. We prevented it with data augmentation, dropout (0.3), weight decay (AdamW), BatchNorm, label smoothing, a small model, a person-held-out validation set and best-epoch selection.

**Q11. What is data augmentation? Which did you use?**
Augmentation creates new training variations on the fly. We used rotation, zoom, shift, flip, gamma, contrast, darkening to 6–30 %, synthetic lens glare, blur and noise.

**Q12. Which loss function and optimizer?**
Cross-entropy with label smoothing 0.05, and the AdamW optimizer with a OneCycle learning-rate schedule (max 0.002), batch 256, 20 epochs.

**Q13. What are precision, recall and F1? Which matters most here?**
- Precision = of the eyes predicted closed, how many were really closed (94.8 %).
- Recall = of the really closed eyes, how many we caught (98.7 %).
- F1 = their harmonic mean (0.967).

For safety, **recall** matters most, because a missed closure could be fatal. False positives are filtered by the EAR fusion and the 1 s rule.

**Q14. What is a confusion matrix? Read yours.**
It is a table of true vs predicted classes. Ours: 6,457 closed eyes correctly found, 84 missed; 4,142 open correct, 351 wrongly called closed.

**Q15. What is accuracy and why isn't it enough?**
Accuracy is the fraction of correct predictions (96.1 %). With unbalanced classes it can hide poor performance on one class, so we also report precision, recall and F1, per condition.

**Q16. What is softmax?**
Softmax turns the 2 output scores into probabilities that sum to 1: [P(open), P(closed)].

**Q17. What is ReLU / BatchNorm / Dropout / MaxPool / Global Average Pooling?**
- ReLU = max(0, x), a non-linearity.
- BatchNorm normalizes layer outputs, for stable and faster training.
- Dropout randomly zeroes 30 % of the features during training, to reduce overfitting.
- MaxPool halves the image size, keeping the strongest responses.
- Global Average Pooling averages each feature map to one number, so there are no big dense layers.

**Q18. What is an epoch? A batch? A learning rate?**
- Epoch = one pass over all the training data (we used 20).
- Batch = the images processed together before one weight update (256).
- Learning rate = the step size of each weight update (OneCycle, up to 0.002).

**Q19. What is ONNX and why did you use it?**
ONNX (Open Neural Network Exchange) is a framework-independent model format. We train in PyTorch, export to ONNX and run it with OpenCV on the Pi, with no PyTorch needed there.

**Q20. What is edge AI? Why not the cloud?**
Edge AI means running the model on the device itself. In a car the internet may be missing, cloud delay could cost lives, and the driver's face video stays private.

**Q21. How fast is it?**
The CNN takes 0.49 ms for both eyes. The whole pipeline takes about 9.4 ms per frame on one laptop core. The Pi target is ≥ 15 FPS.

**Q22. How does it work at night / in different light?**
- Automatic light normalization: gamma + CLAHE, with the mode picked from the measured brightness.
- Per-image normalization inside the CNN.
- Training with darkened images.

It reaches 88.6 % even at 12 % brightness. Pitch-black needs IR hardware.

**Q23. How do you handle spectacles and reflections?**
- The training data includes glasses and reflections, plus synthetic glare augmentation (v3 improved lens-glare accuracy from 79 % to 90 %).
- A live glare detector ignores the eye whose lens has a reflection.
- The model self-check during calibration.

**Q24. What is calibration and why is it needed?**
For the first 10 s the driver looks ahead. We record their normal eye openness and head angles, and all later decisions compare against this baseline, because people's eyes and seating positions differ.

**Q25. What is PERCLOS?**
PERCLOS is the percentage of time the eyes are ≥ 80 % closed over the last minute, a standard drowsiness measure. ≥ 25 % gives a warning, ≥ 40 % is critical.

**Q26. How did you test that the system doesn't false-alarm?**
- Unit tests of normal-driving scenarios (blinks, looking down at the dashboard, noise, yawning, glare on one lens) that must stay silent.
- Video tests in 5 lighting variants.
- Live webcam testing with per-frame CSV logs.

**Q27. How is the final alarm decided: ML or rules?**
Rules, using the ML outputs. For example: eyes closed ≥ 1 s → MICROSLEEP (critical). Head down and eyes not visible ≥ 0.5 s, or the face vanishes while the head drops for 0.3 s → HEAD_DOWN (critical). Rules make the alarm explainable and adjustable.

**Q28. What would you improve with more time?**
Fine-tune on our own camera images, INT8 quantization, IR night vision, larger real-world testing, and possibly a temporal (LSTM) model.

**Q29. What is MediaPipe Face Mesh?**
It is Google's pre-trained lightweight model that finds a face and predicts 468 face landmarks + 10 iris landmarks (478) in 3D, in real time on a CPU. We use it as a feature extractor, through the MediaPipe Tasks `FaceLandmarker` API in VIDEO mode (it tracks the face between frames). We moved from the older `mp.solutions.face_mesh` API because MediaPipe 1.x, the only version for Python 3.13 on the Pi, removed it; the landmarks are the same 478 points (about 2 px apart on our test clip).

**Q30. Why grayscale 48×48?**
Eye open/closed doesn't depend on colour, the dataset is grayscale, and small inputs make the model fast.

**Q31. What is label smoothing?**
Label smoothing replaces hard targets 1/0 with 0.975/0.025, which stops over-confidence and helps with noisy labels.

**Q32. What is the OneCycle learning-rate policy?**
The learning rate increases for the first part of training, then decreases to a very small value, which gives faster training and better generalization.

**Q33. Why AdamW instead of SGD?**
AdamW adapts the step size per weight (fast, little tuning), and its decoupled weight decay regularizes properly.

**Q34. How did you check that the exported model is correct?**
We ran the same images through PyTorch and through OpenCV-ONNX. The maximum difference was 0.00001.

**Q35. What is the difference between validation and test data?**
Validation data guides training choices (here, the best epoch). Test data should be used only once at the end. We used unseen people for validation, and the system-level tests (unit and video tests) act as the final test.

**Q36. Class imbalance: was there any, and how did you handle it?**
Yes: about 2× more closed than open eyes with glasses. We handled it with balanced sampling per (glasses, reflection) group, and we report F1, not only accuracy.

**Q37. What are false positives and false negatives here, and which is worse?**
- False negative = a closed eye missed, so a sleeping driver gets no alarm. This is dangerous, and it is the worse one.
- False positive = an open eye called closed, which could cause an annoying alarm.

We minimize false negatives with the model (98.7 % recall), and filter false positives with fusion, timing and hysteresis.

**Q38. Which hyperparameters did you tune?**
Epochs, learning rate, augmentation strength (dark %, glare %), crop scale (1.8× eye width), fusion weight (0.4), decision thresholds (close 0.6 / reopen 0.4) and alarm durations.

**Q39. Could this run on a microcontroller (Arduino / ESP32)?**
The CNN (286 KB) could fit with quantization, but MediaPipe Face Mesh needs a Linux-class CPU, so a Raspberry Pi is the right level.

**Q40. How is the trained model loaded at run time?**
`src/eye_classifier.py` loads `models/eye_state.onnx` with `cv2.dnn.readNetFromONNX`, crops both eyes using the landmarks, and gets P(closed) for each eye per frame.

---

### File map (where to show things in the viva)

| What | File |
|---|---|
| Training script (data, augmentation, model, training, export) | `training/train_eye_model.py` |
| Training logs (all epochs, final metrics) | `logs/train_eye_model_v3.log` |
| Final metrics (JSON) | `models/eye_state.report.json` |
| Trained model | `models/eye_state.onnx` |
| Running the model | `src/eye_classifier.py` |
| EAR / MAR / blink / PERCLOS | `src/metrics.py` |
| Head pose | `src/head_pose.py` |
| Decision rules | `src/state_machine.py` |
| Thresholds | `config/base.yaml` |
| Tests | `tests/` |

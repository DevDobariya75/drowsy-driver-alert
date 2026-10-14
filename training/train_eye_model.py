"""Trains the open/closed eye CNN and exports it to models/eye_state.onnx.

    python training/train_eye_model.py --data training/data/mrlEyes_2018_01
    python training/train_eye_model.py --data training/data/mrlEyes_2018_01 --extra training/data/own

Labels are read from either:
  * MRL Eye Dataset file names  s0001_00001_0_0_1_0_0_01.png  (5th field: 0 closed, 1 open), or
  * folder names: .../open/*.png and .../closed/*.png  (e.g. your own samples)

Validation uses held-out PEOPLE (MRL subjects), so the score reflects new drivers.
Heavy brightness / contrast / gamma / noise / blur augmentation teaches the model
to work at every light intensity."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent
SIZE = 48
OPEN_NAMES = {"open", "opened", "awake", "open_eyes"}
CLOSED_NAMES = {"closed", "close", "sleepy", "closed_eyes"}


# ---------------------------------------------------------------- data
def label_for(path: Path):
    """Returns (label, group, meta) with label 1 = closed, 0 = open; or None."""
    parent = path.parent.name.lower()
    if parent in CLOSED_NAMES or parent in OPEN_NAMES:
        return int(parent in CLOSED_NAMES), f"folder:{path.parent.parent.name}", {}
    parts = path.stem.split("_")
    if len(parts) == 8 and parts[0].startswith("s") and parts[4] in ("0", "1"):
        meta = {"glasses": parts[3] == "1", "reflection": int(parts[5]), "good_light": parts[6] == "1"}
        return int(parts[4] == "0"), parts[0], meta
    return None


def load_images(root: Path, limit=None):
    files = [p for p in root.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    random.Random(0).shuffle(files)
    if limit:
        files = files[:limit]
    xs, ys, groups, metas = [], [], [], []
    t0 = time.time()
    for i, p in enumerate(files):
        lab = label_for(p)
        if lab is None:
            continue
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        xs.append(cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_AREA))
        ys.append(lab[0]); groups.append(lab[1]); metas.append(lab[2])
        if i and i % 10000 == 0:
            print(f"  loaded {i}/{len(files)} images ({time.time() - t0:.0f}s)")
    if not xs:
        sys.exit(f"No labelled images found under {root}")
    return np.stack(xs), np.array(ys), np.array(groups), metas


def split_by_group(groups, val_fraction, seed=0):
    uniq = sorted(set(groups))
    random.Random(seed).shuffle(uniq)
    n_val = max(1, int(len(uniq) * val_fraction))
    val = set(uniq[:n_val])
    is_val = np.array([g in val for g in groups])
    return ~is_val, is_val


# ---------------------------------------------------------------- augmentation
def add_glare(x: torch.Tensor, prob: float, gen: torch.Generator | None = None) -> torch.Tensor:
    """Spectacle reflections, added as light on top of the image (that is what a reflection is):
    small specular spots, a large soft veil (window / screen on the lens), an elongated
    streak, and sometimes the dark line of a glasses frame. Applied to `prob` of the images."""
    b, dev = x.shape[0], x.device

    def rand(lo, hi):
        return torch.rand(b, device=dev, generator=gen) * (hi - lo) + lo

    def chance(p):
        return (torch.rand(b, device=dev, generator=gen) < p).float().view(b, 1, 1)

    yy, xx = torch.meshgrid(torch.arange(SIZE, device=dev, dtype=torch.float32),
                            torch.arange(SIZE, device=dev, dtype=torch.float32), indexing="ij")
    yy, xx = yy[None], xx[None]
    use = chance(prob)
    light = torch.zeros(b, SIZE, SIZE, device=dev)
    for _ in range(3):                                         # small specular spots
        cy, cx, r = rand(4, 44).view(b, 1, 1), rand(4, 44).view(b, 1, 1), rand(1.2, 4).view(b, 1, 1)
        light += chance(0.45) * rand(0.5, 1.0).view(b, 1, 1) * torch.exp(
            -((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
    cy, cx, r = rand(8, 40).view(b, 1, 1), rand(8, 40).view(b, 1, 1), rand(7, 18).view(b, 1, 1)
    light += chance(0.35) * rand(0.25, 0.75).view(b, 1, 1) * torch.exp(    # veiling glare
        -((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
    a = rand(0, np.pi).view(b, 1, 1)                           # streak
    cy, cx = rand(10, 38).view(b, 1, 1), rand(10, 38).view(b, 1, 1)
    across = (xx - cx) * torch.sin(a) - (yy - cy) * torch.cos(a)
    along = (xx - cx) * torch.cos(a) + (yy - cy) * torch.sin(a)
    width, length = rand(1.5, 5).view(b, 1, 1), rand(8, 30).view(b, 1, 1)
    light += chance(0.35) * rand(0.4, 1.0).view(b, 1, 1) * torch.exp(
        -across ** 2 / (2 * width ** 2) - along ** 2 / (2 * length ** 2))
    a = rand(-0.3, 0.3).view(b, 1, 1)                          # glasses frame line (dark)
    top = chance(0.5) > 0
    cy = torch.where(top, rand(2, 10).view(b, 1, 1), rand(38, 46).view(b, 1, 1))
    line_w = rand(0.8, 2).view(b, 1, 1)
    frame_line = torch.exp(-((yy - cy) - (xx - 24) * torch.tan(a)) ** 2 / (2 * line_w ** 2))
    shade = 1 - chance(0.2) * rand(0.4, 0.8).view(b, 1, 1) * frame_line
    out = (x[:, 0] * shade + light).clamp(0, 1).unsqueeze(1)
    return torch.where(use.unsqueeze(1) > 0, out, x)


def augment(x: torch.Tensor) -> torch.Tensor:
    """x: (B,1,H,W) in [0,1]. Random framing, light conditions, glare, noise, blur, flip."""
    b, dev = x.shape[0], x.device

    def rand(lo, hi):
        return torch.empty(b, device=dev).uniform_(lo, hi)

    # framing: zoom, rotation, shift (landmark crops are never perfectly centred)
    scale, angle = rand(0.85, 1.2), rand(-15, 15) * np.pi / 180
    flip = torch.where(torch.rand(b, device=dev) < 0.5, -1.0, 1.0)
    cos, sin = torch.cos(angle) / scale, torch.sin(angle) / scale
    theta = torch.stack([torch.stack([cos * flip, -sin, rand(-0.08, 0.08)], 1),
                         torch.stack([sin * flip, cos, rand(-0.08, 0.08)], 1)], 1)
    grid = F.affine_grid(theta, x.shape, align_corners=False)
    x = F.grid_sample(x, grid, padding_mode="border", align_corners=False)

    # lighting: gamma, brightness (very dark .. bright), contrast
    x = x.clamp(1e-4, 1) ** torch.exp(rand(-0.7, 0.7)).view(b, 1, 1, 1)
    mean = x.mean(dim=(2, 3), keepdim=True)
    x = ((x - mean) * rand(0.6, 1.4).view(b, 1, 1, 1) + mean)
    dark = torch.rand(b, device=dev) < 0.3                       # 30%: night-time images
    x = x * torch.where(dark, rand(0.06, 0.3), rand(0.4, 1.6)).view(b, 1, 1, 1)

    x = add_glare(x, prob=0.4)

    if random.random() < 0.3:
        x = F.avg_pool2d(F.pad(x, (1, 1, 1, 1), mode="replicate"), 3, stride=1)     # blur
    x = x + torch.randn_like(x) * rand(0, 0.06).view(b, 1, 1, 1) * torch.where(dark, 0.5, 1.0).view(b, 1, 1, 1)
    x = x.clamp(0, 1)
    # Half of the dark images get brightened like the live pipeline does (gamma 0.5).
    fix = dark & (torch.rand(b, device=dev) < 0.5)
    x = torch.where(fix.view(b, 1, 1, 1), x.clamp(1e-4, 1) ** 0.5, x)
    return x


# ---------------------------------------------------------------- model
class EyeNet(nn.Module):
    """~70k parameters. Ends in softmax so the ONNX output is [P(open), P(closed)]."""

    def __init__(self):
        super().__init__()

        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o),
                                 nn.ReLU(inplace=True),
                                 nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o),
                                 nn.ReLU(inplace=True), nn.MaxPool2d(2))

        self.features = nn.Sequential(block(1, 16), block(16, 32), block(32, 64))  # 48 -> 6
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.drop = nn.Dropout(0.3)
        self.fc = nn.Linear(64, 2)

    def forward(self, x):
        # Per-image brightness / contrast normalization: the model sees the eye's
        # SHAPE, not how bright the picture is (key for night-time robustness).
        m = x.mean(dim=(2, 3), keepdim=True)
        d = x - m
        x = d / torch.sqrt((d * d).mean(dim=(2, 3), keepdim=True) + 1e-3)
        x = self.pool(self.features(x)).flatten(1)
        logits = self.fc(self.drop(x))
        return logits if self.training else F.softmax(logits, dim=1)


# ---------------------------------------------------------------- evaluation
def predict(model, x, device, batch=1024):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(x), batch):
            xb = torch.from_numpy(x[i:i + batch]).float().div(255).unsqueeze(1).to(device)
            out.append(model(xb)[:, 1].cpu().numpy())
    return np.concatenate(out)


def scores(y, p_closed, thr=0.5):
    pred = (p_closed >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    precision = tp / max(tp + fp, 1); recall = tp / max(tp + fn, 1)
    return {"accuracy": (tp + tn) / max(len(y), 1), "precision_closed": precision,
            "recall_closed": recall, "f1_closed": 2 * precision * recall / max(precision + recall, 1e-9),
            "confusion": {"true_open_pred_open": tn, "true_open_pred_closed": fp,
                          "true_closed_pred_open": fn, "true_closed_pred_closed": tp},
            "n": int(len(y))}


def brighten(x):
    """Gamma 0.5, as the live pipeline does for dark frames."""
    return (np.sqrt(x.astype(np.float32) / 255.0) * 255).astype(np.uint8)


def darken(x, factor, rng):
    noisy = x.astype(np.float32) * factor + rng.normal(0, 4, x.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="MRL dataset folder (or open/closed folders)")
    ap.add_argument("--extra", help="additional open/closed folders, e.g. your own samples")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--val-fraction", type=float, default=0.2)
    ap.add_argument("--limit", type=int, help="use only N images (quick trial run)")
    ap.add_argument("--out", default=str(ROOT / "models" / "eye_state.onnx"))
    ap.add_argument("--compare", help="older .onnx model to evaluate on the same tests")
    args = ap.parse_args()

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    print(f"Loading {args.data} ...")
    x, y, groups, metas = load_images(Path(args.data), args.limit)
    train_m, val_m = split_by_group(groups, args.val_fraction)
    if args.extra:
        print(f"Loading {args.extra} ...")
        ex, ey, eg, em = load_images(Path(args.extra))
        if len(set(eg)) > 1:   # several people: hold out whole people
            etrain, eval_ = split_by_group(eg, 0.2)
        else:                  # one person: random 80/20 split
            etrain = np.random.rand(len(ey)) > 0.2
            eval_ = ~etrain
        x = np.concatenate([x, ex]); y = np.concatenate([y, ey]); metas += em
        train_m = np.concatenate([train_m, etrain]); val_m = np.concatenate([val_m, eval_])
    xtr, ytr, xva, yva = x[train_m], y[train_m], x[val_m], y[val_m]
    print(f"Train {len(ytr)} ({ytr.mean():.0%} closed) | Val {len(yva)} ({yva.mean():.0%} closed), "
          f"held-out people: {len(set(groups[val_m[:len(groups)]]))}")

    # Balanced sampling: within every (glasses, reflection) group, open and closed eyes are
    # equally likely (the raw data has e.g. 2x more closed than open eyes with glasses, which
    # teaches "glasses -> closed"). Glasses with reflections are drawn 1.5x more often.
    tmeta = [m for m, keep in zip(metas, train_m) if keep]
    keys = [(m.get("glasses", "own"), m.get("reflection", "own"), int(lbl)) for m, lbl in zip(tmeta, ytr)]
    count, gcount = {}, {}
    for k in keys:
        count[k] = count.get(k, 0) + 1
        gcount[k[:2]] = gcount.get(k[:2], 0) + 1
    sw = np.array([gcount[k[:2]] / (2 * count[k]) * (1.5 if k[0] is True and k[1] in (1, 2) else 1.0)
                   for k in keys])
    sample_w = torch.from_numpy(sw / sw.sum())

    gen = torch.Generator().manual_seed(123)
    xva_glare = (add_glare(torch.from_numpy(xva).float().div(255).unsqueeze(1), prob=1.0, gen=gen)
                 [:, 0].mul(255).round().byte().numpy())

    model = EyeNet().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * ((len(ytr) + args.batch - 1) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)

    xtr_t = torch.from_numpy(xtr); ytr_t = torch.from_numpy(ytr).long()
    best_f1, best_state = -1, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total, correct, loss_sum = time.time(), 0, 0, 0.0
        perm = torch.multinomial(sample_w, len(ytr_t), replacement=True)
        for i in range(0, len(perm), args.batch):
            idx = perm[i:i + args.batch]
            xb = augment(xtr_t[idx].float().div(255).unsqueeze(1).to(device))
            yb = ytr_t[idx].to(device)
            logits = model(xb)
            loss = F.cross_entropy(logits, yb, label_smoothing=0.05)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            loss_sum += loss.item() * len(idx); total += len(idx)
            correct += (logits.argmax(1) == yb).sum().item()
        val = scores(yva, predict(model, xva, device))
        valg = scores(yva, predict(model, xva_glare, device))
        print(f"Epoch {epoch:2d}/{args.epochs}  loss {loss_sum / total:.4f}  train acc {correct / total:.3f}  "
              f"val acc {val['accuracy']:.3f}  val+glare acc {valg['accuracy']:.3f}  "
              f"F1 {val['f1_closed']:.3f}/{valg['f1_closed']:.3f}  ({time.time() - t0:.0f}s)")
        sel = (val["f1_closed"] + valg["f1_closed"]) / 2   # good on clean AND reflection images
        if sel > best_f1:
            best_f1 = sel
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    model.eval()

    # -------- report
    rng = np.random.default_rng(0)
    dark30, dark12, dark07 = darken(xva, 0.3, rng), darken(xva, 0.12, rng), darken(xva, 0.07, rng)
    p_val = predict(model, xva, device)
    report = {"validation": scores(yva, p_val),
              "validation_dark_x0.3": scores(yva, predict(model, dark30, device)),
              "validation_very_dark_x0.12": scores(yva, predict(model, dark12, device)),
              "validation_very_dark_x0.12_brightened": scores(yva, predict(model, brighten(dark12), device)),
              "validation_extreme_dark_x0.07": scores(yva, predict(model, dark07, device)),
              "validation_synthetic_lens_glare": scores(yva, predict(model, xva_glare, device))}
    vmeta = [m for m, keep in zip(metas, val_m) if keep]
    for key, name in (("glasses", "glasses"), ("good_light", "good_light")):
        for flag in (True, False):
            sel = np.array([m.get(key) is flag for m in vmeta])
            if sel.any():
                report[f"validation_{name}={flag}"] = scores(yva[sel], p_val[sel])
    for level in (0, 1, 2):
        sel = np.array([m.get("glasses") is True and m.get("reflection") == level for m in vmeta])
        if sel.any():
            report[f"validation_glasses_reflection={level}"] = scores(yva[sel], p_val[sel])
    print("\n=== Validation (held-out people) ===")
    for k, v in report.items():
        print(f"{k:32s} n={v['n']:6d}  acc {v['accuracy']:.3f}  precision {v['precision_closed']:.3f}  "
              f"recall {v['recall_closed']:.3f}  F1 {v['f1_closed']:.3f}")
    c = report["validation"]["confusion"]
    print(f"\nConfusion matrix (rows = truth):\n            pred open  pred closed\n"
          f"  open      {c['true_open_pred_open']:9d}  {c['true_open_pred_closed']:11d}\n"
          f"  closed    {c['true_closed_pred_open']:9d}  {c['true_closed_pred_closed']:11d}")

    # -------- export to ONNX and verify OpenCV can run it
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 1, SIZE, SIZE)
    export_kwargs = dict(input_names=["input"], output_names=["prob"], opset_version=13,
                         dynamic_axes={"input": {0: "n"}, "prob": {0: "n"}})
    model_cpu = model.cpu()
    try:
        torch.onnx.export(model_cpu, dummy, str(out), dynamo=False, **export_kwargs)
    except TypeError:  # older torch without the dynamo argument
        torch.onnx.export(model_cpu, dummy, str(out), **export_kwargs)

    net = cv2.dnn.readNetFromONNX(str(out))
    sample = xva[:64]
    net.setInput(cv2.dnn.blobFromImages(list(sample), 1 / 255.0, (SIZE, SIZE)))
    cv_p = net.forward()[:, 1]
    torch_p = predict(model_cpu, sample, "cpu")
    diff = float(np.abs(cv_p - torch_p).max())
    t0 = time.perf_counter()
    for _ in range(200):
        net.setInput(cv2.dnn.blobFromImages(list(sample[:2]), 1 / 255.0, (SIZE, SIZE)))
        net.forward()
    ms = (time.perf_counter() - t0) / 200 * 1000
    report["onnx"] = {"path": str(out), "size_kb": out.stat().st_size / 1024,
                      "opencv_vs_torch_max_diff": diff, "opencv_ms_per_frame_2_eyes": ms}
    print(f"\nSaved {out} ({out.stat().st_size / 1024:.0f} KB). OpenCV vs PyTorch max diff {diff:.5f}, "
          f"{ms:.2f} ms per frame (2 eyes) on this machine.")
    if args.compare:
        old = cv2.dnn.readNetFromONNX(args.compare)

        def old_predict(imgs):
            res = []
            for i in range(0, len(imgs), 512):
                old.setInput(cv2.dnn.blobFromImages(list(imgs[i:i + 512]), 1 / 255.0, (SIZE, SIZE)))
                res.append(old.forward()[:, 1])
            return np.concatenate(res)

        old_sets = {"validation": xva, "validation_dark_x0.3": dark30, "validation_very_dark_x0.12": dark12,
                    "validation_extreme_dark_x0.07": dark07, "validation_synthetic_lens_glare": xva_glare}
        p_old = old_predict(xva)
        rows = {k: scores(yva, old_predict(v)) for k, v in old_sets.items()}
        for level in (0, 1, 2):
            sel = np.array([m.get("glasses") is True and m.get("reflection") == level for m in vmeta])
            if sel.any():
                rows[f"validation_glasses_reflection={level}"] = scores(yva[sel], p_old[sel])
        sel = np.array([m.get("glasses") is True for m in vmeta])
        rows["validation_glasses=True"] = scores(yva[sel], p_old[sel])
        print(f"\n=== New vs {Path(args.compare).name} (same held-out people, same images) ===")
        for k, v in rows.items():
            if k in report:
                print(f"{k:40s} old acc {v['accuracy']:.3f}   new acc {report[k]['accuracy']:.3f}")
        report["compare"] = {"model": args.compare, **rows}
    report_path = out.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

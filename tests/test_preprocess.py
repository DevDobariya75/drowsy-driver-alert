import numpy as np

from src.preprocess import BRIGHT, DARK, NORMAL, LightNormalizer


def gradient(level):
    """A frame with some texture around a given mean brightness."""
    x = np.tile(np.linspace(-30, 30, 640), (480, 1))
    return np.clip(level + x, 0, 255).astype(np.uint8)[:, :, None].repeat(3, axis=2)


def settle(norm, frame, n=60):
    for _ in range(n):
        out, info = norm.process(frame)
    return out, info


def test_dark_frame_is_brightened():
    n = LightNormalizer()
    frame = gradient(35)
    out, info = settle(n, frame)
    assert info["light_mode"] == DARK
    assert out.mean() > frame.mean() + 20


def test_bright_frame_is_darkened():
    n = LightNormalizer()
    frame = gradient(220)
    out, info = settle(n, frame)
    assert info["light_mode"] == BRIGHT
    assert out.mean() < frame.mean() - 10


def test_normal_frame_mode():
    _, info = settle(LightNormalizer(), gradient(120))
    assert info["light_mode"] == NORMAL


def test_hysteresis_prevents_flicker():
    n = LightNormalizer(dark_below=60, hysteresis=8)
    settle(n, gradient(40))
    modes = {settle(n, gradient(62 + (i % 2) * 3), 5)[1]["light_mode"] for i in range(10)}
    assert modes == {DARK}


def test_very_dark_flag():
    n = LightNormalizer(very_dark_below=25)
    settle(n, gradient(10))
    assert n.very_dark


def test_disabled_passthrough():
    frame = gradient(35)
    out, _ = LightNormalizer(enabled=False).process(frame)
    assert out is frame

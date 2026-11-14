"""Scan and phone-photo degradations. Geometric steps move the word boxes with the pixels."""

import cv2
import numpy as np

DESKS = [(235, 235, 235), (200, 205, 210), (92, 120, 150), (60, 62, 68), (176, 190, 198),
         (255, 255, 255), (120, 140, 160)]  # BGR


def _warp(img, boxes, rng, np_rng):
    """Small rotation plus perspective jitter on a padded canvas, as in a hand-held photo."""
    h, w = img.shape[:2]
    pad = int(rng.uniform(0.02, 0.07) * max(h, w))
    desk = rng.choice(DESKS)
    canvas = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=desk)
    H, W = canvas.shape[:2]
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])

    angle = np.deg2rad(rng.uniform(-3.0, 3.0))
    centre = np.array([W / 2, H / 2])
    rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    jitter = np_rng.uniform(-0.018, 0.018, size=(4, 2)) * [w, h] if rng.random() < 0.7 else 0
    dst = ((src - centre) @ rot.T + centre + jitter).astype(np.float32)
    # Keep the whole sheet inside the frame.
    dst[:, 0] = np.clip(dst[:, 0], 2, W - 3)
    dst[:, 1] = np.clip(dst[:, 1], 2, H - 3)

    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(canvas, M, (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=desk)
    corners = np.stack([boxes[:, [0, 1]], boxes[:, [2, 1]], boxes[:, [2, 3]], boxes[:, [0, 3]]], axis=1) + pad
    moved = cv2.perspectiveTransform(corners.reshape(1, -1, 2).astype(np.float32), M).reshape(-1, 4, 2)
    new_boxes = np.concatenate([moved.min(axis=1), moved.max(axis=1)], axis=1)
    return out, new_boxes


def _shadow(img, rng, np_rng):
    h, w = img.shape[:2]
    angle = rng.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ramp = (xx / w - 0.5) * np.cos(angle) + (yy / h - 0.5) * np.sin(angle) + 0.5
    gain = 1.0 - rng.uniform(0.12, 0.38) * np.clip(ramp, 0, 1)
    return np.clip(img * gain[..., None], 0, 255).astype(np.uint8)


def _tint(img, rng, np_rng):
    paper = np.array(rng.choice([(215, 238, 245), (225, 235, 240), (238, 240, 236), (205, 228, 240)]),
                     dtype=np.float32)  # warm, aged paper in BGR
    return np.clip(img.astype(np.float32) * (paper / 255.0), 0, 255).astype(np.uint8)


def _fade(img, rng, np_rng):
    """Low-ink / faded thermal print: lift the blacks."""
    lift = rng.uniform(40, 110)
    return np.clip(img.astype(np.float32) * (255 - lift) / 255 + lift, 0, 255).astype(np.uint8)


def _blur(img, rng, np_rng):
    return cv2.GaussianBlur(img, (0, 0), rng.uniform(0.5, 1.2))


def _noise(img, rng, np_rng):
    noise = np_rng.normal(0, rng.uniform(3, 11), img.shape[:2] + (1,))
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def _grey(img, rng, np_rng):
    return cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def _photocopy(img, rng, np_rng):
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grey = np.clip((grey - 128) * rng.uniform(1.4, 2.2) + 128 + rng.uniform(-10, 25), 0, 255)
    return cv2.cvtColor(grey.astype(np.uint8), cv2.COLOR_GRAY2BGR)


PHOTOMETRIC = [("shadow", _shadow, 0.45), ("tint", _tint, 0.3), ("fade", _fade, 0.2),
               ("grey", _grey, 0.2), ("photocopy", _photocopy, 0.12), ("blur", _blur, 0.45),
               ("noise", _noise, 0.5)]


def degrade(png_bytes: bytes, boxes, rng):
    """Returns (JPEG bytes, "jpg", boxes, names of the steps applied, (width, height))."""
    img = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    np_rng = np.random.default_rng(rng.getrandbits(32))
    applied = []

    if rng.random() < 0.65:
        img, boxes = _warp(img, boxes, rng, np_rng)
        applied.append("warp")
    for name, fn, prob in PHOTOMETRIC:
        if rng.random() < prob and not (name == "photocopy" and "fade" in applied):
            img = fn(img, rng, np_rng)
            applied.append(name)
    if rng.random() < 0.35:  # low-resolution capture
        factor = rng.uniform(0.62, 0.88)
        img = cv2.resize(img, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
        boxes = boxes * factor
        applied.append("downscale")

    quality = rng.randint(38, 88)
    applied.append(f"jpeg{quality}")
    ok, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok
    h, w = img.shape[:2]
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h)
    return encoded.tobytes(), "jpg", boxes.tolist(), applied, (w, h)

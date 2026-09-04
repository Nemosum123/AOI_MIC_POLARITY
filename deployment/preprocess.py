"""
preprocess.py (multi-task version)

zoom_crop() now takes zoom_factor/max_dim as arguments instead of fixed
module-level constants, so the same function serves multiple inspection
tasks, each calibrated to its own camera framing.
"""

import cv2

# Defaults match the original connector calibration. Always pass explicit
# values for any other task rather than relying on these silently.
DEFAULT_ZOOM_FACTOR = 1.5
DEFAULT_MAX_DIM = 1280


def zoom_crop(frame, zoom_factor=DEFAULT_ZOOM_FACTOR, max_dim=DEFAULT_MAX_DIM):
    h, w = frame.shape[:2]
    crop_w, crop_h = w / zoom_factor, h / zoom_factor
    x0, y0 = (w - crop_w) / 2, (h - crop_h) / 2
    x1, y1 = x0 + crop_w, y0 + crop_h
    cropped = frame[int(round(y0)):int(round(y1)), int(round(x0)):int(round(x1))]

    ch, cw = cropped.shape[:2]
    scale = min(1.0, max_dim / max(ch, cw))
    if scale < 1.0:
        out_w, out_h = int(round(cw * scale)), int(round(ch * scale))
        cropped = cv2.resize(cropped, (out_w, out_h), interpolation=cv2.INTER_AREA)

    return cropped

"""
inspection_core.py (multi-task + auto-detect version)

Supports switching between multiple inspection tasks on one Pi, AND a
continuous auto-detect mode that triggers a logged inspection automatically
as soon as a board is placed under the camera — no button press needed.

Inference is split into two steps so both the manual single-shot capture
and the continuous auto-detect loop share one implementation:
  - _infer_once(): capture + preprocess + predict, no logging
  - _log_result(): writes the CSV row and saves a flagged image if needed
  - run_inspection(): the original manual-capture entry point (unchanged
    interface — touchscreen_app.py's Capture button still calls this)
  - run_auto_detect_loop(): continuous polling, logs automatically on a
    stable detection, waits for the board to be removed before re-arming
"""

import csv
import os
import time
from datetime import datetime

import cv2
from picamera2 import Picamera2
from ultralytics import YOLO
from libcamera import controls as libcontrols

from preprocess import zoom_crop

# ---------------------------------------------------------------------
# Per-task configuration
# ---------------------------------------------------------------------
TASKS = {
    "connector": {
        "display_name": "Connector Alignment",
        "model_path": "models/connector/best_ncnn_model",
        "zoom_factor": 2.0,
        "max_dim": 1280,
        "conf_threshold": 0.4,
        "log_path": "logs/connector/inspection_log.csv",
        "flagged_dir": "logs/connector/flagged_images",
        "passed_dir": "logs/connector/passed_images",
        # No calibrated value yet — falls back to continuous autofocus.
        # Calibrate with macro_capture_test.py the same way mic_wiring
        # was, if this task's images ever need sharpening too.
        "lens_position": None,
    },
    "mic_wiring": {
        "display_name": "Mic Wire Polarity",
        "model_path": "models/mic_wiring/best_ncnn_model",
        # TODO: recalibrate zoom_factor for this board's actual framing —
        # do not trust the connector's value.
        "zoom_factor": 2.0,
        "max_dim": 1280,
        "conf_threshold": 0.4,
        "log_path": "logs/mic_wiring/inspection_log.csv",
        "flagged_dir": "logs/mic_wiring/flagged_images",
        "passed_dir": "logs/mic_wiring/passed_images",
        # Calibrated via macro_capture_test.py's sharpness bracketing —
        # locking this in avoids autofocus drift/inconsistency between
        # captures, matching the sharpness of the training dataset.
        "lens_position": 22.0,
    },
}

_models = {}
_active_task = None


def load_all_models():
    for task_name, cfg in TASKS.items():
        print(f"Loading model for task '{task_name}'...")
        _models[task_name] = YOLO(cfg["model_path"])
    set_active_task(next(iter(TASKS)))


def set_active_task(task_name):
    global _active_task
    if task_name not in TASKS:
        raise ValueError(f"Unknown task '{task_name}'. Valid tasks: {list(TASKS.keys())}")
    _active_task = task_name


def get_active_task():
    return _active_task


def get_task_display_name(task_name=None):
    return TASKS[task_name or _active_task]["display_name"]


def init_camera(camera_index):
    """Starts the camera at its default config. Focus is NOT set here —
    call set_focus_for_task() right after this, once the active task is
    known, so each task gets its own calibrated (or autofocus) behavior."""
    picam2 = Picamera2(camera_num=camera_index)
    config = picam2.create_still_configuration()
    picam2.configure(config)
    picam2.start()
    time.sleep(2)  # settle delay — required, do not remove
    return picam2


def set_focus_for_task(picam2, task_name=None):
    """
    Locks focus to the calibrated LensPosition for the given task (or the
    currently active task if none specified). Falls back to continuous
    autofocus if this task has no calibrated value yet.

    Call this once right after init_camera(), and again any time the
    active task changes (e.g. when the technician taps "Switch Task").
    """
    cfg = TASKS[task_name or _active_task]
    lens_pos = cfg.get("lens_position")
    try:
        if lens_pos is not None:
            picam2.set_controls({
                "AfMode": libcontrols.AfModeEnum.Manual,
                "LensPosition": lens_pos,
            })
            print(f"Focus locked: LensPosition={lens_pos} (task: {task_name or _active_task})")
        else:
            picam2.set_controls({"AfMode": libcontrols.AfModeEnum.Continuous})
            print(f"No calibrated focus for '{task_name or _active_task}' — using continuous autofocus")
        time.sleep(0.5)  # let the lens physically settle before the next capture
    except Exception as e:
        print(f"Setting focus failed (non-fatal): {e}")


def release_camera(picam2):
    picam2.stop()
    picam2.close()


def _ensure_log_dirs(cfg):
    os.makedirs(os.path.dirname(cfg["log_path"]), exist_ok=True)
    os.makedirs(cfg["flagged_dir"], exist_ok=True)
    os.makedirs(cfg["passed_dir"], exist_ok=True)
    if not os.path.exists(cfg["log_path"]):
        with open(cfg["log_path"], "w", newline="") as f:
            csv.writer(f).writerow(
                ["timestamp", "camera_index", "verdict", "confidence", "final_verdict", "qr_code"]
            )
    # NOTE: this only writes the header for brand-new log files. Any
    # inspection_log.csv that already exists on the Pi from before this
    # change still has the OLD 5-column header. New rows written to it
    # will have 6 values and silently misalign under that old header.
    # Before deploying this, either (a) rename/archive the existing
    # inspection_log.csv files on the Pi so fresh ones get created with
    # the new header, or (b) manually add a "qr_code" column to the
    # existing header row yourself.


def _infer_once(cfg, model, picam2):
    """Capture + preprocess + predict only — no logging. Shared by both
    the manual single-shot capture and the continuous auto-detect loop."""
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    cropped = zoom_crop(frame_bgr, zoom_factor=cfg["zoom_factor"], max_dim=cfg["max_dim"])

    results = model.predict(cropped, imgsz=640, conf=cfg["conf_threshold"], verbose=False)
    r = results[0]

    verdict = "NONE"
    confidence = None
    if len(r.boxes) > 0:
        best_idx = int(r.boxes.conf.argmax())
        cls_id = int(r.boxes.cls[best_idx])
        confidence = float(r.boxes.conf[best_idx])
        verdict = model.names[cls_id].upper()

    if verdict == "DEFECTIVE":
        final_verdict = "FAIL"
    elif verdict == "PASSING":
        final_verdict = "PASS"
    else:
        final_verdict = "FLAG_FOR_REVIEW"

    display_frame = r.plot()
    return verdict, final_verdict, confidence, display_frame


def _log_result(cfg, camera_index, verdict, confidence, final_verdict, display_frame, qr_code=None):
    _ensure_log_dirs(cfg)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(cfg["log_path"], "a", newline="") as f:
        csv.writer(f).writerow(
            [timestamp, camera_index, verdict, confidence, final_verdict, qr_code or ""]
        )

    safe_ts = timestamp.replace(":", "-").replace(" ", "_")
    target_dir = cfg["passed_dir"] if final_verdict == "PASS" else cfg["flagged_dir"]
    fname = f"{target_dir}/{safe_ts}_{final_verdict}.jpg"
    cv2.imwrite(fname, display_frame)


def run_inspection(picam2, camera_index, qr_code=None):
    """Manual single-shot capture — unchanged behavior/interface, plus an
    optional qr_code to attach to the logged row. Still used by the
    touchscreen's Capture button."""
    cfg = TASKS[_active_task]
    model = _models[_active_task]
    verdict, final_verdict, confidence, display_frame = _infer_once(cfg, model, picam2)
    _log_result(cfg, camera_index, verdict, confidence, final_verdict, display_frame, qr_code=qr_code)
    return final_verdict, confidence, display_frame


def run_auto_detect_loop(picam2, camera_index, on_detection, stop_event,
                          poll_interval=0.4, confirm_frames=2, clear_frames=2,
                          get_qr_code=None):
    """
    Continuously polls the camera and automatically triggers a logged
    inspection as soon as a board is confidently detected — no button
    press needed. Run this in a background thread.

    on_detection(final_verdict, confidence, display_frame, qr_code) fires
    exactly once per board placement, once the detection is stable across
    `confirm_frames` consecutive polls. It won't fire again for the same
    board until `clear_frames` consecutive empty polls confirm it was
    removed, then re-arms for the next one.

    get_qr_code, if provided, is a zero-arg callable invoked at the exact
    moment a board is confirmed and logged. It should return whatever QR/
    serial value was most recently scanned (and, typically, clear it so
    the next board requires a fresh scan) — the touchscreen app supplies
    this as a small popping getter over its own scanned-value state.

    Tune `poll_interval` for CPU load vs. responsiveness, and
    `confirm_frames`/`clear_frames` for how quickly it locks in a result
    vs. how resistant it is to a stray single-frame misread.
    """
    cfg = TASKS[_active_task]
    model = _models[_active_task]

    board_present = False
    confirm_count = 0
    clear_count = 0

    while not stop_event.is_set():
        verdict, final_verdict, confidence, display_frame = _infer_once(cfg, model, picam2)
        has_detection = verdict != "NONE"

        if not board_present:
            if has_detection:
                confirm_count += 1
                clear_count = 0
                if confirm_count >= confirm_frames:
                    board_present = True
                    confirm_count = 0
                    qr_code = get_qr_code() if get_qr_code else None
                    _log_result(cfg, camera_index, verdict, confidence, final_verdict,
                                display_frame, qr_code=qr_code)
                    on_detection(final_verdict, confidence, display_frame, qr_code)
            else:
                confirm_count = 0
        else:
            if not has_detection:
                clear_count += 1
                if clear_count >= clear_frames:
                    board_present = False
                    clear_count = 0
            else:
                clear_count = 0

        time.sleep(poll_interval)

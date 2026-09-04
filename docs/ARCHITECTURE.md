# Architecture

## Multi-task design

`inspection_core.py` defines a `TASKS` dict, one entry per inspection
task, each carrying its own:

- `model_path` — NCNN-exported model directory
- `zoom_factor` / `max_dim` — passed to `preprocess.zoom_crop()`
- `conf_threshold`
- `log_path` / `flagged_dir` / `passed_dir`
- `lens_position` — fixed manual focus, or `None` for continuous autofocus

`set_active_task()` / `get_active_task()` swap which task's config and
model are used by every downstream call. `touchscreen_app.py`'s
"Switch Task" button cycles through `TASKS.keys()` and re-applies focus
via `set_focus_for_task()`.

## Inference split

Inference is split into two layers so both manual capture and the
continuous auto-detect loop share one implementation:

- `_infer_once()` — capture + preprocess + predict, no logging
- `_log_result()` — writes the CSV row and saves the image (to
  `passed_dir` or `flagged_dir` depending on verdict)
- `run_inspection()` — manual single-shot entry point (Capture button)
- `run_auto_detect_loop()` — continuous polling entry point (Auto toggle),
  debounced via `confirm_frames`/`clear_frames` so it doesn't re-fire
  while a board sits still, and re-arms only after the board is removed

## File structure on the Pi

```
~/aoi-deploy/
├── models/
│   ├── connector/best_ncnn_model/      (v6, multicolor)
│   └── mic_wiring/best_ncnn_model/     (v1, zoom_factor not yet calibrated)
├── logs/
│   ├── connector/
│   │   ├── inspection_log.csv          (now includes qr_code column)
│   │   ├── flagged_images/
│   │   └── passed_images/
│   └── mic_wiring/
│       ├── inspection_log.csv
│       ├── flagged_images/
│       └── passed_images/
├── preprocess.py
├── inspection_core.py
├── touchscreen.py            (touchscreen_app.py's content, deployed under this name)
├── crop_boundary_check.py
├── macro_capture_test.py
├── pi_stream_server.py
└── test_camera.py
```

## QR / serial capture

See `QR_SCANNER_INTEGRATION.md` for the full design. In short: a USB
HID scan gun "types" into an always-focused, invisible Tkinter `Entry`;
the captured value is popped and attached to whichever inspection fires
next, then logged as a `qr_code` CSV column.

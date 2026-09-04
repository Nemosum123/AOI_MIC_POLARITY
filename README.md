# AOI_MIC_POLARITY

Edge AI Automated Optical Inspection running on a Raspberry Pi 5. A
touchscreen-driven kiosk app captures images of a board, runs a YOLO
detection model, and shows a PASS/FAIL verdict to the technician —
switchable between two inspection tasks on the same hardware, with an
automatic (no button press) capture mode and USB scan-gun serial/QR
tracking.

---

## 1. What it does

Two inspection tasks run on one Pi, switchable via a touchscreen button:

| Task | Detects | Classes |
|---|---|---|
| **Mic Wire Polarity** | Whether a button mic's red/gold wires are soldered to the correct terminals | `defective` / `passing` |

Both share one camera, one Tkinter kiosk app, and one underlying
inference pipeline (`inspection_core.py`), configured per-task via a
`TASKS` dict (model path, zoom/crop factor, confidence threshold, focus
position, log paths).

## 2. Hardware

- Raspberry Pi 5, 4GB RAM, Raspberry Pi OS (Bookworm), desktop session
  running **labwc** via XWayland.
- Camera Module 3 (Sony IMX708).
- 7" WaveShare touchscreen, 1024x600, HDMI + USB-A-to-B touch (WS170120
  panel, works via `libinput`/`evtest`).
- USB HID barcode/QR scan gun (keyboard-emulation type — see Section 5).

## 3. Repository layout

```
bluarmor-aoi/
├── README.md
├── .gitignore
├── LICENSE
├── requirements.txt
├── deployment/
│   ├── inspection_core.py     # multi-task inference, auto-detect, QR-aware logging
│   ├── touchscreen_app.py     # Tkinter kiosk UI — deployed on the Pi as touchscreen.py
│   ├── preprocess.py          # preprocessing file
│   ├── pi_stream_server.py    # MJPEG live view for focus tuning
│   └── pc_stream_viewer.py    # PC-side viewer for the above
├── training/
│   └── pipeline.ipynb         # kaggle notebook 
└── docs/
    ├── ARCHITECTURE.md
    ├── QR_SCANNER_INTEGRATION.md
    ├── OUTSTANDING_ITEMS.md
    ├── ITERATION_HISTORY.md
    └── MISSING_FILES.md
```

## 4. Setup on the Pi

```bash
# Virtualenv needs system site-packages so picamera2/libcamera
# (installed via apt, not pip) are visible inside it
python3 -m venv ~/aoi-env --system-site-packages
source ~/aoi-env/bin/activate
pip install -r requirements.txt
```

`picamera2` and `libcamera` are provided by Raspberry Pi OS's apt
packages, not PyPI — `--system-site-packages` is required or imports
will fail even though `pip install` appears to succeed for everything
else.

Directory layout expected under `~/aoi-deploy/` (models, logs, this
code) is documented in `docs/ARCHITECTURE.md`.

## 5. Running it

Manual start (autostart-on-boot was deliberately reverted — see
`docs/OUTSTANDING_ITEMS.md`):

```bash
source ~/aoi-env/bin/activate
cd ~/aoi-deploy
DISPLAY=:0 python3 touchscreen.py
```

The **Auto** toggle in the top bar switches between manual Capture and
continuous auto-detect (fires automatically when a board is placed).

## 6. QR / serial scanning

A USB HID scan gun feeds serial/QR values into the app — no camera-based
QR decoding is used. Full detail, including a **required one-time CSV
migration step**, is in `docs/QR_SCANNER_INTEGRATION.md`. Read that
before deploying this version over an existing installation.

## 7. Known issues / open items

See `docs/OUTSTANDING_ITEMS.md` for the full prioritized list (left-side
connector miss investigation, mic-wiring zoom_factor calibration,
asymmetric confidence thresholds, storage retention, etc.).

## 8. License

All data used for this project belongs to AptEner Mechatronics Private Limited (BluArmor)

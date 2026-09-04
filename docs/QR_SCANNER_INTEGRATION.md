# QR / Serial Scanning

## How it actually works

The scan gun is a **USB HID device that emulates a keyboard** — it
decodes the barcode/QR itself in hardware and "types" the resulting text
wherever keyboard focus currently is, then sends `Enter`. There is no
camera-based QR decoding in this project (an earlier plan to decode QR
codes from the Pi camera feed via OpenCV/`pyzbar` was superseded once
the scan-gun hardware was confirmed — no image processing needed).

## Implementation

In `touchscreen_app.py`:

- `qr_catcher` — a Tkinter `Entry` styled to be invisible (foreground ==
  background, no border, 2x2px, tucked in a corner). Its only job is to
  hold keyboard focus so scan-gun keystrokes land somewhere.
- `_ensure_qr_focus()` — runs every 300ms via `root.after`, re-focusing
  `qr_catcher` if anything else (a button tap, etc.) stole focus.
- `on_qr_scanned()` — bound to `<Return>` on `qr_catcher`. Reads the
  scanned text, stores it in `self.current_qr_code`, and updates the
  visible `qr_display` label (green = scanned, waiting to be used).
- `_pop_qr_code()` — returns and clears `self.current_qr_code`. Called
  right before logging, from both the manual-capture thread and the
  auto-detect background thread, so each board requires a fresh scan.

In `inspection_core.py`:

- `_log_result()` now takes a `qr_code` parameter and writes it as a
  6th CSV column.
- `run_inspection()` accepts `qr_code=None` and passes it through.
- `run_auto_detect_loop()` accepts `get_qr_code` — a zero-arg callable
  invoked at the exact moment a board is confirmed and logged (the
  touchscreen app passes `self._pop_qr_code`).

## ⚠️ Required migration step before deploying

Existing `inspection_log.csv` files on the Pi (from before this change)
have the **old 5-column header**:

```
timestamp,camera_index,verdict,confidence,final_verdict
```

New rows will have 6 values (`qr_code` appended) and will silently
misalign under that old header if appended to as-is. Before deploying:

- **Option A (recommended):** rename/archive the existing
  `logs/connector/inspection_log.csv` and
  `logs/mic_wiring/inspection_log.csv` — fresh files with the correct
  6-column header will be created automatically on next write.
- **Option B:** manually edit the existing header row to add `qr_code`
  as the 6th column.

## UI feedback

The QR status bar at the bottom of the screen shows one of three states:

| State | Meaning | Color |
|---|---|---|
| `Scanned: XXXX` | Code scanned, waiting to be attached to the next result | green |
| `Last used: XXXX` | Code was attached to the most recently logged result | gray |
| `No QR scanned for this result!` | An inspection just logged with no scan at all | orange |

## Not yet implemented

Scanning is currently **optional** — a missed scan just logs with a
blank `qr_code` column and an orange warning, it doesn't block
inspection. Making it mandatory (gate `on_capture` / the auto-detect
loop on `current_qr_code` being non-empty) is a small follow-up if
that's needed on the line.

# Outstanding Items (Priority Order)

1. **Recalibrate `zoom_factor` for `mic_wiring`** in `inspection_core.py`
   — currently a placeholder copied from the connector task (`2.0`),
   flagged with a `TODO` in the code. Do not trust mic-wiring detections
   until this is fixed.
2. **Test auto-detect and focus-locking on real hardware** — both were
   delivered as code but never confirmed working end-to-end on the Pi
   as of the last handoff.
3. **Resolve the left-side connector miss** — run
   `crop_boundary_check.py` against known left-side-loose boards and
   inspect the crop-boundary overlay to determine whether the 2x
   center-crop is clipping the left edge before the model sees it (as
   opposed to a data-coverage gap or a confidence-threshold issue). No
   results have been reported back yet; root cause still unknown.
4. ~~**Decide and integrate QR scanning**~~ — done. See
   `QR_SCANNER_INTEGRATION.md`. (Originally scoped as camera-based
   decode via `qr_test.py`; superseded by the USB scan-gun approach.)
5. **Implement asymmetric confidence thresholds** — a missed defect
   (FAIL) should trigger at a lower confidence bar than a confirmed
   PASS. Never implemented, across either task.
6. **Live-validate the mic-wiring model** — it has offline Kaggle
   metrics only; no live board testing has been done yet. The same
   discipline that caught the connector's false negative should apply
   here.
7. **Deploy and test the central server architecture**
   (`inference_server.py` / `inspection_core_client.py`), if/when the
   project actually moves to a multi-Pi fleet. Currently just designed
   code, not running anywhere.
8. **Storage retention policy** — now more urgent, since pass images
   are also saved permanently (not just flagged ones), roughly doubling
   the rate of disk usage growth in `logs/`.
9. **Consider making QR scanning mandatory** rather than optional — see
   the "Not yet implemented" note in `QR_SCANNER_INTEGRATION.md`.

## Already resolved (don't re-investigate)

- `touchscreen.py` vs `touchscreen_app.py` filename mismatch on the Pi.
- `ImageTk` apt package / import error.
- `labwc` autostart format issues (autostart-on-boot was set up, then
  deliberately reverted — the app is started manually via SSH).

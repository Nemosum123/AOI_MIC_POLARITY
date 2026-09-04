# Files Not Included In This Repo

This repo was assembled from files actually shared in chat
(`inspection_core.py`, `touchscreen_app.py`) plus project handoff
documents describing the rest. The following files are referenced by
name throughout those docs and by imports in the included code, but
their contents were never pasted into the conversation this repo was
built from — copy them in from the Pi (`~/aoi-deploy/`) before this repo
is complete and installable from scratch.

| File | Referenced by | Purpose |
|---|---|---|
| `deployment/preprocess.py` | `import preprocess` in `inspection_core.py` | `zoom_crop(frame, zoom_factor, max_dim)` — center-crop/zoom preprocessing. **Required for the code to run at all.** |
| `deployment/crop_boundary_check.py` | Outstanding item #3 | Diagnostic — overlays the zoom_crop boundary on raw captures, for the left-side connector miss investigation |
| `deployment/macro_capture_test.py` | `ITERATION_HISTORY.md`, focus calibration | Focus-bracketing tool; found `LensPosition=22` for mic_wiring via Laplacian-variance sharpness scoring |
| `deployment/pi_stream_server.py` | `ARCHITECTURE.md` | MJPEG live view with on-page manual focus slider, used for focus tuning |
| `deployment/pc_stream_viewer.py` | — | PC-side OpenCV window to view the Pi's stream |
| `deployment/test_camera.py` | `ARCHITECTURE.md` | Original camera smoke test, untouched since early iterations |
| `training/*` (Kaggle notebooks) | `README.md`, `ITERATION_HISTORY.md` | The actual training pipeline — v6 multicolor connector fine-tune, and `aoi_mic_wiring_v1` from-scratch training |
| `docs/BluArmor_AOI_Story.pptx` | `ITERATION_HISTORY.md` | Non-technical presentation deck — connector-only, predates mic-wiring/auto-detect |
| Original iteration-history handoff doc | `ITERATION_HISTORY.md` | Covers v1-v4 model iterations, the data leakage incident, and class imbalance handling in detail |
| `inference_server.py` / `inspection_core_client.py` | Outstanding item #7 | Central-server architecture for a multi-Pi fleet — designed and coded, never deployed/tested |

**Deleted, not missing:** `run_inspection.py` (old CLI script) was
intentionally removed during the multi-task reorganization — fully
superseded by `touchscreen_app.py`. No need to add it back.

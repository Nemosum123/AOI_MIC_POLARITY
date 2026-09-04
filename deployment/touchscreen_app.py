"""
touchscreen_app.py (multi-task + auto-detect version)

Adds an "Auto: OFF/ON" toggle alongside the existing Switch Task button.
When ON, a background thread continuously watches for a board and fires
a result automatically the moment one is detected — the manual Capture
button is disabled while this is active, since both would otherwise
compete for the same camera.

Results from auto-detect are pushed into the same result_queue the manual
Capture flow already uses, so _poll_queue()/_show_result() need no changes
to handle either source.
"""

import queue
import threading
import tkinter as tk

import cv2
from PIL import Image, ImageTk

import inspection_core as core

CAMERA_INDEX = 0

SCREEN_W, SCREEN_H = 1024, 600
IMAGE_PANEL_W, IMAGE_PANEL_H = 620, 480

VERDICT_COLORS = {
    "PASS": "#1e8e3e",
    "FAIL": "#d93025",
    "FLAG_FOR_REVIEW": "#f9ab00",
}

AUTO_ON_COLOR = "#1e8e3e"
AUTO_OFF_COLOR = "#444444"

# QR/serial scan-gun status colors
QR_READY_COLOR = "#1e8e3e"    # a code has been scanned, waiting to be used
QR_USED_COLOR = "#888888"     # code was attached to the last logged result
QR_MISSING_COLOR = "#f9ab00"  # inspection logged with no scan at all


class AOIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BluArmor AOI")
        self.root.geometry(f"{SCREEN_W}x{SCREEN_H}")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#111111")

        self.result_queue = queue.Queue()
        self.busy = False
        self.auto_mode = False
        self.auto_stop_event = None
        self.auto_thread = None

        # QR/serial scan-gun state. The scan gun is a USB HID device that
        # just "types" the decoded text wherever the keyboard focus is, so
        # there's no image decoding here at all — self.qr_catcher below is
        # the actual keystroke target, kept focused at all times.
        self.qr_var = tk.StringVar()
        self.current_qr_code = ""

        core.load_all_models()
        self._build_layout()

        self.picam2 = core.init_camera(CAMERA_INDEX)
        core.set_focus_for_task(self.picam2)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll_queue)
        self.root.after(300, self._ensure_qr_focus)

    def _build_layout(self):
        self.task_label = tk.Label(
            self.root, text=f"Task: {core.get_task_display_name()}",
            font=("Helvetica", 14, "bold"), bg="#222222", fg="white",
        )
        self.task_label.place(x=10, y=8, width=620, height=36)

        panel_x = IMAGE_PANEL_W + 30

        self.switch_task_btn = tk.Button(
            self.root, text="Switch Task", font=("Helvetica", 11),
            command=self.on_switch_task, takefocus=0,
        )
        self.switch_task_btn.place(x=panel_x, y=8, width=165, height=36)

        self.auto_toggle_btn = tk.Button(
            self.root, text="Auto: OFF", font=("Helvetica", 11, "bold"),
            bg=AUTO_OFF_COLOR, fg="white", command=self.on_toggle_auto, takefocus=0,
        )
        self.auto_toggle_btn.place(x=panel_x + 175, y=8, width=165, height=36)

        self.image_label = tk.Label(self.root, bg="#000000")
        self.image_label.place(x=10, y=54, width=IMAGE_PANEL_W, height=IMAGE_PANEL_H)

        self.capture_btn = tk.Button(
            self.root, text="CAPTURE", font=("Helvetica", 28, "bold"),
            bg="#1a73e8", fg="white", activebackground="#1558b0",
            command=self.on_capture, takefocus=0,
        )
        self.capture_btn.place(x=panel_x, y=60, width=340, height=150)

        self.result_label = tk.Label(
            self.root, text="Ready", font=("Helvetica", 32, "bold"),
            bg="#333333", fg="white", wraplength=340, justify="center",
        )
        self.result_label.place(x=panel_x, y=240, width=340, height=150)

        self.confidence_label = tk.Label(
            self.root, text="", font=("Helvetica", 16), bg="#111111", fg="#cccccc",
        )
        self.confidence_label.place(x=panel_x, y=400, width=340, height=40)

        self.quit_btn = tk.Button(
            self.root, text="Quit", font=("Helvetica", 12), command=self.on_close, takefocus=0,
        )
        self.quit_btn.place(x=panel_x, y=444, width=100, height=36)

        # --- QR/serial scan window, bottom of the screen ---------------
        # qr_display: visible label showing the last scanned/used code.
        # qr_catcher: an Entry that is never actually shown as text input
        #             (fg == bg, no border) — its only job is to hold
        #             keyboard focus so the scan gun's keystrokes land
        #             somewhere. It is kept focused at all times by
        #             _ensure_qr_focus(), regardless of touch taps
        #             elsewhere on screen.
        self.qr_label = tk.Label(
            self.root, text="QR/Serial:", font=("Helvetica", 12, "bold"),
            bg="#111111", fg="#cccccc", anchor="w",
        )
        self.qr_label.place(x=10, y=548, width=100, height=40)

        self.qr_display = tk.Label(
            self.root, text="Waiting for scan...", font=("Helvetica", 16, "bold"),
            bg="#222222", fg=QR_MISSING_COLOR, anchor="w", padx=10,
        )
        self.qr_display.place(x=110, y=548, width=800, height=40)

        self.qr_catcher = tk.Entry(
            self.root, textvariable=self.qr_var,
            bg="#111111", fg="#111111", insertbackground="#111111",
            relief="flat", highlightthickness=0, bd=0,
        )
        # Off in the corner and tiny — never meant to be looked at or
        # tapped, just needs to legitimately hold focus.
        self.qr_catcher.place(x=SCREEN_W - 4, y=SCREEN_H - 4, width=2, height=2)
        self.qr_catcher.bind("<Return>", self.on_qr_scanned)
        self.qr_catcher.focus_set()

    def on_qr_scanned(self, event=None):
        """Fires when the scan gun finishes a code (it sends Enter after
        typing the decoded text). Runs on the main thread — safe to touch
        widgets directly here."""
        code = self.qr_var.get().strip()
        self.qr_var.set("")  # clear the catcher immediately for the next scan
        if code:
            self.current_qr_code = code
            self.qr_display.config(text=f"Scanned: {code}", fg=QR_READY_COLOR)
        return "break"  # swallow the Enter so it can't leak into anything else

    def _pop_qr_code(self):
        """Returns the current scanned code and clears it, so the next
        board requires a fresh scan. Called from _run_inspection_thread
        and from the auto-detect background thread — it only touches a
        plain string attribute (no widget access), which is safe to do
        off the main thread under CPython's GIL."""
        code = self.current_qr_code
        self.current_qr_code = ""
        return code or None

    def _ensure_qr_focus(self):
        """Keeps keyboard focus pinned to the invisible qr_catcher so the
        scan gun's keystrokes always land there, even after a technician
        taps a button elsewhere on the touchscreen."""
        try:
            if self.root.focus_get() is not self.qr_catcher:
                self.qr_catcher.focus_set()
        except KeyError:
            pass  # focus_get() can raise if focus is on a just-destroyed widget
        self.root.after(300, self._ensure_qr_focus)

    def on_switch_task(self):
        if self.busy or self.auto_mode:
            return  # stop auto-detect before switching tasks
        task_names = list(core.TASKS.keys())
        current_idx = task_names.index(core.get_active_task())
        next_task = task_names[(current_idx + 1) % len(task_names)]
        core.set_active_task(next_task)
        core.set_focus_for_task(self.picam2)
        self.task_label.config(text=f"Task: {core.get_task_display_name()}")
        self.result_label.config(text="Ready", bg="#333333")
        self.confidence_label.config(text="")
        self.image_label.config(image="")

    def on_toggle_auto(self):
        if not self.auto_mode:
            self.auto_mode = True
            self.auto_stop_event = threading.Event()
            self.auto_thread = threading.Thread(target=self._auto_detect_worker, daemon=True)
            self.auto_thread.start()

            self.auto_toggle_btn.config(text="Auto: ON", bg=AUTO_ON_COLOR)
            self.capture_btn.config(state="disabled", bg="#888888")
            self.switch_task_btn.config(state="disabled")
            self.result_label.config(text="Watching for board...", bg="#333333")
            self.confidence_label.config(text="")
            self.image_label.config(image="")
        else:
            self.auto_mode = False
            if self.auto_stop_event:
                self.auto_stop_event.set()  # loop exits within one poll interval on its own

            self.auto_toggle_btn.config(text="Auto: OFF", bg=AUTO_OFF_COLOR)
            self.capture_btn.config(state="normal", bg="#1a73e8")
            self.switch_task_btn.config(state="normal")
            self.result_label.config(text="Ready", bg="#333333")

    def _auto_detect_worker(self):
        core.run_auto_detect_loop(
            self.picam2, CAMERA_INDEX,
            on_detection=lambda v, c, f, q: self.result_queue.put(("ok", v, c, f, q)),
            stop_event=self.auto_stop_event,
            get_qr_code=self._pop_qr_code,
        )

    def on_capture(self):
        if self.busy or self.auto_mode:
            return
        self.busy = True
        self.capture_btn.config(state="disabled", bg="#888888")
        self.switch_task_btn.config(state="disabled")
        self.result_label.config(text="Processing...", bg="#333333")
        self.confidence_label.config(text="")

        threading.Thread(target=self._run_inspection_thread, daemon=True).start()

    def _run_inspection_thread(self):
        qr_code = self._pop_qr_code()
        try:
            verdict, confidence, frame = core.run_inspection(self.picam2, CAMERA_INDEX, qr_code=qr_code)
            self.result_queue.put(("ok", verdict, confidence, frame, qr_code))
        except Exception as e:
            self.result_queue.put(("error", str(e), None, None, None))

    def _poll_queue(self):
        try:
            status, a, b, c, qr_code = self.result_queue.get_nowait()
            if status == "ok":
                self._show_result(a, b, c, qr_code)
            else:
                self.result_label.config(text="ERROR", bg="#d93025")
                self.confidence_label.config(text=a)

            # Manual-capture buttons only get re-enabled here if we're not
            # in auto mode — auto mode manages its own button states.
            if not self.auto_mode:
                self.busy = False
                self.capture_btn.config(state="normal", bg="#1a73e8")
                self.switch_task_btn.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _show_result(self, verdict, confidence, frame_bgr, qr_code=None):
        color = VERDICT_COLORS.get(verdict, "#333333")
        self.result_label.config(text=verdict.replace("_", " "), bg=color)
        self.confidence_label.config(
            text=f"Confidence: {confidence:.2f}" if confidence is not None else "No detection"
        )
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img.thumbnail((IMAGE_PANEL_W, IMAGE_PANEL_H))
        photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=photo)
        self.image_label.image = photo

        # Reflect whether this logged result actually had a scan attached.
        if qr_code:
            self.qr_display.config(text=f"Last used: {qr_code}", fg=QR_USED_COLOR)
        else:
            self.qr_display.config(text="No QR scanned for this result!", fg=QR_MISSING_COLOR)

    def on_close(self):
        if self.auto_stop_event:
            self.auto_stop_event.set()
        core.release_camera(self.picam2)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AOIApp(root)
    root.mainloop()

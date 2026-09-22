"""Native Tkinter test application harness for UIAutomation and WinRT OCR E2E testing."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk

# Attach to interactive desktop station (WinSta0\default)
try:
    user32 = ctypes.windll.user32
    hwinsta = user32.OpenWindowStationW("WinSta0", False, 0x037F)
    if hwinsta:
        user32.SetProcessWindowStation(hwinsta)
    hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
    if hdesk:
        user32.SetThreadDesktop(hdesk)
except Exception:
    pass


class NativeTestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Typesafe Computer Use - Native Test App")
        self.root.geometry("1024x768+100+100")
        self.root.configure(bg="#f4f6f9")

        self.step_count = 0

        self._build_ui()

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#0078d4", padx=20, pady=12)
        header_frame.pack(fill="x", padx=16, pady=8)

        title_lbl = tk.Label(
            header_frame,
            text="Snapdragon NPU Copilot+ Native Test Window",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg="#0078d4",
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="Windows 11 ARM64 Qualcomm Hexagon DirectML Verification Target",
            font=("Segoe UI", 10),
            fg="#e0f0ff",
            bg="#0078d4",
        )
        subtitle_lbl.pack(anchor="w")

        # Live State Banner
        banner_frame = tk.Frame(self.root, bg="#e1dfdd", padx=12, pady=8)
        banner_frame.pack(fill="x", padx=16, pady=4)

        self.banner_lbl = tk.Label(
            banner_frame,
            text="DOM Status: Ready: Waiting for input",
            font=("Segoe UI", 12, "bold"),
            fg="#004578",
            bg="#e1dfdd",
        )
        self.banner_lbl.pack(side="left")

        self.step_lbl = tk.Label(
            banner_frame,
            text="Steps: 0",
            font=("Segoe UI", 11),
            fg="#323130",
            bg="#e1dfdd",
        )
        self.step_lbl.pack(side="right")

        # Content Grid
        content_frame = tk.Frame(self.root, bg="#f4f6f9")
        content_frame.pack(fill="both", expand=True, padx=16, pady=8)

        # Left Column: Inputs & Controls
        left_col = tk.Frame(content_frame, bg="white", padx=16, pady=16, relief="groove", bd=1)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

        form_title = tk.Label(left_col, text="Interactive Form Controls", font=("Segoe UI", 13, "bold"), bg="white")
        form_title.pack(anchor="w", pady=(0, 10))

        tk.Label(left_col, text="Username", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w")
        self.user_entry = tk.Entry(left_col, font=("Segoe UI", 10), name="input_user")
        self.user_entry.pack(fill="x", pady=(2, 8))
        self.user_entry.bind("<KeyRelease>", self._on_user_type)

        tk.Label(left_col, text="Email Address", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w")
        self.email_entry = tk.Entry(left_col, font=("Segoe UI", 10), name="input_email")
        self.email_entry.pack(fill="x", pady=(2, 8))
        self.email_entry.bind("<KeyRelease>", self._on_email_type)

        self.accel_var = tk.BooleanVar(value=False)
        self.chk_accel = tk.Checkbutton(
            left_col,
            text="Enable Hardware Acceleration",
            variable=self.accel_var,
            command=self._on_accel_toggle,
            bg="white",
            font=("Segoe UI", 10),
        )
        self.chk_accel.pack(anchor="w", pady=6)

        btn_frame = tk.Frame(left_col, bg="white")
        btn_frame.pack(fill="x", pady=12)

        self.btn_submit = tk.Button(
            btn_frame,
            text="Submit Request",
            command=self._on_submit,
            bg="#0078d4",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=4,
        )
        self.btn_submit.pack(side="left", padx=(0, 8))

        self.btn_reset = tk.Button(
            btn_frame,
            text="Reset Form",
            command=self._on_reset,
            bg="#edebe9",
            fg="#201f1e",
            font=("Segoe UI", 10),
            padx=12,
            pady=4,
        )
        self.btn_reset.pack(side="left", padx=(0, 8))

        self.btn_abort = tk.Button(
            btn_frame,
            text="Simulate Abort",
            command=self._on_abort,
            bg="#d13438",
            fg="white",
            font=("Segoe UI", 10),
            padx=12,
            pady=4,
        )
        self.btn_abort.pack(side="left")

        # Right Column: OCR Text & List
        right_col = tk.Frame(content_frame, bg="white", padx=16, pady=16, relief="groove", bd=1)
        right_col.pack(side="right", fill="both", expand=True, padx=(8, 0))

        ocr_title = tk.Label(right_col, text="WinRT NPU OCR Targets", font=("Segoe UI", 13, "bold"), bg="white")
        ocr_title.pack(anchor="w", pady=(0, 10))

        self.ocr_tok1 = tk.Label(
            right_col,
            text="NPU-LINE-ALPHA: Snapdragon X Plus Hexagon 2026",
            font=("Consolas", 11, "bold"),
            fg="#107c41",
            bg="#f3f2f1",
            padx=8,
            pady=6,
        )
        self.ocr_tok1.pack(fill="x", pady=4)

        self.ocr_tok2 = tk.Label(
            right_col,
            text="BENCHMARK-METRIC: 13.49ms Sub-Second Latency",
            font=("Consolas", 11, "bold"),
            fg="#107c41",
            bg="#f3f2f1",
            padx=8,
            pady=6,
        )
        self.ocr_tok2.pack(fill="x", pady=4)

        self.ocr_tok3 = tk.Label(
            right_col,
            text="TOKEN: ORD-99482-ARM64-VALIDATED",
            font=("Consolas", 11, "bold"),
            fg="#107c41",
            bg="#f3f2f1",
            padx=8,
            pady=6,
        )
        self.ocr_tok3.pack(fill="x", pady=4)

        tk.Label(right_col, text="Scrollable Item Container", font=("Segoe UI", 12, "bold"), bg="white").pack(
            anchor="w", pady=(12, 4)
        )

        list_frame = tk.Frame(right_col)
        list_frame.pack(fill="both", expand=True, pady=4)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 10), height=5)
        for i in range(1, 15):
            self.listbox.insert(tk.END, f"Item {i:02d}: Target Item in Scrolled View #{i}")
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

    def _update_state(self, msg: str):
        self.step_count += 1
        self.banner_lbl.config(text=f"DOM Status: {msg}")
        self.step_lbl.config(text=f"Steps: {self.step_count}")

    def _on_user_type(self, event=None):
        self._update_state(f"User typed: {self.user_entry.get()}")

    def _on_email_type(self, event=None):
        self._update_state(f"Email typed: {self.email_entry.get()}")

    def _on_accel_toggle(self):
        val = "Enabled" if self.accel_var.get() else "Disabled"
        self._update_state(f"Acceleration: {val}")

    def _on_submit(self):
        val = self.user_entry.get() or "Anonymous"
        self._update_state(f"Form Submitted for {val}")

    def _on_reset(self):
        self.user_entry.delete(0, tk.END)
        self.email_entry.delete(0, tk.END)
        self.accel_var.set(False)
        self._update_state("Form Reset: Cleared all fields")

    def _on_abort(self):
        self._update_state("Emergency Abort Triggered")

    def _on_list_select(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            item = self.listbox.get(sel[0])
            self._update_state(f"Selected {item}")


def main():
    root = tk.Tk()
    app = NativeTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

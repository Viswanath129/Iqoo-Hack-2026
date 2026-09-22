"""Test application harness supporting isolated Microsoft Edge and native Tkinter GUI windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_SHOW = 5
SW_RESTORE = 9

# Explicit 64-bit ctypes function signatures to prevent HWND truncation on ARM64
user32.OpenWindowStationW.restype = wintypes.HANDLE
user32.OpenWindowStationW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD]
user32.SetProcessWindowStation.restype = wintypes.BOOL
user32.SetProcessWindowStation.argtypes = [wintypes.HANDLE]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND


def ensure_desktop() -> bool:
    """Attach the current thread to the interactive desktop (WinSta0\\default)."""
    try:
        hwinsta = user32.OpenWindowStationW("WinSta0", False, 0x037F)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
        hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
        return True
    except Exception:
        return False


def find_window_by_title_substring(title_sub: str) -> int | None:
    """Find visible top-level window whose title contains `title_sub`."""
    ensure_desktop()
    found: list[int] = []
    title_sub_lower = title_sub.lower()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if title_sub_lower in buf.value.lower():
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(_enum_cb, 0)
    return found[0] if found else None


def activate_hwnd(hwnd: int) -> bool:
    """Bring window to foreground using AttachThreadInput to bypass ForegroundLockTimeout."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    ensure_desktop()

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)

    cur_tid = kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

    attached = False
    if fg_tid and cur_tid != fg_tid:
        attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))

    try:
        user32.BringWindowToTop(hwnd)
        ret = user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)

    return bool(ret)


def get_hwnd_bounds(hwnd: int) -> tuple[float, float, float, float] | None:
    """Get window bounding box (x, y, w, h)."""
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return float(rect.left), float(rect.top), float(rect.right - rect.left), float(rect.bottom - rect.top)


def get_hwnd_pid(hwnd: int) -> int:
    """Get PID of process owning window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class HarnessSession(NamedTuple):
    proc: subprocess.Popen
    hwnd: int
    pid: int
    title: str
    target_type: str
    temp_dir: str | None


class TargetHarness:
    """Unified test target launcher providing isolated Edge or native Tkinter instances."""

    def __init__(self, fixture_html: Path | None = None):
        if fixture_html is None:
            self.fixture_html = Path(__file__).resolve().parent.parent / "fixtures" / "test_page.html"
        else:
            self.fixture_html = fixture_html

    @staticmethod
    def find_edge_path() -> str | None:
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def launch_edge(self, timeout: float = 8.0) -> HarnessSession:
        edge_exe = self.find_edge_path()
        if not edge_exe:
            raise RuntimeError("Microsoft Edge executable not found on system.")

        temp_profile = tempfile.mkdtemp(prefix="edge_cu_test_")
        file_url = self.fixture_html.as_uri()

        cmd = [
            edge_exe,
            f"--user-data-dir={temp_profile}",
            f"--app={file_url}",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-renderer-accessibility",
            "--window-size=1024,768",
            "--window-position=100,100",
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.monotonic() + timeout
        hwnd = None
        while time.monotonic() < deadline:
            hwnd = find_window_by_title_substring("Snapdragon NPU Typesafe Test Harness")
            if hwnd:
                break
            time.sleep(0.3)

        if not hwnd:
            proc.kill()
            shutil.rmtree(temp_profile, ignore_errors=True)
            raise TimeoutError("Failed to detect launched Edge test harness window within timeout.")

        activate_hwnd(hwnd)
        time.sleep(0.5)
        pid = get_hwnd_pid(hwnd)

        return HarnessSession(
            proc=proc,
            hwnd=hwnd,
            pid=pid,
            title="Snapdragon NPU Typesafe Test Harness",
            target_type="edge",
            temp_dir=temp_profile,
        )

    def launch_native_tk(self, timeout: float = 6.0) -> HarnessSession:
        tk_script = Path(__file__).resolve().parent.parent / "fixtures" / "tk_test_app.py"
        python_exe = sys.executable

        proc = subprocess.Popen(
            [python_exe, str(tk_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + timeout
        hwnd = None
        while time.monotonic() < deadline:
            hwnd = find_window_by_title_substring("Typesafe Computer Use - Native Test App")
            if hwnd:
                break
            time.sleep(0.2)

        if not hwnd:
            proc.kill()
            raise TimeoutError("Failed to detect launched Tkinter test harness window within timeout.")

        activate_hwnd(hwnd)
        time.sleep(0.5)
        pid = get_hwnd_pid(hwnd)

        return HarnessSession(
            proc=proc,
            hwnd=hwnd,
            pid=pid,
            title="Typesafe Computer Use - Native Test App",
            target_type="native_tk",
            temp_dir=None,
        )

    def launch_best(self, prefer: str = "auto") -> HarnessSession:
        """Launch Edge if requested/available, else fall back to native Tkinter."""
        if prefer in ("edge", "auto") and self.find_edge_path():
            try:
                return self.launch_edge()
            except Exception:
                pass
        return self.launch_native_tk()

    @staticmethod
    def terminate(session: HarnessSession):
        """Cleanly terminate test target process and cleanup temporary profile directory."""
        try:
            session.proc.terminate()
            session.proc.wait(timeout=3.0)
        except Exception:
            try:
                session.proc.kill()
            except Exception:
                pass

        if session.temp_dir and os.path.exists(session.temp_dir):
            try:
                shutil.rmtree(session.temp_dir, ignore_errors=True)
            except Exception:
                pass

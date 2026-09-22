"""Windows adapter: synthetic input, app control, screen capture, and the focused accessibility element.

This is the Windows counterpart of macos.py. It provides the same function signatures using
Win32 API (ctypes), UIAutomation, and mss for screen capture.  A Windows port replaces the
Quartz/AX/AppleScript bindings with their Win32 equivalents; the tree walk itself is
platform-free and reused verbatim.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.wintypes as wintypes
import os
import threading
import time
import webbrowser
from collections import deque
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import NamedTuple

from PIL import Image

from .config import ABORT_CORNER_PX
from .models import Abort, AxNode, Field

# ------------------------------------------------------------------ Win32 setup

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Make the process DPI-aware so coordinates match the screenshot pixel grid.
with contextlib.suppress(Exception):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        user32.SetProcessDPIAware()

user32.OpenWindowStationW.restype = wintypes.HANDLE
user32.OpenWindowStationW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD]
user32.SetProcessWindowStation.restype = wintypes.BOOL
user32.SetProcessWindowStation.argtypes = [wintypes.HANDLE]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.restype = wintypes.BOOL
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.CloseWindowStation.restype = wintypes.BOOL
user32.CloseWindowStation.argtypes = [wintypes.HANDLE]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

# Cache desktop handles per-thread to prevent kernel handle leaks.
# Without caching, every call to _ensure_interactive_desktop() leaks 2 OS handles
# (OpenWindowStationW + OpenDesktopW), exhausting the 10K per-process limit quickly.
_desktop_local = threading.local()


def _ensure_interactive_desktop() -> None:
    """Attach the calling thread to WinSta0/Default desktop, caching handles."""
    tid = kernel32.GetCurrentThreadId()
    if getattr(_desktop_local, "tid", None) == tid:
        return  # Already attached on this thread
    try:
        # Close any previously cached handles (from a recycled thread-local)
        old_hdesk = getattr(_desktop_local, "hdesk", None)
        old_hwinsta = getattr(_desktop_local, "hwinsta", None)

        hwinsta = user32.OpenWindowStationW("WinSta0", False, 0x037F)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
        hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)

        # Close old handles *after* setting new ones
        if old_hdesk:
            user32.CloseDesktop(old_hdesk)
        if old_hwinsta:
            user32.CloseWindowStation(old_hwinsta)

        _desktop_local.hwinsta = hwinsta
        _desktop_local.hdesk = hdesk
        _desktop_local.tid = tid
    except Exception:
        pass


_ensure_interactive_desktop()

# Pointer-sized unsigned integer — matches ULONG_PTR in the Windows SDK.
ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_A = 0x41
VK_BACK = 0x08  # macOS "delete" key = Backspace on Windows
VK_SPACE = 0x20
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_CONTROL = 0x11
WHEEL_DELTA = 120
SW_RESTORE = 9
SW_SHOW = 5
SM_CXSCREEN = 0
SM_CYSCREEN = 1
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

KEYCODES = {"return": VK_RETURN, "tab": VK_TAB, "escape": VK_ESCAPE, "a": VK_A, "delete": VK_BACK, "space": VK_SPACE}
MIN_WINDOW_SIDE_PT = 50.0

# ------------------------------------------------------------------ UIAutomation (lazy)

try:
    import uiautomation as auto

    _HAS_UIA = True
except ImportError:
    _HAS_UIA = False

# Map Windows UIA ControlType integer IDs to macOS AX role strings so the rest of the
# codebase works unchanged.  Only the roles used in models.ROLE_WORDS and
# macos.AX_ACTIONABLE_ROLES need entries; the rest map to AXGroup.
UIA_ROLE_MAP: dict[int, str] = {
    50000: "AXButton",       # Button
    50002: "AXCheckBox",     # CheckBox
    50003: "AXComboBox",     # ComboBox
    50004: "AXTextField",    # Edit
    50005: "AXLink",         # Hyperlink
    50006: "AXImage",        # Image
    50007: "AXRow",          # ListItem
    50009: "AXMenu",         # Menu
    50010: "AXMenuBarItem",  # MenuBar
    50011: "AXMenuBarItem",  # MenuItem
    50013: "AXRadioButton",  # RadioButton
    50015: "AXSlider",       # Slider
    50016: "AXIncrementor",  # Spinner
    50019: "AXTab",          # TabItem
    50020: "AXStaticText",   # Text
    50024: "AXRow",          # TreeItem
    50025: "AXGroup",        # Custom
    50026: "AXGroup",        # Group
    50029: "AXCell",         # DataItem
    50030: "AXTextArea",     # Document
    50031: "AXMenuButton",   # SplitButton
    50033: "AXGroup",        # Pane
}

# Friendly app names ↔ process exe stems.
APP_EXE_MAP: dict[str, str] = {
    "Google Chrome": "chrome",
    "Microsoft Edge": "msedge",
    "Firefox": "firefox",
    "Slack": "slack",
    "Notion": "Notion",
    "Spotify": "Spotify",
    "Visual Studio Code": "Code",
    "Windows Terminal": "WindowsTerminal",
    "File Explorer": "explorer",
    "Notepad": "notepad",
    "Notepad++": "notepad++",
}
EXE_APP_MAP: dict[str, str] = {v.lower(): k for k, v in APP_EXE_MAP.items()}

# ------------------------------------------------------------------ escape hatch


def mouse_location() -> tuple[float, float]:
    _ensure_interactive_desktop()
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return float(point.x), float(point.y)


def check_abort() -> None:
    x, y = mouse_location()
    if x <= ABORT_CORNER_PX and y <= ABORT_CORNER_PX:
        raise Abort("mouse in top-left corner")


def sleep_watching(seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        check_abort()
        time.sleep(0.1)


def accessibility_trusted() -> bool:
    # Windows has no equivalent of macOS's Accessibility permission gate.
    return True


# ------------------------------------------------------------------ input helpers


def _send_input(inp: INPUT) -> None:
    _ensure_interactive_desktop()
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _key_down(vk: int) -> None:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki.wVk = vk
    _send_input(inp)


def _key_up(vk: int) -> None:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = KEYEVENTF_KEYUP
    _send_input(inp)


# ------------------------------------------------------------------ input


def click_at(point: tuple[float, float]) -> None:
    _ensure_interactive_desktop()
    x, y = int(point[0]), int(point[1])
    user32.SetCursorPos(x, y)
    time.sleep(0.04)
    inp = INPUT(type=INPUT_MOUSE)
    inp.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
    _send_input(inp)
    time.sleep(0.04)
    inp2 = INPUT(type=INPUT_MOUSE)
    inp2.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
    _send_input(inp2)
    time.sleep(0.04)


def press(key: str, command: bool = False) -> None:
    code = KEYCODES[key]
    if command:
        _key_down(VK_CONTROL)  # Ctrl = macOS Command
    _key_down(code)
    time.sleep(0.04)
    _key_up(code)
    if command:
        _key_up(VK_CONTROL)
    time.sleep(0.04)


def type_text(text: str) -> None:
    for ch in text:
        scan = ord(ch)
        down = INPUT(type=INPUT_KEYBOARD)
        down.union.ki.wScan = scan
        down.union.ki.dwFlags = KEYEVENTF_UNICODE
        _send_input(down)
        time.sleep(0.02)
        up = INPUT(type=INPUT_KEYBOARD)
        up.union.ki.wScan = scan
        up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        _send_input(up)
        time.sleep(0.02)


def clear_field() -> None:
    press("a", command=True)
    press("delete")


def scroll(lines: int) -> None:
    """Scroll the view under the cursor. Positive = up, negative = down — same as macOS."""
    center = frontmost_window_center()
    if center is not None:
        user32.SetCursorPos(int(center[0]), int(center[1]))
        time.sleep(0.04)
    inp = INPUT(type=INPUT_MOUSE)
    inp.union.mi.mouseData = ctypes.c_ulong(lines * WHEEL_DELTA).value
    inp.union.mi.dwFlags = MOUSEEVENTF_WHEEL
    _send_input(inp)
    time.sleep(0.04)


# ------------------------------------------------------------------ process helpers


def _exe_name(pid: int) -> str:
    """Executable base name without extension, e.g. 'chrome'."""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return Path(buf.value).stem
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _app_name_from_hwnd(hwnd: int, pid: int) -> str:
    exe = _exe_name(pid).lower()
    if exe in EXE_APP_MAP:
        return EXE_APP_MAP[exe]
    title = _window_title(hwnd)
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return exe or title


def _main_window_for_pid(target_pid: int) -> int | None:
    """The first visible top-level window owned by *target_pid*."""
    result: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == target_pid:
            result.append(hwnd)
            return False
        return True

    user32.EnumWindows(_cb, 0)
    return result[0] if result else None


def _find_window_by_app(app: str) -> int | None:
    target_exe = APP_EXE_MAP.get(app, "").lower()
    app_lower = app.lower()
    result: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if target_exe and _exe_name(pid.value).lower() == target_exe:
            result.append(hwnd)
            return False
        if app_lower in _window_title(hwnd).lower():
            result.append(hwnd)
            return False
        return True

    user32.EnumWindows(_cb, 0)
    return result[0] if result else None


# ------------------------------------------------------------------ apps and windows


def frontmost_app_and_pid() -> tuple[str, int]:
    _ensure_interactive_desktop()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return _app_name_from_hwnd(hwnd, pid.value), pid.value


def frontmost_app() -> str:
    return frontmost_app_and_pid()[0]


def frontmost_pid() -> int:
    return frontmost_app_and_pid()[1]


def activate(app: str, timeout: float = 3.0) -> bool:
    hwnd = _find_window_by_app(app)
    if not hwnd:
        return False
    _ensure_interactive_desktop()
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
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if frontmost_app() == app:
            return True
        time.sleep(0.1)
    return frontmost_app() == app


_WEB_BROWSERS = ("Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave", "Opera")


def open_url(browser: str, url: str) -> bool:
    webbrowser.open(url)
    time.sleep(1.0)
    if activate(browser):
        return True
    current = frontmost_app()
    for b in _WEB_BROWSERS:
        if b.lower() in current.lower() or current.lower() in b.lower():
            return True
    for b in _WEB_BROWSERS:
        if activate(b):
            return True
    return False


def play_media() -> None:
    """Send media play/pause key and space to start/toggle playback."""
    _ensure_interactive_desktop()
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.2)
    press("space")


def launch_or_activate_app(app: str) -> bool:
    """Activate an app if already running, or launch it and bring it to front."""
    if activate(app):
        return True

    app_lower = app.lower()
    if "spotify" in app_lower:
        with contextlib.suppress(Exception):
            os.system('start "" "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"')
        time.sleep(1.5)
        if activate("Spotify", timeout=4.0):
            return True
        with contextlib.suppress(Exception):
            os.startfile("spotify:")
        time.sleep(1.5)
        if activate("Spotify", timeout=4.0):
            return True
    elif "calc" in app_lower:
        with contextlib.suppress(Exception):
            os.startfile("calc.exe")
        time.sleep(1.0)
        return activate("Calculator")
    elif "notepad" in app_lower:
        with contextlib.suppress(Exception):
            os.startfile("notepad.exe")
        time.sleep(1.0)
        return activate("Notepad")
    elif "explorer" in app_lower or "files" in app_lower:
        with contextlib.suppress(Exception):
            os.startfile("explorer.exe")
        time.sleep(1.0)
        return activate("File Explorer")
    elif "terminal" in app_lower or "cmd" in app_lower:
        with contextlib.suppress(Exception):
            os.startfile("wt.exe")
        time.sleep(1.0)
        return activate("Windows Terminal")

    target_exe = APP_EXE_MAP.get(app, app)
    with contextlib.suppress(Exception):
        os.startfile(target_exe)
    time.sleep(1.5)
    return activate(app, timeout=3.0)


def browser_url(browser: str) -> str | None:
    """Best-effort URL from the browser address bar via UIAutomation."""
    if not _HAS_UIA:
        return None
    try:
        hwnd = _find_window_by_app(browser)
        if not hwnd:
            return None
        window = auto.ControlFromHandle(hwnd)
        if window is None:
            return None
        edit = window.EditControl(searchDepth=8, searchWaitTime=0.3)
        if edit and edit.Exists(0, 0):
            vp = edit.GetValuePattern()
            if vp:
                value = vp.Value
                if value and ("." in value or "://" in value):
                    return value if "://" in value else "https://" + value
    except Exception:
        pass
    return None


def frontmost_window_bounds(pid: int | None = None) -> tuple[float, float, float, float] | None:
    pid = frontmost_pid() if pid is None else pid
    hwnd = _main_window_for_pid(pid)
    if not hwnd:
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    x, y = float(rect.left), float(rect.top)
    w = float(rect.right - rect.left)
    h = float(rect.bottom - rect.top)
    if w > MIN_WINDOW_SIDE_PT and h > MIN_WINDOW_SIDE_PT:
        return x, y, w, h
    return None


def frontmost_window_center(pid: int | None = None) -> tuple[float, float] | None:
    bounds = frontmost_window_bounds(pid)
    if bounds is None:
        return None
    x, y, w, h = bounds
    return x + w / 2, y + h / 2


# ------------------------------------------------------------------ capture and display


def _capture_worker() -> Image.Image:
    _ensure_interactive_desktop()
    import mss

    mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
    with mss_cls() as sct:
        monitor = sct.monitors[1]  # primary monitor
        sshot = sct.grab(monitor)
        return Image.frombytes("RGB", sshot.size, sshot.rgb)


def screenshot() -> Image.Image:
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_capture_worker).result()




def display_scale(image: Image.Image) -> float:
    """Capture pixels per logical screen coordinate."""
    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    return image.width / screen_w if screen_w else 1.0


# ------------------------------------------------------------------ accessibility: focused field


def focused_field() -> Field | None:
    if not _HAS_UIA:
        return None
    _ensure_interactive_desktop()
    try:
        focused = auto.GetFocusedControl()
        if focused is None:
            return None
        ct = focused.ControlType
        role = UIA_ROLE_MAP.get(ct, "AXGroup")
        name = focused.Name or ""
        rect = focused.BoundingRectangle
        x = float(rect.left) if rect else 0.0
        y = float(rect.top) if rect else 0.0
        w = float(rect.right - rect.left) if rect else 0.0
        h = float(rect.bottom - rect.top) if rect else 0.0
        value, placeholder = "", ""
        try:
            vp = focused.GetValuePattern()
            if vp:
                value = vp.Value or ""
        except Exception:
            pass
        return Field(role=role, label=str(name), placeholder=placeholder, value=value if isinstance(value, str) else "", x=x, y=y, w=w, h=h, ref=focused)
    except Exception:
        return None


# ------------------------------------------------------------------ acting on an element

AX_PRESS = "AXPress"  # kept for compatibility with the walk


def ax_press(ref) -> bool:
    if ref is None:
        return False
    for getter in ("GetInvokePattern", "GetTogglePattern", "GetExpandCollapsePattern"):
        try:
            pattern = getattr(ref, getter)()
            if pattern is None:
                continue
            if getter == "GetInvokePattern":
                pattern.Invoke()
            elif getter == "GetTogglePattern":
                pattern.Toggle()
            else:
                pattern.Expand()
            return True
        except Exception:
            continue
    return False


def ax_focus(ref) -> bool:
    try:
        ref.SetFocus()
        return True
    except Exception:
        return False


def ax_set_value(ref, text: str) -> bool:
    try:
        pattern = ref.GetValuePattern()
        if pattern:
            pattern.SetValue(text)
            return True
    except Exception:
        pass
    return False


def ax_value(ref) -> str | None:
    try:
        pattern = ref.GetValuePattern()
        if pattern:
            val = pattern.Value
            return val if isinstance(val, str) else None
    except Exception:
        return None


# ================================================================== accessibility tree walk
# Verbatim from macos.py — the walk is platform-free, taking its bindings as callables.

AX_ACTIONABLE_ROLES = {
    "AXButton", "AXCell", "AXCheckBox", "AXComboBox", "AXDisclosureTriangle",
    "AXImage", "AXIncrementor", "AXLink", "AXMenuBarItem", "AXMenuButton",
    "AXPopUpButton", "AXRadioButton", "AXRow", "AXSearchField", "AXSlider",
    "AXTab", "AXTextArea", "AXTextField",
}
AX_LABEL_PARENT_ROLES = {
    "AXButton", "AXCell", "AXCheckBox", "AXLink", "AXMenuButton",
    "AXPopUpButton", "AXRadioButton", "AXRow", "AXTab",
}
AX_LABEL_DESCENDANT_ROLES = {"AXCell", "AXRow"}
AX_SKIP_SUBTREE_ROLES = {"AXMenu"}
AX_NODE_CAP = 4000
AX_TIME_CAP = 0.6
AX_OFFSCREEN_CAP = 120
AX_MIN_SIDE_PT = 4.0
AX_MESSAGE_TIMEOUT = 0.2
AX_FANOUT = 8
AX_VALUE_CHARS = 120

Frame = tuple[float, float, float, float]


class AxAttrs(NamedTuple):
    role: str
    label: str
    frame: Frame | None


def off_display(frame: Frame | None, display_w_pt: float, display_h_pt: float) -> bool:
    if frame is None:
        return False
    x, y, w, h = frame
    if w <= 0 or h <= 0:
        return False
    return x >= display_w_pt or y >= display_h_pt or x + w <= 0 or y + h <= 0


def node_identity(node) -> object:
    try:
        hash(node)
    except TypeError:
        return ("id", id(node))
    return node


def subtree_key(role: str, label: str, frame: Frame | None) -> tuple | None:
    if frame is None or frame[2] <= 0 or frame[3] <= 0:
        return None
    return (role, label, round(frame[0]), round(frame[1]), round(frame[2]), round(frame[3]))


def clickable(frame: Frame | None) -> bool:
    return frame is not None and min(frame[2], frame[3]) >= AX_MIN_SIDE_PT


def descendant_label(kids: list, children: Callable, attrs: Callable[..., AxAttrs]) -> str:
    for kid in kids[:AX_FANOUT]:
        role, label, _ = attrs(kid)
        if role == "AXStaticText" and label:
            return label
    for kid in kids[:AX_FANOUT]:
        for grandkid in list(children(kid))[:AX_FANOUT]:
            role, label, _ = attrs(grandkid)
            if role == "AXStaticText" and label:
                return label
    return ""


def walk_actionable(
    root,
    children: Callable[..., Iterable],
    attrs: Callable[..., AxAttrs],
    actions: Callable[..., Iterable[str]],
    display_w_pt: float,
    display_h_pt: float,
    node_cap: int = AX_NODE_CAP,
    time_cap: float = AX_TIME_CAP,
    offscreen_cap: int = AX_OFFSCREEN_CAP,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[list[AxNode], list[AxNode], bool]:
    found: list[AxNode] = []
    offscreen: list[AxNode] = []
    deadline = clock() + time_cap
    queue = deque([(root, "", False, False)])
    seen = 0
    visited: set = set()
    visited_keys: set[tuple] = set()
    while queue:
        if seen >= node_cap or clock() >= deadline:
            return found, offscreen, True
        node, parent_label, parent_emitted, hidden = queue.popleft()
        identity = node_identity(node)
        if identity in visited:
            continue
        visited.add(identity)
        seen += 1
        role, own_label, frame = attrs(node)
        if role in AX_SKIP_SUBTREE_ROLES:
            continue
        if role != "AXGroup" or own_label:
            key = subtree_key(role, own_label, frame)
            if key is not None:
                if key in visited_keys:
                    continue
                visited_keys.add(key)
        hidden = hidden or off_display(frame, display_w_pt, display_h_pt)
        if hidden and len(offscreen) >= offscreen_cap:
            continue
        kids = list(children(node))
        label, inherited = own_label, False
        if not label and role in AX_LABEL_DESCENDANT_ROLES:
            label = descendant_label(kids, children, attrs)
        if not label and parent_label:
            label, inherited = parent_label, True
        emitted = False
        duplicate = inherited and parent_emitted
        nameless_group = role == "AXGroup" and not own_label
        visible = not hidden and clickable(frame)
        if label and not duplicate and not nameless_group:
            if visible:
                pressable = AX_PRESS in actions(node)
                if pressable or role in AX_ACTIONABLE_ROLES:
                    x, y, w, h = frame
                    found.append(AxNode(role=role, label=label, x=x, y=y, w=w, h=h, pressable=pressable, ref=node))
                    emitted = True
            elif frame is not None and len(offscreen) < offscreen_cap and AX_PRESS in actions(node):
                x, y, w, h = frame
                offscreen.append(AxNode(role=role, label=label, x=x, y=y, w=w, h=h, pressable=True, ref=node))
        child_label = own_label if role in AX_LABEL_PARENT_ROLES else ""
        queue.extend((kid, child_label, emitted, hidden) for kid in kids)
    return found, offscreen, False


# ================================================================== Windows UIAutomation bindings for the walk


def _uia_children(element) -> list:
    try:
        children = element.GetChildren()
        return children if children else []
    except Exception:
        return []


_UIA_TEXT_CONTROL_TYPES: set[int] = set()
if _HAS_UIA:
    # ControlType IDs for text-like controls where GetValuePattern is useful
    _UIA_TEXT_CONTROL_TYPES = {
        getattr(auto, "EditControl", type("_", (), {"ControlType": 50004})).ControlType
        if hasattr(auto, "EditControl") else 50004,  # Edit
        50007,  # Document
        50010,  # ComboBox
    }
    # Safer: just use the raw IDs directly
    _UIA_TEXT_CONTROL_TYPES = {50004, 50007, 50010}


def _uia_label(element, control_type: int | None = None) -> str:
    try:
        name = element.Name
        if isinstance(name, str) and name.strip():
            return " ".join(name.split())
    except Exception:
        pass
    # Only query ValuePattern for text-like controls — the COM call is expensive
    if control_type is None or control_type in _UIA_TEXT_CONTROL_TYPES:
        try:
            pattern = element.GetValuePattern()
            if pattern:
                val = pattern.Value
                if isinstance(val, str) and 0 < len(val.strip()) <= AX_VALUE_CHARS:
                    return " ".join(val.split())
        except Exception:
            pass
    return ""


def _uia_attrs(element) -> AxAttrs:
    try:
        ct = element.ControlType
        role = UIA_ROLE_MAP.get(ct, "AXGroup")
        label = _uia_label(element, ct)
        rect = element.BoundingRectangle
        frame: Frame | None = None
        if rect:
            w = float(rect.right - rect.left)
            h = float(rect.bottom - rect.top)
            if w > 0 or h > 0:
                frame = (float(rect.left), float(rect.top), w, h)
        return AxAttrs(role, label, frame)
    except Exception:
        return AxAttrs("", "", None)


def _uia_actions(element) -> list[str]:
    # InvokePattern is by far the most common actionable pattern — check it first
    try:
        if element.GetInvokePattern() is not None:
            return [AX_PRESS]
    except Exception:
        pass
    # Only fall through to rarer patterns if Invoke wasn't found
    for getter in ("GetTogglePattern", "GetExpandCollapsePattern", "GetSelectionItemPattern"):
        try:
            if getattr(element, getter)() is not None:
                return [AX_PRESS]
        except Exception:
            continue
    return []


def actionable_elements(pid: int, display_w_pt: float, display_h_pt: float) -> tuple[list[AxNode], list[AxNode], bool]:
    """Labelled controls of one process: the on-screen ones, the pressable off-screen ones,
    and whether a cap cut the walk short."""
    if not _HAS_UIA:
        return [], [], False
    _ensure_interactive_desktop()
    try:
        hwnd = _main_window_for_pid(pid)
        if not hwnd:
            return [], [], False
        # Reduce UIAutomation's internal search timeout during the walk.
        # The library default is 20s which causes COM to wait for unresponsive
        # elements. Our own time_cap (AX_TIME_CAP=0.6s) handles deadlines.
        old_timeout = auto.TIME_OUT_SECOND
        auto.SetGlobalSearchTimeout(0.02)
        try:
            root = auto.ControlFromHandle(hwnd)
            if root is None:
                return [], [], False
            return walk_actionable(root, _uia_children, _uia_attrs, _uia_actions, display_w_pt, display_h_pt)
        finally:
            auto.SetGlobalSearchTimeout(old_timeout)
    except Exception:
        return [], [], False

"""Android platform adapter using ADB."""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
from io import BytesIO

from PIL import Image

from .config import ABORT_CORNER_PX
from .models import Abort, AxNode, Field

logger = logging.getLogger(__name__)

ANDROID_ROLE_MAP = {
    "android.widget.Button": "AXButton",
    "android.widget.ImageButton": "AXButton",
    "android.widget.EditText": "AXTextField",
    "android.widget.AutoCompleteTextView": "AXTextField",
    "android.widget.MultiAutoCompleteTextView": "AXTextField",
    "android.widget.CheckBox": "AXCheckBox",
    "android.widget.Switch": "AXCheckBox",
    "android.widget.ToggleButton": "AXCheckBox",
    "android.widget.RadioButton": "AXRadioButton",
    "android.widget.ImageView": "AXImage",
    "android.widget.TextView": "AXStaticText",
    "android.widget.Spinner": "AXComboBox",
    "android.widget.SeekBar": "AXSlider",
    "android.widget.ProgressBar": "AXSlider",
    "android.widget.TabHost": "AXTab",
    "android.widget.TabWidget": "AXTab",
    "android.webkit.WebView": "AXGroup",
    "android.widget.ListView": "AXGroup",
    "android.widget.GridView": "AXGroup",
    "android.widget.ScrollView": "AXGroup",
    "android.widget.HorizontalScrollView": "AXGroup",
    "androidx.recyclerview.widget.RecyclerView": "AXGroup",
    "android.widget.FrameLayout": "AXGroup",
    "android.widget.LinearLayout": "AXGroup",
    "android.widget.RelativeLayout": "AXGroup",
    "android.view.View": "AXGroup",
    "android.view.ViewGroup": "AXGroup",
}

APP_PACKAGE_MAP = {
    "Chrome": "com.android.chrome",
    "Google Chrome": "com.android.chrome",
    "Settings": "com.android.settings",
    "Calculator": "com.google.android.calculator",
    "Camera": "com.android.camera",
    "Files": "com.google.android.apps.nbu.files",
    "YouTube": "com.google.android.youtube",
    "Gmail": "com.google.android.gm",
    "Maps": "com.google.android.apps.maps",
    "Phone": "com.android.dialer",
    "Messages": "com.google.android.apps.messaging",
    "Clock": "com.android.deskclock",
    "Contacts": "com.google.android.contacts",
}

KEYCODES = {
    "return": "KEYCODE_ENTER",
    "tab": "KEYCODE_TAB",
    "escape": "KEYCODE_BACK",
    "delete": "KEYCODE_DEL",
    "space": "KEYCODE_SPACE",
    "a": "KEYCODE_A",
    "home": "KEYCODE_HOME",
    "back": "KEYCODE_BACK",
}


def _adb(cmd: str, timeout: float = 5.0) -> str:
    """Run an adb command."""
    adb_serial = os.environ.get("ADB_SERIAL")
    base_cmd = ["adb"]
    if adb_serial:
        base_cmd.extend(["-s", adb_serial])
    
    # Check if cmd needs shell execution
    if isinstance(cmd, str):
        full_cmd = base_cmd + shlex.split(cmd)
    else:
        full_cmd = base_cmd + cmd
        
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"ADB command failed: {' '.join(full_cmd)}")
        logger.error(f"Error output: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error(f"ADB command timed out: {' '.join(full_cmd)}")
        raise


def _adb_bytes(cmd: str, timeout: float = 5.0) -> bytes:
    """Run an adb command and return raw bytes."""
    adb_serial = os.environ.get("ADB_SERIAL")
    base_cmd = ["adb"]
    if adb_serial:
        base_cmd.extend(["-s", adb_serial])
        
    if isinstance(cmd, str):
        full_cmd = base_cmd + shlex.split(cmd)
    else:
        full_cmd = base_cmd + cmd
        
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            timeout=timeout,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"ADB bytes command failed: {' '.join(full_cmd)}")
        raise


def _dump_ui_xml() -> str:
    """Dump the UI hierarchy as XML."""
    return _adb("exec-out uiautomator dump /dev/tty")


def _parse_bounds(bounds_input: str | tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Parse bounds string like [0,0][1080,2400] to (x, y, w, h), or pass through tuple."""
    if isinstance(bounds_input, (tuple, list)):
        return tuple(float(v) for v in bounds_input)
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", str(bounds_input))
    if not match:
        return 0.0, 0.0, 0.0, 0.0
    left, top, right, bottom = map(float, match.groups())
    return left, top, right - left, bottom - top


def mouse_location() -> tuple[float, float]:
    """Not applicable on Android."""
    return 0.0, 0.0


def check_abort() -> None:
    """Check for abort sentinel file."""
    try:
        res = _adb("shell ls /sdcard/argus_abort", timeout=1.0)
        if "/sdcard/argus_abort" in res:
            _adb("shell rm /sdcard/argus_abort")
            raise Abort()
    except subprocess.CalledProcessError:
        pass


def sleep_watching(seconds: float) -> None:
    """Sleep while watching for abort."""
    end = time.time() + seconds
    while time.time() < end:
        check_abort()
        time.sleep(min(0.5, end - time.time()))


def accessibility_trusted() -> bool:
    """Always trusted via ADB."""
    return True


def click_at(point: tuple[float, float]) -> None:
    """Tap at the given coordinates."""
    x, y = int(point[0]), int(point[1])
    _adb(f"shell input tap {x} {y}")


def press(key: str, command: bool = False) -> None:
    """Press a key."""
    key_clean = key.strip()
    if key_clean.upper().startswith("KEYCODE_"):
        keycode = key_clean.upper()
    else:
        keycode = KEYCODES.get(key_clean.lower(), f"KEYCODE_{key_clean.upper()}")
    _adb(f"shell input keyevent {keycode}")


def type_text(text: str) -> None:
    """Type text."""
    # Escape special characters for shell
    escaped = shlex.quote(text)
    _adb(f"shell input text {escaped}")


def clear_field() -> None:
    """Clear field by focusing, selecting all, and deleting."""
    _adb("shell input keyevent KEYCODE_MOVE_END")
    for _ in range(50):
        _adb("shell input keyevent KEYCODE_DEL", timeout=0.5)


def scroll(lines: int) -> None:
    """Scroll vertically."""
    try:
        size = _adb("shell wm size")
        match = re.search(r"(\d+)x(\d+)", str(size))
        if match:
            w, h = map(int, match.groups())
        else:
            w, h = 1080, 2400
    except Exception:
        w, h = 1080, 2400
    cx = w // 2
    cy = h // 2
    start_y = cy + (200 if lines > 0 else -200)
    end_y = cy - (200 if lines > 0 else -200)
    _adb(f"shell input swipe {cx} {start_y} {cx} {end_y} 300")


def frontmost_app_and_pid() -> tuple[str, int]:
    """Get frontmost app package and its PID."""
    out = _adb("shell dumpsys activity activities")
    app = ""
    pid = 0
    # Search for mResumedActivity or Hist / ActivityRecord
    for line in str(out).splitlines():
        if "mResumedActivity" in line or "ActivityRecord{" in line or "Hist #" in line:
            match = re.search(r" ([a-zA-Z0-9_.]+)/", line)
            if match:
                pkg = match.group(1)
                # Map package back to friendly name if known
                app = pkg
                for name, p in APP_PACKAGE_MAP.items():
                    if p == pkg:
                        app = name
                        break
                break
    
    if app:
        try:
            target_pkg = APP_PACKAGE_MAP.get(app, app)
            ps_out = _adb(f"shell pidof {target_pkg}", timeout=2.0)
            if ps_out and str(ps_out).split():
                pid = int(str(ps_out).split()[0])
        except Exception:
            pid = 0
            
    return app, pid


def frontmost_app() -> str:
    """Get frontmost app package."""
    return frontmost_app_and_pid()[0]


def frontmost_pid() -> int:
    """Get frontmost app PID."""
    return frontmost_app_and_pid()[1]


def activate(app: str, timeout: float = 3.0) -> bool:
    """Activate an app by package name or common name."""
    pkg = APP_PACKAGE_MAP.get(app, app)
    try:
        _adb(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        time.sleep(timeout)
        return True
    except subprocess.CalledProcessError:
        return False


def open_url(browser: str, url: str) -> bool:
    """Open URL."""
    try:
        _adb(f"shell am start -a android.intent.action.VIEW -d {shlex.quote(url)}")
        return True
    except subprocess.CalledProcessError:
        return False


def play_media() -> None:
    """Play/pause media."""
    _adb("shell input keyevent KEYCODE_MEDIA_PLAY_PAUSE")


def launch_or_activate_app(app: str) -> bool:
    """Launch or activate an app."""
    return activate(app)


def browser_url(browser: str) -> str | None:
    """Try to extract URL from the browser."""
    xml_str = _dump_ui_xml()
    try:
        root = ET.fromstring(xml_str)
        # Look for EditText with ID com.android.chrome:id/url_bar
        for node in root.iter("node"):
            res_id = node.get("resource-id", "")
            if "url_bar" in res_id:
                return node.get("text")
    except Exception:
        pass
    return None


def frontmost_window_bounds(pid: int | None = None) -> tuple[float, float, float, float] | None:
    """Get frontmost window bounds. On Android, usually the whole screen."""
    size = _adb("shell wm size")
    match = re.search(r"(\d+)x(\d+)", size)
    if match:
        w, h = map(float, match.groups())
        return 0.0, 0.0, w, h
    return None


def frontmost_window_center(pid: int | None = None) -> tuple[float, float] | None:
    """Get frontmost window center."""
    bounds = frontmost_window_bounds(pid)
    if bounds:
        x, y, w, h = bounds
        return x + w / 2, y + h / 2
    return None


def screenshot() -> Image.Image:
    """Take a screenshot."""
    png_bytes = _adb_bytes("exec-out screencap -p")
    return Image.open(BytesIO(png_bytes))


def display_scale(image: Image.Image) -> float:
    """Return the display scale."""
    # Often 1.0 on Android for raw coordinates, but can differ if wm size overrides physical size
    # For now, return 1.0 or calculate based on image size vs wm size
    out = _adb("shell wm size")
    # Physical size: 1080x2400
    match = re.search(r"Physical size: (\d+)x(\d+)", out)
    if match:
        w = int(match.group(1))
        # Image width might be w
        return image.width / w
    return 1.0


def focused_field() -> Field | None:
    """Return the focused field if any."""
    xml_str = _dump_ui_xml()
    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            if node.get("focused") == "true" and node.get("class") in ("android.widget.EditText", "android.widget.AutoCompleteTextView"):
                bounds_str = node.get("bounds", "")
                x, y, w, h = _parse_bounds(bounds_str)
                text = node.get("text", "")
                role = ANDROID_ROLE_MAP.get(node.get("class", ""), "AXTextField")
                label = node.get("text") or node.get("content-desc") or ""
                placeholder = node.get("content-desc") or ""
                return Field(
                    role=role,
                    label=label,
                    placeholder=placeholder,
                    value=text,
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    ref={"bounds": bounds_str, "id": node.get("resource-id"), "class": node.get("class")}
                )
    except Exception as e:
        logger.debug(f"Failed to find focused field: {e}")
    return None


def ax_press(ref) -> bool:
    """Press an accessibility node."""
    if not isinstance(ref, dict):
        return False
    bounds_val = ref.get("bounds")
    if bounds_val is None:
        return False
    x, y, w, h = _parse_bounds(bounds_val)
    cx, cy = x + w / 2, y + h / 2
    click_at((cx, cy))
    return True


def ax_focus(ref) -> bool:
    """Focus an accessibility node."""
    return ax_press(ref)


def ax_set_value(ref, text: str) -> bool:
    """Set value of an accessibility node."""
    if ax_focus(ref):
        clear_field()
        type_text(text)
        return True
    return False


def ax_value(ref) -> str | None:
    """Get value of an accessibility node."""
    if not isinstance(ref, dict) or not ref.get("id"):
        return None
    xml_str = _dump_ui_xml()
    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            if node.get("resource-id") == ref.get("id"):
                return node.get("text")
    except Exception:
        pass
    return None


def actionable_elements(pid: int, display_w_pt: float, display_h_pt: float) -> tuple[list[AxNode], list[AxNode], bool]:
    """Parse UIAutomator XML into AxNodes."""
    xml_str = _dump_ui_xml()
    elements: list[AxNode] = []
    
    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            clickable = node.get("clickable") == "true"
            focusable = node.get("focusable") == "true"
            editable = node.get("class") in ("android.widget.EditText", "android.widget.AutoCompleteTextView")
            
            if not (clickable or focusable or editable):
                continue
                
            bounds_str = node.get("bounds", "")
            x, y, w, h = _parse_bounds(bounds_str)
            if w <= 0 or h <= 0:
                continue
                
            cls = node.get("class", "")
            role = ANDROID_ROLE_MAP.get(cls, "AXGroup")
            
            text = node.get("text") or node.get("content-desc") or ""
            
            elements.append(
                AxNode(
                    role=role,
                    label=text,
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    pressable=clickable or editable,
                    ref={"bounds": bounds_str, "id": node.get("resource-id"), "class": cls}
                )
            )
            
    except Exception as e:
        logger.error(f"Failed to parse UI XML: {e}")
        
    return elements, [], False

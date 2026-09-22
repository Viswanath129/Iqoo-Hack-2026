"""Unit tests for the Android platform adapter."""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from typesafe_computer_use import android
from typesafe_computer_use.models import Abort, AxNode, Field


SAMPLE_UIAUTOMATOR_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[0,0][1080,2400]">
    <node index="0" text="Settings" resource-id="com.android.settings:id/title" class="android.widget.TextView" package="com.android.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[48,120][400,200]" />
    <node index="1" text="" resource-id="com.android.settings:id/search_action_bar" class="android.widget.EditText" package="com.android.settings" content-desc="Search settings" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="true" scrollable="false" long-clickable="true" password="false" selected="false" bounds="[48,240][1032,360]" />
    <node index="2" text="Network &amp; internet" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[192,400][800,460]" />
    <node index="3" text="" resource-id="com.android.settings:id/wifi_switch" class="android.widget.Switch" package="com.android.settings" content-desc="Wi-Fi" checkable="true" checked="true" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[880,390][1032,470]" />
    <node index="4" text="Save" resource-id="com.android.settings:id/save_btn" class="android.widget.Button" package="com.android.settings" content-desc="" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[400,2100][680,2220]" />
  </node>
</hierarchy>
"""


def test_mouse_location():
    assert android.mouse_location() == (0.0, 0.0)


def test_accessibility_trusted():
    assert android.accessibility_trusted() is True


def test_check_abort_not_triggered():
    with patch("typesafe_computer_use.android._adb", return_value="File does not exist"):
        android.check_abort()  # Should not raise


def test_check_abort_triggered():
    with patch("typesafe_computer_use.android._adb", return_value="/sdcard/argus_abort"):
        with pytest.raises(Abort):
            android.check_abort()


def test_click_at():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.click_at((540.0, 960.0))
        mock_adb.assert_called_once_with("shell input tap 540 960")


def test_press_known_key():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.press("return")
        mock_adb.assert_called_once_with("shell input keyevent KEYCODE_ENTER")


def test_press_custom_key():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.press("KEYCODE_HOME")
        mock_adb.assert_called_once_with("shell input keyevent KEYCODE_HOME")


def test_type_text():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.type_text("hello world")
        mock_adb.assert_called_once()
        args = mock_adb.call_args[0][0]
        assert "shell input text" in args
        assert "hello" in args


def test_clear_field():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.clear_field()
        assert mock_adb.call_count >= 1


def test_scroll():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.scroll(-5)  # Scroll down
        assert mock_adb.call_count >= 1
        last_call = mock_adb.call_args_list[-1][0][0]
        assert "shell input swipe" in last_call


def test_frontmost_app_and_pid():
    dumpsys_output = "  * Hist #0: ActivityRecord{abc u0 com.android.settings/.SettingsActivity t100}"
    with patch("typesafe_computer_use.android._adb", return_value=dumpsys_output):
        app, pid = android.frontmost_app_and_pid()
        assert app == "Settings"
        assert isinstance(pid, int)


def test_activate():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        success = android.activate("Settings")
        assert success is True
        mock_adb.assert_called_once()
        args = mock_adb.call_args[0][0]
        assert "com.android.settings" in args


def test_open_url():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        success = android.open_url("Chrome", "https://github.com")
        assert success is True
        mock_adb.assert_called_once()
        args = mock_adb.call_args[0][0]
        assert "android.intent.action.VIEW" in args
        assert "https://github.com" in args


def test_play_media():
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        android.play_media()
        mock_adb.assert_called_once_with("shell input keyevent KEYCODE_MEDIA_PLAY_PAUSE")


def test_screenshot():
    # Generate in-memory PNG bytes
    img = Image.new("RGBA", (1080, 2400), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=raw_bytes, returncode=0)
        captured = android.screenshot()
        assert captured.size == (1080, 2400)


def test_display_scale():
    img = Image.new("RGBA", (1080, 2400))
    with patch("typesafe_computer_use.android._adb", return_value="Physical size: 1080x2400"):
        scale = android.display_scale(img)
        assert scale == 1.0


def test_focused_field():
    with patch("typesafe_computer_use.android._dump_ui_xml", return_value=SAMPLE_UIAUTOMATOR_XML):
        field = android.focused_field()
        assert field is not None
        assert field.role == "AXTextField"
        assert field.placeholder == "Search settings"


def test_actionable_elements():
    with patch("typesafe_computer_use.android._dump_ui_xml", return_value=SAMPLE_UIAUTOMATOR_XML):
        onscreen, offscreen, truncated = android.actionable_elements(1234, 1080.0, 2400.0)
        assert len(onscreen) >= 3
        roles = [node.role for node in onscreen]
        assert "AXTextField" in roles
        assert "AXButton" in roles
        assert "AXCheckBox" in roles


def test_ax_press():
    node_ref = {"bounds": "[400,2100][680,2220]"}
    with patch("typesafe_computer_use.android._adb") as mock_adb:
        success = android.ax_press(node_ref)
        assert success is True
        mock_adb.assert_called_once_with("shell input tap 540 2160")

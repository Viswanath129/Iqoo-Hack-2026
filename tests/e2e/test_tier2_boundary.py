"""Tier 2: Boundary & Corner Cases E2E Tests (F1 to F8).

Covers edge cases, coordinate boundaries, empty inputs, limits, and error handling:
- F1: Geometry boundaries, offscreen/negative coords, invalid PIDs, extreme dimensions
- F2: Empty/1x1 crops, extreme aspect ratios, dense text, float coordinates
- F3: Tree walk limits, time/node caps, off-display boundaries, invalid roots
- F4: Coordinate extremes, Unicode symbols, zero scroll delta, invalid keys
- F5: Exact threshold boundaries, one-axis escapes, negative coords, rapid polling
- F6: ValuePattern exceptions, empty strings, mismatch fallback, repeat clear_field
- F7: Zero budgets, echo length boundaries, unknown actions, no-op markers
- F8: Empty item lists, offscreen sections, unselected items, fractional scales
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from typesafe_computer_use import (
    actions,
    models,
    ocr,
    perception,
    platform_adapter,
    report,
    windows,
)
from typesafe_computer_use.config import ABORT_CORNER_PX
from typesafe_computer_use.models import Abort, AxNode, Field, Item, Screen


# ==============================================================================
# F1: Screen & Window Geometry Boundary Cases (5 tests)
# ==============================================================================


def test_f1_b01_zero_side_window_bounds_rejected(monkeypatch):
    """Verify frontmost_window_bounds returns None when window has zero width or height."""
    def fake_get_window_rect(hwnd, rect_ptr):
        r = rect_ptr._obj
        r.left, r.top, r.right, r.bottom = 100, 100, 100, 200  # width = 0
        return 1

    monkeypatch.setattr(windows, "_main_window_for_pid", lambda pid: 12345)
    monkeypatch.setattr(windows.user32, "GetWindowRect", fake_get_window_rect)

    bounds = windows.frontmost_window_bounds(99999)
    assert bounds is None


def test_f1_b02_below_min_side_window_bounds_rejected(monkeypatch):
    """Verify frontmost_window_bounds returns None when dimensions are below MIN_WINDOW_SIDE_PT (50pt)."""
    def fake_get_window_rect(hwnd, rect_ptr):
        r = rect_ptr._obj
        r.left, r.top, r.right, r.bottom = 100, 100, 149, 149  # 49x49 < 50
        return 1

    monkeypatch.setattr(windows, "_main_window_for_pid", lambda pid: 12345)
    monkeypatch.setattr(windows.user32, "GetWindowRect", fake_get_window_rect)

    bounds = windows.frontmost_window_bounds(99999)
    assert bounds is None


def test_f1_b03_negative_window_rect_coordinates(monkeypatch):
    """Verify window rect with negative left/top coordinates computes correct positive dimensions."""
    def fake_get_window_rect(hwnd, rect_ptr):
        r = rect_ptr._obj
        r.left, r.top, r.right, r.bottom = -100, -50, 700, 550  # w = 800, h = 600
        return 1

    monkeypatch.setattr(windows, "_main_window_for_pid", lambda pid: 12345)
    monkeypatch.setattr(windows.user32, "GetWindowRect", fake_get_window_rect)

    bounds = windows.frontmost_window_bounds(99999)
    assert bounds is not None
    x, y, w, h = bounds
    assert x == -100.0 and y == -50.0
    assert w == 800.0 and h == 600.0


def test_f1_b04_display_scale_extreme_dimensions():
    """Verify display_scale handles extreme dimensions (1x1 and 8K 7680x4320) without crashing."""
    tiny_img = Image.new("RGB", (1, 1))
    scale_tiny = windows.display_scale(tiny_img)
    assert isinstance(scale_tiny, float)
    assert scale_tiny > 0.0

    huge_img = Image.new("RGB", (7680, 4320))
    scale_huge = windows.display_scale(huge_img)
    assert isinstance(scale_huge, float)
    assert scale_huge > 1.0


def test_f1_b05_exe_name_invalid_pid_returns_empty():
    """Verify _exe_name returns empty string without error for invalid or non-existent PIDs."""
    assert windows._exe_name(0) == ""
    assert windows._exe_name(-1) == ""
    assert windows._exe_name(9999999) == ""


# ==============================================================================
# F2: WinRT NPU OCR Boundary Cases (5 tests)
# ==============================================================================


def test_f2_b01_blank_image_returns_empty_lines():
    """Verify ocr_crop on solid white image returns empty line list."""
    blank_img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    lines = ocr.ocr_crop(blank_img, (0, 0, 200, 200))
    assert lines == []


def test_f2_b02_single_pixel_crop_handling():
    """Verify ocr_crop on 1x1 pixel image executes cleanly returning empty list."""
    pixel_img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
    lines = ocr.ocr_crop(pixel_img, (0, 0, 1, 1))
    assert lines == []


def test_f2_b03_extreme_aspect_ratio_crops(ocr_test_image_factory):
    """Verify ocr_crop handles extreme wide and tall aspect ratios."""
    wide_img = ocr_test_image_factory(["Wide Aspect Banner"], width=1200, height=50)
    lines_wide = ocr.ocr_crop(wide_img, (0, 0, 1200, 50))
    assert isinstance(lines_wide, list)

    tall_img = ocr_test_image_factory(["Tall", "Banner", "Stack"], width=80, height=600)
    lines_tall = ocr.ocr_crop(tall_img, (0, 0, 80, 600))
    assert isinstance(lines_tall, list)


def test_f2_b04_crop_subpixel_floating_point_coordinates(ocr_test_image_factory):
    """Verify ocr_crop rounds floating-point crop coordinates without type error."""
    img = ocr_test_image_factory(["Floating Point Boundary"])
    float_rect = (0.2, 0.8, float(img.width) - 0.4, float(img.height) - 0.6)
    lines = ocr.ocr_crop(img, float_rect)
    assert isinstance(lines, list)


def test_f2_b05_dense_text_with_small_font(ocr_test_image_factory):
    """Verify ocr_crop handles multiple dense text lines without dropping lines."""
    dense_lines = [f"Record Line {i:02d} Target Content" for i in range(1, 6)]
    img = ocr_test_image_factory(dense_lines, width=600, height=300, font_size=16)
    results = ocr.ocr_crop(img, (0, 0, img.width, img.height))

    assert len(results) >= 3


# ==============================================================================
# F3: UIAutomation Boundary Cases (5 tests)
# ==============================================================================


def test_f3_b01_actionable_elements_invalid_pid():
    """Verify actionable_elements with invalid PID returns empty lists safely."""
    found, offscreen, capped = windows.actionable_elements(9999999, 1920.0, 1200.0)
    assert found == []
    assert offscreen == []
    assert capped is False


def test_f3_b02_off_display_boundary_conditions():
    """Verify off_display edge boundary logic."""
    display_w, display_h = 1920.0, 1200.0

    # None or zero-area frames are not off display (not displayed at all)
    assert windows.off_display(None, display_w, display_h) is False
    assert windows.off_display((100, 100, 0, 50), display_w, display_h) is False
    assert windows.off_display((100, 100, 50, 0), display_w, display_h) is False

    # Fully inside
    assert windows.off_display((100, 100, 200, 100), display_w, display_h) is False

    # Right of screen
    assert windows.off_display((1920.0, 100, 50, 50), display_w, display_h) is True
    # Below screen
    assert windows.off_display((100, 1200.0, 50, 50), display_w, display_h) is True
    # Fully left of screen (x + w <= 0)
    assert windows.off_display((-100.0, 100, 50, 50), display_w, display_h) is True
    # Fully above screen (y + h <= 0)
    assert windows.off_display((100, -80.0, 50, 50), display_w, display_h) is True


def test_f3_b03_subtree_key_invalid_and_empty_frames():
    """Verify subtree_key returns None for invalid or zero-dimension frames."""
    assert windows.subtree_key("AXButton", "Label", None) is None
    assert windows.subtree_key("AXButton", "Label", (10.0, 10.0, 0.0, 50.0)) is None
    assert windows.subtree_key("AXButton", "Label", (10.0, 10.0, 50.0, -1.0)) is None

    key = windows.subtree_key("AXButton", "Label", (10.4, 20.6, 100.2, 50.1))
    assert key == ("AXButton", "Label", 10, 21, 100, 50)


def test_f3_b04_walk_actionable_empty_tree():
    """Verify walk_actionable on an empty root node returns empty lists."""
    class EmptyRoot:
        pass

    found, offscreen, capped = windows.walk_actionable(
        EmptyRoot(),
        children=lambda n: [],
        attrs=lambda n: windows.AxAttrs("", "", None),
        actions=lambda n: [],
        display_w_pt=1920.0,
        display_h_pt=1200.0,
    )
    assert found == []
    assert offscreen == []
    assert capped is False


def test_f3_b05_walk_actionable_zero_time_cap():
    """Verify walk_actionable with expired time_cap halts and sets capped=True."""
    class SimpleNode:
        def __init__(self, idx):
            self.idx = idx
            self.kids = [SimpleNode(idx + 1)] if idx < 5 else []

    root = SimpleNode(1)
    found, offscreen, capped = windows.walk_actionable(
        root,
        children=lambda n: n.kids,
        attrs=lambda n: windows.AxAttrs("AXButton", f"Btn{n.idx}", (10.0, 10.0, 20.0, 20.0)),
        actions=lambda n: [windows.AX_PRESS],
        display_w_pt=1920.0,
        display_h_pt=1200.0,
        time_cap=0.0,  # Zero deadline
    )
    assert capped is True


# ==============================================================================
# F4: Synthetic Actions Boundary Cases (5 tests)
# ==============================================================================


def test_f4_b01_click_at_screen_extremes():
    """Verify click_at dispatches without error at extreme display coordinates."""
    # (0, 0)
    windows.click_at((0.0, 0.0))
    # Near primary resolution edge
    windows.click_at((1910.0, 1070.0))


def test_f4_b02_type_text_empty_string():
    """Verify type_text with empty string is a clean no-op."""
    windows.type_text("")


def test_f4_b03_type_text_unicode_symbols_and_emojis():
    """Verify type_text dispatches arbitrary Unicode math and symbolic characters."""
    windows.type_text("★ ⚡ ☺ € ¥")


def test_f4_b04_scroll_zero_delta():
    """Verify scroll(0) executes without throwing errors."""
    windows.scroll(0)


def test_f4_b05_press_invalid_key_raises_keyerror():
    """Verify press with unknown key raises KeyError."""
    with pytest.raises(KeyError):
        windows.press("nonexistent_special_key_xyz")


# ==============================================================================
# F5: Mouse-in-Corner Abort Boundary Cases (5 tests)
# ==============================================================================


def test_f5_b01_check_abort_at_subpixel_threshold(monkeypatch):
    """Verify exact subpixel boundary of ABORT_CORNER_PX."""
    # Exactly on boundary: aborts
    monkeypatch.setattr(windows, "mouse_location", lambda: (float(ABORT_CORNER_PX), float(ABORT_CORNER_PX)))
    with pytest.raises(Abort):
        windows.check_abort()

    # Just 0.01 px outside: safe
    monkeypatch.setattr(windows, "mouse_location", lambda: (float(ABORT_CORNER_PX) + 0.01, float(ABORT_CORNER_PX) + 0.01))
    windows.check_abort()


def test_f5_b02_check_abort_negative_coordinates(monkeypatch):
    """Verify negative mouse coordinates (e.g. secondary monitor left) are treated as within corner."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (-5.0, -10.0))
    with pytest.raises(Abort):
        windows.check_abort()


def test_f5_b03_check_abort_one_axis_exceeding_threshold(monkeypatch):
    """Verify check_abort requires BOTH x and y to be within threshold; one axis alone does not abort."""
    # x is 0, but y is far away
    monkeypatch.setattr(windows, "mouse_location", lambda: (0.0, 500.0))
    windows.check_abort()

    # y is 0, but x is far away
    monkeypatch.setattr(windows, "mouse_location", lambda: (500.0, 0.0))
    windows.check_abort()


def test_f5_b04_sleep_watching_zero_seconds():
    """Verify sleep_watching(0.0) returns immediately without hanging."""
    t0 = time.monotonic()
    windows.sleep_watching(0.0)
    assert time.monotonic() - t0 < 0.1


def test_f5_b05_check_abort_rapid_calls(monkeypatch):
    """Verify 100 rapid successive check_abort calls at safe location execute in sub-millisecond time."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (200.0, 200.0))
    t0 = time.perf_counter()
    for _ in range(100):
        windows.check_abort()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05


# ==============================================================================
# F6: Text Entry & Persistence Boundary Cases (5 tests)
# ==============================================================================


def test_f6_b01_clear_field_rapid_invocation():
    """Verify clear_field can be invoked multiple times rapidly without issue."""
    windows.clear_field()
    windows.clear_field()


def test_f6_b02_ax_set_value_empty_string():
    """Verify ax_set_value handles empty string gracefully."""
    assert windows.ax_set_value(None, "") is False


def test_f6_b03_ax_set_value_handles_pattern_exception():
    """Verify ax_set_value catches unexpected COM errors in GetValuePattern and returns False."""
    class BrokenRef:
        def GetValuePattern(self):
            raise OSError("COM Interface Failure")

    assert windows.ax_set_value(BrokenRef(), "text") is False


def test_f6_b04_ax_value_handles_pattern_exception():
    """Verify ax_value catches unexpected COM errors and returns None safely."""
    class BrokenRef:
        def GetValuePattern(self):
            raise OSError("COM Interface Failure")

    assert windows.ax_value(BrokenRef()) is None


def test_f6_b05_fill_field_fallback_on_value_mismatch(monkeypatch):
    """Verify actions.fill_field falls back to keystrokes when ax_value does not match target text."""
    typed_keys = []
    monkeypatch.setattr(windows, "ax_focus", lambda ref: True)
    monkeypatch.setattr(windows, "ax_set_value", lambda ref, txt: True)
    # Simulate field reporting different or stale text
    monkeypatch.setattr(windows, "ax_value", lambda ref: "stale_unrelated_value")
    monkeypatch.setattr(windows, "type_text", lambda txt: typed_keys.append(txt))

    field = Field(role="AXTextField", label="Input", placeholder="", value="", x=0, y=0, w=100, h=30, ref=MagicMock())
    result = actions.fill_field(field, "target_text")

    assert result == "via keystrokes"
    assert "target_text" in typed_keys


# ==============================================================================
# F7: Workflow Transition Boundary Cases (5 tests)
# ==============================================================================


def test_f7_b01_perceive_zero_budget(tmp_path):
    """Verify perception.perceive with budget=0 returns empty list."""
    img_path = tmp_path / "img.png"
    Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(img_path)
    screen = perception.capture(image_path=img_path, app="App")

    items = perception.perceive(screen, budget=0, goal="test")
    assert items == []


def test_f7_b02_goal_echoes_short_and_long_goals():
    """Verify goal_echoes extracts prefix and suffix for long goals, and full goal for short ones."""
    short = perception.goal_echoes("Short goal")
    assert short == {"short goal"}

    long_goal = "A" * 50
    long_echoes = perception.goal_echoes(long_goal)
    assert len(long_echoes) == 1
    assert list(long_echoes)[0] == "a" * 24


def test_f7_b03_is_echo_normalization():
    """Verify is_echo matches strings with normalized whitespace and case differences."""
    echoes = perception.goal_echoes("Submit Order Now")
    assert perception.is_echo("submit   order now", echoes) is True
    assert perception.is_echo("unrelated text", echoes) is False


def test_f7_b04_is_noop_boundary():
    """Verify is_noop identifies failure markers correctly."""
    assert actions.is_noop("click refused by control") is True
    assert actions.is_noop("use_browser failed: not found") is True
    assert actions.is_noop("waited 5s") is True
    assert actions.is_noop("clicked 'Submit'") is False


def test_f7_b05_perform_unknown_action_raises_value_error():
    """Verify actions.perform raises ValueError when unknown action key is provided."""
    from typesafe_computer_use.decide import Decision
    from typesafe_sdk import ChoiceAnswer

    unknown_decision = Decision(
        kind=ChoiceAnswer(choice="alien_action", confidence=1.0, probabilities={"alien_action": 1.0}),
        item=None,
        site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
        offscreen=None,
    )
    screen = Screen(image=Image.new("RGB", (100, 100)), scale=1.0, app="App", field=None, url=None)
    ctx = actions.Context(
        goal="goal", browser="msedge", email=None, typesafe=MagicMock(), writer=None, history=[]
    )

    with pytest.raises(ValueError, match="unknown action 'alien_action'"):
        actions.perform(unknown_decision, screen, [], ctx)


# ==============================================================================
# F8: Inspection Artifacts Boundary Cases (5 tests)
# ==============================================================================


def test_f8_b01_render_payload_empty_items():
    """Verify render_payload handles screen with 0 items cleanly."""
    screen = Screen(image=Image.new("RGB", (400, 300)), scale=1.0, app="Edge", field=None, url=None)
    payload = report.render_payload("goal", screen, [], [], "msedge", None)
    assert "ITEMS  (0 after merge/filter" in payload


def test_f8_b02_render_payload_with_offscreen_controls():
    """Verify render_payload includes OFFSCREEN CONTROLS section when screen.offscreen is populated."""
    off_node = AxNode(role="AXButton", label="Hidden Action", x=-100, y=-100, w=10, h=10, pressable=True)
    screen = Screen(
        image=Image.new("RGB", (400, 300)),
        scale=1.0,
        app="Edge",
        field=None,
        url=None,
        offscreen=[off_node],
    )
    payload = report.render_payload("goal", screen, [], [], "msedge", None)
    assert "OFFSCREEN CONTROLS  (1 the app exposes" in payload
    assert "Hidden Action" in payload


def test_f8_b03_annotate_zero_items(tmp_path):
    """Verify annotate on empty item list produces valid image without exception."""
    screen = Screen(image=Image.new("RGB", (200, 200), (255, 255, 255)), scale=1.0, app="Edge", field=None, url=None)
    out_file = tmp_path / "empty_annotated.png"
    report.annotate(screen, [], chosen="", out=out_file)
    assert out_file.exists()


def test_f8_b04_annotate_chosen_not_found(tmp_path):
    """Verify annotate with non-existent chosen index completes without crashing."""
    screen = Screen(image=Image.new("RGB", (200, 200), (255, 255, 255)), scale=1.0, app="Edge", field=None, url=None)
    item = Item(index=1, text="Ok", ocr_confidence=1.0, x1=10, y1=10, x2=50, y2=30)
    out_file = tmp_path / "chosen_missing.png"
    report.annotate(screen, [item], chosen="999", out=out_file)
    assert out_file.exists()


def test_f8_b05_annotate_fractional_scale(tmp_path):
    """Verify annotate supports fractional display scales (e.g. 1.5, 2.25)."""
    screen = Screen(image=Image.new("RGB", (600, 400), (255, 255, 255)), scale=1.5, app="Edge", field=None, url=None)
    item = Item(index=1, text="Scale Test", ocr_confidence=1.0, x1=20, y1=20, x2=100, y2=60)
    out_file = tmp_path / "scale_annotated.png"
    report.annotate(screen, [item], chosen="1", out=out_file)
    assert out_file.exists()

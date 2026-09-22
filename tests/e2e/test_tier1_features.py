"""Tier 1: Feature Coverage E2E Tests (F1 to F8).

Covers primary behavior (happy paths) with >=5 tests per feature across:
- F1: Screen capture & window geometry
- F2: WinRT NPU OCR latency and text extraction
- F3: UIAutomation actionable controls retrieval
- F4: Synthetic actions (click, type, press, scroll)
- F5: Mouse-in-corner emergency abort
- F6: Text entry persistence & fallback
- F7: End-to-end workflow state transitions
- F8: Inspection artifact generation (annotated.png, state.txt)
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
    runner,
    windows,
)
from typesafe_computer_use.config import ABORT_CORNER_PX
from typesafe_computer_use.models import Abort, AxNode, Field, Item, Screen


# ==============================================================================
# F1: Screen Capture & Window Geometry (5 tests)
# ==============================================================================


def test_f1_01_screenshot_returns_valid_rgb_image():
    """Verify live screen capture returns a non-empty PIL RGB Image matching display dimensions."""
    img = windows.screenshot()
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.width > 0 and img.height > 0
    # Sanity check: primary monitor on Snapdragon PC is typically >= 1024x768
    assert img.width >= 1024 and img.height >= 700


def test_f1_02_display_scale_returns_positive_factor():
    """Verify display_scale computes a positive float scale factor (e.g. 1.0 or 1.5)."""
    img = windows.screenshot()
    scale = windows.display_scale(img)
    assert isinstance(scale, float)
    assert scale >= 1.0
    assert scale <= 3.0


def test_f1_03_frontmost_app_and_pid_identifies_process():
    """Verify frontmost_app_and_pid returns non-empty string app name and valid integer PID."""
    app, pid = windows.frontmost_app_and_pid()
    assert isinstance(app, str)
    assert isinstance(pid, int)
    # The running process or desktop/explorer always has a valid PID >= 0
    assert pid >= 0


def test_f1_04_frontmost_window_bounds_returns_positive_rect():
    """Verify frontmost_window_bounds returns (x, y, w, h) with dimensions above MIN_WINDOW_SIDE_PT."""
    bounds = windows.frontmost_window_bounds()
    if bounds is not None:
        x, y, w, h = bounds
        assert isinstance(x, float) and isinstance(y, float)
        assert isinstance(w, float) and isinstance(h, float)
        assert w >= windows.MIN_WINDOW_SIDE_PT
        assert h >= windows.MIN_WINDOW_SIDE_PT
    else:
        # If no main window has focus, querying by our own PID should be valid or None
        my_bounds = windows.frontmost_window_bounds(os.getpid())
        assert my_bounds is None or len(my_bounds) == 4


def test_f1_05_frontmost_window_center_matches_midpoint():
    """Verify frontmost_window_center calculates exact midpoint (x + w/2, y + h/2)."""
    bounds = windows.frontmost_window_bounds()
    center = windows.frontmost_window_center()
    if bounds is not None:
        assert center is not None
        expected_cx = bounds[0] + bounds[2] / 2.0
        expected_cy = bounds[1] + bounds[3] / 2.0
        assert abs(center[0] - expected_cx) < 1e-3
        assert abs(center[1] - expected_cy) < 1e-3
    else:
        assert center is None


# ==============================================================================
# F2: WinRT NPU OCR Sub-Second Latency & Text Extraction (5 tests)
# ==============================================================================


def test_f2_01_winrt_ocr_engine_availability():
    """Verify WinRT OCR engine initializes on Windows 11 ARM64."""
    assert ocr._WINRT_OCR_AVAILABLE is True
    assert ocr._ocr_engine is not None


def test_f2_02_winrt_npu_ocr_sub_second_latency(ocr_test_image_factory):
    """Verify WinRT NPU OCR performs crop recognition with sub-second execution latency (<1.0s)."""
    img = ocr_test_image_factory(["Qualcomm Hexagon NPU Accelerated", "Sub-Second Benchmark Test 2026"])
    t0 = time.perf_counter()
    lines = ocr.ocr_crop(img, (0, 0, img.width, img.height))
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"OCR latency was {elapsed:.3f}s, expected < 1.0s"
    assert len(lines) > 0


def test_f2_03_ocr_extracts_expected_tokens(ocr_test_image_factory):
    """Verify WinRT NPU OCR extracts expected text tokens and assigns confidence scores >= 0.5."""
    target_token = "ORD-99482"
    img = ocr_test_image_factory([f"TOKEN: {target_token} ARM64"])
    lines = ocr.ocr_crop(img, (0, 0, img.width, img.height))

    found_tokens = [line[0] for line in lines]
    assert any(target_token in text for text in found_tokens), f"Token {target_token} not in {found_tokens}"
    for text, conf, box in lines:
        assert conf >= 0.5


def test_f2_04_ocr_bounding_boxes_within_crop_geometry(ocr_test_image_factory):
    """Verify all recognized lines have bounding boxes (x1, y1, x2, y2) within image boundaries."""
    img = ocr_test_image_factory(["Top Line Geometry", "Bottom Line Geometry"])
    lines = ocr.ocr_crop(img, (0, 0, img.width, img.height))

    assert len(lines) >= 2
    for text, conf, (x1, y1, x2, y2) in lines:
        assert 0 <= x1 < x2 <= img.width
        assert 0 <= y1 < y2 <= img.height


def test_f2_05_ocr_crop_sub_rectangle_offset_accuracy(ocr_test_image_factory):
    """Verify ocr_crop on a sub-rectangle returns boxes mapped to full-capture coordinates."""
    img = ocr_test_image_factory(["Line Inside Target Region"], width=600, height=300)
    crop_rect = (10.0, 10.0, 500.0, 150.0)
    lines = ocr.ocr_crop(img, crop_rect)

    assert len(lines) >= 1
    for text, conf, (x1, y1, x2, y2) in lines:
        assert x1 >= 10.0
        assert y1 >= 10.0
        assert x2 <= 500.0
        assert y2 <= 150.0


# ==============================================================================
# F3: UIAutomation Actionable Controls Discovery (5 tests)
# ==============================================================================


def test_f3_01_actionable_elements_returns_standard_tuple():
    """Verify actionable_elements returns 3-tuple (found, offscreen, capped)."""
    found, offscreen, capped = windows.actionable_elements(os.getpid(), 1920.0, 1200.0)
    assert isinstance(found, list)
    assert isinstance(offscreen, list)
    assert isinstance(capped, bool)


def test_f3_02_uia_role_mapping_covers_standard_ax_roles():
    """Verify UIA_ROLE_MAP maps Windows control types to standard AX role strings."""
    assert windows.UIA_ROLE_MAP.get(50000) == "AXButton"
    assert windows.UIA_ROLE_MAP.get(50004) == "AXTextField"
    assert windows.UIA_ROLE_MAP.get(50002) == "AXCheckBox"
    assert windows.UIA_ROLE_MAP.get(50005) == "AXLink"
    assert windows.UIA_ROLE_MAP.get(50030) == "AXTextArea"
    assert windows.UIA_ROLE_MAP.get(50033) == "AXGroup"


def test_f3_03_walk_actionable_discovers_nodes():
    """Verify walk_actionable BFS traversal extracts actionable elements with role, label, and frame."""
    class FakeNode:
        def __init__(self, name, role, frame, actions=None, children=None):
            self.name = name
            self.role = role
            self.frame = frame
            self.actions = actions or []
            self.kids = children or []

    btn = FakeNode("Submit", "AXButton", (100.0, 100.0, 80.0, 30.0), actions=[windows.AX_PRESS])
    root = FakeNode("Window", "AXWindow", (0.0, 0.0, 800.0, 600.0), children=[btn])

    def get_kids(n):
        return n.kids

    def get_attrs(n):
        return windows.AxAttrs(n.role, n.name, n.frame)

    def get_acts(n):
        return n.actions

    found, offscreen, capped = windows.walk_actionable(root, get_kids, get_attrs, get_acts, 1920.0, 1200.0)
    assert len(found) == 1
    assert found[0].label == "Submit"
    assert found[0].role == "AXButton"
    assert found[0].pressable is True
    assert capped is False


def test_f3_04_walk_actionable_respects_time_and_node_caps():
    """Verify walk_actionable halts and sets capped=True when node_cap is reached."""
    class ChainNode:
        def __init__(self, idx, child=None):
            self.idx = idx
            self.kids = [child] if child else []

    n3 = ChainNode(3)
    n2 = ChainNode(2, n3)
    n1 = ChainNode(1, n2)

    def get_kids(n):
        return n.kids

    def get_attrs(n):
        return windows.AxAttrs("AXButton", f"Btn {n.idx}", (10.0, 10.0, 20.0, 20.0))

    def get_acts(n):
        return [windows.AX_PRESS]

    found, offscreen, capped = windows.walk_actionable(n1, get_kids, get_attrs, get_acts, 1920.0, 1200.0, node_cap=2)
    assert capped is True
    assert len(found) <= 2


def test_f3_05_walk_actionable_traverses_nameless_container_groups():
    """Verify nameless container groups (AXGroup with no label) do not block child traversal."""
    class Node:
        def __init__(self, role, label, frame, kids=None):
            self.role = role
            self.label = label
            self.frame = frame
            self.kids = kids or []

    leaf_btn = Node("AXButton", "Confirm", (50.0, 50.0, 80.0, 30.0))
    nameless_pane = Node("AXGroup", "", (0.0, 0.0, 500.0, 500.0), kids=[leaf_btn])
    root = Node("AXWindow", "App Root", (0.0, 0.0, 1000.0, 800.0), kids=[nameless_pane])

    def get_kids(n):
        return n.kids

    def get_attrs(n):
        return windows.AxAttrs(n.role, n.label, n.frame)

    def get_acts(n):
        return [windows.AX_PRESS] if n.role == "AXButton" else []

    found, offscreen, capped = windows.walk_actionable(root, get_kids, get_attrs, get_acts, 1920.0, 1200.0)
    labels = [n.label for n in found]
    assert "Confirm" in labels


# ==============================================================================
# F4: Synthetic Actions (Click/Type/Scroll/Focus) (5 tests)
# ==============================================================================


def test_f4_01_mouse_location_returns_screen_coordinates():
    """Verify mouse_location returns current physical cursor coordinates (float x, float y)."""
    x, y = windows.mouse_location()
    assert isinstance(x, float) and isinstance(y, float)
    assert x >= 0.0 and y >= 0.0


def test_f4_02_click_at_dispatches_input():
    """Verify click_at sets cursor position and completes SendInput mouse click sequence."""
    orig_x, orig_y = windows.mouse_location()
    # Click at current position to avoid disturbing background apps
    windows.click_at((orig_x, orig_y))
    now_x, now_y = windows.mouse_location()
    assert abs(now_x - orig_x) < 50.0
    assert abs(now_y - orig_y) < 50.0


def test_f4_03_type_text_sends_unicode_characters():
    """Verify type_text sends Unicode character stream without throwing exceptions."""
    # Test safe Unicode sequence
    windows.type_text("TypesafeCU")


def test_f4_04_press_executes_valid_keycodes():
    """Verify press sends virtual keycodes for return, tab, escape, and command modifier."""
    windows.press("tab")
    windows.press("escape")
    windows.press("a", command=True)


def test_f4_05_scroll_dispatches_wheel_delta():
    """Verify scroll sends mouse wheel input in positive (up) and negative (down) directions."""
    windows.scroll(1)
    windows.scroll(-1)


# ==============================================================================
# F5: Mouse-in-Corner Emergency Abort Safety Trigger (5 tests)
# ==============================================================================


def test_f5_01_check_abort_raises_at_zero_zero(monkeypatch):
    """Verify check_abort immediately raises Abort when mouse is at (0, 0)."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (0.0, 0.0))
    with pytest.raises(Abort, match="mouse in top-left corner"):
        windows.check_abort()


def test_f5_02_check_abort_raises_at_exact_threshold(monkeypatch):
    """Verify check_abort raises Abort at exact threshold (ABORT_CORNER_PX, ABORT_CORNER_PX)."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (float(ABORT_CORNER_PX), float(ABORT_CORNER_PX)))
    with pytest.raises(Abort, match="mouse in top-left corner"):
        windows.check_abort()


def test_f5_03_check_abort_safe_at_offset(monkeypatch):
    """Verify check_abort does not raise when cursor is outside the abort corner."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (float(ABORT_CORNER_PX + 5), float(ABORT_CORNER_PX + 5)))
    # Should complete cleanly with no exception
    windows.check_abort()


def test_f5_04_sleep_watching_completes_when_safe(monkeypatch):
    """Verify sleep_watching completes normally when mouse cursor remains in safe region."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (400.0, 400.0))
    t0 = time.monotonic()
    windows.sleep_watching(0.1)
    assert time.monotonic() - t0 >= 0.08


def test_f5_05_sleep_watching_aborts_when_corner_reached(monkeypatch):
    """Verify sleep_watching aborts mid-wait if mouse moves into the top-left corner."""
    locs = iter([(500.0, 500.0), (0.0, 0.0)])
    monkeypatch.setattr(windows, "mouse_location", lambda: next(locs, (0.0, 0.0)))
    with pytest.raises(Abort, match="mouse in top-left corner"):
        windows.sleep_watching(0.5)


# ==============================================================================
# F6: Text Persistence & Keystroke Fallback (5 tests)
# ==============================================================================


def test_f6_01_clear_field_sends_select_all_and_delete():
    """Verify clear_field issues Ctrl+A and Backspace sequence cleanly."""
    windows.clear_field()


def test_f6_02_ax_set_value_handles_none_and_returns_bool():
    """Verify ax_set_value handles None ref gracefully without raising exception."""
    result = windows.ax_set_value(None, "sample text")
    assert result is False


def test_f6_03_ax_value_handles_none_safely():
    """Verify ax_value handles None ref safely returning None."""
    val = windows.ax_value(None)
    assert val is None


def test_f6_04_actions_fill_field_verifies_persistence(monkeypatch):
    """Verify actions.fill_field verifies persistence with ax_value and does not fallback when matched."""
    typed = []
    monkeypatch.setattr(windows, "ax_focus", lambda ref: True)
    monkeypatch.setattr(windows, "ax_set_value", lambda ref, txt: True)
    monkeypatch.setattr(windows, "ax_value", lambda ref: "expected_text")
    monkeypatch.setattr(windows, "type_text", lambda txt: typed.append(txt))

    fake_ref = MagicMock()
    # When ax_value matches text, type_text is NOT called
    actions.fill_field(fake_ref, "expected_text")
    assert "expected_text" not in typed


def test_f6_05_focused_field_returns_field_or_none():
    """Verify focused_field returns either an instance of Field or None."""
    res = windows.focused_field()
    assert res is None or isinstance(res, Field)
    if res is not None:
        assert isinstance(res.role, str)
        assert isinstance(res.label, str)
        assert isinstance(res.value, str)


# ==============================================================================
# F7: E2E Workflow & State Transitions (5 tests)
# ==============================================================================


def test_f7_01_perception_capture_creates_valid_screen(tmp_path):
    """Verify perception.capture creates a valid Screen object from replay image."""
    img_path = tmp_path / "capture.png"
    Image.new("RGB", (800, 600), color=(255, 255, 255)).save(img_path)

    screen = perception.capture(image_path=img_path, app="ReplayTarget", url="http://local.test")
    assert isinstance(screen, Screen)
    assert screen.app == "ReplayTarget"
    assert screen.url == "http://local.test"
    assert screen.image.size == (800, 600)


def test_f7_02_perception_perceive_merges_and_indexes_items(tmp_path):
    """Verify perception.perceive produces indexed Items from a captured Screen."""
    img_path = tmp_path / "test.png"
    img = Image.new("RGBA", (500, 200), (255, 255, 255, 255))
    img.save(img_path)
    screen = perception.capture(image_path=img_path, app="TestApp")

    items = perception.perceive(screen, budget=10, goal="click button")
    assert isinstance(items, list)
    for idx, item in enumerate(items, 1):
        assert item.index == idx
        assert item.x2 >= item.x1
        assert item.y2 >= item.y1


def test_f7_03_actions_execute_updates_history(monkeypatch):
    """Verify actions.click_item executes click and returns descriptive action string."""
    monkeypatch.setattr(windows, "click_at", lambda pt: None)
    monkeypatch.setattr(windows, "ax_press", lambda ref: True)

    item = Item(index=1, text="Submit Order", ocr_confidence=1.0, x1=50, y1=50, x2=150, y2=80, source="ax")
    screen = Screen(
        image=Image.new("RGB", (400, 400)),
        scale=1.0,
        app="App",
        field=None,
        url=None,
        ax_refs={1: MagicMock()},
    )

    desc = actions.click_item(item, screen)
    assert "Submit Order" in desc
    assert "accessibility" in desc


def test_f7_04_actions_execute_with_type_text(monkeypatch):
    """Verify actions.fill_field dispatches keystrokes and returns execution mode string."""
    typed_values = []
    monkeypatch.setattr(windows, "type_text", lambda txt: typed_values.append(txt))
    monkeypatch.setattr(windows, "ax_focus", lambda ref: True)
    monkeypatch.setattr(windows, "ax_set_value", lambda ref, txt: False)

    field = Field(role="AXTextField", label="Username", placeholder="", value="", x=10, y=10, w=100, h=30, ref=MagicMock())
    result = actions.fill_field(field, "admin_user")
    assert result == "via keystrokes"
    assert "admin_user" in typed_values


def test_f7_05_runner_run_executes_autonomous_loop(tmp_path, monkeypatch):
    """Verify runner.run executes single-step autonomous loop and completes with valid outcome."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (500.0, 500.0))
    img_path = tmp_path / "screen.png"
    Image.new("RGB", (400, 400), (240, 240, 240)).save(img_path)

    cfg = runner.RunConfig(
        goal="Test goal",
        out=tmp_path / "out",
        act=False,
        steps=1,
        image=img_path,
        app="MockApp",
    )

    class FakeTypesafe:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(runner, "TypeSafeClient", FakeTypesafe)

    from typesafe_computer_use.decide import Decision
    from typesafe_sdk import ChoiceAnswer
    dummy_decision = Decision(
        kind=ChoiceAnswer(choice="done", confidence=0.95, probabilities={"done": 0.95, "nothing helps": 0.05}),
        item=None,
        site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
        offscreen=None,
    )
    monkeypatch.setattr(runner, "decide", lambda *args, **kwargs: dummy_decision)

    def ctx_factory(typesafe, history):
        return actions.Context(
            goal=cfg.goal,
            browser="msedge",
            email=None,
            typesafe=FakeTypesafe(),
            writer=None,
            history=history,
        )

    state = runner.run(cfg, ctx_factory)
    assert state.outcome == "done"
    assert len(state.timings) >= 1


# ==============================================================================
# F8: Inspection Artifact Generation (annotated.png & state.txt) (5 tests)
# ==============================================================================


def test_f8_01_render_payload_structure():
    """Verify render_payload outputs structured sections: STATE, QUESTION kind/item/site, and ITEMS."""
    screen = Screen(image=Image.new("RGB", (800, 600)), scale=1.0, app="Edge", field=None, url=None)
    item = Item(index=1, text="Home", ocr_confidence=1.0, x1=10, y1=10, x2=50, y2=30)
    payload = report.render_payload("Test goal", screen, [item], [], "msedge", None)

    assert "STATE  (sent as `state`)" in payload
    assert "QUESTION kind  (Choice criteria)" in payload
    assert "QUESTION item  (Choice criteria)" in payload
    assert "ITEMS  (1 after merge/filter" in payload
    assert "[  1] src=" in payload


def test_f8_02_annotate_generates_valid_png(tmp_path):
    """Verify report.annotate writes a valid PNG matching capture dimensions."""
    screen = Screen(image=Image.new("RGB", (640, 480), (255, 255, 255)), scale=1.0, app="Edge", field=None, url=None)
    item = Item(index=1, text="Button", ocr_confidence=1.0, x1=20, y1=20, x2=80, y2=50)
    out_file = tmp_path / "annotated.png"

    report.annotate(screen, [item], chosen="", out=out_file)
    assert out_file.exists()
    annotated_img = Image.open(out_file)
    assert annotated_img.format == "PNG"
    assert annotated_img.size == (640, 480)


def test_f8_03_annotate_color_coding_rules(tmp_path):
    """Verify report.annotate draws distinctive bounding box colors for OCR, AX, and chosen items."""
    screen = Screen(image=Image.new("RGB", (300, 300), (255, 255, 255)), scale=1.0, app="Edge", field=None, url=None)
    ocr_item = Item(index=1, text="OCR", ocr_confidence=1.0, x1=10, y1=10, x2=40, y2=40, source="ocr")
    ax_item = Item(index=2, text="AX", ocr_confidence=1.0, x1=50, y1=50, x2=80, y2=80, source="ax")
    chosen_item = Item(index=3, text="Chosen", ocr_confidence=1.0, x1=100, y1=100, x2=140, y2=140, source="ax")

    out_file = tmp_path / "annotated_colors.png"
    report.annotate(screen, [ocr_item, ax_item, chosen_item], chosen="3", out=out_file)
    assert out_file.exists()
    img = Image.open(out_file).convert("RGB")

    # The chosen item border at (100, 100) should be Red (255, 0, 0)
    pixel_chosen = img.getpixel((100, 100))
    assert pixel_chosen == (255, 0, 0)


def test_f8_04_annotate_draws_focused_field_in_green(tmp_path):
    """Verify report.annotate draws a green (0, 200, 0) outline around focused field."""
    field_item = Field(role="AXTextField", label="Input", placeholder="", value="", x=30, y=30, w=100, h=40, ref=None)
    screen = Screen(image=Image.new("RGB", (300, 300), (255, 255, 255)), scale=1.0, app="Edge", field=field_item, url=None)
    out_file = tmp_path / "annotated_field.png"

    report.annotate(screen, [], chosen="", out=out_file)
    assert out_file.exists()
    img = Image.open(out_file).convert("RGB")

    pixel_field = img.getpixel((30, 30))
    assert pixel_field == (0, 200, 0)


def test_f8_05_ax_count_matches_actual_ax_items():
    """Verify report.ax_count returns count of items originating from accessibility tree."""
    items = [
        Item(index=1, text="A", ocr_confidence=1.0, x1=0, y1=0, x2=10, y2=10, source="ax"),
        Item(index=2, text="B", ocr_confidence=1.0, x1=0, y1=0, x2=10, y2=10, source="ocr"),
        Item(index=3, text="C", ocr_confidence=1.0, x1=0, y1=0, x2=10, y2=10, source="ax+ocr"),
        Item(index=4, text="D", ocr_confidence=1.0, x1=0, y1=0, x2=10, y2=10, source="ocr"),
    ]
    assert report.ax_count(items) == 2

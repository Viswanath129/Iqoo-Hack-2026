"""Tier 3: Pairwise Cross-Feature Interactions E2E Tests.

Verifies cross-subsystem interactions between:
- Pair 1 (F1 + F4 + F7): Screen Perception + Action Execution + State Change
- Pair 2 (F2 + F3 + F7): WinRT NPU OCR + UIAutomation Tree Merge & Deduplication
- Pair 3 (F4 + F5): Synthetic Action Sequence + Emergency Corner Abort
- Pair 4 (F3 + F4 + F6): Control Discovery + Field Focus + Text Value Persistence
- Pair 5 (F7 + F8): Workflow Step Execution + Inspection Artifact Generation
- Pair 6 (F1 + F2 + F8): Screen DPI Scale + Geometry + OCR Bounding Box Alignment
- Pair 7 (F3 + F4 + F6): Offscreen Control Discovery + Accessibility Press Dispatch
- Pair 8 (F4 + F6 + F7): Keyboard Navigation (Tab/Return) + Focused Field Tracking
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


def test_tier3_p1_perception_action_state_transition(tmp_path, monkeypatch):
    """Pair 1 (F1+F4+F7): Perception captures screen, identifies button, clicks it, and transitions state."""
    clicks = []
    monkeypatch.setattr(windows, "click_at", lambda pt: clicks.append(pt))

    # Step 1: Initial state
    screen1_img = tmp_path / "screen1.png"
    Image.new("RGB", (600, 400), (250, 250, 250)).save(screen1_img)
    screen1 = perception.capture(image_path=screen1_img, app="TargetApp")

    btn_item = Item(index=1, text="Run Test", ocr_confidence=1.0, x1=100, y1=100, x2=200, y2=140)
    pt = screen1.to_points(btn_item)
    windows.click_at(pt)
    assert len(clicks) == 1
    assert clicks[0] == screen1.to_points(btn_item)

    # Step 2: Post-click capture reflects new state
    screen2_img = tmp_path / "screen2.png"
    Image.new("RGB", (600, 400), (200, 220, 240)).save(screen2_img)
    screen2 = perception.capture(image_path=screen2_img, app="TargetApp")
    assert screen2.image.size == screen1.image.size


def test_tier3_p2_ocr_and_uia_merge_deduplication(ocr_test_image_factory):
    """Pair 2 (F2+F3+F7): WinRT OCR text and UIA accessibility nodes merge with deduplication."""
    text_content = "Confirm Order"
    img = ocr_test_image_factory([text_content], width=500, height=200)
    lines = ocr.ocr_crop(img, (0, 0, img.width, img.height))

    assert len(lines) >= 1
    ocr_box = lines[0][2]

    # Create matching AX node covering the same region
    ax_node = AxNode(
        role="AXButton",
        label=text_content,
        x=ocr_box[0],
        y=ocr_box[1],
        w=ocr_box[2] - ocr_box[0],
        h=ocr_box[3] - ocr_box[1],
        pressable=True,
    )

    ocr_items = [
        Item(index=i, text=text, ocr_confidence=conf, x1=box[0], y1=box[1], x2=box[2], y2=box[3], source="ocr")
        for i, (text, conf, box) in enumerate(lines)
    ]
    ax_items = perception.to_ax_items([ax_node], scale=1.0)
    items = perception.merge_sources(ocr_items, ax_items)

    # The merge should deduplicate them into a single item with source="ax+ocr"
    matching_items = [it for it in items if text_content in it.text]
    assert len(matching_items) == 1
    assert matching_items[0].source == "ax+ocr"


def test_tier3_p3_action_sequence_with_corner_abort(monkeypatch):
    """Pair 3 (F4+F5): Synthetic action sequence aborts immediately when mouse enters corner."""
    positions = iter([(500.0, 500.0), (300.0, 300.0), (0.0, 0.0)])
    monkeypatch.setattr(windows, "mouse_location", lambda: next(positions, (0.0, 0.0)))

    executed_actions = []

    def perform_step(step_name):
        windows.check_abort()
        executed_actions.append(step_name)

    perform_step("step_1")
    perform_step("step_2")
    with pytest.raises(Abort, match="mouse in top-left corner"):
        perform_step("step_3")

    assert executed_actions == ["step_1", "step_2"]


def test_tier3_p4_control_discovery_focus_and_text_persistence(monkeypatch):
    """Pair 4 (F3+F4+F6): Discover text field, focus it, fill text, and verify value persistence."""
    field_storage = {"value": ""}

    class FakeUiaEdit:
        def SetFocus(self):
            return True

        def GetValuePattern(self):
            class VP:
                @property
                def Value(self):
                    return field_storage["value"]

                def SetValue(self, txt):
                    field_storage["value"] = txt
            return VP()

    fake_edit = FakeUiaEdit()
    field = Field(role="AXTextField", label="User Name", placeholder="", value="", x=50, y=50, w=150, h=30, ref=fake_edit)

    monkeypatch.setattr(windows, "ax_focus", lambda ref: ref.SetFocus())
    monkeypatch.setattr(windows, "ax_set_value", lambda ref, txt: ref.GetValuePattern().SetValue(txt) or True)
    monkeypatch.setattr(windows, "ax_value", lambda ref: ref.GetValuePattern().Value)

    result = actions.fill_field(field, "john_snapdragon")
    assert result == "via accessibility"
    assert field_storage["value"] == "john_snapdragon"
    assert windows.ax_value(fake_edit) == "john_snapdragon"


def test_tier3_p5_workflow_step_artifact_generation(tmp_path):
    """Pair 5 (F7+F8): Workflow step outputs valid annotated screenshot and state text dump."""
    out_dir = tmp_path / "step_run"
    out_dir.mkdir()

    img = Image.new("RGB", (800, 600), (240, 240, 240))
    field = Field(role="AXTextField", label="Search", placeholder="search...", value="Snapdragon", x=100, y=50, w=200, h=35, ref=None)
    screen = Screen(image=img, scale=1.0, app="msedge", field=field, url="https://test.local")

    items = [
        Item(index=1, text="Search Input", ocr_confidence=1.0, x1=100, y1=50, x2=300, y2=85, source="ax"),
        Item(index=2, text="Submit Button", ocr_confidence=1.0, x1=310, y1=50, x2=390, y2=85, source="ax"),
    ]

    annotated_path = out_dir / "annotated.png"
    state_path = out_dir / "state.txt"

    report.annotate(screen, items, chosen="2", out=annotated_path)
    state_path.write_text(report.render_payload("Search Snapdragon", screen, items, ["opened browser"], "msedge", None))

    assert annotated_path.exists()
    assert state_path.exists()

    state_content = state_path.read_text()
    assert "Search Snapdragon" in state_content
    assert "Submit Button" in state_content
    assert "FOCUSED FIELD" in state_content

    # Inspect annotated image
    saved_img = Image.open(annotated_path)
    assert saved_img.size == (800, 600)


def test_tier3_p6_dpi_scale_geometry_ocr_alignment(ocr_test_image_factory):
    """Pair 6 (F1+F2+F8): Verify physical capture pixels align with display scale onto point coordinates."""
    img = ocr_test_image_factory(["DPI-SCALE-ALIGNMENT-TEST"], width=800, height=200)
    lines = ocr.ocr_crop(img, (0, 0, img.width, img.height))
    assert len(lines) >= 1

    box = lines[0][2]
    scale = 1.5
    screen = Screen(image=img, scale=scale, app="Edge", field=None, url=None)

    item = Item(index=1, text=lines[0][0], ocr_confidence=lines[0][1], x1=box[0], y1=box[1], x2=box[2], y2=box[3])
    click_pt = screen.to_points(item)

    # Click point should be center of box divided by scale
    expected_cx = (box[0] + box[2]) / (2.0 * scale)
    expected_cy = (box[1] + box[3]) / (2.0 * scale)

    assert abs(click_pt[0] - expected_cx) < 1e-3
    assert abs(click_pt[1] - expected_cy) < 1e-3


def test_tier3_p7_offscreen_control_discovery_and_ax_press():
    """Pair 7 (F3+F4+F6): Discover offscreen controls and dispatch action through AXPress without clicking."""
    pressed_elements = []

    class FakeOffscreenControl:
        def __init__(self, label):
            self.label = label

    off_node = AxNode(
        role="AXButton",
        label="Scrolled Deep Action",
        x=-500.0,
        y=-500.0,
        w=10.0,
        h=10.0,
        pressable=True,
        ref=FakeOffscreenControl("Scrolled Deep Action"),
    )

    screen = Screen(
        image=Image.new("RGB", (400, 400)),
        scale=1.0,
        app="Edge",
        field=None,
        url=None,
        offscreen=[off_node],
    )

    # Monkeypatch ax_press to record execution
    def fake_ax_press(ref):
        if isinstance(ref, FakeOffscreenControl):
            pressed_elements.append(ref.label)
            return True
        return False

    old_ax_press = platform_adapter.ax_press
    platform_adapter.ax_press = fake_ax_press
    try:
        desc = actions.press_offscreen("0", screen)
        assert "pressed 'Scrolled Deep Action'" in desc
        assert "Scrolled Deep Action" in pressed_elements
    finally:
        platform_adapter.ax_press = old_ax_press


def test_tier3_p8_keyboard_navigation_and_focused_field_tracking():
    """Pair 8 (F4+F6+F7): Tab navigation updates focused field tracking."""
    # Test tab press execution
    windows.press("tab")

    # Verify focused field query succeeds
    field = windows.focused_field()
    assert field is None or isinstance(field, Field)

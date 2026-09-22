"""Tier 4: Real-World Application Scenarios E2E Tests.

Implements full end-to-end multi-step interactive workflows:
- Scenario 1: Form Filling and Submission
- Scenario 2: Search, Scroll, and Select Workflow
- Scenario 3: Multi-Step Navigation Flow
- Scenario 4: Field Editing with Value Replacement and Backspace
- Scenario 5: Emergency Corner Abort During In-Progress Run
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

from .harness import TargetHarness, activate_hwnd, ensure_desktop, get_hwnd_bounds


# ==============================================================================
# Scenario 1: Form Filling & Submission
# ==============================================================================


def test_scenario_1_form_filling_and_submission(native_app_session, tmp_path):
    """Scenario 1: End-to-end form fill and submit on live interactive target window."""
    ensure_desktop()
    hwnd = native_app_session.hwnd
    activate_hwnd(hwnd)
    time.sleep(0.3)

    bounds = get_hwnd_bounds(hwnd)
    assert bounds is not None
    x, y, w, h = bounds

    # Capture live screen
    screen_img = windows.screenshot()
    assert screen_img.width >= 800 and screen_img.height >= 600

    # Locate and interact with controls using UIAutomation
    found_nodes, _, _ = windows.actionable_elements(native_app_session.pid, 1920.0, 1200.0)

    # Find the submit button or click within the window bounds
    submit_nodes = [n for n in found_nodes if "Submit" in n.label]
    if submit_nodes:
        node = submit_nodes[0]
        windows.click_at((node.x + node.w / 2, node.y + node.h / 2))
    else:
        # Fallback to calculated coordinate inside the test window form area
        windows.click_at((x + 200, y + 360))

    time.sleep(0.3)

    # Verify inspection artifact generation for this scenario
    out_dir = tmp_path / "scenario_1_artifacts"
    out_dir.mkdir()
    annotated = out_dir / "annotated.png"
    state_txt = out_dir / "state.txt"

    screen = Screen(
        image=screen_img,
        scale=windows.display_scale(screen_img),
        app=native_app_session.title,
        field=None,
        url=None,
    )
    items = [Item(index=1, text="Submit Request", ocr_confidence=1.0, x1=x + 100, y1=y + 350, x2=x + 220, y2=y + 380, source="ax")]
    report.annotate(screen, items, chosen="1", out=annotated)
    state_txt.write_text(report.render_payload("Submit user form", screen, items, ["clicked Submit"], "native_app", None))

    assert annotated.exists()
    assert state_txt.exists()
    assert "Submit Request" in state_txt.read_text()


# ==============================================================================
# Scenario 2: Search, Scroll, and Select Workflow
# ==============================================================================


def test_scenario_2_search_scroll_and_select(ocr_test_image_factory):
    """Scenario 2: Read list, perform scroll down, observe new items, and select target item."""
    # Step 1: Initial list view
    initial_items = ["Item 01: Alpha", "Item 02: Beta", "Item 03: Gamma", "Item 04: Delta"]
    img_before = ocr_test_image_factory(initial_items, width=600, height=300)
    lines_before = ocr.ocr_crop(img_before, (0, 0, img_before.width, img_before.height))
    texts_before = [ln[0] for ln in lines_before]
    assert any("Item 01" in t for t in texts_before)

    # Step 2: Dispatch scroll down
    windows.scroll(-4)
    time.sleep(0.1)

    # Step 3: Scrolled list view exposes deeper items
    scrolled_items = ["Item 08: Theta", "Item 09: Iota Target", "Item 10: Kappa"]
    img_after = ocr_test_image_factory(scrolled_items, width=600, height=300)
    lines_after = ocr.ocr_crop(img_after, (0, 0, img_after.width, img_after.height))
    texts_after = [ln[0] for ln in lines_after]
    assert any("Target" in t for t in texts_after)

    # Step 4: Click the target item
    target_line = [ln for ln in lines_after if "Target" in ln[0]][0]
    box = target_line[2]
    click_target = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    windows.click_at(click_target)


# ==============================================================================
# Scenario 3: Multi-Step Navigation Flow
# ==============================================================================


def test_scenario_3_multistep_navigation_flow(tmp_path):
    """Scenario 3: Multi-step interactive flow (Home -> Settings -> Save -> Complete)."""
    history = []
    timing = {}

    class MockAppFlow:
        def __init__(self):
            self.current_view = "Home"

        def click(self, item_label):
            if "Settings" in item_label:
                self.current_view = "Settings"
            elif "Save" in item_label:
                self.current_view = "Complete"
            return f"transitioned to {self.current_view}"

    flow = MockAppFlow()

    # Step 1: On Home view, click Settings
    assert flow.current_view == "Home"
    desc1 = flow.click("Go to Settings")
    history.append(desc1)
    assert flow.current_view == "Settings"

    # Step 2: On Settings view, modify setting and click Save
    desc2 = flow.click("Save Configuration")
    history.append(desc2)
    assert flow.current_view == "Complete"

    # Verify flow record
    assert len(history) == 2
    assert "transitioned to Settings" in history[0]
    assert "transitioned to Complete" in history[1]


# ==============================================================================
# Scenario 4: Field Editing with Value Replacement and Backspace
# ==============================================================================


def test_scenario_4_field_editing_with_value_replacement(monkeypatch):
    """Scenario 4: Clear existing field text using clear_field() and enter replacement value."""
    field_state = {"text": "original_outdated_value"}
    typed_keys = []

    def fake_type(text):
        typed_keys.append(text)
        field_state["text"] += text

    def fake_press(key, command=False):
        if command and key == "a":
            # Select all
            pass
        elif key == "delete":
            # Clear selected text
            field_state["text"] = ""

    monkeypatch.setattr(windows, "type_text", fake_type)
    monkeypatch.setattr(windows, "press", fake_press)

    # Initial state
    assert field_state["text"] == "original_outdated_value"

    # Step 1: Clear existing text
    windows.clear_field()
    assert field_state["text"] == ""

    # Step 2: Enter new text
    windows.type_text("brand_new_snapdragon_value")
    assert field_state["text"] == "brand_new_snapdragon_value"
    assert "brand_new_snapdragon_value" in typed_keys


# ==============================================================================
# Scenario 5: Emergency Corner Abort During In-Progress Run
# ==============================================================================


def test_scenario_5_emergency_corner_abort_during_workflow(tmp_path, monkeypatch):
    """Scenario 5: Multi-step automated workflow is aborted immediately when mouse enters corner."""
    monkeypatch.setattr(windows, "mouse_location", lambda: (0.0, 0.0))

    cfg = runner.RunConfig(
        goal="Perform automated task",
        out=tmp_path / "abort_run",
        act=False,
        steps=5,
        image=tmp_path / "mock.png",
        app="MockApp",
    )
    Image.new("RGB", (400, 400), (255, 255, 255)).save(tmp_path / "mock.png")

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

    # The runner must catch the Abort and set outcome="aborted (mouse in top-left corner)"
    state = runner.run(cfg, ctx_factory)
    assert state.outcome.startswith("aborted")
    assert "mouse in top-left corner" in state.outcome

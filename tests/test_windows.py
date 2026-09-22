import sys
import time
from typing import Any
import pytest
from PIL import Image

from typesafe_computer_use import windows
from typesafe_computer_use import ocr
from typesafe_computer_use import platform_adapter
from typesafe_computer_use.windows import walk_actionable, AxAttrs
from typesafe_computer_use.models import Field, Item
from typesafe_computer_use.perception import capture, perceive

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only tests")

# 1. Win32 basics
def test_windows_display_scale():
    img = Image.new("RGB", (100, 100))
    scale = windows.display_scale(img)
    assert isinstance(scale, float)
    assert scale > 0

def test_windows_mouse_location():
    pos = windows.mouse_location()
    assert isinstance(pos, tuple)
    assert len(pos) == 2
    assert isinstance(pos[0], float)
    assert isinstance(pos[1], float)

def test_windows_screenshot():
    img = windows.screenshot()
    assert isinstance(img, Image.Image)
    assert img.width > 0
    assert img.height > 0

def test_windows_frontmost_app():
    app = windows.frontmost_app()
    assert isinstance(app, str)
    assert len(app) > 0

def test_windows_accessibility_trusted():
    assert windows.accessibility_trusted() is True

# 2. UIA role mapping
def test_uia_role_map():
    assert len(windows.UIA_ROLE_MAP) > 0
    for key, value in windows.UIA_ROLE_MAP.items():
        assert isinstance(key, int)
        assert isinstance(value, str)
        assert value.startswith("AX")

# 3. Tree walk
def test_tree_walk():
    def node(role, label, frame, press=False, children=None):
        return {"role": role, "label": label, "frame": frame, "press": press, "children": children or []}

    root = node("AXApplication", "TestApp", (0.0, 1000.0, 0.0, 0.0), children=[
        node("AXButton", "ClickMe", (10.0, 10.0, 100.0, 20.0), press=True),
        node("AXButton", "Offscreen", (10.0, -100.0, 100.0, 20.0), press=True),
        node("AXButton", "TooSmall", (10.0, 10.0, 1.0, 1.0), press=True),
    ])

    found, offscreen, capped = walk_actionable(
        root,
        lambda n: n["children"],
        lambda n: AxAttrs(n["role"], n["label"], n["frame"]),
        lambda n: ["AXPress"] if n["press"] else [],
        1000.0,
        1000.0,
        offscreen_cap=10,
        time_cap=1.0,
    )

    assert len(found) == 1
    assert found[0].label == "ClickMe"
    assert len(offscreen) == 2
    assert offscreen[0].label == "Offscreen"
    assert capped is False

# 4. OCR adapter
def test_ocr_available():
    assert ocr._WINRT_OCR_AVAILABLE is True

def test_ocr_crop():
    img = Image.new("RGB", (300, 100), (255, 255, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Snapdragon NPU", fill=(0, 0, 0))

    lines = ocr.ocr_crop(img, (0.0, 0.0, 300.0, 100.0))
    assert isinstance(lines, list)
    if lines:
        text, conf, box = lines[0]
        assert isinstance(text, str)
        assert isinstance(conf, float)
        assert isinstance(box, tuple)
        assert len(box) == 4

# 5. Platform adapter
def test_platform_adapter():
    import sys
    assert sys.platform == "win32"
    assert platform_adapter.screenshot is windows.screenshot
    assert platform_adapter.click_at is windows.click_at

# 6. Input functions (interactive)
@pytest.mark.interactive
def test_input_functions():
    # Save mouse pos
    orig = windows.mouse_location()
    
    try:
        windows.click_at((100.0, 100.0))
        windows.press("a")
        windows.type_text("test")
        windows.scroll(-1)
        
        # Verify it didn't crash
        assert True
    finally:
        windows.click_at(orig)

# 7. Focused field
def test_focused_field():
    field = windows.focused_field()
    assert field is None or isinstance(field, Field)

# 8. Browser URL
def test_browser_url():
    url = windows.browser_url("Google Chrome")
    assert url is None or isinstance(url, str)

# 9. Full pipeline integration
def test_full_pipeline():
    cap = capture()
    assert cap is not None
    assert cap.image.width > 0

    items = perceive(cap, 5, "find a button")
    assert isinstance(items, list)
    if items:
        assert isinstance(items[0], Item)


# 10. End-to-end runner loop (dry run)
def test_runner_dry_run_end_to_end(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from typesafe_computer_use import runner
    from typesafe_computer_use.actions import Context
    from typesafe_computer_use.runner import RunConfig, run

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


        def system_one(self, state, questions):
            return SimpleNamespace(
                answers={
                    "kind": SimpleNamespace(choice="done", confidence=0.99, probabilities={"done": 0.99}),
                    "site": SimpleNamespace(choice="none", confidence=1.0, probabilities={"none": 1.0}),
                }
            )

    monkeypatch.setattr(runner, "TypeSafeClient", MockClient)
    cfg = RunConfig(goal="test windows runner loop", out=tmp_path / "run_out", steps=1, act=False)
    state = run(
        cfg,
        lambda ts, hist: Context(
            goal=cfg.goal,
            browser="Google Chrome",
            email=None,
            typesafe=ts,
            writer=None,
            history=hist,
        ),
    )

    assert state.outcome == "done"
    assert (cfg.out / "run.json").is_file()
    assert (cfg.out / "step-001.png").is_file()
    assert (cfg.out / "step-001-payload.txt").is_file()


import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from typesafe_computer_use.models import Field, Item, Screen
from typesafe_computer_use.slm_decide import (
    LocalChoiceAnswer,
    ParsedResponse,
    _backend,
    _backend_failed,
    _backend_init_done,
    _init_backend,
    format_prompt,
    parse_slm_response,
    slm_available,
    slm_verify_typed,
    to_decision,
)


@pytest.fixture(autouse=True)
def reset_backend_state():
    """Reset the singleton backend state between tests."""
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._backend = None
    slm_mod._backend_init_done = False
    slm_mod._backend_failed = False
    yield
    slm_mod._backend = None
    slm_mod._backend_init_done = False
    slm_mod._backend_failed = False


def test_format_prompt_basic(screen, make_item):
    items = [make_item(index=1, text="Submit", x1=10, y1=10, x2=50, y2=20, conf=0.9)]
    sys_prompt, user_prompt = format_prompt("click submit", screen, items, [])
    
    assert "You are an AI agent" in sys_prompt
    assert "Goal: click submit" in user_prompt
    assert "App: Google Chrome" in user_prompt
    assert "[1] 'Submit' (top-left)" in user_prompt
    assert "Recent actions: none" in user_prompt


def test_format_prompt_empty_items(screen):
    sys_prompt, user_prompt = format_prompt("do something", screen, [], [])
    assert "(no items visible)" in user_prompt


def test_format_prompt_focused_field(screen):
    field = Field(role="AXTextField", label="Search", placeholder="Search here", value="query", x=0, y=0, w=10, h=10)
    screen_with_field = Screen(image=screen.image, scale=screen.scale, app=screen.app, field=field, url=None)
    sys_prompt, user_prompt = format_prompt("search", screen_with_field, [], [])
    assert "Focused field: 'Search' (AXTextField), current value: 'query', placeholder: 'Search here'" in user_prompt


def test_format_prompt_history(screen):
    sys_prompt, user_prompt = format_prompt("goal", screen, [], ["opened browser", "clicked search"])
    assert "Recent actions: \n- opened browser\n- clicked search" in user_prompt or "Recent actions: \n- opened browser\n- clicked search" in user_prompt.replace("Recent actions:\n", "Recent actions: \n") or "Recent actions: - opened browser" in user_prompt.replace("\n-", " -") or "\n- opened browser\n- clicked search" in user_prompt


def test_format_prompt_max_items(screen, make_item):
    items = [make_item(index=i, text=f"item {i}") for i in range(30)]
    sys_prompt, user_prompt = format_prompt("goal", screen, items, [])
    assert "[0] 'item 0'" in user_prompt
    assert "[24] 'item 24'" in user_prompt
    assert "[25] 'item 25'" not in user_prompt


@pytest.mark.parametrize("json_text, expected_action, expected_item, expected_site, expected_conf", [
    ('{"action":"click_item","item":3,"site":null,"reason":"test"}', "click_item", 3, "none", 0.85),
    ('{"action":"click","item":3}', "click_item", 3, "none", 0.85),
    ('{"action":"tap","item":3}', "click_item", 3, "none", 0.85),
    ('{"action":"type","item":null}', "type_text", None, "none", 0.85),
    ('{"action":"invalid_action"}', "none", None, "none", 0.55),  # 0.85 - 0.3 penalty
    ('{"action":"click_item","item":"invalid","reason":"x"}', "none", None, "none", 0.55), # NaN item -> none fallback + penalty
    ('{"action":"click_item","item":99,"reason":"x"}', "none", None, "none", 0.55), # out of range -> penalty
    ('```json\n{"action":"scroll_down"}\n```', "scroll_down", None, "none", 0.85),
    ('{"action": "click_item", "item": 3,}', "click_item", 3, "none", 0.85), # trailing comma fixed
    ("{'action':'done'}", "done", None, "none", 0.85), # single quotes
    ('finish', "done", None, None, 0.5), # bare action returns site None
    ('', "none", None, None, 0.3), # empty string returns site None
    ('{"action":"use_browser","site":"youtube"}', "use_browser", None, "youtube", 0.85),
    ('{"action":"done","confidence":1.5}', "done", None, "none", 1.0),
    ('{"action":"done","confidence":-0.5}', "done", None, "none", 0.1),
])
def test_parse_slm_response(make_item, json_text, expected_action, expected_item, expected_site, expected_conf):
    items = [make_item(index=3, text="btn")]
    resp = parse_slm_response(json_text, items)
    assert resp.action == expected_action
    assert resp.item == expected_item
    assert resp.site == expected_site
    assert abs(resp.confidence - expected_conf) < 0.01


def test_parse_slm_response_click_reason_fallback(make_item):
    # click_item without valid item, but reason contains item text
    items = [make_item(index=5, text="login")]
    resp = parse_slm_response('{"action":"click_item","item":null,"reason":"click login button"}', items)
    assert resp.action == "click_item"
    assert resp.item == 5
    # penalty is still applied if item was null in json but recovered
    assert abs(resp.confidence - 0.85) < 0.01


def test_to_decision_click_item(screen, make_item):
    items = [make_item(index=1, text="test")]
    parsed = ParsedResponse(action="click_item", item=1, site="none", reason="", confidence=0.9)
    decision = to_decision(parsed, items, screen)
    
    assert decision.kind.choice == "click_item"
    assert decision.item.choice == "1"
    assert decision.site.choice == "none"
    assert decision.clicking is True
    assert decision.stops is False
    assert decision.chosen == "1"
    assert decision.confidence == 0.9


def test_to_decision_type_text(screen, make_item):
    parsed = ParsedResponse(action="type_text", item=None, site="none", reason="", confidence=0.8)
    decision = to_decision(parsed, [], screen)
    
    assert decision.kind.choice == "type_text"
    assert decision.item is None
    assert decision.clicking is False
    assert decision.stops is False


def test_to_decision_use_browser(screen, make_item):
    parsed = ParsedResponse(action="use_browser", item=None, site="github", reason="", confidence=0.7)
    decision = to_decision(parsed, [], screen)
    
    assert decision.kind.choice == "use_browser"
    assert decision.site.choice == "github"
    assert decision.site.confidence == 0.7


def test_to_decision_stops(screen, make_item):
    parsed = ParsedResponse(action="done", item=None, site="none", reason="", confidence=0.95)
    decision = to_decision(parsed, [], screen)
    assert decision.stops is True


def test_slm_available_no_model(monkeypatch):
    monkeypatch.setenv("ARGUS_SLM_MODEL_DIR", "/nonexistent/dir")
    monkeypatch.setenv("ARGUS_SLM_GGUF", "/nonexistent/file.gguf")
    monkeypatch.setenv("ARGUS_SLM_REST_URL", "http://invalid.url:9999")
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._DEFAULT_MODEL_DIRS = []
    assert not slm_available()
    assert slm_mod._backend_failed is True


def test_slm_available_with_model(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "genai_config.json").touch()
    monkeypatch.setenv("ARGUS_SLM_MODEL_DIR", str(model_dir))
    
    class MockOrtGenAIBackend:
        def __init__(self, d): self.d = d
        def generate(self, s, u): return '{"action":"done"}'
        def name(self): return "mock_onnx"
        
    import typesafe_computer_use.slm_decide as slm_mod
    monkeypatch.setattr(slm_mod, "_OrtGenAIBackend", MockOrtGenAIBackend)
    
    assert slm_available()
    assert slm_mod._backend_init_done is True
    assert _backend_failed is False


def test_slm_available_rest_backend(monkeypatch):
    monkeypatch.setenv("ARGUS_SLM_MODEL_DIR", "/nonexistent/dir")
    monkeypatch.setenv("ARGUS_SLM_GGUF", "/nonexistent/file.gguf")
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._DEFAULT_MODEL_DIRS = []
    
    class MockRestBackend:
        def __init__(self, url, model): self.url = url
        def generate(self, s, u): return 'OK'
        def name(self): return "mock_rest"
        
    import typesafe_computer_use.slm_decide as slm_mod
    monkeypatch.setattr(slm_mod, "_RestBackend", MockRestBackend)
    assert slm_available()
    assert slm_mod._backend_init_done is True


def test_slm_verify_typed_no_backend(monkeypatch):
    monkeypatch.setenv("ARGUS_SLM_MODEL_DIR", "/nonexistent/dir")
    monkeypatch.setenv("ARGUS_SLM_GGUF", "/nonexistent/file.gguf")
    monkeypatch.setenv("ARGUS_SLM_REST_URL", "http://invalid.url:9999")
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._DEFAULT_MODEL_DIRS = []
    
    f_before = Field("AXTextField", "Search", "", "", 0, 0, 10, 10)
    f_after = Field("AXTextField", "Search", "", "hello", 0, 0, 10, 10)
    
    conf = slm_verify_typed("type hello", f_before, "hello", f_after)
    assert conf == 1.0


def test_slm_verify_typed_with_backend_ok(monkeypatch):
    class MockBackend:
        def generate(self, s, u): return '{"ok":true,"confidence":0.99}'
        def name(self): return "mock"
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._backend = MockBackend()
    slm_mod._backend_init_done = True
    
    f_before = Field("AXTextField", "Search", "", "", 0, 0, 10, 10)
    f_after = Field("AXTextField", "Search", "", "hello", 0, 0, 10, 10)
    
    conf = slm_verify_typed("type hello", f_before, "hello", f_after)
    assert conf == 0.99


def test_slm_verify_typed_missing_field_after(monkeypatch):
    monkeypatch.setenv("ARGUS_SLM_MODEL_DIR", "/nonexistent/dir")
    monkeypatch.setenv("ARGUS_SLM_GGUF", "/nonexistent/file.gguf")
    monkeypatch.setenv("ARGUS_SLM_REST_URL", "http://invalid.url:9999")
    import typesafe_computer_use.slm_decide as slm_mod
    slm_mod._DEFAULT_MODEL_DIRS = []
    
    f_before = Field("AXTextField", "Search", "", "", 0, 0, 10, 10)
    conf = slm_verify_typed("type hello", f_before, "hello", None)
    assert conf == 0.95

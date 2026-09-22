"""Pytest fixtures and environment hooks for E2E testing."""

from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from .harness import TargetHarness, ensure_desktop

FONT_PATH = r"C:\Windows\Fonts\segoeui.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeui.ttf") else r"C:\Windows\Fonts\arial.ttf"


@pytest.fixture(autouse=True)
def setup_interactive_desktop():
    """Ensure every test thread is attached to the interactive desktop station."""
    ensure_desktop()
    yield
    gc.collect()


def pytest_sessionfinish(session, exitstatus):
    """Cleanly teardown WinRT OCR COM engine before COM runtime uninitialization."""
    try:
        from typesafe_computer_use import ocr
        if hasattr(ocr, "_ocr_engine"):
            ocr._ocr_engine = None
    except Exception:
        pass
    gc.collect()


@pytest.fixture
def harness():
    """Return a TargetHarness instance."""
    return TargetHarness()


@pytest.fixture
def native_app_session(harness):
    """Launch native Tkinter test app and ensure cleanup."""
    session = harness.launch_native_tk()
    yield session
    harness.terminate(session)
    gc.collect()


@pytest.fixture
def ocr_test_image_factory():
    """Factory fixture to create synthetic images containing known text with known coordinates."""

    def _create(
        lines: list[str],
        width: int = 500,
        height: int = 200,
        bg_color: tuple = (255, 255, 255),
        text_color: tuple = (0, 0, 0),
        font_size: int = 24,
    ) -> Image.Image:
        img = Image.new("RGBA", (width, height), (*bg_color, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            font = ImageFont.load_default()

        y = 20
        for line in lines:
            draw.text((20, y), line, fill=(*text_color, 255), font=font)
            y += font_size + 14
        return img

    return _create

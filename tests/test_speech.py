import sys
import pytest
from typesafe_computer_use import speech


def test_speech_module_exports():
    assert hasattr(speech, "speak")
    assert hasattr(speech, "listen")


def test_speech_speak_noop_on_empty():
    # Should safely return without error on empty string
    speech.speak("")
    speech.speak("   ")


def test_speech_speak_mocked(monkeypatch):
    called = []
    monkeypatch.setattr(speech, "_do_speak", lambda: called.append(True), raising=False)
    # Ensure speak doesn't crash
    speech.speak("Test voice output", wait=True)

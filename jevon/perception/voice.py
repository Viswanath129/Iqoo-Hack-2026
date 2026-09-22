"""Voice pipeline for JEVON on-device perception."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes using Whisper NPU or local fallback."""
    try:
        from typesafe_computer_use import whisper_npu
        return whisper_npu.transcribe_audio_data(audio_bytes)
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return ""


def speak_text_async(text: str) -> None:
    """Speak text asynchronously using on-device TTS."""
    try:
        from typesafe_computer_use import speech
        speech.speak_async(text)
    except Exception as e:
        logger.debug(f"Speech synthesis unavailable: {e}")

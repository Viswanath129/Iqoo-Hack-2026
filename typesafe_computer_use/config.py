"""Tunables, the site catalog, and environment loading."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MIN_OCR_CONFIDENCE = 0.3
MAX_OPTIONS = 255  # TypeSafe Choice ceiling
ABORT_CORNER_PX = 4
DEFAULT_MIN_CONFIDENCE = 0.25
DEFAULT_STEPS = 100
DEFAULT_DELAY = 2.0
DEFAULT_WRITER_MODEL = "claude-haiku-4-5"
DEFAULT_ANSWER_MODEL = "claude-sonnet-5"  # runs once per run, on a screenshot: worth a stronger reader
DEFAULT_BROWSER = "Microsoft Edge" if sys.platform == "win32" else "Google Chrome"
DEFAULT_CLASSIFIER_MODEL = "jev-latest"  # TypeSafe JEV decision model


# Sites the classifier can pick by name. Anything else goes through the writer.
SITES: dict[str, str] = {
    "chatgpt": "https://chatgpt.com/",
    "claude": "https://claude.ai/",
    "gemini": "https://gemini.google.com/",
    "github": "https://github.com/",
    "gmail": "https://mail.google.com/",
    "google": "https://www.google.com/",
    "google_calendar": "https://calendar.google.com/",
    "launchdarkly": "https://app.launchdarkly.com/",
    "linear": "https://linear.app/",
    "notion": "https://www.notion.so/",
    "perplexity": "https://www.perplexity.ai/",
    "reddit": "https://reddit.com/",
    "slack": "https://app.slack.com/",
    "spotify": "https://open.spotify.com/",
    "twitter": "https://x.com/",
    "typesafe_console": "https://console.typesafe.ai/",
    "wikipedia": "https://www.wikipedia.org/",
    "youtube": "https://www.youtube.com/",
}


def load_dotenv(path: Path) -> None:
    """Set KEY=VALUE lines from a .env file into the environment unless already set."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def browser() -> str:
    return os.environ.get("CLICKER_BROWSER", DEFAULT_BROWSER)


def classifier_model() -> str:
    return os.environ.get("CLICKER_MODEL", DEFAULT_CLASSIFIER_MODEL)


def writer_model() -> str:
    return os.environ.get("CLICKER_WRITER_MODEL", DEFAULT_WRITER_MODEL)



def answer_model() -> str:
    return os.environ.get("CLICKER_ANSWER_MODEL", DEFAULT_ANSWER_MODEL)


def email() -> str | None:
    return os.environ.get("CLICKER_EMAIL") or None


# ------------------------------------------------------------------ SLM (on-device decision model)

DEFAULT_SLM_MODEL = "qwen2.5-0.5b"


def slm_model_dir() -> str | None:
    """Directory containing the ONNX GenAI model for on-device decisions."""
    return os.environ.get("ARGUS_SLM_MODEL_DIR")


def slm_gguf_path() -> str | None:
    """Path to a GGUF model file for llama.cpp backend."""
    return os.environ.get("ARGUS_SLM_GGUF")


def slm_rest_url() -> str:
    """REST endpoint for remote SLM inference (Ollama-compatible)."""
    return os.environ.get("ARGUS_SLM_REST_URL", "http://localhost:11434/api/generate")


def slm_rest_model() -> str:
    """Model name for REST inference."""
    return os.environ.get("ARGUS_SLM_REST_MODEL", "qwen2.5:0.5b")


def target_platform() -> str:
    """Target platform: 'android', 'windows', or 'macos'. Set ARGUS_TARGET to override auto-detect."""
    target = os.environ.get("ARGUS_TARGET", "").lower()
    if target in ("android", "windows", "macos"):
        return target
    if sys.platform == "win32":
        return "windows"
    return "macos"


# ------------------------------------------------------------------ Android-specific

ANDROID_BROWSER = "Chrome"
ANDROID_DELAY = 1.5
ADB_HOST = os.environ.get("ADB_HOST", "localhost")
ADB_PORT = int(os.environ.get("ADB_PORT", "5037"))

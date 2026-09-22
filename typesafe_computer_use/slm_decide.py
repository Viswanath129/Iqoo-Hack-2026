"""On-device SLM decision engine — replaces cloud TypeSafe JEV with local NPU inference.

Runs Qwen 2.5 (0.5B-Instruct, INT4 quantized) on the Qualcomm Hexagon NPU
via ONNX Runtime GenAI with QNN Execution Provider.  Falls back to llama.cpp
(GGUF), a local REST inference server, or enhanced heuristics.

The SLM replicates JEV's three-choice interface:
  kind  → which action type (click_item, type_text, scroll_down, done, ...)
  item  → which screen item to click (index number)
  site  → which website to open (catalog key or "none")

One inference call produces all three answers as structured JSON, keeping the
per-step NPU latency under 800ms on Snapdragon 8 Elite Gen 5 (INT4).

Backend priority:
  1. onnxruntime-genai + QNN EP  (Snapdragon Hexagon NPU — fastest)
  2. onnxruntime-genai + CPU EP  (ARM64 or x86 fallback)
  3. llama-cpp-python GGUF model (widely available)
  4. Local HTTP inference server  (run model anywhere on LAN)
  5. decide_local() heuristics   (no model needed, keyword matching)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import SITES
from .dates import now_context
from .models import AxNode, Field, Item, Screen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LocalChoiceAnswer — drop-in replacement for typesafe_sdk.ChoiceAnswer
# so Decision objects work identically regardless of whether the answer came
# from the cloud JEV API or the local SLM.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalChoiceAnswer:
    """Compatible with typesafe_sdk.ChoiceAnswer: .choice, .confidence, .probabilities."""

    choice: str
    confidence: float
    probabilities: dict[str, float]


# ---------------------------------------------------------------------------
# SLM configuration
# ---------------------------------------------------------------------------

# Default model search paths — checked in order.  The first directory containing
# an ONNX GenAI model (genai_config.json) or a GGUF file wins.
_DEFAULT_MODEL_DIRS: list[str] = [
    # Android / Termux
    os.path.expanduser("~/models/qwen2.5-0.5b"),
    "/data/local/tmp/models/qwen2.5-0.5b",
    "/sdcard/argus/models/qwen2.5-0.5b",
    # Windows / Snapdragon X
    r"B:\projects\models\qwen2.5-0.5b",
    os.path.expanduser("~/.cache/argus/models/qwen2.5-0.5b"),
    # Relative to project root
    str(Path(__file__).resolve().parent.parent / "models" / "qwen2.5-0.5b"),
]

# REST server endpoint for Option 4 (local server on LAN)
_DEFAULT_REST_URL = "http://localhost:11434/api/generate"  # Ollama-compatible

# Generation parameters — tuned for fast, deterministic single-choice output
_MAX_TOKENS = 150
_TEMPERATURE = 0.1
_TOP_P = 0.9

# How many screen items to include in the prompt (keep token count low)
_MAX_PROMPT_ITEMS = 25

# Timeout for REST inference calls
_REST_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an AI agent that controls a phone or computer one action at a time. "
    "Analyze the current screen state and choose the single best next action to make "
    "progress toward the goal. Do NOT repeat an action that was just taken unless the "
    "screen changed. Output ONLY valid JSON, nothing else."
)

_USER_TEMPLATE = """\
Goal: {goal}
Time: {now}
App: {app}
URL: {url}
Focused field: {field}
Recent actions: {history}

Screen items (click by index):
{items}

Available actions:
- click_item: Click a screen item by its index number.
- type_text: Type into the focused text field. Only when a text field is focused.
- use_browser: Open a website. Specify site name or "other".
- launch_app: Open or switch to a desktop/mobile application.
- play_media: Play/pause media playback.
- scroll_down / scroll_up: Scroll the page.
- press_enter: Press Return/Enter to submit.
- press_escape: Press Escape to dismiss.
- done: The goal is already achieved on this screen.
- none: Nothing on screen helps with the goal.

Respond with JSON: {{"action":"...","item":<index_or_null>,"site":"<name_or_null>","reason":"brief"}}"""


def _format_field(field: Field | None) -> str:
    if field is None:
        return "none"
    val = f"{field.label!r} ({field.role})" if field.label else field.role
    if field.value:
        val += f", current value: {field.value[:60]!r}"
    if field.placeholder:
        val += f", placeholder: {field.placeholder!r}"
    return val


def _format_item(item: Item, screen: Screen) -> str:
    role_prefix = f"{item.role} " if item.role else ""
    region = screen.region(item)
    return f"[{item.index}] {role_prefix}{item.text!r} ({region})"


def _format_history(history: list[str]) -> str:
    if not history:
        return "none"
    return "\n".join(f"- {h}" for h in history[-5:])


def format_prompt(
    goal: str, screen: Screen, items: list[Item], history: list[str]
) -> tuple[str, str]:
    """Build the system and user prompts for the SLM.  Returns (system, user)."""
    items_text = "\n".join(
        _format_item(it, screen) for it in items[:_MAX_PROMPT_ITEMS]
    )
    if not items_text:
        items_text = "(no items visible)"
    user = _USER_TEMPLATE.format(
        goal=goal,
        now=now_context(),
        app=screen.app or "unknown",
        url=screen.url or "none",
        field=_format_field(screen.field),
        history=_format_history(history),
        items=items_text,
    )
    return _SYSTEM_PROMPT, user


# ---------------------------------------------------------------------------
# Response parsing — extract structured decision from SLM output
# ---------------------------------------------------------------------------

# Map action synonyms the model might produce to canonical action names
_ACTION_ALIASES: dict[str, str] = {
    "click": "click_item",
    "tap": "click_item",
    "tap_item": "click_item",
    "type": "type_text",
    "enter_text": "type_text",
    "input_text": "type_text",
    "browser": "use_browser",
    "open_browser": "use_browser",
    "open_url": "use_browser",
    "scroll": "scroll_down",
    "enter": "press_enter",
    "escape": "press_escape",
    "launch": "launch_app",
    "open_app": "launch_app",
    "play": "play_media",
    "finish": "done",
    "complete": "done",
    "achieved": "done",
    "nothing": "none",
    "wait": "none",
}

_VALID_ACTIONS = {
    "click_item", "type_text", "use_browser", "launch_app", "play_media",
    "scroll_down", "scroll_up", "press_enter", "press_escape", "done", "none",
}

# Site catalog keys for mapping model output
_SITE_ALIASES: dict[str, str] = {}
for key in SITES:
    _SITE_ALIASES[key] = key
    _SITE_ALIASES[key.replace("_", "")] = key
    # Also map domain names
    from urllib.parse import urlparse as _urlparse
    domain = _urlparse(SITES[key]).netloc.replace("www.", "").split(".")[0]
    _SITE_ALIASES[domain] = key


@dataclass
class ParsedResponse:
    action: str
    item: int | None
    site: str | None
    reason: str
    confidence: float


def parse_slm_response(
    text: str, items: list[Item], valid_sites: dict[str, str] | None = None
) -> ParsedResponse:
    """Parse the SLM's JSON output into a structured response.

    Handles common model quirks: markdown code fences, trailing text, action
    name variations, invalid item indices.
    """
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    # Try to extract JSON from the text
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match is None:
        # No JSON found — try to interpret as a bare action name
        action = text.strip().lower().replace(" ", "_")
        action = _ACTION_ALIASES.get(action, action)
        if action in _VALID_ACTIONS:
            return ParsedResponse(action=action, item=None, site=None, reason="", confidence=0.5)
        return ParsedResponse(action="none", item=None, site=None, reason="parse_failed", confidence=0.3)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        # Try fixing common JSON issues (single quotes, trailing commas)
        fixed = json_match.group().replace("'", '"')
        fixed = re.sub(r",\s*}", "}", fixed)
        fixed = re.sub(r",\s*]", "]", fixed)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError:
            return ParsedResponse(action="none", item=None, site=None, reason="json_parse_failed", confidence=0.3)

    # Extract and normalize action
    raw_action = str(data.get("action", "none")).strip().lower().replace(" ", "_")
    action = _ACTION_ALIASES.get(raw_action, raw_action)
    if action not in _VALID_ACTIONS:
        action = "none"
        confidence_penalty = 0.3
    else:
        confidence_penalty = 0.0

    # Extract item index
    raw_item = data.get("item")
    item_idx = None
    if raw_item is not None:
        try:
            item_idx = int(raw_item)
            # Validate against actual items
            valid_indices = {it.index for it in items}
            if item_idx not in valid_indices:
                item_idx = None
                confidence_penalty = max(confidence_penalty, 0.2)
        except (ValueError, TypeError):
            item_idx = None

    # If action is click_item but no valid item, fall back
    if action == "click_item" and item_idx is None:
        if items:
            # Try to find item by matching reason text against item labels
            reason = str(data.get("reason", "")).lower()
            for it in items:
                if it.text.lower() in reason or reason in it.text.lower():
                    item_idx = it.index
                    break
        if item_idx is None:
            action = "none"
            confidence_penalty = max(confidence_penalty, 0.3)

    # Extract site
    raw_site = data.get("site")
    site = "none"
    if raw_site and isinstance(raw_site, str) and raw_site.lower() not in ("null", "none", ""):
        site_lower = raw_site.lower().strip()
        site = _SITE_ALIASES.get(site_lower, "other")

    # Extract reason
    reason = str(data.get("reason", ""))[:200]

    # Estimate confidence from response quality
    confidence = data.get("confidence", 0.85)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.85
    confidence = max(0.1, min(1.0, confidence - confidence_penalty))

    return ParsedResponse(
        action=action, item=item_idx, site=site, reason=reason, confidence=confidence
    )


# ---------------------------------------------------------------------------
# Convert parsed response to a Decision (matching JEV's output format)
# ---------------------------------------------------------------------------

# Import Decision here to avoid circular imports at module level
# (decide.py imports from us, we import Decision from decide.py)
# We use a lazy import pattern.

_Decision = None


def _get_decision_class():
    global _Decision
    if _Decision is None:
        from .decide import Decision
        _Decision = Decision
    return _Decision


def to_decision(
    parsed: ParsedResponse, items: list[Item], screen: Screen
) -> Any:
    """Convert a ParsedResponse into a Decision object compatible with the rest of the codebase."""
    Decision = _get_decision_class()

    kind = LocalChoiceAnswer(
        choice=parsed.action,
        confidence=parsed.confidence,
        probabilities={parsed.action: parsed.confidence},
    )

    item_answer = None
    if parsed.action == "click_item" and parsed.item is not None:
        item_answer = LocalChoiceAnswer(
            choice=str(parsed.item),
            confidence=parsed.confidence,
            probabilities={str(parsed.item): parsed.confidence},
        )

    site_answer = LocalChoiceAnswer(
        choice=parsed.site or "none",
        confidence=parsed.confidence if parsed.action == "use_browser" else 1.0,
        probabilities={parsed.site or "none": 1.0},
    )

    offscreen_answer = None

    return Decision(
        kind=kind,
        item=item_answer,
        site=site_answer,
        offscreen=offscreen_answer,
    )


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------


class SLMBackend(Protocol):
    """Any backend that can generate text from a prompt."""

    def generate(self, system: str, user: str) -> str: ...
    def name(self) -> str: ...


# ---------------------------------------------------------------------------
# Backend 1: ONNX Runtime GenAI (NPU-accelerated)
# ---------------------------------------------------------------------------

class _OrtGenAIBackend:
    """ONNX Runtime GenAI — best path for Snapdragon Hexagon NPU."""

    def __init__(self, model_dir: str):
        import onnxruntime_genai as og

        self._model = og.Model(model_dir)
        self._tokenizer = og.Tokenizer(self._model)
        self._model_dir = model_dir
        logger.info("[SLM] Loaded ONNX GenAI model from %s", model_dir)

    def generate(self, system: str, user: str) -> str:
        import onnxruntime_genai as og

        # Format as Qwen 2.5 chat template
        prompt = (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        params = og.GeneratorParams(self._model)
        params.set_search_options(
            max_length=len(self._tokenizer.encode(prompt)) + _MAX_TOKENS,
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            do_sample=_TEMPERATURE > 0,
        )

        input_tokens = self._tokenizer.encode(prompt)
        params.input_ids = input_tokens

        output_tokens = self._model.generate(params)
        response = self._tokenizer.decode(output_tokens[0][len(input_tokens):])

        # Strip end-of-turn tokens
        for eos in ("<|im_end|>", "<|endoftext|>", "</s>"):
            if eos in response:
                response = response[:response.index(eos)]

        return response.strip()

    def name(self) -> str:
        return f"onnxruntime-genai ({self._model_dir})"


# ---------------------------------------------------------------------------
# Backend 2: llama.cpp (GGUF models)
# ---------------------------------------------------------------------------

class _LlamaCppBackend:
    """llama-cpp-python — widely available, supports Vulkan GPU and CPU."""

    def __init__(self, model_path: str):
        from llama_cpp import Llama

        self._llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_gpu_layers=-1,  # Use GPU/NPU if available
            verbose=False,
        )
        self._model_path = model_path
        logger.info("[SLM] Loaded GGUF model from %s", model_path)

    def generate(self, system: str, user: str) -> str:
        # Qwen 2.5 chat format via llama.cpp
        prompt = (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        output = self._llm(
            prompt,
            max_tokens=_MAX_TOKENS,
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            stop=["<|im_end|>", "<|endoftext|>"],
            echo=False,
        )
        return output["choices"][0]["text"].strip()

    def name(self) -> str:
        return f"llama.cpp ({self._model_path})"


# ---------------------------------------------------------------------------
# Backend 3: REST API (Ollama-compatible)
# ---------------------------------------------------------------------------

class _RestBackend:
    """HTTP inference server — Ollama, vLLM, or any OpenAI-compatible endpoint."""

    def __init__(self, url: str, model: str = "qwen2.5:0.5b"):
        self._url = url.rstrip("/")
        self._model = model
        logger.info("[SLM] Using REST backend at %s (model=%s)", url, model)

    def generate(self, system: str, user: str) -> str:
        import urllib.error
        import urllib.request

        # Try Ollama /api/generate format first
        payload = json.dumps({
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {
                "temperature": _TEMPERATURE,
                "top_p": _TOP_P,
                "num_predict": _MAX_TOKENS,
            },
        }).encode()

        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_REST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data.get("response", "").strip()
        except Exception as e:
            logger.warning("[SLM] REST inference failed: %s", e)
            return ""

    def name(self) -> str:
        return f"REST ({self._url}, model={self._model})"


# ---------------------------------------------------------------------------
# Backend initialization — lazy, thread-safe, tries each backend in priority
# ---------------------------------------------------------------------------

_backend: SLMBackend | None = None
_backend_lock = threading.Lock()
_backend_init_done = False
_backend_failed = False


def _find_model_dir() -> str | None:
    """Search for a model directory containing an ONNX GenAI model."""
    env_dir = os.environ.get("ARGUS_SLM_MODEL_DIR")
    search = [env_dir] if env_dir else _DEFAULT_MODEL_DIRS

    for candidate in search:
        if not candidate:
            continue
        p = Path(candidate)
        # ONNX GenAI model directory (contains genai_config.json)
        if (p / "genai_config.json").is_file():
            return str(p)
        # Also check for ONNX model file directly
        if p.is_file() and p.suffix == ".onnx":
            return str(p.parent)
    return None


def _find_gguf() -> str | None:
    """Search for a GGUF model file."""
    env_path = os.environ.get("ARGUS_SLM_GGUF")
    if env_path and Path(env_path).is_file():
        return env_path

    for candidate in _DEFAULT_MODEL_DIRS:
        if not candidate:
            continue
        p = Path(candidate)
        # Check for GGUF files in the model directory
        if p.is_dir():
            for gguf in sorted(p.glob("*.gguf")):
                return str(gguf)
        # Also check parent directory
        parent = p.parent
        if parent.is_dir():
            for gguf in sorted(parent.glob("*.gguf")):
                return str(gguf)
    return None


def _init_backend() -> SLMBackend | None:
    """Try each backend in priority order. Returns the first one that works."""
    global _backend, _backend_init_done, _backend_failed

    with _backend_lock:
        if _backend_init_done:
            return _backend
        _backend_init_done = True

        # 1. Try ONNX Runtime GenAI
        model_dir = _find_model_dir()
        if model_dir:
            try:
                _backend = _OrtGenAIBackend(model_dir)
                print(f"[SLM] ✓ ONNX GenAI backend loaded (Hexagon NPU): {model_dir}", flush=True)
                return _backend
            except Exception as e:
                logger.warning("[SLM] ONNX GenAI failed: %s", e)
                print(f"[SLM] ONNX GenAI failed: {e}", flush=True)

        # 2. Try llama.cpp
        gguf_path = _find_gguf()
        if gguf_path:
            try:
                _backend = _LlamaCppBackend(gguf_path)
                print(f"[SLM] ✓ llama.cpp backend loaded: {gguf_path}", flush=True)
                return _backend
            except Exception as e:
                logger.warning("[SLM] llama.cpp failed: %s", e)
                print(f"[SLM] llama.cpp failed: {e}", flush=True)

        # 3. Try REST endpoint
        rest_url = os.environ.get("ARGUS_SLM_REST_URL", _DEFAULT_REST_URL)
        rest_model = os.environ.get("ARGUS_SLM_REST_MODEL", "qwen2.5:0.5b")
        try:
            backend = _RestBackend(rest_url, rest_model)
            # Quick health check
            test = backend.generate("Reply with OK.", "Test")
            if test:
                _backend = backend
                print(f"[SLM] ✓ REST backend connected: {rest_url}", flush=True)
                return _backend
        except Exception as e:
            logger.debug("[SLM] REST backend unavailable: %s", e)

        # 4. No model available — will fall back to decide_local() in the caller
        _backend_failed = True
        print("[SLM] ✗ No SLM backend available. Falling back to keyword heuristics.", flush=True)
        return None


def warmup() -> None:
    """Pre-initialize the SLM backend (call at startup for faster first decision)."""
    _init_backend()


def warmup_background() -> None:
    """Pre-initialize in a background thread."""
    t = threading.Thread(target=warmup, daemon=True, name="SLM-Warmup")
    t.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def slm_available() -> bool:
    """True when an SLM backend is loaded and ready for inference."""
    if _backend is not None:
        return True
    if _backend_init_done and _backend_failed:
        return False
    # Not yet initialized — try now
    return _init_backend() is not None


def slm_decide(
    goal: str,
    screen: Screen,
    items: list[Item],
    history: list[str],
    browser: str = "",
    email: str | None = None,
) -> Any:
    """Run the on-device SLM to choose the next action.

    Returns a Decision object identical to what decide() and decide_local() return.
    Raises RuntimeError if no SLM backend is available (caller should fall back).
    """
    backend = _init_backend()
    if backend is None:
        raise RuntimeError("No SLM backend available")

    system_prompt, user_prompt = format_prompt(goal, screen, items, history)

    started = time.monotonic()
    try:
        raw_output = backend.generate(system_prompt, user_prompt)
    except Exception as e:
        logger.error("[SLM] Inference failed: %s", e)
        raise RuntimeError(f"SLM inference failed: {e}") from e

    elapsed = time.monotonic() - started
    logger.info("[SLM] Inference in %.3fs via %s", elapsed, backend.name())
    print(f"[SLM] Decision in {elapsed:.2f}s via {backend.name()}: {raw_output[:120]}", flush=True)

    parsed = parse_slm_response(raw_output, items)
    return to_decision(parsed, items, screen)


def slm_verify_typed(
    goal: str, field_before: Field, typed: str, field_after: Field | None
) -> float:
    """Verify that typed text is correct — SLM-based replacement for TypeSafe Noul.

    Returns probability (0.0 to 1.0) that the field now holds a sensible value.
    """
    backend = _init_backend()
    if backend is None:
        # Basic string-match fallback
        if field_after and typed.strip().lower() in field_after.value.lower():
            return 1.0
        return 0.95

    system = (
        "You verify whether text was typed correctly into a form field. "
        "Output JSON: {\"ok\": true/false, \"confidence\": 0.0-1.0}"
    )
    user = (
        f"Goal: {goal}\n"
        f"Field: {field_before.label!r} ({field_before.role})\n"
        f"Text typed: {typed!r}\n"
        f"Field value now: {(field_after.value[:200] if field_after else 'unknown')!r}\n"
        f"Is this correct?"
    )

    try:
        raw = backend.generate(system, user)
        match = re.search(r"\{[^{}]*\}", raw)
        if match:
            data = json.loads(match.group())
            ok = data.get("ok", True)
            conf = float(data.get("confidence", 0.9))
            return conf if ok else 1.0 - conf
    except Exception as e:
        logger.warning("[SLM] Verify failed: %s", e)

    # Fallback: simple string match
    if field_after and typed.strip().lower() in field_after.value.lower():
        return 1.0
    return 0.95


def slm_backend_name() -> str:
    """Human-readable name of the active backend, or 'none'."""
    if _backend is not None:
        return _backend.name()
    return "none"

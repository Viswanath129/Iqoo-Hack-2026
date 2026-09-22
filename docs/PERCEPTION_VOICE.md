# Perception & Voice Pipeline

## Overview

The Perception & Voice Pipeline handles all environmental sensing — screen capture, accessibility tree parsing, OCR, speech recognition, and speech synthesis — enabling JEVON to perceive, hear, and respond to the developer environment.

**Source**: [`typesafe_computer_use/`](../typesafe_computer_use/) (desktop) and [`jevon/perception/`](../jevon/perception/) (JEVON-specific)

---

## Screen Perception

### Platform Adapter

[`platform_adapter.py`](../typesafe_computer_use/platform_adapter.py) dynamically dispatches to the correct OS backend:

```python
# Automatic routing based on environment
if os.environ.get("ARGUS_TARGET") == "android":
    from . import android         # ADB-based
elif sys.platform == "win32":
    return getattr(windows, name)  # Win32/UIA
else:
    return getattr(macos, name)    # macOS Quartz
```

- Preserves test monkeypatching hooks on the `macos` module
- Supports runtime override via `ARGUS_TARGET` environment variable

### Windows Perception Stack

| Component | File | Technology | Latency |
|:---|:---|:---|:---|
| **Screen Capture** | `windows.py` | `mss` multi-monitor DPI-aware | ~20ms |
| **UIAutomation Tree** | `windows.py` | COM-based `uiautomation` | ~50ms |
| **Hardware OCR** | `ocr.py` | WinRT `Windows.Media.Ocr` | ~150ms |
| **Tile Cache** | `ocr.py` | Changed-tile bounding box cache | Reduces re-OCR |

#### DPI-Aware Capture
```python
# Per-monitor DPI scaling handled by mss
# Coordinates are normalized to prevent alignment drift
```

#### UIAutomation Tree
- COM-based tree traversal with configurable depth limits
- Duplicate control filtering
- Focused field inspection
- Indexed control list `[0..N]` for decision targeting

#### WinRT Hardware OCR
- Uses `Windows.Media.Ocr.OcrEngine` via `winsdk`
- Tile-level change detection (`_TileCache`) avoids re-OCRing unchanged regions
- Bounding box extraction for text positioning
- ~150ms typical latency (GPU-accelerated via Direct3D)

### macOS Perception Stack

| Component | Technology |
|:---|:---|
| Screen Capture | `Quartz.CGWindowListCreateImage` |
| Accessibility Tree | PyObjC `AXUIElement` |
| OCR | Apple Vision framework via `ocrmac` |

### Android Perception Stack

| Component | Technology |
|:---|:---|
| Screen Capture | `adb shell screencap` |
| UI Hierarchy | `adb shell uiautomator dump` |
| Input Simulation | `adb shell input tap/text/keyevent` |

---

## Perception Pipeline (`perception.py`)

The main perception pipeline:

1. **Capture**: Take a screenshot with DPI awareness
2. **OCR**: Run WinRT hardware OCR on the capture
3. **UIA Parse**: Walk the UIAutomation tree for interactive controls
4. **Merge**: Combine OCR text regions with UIA control nodes
5. **Index**: Assign `[0..N]` indices to interactive elements
6. **Reading Order**: Sort items in human reading order (top-to-bottom, left-to-right)
7. **Offscreen Detection**: Identify controls in the accessibility tree that aren't visible on screen

---

## NPU Detection

**Source**: [`jevon/perception/npu_detector.py`](../jevon/perception/npu_detector.py)

Implements an **honest 4-tier probe** with **zero fabricated NPU claims**:

```python
class NpuDetector:
    TIER_QUALCOMM_NPU = "QUALCOMM_HEXAGON_NPU"
    TIER_CPU_ONNX     = "CPU_ONNX"
    TIER_OS_SAPI      = "OS_SAPI"
    TIER_CLI_KEYBOARD  = "CLI_KEYBOARD"
```

### Detection Hierarchy

| Tier | What's Checked | Runtime |
|:---:|:---|:---|
| **1** | `importlib.util.find_spec("onnxruntime_qnn")` + Whisper bundle directory exists | Qualcomm Hexagon NPU |
| **2** | `importlib.util.find_spec("onnxruntime")` | Standard CPU ONNX Runtime |
| **3** | `sys.platform == "win32"` | Windows SAPI speech services |
| **4** | (fallback) | CLI keyboard input only |

**Truth-first guarantee**: If Tier 1 checks fail (no QNN runtime or no compiled models), the system honestly reports the actual tier — never fabricating NPU capability claims.

---

## Terminal Error Extraction

**Source**: [`jevon/perception/extractor.py`](../jevon/perception/extractor.py)

Parses terminal output to extract structured error information:

```python
class TerminalErrorExtractor:
    @staticmethod
    def extract_error(text: str) -> dict[str, Any]:
        # Returns: {"file": str, "line": int, "error_type": str, "message": str}
```

### Extraction Patterns

| Pattern | Matches | Example |
|:---|:---|:---|
| `File "([^"]+)", line (\d+)` | Python tracebacks | `File "calc.py", line 42` |
| `([A-Za-z_]+Error):\s*(.+)` | Error type + message | `SyntaxError: unexpected indent` |

---

## Speech-to-Text (STT)

### Whisper NPU Pipeline

**Source**: [`typesafe_computer_use/whisper_npu.py`](../typesafe_computer_use/whisper_npu.py)

5-tier backend priority for speech recognition:

| Priority | Backend | Hardware | Requirements |
|:---:|:---|:---|:---|
| 1 | ONNX GenAI + QNN EP | Snapdragon Hexagon NPU | `onnxruntime_qnn`, compiled models |
| 2 | ONNX GenAI + CPU EP | ARM64 / x86 CPU | `onnxruntime`, model files |
| 3 | Local REST server | Network | HTTP endpoint |
| 4 | Google Speech | Cloud | Internet connection |
| 5 | Windows SAPI | OS | Windows built-in |

### Model Search Paths

```
Custom:     $ARGUS_WHISPER_DIR
Android:    ~/models/whisper-small
            /data/local/tmp/models/whisper-small
Local:      ./models/whisper-small
Windows:    B:\projects\Qualcomm\whisper_bundle\whisper_small_quantized_onnx\...
            B:\projects\Qualcomm\whisper_bundle\distil_whisper_onnx\...
```

### Microphone Speech Recognition

**Source**: [`typesafe_computer_use/speech.py`](../typesafe_computer_use/speech.py)

```python
# Listen for voice input
goal = speech.listen(prompt="Speak your goal now...")

# FLAC encoding via ffmpeg (monkeypatched for performance)
# Falls back to built-in FLAC encoder if ffmpeg unavailable
```

---

## Text-to-Speech (TTS)

**Source**: [`typesafe_computer_use/speech.py`](../typesafe_computer_use/speech.py)

### Platform Support

| Platform | Engine | Implementation |
|:---|:---|:---|
| **Windows** | WinRT `SpeechSynthesizer` | Async via `winsdk`, runs in background thread |
| **Windows fallback** | SAPI `SpVoice` | COM-based, synchronous |
| **macOS** | `say` command | subprocess call |

### Usage

```python
from typesafe_computer_use import speech

# Speak text aloud
speech.speak("Test passed. 6 steps completed.", wait=True)

# Non-blocking speech
speech.speak("Starting analysis...", wait=False)
```

---

## SLM Decision Engine

**Source**: [`typesafe_computer_use/slm_decide.py`](../typesafe_computer_use/slm_decide.py) (734 lines)

On-device Small Language Model that replaces cloud inference for action classification:

### Model: Qwen 2.5 (0.5B Instruct, INT4 Quantized)

| Property | Value |
|:---|:---|
| Model | Qwen 2.5 0.5B-Instruct |
| Quantization | INT4 |
| Max Tokens | 150 |
| Target Latency | <800ms on Snapdragon 8 Elite |
| Output Format | Structured JSON |

### Backend Priority

| # | Backend | Check | Hardware |
|:---:|:---|:---|:---|
| 1 | `onnxruntime-genai` + QNN EP | `genai_config.json` in model dir | Hexagon NPU |
| 2 | `onnxruntime-genai` + CPU EP | `genai_config.json` in model dir | ARM64/x86 CPU |
| 3 | `llama-cpp-python` | `.gguf` file in model dir | Any CPU |
| 4 | Local REST server | HTTP endpoint at `localhost:11434` | Network |
| 5 | `decide_local()` heuristics | (always available) | Any |

### Model Search Paths

```
Android:  ~/models/qwen2.5-0.5b
          /data/local/tmp/models/qwen2.5-0.5b
          /sdcard/argus/models/qwen2.5-0.5b
Windows:  B:\projects\models\qwen2.5-0.5b
          ~/.cache/argus/models/qwen2.5-0.5b
Relative: ../models/qwen2.5-0.5b
```

### Output: `LocalChoiceAnswer`

Compatible with TypeSafe SDK's `ChoiceAnswer` interface:

```python
@dataclass(frozen=True)
class LocalChoiceAnswer:
    choice: str               # Selected action
    confidence: float         # Confidence score
    probabilities: dict       # Full probability distribution
```

---

## Voice Workflow

```
1. Developer speaks ──> Microphone captures audio
2. Audio ──> Whisper STT (NPU/CPU/REST)
3. Transcribed text ──> Goal string
4. Goal processed by Decision Engine
5. Action executed
6. Result ──> TTS speaks outcome aloud
```

### CLI Flags

```bash
clicker --voice --speak --act
# --voice: Listen to microphone for goal
# --speak: Speak actions and results via TTS
# --act:   Enable live execution
```

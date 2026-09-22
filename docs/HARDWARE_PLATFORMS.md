# Hardware & Platform Support

## Overview

JEVON supports multiple platforms through its platform adapter architecture, with specialized optimization for Qualcomm Snapdragon hardware.

---

## Support Matrix

| Platform | Subsystems | Acceleration | Status |
|:---|:---|:---|:---|
| **Windows 11 (x64)** | Win32 API, UIAutomation, WinRT OCR, `mss` | Direct3D / WinRT GPU OCR | ✅ Fully Supported |
| **Windows 11 (ARM64)** | Win32 API, UIAutomation, WinRT OCR, `mss` | Direct3D / WinRT GPU OCR | ✅ Fully Supported |
| **Qualcomm Snapdragon X (Copilot+)** | On-Device SLM (ONNX GenAI), Distil-Whisper | Hexagon NPU (45 TOPS) via QNN | 🧪 Experimental |
| **macOS (Apple Silicon)** | PyObjC, Quartz, Apple Vision OCR, AppleScript | Apple Neural Engine / Metal | ✅ Fully Supported |
| **macOS (Intel)** | PyObjC, Quartz, Apple Vision OCR, AppleScript | GPU OCR | ✅ Fully Supported |
| **Android (via ADB)** | ADB input, screencap, uiautomator dump | Host-side inference | ✅ Supported via Host |
| **iQOO 15** | On-device Qwen 2.5, Whisper, Office Kit | Snapdragon 8 Elite (Hexagon NPU 45+ TOPS) | 🎯 Target Device |
| **Linux** | Host controller for Android ADB | CPU inference | ⚠️ Partial |

---

## Windows 11 Details

### Screen Capture
- **Library**: `mss` (multi-monitor screenshot)
- **DPI Awareness**: Per-monitor DPI scaling with coordinate normalization
- **Multi-monitor**: Supports multiple displays with different DPI settings

### UIAutomation
- **Library**: `uiautomation` (COM-based)
- **Capabilities**: Tree traversal, control enumeration, focused field detection
- **Safety**: Depth limits to prevent infinite traversal, duplicate filtering

### Hardware OCR
- **Engine**: WinRT `Windows.Media.Ocr.OcrEngine`
- **Acceleration**: Direct3D GPU-accelerated
- **Optimization**: Tile-level change detection cache (`_TileCache`)
- **Latency**: ~150ms typical
- **Minimum OS**: Windows 10 build 1903+

### Synthetic Input
- **API**: Win32 `SendInput`
- **Types**: Mouse clicks, keyboard keystrokes, text input
- **Safety**: Emergency corner abort at (0,0) within 10px

### Speech
- **TTS**: WinRT `SpeechSynthesizer` (async) with SAPI fallback
- **STT**: Google Speech Recognition, Windows SAPI offline

---

## Qualcomm Snapdragon X (Copilot+ PCs)

### NPU Specifications
| Property | Value |
|:---|:---|
| **NPU** | Qualcomm Hexagon (45 TOPS) |
| **Runtime** | ONNX Runtime GenAI + QNN Execution Provider |
| **Target Models** | Qwen 2.5 (0.5B/1.5B), Distil-Whisper, Whisper-Small |

### Model Requirements
- Pre-compiled QNN model binaries matching the exact Hexagon driver version
- ONNX GenAI configuration file (`genai_config.json`)
- Quantized models (INT4/INT8) for optimal NPU performance

### Detection
The `NpuDetector` verifies NPU availability:
1. Checks for `onnxruntime_qnn` Python package
2. Verifies compiled model directory exists
3. Returns honest tier assessment (never fabricates NPU claims)

---

## macOS Details

### Accessibility
- **Framework**: PyObjC `AXUIElement`
- **Permissions**: Requires Accessibility permission in System Settings
- **Actions**: `AXPress`, `AXSetValue`, `AXFocus`

### Screen Capture
- **API**: `Quartz.CGWindowListCreateImage`
- **Resolution**: Retina-aware capture

### OCR
- **Framework**: Apple Vision via `ocrmac`
- **Minimum OS**: macOS 13+

### Automation
- **AppleScript**: App launching, browser control
- **Quartz Events**: Mouse/keyboard simulation

---

## Android (via ADB)

### Connection Methods
| Method | Setup |
|:---|:---|
| **USB** | `adb forward tcp:9876 tcp:9876` |
| **Wi-Fi** | `adb connect <phone-ip>:5555` |

### Capabilities

| Capability | ADB Command |
|:---|:---|
| Touch input | `adb shell input tap X Y` |
| Key events | `adb shell input keyevent KEYCODE` |
| Text input | `adb shell input text "string"` |
| Screen capture | `adb shell screencap -p` |
| UI hierarchy | `adb shell uiautomator dump` |
| App launch | `adb shell am start -n package/activity` |

### Activation
```bash
# Set target to Android
export ARGUS_TARGET=android
# or
clicker "open Settings" --act --target android
```

---

## iQOO 15 (Target Device)

### Specifications

| Component | Detail |
|:---|:---|
| **SoC** | Qualcomm Snapdragon 8 Elite Gen 5 |
| **NPU** | Hexagon NPU (45+ TOPS) |
| **OS** | OriginOS 6 (Android) |
| **Connectivity** | USB-C, 5GHz Wi-Fi, Office Kit |
| **Display** | 1080p 60fps (mirrored via Office Kit) |

### Role in Architecture
The iQOO 15 serves as the **Intelligence Center**:
- Runs on-device SLM (Qwen 2.5) on the Hexagon NPU
- Processes voice input via Whisper STT on NPU
- Manages Truth-First State ledger
- Makes decisions and dispatches commands to laptop via Office Kit Bridge

---

## AI Models & Inference Runtimes

| Task | Model | Runtime | Hardware Target |
|:---|:---|:---|:---|
| **Decision Intelligence** | Qwen 2.5 (0.5B/1.5B Instruct) | ONNX GenAI / llama-cpp-python | Snapdragon NPU / CPU |
| **Heuristic Fallback** | Deterministic FSM (`decide_local`) | Pure Python (0 parameters) | Any CPU |
| **Speech-to-Text** | Distil-Whisper / Whisper-Small | QNN EP / REST | Qualcomm NPU / CPU |
| **Text-to-Speech** | Windows Media Synthesis | Native `winsdk` COM | Windows Audio |
| **OCR Perception** | WinRT Hardware OCR | Windows Imaging API | GPU |

---

## Known Platform Issues

| Issue | Platform | Impact | Workaround |
|:---|:---|:---|:---|
| DPI coordinate drift | Windows (multi-monitor, mixed DPI) | Minor alignment offset | Use single DPI scale |
| NPU model compilation | Snapdragon X | Must match Hexagon driver | Use pre-compiled binaries |
| Canvas-rendered controls | All platforms | No accessibility nodes | Falls back to OCR bounding boxes |
| Python 3.13 wheels | All platforms | Some packages lack 3.13 wheels | Use Python 3.11 or 3.12 |

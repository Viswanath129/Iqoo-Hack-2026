# Setup Guide

## Prerequisites

| Requirement | Version | Notes |
|:---|:---|:---|
| **Python** | 3.11 or 3.12 | Python 3.13 not fully supported by binary wheels |
| **Package Manager** | `uv` (recommended) or `pip` | `uv` is significantly faster |
| **Operating System** | Windows 10/11, macOS 13+, or Linux | Linux acts as host controller for Android |
| **Git** | Latest | For cloning the repository |

---

## 1. Clone the Repository

```bash
git clone https://github.com/Viswanath129/Iqoo-Hack-2026.git
cd Iqoo-Hack-2026
```

---

## 2. Environment Setup

### Option A: Using `uv` (Recommended — Fastest)

```bash
# Create virtual environment with Python 3.11
uv venv --python 3.11

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies (editable mode)
uv pip install -e .
```

### Option B: Using Standard `pip`

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### Install Dev Dependencies

```bash
# With uv
uv pip install -e ".[dev]"

# Or install directly
pip install pytest==9.1.1 ruff==0.16.8
```

---

## 3. Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your optional API keys:
```env
TYPESAFE_API_KEY=your_typesafe_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

> **Note**: Both keys are **optional**. JEVON operates fully offline with `--local` mode.

---

## 4. Verify Installation

### Run Unit Tests
```bash
uv run pytest tests/ -q
```

Expected: **170 tests passed**

### Run E2E Tests
```bash
python e2e/runner.py --all
```

Expected: **226 tests passed** across 4 tiers

### Run Linter
```bash
uv run ruff check .
```

### Quick Dry Run
```bash
clicker "open calculator" 
```

---

## 5. (Optional) On-Device SLM Models

To enable zero-cloud SLM decision inference:

### Download GGUF Format
```bash
python hackathon/download_models.py --format gguf
```

### Download ONNX Format
```bash
python hackathon/download_models.py --format onnx
```

### Model Storage Locations

The downloader searches these paths:

| Platform | Path |
|:---|:---|
| Android | `~/models/qwen2.5-0.5b` |
| Android | `/data/local/tmp/models/qwen2.5-0.5b` |
| Windows | `B:\projects\models\qwen2.5-0.5b` |
| Cross-platform | `~/.cache/argus/models/qwen2.5-0.5b` |
| Relative | `./models/qwen2.5-0.5b` |

---

## 6. (Optional) Whisper STT Models

For on-device voice recognition:

### Model Paths

| Platform | Path |
|:---|:---|
| Custom | `$ARGUS_WHISPER_DIR` |
| Android | `~/models/whisper-small` |
| Local | `./models/whisper-small` |
| Snapdragon X | `B:\projects\Qualcomm\whisper_bundle\...` |

Required files in the model directory:
- `encoder.onnx`
- `decoder.onnx`

---

## 7. iQOO Office Kit Setup

### Installation
1. Download **iQOO Office Kit** from [pc.vivoglobal.com](https://pc.vivoglobal.com)
2. Install on your laptop

### Phone Pairing
1. Connect iQOO 15 phone via USB-C cable (or 5GHz Wi-Fi)
2. Accept the **"Trust this computer"** prompt on the phone
3. Grant Office Kit permissions
4. Launch Office Kit → click **"Phone Screen Mirroring"**

### Developer Testing View
- **Left 60%**: Office Kit window showing live phone mirror (1080p 60fps)
- **Right 40%**: Terminal showing real-time test logs

For detailed Office Kit setup, see [`hackathon/setup_officekit.md`](../hackathon/setup_officekit.md).

---

## 8. Android ADB Setup

For targeting Android devices:

```bash
# Verify ADB connection
adb devices

# Run with Android target
clicker "open Settings and tap Display" --act --target android
```

### Phone Setup Script
```bash
bash hackathon/setup_phone.sh
```

---

## 9. Platform-Specific Notes

### Windows
- UIAutomation requires the terminal to have accessibility permissions
- WinRT OCR requires Windows 10 build 1903+
- Multi-monitor DPI scaling may cause minor coordinate offsets

### macOS
- Grant Accessibility permission: System Settings → Privacy & Security → Accessibility
- Vision OCR requires macOS 13+

### Qualcomm Snapdragon X
- NPU acceleration requires Qualcomm AI Stack (QNN)
- Pre-compiled model binaries must match the Hexagon driver version
- Install `onnxruntime-qnn` for QNN Execution Provider

---

## Troubleshooting

| Issue | Solution |
|:---|:---|
| `ModuleNotFoundError: No module named 'winsdk'` | Run on Windows or use `--target android` |
| `No module named 'uiautomation'` | Install: `pip install uiautomation` |
| `TYPESAFE_API_KEY not set` | Use `--local` flag or add key to `.env` |
| `Accessibility permission denied` | Grant terminal accessibility in OS settings |
| `NPU not detected` | Expected — system honestly reports available tier |
| Tests fail on non-Windows | Some tests require Windows-specific modules |

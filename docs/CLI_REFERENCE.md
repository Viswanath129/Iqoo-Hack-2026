# CLI Reference

## Overview

JEVON provides two command-line utilities for desktop automation:
- **`clicker`** — Main automation engine
- **`clicker-inspect`** — Screen perception inspector

Both are registered as entry points in `pyproject.toml`.

---

## `clicker` — Main Automation CLI

### Synopsis

```bash
clicker [GOAL] [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|:---|:---|:---:|:---|
| `goal` | positional string | No* | What you want done on this computer |

*If omitted or empty, the system enters voice/keyboard input mode.

### Options

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--act` | flag | `False` | Enable live click/type execution (default: dry run) |
| `--steps N` | int | 30 | Maximum actions before stopping |
| `--min-confidence F` | float | 0.5 | Stop below this confidence threshold |
| `--delay F` | float | 1.0 | Seconds to wait after each action |
| `--out PATH` | path | `runs/<timestamp>` | Output folder for run artifacts |
| `--image PATH` | path | None | Replay a saved capture (never acts) |
| `--app NAME` | string | None | Frontmost app name for replay mode |
| `--url URL` | string | None | Browser URL for replay mode |
| `--voice` | flag | `False` | Listen to microphone for the goal |
| `--speak` | flag | `False` | Speak actions and results aloud via TTS |
| `--local` | flag | `False` | Force local on-device decision engine (no cloud API) |
| `--target` | choice | Auto-detect | Target platform: `android`, `windows`, `macos` |
| `--model` | choice | None | Decision engine: `slm`, `cloud`, `local` |

### Decision Engine Modes

| `--model` Value | Engine | Cloud Required |
|:---|:---|:---:|
| `local` | Keyword heuristic FSM (`decide_local`) | No |
| `slm` | On-device SLM (Qwen 2.5 ONNX/GGUF) | No |
| `cloud` | TypeSafe JEV classifier | Yes |
| *(default)* | Auto-select based on API key availability | Depends |

---

## Usage Examples

### 1. Dry Run / Inspection (Perceive Only)
```bash
clicker "open calculator and compute 42 * 2"
```
Inspects the active window, dumps accessibility hierarchy, highlights interactive elements — **no clicking or typing**.

### 2. Live Action Execution
```bash
clicker "open calculator and compute 42 * 2" --act
```
Enables native keyboard and mouse interaction. The system will actually click buttons and type text.

### 3. Fully Offline (Zero API Keys)
```bash
clicker "launch notepad and write build report" --act --local
```
Forces the local deterministic heuristic engine — no cloud API calls of any kind.

### 4. On-Device SLM Decision
```bash
clicker "search for error in terminal" --act --model slm
```
Routes decisions through the local Qwen 2.5 SLM (requires downloaded model).

### 5. Voice Control
```bash
clicker --voice --speak --act
```
Listens for voice commands via microphone (Whisper STT) and speaks results (TTS).

### 6. Windows Voice Batch Runner
```batch
run_voice.bat
```
Automated batch script that activates voice mode with speech feedback.

### 7. Target Android via ADB
```bash
clicker "open Settings and tap Display" --act --target android
```
Dispatches actions to a connected Android phone via ADB commands.

### 8. Custom Step Limit and Confidence
```bash
clicker "debug failing test" --act --steps 50 --min-confidence 0.7
```
Allows up to 50 steps and stops if confidence drops below 0.7.

### 9. Replay a Saved Capture
```bash
clicker "open calculator" --image runs/20260922-143000/raw.png --app Calculator
```
Uses a previously saved screenshot instead of live capture (never acts).

---

## `clicker-inspect` — Screen Inspector

### Synopsis

```bash
clicker-inspect [GOAL] [OPTIONS]
```

### Purpose

Captures the screen after a countdown, processes it through the full perception pipeline, and saves annotated results — without executing any actions.

### Options

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `goal` | positional | `"(no goal given)"` | Goal context for perception |
| `--countdown N` | int | 3 | Seconds to countdown before capture |
| `--no-open` | flag | `False` | Write files without opening them |
| `--out PATH` | path | `inspections/<timestamp>` | Output directory |

### Output Files

| File | Content |
|:---|:---|
| `raw.png` | Unmodified screenshot capture |
| `annotated.png` | Screenshot with indexed interactive elements highlighted |
| `state.txt` | Full perception state: items, controls, offscreen nodes |

### Example

```bash
# Inspect with 5-second countdown
clicker-inspect "find the search button" --countdown 5

# Output without auto-opening files
clicker-inspect "check calculator state" --no-open --out inspections/calc-test
```

### Output

```
app='Calculator' url='' items=12 ax=8 offscreen=3 field=None
  capture: 45.2ms  ocr: 148.6ms  ax: 52.3ms  merge: 12.1ms
  inspections/20260922-143500/annotated.png
  inspections/20260922-143500/state.txt
```

---

## Environment Variables

| Variable | Required | Purpose |
|:---|:---:|:---|
| `TYPESAFE_API_KEY` | No | Enables TypeSafe cloud classifier (Mode B/C) |
| `ANTHROPIC_API_KEY` | No | Enables Claude writer for free-text composition |
| `ARGUS_TARGET` | No | Override target platform (`android`, `windows`, `macos`) |
| `ARGUS_WHISPER_DIR` | No | Custom Whisper model directory path |

### `.env` File

Create a `.env` file in the project root (see `.env.example`):
```env
TYPESAFE_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

---

## Exit Codes

| Code | Meaning |
|:---:|:---|
| 0 | Success — task completed |
| 1 | Error — task failed or aborted |
| 130 | Aborted — user interrupt or emergency stop |

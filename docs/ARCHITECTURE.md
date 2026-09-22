# System Architecture

## Overview

JEVON is architected as a **4-layer, dual-device system** separating intelligence (phone) from execution (laptop), connected by a latency-instrumented Office Kit Bridge.

---

## The Core Control Loop

Traditional developer AI assistants follow a broken open-loop pattern:

```
Developer Intent  ──>  LLM (Cloud)  ──>  Generated Text / Code Snippet
                             ▲                       │
                             │ (Manual copy-paste)   │
                             └───────────────────────┘
```

JEVON replaces this with a **deterministic closed-loop**:

```
Developer Intent
       │
       ▼
   Perceive ──> Structured Decision ──> Deterministic Action ──> Observe ──> Verify
       ▲                                                                       │
       └───────────────────────── Next Decision ───────────────────────────────┘
```

---

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Input ["1. Developer Intent"]
        VOICE["Voice Command (Microphone)"]
        CLI_ARG["CLI Command Line"]
    end

    subgraph Perception ["2. Perception Engine"]
        STT["Whisper STT (Hexagon NPU / CPU)"]
        UIA["Accessibility Tree (Win32 UIA / macOS AX / Android)"]
        OCR["Hardware OCR (WinRT / Apple Vision)"]
        SCREEN["DPI-Aware Capture (mss)"]
    end

    subgraph DecisionCore ["3. Decision Core"]
        SLM["On-Device SLM (Qwen2.5 ONNX / GGUF)"]
        LOCAL_FSM["Zero-Cloud Rule Heuristic"]
        CLOUD_JEV["Optional TypeSafe JEV Provider"]
        SAFETY_FB["Safety Fallback (< 0.60 Conf / Loops)"]
        LEDGER["7-Pillar Truth-First State Ledger"]
    end

    subgraph Execution ["4. Deterministic Executor"]
        WIN_EXEC["Windows (Win32 SendInput & UIA)"]
        MAC_EXEC["macOS (AppleScript & Quartz)"]
        AND_EXEC["Android (ADB Shell Input & Keyevents)"]
        SUBPROC["Isolated Subprocess Runner"]
    end

    subgraph Safety ["Safety Layer"]
        CORNER["Emergency Mouse Corner Abort (0,0)"]
        TIMEOUT["Step Timeouts (30s)"]
        ALLOW["Command & Path Allowlist"]
    end

    subgraph Verification ["5. Verification & Feedback"]
        VERIF["Independent Verifier (Exit Code / Regex / AST)"]
        TTS["On-Device TTS Feedback (WinRT / SAPI / macOS)"]
    end

    VOICE --> STT --> Perception
    CLI_ARG --> Perception
    Perception --> DecisionCore
    DecisionCore --> Safety --> Execution
    Execution --> Verification
    Verification -->|"Updated State & Facts"| LEDGER
    LEDGER -->|"Next Step"| DecisionCore
    Verification --> TTS
```

---

## Architectural Layers

### Layer 1 — Developer Intent

The system accepts input via two channels:

- **CLI argument**: Direct text goal (`clicker "open calculator and compute 42 * 2"`)
- **Voice command**: Microphone capture → Whisper STT → transcribed goal

### Layer 2 — Perception Engine

Captures the current state of the developer environment:

| Component | Technology | Platform |
| :--- | :--- | :--- |
| Screen Capture | `mss` with per-monitor DPI scaling | Windows |
| UIAutomation Tree | COM-based UIA tree traversal | Windows |
| Hardware OCR | WinRT OCR with tile-level change cache | Windows |
| Accessibility API | PyObjC `AXUIElement` | macOS |
| Vision OCR | Apple Vision framework | macOS |
| UI Hierarchy | `uiautomator dump` | Android |

### Layer 3 — Decision Core

Evaluates perception data and selects the next action:

| Provider | Type | Cloud Requirement |
| :--- | :--- | :--- |
| `LocalDecisionProvider` | 7-rule deterministic FSM | **Zero** — fully offline |
| `TypeSafeJevProvider` | Cloud classifier + local fallback | Optional API key |
| `SafetyFallback` | Decorator wrapping any provider | None |
| On-device SLM | Qwen 2.5 (0.5B) via ONNX/GGUF | None |

### Layer 4 — Deterministic Executor

Executes the chosen action via native OS APIs:

| Platform | Input Method | Process Execution |
| :--- | :--- | :--- |
| Windows | Win32 `SendInput` + UIAutomation | `subprocess.run()` |
| macOS | AppleScript + Quartz Events | `subprocess.run()` |
| Android | ADB `input tap/text/keyevent` | ADB shell |

### Layer 5 — Verification & Feedback

Validates action outcomes independently:

- Exit code verification (0 = success)
- Regex pattern matching on output
- AST syntax validation (Python)
- Error elimination confirmation
- TTS audio feedback to developer

---

## Dual-Device Separation

The system is explicitly separated into two devices connected by the OfficeKitBridge:

```mermaid
flowchart LR
    subgraph Phone ["iQOO Phone (Intelligence Center)"]
        P_PERC["Perception & Voice"]
        P_DEC["Decision Engine"]
        P_STATE["Truth-First Ledger"]
    end

    subgraph Bridge ["OfficeKitBridge"]
        B_ADB["ADB USB Tunnel"]
        B_SOCK["TCP Socket"]
        B_IPC["Local IPC"]
    end

    subgraph Laptop ["Laptop (Execution)"]
        L_EXEC["Action Executor"]
        L_SAFE["Safety Gate"]
        L_VERIF["Verification Engine"]
    end

    Phone -->|"DecisionCommand"| Bridge
    Bridge -->|"DecisionCommand"| Laptop
    Laptop -->|"ActionReceipt"| Bridge
    Bridge -->|"ActionReceipt"| Phone
    Laptop -->|"StateObservation"| Bridge
    Bridge -->|"StateObservation"| Phone
```

| Role | Device | Responsibilities |
| :--- | :--- | :--- |
| **Intelligence Center** | iQOO Phone / Android | Perception, voice, SLM inference, Truth-First state, decision making |
| **Communication Bridge** | OfficeKitBridge | Bi-directional telemetry exchange with latency instrumentation |
| **Execution Environment** | Windows / ARM64 Laptop | Native OS automation, subprocess execution, independent verification |
| **Standalone Mode** | Single Machine | Both roles via in-memory IPC transport (for CI/CD and testing) |

---

## The 6-Step State Machine

Every cycle follows a strict sequence:

```
 1. SENSE SCREEN ───────> mss raster capture + UIAutomation XML + WinRT OCR
         │
         ▼
 2. BUILD PROMPT ───────> Index interactive controls [0..N], active focus, recent history
         │
         ▼
 3. SELECT ACTION ──────> SLM / Local FSM outputs typed action, target item, & confidence
         │
         ▼
 4. SAFETY CHECK ───────> Verify coordinates != (0,0), action in allowlist, step < 100
         │
         ▼
 5. EXECUTE ────────────> Native Win32 SendInput / ADB input tap / Shell subprocess
         │
         ▼
 6. VERIFY & RECORD ────> Evaluate exit code, regex matching, log to 7-pillar ledger
```

---

## Dual-Device Sequence Diagram

Every developer interaction runs as an instrumented, asynchronous closed-loop cycle across the **iQOO Office Kit Bridge**:

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 👨‍💻 Developer
    participant Phone as 📱 iQOO 15 (Edge Brain)
    participant Bridge as 🌉 OfficeKitBridge
    participant Laptop as 💻 Workstation (Execution)
    participant Verifier as ✅ VerificationEngine

    Note over Dev,Phone: Phase 1: Intent Ingestion (Voice STT / CLI)
    Dev->>Phone: 1. Voice Command / CLI Goal [182 ms STT]
    
    loop Autonomous Closed-Loop Cycle (Max 100 Steps)
        Note over Laptop,Phone: Phase 2: State Perception & Telemetry Ingestion
        Laptop->>Bridge: 2. StateObservation (mss raster + UIA tree + OCR) [148.5 ms]
        Bridge->>Phone: 3. Dispatch StateObservation via TCP/ADB [1.5 ms]
        
        Note over Phone: Phase 3: Edge Decision & Audit Ledger Commit
        Phone->>Phone: 4. DecisionProvider.decide() [FSM 12.4 ms / SLM 180 ms]
        Phone->>Phone: 5. Append Decision to 7-Pillar Truth Ledger [3.2 ms]
        Phone->>Bridge: 6. send_command(DecisionCommand) [1.5 ms]
        Bridge->>Laptop: 7. Deliver DecisionCommand to Workstation
        
        Note over Laptop,Verifier: Phase 4: Guarded Execution & Independent Verification
        Laptop->>Laptop: 8. SafetyGate.is_destructive() & Corner Abort (0,0) [0.6 ms]
        
        alt Destructive & Unconfirmed Operation
            Laptop-->>Bridge: 9a. BLOCKED_BY_SAFETY Receipt (Requires Developer Approval)
            Bridge-->>Phone: Deliver Blocked Receipt ➔ Trigger Human Confirmation
        else Safe or Confirmed Action
            Laptop->>Laptop: 9b. LaptopActionExecutor.execute() [Win32 / Quartz / ADB] [185 ms]
            Laptop->>Verifier: 10. verify(exit_code, stdout, stderr, ast_diff) [62.1 ms]
            Verifier-->>Laptop: 11. VerificationOutcome (Success / Failure Signature)
            Laptop->>Bridge: 12. send_receipt(ActionReceipt) [1.5 ms]
        end
        
        Bridge->>Phone: 13. Deliver ActionReceipt to Phone
        Phone->>Phone: 14. Update Ledger Facts, Hash Signatures & Check Loop Breaker [3.2 ms]
        
        alt Action == DONE (Verification Succeeded)
            Note over Phone,Dev: Phase 5: Voice Audio Feedback & Completion
            Phone-->>Dev: 15. Spoken Task Confirmation (On-Device WinRT / SAPI TTS)
        end
    end
```

### Telemetry Message Trace

| Step | Telemetry Frame / Event | Channel & Direction | Payload / Operation | Latency Budget | Guardrail / Fallback |
| :---: | :--- | :---: | :--- | :---: | :--- |
| **1** | **Developer Intent** | Workstation / Mic ➔ Phone | Raw PCM audio stream or CLI argument string | **182 ms** | Qualcomm Hexagon NPU Whisper model |
| **2–3** | **`StateObservation`** | Laptop ➔ Bridge ➔ Phone | Screen PNG, active UIA control tree, error trace | **~150 ms** | Direct3D 12 WinRT OCR tile-cache |
| **4** | **Edge Decision** | Phone (Local Inference) | Evaluates 7-rule FSM or Qwen 2.5 SLM (ONNX/GGUF) | **12.4 ms** | Confidence floor $p \ge 0.60$ fallback |
| **5** | **Audit State Commit** | Phone (Truth Ledger) | Appends typed decision + probabilities to ledger | **3.2 ms** | Append-only immutable history |
| **6–7** | **`DecisionCommand`** | Phone ➔ Bridge ➔ Laptop | Typed action, target coordinates/file, parameters | **~1.5 ms** | Transport auto-reconnect retry queue |
| **8** | **Safety Gate Check** | Laptop (Pre-Execution) | Checks mouse pointer $\ne (0,0)$, step count $< 100$ | **0.6 ms** | Immediate hardware interrupt on corner abort |
| **9** | **Deterministic Action** | Laptop ➔ Target OS | Win32 `SendInput`, macOS Quartz, or ADB keyevents | **185.0 ms** | 30-second isolated subprocess ceiling |
| **10–11**| **Objective Verification** | Laptop ➔ Verification Engine | Checks exit code $== 0$, stdout regex, AST diff | **62.1 ms** | Zero self-certification rule |
| **12–13**| **`ActionReceipt`** | Laptop ➔ Bridge ➔ Phone | Execution status, stdout/stderr, verification flag | **~1.5 ms** | Marshaled over USB tunnel or TCP socket |
| **14** | **Ledger Fact Update** | Phone (Truth Ledger) | Records output, computes 16-char SHA-256 error hash | **3.2 ms** | Oscillation loop detection breaker |
| **15** | **Audio TTS Feedback** | Phone ➔ Developer | Local speech synthesizer emits audible confirmation | **Async** | Spoken task completion without context-switching |

---

## Design Principles

1. **Bounded Action Space**: Exactly 8 mutually exclusive actions — prevents infinite text generation
2. **Deterministic Execution**: Every action maps to a concrete OS operation — no ambiguity
3. **Independent Verification**: Never self-certify — always validate via exit codes, regex, AST
4. **Safety-First**: 7 layers of protection from hardware abort to policy allowlists
5. **Truth-First Auditing**: Immutable 7-pillar ledger — every decision, fact, and failure recorded
6. **Zero-Cloud Default**: Full functionality with 0 API keys — cloud is optional escalation
7. **Platform Abstraction**: Single interface, multiple OS backends (Windows/macOS/Android)
8. **Latency Instrumentation**: Nanosecond-precision timing on every pipeline stage

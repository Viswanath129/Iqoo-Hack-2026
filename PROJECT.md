# Project: JEVON (On-Device Developer Decision Engine)

## Architecture
JEVON transforms `viswa_jav` into an on-device developer decision-and-execution layer for the iQOO Hackathon 2026 Developer Tools track.
The system is separated into:
1. **On-Device Intelligence Center (iQOO Phone / Android Layer & Local Emulation)**:
   - Perception & Voice: Local Whisper STT (with Qualcomm Snapdragon NPU acceleration where runtime-supported), TTS feedback, terminal/code error extraction.
   - Truth-First State Engine: 7-pillar append-only state tracking (`GOAL`, `CONSTRAINTS`, `FACTS`, `DECISIONS`, `EVIDENCE`, `OPEN_QUESTIONS`, `FAILED_APPROACHES`).
   - Decision Engine: Pluggable `DecisionProvider` interface featuring `LocalDecisionProvider` (100% offline, zero cloud API keys, rule-based FSM + on-device SLM), optional `TypeSafeJevProvider`, and `SafetyFallback`. Bounded $\le 8$ mutually exclusive developer actions with typed probability distributions summing to 1.0.
2. **Dual-Device Communication Layer (`OfficeKitBridge`)**:
   - Bi-directional latency-instrumented bridge layer supporting:
     - ADB USB Port Forwarding (`AdbTunnelTransport`)
     - Office Kit TCP streaming socket (`SocketTransport`) with binary framing
     - Local IPC fallback (`IpcTransport`) for standalone single-machine execution, CI/CD, and reproducible testing.
   - Strongly-typed telemetry frames: `StateObservation`, `DecisionCommand`, `ActionReceipt`.
3. **Laptop Execution & Verification Layer (Windows / ARM64 Developer Machine)**:
   - Deterministic Laptop Action Execution (`LaptopActionExecutor` adapting `windows.py` and `actions.py`): Win32 input, UIA, subprocess isolation, emergency mouse-corner stop (`ABORT_CORNER_PX = 10`), 30s timeout, allowlist, and `SafetyGate` blocking destructive actions (`git reset --hard`, file deletion, credential access).
   - Independent Verification Engine (`VerificationEngine` in `verification/`): Validates developer actions without self-certification (compiler exit code, regex matching, AST validation, git status, error elimination).
4. **Real-Time Telemetry & Comparative Benchmarks**:
   - Micro-benchmarks capturing latency at all 7 pipeline stages.
   - Comparative benchmark CLI contrasting Mode A (Local-Only), Mode B (Cloud Baseline), and Mode C (Hybrid) with empirical tables and cost metrics ($0.00 local vs cloud).

---

## Feature Inventory
Every requirement from `ORIGINAL_REQUEST.md` (R1-R6) is inventoried and mapped to an implementation milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | DecisionProvider Interface | Pluggable abstraction for decision providers | M1 | R1 |
| 2 | Bounded Action Space | Bounded $\le 8$ mutually exclusive developer actions (`inspect_error`, `inspect_file`, `run_targeted_test`, `rerun_build`, `inspect_recent_change`, `apply_fix`, `request_confirmation`, `done`) | M1 | R1 |
| 3 | LocalDecisionProvider | Offline decision engine operating with zero cloud API keys (rule FSM + SLM) | M1 | R1 |
| 4 | TypeSafeJevProvider | Optional cloud-assisted decision provider | M1 | R1 |
| 5 | SafetyFallback | Deterministic fallback intercepting low confidence (<0.60) or oscillation loops | M1 | R1 |
| 6 | Typed Decisions | `Decision` output with typed confidence and normalized probability distribution | M1 | R1 |
| 7 | Truth-First State Model | 7-pillar state tracking (`GOAL`, `CONSTRAINTS`, `FACTS`, `DECISIONS`, `EVIDENCE`, `OPEN_QUESTIONS`, `FAILED_APPROACHES`) | M1 | R3 |
| 8 | Bridge Telemetry Schema | Strict schemas for `StateObservation`, `DecisionCommand`, and `ActionReceipt` | M2 | R2 |
| 9 | OfficeKitBridge Core | Bi-directional latency-instrumented communication bridge | M2 | R2 |
| 10 | Tri-Transport Layer | Support for ADB USB tunnel, Office Kit TCP socket, and Local IPC fallback | M2 | R2 |
| 11 | LaptopActionExecutor | Deterministic laptop execution adapting `windows.py` and `actions.py` | M3 | R4 |
| 12 | Safety Failsafes | Mouse-corner stop (10px), step timeouts (30s), action allowlist, loop detection | M3 | R4 |
| 13 | SafetyGate Destructive Blocker | Blocks `git reset --hard`, file deletion, `.env`/credential access until confirmed | M3 | R4 |
| 14 | Independent VerificationEngine | Validates actions without self-certification (compiler exit code, regex, AST, git diff) | M3 | R5 |
| 15 | Closed-Loop Orchestrator | `STATE -> DECISION -> ACTION -> OBSERVATION -> VERIFICATION -> NEXT STATE` | M3 | R5 |
| 16 | Honest NPU Runtime Detection | 4-tier probe (Hexagon NPU -> CPU ONNX -> OS SAPI -> CLI), zero false NPU claims | M4 | R3 |
| 17 | Whisper STT Pipeline | On-device Whisper STT with Snapdragon NPU acceleration where runtime-supported | M4 | R3 |
| 18 | TTS Feedback & Terminal Parser | On-device TTS audio feedback and terminal/compiler error snippet state extraction | M4 | R3 |
| 19 | Micro-Benchmark Instrumenter | Nanosecond-precision stopwatch capturing all 7 loop stages | M5 | R6 |
| 20 | Comparative Benchmark Suite | Benchmark CLI comparing Local-Only (A), Cloud Baseline (B), Hybrid (C) | M5 | R6 |
| 21 | Existing Test Preservation | Zero regression across all 170 existing unit tests | M1-M5, Final | AC Line 53 |
| 22 | 100% E2E Test Pass (Tiers 1-4) | Complete pass of all opaque-box E2E test tiers | Final M6 | Dual Track |
| 23 | Adversarial Coverage Hardening | Tier 5 adversarial stress testing, boundary hardening, zero integrity violations | Final M6 | Dual Track |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Decision Engine & Truth-First State | `jevon/decision/` (`DecisionProvider`, `LocalDecisionProvider`, `TypeSafeJevProvider`, `SafetyFallback`, 8 actions, probability distribution) and `jevon/truth_first/` (7-pillar ledger) | none | IN_PROGRESS |
| M2 | OfficeKitBridge & Dual-Device Telemetry | `jevon/bridge/` (`OfficeKitBridge`, `AdbTunnelTransport`, `SocketTransport`, `IpcTransport`, `StateObservation`, `DecisionCommand`, `ActionReceipt`) | M1 | PLANNED |
| M3 | Laptop Action Execution & Verification Engine | `jevon/execution/` (`LaptopActionExecutor`, failsafe bounds, mouse corner, `SafetyGate`) and `jevon/verification/` (`VerificationEngine`, regex, exit code, AST, git diff) + closed loop | M1, M2 | PLANNED |
| M4 | On-Device Perception & Voice Pipeline | `jevon/perception/` (`npu_detector.py`, Whisper STT, TTS audio, terminal error parser) | M1 | PLANNED |
| M5 | Real-Time Telemetry & Benchmark CLI Suite | `jevon/telemetry/` (nanosecond micro-benchmarks, comparative CLI suite: Mode A, Mode B, Mode C, markdown tables) | M1, M2, M3 | PLANNED |
| M6 | Final Milestone: E2E Integration & Adversarial Hardening | Phase 1: 100% pass of E2E test suite (Tiers 1-4). Phase 2: Tier 5 adversarial coverage hardening with Challengers. | M1, M2, M3, M4, M5, TEST_READY | PLANNED |

---

## Dual Track: E2E Testing Track
Runs in parallel with Implementation Track:
- **E2E Testing Orchestrator** creates test runner and comprehensive test suite across Tiers 1-4 covering all 23 features in the Feature Inventory.
- Publishes `TEST_READY.md` upon completion.
- Passes pass/fail criteria to Implementation Track's Final Milestone.

---

## Interface Contracts

### 1. `StateObservation` (Laptop -> Phone)
```python
@dataclass(frozen=True)
class StateObservation:
    session_id: str
    step_index: int
    timestamp_ns: int
    working_directory: str
    active_file: str | None
    terminal_output: str
    compiler_exit_code: int | None
    git_status_summary: str
    recent_error: str | None
    metadata: dict[str, Any]
```

### 2. `DecisionCommand` (Phone -> Laptop)
```python
@dataclass(frozen=True)
class DecisionCommand:
    command_id: str
    session_id: str
    step_index: int
    timestamp_ns: int
    action: DeveloperAction  # 1 of 8 bounded actions
    confidence: float        # max(probabilities)
    probabilities: dict[str, float]  # all 8 actions summing to 1.0
    parameters: dict[str, Any]       # e.g., target_test, target_file, fix_patch
    requires_confirmation: bool
```

### 3. `ActionReceipt` (Laptop -> Phone)
```python
@dataclass(frozen=True)
class ActionReceipt:
    command_id: str
    session_id: str
    step_index: int
    action: DeveloperAction
    status: str              # "SUCCESS", "FAILED", "BLOCKED_BY_SAFETY", "ABORTED"
    exit_code: int
    stdout: str
    stderr: str
    verification_passed: bool
    verification_details: dict[str, Any]
    duration_ns: int
    timestamp_ns: int
```

### 4. `DecisionProvider` Interface
```python
class DecisionProvider(ABC):
    @abstractmethod
    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        """Returns DeveloperDecision with action, confidence, and normalized probabilities."""
        pass
```

### 5. `VerificationEngine` Interface
```python
class VerificationEngine(ABC):
    @abstractmethod
    def verify(self, action: DeveloperAction, params: dict[str, Any], exec_result: ExecutionResult) -> VerificationOutcome:
        """Performs objective, independent verification without self-certification."""
        pass
```

---

## Code Layout
```
B:\projects\viswa_jav\
├── jevon/                                # Dedicated JEVON implementation package
│   ├── __init__.py
│   ├── decision/                         # R1: Core Decision Engine & Action Space
│   │   ├── __init__.py
│   │   ├── actions.py                    # 8 bounded developer actions & Decision types
│   │   ├── provider.py                   # DecisionProvider base interface
│   │   ├── local_provider.py             # Offline LocalDecisionProvider (FSM + SLM)
│   │   ├── jev_provider.py               # TypeSafeJevProvider (Cloud fallback)
│   │   └── safety_fallback.py            # SafetyFallback wrapper
│   ├── truth_first/                      # R3 part: Truth-First State Model
│   │   ├── __init__.py
│   │   └── state.py                      # 7-pillar state tracking ledger
│   ├── bridge/                           # R2: Dual-Device OfficeKitBridge
│   │   ├── __init__.py
│   │   ├── protocol.py                   # StateObservation, DecisionCommand, ActionReceipt
│   │   ├── bridge.py                     # OfficeKitBridge core
│   │   └── transports.py                 # AdbTunnelTransport, SocketTransport, IpcTransport
│   ├── execution/                        # R4: Deterministic Laptop Execution
│   │   ├── __init__.py
│   │   ├── executor.py                   # LaptopActionExecutor adapting windows.py / actions.py
│   │   ├── safety_gate.py                # SafetyGate for destructive operation blocking
│   │   └── allowlist.py                  # Allowed commands and paths
│   ├── verification/                     # R5: Objective Independent Verification
│   │   ├── __init__.py
│   │   ├── engine.py                     # VerificationEngine
│   │   └── checkers.py                   # ExitCode, Regex, AST, GitStatus, ErrorElimination
│   ├── perception/                       # R3: On-Device AI Perception & Voice
│   │   ├── __init__.py
│   │   ├── npu_detector.py               # Honest 4-tier NPU detection hierarchy
│   │   ├── voice.py                      # Whisper STT & TTS feedback
│   │   └── extractor.py                  # Terminal & code snippet state extraction
│   ├── telemetry/                        # R6: Real-Time Micro-Benchmarks
│   │   ├── __init__.py
│   │   ├── metrics.py                    # Nanosecond stopwatch & latency records
│   │   └── benchmark.py                  # Comparative Benchmark CLI (Modes A, B, C)
│   └── loop.py                           # Full Closed-Loop Orchestrator
├── tests/                                # Existing 170 unit tests (DO NOT REGRESS)
├── e2e/                                  # Opaque-box E2E test suite (Tiers 1-5)
│   ├── runner.py                         # E2E test harness
│   ├── tier1_feature/                    # Tier 1: Feature Coverage (>=5 per feature)
│   ├── tier2_boundary/                   # Tier 2: Boundary & Corner Cases (>=5 per feature)
│   ├── tier3_combination/                # Tier 3: Cross-Feature Combinations
│   ├── tier4_application/                # Tier 4: Real-World Build/Test/Debug Scenarios
│   └── tier5_adversarial/                # Tier 5: Adversarial Stress Tests
├── pyproject.toml
├── PROJECT.md
├── TEST_INFRA.md
└── TEST_READY.md                         # Published when E2E Testing Track completes
```

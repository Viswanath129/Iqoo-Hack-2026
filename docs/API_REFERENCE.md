# API Reference

## Overview

This document defines all public data contracts, interface definitions, and serialization schemas used throughout JEVON.

---

## Interface Contracts

### 1. `DecisionProvider` (Abstract Base Class)

```python
from jevon.decision.provider import DecisionProvider

class DecisionProvider(ABC):
    @property
    def name(self) -> str:
        """Human-readable provider identification."""

    def is_available(self) -> bool:
        """Return True if the backend is initialized and operational."""

    @abstractmethod
    def decide(
        self,
        state: TruthFirstState,
        observation: StateObservation
    ) -> DeveloperDecision:
        """Evaluate developer state and return a typed DeveloperDecision.
        
        The decision must specify an action from the bounded 8-action set,
        a confidence score in [0.0, 1.0], and normalized probabilities
        summing to 1.0.
        """
```

**Implementations**: `LocalDecisionProvider`, `TypeSafeJevProvider`, `SafetyFallback`

---

### 2. `BridgeTransport` (Abstract Base Class)

```python
from jevon.bridge.transports import BridgeTransport

class BridgeTransport(ABC):
    @abstractmethod
    def connect(self) -> bool: ...
    
    @abstractmethod
    def disconnect(self) -> None: ...
    
    @abstractmethod
    def is_connected(self) -> bool: ...
    
    @abstractmethod
    def send(self, data: bytes) -> None: ...
    
    @abstractmethod
    def receive(self, timeout_s: float = 5.0) -> bytes: ...
```

**Implementations**: `IpcTransport`, `SocketTransport`, `AdbTunnelTransport`

---

## Data Contracts

### 3. `DeveloperAction` (StrEnum)

```python
from jevon.decision.actions import DeveloperAction

class DeveloperAction(StrEnum):
    INSPECT_ERROR = "inspect_error"
    INSPECT_FILE = "inspect_file"
    RUN_TARGETED_TEST = "run_targeted_test"
    RERUN_BUILD = "rerun_build"
    INSPECT_RECENT_CHANGE = "inspect_recent_change"
    APPLY_FIX = "apply_fix"
    REQUEST_CONFIRMATION = "request_confirmation"
    DONE = "done"
```

**Methods**: `all_actions()`, `is_terminal`, `__str__`

---

### 4. `DeveloperDecision` (Dataclass)

```python
from jevon.decision.actions import DeveloperDecision

@dataclass
class DeveloperDecision:
    action: DeveloperAction          # One of 8 bounded actions
    confidence: float                # [0.0, 1.0]
    probabilities: dict[str, float]  # All 8 actions, sum = 1.0
    parameters: dict[str, Any]       # Action-specific params
    metadata: dict[str, Any]         # Diagnostic audit data
```

**Properties**: `is_terminal`, `requires_confirmation`  
**Serialization**: `to_dict()`, `from_dict()`, `to_json()`, `from_json()`

---

### 5. `StateObservation` (Frozen Dataclass)

```python
from jevon.decision.provider import StateObservation

@dataclass(frozen=True)
class StateObservation:
    session_id: str = ""
    step_index: int = 0
    timestamp_ns: int = time.time_ns()
    working_directory: str = ""
    active_file: str | None = None
    terminal_output: str = ""
    compiler_exit_code: int | None = None
    git_status_summary: str = ""
    recent_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Serialization**: `to_dict()`, `from_dict()`

---

### 6. `DecisionCommand` (Frozen Dataclass)

```python
from jevon.bridge.protocol import DecisionCommand

@dataclass(frozen=True)
class DecisionCommand:
    command_id: str
    session_id: str
    step_index: int
    timestamp_ns: int
    action: DeveloperAction
    confidence: float                # [0.0, 1.0]
    probabilities: dict[str, float]
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
```

**Validation**: Action must be in bounded set, confidence in [0.0, 1.0]  
**Serialization**: `to_dict()`, `from_dict()`, `to_json()`, `from_json()`

---

### 7. `ActionReceipt` (Frozen Dataclass)

```python
from jevon.bridge.protocol import ActionReceipt

@dataclass(frozen=True)
class ActionReceipt:
    command_id: str
    session_id: str
    step_index: int
    action: DeveloperAction
    status: str                      # "SUCCESS"|"FAILED"|"BLOCKED_BY_SAFETY"|"ABORTED"
    exit_code: int
    stdout: str
    stderr: str
    verification_passed: bool
    verification_details: dict[str, Any] = field(default_factory=dict)
    duration_ns: int = 0
    timestamp_ns: int = time.time_ns()
```

**Serialization**: `to_dict()`, `from_dict()`, `to_json()`, `from_json()`

---

### 8. `TruthFirstState` (Dataclass)

```python
from jevon.truth_first.state import TruthFirstState

@dataclass
class TruthFirstState:
    goal: str = ""
    constraints: list[str]
    facts: list[str]
    decisions: list[dict[str, Any]]
    evidence: list[str]
    open_questions: list[str]
    failed_approaches: list[dict[str, Any]]
    cycle_index: int = 0
    session_id: str = ""
    timestamp_utc: float
    failure_signatures: list[str]
    metadata: dict[str, Any]
```

**Methods**: `set_goal()`, `add_constraint()`, `add_fact()`, `record_decision()`, `add_evidence()`, `add_open_question()`, `resolve_open_question()`, `add_failed_approach()`, `record_failure_signature()`, `detect_repeated_failure()`, `detect_oscillation()`, `format_audit_log()`  
**Serialization**: `to_dict()`, `from_dict()`, `to_json()`, `from_json()`

---

### 9. `VerificationOutcome` (Dataclass)

```python
from jevon.verification.engine import VerificationOutcome

@dataclass
class VerificationOutcome:
    passed: bool                     # all(checks.values())
    checks: dict[str, bool]          # Per-check results
    details: dict[str, Any]          # Additional details
```

---

### 10. `MicroBenchmarkMetrics` (Dataclass)

```python
from jevon.telemetry.metrics import MicroBenchmarkMetrics

@dataclass
class MicroBenchmarkMetrics:
    perception_ns: int = 0
    local_inference_ns: int = 0
    decision_ns: int = 0
    bridge_out_ns: int = 0
    action_exec_ns: int = 0
    verification_ns: int = 0
    bridge_in_ns: int = 0
```

**Properties**: `total_latency_ns`, `total_latency_ms`

---

### 11. `LoopResult` (Dataclass)

```python
from jevon.loop import LoopResult

@dataclass
class LoopResult:
    session_id: str
    total_steps: int
    final_action: DeveloperAction
    success: bool
    state: TruthFirstState
    metrics: list[MicroBenchmarkMetrics]
    receipts: list[ActionReceipt]
```

---

## Utility Functions

### `normalize_probabilities()`

```python
from jevon.decision.actions import normalize_probabilities

def normalize_probabilities(
    probs: dict[str | DeveloperAction, float]
) -> dict[str, float]:
    """Normalize probability distribution across all 8 actions to sum to 1.0."""
```

### `compute_failure_signature()`

```python
from jevon.truth_first.state import compute_failure_signature

def compute_failure_signature(
    exit_code: int | None,
    culprit_file: str | None,
    error_summary: str | None,
) -> str:
    """Compute deterministic 16-char SHA-256 hash for failure state."""
```

---

## Public API Exports

All public symbols are exported from the `jevon` package `__init__.py`:

```python
from jevon import (
    ActionReceipt,
    AdbTunnelTransport,
    BridgeTransport,
    ClosedLoopOrchestrator,
    ComparativeBenchmark,
    DecisionCommand,
    DecisionProvider,
    DeveloperAction,
    DeveloperDecision,
    IpcTransport,
    LaptopActionExecutor,
    LocalDecisionProvider,
    LoopResult,
    MicroBenchmarkMetrics,
    NpuDetector,
    OfficeKitBridge,
    SafetyFallback,
    SafetyGate,
    SocketTransport,
    StateObservation,
    TerminalErrorExtractor,
    TruthFirstState,
    VerificationEngine,
    VerificationOutcome,
    normalize_probabilities,
)
```

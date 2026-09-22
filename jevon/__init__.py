"""JEVON: On-Device Developer Decision Engine.

From developer intent to verified action.
"""

from jevon.bridge.bridge import OfficeKitBridge
from jevon.bridge.protocol import ActionReceipt, DecisionCommand
from jevon.bridge.transports import (
    AdbTunnelTransport,
    BridgeTransport,
    IpcTransport,
    SocketTransport,
)
from jevon.decision.actions import (
    DeveloperAction,
    DeveloperDecision,
    normalize_probabilities,
)
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.execution.executor import LaptopActionExecutor
from jevon.execution.safety_gate import SafetyGate
from jevon.loop import ClosedLoopOrchestrator, LoopResult
from jevon.perception.extractor import TerminalErrorExtractor
from jevon.perception.npu_detector import NpuDetector
from jevon.telemetry.benchmark import ComparativeBenchmark
from jevon.telemetry.metrics import MicroBenchmarkMetrics
from jevon.truth_first.state import TruthFirstState
from jevon.verification.engine import VerificationEngine, VerificationOutcome

__version__ = "0.2.0"

__all__ = [
    "ActionReceipt",
    "AdbTunnelTransport",
    "BridgeTransport",
    "ClosedLoopOrchestrator",
    "ComparativeBenchmark",
    "DecisionCommand",
    "DecisionProvider",
    "DeveloperAction",
    "DeveloperDecision",
    "IpcTransport",
    "LaptopActionExecutor",
    "LocalDecisionProvider",
    "LoopResult",
    "MicroBenchmarkMetrics",
    "NpuDetector",
    "OfficeKitBridge",
    "SafetyFallback",
    "SafetyGate",
    "SocketTransport",
    "StateObservation",
    "TerminalErrorExtractor",
    "TruthFirstState",
    "VerificationEngine",
    "VerificationOutcome",
    "normalize_probabilities",
]

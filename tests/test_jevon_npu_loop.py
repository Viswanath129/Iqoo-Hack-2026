"""Comprehensive tests for JEVON NPU Detector and ClosedLoopOrchestrator (R1/R2)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import pytest

from jevon.bridge.bridge import OfficeKitBridge
from jevon.bridge.protocol import ActionReceipt, DecisionCommand
from jevon.bridge.transports import IpcTransport
from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.execution.executor import LaptopActionExecutor
from jevon.loop import ClosedLoopOrchestrator, LoopResult
from jevon.perception.npu_detector import NpuDetector
from jevon.truth_first.state import TruthFirstState
from jevon.verification.engine import VerificationEngine


class SequenceDecisionProvider(DecisionProvider):
    """Decision provider that emits a predetermined sequence of DeveloperDecisions."""
    def __init__(self, sequence: list[DeveloperDecision] | None = None) -> None:
        self.sequence, self.call_history = list(sequence or []), []

    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        self.call_history.append((state, observation))
        return self.sequence.pop(0) if self.sequence else DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)


class MockExecutor:
    """Mock executor tracking dispatched commands and returning configurable ActionReceipts."""
    def __init__(self, exit_code: int = 0, stdout: str = "ok", stderr: str = "") -> None:
        self.commands, self.exit_code, self.stdout, self.stderr = [], exit_code, stdout, stderr

    def execute(self, command_str: str) -> ActionReceipt:
        self.commands.append(command_str)
        return ActionReceipt(
            command_id="cmd_mock", session_id="sess_test", step_index=len(self.commands) - 1,
            action=DeveloperAction.RERUN_BUILD, status="SUCCESS" if self.exit_code == 0 else "FAILED",
            exit_code=self.exit_code, stdout=self.stdout, stderr=self.stderr, verification_passed=(self.exit_code == 0),
        )


class TrackingBridge:
    """Mock OfficeKitBridge tracking connect/disconnect counts and relaying frames."""
    def __init__(self) -> None:
        self.connect_count = self.disconnect_count = 0
        self.sent_commands, self.sent_receipts = [], []
    def connect(self) -> bool:
        self.connect_count += 1
        return True
    def disconnect(self) -> None:
        self.disconnect_count += 1
    def is_connected(self) -> bool:
        return self.connect_count > self.disconnect_count
    def send_command(self, cmd: DecisionCommand) -> int:
        self.sent_commands.append(cmd)
        return 120
    def receive_command(self, timeout_s: float = 5.0) -> DecisionCommand:
        return self.sent_commands[-1]
    def send_receipt(self, receipt: ActionReceipt) -> int:
        self.sent_receipts.append(receipt)
        return 240
    def receive_receipt(self, timeout_s: float = 5.0) -> ActionReceipt:
        return self.sent_receipts[-1]


@pytest.fixture
def sample_obs() -> StateObservation:
    """Standard initial developer observation."""
    return StateObservation(
        session_id="test_session_001", step_index=0, working_directory="/mock/workspace",
        active_file="calc.py", terminal_output="", compiler_exit_code=None, git_status_summary="clean", recent_error=None,
    )


# 1. NpuDetector Unit Tests (14 Tests)

def test_npu_detector_tier_constants() -> None:
    """Verify all 4 tier constants exist and match expected string values."""
    assert (
        NpuDetector.TIER_QUALCOMM_NPU == "QUALCOMM_HEXAGON_NPU"
        and NpuDetector.TIER_CPU_ONNX == "CPU_ONNX"
        and NpuDetector.TIER_OS_SAPI == "OS_SAPI"
        and NpuDetector.TIER_CLI_KEYBOARD == "CLI_KEYBOARD"
    )

def test_npu_detector_tier_constants_distinct() -> None:
    """Verify all 4 tier constants are non-empty and mutually distinct."""
    tiers = {NpuDetector.TIER_QUALCOMM_NPU, NpuDetector.TIER_CPU_ONNX, NpuDetector.TIER_OS_SAPI, NpuDetector.TIER_CLI_KEYBOARD}
    assert len(tiers) == 4 and all(tiers)

def test_npu_detector_tier1_qualcomm_win32_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tier 1 Qualcomm Hexagon NPU detected when on win32, qnn is installed, and bundle exists."""
    monkeypatch.setattr(sys, "platform", "win32")
    bundle_dir = tmp_path / "whisper_bundle"
    bundle_dir.mkdir()
    monkeypatch.setenv("QNN_BUNDLE_PATH", str(bundle_dir))
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock() if n == "onnxruntime_qnn" else None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_QUALCOMM_NPU

def test_npu_detector_tier1_default_bundle_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 1 Qualcomm NPU detected using default bundle path when Path.exists is True."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("QNN_BUNDLE_PATH", raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock() if n == "onnxruntime_qnn" else None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_QUALCOMM_NPU

def test_npu_detector_tier1_bundle_missing_falls_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When QNN bundle path does not exist, Tier 1 falls through to CPU_ONNX."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("QNN_BUNDLE_PATH", str(tmp_path / "missing_bundle"))
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock() if n in {"onnxruntime_qnn", "onnxruntime"} else None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_CPU_ONNX

def test_npu_detector_tier1_non_win32_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tier 1 Qualcomm NPU requires win32; non-win32 platforms fall through to Tier 2."""
    monkeypatch.setattr(sys, "platform", "linux")
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    monkeypatch.setenv("QNN_BUNDLE_PATH", str(bundle_dir))
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock())
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_CPU_ONNX

def test_npu_detector_tier1_find_spec_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exception raised by find_spec('onnxruntime_qnn') safely falls through to Tier 2."""
    monkeypatch.setattr(sys, "platform", "win32")
    def mock_find(name: str) -> Any:
        if name == "onnxruntime_qnn": raise RuntimeError("Driver probe crashed")
        return MagicMock() if name == "onnxruntime" else None
    monkeypatch.setattr(importlib.util, "find_spec", mock_find)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_CPU_ONNX

@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_npu_detector_tier2_cpu_onnx_platforms(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    """Tier 2 CPU_ONNX detected on any platform when qnn is absent but onnxruntime is present."""
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock() if n == "onnxruntime" else None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_CPU_ONNX

def test_npu_detector_tier2_find_spec_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exception raised by find_spec('onnxruntime') safely falls through to OS_SAPI on win32."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(importlib.util, "find_spec", MagicMock(side_effect=ValueError("Corrupt metadata")))
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_OS_SAPI

def test_npu_detector_tier3_os_sapi_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 3 OS_SAPI detected on win32 when neither qnn nor onnxruntime is installed."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_OS_SAPI

@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_npu_detector_tier4_cli_keyboard_platforms(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    """Tier 4 CLI_KEYBOARD fallback returned on non-win32 when no ML engines exist."""
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: None)
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_CLI_KEYBOARD

@pytest.mark.parametrize("platform,expected", [("win32", NpuDetector.TIER_OS_SAPI), ("linux", NpuDetector.TIER_CLI_KEYBOARD)])
def test_npu_detector_both_find_specs_error(monkeypatch: pytest.MonkeyPatch, platform: str, expected: str) -> None:
    """When all find_spec calls raise exceptions, win32 yields OS_SAPI and linux yields CLI_KEYBOARD."""
    monkeypatch.setattr(importlib.util, "find_spec", MagicMock(side_effect=ImportError("Subsystem error")))
    monkeypatch.setattr(sys, "platform", platform)
    assert NpuDetector.detect_runtime_tier() == expected

def test_npu_detector_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """QNN_BUNDLE_PATH override selects Tier 1 if directory exists, falls through if nonexistent."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(importlib.util, "find_spec", lambda n: MagicMock() if n == "onnxruntime_qnn" else None)
    bundle = tmp_path / "custom_bundle"
    bundle.mkdir()
    monkeypatch.setenv("QNN_BUNDLE_PATH", str(bundle))
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_QUALCOMM_NPU
    monkeypatch.setenv("QNN_BUNDLE_PATH", str(tmp_path / "missing"))
    assert NpuDetector.detect_runtime_tier() == NpuDetector.TIER_OS_SAPI


# 2. LoopResult & Construction Tests (4 Tests)

def test_loop_result_fields_and_defaults() -> None:
    """LoopResult dataclass properly initializes fields and independent default list factories."""
    state = TruthFirstState(goal="Build app")
    res1, res2 = LoopResult("s_1", 2, DeveloperAction.DONE, True, state), LoopResult("s_2", 0, DeveloperAction.DONE, False, state)
    assert res1.session_id == "s_1" and res1.total_steps == 2 and res1.success is True
    assert res1.metrics == [] and res1.receipts == [] and res1.state is state
    assert res1.metrics is not res2.metrics and res1.receipts is not res2.receipts

def test_orchestrator_default_construction() -> None:
    """ClosedLoopOrchestrator instantiates standard default components safely."""
    orch = ClosedLoopOrchestrator()
    assert isinstance(orch.provider, SafetyFallback) and isinstance(orch.provider._wrapped, LocalDecisionProvider)
    assert isinstance(orch.bridge, OfficeKitBridge) and isinstance(orch.executor, LaptopActionExecutor)
    assert isinstance(orch.verifier, VerificationEngine) and orch.max_steps == 10

def test_orchestrator_custom_construction() -> None:
    """ClosedLoopOrchestrator correctly assigns provided custom dependencies."""
    provider, bridge, executor, verifier = SequenceDecisionProvider(), TrackingBridge(), MockExecutor(), VerificationEngine()
    orch = ClosedLoopOrchestrator(provider=provider, bridge=bridge, executor=executor, verifier=verifier, max_steps=7)  # type: ignore[arg-type]
    assert orch.provider is provider and orch.bridge is bridge and orch.executor is executor and orch.verifier is verifier and orch.max_steps == 7

def test_orchestrator_max_steps_zero(sample_obs: StateObservation) -> None:
    """When max_steps is 0, orchestrator exits immediately with total_steps=0 and success=False."""
    bridge = TrackingBridge()
    orch = ClosedLoopOrchestrator(provider=SequenceDecisionProvider(), bridge=bridge, executor=MockExecutor(), max_steps=0)  # type: ignore[arg-type]
    res = orch.run_standalone_cycle("Goal zero", sample_obs)
    assert res.total_steps == 0 and res.success is False and bridge.connect_count == 1 and bridge.disconnect_count == 1


# 3. ClosedLoopOrchestrator Lifecycle & Execution Tests (14 Tests)

def test_standalone_cycle_immediate_done(sample_obs: StateObservation) -> None:
    """Provider returning DONE immediately at step 0 results in instant success."""
    bridge = TrackingBridge()
    orch = ClosedLoopOrchestrator(
        provider=SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)]),
        bridge=bridge, executor=MockExecutor(),  # type: ignore[arg-type]
    )
    res = orch.run_standalone_cycle("Goal instant", sample_obs)
    assert res.success is True and res.total_steps == 0 and res.final_action == DeveloperAction.DONE
    assert len(res.receipts) == 0 and bridge.connect_count == 1 and bridge.disconnect_count == 1

def test_standalone_cycle_max_steps_1_terminates_early(sample_obs: StateObservation) -> None:
    """Orchestrator with max_steps=1 halts after exactly 1 non-terminal step."""
    bridge = TrackingBridge()
    orch = ClosedLoopOrchestrator(
        provider=SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.8)]),
        bridge=bridge, executor=MockExecutor(exit_code=0), max_steps=1,  # type: ignore[arg-type]
    )
    res = orch.run_standalone_cycle("Goal 1 step", sample_obs)
    assert res.total_steps == 1 and res.success is False and res.final_action == DeveloperAction.INSPECT_ERROR
    assert len(res.receipts) == 1 and bridge.connect_count == 1 and bridge.disconnect_count == 1

def test_standalone_cycle_respects_max_steps_limit(sample_obs: StateObservation) -> None:
    """Orchestrator strictly honors max_steps limit when provider never signals DONE."""
    orch = ClosedLoopOrchestrator(
        provider=SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.9)] * 10),
        bridge=TrackingBridge(), executor=MockExecutor(), max_steps=3,  # type: ignore[arg-type]
    )
    res = orch.run_standalone_cycle("Loop limit goal", sample_obs)
    assert res.total_steps == 3 and res.success is False and len(res.receipts) == 3 and len(res.metrics) == 3

def test_standalone_cycle_multi_step_error_fix_done(sample_obs: StateObservation) -> None:
    """Multi-step lifecycle: INSPECT_ERROR -> APPLY_FIX -> RERUN_BUILD -> DONE."""
    decisions = [
        DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.9, parameters={"error_text": "TypeError"}),
        DeveloperDecision(action=DeveloperAction.APPLY_FIX, confidence=0.85, parameters={"target_file": "c.py", "fix_patch": "pass"}),
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.95, parameters={"target_file": "c.py"}),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ]
    executor = MockExecutor(exit_code=0, stdout="compiled ok")
    orch = ClosedLoopOrchestrator(provider=SequenceDecisionProvider(decisions), bridge=TrackingBridge(), executor=executor, max_steps=10)  # type: ignore[arg-type]
    res = orch.run_standalone_cycle("Fix error", sample_obs)
    assert res.success is True and res.total_steps == 3 and res.final_action == DeveloperAction.DONE and len(res.receipts) == 3

def test_standalone_cycle_on_step_callback_called(sample_obs: StateObservation) -> None:
    """Step callback is invoked for each executed step with step index, command, and receipt."""
    recorded_steps: list[tuple[int, DeveloperAction, str]] = []
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.INSPECT_FILE, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.RUN_TARGETED_TEST, confidence=0.9),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=MockExecutor(exit_code=0))  # type: ignore[arg-type]
    orch.run_standalone_cycle("Callback goal", sample_obs, on_step=lambda s, c, r: recorded_steps.append((s, c.action, r.status)))
    assert recorded_steps == [(0, DeveloperAction.INSPECT_FILE, "SUCCESS"), (1, DeveloperAction.RUN_TARGETED_TEST, "SUCCESS")]

def test_standalone_cycle_on_step_not_called_on_immediate_done(sample_obs: StateObservation) -> None:
    """When first decision is DONE, on_step callback is never invoked."""
    called: list[int] = []
    orch = ClosedLoopOrchestrator(
        provider=SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)]),
        bridge=TrackingBridge(), executor=MockExecutor(),  # type: ignore[arg-type]
    )
    orch.run_standalone_cycle("Instant goal", sample_obs, on_step=lambda s, c, r: called.append(s))
    assert len(called) == 0

def test_standalone_cycle_bridge_connect_disconnect_lifecycle(sample_obs: StateObservation) -> None:
    """Bridge connect and disconnect lifecycle is strictly maintained across normal runs."""
    bridge = TrackingBridge()
    orch = ClosedLoopOrchestrator(
        provider=SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)]),
        bridge=bridge, executor=MockExecutor(),  # type: ignore[arg-type]
    )
    orch.run_standalone_cycle("Lifecycle goal", sample_obs)
    assert bridge.connect_count == 1 and bridge.disconnect_count == 1

def test_standalone_cycle_bridge_disconnect_on_exception(sample_obs: StateObservation) -> None:
    """Bridge disconnect is guaranteed via finally even if provider raises an exception."""
    bridge = TrackingBridge()
    class FaultyProvider(DecisionProvider):
        def decide(self, s: TruthFirstState, o: StateObservation) -> DeveloperDecision: raise RuntimeError("Provider malfunction")
    orch = ClosedLoopOrchestrator(provider=FaultyProvider(), bridge=bridge, executor=MockExecutor())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="Provider malfunction"):
        orch.run_standalone_cycle("Faulty goal", sample_obs)
    assert bridge.connect_count == 1 and bridge.disconnect_count == 1

def test_standalone_cycle_cmd_generation_build_and_test(sample_obs: StateObservation) -> None:
    """Command generation for RERUN_BUILD and RUN_TARGETED_TEST with default and custom arguments."""
    executor = MockExecutor()
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.8, parameters={"target_file": "main.py"}),
        DeveloperDecision(action=DeveloperAction.RUN_TARGETED_TEST, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.RUN_TARGETED_TEST, confidence=0.8, parameters={"target_test": "test_app.py"}),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=executor)  # type: ignore[arg-type]
    orch.run_standalone_cycle("Build & test cmds", sample_obs)
    assert executor.commands == ["python -m py_compile calc.py", "python -m py_compile main.py", "pytest test_calc.py", "pytest test_app.py"]

def test_standalone_cycle_cmd_generation_inspect_error_and_file(sample_obs: StateObservation) -> None:
    """Command generation for INSPECT_ERROR and INSPECT_FILE with provided and fallback values."""
    executor = MockExecutor()
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.8, parameters={"error_text": "ZeroDivision"}),
        DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.INSPECT_FILE, confidence=0.8, parameters={"target_file": "c.py"}),
        DeveloperDecision(action=DeveloperAction.INSPECT_FILE, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=executor)  # type: ignore[arg-type]
    orch.run_standalone_cycle("Inspect cmds", sample_obs)
    assert executor.commands == ['python -c "print(\'ZeroDivision\')"', "echo No error text", 'python -c "print(open(\'c.py\').read())"', "echo No target file specified"]

def test_standalone_cycle_cmd_generation_diff_and_fix(sample_obs: StateObservation) -> None:
    """Command generation for INSPECT_RECENT_CHANGE and APPLY_FIX with valid and fallback arguments."""
    executor, patch = MockExecutor(), "pass\n"
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.INSPECT_RECENT_CHANGE, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.INSPECT_RECENT_CHANGE, confidence=0.8, parameters={"git_command": "git diff HEAD~2"}),
        DeveloperDecision(action=DeveloperAction.APPLY_FIX, confidence=0.8, parameters={"target_file": "p.py", "fix_patch": patch}),
        DeveloperDecision(action=DeveloperAction.APPLY_FIX, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=executor)  # type: ignore[arg-type]
    orch.run_standalone_cycle("Diff & fix cmds", sample_obs)
    assert executor.commands == ["git diff HEAD~1", "git diff HEAD~2", f'python -c "open(\'p.py\', \'a\').write({patch!r})"', "echo No fix patch or target file specified"]

def test_standalone_cycle_cmd_generation_explicit_override_and_fallback(sample_obs: StateObservation) -> None:
    """Explicit 'command' parameter overrides default mapping, and unhandled actions default to 'git status'."""
    executor = MockExecutor()
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.8, parameters={"command": "ninja"}),
        DeveloperDecision(action=DeveloperAction.REQUEST_CONFIRMATION, confidence=0.8),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=executor)  # type: ignore[arg-type]
    orch.run_standalone_cycle("Override & fallback cmds", sample_obs)
    assert executor.commands == ["ninja", "git status"]

def test_standalone_cycle_truth_first_state_updates(sample_obs: StateObservation) -> None:
    """TruthFirstState records decisions, evidence, facts for passes, and failures for errors."""
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.9),
        DeveloperDecision(action=DeveloperAction.RUN_TARGETED_TEST, confidence=0.85),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    class ToggleExecutor:
        def __init__(self) -> None: self.step = 0
        def execute(self, cmd: str) -> ActionReceipt:
            self.step += 1
            return ActionReceipt("c1", "s1", 0, DeveloperAction.RERUN_BUILD, "SUCCESS", 0, "Build OK", "", True) if self.step == 1 else ActionReceipt("c2", "s1", 1, DeveloperAction.RUN_TARGETED_TEST, "FAILED", 1, "", "AssertErr", False)

    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=ToggleExecutor())  # type: ignore[arg-type]
    res = orch.run_standalone_cycle("State update goal", sample_obs)
    assert len(res.state.decisions) == 3 and any("Build OK" in ev for ev in res.state.evidence)
    assert any("Step 0 verified successfully" in fact for fact in res.state.facts)
    assert len(res.state.failed_approaches) == 1 and res.state.failed_approaches[0]["approach"] == "run_targeted_test"

def test_standalone_cycle_state_observation_and_metrics(sample_obs: StateObservation) -> None:
    """StateObservation advances step_index/status, and MicroBenchmarkMetrics records positive stage latencies."""
    provider = SequenceDecisionProvider([DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.9), DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=TrackingBridge(), executor=MockExecutor(exit_code=0, stdout="compiled ok"))  # type: ignore[arg-type]
    res = orch.run_standalone_cycle("Obs and metrics goal", sample_obs)
    assert len(provider.call_history) == 2
    step1_obs = provider.call_history[1][1]
    assert step1_obs.step_index == 1 and step1_obs.compiler_exit_code == 0 and step1_obs.git_status_summary == "clean"
    assert len(res.metrics) == 1 and res.metrics[0].total_latency_ns > 0

def test_standalone_cycle_real_ipc_bridge_integration(sample_obs: StateObservation) -> None:
    """Full end-to-end integration test across real OfficeKitBridge with in-memory IpcTransport."""
    real_bridge = OfficeKitBridge(IpcTransport())
    provider = SequenceDecisionProvider([
        DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.9, parameters={"target_file": "calc.py"}),
        DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0),
    ])
    orch = ClosedLoopOrchestrator(provider=provider, bridge=real_bridge, executor=MockExecutor(exit_code=0, stdout="Syntax OK"), max_steps=5)  # type: ignore[arg-type]
    res = orch.run_standalone_cycle("Real IPC bridge goal", sample_obs)
    assert res.success is True and res.total_steps == 1 and res.final_action == DeveloperAction.DONE
    assert len(res.receipts) == 1 and res.receipts[0].verification_passed is True and real_bridge.is_connected() is False

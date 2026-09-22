"""Closed-loop developer decision orchestrator for JEVON.

Coordinates the end-to-end loop:
    STATE → DECISION → ACTION → OBSERVATION → VERIFICATION → NEXT STATE

Supports three operating roles:
1. Phone Role (Intelligence Center):
   - Runs perception, on-device SLM / local decision provider, Truth-First ledger.
   - Dispatches DecisionCommand across OfficeKitBridge.
   - Receives ActionReceipt, verifies, updates TruthFirstState, decides next step.
2. Laptop Role (Execution Environment):
   - Receives DecisionCommand, runs LaptopActionExecutor (subprocess / desktop input).
   - Observes result, runs VerificationEngine, returns ActionReceipt across bridge.
3. Standalone Role (Single-Machine / CI/CD):
   - Runs both phone intelligence and laptop executor via local IpcTransport.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from jevon.bridge.bridge import OfficeKitBridge
from jevon.bridge.protocol import ActionReceipt, DecisionCommand
from jevon.bridge.transports import IpcTransport
from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.execution.executor import LaptopActionExecutor
from jevon.telemetry.metrics import MicroBenchmarkMetrics
from jevon.truth_first.state import TruthFirstState
from jevon.verification.engine import VerificationEngine

logger = logging.getLogger(__name__)


@dataclass
class LoopResult:
    """Summary of completed decision loop run."""

    session_id: str
    total_steps: int
    final_action: DeveloperAction
    success: bool
    state: TruthFirstState
    metrics: list[MicroBenchmarkMetrics] = field(default_factory=list)
    receipts: list[ActionReceipt] = field(default_factory=list)


class ClosedLoopOrchestrator:
    """End-to-end dual-device or standalone developer loop orchestrator."""

    def __init__(
        self,
        provider: DecisionProvider | None = None,
        bridge: OfficeKitBridge | None = None,
        executor: LaptopActionExecutor | None = None,
        verifier: VerificationEngine | None = None,
        max_steps: int = 10,
    ) -> None:
        self.provider = provider or SafetyFallback(LocalDecisionProvider())
        self.bridge = bridge or OfficeKitBridge(IpcTransport())
        self.executor = executor or LaptopActionExecutor()
        self.verifier = verifier or VerificationEngine()
        self.max_steps = max_steps

    def run_standalone_cycle(
        self,
        goal: str,
        initial_obs: StateObservation,
        on_step: Callable[[int, DecisionCommand, ActionReceipt], None] | None = None,
    ) -> LoopResult:
        """Run complete standalone loop using local IPC transport."""
        state = TruthFirstState(goal=goal)
        current_obs = initial_obs
        step = 0
        receipts: list[ActionReceipt] = []
        metrics_history: list[MicroBenchmarkMetrics] = []
        final_action = DeveloperAction.DONE
        success = False

        self.bridge.connect()

        try:
            while step < self.max_steps:
                step_metrics = MicroBenchmarkMetrics()

                # Stage 1: Local Inference & Decision on Phone
                t0 = time.perf_counter_ns()
                decision: DeveloperDecision = self.provider.decide(state, current_obs)
                decision_ns = time.perf_counter_ns() - t0
                step_metrics.decision_ns = decision_ns

                # Record decision in Truth-First State
                state.append_decision(
                    action=decision.action.value,
                    rationale=f"Confidence: {decision.confidence:.2f}",
                    params=decision.parameters,
                    probs=decision.probabilities,
                )

                cmd = DecisionCommand(
                    command_id=f"cmd_{step}_{int(time.time())}",
                    session_id=current_obs.session_id,
                    step_index=step,
                    timestamp_ns=time.time_ns(),
                    action=decision.action,
                    confidence=decision.confidence,
                    probabilities=decision.probabilities,
                    parameters=decision.parameters,
                )

                if decision.action == DeveloperAction.DONE:
                    final_action = DeveloperAction.DONE
                    success = True
                    break

                # Stage 2: Bridge Out (Phone -> Laptop)
                t0 = time.perf_counter_ns()
                bridge_out_ns = self.bridge.send_command(cmd)
                step_metrics.bridge_out_ns = bridge_out_ns

                # Laptop receives command
                received_cmd = self.bridge.receive_command()

                # Stage 3: Laptop Action Execution
                cmd_str = received_cmd.parameters.get("command", "")
                if not cmd_str:
                    if received_cmd.action == DeveloperAction.RERUN_BUILD:
                        cmd_str = "python -m py_compile " + (received_cmd.parameters.get("target_file") or "calc.py")
                    elif received_cmd.action == DeveloperAction.RUN_TARGETED_TEST:
                        cmd_str = "pytest " + (received_cmd.parameters.get("target_test") or "test_calc.py")
                    else:
                        cmd_str = "git status"

                t0 = time.perf_counter_ns()
                receipt = self.executor.execute(cmd_str)
                action_exec_ns = time.perf_counter_ns() - t0
                step_metrics.action_exec_ns = action_exec_ns

                # Stage 4: Independent Verification on Laptop
                t0 = time.perf_counter_ns()
                verif_outcome = self.verifier.verify(
                    exit_code=receipt.exit_code,
                    stdout=receipt.stdout,
                    stderr=receipt.stderr,
                )
                verif_ns = time.perf_counter_ns() - t0
                step_metrics.verification_ns = verif_ns

                receipt_verified = ActionReceipt(
                    command_id=received_cmd.command_id,
                    session_id=received_cmd.session_id,
                    step_index=step,
                    action=received_cmd.action,
                    status=receipt.status,
                    exit_code=receipt.exit_code,
                    stdout=receipt.stdout,
                    stderr=receipt.stderr,
                    verification_passed=verif_outcome.passed,
                    verification_details=verif_outcome.checks,
                    duration_ns=action_exec_ns,
                )

                # Stage 5: Bridge In (Laptop -> Phone)
                t0 = time.perf_counter_ns()
                bridge_in_ns = self.bridge.send_receipt(receipt_verified)
                step_metrics.bridge_in_ns = bridge_in_ns

                received_receipt = self.bridge.receive_receipt()
                receipts.append(received_receipt)
                metrics_history.append(step_metrics)

                # Update Truth-First State with observations & evidence
                if received_receipt.stdout:
                    state.append_evidence(f"stdout [step {step}]: {received_receipt.stdout.strip()}")
                if received_receipt.stderr:
                    state.append_evidence(f"stderr [step {step}]: {received_receipt.stderr.strip()}")

                if received_receipt.verification_passed:
                    state.append_fact(f"Step {step} verified successfully ({received_receipt.action}).")
                else:
                    state.record_failure(
                        cycle=step,
                        approach=received_receipt.action.value,
                        reason=received_receipt.stderr or f"Exit code {received_receipt.exit_code}",
                        exit_code=received_receipt.exit_code,
                    )

                if on_step:
                    on_step(step, cmd, received_receipt)

                # Advance observation
                current_obs = StateObservation(
                    session_id=current_obs.session_id,
                    step_index=step + 1,
                    working_directory=current_obs.working_directory,
                    active_file=current_obs.active_file,
                    terminal_output=received_receipt.stdout or received_receipt.stderr,
                    compiler_exit_code=received_receipt.exit_code,
                    git_status_summary="clean" if received_receipt.exit_code == 0 else "modified",
                    recent_error=received_receipt.stderr if received_receipt.exit_code != 0 else None,
                )

                step += 1
                final_action = received_receipt.action

        finally:
            self.bridge.disconnect()

        return LoopResult(
            session_id=initial_obs.session_id,
            total_steps=step,
            final_action=final_action,
            success=success,
            state=state,
            metrics=metrics_history,
            receipts=receipts,
        )

"""Tier 4 Scenario S4: Full Offline Dual-Device Roundtrip Workflow.

Features Exercised:
- F1: DecisionProvider Interface & Polymorphism
- F3: LocalDecisionProvider Offline (0 API Keys)
- F6: Typed Decisions (Confidence & Probability Sum = 1.0)
- F7: Truth-First State Model (7 Pillars)
- F8: Telemetry Schemas (StateObservation, DecisionCommand, ActionReceipt)
- F9: OfficeKitBridge Bi-Directional Protocol
- F10: Tri-Transport Layer (Local IPC Fallback)
"""

from __future__ import annotations

import time
import unittest

from e2e.stubs import (
    ActionReceipt,
    DecisionCommand,
    IpcTransport,
    OfficeKitBridge,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestScenarioOfflineDecisionLoop(unittest.TestCase):
    """Scenario S4: End-to-end dual-device roundtrip running 100% offline with zero cloud keys."""

    def setUp(self) -> None:
        # Dual-device bridge over local IPC
        self.bridge_laptop = OfficeKitBridge(transport=IpcTransport())
        self.bridge_laptop.connect()

        # Phone Intelligence Center
        self.phone_decision_engine = LocalDecisionProvider()
        self.phone_state = TruthFirstState(goal="Dual-device offline build/test loop", session_id="s4_dual_device")

    def tearDown(self) -> None:
        self.bridge_laptop.disconnect()

    def test_scenario_s4_full_offline_roundtrip_loop(self) -> None:
        # Phase 1: Laptop observes error state and sends StateObservation across bridge
        laptop_obs = StateObservation(
            session_id=self.phone_state.session_id,
            step_index=1,
            working_directory="/workspace/project",
            active_file="src/utils.py",
            terminal_output='File "src/utils.py", line 12\nTypeError: unsupported operand',
            compiler_exit_code=1,
            recent_error="TypeError: unsupported operand",
        )
        self.bridge_laptop.send_observation(laptop_obs)

        # Phone receives observation
        phone_obs = self.bridge_laptop.receive_observation(timeout_s=1.0)
        self.assertEqual(phone_obs.session_id, self.phone_state.session_id)
        self.assertEqual(phone_obs.recent_error, "TypeError: unsupported operand")

        # Phase 2: Phone decides 100% offline using LocalDecisionProvider
        self.phone_state.add_fact("Observed build error on src/utils.py")
        decision = self.phone_decision_engine.decide(self.phone_state, phone_obs)
        self.assertEqual(decision.action, DeveloperAction.INSPECT_ERROR)
        self.assertGreaterEqual(decision.confidence, 0.8)
        self.phone_state.record_decision(decision)

        # Phase 3: Phone dispatches DecisionCommand across bridge to laptop
        cmd = DecisionCommand(
            command_id="cmd_s4_step1",
            session_id=self.phone_state.session_id,
            step_index=1,
            timestamp_ns=time.time_ns(),
            action=decision.action,
            confidence=decision.confidence,
            probabilities=decision.probabilities,
            parameters=decision.parameters,
        )
        self.bridge_laptop.send_command(cmd)

        # Laptop receives DecisionCommand
        laptop_received_cmd = self.bridge_laptop.receive_command(timeout_s=1.0)
        self.assertEqual(laptop_received_cmd.action, DeveloperAction.INSPECT_ERROR)

        # Phase 4: Laptop executes action and returns ActionReceipt across bridge
        receipt = ActionReceipt(
            command_id=laptop_received_cmd.command_id,
            session_id=laptop_received_cmd.session_id,
            step_index=1,
            action=laptop_received_cmd.action,
            status="SUCCESS",
            exit_code=0,
            stdout="Inspected error trace: culprit is line 12 in src/utils.py",
            stderr="",
            verification_passed=True,
            duration_ns=1200000,
        )
        self.bridge_laptop.send_receipt(receipt)

        # Phone receives ActionReceipt and advances TruthFirstState
        phone_receipt = self.bridge_laptop.receive_receipt(timeout_s=1.0)
        self.assertEqual(phone_receipt.status, "SUCCESS")
        self.phone_state.add_evidence(phone_receipt.stdout)
        self.phone_state.cycle_index += 1

        self.assertEqual(self.phone_state.cycle_index, 1)
        self.assertEqual(len(self.phone_state.evidence), 1)
        self.assertIn("culprit is line 12", self.phone_state.evidence[0])


if __name__ == "__main__":
    unittest.main()

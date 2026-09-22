"""Tier 3 Pairwise Combinatorial Tests: Bridge & Decision Engine Coordination.

Covers:
- Pairwise interaction between OfficeKitBridge and DecisionProvider (Features 1, 3, 5, 8, 9, 10).
Total: 5 tests.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from e2e.stubs import (
    DecisionCommand,
    IpcTransport,
    OfficeKitBridge,
)
from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.truth_first.state import TruthFirstState


class TestBridgeWithDecisionCombination(unittest.TestCase):
    """Validates coordination between OfficeKitBridge and Decision Engine."""

    def setUp(self) -> None:
        self.bridge = OfficeKitBridge(transport=IpcTransport())
        self.bridge.connect()
        self.provider = LocalDecisionProvider()
        self.state = TruthFirstState(goal="Bridge decision coordination")

    def tearDown(self) -> None:
        self.bridge.disconnect()

    def test_p1_bridge_transports_decision_command_from_local_provider(self) -> None:
        obs = StateObservation(compiler_exit_code=1, recent_error="SyntaxError: invalid syntax")
        decision = self.provider.decide(self.state, obs)

        # Convert decision to DecisionCommand for transmission
        cmd = DecisionCommand(
            command_id="cmd_bridge_1",
            session_id="sess_comb",
            step_index=1,
            timestamp_ns=time.time_ns(),
            action=decision.action,
            confidence=decision.confidence,
            probabilities=decision.probabilities,
            parameters=decision.parameters,
            requires_confirmation=decision.requires_confirmation,
        )

        self.bridge.send_command(cmd)
        received_cmd = self.bridge.receive_command(timeout_s=1.0)

        self.assertEqual(received_cmd.command_id, "cmd_bridge_1")
        self.assertEqual(received_cmd.action, DeveloperAction.INSPECT_ERROR)
        self.assertAlmostEqual(received_cmd.confidence, decision.confidence, places=4)

    def test_p1_bridge_transports_state_observation_to_decision_engine(self) -> None:
        laptop_obs = StateObservation(
            session_id="sess_comb",
            step_index=2,
            compiler_exit_code=0,
            terminal_output="5 passed in 0.12s",
        )

        self.bridge.send_observation(laptop_obs)
        received_obs = self.bridge.receive_observation(timeout_s=1.0)

        self.state.record_decision("rerun_build")
        phone_decision = self.provider.decide(self.state, received_obs)
        self.assertEqual(phone_decision.action, DeveloperAction.DONE)

    def test_p1_bridge_with_safety_fallback_intercepted_command(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockLow"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.APPLY_FIX,
            confidence=0.45,  # Low confidence
            parameters={"target_file": "src/app.py"},
        )

        safe_engine = SafetyFallback(wrapped_provider=mock_provider, min_confidence=0.60)
        obs = StateObservation(compiler_exit_code=1)
        dec = safe_engine.decide(self.state, obs)

        cmd = DecisionCommand(
            command_id="cmd_safe_interception",
            session_id="sess_comb",
            step_index=3,
            timestamp_ns=time.time_ns(),
            action=dec.action,
            confidence=dec.confidence,
            probabilities=dec.probabilities,
            parameters=dec.parameters,
            requires_confirmation=dec.requires_confirmation,
        )

        self.bridge.send_command(cmd)
        received = self.bridge.receive_command(timeout_s=1.0)
        self.assertEqual(received.action, DeveloperAction.REQUEST_CONFIRMATION)
        self.assertTrue(received.requires_confirmation)

    def test_p1_bridge_reconnect_during_decision_loop(self) -> None:
        obs1 = StateObservation(session_id="reconnect_test", step_index=1)
        self.bridge.send_observation(obs1)

        # Simulate connection drop
        self.bridge.disconnect()
        self.assertFalse(self.bridge.is_connected())

        # Reconnect
        self.bridge.connect()
        self.assertTrue(self.bridge.is_connected())

        obs2 = StateObservation(session_id="reconnect_test", step_index=2)
        self.bridge.send_observation(obs2)
        rec2 = self.bridge.receive_observation(timeout_s=1.0)
        self.assertEqual(rec2.step_index, 2)

    def test_p1_bridge_multi_step_roundtrip_sequence(self) -> None:
        for i in range(3):
            obs = StateObservation(session_id="roundtrip", step_index=i + 1, compiler_exit_code=1)
            self.bridge.send_observation(obs)
            received_obs = self.bridge.receive_observation(timeout_s=1.0)
            self.assertEqual(received_obs.step_index, i + 1)

            dec = self.provider.decide(self.state, received_obs)
            cmd = DecisionCommand(
                command_id=f"cmd_{i+1}",
                session_id="roundtrip",
                step_index=i + 1,
                timestamp_ns=time.time_ns(),
                action=dec.action,
                confidence=dec.confidence,
                probabilities=dec.probabilities,
            )
            self.bridge.send_command(cmd)
            received_cmd = self.bridge.receive_command(timeout_s=1.0)
            self.assertEqual(received_cmd.command_id, f"cmd_{i+1}")


if __name__ == "__main__":
    unittest.main()

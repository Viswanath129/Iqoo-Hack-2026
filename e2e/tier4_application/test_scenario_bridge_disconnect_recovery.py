"""Tier 4 Scenario S5: Network Dropout & Reconnection Recovery Workflow.

Features Exercised:
- F8: Telemetry Schemas
- F9: OfficeKitBridge Bi-Directional Protocol
- F10: Tri-Transport Layer
- F12: Safety Failsafes (Timeouts & Connection Guard)
"""

from __future__ import annotations

import time
import unittest

from e2e.stubs import (
    ActionReceipt,
    DecisionCommand,
    IpcTransport,
    OfficeKitBridge,
    SocketTransport,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestScenarioBridgeDisconnectRecovery(unittest.TestCase):
    """Scenario S5: Verification of bridge fault tolerance, dropout resilience, and state recovery."""

    def test_scenario_s5_bridge_dropout_and_resume(self) -> None:
        state = TruthFirstState(goal="Network resilience check", session_id="s5_dropout_test")
        bridge = OfficeKitBridge(transport=IpcTransport())
        bridge.connect()

        # Step 1: Normal Transmission
        obs1 = StateObservation(session_id=state.session_id, step_index=1, compiler_exit_code=1)
        bridge.send_observation(obs1)
        rec_obs1 = bridge.receive_observation(timeout_s=1.0)
        self.assertEqual(rec_obs1.step_index, 1)

        # Step 2: Mid-Loop Network Dropout (Simulate connection drop)
        bridge.disconnect()
        self.assertFalse(bridge.is_connected())

        # Attempt to transmit while dropped -> Handled with ConnectionError
        obs_dropped = StateObservation(session_id=state.session_id, step_index=2)
        with self.assertRaises(ConnectionError):
            bridge.send_observation(obs_dropped)

        # Step 3: Transport Reconnect
        bridge.connect()
        self.assertTrue(bridge.is_connected())

        # Step 4: Resume Transmission after reconnect
        obs_resumed = StateObservation(
            session_id=state.session_id,
            step_index=2,
            terminal_output="Resumed connection. Running build.",
            compiler_exit_code=0,
        )
        bridge.send_observation(obs_resumed)
        rec_obs_resumed = bridge.receive_observation(timeout_s=1.0)
        self.assertEqual(rec_obs_resumed.step_index, 2)
        self.assertEqual(rec_obs_resumed.compiler_exit_code, 0)

        # Step 5: Command and Receipt over reconnected bridge
        cmd = DecisionCommand(
            command_id="cmd_post_recovery",
            session_id=state.session_id,
            step_index=2,
            timestamp_ns=time.time_ns(),
            action=DeveloperAction.DONE,
            confidence=0.98,
            probabilities={"done": 0.98},
        )
        bridge.send_command(cmd)
        rec_cmd = bridge.receive_command(timeout_s=1.0)
        self.assertEqual(rec_cmd.command_id, "cmd_post_recovery")
        self.assertEqual(rec_cmd.action, DeveloperAction.DONE)

        bridge.disconnect()


if __name__ == "__main__":
    unittest.main()

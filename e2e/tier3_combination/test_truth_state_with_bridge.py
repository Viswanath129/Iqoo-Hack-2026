"""Tier 3 Pairwise Combinatorial Tests: Truth-First State Model & Bridge Telemetry Coordination.

Covers:
- Pairwise interaction between TruthFirstState and OfficeKitBridge (Features 7, 8, 9, 10).
Total: 5 tests.
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
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState, compute_failure_signature


class TestTruthStateWithBridgeCombination(unittest.TestCase):
    """Validates coordination between Truth-First State Model and OfficeKitBridge."""

    def setUp(self) -> None:
        self.bridge = OfficeKitBridge(transport=IpcTransport())
        self.bridge.connect()
        self.state = TruthFirstState(goal="Full bridge state coordination", session_id="sess_sync")

    def tearDown(self) -> None:
        self.bridge.disconnect()

    def test_p4_truth_first_records_bridge_observation_facts(self) -> None:
        obs = StateObservation(
            session_id=self.state.session_id,
            step_index=1,
            compiler_exit_code=1,
            active_file="src/calc.py",
            recent_error="SyntaxError: invalid syntax",
        )
        self.bridge.send_observation(obs)
        received = self.bridge.receive_observation(timeout_s=1.0)

        # Parse observation into truth-first state facts
        self.state.add_fact(f"Observed exit code {received.compiler_exit_code} on {received.active_file}")
        self.state.add_evidence(received.recent_error or "")

        self.assertEqual(len(self.state.facts), 1)
        self.assertIn("src/calc.py", self.state.facts[0])
        self.assertEqual(len(self.state.evidence), 1)

    def test_p4_truth_first_records_transmitted_decisions(self) -> None:
        cmd = DecisionCommand(
            command_id="cmd_tf_1",
            session_id=self.state.session_id,
            step_index=1,
            timestamp_ns=time.time_ns(),
            action=DeveloperAction.INSPECT_FILE,
            confidence=0.92,
            probabilities={"inspect_file": 0.92, "done": 0.08},
            parameters={"target_file": "src/calc.py"},
        )
        self.bridge.send_command(cmd)
        rec_cmd = self.bridge.receive_command(timeout_s=1.0)

        # Record decision into truth-first state ledger
        self.state.record_decision(rec_cmd.action.value, parameters=rec_cmd.parameters)
        self.assertEqual(len(self.state.decisions), 1)
        self.assertEqual(self.state.decisions[0]["action"], "inspect_file")

    def test_p4_truth_first_tracks_receipt_in_evidence(self) -> None:
        receipt = ActionReceipt(
            command_id="cmd_tf_1",
            session_id=self.state.session_id,
            step_index=1,
            action=DeveloperAction.INSPECT_FILE,
            status="SUCCESS",
            exit_code=0,
            stdout="def add(a, b): return a + b",
            stderr="",
            verification_passed=True,
        )
        self.bridge.send_receipt(receipt)
        rec_receipt = self.bridge.receive_receipt(timeout_s=1.0)

        self.state.add_evidence(rec_receipt.stdout)
        self.assertTrue(rec_receipt.verification_passed)
        self.assertEqual(len(self.state.evidence), 1)
        self.assertIn("def add", self.state.evidence[0])

    def test_p4_truth_first_detects_loop_over_bridge_telemetry(self) -> None:
        # 3 identical error receipts over bridge
        for i in range(3):
            receipt = ActionReceipt(
                command_id=f"cmd_fail_{i}",
                session_id=self.state.session_id,
                step_index=i + 1,
                action=DeveloperAction.RUN_TARGETED_TEST,
                status="FAILED",
                exit_code=1,
                stdout="",
                stderr="AssertionError: Expected 5, got -1",
                verification_passed=False,
            )
            self.bridge.send_receipt(receipt)
            rec = self.bridge.receive_receipt(timeout_s=1.0)

            sig = compute_failure_signature(rec.exit_code, "calc.py", rec.stderr)
            self.state.record_failure_signature(sig)

        # Verify loop detected
        self.assertTrue(self.state.detect_repeated_failure(window=3))

    def test_p4_truth_first_audit_log_reflects_full_bridge_session(self) -> None:
        self.state.add_constraint("Allowlist developer tools only")
        self.state.add_fact("Target machine Windows ARM64")
        self.state.record_decision(DeveloperAction.RERUN_BUILD.value)
        self.state.add_evidence("uv run pytest: 15 passed")

        log = self.state.format_audit_log()
        self.assertIn("sess_sync", log)
        self.assertIn("Allowlist developer tools only", log)
        self.assertIn("Target machine Windows ARM64", log)
        self.assertIn("rerun_build", log)
        self.assertIn("15 passed", log)


if __name__ == "__main__":
    unittest.main()

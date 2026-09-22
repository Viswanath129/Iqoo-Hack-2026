"""Tier 4 Scenario S3: Destructive Action Interception Workflow.

Features Exercised:
- F1: DecisionProvider Interface & Polymorphism
- F12: Safety Failsafes (Allowlist & Failsafe Bounds)
- F13: SafetyGate Destructive Action Blocking
"""

from __future__ import annotations

import json
import sys
import unittest

from e2e.fixtures import DESTRUCTIVE_COMMANDS_DIR
from e2e.stubs import (
    ActionReceipt,
    LaptopActionExecutor,
    SafetyGate,
)
from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestScenarioDestructiveGate(unittest.TestCase):
    """Scenario S3: Verification of SafetyGate blocking destructive commands and requiring human confirmation."""

    def setUp(self) -> None:
        self.executor = LaptopActionExecutor()
        self.provider = LocalDecisionProvider()
        self.state = TruthFirstState(goal="Verify safety bounds against destructive commands")

        # Load fixture commands
        fixture_path = DESTRUCTIVE_COMMANDS_DIR / "sample_commands.json"
        with open(fixture_path, encoding="utf-8") as f:
            self.fixture_data = json.load(f)

    def test_scenario_s3_destructive_actions_blocked_until_confirmed(self) -> None:
        destructive_cases = self.fixture_data["destructive_commands"]

        for item in destructive_cases:
            cmd = item["command"]
            is_dest, reason = SafetyGate.is_destructive(cmd)
            self.assertTrue(is_dest, f"Command '{cmd}' was not classified as destructive!")

            # Attempt unconfirmed execution -> Must be BLOCKED
            receipt = self.executor.execute(cmd, confirmed=False)
            self.assertEqual(
                receipt.status,
                "BLOCKED_BY_SAFETY",
                f"Destructive command '{cmd}' should have been blocked!",
            )
            self.assertEqual(receipt.exit_code, 126)
            self.assertFalse(receipt.verification_passed)

            # Decision Engine evaluates state -> Must require confirmation
            dec = DeveloperDecision(
                action=DeveloperAction.RERUN_BUILD,
                confidence=0.9,
                parameters={"command": cmd},
                metadata={"destructive": True},
            )
            self.assertTrue(
                dec.requires_confirmation,
                f"Decision for '{cmd}' must require developer confirmation",
            )

        # Verify safe commands are allowed
        safe_cases = self.fixture_data["safe_commands"]
        for item in safe_cases:
            cmd = item["command"]
            is_dest, _ = SafetyGate.is_destructive(cmd)
            self.assertFalse(is_dest, f"Safe command '{cmd}' was falsely flagged as destructive!")


if __name__ == "__main__":
    unittest.main()

"""Tier 4 Scenario S2: Failing Unit Test Debug Loop Workflow.

Features Exercised:
- F1: DecisionProvider Interface & Polymorphism
- F2: Bounded Action Space
- F3: LocalDecisionProvider Offline
- F6: Typed Decisions (Confidence & Probability Sum = 1.0)
- F11: LaptopActionExecutor Adaptation & Process Isolation
- F14: VerificationEngine Independent Validation
- F15: Closed-Loop Cycle
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from e2e.fixtures import BROKEN_TEST_DIR
from e2e.stubs import (
    LaptopActionExecutor,
    VerificationEngine,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestScenarioFailingTestDebug(unittest.TestCase):
    """Scenario S2: Full debug loop diagnosing and fixing a semantic unit test failure."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        shutil.copy(BROKEN_TEST_DIR / "calc.py", self.workspace / "calc.py")
        shutil.copy(BROKEN_TEST_DIR / "test_calc.py", self.workspace / "test_calc.py")

        self.executor = LaptopActionExecutor(working_directory=str(self.workspace))
        self.provider = LocalDecisionProvider()
        self.verifier = VerificationEngine()
        self.state = TruthFirstState(goal="Debug and fix failing unit test in test_calc.py", session_id="s2_debug_session")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scenario_s2_failing_test_debug_loop(self) -> None:
        # Step 1: Run Failing Test
        cmd_run = f'{sys.executable} -m pytest test_calc.py'
        receipt_1 = self.executor.execute(cmd_run)
        self.assertNotEqual(receipt_1.exit_code, 0)
        self.assertIn("AssertionError", receipt_1.stdout)
        self.assertIn("Expected 5, got -1", receipt_1.stdout)

        # Emit Observation
        obs_1 = StateObservation(
            session_id=self.state.session_id,
            step_index=1,
            working_directory=str(self.workspace),
            active_file="calc.py",
            terminal_output=receipt_1.stdout,
            compiler_exit_code=receipt_1.exit_code,
            recent_error="AssertionError: Expected 5, got -1",
        )
        self.state.add_evidence(receipt_1.stdout)
        self.state.add_fact("test_add failed with AssertionError")

        dec_1 = self.provider.decide(self.state, obs_1)
        self.assertEqual(dec_1.action, DeveloperAction.INSPECT_ERROR)
        self.state.record_decision(dec_1)

        # Step 2: Next observation inspects file
        obs_2 = StateObservation(
            session_id=self.state.session_id,
            step_index=2,
            working_directory=str(self.workspace),
            active_file="calc.py",
            compiler_exit_code=1,
            recent_error="AssertionError: Expected 5, got -1",
        )
        dec_2 = self.provider.decide(self.state, obs_2)
        self.assertEqual(dec_2.action, DeveloperAction.INSPECT_FILE)
        self.state.record_decision(dec_2)

        # Step 3: Apply fix
        obs_3 = StateObservation(
            session_id=self.state.session_id,
            step_index=3,
            working_directory=str(self.workspace),
            active_file="calc.py",
            compiler_exit_code=1,
            metadata={"suggested_fix": "return a + b\n"},
        )
        dec_3 = self.provider.decide(self.state, obs_3)
        self.assertEqual(dec_3.action, DeveloperAction.APPLY_FIX)
        self.state.record_decision(dec_3)

        # Apply fix to calc.py
        fixed_code = (
            "def add(a: int, b: int) -> int:\n"
            "    return a + b  # Corrected implementation\n\n"
            "def multiply(a: int, b: int) -> int:\n"
            "    return a * b\n"
        )
        (self.workspace / "calc.py").write_text(fixed_code, encoding="utf-8")
        self.state.add_fact("calc.py patched with addition operator")

        # Step 4: Run targeted test
        obs_4 = StateObservation(
            session_id=self.state.session_id,
            step_index=4,
            active_file="calc.py",
            compiler_exit_code=None,
        )
        dec_4 = self.provider.decide(self.state, obs_4)
        self.assertEqual(dec_4.action, DeveloperAction.RUN_TARGETED_TEST)
        self.state.record_decision(dec_4)

        # Execute test
        receipt_targeted = self.executor.execute(cmd_run)
        self.assertEqual(receipt_targeted.status, "SUCCESS")
        self.assertEqual(receipt_targeted.exit_code, 0)
        self.assertIn("2 passed", receipt_targeted.stdout)

        # Step 5: Full verification rerun
        obs_5 = StateObservation(
            session_id=self.state.session_id,
            step_index=5,
            compiler_exit_code=0,
            terminal_output=receipt_targeted.stdout,
        )
        dec_5 = self.provider.decide(self.state, obs_5)
        self.assertEqual(dec_5.action, DeveloperAction.RERUN_BUILD)
        self.state.record_decision(dec_5)

        # Step 6: Verify clean completion
        obs_6 = StateObservation(
            session_id=self.state.session_id,
            step_index=6,
            compiler_exit_code=0,
            terminal_output="2 passed in 0.05s",
        )
        dec_6 = self.provider.decide(self.state, obs_6)
        self.assertEqual(dec_6.action, DeveloperAction.DONE)
        self.assertTrue(dec_6.is_terminal)

        # Independent Verification Engine validation
        outcome = self.verifier.verify(
            exit_code=receipt_targeted.exit_code,
            stdout=receipt_targeted.stdout,
            stderr=receipt_targeted.stderr,
            expected_regex=r"2 passed",
            previous_error="AssertionError: Expected 5, got -1",
        )
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.checks["exit_code_zero"])
        self.assertTrue(outcome.checks["regex_matched"])
        self.assertTrue(outcome.checks["error_eliminated"])


if __name__ == "__main__":
    unittest.main()

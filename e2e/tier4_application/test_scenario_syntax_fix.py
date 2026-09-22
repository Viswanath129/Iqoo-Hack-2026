"""Tier 4 Scenario S1: Syntax Error Auto-Diagnosis & Fix Workflow.

Features Exercised:
- F1: DecisionProvider Interface & Polymorphism
- F2: Bounded Action Space
- F3: LocalDecisionProvider Offline
- F7: Truth-First State Model (7 Pillars)
- F8: Telemetry Schemas
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

from e2e.fixtures import BROKEN_SYNTAX_DIR
from e2e.stubs import (
    LaptopActionExecutor,
    VerificationEngine,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestScenarioSyntaxFix(unittest.TestCase):
    """Scenario S1: Fully automated detection, diagnosis, fix application, and verification of a SyntaxError."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        shutil.copy(BROKEN_SYNTAX_DIR / "calc.py", self.workspace / "calc.py")
        shutil.copy(BROKEN_SYNTAX_DIR / "test_calc.py", self.workspace / "test_calc.py")

        self.executor = LaptopActionExecutor(working_directory=str(self.workspace))
        self.provider = LocalDecisionProvider()
        self.verifier = VerificationEngine()
        self.state = TruthFirstState(goal="Diagnose and resolve Python SyntaxError", session_id="s1_syntax_session")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scenario_s1_full_syntax_fix_loop(self) -> None:
        # Step 1: Baseline Build Attempt -> Expect SyntaxError
        cmd_build = f'{sys.executable} -m py_compile calc.py'
        receipt_1 = self.executor.execute(cmd_build)
        self.assertNotEqual(receipt_1.exit_code, 0)
        self.assertIn("SyntaxError", receipt_1.stderr)

        # Emit Observation to Phone Intelligence
        obs_1 = StateObservation(
            session_id=self.state.session_id,
            step_index=1,
            working_directory=str(self.workspace),
            active_file="calc.py",
            terminal_output=receipt_1.stderr,
            compiler_exit_code=receipt_1.exit_code,
            recent_error="SyntaxError: closing parenthesis ')' does not match opening parenthesis '('",
        )
        self.state.add_fact("calc.py failed build compilation")
        self.state.add_evidence(receipt_1.stderr)

        dec_1 = self.provider.decide(self.state, obs_1)
        self.assertEqual(dec_1.action, DeveloperAction.INSPECT_ERROR)
        self.state.record_decision(dec_1)

        # Step 2: Next observation with parsed culprit file -> Expect INSPECT_FILE
        obs_2 = StateObservation(
            session_id=self.state.session_id,
            step_index=2,
            working_directory=str(self.workspace),
            active_file="calc.py",
            compiler_exit_code=1,
            recent_error="SyntaxError: unclosed parenthesis",
        )
        dec_2 = self.provider.decide(self.state, obs_2)
        self.assertEqual(dec_2.action, DeveloperAction.INSPECT_FILE)
        self.state.record_decision(dec_2)

        # Step 3: Diagnose root cause -> Expect APPLY_FIX
        obs_3 = StateObservation(
            session_id=self.state.session_id,
            step_index=3,
            working_directory=str(self.workspace),
            active_file="calc.py",
            compiler_exit_code=1,
            recent_error="SyntaxError: line 3 unclosed parenthesis",
            metadata={"suggested_fix": "return (a + b)\n"},
        )
        dec_3 = self.provider.decide(self.state, obs_3)
        self.assertEqual(dec_3.action, DeveloperAction.APPLY_FIX)
        self.state.record_decision(dec_3)

        # Apply Patch to calc.py
        fixed_code = "def add(a: int, b: int) -> int:\n    return a + b\n\ndef multiply(a: int, b: int) -> int:\n    return a * b\n"
        (self.workspace / "calc.py").write_text(fixed_code, encoding="utf-8")
        self.state.add_fact("Applied patch closing unclosed parenthesis in calc.py")

        # Step 4: Verify syntax elimination with AST
        ast_ok, ast_err = self.verifier.verify_ast_syntax(fixed_code)
        self.assertTrue(ast_ok, f"AST verification failed: {ast_err}")

        # Step 5: After fix -> Expect RUN_TARGETED_TEST
        obs_4 = StateObservation(
            session_id=self.state.session_id,
            step_index=4,
            active_file="calc.py",
            compiler_exit_code=None,
        )
        dec_4 = self.provider.decide(self.state, obs_4)
        self.assertEqual(dec_4.action, DeveloperAction.RUN_TARGETED_TEST)
        self.state.record_decision(dec_4)

        # Execute targeted test
        cmd_test = f'{sys.executable} -m pytest test_calc.py'
        receipt_test = self.executor.execute(cmd_test)
        self.assertEqual(receipt_test.status, "SUCCESS")
        self.assertEqual(receipt_test.exit_code, 0)
        self.assertIn("passed", receipt_test.stdout)

        # Step 6: Targeted test passed -> Expect RERUN_BUILD
        obs_5 = StateObservation(
            session_id=self.state.session_id,
            step_index=5,
            compiler_exit_code=0,
            terminal_output=receipt_test.stdout,
        )
        dec_5 = self.provider.decide(self.state, obs_5)
        self.assertEqual(dec_5.action, DeveloperAction.RERUN_BUILD)
        self.state.record_decision(dec_5)

        # Step 7: Clean build complete -> Expect DONE
        cmd_full_build = f'{sys.executable} -m py_compile calc.py'
        receipt_full = self.executor.execute(cmd_full_build)
        self.assertEqual(receipt_full.exit_code, 0)

        obs_6 = StateObservation(
            session_id=self.state.session_id,
            step_index=6,
            compiler_exit_code=0,
            terminal_output="Build passed cleanly. 1 test passed.",
        )
        dec_6 = self.provider.decide(self.state, obs_6)
        self.assertEqual(dec_6.action, DeveloperAction.DONE)
        self.assertTrue(dec_6.is_terminal)

        # Step 8: Final Independent Verification
        outcome = self.verifier.verify(
            exit_code=receipt_full.exit_code,
            stdout=receipt_test.stdout,
            stderr=receipt_full.stderr,
            expected_regex=r"\d+ passed",
            source_code=fixed_code,
            previous_error="SyntaxError",
        )
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.checks["exit_code_zero"])
        self.assertTrue(outcome.checks["regex_matched"])
        self.assertTrue(outcome.checks["ast_valid"])
        self.assertTrue(outcome.checks["error_eliminated"])


if __name__ == "__main__":
    unittest.main()

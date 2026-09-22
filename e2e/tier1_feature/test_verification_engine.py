"""Tier 1 Feature Tests: Verification Engine & Closed-Loop Cycle (Features 14, 15).

Covers:
- Feature 14: VerificationEngine Independent Validation (No Self-Cert) (5 tests)
- Feature 15: Closed-Loop Cycle (STATE -> DECISION -> ACTION -> OBS -> VERIF -> NEXT) (5 tests)
Total: 10 tests.
"""

from __future__ import annotations

import unittest

from e2e.stubs import (
    VerificationEngine,
)
from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState

# ===========================================================================
# Feature 14: VerificationEngine Independent Validation (R5)
# ===========================================================================

class TestFeature14VerificationEngine(unittest.TestCase):
    """Validates Feature 14: Objective verification without self-certification."""

    def setUp(self) -> None:
        self.verifier = VerificationEngine()

    def test_f14_verification_exit_code_zero(self) -> None:
        self.assertTrue(self.verifier.verify_exit_code(0))
        self.assertFalse(self.verifier.verify_exit_code(1))
        self.assertFalse(self.verifier.verify_exit_code(127))

    def test_f14_verification_regex_pattern_match(self) -> None:
        pytest_out = "===== 15 passed in 0.42s ====="
        self.assertTrue(self.verifier.verify_regex(pytest_out, r"\d+ passed"))
        self.assertFalse(self.verifier.verify_regex(pytest_out, r"\d+ failed"))

    def test_f14_verification_ast_syntax_check(self) -> None:
        valid_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        ok, err = self.verifier.verify_ast_syntax(valid_code)
        self.assertTrue(ok)
        self.assertIsNone(err)

        invalid_code = "def add(a, b:\n    return a + b\n"
        ok_bad, err_bad = self.verifier.verify_ast_syntax(invalid_code)
        self.assertFalse(ok_bad)
        self.assertIsNotNone(err_bad)

    def test_f14_verification_error_elimination_check(self) -> None:
        prev_err = "SyntaxError: unclosed parenthesis"
        clean_out = "Running build... Success. 5 passed."
        dirty_out = f"Error trace: {prev_err} at line 3"

        self.assertTrue(self.verifier.verify_error_eliminated(clean_out, prev_err))
        self.assertFalse(self.verifier.verify_error_eliminated(dirty_out, prev_err))

    def test_f14_verification_composite_all_checks_required(self) -> None:
        outcome_pass = self.verifier.verify(
            exit_code=0,
            stdout="3 passed in 0.1s",
            stderr="",
            expected_regex=r"\d+ passed",
            source_code="x = 10\n",
            previous_error="NameError: name 'x' is not defined",
        )
        self.assertTrue(outcome_pass.passed)
        self.assertTrue(outcome_pass.checks["exit_code_zero"])
        self.assertTrue(outcome_pass.checks["regex_matched"])
        self.assertTrue(outcome_pass.checks["ast_valid"])
        self.assertTrue(outcome_pass.checks["error_eliminated"])

        outcome_fail = self.verifier.verify(
            exit_code=1,
            stdout="1 failed",
            stderr="AssertionError",
            expected_regex=r"\d+ passed",
        )
        self.assertFalse(outcome_fail.passed)


# ===========================================================================
# Feature 15: Closed-Loop Cycle (R5)
# ===========================================================================

class TestFeature15ClosedLoopCycle(unittest.TestCase):
    """Validates Feature 15: Advancement of the closed feedback loop."""

    def test_f15_closed_loop_state_advancement(self) -> None:
        state = TruthFirstState(goal="Diagnose syntax bug")
        provider = LocalDecisionProvider()

        # Step 1: Initial observation with syntax error
        obs1 = StateObservation(
            step_index=1,
            compiler_exit_code=1,
            recent_error="SyntaxError: invalid syntax",
            terminal_output='File "calc.py", line 3\n  return (a + b\nSyntaxError',
        )
        dec1 = provider.decide(state, obs1)
        self.assertEqual(dec1.action, DeveloperAction.INSPECT_ERROR)
        state.record_decision(dec1)
        state.cycle_index += 1

        self.assertEqual(state.cycle_index, 1)
        self.assertEqual(len(state.decisions), 1)

    def test_f15_closed_loop_cycle_index_increments(self) -> None:
        state = TruthFirstState()
        for i in range(5):
            state.cycle_index += 1
            state.record_decision(f"action_{i}")
        self.assertEqual(state.cycle_index, 5)
        self.assertEqual(len(state.decisions), 5)

    def test_f15_closed_loop_history_accumulation(self) -> None:
        state = TruthFirstState()
        state.record_decision(DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.9))
        state.record_decision(DeveloperDecision(action=DeveloperAction.INSPECT_FILE, confidence=0.88))
        state.record_decision(DeveloperDecision(action=DeveloperAction.APPLY_FIX, confidence=0.85))

        self.assertEqual(len(state.decisions), 3)
        actions = [d["action"] for d in state.decisions]
        self.assertEqual(actions, ["inspect_error", "inspect_file", "apply_fix"])

    def test_f15_closed_loop_terminal_condition(self) -> None:
        state = TruthFirstState()
        state.record_decision("apply_fix")
        state.record_decision("run_targeted_test")
        state.record_decision("rerun_build")

        provider = LocalDecisionProvider()
        obs_clean = StateObservation(compiler_exit_code=0, terminal_output="3 passed in 0.05s")
        dec = provider.decide(state, obs_clean)
        self.assertEqual(dec.action, DeveloperAction.DONE)
        self.assertTrue(dec.is_terminal)

    def test_f15_closed_loop_unrecovered_failure_halts(self) -> None:
        state = TruthFirstState()
        provider = LocalDecisionProvider()

        # Simulate 3 identical failure signatures
        sig = "sig_fatal_err_123"
        state.record_failure_signature(sig)
        state.record_failure_signature(sig)
        state.record_failure_signature(sig)

        obs = StateObservation(compiler_exit_code=1, recent_error="Fatal unrecoverable error")
        dec = provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.REQUEST_CONFIRMATION)
        self.assertEqual(dec.parameters.get("reason"), "loop_detected")


if __name__ == "__main__":
    unittest.main()

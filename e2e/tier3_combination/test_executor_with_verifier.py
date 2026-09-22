"""Tier 3 Pairwise Combinatorial Tests: Laptop Executor & Verification Engine Coordination.

Covers:
- Pairwise interaction between LaptopActionExecutor and VerificationEngine (Features 11, 12, 13, 14, 15).
Total: 5 tests.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

from e2e.fixtures import (
    BROKEN_SYNTAX_DIR,
    CLEAN_PROJECT_DIR,
)
from e2e.stubs import (
    LaptopActionExecutor,
    VerificationEngine,
)


class TestExecutorWithVerifierCombination(unittest.TestCase):
    """Validates coordination between LaptopActionExecutor and VerificationEngine."""

    def setUp(self) -> None:
        self.executor = LaptopActionExecutor()
        self.verifier = VerificationEngine()

    def test_p3_executor_clean_run_verified_by_exit_code_and_regex(self) -> None:
        cmd = f'{sys.executable} -m pytest "{CLEAN_PROJECT_DIR / "test_calc.py"}"'
        receipt = self.executor.execute(cmd)

        outcome = self.verifier.verify(
            exit_code=receipt.exit_code,
            stdout=receipt.stdout,
            stderr=receipt.stderr,
            expected_regex=r"\d+ passed",
        )
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.checks["exit_code_zero"])
        self.assertTrue(outcome.checks["regex_matched"])

    def test_p3_executor_broken_syntax_verified_syntax_error_detected(self) -> None:
        syntax_file = BROKEN_SYNTAX_DIR / "calc.py"
        code_content = syntax_file.read_text(encoding="utf-8")

        # Compile should fail
        cmd = f'{sys.executable} -m py_compile "{syntax_file}"'
        receipt = self.executor.execute(cmd)
        self.assertNotEqual(receipt.exit_code, 0)

        # Verifier checks AST parse error
        ok, err = self.verifier.verify_ast_syntax(code_content)
        self.assertFalse(ok)
        self.assertIsNotNone(err)

    def test_p3_executor_fixed_syntax_verified_clean(self) -> None:
        fixed_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        ok, err = self.verifier.verify_ast_syntax(fixed_code)
        self.assertTrue(ok)
        self.assertIsNone(err)

        outcome = self.verifier.verify(
            exit_code=0,
            stdout="Compile OK",
            stderr="",
            source_code=fixed_code,
        )
        self.assertTrue(outcome.passed)

    def test_p3_executor_blocked_safety_verified_unpassed(self) -> None:
        cmd = "git reset --hard HEAD~1"
        receipt = self.executor.execute(cmd, confirmed=False)

        outcome = self.verifier.verify(
            exit_code=receipt.exit_code,
            stdout=receipt.stdout,
            stderr=receipt.stderr,
        )
        # Blocked action has non-zero exit code (126), so verification must fail
        self.assertFalse(outcome.passed)
        self.assertFalse(outcome.checks["exit_code_zero"])

    def test_p3_executor_error_elimination_verified(self) -> None:
        prev_err = "SyntaxError: unclosed parenthesis"
        cmd = f'{sys.executable} -m pytest "{CLEAN_PROJECT_DIR / "test_calc.py"}"'
        receipt = self.executor.execute(cmd)

        outcome = self.verifier.verify(
            exit_code=receipt.exit_code,
            stdout=receipt.stdout,
            stderr=receipt.stderr,
            previous_error=prev_err,
        )
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.checks["error_eliminated"])


if __name__ == "__main__":
    unittest.main()

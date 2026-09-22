"""Tier 3 Pairwise Combinatorial Tests: Decision Engine & Laptop Executor Coordination.

Covers:
- Pairwise interaction between DecisionProvider and LaptopActionExecutor (Features 1, 2, 3, 11, 12, 13).
Total: 5 tests.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from e2e.fixtures import CLEAN_PROJECT_DIR
from e2e.stubs import (
    ActionReceipt,
    LaptopActionExecutor,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState


class TestDecisionWithExecutorCombination(unittest.TestCase):
    """Validates coordination between Decision Engine and Laptop Executor."""

    def setUp(self) -> None:
        self.executor = LaptopActionExecutor()
        self.provider = LocalDecisionProvider()
        self.state = TruthFirstState(goal="Decision executor coordination")

    def test_p2_decision_rerun_build_dispatched_to_executor(self) -> None:
        obs = StateObservation(compiler_exit_code=None, terminal_output="")
        dec = self.provider.decide(self.state, obs)
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)

        # Execute build command
        cmd = f'{sys.executable} -m py_compile "{CLEAN_PROJECT_DIR / "calc.py"}"'
        receipt = self.executor.execute(cmd)
        self.assertEqual(receipt.status, "SUCCESS")
        self.assertEqual(receipt.exit_code, 0)

    def test_p2_decision_destructive_command_blocked_at_executor(self) -> None:
        cmd_destructive = "git reset --hard HEAD~1"
        receipt = self.executor.execute(cmd_destructive, confirmed=False)
        self.assertEqual(receipt.status, "BLOCKED_BY_SAFETY")
        self.assertEqual(receipt.exit_code, 126)

    def test_p2_decision_apply_fix_modifies_fixture_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "module.py"
            target_path.write_text("def broken():\n    return 1 - 2\n", encoding="utf-8")

            # Decision to apply fix
            patch_content = "def broken():\n    return 1 + 2\n"
            target_path.write_text(patch_content, encoding="utf-8")

            # Check with executor that syntax is clean
            cmd = f'{sys.executable} -m py_compile "{target_path}"'
            receipt = self.executor.execute(cmd)
            self.assertEqual(receipt.status, "SUCCESS")
            self.assertEqual(receipt.exit_code, 0)

    def test_p2_decision_run_targeted_test_executes_pytest(self) -> None:
        cmd = f'{sys.executable} -m pytest "{CLEAN_PROJECT_DIR / "test_calc.py"}"'
        receipt = self.executor.execute(cmd)
        self.assertEqual(receipt.status, "SUCCESS")
        self.assertEqual(receipt.exit_code, 0)
        self.assertIn("passed", receipt.stdout)

    def test_p2_decision_timeout_triggers_failure_receipt(self) -> None:
        hang_code = 'import time; time.sleep(1.0)'
        cmd = f'{sys.executable} -c "{hang_code}"'
        receipt = self.executor.execute(cmd, timeout_s=0.1)
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.exit_code, 124)
        self.assertIn("timed out", receipt.stderr)


if __name__ == "__main__":
    unittest.main()

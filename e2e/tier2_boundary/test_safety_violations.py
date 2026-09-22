"""Tier 2 Boundary Tests: Safety Violations, Corner Failsafes & Execution Bounds (Features 11, 12, 13).

Covers:
- Feature 11: LaptopActionExecutor Adaptation & Process Isolation (5 boundary tests)
- Feature 12: Safety Failsafes (Mouse Corner 10px, 30s Timeout, Allowlist) (5 boundary tests)
- Feature 13: SafetyGate Destructive Action Blocking (5 boundary tests)
Total: 15 tests.
"""

from __future__ import annotations

import sys
import unittest

from e2e.stubs import (
    ABORT_CORNER_PX,
    LaptopActionExecutor,
    SafetyGate,
)


# ===========================================================================
# Feature 11 Boundary Cases: LaptopActionExecutor
# ===========================================================================

class TestFeature11LaptopActionExecutorBoundaries(unittest.TestCase):
    """Boundary conditions for LaptopActionExecutor."""

    def setUp(self) -> None:
        self.executor = LaptopActionExecutor()

    def test_b11_executor_empty_command(self) -> None:
        receipt = self.executor.execute("")
        self.assertEqual(receipt.exit_code, 0)

    def test_b11_executor_command_with_quotes_and_spaces(self) -> None:
        cmd = f'{sys.executable} -c "msg = \'hello \\"world\\"\'; print(msg)"'
        receipt = self.executor.execute(cmd)
        self.assertEqual(receipt.status, "SUCCESS")
        self.assertIn('hello "world"', receipt.stdout)

    def test_b11_executor_non_zero_exit_code_255(self) -> None:
        cmd = f'{sys.executable} -c "import sys; sys.exit(255)"'
        receipt = self.executor.execute(cmd)
        self.assertEqual(receipt.exit_code, 255)
        self.assertEqual(receipt.status, "FAILED")

    def test_b11_executor_stdout_stderr_interleaving(self) -> None:
        code = "import sys; print('OUT1'); sys.stderr.write('ERR1\\n'); print('OUT2')"
        cmd = f'{sys.executable} -c "{code}"'
        receipt = self.executor.execute(cmd)
        self.assertIn("OUT1", receipt.stdout)
        self.assertIn("OUT2", receipt.stdout)
        self.assertIn("ERR1", receipt.stderr)

    def test_b11_executor_long_running_killed_cleanly(self) -> None:
        code = 'import time; time.sleep(2.0)'
        cmd = f'{sys.executable} -c "{code}"'
        receipt = self.executor.execute(cmd, timeout_s=0.1)
        self.assertEqual(receipt.exit_code, 124)
        self.assertEqual(receipt.status, "FAILED")


# ===========================================================================
# Feature 12 Boundary Cases: Safety Failsafes
# ===========================================================================

class TestFeature12SafetyFailsafesBoundaries(unittest.TestCase):
    """Boundary conditions for failsafes (mouse corner 10px, timeout, allowlist)."""

    def setUp(self) -> None:
        self.executor = LaptopActionExecutor()

    def test_b12_mouse_corner_exact_boundary_10px(self) -> None:
        # Exactly (10.0, 10.0) must abort
        with self.assertRaises(RuntimeError):
            self.executor.check_abort(mouse_pos=(10.0, 10.0))

    def test_b12_mouse_corner_exact_boundary_11px(self) -> None:
        # (11.0, 10.0) is outside corner -> must not abort
        self.executor.check_abort(mouse_pos=(11.0, 10.0))
        self.executor.check_abort(mouse_pos=(10.0, 11.0))

    def test_b12_mouse_corner_negative_coordinates(self) -> None:
        # Negative coordinates (virtual multi-monitor offset) <= 10px must abort
        with self.assertRaises(RuntimeError):
            self.executor.check_abort(mouse_pos=(-5.0, 5.0))

    def test_b12_timeout_boundary_microsecond(self) -> None:
        code = 'import time; time.sleep(0.5)'
        cmd = f'{sys.executable} -c "{code}"'
        receipt = self.executor.execute(cmd, timeout_s=0.05)
        self.assertEqual(receipt.exit_code, 124)

    def test_b12_allowlist_prefix_match_requires_boundary(self) -> None:
        # Allowed prefixes: python, uv run, pytest, git status, etc.
        self.assertTrue(SafetyGate.is_allowed("python -V"))
        self.assertTrue(SafetyGate.is_allowed("pytest tests/"))
        # Unrecognized commands
        self.assertFalse(SafetyGate.is_allowed("rmdir /s /q temp"))


# ===========================================================================
# Feature 13 Boundary Cases: SafetyGate Destructive Action Blocking
# ===========================================================================

class TestFeature13SafetyGateBoundaries(unittest.TestCase):
    """Boundary conditions for SafetyGate destructive action blocking."""

    def test_b13_safety_gate_obfuscated_reset_hard(self) -> None:
        obfuscated = "git   reset   --hard   HEAD~2"
        is_dest, reason = SafetyGate.is_destructive(obfuscated)
        self.assertTrue(is_dest)
        self.assertIn("reset", reason)

    def test_b13_safety_gate_case_insensitive_git_reset(self) -> None:
        upper = "GIT RESET --HARD"
        is_dest, _ = SafetyGate.is_destructive(upper)
        self.assertTrue(is_dest)

    def test_b13_safety_gate_clean_flags_combination(self) -> None:
        self.assertTrue(SafetyGate.is_destructive("git clean -xdf")[0])
        self.assertTrue(SafetyGate.is_destructive("git clean -fdx")[0])

    def test_b13_safety_gate_drop_database_blocked(self) -> None:
        is_dest, _ = SafetyGate.is_destructive("DROP DATABASE production;")
        self.assertTrue(is_dest)

    def test_b13_safety_gate_safe_git_command_not_blocked(self) -> None:
        safe_commands = [
            "git status",
            "git status --porcelain",
            "git log -n 5",
            "git diff HEAD",
            "git show HEAD",
        ]
        for cmd in safe_commands:
            is_dest, _ = SafetyGate.is_destructive(cmd)
            self.assertFalse(is_dest, f"Safe command '{cmd}' should NOT be blocked")


if __name__ == "__main__":
    unittest.main()

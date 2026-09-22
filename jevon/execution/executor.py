"""Laptop action executor for JEVON.

Executes developer commands with subprocess isolation, step timeout,
mouse-corner failsafe, and SafetyGate destructive operation interception.
"""

from __future__ import annotations

import os
import subprocess
import time

from jevon.bridge.protocol import ActionReceipt
from jevon.decision.actions import DeveloperAction
from jevon.execution.allowlist import ABORT_CORNER_PX, STEP_TIMEOUT_SECONDS
from jevon.execution.safety_gate import SafetyGate


class LaptopActionExecutor:
    """Executes developer commands with subprocess isolation, timeout, and corner abort."""

    def __init__(self, working_directory: str | None = None) -> None:
        self.working_directory = working_directory or os.getcwd()
        self.safety_gate = SafetyGate()

    def check_abort(self, mouse_pos: tuple[float, float] | None = None) -> None:
        """Check emergency mouse-corner stop (10px)."""
        if mouse_pos:
            x, y = mouse_pos
            if x <= ABORT_CORNER_PX and y <= ABORT_CORNER_PX:
                raise RuntimeError("Abort: Emergency mouse-corner stop triggered (<10px)")

    def execute(
        self,
        command_str: str,
        timeout_s: float = STEP_TIMEOUT_SECONDS,
        mouse_pos: tuple[float, float] | None = None,
        confirmed: bool = False,
    ) -> ActionReceipt:
        """Execute a shell/terminal command safely within the target workspace."""
        t0 = time.perf_counter_ns()
        self.check_abort(mouse_pos)

        # Safety Gate Check
        destructive, reason = self.safety_gate.is_destructive(command_str)
        if destructive and not confirmed:
            duration_ns = time.perf_counter_ns() - t0
            return ActionReceipt(
                command_id="cmd_blocked",
                session_id="",
                step_index=0,
                action=DeveloperAction.REQUEST_CONFIRMATION,
                status="BLOCKED_BY_SAFETY",
                exit_code=126,
                stdout="",
                stderr=f"Action blocked by SafetyGate: {reason}",
                verification_passed=False,
                verification_details={"reason": reason, "blocked": True},
                duration_ns=duration_ns,
            )

        # Subprocess Execution
        try:
            res = subprocess.run(
                command_str,
                shell=True,
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            duration_ns = time.perf_counter_ns() - t0
            status = "SUCCESS" if res.returncode == 0 else "FAILED"
            return ActionReceipt(
                command_id="cmd_exec",
                session_id="",
                step_index=0,
                action=DeveloperAction.RERUN_BUILD,
                status=status,
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                verification_passed=(res.returncode == 0),
                verification_details={"exit_code": res.returncode},
                duration_ns=duration_ns,
            )
        except subprocess.TimeoutExpired:
            duration_ns = time.perf_counter_ns() - t0
            return ActionReceipt(
                command_id="cmd_timeout",
                session_id="",
                step_index=0,
                action=DeveloperAction.RERUN_BUILD,
                status="FAILED",
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {timeout_s}s",
                verification_passed=False,
                verification_details={"timeout": True},
                duration_ns=duration_ns,
            )
        except RuntimeError as e:
            duration_ns = time.perf_counter_ns() - t0
            return ActionReceipt(
                command_id="cmd_aborted",
                session_id="",
                step_index=0,
                action=DeveloperAction.RERUN_BUILD,
                status="ABORTED",
                exit_code=130,
                stdout="",
                stderr=str(e),
                verification_passed=False,
                verification_details={"aborted": True},
                duration_ns=duration_ns,
            )

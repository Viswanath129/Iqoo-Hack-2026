"""Comprehensive pytest test suite for JEVON Execution Layer.

Covers:
- SafetyGate: destructive patterns, allowlist prefixes, safe vs dangerous commands
- LaptopActionExecutor: corner abort failsafe, subprocess isolation, timeouts, safety blocking, confirmation
- ActionReceipt: protocol serialization/deserialization round-trips and status invariants
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from jevon.bridge.protocol import ActionReceipt
from jevon.decision.actions import DeveloperAction
from jevon.execution.allowlist import (
    ABORT_CORNER_PX,
    ALLOWED_COMMAND_PREFIXES,
    STEP_TIMEOUT_SECONDS,
)
from jevon.execution.executor import LaptopActionExecutor
from jevon.execution.safety_gate import DESTRUCTIVE_PATTERNS, SafetyGate


# ============================================================================
# 1. SafetyGate: Destructive Patterns
# ============================================================================

def test_safety_gate_git_reset_hard() -> None:
    """Git reset --hard in various forms must be recognized as destructive."""
    for cmd in ["git reset --hard", "git reset --hard HEAD~1", "GIT RESET --HARD", "git   reset   --hard"]:
        is_dest, reason = SafetyGate.is_destructive(cmd)
        assert is_dest is True and "git" in reason.lower()


def test_safety_gate_git_clean_flags() -> None:
    """Git clean with force flags must be recognized as destructive."""
    for cmd in ["git clean -f", "git clean -fd", "git clean -df", "GIT CLEAN -FD"]:
        is_dest, reason = SafetyGate.is_destructive(cmd)
        assert is_dest is True and "clean" in reason.lower()


def test_safety_gate_rm_rf_root_and_wildcard() -> None:
    """Recursive root or wildcard deletion must be flagged destructive."""
    for cmd in ["rm -rf /", "rm -rf *", "rm -fr /", "rm -rf C:\\", "RM -RF /"]:
        is_dest, _ = SafetyGate.is_destructive(cmd)
        assert is_dest is True


def test_safety_gate_rmdir_and_del_flags() -> None:
    """Windows rmdir /s /q and del /f /q must be flagged as destructive."""
    destructive_cmds = [
        "rmdir /s /q target_dir", "rmdir /S /Q C:\\build", "RMDIR /s /q .",
        "del /f /q *.*", "del /F /Q files", "DEL /f /q temp.log",
    ]
    for cmd in destructive_cmds:
        is_dest, _ = SafetyGate.is_destructive(cmd)
        assert is_dest is True


def test_safety_gate_sensitive_files_and_keys() -> None:
    """Accessing .env configuration files, keys, credentials must be flagged destructive."""
    sensitive_cmds = [
        "cat .env", "type .env", "echo SECRET=1 > .env", "cat '.env'", 'cat ".env"',
        "cat credentials", "type credentials.json", "cat ~/.ssh/id_rsa", "cat cert.pem",
    ]
    for cmd in sensitive_cmds:
        is_dest, _ = SafetyGate.is_destructive(cmd)
        assert is_dest is True


def test_safety_gate_drop_database() -> None:
    """Drop database commands must be flagged destructive."""
    for cmd in ["drop database test_db", "DROP DATABASE production;", "drop   database mydb"]:
        is_dest, _ = SafetyGate.is_destructive(cmd)
        assert is_dest is True


def test_safety_gate_safe_commands_return_false() -> None:
    """Benign development commands must not be flagged as destructive."""
    safe_cmds = [
        "git status", "git diff", "git log -n 5", "git reset --soft HEAD~1",
        "git clean -n", "pytest tests/", "python app.py", "cargo test", "npm test",
        "echo environment", "echo hello world",
    ]
    for cmd in safe_cmds:
        is_dest, reason = SafetyGate.is_destructive(cmd)
        assert is_dest is False and reason == ""


def test_safety_gate_empty_and_whitespace() -> None:
    """Empty or whitespace-only commands must return False."""
    for cmd in ["", "   ", "\t\n"]:
        is_dest, reason = SafetyGate.is_destructive(cmd)
        assert is_dest is False and reason == ""


# ============================================================================
# 2. SafetyGate: Allowlist Prefixes
# ============================================================================

@pytest.mark.parametrize("prefix", ALLOWED_COMMAND_PREFIXES)
def test_safety_gate_is_allowed_prefixes(prefix: str) -> None:
    """Every configured prefix in ALLOWED_COMMAND_PREFIXES must return True."""
    assert SafetyGate.is_allowed(f"{prefix} arg1 arg2") is True


def test_safety_gate_is_allowed_strips_whitespace() -> None:
    """Leading and trailing whitespace must be ignored when checking allowlist."""
    assert SafetyGate.is_allowed("   python main.py   ") is True
    assert SafetyGate.is_allowed("\tpytest tests\n") is True


def test_safety_gate_is_allowed_rejects_unlisted() -> None:
    """Commands not starting with an allowed prefix must return False."""
    for cmd in ["curl http://example.com", "bash deploy.sh", "sh run.sh", "sudo reboot"]:
        assert SafetyGate.is_allowed(cmd) is False


def test_safety_gate_is_allowed_empty_string() -> None:
    """Empty strings must not be allowed."""
    assert SafetyGate.is_allowed("") is False
    assert SafetyGate.is_allowed("   ") is False


# ============================================================================
# 3. LaptopActionExecutor: Initialization & Emergency Corner Abort
# ============================================================================

def test_executor_init(tmp_path) -> None:
    """Executor initializes with default and custom working directory, and SafetyGate."""
    default_exec = LaptopActionExecutor()
    assert default_exec.working_directory == os.getcwd()
    assert isinstance(default_exec.safety_gate, SafetyGate)

    custom_exec = LaptopActionExecutor(working_directory=str(tmp_path))
    assert custom_exec.working_directory == str(tmp_path)


@pytest.mark.parametrize("pos", [(0.0, 0.0), (5.0, 5.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)])
def test_check_abort_inside_corner_raises(pos: tuple[float, float]) -> None:
    """Mouse within ABORT_CORNER_PX (10px) must raise RuntimeError."""
    with pytest.raises(RuntimeError, match="Emergency mouse-corner stop"):
        LaptopActionExecutor().check_abort(pos)


@pytest.mark.parametrize("pos", [(10.1, 5.0), (5.0, 10.1), (11.0, 11.0), (500.0, 500.0), None])
def test_check_abort_outside_corner_passes(pos: tuple[float, float] | None) -> None:
    """Mouse coordinates outside corner threshold or None must not raise."""
    LaptopActionExecutor().check_abort(pos)


def test_execute_corner_abort_raises_error() -> None:
    """Executing with mouse in abort corner raises RuntimeError before execution."""
    with pytest.raises(RuntimeError, match="Emergency mouse-corner stop"):
        LaptopActionExecutor().execute("echo test", mouse_pos=(2.0, 2.0))


# ============================================================================
# 4. LaptopActionExecutor: Execution Happy Path & Exit Codes
# ============================================================================

def test_execute_success_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safe echo command must execute successfully and return a valid ActionReceipt."""
    mock_run = MagicMock(
        return_value=subprocess.CompletedProcess(
            args="echo hello_jevon", returncode=0, stdout="hello_jevon\n", stderr=""
        )
    )
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("echo hello_jevon")
    assert receipt.status == "SUCCESS"
    assert receipt.exit_code == 0
    assert "hello_jevon" in receipt.stdout
    assert receipt.verification_passed is True
    assert receipt.action == DeveloperAction.RERUN_BUILD
    assert receipt.duration_ns >= 0


def test_execute_failure_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero exit code must produce FAILED status and verification_passed=False."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="pytest", returncode=1, stdout="", stderr="error"))
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("pytest")
    assert receipt.status == "FAILED" and receipt.exit_code == 1
    assert receipt.verification_passed is False
    assert receipt.verification_details == {"exit_code": 1}


def test_execute_captures_stdout_and_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Standard output and standard error streams must be captured on the receipt."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="cmd", returncode=0, stdout="out\n", stderr="err\n"))
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("cmd")
    assert receipt.stdout == "out\n" and receipt.stderr == "err\n"


def test_execute_forwards_working_directory_and_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Subprocess must receive custom working directory and timeout parameters."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="py", returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(subprocess, "run", mock_run)
    LaptopActionExecutor(working_directory=str(tmp_path)).execute("py", timeout_s=12.5)
    assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)
    assert mock_run.call_args.kwargs["timeout"] == 12.5


# ============================================================================
# 5. LaptopActionExecutor: Safety Gate Interception & Confirmation
# ============================================================================

def test_execute_destructive_blocked_without_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Destructive command without confirmation must return BLOCKED_BY_SAFETY receipt."""
    mock_run = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("git reset --hard", confirmed=False)

    assert receipt.status == "BLOCKED_BY_SAFETY"
    assert receipt.exit_code == 126
    assert receipt.action == DeveloperAction.REQUEST_CONFIRMATION
    assert receipt.verification_passed is False
    assert receipt.verification_details["blocked"] is True
    mock_run.assert_not_called()


def test_execute_destructive_allowed_when_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Destructive command with confirmed=True bypasses safety gate to execute."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="git reset", returncode=0, stdout="HEAD reset", stderr=""))
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("git reset --hard", confirmed=True)

    assert receipt.status == "SUCCESS"
    assert receipt.command_id == "cmd_exec"
    mock_run.assert_called_once()


def test_execute_non_destructive_ignores_confirmed_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-destructive commands execute regardless of confirmed=False."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="git status", returncode=0, stdout="clean", stderr=""))
    monkeypatch.setattr(subprocess, "run", mock_run)
    receipt = LaptopActionExecutor().execute("git status", confirmed=False)
    assert receipt.status == "SUCCESS"
    mock_run.assert_called_once()


# ============================================================================
# 6. LaptopActionExecutor: Timeouts and Runtime Aborts
# ============================================================================

def test_execute_timeout_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """TimeoutExpired must be caught and returned as FAILED receipt with exit code 124."""
    def mock_timeout(*_, **__):
        raise subprocess.TimeoutExpired(cmd="python slow.py", timeout=5.0)

    monkeypatch.setattr(subprocess, "run", mock_timeout)
    receipt = LaptopActionExecutor().execute("python slow.py", timeout_s=5.0)

    assert receipt.status == "FAILED"
    assert receipt.exit_code == 124
    assert receipt.command_id == "cmd_timeout"
    assert receipt.verification_details == {"timeout": True}
    assert "Command timed out after 5.0s" in receipt.stderr


def test_execute_runtime_error_in_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """RuntimeError during execution must be caught and returned as ABORTED receipt."""
    def mock_runtime_error(*_, **__):
        raise RuntimeError("Process interrupted by OS signal")

    monkeypatch.setattr(subprocess, "run", mock_runtime_error)
    receipt = LaptopActionExecutor().execute("pytest tests/")

    assert receipt.status == "ABORTED"
    assert receipt.exit_code == 130
    assert receipt.command_id == "cmd_aborted"
    assert receipt.verification_details == {"aborted": True}
    assert "Process interrupted by OS signal" in receipt.stderr


# ============================================================================
# 7. ActionReceipt: Serialization, Invariants, and Properties
# ============================================================================

def test_action_receipt_serialization_roundtrips() -> None:
    """ActionReceipt serialization to dict and JSON roundtrips must preserve all fields."""
    receipt = ActionReceipt(
        command_id="cmd_test_123",
        session_id="session_abc",
        step_index=4,
        action=DeveloperAction.RERUN_BUILD,
        status="SUCCESS",
        exit_code=0,
        stdout="tests passed",
        stderr="",
        verification_passed=True,
        verification_details={"passed": 10},
        duration_ns=15_000_000,
    )
    assert ActionReceipt.from_dict(receipt.to_dict()) == receipt
    assert ActionReceipt.from_json(receipt.to_json()) == receipt


def test_action_receipt_validations() -> None:
    """is_valid verifies command_id and status; invalid status raises ValueError."""
    receipt = ActionReceipt(
        command_id="cmd_valid",
        session_id="",
        step_index=0,
        action=DeveloperAction.DONE,
        status="SUCCESS",
        exit_code=0,
        stdout="",
        stderr="",
        verification_passed=True,
    )
    assert receipt.is_valid() is True

    with pytest.raises(ValueError, match="Invalid status 'PENDING'"):
        ActionReceipt(
            command_id="cmd_inv",
            session_id="",
            step_index=0,
            action=DeveloperAction.DONE,
            status="PENDING",
            exit_code=0,
            stdout="",
            stderr="",
            verification_passed=True,
        )


def test_action_receipt_string_action_and_immutability() -> None:
    """String action is coerced to DeveloperAction; mutation raises FrozenInstanceError."""
    receipt = ActionReceipt(
        command_id="cmd_str_act",
        session_id="",
        step_index=0,
        action="apply_fix",  # type: ignore[arg-type]
        status="SUCCESS",
        exit_code=0,
        stdout="",
        stderr="",
        verification_passed=True,
    )
    assert isinstance(receipt.action, DeveloperAction)
    assert receipt.action == DeveloperAction.APPLY_FIX

    with pytest.raises(FrozenInstanceError):
        receipt.exit_code = 1  # type: ignore[misc]


# ============================================================================
# 8. Property-based and Constants Invariants
# ============================================================================

def test_execution_duration_ns_non_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duration in nanoseconds must be >= 0 for all execution pathways."""
    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args="echo", returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(subprocess, "run", mock_run)
    executor = LaptopActionExecutor()
    assert executor.execute("git reset --hard").duration_ns >= 0
    assert executor.execute("echo test").duration_ns >= 0


def test_destructive_patterns_are_compiled_regex() -> None:
    """Every pattern in DESTRUCTIVE_PATTERNS must be a compiled re.Pattern with IGNORECASE."""
    assert len(DESTRUCTIVE_PATTERNS) >= 7
    for pattern in DESTRUCTIVE_PATTERNS:
        assert isinstance(pattern, re.Pattern)
        assert bool(pattern.flags & re.IGNORECASE)


def test_allowlist_and_abort_constants() -> None:
    """Execution bounds constants must match design specifications."""
    assert ABORT_CORNER_PX == 10
    assert STEP_TIMEOUT_SECONDS == 30
    assert len(ALLOWED_COMMAND_PREFIXES) >= 10

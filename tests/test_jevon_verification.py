"""Comprehensive unit and boundary tests for JEVON Verification Engine and Telemetry Metrics."""

from __future__ import annotations

import ast
import pytest

from jevon.telemetry.metrics import MicroBenchmarkMetrics
from jevon.verification.engine import VerificationEngine, VerificationOutcome


# ============================================================================
# 1. VerificationOutcome Tests
# ============================================================================

def test_verification_outcome_creation_and_defaults() -> None:
    """VerificationOutcome stores passed status and defaults checks/details to independent dicts."""
    outcome1 = VerificationOutcome(passed=True)
    outcome2 = VerificationOutcome(passed=False, checks={"c": True}, details={"d": 1})
    assert outcome1.passed is True
    assert outcome1.checks == {} and outcome1.details == {}
    outcome1.checks["x"] = True
    assert "x" not in outcome2.checks
    assert outcome2.passed is False
    assert outcome2.checks == {"c": True} and outcome2.details == {"d": 1}


def test_verification_outcome_equality() -> None:
    """VerificationOutcome instances with identical values compare equal."""
    o1 = VerificationOutcome(passed=True, checks={"a": True}, details={"k": "v"})
    o2 = VerificationOutcome(passed=True, checks={"a": True}, details={"k": "v"})
    assert o1 == o2


# ============================================================================
# 2. VerificationEngine.verify_exit_code Tests
# ============================================================================

def test_verify_exit_code_zero() -> None:
    """verify_exit_code returns True only when exit_code is exactly 0."""
    engine = VerificationEngine()
    assert engine.verify_exit_code(0) is True


def test_verify_exit_code_nonzero_and_negative() -> None:
    """verify_exit_code returns False for nonzero positive, negative, and large integers."""
    engine = VerificationEngine()
    for code in (1, 2, 42, 127, 255, 65535, -1, -9, -15, -32768):
        assert engine.verify_exit_code(code) is False


# ============================================================================
# 3. VerificationEngine.verify_regex Tests
# ============================================================================

def test_verify_regex_matching_and_substring() -> None:
    """verify_regex matches full text as well as substrings within output."""
    engine = VerificationEngine()
    text = "Build successful: 5 tests passed in 0.12s"
    assert engine.verify_regex(text, r"5 tests passed") is True
    assert engine.verify_regex(text, r"Build successful: 5 tests passed in 0.12s") is True


def test_verify_regex_non_matching() -> None:
    """verify_regex returns False when target pattern is not present."""
    engine = VerificationEngine()
    assert engine.verify_regex("Build succeeded", r"FAILURE") is False
    assert engine.verify_regex("Passed 5", r"\d+ failed") is False


def test_verify_regex_complex_patterns_and_special_chars() -> None:
    """verify_regex handles complex regex patterns with escaped characters and character classes."""
    engine = VerificationEngine()
    output = "[ERROR] (code=404): Resource not found at /api/v1/users"
    assert engine.verify_regex(output, r"\[ERROR\]\s+\(code=\d+\)") is True
    assert engine.verify_regex(output, r"/api/v[0-9]+/users") is True


def test_verify_regex_multiline() -> None:
    """verify_regex matches patterns spanning multiline output."""
    engine = VerificationEngine()
    text = "Traceback (most recent call last):\n  File 'app.py'\nKeyError: 'id'"
    assert engine.verify_regex(text, r"KeyError: 'id'") is True
    assert engine.verify_regex(text, r"Traceback.*") is True


def test_verify_regex_empty_and_case() -> None:
    """verify_regex handles empty patterns/text and respects case sensitivity."""
    engine = VerificationEngine()
    assert engine.verify_regex("output", "") is True
    assert engine.verify_regex("", "") is True
    assert engine.verify_regex("", r"\w+") is False
    assert engine.verify_regex("ALL PASSED", r"passed") is False
    assert engine.verify_regex("ALL PASSED", r"(?i)passed") is True


# ============================================================================
# 4. VerificationEngine.verify_ast_syntax Tests
# ============================================================================

def test_verify_ast_syntax_valid() -> None:
    """verify_ast_syntax returns (True, None) for valid Python code including modern constructs."""
    engine = VerificationEngine()
    code = "@decorator\nasync def fetch(urls: list[str]) -> int:\n    if (n := len(urls)) > 0:\n        return n\n    return 0\n"
    ok, err = engine.verify_ast_syntax(code)
    assert ok is True and err is None


def test_verify_ast_syntax_invalid_and_indentation() -> None:
    """verify_ast_syntax returns (False, err_msg) for unparseable syntax and indentation errors."""
    engine = VerificationEngine()
    ok_syn, err_syn = engine.verify_ast_syntax("def broken(\n    return 42\n")
    assert ok_syn is False and err_syn is not None
    ok_ind, err_ind = engine.verify_ast_syntax("def foo():\nreturn 1\n")
    assert ok_ind is False and err_ind is not None


def test_verify_ast_syntax_empty_and_whitespace() -> None:
    """verify_ast_syntax returns (True, None) for empty strings, whitespace, and comments."""
    engine = VerificationEngine()
    assert engine.verify_ast_syntax("") == (True, None)
    assert engine.verify_ast_syntax("   \n\t\n# Just a comment\n") == (True, None)


def test_verify_ast_syntax_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """verify_ast_syntax handles simulated SyntaxError exception via monkeypatch."""
    engine = VerificationEngine()
    monkeypatch.setattr(ast, "parse", lambda _: (_ for _ in ()).throw(SyntaxError("mock error")))
    ok, err = engine.verify_ast_syntax("x = 1")
    assert ok is False and "mock error" in str(err)


# ============================================================================
# 5. VerificationEngine.verify_error_eliminated Tests
# ============================================================================

def test_verify_error_eliminated_absent() -> None:
    """verify_error_eliminated returns True when the previous error string is absent."""
    engine = VerificationEngine()
    assert engine.verify_error_eliminated("All 10 tests passed", "TypeError: bad operand") is True


def test_verify_error_eliminated_present() -> None:
    """verify_error_eliminated returns False when the previous error persists in output."""
    engine = VerificationEngine()
    err = "AssertionError: expected 5 got 4"
    assert engine.verify_error_eliminated(f"Traceback:\n{err}\nFailed", err) is False


def test_verify_error_eliminated_empty_inputs() -> None:
    """verify_error_eliminated returns True when previous_error or output is empty/None."""
    engine = VerificationEngine()
    assert engine.verify_error_eliminated("output text", "") is True
    assert engine.verify_error_eliminated("", "SomeError") is True
    assert engine.verify_error_eliminated("", "") is True


def test_verify_error_eliminated_whitespace_and_boundary() -> None:
    """verify_error_eliminated strips whitespace and tests exact substring boundary."""
    engine = VerificationEngine()
    assert engine.verify_error_eliminated("Error: ValueError: bad val", "   ValueError: bad val   ") is False
    assert engine.verify_error_eliminated("KeyError: 'foo_bar'", "KeyError: 'foo'") is True


# ============================================================================
# 6. VerificationEngine.verify Composite Tests
# ============================================================================

def test_verify_all_checks_pass() -> None:
    """verify returns passed=True when all configured checks succeed."""
    engine = VerificationEngine()
    outcome = engine.verify(
        exit_code=0, stdout="3 passed in 0.05s", stderr="",
        expected_regex=r"\d+ passed", source_code="a = 1 + 2\n",
        previous_error="ZeroDivisionError",
    )
    assert outcome.passed is True
    assert outcome.checks == {
        "exit_code_zero": True, "regex_matched": True,
        "ast_valid": True, "error_eliminated": True,
    }
    assert outcome.details == {}


def test_verify_exit_code_failure() -> None:
    """verify returns passed=False if exit_code is nonzero despite other checks passing."""
    engine = VerificationEngine()
    outcome = engine.verify(exit_code=1, stdout="3 passed in 0.05s", stderr="", expected_regex=r"\d+ passed")
    assert outcome.passed is False
    assert outcome.checks["exit_code_zero"] is False
    assert outcome.checks["regex_matched"] is True


def test_verify_regex_failure() -> None:
    """verify returns passed=False if expected regex is not matched."""
    engine = VerificationEngine()
    outcome = engine.verify(exit_code=0, stdout="0 passed, 2 failed", stderr="", expected_regex=r"ALL PASSED")
    assert outcome.passed is False
    assert outcome.checks["regex_matched"] is False


def test_verify_ast_failure() -> None:
    """verify records ast_valid=False and populates details['ast_error'] on invalid syntax."""
    engine = VerificationEngine()
    outcome = engine.verify(exit_code=0, stdout="ok", stderr="", source_code="def broken(")
    assert outcome.passed is False
    assert outcome.checks["ast_valid"] is False
    assert "ast_error" in outcome.details


def test_verify_error_not_eliminated() -> None:
    """verify returns passed=False if previous error still appears in output."""
    engine = VerificationEngine()
    prev = "AttributeError: 'NoneType' object"
    outcome = engine.verify(exit_code=0, stdout="", stderr=f"Log: {prev}", previous_error=prev)
    assert outcome.passed is False
    assert outcome.checks["error_eliminated"] is False


def test_verify_combinations_multiple_failures() -> None:
    """verify records individual check states when multiple checks fail simultaneously."""
    engine = VerificationEngine()
    outcome = engine.verify(
        exit_code=137, stdout="Killed", stderr="MemoryError",
        expected_regex=r"SUCCESS", source_code="invalid syntax ::::",
        previous_error="MemoryError",
    )
    assert outcome.passed is False
    assert outcome.checks == {
        "exit_code_zero": False, "regex_matched": False,
        "ast_valid": False, "error_eliminated": False,
    }
    assert "ast_error" in outcome.details


def test_verify_minimal_invocation() -> None:
    """verify with only exit_code and stream outputs evaluates only exit_code_zero."""
    engine = VerificationEngine()
    outcome = engine.verify(exit_code=0, stdout="clean", stderr="")
    assert outcome.passed is True
    assert outcome.checks == {"exit_code_zero": True}
    assert outcome.details == {}


def test_verify_combined_stdout_and_stderr() -> None:
    """verify matches regex and detects previous errors across combined stdout and stderr."""
    engine = VerificationEngine()
    out1 = engine.verify(exit_code=0, stdout="out", stderr="warn: matched_target", expected_regex=r"matched_target")
    assert out1.passed is True and out1.checks["regex_matched"] is True

    out2 = engine.verify(exit_code=0, stdout="clean out", stderr="Fatal: old_error", previous_error="old_error")
    assert out2.passed is False and out2.checks["error_eliminated"] is False


def test_verify_ast_valid_details_clean() -> None:
    """verify does not populate ast_error in details when source code syntax is valid."""
    engine = VerificationEngine()
    outcome = engine.verify(exit_code=0, stdout="ok", stderr="", source_code="x: int = 10\n")
    assert outcome.passed is True
    assert outcome.checks["ast_valid"] is True
    assert "ast_error" not in outcome.details


# ============================================================================
# 7. MicroBenchmarkMetrics Tests
# ============================================================================

def test_metrics_default_zeros() -> None:
    """MicroBenchmarkMetrics defaults all stage latencies to 0 and computes 0 total latency."""
    m = MicroBenchmarkMetrics()
    assert (
        m.perception_ns == m.local_inference_ns == m.decision_ns
        == m.bridge_out_ns == m.action_exec_ns == m.verification_ns
        == m.bridge_in_ns == m.total_latency_ns == 0
    )
    assert m.total_latency_ms == 0.0


def test_metrics_custom_values() -> None:
    """MicroBenchmarkMetrics initializes all 7 stages with explicit custom values."""
    m = MicroBenchmarkMetrics(
        perception_ns=10, local_inference_ns=20, decision_ns=30,
        bridge_out_ns=40, action_exec_ns=50, verification_ns=60, bridge_in_ns=70,
    )
    assert (
        m.perception_ns, m.local_inference_ns, m.decision_ns,
        m.bridge_out_ns, m.action_exec_ns, m.verification_ns, m.bridge_in_ns
    ) == (10, 20, 30, 40, 50, 60, 70)


def test_metrics_total_latency_ns_computation() -> None:
    """total_latency_ns correctly sums nanoseconds across all 7 stages."""
    m = MicroBenchmarkMetrics(
        perception_ns=100, local_inference_ns=200, decision_ns=300,
        bridge_out_ns=400, action_exec_ns=500, verification_ns=600, bridge_in_ns=700,
    )
    assert m.total_latency_ns == 2800


def test_metrics_total_latency_ms_computation() -> None:
    """total_latency_ms accurately converts nanosecond total to milliseconds."""
    m = MicroBenchmarkMetrics(action_exec_ns=1_500_000)
    assert m.total_latency_ms == 1.5


def test_metrics_single_stage_set() -> None:
    """MicroBenchmarkMetrics computes total latency with only one stage populated."""
    m = MicroBenchmarkMetrics(decision_ns=500_000)
    assert m.total_latency_ns == 500_000
    assert m.total_latency_ms == 0.5
    assert m.perception_ns == 0


def test_metrics_all_stages_set() -> None:
    """MicroBenchmarkMetrics computes accurate cumulative latencies when all stages are set."""
    m = MicroBenchmarkMetrics(
        perception_ns=1_000_000, local_inference_ns=2_000_000, decision_ns=3_000_000,
        bridge_out_ns=4_000_000, action_exec_ns=5_000_000, verification_ns=6_000_000,
        bridge_in_ns=7_000_000,
    )
    assert m.total_latency_ns == 28_000_000
    assert m.total_latency_ms == 28.0


def test_metrics_to_dict_keys_and_values() -> None:
    """to_dict returns a dict with 8 keys (7 stages + total_latency_ns)."""
    m = MicroBenchmarkMetrics(
        perception_ns=1, local_inference_ns=2, decision_ns=3,
        bridge_out_ns=4, action_exec_ns=5, verification_ns=6, bridge_in_ns=7,
    )
    assert m.to_dict() == {
        "perception_ns": 1, "local_inference_ns": 2, "decision_ns": 3,
        "bridge_out_ns": 4, "action_exec_ns": 5, "verification_ns": 6,
        "bridge_in_ns": 7, "total_latency_ns": 28,
    }


def test_metrics_summary_ms_conversion() -> None:
    """summary_ms converts each nanosecond field to milliseconds."""
    m = MicroBenchmarkMetrics(perception_ns=1_000_000, action_exec_ns=2_500_000)
    summary = m.summary_ms()
    assert summary["perception_ns"] == 1.0
    assert summary["action_exec_ns"] == 2.5
    assert summary["decision_ns"] == 0.0
    assert summary["total_latency_ns"] == 3.5


def test_metrics_roundtrip_reconstruction() -> None:
    """Reconstructing MicroBenchmarkMetrics from to_dict values preserves state."""
    orig = MicroBenchmarkMetrics(
        perception_ns=11, local_inference_ns=22, decision_ns=33,
        bridge_out_ns=44, action_exec_ns=55, verification_ns=66, bridge_in_ns=77,
    )
    d = orig.to_dict()
    reconstructed = MicroBenchmarkMetrics(**{k: v for k, v in d.items() if k != "total_latency_ns"})
    assert reconstructed == orig
    assert reconstructed.total_latency_ns == orig.total_latency_ns


def test_metrics_dynamic_mutation() -> None:
    """Mutating stage latency fields dynamically updates total latency properties."""
    m = MicroBenchmarkMetrics()
    assert m.total_latency_ns == 0
    m.verification_ns = 5_000_000
    assert m.total_latency_ns == 5_000_000 and m.total_latency_ms == 5.0
    m.perception_ns = 2_000_000
    assert m.total_latency_ns == 7_000_000 and m.total_latency_ms == 7.0


def test_metrics_large_latency_precision() -> None:
    """MicroBenchmarkMetrics handles large nanosecond values without precision loss or overflow."""
    hour_ns = 3_600 * 1_000_000_000
    m = MicroBenchmarkMetrics(perception_ns=hour_ns, action_exec_ns=hour_ns * 2)
    assert m.total_latency_ns == 3 * hour_ns
    assert m.total_latency_ms == 3 * 3_600 * 1_000.0

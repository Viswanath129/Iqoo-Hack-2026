"""Adversarial and stress test suite for Milestone M1 (Core Decision Engine & Truth-First State Model).

Authored by challenger_1_m1 to empirically stress-test:
1. normalize_probabilities:
   - Extreme values, subnormal floats (denormals), all zeros, empty dicts, negative floats.
   - Float precision and summation invariance across 1000 randomized distributions.
   - [BUG EMPIRICALLY CONFIRMED] Infinity handling: passing float('inf') causes NaN propagation.
2. LocalDecisionProvider:
   - Chaotic and None-filled StateObservations.
   - Corrupted and negative exit codes (SIGKILL -9, segfault -11, 255, 65535).
   - Massive 1MB+ terminal outputs with noise and embedded traceback patterns.
   - 100-step randomized lifecycle simulation.
   - [BUG EMPIRICALLY CONFIRMED] Unhandled KeyError when state.decisions entry lacks 'action' key.
3. SafetyFallback:
   - Exact boundary conditions: 0.59999 (intercepted) vs 0.60000 (passes) vs 0.60001 (passes).
   - Oscillation thresholds (threshold=2 vs threshold=3).
   - DONE action exemption from loop detection.
   - [BUG EMPIRICALLY CONFIRMED] NaN confidence bypass: float('nan') is converted to 1.0, bypassing safety guards.
   - Oscillation threshold=1 slice bug: list[-0:] evaluates to list[0:], causing first action to be flagged as loop.
"""

import math
import random
import string
import sys

import pytest

from jevon.decision.actions import (
    DeveloperAction,
    DeveloperDecision,
    normalize_probabilities,
)
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.truth_first.state import TruthFirstState

# ============================================================================
# Section 1: normalize_probabilities Adversarial Tests
# ============================================================================

def test_normalize_empty_dict():
    """Empty dict must return uniform distribution summing to 1.0."""
    res = normalize_probabilities({})
    assert len(res) == 8
    assert all(a.value in res for a in DeveloperAction.all_actions())
    assert all(v == 0.125 for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_all_zeros():
    """Dict of all zeros must fallback to uniform distribution summing to 1.0."""
    res = normalize_probabilities({a: 0.0 for a in DeveloperAction.all_actions()})
    assert len(res) == 8
    assert all(v == 0.125 for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_all_negatives():
    """All negative values must be clamped to 0.0 and fallback to uniform 1.0 sum."""
    raw = {a.value: -random.uniform(0.1, 100.0) for a in DeveloperAction.all_actions()}
    res = normalize_probabilities(raw)
    assert len(res) == 8
    assert all(v == 0.125 for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_mixed_negative_and_positive():
    """Negative values must be clamped to 0.0, positive normalized to sum to 1.0."""
    raw = {
        DeveloperAction.INSPECT_ERROR: -10.0,
        DeveloperAction.INSPECT_FILE: -5.0,
        DeveloperAction.APPLY_FIX: 0.75,
        DeveloperAction.RUN_TARGETED_TEST: 0.25,
    }
    res = normalize_probabilities(raw)
    assert len(res) == 8
    assert res[DeveloperAction.INSPECT_ERROR.value] == 0.0
    assert res[DeveloperAction.INSPECT_FILE.value] == 0.0
    assert pytest.approx(res[DeveloperAction.APPLY_FIX.value], abs=1e-6) == 0.75
    assert pytest.approx(res[DeveloperAction.RUN_TARGETED_TEST.value], abs=1e-6) == 0.25
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_denormal_subnormals():
    """Floating point subnormals (denormals) must not cause divide-by-zero or crash."""
    denormal_small = sys.float_info.min * 1e-10  # roughly ~2e-318
    raw = {
        DeveloperAction.DONE: denormal_small,
        DeveloperAction.RERUN_BUILD: denormal_small,
    }
    res = normalize_probabilities(raw)
    assert len(res) == 8
    assert all(math.isfinite(v) for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_extremely_large_numbers():
    """Extreme float values near float_info.max must not crash."""
    huge = 1e308
    raw = {
        DeveloperAction.DONE: huge,
        DeveloperAction.RERUN_BUILD: huge,
    }
    res = normalize_probabilities(raw)
    assert len(res) == 8
    assert all(math.isfinite(v) for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_nan_input_handling():
    """NaN in input probabilities: single/mixed NaN is clamped to 0.0, all-NaN falls back to uniform."""
    # Case A: all-NaN input falls back to uniform
    raw_all_nan = {a: float("nan") for a in DeveloperAction.all_actions()}
    res_all_nan = normalize_probabilities(raw_all_nan)
    assert len(res_all_nan) == 8
    assert all(math.isfinite(v) for v in res_all_nan.values())
    assert all(v == 0.125 for v in res_all_nan.values())
    assert math.isclose(sum(res_all_nan.values()), 1.0, abs_tol=1e-12)

    # Case B: mixed NaN is clamped to 0.0 while valid probability is normalized
    raw_mixed = {
        DeveloperAction.DONE: float("nan"),
        DeveloperAction.RERUN_BUILD: 1.0,
    }
    res_mixed = normalize_probabilities(raw_mixed)
    assert len(res_mixed) == 8
    assert res_mixed[DeveloperAction.DONE.value] == 0.0
    assert res_mixed[DeveloperAction.RERUN_BUILD.value] == 1.0
    assert math.isclose(sum(res_mixed.values()), 1.0, abs_tol=1e-12)


def test_normalize_infinity_bug_reproduction():
    """[REMEDIATED] float('inf') falls back to uniform distribution and does not propagate NaN.
    
    Because `math.isinf(total)` is checked in:
        `if math.isnan(total) or math.isinf(total) or total <= 0.0:`
    `total == inf` safely triggers uniform fallback where all probabilities are finite and sum to 1.0.
    """
    raw = {
        DeveloperAction.DONE: float("inf"),
        DeveloperAction.RERUN_BUILD: 1.0,
    }
    res = normalize_probabilities(raw)
    nan_keys = [k for k, v in res.items() if math.isnan(v)]
    assert len(nan_keys) == 0, "No NaN values should propagate"
    assert all(math.isfinite(v) for v in res.values())
    assert all(v == 0.125 for v in res.values())
    assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


def test_normalize_fuzzing_random_distributions():
    """Fuzz 1,000 random distributions: probabilities sum to 1.0 within floating point tolerance."""
    actions = DeveloperAction.all_actions()
    rng = random.Random(42)

    for _ in range(1000):
        raw = {}
        for a in actions:
            coin = rng.random()
            if coin < 0.2:
                raw[a] = 0.0
            elif coin < 0.4:
                raw[a] = -rng.uniform(0.01, 100.0)
            elif coin < 0.8:
                raw[a] = rng.uniform(0.001, 10.0)
            elif coin < 0.9:
                raw[a] = rng.uniform(1e10, 1e20)
            else:
                raw[a] = rng.uniform(1e-20, 1e-10)

        res = normalize_probabilities(raw)
        assert len(res) == 8
        assert all(v >= 0.0 for v in res.values())
        # In IEEE 754, sum matches 1.0 within 1 ULP (1e-12)
        assert math.isclose(sum(res.values()), 1.0, abs_tol=1e-12)


# ============================================================================
# Section 2: LocalDecisionProvider Fuzzing & Stress Tests
# ============================================================================

def test_local_provider_all_none_observation():
    """LocalDecisionProvider must not crash when every optional field is None."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Test resilience")
    obs = StateObservation(
        session_id="",
        step_index=0,
        working_directory="",
        active_file=None,
        terminal_output="",
        compiler_exit_code=None,
        git_status_summary="",
        recent_error=None,
        metadata={},
    )
    decision = provider.decide(state, obs)
    assert decision.action in DeveloperAction.all_actions()
    assert 0.0 <= decision.confidence <= 1.0
    assert math.isclose(sum(decision.probabilities.values()), 1.0, abs_tol=1e-12)


def test_local_provider_corrupted_exit_codes():
    """LocalDecisionProvider must handle negative, extreme, and POSIX signal exit codes."""
    provider = LocalDecisionProvider()
    state = TruthFirstState()

    weird_codes = [-1, -9, -11, 137, 255, 65535, -2147483648]
    for code in weird_codes:
        obs = StateObservation(
            compiler_exit_code=code,
            recent_error=f"Process killed with exit code {code}",
        )
        dec = provider.decide(state, obs)
        assert dec.action == DeveloperAction.INSPECT_ERROR
        assert dec.confidence >= 0.80
        assert math.isclose(sum(dec.probabilities.values()), 1.0, abs_tol=1e-12)


def test_local_provider_massive_terminal_log_fuzzing():
    """LocalDecisionProvider must handle megabyte-scale chaotic terminal logs without crashing or regex hanging."""
    provider = LocalDecisionProvider()
    state = TruthFirstState()

    noise_chars = string.ascii_letters + string.digits + " \t\n\r/\\:.-_!@#$%^&*()[]{}<>"
    random_noise = "".join(random.choices(noise_chars, k=500_000))
    trace = '\nFile "corrupted/path/deep_file.py", line 428\n'
    tail_noise = "".join(random.choices(noise_chars, k=500_000))

    giant_terminal = random_noise + trace + tail_noise

    obs = StateObservation(
        compiler_exit_code=1,
        terminal_output=giant_terminal,
        recent_error="Massive crash dump",
    )

    dec = provider.decide(state, obs)
    assert dec.action in DeveloperAction.all_actions()
    assert math.isclose(sum(dec.probabilities.values()), 1.0, abs_tol=1e-12)


def test_local_provider_regex_path_extraction_heuristics():
    """Culprit extractor must extract paths accurately across Python, Pytest, and generic path:line formats."""
    provider = LocalDecisionProvider()
    state = TruthFirstState()
    state.record_decision(DeveloperAction.INSPECT_ERROR)

    # Format 1: Python traceback
    obs1 = StateObservation(
        compiler_exit_code=1,
        terminal_output='Traceback (most recent call last):\n  File "jevon/decision/actions.py", line 42, in test\n',
    )
    dec1 = provider.decide(state, obs1)
    assert dec1.action == DeveloperAction.INSPECT_FILE
    assert dec1.parameters["target_file"] == "jevon/decision/actions.py"

    # Format 2: Pytest FAILED line
    obs2 = StateObservation(
        compiler_exit_code=1,
        terminal_output="FAILED tests/test_actions.py::test_foo - AssertionError",
    )
    dec2 = provider.decide(state, obs2)
    assert dec2.action == DeveloperAction.INSPECT_FILE
    assert dec2.parameters["target_file"] == "tests/test_actions.py"

    # Format 3: Generic path:line
    obs3 = StateObservation(
        compiler_exit_code=1,
        terminal_output="error in src/engine/core.rs:182: syntax error",
    )
    dec3 = provider.decide(state, obs3)
    assert dec3.action == DeveloperAction.INSPECT_FILE
    assert dec3.parameters["target_file"] == "src/engine/core.rs"


def test_local_provider_fuzz_transition_sequences():
    """Execute a 100-step randomized lifecycle through LocalDecisionProvider. Must not raise unhandled exception."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fuzz lifecycle test")
    rng = random.Random(123)

    for step in range(100):
        exit_code = rng.choice([0, 1, 2, None, -9])
        recent_error = rng.choice([None, "IndexError: out of range", "SyntaxError", ""])
        active_file = rng.choice([None, "src/lib.py", "tests/test_foo.py"])
        terminal_out = rng.choice(["200 passed", "FAILED test", "Building...", ""])

        obs = StateObservation(
            session_id="fuzz_sess",
            step_index=step,
            active_file=active_file,
            terminal_output=terminal_out,
            compiler_exit_code=exit_code,
            recent_error=recent_error,
        )

        decision = provider.decide(state, obs)
        assert decision.action in DeveloperAction.all_actions()
        assert math.isclose(sum(decision.probabilities.values()), 1.0, abs_tol=1e-12)

        state.record_decision(decision)
        if decision.action == DeveloperAction.DONE:
            state = TruthFirstState(goal=f"Fuzz cycle {step}")


def test_local_provider_missing_action_key_bug_reproduction():
    """[REMEDIATED] LocalDecisionProvider handles state.decisions entry without 'action' key safely.
    
    Line 97 of local_provider.py executes:
        `last_decision_str = state.decisions[-1].get("action") if decisions_count > 0 else None`
    Using .get("action") prevents KeyError when state history contains irregular entries.
    """
    provider = LocalDecisionProvider()
    state = TruthFirstState()
    state.decisions.append({"step": 1, "note": "manual audit entry without action key"})
    obs = StateObservation(compiler_exit_code=1, recent_error="Error")

    decision = provider.decide(state, obs)
    assert decision.action in DeveloperAction.all_actions()
    assert decision.confidence >= 0.80


# ============================================================================
# Section 3: SafetyFallback Stress Tests
# ============================================================================

class MockProvider(DecisionProvider):
    """Controllable decision provider for stress testing SafetyFallback."""

    def __init__(self, action: DeveloperAction, confidence: float, params: dict | None = None):
        self.action = action
        self.confidence = confidence
        self.params = params or {}

    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        return DeveloperDecision(
            action=self.action,
            confidence=self.confidence,
            parameters=dict(self.params),
        )


def test_safety_fallback_confidence_boundary_precision():
    """Test precise threshold boundary at min_confidence (0.60).
    
    0.59999 -> intercepted
    0.60000 -> passes unharmed
    0.60001 -> passes unharmed
    """
    state = TruthFirstState()
    obs = StateObservation()

    # Case A: 0.59999 must be intercepted
    provider_below = MockProvider(DeveloperAction.RERUN_BUILD, 0.59999)
    sf_below = SafetyFallback(provider_below, min_confidence=0.60)
    dec_below = sf_below.decide(state, obs)
    assert dec_below.action == DeveloperAction.REQUEST_CONFIRMATION
    assert dec_below.metadata.get("safety_override") == "low_confidence"

    # Case B: 0.60000 exactly must pass through
    provider_exact = MockProvider(DeveloperAction.RERUN_BUILD, 0.60000)
    sf_exact = SafetyFallback(provider_exact, min_confidence=0.60)
    dec_exact = sf_exact.decide(state, obs)
    assert dec_exact.action == DeveloperAction.RERUN_BUILD
    assert "safety_override" not in dec_exact.metadata

    # Case C: 0.60001 must pass through
    provider_above = MockProvider(DeveloperAction.RERUN_BUILD, 0.60001)
    sf_above = SafetyFallback(provider_above, min_confidence=0.60)
    dec_above = sf_above.decide(state, obs)
    assert dec_above.action == DeveloperAction.RERUN_BUILD
    assert "safety_override" not in dec_above.metadata


def test_safety_fallback_oscillation_threshold_2():
    """Test oscillation threshold = 2 (2 repeated actions trigger loop guard)."""
    provider = MockProvider(DeveloperAction.INSPECT_FILE, 0.85, {"target_file": "a.py"})
    sf = SafetyFallback(provider, oscillation_threshold=2)
    state = TruthFirstState()
    obs = StateObservation()

    # Step 1: 1st time, should pass
    d1 = sf.decide(state, obs)
    assert d1.action == DeveloperAction.INSPECT_FILE
    assert "safety_override" not in d1.metadata

    # Step 2: 2nd time, should be intercepted because threshold is 2
    d2 = sf.decide(state, obs)
    assert d2.action == DeveloperAction.REQUEST_CONFIRMATION
    assert d2.metadata.get("safety_override") == "oscillation_detected"


def test_safety_fallback_oscillation_threshold_3():
    """Test oscillation threshold = 3 (default: 3 repeated actions trigger loop guard)."""
    provider = MockProvider(DeveloperAction.INSPECT_FILE, 0.85, {"target_file": "a.py"})
    sf = SafetyFallback(provider, oscillation_threshold=3)
    state = TruthFirstState()
    obs = StateObservation()

    # Step 1: 1st time, passes
    d1 = sf.decide(state, obs)
    assert d1.action == DeveloperAction.INSPECT_FILE

    # Step 2: 2nd time, passes
    d2 = sf.decide(state, obs)
    assert d2.action == DeveloperAction.INSPECT_FILE

    # Step 3: 3rd time, intercepted
    d3 = sf.decide(state, obs)
    assert d3.action == DeveloperAction.REQUEST_CONFIRMATION
    assert d3.metadata.get("safety_override") == "oscillation_detected"


def test_safety_fallback_done_action_is_exempt_from_oscillation():
    """DeveloperAction.DONE is terminal and must not trigger oscillation override even if repeated."""
    provider = MockProvider(DeveloperAction.DONE, 0.99)
    sf = SafetyFallback(provider, oscillation_threshold=3)
    state = TruthFirstState()
    obs = StateObservation()

    for _ in range(5):
        d = sf.decide(state, obs)
        assert d.action == DeveloperAction.DONE
        assert "safety_override" not in d.metadata


def test_safety_fallback_nan_confidence_bypass_bug_reproduction():
    """[REMEDIATED] NaN confidence is clamped to 0.0 and intercepted by SafetyFallback.
    
    In DeveloperDecision.__post_init__:
        `if math.isnan(c) or math.isinf(c): self.confidence = 0.0`
    Corrupted NaN confidence defaults to 0.0 (maximal uncertainty), ensuring SafetyFallback
    properly intercepts it (< 0.60) and requires confirmation.
    """
    nan_provider = MockProvider(DeveloperAction.RERUN_BUILD, float("nan"))
    sf = SafetyFallback(nan_provider, min_confidence=0.60)
    state = TruthFirstState()
    obs = StateObservation()

    decision = sf.decide(state, obs)

    # Empirically verify the fix:
    assert decision.confidence == 0.0 or decision.metadata.get("original_confidence") == 0.0
    assert decision.requires_confirmation is True
    assert decision.action == DeveloperAction.REQUEST_CONFIRMATION
    assert decision.metadata.get("safety_override") == "low_confidence"


def test_safety_fallback_oscillation_threshold_1_slice_bug_reproduction():
    """[REMEDIATED] oscillation_threshold=1 does not falsely trigger on the VERY FIRST action.
    
    On turn 1 with empty history, the action should not be flagged as a loop.
    On turn 2 with repeated identical action, it correctly triggers loop interception.
    """
    provider = MockProvider(DeveloperAction.INSPECT_FILE, 0.90, {"target_file": "file.py"})
    sf = SafetyFallback(provider, oscillation_threshold=1)
    state = TruthFirstState()
    obs = StateObservation()

    d1 = sf.decide(state, obs)
    assert d1.action == DeveloperAction.INSPECT_FILE
    assert "safety_override" not in d1.metadata

    d2 = sf.decide(state, obs)
    assert d2.action == DeveloperAction.REQUEST_CONFIRMATION
    assert d2.metadata.get("safety_override") == "oscillation_detected"

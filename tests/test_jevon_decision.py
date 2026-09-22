"""Comprehensive unit tests for JEVON Core Decision Engine & Bounded Action Space (R1)."""

import math
import pytest

from jevon.decision.actions import (
    Decision,
    DeveloperAction,
    DeveloperDecision,
    normalize_probabilities,
)
from jevon.decision.jev_provider import TypeSafeJevProvider
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.truth_first.state import TruthFirstState

# ============================================================================
# 1. DeveloperAction Tests
# ============================================================================

def test_developer_action_enumeration() -> None:
    """Action space must contain exactly 8 bounded, mutually exclusive actions."""
    all_actions = DeveloperAction.all_actions()
    assert len(all_actions) == 8

    expected_values = {
        "inspect_error",
        "inspect_file",
        "run_targeted_test",
        "rerun_build",
        "inspect_recent_change",
        "apply_fix",
        "request_confirmation",
        "done",
    }
    actual_values = {a.value for a in all_actions}
    assert actual_values == expected_values


def test_developer_action_is_terminal() -> None:
    """Only DeveloperAction.DONE must be terminal."""
    for action in DeveloperAction.all_actions():
        if action == DeveloperAction.DONE:
            assert action.is_terminal is True
        else:
            assert action.is_terminal is False


def test_developer_action_string_compatibility() -> None:
    """Enum values must match expected string representations."""
    assert DeveloperAction.INSPECT_ERROR == "inspect_error"
    assert DeveloperAction.APPLY_FIX == "apply_fix"
    assert DeveloperAction("done") == DeveloperAction.DONE


# ============================================================================
# 2. Probability Normalization Tests
# ============================================================================

def test_normalize_probabilities_standard() -> None:
    """Probabilities across all 8 actions must sum to exactly 1.0."""
    raw = {
        "inspect_error": 0.8,
        "inspect_file": 0.1,
        "done": 0.1,
    }
    norm = normalize_probabilities(raw)
    assert len(norm) == 8
    assert pytest.approx(sum(norm.values()), abs=1e-6) == 1.0
    assert norm["inspect_error"] == 0.8
    assert norm["rerun_build"] == 0.0


def test_normalize_probabilities_empty_fallback() -> None:
    """Empty or uninitialized probability dict must produce uniform distribution."""
    norm = normalize_probabilities({})
    assert len(norm) == 8
    assert pytest.approx(sum(norm.values()), abs=1e-6) == 1.0
    for val in norm.values():
        assert pytest.approx(val, abs=1e-4) == 1.0 / 8.0


# ============================================================================
# 3. DeveloperDecision Tests
# ============================================================================

def test_developer_decision_creation_and_properties() -> None:
    """DeveloperDecision must validate bounds and expose convenience properties."""
    decision = DeveloperDecision(
        action=DeveloperAction.DONE,
        confidence=0.98,
        probabilities={"done": 0.98, "rerun_build": 0.02},
        parameters={"status": "clean"},
        metadata={"reasoning": "all tests passed"},
    )
    assert decision.is_terminal is True
    assert decision.requires_confirmation is False
    assert decision.confidence == 0.98
    assert pytest.approx(sum(decision.probabilities.values()), abs=1e-6) == 1.0


def test_developer_decision_requires_confirmation_triggers() -> None:
    """Requires confirmation must trigger on REQUEST_CONFIRMATION, low confidence, or destructive flag."""
    # Low confidence (< 0.60)
    low_conf = DeveloperDecision(
        action=DeveloperAction.APPLY_FIX,
        confidence=0.55,
        parameters={"target": "foo.py"},
    )
    assert low_conf.requires_confirmation is True

    # REQUEST_CONFIRMATION action
    req_conf = DeveloperDecision(
        action=DeveloperAction.REQUEST_CONFIRMATION,
        confidence=0.90,
    )
    assert req_conf.requires_confirmation is True

    # Destructive metadata flag
    destruct = DeveloperDecision(
        action=DeveloperAction.APPLY_FIX,
        confidence=0.95,
        metadata={"destructive": True},
    )
    assert destruct.requires_confirmation is True


def test_developer_decision_serialization_roundtrip() -> None:
    """DeveloperDecision must roundtrip through dict serialization."""
    original = DeveloperDecision(
        action=DeveloperAction.RUN_TARGETED_TEST,
        confidence=0.88,
        probabilities={"run_targeted_test": 0.88, "rerun_build": 0.12},
        parameters={"target_test": "tests/test_demo.py"},
        metadata={"provider": "LocalDecisionProvider"},
    )
    data = original.to_dict()
    reconstructed = DeveloperDecision.from_dict(data)

    assert reconstructed.action == original.action
    assert reconstructed.confidence == original.confidence
    assert reconstructed.parameters == original.parameters
    assert reconstructed.metadata == original.metadata
    assert Decision is DeveloperDecision


def test_developer_decision_json_serialization_roundtrip() -> None:
    """DeveloperDecision must roundtrip through JSON string serialization."""
    original = DeveloperDecision(
        action=DeveloperAction.APPLY_FIX,
        confidence=0.92,
        probabilities={"apply_fix": 0.92, "done": 0.08},
        parameters={"target_file": "jevon/actions.py", "patch": "diff"},
        metadata={"session_id": "test_json_sess"},
    )
    json_str = original.to_json()
    assert isinstance(json_str, str)
    reconstructed = DeveloperDecision.from_json(json_str)

    assert reconstructed.action == original.action
    assert math.isclose(reconstructed.confidence, original.confidence, abs_tol=1e-6)
    assert reconstructed.parameters == original.parameters
    assert reconstructed.metadata == original.metadata


def test_developer_decision_nan_inf_confidence_clamping() -> None:
    """DeveloperDecision must clamp NaN and Inf confidence to 0.0."""
    d_nan = DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=float("nan"))
    assert d_nan.confidence == 0.0
    assert d_nan.requires_confirmation is True

    d_inf = DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=float("inf"))
    assert d_inf.confidence == 0.0
    assert d_inf.requires_confirmation is True

    d_neginf = DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=float("-inf"))
    assert d_neginf.confidence == 0.0
    assert d_neginf.requires_confirmation is True


# ============================================================================
# 4. StateObservation Tests
# ============================================================================

def test_state_observation_defaults_and_serialization() -> None:
    """StateObservation dataclass must support defaults and serialization."""
    obs = StateObservation(
        session_id="sess_123",
        step_index=1,
        working_directory="B:/projects/viswa_jav",
        terminal_output="pytest failed",
        compiler_exit_code=1,
        recent_error="AssertionError: 1 != 2",
    )
    assert obs.compiler_exit_code == 1
    assert obs.recent_error == "AssertionError: 1 != 2"

    d = obs.to_dict()
    obs2 = StateObservation.from_dict(d)
    assert obs2.session_id == "sess_123"
    assert obs2.compiler_exit_code == 1
    assert obs2.recent_error == "AssertionError: 1 != 2"


# ============================================================================
# 5. DecisionProvider Base ABC Tests
# ============================================================================

def test_decision_provider_abc() -> None:
    """Cannot instantiate base DecisionProvider without implementing decide."""
    class IncompleteProvider(DecisionProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()  # type: ignore[abstract]


# ============================================================================
# 6. LocalDecisionProvider Tests
# ============================================================================

def test_local_decision_provider_availability() -> None:
    """LocalDecisionProvider is 100% offline with zero cloud API keys."""
    provider = LocalDecisionProvider()
    assert provider.name == "LocalDecisionProvider"
    assert provider.is_available() is True


def test_local_provider_baseline_initial_assessment() -> None:
    """With no recent executions and idle state, provider decides rerun_build."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Verify project build")
    obs = StateObservation(compiler_exit_code=None, terminal_output="")

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.RERUN_BUILD
    assert decision.confidence >= 0.80
    assert pytest.approx(sum(decision.probabilities.values()), abs=1e-6) == 1.0


def test_local_provider_error_uninspected_to_inspect_error() -> None:
    """When a build fails and error is unparsed, provider decides inspect_error."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix broken test")
    obs = StateObservation(
        compiler_exit_code=1,
        terminal_output="FAILED tests/test_actions.py::test_click - AssertionError",
        recent_error="AssertionError in test_click",
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.INSPECT_ERROR
    assert decision.confidence >= 0.85
    assert pytest.approx(sum(decision.probabilities.values()), abs=1e-6) == 1.0


def test_local_provider_error_parsed_to_inspect_file() -> None:
    """When error is parsed and culprit file is identified, provider decides inspect_file."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix syntax error")
    state.record_decision(DeveloperAction.INSPECT_ERROR)

    obs = StateObservation(
        compiler_exit_code=1,
        active_file="typesafe_computer_use/actions.py",
        recent_error="SyntaxError: invalid syntax in actions.py line 42",
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.INSPECT_FILE
    assert decision.parameters["target_file"] == "typesafe_computer_use/actions.py"
    assert decision.confidence >= 0.85


def test_local_provider_file_inspected_to_apply_fix() -> None:
    """When culprit file was inspected, provider decides apply_fix."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix bug")
    state.record_decision(DeveloperAction.INSPECT_FILE)

    obs = StateObservation(
        compiler_exit_code=1,
        active_file="typesafe_computer_use/actions.py",
        recent_error="ZeroDivisionError",
        metadata={"suggested_fix": "return 0 if x == 0 else 1 / x"},
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.APPLY_FIX
    assert decision.parameters["target_file"] == "typesafe_computer_use/actions.py"


def test_local_provider_fix_applied_to_run_targeted_test() -> None:
    """When fix is applied, provider decides run_targeted_test."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix bug")
    state.record_decision(DeveloperAction.APPLY_FIX)

    obs = StateObservation(
        active_file="src/calculator.py",
        metadata={"target_test": "tests/test_calculator.py::test_divide"},
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.RUN_TARGETED_TEST
    assert decision.parameters["target_test"] == "tests/test_calculator.py::test_divide"


def test_local_provider_targeted_test_passed_to_rerun_build() -> None:
    """When targeted test passes, provider decides rerun_build to check regressions."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Verify fix")
    state.record_decision(DeveloperAction.RUN_TARGETED_TEST)

    obs = StateObservation(
        compiler_exit_code=0,
        recent_error=None,
        terminal_output="1 passed in 0.05s",
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.RERUN_BUILD


def test_local_provider_clean_build_to_done() -> None:
    """When full build passes cleanly with exit code 0, provider decides done."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix all tests")
    state.record_decision(DeveloperAction.RERUN_BUILD)

    obs = StateObservation(
        compiler_exit_code=0,
        recent_error=None,
        terminal_output="201 passed in 15.43s",
    )

    decision = provider.decide(state, obs)
    assert decision.action == DeveloperAction.DONE
    assert decision.is_terminal is True
    assert decision.confidence >= 0.95


def test_local_provider_repeated_failure_requests_confirmation() -> None:
    """When state detects repeated failure signatures, provider requests confirmation."""
    provider = LocalDecisionProvider()
    state = TruthFirstState(goal="Fix bug")
    # Record 3 identical failure signatures
    state.record_failure_signature("sig_abc123")
    state.record_failure_signature("sig_abc123")
    state.record_failure_signature("sig_abc123")

    obs = StateObservation(compiler_exit_code=1, recent_error="Error 123")
    decision = provider.decide(state, obs)

    assert decision.action == DeveloperAction.REQUEST_CONFIRMATION
    assert decision.requires_confirmation is True


# ============================================================================
# 7. TypeSafeJevProvider Tests
# ============================================================================

def test_typesafe_jev_provider_fallback_without_keys() -> None:
    """TypeSafeJevProvider safely delegates to local provider when no API key is provided."""
    provider = TypeSafeJevProvider(api_key=None)
    assert provider.name == "TypeSafeJevProvider"
    assert provider.is_available() is True
    assert provider.has_cloud_credentials() is False

    state = TruthFirstState(goal="Check workspace")
    obs = StateObservation(compiler_exit_code=0, terminal_output="passed")

    decision = provider.decide(state, obs)
    assert decision.action in DeveloperAction.all_actions()
    assert decision.metadata.get("cloud_fallback") is True
    assert decision.metadata.get("fallback_reason") == "no_credentials"


def test_typesafe_jev_provider_handles_exception_with_fallback() -> None:
    """TypeSafeJevProvider catches cloud exception and returns local decision."""
    provider = TypeSafeJevProvider(api_key="sk-test-fake-key")
    assert provider.has_cloud_credentials() is True

    # Intentionally trigger fallback by passing state
    state = TruthFirstState(goal="Test exception safety")
    obs = StateObservation(compiler_exit_code=1, recent_error="Runtime error")

    decision = provider.decide(state, obs)
    # Must succeed cleanly via fallback
    assert decision.action in DeveloperAction.all_actions()
    assert decision.metadata.get("cloud_fallback") is True


# ============================================================================
# 8. SafetyFallback Tests
# ============================================================================

def test_safety_fallback_intercepts_low_confidence() -> None:
    """SafetyFallback must intercept decisions with confidence < min_confidence (0.60)."""
    class LowConfProvider(DecisionProvider):
        def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
            return DeveloperDecision(
                action=DeveloperAction.APPLY_FIX,
                confidence=0.45,
                parameters={"target_file": "fix.py"},
            )

    wrapped = SafetyFallback(LowConfProvider(), min_confidence=0.60)
    state = TruthFirstState(goal="Test low conf")
    obs = StateObservation(compiler_exit_code=0)

    decision = wrapped.decide(state, obs)
    assert decision.action == DeveloperAction.REQUEST_CONFIRMATION
    assert decision.metadata.get("safety_override") == "low_confidence"
    assert decision.confidence >= 0.60
    assert pytest.approx(sum(decision.probabilities.values()), abs=1e-6) == 1.0


def test_safety_fallback_intercepts_oscillation() -> None:
    """SafetyFallback must intercept 3 consecutive identical actions as oscillation."""
    class FixedActionProvider(DecisionProvider):
        def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
            return DeveloperDecision(
                action=DeveloperAction.INSPECT_FILE,
                confidence=0.85,
                parameters={"target_file": "test.py"},
            )

    wrapped = SafetyFallback(FixedActionProvider(), oscillation_threshold=3)
    state = TruthFirstState(goal="Test oscillation")
    obs = StateObservation(active_file="test.py")

    d1 = wrapped.decide(state, obs)
    assert d1.action == DeveloperAction.INSPECT_FILE

    d2 = wrapped.decide(state, obs)
    assert d2.action == DeveloperAction.INSPECT_FILE

    # Third identical call triggers oscillation interceptor
    d3 = wrapped.decide(state, obs)
    assert d3.action == DeveloperAction.REQUEST_CONFIRMATION
    assert d3.metadata.get("safety_override") == "oscillation_detected"


def test_safety_fallback_precondition_missing_target_file() -> None:
    """APPLY_FIX without target_file or active_file must be intercepted."""
    class BrokenApplyProvider(DecisionProvider):
        def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
            return DeveloperDecision(
                action=DeveloperAction.APPLY_FIX,
                confidence=0.90,
                parameters={},  # No target file!
            )

    wrapped = SafetyFallback(BrokenApplyProvider())
    state = TruthFirstState(goal="Apply broken fix")
    obs = StateObservation(active_file=None, recent_error="Error")

    decision = wrapped.decide(state, obs)
    assert decision.action in (DeveloperAction.INSPECT_FILE, DeveloperAction.INSPECT_ERROR)
    assert decision.metadata.get("safety_override") == "missing_target_file"


def test_safety_fallback_passes_confident_decision() -> None:
    """Confident non-oscillating decisions pass through unharmed."""
    class ConfidentProvider(DecisionProvider):
        def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
            return DeveloperDecision(
                action=DeveloperAction.RERUN_BUILD,
                confidence=0.92,
                parameters={"command": "uv run pytest"},
            )

    wrapped = SafetyFallback(ConfidentProvider())
    state = TruthFirstState(goal="Run build")
    obs = StateObservation()

    decision = wrapped.decide(state, obs)
    assert decision.action == DeveloperAction.RERUN_BUILD
    assert decision.confidence == 0.92
    assert "safety_override" not in decision.metadata

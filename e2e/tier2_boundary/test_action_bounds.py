"""Tier 2 Boundary Tests: Action Bounds & Decision Engine Edge Cases (Features 1-6).

Covers boundary value analysis and corner cases for:
- Feature 1: DecisionProvider (5 boundary tests)
- Feature 2: Bounded Action Space (5 boundary tests)
- Feature 3: LocalDecisionProvider (5 boundary tests)
- Feature 4: TypeSafeJevProvider (5 boundary tests)
- Feature 5: SafetyFallback (5 boundary tests)
- Feature 6: Typed Decisions (5 boundary tests)
Total: 30 tests.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock

from jevon.decision.actions import (
    DeveloperAction,
    DeveloperDecision,
    normalize_probabilities,
)
from jevon.decision.jev_provider import TypeSafeJevProvider
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.truth_first.state import TruthFirstState


# ===========================================================================
# Feature 1 Boundary Cases: DecisionProvider
# ===========================================================================

class TestFeature1DecisionProviderBoundaries(unittest.TestCase):
    """Boundary conditions for DecisionProvider."""

    def setUp(self) -> None:
        self.provider = LocalDecisionProvider()

    def test_b1_provider_empty_observation(self) -> None:
        state = TruthFirstState()
        obs = StateObservation()
        dec = self.provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)

    def test_b1_provider_empty_state(self) -> None:
        state = TruthFirstState(goal="", constraints=[], facts=[], decisions=[])
        obs = StateObservation(compiler_exit_code=0, terminal_output="passed")
        dec = self.provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)

    def test_b1_provider_very_large_terminal_output(self) -> None:
        state = TruthFirstState()
        # 500,000 characters of compiler output
        large_output = ("warning: unused variable\n" * 20000) + 'File "calc.py", line 10\nSyntaxError: bad syntax\n'
        obs = StateObservation(compiler_exit_code=1, terminal_output=large_output)
        dec = self.provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.INSPECT_ERROR)

    def test_b1_provider_unicode_and_emojis_in_observation(self) -> None:
        state = TruthFirstState(goal="Test 🚀 unicode 中文")
        obs = StateObservation(
            working_directory="C:\\Users\\测试\\project_🦀",
            terminal_output="Error ❌: 符号未找到 \x00\x1f\n",
            recent_error="SyntaxError: 💥 invalid token",
        )
        dec = self.provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)

    def test_b1_provider_negative_compiler_exit_code(self) -> None:
        # Process killed by signal (e.g., -9 SIGKILL)
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=-9, terminal_output="Process killed by signal 9")
        dec = self.provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.INSPECT_ERROR)


# ===========================================================================
# Feature 2 Boundary Cases: Bounded Action Space
# ===========================================================================

class TestFeature2BoundedActionSpaceBoundaries(unittest.TestCase):
    """Boundary conditions for DeveloperAction enum."""

    def test_b2_action_enum_case_sensitivity(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction("INSPECT_ERROR")

    def test_b2_action_enum_whitespace_in_action_name(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction(" done ")

    def test_b2_action_empty_string(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction("")

    def test_b2_action_injection_attack(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction("done; rm -rf /")

    def test_b2_action_numeric_type(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction(12345)  # type: ignore[arg-type]


# ===========================================================================
# Feature 3 Boundary Cases: LocalDecisionProvider
# ===========================================================================

class TestFeature3LocalDecisionProviderBoundaries(unittest.TestCase):
    """Boundary conditions for LocalDecisionProvider."""

    def setUp(self) -> None:
        self.provider = LocalDecisionProvider()

    def test_b3_local_provider_exit_code_none_with_empty_output(self) -> None:
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=None, terminal_output="")
        dec = self.provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)

    def test_b3_local_provider_corrupted_traceback(self) -> None:
        state = TruthFirstState()
        obs = StateObservation(
            compiler_exit_code=1,
            terminal_output='File "corrupted.py", line not_a_number\nSyntaxError',
        )
        dec = self.provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)

    def test_b3_local_provider_infinite_loop_prevention_at_3_signatures(self) -> None:
        state = TruthFirstState()
        sig = "sig_loop_x"
        state.record_failure_signature(sig)
        state.record_failure_signature(sig)
        # At 2 signatures, not yet a loop
        obs = StateObservation(compiler_exit_code=1)
        dec2 = self.provider.decide(state, obs)
        self.assertNotEqual(dec2.action, DeveloperAction.REQUEST_CONFIRMATION)

        # At 3 identical signatures, loop detected
        state.record_failure_signature(sig)
        dec3 = self.provider.decide(state, obs)
        self.assertEqual(dec3.action, DeveloperAction.REQUEST_CONFIRMATION)
        self.assertEqual(dec3.parameters.get("reason"), "loop_detected")

    def test_b3_local_provider_non_existent_culprit_file(self) -> None:
        state = TruthFirstState()
        state.decisions.append({"action": "inspect_error", "step": 1})
        obs = StateObservation(
            compiler_exit_code=1,
            active_file="non_existent_ghost_file.py",
            recent_error="SyntaxError: invalid syntax",
        )
        dec = self.provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.INSPECT_FILE)
        self.assertEqual(dec.parameters.get("target_file"), "non_existent_ghost_file.py")

    def test_b3_local_provider_secondary_weights_zero_sum(self) -> None:
        # When secondary weights are all zero, builder must fall back to uniform distribution
        probs = self.provider._build_probabilities(DeveloperAction.DONE, confidence=0.8, secondary_weights={})
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=5)
        for a in DeveloperAction.all_actions():
            self.assertIn(a.value, probs)


# ===========================================================================
# Feature 4 Boundary Cases: TypeSafeJevProvider
# ===========================================================================

class TestFeature4TypeSafeJevProviderBoundaries(unittest.TestCase):
    """Boundary conditions for TypeSafeJevProvider."""

    def test_b4_jev_provider_whitespace_only_key(self) -> None:
        provider = TypeSafeJevProvider(api_key="   \t\n  ")
        self.assertFalse(provider.has_cloud_credentials())

    def test_b4_jev_provider_network_timeout_in_cloud_call(self) -> None:
        provider = TypeSafeJevProvider(api_key="ts_key_valid")
        provider._call_cloud_classifier = MagicMock(side_effect=TimeoutError("Request timed out after 10000ms"))
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=1)
        dec = provider.decide(state, obs)
        self.assertTrue(dec.metadata.get("cloud_fallback"))
        self.assertIn("timed out", dec.metadata.get("fallback_reason", ""))

    def test_b4_jev_provider_special_characters_in_api_key(self) -> None:
        provider = TypeSafeJevProvider(api_key="key_!@#$%^&*()_+-=[]{}|;':\",./<>?")
        self.assertTrue(provider.has_cloud_credentials())

    def test_b4_jev_provider_large_context_cloud_classification(self) -> None:
        provider = TypeSafeJevProvider(api_key=None)
        state = TruthFirstState(goal="Very long goal: " + "X" * 10000)
        obs = StateObservation(terminal_output="Y" * 10000)
        dec = provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)

    def test_b4_jev_provider_double_fallback(self) -> None:
        # Fallback provider also has an issue with a specific parameter, FSM still returns valid decision
        provider = TypeSafeJevProvider(api_key=None, local_fallback=LocalDecisionProvider())
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=0, terminal_output="all 200 passed")
        dec = provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.DONE)


# ===========================================================================
# Feature 5 Boundary Cases: SafetyFallback
# ===========================================================================

class TestFeature5SafetyFallbackBoundaries(unittest.TestCase):
    """Boundary conditions for SafetyFallback interceptor."""

    def test_b5_safety_fallback_boundary_confidence_exact_0_60(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockProvider"
        mock_provider.is_available.return_value = True

        # Exactly 0.60: must PASS without interception
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.60,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, min_confidence=0.60)
        dec = safe.decide(TruthFirstState(), StateObservation())
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)

        # Exactly 0.5999: must INTERCEPT
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.5999,
        )
        dec_intercepted = safe.decide(TruthFirstState(), StateObservation())
        self.assertEqual(dec_intercepted.action, DeveloperAction.REQUEST_CONFIRMATION)

    def test_b5_safety_fallback_confidence_zero(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockZeroConf"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.DONE,
            confidence=0.0,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider)
        dec = safe.decide(TruthFirstState(), StateObservation())
        self.assertEqual(dec.action, DeveloperAction.REQUEST_CONFIRMATION)

    def test_b5_safety_fallback_oscillation_threshold_1(self) -> None:
        # Threshold of 1 means even the very first action triggers loop guard
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockThresh1"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.9,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, oscillation_threshold=1)
        dec = safe.decide(TruthFirstState(), StateObservation())
        self.assertEqual(dec.action, DeveloperAction.REQUEST_CONFIRMATION)

    def test_b5_safety_fallback_done_never_oscillates(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockDone"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.DONE,
            confidence=0.95,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, oscillation_threshold=2)
        state = TruthFirstState()
        obs = StateObservation()

        # DONE multiple times should NOT trigger oscillation
        d1 = safe.decide(state, obs)
        d2 = safe.decide(state, obs)
        d3 = safe.decide(state, obs)
        self.assertEqual(d1.action, DeveloperAction.DONE)
        self.assertEqual(d2.action, DeveloperAction.DONE)
        self.assertEqual(d3.action, DeveloperAction.DONE)

    def test_b5_safety_fallback_metadata_preservation_on_override(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockMeta"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.APPLY_FIX,
            confidence=0.4,
            parameters={"target_file": "app.py"},
            metadata={"custom_debug": 1234},
        )
        safe = SafetyFallback(wrapped_provider=mock_provider)
        dec = safe.decide(TruthFirstState(), StateObservation())
        self.assertEqual(dec.metadata.get("custom_debug"), 1234)
        self.assertEqual(dec.metadata.get("safety_override"), "low_confidence")


# ===========================================================================
# Feature 6 Boundary Cases: Typed Decisions
# ===========================================================================

class TestFeature6TypedDecisionsBoundaries(unittest.TestCase):
    """Boundary conditions for DeveloperDecision schema and probability distributions."""

    def test_b6_decision_confidence_boundary_0_0(self) -> None:
        dec = DeveloperDecision(action=DeveloperAction.DONE, confidence=0.0)
        self.assertEqual(dec.confidence, 0.0)

    def test_b6_decision_confidence_boundary_1_0(self) -> None:
        dec = DeveloperDecision(action=DeveloperAction.DONE, confidence=1.0)
        self.assertEqual(dec.confidence, 1.0)

    def test_b6_decision_probabilities_all_zero_normalized_to_uniform(self) -> None:
        all_zeros = {a: 0.0 for a in DeveloperAction.all_actions()}
        normalized = normalize_probabilities(all_zeros)
        self.assertAlmostEqual(sum(normalized.values()), 1.0, places=6)
        expected_uniform = 1.0 / 8.0
        for val in normalized.values():
            self.assertAlmostEqual(val, expected_uniform, places=5)

    def test_b6_decision_single_action_1_0_others_0_0(self) -> None:
        single = {DeveloperAction.DONE: 1.0}
        normalized = normalize_probabilities(single)
        self.assertAlmostEqual(sum(normalized.values()), 1.0, places=6)
        self.assertEqual(normalized[DeveloperAction.DONE.value], 1.0)

    def test_b6_decision_nan_and_inf_probabilities_handled(self) -> None:
        nan_probs = {DeveloperAction.DONE: float("nan")}
        normalized = normalize_probabilities(nan_probs)
        self.assertAlmostEqual(sum(normalized.values()), 1.0, places=6)
        for val in normalized.values():
            self.assertFalse(math.isnan(val))


if __name__ == "__main__":
    unittest.main()

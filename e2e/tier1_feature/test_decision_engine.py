"""Tier 1 Feature Tests: Decision Engine & Action Space (Features 1-6).

Covers:
- Feature 1: DecisionProvider Interface & Polymorphism (5 tests)
- Feature 2: Bounded Action Space (<= 8 Actions) (5 tests)
- Feature 3: LocalDecisionProvider Offline (0 API Keys) (5 tests)
- Feature 4: TypeSafeJevProvider Cloud Fallback (5 tests)
- Feature 5: SafetyFallback Interceptor (C < 0.60 / Loops) (5 tests)
- Feature 6: Typed Decisions (Confidence & Probability Sum = 1.0) (5 tests)
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
# Feature 1: DecisionProvider Interface & Polymorphism (R1)
# ===========================================================================

class DummyProvider(DecisionProvider):
    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        return DeveloperDecision(
            action=DeveloperAction.DONE,
            confidence=0.99,
            metadata={"dummy": True},
        )


class TestFeature1DecisionProviderInterface(unittest.TestCase):
    """Validates Feature 1: DecisionProvider interface, polymorphism, and contracts."""

    def test_f1_decision_provider_subclassing_and_name(self) -> None:
        provider = DummyProvider()
        self.assertEqual(provider.name, "DummyProvider")

    def test_f1_decision_provider_is_available_default(self) -> None:
        provider = DummyProvider()
        self.assertTrue(provider.is_available())

    def test_f1_decision_provider_polymorphic_dispatch(self) -> None:
        providers: list[DecisionProvider] = [DummyProvider(), LocalDecisionProvider()]
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=0, terminal_output="3 passed in 0.1s")

        for p in providers:
            decision = p.decide(state, obs)
            self.assertIsInstance(decision, DeveloperDecision)
            self.assertIn(decision.action, DeveloperAction.all_actions())

    def test_f1_decision_provider_abstract_instantiation_raises(self) -> None:
        with self.assertRaises(TypeError):
            DecisionProvider()  # type: ignore[abstract]

    def test_f1_decision_provider_decide_signature_contract(self) -> None:
        provider = LocalDecisionProvider()
        state = TruthFirstState(goal="Fix broken test")
        obs = StateObservation(session_id="sess_1", step_index=1, compiler_exit_code=1, recent_error="SyntaxError")
        dec = provider.decide(state, obs)
        self.assertIsInstance(dec, DeveloperDecision)
        self.assertTrue(hasattr(dec, "action"))
        self.assertTrue(hasattr(dec, "confidence"))
        self.assertTrue(hasattr(dec, "probabilities"))


# ===========================================================================
# Feature 2: Bounded Action Space (<= 8 Actions) (R1)
# ===========================================================================

class TestFeature2BoundedActionSpace(unittest.TestCase):
    """Validates Feature 2: Action space boundedness, mutual exclusivity, and cardinality."""

    def test_f2_action_space_exact_count(self) -> None:
        all_actions = DeveloperAction.all_actions()
        self.assertEqual(len(all_actions), 8, "Action space must contain exactly 8 actions")

    def test_f2_action_space_member_names(self) -> None:
        expected = {
            "inspect_error",
            "inspect_file",
            "run_targeted_test",
            "rerun_build",
            "inspect_recent_change",
            "apply_fix",
            "request_confirmation",
            "done",
        }
        actual = {a.value for a in DeveloperAction.all_actions()}
        self.assertEqual(actual, expected)

    def test_f2_action_space_done_is_terminal(self) -> None:
        self.assertTrue(DeveloperAction.DONE.is_terminal)
        non_terminals = [a for a in DeveloperAction.all_actions() if a != DeveloperAction.DONE]
        for a in non_terminals:
            self.assertFalse(a.is_terminal, f"Action {a} should not be terminal")

    def test_f2_action_space_string_enum_coercion(self) -> None:
        self.assertEqual(DeveloperAction("inspect_error"), DeveloperAction.INSPECT_ERROR)
        self.assertEqual(DeveloperAction.DONE.value, "done")
        self.assertTrue(isinstance(DeveloperAction.APPLY_FIX, str))

    def test_f2_action_space_rejects_unbounded_action(self) -> None:
        with self.assertRaises(ValueError):
            DeveloperAction("reboot_system")
        with self.assertRaises(ValueError):
            DeveloperAction("browse_web")


# ===========================================================================
# Feature 3: LocalDecisionProvider Offline (0 API Keys) (R1)
# ===========================================================================

class TestFeature3LocalDecisionProvider(unittest.TestCase):
    """Validates Feature 3: Offline decision engine operating with zero cloud API keys."""

    def setUp(self) -> None:
        self.provider = LocalDecisionProvider()

    def test_f3_local_provider_runs_with_zero_keys(self) -> None:
        self.assertEqual(self.provider.name, "LocalDecisionProvider")
        self.assertTrue(self.provider.is_available())

    def test_f3_local_provider_clean_build_decides_done(self) -> None:
        state = TruthFirstState(goal="Verify build")
        state.decisions.append({"action": "rerun_build", "step": 1})
        obs = StateObservation(compiler_exit_code=0, terminal_output="12 passed in 1.2s")
        decision = self.provider.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.DONE)
        self.assertGreaterEqual(decision.confidence, 0.95)

    def test_f3_local_provider_syntax_error_decides_inspect_error(self) -> None:
        state = TruthFirstState(goal="Fix syntax error")
        obs = StateObservation(
            compiler_exit_code=1,
            recent_error="SyntaxError: invalid syntax",
            terminal_output='File "calc.py", line 3\n  return (a + b\n         ^\nSyntaxError',
        )
        decision = self.provider.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.INSPECT_ERROR)

    def test_f3_local_provider_culprit_file_extraction_decides_inspect_file(self) -> None:
        state = TruthFirstState(goal="Fix error")
        state.decisions.append({"action": "inspect_error", "step": 1})
        obs = StateObservation(
            compiler_exit_code=1,
            active_file="src/calc.py",
            recent_error="SyntaxError: unclosed parenthesis",
        )
        decision = self.provider.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.INSPECT_FILE)
        self.assertEqual(decision.parameters.get("target_file"), "src/calc.py")

    def test_f3_local_provider_after_apply_fix_decides_targeted_test(self) -> None:
        state = TruthFirstState(goal="Verify applied fix")
        state.decisions.append({"action": "apply_fix", "step": 2})
        obs = StateObservation(active_file="calc.py", compiler_exit_code=None)
        decision = self.provider.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.RUN_TARGETED_TEST)


# ===========================================================================
# Feature 4: TypeSafeJevProvider Cloud Fallback (R1)
# ===========================================================================

class TestFeature4TypeSafeJevProvider(unittest.TestCase):
    """Validates Feature 4: Cloud-assisted provider with guaranteed local fallback."""

    def test_f4_jev_provider_no_keys_falls_back_to_local(self) -> None:
        provider = TypeSafeJevProvider(api_key=None)
        self.assertFalse(provider.has_cloud_credentials())
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=0, terminal_output="passed")
        decision = provider.decide(state, obs)
        self.assertTrue(decision.metadata.get("cloud_fallback"))
        self.assertEqual(decision.metadata.get("fallback_reason"), "no_credentials")

    def test_f4_jev_provider_is_available_always_true(self) -> None:
        provider = TypeSafeJevProvider(api_key=None)
        self.assertTrue(provider.is_available())

    def test_f4_jev_provider_has_cloud_credentials_check(self) -> None:
        no_key = TypeSafeJevProvider(api_key="")
        has_key = TypeSafeJevProvider(api_key="ts_live_mock_key_123")
        self.assertFalse(no_key.has_cloud_credentials())
        self.assertTrue(has_key.has_cloud_credentials())

    def test_f4_jev_provider_cloud_failure_falls_back(self) -> None:
        provider = TypeSafeJevProvider(api_key="ts_test_key")
        # Mock cloud classifier to raise an error
        provider._call_cloud_classifier = MagicMock(side_effect=RuntimeError("Cloud API 503 Service Unavailable"))
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=1, recent_error="Test failure")
        decision = provider.decide(state, obs)
        self.assertTrue(decision.metadata.get("cloud_fallback"))
        self.assertIn("Cloud API 503", decision.metadata.get("fallback_reason", ""))

    def test_f4_jev_provider_custom_local_fallback_injection(self) -> None:
        custom_local = LocalDecisionProvider()
        provider = TypeSafeJevProvider(api_key=None, local_fallback=custom_local)
        self.assertIs(provider._local_provider, custom_local)


# ===========================================================================
# Feature 5: SafetyFallback Interceptor (C < 0.60 / Loops) (R1)
# ===========================================================================

class TestFeature5SafetyFallback(unittest.TestCase):
    """Validates Feature 5: Safety fallback intercepting low confidence, loops, and invalid states."""

    def test_f5_safety_fallback_intercepts_low_confidence(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockLowConf"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.APPLY_FIX,
            confidence=0.42,  # < 0.60 threshold
            parameters={"target_file": "foo.py"},
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, min_confidence=0.60)
        state = TruthFirstState()
        obs = StateObservation(active_file="foo.py")
        decision = safe.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.REQUEST_CONFIRMATION)
        self.assertEqual(decision.metadata.get("safety_override"), "low_confidence")

    def test_f5_safety_fallback_passes_high_confidence(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockHighConf"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.DONE,
            confidence=0.92,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, min_confidence=0.60)
        state = TruthFirstState()
        obs = StateObservation(compiler_exit_code=0)
        decision = safe.decide(state, obs)
        self.assertEqual(decision.action, DeveloperAction.DONE)
        self.assertEqual(decision.confidence, 0.92)

    def test_f5_safety_fallback_intercepts_oscillation_loop(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockOscillation"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.85,
        )
        safe = SafetyFallback(wrapped_provider=mock_provider, oscillation_threshold=3)
        state = TruthFirstState()
        obs = StateObservation()

        safe.decide(state, obs)
        safe.decide(state, obs)
        third_dec = safe.decide(state, obs)  # 3rd consecutive rerun_build -> intercept

        self.assertEqual(third_dec.action, DeveloperAction.REQUEST_CONFIRMATION)
        self.assertEqual(third_dec.metadata.get("safety_override"), "oscillation_detected")

    def test_f5_safety_fallback_intercepts_apply_fix_without_target_file(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockApplyFixNoTarget"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.APPLY_FIX,
            confidence=0.88,
            parameters={},  # Missing target_file
        )
        safe = SafetyFallback(wrapped_provider=mock_provider)
        state = TruthFirstState()
        obs = StateObservation(active_file=None, recent_error="SyntaxError")
        dec = safe.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.INSPECT_FILE)
        self.assertEqual(dec.metadata.get("safety_override"), "missing_target_file")

    def test_f5_safety_fallback_intercepts_targeted_test_without_target(self) -> None:
        mock_provider = MagicMock(spec=DecisionProvider)
        mock_provider.name = "MockTargetedTestNoTarget"
        mock_provider.is_available.return_value = True
        mock_provider.decide.return_value = DeveloperDecision(
            action=DeveloperAction.RUN_TARGETED_TEST,
            confidence=0.88,
            parameters={},  # Missing target_test
        )
        safe = SafetyFallback(wrapped_provider=mock_provider)
        state = TruthFirstState()
        obs = StateObservation()
        dec = safe.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)
        self.assertEqual(dec.metadata.get("safety_override"), "missing_test_target")


# ===========================================================================
# Feature 6: Typed Decisions (Confidence & Probability Sum = 1.0) (R1)
# ===========================================================================

class TestFeature6TypedDecisions(unittest.TestCase):
    """Validates Feature 6: Typed decision schema, normalized probabilities, and serialization."""

    def test_f6_decision_probability_distribution_sums_to_one(self) -> None:
        raw_probs = {
            DeveloperAction.INSPECT_ERROR: 0.7,
            DeveloperAction.INSPECT_FILE: 0.1,
            DeveloperAction.DONE: 0.1,
        }
        normalized = normalize_probabilities(raw_probs)
        prob_sum = sum(normalized.values())
        self.assertAlmostEqual(prob_sum, 1.0, places=6)

    def test_f6_decision_probability_contains_all_eight_actions(self) -> None:
        dec = DeveloperDecision(action=DeveloperAction.INSPECT_ERROR, confidence=0.8)
        all_actions = DeveloperAction.all_actions()
        for a in all_actions:
            self.assertIn(a.value, dec.probabilities)
            self.assertGreaterEqual(dec.probabilities[a.value], 0.0)

    def test_f6_decision_confidence_in_unit_interval(self) -> None:
        dec_normal = DeveloperDecision(action=DeveloperAction.DONE, confidence=0.75)
        self.assertEqual(dec_normal.confidence, 0.75)

        # Clamping checks
        dec_over = DeveloperDecision(action=DeveloperAction.DONE, confidence=1.4)
        self.assertEqual(dec_over.confidence, 1.0)
        dec_under = DeveloperDecision(action=DeveloperAction.DONE, confidence=-0.5)
        self.assertEqual(dec_under.confidence, 0.0)

    def test_f6_decision_to_dict_and_from_dict_roundtrip(self) -> None:
        orig = DeveloperDecision(
            action=DeveloperAction.RUN_TARGETED_TEST,
            confidence=0.89,
            probabilities={"run_targeted_test": 0.89, "done": 0.11},
            parameters={"target_test": "tests/test_foo.py"},
            metadata={"source": "test_suite"},
        )
        d = orig.to_dict()
        reconstructed = DeveloperDecision.from_dict(d)
        self.assertEqual(reconstructed.action, orig.action)
        self.assertAlmostEqual(reconstructed.confidence, orig.confidence, places=5)
        self.assertEqual(reconstructed.parameters, orig.parameters)
        self.assertEqual(reconstructed.metadata, orig.metadata)

    def test_f6_decision_requires_confirmation_property(self) -> None:
        dec_request = DeveloperDecision(action=DeveloperAction.REQUEST_CONFIRMATION, confidence=0.9)
        self.assertTrue(dec_request.requires_confirmation)

        dec_destructive = DeveloperDecision(
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.9,
            metadata={"destructive": True},
        )
        self.assertTrue(dec_destructive.requires_confirmation)

        dec_low_conf = DeveloperDecision(action=DeveloperAction.APPLY_FIX, confidence=0.55)
        self.assertTrue(dec_low_conf.requires_confirmation)

        dec_safe = DeveloperDecision(action=DeveloperAction.RERUN_BUILD, confidence=0.85)
        self.assertFalse(dec_safe.requires_confirmation)


if __name__ == "__main__":
    unittest.main()

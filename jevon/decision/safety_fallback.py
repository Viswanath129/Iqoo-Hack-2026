"""Deterministic SafetyFallback wrapper for developer decision providers.

Guarantees safety bounds by intercepting low-confidence decisions (< 0.60),
oscillation loops, and invalid action preconditions.
"""

from __future__ import annotations

import logging

from jevon.decision.actions import DeveloperAction, DeveloperDecision, normalize_probabilities
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.truth_first.state import TruthFirstState

logger = logging.getLogger(__name__)


class SafetyFallback(DecisionProvider):
    """Decorator/Wrapper that validates decisions against deterministic safety invariants."""

    def __init__(
        self,
        wrapped_provider: DecisionProvider,
        min_confidence: float = 0.60,
        oscillation_threshold: int = 3,
    ) -> None:
        """Initialize SafetyFallback wrapper.

        Args:
            wrapped_provider: Inner decision provider.
            min_confidence: Threshold below which decisions are intercepted (default 0.60).
            oscillation_threshold: Count of repeated identical actions that triggers loop guard.
        """
        self._wrapped = wrapped_provider
        self.min_confidence = min_confidence
        self.oscillation_threshold = oscillation_threshold
        self._history: list[DeveloperDecision] = []

    @property
    def name(self) -> str:
        return f"SafetyFallback({self._wrapped.name})"

    def is_available(self) -> bool:
        return self._wrapped.is_available()

    def _build_probabilities(self, chosen: DeveloperAction, confidence: float) -> dict[str, float]:
        """Generate normalized probability distribution for safety override action."""
        all_actions = DeveloperAction.all_actions()
        other_actions = [a for a in all_actions if a != chosen]
        remaining = max(0.0, 1.0 - confidence)
        share = remaining / len(other_actions)
        weights = {a.value: (confidence if a == chosen else share) for a in all_actions}
        return normalize_probabilities(weights)

    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        """Query inner provider and intercept unsafe or low-confidence decisions."""
        decision = self._wrapped.decide(state, observation)

        # Precondition check: Missing target_file for APPLY_FIX
        if decision.action == DeveloperAction.APPLY_FIX:
            target_file = decision.parameters.get("target_file") or observation.active_file
            if not target_file:
                logger.warning("[SafetyFallback] Intercepted APPLY_FIX with no target file.")
                override_action = DeveloperAction.INSPECT_FILE if observation.recent_error else DeveloperAction.INSPECT_ERROR
                confidence = 0.85
                override = DeveloperDecision(
                    action=override_action,
                    confidence=confidence,
                    probabilities=self._build_probabilities(override_action, confidence),
                    parameters={"reason": "apply_fix_missing_target"},
                    metadata={
                        **decision.metadata,
                        "safety_override": "missing_target_file",
                        "original_action": decision.action.value,
                    },
                )
                self._history.append(override)
                return override

        # Precondition check: Missing test target for RUN_TARGETED_TEST
        if decision.action == DeveloperAction.RUN_TARGETED_TEST:
            target_test = decision.parameters.get("target_test") or observation.metadata.get("target_test")
            if not target_test:
                logger.warning("[SafetyFallback] Intercepted RUN_TARGETED_TEST with no test target; falling back to RERUN_BUILD.")
                override_action = DeveloperAction.RERUN_BUILD
                confidence = 0.88
                override = DeveloperDecision(
                    action=override_action,
                    confidence=confidence,
                    probabilities=self._build_probabilities(override_action, confidence),
                    parameters={"command": "uv run pytest"},
                    metadata={
                        **decision.metadata,
                        "safety_override": "missing_test_target",
                        "original_action": decision.action.value,
                    },
                )
                self._history.append(override)
                return override

        # Guard 1: Intercept Low Confidence Decisions (< min_confidence)
        if decision.confidence < self.min_confidence:
            logger.warning(
                "[SafetyFallback] Intercepted low-confidence decision: %s (conf=%.2f < %.2f)",
                decision.action.value,
                decision.confidence,
                self.min_confidence,
            )
            # If error is active and unparsed, fall back to inspect_error, otherwise request_confirmation
            has_unparsed_error = bool(observation.recent_error and not observation.active_file)
            fallback_action = (
                DeveloperAction.INSPECT_ERROR if has_unparsed_error else DeveloperAction.REQUEST_CONFIRMATION
            )
            confidence = 0.85
            override = DeveloperDecision(
                action=fallback_action,
                confidence=confidence,
                probabilities=self._build_probabilities(fallback_action, confidence),
                parameters={
                    "reason": "low_confidence",
                    "original_confidence": decision.confidence,
                    "original_action": decision.action.value,
                },
                metadata={
                    **decision.metadata,
                    "safety_override": "low_confidence",
                    "original_action": decision.action.value,
                    "original_confidence": decision.confidence,
                },
            )
            self._history.append(override)
            return override

        # Guard 2: Intercept Oscillation Loops (Repeated Identical Actions & Periodic Cycles)
        effective_threshold = max(2, self.oscillation_threshold)
        if len(self._history) >= (effective_threshold - 1):
            history_window = self._history[-(effective_threshold - 1):]
        else:
            history_window = self._history

        recent_actions = [d.action for d in history_window] + [decision.action]
        all_candidate_actions = [d.action for d in self._history] + [decision.action]

        # Check 1: Single-action stagnation (e.g. A -> A -> A)
        is_stagnation = (
            len(recent_actions) >= effective_threshold
            and len(set(recent_actions)) == 1
        )

        # Check 2: 2-cycle periodic oscillation (e.g. A -> B -> A -> B)
        is_2_cycle = (
            len(all_candidate_actions) >= 4
            and all_candidate_actions[-4:] == all_candidate_actions[-2:] * 2
            and all_candidate_actions[-1] != all_candidate_actions[-2]
        )

        # Check 3: 3-cycle periodic oscillation (e.g. A -> B -> C -> A -> B -> C)
        is_3_cycle = (
            len(all_candidate_actions) >= 6
            and all_candidate_actions[-6:] == all_candidate_actions[-3:] * 2
            and len(set(all_candidate_actions[-3:])) == 3
        )

        if (is_stagnation or is_2_cycle or is_3_cycle) and decision.action != DeveloperAction.DONE:
            repeated_desc = decision.action.value
            if is_2_cycle:
                repeated_desc = f"{all_candidate_actions[-2].value}->{all_candidate_actions[-1].value}"
            elif is_3_cycle:
                repeated_desc = (
                    f"{all_candidate_actions[-3].value}->"
                    f"{all_candidate_actions[-2].value}->"
                    f"{all_candidate_actions[-1].value}"
                )

            logger.warning(
                "[SafetyFallback] Intercepted oscillation loop of action(s): %s",
                repeated_desc,
            )
            override_action = DeveloperAction.REQUEST_CONFIRMATION
            confidence = 0.95
            override = DeveloperDecision(
                action=override_action,
                confidence=confidence,
                probabilities=self._build_probabilities(override_action, confidence),
                parameters={
                    "reason": "loop_detected",
                    "repeated_action": repeated_desc,
                    "count": self.oscillation_threshold,
                },
                metadata={
                    **decision.metadata,
                    "safety_override": "oscillation_detected",
                    "repeated_action": repeated_desc,
                },
            )
            self._history.append(override)
            if len(self._history) > 50:
                self._history = self._history[-50:]
            return override

        # Passed all safety checks
        self._history.append(decision)
        if len(self._history) > 50:
            self._history = self._history[-50:]
        return decision

"""Local offline decision provider for JEVON.

Operates 100% on-device with zero cloud API keys using rule-based FSM
and heuristic SLM logic over bounded developer states.
"""

from __future__ import annotations

import os
import re
from typing import Any

from jevon.decision.actions import DeveloperAction, DeveloperDecision, normalize_probabilities
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.truth_first.state import TruthFirstState


class LocalDecisionProvider(DecisionProvider):
    """100% offline, zero-cloud-key decision provider for developer workflow."""

    def __init__(self, slm_backend: Any = None) -> None:
        """Initialize local provider with optional on-device SLM backend."""
        self._slm_backend = slm_backend

    @property
    def name(self) -> str:
        return "LocalDecisionProvider"

    def is_available(self) -> bool:
        return True

    def _extract_culprit(self, observation: StateObservation) -> str | None:
        """Heuristically extract culprit file from observation."""
        if observation.active_file:
            return observation.active_file

        search_text = f"{observation.recent_error or ''}\n{observation.terminal_output or ''}"

        # Python stack trace file pattern: File "...", line \d+
        py_match = re.search(r'File "([^"]+\.py)", line (\d+)', search_text)
        if py_match:
            return py_match.group(1)

        # Pytest FAILED tests/test_*.py::test_* pattern
        pytest_match = re.search(r"FAILED\s+([^\s:]+\.py)", search_text)
        if pytest_match:
            return pytest_match.group(1)

        # Generic path with error: path/file.py:123
        generic_match = re.search(r"([a-zA-Z0-9_/\\.-]+\.(?:py|rs|ts|js)):(\d+)", search_text)
        if generic_match:
            return generic_match.group(1)

        return None

    def _build_probabilities(
        self,
        chosen: DeveloperAction,
        confidence: float,
        secondary_weights: dict[DeveloperAction, float] | None = None,
    ) -> dict[str, float]:
        """Construct normalized probability distribution across all 8 actions."""
        all_actions = DeveloperAction.all_actions()
        weights: dict[DeveloperAction, float] = {}

        remaining_mass = max(0.0, 1.0 - confidence)
        other_actions = [a for a in all_actions if a != chosen]

        if secondary_weights:
            custom_sum = sum(secondary_weights.get(a, 0.0) for a in other_actions)
            if custom_sum > 0:
                for a in other_actions:
                    weights[a] = remaining_mass * (secondary_weights.get(a, 0.0) / custom_sum)
            else:
                uniform_share = remaining_mass / len(other_actions)
                for a in other_actions:
                    weights[a] = uniform_share
        else:
            uniform_share = remaining_mass / len(other_actions)
            for a in other_actions:
                weights[a] = uniform_share

        weights[chosen] = confidence
        return normalize_probabilities(weights)

    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        """Evaluate developer state and observation, returning a typed DeveloperDecision."""
        exit_code = observation.compiler_exit_code
        recent_error = observation.recent_error
        terminal_out = observation.terminal_output or ""
        culprit_file = self._extract_culprit(observation)

        has_error = bool(recent_error or (exit_code is not None and exit_code != 0))
        clean_build = (exit_code == 0 and not has_error)

        decisions_count = len(state.decisions)
        last_decision_str = state.decisions[-1].get("action") if decisions_count > 0 else None

        # Guard 1: Detect repeated failure signatures or oscillation
        if state.detect_repeated_failure(window=3) or state.detect_oscillation(window=3):
            action = DeveloperAction.REQUEST_CONFIRMATION
            confidence = 0.95
            reason = "Repeated failure signature or decision oscillation detected; human intervention required."
            params = {
                "reason": "loop_detected",
                "failure_count": len(state.failure_signatures),
            }
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 1: Targeted test passed -> Rerun full build to verify no regression
        if last_decision_str == DeveloperAction.RUN_TARGETED_TEST.value and exit_code == 0 and not has_error:
            action = DeveloperAction.RERUN_BUILD
            confidence = 0.92
            reason = "Targeted test passed; running full build suite to verify no regressions."
            params = {"command": "uv run pytest"}
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 2: Fix was applied -> Run targeted test
        if last_decision_str == DeveloperAction.APPLY_FIX.value:
            action = DeveloperAction.RUN_TARGETED_TEST
            confidence = 0.94
            reason = "Fix patch applied; executing targeted test to verify resolution."
            target_test = observation.metadata.get("target_test")
            if not target_test and culprit_file:
                clean_path = culprit_file.replace("\\", "/")
                base_name = os.path.basename(clean_path)
                target_test = f"tests/test_{base_name}"
            params = {
                "target_file": culprit_file,
                "target_test": target_test or "tests/",
            }
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 3: Clean build and full checks passed -> DONE
        if clean_build and (decisions_count > 0 or "passed" in terminal_out.lower()):
            action = DeveloperAction.DONE
            confidence = 0.98
            reason = "Build and test suite passed with exit code 0; task verified complete."
            params = {"status": "success", "exit_code": 0}
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 4: Error occurred, culprit file identified, file snippet not yet inspected
        if has_error and culprit_file and last_decision_str == DeveloperAction.INSPECT_ERROR.value:
            action = DeveloperAction.INSPECT_FILE
            confidence = 0.89
            reason = f"Culprit file '{culprit_file}' identified from error trace; inspecting file context."
            params = {"target_file": culprit_file, "line_range": [-20, 20]}
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 5: Culprit file inspected, inspect git diff or apply fix
        if has_error and culprit_file and last_decision_str == DeveloperAction.INSPECT_FILE.value:
            if observation.metadata.get("ambiguous_diff", False) or "git" in terminal_out.lower():
                action = DeveloperAction.INSPECT_RECENT_CHANGE
                confidence = 0.85
                reason = "Error root cause ambiguous; inspecting git changes for recent regressions."
                params = {"git_command": "git diff"}
            else:
                action = DeveloperAction.APPLY_FIX
                confidence = 0.88
                reason = f"Root cause diagnosed in '{culprit_file}'; applying targeted fix."
                params = {
                    "target_file": culprit_file,
                    "fix_patch": observation.metadata.get("suggested_fix", ""),
                }
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 6: Error present but not yet parsed / culprit unknown
        if has_error:
            action = DeveloperAction.INSPECT_ERROR
            confidence = 0.91
            reason = "Process failed with error; inspecting compiler/test error trace."
            params = {
                "error_text": recent_error or terminal_out[-500:],
                "exit_code": exit_code,
            }
            probs = self._build_probabilities(action, confidence)
            return DeveloperDecision(
                action=action,
                confidence=confidence,
                probabilities=probs,
                parameters=params,
                metadata={"reasoning": reason, "provider": self.name},
            )

        # Rule 7: Initial assessment or idle state -> Rerun build
        action = DeveloperAction.RERUN_BUILD
        confidence = 0.85
        reason = "Baseline project state assessment; executing build/test suite."
        params = {"command": "uv run pytest"}
        probs = self._build_probabilities(action, confidence)
        return DeveloperDecision(
            action=action,
            confidence=confidence,
            probabilities=probs,
            parameters=params,
            metadata={"reasoning": reason, "provider": self.name},
        )

"""Developer action space and decision dataclass for JEVON.

Defines the bounded 8-action developer decision space and typed decision structures.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DeveloperAction(StrEnum):
    """Bounded, mutually exclusive developer action space (exactly 8 actions)."""

    INSPECT_ERROR = "inspect_error"
    INSPECT_FILE = "inspect_file"
    RUN_TARGETED_TEST = "run_targeted_test"
    RERUN_BUILD = "rerun_build"
    INSPECT_RECENT_CHANGE = "inspect_recent_change"
    APPLY_FIX = "apply_fix"
    REQUEST_CONFIRMATION = "request_confirmation"
    DONE = "done"

    @classmethod
    def all_actions(cls) -> tuple[DeveloperAction, ...]:
        """Return all 8 bounded developer actions."""
        return (
            cls.INSPECT_ERROR,
            cls.INSPECT_FILE,
            cls.RUN_TARGETED_TEST,
            cls.RERUN_BUILD,
            cls.INSPECT_RECENT_CHANGE,
            cls.APPLY_FIX,
            cls.REQUEST_CONFIRMATION,
            cls.DONE,
        )

    @property
    def is_terminal(self) -> bool:
        """Return True if this action terminates the decision loop."""
        return self == DeveloperAction.DONE

    def __str__(self) -> str:
        """Return raw action name string."""
        return self.value


def normalize_probabilities(probs: dict[str | DeveloperAction, float]) -> dict[str, float]:
    """Normalize a probability distribution across all 8 DeveloperActions to sum to 1.0."""
    all_actions = DeveloperAction.all_actions()
    converted: dict[str, float] = {}

    for action in all_actions:
        val = probs.get(action, probs.get(action.value, 0.0))
        converted[action.value] = max(0.0, float(val))

    total = sum(converted.values())
    if math.isnan(total) or math.isinf(total) or total <= 0.0:
        # Uniform fallback if uninitialized, non-finite, or zero sum
        uniform = 1.0 / len(all_actions)
        return {a.value: uniform for a in all_actions}

    normalized = {k: v / total for k, v in converted.items()}
    # Adjust floating point residual onto highest probability to guarantee exact 1.0 sum
    diff = 1.0 - sum(normalized.values())
    if diff != 0.0:
        max_k = max(normalized, key=lambda k: normalized[k])
        normalized[max_k] += diff

    return normalized


@dataclass
class DeveloperDecision:
    """Typed decision output from a DecisionProvider.

    Attributes:
        action: The chosen DeveloperAction.
        confidence: Confidence score in range [0.0, 1.0].
        probabilities: Normalized probability distribution over all 8 actions.
        parameters: Target parameters for the action (e.g., target_file, test_command).
        metadata: Diagnostic and audit metadata (e.g., reasoning, provider_name).
    """

    action: DeveloperAction
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce action if passed as string
        if isinstance(self.action, str) and not isinstance(self.action, DeveloperAction):
            self.action = DeveloperAction(self.action)

        # Validate action
        if self.action not in DeveloperAction.all_actions():
            raise ValueError(f"Invalid action {self.action}; must be one of {DeveloperAction.all_actions()}")

        # Bound confidence between 0.0 and 1.0 (clamping NaN/Inf to 0.0)
        c = float(self.confidence)
        if math.isnan(c) or math.isinf(c):
            self.confidence = 0.0
        else:
            self.confidence = max(0.0, min(1.0, c))

        # Ensure probabilities contain all 8 actions and sum to 1.0
        self.probabilities = normalize_probabilities(self.probabilities)

    @property
    def is_terminal(self) -> bool:
        """True if the decision terminates the loop."""
        return self.action == DeveloperAction.DONE

    @property
    def requires_confirmation(self) -> bool:
        """True if execution requires human developer confirmation."""
        return (
            self.action == DeveloperAction.REQUEST_CONFIRMATION
            or bool(self.metadata.get("destructive", False))
            or self.confidence < 0.60
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize decision to a plain dictionary."""
        return {
            "action": self.action.value,
            "confidence": self.confidence,
            "probabilities": dict(self.probabilities),
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
            "is_terminal": self.is_terminal,
            "requires_confirmation": self.requires_confirmation,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize decision to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeveloperDecision:
        """Deserialize decision from a dictionary."""
        action_val = data["action"]
        action = DeveloperAction(action_val) if isinstance(action_val, str) else action_val

        return cls(
            action=action,
            confidence=float(data.get("confidence", 0.0)),
            probabilities=dict(data.get("probabilities", {})),
            parameters=dict(data.get("parameters", {})),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> DeveloperDecision:
        """Deserialize decision from JSON string."""
        return cls.from_dict(json.loads(json_str))


# Convenient alias for backward/cross-compatibility
Decision = DeveloperDecision

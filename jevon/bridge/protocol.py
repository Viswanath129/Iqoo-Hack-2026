"""Protocol data models for JEVON Office Kit Bridge.

Defines the strongly-typed telemetry frames exchanged between the Phone
(intelligence center) and Laptop (development execution environment).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from jevon.decision.actions import DeveloperAction


@dataclass(frozen=True)
class DecisionCommand:
    """Phone-to-Laptop decision command dispatched across Office Kit Bridge."""

    command_id: str
    session_id: str
    step_index: int
    timestamp_ns: int
    action: DeveloperAction
    confidence: float
    probabilities: dict[str, float]
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.action, str) and not isinstance(self.action, DeveloperAction):
            object.__setattr__(self, "action", DeveloperAction(self.action))
        if self.action not in DeveloperAction.all_actions():
            raise ValueError(f"Action {self.action} not in bounded action set")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be in [0.0, 1.0]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "session_id": self.session_id,
            "step_index": self.step_index,
            "timestamp_ns": self.timestamp_ns,
            "action": self.action.value,
            "confidence": self.confidence,
            "probabilities": dict(self.probabilities),
            "parameters": dict(self.parameters),
            "requires_confirmation": self.requires_confirmation,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionCommand:
        action_val = data["action"]
        action = DeveloperAction(action_val) if isinstance(action_val, str) else action_val
        return cls(
            command_id=str(data["command_id"]),
            session_id=str(data.get("session_id", "")),
            step_index=int(data.get("step_index", 0)),
            timestamp_ns=int(data.get("timestamp_ns", time.time_ns())),
            action=action,
            confidence=float(data.get("confidence", 0.0)),
            probabilities=dict(data.get("probabilities", {})),
            parameters=dict(data.get("parameters", {})),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> DecisionCommand:
        return cls.from_dict(json.loads(json_str))

    def is_valid(self) -> bool:
        """Validate command parameters and confidence boundaries."""
        return bool(
            self.command_id
            and self.action in DeveloperAction.all_actions()
            and 0.0 <= self.confidence <= 1.0
        )


@dataclass(frozen=True)
class ActionReceipt:
    """Laptop-to-Phone execution and verification receipt."""

    command_id: str
    session_id: str
    step_index: int
    action: DeveloperAction
    status: str  # "SUCCESS", "FAILED", "BLOCKED_BY_SAFETY", "ABORTED"
    exit_code: int
    stdout: str
    stderr: str
    verification_passed: bool
    verification_details: dict[str, Any] = field(default_factory=dict)
    duration_ns: int = 0
    timestamp_ns: int = field(default_factory=time.time_ns)

    VALID_STATUSES = ("SUCCESS", "FAILED", "BLOCKED_BY_SAFETY", "ABORTED")

    def __post_init__(self) -> None:
        if isinstance(self.action, str) and not isinstance(self.action, DeveloperAction):
            object.__setattr__(self, "action", DeveloperAction(self.action))
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'; must be one of {self.VALID_STATUSES}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "session_id": self.session_id,
            "step_index": self.step_index,
            "action": self.action.value,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "verification_passed": self.verification_passed,
            "verification_details": dict(self.verification_details),
            "duration_ns": self.duration_ns,
            "timestamp_ns": self.timestamp_ns,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionReceipt:
        action_val = data["action"]
        action = DeveloperAction(action_val) if isinstance(action_val, str) else action_val
        return cls(
            command_id=str(data["command_id"]),
            session_id=str(data.get("session_id", "")),
            step_index=int(data.get("step_index", 0)),
            action=action,
            status=str(data.get("status", "SUCCESS")),
            exit_code=int(data.get("exit_code", 0)),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            verification_passed=bool(data.get("verification_passed", False)),
            verification_details=dict(data.get("verification_details", {})),
            duration_ns=int(data.get("duration_ns", 0)),
            timestamp_ns=int(data.get("timestamp_ns", time.time_ns())),
        )

    @classmethod
    def from_json(cls, json_str: str) -> ActionReceipt:
        return cls.from_dict(json.loads(json_str))

    def is_valid(self) -> bool:
        """Validate receipt status and bounds."""
        return bool(
            self.command_id
            and self.action in DeveloperAction.all_actions()
            and self.status in {"SUCCESS", "FAILED", "BLOCKED_BY_SAFETY", "ABORTED"}
        )

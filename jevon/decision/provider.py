"""DecisionProvider abstract base class and StateObservation contract for JEVON."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from jevon.decision.actions import DeveloperDecision
from jevon.truth_first.state import TruthFirstState


@dataclass(frozen=True)
class StateObservation:
    """Telemetry observation emitted from developer environment to phone decision layer.

    Attributes:
        session_id: Unique identifier for current session.
        step_index: Incremental step index in decision cycle.
        timestamp_ns: Nanosecond timestamp of observation.
        working_directory: Root path of active workspace.
        active_file: Culprit or target file path currently focused/edited.
        terminal_output: Raw stdout/stderr tail from last terminal command.
        compiler_exit_code: Process exit code (0 for pass, non-zero for error, None for idle).
        git_status_summary: Summary of git tree status (e.g. porcelain or branch info).
        recent_error: Extracted error message or exception trace.
        metadata: Custom metadata dictionary.
    """

    session_id: str = ""
    step_index: int = 0
    timestamp_ns: int = field(default_factory=time.time_ns)
    working_directory: str = ""
    active_file: str | None = None
    terminal_output: str = ""
    compiler_exit_code: int | None = None
    git_status_summary: str = ""
    recent_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert observation to dictionary."""
        return {
            "session_id": self.session_id,
            "step_index": self.step_index,
            "timestamp_ns": self.timestamp_ns,
            "working_directory": self.working_directory,
            "active_file": self.active_file,
            "terminal_output": self.terminal_output,
            "compiler_exit_code": self.compiler_exit_code,
            "git_status_summary": self.git_status_summary,
            "recent_error": self.recent_error,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateObservation:
        """Construct StateObservation from dictionary."""
        return cls(
            session_id=str(data.get("session_id", "")),
            step_index=int(data.get("step_index", 0)),
            timestamp_ns=int(data.get("timestamp_ns", time.time_ns())),
            working_directory=str(data.get("working_directory", "")),
            active_file=data.get("active_file"),
            terminal_output=str(data.get("terminal_output", "")),
            compiler_exit_code=data.get("compiler_exit_code"),
            git_status_summary=str(data.get("git_status_summary", "")),
            recent_error=data.get("recent_error"),
            metadata=dict(data.get("metadata", {})),
        )


class DecisionProvider(ABC):
    """Abstract interface for all developer decision backends."""

    @property
    def name(self) -> str:
        """Human-readable provider identification."""
        return self.__class__.__name__

    def is_available(self) -> bool:
        """Return True if the backend is initialized and operational."""
        return True

    @abstractmethod
    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        """Evaluates developer state and observation, returning a typed DeveloperDecision.

        The decision must specify an action from the bounded 8-action set, a confidence
        score in [0.0, 1.0], and normalized probabilities summing to 1.0.
        """
        pass

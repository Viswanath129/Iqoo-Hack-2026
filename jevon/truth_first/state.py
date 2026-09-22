"""Truth-First State Model for JEVON.

Maintains an immutable/audit-friendly 7-pillar ledger:
1. GOAL: Developer's primary objective.
2. CONSTRAINTS: Invariants, safety constraints, allowlists.
3. FACTS: Empirically verified truths from observation/verification.
4. DECISIONS: Ordered sequence of chosen actions and rationale.
5. EVIDENCE: Verbatim quotes, compiler errors, stack traces, diffs.
6. OPEN_QUESTIONS: Active hypotheses and diagnostic queries.
7. FAILED_APPROACHES: Disproven hypotheses and failed fix attempts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from jevon.decision.actions import DeveloperAction, DeveloperDecision


def compute_failure_signature(
    exit_code: int | None,
    culprit_file: str | None,
    error_summary: str | None,
) -> str:
    """Compute a deterministic hash signature for a failure state."""
    norm_file = culprit_file.replace("\\", "/") if culprit_file else ""
    raw = json.dumps([exit_code, norm_file, error_summary or ""], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class TruthFirstState:
    """7-pillar state tracking ledger for the developer decision loop."""

    # 1. Goal
    goal: str = ""

    # 2. Constraints
    constraints: list[str] = field(default_factory=list)

    # 3. Facts (empirically verified observations)
    facts: list[str] = field(default_factory=list)

    # 4. Decisions (decision history)
    decisions: list[dict[str, Any]] = field(default_factory=list)

    # 5. Evidence (verbatim compiler/test outputs, snippets)
    evidence: list[str] = field(default_factory=list)

    # 6. Open Questions (hypotheses under test)
    open_questions: list[str] = field(default_factory=list)

    # 7. Failed Approaches (disproven attempts)
    failed_approaches: list[dict[str, Any]] = field(default_factory=list)

    # Metadata & Tracking
    cycle_index: int = 0
    session_id: str = ""
    timestamp_utc: float = field(default_factory=time.time)
    failure_signatures: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- Pillar 1: Goal ---
    def set_goal(self, goal: str) -> None:
        """Set or update the primary developer goal."""
        self.goal = goal.strip()

    # --- Pillar 2: Constraints ---
    def add_constraint(self, constraint: str) -> None:
        """Add a safety invariant or boundary constraint."""
        c = constraint.strip()
        if c and c not in self.constraints:
            self.constraints.append(c)

    # --- Pillar 3: Facts ---
    def add_fact(self, fact: str) -> None:
        """Record an empirically verified observation."""
        f = fact.strip()
        if f and f not in self.facts:
            self.facts.append(f)

    # --- Pillar 4: Decisions ---
    def record_decision(
        self,
        decision: DeveloperDecision | str | dict[str, Any],
        parameters: dict[str, Any] | None = None,
        reasoning: str = "",
    ) -> None:
        """Append a decision to the audit ledger."""
        if isinstance(decision, DeveloperDecision):
            entry = {
                "step": len(self.decisions) + 1,
                "action": decision.action.value,
                "confidence": decision.confidence,
                "parameters": dict(decision.parameters),
                "reasoning": str(decision.metadata.get("reasoning", reasoning)),
                "timestamp_utc": time.time(),
            }
        elif isinstance(decision, DeveloperAction):
            entry = {
                "step": len(self.decisions) + 1,
                "action": decision.value,
                "confidence": 1.0,
                "parameters": dict(parameters or {}),
                "reasoning": reasoning,
                "timestamp_utc": time.time(),
            }
        elif isinstance(decision, dict):
            entry = dict(decision)
            entry.setdefault("step", len(self.decisions) + 1)
            entry.setdefault("timestamp_utc", time.time())
        else:
            action_str = decision.value if hasattr(decision, "value") else str(decision)
            entry = {
                "step": len(self.decisions) + 1,
                "action": action_str,
                "confidence": 1.0,
                "parameters": dict(parameters or {}),
                "reasoning": reasoning,
                "timestamp_utc": time.time(),
            }
        self.decisions.append(entry)

    # --- Pillar 5: Evidence ---
    def add_evidence(self, evidence: str) -> None:
        """Add verbatim code snippet, error message, or log excerpt."""
        if evidence and evidence.strip() and evidence not in self.evidence:
            self.evidence.append(evidence)

    # --- Pillar 6: Open Questions ---
    def add_open_question(self, question: str) -> None:
        """Add a hypothesis or diagnostic query to investigate."""
        q = question.strip()
        if q and q not in self.open_questions:
            self.open_questions.append(q)

    def resolve_open_question(self, question: str, answer: str | None = None) -> None:
        """Resolve and remove an open question, optionally recording the answer as a fact."""
        q = question.strip()
        if q in self.open_questions:
            self.open_questions.remove(q)
        if answer:
            self.add_fact(f"Resolved '{q}': {answer.strip()}")

    # --- Pillar 7: Failed Approaches & Signatures ---
    def add_failed_approach(
        self,
        approach: str | dict[str, Any],
        reason: str = "",
        signature: str | None = None,
    ) -> None:
        """Record an unsuccessful fix attempt or failed hypothesis."""
        if isinstance(approach, dict):
            entry = dict(approach)
            entry.setdefault("reason", reason)
            entry.setdefault("signature", signature or "")
        else:
            entry = {
                "approach": str(approach),
                "reason": reason,
                "signature": signature or "",
                "timestamp_utc": time.time(),
            }
        self.failed_approaches.append(entry)

        if signature:
            self.record_failure_signature(signature)

    def record_failure(
        self,
        cycle: int = 0,
        approach: str = "",
        reason: str = "",
        exit_code: int = 1,
        signature: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Record an unsuccessful execution attempt (alias for add_failed_approach)."""
        sig = signature or (f"exit_{exit_code}" if exit_code else None)
        self.add_failed_approach(
            approach={"approach": approach, "cycle": cycle, "exit_code": exit_code},
            reason=reason,
            signature=sig,
        )

    def append_decision(
        self,
        action: Any,
        rationale: str = "",
        params: dict[str, Any] | None = None,
        probs: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        """Append a decision to the audit ledger (alias for record_decision)."""
        entry_params = dict(params or {})
        if probs:
            entry_params["probabilities"] = probs
        self.record_decision(decision=action, parameters=entry_params, reasoning=rationale)

    def append_fact(self, fact: str) -> None:
        """Record an empirically verified observation (alias for add_fact)."""
        self.add_fact(fact)

    def append_evidence(self, evidence: str) -> None:
        """Add verbatim snippet or log excerpt (alias for add_evidence)."""
        self.add_evidence(evidence)

    def record_failure_signature(self, signature: str) -> None:
        """Record a failure state signature in sequential history."""
        if signature:
            self.failure_signatures.append(signature)

    def detect_repeated_failure(self, window: int = 3) -> bool:
        """Return True if the last `window` failure signatures are identical."""
        if len(self.failure_signatures) < window:
            return False
        recent = self.failure_signatures[-window:]
        return len(set(recent)) == 1

    def detect_oscillation(self, window: int = 3) -> bool:
        """Return True if recent decisions repeat the same action or form periodic cycles."""
        actions = [d.get("action") for d in self.decisions if d.get("action")]
        if not actions:
            return False

        # 1. Single-action stagnation: last `window` decisions repeat the same action
        effective_window = max(2, window)
        if len(actions) >= effective_window and len(set(actions[-effective_window:])) == 1:
            return True

        # 2. 2-cycle periodic oscillation (A -> B -> A -> B)
        if len(actions) >= 4 and actions[-4:] == actions[-2:] * 2 and actions[-1] != actions[-2]:
            return True

        # 3. 3-cycle periodic oscillation (A -> B -> C -> A -> B -> C)
        return bool(
            len(actions) >= 6
            and actions[-6:] == actions[-3:] * 2
            and len(set(actions[-3:])) == 3
        )

    # --- Serialization ---
    def to_dict(self) -> dict[str, Any]:
        """Convert state to serializable dictionary."""
        return {
            "goal": self.goal,
            "constraints": list(self.constraints),
            "facts": list(self.facts),
            "decisions": copy.deepcopy(self.decisions),
            "evidence": list(self.evidence),
            "open_questions": list(self.open_questions),
            "failed_approaches": copy.deepcopy(self.failed_approaches),
            "cycle_index": self.cycle_index,
            "session_id": self.session_id,
            "timestamp_utc": self.timestamp_utc,
            "failure_signatures": list(self.failure_signatures),
            "metadata": copy.deepcopy(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize state to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TruthFirstState:
        """Reconstruct TruthFirstState from dictionary."""
        return cls(
            goal=data.get("goal", ""),
            constraints=list(data.get("constraints", [])),
            facts=list(data.get("facts", [])),
            decisions=copy.deepcopy(data.get("decisions", [])),
            evidence=list(data.get("evidence", [])),
            open_questions=list(data.get("open_questions", [])),
            failed_approaches=copy.deepcopy(data.get("failed_approaches", [])),
            cycle_index=int(data.get("cycle_index", 0)),
            session_id=str(data.get("session_id", "")),
            timestamp_utc=float(data.get("timestamp_utc", time.time())),
            failure_signatures=list(data.get("failure_signatures", [])),
            metadata=copy.deepcopy(data.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TruthFirstState:
        """Deserialize TruthFirstState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def format_audit_log(self) -> str:
        """Render a clean Markdown audit log representation of the 7 pillars."""
        lines = [
            "# Truth-First State Ledger",
            f"**Cycle Index**: {self.cycle_index} | **Session**: {self.session_id or 'N/A'}",
            "",
            f"## 1. GOAL\n{self.goal or 'No goal defined.'}",
            "",
            "## 2. CONSTRAINTS",
        ]
        if self.constraints:
            lines.extend(f"- {c}" for c in self.constraints)
        else:
            lines.append("*(none)*")

        lines.append("\n## 3. FACTS")
        if self.facts:
            lines.extend(f"- {f}" for f in self.facts)
        else:
            lines.append("*(none recorded)*")

        lines.append("\n## 4. DECISIONS")
        if self.decisions:
            for d in self.decisions:
                lines.append(f"- Step {d.get('step')}: **{d.get('action')}** (conf={d.get('confidence')})")
        else:
            lines.append("*(no decisions yet)*")

        lines.append("\n## 5. EVIDENCE")
        if self.evidence:
            for e in self.evidence:
                lines.append(f"```\n{e}\n```")
        else:
            lines.append("*(none)*")

        lines.append("\n## 6. OPEN QUESTIONS")
        if self.open_questions:
            lines.extend(f"- {q}" for q in self.open_questions)
        else:
            lines.append("*(none)*")

        lines.append("\n## 7. FAILED APPROACHES")
        if self.failed_approaches:
            for fa in self.failed_approaches:
                lines.append(f"- {fa.get('approach')}: {fa.get('reason')}")
        else:
            lines.append("*(none)*")

        return "\n".join(lines)

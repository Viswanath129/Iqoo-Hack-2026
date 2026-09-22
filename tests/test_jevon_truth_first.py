"""Comprehensive unit tests for JEVON Truth-First State Model (R3)."""

from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.truth_first.state import TruthFirstState, compute_failure_signature


def test_truth_first_state_initialization() -> None:
    """TruthFirstState must initialize all 7 pillars empty or with provided values."""
    state = TruthFirstState(goal="Fix failing pytest")
    assert state.goal == "Fix failing pytest"
    assert state.constraints == []
    assert state.facts == []
    assert state.decisions == []
    assert state.evidence == []
    assert state.open_questions == []
    assert state.failed_approaches == []
    assert state.cycle_index == 0


def test_truth_first_pillar_1_goal() -> None:
    """Setting and updating goal in state."""
    state = TruthFirstState()
    assert state.goal == ""
    state.set_goal("Achieve 100% test pass rate")
    assert state.goal == "Achieve 100% test pass rate"


def test_truth_first_pillar_2_constraints() -> None:
    """Adding constraints and preventing duplicates."""
    state = TruthFirstState()
    state.add_constraint("zero cloud API keys")
    state.add_constraint("no hardcoding test results")
    state.add_constraint("zero cloud API keys")  # duplicate

    assert len(state.constraints) == 2
    assert "zero cloud API keys" in state.constraints
    assert "no hardcoding test results" in state.constraints


def test_truth_first_pillar_3_facts() -> None:
    """Recording empirically verified facts and preventing duplicates."""
    state = TruthFirstState()
    state.add_fact("Compiler returned exit code 1")
    state.add_fact("Line 42 in actions.py raised SyntaxError")
    state.add_fact("Compiler returned exit code 1")  # duplicate

    assert len(state.facts) == 2
    assert state.facts[0] == "Compiler returned exit code 1"
    assert state.facts[1] == "Line 42 in actions.py raised SyntaxError"


def test_truth_first_pillar_4_decisions() -> None:
    """Recording decisions as DeveloperDecision, string, or dict."""
    state = TruthFirstState()

    # Record via DeveloperDecision
    d1 = DeveloperDecision(
        action=DeveloperAction.INSPECT_ERROR,
        confidence=0.91,
        parameters={"error_text": "SyntaxError"},
        metadata={"reasoning": "Parse trace"},
    )
    state.record_decision(d1)

    # Record via string
    state.record_decision("inspect_file", parameters={"target": "foo.py"}, reasoning="Examine context")

    assert len(state.decisions) == 2
    assert state.decisions[0]["step"] == 1
    assert state.decisions[0]["action"] == "inspect_error"
    assert state.decisions[0]["confidence"] == 0.91

    assert state.decisions[1]["step"] == 2
    assert state.decisions[1]["action"] == "inspect_file"


def test_truth_first_pillar_5_evidence() -> None:
    """Appending verbatim evidence snippets."""
    state = TruthFirstState()
    trace = "Traceback (most recent call last):\n  File 'test.py', line 1"
    state.add_evidence(trace)
    state.add_evidence(trace)  # duplicate check

    assert len(state.evidence) == 1
    assert state.evidence[0] == trace


def test_truth_first_pillar_6_open_questions_and_resolution() -> None:
    """Adding open questions and resolving them with fact updates."""
    state = TruthFirstState()
    state.add_open_question("Does Python 3.11 support nested f-string quotes?")
    assert len(state.open_questions) == 1

    state.resolve_open_question(
        "Does Python 3.11 support nested f-string quotes?",
        answer="No, Python 3.11 requires backslash-free f-string expressions.",
    )
    assert len(state.open_questions) == 0
    assert any("Resolved" in f for f in state.facts)


def test_truth_first_pillar_7_failed_approaches() -> None:
    """Recording failed approaches with rationale and failure signatures."""
    state = TruthFirstState()
    state.add_failed_approach(
        approach="Replacing nested quote with single quote",
        reason="SyntaxError still raised on line 707",
        signature="sig_707_syntax",
    )
    assert len(state.failed_approaches) == 1
    assert state.failed_approaches[0]["signature"] == "sig_707_syntax"
    assert state.failure_signatures == ["sig_707_syntax"]


def test_compute_failure_signature_deterministic() -> None:
    """Failure signature computation must be strictly deterministic."""
    sig1 = compute_failure_signature(1, "foo.py", "SyntaxError")
    sig2 = compute_failure_signature(1, "foo.py", "SyntaxError")
    sig3 = compute_failure_signature(2, "foo.py", "SyntaxError")

    assert sig1 == sig2
    assert sig1 != sig3
    assert len(sig1) == 16


def test_detect_repeated_failure() -> None:
    """Detect repeated failure signatures across a window of steps."""
    state = TruthFirstState()
    sig = compute_failure_signature(1, "broken.py", "AssertionError")

    # Less than window (default 3)
    state.record_failure_signature(sig)
    state.record_failure_signature(sig)
    assert state.detect_repeated_failure(window=3) is False

    # 3 consecutive identical signatures
    state.record_failure_signature(sig)
    assert state.detect_repeated_failure(window=3) is True

    # Broken by a different signature
    diff_sig = compute_failure_signature(1, "other.py", "KeyError")
    state.record_failure_signature(diff_sig)
    assert state.detect_repeated_failure(window=3) is False


def test_detect_oscillation() -> None:
    """Detect oscillation when decisions repeat the same action."""
    state = TruthFirstState()
    for _ in range(2):
        state.record_decision("inspect_file")
    assert state.detect_oscillation(window=3) is False

    state.record_decision("inspect_file")
    assert state.detect_oscillation(window=3) is True

    state.record_decision("apply_fix")
    assert state.detect_oscillation(window=3) is False


def test_truth_first_state_serialization_roundtrip() -> None:
    """TruthFirstState must cleanly serialize and deserialize to/from dict and JSON."""
    original = TruthFirstState(
        goal="Run tests",
        constraints=["offline only"],
        facts=["Exit code was 0"],
        cycle_index=2,
        session_id="session_xyz",
    )
    original.record_decision("done", reasoning="clean build")
    original.add_evidence("201 passed in 15.43s")

    # Dict roundtrip
    data = original.to_dict()
    from_d = TruthFirstState.from_dict(data)
    assert from_d.goal == original.goal
    assert from_d.constraints == original.constraints
    assert from_d.facts == original.facts
    assert from_d.cycle_index == original.cycle_index
    assert len(from_d.decisions) == 1

    # JSON roundtrip
    json_str = original.to_json()
    from_j = TruthFirstState.from_json(json_str)
    assert from_j.goal == original.goal
    assert from_j.session_id == original.session_id
    assert from_j.evidence == original.evidence


def test_format_audit_log_renders_all_7_pillars() -> None:
    """format_audit_log must include headers for all 7 pillars."""
    state = TruthFirstState(goal="Implement JEVON M1")
    state.add_constraint("Zero cloud API keys")
    state.add_fact("All tests pass")
    state.record_decision("done")
    state.add_evidence("Test suite passed")
    state.add_open_question("Are all pillars covered?")
    state.add_failed_approach("Hardcoding values", reason="Violates integrity mandate")

    audit = state.format_audit_log()
    assert "## 1. GOAL" in audit
    assert "## 2. CONSTRAINTS" in audit
    assert "## 3. FACTS" in audit
    assert "## 4. DECISIONS" in audit
    assert "## 5. EVIDENCE" in audit
    assert "## 6. OPEN QUESTIONS" in audit
    assert "## 7. FAILED APPROACHES" in audit
    assert "Zero cloud API keys" in audit
    assert "Violates integrity mandate" in audit

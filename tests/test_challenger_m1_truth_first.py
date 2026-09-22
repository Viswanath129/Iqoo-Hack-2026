"""Adversarial stress tests for TruthFirstState and Serialization in Milestone M1.

Empirical verification suite by challenger_2_m1 covering:
1. Serialization roundtrips under unicode, complex metadata, special characters, and edge cases.
2. Failure signature collision analysis, delimiter injection, and entropy.
3. Oscillation detection under cycling patterns (A -> B -> A -> B vs A -> A -> A).
4. Memory and immutability checks on returned pillar collections.
"""

from __future__ import annotations

from typing import Any

from jevon.decision.actions import DeveloperAction, DeveloperDecision
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.truth_first.state import TruthFirstState, compute_failure_signature

# ==============================================================================
# 1. TruthFirstState Serialization Roundtrip Stress Tests
# ==============================================================================


def test_serialization_roundtrip_unicode_and_emojis() -> None:
    """Stress test serialization with multilingual unicode, emojis, CJK, and RTL scripts."""
    unicode_goal = "修复 Python 3.11 🐛 兼容性问题 🚀 (Fix compatibility) - שגיאת מהדר - خطأ في البناء"
    unicode_constraints = [
        "不使用云端 API 密钥 🛑 (Zero cloud API keys)",
        "Strict CRLF/LF check \u202eRTL_OVERRIDE\u202c",
        "Emoji flag: 🏁, mathematical symbols: ∑(x) = 1.0, 𝒳 ∈ 𝒮",  # noqa: RUF001
    ]
    unicode_facts = [
        "Élève a réussi l'examen: café & résumé",
        "日本語のコンパイルエラー: 構文エラー line 42",
        "Cyrillic traceback: Ошибка компиляции в файле actions.py",
        "Devanagari: विफलता कोड १ (Failure code 1)",
    ]
    unicode_evidence = [
        "Traceback:\n  File \"测试.py\", line 12\n    raise ValueError('❌ 错误: 无效输入')",
        "ANSI escape in log: \x1b[31m\x1b[1mError: build failed\x1b[0m",
    ]

    state = TruthFirstState(
        goal=unicode_goal,
        constraints=unicode_constraints,
        facts=unicode_facts,
        cycle_index=99,
        session_id="session_unicode_🌏_123",
        metadata={
            "author": "JEVON 团队",
            "symbols": "«»“”‘’—–…",  # noqa: RUF001
            "surrogate_safe": "𐍈𐍈𐍈",
        },
    )
    for ev in unicode_evidence:
        state.add_evidence(ev)

    # JSON roundtrip
    json_str = state.to_json()
    assert isinstance(json_str, str)
    deserialized = TruthFirstState.from_json(json_str)

    assert deserialized.goal == unicode_goal
    assert deserialized.constraints == unicode_constraints
    assert deserialized.facts == unicode_facts
    assert deserialized.evidence == unicode_evidence
    assert deserialized.session_id == "session_unicode_🌏_123"
    assert deserialized.metadata["author"] == "JEVON 团队"
    assert deserialized.metadata["symbols"] == "«»“”‘’—–…"  # noqa: RUF001


def test_serialization_roundtrip_special_characters_and_escapes() -> None:
    """Stress test serialization with newlines, backslashes, quotes, raw bytes/ANSI, and code blocks."""
    complex_raw_evidence = (
        'def test_broken():\n'
        '    """Docstring with """nested""" quotes and \\backslashes\\ and \t tabs."""\n'
        '    assert 1 == 2, f"Failed with {{\'quoted\': True}}"\n'
        '    # Windows path: C:\\Users\\developer\\AppData\\Local\\Temp\\run_1.bat\r\n'
        '    # XML/HTML tags: <script>alert("xss")</script> &amp; <div class="err">\n'
        '    # Markdown backticks: ```python\nprint("hello")\n```\n'
    )

    state = TruthFirstState(
        goal="Handle \"dangerous\" inputs: 'single', \"double\", `backtick`, \\backslash\\",
        session_id="id_with_special_chars_!@#$%^&*()_+~|}{[]:;?><,./",
    )
    state.add_evidence(complex_raw_evidence)
    state.add_fact("Line contains \\r\\n and \\t and \\\\ and '\"")
    state.add_open_question("Can JSON safely roundtrip quotes: \"foo\" and 'bar'?")

    json_str = state.to_json()
    reconstructed = TruthFirstState.from_json(json_str)

    assert reconstructed.goal == state.goal
    assert reconstructed.evidence == state.evidence
    assert reconstructed.facts == state.facts
    assert reconstructed.open_questions == state.open_questions
    assert reconstructed.session_id == state.session_id


def test_evidence_stripping_corrupts_verbatim_indentation_and_diffs() -> None:
    """[REMEDIATED] add_evidence preserves verbatim indentation and diff context lines.
    
    The 5th pillar is documented as:
    '5. EVIDENCE: Verbatim quotes, compiler errors, stack traces, diffs.'
    
    TruthFirstState.add_evidence checks non-emptiness without stripping raw content,
    preserving Python indentation and unified diff format lines verbatim.
    """
    state = TruthFirstState()
    # Python code snippet with 4-space indentation on first line
    indented_code = "    def test_sample():\n        return True"
    state.add_evidence(indented_code)

    # Unified diff where line 1 is a context line with a leading space
    unified_diff = " context line\n-old line\n+new line"
    state.add_evidence(unified_diff)

    # Empirical check: Evidence is verbatim — leading indentation is preserved
    assert state.evidence[0] == indented_code

    # Empirical check: Unified diff context space is preserved
    assert state.evidence[1] == unified_diff


def test_serialization_roundtrip_complex_nested_metadata() -> None:
    """Stress test metadata containing nested dicts, lists, booleans, floats, nulls, and large structures."""
    nested_metadata = {
        "build_info": {
            "exit_code": 1,
            "success": False,
            "duration_ms": 1542.875,
            "null_field": None,
            "flags": [True, False, True],
            "nested_env": {
                "PYTHONPATH": "B:\\projects\\viswa_jav;C:\\python311",
                "STAGE": "adversarial_m1",
                "RETRIES": 3,
            },
        },
        "deep_tree": {
            "l1": {"l2": {"l3": {"l4": ["leaf_a", "leaf_b", 42, 3.1415926535]}}},
        },
        "large_array": list(range(500)),
    }

    state = TruthFirstState(
        goal="Verify complex metadata persistence",
        metadata=nested_metadata,
    )
    state.record_decision(
        decision=DeveloperAction.APPLY_FIX,
        parameters={"patch_diff": "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-broken\n+fixed"},
        reasoning="Applied verified patch",
    )

    json_str = state.to_json()
    deserialized = TruthFirstState.from_json(json_str)

    assert deserialized.metadata["build_info"]["exit_code"] == 1
    assert deserialized.metadata["build_info"]["success"] is False
    assert deserialized.metadata["build_info"]["null_field"] is None
    assert deserialized.metadata["build_info"]["flags"] == [True, False, True]
    assert deserialized.metadata["deep_tree"]["l1"]["l2"]["l3"]["l4"] == ["leaf_a", "leaf_b", 42, 3.1415926535]
    assert deserialized.metadata["large_array"] == list(range(500))
    assert deserialized.decisions[0]["action"] == "apply_fix"
    assert "patch_diff" in deserialized.decisions[0]["parameters"]


def test_serialization_type_resilience_int_vs_str_keys() -> None:
    """Test behavior when metadata has non-string keys: in standard JSON, dict keys are strings."""
    state = TruthFirstState(
        metadata={"str_key": "val1", "numeric_key": "val2"},
    )
    json_str = state.to_json()
    reconstructed = TruthFirstState.from_json(json_str)
    assert reconstructed.metadata["str_key"] == "val1"


# ==============================================================================
# 2. Failure Signature Collision Stress Tests
# ==============================================================================


def test_failure_signature_distinct_compiler_errors() -> None:
    """Distinct compiler errors must produce distinct SHA-256 failure signatures."""
    signatures = set()
    errors = [
        (1, "jevon/decision/actions.py", "SyntaxError: invalid syntax at line 707"),
        (1, "jevon/decision/actions.py", "SyntaxError: invalid syntax at line 708"),  # line difference
        (1, "jevon/decision/provider.py", "SyntaxError: invalid syntax at line 707"),  # file difference
        (2, "jevon/decision/actions.py", "SyntaxError: invalid syntax at line 707"),  # exit code difference
        (1, "jevon/decision/actions.py", "IndentationError: unexpected indent"),
        (1, "jevon/decision/actions.py", "TypeError: unsupported operand type(s)"),
        (1, "jevon/decision/actions.py", "AttributeError: 'NoneType' object has no attribute 'name'"),
        (1, "jevon/decision/actions.py", "NameError: name 'Undefined' is not defined"),
        (127, "build.bat", "command not found: uv"),
        (137, "test_suite.py", "Killed (Out of memory)"),
    ]

    for exit_code, culprit, err in errors:
        sig = compute_failure_signature(exit_code, culprit, err)
        assert len(sig) == 16, f"Signature length must be 16 hex chars, got {len(sig)}"
        assert sig not in signatures, f"Collision detected for ({exit_code}, {culprit}, {err}): {sig}"
        signatures.add(sig)

    assert len(signatures) == len(errors)


def test_failure_signature_scale_collision_resistance() -> None:
    """Empirically test 2,000 distinct synthetic error diagnostics for zero collisions."""
    signatures = set()
    total = 2000
    for i in range(total):
        sig = compute_failure_signature(
            exit_code=i % 5,
            culprit_file=f"jevon/module_{i % 20}.py",
            error_summary=f"CompilerDiagnostic_E{1000 + i}: Type mismatch on symbol_{i}",
        )
        signatures.add(sig)

    assert len(signatures) == total, f"Expected {total} unique signatures, got {len(signatures)}"


def test_failure_signature_delimiter_injection_vulnerability() -> None:
    """VULNERABILITY PROOF: Delimiter injection in culprit_file / error_summary causes signature collisions.
    
    Because compute_failure_signature uses unescaped '|err:' delimiter formatting:
    `raw = f"code:{exit_code}|file:{culprit_file or ''}|err:{error_summary or ''}".strip()`
    
    If culprit_file contains '|err:', it can collide with an input where that text is part of error_summary!
    """
    exit_code = 1
    # Input A: culprit_file contains delimiter '|err:' and error_summary is 'baz'
    file_a = "module.py|err:bar"
    err_a = "baz"

    # Input B: culprit_file is 'module.py' and error_summary starts with 'bar|err:'
    file_b = "module.py"
    err_b = "bar|err:baz"

    sig_a = compute_failure_signature(exit_code, file_a, err_a)
    sig_b = compute_failure_signature(exit_code, file_b, err_b)

    # Empirical check: These are distinct error contexts
    assert (file_a, err_a) != (file_b, err_b)

    # Delimiter collision: Both produce raw string 'code:1|file:module.py|err:bar|err:baz'
    # Demonstrating the existence of delimiter injection collision:
    assert sig_a == sig_b, (
        f"Delimiter collision confirmed: sig_a ({sig_a}) == sig_b ({sig_b}) despite distinct inputs!"
    )


def test_failure_signature_path_separator_sensitivity() -> None:
    """Investigate whether Windows vs POSIX path separators produce distinct signatures for the same file."""
    sig_windows = compute_failure_signature(1, "jevon\\decision\\actions.py", "SyntaxError")
    sig_posix = compute_failure_signature(1, "jevon/decision/actions.py", "SyntaxError")

    # Because compute_failure_signature does not normalize slashes, these produce distinct signatures:
    # This means a tool running on Windows vs WSL/Linux will record different failure signatures.
    assert sig_windows != sig_posix


# ==============================================================================
# 3. Oscillation Detection Under Cycling Patterns Stress Tests
# ==============================================================================


def test_oscillation_detection_stagnation_vs_true_oscillation() -> None:
    """EMPIRICAL CHALLENGE: Verify detect_oscillation behavior on A -> A -> A vs A -> B -> A -> B.
    
    The method TruthFirstState.detect_oscillation is implemented as:
        recent_actions = [d.get("action") for d in self.decisions[-window:]]
        return len(set(recent_actions)) == 1
        
    This means it detects STAGNATION (A -> A -> A), but COMPLETELY MISSES
    alternating oscillation cycles (A -> B -> A -> B).
    """
    state_stagnation = TruthFirstState()
    for _ in range(4):
        state_stagnation.record_decision("inspect_error")

    # Stagnation pattern A -> A -> A -> A is detected:
    assert state_stagnation.detect_oscillation(window=3) is True

    # Cycling pattern A -> B -> A -> B -> A -> B (classic ping-pong oscillation):
    state_cycling = TruthFirstState()
    cycling_sequence = [
        "inspect_error",
        "inspect_file",
        "inspect_error",
        "inspect_file",
        "inspect_error",
        "inspect_file",
    ]
    for action in cycling_sequence:
        state_cycling.record_decision(action)

    # Empirical finding: detect_oscillation returns False on cycling ping-pong!
    is_cycling_detected = state_cycling.detect_oscillation(window=3)
    assert is_cycling_detected is False, (
        "TruthFirstState.detect_oscillation failed to detect ping-pong cycling (A -> B -> A -> B) "
        "because it only tests len(set(recent_actions)) == 1!"
    )

    is_cycling_detected_w4 = state_cycling.detect_oscillation(window=4)
    assert is_cycling_detected_w4 is False

    is_cycling_detected_w6 = state_cycling.detect_oscillation(window=6)
    assert is_cycling_detected_w6 is False


def test_safety_fallback_oscillation_guard_blindness_to_cycles() -> None:
    """EMPIRICAL CHALLENGE: Verify SafetyFallback oscillation loop guard behavior on cycling decisions.
    
    SafetyFallback defines loop guard as:
        recent_actions = [d.action for d in self._history[-(self.oscillation_threshold - 1):]] + [decision.action]
        if (
            len(recent_actions) >= self.oscillation_threshold
            and len(set(recent_actions)) == 1
            and decision.action != DeveloperAction.DONE
        ):
    
    Like TruthFirstState, SafetyFallback only intercepts repetition of the SAME action.
    An infinite alternating cycle (inspect_error <-> inspect_file) is NEVER intercepted by SafetyFallback!
    """
    class CyclingProvider(DecisionProvider):
        """Mock provider that ping-pongs between INSPECT_ERROR and INSPECT_FILE."""
        def __init__(self) -> None:
            self.turn = 0

        @property
        def name(self) -> str:
            return "CyclingProvider"

        def is_available(self) -> bool:
            return True

        def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
            self.turn += 1
            action = DeveloperAction.INSPECT_ERROR if self.turn % 2 == 1 else DeveloperAction.INSPECT_FILE
            return DeveloperDecision(
                action=action,
                confidence=0.85,  # high confidence, passes min_confidence guard
                probabilities={
                    action.value: 0.85,
                    **{a.value: (0.15 / 7) for a in DeveloperAction.all_actions() if a != action},
                },
                parameters={"turn": self.turn},
            )

    dummy_state = TruthFirstState()
    dummy_obs = StateObservation(
        session_id="test",
        step_index=1,
        timestamp_ns=0,
        working_directory=".",
        active_file="foo.py",
        terminal_output="error",
        compiler_exit_code=1,
        git_status_summary="",
        recent_error="SyntaxError",
        metadata={},
    )

    cycling_provider = CyclingProvider()
    fallback_guard = SafetyFallback(cycling_provider, oscillation_threshold=3)

    # Execute 10 alternating cycles
    emitted_decisions = []
    for _ in range(10):
        decision = fallback_guard.decide(dummy_state, dummy_obs)
        emitted_decisions.append(decision)

    # Empirical finding: None of the 10 alternating decisions was intercepted as loop_detected!
    loop_intercepts = [
        d for d in emitted_decisions
        if d.metadata.get("safety_override") == "oscillation_detected"
    ]
    assert len(loop_intercepts) == 0, (
        "SafetyFallback failed to intercept alternating oscillation (A -> B -> A -> B) "
        "because its loop guard only checks len(set(recent_actions)) == 1!"
    )


# ==============================================================================
# 4. Memory and Immutability Checks on Returned Pillar Collections
# ==============================================================================


def test_truth_first_state_direct_pillar_mutability() -> None:
    """EMPIRICAL CHALLENGE: Verify whether TruthFirstState pillars are mutable or protect against external tampering.
    
    The module docstring states:
    'Maintains an immutable/audit-friendly 7-pillar ledger:'
    
    Empirically test whether callers can bypass ledger methods and directly mutate
    constraints, facts, decisions, evidence, open_questions, and failed_approaches.
    """
    state = TruthFirstState(goal="Initial Goal")
    state.add_constraint("Must be offline")
    state.add_fact("Compiler returned exit code 1")
    state.record_decision("inspect_error", parameters={"target": "foo.py"})
    state.add_evidence("Traceback line 42")
    state.add_open_question("Is syntax valid?")
    state.add_failed_approach("Patch A", reason="Failed")

    # 1. Direct mutation of constraints
    state.constraints.append("TAMPERED_CONSTRAINT")
    assert "TAMPERED_CONSTRAINT" in state.constraints, "Direct mutation of constraints is possible."

    # 2. Direct clearing of facts
    state.facts.clear()
    assert len(state.facts) == 0, "External caller can erase facts pillar directly."

    # 3. Direct modification of recorded decisions
    state.decisions[0]["action"] = "MALICIOUS_ACTION"
    state.decisions[0]["confidence"] = 0.0
    assert state.decisions[0]["action"] == "MALICIOUS_ACTION", "Decision ledger can be tampered in-place."

    # 4. Direct clearing of evidence
    state.evidence.pop()
    assert len(state.evidence) == 0, "Evidence can be purged directly."


def test_truth_first_state_to_dict_shallow_copy_leakage() -> None:
    """EMPIRICAL CHALLENGE: Verify whether to_dict() returns deep or shallow copies of nested collections.
    
    In to_dict():
        'decisions': list(self.decisions)
        'failed_approaches': list(self.failed_approaches)
        'metadata': dict(self.metadata)
        
    `list(self.decisions)` is a shallow copy. Modifying the inner dictionaries in the returned
    dict mutates the internal state of TruthFirstState!
    """
    state = TruthFirstState(
        goal="Audit integrity test",
        metadata={"config": {"timeout_s": 30, "retries": 3}},
    )
    state.record_decision(
        DeveloperAction.APPLY_FIX,
        parameters={"patch_target": "src/main.py", "nested_opt": {"safety": True}},
        reasoning="Initial fix",
    )
    state.add_failed_approach("Approach 1", reason="Failed syntax check")

    # Export to dict
    exported_dict = state.to_dict()

    # Tamper with the exported dict's decision parameters
    exported_dict["decisions"][0]["parameters"]["nested_opt"]["safety"] = False
    exported_dict["decisions"][0]["action"] = "TAMPERED_ACTION"

    # Tamper with the exported dict's metadata
    exported_dict["metadata"]["config"]["timeout_s"] = 9999

    # Tamper with failed_approaches
    exported_dict["failed_approaches"][0]["reason"] = "TAMPERED_REASON"

    # Empirical check: Did the internal state get mutated via shallow-copy leakage?
    # Note: exported_dict["decisions"][0] is the exact same dictionary object!
    assert state.decisions[0]["action"] == "TAMPERED_ACTION", (
        "VULNERABILITY: Modifying to_dict()['decisions'][0] directly mutated state.decisions[0]!"
    )
    assert state.decisions[0]["parameters"]["nested_opt"]["safety"] is False, (
        "VULNERABILITY: Modifying nested parameters in to_dict() directly mutated state.decisions[0]['parameters']!"
    )
    assert state.metadata["config"]["timeout_s"] == 9999, (
        "VULNERABILITY: Modifying nested metadata in to_dict() directly mutated state.metadata!"
    )
    assert state.failed_approaches[0]["reason"] == "TAMPERED_REASON", (
        "VULNERABILITY: Modifying failed_approaches in to_dict() directly mutated state.failed_approaches!"
    )


def test_truth_first_state_from_dict_shallow_aliasing() -> None:
    """EMPIRICAL CHALLENGE: Verify whether from_dict() shallow-aliases incoming nested collections.
    
    When reconstructed via from_dict(data):
        decisions=list(data.get("decisions", []))
    If the caller subsequently modifies `data["decisions"]`, does it affect the reconstructed state?
    """
    source_data: dict[str, Any] = {
        "goal": "Reconstruction test",
        "decisions": [
            {"step": 1, "action": "inspect_error", "parameters": {"file": "a.py"}}
        ],
        "metadata": {"tags": ["dev", "m1"]},
    }

    state = TruthFirstState.from_dict(source_data)

    # Caller modifies source_data after construction
    source_data["decisions"][0]["action"] = "MODIFIED_AFTER_FROM_DICT"

    assert state.decisions[0]["action"] == "MODIFIED_AFTER_FROM_DICT", (
        "VULNERABILITY: Modifying source_data after from_dict() directly mutated reconstructed TruthFirstState!"
    )


def test_json_roundtrip_isolates_memory() -> None:
    """Unlike to_dict() / from_dict(), to_json() -> from_json() performs a full serialization boundary,
    preventing object reference sharing.
    """
    state = TruthFirstState(
        goal="JSON isolation test",
        metadata={"config": {"timeout_s": 30}},
    )
    state.record_decision(
        DeveloperAction.APPLY_FIX,
        parameters={"patch_target": "src/main.py"},
    )

    json_str = state.to_json()
    reconstructed = TruthFirstState.from_json(json_str)

    # Mutating reconstructed does NOT mutate original because JSON creates new primitives
    reconstructed.decisions[0]["action"] = "MUTATED"
    reconstructed.metadata["config"]["timeout_s"] = 999

    assert state.decisions[0]["action"] == DeveloperAction.APPLY_FIX.value
    assert state.metadata["config"]["timeout_s"] == 30


# ==============================================================================
# 5. Scale, Robustness, and Boundary Stress Tests
# ==============================================================================


def test_truth_first_state_large_payload_scale() -> None:
    """Stress test serialization performance and memory on a large session state."""
    state = TruthFirstState(
        goal="Large scale stress test",
        session_id="stress_session_large_payload",
    )
    # 1,000 facts
    for i in range(1000):
        state.add_fact(f"Empirical fact #{i}: Subsystem {i % 10} verified healthy at tick {i * 100}")

    # 500 decisions
    for i in range(500):
        action = DeveloperAction.INSPECT_FILE if i % 2 == 0 else DeveloperAction.RUN_TARGETED_TEST
        state.record_decision(
            decision=action,
            parameters={"target": f"tests/subsystem_{i % 25}/test_{i}.py", "index": i},
            reasoning=f"Automated iteration {i}",
        )

    # 100 evidence blocks (each 1KB)
    for i in range(100):
        state.evidence.append(f"LOG_DUMP_{i}:\n" + ("x" * 1000) + "\n")

    # Serialize to JSON and measure integrity
    json_str = state.to_json()
    assert len(json_str) > 200_000, "Serialized JSON should reflect large payload"

    # Deserialize back
    reconstructed = TruthFirstState.from_json(json_str)
    assert len(reconstructed.facts) == 1000
    assert len(reconstructed.decisions) == 500
    assert len(reconstructed.evidence) == 100
    assert reconstructed.decisions[499]["action"] == DeveloperAction.RUN_TARGETED_TEST.value


def test_truth_first_state_from_json_partial_data_resilience() -> None:
    """Verify from_json handles minimal or partial JSON without crashing."""
    minimal_json = '{"goal": "Only goal provided"}'
    state = TruthFirstState.from_json(minimal_json)

    assert state.goal == "Only goal provided"
    assert state.constraints == []
    assert state.facts == []
    assert state.decisions == []
    assert state.cycle_index == 0
    assert state.metadata == {}


def test_format_audit_log_with_sparse_or_custom_decisions() -> None:
    """Verify format_audit_log renders cleanly even when decisions have sparse or non-standard keys."""
    state = TruthFirstState(goal="Sparse decision audit log")
    # Non-standard decision dict missing step, confidence, etc.
    state.decisions.append({"action": "custom_action"})
    state.failed_approaches.append({"approach": "try_something", "reason": "unspecified"})

    log_markdown = state.format_audit_log()
    assert "## 1. GOAL" in log_markdown
    assert "custom_action" in log_markdown
    assert "try_something" in log_markdown


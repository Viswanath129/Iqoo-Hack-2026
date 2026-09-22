# Truth-First State Ledger

## Overview

The Truth-First State Ledger is JEVON's immutable, append-only state tracking model. It ensures complete auditability of every decision cycle by organizing developer state into **7 distinct pillars**.

**Source**: [`jevon/truth_first/state.py`](../jevon/truth_first/state.py)

---

## The 7 Pillars

| # | Pillar | Type | Purpose | Mutability |
|:---:|:---|:---|:---|:---|
| 1 | **GOAL** | `str` | Developer's primary objective | Set once, update allowed |
| 2 | **CONSTRAINTS** | `list[str]` | Safety invariants, boundary constraints, allowlists | Append-only, no duplicates |
| 3 | **FACTS** | `list[str]` | Empirically verified truths from OS observations | Append-only, no duplicates |
| 4 | **DECISIONS** | `list[dict]` | Chronological decision history | Append-only with timestamps |
| 5 | **EVIDENCE** | `list[str]` | Verbatim compiler errors, diffs, stack traces, return codes | Append-only, no duplicates |
| 6 | **OPEN_QUESTIONS** | `list[str]` | Active diagnostic hypotheses under investigation | Add/remove with resolution |
| 7 | **FAILED_APPROACHES** | `list[dict]` | Disproven fix attempts with failure signatures | Append-only |

---

## Pillar Details

### Pillar 1: GOAL
```python
state.set_goal("Fix failing test in tests/test_calc.py")
```
The primary developer objective. Set at the beginning of a session and can be updated if the task scope changes.

### Pillar 2: CONSTRAINTS
```python
state.add_constraint("No destructive git operations without confirmation")
state.add_constraint("Step timeout must not exceed 30 seconds")
```
Safety invariants and boundary rules. Duplicate constraints are silently ignored.

### Pillar 3: FACTS
```python
state.add_fact("calc.py contains a SyntaxError on line 42")
state.add_fact("test_calc.py has 5 test functions, 1 failing")
```
Empirically verified observations — only things confirmed by the system (exit codes, file contents, test results). Duplicates are rejected.

### Pillar 4: DECISIONS
```python
# From a DeveloperDecision object
state.record_decision(decision)

# From a DeveloperAction enum
state.record_decision(
    DeveloperAction.INSPECT_ERROR,
    parameters={"error_text": "SyntaxError..."},
    reasoning="Process failed with exit code 1"
)

# From a raw dictionary
state.record_decision({
    "action": "inspect_error",
    "confidence": 0.91,
    "parameters": {...}
})
```

Each decision entry contains:
```python
{
    "step": 1,                    # Auto-incremented step number
    "action": "inspect_error",    # Action enum value
    "confidence": 0.91,           # Confidence score
    "parameters": {...},          # Action-specific parameters
    "reasoning": "...",           # Human-readable rationale
    "timestamp_utc": 1695456000.0 # UTC timestamp
}
```

### Pillar 5: EVIDENCE
```python
state.add_evidence('File "calc.py", line 42\n  SyntaxError: unexpected indent')
state.add_evidence("pytest: 4 passed, 1 failed")
```
Verbatim output snippets from compilers, test runners, and terminal sessions. Raw data — never summarized or interpreted.

### Pillar 6: OPEN_QUESTIONS
```python
state.add_open_question("Is the indent error caused by mixed tabs/spaces?")

# Later, when resolved:
state.resolve_open_question(
    "Is the indent error caused by mixed tabs/spaces?",
    answer="Yes — line 42 uses a tab while the file uses 4-space indentation"
)
# This removes the question and adds a fact:
# "Resolved 'Is the indent error caused by mixed tabs/spaces?': Yes — ..."
```

### Pillar 7: FAILED_APPROACHES
```python
state.add_failed_approach(
    approach="Replaced tab with 4 spaces on line 42",
    reason="Fix introduced a new NameError on line 43",
    signature="a3f8b2c1e9d04567"  # Deterministic failure hash
)
```

---

## Failure Signatures

Failure states generate a **deterministic 16-character SHA-256 signature** combining three factors:

```python
def compute_failure_signature(
    exit_code: int | None,
    culprit_file: str | None,
    error_summary: str | None,
) -> str:
    # Normalize file path separators
    norm_file = culprit_file.replace("\\", "/") if culprit_file else ""
    # JSON-encode the triple
    raw = json.dumps([exit_code, norm_file, error_summary or ""], separators=(",", ":"))
    # SHA-256 truncated to 16 characters
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

**Purpose**: Instantly identify whether the system is encountering the same failure repeatedly (regression loop detection).

**Example**:
```python
sig = compute_failure_signature(1, "calc.py", "SyntaxError: unexpected indent")
# => "a3f8b2c1e9d04567"
```

---

## Loop Detection

### Repeated Failure Detection

```python
state.detect_repeated_failure(window=3) -> bool
```

Returns `True` if the last `window` failure signatures are **identical** — indicating the system is stuck in a regression loop and human intervention is needed.

### Decision Oscillation Detection

```python
state.detect_oscillation(window=3) -> bool
```

Detects three patterns of repetitive decision-making:

| Pattern | Detection Logic | Example |
|:---|:---|:---|
| **Single-action stagnation** | Last `window` decisions repeat the same action | `inspect_error → inspect_error → inspect_error` |
| **2-cycle periodic** | Last 4 actions form `A→B→A→B` with `A≠B` | `inspect_error → inspect_file → inspect_error → inspect_file` |
| **3-cycle periodic** | Last 6 actions form `A→B→C→A→B→C` with 3 distinct actions | Three different actions repeating in sequence |

---

## Tracking Metadata

| Field | Type | Purpose |
|:---|:---|:---|
| `cycle_index` | `int` | Current loop cycle counter |
| `session_id` | `str` | Unique session identifier |
| `timestamp_utc` | `float` | State creation timestamp |
| `failure_signatures` | `list[str]` | Sequential history of failure hashes |
| `metadata` | `dict` | Custom key-value metadata |

---

## Serialization

Full roundtrip serialization is supported:

```python
# To dictionary / JSON
d = state.to_dict()
j = state.to_json(indent=2)

# From dictionary / JSON
state = TruthFirstState.from_dict(d)
state = TruthFirstState.from_json(j)
```

All nested structures (decisions, failed_approaches, metadata) are deep-copied during serialization to prevent reference mutations.

---

## Audit Log Rendering

```python
print(state.format_audit_log())
```

Produces a clean Markdown report:

```markdown
# Truth-First State Ledger
**Cycle Index**: 5 | **Session**: sess_20260922

## 1. GOAL
Fix failing test in tests/test_calc.py

## 2. CONSTRAINTS
- No destructive git operations without confirmation
- Step timeout must not exceed 30 seconds

## 3. FACTS
- calc.py contains a SyntaxError on line 42
- Fix applied successfully, AST validation passed

## 4. DECISIONS
- Step 1: **inspect_error** (conf=0.91)
- Step 2: **inspect_file** (conf=0.89)
- Step 3: **apply_fix** (conf=0.88)

## 5. EVIDENCE
```
File "calc.py", line 42
  SyntaxError: unexpected indent
```

## 6. OPEN QUESTIONS
*(none)*

## 7. FAILED APPROACHES
*(none)*
```

---

## Integration Points

The TruthFirstState is consumed by:

1. **`LocalDecisionProvider`** — reads `decisions` history, `failure_signatures` for loop detection
2. **`SafetyFallback`** — checks oscillation patterns in decision history
3. **`ClosedLoopOrchestrator`** — updates facts, evidence, and failures after each cycle
4. **`TypeSafeJevProvider`** — passes goal and state context to cloud classifier
5. **Audit logs** — rendered as Markdown for human review and submission artifacts

# Security Model

## Overview

JEVON implements a **7-layer defense-in-depth** security architecture to prevent runaway automation, destructive operations, and data exposure.

---

## Security Architecture

```
Layer 7: Command & Path Allowlist (policy level)
    └─ Only known-safe command prefixes permitted
Layer 6: Subprocess Isolation (execution level)
    └─ 30s timeout, captured output, no TTY attachment
Layer 5: Step Limits (session level)
    └─ Default max 100 steps per session, configurable
Layer 4: Oscillation Loop Detection (behavior level)
    └─ Stagnation / 2-cycle / 3-cycle → REQUEST_CONFIRMATION
Layer 3: SafetyFallback Confidence Guard (decision level)
    └─ Confidence < 0.60 → REQUEST_CONFIRMATION
Layer 2: SafetyGate Destructive Blocking (command level)
    └─ 7 regex patterns → BLOCKED_BY_SAFETY (exit 126)
Layer 1: Emergency Mouse-Corner Stop (hardware level)
    └─ Mouse at (0,0) within 10px → immediate RuntimeError
```

---

## Layer 1: Emergency Mouse-Corner Stop

**Type**: Hardware-level abort  
**Trigger**: Mouse position at (0,0) within 10 pixels  
**Response**: Immediate `RuntimeError` — all automation halts instantly

```python
if mouse_pos.x <= 10 and mouse_pos.y <= 10:
    raise RuntimeError("Abort: Emergency mouse-corner stop triggered (<10px)")
```

**How to use**: Move your mouse to the **top-left corner** of any display to immediately stop JEVON.

---

## Layer 2: SafetyGate Destructive Blocking

**Type**: Command-level interception  
**Location**: `jevon/execution/safety_gate.py`

### Blocked Patterns

| # | Pattern | Risk | Example |
|:---:|:---|:---|:---|
| 1 | `git reset --hard` | Uncommitted work loss | `git reset --hard HEAD~5` |
| 2 | `git clean -[*]f` | Untracked file deletion | `git clean -fdx` |
| 3 | `rm -rf` / `rm -fr` | Directory tree destruction | `rm -rf /home/user` |
| 4 | `rmdir /s /q` | Windows directory deletion | `rmdir /s /q C:\project` |
| 5 | `del /f /q` | Windows file deletion | `del /f /q *.py` |
| 6 | `.env`, `id_rsa`, `credentials`, `.pem` | Credential exposure | `cat .env` |
| 7 | `drop database` | Database destruction | `DROP DATABASE production` |

**Response**: Returns `ActionReceipt` with `status="BLOCKED_BY_SAFETY"` and `exit_code=126`.

**Override**: Only possible with explicit `confirmed=True` parameter.

---

## Layer 3: SafetyFallback Confidence Guard

**Type**: Decision-level interception  
**Location**: `jevon/decision/safety_fallback.py`  
**Threshold**: 0.60 (configurable)

When a decision's confidence is below the threshold:
- **With unparsed error**: Redirects to `INSPECT_ERROR` (confidence 0.85)
- **Without error**: Redirects to `REQUEST_CONFIRMATION` (confidence 0.85)

Original action and confidence are preserved in metadata for audit.

---

## Layer 4: Oscillation Loop Detection

**Type**: Behavioral analysis  
**Location**: `SafetyFallback` + `TruthFirstState`

Detects three repetitive patterns:

| Pattern | Detection | Example |
|:---|:---|:---|
| **Stagnation** | N identical consecutive actions | `inspect_error` × 3 |
| **2-cycle** | `A→B→A→B` with `A≠B` | `inspect_error ↔ inspect_file` |
| **3-cycle** | `A→B→C→A→B→C` with 3 distinct | Three actions in repeating loop |

**Response**: `REQUEST_CONFIRMATION` with confidence 0.95 — requires human intervention.

---

## Layer 5: Step Limits

**Type**: Session-level bounds  
**Default**: 100 steps per task session

Prevents infinite loops by imposing a hard upper bound on the number of decision cycles. Configurable via CLI (`--steps N`) or orchestrator constructor (`max_steps`).

---

## Layer 6: Subprocess Isolation

**Type**: Execution-level sandboxing

| Property | Value |
|:---|:---|
| **Execution mode** | `subprocess.run(shell=True)` |
| **Timeout** | 30 seconds per command |
| **Output capture** | stdout and stderr fully captured |
| **TTY** | No TTY attachment (non-interactive) |
| **Working directory** | Explicitly set to target workspace |

Timed-out commands return `exit_code=124` with `FAILED` status.

---

## Layer 7: Command & Path Allowlist

**Type**: Policy-level filtering  
**Location**: `jevon/execution/allowlist.py`

Only commands starting with approved prefixes are considered "allowed":

```python
ALLOWED_COMMAND_PREFIXES = (
    "python", "python3", "uv run", "pytest",
    "git status", "git diff", "git log",
    "cargo test", "cargo build", "npm test",
    "pytest tests", "python e2e/runner.py",
)
```

---

## Privacy Model

| Aspect | Implementation |
|:---|:---|
| **Data Residency** | All perception, decision, and execution data stays on-device |
| **Zero Cloud Default** | Mode A operates with 0 API keys — no data leaves the device |
| **API Key Optional** | Cloud features (Mode B/C) require explicit opt-in via API key |
| **Credential Blocking** | SafetyGate blocks `.env`, `id_rsa`, `.pem`, `credentials` access |
| **No Password Paths** | Contributing guidelines explicitly prohibit password typing |
| **Audit Trail** | Truth-First ledger records all decisions for transparency |

---

## Precondition Validation

### APPLY_FIX Precondition
Before applying a code fix, SafetyFallback verifies:
- `target_file` is specified in parameters **or** observation
- If missing: redirects to `INSPECT_FILE` or `INSPECT_ERROR`
- Prevents blind patching of unidentified files

### RUN_TARGETED_TEST Precondition
Before running a targeted test, SafetyFallback verifies:
- `target_test` is specified in parameters **or** observation metadata
- If missing: falls back to `RERUN_BUILD` (full test suite)
- Prevents running non-existent test files

---

## Failure Signature Integrity

| Property | Implementation |
|:---|:---|
| **Algorithm** | SHA-256 (truncated to 16 characters) |
| **Inputs** | `[exit_code, normalized_file_path, error_summary]` |
| **Determinism** | Same failure always produces same signature |
| **Path Normalization** | Backslashes converted to forward slashes |
| **Encoding** | JSON-encoded with compact separators |

---

## Threat Boundaries

| Threat | Mitigation |
|:---|:---|
| **Runaway clicking** | Mouse-corner abort + step limits |
| **Infinite loops** | Oscillation detection + step limits |
| **Data destruction** | SafetyGate + command allowlist |
| **Credential exposure** | SafetyGate regex for sensitive files |
| **Low-confidence mistakes** | Confidence threshold + human confirmation |
| **Cloud data leakage** | Zero-cloud default mode |
| **Subprocess escape** | Timeout + output capture + isolated execution |

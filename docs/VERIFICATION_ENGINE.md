# Verification Engine

## Overview

The Verification Engine performs **objective, independent verification** of developer action results without self-certification. It ensures that every action's outcome is validated by external criteria (exit codes, regex, AST parsing, error elimination) — never by the decision engine's own assertion.

**Source**: [`jevon/verification/engine.py`](../jevon/verification/engine.py)

---

## `VerificationOutcome`

```python
@dataclass
class VerificationOutcome:
    passed: bool                      # True only if ALL checks passed
    checks: dict[str, bool]           # Per-check pass/fail results
    details: dict[str, Any]           # Additional details (e.g., AST error messages)
```

**Key invariant**: `passed = all(checks.values())` — a single failing check means the overall verification fails.

---

## Verification Checks

### Check 1: Exit Code Verification

```python
def verify_exit_code(self, exit_code: int) -> bool:
    return exit_code == 0
```

| Input | Result | Meaning |
|:---:|:---:|:---|
| `0` | `True` | Process completed successfully |
| `1` | `False` | General error |
| `124` | `False` | Command timed out |
| `126` | `False` | Blocked by SafetyGate |

### Check 2: Regex Pattern Matching

```python
def verify_regex(self, text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text))
```

Used to verify expected strings in output:
- `r"\\d+ passed"` — Confirms tests passed
- `r"Build successful"` — Confirms build success
- `r"no errors found"` — Confirms clean lint

### Check 3: AST Syntax Validation

```python
def verify_ast_syntax(self, code_str: str) -> tuple[bool, str | None]:
    try:
        ast.parse(code_str)
        return True, None
    except SyntaxError as e:
        return False, str(e)
```

Validates Python code without executing it:
- Parses the source code using Python's `ast.parse()`
- Catches `SyntaxError` and returns the error message
- **Does NOT execute any code** — purely static analysis

### Check 4: Error Elimination

```python
def verify_error_eliminated(self, output: str, previous_error: str) -> bool:
    if not previous_error or not output:
        return True
    return previous_error.strip() not in output
```

Confirms that a previously observed error is no longer present in the new output. This prevents false "success" claims where the same error persists after a fix attempt.

---

## Unified `verify()` Method

```python
def verify(
    self,
    exit_code: int,
    stdout: str,
    stderr: str,
    expected_regex: str | None = None,
    source_code: str | None = None,
    previous_error: str | None = None,
) -> VerificationOutcome:
```

Runs all applicable checks based on which parameters are provided:

| Parameter | Check Activated | Key in `checks` |
|:---|:---|:---|
| `exit_code` (always) | Exit code == 0 | `exit_code_zero` |
| `expected_regex` | Regex pattern in combined output | `regex_matched` |
| `source_code` | AST syntax parse | `ast_valid` |
| `previous_error` | Error string absent from output | `error_eliminated` |

### Example Usage

```python
from jevon.verification.engine import VerificationEngine

verifier = VerificationEngine()

# Basic exit code check
outcome = verifier.verify(exit_code=0, stdout="5 passed", stderr="")
# outcome.passed = True
# outcome.checks = {"exit_code_zero": True}

# Full verification with regex and error elimination
outcome = verifier.verify(
    exit_code=0,
    stdout="tests/test_calc.py::test_add PASSED\n5 passed",
    stderr="",
    expected_regex=r"\d+ passed",
    source_code="def add(a, b):\n    return a + b\n",
    previous_error="SyntaxError: unexpected indent",
)
# outcome.passed = True
# outcome.checks = {
#     "exit_code_zero": True,
#     "regex_matched": True,
#     "ast_valid": True,
#     "error_eliminated": True
# }

# Failed verification
outcome = verifier.verify(
    exit_code=1,
    stdout="",
    stderr="SyntaxError: unexpected indent",
    source_code="def add(a, b):\n    return a + b\n  extra_indent",
    previous_error="SyntaxError: unexpected indent",
)
# outcome.passed = False
# outcome.checks = {
#     "exit_code_zero": False,
#     "ast_valid": False,
#     "error_eliminated": False
# }
# outcome.details = {"ast_error": "invalid syntax (line 3)"}
```

---

## Integration with Closed-Loop Orchestrator

In the orchestrator loop, verification happens at **Stage 4** after execution:

```python
# Stage 3: Execute
receipt = self.executor.execute(cmd_str)

# Stage 4: Verify independently
verif_outcome = self.verifier.verify(
    exit_code=receipt.exit_code,
    stdout=receipt.stdout,
    stderr=receipt.stderr,
)

# Build verified receipt
receipt_verified = ActionReceipt(
    ...
    verification_passed=verif_outcome.passed,
    verification_details=verif_outcome.checks,
    ...
)
```

The verification result feeds back into the TruthFirstState:
- **Passed**: `state.append_fact("Step N verified successfully")`
- **Failed**: `state.record_failure(approach=action, reason=stderr, exit_code=code)`

---

## Design Principles

1. **No self-certification** — The decision engine never validates its own output
2. **Multiple independent checks** — A single failing check fails the entire verification
3. **Static analysis only** — AST checks never execute code
4. **Evidence-based** — All checks operate on objective, measurable data (exit codes, string matching)
5. **Extensible** — New checks can be added without modifying existing ones

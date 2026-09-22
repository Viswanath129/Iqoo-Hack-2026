# Broken Syntax Fixture

This fixture contains a Python project with an intentional `SyntaxError` on line 3 of `calc.py` (unclosed parenthesis in `return (a + b`).
Used by JEVON E2E tests to verify:
1. Terminal error extraction and AST parse failure detection.
2. `LocalDecisionProvider` choosing `INSPECT_ERROR` -> `INSPECT_FILE` -> `APPLY_FIX`.
3. Independent `VerificationEngine` validating syntax elimination.

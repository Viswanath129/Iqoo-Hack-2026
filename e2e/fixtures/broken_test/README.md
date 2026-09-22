# Broken Test Fixture

This fixture compiles cleanly but fails pytest assertions because `calc.add(2, 3)` returns -1 instead of 5.
Used by JEVON E2E tests to verify:
1. Pytest output parsing (`FAILED test_calc.py::test_add - AssertionError: Expected 5, got -1`).
2. Decision engine executing `INSPECT_ERROR` -> `INSPECT_FILE` -> `APPLY_FIX` -> `RUN_TARGETED_TEST`.
3. Independent `VerificationEngine` verifying assertion error resolution.

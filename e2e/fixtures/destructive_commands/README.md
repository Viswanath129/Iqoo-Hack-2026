# Destructive Commands Fixture

This fixture defines commands and scripts categorized as destructive:
- `git reset --hard`
- `git clean -fdx`
- `rm -rf /` and `rmdir /s /q`
- Access or overwrite of `.env`, `id_rsa`, and secrets.

Used by JEVON E2E tests to verify:
1. `SafetyGate.evaluate_command()` classifying destructive actions.
2. Interception before subprocess execution.
3. Status set to `BLOCKED_BY_SAFETY` in `ActionReceipt`.

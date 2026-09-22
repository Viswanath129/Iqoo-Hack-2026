"""Command allowlists and execution bounds for JEVON."""

ALLOWED_COMMAND_PREFIXES = (
    "python",
    "python3",
    "uv run",
    "pytest",
    "git status",
    "git diff",
    "git log",
    "cargo test",
    "cargo build",
    "npm test",
    "pytest tests",
    "python e2e/runner.py",
)

ABORT_CORNER_PX = 10
STEP_TIMEOUT_SECONDS = 30

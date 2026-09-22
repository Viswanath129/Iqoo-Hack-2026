"""Reproducible test fixtures for JEVON E2E test suite."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.resolve()
BROKEN_SYNTAX_DIR = FIXTURES_DIR / "broken_syntax"
BROKEN_TEST_DIR = FIXTURES_DIR / "broken_test"
CLEAN_PROJECT_DIR = FIXTURES_DIR / "clean_project"
DESTRUCTIVE_COMMANDS_DIR = FIXTURES_DIR / "destructive_commands"

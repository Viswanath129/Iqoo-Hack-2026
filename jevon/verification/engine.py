"""Verification Engine and Checkers for JEVON.

Provides objective, independent verification of developer action results
without self-certification.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerificationOutcome:
    """Outcome of independent verification validation."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


class VerificationEngine:
    """Performs objective, independent verification without self-certification."""

    def verify_exit_code(self, exit_code: int) -> bool:
        """Verify that process exit code is zero."""
        return exit_code == 0

    def verify_regex(self, text: str, pattern: str) -> bool:
        """Verify that regex pattern matches target output."""
        return bool(re.search(pattern, text))

    def verify_ast_syntax(self, code_str: str) -> tuple[bool, str | None]:
        """Verify Python code syntax via AST without executing code."""
        try:
            ast.parse(code_str)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def verify_error_eliminated(self, output: str, previous_error: str) -> bool:
        """Verify that prior compiler/test error string is absent from new output."""
        if not previous_error or not output:
            return True
        return previous_error.strip() not in output

    def verify(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        expected_regex: str | None = None,
        source_code: str | None = None,
        previous_error: str | None = None,
    ) -> VerificationOutcome:
        """Run all applicable independent verification checks."""
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}

        # 1. Exit code
        checks["exit_code_zero"] = self.verify_exit_code(exit_code)

        # 2. Regex match
        if expected_regex:
            combined = f"{stdout}\n{stderr}"
            checks["regex_matched"] = self.verify_regex(combined, expected_regex)

        # 3. AST syntax parse
        if source_code is not None:
            ast_ok, ast_err = self.verify_ast_syntax(source_code)
            checks["ast_valid"] = ast_ok
            if ast_err:
                details["ast_error"] = ast_err

        # 4. Error eliminated check
        if previous_error:
            checks["error_eliminated"] = self.verify_error_eliminated(f"{stdout}\n{stderr}", previous_error)

        passed = all(checks.values())
        return VerificationOutcome(passed=passed, checks=checks, details=details)

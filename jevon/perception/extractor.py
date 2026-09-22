"""Terminal and error extractor for JEVON perception.

Parses stack traces, syntax errors, and test failures to isolate culprit files,
line numbers, error types, and error messages.
"""

from __future__ import annotations

import re
from typing import Any


class TerminalErrorExtractor:
    """Extracts culprit file, line number, and error message from terminal output."""

    @staticmethod
    def extract_error(text: str) -> dict[str, Any]:
        """Parse error information from terminal or build output."""
        result: dict[str, Any] = {"file": None, "line": None, "error_type": None, "message": None}
        if not text:
            return result

        # Python traceback: File "...", line \d+
        py_match = re.search(r'File "([^"]+)", line (\d+)', text)
        if py_match:
            result["file"] = py_match.group(1)
            result["line"] = int(py_match.group(2))

        # SyntaxError / AssertionError / Exception
        err_match = re.search(r"([A-Za-z_]+Error):\s*(.+)", text)
        if err_match:
            result["error_type"] = err_match.group(1)
            result["message"] = err_match.group(2).strip()

        return result

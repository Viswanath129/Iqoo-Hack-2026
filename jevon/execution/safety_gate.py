"""Safety gate for JEVON execution.

Intercepts and blocks destructive commands (such as hard git resets, file deletions,
and sensitive credential/environment file access) until human confirmation.
"""

from __future__ import annotations

import re
from typing import Tuple

from jevon.execution.allowlist import ALLOWED_COMMAND_PREFIXES

DESTRUCTIVE_PATTERNS = [
    re.compile(r"git\s+reset\s+--hard", re.IGNORECASE),
    re.compile(r"git\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE),
    re.compile(r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f?|-f[a-zA-Z]*r?)\s+(/|[a-zA-Z]:\\|\*)", re.IGNORECASE),
    re.compile(r"rmdir\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"del\s+/[fF]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"(\.env(?:\b|[\"'\s]|$)|id_rsa|credentials|\.pem)", re.IGNORECASE),
    re.compile(r"drop\s+database", re.IGNORECASE),
]


class SafetyGate:
    """Intercepts and blocks destructive commands until human confirmation."""

    @staticmethod
    def is_destructive(command_str: str) -> tuple[bool, str]:
        """Check if command matches any destructive pattern."""
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.search(command_str):
                return True, f"Matched destructive safety rule: {pattern.pattern}"
        return False, ""

    @staticmethod
    def is_allowed(command_str: str) -> bool:
        """Check if command matches allowlist prefixes."""
        cmd_stripped = command_str.strip()
        return any(cmd_stripped.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES)

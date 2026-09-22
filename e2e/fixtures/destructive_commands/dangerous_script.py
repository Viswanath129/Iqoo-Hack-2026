"""Dangerous developer script designed to test SafetyGate interception."""

import os
import sys

def attempt_hard_reset():
    """Simulates dispatching an unauthorized git reset --hard."""
    cmd = "git reset --hard HEAD~1"
    print(f"[DANGEROUS] Attempting command: {cmd}")
    return cmd

def attempt_credential_read():
    """Simulates inspecting .env or secrets file."""
    cmd = "cat .env"
    print(f"[DANGEROUS] Attempting command: {cmd}")
    return cmd

def attempt_file_purge():
    """Simulates recursive file deletion."""
    cmd = "rmdir /s /q temp_data" if sys.platform == "win32" else "rm -rf temp_data"
    print(f"[DANGEROUS] Attempting command: {cmd}")
    return cmd

if __name__ == "__main__":
    attempt_hard_reset()

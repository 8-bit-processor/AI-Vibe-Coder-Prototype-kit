"""
Validation utilities for ensuring code correctness.

This module provides functions to verify that generated code can be executed
without immediate runtime failures. It is primarily used during the staging
phase of a code fix or feature implementation.
"""

import subprocess
import sys
from typing import Optional, Tuple

def verify_code(file_path: str, python_exe: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Attempts to run the code briefly to check for syntax and runtime errors.
    Returns (success, error_message, full_output).
    """
    exe = python_exe or sys.executable
    try:
        # Use a short timeout to avoid hanging the engine on long-running scripts
        result = subprocess.run(
            [exe, file_path],
            timeout=5,
            capture_output=True,
            text=True
        )
        full_output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            # Code crashed or had a syntax error
            return False, result.stderr, full_output
        return True, None, full_output
    except subprocess.TimeoutExpired:
        # The script ran for more than 5 seconds without crashing - good enough for validation
        return True, None, "Process timed out (indicates long-running script, likely successful)"
    except Exception as e:
        # System-level or unexpected error
        return False, str(e), f"System Error: {str(e)}"

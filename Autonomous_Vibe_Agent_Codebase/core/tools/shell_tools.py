"""
Shell execution tools: run_command.
"""

import os
import subprocess
import sys
from typing import Any, Dict, Optional
from core.tools.base import Tool


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Execute a shell command in the local workspace directory (e.g. run tests, build projects, pip install, git commands). "
        "Returns stdout, stderr, and the return code. If a command fails, inspect the error output to self-correct."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command line to run."
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait before timing out (default: 60)."
            }
        },
        "required": ["command"]
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def execute(self, command: Optional[Any] = None, timeout: Any = 60, **kwargs) -> str:
        raw_cmd = command if command is not None else kwargs.get("cmd", kwargs.get("shell_command", kwargs.get("action", "")))
        cmd_str = str(raw_cmd).strip() if raw_cmd is not None else ""
        if not cmd_str:
            return "Error: Empty command provided."

        raw_timeout = timeout if timeout is not None else kwargs.get("timeout_sec", 60)
        try:
            timeout_int = int(raw_timeout)
        except (ValueError, TypeError):
            timeout_int = 60

        try:
            if sys.platform == "win32":
                args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_str]
                process = subprocess.run(
                    args,
                    cwd=self.workspace_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout_int,
                    encoding="utf-8",
                    errors="replace"
                )
            else:
                process = subprocess.run(
                    cmd_str,
                    cwd=self.workspace_dir,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout_int,
                    encoding="utf-8",
                    errors="replace"
                )

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            return_code = process.returncode

            output = []
            output.append(f"[Command exited with code {return_code}]")
            if stdout:
                output.append(f"--- STDOUT ---\n{stdout}")
            if stderr:
                output.append(f"--- STDERR ---\n{stderr}")
            if not stdout and not stderr:
                output.append("(No output produced)")

            return "\n".join(output)

        except subprocess.TimeoutExpired:
            return f"Error: Command '{cmd_str}' timed out after {timeout_int} seconds."
        except Exception as ex:
            return f"Error running command '{cmd_str}': {str(ex)}"


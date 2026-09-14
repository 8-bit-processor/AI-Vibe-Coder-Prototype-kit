#!/usr/bin/env python3
"""
Local Vibe Coder - Top Level Entry Point with Dual-Mode Support.
Run: python vibe.py [--model <model>] [--mode <local|cloud>] [--workspace <dir>] [--prompt <text>]
"""

import argparse
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.main import run_cli, TerminalUI
from core.agent import Agent
from core.config import AgentMode

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def prompt_workspace() -> str:
    """
    Interactively ask the user to specify a project workspace directory.
    Returns an absolute, existing path.
    """
    print()
    print("  +-------------------------------------------------+")
    print("  |        Local Vibe Coder - Workspace Setup       |")
    print("  +-------------------------------------------------+")
    print()
    print("  The workspace is the project folder the AI will read,")
    print("  write, and run commands inside.")
    print()
    print(f"  App directory : {APP_DIR}")
    print()

    # Suggest a sensible default: a 'projects' sibling folder on the Desktop or home
    home = os.path.expanduser("~")
    desktop = os.path.join(home, "Desktop")
    default_ws = os.path.join(desktop if os.path.isdir(desktop) else home, "vibe-workspace")

    while True:
        raw = input(f"  Enter workspace path [{default_ws}]: ").strip()
        if not raw:
            raw = default_ws

        path = os.path.abspath(raw)

        if not os.path.exists(path):
            create = input(f"  Directory does not exist. Create '{path}'? [Y/n]: ").strip().lower()
            if create in ("", "y", "yes"):
                try:
                    os.makedirs(path, exist_ok=True)
                    print(f"  Created: {path}")
                    return path
                except Exception as e:
                    print(f"  Error creating directory: {e}. Try again.")
                    continue
            else:
                continue
        elif not os.path.isdir(path):
            print(f"  '{path}' is not a directory. Try again.")
            continue
        else:
            return path


def main():
    parser = argparse.ArgumentParser(
        description="Local Vibe Coder: Autonomous local AI coding assistant powered by Ollama."
    )
    parser.add_argument(
        "--model", "-m",
        default="qwen3-coder:30b",
        help="Ollama model name (default: qwen2.5-coder:32b)"
    )
    parser.add_argument(
        "--mode",
        choices=["local", "cloud"],
        default="local",
        help="Optimization profile: 'local' or 'cloud'. Default: local"
    )
    parser.add_argument(
        "--workspace", "-w",
        default=None,
        help="Workspace directory to operate on. If omitted, you will be prompted interactively."
    )
    parser.add_argument(
        "--host",
        default="http://127.0.0.1:11434",
        help="Ollama server host (default: http://127.0.0.1:11434)"
    )
    parser.add_argument(
        "--prompt", "-p",
        default=None,
        help="Run a single prompt in non-interactive mode and exit"
    )

    args = parser.parse_args()
    selected_mode = AgentMode.LOCAL if args.mode == "local" else AgentMode.CLOUD

    # Determine workspace - interactive prompt if not specified
    if args.workspace:
        workspace = os.path.abspath(args.workspace)
        os.makedirs(workspace, exist_ok=True)
    elif args.prompt:
        # Non-interactive batch mode: default to cwd
        workspace = os.getcwd()
    else:
        workspace = prompt_workspace()

    if args.prompt:
        # Non-interactive batch execution
        agent = Agent(workspace_dir=workspace, model=args.model, host=args.host, mode=selected_mode)
        ui = TerminalUI(agent)
        agent.run(args.prompt)
    else:
        # Interactive REPL
        run_cli(workspace_dir=workspace, default_model=args.model, host=args.host, mode=selected_mode)


if __name__ == "__main__":
    main()

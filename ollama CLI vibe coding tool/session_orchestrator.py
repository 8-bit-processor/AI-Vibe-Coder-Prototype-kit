"""
Orchestrates the lifecycle of a coding session.

The SessionOrchestrator acts as the central hub, connecting the LLM client, 
the PatchCoordinator (for file operations), the ContextEngine (for project analysis),
and the ExecutionEngine (for running tasks and fixes).
"""

from rich.console import Console
from attention_context.context_data import ContextData
from code_surgery.patch_coordinator import PatchCoordinator
from attention_context.context_engine import ContextEngine
from execution_engine import ExecutionEngine
from utils.logger_utils import log_to_file
from pathlib import Path
from typing import Dict, List, Optional

# Global console instance for consistent terminal output across the orchestrator
console = Console()

class SessionOrchestrator:
    """
    Manages the state and components of an active coding session.
    
    Attributes:
        coordinator: Manages staging, backups, and committing file changes.
        context_engine: Scans and maps the project structure and symbols.
        engine: Executes LLM-driven coding and fix cycles.
        project_dir: The root directory of the active project.
        last_run_error: Stores the last captured runtime error for display.
        context_data: Structured project context for LLM queries.
    """

    def __init__(self, coder_client, coder_model, project_dir):
        """
        Initializes the orchestrator and its constituent engines.

        Args:
            coder_client: The LLM client instance (Ollama or OpenAI).
            coder_model: The name of the model to use for generation.
            project_dir: Path to the project root directory.
        """
        self.project_dir = Path(project_dir)
        
        # 1. Instantiate central context data container FIRST
        self.context_data = ContextData(project_root=str(project_dir))

        # 2. Initialize components with shared context data
        self.coordinator = PatchCoordinator(project_root=str(project_dir), logger_func=log_to_file)
        
        # Pass context_data to context_engine
        self.context_engine = ContextEngine(project_root=self.project_dir, logger_func=log_to_file, context_data=self.context_data)

        self.engine = ExecutionEngine(coder_client, coder_model, self.coordinator, self.context_engine, self.context_data)
        
        self.context_engine.scan_project()
        
    def set_auto_commit(self, value: bool):
        """
        Enables or disables automatic committing of staged code changes.

        Args:
            value: True to enable auto-commit, False to prompt for confirmation.
        """
        self.coordinator.auto_commit = value

    @property
    def project_goal(self):
        return self.context_data.project_goal

    @project_goal.setter
    def project_goal(self, value):
        self.context_data.project_goal = value

    @property
    def prompt(self):
        return self.context_data.prompt

    @prompt.setter
    def prompt(self, value):
        self.context_data.prompt = value

    @property
    def last_run_error(self):
        return self.context_data.last_run_error

    @last_run_error.setter
    def last_run_error(self, value):
        self.context_data.last_run_error = value

    def get_status_summary(self, lint_reports: Optional[Dict[str, List[str]]] = None) -> str:
        """
        Generates a human-readable summary of the current project status.

        Includes project path, project goal, last errors, environment recommendations,
        linting health, and a visual directory tree.

        Args:
            lint_reports: Optional raw linting violations from the context engine.

        Returns:
            A formatted string containing the session status.
        """
        summary = f"Project: {self.project_dir.resolve()}"
        
        # DISPLAY GOAL: Prominently show the project's objective.
        # This acts as a persistent reminder for the user and ensures the agent 
        # stays aligned with the intended outcome.
        summary += f"\nGoal: [bold green]{self.project_goal}[/bold green]"
        
        if self.last_run_error:
            summary += f"\n⚠️ [bold red]Last Run Error:[/bold red] {self.last_run_error[:100]}..."
        
        recs = []
        
        # ADVISORY: Encourage the user to define a specific project goal.
        # This prevents context drift and ensures the agent understands the 'big picture'.
        if self.project_goal == "":
            recs.append("💡 Project goal is not set. Use 'settings (menu) -> set project goal' for better accuracy.")

        # Check for virtual environment presence as a basic health check
        if not (self.project_dir / ".venv").exists() and not (self.project_dir / "venv").exists():
            recs.append("⚠️ No virtual environment detected. Use 'settings (menu) -> setup venv'.")

        if recs:
            summary += "\nRecommendations:"
            for rec in recs:
                summary += f"\n{rec}"

        if lint_reports:
            total_lint = sum(len(issues) for issues in lint_reports.values())
            summary += f"\nCode Health: {total_lint} violations found"

        summary += "\nStructure:\n"
        summary += self._generate_tree(self.project_dir)
        return summary

    def _generate_tree(self, root_path: Path, max_depth: int = 3, limit: int = 20) -> str:
        """
        Generates a visually correct ASCII tree of the project directory.
        """
        output = []
        
        def build_tree(current_dir: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth or len(output) > limit:
                return

            ignored = {".venv", "__pycache__", ".git", ".backups", ".tmp", ".ruff_cache", ".pytest_cache"}
            try:
                entries = sorted(
                    [e for e in current_dir.iterdir() if e.name not in ignored],
                    key=lambda x: (x.is_file(), x.name)
                )
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                
                output.append(f"{prefix}{connector}{entry.name}")
                
                if entry.is_dir():
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    build_tree(entry, new_prefix, depth + 1)

        build_tree(root_path)
        return "\n".join(output[:limit])

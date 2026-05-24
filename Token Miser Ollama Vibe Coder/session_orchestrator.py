"""
Orchestrates the lifecycle of a coding session.

The SessionOrchestrator acts as the central hub, connecting the LLM client, 
the PatchCoordinator (for file operations), the ContextEngine (for project analysis),
and the ExecutionEngine (for running tasks and fixes).
"""

from rich.console import Console
from context_data import ContextData
from patch_coordinator import PatchCoordinator
from context_engine import ContextEngine
from execution_engine import ExecutionEngine
from logger_utils import log_to_file
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
        self.coordinator = PatchCoordinator(project_root=str(project_dir), logger_func=log_to_file)
        self.coordinator.session_orchestrator = self

        self.context_engine = ContextEngine(project_root=project_dir, logger_func=log_to_file)
        self.context_engine.session_orchestrator = self 

        # Instantiate central context data container
        self.context_data = ContextData(project_root=str(project_dir))

        self.engine = ExecutionEngine(coder_client, coder_model, self.coordinator, self.context_engine, self.context_data)
        self.project_dir = Path(project_dir)
        self.last_run_error = None
        self.project_goal = "General development" 
        
        self.context_engine.scan_project()

    def set_auto_commit(self, value: bool):
        """
        Enables or disables automatic committing of staged code changes.

        Args:
            value: True to enable auto-commit, False to prompt for confirmation.
        """
        self.coordinator.auto_commit = value

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
        if self.project_goal == "General development":
            recs.append("💡 Project goal is generic. Use 'settings (menu) -> change project goal' for better accuracy.")

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

        summary += "\nStructure:"
        summary += self._generate_tree(self.project_dir)
        return summary

    def _generate_tree(self, root_path: Path, limit: int = 15) -> str:
        """
        Generates a visual ASCII tree of the project directory.

        Args:
            root_path: The directory to start the tree from.
            limit: Maximum number of entries to display to prevent terminal overflow.

        Returns:
            A string representing the directory structure.
        """
        def build_tree(current_dir: Path, current_prefix: str, count: int = 0):
            if count > limit: 
                return []
            
            # Filter noise and internal directories to keep the tree relevant
            ignored = {".venv", "__pycache__", ".git", ".backups", ".tmp", ".ruff_cache", ".pytest_cache"}
            try:
                entries = sorted(
                    [e for e in current_dir.iterdir() if e.name not in ignored], 
                    key=lambda x: (x.is_file(), x.name)
                )
            except PermissionError:
                return []
            
            lines = []
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                lines.append(f"{current_prefix}\n{'└── ' if is_last else '├── '}{entry.name}")
                if entry.is_dir():
                    # Recursive call for subdirectories
                    lines.extend(build_tree(entry, current_prefix + ("    " if is_last else "│   "), count + 1))
            return lines

        tree = build_tree(root_path, "")
        return "".join(tree[:limit])

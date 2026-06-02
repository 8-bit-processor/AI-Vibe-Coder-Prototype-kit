"""
The Project Memory: A lightweight container for structured project state.

ContextData serves as the 'short-term memory' for the session. It consolidates
high-level facts (goals, last errors, linting health) into a format that the 
LLM can quickly ingest to stay aligned with the project's current status.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class ContextData:
    """
    Maintains the 'source of truth' for the session's technical state.

    Attributes:
        project_root: The filesystem root of the current project.
        project_goal: The high-level objective (e.g., 'make a calculator').
        last_run_error: The captured traceback or error from the last execution.
        last_verification_report: Detailed report from the sandbox validation phase.
        module_map: Metadata about files and symbols (populated by ContextEngine).
        lint_reports: Active code health violations (e.g., from Ruff).
        active_file: The file currently being worked on by the agent.
        user_feedback: Direct instructions or corrections from the user.
    """
    project_root: str = ""
    project_goal: str = ""
    prompt: str = ""
    last_run_error: Optional[str] = None
    last_verification_report: Optional[str] = None
    module_map: Dict[str, Any] = field(default_factory=dict)
    lint_reports: Dict[str, List[str]] = field(default_factory=dict)
    active_file: Optional[str] = None
    user_feedback: Optional[str] = None
    

    def to_prompt_string(self) -> str:
        """
        Condenses active state into a high-signal string for the system prompt.

        Algorithm:
        1. Prioritize critical failures (runtime errors).
        2. Inject specific user feedback or corrections.
        3. Remind the agent of the primary goal to prevent 'context drift'.

        Returns:
            A formatted string block for the LLM.
        """
        # === CONTEXT SIGNAL FILTERING ===
        # We only include non-empty, actionable sections to minimize token cost.
        sections = []
        
        # Priority 1: Immediate blockers
        if self.last_run_error:
            sections.append(f"!!! CRITICAL: LAST RUNTIME ERROR !!!\n{self.last_run_error}")
        
        # Priority 2: User-specific steering
        if self.user_feedback:
            sections.append(f"--- USER FEEDBACK/INPUT ---\n{self.user_feedback}")
        
        # Priority 3: Current task context
        if self.prompt:
            sections.append(f"--- CURRENT TASK ---\n{self.prompt}")

        # Priority 4: Foundational objective
        if self.project_goal:
            sections.append(f"--- CORE OBJECTIVE ---\n{self.project_goal}")
        
        # Note: Detailed architectural info is pulled by the ContextEngine on-demand
        # to ensure the prompt stays focused on the immediate task.
                
        return "\n\n".join(sections)

"""
Data container for project-wide context.
Used by the LLM as a lever to pull supplemental information.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class ContextData:
    """
    Holds structured context information for the LLM.
    """
    project_root: str = ""
    project_goal: str = ""
    last_run_error: Optional[str] = None
    last_verification_report: Optional[str] = None
    module_map: Dict[str, Any] = field(default_factory=dict)
    lint_reports: Dict[str, List[str]] = field(default_factory=dict)
    active_file: Optional[str] = None
    
    def to_prompt_string(self) -> str:
        """
        Converts the context data into a highly salient string for the LLM.
        Focuses exclusively on actionable state to prevent context bloat.
        """
        sections = []
        if self.last_run_error:
            sections.append(f"!!! CRITICAL: LAST RUNTIME ERROR !!!\n{self.last_run_error}")
        if self.project_goal:
            sections.append(f"--- CORE OBJECTIVE ---\n{self.project_goal}")
        
        # We removed the module map here; architecture is better handled 
        # via the ContextEngine's smarter, selective querying when needed.
        # This keeps the 'ContextData' object ultra-light and high-signal.
                
        return "\n\n".join(sections)

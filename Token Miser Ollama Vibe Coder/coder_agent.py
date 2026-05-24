from pathlib import Path
from typing import Optional, Tuple
from llm.base import LLMClient
from execution_engine import ExecutionEngine
from logger_utils import log_to_file
from rich.console import Console

console = Console()

class CoderAgent:
    """
    The Coding Assistant: Specialized in code generation and technical implementation.
    Now supports pushing back if clarification is required.
    """
    def __init__(self, client: LLMClient, model: str, engine: ExecutionEngine):
        self.client = client
        self.model = model
        self.engine = engine

    async def execute_task(self, task_prompt: str, project_context: str, project_dir: Path) -> Tuple[str, Optional[str]]:
        """
        Executes a specific coding task.
        Returns (response_text, diagnostic_report).
        """
        log_to_file(f"CoderAgent starting task: {task_prompt[:100]}...", "CODER")
        
        # Check for fix intent
        is_fix = any(word in task_prompt.lower() for word in ['fix', 'bug', 'error', 'issue', 'fail'])
        
        if is_fix:
            response, diagnostic = await self.engine.run_fix_cycle(task_prompt, project_context, project_dir)
        else:
            response = await self.engine.run_general_cycle("general", task_prompt, project_context)
            diagnostic = None

        # Check for clarification request from Coder
        if "[CLARIFICATION REQUIRED]" in response.upper():
            log_to_file("CoderAgent requested clarification.", "CODER")
            
        return response, diagnostic

    def update_model(self, model: str):
        self.model = model
        self.engine.model = model
        log_to_file(f"CoderAgent model updated to: {model}", "CODER")

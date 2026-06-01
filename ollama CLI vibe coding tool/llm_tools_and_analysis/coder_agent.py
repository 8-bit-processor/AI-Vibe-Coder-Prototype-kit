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

    The CoderAgent acts as the high-level brain for coding tasks. It analyzes 
    prompts to decide whether to trigger a 'Fix Cycle' (for bugs) or a 
    'General Cycle' (for new features). It also monitors for clarification 
    requests from the underlying LLM.
    """
    def __init__(self, client: LLMClient, model: str, engine: ExecutionEngine):
        self.client = client
        self.model = model
        self.engine = engine

    async def execute_task(self, task_prompt: str, project_context: str, project_dir: Path) -> Tuple[str, Optional[str]]:
        """
        Orchestrates the execution of a coding task through the engine.
        """
        # === STEP 1: INTENT ANALYSIS ===
        # We check the prompt for keywords to decide the best architectural approach.
        log_to_file(f"CoderAgent starting task: {task_prompt[:100]}...", "CODER")
        
        is_fix = any(word in task_prompt.lower() for word in ['fix', 'bug', 'error', 'issue', 'fail'])
        
        # === STEP 2: CYCLE EXECUTION ===
        if is_fix:
            # Fix cycles include diagnostic steps and multi-attempt retries
            response, diagnostic = await self.engine.run_fix_cycle(task_prompt, project_context, project_dir)
        else:
            # General cycles focus on direct implementation or repository analysis
            response = await self.engine.run_general_cycle("general", task_prompt, project_context)
            diagnostic = None

        # === STEP 3: RESPONSE MONITORING ===
        # If the LLM indicates it doesn't have enough info, we log it for the orchestrator.
        if "[CLARIFICATION REQUIRED]" in response.upper():
            log_to_file("CoderAgent requested clarification.", "CODER")
            
        return response, diagnostic

    def update_model(self, model: str):
        self.model = model
        self.engine.model = model
        log_to_file(f"CoderAgent model updated to: {model}", "CODER")

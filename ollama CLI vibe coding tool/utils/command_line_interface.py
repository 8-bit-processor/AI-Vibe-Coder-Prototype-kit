"""
Terminal User Interface Utilities.

This module provides high-level interactive prompts for configuring the session.
It handles backend-specific logic (like model discovery) and robust project 
directory setup with validation.
"""

import questionary
from pathlib import Path
from rich.console import Console

console = Console()

async def select_model(client) -> str:
    """
    Orchestrates model selection for the active backend.
    """
    # === STEP 1: DISCOVERY ===
    # Poll the backend for what models are currently installed/available.
    models = await client.list_models()
    if not models:
        return "None"
    
    # === STEP 2: USER SELECTION ===
    return await questionary.select("Select a model:", choices=models).ask_async()

async def select_project_dir() -> Path:
    """
    Prompts the user for a project directory and ensures it is valid and accessible.
    """
    while True:
        # === STEP 1: INPUT ACQUISITION ===
        project_dir_str = await questionary.text(
            "Enter the target project folder (relative or absolute):",
            default="."
        ).ask_async()
        
        if not project_dir_str:
            continue
            
        # === STEP 2: PATH CLEANUP & RESOLUTION ===
        # Remove common input artifacts like quotes and whitespace.
        project_dir_str = project_dir_str.strip().strip('"').strip("'")
        
        try:
            # Resolve to an absolute path immediately to prevent relative-path confusion.
            project_dir = Path(project_dir_str).resolve()
            
            # === STEP 3: DIRECTORY VALIDATION ===
            # Ensure the path exists or is created with explicit permission.
            if not project_dir.exists():
                confirm = await questionary.confirm(f"Directory {project_dir} does not exist. Create it?").ask_async()
                if not confirm:
                    continue
            
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # === STEP 4: PERMISSION CHECK ===
            # Verify we have write access by touching a temporary file.
            test_file = project_dir / ".permission_test"
            test_file.touch()
            test_file.unlink()
            
            console.print(f"[green]✅ Project folder set to: {project_dir}[/green]")
            return project_dir
            
        except PermissionError:
            console.print(f"[bold red]❌ Permission Denied:[/bold red] You don't have access to create or write in {project_dir_str}")
        except Exception as e:
            console.print(f"[bold red]❌ Invalid Path:[/bold red] {str(e)}")

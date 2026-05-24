# cli.py
import questionary
from pathlib import Path
from rich.console import Console

console = Console()

async def select_model(client) -> str:
    models = await client.list_models()
    if not models:
        return "None"
    return await questionary.select("Select a model:", choices=models).ask_async()

async def select_project_dir() -> Path:
    """
    Prompts the user for a project directory and ensures it is valid and accessible.
    Handles absolute paths, relative paths, and cleans up common input artifacts like quotes.
    """
    while True:
        project_dir_str = await questionary.text(
            "Enter the target project folder (relative or absolute):",
            default="."
        ).ask_async()
        
        if not project_dir_str:
            continue
            
        # CLEANUP: Remove leading/trailing whitespace and quotes (common when copying paths in Windows)
        project_dir_str = project_dir_str.strip().strip('"').strip("'")
        
        try:
            # RESOLUTION: Convert the string input into a normalized, absolute Path object.
            # Python's pathlib handles spaces and backslashes correctly.
            project_dir = Path(project_dir_str).resolve()
            
            # CONFIRMATION: If the folder doesn't exist, ask the user before creating it.
            # This prevents accidental creation of folders due to typos.
            if not project_dir.exists():
                confirm = await questionary.confirm(f"Directory {project_dir} does not exist. Create it?").ask_async()
                if not confirm:
                    continue
            
            # INITIALIZATION: Ensure the directory exists and we have actual write permissions.
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # VALIDATION: Check for write permission by attempting a file operation.
            # This catches issues with protected system folders early.
            test_file = project_dir / ".permission_test"
            test_file.touch()
            test_file.unlink()
            
            console.print(f"[green]✅ Project folder set to: {project_dir}[/green]")
            return project_dir
            
        except PermissionError:
            console.print(f"[bold red]❌ Permission Denied:[/bold red] You don't have access to create or write in {project_dir_str}")
        except Exception as e:
            # Catch-all for malformed paths or other OS-level errors
            console.print(f"[bold red]❌ Invalid Path:[/bold red] {str(e)}")

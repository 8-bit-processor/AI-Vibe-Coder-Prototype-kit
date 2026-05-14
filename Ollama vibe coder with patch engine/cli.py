# cli.py
import questionary
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

async def select_model(client) -> str:
    models = await client.list_models()
    if not models:
        console.print("[red]No models found.[/red]")
        return ""
    return await questionary.select("Select a model:", choices=models).ask_async()

async def select_project_dir() -> Path:
    project_dir_str = await questionary.text(
        "Enter the target project folder (relative or absolute):",
        default="."
    ).ask_async()
    project_dir = Path(project_dir_str).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Project folder set to: {project_dir}[/green]")
    return project_dir

"""
Main entry point for the Ollama Agent Coder CLI.

This module orchestrates the user interface, LLM backend selection, and project
management workflow. It serves as the primary loop for interacting with the 
SessionOrchestrator to perform coding tasks, repository analysis, and app execution.
"""

import asyncio
import questionary
import os
import httpx
from rich.console import Console
from rich.panel import Panel
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from logger_utils import log_to_file
from session_orchestrator import SessionOrchestrator
from pathlib import Path

# Initialize Rich console for high-quality terminal output
console = Console(record=True)

def print_error_panel(error_type: str, message: str, suggestion: str = "None"):
    """
    Displays a formatted error message in a Rich panel.

    Args:
        error_type: The category or title of the error (e.g., "Connection Error").
        message: The detailed error message to display.
        suggestion: An optional helpful tip to resolve the issue.
    """
    content = f"[bold white]{message}[/bold white]"
    if suggestion:
        content += "\n\n[bold yellow]💡 Suggestion:[/bold yellow] " + suggestion
    console.print(Panel(
        content,
        title=f"[bold red]❌ {error_type}[/bold red]",
        border_style="red",
        expand=False
    ))

def display_conversation(orch: SessionOrchestrator):
    """
    Prints the conversation history between the user and the LLM.

    Args:
        orch: The active SessionOrchestrator instance containing the history.
    """
    history = orch.coordinator.get_conversation_history()
    if not history:
        console.print("[dim]No conversation history yet.[/dim]")
    else:
        for turn in history:
            role = turn['role'].upper()
            content = turn['content']
            style = "bold cyan" if role == "USER" else "bold magenta"
            console.print(Panel(content, title=f"[{style}]{role}[/]"))

async def main():
    """
    Main asynchronous loop for the CLI application.
    
    Handles initialization, backend/model selection, project directory setup,
    and the primary task selection menu.
    """
    console.print(Panel.fit("Ollama Agent Coder", style="bold blue"))
    log_to_file("Ollama Agent Coder Session Started")
    
    # Session state variables
    client = None        # The LLM client (Ollama or OpenAI)
    coder_model = None   # The specific model name to use for coding
    project_dir = None   # The root directory of the project being worked on
    auto_commit = True   # Whether to automatically save LLM changes to disk
    
    while True:
        try:
            # Phase 1: Ensure LLM Backend is selected and connected
            if not client:
                backend = await questionary.select("Choose LLM backend:", choices=["Ollama", "OpenAI", "Exit"]).ask_async()
                if not backend or backend == "Exit": break
                
                if backend == "Ollama":
                    client = OllamaClient()
                    try: 
                        await client.list_models()
                    except (httpx.ConnectError, httpx.HTTPError):
                        print_error_panel("Connection Error", "Could not connect to Ollama.", "Make sure Ollama is running.")
                        client = None
                        continue
                else:
                    # OpenAI backend requires an API key
                    api_key = os.getenv("OPENAI_API_KEY") or await questionary.text("Enter OpenAI API Key:").ask_async()
                    if not api_key: 
                        print_error_panel("Configuration Error", "Invalid API Key.")
                        continue
                    client = OpenAIClient(api_key)
            
            # Phase 2: Select the Coder Model
            if not coder_model:
                console.print("[bold magenta]Select your Coder Assistant model:[/bold magenta]")
                coder_model = await select_model(client)
                if not coder_model: 
                    print_error_panel("Model Error", "No models found.")
                    client = None
                    continue
            
            # Phase 3: Select and validate project directory
            if not project_dir: 
                project_dir = await select_project_dir()
            
            if not isinstance(project_dir, Path): 
                project_dir = Path(str(project_dir))

            # Final type-safety check for Pylance/Type checkers
            active_project_dir: Path = project_dir

            # Initialize the session orchestrator which manages the engine, context, and patches
            orch = SessionOrchestrator(client, coder_model, active_project_dir)
            orch.set_auto_commit(auto_commit)
            
            session_active = True
            while session_active:
                try:
                    # Display current project status and active settings
                    console.print(Panel(orch.get_status_summary(), title=f"[bold cyan]Session: {active_project_dir.name}[/bold cyan]"))
                    console.print(f"[dim]Auto-Commit: {'ENABLED' if auto_commit else 'DISABLED'} | Model: {coder_model}[/dim]")
                    
                    # Main Action Menu
                    task_action = await questionary.select("Action:", choices=[
                        "Provide Task (Coding)",
                        "Analyze Entire Repository",
                        "Run/Launch App",
                        "Settings (Menu)",
                        "Exit"
                    ]).ask_async()
                    
                    log_to_file(f"User Action: {task_action}", "USER_INPUT")

                    if task_action == "Exit": return
                    
                    if task_action == "Analyze Entire Repository":
                        # Perform a full scan and use LLM to summarize/audit the repo
                        console.print("[bold yellow]🧠 Performing full repository audit...[/bold yellow]")
                        orch.context_engine.scan_project(force=True)
                        summary = orch.get_status_summary(orch.context_engine.lint_reports)
                        
                        # Pass the persistent project goal to the audit to keep it focused.
                        # We use the architectural summary for high-level project mapping.
                        prompt = f"Perform a deep technical audit of the repository. Current goal: {orch.project_goal}"
                        context = orch.context_engine.get_architectural_summary()
                        await orch.engine.run_general_cycle("audit", prompt, context)
                        display_conversation(orch)
                        continue

                    if task_action == "Settings (Menu)":
                        action = await questionary.select("Settings:", choices=[
                            "Change Project Directory", 
                            "Change Model", 
                            "Toggle Auto-Commit", 
                            "Setup Venv",
                            "Install Dependencies",
                            "Change Project Goal", # Allow manual override of the project focus
                            "Back to Task"
                        ]).ask_async()
                        
                        if action == "Change Project Directory": 
                            project_dir = None
                            session_active = False
                        elif action == "Change Model": 
                            coder_model = None
                            session_active = False
                        elif action == "Toggle Auto-Commit":
                            auto_commit = not auto_commit
                            orch.set_auto_commit(auto_commit)
                            console.print(f"Auto-Commit is now {'ENABLED' if auto_commit else 'DISABLED'}")
                        elif action == "Setup Venv":
                            success, error = await orch.engine.setup_venv(active_project_dir)
                            if success: console.print("[green]✅ Venv created.[/green]")
                            else: print_error_panel("Environment Error", f"Venv creation failed: {error}")
                        elif action == "Install Dependencies":
                            success, error = await orch.engine.install_dependencies(active_project_dir)
                            if success: console.print("[green]✅ Deps installed.[/green]")
                            else: print_error_panel("Dependency Error", f"Installation failed: {error}")
                        elif action == "Change Project Goal":
                            new_goal = await questionary.text("Enter new project goal:", default=orch.project_goal).ask_async()
                            if new_goal: orch.project_goal = new_goal
                        continue
                    
                    if task_action == "Run/Launch App":
                        # Execute a specified Python file within the project's environment
                        target = await questionary.text("Enter entry file:", default="main.py").ask_async()
                        success, error = await orch.engine.launch_app(str(active_project_dir / target), active_project_dir)
                        if not success: 
                            print_error_panel("Execution Error", f"Launch failed: {error}")
                        continue

                    # Coding Task: The core interactive loop
                    prompt = await questionary.text("Describe the coding task:").ask_async()
                    log_to_file(f"Coding Prompt: {prompt}", "USER_INPUT")
                    
                    # Heuristic: Capture the first descriptive prompt as the project's primary goal.
                    # This ensures the agent 'remembers' what we are building during audits.
                    if orch.project_goal == "General development" and len(prompt) > 10:
                        orch.project_goal = prompt
                    
                    with console.status("[bold yellow]🧠 Gathering context...[/bold yellow]", spinner="dots"):
                        # Get 'smart' context which prioritizes files relevant to the prompt
                        context, _ = orch.context_engine.get_smart_context(prompt, target_file=orch.coordinator.get_current_working_file() or "main.py")
                    
                    # Decide between a fix cycle (diagnostic + rewrite) or a general generation cycle
                    if any(k in prompt.lower() for k in ["fix", "bug", "error"]): 
                        await orch.engine.run_fix_cycle(prompt, context, active_project_dir)
                    else: 
                        await orch.engine.run_general_cycle("coding", prompt, context)
                    
                    # Refresh context after changes
                    orch.context_engine.scan_project()
                    display_conversation(orch)
                
                except Exception as e: 
                    print_error_panel("Loop Error", str(e))
        except Exception as e: 
            print_error_panel("Startup Error", str(e))
            client = None
    
    console.print("[blue]Goodbye![/blue]")
    log_to_file("Session ended")

if __name__ == "__main__":
    asyncio.run(main())

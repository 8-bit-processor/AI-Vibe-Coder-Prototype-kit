# main.py
import os
import asyncio
import questionary
from pathlib import Path
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from src.services.recordkeeper import Recordkeeper
from src.services.file_clerk import FileClerk
from src.services.code_management import CodeManagementServices
from src.services.LLM_CLI_interface import LLM_CLI_Interface

import sys

# Explicitly set ProactorEventLoop on Windows for robust subprocess handling
if sys.platform == 'win32':
    policy_cls = getattr(asyncio, 'WindowsProactorEventLoopPolicy', None)
    if policy_cls is not None:
        asyncio.set_event_loop_policy(policy_cls())

console = Console()

# Keep system prompt empty to avoid noise for the LLM
SYSTEM_PROMPT = ""

class FacadeSessionOrchestrator:
    """
    The central orchestrator for an AI-assisted coding session.
    
    This class manages the lifecycle of a session, including model selection,
    project indexing, the conversation loop with the LLM, and the autonomous 
    execution of actions (saving files, running commands).

    Attributes:
        client: The LLM client (Ollama or OpenAI).
        model (str): The name of the LLM model being used.
        project_dir (Path): The root directory of the project being worked on.
        recordkeeper (Recordkeeper): Service for logging interactions.
        llm_cli_interface (LLM_CLI_Interface): Heuristic parser for LLM responses.
        file_clerk (FileClerk): Service for executing file and shell actions.
        code_management (CodeManagementServices): Service for file I/O and indexing.
        messages (list): The conversation history for the LLM.
        support_mode_count (int): Tracks consecutive conversational responses.
    """
    def __init__(self, client, model, project_dir):
        """Initializes the orchestrator with required services and clients."""
        self.client = client
        self.model = model
        self.project_dir = Path(project_dir)
        self.recordkeeper = Recordkeeper(orchestrator=self)
        self.llm_cli_interface = LLM_CLI_Interface(orchestrator=self, console=console)
        self.file_clerk = FileClerk(orchestrator=self)
        self.code_management = CodeManagementServices(self.project_dir, orchestrator=self)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.support_mode_count = 0 # Tracks consecutive conversational responses

    async def run(self):
        """
        Starts the main interaction loop.
        
        This method handles project indexing and the main menu for user input,
        orchestrating the flow between prompting the LLM and executing actions.
        """
        console.print(f"[bold green]Session started. Project directory: {self.project_dir}[/bold green]")
        
        # Initial context scan
        await self._index_project()

        while True:
            try:
                choice = await questionary.select(
                    "Main Menu:",
                    choices=[
                        "Prompt LLM",
                        "Run/Open File",
                        "View Files",
                        "Delete File",
                        "Setup Virtual Environment (venv)",
                        "Reset LLM Context (Clear History)",
                        "Change Model",
                        "Exit"
                    ]
                ).ask_async()

                if choice == "Prompt LLM":
                    prompt = await questionary.text("What would you like me to code?").ask_async()
                    if prompt:
                        self.messages.append({"role": "user", "content": prompt})
                        await self._process_turn()
                
                elif choice == "Run/Open File":
                    await self._run_and_feedback()
                
                elif choice == "View Files":
                    await self._view_files()
                
                elif choice == "Delete File":
                    await self._delete_file()

                elif choice == "Setup Virtual Environment (venv)":
                    await self._setup_venv()

                elif choice == "Reset LLM Context (Clear History)":
                    await self._reset_session()

                elif choice == "Change Model":
                    await self._change_model()

                elif choice == "Exit":
                    break

            except Exception as e:
                console.print(f"[bold red]Orchestrator encountered an error: {e}[/bold red]")
                import traceback
                console.print(traceback.format_exc())

    async def _index_project(self):
        """Indexes the project structure and provides it to the LLM context."""
        with console.status("[bold blue]Indexing project structure..."):
            tree = self.code_management.get_tree()
            self.messages.append({
                "role": "system", 
                "content": f"Current project structure:\n\n{tree}"
            })
            console.print(Panel(tree, title="Project Structure", border_style="blue"))
            console.print("[blue]Project structure indexed.[/blue]")

    async def _reset_session(self, silent=False):
        """
        Clears the LLM conversation history while preserving project context.

        Args:
            silent (bool): If True, suppresses console output.
        """
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.support_mode_count = 0
        await self._index_project()
        if not silent:
            console.print("[bold yellow]LLM Context reset. History cleared, project re-indexed.[/bold yellow]")

    async def _run_and_feedback(self):
        """
        Prompts the user to select a file and either runs or opens it.
        """
        files = self.code_management.list_files()
        
        if not files:
            console.print("[yellow]No files found.[/yellow]")
            return

        target = await questionary.select("Select file to run/open:", choices=files).ask_async()
        if not target:
            return
            
        action = await questionary.select(
            f"What to do with {target}?",
            choices=["Run (Shell)", "Open (Default App)"]
        ).ask_async()
        
        if action == "Run (Shell)":
            # Assume python for now, or could enhance to use file extension
            cmd = f"python {target}" if target.endswith('.py') else target
            result = await self.file_clerk.run_shell(cmd)
            
            if result["action"] == "run_error":
                error_msg = result.get("stderr") or result.get("error") or "Unknown error"
                feedback = self.llm_cli_interface.get_adaptive_prompt("debug", error=error_msg)
                console.print(f"[bold red]Execution failed. Feeding error back to LLM...[/bold red]")
                self.messages.append({"role": "user", "content": feedback})
                
                # Transparency: Display the facade's internal feedback
                console.print(Panel(feedback, title="Facade Feedback (Debug)", style="cyan"))
                
                await self._process_turn()
            else:
                console.print(Panel(result.get("stdout", ""), title="Execution Output", style="green"))

        elif action == "Open (Default App)":
            file_path = os.path.join(self.project_dir, target)
            try:
                os.startfile(file_path)
                console.print(f"[green]Opened {target} with default application.[/green]")
            except Exception as e:
                console.print(f"[red]Failed to open {target}: {e}[/red]")

    async def _setup_venv(self):
        """Creates a Python virtual environment in the project directory."""
        console.print("[bold blue]Setting up virtual environment...[/bold blue]")
        cmd = "python -m venv venv"
        result = await self.file_clerk.run_shell(cmd)
        if result["action"] == "run_success":
            console.print("[green]Virtual environment 'venv' created.[/green]")
            console.print("[yellow]Note: You may need to activate it manually depending on your shell.[/yellow]")
        else:
            error_msg = result.get('stderr') or result.get('error') or "Unknown error"
            console.print(f"[red]Failed to create venv: {error_msg}[/red]")

    async def _change_model(self):
        """Allows the user to switch the active LLM model."""
        new_model = await select_model(self.client)
        if new_model:
            self.model = new_model
            console.print(f"[green]Model changed to: {self.model}[/green]")

    async def _view_files(self):
        """Displays project files and allows viewing content."""
        files = self.code_management.list_files()
        target = await questionary.select("Select file to view:", choices=files).ask_async()
        if target:
            content = self.code_management.read_file(target)
            console.print(Panel(content, title=f"Content of {target}"))
            self.recordkeeper.log_interaction("User viewed file", target, [{"action": "view", "filename": target}])

    async def _delete_file(self):
        """Allows user to delete a file."""
        files = self.code_management.list_files()
        target = await questionary.select("Select file to delete:", choices=files).ask_async()
        if target:
            confirm = await questionary.confirm(f"Are you sure you want to delete {target}?").ask_async()
            if confirm:
                self.code_management.delete_file(target)
                console.print(f"[red]Deleted {target}[/red]")
                self.recordkeeper.log_interaction("User deleted file", target, [{"action": "delete", "filename": target}])

    async def _process_turn(self, retry_count=0):
        """
        Processes a single turn in the conversation with the LLM.
        """
        if retry_count > 5:
            console.print("[red]Max autonomous turns reached.[/red]")
            return

        # 1. Loop Detection
        if len(self.messages) >= 6:
            last_three_user = [m["content"] for m in self.messages[-6::2]]
            if len(set(last_three_user)) == 1:
                console.print("[bold red]Circular interaction detected. Triggering breakout prompt...[/bold red]")
                breakout = (
                    "We seem to be stuck in a loop. I will provide the full project context again. "
                    "Please provide the complete, corrected code for all relevant files, "
                    "ensuring there are no syntax or logic errors.\n\n"
                    f"Current Project Structure:\n{self.code_management.get_tree()}\n\n"
                    "Please proceed with the fix."
                )
                self.messages.append({"role": "user", "content": breakout})
                console.print(Panel(breakout, title="Facade Feedback (Breakout)", style="magenta"))
                retry_count = 0 

        # Transparency: Print full message history before sending
        console.print(Panel(str(self.messages), title="Full Conversation History", style="dim"))

        # 2. Get LLM Response
        with console.status(f"[bold yellow]Agent is thinking ({self.model})..."):
            response_text = await self.client.chat(self.model, self.messages)

        if not response_text:
            console.print("[red]No response from LLM.[/red]")
            return

        self.messages.append({"role": "assistant", "content": response_text})
        console.print(Panel(Markdown(response_text), title="Agent Response"))

        # 3. Process Actions
        actions = await self.file_clerk.process_llm_output(response_text, self.project_dir)
        
        # Transparency: Show interpreted actions
        console.print(Panel(str(actions), title="Interpreted Actions", style="green"))

        results_for_next_turn = []
        support_detected = False
        
        for action in actions:
            if action["action"] == "read":
                results_for_next_turn.append(f"Content of {action['filename']}:\n\n{action['content']}")
            elif action["action"] == "list":
                results_for_next_turn.append(f"Files in {action['path']}:\n" + "\n".join(action['files']))
            elif action["action"] == "run_error":
                error_msg = action.get("stderr") or action.get("error") or "Unknown error"
                results_for_next_turn.append(f"Command failed with error:\n\n```\n{error_msg}\n```")
            elif action["action"] == "feedback_required":
                results_for_next_turn.append(action["message"])
            elif action["action"] == "support_mode_detected":
                support_detected = True

        # 4. Handle Support Mode (Conversational drift)
        if support_detected:
            self.support_mode_count += 1
            if self.support_mode_count >= 2:
                console.print("[bold red]Persistent Support Mode detected. Resetting context...[/bold red]")
                await self._reset_session()
                return
            
            refocus_prompt = (
                "I am your automated facade and I handle the saving and execution of code for you. "
                "I cannot follow manual GUI instructions like 'Right-click' or 'Paste into IDE'. "
                "Please provide the full source code for the requested changes in a standard Markdown "
                "code block so I can save it automatically."
            )
            results_for_next_turn.append(refocus_prompt)
        else:
            self.support_mode_count = 0

        # 5. Log interaction
        if len(self.messages) >= 2:
            self.recordkeeper.log_interaction(self.messages[-2]["content"], response_text, actions)

        # 6. Recursive Feedback Loop
        if results_for_next_turn:
            feedback_prompt = "\n\n---\n\n".join(results_for_next_turn)
            self.messages.append({"role": "user", "content": feedback_prompt})
            
            # Transparency: Display the facade's internal feedback
            console.print(Panel(feedback_prompt, title="Facade Feedback", style="cyan"))
            
            await self._process_turn(retry_count + 1)
            return


async def main():
    console.print(Panel.fit("Ollama Agent Coder", style="bold blue"))

    # Choose LLM backend
    backend = await questionary.select(
        "Choose LLM backend:",
        choices=["Ollama", "OpenAI"]
    ).ask_async()

    if backend == "Ollama":
        client = OllamaClient()
    elif backend == "OpenAI":
        api_key = await questionary.text("Enter OpenAI API Key:").ask_async()
        client = OpenAIClient(api_key)
    else:
        console.print("[red]Unsupported backend.[/red]")
        return

    model = await select_model(client)
    if not model:
        return

    project_dir = await select_project_dir()
    
    orchestrator = FacadeSessionOrchestrator(client, model, project_dir)
    await orchestrator.run()

    console.print("[blue]Goodbye![/blue]")

if __name__ == "__main__":
    asyncio.run(main())

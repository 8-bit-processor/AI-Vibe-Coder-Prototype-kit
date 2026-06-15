import re
import asyncio
import json
import ast
import questionary
from pathlib import Path
from typing import List, Dict, Any
from src.services.base import BaseService
from code_extractor import extract_code_blocks
from rich.console import Console

console = Console()

class FileClerk(BaseService):
    """
    Service responsible for executing actions recommended by the LLM.

    Interprets the processed output from the LLM_CLI_Interface and performs
    tasks such as saving files, running shell commands, and managing user
    confirmations.
    """
    async def process_llm_output(self, response: str, project_dir: Path) -> List[Dict[str, Any]]:
        """
        Interprets the LLM response and executes identified actions.

        Args:
            response (str): The raw text response from the LLM.
            project_dir (Path): The root directory of the project.

        Returns:
            List[Dict[str, Any]]: A list of results from the performed actions.
        """
        performed_actions = []
        
        console.print("[cyan]Observing LLM recommendations...[/cyan]")
        
        # Use the new heuristic interface
        actions = self.orchestrator.llm_cli_interface.llm_output_processor(response)
        
        for item in actions:
            action = item.get('action')
            
            if action == 'save':
                filename = item.get('filename')
                content = item.get('content')
                
                # High confidence save
                self.orchestrator.code_management.save_code(filename, content)
                console.print(f"[green]Heuristic Match: Saved {filename}[/green]")
                performed_actions.append({"action": "save", "filename": filename})

            elif action == 'rename':
                old_name = item.get('old_name')
                new_name = item.get('new_name')
                message = item.get('message', f"Rename {old_name} to {new_name}?")
                
                # Ask user for confirmation
                do_rename = await questionary.confirm(message).ask_async()
                if do_rename:
                    success = self.orchestrator.code_management.rename_file(old_name, new_name)
                    if success:
                        console.print(f"[green]Renamed {old_name} -> {new_name}[/green]")
                        performed_actions.append({"action": "rename", "old_name": old_name, "new_name": new_name})
                    else:
                        console.print(f"[red]Failed to rename {old_name}[/red]")

            elif action == 'needs_confirmation':
                if item.get('type') == 'save':
                    code = item.get('content')
                    message = item.get('message')
                    
                    # Ask user for filename
                    save_it = await questionary.confirm("I see a code block. Should I save it?").ask_async()
                    if save_it:
                        filename = await questionary.text("What should be the filename?").ask_async()
                        if filename:
                            self.orchestrator.code_management.save_code(filename, code)
                            console.print(f"[green]Saved {filename}[/green]")
                            performed_actions.append({"action": "save", "filename": filename})
                
                elif item.get('type') == 'run_shell':
                    command = item.get('command')
                    message = item.get('message')
                    
                    # Dependency Check: If it's a python command, check if the file exists
                    if command.startswith("python "):
                        target_file = command.split(" ")[1]
                        full_path = self.orchestrator.project_dir / target_file
                        # Also check if it was JUST saved in this turn
                        just_saved = any(a.get('filename') == target_file for a in performed_actions)
                        
                        if not full_path.exists() and not just_saved:
                            console.print(f"[yellow]Skipping command '{command}' because {target_file} does not exist yet.[/yellow]")
                            continue

                    run_it = await questionary.confirm(message).ask_async()
                    if run_it:
                        result = await self.run_shell(command)
                        performed_actions.append(result)

            elif action == 'needs_manual_completion':
                filename = item.get('filename')
                console.print(f"[bold yellow]Snippet detected for {filename}.[/bold yellow]")
                # Ask user for full code, log the intervention
                full_code = await questionary.text(f"Please provide the full code for {filename}:").ask_async()
                if full_code:
                    self.orchestrator.code_management.save_code(filename, full_code)
                    console.print(f"[green]Saved full code for {filename}[/green]")
                    performed_actions.append({"action": "save", "filename": filename})

            elif action == 'feedback_required':
                # This will be handled by the orchestrator loop
                performed_actions.append(item)

        return performed_actions

    async def run_shell(self, command: str, is_background: bool = False) -> Dict[str, Any]:
        """
        Executes a shell command asynchronously.

        Args:
            command (str): The shell command to run.
            is_background (bool): Whether to run the command in the background.

        Returns:
            Dict[str, Any]: A dictionary containing the action result (success/error, stdout, stderr).
        """
        if is_background:
            console.print(f"[bold]Starting background process: {command}...[/bold]")
            cwd = self.orchestrator.code_management.get_build_dir()
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(cwd.absolute())
                )
                return {"action": "run_success", "command": command, "stdout": f"Process started in background (PID: {process.pid})"}
            except Exception as e:
                return {"action": "run_error", "command": command, "error": str(e)}

        console.print(f"[bold]Executing shell: {command}...[/bold]")
        try:
            cwd = self.orchestrator.code_management.get_build_dir()
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd.absolute())
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
                output = stdout.decode(errors='replace')
                error = stderr.decode(errors='replace')
                
                if process.returncode == 0:
                    console.print(f"[green]Command success[/green]")
                    return {"action": "run_success", "command": command, "stdout": output}
                else:
                    console.print(f"[red]Command failed[/red]")
                    return {"action": "run_error", "command": command, "stdout": output, "stderr": error}
            except asyncio.TimeoutError:
                console.print(f"[yellow]Command timed out after 30s.[/yellow]")
                try:
                    process.terminate()
                except:
                    pass
                return {"action": "run_success", "command": command, "stdout": "Timeout reached."}
                
        except Exception as e:
            console.print(f"[red]Execution error: {e}[/red]")
            return {"action": "run_error", "command": command, "error": str(e)}

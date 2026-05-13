import asyncio
import re
import datetime
import questionary
import os # Added for path operations
from pathlib import Path
from refactor_engine import determine_intent, build_system_prompt, get_diagnostic_prompt, get_rewrite_prompt, review_and_refine_code
from code_validator import validate_code, check_blocking_code
from patch_engine import apply_patch
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from code_extractor import extract_code_blocks, extract_code_blocks_with_filenames
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from patch_coordinator import PatchCoordinator # Added PatchCoordinator import
from project_supervisor import ProjectSupervisor # Added ProjectSupervisor import

SESSION_LOG = "session.log"

console = Console(record=True)

def log_to_file(text, category="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        # Construct the log message using simple string concatenation for maximum robustness.
        # This avoids potential parsing issues with complex formatting or internal newlines.
        log_message_content = "[" + timestamp + "] [" + category + "] " + text
        f.write(log_message_content + "\n") # Explicitly append newline character
        f.write("-" * 40 + "\n") # Ensure separator line is also correctly formed

def get_project_context(project_dir: Path) -> tuple[str, str]:
    context = "Existing project files:"
    summary = "Loaded project files:"
    MAX_SIZE = 100 * 1024  # 100KB limit
    current_size = 0
    
    # Include common configuration files in context
    files_to_include = [".py", ".md", ".txt", ".json", ".yaml", ".yml", ".env", ".gitignore", "requirements.txt", "Dockerfile"]
    
    files = sorted([f for f in project_dir.rglob("*") if f.is_file() and f.suffix.lower() in files_to_include], 
                   key=lambda f: f.suffix.lower() != ".py") # Prioritize .py files

    for file in files:
        if current_size >= MAX_SIZE:
            summary += f"- [SKIPPED] {file.name} (limit reached)"
            log_to_file(f"Skipped file '{file.name}' due to context size limit ({MAX_SIZE} bytes).", "CONTEXT_MANAGER")
            continue
            
        try:
            # Attempt to read with utf-8, fallback for encoding errors
            try:
                content = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                log_to_file(f"Encoding error reading file '{file.name}'. Attempting with 'latin-1'.", "CONTEXT_MANAGER")
                content = file.read_text(encoding="latin-1")

            file_size = len(content.encode('utf-8', errors='ignore')) # Get size in bytes for consistency

            if current_size + file_size > MAX_SIZE:
                truncated_content = content[:int((MAX_SIZE - current_size) / 2)] # Approximate truncation to stay within byte limit
                context += f"--- {file.name} (TRUNCATED) ---{truncated_content}"
                summary += f"- {file.name} ({file_size} bytes, TRUNCATED)"
                current_size = MAX_SIZE # Cap current size
                log_to_file(f"Truncated file '{file.name}' to fit context limit.", "CONTEXT_MANAGER")
            else:
                context += f"--- {file.name} ---{content}"
                summary += f"- {file.name} ({file_size} bytes)"
                current_size += file_size
        except FileNotFoundError:
            error_msg = f"File not found: {file.name}. This should not happen after rglob, but is logged for safety."
            console.print(f"[yellow]⚠️ Warning: Could not read file {file.name} ({error_msg}). It will be skipped. See session log for details.[/yellow]")
            log_to_file(f"Error reading file {file.name}: {error_msg}", "ERROR")
        except PermissionError:
            error_msg = f"Permission denied when trying to read {file.name}."
            console.print(f"[yellow]⚠️ Warning: Could not read file {file.name} ({error_msg}). It will be skipped. See session log for details.[/yellow]")
            log_to_file(f"Error reading file {file.name}: {error_msg}", "ERROR")
        except IOError as e:
            error_msg = f"I/O error reading {file.name}: {str(e)}"
            console.print(f"[yellow]⚠️ Warning: Could not read file {file.name} ({error_msg}). It will be skipped. See session log for details.[/yellow]")
            log_to_file(f"Error reading file {file.name}: {error_msg}", "ERROR")
        except Exception as e: # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred while processing {file.name}: {str(e)}"
            console.print(f"[yellow]⚠️ Warning: Could not read file {file.name} ({error_msg}). It will be skipped. See session log for details.[/yellow]")
            log_to_file(f"Error processing file {file.name}: {error_msg}", "ERROR")
            
    return context, summary

async def main():
    # Fresh startup: Delete old session log
    if os.path.exists(SESSION_LOG):
        try:
            os.remove(SESSION_LOG)
        except Exception as e:
            # If we can't delete it (e.g., file locked), we just log the error to the console
            # We don't use log_to_file here because it would recreate the file
            print(f"[dim yellow]Warning: Could not clear old session log: {e}[/dim yellow]")

    console.print(Panel.fit("Ollama Agent Coder", style="bold blue"))
    log_to_file("Ollama Agent Coder Session Started")

    backend = await questionary.select(
        "Choose LLM backend:",
        choices=["Ollama", "OpenAI"]
    ).ask_async()
    log_to_file(f"Backend selected: {backend}")

    if backend == "Ollama":
        client = OllamaClient()
    elif backend == "OpenAI":
        api_key = await questionary.text("Enter OpenAI API Key:").ask_async()
        client = OpenAIClient(api_key)
    else:
        console.print("[red]Unsupported backend.[/red]")
        log_to_file("Unsupported LLM backend selected.", "ERROR")
        return

    model = await select_model(client)
    if not model:
        log_to_file("Model selection failed or was cancelled.", "SYSTEM")
        return
    log_to_file(f"Model selected: {model}")

    project_dir = await select_project_dir()
    log_to_file(f"Project directory set: {project_dir}", "SYSTEM")
    
    # Instantiate PatchCoordinator and ProjectSupervisor
    coordinator = PatchCoordinator(project_root=str(project_dir), logger_func=log_to_file)
    supervisor = ProjectSupervisor(project_root=project_dir, logger_func=log_to_file)
    log_to_file(f"Coordinator and Supervisor instantiated for: {project_dir}", "SYSTEM")

    # Capture Original Project Purpose
    if not coordinator.get_original_project_purpose(): # Only ask once per session
        project_purpose = await questionary.text("What is the original purpose/goal of this project? (e.g., 'Develop a CLI tool for managing tasks', 'Create a simple web application')").ask_async()
        if project_purpose:
            coordinator.set_original_project_purpose(project_purpose)
            log_to_file(f"Original Project Purpose set: {project_purpose}", "SYSTEM")
        else:
            log_to_file("Original Project Purpose not provided.", "SYSTEM")
    
    # Initial context load
    project_context, context_summary = get_project_context(project_dir)
    console.print(Panel(context_summary, title="[bold green]Initial Project Context[/bold green]", border_style="green"))
    log_to_file(context_summary, "INITIAL_CONTEXT")

    while True:
        prompt = await questionary.text("What would you like me to do? (Type 'exit' to quit, 'context' to refresh)").ask_async()
        if not prompt or prompt.lower() in ['exit', 'quit']:
            log_to_file("User exited session", "SYSTEM")
            break
        
        # Refresh and display context for EVERY prompt as requested
        project_context, context_summary = get_project_context(project_dir)
        console.print(f"[dim green]{context_summary}[/dim green]")
        log_to_file(context_summary, "CONTEXT_SNAPSHOT")

        if prompt.lower() == 'context':
            console.print("[blue]Context refreshed manually.[/blue]")
            continue

        log_to_file(f"User Prompt: {prompt}", "USER_PROMPT")
        coordinator.add_to_conversation_history("user", prompt) # Add user prompt to history
        
        with console.status("[bold yellow]🤔 Thinking...analyzing project architecture...[/bold yellow]", spinner="dots"):
            supervisor_report = supervisor.get_supervisor_report()
            log_to_file(f"Supervisor Report: {supervisor_report}")
            
            # Keyword-based fallback for 'fix' intent
            repair_keywords = ['fix', 'repair', 'error', 'broken', 'not working']
            intent = await determine_intent(client, model, prompt, project_context)
            
            if any(keyword in prompt.lower() for keyword in repair_keywords):
                intent = 'fix'
                log_to_file("Overriding intent to 'fix' due to keyword match")

        log_to_file(f"Detected Intent: {intent}")
        console.print(f"[dim]Detected intent: {intent}[/dim]")

        # Check for explicit filename in user prompt for 'save' or 'create' or 'coding'
        user_specified_filename = ""
        file_match = re.search(r'(?:save to|save as|into|file|filename|path):\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', prompt, re.IGNORECASE)
        if not file_match:
            # Fallback for just the filename at the end or in quotes
            file_match = re.search(r'[\s\'"]([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)[\'"]?', prompt)
        
        if file_match:
            user_specified_filename = file_match.group(1).strip()
            log_to_file(f"User specified filename in prompt: {user_specified_filename}")
            coordinator.set_current_working_file(user_specified_filename)

        current_working_file = coordinator.get_current_working_file()
        if current_working_file:
            console.print(f"[dim]Target Focus: {current_working_file}[/dim]")

        if 'fix' in intent:
            with console.status("[bold yellow]🔍 PHASE 1: Analyzing bug diagnostics...[/bold yellow]", spinner="bouncingBar"):
                current_warnings = coordinator.get_last_warnings()
                # Pass coordinator state to diagnostic prompt
                last_patch_result = coordinator.get_last_patch_result()
                last_validation_results = coordinator.get_last_validation_results()
                
                diag_prompt = get_diagnostic_prompt(
                    prompt, 
                    project_context, 
                    coordinator,
                    supervisor_report=supervisor_report,
                    previous_warnings=current_warnings,
                    last_patch_result=last_patch_result,
                    last_validation_results=last_validation_results
                )
                diagnostic = await client.chat(model, [{"role": "user", "content": diag_prompt}])
                coordinator.add_to_conversation_history("llm", diagnostic) # Add LLM diagnostic to history
            
            log_to_file(f"Diagnostic Report: {diagnostic}", "DIAGNOSTIC")
            console.print(Panel(diagnostic, title="[bold yellow]Diagnostic Report[/bold yellow]", border_style="yellow"))

            with console.status("[bold yellow]📝 PHASE 2: Generating surgical patch...[/bold yellow]", spinner="bouncingBar"):
                current_target_file = coordinator.get_current_working_file()
                current_problematic_code = coordinator.get_last_problematic_code()
                
                rewrite_prompt = get_rewrite_prompt(
                    prompt, 
                    diagnostic, 
                    project_context, 
                    coordinator,
                    supervisor_report=supervisor_report,
                    target_file=current_target_file,
                    problematic_code_content=current_problematic_code,
                    last_patch_result=last_patch_result, # Pass patch result
                    last_validation_results=last_validation_results # Pass validation results
                )
                response_text = await client.chat(model, [{"role": "user", "content": rewrite_prompt}])
                # Automated QC pass
                with console.status("[bold magenta]🔍 Quality Control: Reviewing patch...[/bold magenta]", spinner="point"):
                    response_text, refined = await review_and_refine_code(client, model, prompt, response_text, supervisor_report, 'fix', project_context)
                    if refined:
                        log_to_file("Patch refined by QC pass.", "QC_REFINEMENT")
                coordinator.add_to_conversation_history("llm", response_text) # Add LLM patch response to history
            
            log_to_file(f"Patch Response: {response_text}", "PATCH_RESPONSE")
            
            # Extract filename from response if available
            filename = ""
            file_match = re.search(r'### FILE ###\s*(.*?)', response_text)
            if file_match:
                filename = file_match.group(1).strip()
            
            # Determine effective target for the fix
            effective_target_filename = filename # Default to filename from LLM
            if current_problematic_code:
                # If we're fixing problematic code, force a temporary filename for the output
                effective_target_filename = "temp_fix.py" # The LLM is prompted to suggest this
                console.print(f"[blue]🎯 Fixing problematic code. Output will be saved to: [bold]{effective_target_filename}[/bold][/blue]")
            elif not effective_target_filename:
                console.print("[yellow]⚠️ Target file not identified in response. Asking user.[/yellow]")
                effective_target_filename = await questionary.text("Which file should I patch? (e.g. main.py):").ask_async()

            if not effective_target_filename:
                continue

            target_path = project_dir / effective_target_filename
            
            # Attempt surgical patch only if not fixing problematic code content (which doesn't have a file)
            applied = False
            patch_success = False
            patch_message = ""
            if not current_problematic_code and "### SEARCH ###" in response_text and "### REPLACE ###" in response_text:
                console.print(f"[yellow]🔧 Attempting expert surgical repair on {effective_target_filename}...[/yellow]")
                success, msg = apply_patch(str(target_path), response_text)
                if success:
                    coordinator.log_to_coordinator(f"Surgical patch successful on {effective_target_filename}")
                    console.print(f"[green]✅ SUCCESS: {msg}[/green]")
                    log_to_file(f"Successfully patched {effective_target_filename}: {msg}", "SUCCESS")
                    applied = True
                    patch_success = True
                    patch_message = msg
                    coordinator.set_current_working_file(str(target_path))
                    # Updated call to generate_user_message
                    user_message = coordinator.generate_user_message(str(target_path), "Surgical patch applied.")
                    console.print(Panel(user_message, title="[bold blue]Action Completed[/bold blue]", border_style="blue"))
                else:
                    console.print(f"[bold red]❌ SURGICAL PATCH FAILED:[/bold red] [yellow]{msg}[/yellow]")
                    log_to_file(f"Patch failed for {effective_target_filename}: {msg}", "ERROR")
                    patch_success = False
                    patch_message = msg
                    console.print("[blue]🔄 Falling back to full file rewrite...[/blue]")
            
            # Record the patch result, whether applied or failed
            coordinator.set_last_patch_result(patch_success, patch_message, patch_applied=applied)

            # Fallback to full rewrite (always if problematic_code_content, or if surgical failed)
            if not applied or current_problematic_code:
                with console.status(f"[bold blue]📝 PHASE 3: Generating full rewrite for {effective_target_filename}...[/bold blue]", spinner="simpleDotsScrolling"):
                    # If fixing problematic code, use that as the basis for rewrite
                    if current_problematic_code:
                        rewrite_req = f"Rewrite the entire code block below to fix the issue described: {prompt}. Diagnostic: {diagnostic}. Original problematic code:```python\n{current_problematic_code}\n```"
                    else:
                        rewrite_req = f"Rewrite the entire file '{effective_target_filename}' to fix the issue described: {prompt}. Diagnostic: {diagnostic}"
                    
                    log_to_file(f"Full Rewrite Request: {rewrite_req}", "REWRITE_REQUEST")
                    
                    full_code_response = await client.chat(model, [{"role": "user", "content": rewrite_req}])
                    # Automated QC pass
                    with console.status("[bold magenta]🔍 Quality Control: Reviewing rewrite...[/bold magenta]", spinner="point"):
                        full_code_response, refined = await review_and_refine_code(client, model, prompt, full_code_response, supervisor_report, 'fix', project_context)
                        if refined:
                            log_to_file("Rewrite refined by QC pass.", "QC_REFINEMENT")
                    coordinator.add_to_conversation_history("llm", full_code_response) # Add LLM full rewrite response to history
                
                log_to_file(f"Full Rewrite Raw Response: {full_code_response}", "REWRITE_RESPONSE")
                
                code_blocks = extract_code_blocks(full_code_response)
                # If multiple blocks are returned for a full rewrite, merge them
                code = "".join(code_blocks) if code_blocks else full_code_response
                
                console.print(Panel(code, title=f"Proposed Full Rewrite for {effective_target_filename}", border_style="blue"))
                if await questionary.confirm(f"Overwrite {effective_target_filename} with this full rewrite?").ask_async():
                    # Sanitize filename input from user (remove trailing slashes) - using effective_target_filename directly
                    clean_filename = effective_target_filename.strip().rstrip(os.sep).rstrip('/') # Handle both Windows and Unix path separators

                    # Extract base filename and extension
                    base_filename, file_ext = os.path.splitext(clean_filename)
                    file_ext = file_ext.lstrip('.') if file_ext else "py" # Default to py if no extension provided

                    saved_file_path = coordinator.save_code(base_filename, code, file_extension=file_ext, description=f"Full rewrite for {clean_filename} based on '{prompt}'", operation_type="rewritten")
                    console.print(f"[green]✅ Successfully saved {saved_file_path}[/green]")
                    log_to_file(f"Saved full rewrite to {saved_file_path}", "SUCCESS")
                    
                    # Updated call to generate_user_message
                    user_message = coordinator.generate_user_message(saved_file_path, "Full file rewritten.")
                    console.print(Panel(user_message, title="[bold blue]Action Completed[/bold blue]", border_style="blue"))
        else:
            system_prompt = build_system_prompt(intent, prompt, project_context, coordinator, supervisor_report=supervisor_report) # Pass coordinator and supervisor
            log_to_file(f"Main System Prompt: {system_prompt}")
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            
            with console.status(f"[bold yellow]Generating response using {model}...[/bold yellow]", spinner="aesthetic"):
                response_text = await client.chat(model, messages)
                # Automated QC pass
                with console.status("[bold magenta]🔍 Quality Control: Reviewing response...[/bold magenta]", spinner="point"):
                    response_text, refined = await review_and_refine_code(client, model, prompt, response_text, supervisor_report, intent, project_context)
                    if refined:
                        log_to_file("General response refined by QC pass.", "QC_REFINEMENT")
                coordinator.add_to_conversation_history("llm", response_text) # Add LLM response to history
            
            log_to_file(f"Response: {response_text}")
            console.print(Panel(response_text, title="Full LLM Raw Output", border_style="dim"))

            if not response_text:
                console.print("[red]❌ Failed to generate code.[/red]")
                continue

            console.print(Panel(Markdown(response_text), title="Formatted Content"))

            code_blocks_with_filenames = extract_code_blocks_with_filenames(response_text)
            validation_results_for_coordinator = [] # Collect validation results for PatchCoordinator
            if code_blocks_with_filenames:
                for i, (suggested_filename, code) in enumerate(code_blocks_with_filenames):
                    # Use user-specified filename if only one block is found and it was a 'save'/'create' intent
                    # Otherwise, use the LLM-suggested name, or fall back to the coordinator's suggestion
                    effective_filename = user_specified_filename or suggested_filename or coordinator.suggest_filename(prompt)
                    
                    # If still generic, ask LLM for a better name
                    if effective_filename == "new_script.py":
                        naming_messages = [
                            {"role": "system", "content": "You are a file naming assistant. Based on the user's prompt and the provided code, suggest a single, short, descriptive filename with extension (e.g. 'utils.py'). Respond with ONLY the filename."},
                            {"role": "user", "content": f"Prompt: {prompt}\nCode:\n{code[:500]}..."}
                        ]
                        llm_name = await client.chat(model, naming_messages)
                        effective_filename = llm_name.strip().replace("'", "").replace('"', "")
                        log_to_file(f"LLM suggested intelligent filename: {effective_filename}")

                    console.print(Panel(code, title=f"Code Block {i+1} (Target: {effective_filename})"))
                    # Auto Syntax Validation
                    is_valid, error = validate_code(code)
                    validation_results_for_coordinator.append({"type": "syntax", "is_valid": is_valid, "detail": error, "block_index": i+1})
                    if not is_valid:
                        console.print(f"[red]❌ Syntax error detected in code block {i+1}: {error}[/red]")
                        log_to_file(f"Syntax error in generated code block {i+1}: {error}", "CODE_VALIDATION_ERROR")
                        continue

                    # System Guard: Check for blocking code
                    blocking_warnings = check_blocking_code(code)
                    if blocking_warnings:
                        console.print("[bold red]⚠️ SYSTEM GUARD WARNING:[/bold red]")
                        for warning in blocking_warnings:
                            console.print(f"  - [yellow]{warning}[/yellow]")
                        
                        log_to_file(f"Blocking code warnings for generated code block {i+1}: {blocking_warnings}", "CODE_VALIDATION_WARNING")

                        if not await questionary.confirm("This code might hang your application. Save anyway?").ask_async():
                            coordinator.set_last_warnings(blocking_warnings) # Store the warnings
                            coordinator.set_last_problematic_code(code) # Store the problematic code content
                            log_to_file(f"User chose not to save code block {i+1} due to blocking code warnings.", "USER_DECISION")
                            continue # Skip saving

                    # Bypass confirmation if intent was explicitly save/create and it's the only block
                    auto_save = (intent in ['save', 'create']) and len(code_blocks_with_filenames) == 1 and effective_filename
                    
                    save = auto_save or await questionary.confirm(f"Save Code Block {i+1} to a file?").ask_async()
                    if save:
                        if not auto_save or not effective_filename:
                            filename = await questionary.text("Enter filename (e.g., script.py):", default=effective_filename).ask_async()
                        else:
                            filename = effective_filename
                            console.print(f"[blue]💾 Auto-saving to {filename} based on your request...[/blue]")

                        if filename:
                            # Sanitize filename input from user (remove trailing slashes)
                            clean_filename = filename.strip().rstrip(os.sep).rstrip('/') # Handle both Windows and Unix path separators

                            # Extract base filename and extension
                            base_filename, file_ext = os.path.splitext(clean_filename)
                            file_ext = file_ext.lstrip('.') if file_ext else "py" # Default to py if no extension provided

                            try:
                                saved_file_path = coordinator.save_code(base_filename, code, file_extension=file_ext, description=f"New code block saved as {clean_filename}", operation_type="created")
                                console.print(f"[green]✅ Saved {saved_file_path}[/green]")
                                log_to_file(f"Saved to {saved_file_path}", "SUCCESS")
                                # Updated call to generate_user_message
                                user_message = coordinator.generate_user_message(saved_file_path, "New code block created.")
                                console.print(Panel(user_message, title="[bold blue]Action Completed[/bold blue]", border_style="blue"))
                            except Exception as err:
                                console.print(f"[red]❌ Error saving to {clean_filename}: {err}[/red]")
                                log_to_file(f"Error saving generated code block {i+1} to {clean_filename}: {err}", "ERROR")
                    else:
                        log_to_file(f"User chose not to save code block {i+1}.", "USER_DECISION")
                
                # Record all validation results after processing code blocks
                if validation_results_for_coordinator:
                    coordinator.set_last_validation_results(validation_results_for_coordinator)
            
            # Clear operation state after handling code blocks or if no code blocks were found
            coordinator.clear_operation_state()

    console.print("[blue]Goodbye![/blue]")
    log_to_file("Session ended")

if __name__ == "__main__":
    asyncio.run(main())

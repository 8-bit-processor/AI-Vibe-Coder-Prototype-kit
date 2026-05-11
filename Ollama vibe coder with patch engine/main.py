import asyncio
import re
import datetime
import questionary
from pathlib import Path
from refactor_engine import determine_intent, build_system_prompt, get_diagnostic_prompt, get_rewrite_prompt
from code_validator import validate_code, check_blocking_code
from patch_engine import apply_patch
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from code_extractor import extract_code_blocks
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

SESSION_LOG = "session.log"

console = Console(record=True)

def log_to_file(text, category="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{category}] {text}\n")
        f.write("-" * 40 + "\n")

def get_project_context(project_dir: Path) -> tuple[str, str]:
    context = "Existing project files:\n\n"
    summary = "Loaded project files:\n"
    MAX_SIZE = 100 * 1024  # 100KB limit
    current_size = 0
    
    files = sorted([f for f in project_dir.rglob("*") if f.is_file() and f.suffix in [".py", ".md", ".txt"]], 
                   key=lambda f: f.suffix != ".py")

    for file in files:
        if current_size >= MAX_SIZE:
            summary += f"- [SKIPPED] {file.name} (limit reached)\n"
            continue
            
        try:
            content = file.read_text(encoding="utf-8")
            file_size = len(content)
            
            if current_size + file_size > MAX_SIZE:
                truncated_content = content[:(MAX_SIZE - current_size)]
                context += f"--- {file.name} (TRUNCATED) ---\n{truncated_content}\n\n"
                summary += f"- {file.name} ({file_size} bytes, TRUNCATED)\n"
                current_size = MAX_SIZE
            else:
                context += f"--- {file.name} ---\n{content}\n\n"
                summary += f"- {file.name} ({file_size} bytes)\n"
                current_size += file_size
        except Exception:
            continue
            
    return context, summary

async def main():
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
        return

    model = await select_model(client)
    if not model:
        return
    log_to_file(f"Model selected: {model}")

    project_dir = await select_project_dir()
    log_to_file(f"Project directory set: {project_dir}", "SYSTEM")
    
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
        
        console.print("[yellow]🤔 Thinking...determining user intent...[/yellow]")
        
        # Keyword-based fallback for 'fix' intent
        repair_keywords = ['fix', 'repair', 'error', 'broken', 'not working']
        intent = await determine_intent(client, model, prompt, project_context)
        intent = intent.lower().strip()
        
        if any(keyword in prompt.lower() for keyword in repair_keywords):
            intent = 'fix'
            log_to_file("Overriding intent to 'fix' due to keyword match")

        log_to_file(f"Detected Intent: {intent}")
        console.print(f"[dim]Detected intent: {intent}[/dim]")

        if 'fix' in intent:
            console.print("[bold yellow]🔍 PHASE 1: Analyzing bug diagnostics...[/bold yellow]")
            diag_prompt = get_diagnostic_prompt(prompt, project_context)
            diagnostic = await client.chat(model, [{"role": "user", "content": diag_prompt}])
            log_to_file(f"Diagnostic Report: {diagnostic}", "DIAGNOSTIC")
            console.print(Panel(diagnostic, title="[bold yellow]Diagnostic Report[/bold yellow]", border_style="yellow"))

            console.print("[bold yellow]📝 PHASE 2: Generating surgical patch...[/bold yellow]")
            rewrite_prompt = get_rewrite_prompt(prompt, diagnostic, project_context)
            response_text = await client.chat(model, [{"role": "user", "content": rewrite_prompt}])
            log_to_file(f"Patch Response: {response_text}", "PATCH_RESPONSE")
            
            # Extract filename from response if available
            filename = ""
            file_match = re.search(r'### FILE ###\s*\n(.*?)\n', response_text)
            if file_match:
                filename = file_match.group(1).strip()
            
            if filename:
                console.print(f"[blue]🎯 Target identified automatically: [bold]{filename}[/bold][/blue]")
                if not await questionary.confirm(f"Apply surgical patch to {filename}?").ask_async():
                    filename = await questionary.text("Enter target filename manually:").ask_async()
            else:
                console.print("[yellow]⚠️ Target file not identified in response.[/yellow]")
                filename = await questionary.text("Which file should I patch? (e.g. main.py):").ask_async()
            
            if not filename:
                continue
                
            target_path = project_dir / filename
            
            # Attempt surgical patch
            applied = False
            if "### SEARCH ###" in response_text and "### REPLACE ###" in response_text:
                console.print(f"[yellow]🔧 Attempting expert surgical repair on {filename}...[/yellow]")
                success, msg = apply_patch(str(target_path), response_text)
                if success:
                    console.print(f"[green]✅ SUCCESS: {msg}[/green]")
                    log_to_file(f"Successfully patched {filename}: {msg}", "SUCCESS")
                    applied = True
                else:
                    console.print(f"[bold red]❌ SURGICAL PATCH FAILED:[/bold red] [yellow]{msg}[/yellow]")
                    log_to_file(f"Patch failed for {filename}: {msg}", "ERROR")
                    console.print("[blue]🔄 Falling back to full file rewrite...[/blue]")
            
            # Fallback to full rewrite
            if not applied:
                console.print(f"[bold blue]📝 PHASE 3: Generating full rewrite for {filename}...[/bold blue]")
                rewrite_req = f"Rewrite the entire file '{filename}' to fix the issue described: {prompt}. Diagnostic: {diagnostic}"
                log_to_file(f"Full Rewrite Request: {rewrite_req}", "REWRITE_REQUEST")
                
                full_code_response = await client.chat(model, [{"role": "user", "content": rewrite_req}])
                log_to_file(f"Full Rewrite Raw Response: {full_code_response}", "REWRITE_RESPONSE")
                
                code_blocks = extract_code_blocks(full_code_response)
                # If multiple blocks are returned for a full rewrite, merge them
                code = "\n".join(code_blocks) if code_blocks else full_code_response
                
                console.print(Panel(code, title=f"Proposed Full Rewrite for {filename}", border_style="blue"))
                if await questionary.confirm(f"Overwrite {filename} with this full rewrite?").ask_async():
                    target_path.write_text(code)
                    console.print(f"[green]✅ Successfully saved {target_path}[/green]")
                    log_to_file(f"Saved full rewrite to {target_path}", "SUCCESS")
        else:
            system_prompt = build_system_prompt(intent, prompt, project_context)
            log_to_file(f"Main System Prompt: {system_prompt}")
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            console.print(f"\n[bold yellow]Generating response using {model}...[/bold yellow]")
            response_text = await client.chat(model, messages)
            
            log_to_file(f"Response: {response_text}")
            console.print(Panel(response_text, title="Full LLM Raw Output", border_style="dim"))

            if not response_text:
                console.print("[red]❌ Failed to generate code.[/red]")
                continue

            console.print(Panel(Markdown(response_text), title="Formatted Content"))

            code_blocks = extract_code_blocks(response_text)
            if code_blocks:
                for i, code in enumerate(code_blocks):
                    console.print(Panel(code, title=f"Code Block {i+1}"))
                    # Auto Syntax Validation
                    is_valid, error = validate_code(code)
                    if not is_valid:
                        console.print(f"[red]❌ Syntax error detected in code block {i+1}: {error}[/red]")
                        continue

                    # System Guard: Check for blocking code
                    blocking_warnings = check_blocking_code(code)
                    if blocking_warnings:
                        console.print("[bold red]⚠️ SYSTEM GUARD WARNING:[/bold red]")
                        for warning in blocking_warnings:
                            console.print(f"  - [yellow]{warning}[/yellow]")
                        if not await questionary.confirm("This code might hang your application. Save anyway?").ask_async():
                            continue

                    save = await questionary.confirm(f"Save Code Block {i+1} to a file?").ask_async()
                    if save:
                        filename = await questionary.text("Enter filename (e.g., script.py):").ask_async()
                        if filename:
                            target_file = project_dir / filename
                            console.print(f"[blue]🔧 Working on {target_file}...[/blue]")
                            try:
                                target_file.write_text(code)
                                console.print(f"[green]✅ Saved {target_file}[/green]")
                                log_to_file(f"Saved to {target_file}")
                            except Exception as err:
                                console.print(f"[red]❌ Error saving to {target_file}: {err}[/red]")

    console.print("[blue]Goodbye![/blue]")
    log_to_file("Session ended")

if __name__ == "__main__":
    asyncio.run(main())

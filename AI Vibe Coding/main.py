# main.py
import asyncio
import questionary
from llm.ollama_client import OllamaClient
from llm.openai_client import OpenAIClient
from cli import select_model, select_project_dir
from code_extractor import extract_code_blocks
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

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

    while True:
        prompt = await questionary.text("What would you like me to code? (Type 'exit' to quit)").ask_async()
        if not prompt or prompt.lower() in ['exit', 'quit']:
            break

        messages = [
            {"role": "system", "content": "You are an expert coder. When asked to code, provide the complete code in markdown code blocks. Explain your logic briefly."},
            {"role": "user", "content": prompt}
        ]

        console.print(f"\n[bold yellow]Generating response using {model}...[/bold yellow]")
        response_text = await client.chat(model, messages)

        if not response_text:
            continue

        console.print(Panel(Markdown(response_text), title="LLM Response"))

        code_blocks = extract_code_blocks(response_text)
        if not code_blocks:
            console.print("[yellow]No code blocks found in the response.[/yellow]")
            continue

        for i, code in enumerate(code_blocks):
            console.print(Panel(code, title=f"Code Block {i+1}"))
            save = await questionary.confirm(f"Save Code Block {i+1} to a file?").ask_async()
            if save:
                filename = await questionary.text("Enter filename (e.g., script.py):").ask_async()
                if filename:
                    file_path = project_dir / filename
                    file_path.write_text(code)
                    console.print(f"[green]Saved to {file_path}[/green]")

    console.print("[blue]Goodbye![/blue]")

if __name__ == "__main__":
    asyncio.run(main())

"""
Interactive Rich Terminal CLI for Local Vibe Coder with Dual-Mode & MCP Support.
"""

import os
import sys
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from core.agent import Agent
from core.config import AgentMode
from core.events import (
    AgentDoneEvent,
    AgentEvent,
    ErrorEvent,
    ThinkingStartEvent,
    TokenStreamEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from core import sounds

console = Console(highlight=False)

PT_STYLE = Style.from_dict({
    "prompt": "ansicyan bold",
})


def format_tool_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 120:
            v_str = v_str[:117] + "..."
        if "\n" in v_str and len(v_str) < 200:
            v_str = v_str.replace("\n", "\\n")
        parts.append(f"[bold yellow]{k}[/bold yellow]={v_str}")
    return ", ".join(parts)


class TerminalUI:
    """Manages CLI rendering of agent events."""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.agent.event_callback = self.handle_event
        self.last_tool_name = ""

    def handle_event(self, event: AgentEvent):
        if isinstance(event, ThinkingStartEvent):
            console.print("[dim italic]>> Thinking & analyzing...[/dim italic]")

        elif isinstance(event, ToolCallEvent):
            self.last_tool_name = event.tool_name
            sounds.play_tool_call()

            if event.tool_name == "invoke_research_subagent":
                task_desc = event.arguments.get("task", "")
                console.print(
                    Panel(
                        f"[bold magenta]Research Goal:[/bold magenta] {task_desc}\n"
                        f"[dim italic]Subagent spawned in isolated context with read-only tools...[/dim italic]",
                        title="🔬 [bold magenta]Research Subagent Delegated[/bold magenta]",
                        border_style="magenta",
                        padding=(0, 1),
                    )
                )
            elif event.tool_name.startswith("mcp__"):
                parts = event.tool_name.split("__", 2)
                server_name = parts[1] if len(parts) > 1 else "mcp"
                tool_actual = parts[2] if len(parts) > 2 else event.tool_name
                args_formatted = format_tool_args(event.arguments)
                console.print(
                    Panel(
                        f"[bold yellow]MCP Server:[/bold yellow] {server_name}\n[bold yellow]Tool:[/bold yellow] {tool_actual}\n[bold yellow]Arguments:[/bold yellow] {args_formatted}",
                        title="🌐 [bold yellow]Executing MCP Tool[/bold yellow]",
                        border_style="yellow",
                        padding=(0, 1),
                    )
                )
            else:
                args_formatted = format_tool_args(event.arguments)
                console.print(
                    Panel(
                        f"[bold cyan]Action:[/bold cyan] {event.tool_name}\n[bold cyan]Arguments:[/bold cyan] {args_formatted}",
                        title="[bold]Executing Tool[/bold]",
                        border_style="cyan",
                        padding=(0, 1),
                    )
                )

        elif isinstance(event, ToolResultEvent):
            if event.tool_name == "invoke_research_subagent":
                console.print(
                    Panel(
                        Markdown(event.output),
                        title="🔬 [bold magenta]Research Subagent Citations & Report[/bold magenta]",
                        border_style="magenta",
                        padding=(0, 1),
                    )
                )
            else:
                border_col = "green" if event.success else "red"
                status_text = "Success" if event.success else "Error"

                if "--- a/" in event.output or "+++ b/" in event.output or "Diff:\n" in event.output:
                    diff_part = event.output
                    if "Diff:\n" in diff_part:
                        diff_part = diff_part.split("Diff:\n", 1)[1]
                    syntax = Syntax(diff_part, "diff", theme="monokai", line_numbers=False)
                    console.print(
                        Panel(
                            syntax,
                            title=f"[bold {border_col}]{event.tool_name} [{status_text}][/bold {border_col}]",
                            border_style=border_col,
                            padding=(0, 1),
                        )
                    )
                else:
                    out = event.output
                    if len(out) > 1500:
                        out = out[:1490] + f"\n... [Truncated {len(out) - 1490} chars]"

                    console.print(
                        Panel(
                            out,
                            title=f"[bold {border_col}]{event.tool_name} [{status_text}][/bold {border_col}]",
                            border_style=border_col,
                            padding=(0, 1),
                        )
                    )

        elif isinstance(event, ErrorEvent):
            sounds.play_error()
            console.print(Panel(f"[bold red]{event.message}[/bold red]", title="Error", border_style="red"))

        elif isinstance(event, AgentDoneEvent):
            sounds.play_done()
            console.print()
            if event.final_response:
                console.print(Panel(Markdown(event.final_response), title="[bold green]Response[/bold green]", border_style="green"))
            console.print(f"[dim]Turn completed with {event.total_tool_calls} tool actions.[/dim]\n")


def print_banner(model: str, workspace_dir: str, mode: AgentMode, mcp_count: int = 0):
    mode_color = "green" if mode == AgentMode.LOCAL else "cyan"
    banner = f"""
[bold cyan]  _                     _  __     ___ _             ____          _           [/bold cyan]
[bold cyan] | |    ___   ___ __ _| | \\ \\   / (_) |__   ___   / ___|___   __| | ___ _ __ [/bold cyan]
[bold cyan] | |   / _ \\ / __/ _` | |  \\ \\ / /| | '_ \\ / _ \\ | |   / _ \\ / _` |/ _ \\ '__|[/bold cyan]
[bold cyan] | |__| (_) | (_| (_| | |   \\ V / | | |_) |  __/ | |__| (_) | (_| |  __/ |   [/bold cyan]
[bold cyan] |_____\\___/ \\___\\__,_|_|    \\_/  |_|_.__/ \\___|  \\____\\___/ \\__,_|\\___|_|   [/bold cyan]
                                                                             
[bold white]Local AI Coding Assistant with MCP & Dual-Mode Support[/bold white]
[bold yellow]Model:[/bold yellow] {model} | [bold {mode_color}]Mode:[/bold {mode_color}] [{mode_color} bold]{mode.value.upper()}[/{mode_color} bold] | [bold yellow]MCP Servers:[/bold yellow] {mcp_count} connected | [bold yellow]Workspace:[/bold yellow] {workspace_dir}
[dim]Type [bold]/help[/bold] for commands, [bold]/mcp[/bold] to view servers, [bold]/mode local|cloud[/bold] to switch profiles.[/dim]
"""
    console.print(banner)


def show_help():
    table = Table(title="Available Slash Commands", border_style="dim")
    table.add_column("Command", style="cyan bold")
    table.add_column("Description", style="white")

    table.add_row("/help", "Show this help screen")
    table.add_row("/workspace", "Show current workspace directory")
    table.add_row("/workspace <path>", "Switch to a different project folder")
    table.add_row("/sound", "Toggle notification sounds on/off")
    table.add_row("/mode local", "Switch to Local Mode (32k num_ctx, zero-temp, SEARCH/REPLACE diff support)")
    table.add_row("/mode cloud", "Switch to Cloud Mode (Strict JSON function calling & large cloud context)")
    table.add_row("/mcp", "List connected MCP servers and their exposed tools")
    table.add_row("/mcp reload", "Reload mcp_config.json and reconnect servers")
    table.add_row("/models", "List all available local Ollama models")
    table.add_row("/model <name>", "Switch active LLM model (e.g. /model qwen2.5-coder:32b)")
    table.add_row("/tools", "List all available local & MCP tools")
    table.add_row("/clear", "Clear conversation history & start fresh")
    table.add_row("/plan <prompt>", "Run with explicit step-by-step planning prompt")
    table.add_row("/exit or /quit", "Exit Local Vibe Coder")
    console.print(table)


def run_cli(
    workspace_dir: str,
    default_model: str = "qwen2.5-coder:32b",
    host: str = "http://127.0.0.1:11434",
    mode: AgentMode = AgentMode.LOCAL
):
    workspace = os.path.abspath(workspace_dir)
    agent = Agent(workspace_dir=workspace, model=default_model, host=host, mode=mode)
    ui = TerminalUI(agent)

    connected_mcps = len([s for s in agent.mcp.get_status() if s["connected"]])
    print_banner(agent.model, workspace, agent.mode, connected_mcps)

    session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            mode_tag = agent.mode.value.upper()
            user_input = session.prompt(
                f"\n[vibe ({agent.model} | {mode_tag})]> ",
                style=PT_STYLE
            ).strip()

            if not user_input:
                continue

            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            cmd_arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

            # Command handling
            if cmd in ("/exit", "/quit", "exit", "quit"):
                agent.mcp.stop_all()
                console.print("[bold yellow]Goodbye! Happy vibe coding![/bold yellow]")
                break

            elif cmd in ("/help", "help", "?"):
                show_help()
                continue

            elif cmd in ("/models", "models"):
                models = agent.llm.list_models_detailed()
                if not models:
                    console.print("[bold red]No models found. Make sure Ollama is running (`ollama serve`).[/bold red]")
                else:
                    table = Table(title="Installed Ollama Models", border_style="cyan")
                    table.add_column("Model Name", style="bold green")
                    table.add_column("Parameters", style="white")
                    table.add_column("Quantization", style="yellow")
                    table.add_column("Size", style="cyan")
                    table.add_column("Status", style="bold magenta")

                    for m in models:
                        is_active = m["name"] == agent.model or m["name"].split(":")[0] == agent.model.split(":")[0]
                        status = "[bold green]ACTIVE[/bold green]" if is_active else ""
                        table.add_row(
                            m["name"],
                            m["parameter_size"],
                            m["quantization"],
                            m["size_gb"],
                            status
                        )
                    console.print(table)
                continue

            elif cmd in ("/mode", "mode"):
                if not cmd_arg:
                    console.print(f"[bold yellow]Current mode:[/bold yellow] {agent.mode.value.upper()}")
                    console.print(f"[dim]{agent.profile.description}[/dim]")
                    console.print("Usage: /mode local  OR  /mode cloud")
                else:
                    target_mode = cmd_arg.lower()
                    if target_mode in ("local", "loc"):
                        agent.set_mode(AgentMode.LOCAL)
                        console.print("[bold green]Switched to LOCAL Mode:[/bold green] num_ctx=32768, temp=0.0, Hybrid Diff & JSON parsing enabled.")
                    elif target_mode in ("cloud", "frontier"):
                        agent.set_mode(AgentMode.CLOUD)
                        console.print("[bold cyan]Switched to CLOUD Mode:[/bold cyan] Strict JSON function calling, full tool parameter schemas.")
                    else:
                        console.print(f"[bold red]Unknown mode '{target_mode}'. Use 'local' or 'cloud'.[/bold red]")
                continue

            elif cmd in ("/model", "model"):
                if not cmd_arg:
                    console.print(f"[bold yellow]Current model:[/bold yellow] {agent.model}")
                    console.print("Usage: /model <model_name>")
                else:
                    agent.set_model(cmd_arg)
                    console.print(f"[bold green]Switched active model to:[/bold green] {cmd_arg}")
                continue

            elif cmd in ("/mcp", "mcp"):
                if cmd_arg == "reload":
                    results = agent.reload_mcp()
                    console.print(f"[bold green]MCP Reloaded:[/bold green] {results}")
                else:
                    statuses = agent.mcp.get_status()
                    if not statuses:
                        console.print(
                            Panel(
                                "No MCP servers configured or running.\n"
                                f"To add servers, edit [bold yellow]{agent.mcp.config_path}[/bold yellow] and type [bold cyan]/mcp reload[/bold cyan].",
                                title="🌐 Model Context Protocol (MCP) Status",
                                border_style="yellow"
                            )
                        )
                    else:
                        table = Table(title="Connected MCP Servers", border_style="yellow")
                        table.add_column("Server", style="bold yellow")
                        table.add_column("Status", style="white")
                        table.add_column("Command", style="dim")
                        table.add_column("Tools Exposed", style="cyan")

                        for s in statuses:
                            stat = "[bold green]Online[/bold green]" if s["connected"] else "[bold red]Offline / Not Started[/bold red]"
                            tools_str = ", ".join(s["tools"]) if s["tools"] else "(None)"
                            table.add_row(s["name"], stat, s["command"], tools_str)

                        console.print(table)
                continue

            elif cmd in ("/sound", "sound"):
                enabled = sounds.toggle()
                state = "[bold green]ON[/bold green]" if enabled else "[bold yellow]OFF (muted)[/bold yellow]"
                console.print(f"[bold]Notification sounds:[/bold] {state}")
                if enabled:
                    sounds.play_done()  # preview the done sound immediately
                continue

            elif cmd in ("/workspace", "workspace"):
                if not cmd_arg:
                    console.print(f"[bold yellow]Current workspace:[/bold yellow] {agent.workspace_dir}")
                    console.print("[dim]To change: /workspace <path>[/dim]")
                else:
                    new_ws = os.path.abspath(cmd_arg)
                    if not os.path.exists(new_ws):
                        try:
                            os.makedirs(new_ws, exist_ok=True)
                            console.print(f"[bold green]Created directory:[/bold green] {new_ws}")
                        except Exception as e:
                            console.print(f"[bold red]Error creating directory: {e}[/bold red]")
                            continue
                    elif not os.path.isdir(new_ws):
                        console.print(f"[bold red]'{new_ws}' is not a directory.[/bold red]")
                        continue
                    agent.set_workspace(new_ws)
                    console.print(f"[bold green]Workspace changed to:[/bold green] {new_ws}")
                    console.print("[dim]Conversation cleared to avoid cross-project confusion.[/dim]")
                continue

            elif cmd in ("/clear", "clear"):
                agent.reset_conversation()
                console.print("[bold green]Conversation history cleared.[/bold green]")
                continue

            elif cmd in ("/tools", "tools"):
                table = Table(title="Registered Tools (Local & MCP)", border_style="cyan")
                table.add_column("Tool Name", style="bold cyan")
                table.add_column("Description", style="white")
                for t in agent.tools.list_tools():
                    table.add_row(t.name, t.description)
                console.print(table)
                continue

            elif cmd in ("/plan", "plan"):
                if not cmd_arg:
                    console.print("[bold red]Please provide a task after /plan[/bold red]")
                    continue
                user_input = (
                    f"First, write a detailed step-by-step implementation plan for the following task. "
                    f"Then systematically execute each step using your tools, run tests to verify, and summarize:\n\n{cmd_arg}"
                )

            # Run agent loop
            agent.run(user_input)

        except (KeyboardInterrupt, EOFError):
            agent.mcp.stop_all()
            console.print("\n[bold yellow]Session cancelled.[/bold yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {str(e)}[/bold red]")

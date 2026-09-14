# Local Vibe Coder 🚀

An autonomous AI pair programmer running entirely on **local hardware via Ollama** (or frontier cloud endpoints) — powered by a resilient **Universal Tool Calling Engine**, an autonomous ReAct self-correction loop, Model Context Protocol (MCP) integration, and a sandboxed research subagent.

100% private, offline-capable, and completely free.

---

## Key Features

### 🧠 Autonomous ReAct Agent Loop
- **Think → Act → Observe → Self-Correct**: The model inspects your codebase, edits files surgically, executes tests/linters, and automatically diagnoses syntax errors and test failures in a continuous feedback loop.
- **Configurable Iteration Safety**: Prevents runaway loops with profile-based turn limits.

### 🔌 Universal Tool Calling Engine
Local models output tool calls in various formats depending on their tokenizer, Ollama version, and model architecture. Local Vibe Coder includes a multi-strategy parser supporting:
- **Native JSON Function Calling**: Full OpenAI & Ollama `tool_calls` schema support.
- **Qwen XML / Tag Format**: `<function=tool_name> <parameter=key> val </tool_call>` and `<function=tool_name><parameter=key>val</parameter></function>`.
- **Tag-Wrapped JSON**: `<tool_call> ... </tool_call>` and `<function_call> ... </function_call>`.
- **Claude / XML Invoke**: `<invoke name="tool_name"><parameter name="key">val</parameter></invoke>`.
- **ReAct Format**: `Action: tool_name` + `Action Input: {...}`.
- **Aider-Style SEARCH/REPLACE Diffs**: Surgical line-by-line block replacements.
- **DeepSeek-R1 / Reasoning Support**: Safely isolates `<think>...</think>` tokens so chain-of-thought reasoning never interferes with tool execution.
- **Intelligent Parameter Aliasing**: Automatically maps parameter variants (e.g., `path` ➔ `file_path`, `cmd` ➔ `command`, `pattern` ➔ `query`, `prompt` ➔ `task`).

### ⚡ Dual-Mode Optimization Profiles

| Feature | Local Mode (`/mode local`) | Cloud Mode (`/mode cloud`) |
|---|---|---|
| **Context Window** | 32,768 tokens (`num_ctx=32768`) — eliminates 2k truncation | Frontier model context |
| **Sampling** | `temperature=0.0` (deterministic code generation) | Default API sampling |
| **Tool Calling** | Universal parser + SEARCH/REPLACE diff blocks | Strict JSON function-calling schema |
| **Target Models** | `qwen3-coder:30b`, `qwen2.5-coder:32b`, `codestral:22b`, `llama3.3` | GPT-4o, Claude 3.5 Sonnet, Gemini 2.5 |

### 🔬 Sandboxed Research Subagent
- Delegates deep codebase exploration to an isolated subagent via `invoke_research_subagent`.
- **Auto-selects the fastest small model** installed on your system (e.g., `llama3.2:latest` 3.2B) to preserve main GPU resources.
- **Strict Read-Only Sandbox**: Can only view files, find files, and grep search — cannot modify files or execute arbitrary commands.
- **Zero Context Contamination**: Operates in a fresh context window to keep your main conversation clean.

### 🌐 Model Context Protocol (MCP) Integration
Connect any MCP-compatible server to grant the agent live database access, web search, GitHub integration, or custom tooling:
- Configured via `mcp_config.json` (compatible with Claude Desktop, Cursor, and Antigravity).
- Automatic tool discovery and dynamic namespace registration (`mcp__<server>__<tool>`).

### 🗂️ Safe Workspace Management
- **Interactive Workspace Setup**: Choose your project folder on startup.
- Switch projects at runtime with `/workspace <path>` without restarting.
- All tools and subagent sandboxes are automatically rewired to the target directory.

### 🔔 Audio Feedback & Terminal UI
- Optional audio chimes (`winsound` on Windows, terminal bell fallback) for task completion and error alerts. Toggle anytime with `/sound`.
- Rich syntax-highlighted diffs, tool execution panels, and command history.

---

## Built-in Tools

| Tool | Description |
|---|---|
| `view_file` | Read file contents with line numbers and optional line slicing (`start_line`, `end_line`). |
| `write_file` | Create or overwrite files in the local workspace. |
| `replace_file_content` | Surgical in-place text replacement for token-efficient editing. |
| `run_command` | Execute shell commands (PowerShell on Windows, bash on Linux/macOS). |
| `grep_search` | Search files for regex or exact text matches. |
| `find_files` | Find files matching glob patterns (e.g. `*.py`, `**/*.json`). |
| `invoke_research_subagent` | Delegate code exploration to the fast read-only subagent. |
| `list_models` | List installed Ollama models with parameter sizes, quant levels, and disk footprint. |

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.10+**
- **[Ollama](https://ollama.com/)** installed and running

### 2. Pull Recommended Models
```powershell
# Main coding agent
ollama pull qwen3-coder:30b      # or qwen2.5-coder:32b / codestral:22b

# Fast research subagent (optional, will fall back to main model if omitted)
ollama pull llama3.2:latest
```

### 3. Install Python Dependencies
```powershell
pip install ollama rich prompt_toolkit pydantic
```

### 4. Run Local Vibe Coder
```powershell
python vibe.py
```

---

## Usage Guide

### Interactive Mode
```powershell
# Launches interactive setup prompt for workspace
python vibe.py

# Launch with specific model and workspace
python vibe.py --model qwen3-coder:30b --workspace C:\Projects\my-app
```

### Non-Interactive Batch Mode
```powershell
python vibe.py --prompt "Add unit tests for all functions in src/utils.py and run pytest"
```

---

## CLI Slash Commands

| Command | Description |
|---|---|
| `/help` | Display available commands and quick help |
| `/workspace` | Show current workspace directory |
| `/workspace <path>` | Switch active workspace directory on the fly |
| `/sound` | Toggle notification sounds on or off |
| `/mode local` | Switch to Local Mode (32k context, temp=0, universal parser) |
| `/mode cloud` | Switch to Cloud Mode (strict JSON schema) |
| `/models` | List installed Ollama models with sizes and quantization info |
| `/model <name>` | Switch active model on the fly (e.g. `/model codestral:22b`) |
| `/mcp` | List connected MCP servers and discovered tools |
| `/mcp reload` | Reconnect MCP servers from `mcp_config.json` |
| `/tools` | List all currently available tools (built-in + MCP) |
| `/plan <task>` | Instruct the agent to produce a structured plan before executing |
| `/clear` | Reset conversation history |
| `/exit` | Exit the CLI session |

---

## Configuring MCP Servers

Configure external servers in `mcp_config.json`:

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": { "BRAVE_API_KEY": "YOUR_BRAVE_API_KEY" }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost:5432/mydb"]
    },
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "app.db"]
    }
  }
}
```

Reload at runtime anytime by typing `/mcp reload`.

---

## Project Structure

```
VibeCoder/
├── vibe.py                    # Application entry point & CLI parser
├── mcp_config.json            # Active MCP server configuration
├── core/
│   ├── agent.py               # ReAct agent loop, dual profiles, message history
│   ├── config.py              # Profile configuration (LOCAL / CLOUD)
│   ├── diff_parser.py         # Aider SEARCH/REPLACE diff extractor
│   ├── events.py              # Typed UI event architecture
│   ├── llm_client.py          # Universal Tool Calling Engine & Ollama client
│   ├── sounds.py              # Notification sound engine
│   ├── mcp/
│   │   ├── client.py          # Stdio JSON-RPC 2.0 MCP subprocess client
│   │   ├── manager.py         # MCP lifecycle & ToolRegistry bridge
│   │   └── protocol.py        # MCP & JSON-RPC data models
│   └── tools/
│       ├── base.py            # Base Tool & ToolRegistry
│       ├── file_tools.py      # view_file, write_file, replace_file_content
│       ├── shell_tools.py     # run_command execution
│       ├── search_tools.py    # grep_search, find_files
│       ├── subagent_tool.py   # invoke_research_subagent (sandboxed)
│       └── model_tools.py     # list_models
└── cli/
    └── main.py                # Rich terminal REPL, event renderer, slash commands
```

---

## Security & Disclaimer

> [!WARNING]
> **Safety Notice**: Local Vibe Coder enables AI models to run shell commands and modify files in your chosen workspace directory. Always run the assistant on trusted codebases, review changes carefully, and configure appropriate permissions in your environment.

---

## License

This project is licensed under the [MIT License](LICENSE).


"""
Sandboxed Read-Only Research Subagent Tool.

Optimizations:
- Defaults to a small/fast model for cheap codebase lookups (llama3.2:latest or codellama:latest).
- Forces num_ctx=16384 to avoid Ollama's silent 2k truncation on file reads.
- Automatic fallback to prompt-based tool calling for models without native tool support.
- Enforces strict read-only sandbox: only view_file, grep_search, find_files are permitted.
- Clean isolated context: no main-agent history is passed to the subagent.
"""

from typing import Any, Callable, Dict, List, Optional
from core.events import AgentEvent, ThinkingStartEvent, ToolCallEvent, ToolResultEvent
from core.llm_client import OllamaClient
from core.tools.base import Tool, ToolRegistry
from core.tools.file_tools import ViewFileTool
from core.tools.search_tools import FindFilesTool, GrepSearchTool

# Smaller/faster models preferred for research subagent to save VRAM and time.
# The user can override per-call via the `model` argument.
PREFERRED_RESEARCH_MODELS = [
    "llama3.2:latest",
    "codellama:latest",
    "llama3:latest",
    "gemma4:12b",
]

RESEARCH_SUBAGENT_SYSTEM_PROMPT = """You are a specialized, read-only Codebase Research Subagent.
Your sole mission is to explore the codebase, locate relevant files, inspect code lines, and return clear, factual, and verified citations to the lead software engineer.

### Operating Rules:
1. **Strictly Read-Only**: You can ONLY view files, find files, and grep search. You cannot edit files or run any commands.
2. **Be Concrete and Factual**:
   - Always report exact relative file paths (e.g. `src/auth/service.py`).
   - Always report exact line numbers and function/class signatures.
   - Quote short, relevant snippets of code rather than summarizing from memory.
3. **No Hallucinations**: If something is not found in the codebase after searching, state clearly that it does not exist.
4. **Efficiency**: Do not repeat tool calls that already returned results. Move on once you have enough evidence.
5. **Final Response**: Once you have gathered the required evidence, produce a concise markdown report with:
   - **File Locations & Line Numbers**
   - **Key Definitions & Signatures**
   - **Relevant Code Snippets / Data Flows**
"""

FALLBACK_TOOL_PROMPT = """
### Available Tools (call with JSON block ```json {"name": "...", "arguments": {...}} ```):
- `view_file(file_path, start_line?, end_line?)`: View file contents with line numbers.
- `grep_search(pattern, path?)`: Search for text patterns across files.
- `find_files(pattern, path?)`: Find files by name pattern.
"""


def build_fallback_tool_descriptions() -> str:
    return FALLBACK_TOOL_PROMPT


class InvokeResearchSubagentTool(Tool):
    name = "invoke_research_subagent"
    description = (
        "Spawn a sandboxed read-only research subagent with a CLEAN context to explore the codebase, "
        "search files, and return verified factual citations (file paths, line numbers, function signatures). "
        "Uses a small fast model by default. "
        "Use for broad searches, locating symbols, understanding data flows, or any exploration that would "
        "clutter your main context. Specify `model` to use a different model."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Clear, specific description of what code, symbols, or architecture to locate."
            },
            "model": {
                "type": "string",
                "description": (
                    "Optional: model to use for research. Defaults to the fastest available small model "
                    "(e.g. llama3.2:latest). Only set this if you need a specific model."
                )
            }
        },
        "required": ["task"]
    }

    def __init__(
        self,
        workspace_dir: str,
        default_model: str = "qwen2.5-coder:32b",
        host: str = "http://127.0.0.1:11434",
        event_callback: Optional[Callable[[AgentEvent], None]] = None
    ):
        self.workspace_dir = workspace_dir
        self.main_model = default_model        # main agent's model (for fallback)
        self.default_model = default_model     # will be overridden to best small model after init
        self.host = host
        self.event_callback = event_callback
        self.llm = OllamaClient(host=host, default_model=default_model)
        self._supports_native_tools = True     # per-instance tool support flag

        # Build sandboxed READ-ONLY tool registry
        self.sandbox_tools = ToolRegistry()
        self.sandbox_tools.register(ViewFileTool(workspace_dir))
        self.sandbox_tools.register(GrepSearchTool(workspace_dir))
        self.sandbox_tools.register(FindFilesTool(workspace_dir))

        # Auto-detect the best available small model for research
        self._auto_select_research_model()

    def _auto_select_research_model(self):
        """Pick the fastest available small model installed in Ollama."""
        try:
            available = {m["name"] for m in self.llm.list_models_detailed()}
            for candidate in PREFERRED_RESEARCH_MODELS:
                # Check exact match or tag-stripped match
                if candidate in available or candidate.split(":")[0] in {n.split(":")[0] for n in available}:
                    # Find the exact tag
                    for name in available:
                        if name.split(":")[0] == candidate.split(":")[0]:
                            self.default_model = name
                            return
            # No preferred model found — fall back to main model (will be slower)
            self.default_model = self.main_model
        except Exception:
            self.default_model = self.main_model

    def set_model(self, model: str):
        """Update the main model reference (does NOT change the preferred small research model)."""
        self.main_model = model
        self.llm.default_model = model
        # Re-run auto-selection in case available models changed
        self._auto_select_research_model()

    def set_workspace(self, workspace_dir: str):
        """Rewire sandbox tools to a new workspace directory."""
        self.workspace_dir = workspace_dir
        self.sandbox_tools = ToolRegistry()
        self.sandbox_tools.register(ViewFileTool(workspace_dir))
        self.sandbox_tools.register(GrepSearchTool(workspace_dir))
        self.sandbox_tools.register(FindFilesTool(workspace_dir))

    def execute(self, task: Optional[str] = None, model: Optional[str] = None, **kwargs) -> str:
        """Run the research subagent in an isolated context loop."""
        raw_task = task if task is not None else kwargs.get("prompt", kwargs.get("query", kwargs.get("description", kwargs.get("input", ""))))
        task_str = str(raw_task).strip() if raw_task is not None else ""
        if not task_str:
            return "Error: Missing 'task' argument for research subagent."

        target_model = model or kwargs.get("model_name") or self.default_model
        tool_schemas = self.sandbox_tools.get_ollama_tools()

        # Expanded context to handle reading large files without silent truncation
        options = {
            "num_ctx": 16384,
            "temperature": 0.0,  # Deterministic: we want facts, not creativity
        }

        system_content = RESEARCH_SUBAGENT_SYSTEM_PROMPT
        # If we already know this model doesn't support native tools, add prompt-based descriptions
        if not self._supports_native_tools:
            system_content += build_fallback_tool_descriptions()

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Research task: {task_str}"}
        ]

        max_turns = 10
        for turn in range(max_turns):
            response = None
            try:
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_schemas if self._supports_native_tools else None,
                    model=target_model,
                    options=options,
                    stream=False
                )
            except Exception as e:
                err_text = str(e)
                if "does not support tools" in err_text.lower() or "status code: 400" in err_text.lower():
                    # Downgrade to prompt-based tool calling for this model
                    self._supports_native_tools = False
                    if FALLBACK_TOOL_PROMPT not in messages[0]["content"]:
                        messages[0]["content"] += build_fallback_tool_descriptions()
                    try:
                        response = self.llm.chat(
                            messages=messages,
                            tools=None,
                            model=target_model,
                            options=options,
                            stream=False
                        )
                    except Exception as retry_err:
                        return f"[Research Subagent Error]: {str(retry_err)}"
                else:
                    return f"[Research Subagent Error]: Failed LLM call: {err_text}"

            msg = response.get("message", {}) if isinstance(response, dict) else getattr(response, "message", {})
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            tool_calls = self.llm.extract_tool_calls(msg)

            # Check if native tool calls exist on the response message
            raw_tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
            is_native_call = bool(raw_tool_calls) and self._supports_native_tools

            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            if is_native_call and raw_tool_calls:
                assistant_msg["tool_calls"] = [
                    tc.model_dump() if hasattr(tc, "model_dump") else
                    tc.dict() if hasattr(tc, "dict") else tc
                    for tc in raw_tool_calls
                ]
            messages.append(assistant_msg)

            if not tool_calls:
                # Subagent finished; return its synthesis
                cleaned_report = content.strip()
                return f"=== RESEARCH SUBAGENT REPORT ===\nModel used: {target_model}\n\n{cleaned_report}"

            # Execute read-only sandbox tools
            for call in tool_calls:
                tool_name = call["name"]
                tool_args = call["arguments"]

                # Strict sandbox guard
                if not self.sandbox_tools.get(tool_name):
                    res_out = f"Error: Tool '{tool_name}' is not permitted in the read-only research sandbox."
                else:
                    res_out = self.sandbox_tools.execute(tool_name, tool_args)

                # Append tool result matching conversation format
                if is_native_call:
                    messages.append({"role": "tool", "content": res_out, "name": tool_name})
                else:
                    messages.append({"role": "user", "content": f"[Tool Result for '{tool_name}']:\n{res_out}"})

        return (
            "=== RESEARCH SUBAGENT REPORT ===\n"
            f"Model used: {target_model}\n\n"
            "Reached research iteration limit. Partial findings above represent the best gathered evidence."
        )


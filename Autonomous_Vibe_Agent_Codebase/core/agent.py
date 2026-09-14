"""
Autonomous ReAct Agent Engine for Local Vibe Coder with Dual-Mode optimization,
MCP support, and Automatic Prompt-Based Tool Calling Fallback for models without native tool support.
"""

import json
from typing import Any, Callable, Dict, Generator, List, Optional
from core.config import AgentMode, ModeProfile, LOCAL_PROFILE, CLOUD_PROFILE
from core.diff_parser import extract_search_replace_blocks, extract_new_file_blocks
from core.events import (
    AgentEvent,
    AgentDoneEvent,
    DiffPreviewEvent,
    ErrorEvent,
    ThinkingStartEvent,
    TokenStreamEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from core.llm_client import OllamaClient, clean_tool_call_text
from core.mcp.manager import MCPManager
from core.tools import ToolRegistry, create_default_registry


LOCAL_SYSTEM_PROMPT = """You are Local Vibe Coder, an expert AI software engineer running on local hardware.

### Action Guidelines:
1. **Workspace Context**:
   - All files must be saved and edited directly inside the local project workspace.
   - Always provide the relative file path (e.g. `main.py`, `src/utils.py`, `app.py`).
2. **Creating & Saving Files**:
   - Use the `write_file` tool (with `file_path="filename.ext"` and `content="..."`) or markdown code block ````python file="filename.ext" ... ````.
3. **Editing Existing Code (Aider-Style Diff Blocks)**:
   You can edit files by calling `replace_file_content` or by providing clear `SEARCH/REPLACE` blocks in your response:

path/to/file.py
<<<<<<< SEARCH
exact lines to replace
=======
new replacement lines
>>>>>>> REPLACE

4. **Explore & Research**: Use `invoke_research_subagent` or `view_file` to inspect code before modifying.
5. **Verifying Work**: Always run tests or syntax checks with `run_command`. If an error occurs, inspect the error output and fix the code immediately.
"""

CLOUD_SYSTEM_PROMPT = """You are Local Vibe Coder (Cloud Mode), an expert autonomous software engineer powered by frontier cloud models.

### Guidelines & Best Practices:
1. **Explore First**: Use `invoke_research_subagent`, `grep_search`, `find_files`, or `view_file` to thoroughly understand the architecture.
2. **MCP Integration**: Leverage connected MCP servers for external search, databases, or API operations.
3. **Be Token-Efficient**: Use `replace_file_content` for surgical updates, or `write_file` for new files.
4. **Verify & Self-Correct**: Always execute tests and linters using `run_command`. Automatically analyze failures and fix code.
5. **Proactive**: Take full ownership of the user's task and execute all required tools to deliver a complete, verified solution.
"""


def build_fallback_tool_prompt(tools: ToolRegistry) -> str:
    """Build text-based tool descriptions for models without native tool support."""
    lines = ["\n### Available Tools (Respond with JSON block ```json {\"name\": \"...\", \"arguments\": {...}} ``` to call):"]
    for t in tools.list_tools():
        props = t.parameters.get("properties", {})
        param_str = ", ".join([f"{k}: {v.get('type', 'any')}" for k, v in props.items()])
        lines.append(f"- `{t.name}({param_str})`: {t.description}")
    return "\n".join(lines)


class Agent:
    """Core autonomous coding agent loop supporting Local/Cloud profiles, MCP, and tool fallbacks."""

    def __init__(
        self,
        workspace_dir: str,
        model: str = "qwen2.5-coder:32b",
        host: str = "http://127.0.0.1:11434",
        mode: AgentMode = AgentMode.LOCAL,
        tools: Optional[ToolRegistry] = None,
        event_callback: Optional[Callable[[AgentEvent], None]] = None,
        enable_mcp: bool = True,
    ):
        self.workspace_dir = workspace_dir
        self.model = model
        self.host = host
        self.mode = mode
        self.profile: ModeProfile = LOCAL_PROFILE if mode == AgentMode.LOCAL else CLOUD_PROFILE
        self.system_prompt = LOCAL_SYSTEM_PROMPT if mode == AgentMode.LOCAL else CLOUD_SYSTEM_PROMPT
        self.tools = tools or create_default_registry(workspace_dir, default_model=model, host=host)
        self.llm = OllamaClient(host=host, default_model=model)
        self.event_callback = event_callback or (lambda e: None)
        self.supports_native_tools = True
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Initialize MCP Manager
        self.mcp = MCPManager(workspace_dir)
        if enable_mcp:
            self.reload_mcp()

    def reload_mcp(self) -> Dict[str, bool]:
        """Start/reload all MCP servers from mcp_config.json and register their tools."""
        results = self.mcp.start_all()
        self.mcp.register_tools_into(self.tools)
        return results

    def emit(self, event: AgentEvent):
        """Dispatch event to UI listener (CLI/GUI)."""
        if self.event_callback:
            self.event_callback(event)

    def set_mode(self, mode: AgentMode):
        """Toggle between LOCAL and CLOUD optimization profiles."""
        self.mode = mode
        self.profile = LOCAL_PROFILE if mode == AgentMode.LOCAL else CLOUD_PROFILE
        self.system_prompt = LOCAL_SYSTEM_PROMPT if mode == AgentMode.LOCAL else CLOUD_SYSTEM_PROMPT
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = self.system_prompt

    def set_model(self, model_name: str):
        """Change current model and reset native tool capability check."""
        self.model = model_name
        self.llm.default_model = model_name
        self.supports_native_tools = True
        subagent_tool = self.tools.get("invoke_research_subagent")
        if subagent_tool and hasattr(subagent_tool, "set_model"):
            subagent_tool.set_model(model_name)

    def reset_conversation(self):
        """Clear conversation history while preserving system prompt."""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def set_workspace(self, new_workspace: str):
        """Switch to a different project workspace directory and rewire all file tools."""
        self.workspace_dir = new_workspace
        # Re-create the tool registry pointing at the new workspace
        self.tools = create_default_registry(new_workspace, default_model=self.model, host=self.host)
        # Also rewire the subagent's sandbox to the new workspace
        subagent_tool = self.tools.get("invoke_research_subagent")
        if subagent_tool and hasattr(subagent_tool, "set_workspace"):
            subagent_tool.set_workspace(new_workspace)
        # Re-register any active MCP tools into the fresh registry
        self.mcp.register_tools_into(self.tools)
        # Clear conversation so old file paths don't bleed into new project context
        self.reset_conversation()

    def run(self, user_prompt: str) -> str:
        """
        Run the autonomous ReAct tool loop for a user prompt.
        Gracefully falls back to prompt-based tool calling if model lacks native tool support.
        """
        self.messages.append({"role": "user", "content": user_prompt})
        tool_schemas = self.tools.get_ollama_tools() if self.supports_native_tools else None
        total_tool_calls = 0

        options = {
            "num_ctx": self.profile.num_ctx,
            "temperature": self.profile.temperature,
        }

        for iteration in range(self.profile.max_iterations):
            self.emit(ThinkingStartEvent())

            # If fallback mode active, ensure tool descriptions are in system prompt
            if not self.supports_native_tools:
                tool_prompt = build_fallback_tool_prompt(self.tools)
                if tool_prompt not in self.messages[0]["content"]:
                    self.messages[0]["content"] += "\n" + tool_prompt

            response = None
            try:
                response = self.llm.chat(
                    messages=self.messages,
                    tools=tool_schemas if self.supports_native_tools else None,
                    model=self.model,
                    options=options,
                    stream=False
                )
            except Exception as e:
                err_text = str(e)
                # Catch "does not support tools" 400 error from older Ollama models (e.g. llama3:latest)
                if "does not support tools" in err_text.lower() or "status code: 400" in err_text.lower():
                    self.supports_native_tools = False
                    tool_schemas = None
                    tool_prompt = build_fallback_tool_prompt(self.tools)
                    if tool_prompt not in self.messages[0]["content"]:
                        self.messages[0]["content"] += "\n" + tool_prompt

                    try:
                        # Retry immediately without native tools parameter
                        response = self.llm.chat(
                            messages=self.messages,
                            tools=None,
                            model=self.model,
                            options=options,
                            stream=False
                        )
                    except Exception as retry_err:
                        err_msg = f"LLM Chat Error (Fallback): {str(retry_err)}"
                        self.emit(ErrorEvent(message=err_msg))
                        return err_msg
                else:
                    err_msg = f"LLM Chat Error: {err_text}"
                    self.emit(ErrorEvent(message=err_msg))
                    return err_msg

            msg = response.get("message", {}) if isinstance(response, dict) else getattr(response, "message", {})
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            tool_calls = self.llm.extract_tool_calls(msg)

            # Check for natural markdown SEARCH/REPLACE diff blocks or code fences
            if self.profile.enable_markdown_diff_blocks and content:
                diff_blocks = extract_search_replace_blocks(content)
                new_files = extract_new_file_blocks(content)

                for nb in new_files:
                    tool_calls.append({
                        "name": "write_file",
                        "arguments": {"file_path": nb.file_path, "content": nb.content, "overwrite": True}
                    })

                for db in diff_blocks:
                    tool_calls.append({
                        "name": "replace_file_content",
                        "arguments": {
                            "file_path": db.file_path,
                            "target_content": db.search_text,
                            "replacement_content": db.replace_text
                        }
                    })

            # Determine if this response used native function calling or text-based fallback
            raw_tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
            is_native_call = bool(raw_tool_calls) and self.supports_native_tools

            # Record assistant turn in context
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            if is_native_call and raw_tool_calls:
                assistant_msg["tool_calls"] = [
                    tc.model_dump() if hasattr(tc, "model_dump") else
                    tc.dict() if hasattr(tc, "dict") else tc
                    for tc in raw_tool_calls
                ]
            self.messages.append(assistant_msg)

            if not tool_calls:
                cleaned_text = clean_tool_call_text(content) if content else ""
                if cleaned_text:
                    self.emit(TokenStreamEvent(text=cleaned_text))
                self.emit(AgentDoneEvent(final_response=cleaned_text or content, total_tool_calls=total_tool_calls))
                return cleaned_text or content

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                total_tool_calls += 1

                self.emit(ToolCallEvent(tool_name=tool_name, arguments=tool_args))

                result_output = self.tools.execute(tool_name, tool_args)
                is_success = not result_output.startswith("Error:") and not result_output.startswith("[Research Subagent Error]") and not result_output.startswith("MCP Error")

                self.emit(ToolResultEvent(
                    tool_name=tool_name,
                    success=is_success,
                    output=result_output
                ))

                # Append tool result to messages with correct role matching
                if is_native_call:
                    self.messages.append({
                        "role": "tool",
                        "content": result_output,
                        "name": tool_name
                    })
                else:
                    # For fallback-parsed tool calls or models without native tools, inject as user feedback
                    self.messages.append({
                        "role": "user",
                        "content": f"[Tool Result for '{tool_name}']:\n{result_output}"
                    })

        final_msg = f"Reached maximum iteration limit ({self.profile.max_iterations} turns)."
        self.emit(AgentDoneEvent(final_response=final_msg, total_tool_calls=total_tool_calls))
        return final_msg


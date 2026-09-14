"""
Event definitions for Local Vibe Coder.
These events decouple the Core Agent Engine from any UI (CLI, Web GUI, WebSocket, Desktop app).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    """Base event emitted by the agent loop."""
    event_type: str


class TokenStreamEvent(AgentEvent):
    """Emitted when LLM streams raw text/reasoning tokens."""
    event_type: str = "token_stream"
    text: str


class ThinkingStartEvent(AgentEvent):
    """Emitted when model begins reasoning/planning a turn."""
    event_type: str = "thinking_start"


class ToolCallEvent(AgentEvent):
    """Emitted when the LLM requests a tool call."""
    event_type: str = "tool_call"
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


class ToolResultEvent(AgentEvent):
    """Emitted after a tool has been executed."""
    event_type: str = "tool_result"
    tool_name: str
    success: bool
    output: str
    call_id: Optional[str] = None


class DiffPreviewEvent(AgentEvent):
    """Emitted when a file replacement or write is about to happen."""
    event_type: str = "diff_preview"
    file_path: str
    diff_text: str
    is_new_file: bool = False


class PlanStepEvent(AgentEvent):
    """Emitted when the agent outlines a plan step."""
    event_type: str = "plan_step"
    step_number: int
    total_steps: int
    description: str


class ErrorEvent(AgentEvent):
    """Emitted on an unrecoverable or critical error."""
    event_type: str = "error"
    message: str


class AgentDoneEvent(AgentEvent):
    """Emitted when the agent finishes its task."""
    event_type: str = "agent_done"
    final_response: str
    total_tool_calls: int = 0

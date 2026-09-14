"""
Core Agent package exports with Dual-Mode support.
"""

from core.agent import Agent, LOCAL_SYSTEM_PROMPT, CLOUD_SYSTEM_PROMPT
from core.config import AgentMode, ModeProfile, LOCAL_PROFILE, CLOUD_PROFILE
from core.diff_parser import extract_search_replace_blocks, extract_new_file_blocks
from core.llm_client import OllamaClient
from core.events import (
    AgentEvent,
    TokenStreamEvent,
    ThinkingStartEvent,
    ToolCallEvent,
    ToolResultEvent,
    DiffPreviewEvent,
    ErrorEvent,
    AgentDoneEvent,
)
from core.tools import create_default_registry, ToolRegistry

__all__ = [
    "Agent",
    "LOCAL_SYSTEM_PROMPT",
    "CLOUD_SYSTEM_PROMPT",
    "AgentMode",
    "ModeProfile",
    "LOCAL_PROFILE",
    "CLOUD_PROFILE",
    "extract_search_replace_blocks",
    "extract_new_file_blocks",
    "OllamaClient",
    "ToolRegistry",
    "create_default_registry",
    "AgentEvent",
    "TokenStreamEvent",
    "ThinkingStartEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "DiffPreviewEvent",
    "ErrorEvent",
    "AgentDoneEvent",
]

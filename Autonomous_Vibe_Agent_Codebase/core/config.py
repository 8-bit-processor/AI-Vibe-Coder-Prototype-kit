"""
Configuration and Profiles for Local Mode vs Cloud Mode.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class ModeProfile(BaseModel):
    """Configuration profile tuned for either Local LLMs or Cloud Frontier LLMs."""
    mode: AgentMode
    num_ctx: int = 32768
    temperature: float = 0.0
    enable_markdown_diff_blocks: bool = True
    max_iterations: int = 25
    description: str = ""


LOCAL_PROFILE = ModeProfile(
    mode=AgentMode.LOCAL,
    num_ctx=32768,             # Explicitly fix Ollama's 2048 token silent truncation
    temperature=0.0,           # Max code determinism & syntax reliability
    enable_markdown_diff_blocks=True,  # Allow natural SEARCH/REPLACE blocks (Aider-style)
    max_iterations=20,
    description="Optimized for local Ollama models (Qwen, DeepSeek, Codestral, Llama). Expanded context & Markdown diff support."
)

CLOUD_PROFILE = ModeProfile(
    mode=AgentMode.CLOUD,
    num_ctx=128000,
    temperature=0.2,
    enable_markdown_diff_blocks=False,  # Strict JSON function calling for cloud models
    max_iterations=30,
    description="Optimized for Cloud Frontier models (Gemini, Claude, GPT-4o). Strict JSON tool calling & large context."
)

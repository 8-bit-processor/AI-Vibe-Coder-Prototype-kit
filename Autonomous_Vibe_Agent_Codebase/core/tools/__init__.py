"""
Tools package initialization and default registry builder.
"""

from typing import Optional
from core.tools.base import Tool, ToolRegistry
from core.tools.file_tools import ViewFileTool, WriteFileTool, ReplaceFileContentTool
from core.tools.shell_tools import RunCommandTool
from core.tools.search_tools import GrepSearchTool, FindFilesTool
from core.tools.subagent_tool import InvokeResearchSubagentTool
from core.tools.model_tools import ListModelsTool


def create_default_registry(workspace_dir: str, default_model: str = "qwen2.5-coder:32b", host: str = "http://127.0.0.1:11434") -> ToolRegistry:
    """Create and register all default coding tools for a workspace."""
    registry = ToolRegistry()
    registry.register(ViewFileTool(workspace_dir))
    registry.register(WriteFileTool(workspace_dir))
    registry.register(ReplaceFileContentTool(workspace_dir))
    registry.register(RunCommandTool(workspace_dir))
    registry.register(GrepSearchTool(workspace_dir))
    registry.register(FindFilesTool(workspace_dir))
    registry.register(InvokeResearchSubagentTool(workspace_dir, default_model=default_model, host=host))
    registry.register(ListModelsTool(host=host))
    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "ViewFileTool",
    "WriteFileTool",
    "ReplaceFileContentTool",
    "RunCommandTool",
    "GrepSearchTool",
    "FindFilesTool",
    "InvokeResearchSubagentTool",
    "ListModelsTool",
    "create_default_registry",
]

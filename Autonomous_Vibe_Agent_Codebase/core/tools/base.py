"""
Base Tool class and registry for Local Vibe Coder.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel


class Tool(ABC):
    """Abstract base class for all agent tools."""
    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments and return a string result."""
        pass

    def to_ollama_schema(self) -> Dict[str, Any]:
        """Convert tool to OpenAI/Ollama function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """Registry managing available tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_ollama_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_ollama_schema() for tool in self._tools.values()]

    def execute(self, name: str, kwargs: Optional[Dict[str, Any]] = None) -> str:
        tool = self.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available tools: {list(self._tools.keys())}"
        safe_kwargs = kwargs if isinstance(kwargs, dict) else {}
        try:
            return tool.execute(**safe_kwargs)
        except Exception as e:
            return f"Error executing tool '{name}': {str(e)}"

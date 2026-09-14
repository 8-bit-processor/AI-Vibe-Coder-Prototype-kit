"""
Model discovery tool for agent loop.
"""

from typing import Any, Dict, List, Optional
from core.llm_client import OllamaClient
from core.tools.base import Tool


class ListModelsTool(Tool):
    name = "list_models"
    description = (
        "List all local Ollama models installed on this machine, along with their parameter sizes and quantization levels."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def __init__(self, host: str = "http://127.0.0.1:11434"):
        self.llm = OllamaClient(host=host)

    def execute(self, **_kwargs) -> str:
        try:
            detailed = self.llm.list_models_detailed()
            if not detailed:
                return "No local Ollama models found."

            lines = ["Installed Ollama Models:"]
            for m in detailed:
                lines.append(
                    f"- {m['name']} (Size: {m['size_gb']}, Params: {m['parameter_size']}, Quant: {m['quantization']})"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing models: {str(e)}"


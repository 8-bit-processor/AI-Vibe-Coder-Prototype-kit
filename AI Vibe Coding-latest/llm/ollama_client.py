# llm/ollama_client.py
import httpx
from typing import List, Dict, Any
from llm.base import LLMClient

OLLAMA_URL = "http://localhost:11434"

class OllamaClient(LLMClient):
    """
    Client for interacting with a local Ollama server.
    """
    def __init__(self):
        """Initializes the HTTP client for Ollama."""
        self.client = httpx.AsyncClient(timeout=300.0)

    async def list_models(self) -> List[str]:
        """
        Fetches the list of installed models from the local Ollama instance.

        Returns:
            List[str]: A list of model names.
        """
        try:
            response = await self.client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            print(f"[red]Error fetching models: {e}[/red]")
            return []

    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Sends a chat request to the local Ollama instance.

        Args:
            model (str): The model to use (e.g., 'llama3').
            messages (List[Dict[str, str]]): The conversation history.

        Returns:
            str: The LLM response text.
        """
        try:
            response = await self.client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json().get('message', {}).get('content', '')
        except httpx.HTTPStatusError as e:
            print(f"[red]Ollama HTTP error: {e.response.status_code} - {e.response.text}[/red]")
            return ""
        except Exception as e:
            print(f"[red]Error chatting with Ollama: {type(e).__name__}: {e}[/red]")
            return ""

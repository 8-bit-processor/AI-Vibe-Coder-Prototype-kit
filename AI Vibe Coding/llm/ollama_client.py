# llm/ollama_client.py
import httpx
from typing import List, Dict, Any
from llm.base import LLMClient

OLLAMA_URL = "http://localhost:11434"

class OllamaClient(LLMClient):
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)

    async def list_models(self) -> List[str]:
        try:
            response = await self.client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            print(f"[red]Error fetching models: {e}[/red]")
            return []

    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
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
        except Exception as e:
            print(f"[red]Error chatting with Ollama: {e}[/red]")
            return ""

# llm/openai_client.py
from openai import AsyncOpenAI
from typing import List, Dict, Any
from llm.base import LLMClient

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def list_models(self) -> List[str]:
        try:
            response = await self.client.models.list()
            # Filter for chat models to keep the list relevant
            return [model.id for model in response.data if "gpt" in model.id]
        except Exception as e:
            print(f"[red]Error fetching models: {e}[/red]")
            return []

    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"[red]Error chatting with OpenAI: {e}[/red]")
            return ""

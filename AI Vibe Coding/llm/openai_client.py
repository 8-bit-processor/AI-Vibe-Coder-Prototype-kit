# llm/openai_client.py
import openai
from typing import List, Dict, Any
from llm.base import LLMClient

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        openai.api_key = api_key

    async def list_models(self) -> List[str]:
        try:
            response = await openai.Model.acreate()
            return [model.id for model in response.data]
        except Exception as e:
            print(f"[red]Error fetching models: {e}[/red]")
            return []

    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[red]Error chatting with OpenAI: {e}[/red]")
            return ""

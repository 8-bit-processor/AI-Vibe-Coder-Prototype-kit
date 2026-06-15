# llm/openai_client.py
from openai import AsyncOpenAI
from typing import List, Dict, Any
from llm.base import LLMClient

class OpenAIClient(LLMClient):
    """
    Client for interacting with the OpenAI API.
    """
    def __init__(self, api_key: str):
        """
        Initializes the async OpenAI client.

        Args:
            api_key (str): The OpenAI API key.
        """
        self.client = AsyncOpenAI(api_key=api_key)

    async def list_models(self) -> List[str]:
        """
        Fetches the list of available models from OpenAI.

        Returns:
            List[str]: A list of model IDs.
        """
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except Exception as e:
            print(f"[red]Error fetching models: {e}[/red]")
            return []

    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Sends a chat completion request to OpenAI.

        Args:
            model (str): The model ID (e.g., 'gpt-4').
            messages (List[Dict[str, str]]): The conversation history.

        Returns:
            str: The completion text.
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[red]Error chatting with OpenAI: {e}[/red]")
            return ""

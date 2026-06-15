# llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMClient(ABC):
    """
    Abstract base class for all LLM backend clients.

    Defines the standard interface for sending chat messages and listing 
    available models.
    """
    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Sends a conversation history to the LLM and returns the response.

        Args:
            model (str): The name of the model to use.
            messages (List[Dict[str, str]]): A list of message dictionaries.

        Returns:
            str: The LLM's text response.
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        Retrieves a list of available models from the backend.

        Returns:
            List[str]: A list of model names.
        """
        pass

"""
Foundational interfaces for LLM backend integrations.

This module defines the abstract base class (LLMClient) that all specific
backends (Ollama, OpenAI, etc.) must implement. This ensures that the rest 
of the application can interact with any LLM in a uniform, backend-agnostic way.
"""

from abc import ABC, abstractmethod
from typing import List, Dict

class LLMClient(ABC):
    """
    Abstract interface for LLM communication.
    """

    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Sends a conversation history to the model and returns the response.

        Args:
            model: The ID or name of the model to use.
            messages: A list of dicts with 'role' and 'content'.

        Returns:
            The raw string response from the LLM.
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        Retrieves a list of available model IDs from the backend.

        Returns:
            A list of strings representing model names.
        """
        pass

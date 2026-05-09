# llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMClient(ABC):
    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> str:
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        pass

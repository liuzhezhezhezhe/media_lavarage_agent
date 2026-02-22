from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    tokens_used: int = 0
    model: str = ""


class LLMClient(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        """Send a single-turn completion request."""
        ...

    @abstractmethod
    async def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> LLMResponse:
        """Send a multi-turn chat request.

        messages: [{"role": "user"|"assistant", "content": "..."], ...]
        """
        ...

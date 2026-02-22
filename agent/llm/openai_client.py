from openai import AsyncOpenAI
from agent.llm.base import LLMClient, LLMResponse


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return LLMResponse(content=content, tokens_used=tokens, model=self._model)

    async def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}] + messages,
        )
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return LLMResponse(content=content, tokens_used=tokens, model=self._model)

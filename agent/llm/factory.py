from agent.llm.base import LLMClient


def get_llm_client() -> LLMClient:
    from config import settings

    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        from agent.llm.anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    if provider == "openai":
        from agent.llm.openai_client import OpenAIClient
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url or None,
        )

    if provider == "copilot":
        from agent.llm.copilot_client import CopilotClient
        token = settings.github_token
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN not set in .env. "
                "Run with LLM_PROVIDER=copilot and no GITHUB_TOKEN to trigger device flow, "
                "which will save the token to .env automatically."
            )
        return CopilotClient(github_token=token, model=settings.copilot_model)

    if provider == "custom":
        from agent.llm.openai_client import OpenAIClient
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")

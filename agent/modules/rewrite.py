from agent.llm.base import LLMClient, LLMResponse
from agent.prompts import rewrite as prompts


async def rewrite(
    content: str,
    platform: str,
    analysis: dict,
    llm: LLMClient,
    user_style: str | None = None,
) -> str:
    """Generate platform-specific content version."""
    platform_instruction = prompts.PLATFORM_INSTRUCTIONS.get(
        platform,
        f"Write content optimized for {platform}.",
    )
    key_points = analysis.get("key_points", [])
    key_points_str = "\n".join(f"- {p}" for p in key_points) if key_points else "(none extracted)"
    style_instruction = (user_style or "").strip() or "(none)"

    user_prompt = prompts.USER_TEMPLATE.format(
        content=content,
        summary=analysis.get("summary", ""),
        key_points=key_points_str,
        style_instruction=style_instruction,
        platform_instruction=platform_instruction,
        platform=platform,
    )

    max_tokens = 2048 if platform in ("medium", "substack") else 512

    response: LLMResponse = await llm.complete(
        system=prompts.SYSTEM,
        user=user_prompt,
        max_tokens=max_tokens,
    )
    return response.content.strip()

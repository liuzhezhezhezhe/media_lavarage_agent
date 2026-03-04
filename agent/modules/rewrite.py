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
    if platform == "x" and len(key_points) >= 2:
        platform_instruction += (
            "\n\nRUNTIME PRIORITY FOR THIS INPUT:\n"
            "- The source contains multiple key points. Prefer 2–5 standalone tweets"
            " separated by a line containing only '---'.\n"
            "- Do not write them as a dependency thread; each tweet must work on its own.\n"
            "- Set PostType to TWEET_PACK unless a true THREAD is necessary."
        )
    if platform == "x":
        platform_instruction += (
            "\n\nRUNTIME OUTPUT CONTRACT (strict):\n"
            "- First non-empty line must be: PostType: TWEET or PostType: TWEET_PACK or PostType: THREAD.\n"
            "- Then one blank line, then post content.\n"
            "- If PostType is TWEET_PACK or THREAD, separate each post with a line containing only '---'."
        )
    if platform == "medium":
        platform_instruction += (
            "\n\nRUNTIME OUTPUT CONTRACT (strict):\n"
            "- Start with exactly four labeled lines in this order:\n"
            "  Title: ...\n"
            "  Subtitle: ...\n"
            "  Topics: ...\n"
            "  CanonicalURL: ...\n"
            "- Then add one blank line, then the full body content.\n"
            "- Do not omit any of the four labels, and do not rename labels."
        )
    if platform == "substack":
        platform_instruction += (
            "\n\nRUNTIME OUTPUT CONTRACT (strict):\n"
            "- Start with exactly four labeled lines in this order:\n"
            "  Title: ...\n"
            "  Subtitle: ...\n"
            "  EmailSubject: ...\n"
            "  Tags: ...\n"
            "- Then add one blank line, then the full body content.\n"
            "- Do not omit any of the four labels, and do not rename labels."
        )
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

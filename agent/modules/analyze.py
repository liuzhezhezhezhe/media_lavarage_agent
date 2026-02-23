import json
import re
from agent.llm.base import LLMClient, LLMResponse
from agent.prompts import analyze as prompts


async def analyze(content: str, llm: LLMClient) -> dict:
    """Call LLM to analyze content. Returns parsed analysis dict."""
    user_prompt = prompts.USER_TEMPLATE.format(content=content)
    response: LLMResponse = await llm.complete(
        system=prompts.SYSTEM,
        user=user_prompt,
        max_tokens=1024,
    )
    return _parse_json(response.content)


def _parse_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        # Fallback: try to find JSON object in the response
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        # Return fail-closed defaults so malformed model output is never
        # treated as publishable content.
        return {
            "idea_type": "essay",
            "novelty_score": 0,
            "clarity_score": 0,
            "publishable": False,
            "risk_level": "unknown",
            "summary": "Analysis parsing failed. Please retry.",
            "recommended_platforms": [],
            "key_points": [],
        }

"""
Pure-function platform routing.

Decides which platforms to generate content for based on content analysis.
No LLM involvement — all logic is deterministic and testable.

Platform selection is driven by two signals:
  1. idea_type  — what kind of content this is
  2. novelty_score — how fresh the idea is (low novelty = fewer platforms)
"""

# Platform fit by idea_type, ordered best-fit first.
# Rationale:
#   x         — always included; short-form suits any content type
#   medium    — suits substantive arguments, tutorials, analysis, long narrative
#   substack  — suits personal voice: opinions, essays, stories
#   reddit    — suits community-relevant content: tutorials, analysis, news, opinions
_TYPE_TO_PLATFORMS: dict[str, list[str]] = {
    "opinion":  ["x", "substack", "medium"],
    "analysis": ["x", "medium", "reddit"],
    "essay":    ["x", "medium", "substack"],
    "tutorial": ["x", "medium", "reddit"],
    "story":    ["x", "medium", "substack"],
    "thread":   ["x"],
    "news":     ["x", "reddit"],
}

_DEFAULT_PLATFORMS = ["x", "medium"]

# Below this novelty threshold, only generate for X (not worth long-form effort)
_NOVELTY_THRESHOLD_LONGFORM = 3

# Above this threshold, allow a third platform
_NOVELTY_THRESHOLD_WIDE = 6


def route(analysis: dict) -> list[str]:
    """Return ordered list of platforms to generate content for.

    Rules:
    - idea_type determines platform affinity order.
    - novelty_score gates how many platforms are included:
        < 3  → X only (idea too conventional for long-form investment)
        3–6  → top 2 platforms from the affinity list
        > 6  → top 3 platforms from the affinity list
    - X is always included and always first.
    """
    idea_type = analysis.get("idea_type", "essay")
    novelty = int(analysis.get("novelty_score") or 5)

    if novelty < _NOVELTY_THRESHOLD_LONGFORM:
        return ["x"]

    preferred = _TYPE_TO_PLATFORMS.get(idea_type, _DEFAULT_PLATFORMS)

    # Ensure x is always present and first
    ordered = ["x"] + [p for p in preferred if p != "x"]

    limit = 3 if novelty > _NOVELTY_THRESHOLD_WIDE else 2
    return ordered[:limit]

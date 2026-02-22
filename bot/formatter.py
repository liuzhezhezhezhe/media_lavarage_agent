"""Format analysis results as Telegram MarkdownV2 messages."""
import re

# Characters that must be escaped in MarkdownV2
_ESCAPE_CHARS = r"\_*[]()~`>#+-=|{}.!"


def escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return re.sub(r"([" + re.escape(_ESCAPE_CHARS) + r"])", r"\\\1", text)


def _score_bar(score: int, total: int = 10) -> str:
    filled = min(max(int(score), 0), total)
    bar = "█" * filled + "░" * (total - filled)
    return bar


def format_analysis(analysis: dict, thought_id: int) -> str:
    idea_type = analysis.get("idea_type", "unknown")
    novelty = int(analysis.get("novelty_score") or 0)
    clarity = int(analysis.get("clarity_score") or 0)
    risk = analysis.get("risk_level", "unknown")
    publishable = analysis.get("publishable", False)
    summary = analysis.get("summary", "")
    recommended = analysis.get("recommended_platforms", [])

    pub_icon = "✅" if publishable else "❌"
    platforms_str = " → ".join(p.capitalize() for p in recommended) if recommended else "N/A"

    novelty_bar = _score_bar(novelty)
    clarity_bar = _score_bar(clarity)

    lines = [
        "📊 *Analysis Results*",
        "",
        f"Type: `{escape(idea_type)}`",
        f"Novelty: {novelty}/10  {escape(novelty_bar)}",
        f"Clarity: {clarity}/10  {escape(clarity_bar)}",
        f"Risk: `{escape(risk)}`",
        f"Publishable: {pub_icon}",
        "",
        f"💡 Summary: {escape(summary)}",
        "",
        f"📌 Recommended platforms: *{escape(platforms_str)}*",
        f"_\\(Record ID: {thought_id} — full version: /show {thought_id}\\)_",
    ]
    return "\n".join(lines)


_PLATFORM_ICONS = {
    "x": "🐦",
    "medium": "📝",
    "substack": "📧",
    "reddit": "🤖",
}

_MAX_INLINE_CHARS = 3800  # leave headroom below 4096


def format_platform_output(platform: str, content: str, thought_id: int) -> tuple[str, bool]:
    """
    Returns (message_text, was_truncated).
    Truncated content will include a note about /show <id>.
    """
    icon = _PLATFORM_ICONS.get(platform, "📄")
    platform_name = escape(platform.capitalize())
    separator = escape("─" * 17)

    header = f"{icon} *{platform_name}*\n{separator}\n"

    # Escape the content for MarkdownV2
    escaped_content = escape(content)

    # Check if we need to truncate
    full = header + escaped_content
    if len(full) <= _MAX_INLINE_CHARS:
        return full, False

    # Truncate
    max_content_len = _MAX_INLINE_CHARS - len(header) - 100
    truncated_content = escaped_content[:max_content_len]
    # Try not to cut mid-word
    last_space = truncated_content.rfind(" ")
    if last_space > max_content_len - 50:
        truncated_content = truncated_content[:last_space]

    footer = f"\n\n_\\(Truncated — full version: /show {thought_id}\\)_"
    return header + truncated_content + footer, True


def format_history(records: list[dict]) -> str:
    if not records:
        return "No records yet."

    lines = ["📋 *Recent Records*", ""]
    for r in records:
        idea_type = escape(r.get("idea_type") or "unknown")
        summary = escape((r.get("summary") or "")[:60])
        created = escape(r.get("created_at", "")[:10])
        rid = r["id"]
        novelty = int(r.get("novelty_score") or 0)
        lines.append(f"`#{rid}` {created} \\| `{idea_type}` \\| {novelty}/10")
        if summary:
            lines.append(f"     _{summary}_")
        lines.append(f"     👉 /show {rid}")
        lines.append("")

    return "\n".join(lines)


def format_full_record(thought: dict, outputs: list[dict]) -> list[str]:
    """Return list of messages for /show command."""
    messages = []

    # Analysis summary
    idea_type = escape(thought.get("idea_type") or "unknown")
    novelty = int(thought.get("novelty_score") or 0)
    clarity = int(thought.get("clarity_score") or 0)
    risk = escape(thought.get("risk_level") or "unknown")
    summary = escape(thought.get("summary") or "")
    created = escape(thought.get("created_at", "")[:19])
    source = escape(thought.get("source") or "text")
    pub = "✅" if thought.get("publishable") else "❌"

    msg1 = "\n".join([
        f"📊 *Record \\#{thought['id']}*",
        "",
        f"Date: `{created}`",
        f"Source: `{source}`",
        f"Type: `{idea_type}`",
        f"Novelty: {novelty}/10  {escape(_score_bar(int(novelty or 0)))}",
        f"Clarity: {clarity}/10  {escape(_score_bar(int(clarity or 0)))}",
        f"Risk: `{risk}`  Publishable: {pub}",
        "",
        f"💡 {summary}",
    ])
    messages.append(msg1)

    # Each platform output
    for output in outputs:
        platform = output.get("platform", "")
        content = output.get("content", "")
        icon = _PLATFORM_ICONS.get(platform, "📄")
        platform_name = escape(platform.capitalize())
        separator = escape("─" * 17)
        escaped_content = escape(content)

        msg = f"{icon} *{platform_name}*\n{separator}\n{escaped_content}"
        # Split into chunks if too long
        for chunk in _split_message(msg):
            messages.append(chunk)

    return messages


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks

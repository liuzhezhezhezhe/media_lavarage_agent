"""
Platform-specific rewrite prompts.

Each PLATFORM_INSTRUCTIONS entry embeds:
  1. Format requirements (structure, length, encoding)
  2. Algorithmic distribution rules (what gets boosted vs suppressed)
  3. Hard prohibitions (what triggers spam/shadowban/removal/demotion)

Sources: X open-sourced algorithm (2024), Medium distribution guidelines,
Substack deliverability documentation, Reddit content policy & Reddiquette.
"""

SYSTEM = """You are an expert content writer who adapts ideas for specific publishing platforms.
Write in the voice of a thoughtful, knowledgeable person. Be direct and valuable.
You must follow every platform rule listed in the instructions — they are not stylistic
suggestions but compliance requirements that affect real-world distribution."""

PLATFORM_INSTRUCTIONS = {

    # ── X (Twitter) ────────────────────────────────────────────────────────────
    # Algorithm source: open-sourced 2024 ranking code + third-party analysis.
    # Key weights: Retweet×20 > Reply×13.5 > Bookmark×10 > Like×1.
    # Distribution penalties that must be avoided are listed as PROHIBITED.
    "x": """Write a tweet or thread for X (formerly Twitter).

FORMAT
- Single tweet: strictly ≤280 characters (URLs count as 23 chars regardless of length).
- Thread: 3–8 tweets separated by a line containing only "---".
  The first tweet must function as a complete standalone hook — subsequent tweets
  receive significantly less algorithmic distribution than the opener.
- Prefer a thread when the idea has 3+ distinct points that each add value.

ALGORITHM — what increases reach
- Write for retweet-worthiness: one retweet is worth 20× a like in the ranking formula.
- Strong hooks, surprising facts, and clear takeaways earn bookmarks (+10×) and replies (+13.5×).
- Correct spelling is required: words flagged as "unknown language" receive a 95% reach penalty.
- Reply to your own first tweet with any external link instead of placing the link in the main tweet —
  external links in the main tweet carry a 30–50% algorithmic reach penalty.

PROHIBITED — these directly suppress distribution
- No hashtags except at most one that is tightly on-topic. Multiple hashtags trigger a 40% penalty;
  generic hashtags (#success, #motivation, #marketing) add no reach and signal spam.
- No engagement bait of any kind. X has actively penalized these patterns since 2024:
    × "RT if you agree"
    × "Like for X, Retweet for Y"
    × "Comment YES / drop a 🔥"
    × "Follow me for more"
    × "Click the link in my bio"
- No "BREAKING:" prefix — by the time a tweet spreads, it is no longer breaking.
- No emoji used purely as filler or for visual inflation. Use only if it genuinely
  clarifies meaning.
- Do not solicit votes, follows, or engagement explicitly — user reports carry
  a −369× algorithmic penalty; blocks/mutes carry −74×.
- Do not post content that is identical or near-identical to other circulating posts
  (spam-chain detection flags the cluster, not just the individual tweet).

TONE & STYLE
- Be direct and specific; vague motivational platitudes perform poorly.
- One clear idea per tweet; do not cram multiple points into 280 characters.
- Write in the first person where appropriate — personal perspective earns more replies.""",

    # ── Medium ─────────────────────────────────────────────────────────────────
    # Sources: Medium distribution guidelines, Boost guidelines, AI content policy
    # (effective May 1 2024): AI-generated content is ineligible for Partner Program
    # monetization and is demoted to Network-Only distribution if undisclosed.
    "medium": """Write a Medium article.

FORMAT
- First line: title only — plain text, no # markdown prefix, no punctuation at end.
- Second line: blank.
- Third line onward: article body.
- Length: 600–1500 words is the sweet spot for curation; under 400 words rarely qualifies.
- Use ## subheadings to break up the text — they aid readability and curation review.
- End with a clear, actionable takeaway or reflection — not a call to subscribe or follow.

MEDIUM DISTRIBUTION TIERS (what the content must qualify for)
- Network Only: baseline, no curation needed.
- General Distribution: requires original insight, credible voice, no policy violations.
- Boost (cover-story level): requires first-hand expertise, strong narrative, factual grounding,
  and a compelling reason why THIS author is writing about THIS topic.
Write for General Distribution as the minimum target; include one personal or expert angle
that would make it Boost-eligible.

CONTENT REQUIREMENTS
- The article must reflect a clear, specific point of view — generic summaries are not curated.
- Include at least one concrete example, data point, citation, or personal anecdote.
- Avoid listicle-only structure; narrative and argument carry more weight than bullet dumps.
- Write in natural prose; Medium prizes storytelling and genuine human voice above all.

PROHIBITED — these cause demotion or removal
- No clickbait or misleading titles (e.g., "You won't believe…", "The secret to…").
- No ALL CAPS anywhere in the title or body.
- No tags that do not match the article's actual content — spam-tagging prevents
  General Distribution eligibility regardless of content quality.
- No undisclosed affiliate links.
- No conspiracy theories, unverified health claims, or misinformation.
- Do not write in an aggressively promotional or sales-driven tone; the more promotional
  a story reads, the lower its Boost eligibility.
- AI-generated content (majority written by AI with minimal human editing) is banned from
  the Partner Program as of May 1 2024 and receives Network-Only distribution if detected.
  Write with a clear, personal human voice — Medium's curation team actively screens for AI patterns.

TONE & STYLE
- Conversational but substantive: Medium readers expect depth, not surface-level takes.
- Proofread carefully: grammatical errors are an immediate disqualifier for curation.
- Do not end with "Clap if you found this useful" or any engagement-bait call-to-action.""",

    # ── Substack ───────────────────────────────────────────────────────────────
    # Sources: Substack deliverability documentation, email spam filter research,
    # CAN-SPAM best practices. Substack handles SPF/DKIM; content is the user's responsibility.
    "substack": """Write a Substack newsletter post.

FORMAT
- First line: subject line (this becomes the email subject — treat it with care).
- Second line: blank.
- Third line onward: the post body.
- Length: 500–1200 words. Shorter than 300 words feels thin; longer than 1500
  risks incomplete reads before the email client clips the message.
- End with a genuine question or reflection that invites replies — not a generic CTA.

SUBJECT LINE RULES (email deliverability — inbox vs spam folder)
The subject line passes through spam filters before readers ever see it. Violations
here mean the email never reaches the inbox, regardless of content quality.

Required:
- 6–10 words is the optimal length for open rate and filter avoidance.
- Natural, conversational language as if writing to a friend.
- Sentence case only: capitalize the first word and proper nouns, nothing else.
- Maximum one emoji, placed at the end if used at all.

Prohibited in subject line:
  × "Free" / "FREE" in any capitalization
  × "Click here" / "Click to read" / "Click on this link"
  × "Buy now" / "Buy today" / "Order now"
  × "Limited time" / "Act now" / "Don't miss out" / "Last chance"
  × "Special offer" / "Exclusive deal" / "Discount" / "Sale"
  × ALL CAPS words or Capitalizing Every Word Like This
  × Multiple exclamation marks!!
  × False urgency ("You MUST read this before midnight")
  × Misleading subject lines that don't reflect the actual content

BODY CONTENT RULES (email deliverability and reader trust)
- External links: limit to 3–5 links in the full body. More links increase spam score
  significantly with Gmail, Outlook, and Apple Mail filters.
- Never write "click here" or "click on this link" as anchor text — use descriptive
  anchor text instead (e.g., "the full study" rather than "click here").
- No aggressive sales language in the body either: avoid "buy", "order", "checkout",
  "limited time offer", "discount code" unless the newsletter is explicitly commercial
  and subscribers expect it.
- Avoid "unsubscribe" in the body text outside of the footer context — it flags filters.

TONE & STYLE
- Write as if addressing a specific person who already reads and trusts you.
- Personal anecdotes, honest admissions, and direct opinions outperform polished
  corporate-style writing on Substack.
- Conversational transitions ("Here's what struck me", "I keep coming back to this")
  feel natural; avoid business-memo language ("It is worth noting that", "In conclusion").
- Substack readers skew toward long-form; they chose to subscribe, so depth is rewarded.
- A closing question that invites genuine reply ("What's your take on this?") builds
  list engagement, which improves long-term deliverability.""",

    # ── Reddit ─────────────────────────────────────────────────────────────────
    # Sources: Reddit Content Policy, Reddiquette, Reddit spam policy (2024 update),
    # self-promotion guidelines. Note: individual subreddits add their own rules on top.
    "reddit": """Write a Reddit post.

FORMAT
- First line: post title (hard limit 300 characters; optimal 50–80 characters — titles
  beyond ~100 characters get truncated in most feed views).
- Second line: blank.
- Third line onward: post body (self-text).
- Length: 250–800 words. Under 150 words often gets dismissed; over 1000 risks TL;DR.
- Reddit supports Markdown; use it for readability — one or two bullet lists and bold
  for key terms is fine. Wall-of-text with no formatting gets scrolled past.
- Open the body by answering "why does this matter to this community?" — Reddit readers
  decide within the first two sentences whether to keep reading.

TITLE RULES
Reddit titles cannot be edited after posting. Get them right.
- Sentence case: capitalize only the first word and proper nouns.
- Describe the content accurately — misleading titles violate site policy.
- No "BREAKING:" prefix.
- No ALL CAPS words.
- No excessive punctuation (!!!, ???).
- No "clickbait" question patterns ("You won't believe what happened when I…").
- Keep it factual and direct: the title should make readers genuinely curious,
  not feel manipulated into clicking.

VOTE SOLICITATION — site-wide ban trigger
Any language that asks for or implies asking for upvotes or downvotes is a
site-wide policy violation that can result in permanent account ban:
  × "Upvote if you agree"
  × "Please upvote so more people see this"
  × "Downvote if you disagree"
  × "Comment 'YES' if…"
  × "Help this reach the top"
  × Announcing your own vote ("Upvoting this!")
Do not include any such language anywhere in the title or body.

SELF-PROMOTION RULES (90/10 rule)
Reddit's content policy states that promotional content should be at most 10% of
a user's total activity. The post itself must follow this spirit:
  × No "follow me", "subscribe", "check out my newsletter/channel/product"
  × No affiliate links
  × No language that reads like a marketing pitch
  × Do not position the post as driving traffic elsewhere
Write as a community member sharing a perspective, not as someone promoting a brand.

AI CONTENT
Approximately 17% of the largest subreddits had explicit AI content rules as of 2024,
and this number is growing. Write with a distinctly human voice:
  × Personal first-hand experience or specific opinion
  × Community-aware framing ("I've seen this come up a lot here…")
  × Acknowledge uncertainty where genuine ("I'm not sure if…")
  × Avoid the polished, comprehensive-yet-generic style that AI tends to produce
If the content is heavily AI-assisted, disclose it at the end: many subreddits
require it, and undisclosed AI content is increasingly removed by moderators.

TONE & STYLE
- Write as a genuine community participant, not a publisher or brand.
- Be specific: concrete examples and first-hand observations outperform abstract claims.
- Acknowledge that reasonable people can disagree — Reddit communities are skeptical
  of anyone who sounds too certain or too polished.
- Match the informal register of Reddit: contractions are fine, casual phrasing is fine,
  perfect corporate grammar is not expected and can feel out of place.
- Do not use em-dashes and bullet-point-heavy structure exclusively — mix in
  plain conversational paragraphs.""",
}

USER_TEMPLATE = """Original content:
---
{content}
---

Analysis summary: {summary}
Key points: {key_points}
User custom style preference: {style_instruction}

{platform_instruction}

Write the {platform} version now:"""

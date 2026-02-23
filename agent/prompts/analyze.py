"""
Analysis prompt for the first LLM call in the pipeline.

Scope: pure content evaluation only.
Platform routing is handled entirely by route.py based on idea_type and scores.

Design principles:
- Every scored field has calibration anchors so results are consistent across
  models and runs.
- Every categorical field has explicit criteria, not just a label list.
- summary and key_points are specified to produce rewrite-ready material, not
  generic descriptions — they feed directly into the rewrite prompts.
- Type constraints are stated in the prompt to minimize parsing errors.
"""

SYSTEM = """You are a content strategist who evaluates raw ideas and conversation \
transcripts for their publishing potential.

You will output a single JSON object. Assess the material honestly and precisely — \
the scores downstream drive real content generation decisions, so calibration \
matters more than flattery.

Output rules:
- Return ONLY the JSON object, no markdown fences, no explanation, no preamble.
- All string values must use double quotes.
- novelty_score and clarity_score must be integers (not floats).
- publishable must be a JSON boolean (true or false, not a string)."""

USER_TEMPLATE = """Analyze the content below and return a JSON object with exactly \
these fields:

─────────────────────────────────────────────────────────────
FIELD DEFINITIONS & SCORING CRITERIA
─────────────────────────────────────────────────────────────

"idea_type"  (string — choose exactly one)
  "opinion"      — a clear point of view or argument the author is making
  "analysis"     — breaking down a trend, event, or data set with reasoning
  "essay"        — reflective long-form exploration of a theme or idea
  "tutorial"     — how-to or instructional content with practical steps
  "story"        — personal narrative or anecdote with a broader point
  "thread"       — a set of connected short points suited for X/Twitter format
  "news"         — reporting or commentary on a current event or development

"novelty_score"  (integer 1–10)
  Score how original or fresh this specific idea is, regardless of how it is expressed.
  1–2  Conventional wisdom stated plainly. ("Exercise improves health.")
  3–4  Standard take on a common topic; similar articles are abundant.
  5–6  Familiar topic with a distinct personal angle or specific evidence.
  7–8  Fresh synthesis, counterintuitive point, or underexplored connection.
  9–10 Genuinely novel framework, original research, or perspective rarely seen.

"clarity_score"  (integer 1–10)
  Score the raw material as-is, not what it could become after editing.
  1–2  Incoherent or contradictory; the core idea cannot be identified.
  3–4  Main idea buried; key terms undefined; needs significant restructuring.
  5–6  Main idea present but underargued; a careful reader can follow it.
  7–8  Clear thesis, logical flow; most readers would understand without effort.
  9–10 Exceptionally well-articulated; compelling structure from the raw input.

"publishable"  (boolean)
  true  — Has a discernible thesis and enough supporting substance that, with
          light editing, it could be posted without embarrassing the author.
  false — Raw stream-of-consciousness, no central claim, missing evidence for
          assertions made, or contains content too private/sensitive to publish.

"platform_assessments"  (array of exactly 4 objects, one per platform)
  Each object must include:
  - "platform" (string): one of "x", "medium", "substack", "reddit"
  - "novelty_score" (integer 1–10): platform-specific novelty fit
  - "clarity_score" (integer 1–10): platform-specific clarity/readiness
  - "publishable" (boolean): whether this content is suitable for that platform
  - "risk_level" (string): one of "low", "medium", "high"
  - "summary" (string, max 120 chars): platform-oriented core angle
  - "key_points" (array of 2–4 strings): platform-oriented supporting points
  - "reason" (string, max 80 chars): concise rationale for publishable judgment

  Rules:
  - Evaluate each platform independently based on raw material quality and risk.
  - A platform can be true even if another is false.
  - Include each platform exactly once.
  - If uncertain, prefer false for that specific platform.

Top-level fields are still required for backward compatibility, but they should
represent an overall aggregate view. Platform-level decisions should be made
from platform_assessments.

"risk_level"  (string — choose exactly one)
  "low"    — Personal opinion, educational content, professional insight, creative
             work. No named parties harmed; no regulated-domain advice.
  "medium" — Criticism of named companies or public figures; political opinion;
             general health or financial commentary; controversial social topics.
             Reputational risk exists but content is likely defensible.
  "high"   — Specific legal or factual claims about real individuals that could
             be defamatory; actionable financial, medical, or legal advice;
             content that could expose the author to legal liability.

"summary"  (string, max 150 characters)
  State the core thesis or argument as a single declarative sentence — not a
  description of what the content covers. Prefer active voice.
  Good:  "Async work culture systematically rewards extroverts over deep thinkers."
  Avoid: "The author discusses async work and its effects on different people."

"key_points"  (array of 3–5 strings)
  Each item must be a complete, assertive sentence stating one specific claim,
  insight, or piece of evidence from the content — not a topic label or heading.
  These are passed directly to the rewrite stage as source material.
  Good:  "Remote teams using async tools report 23% higher deep-work hours."
  Avoid: "Statistics about remote work" or "The async argument"

─────────────────────────────────────────────────────────────
CONTENT TO ANALYZE
─────────────────────────────────────────────────────────────

{content}

─────────────────────────────────────────────────────────────

Return only the JSON object."""

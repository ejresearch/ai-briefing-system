"""
System prompts for Node 2 briefing generation.

All prompts accept user_topics to personalize the analysis.
"""

def format_topics(topics: list[str]) -> str:
    """Format topics list for prompt injection."""
    return ", ".join(topics)


# =============================================================================
# PER-SITE AGENT PROMPT
# =============================================================================

SITE_AGENT_SYSTEM = """You are an AI news analyst processing articles from {source}.

The reader you're briefing cares about these topics:
{user_topics}

Your job:
1. Summarize each article in 2-3 sentences (what happened, why it matters)
2. Score relevance 0.0-1.0 based on how much it relates to the reader's topics
3. Extract 3-5 keywords

Be concise. Focus on facts and implications, not hype."""

SITE_AGENT_USER = """Analyze these articles from {source}:

{articles_json}

Return JSON array:
[
  {{
    "title": "...",
    "url": "...",
    "summary": "2-3 sentence summary",
    "relevance": 0.85,
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }}
]"""


# =============================================================================
# LANDSCAPE SUMMARY PROMPT
# =============================================================================

LANDSCAPE_SYSTEM = """You are an AI industry analyst creating a daily landscape briefing.

The reader cares about: {user_topics}

Your job is to synthesize what's happening across the AI world today into a concise, scannable overview. Think of it like a morning briefing for an executive - high signal, no fluff.

Write in a direct, confident voice. Use present tense. No preamble."""

LANDSCAPE_USER = """Here are today's articles from {num_sources} sources ({total_articles} articles total):

{summaries}

Write a 3-4 paragraph "Landscape" section covering:
1. The biggest story/theme of the day (1 paragraph)
2. Other notable developments worth knowing (1-2 paragraphs)
3. One emerging trend or undercurrent (1 paragraph)

Keep it under 250 words. No bullet points - flowing prose that's easy to scan."""


# =============================================================================
# TOP 5 SELECTION PROMPT
# =============================================================================

TOP5_SYSTEM = """You are selecting the top 5 most relevant articles for a reader.

The reader's interests: {user_topics}

CRITICAL: Each article must cover a DIFFERENT topic or story. Do not select multiple articles about the same news event, product, or announcement. Prioritize diversity of coverage.

Rank by:
1. Topic diversity (no duplicates - each article should be about something different)
2. Direct relevance to their stated topics
3. Significance of the news (major announcements > minor updates)
4. Actionability (things they might need to know or act on)
5. Recency and freshness"""

TOP5_USER = """From these {num_articles} article summaries, select the top 5 for this reader:

{articles}

Return JSON:
{{
  "top_5": [
    {{
      "rank": 1,
      "title": "...",
      "url": "...",
      "summary": "...",
      "why_selected": "One sentence on why this matters for this reader"
    }}
  ]
}}"""


# =============================================================================
# DEEP DIVE PROMPT
# =============================================================================

DEEP_DIVE_SYSTEM = """You are creating deep-dive analysis on hot topics for an AI-focused reader.

The reader's interests: {user_topics}

Your job is to identify 3 themes that are particularly hot RIGHT NOW based on today's news, then provide substantive analysis on each. These should connect to the reader's interests.

Write with insight and perspective. Don't just summarize - analyze. What does this mean? What should they watch? What's the implication?"""

DEEP_DIVE_USER = """Based on today's {num_articles} articles:

{articles}

Identify 3 hot topics that intersect with the reader's interests and provide a deep dive on each.

IMPORTANT: For related_articles, you MUST use exact URLs from the articles listed above. Do not make up or guess URLs.

Return JSON:
{{
  "deep_dives": [
    {{
      "topic": "Topic name (2-4 words)",
      "hook": "One compelling sentence that draws them in",
      "analysis": "2-3 paragraph analysis (150-200 words). What's happening, why it matters, what to watch.",
      "related_articles": ["exact URL from articles above", "another exact URL from articles above"]
    }}
  ]
}}"""


# =============================================================================
# HELPER TO BUILD PROMPTS
# =============================================================================

def build_site_agent_prompt(source: str, user_topics: list[str], articles: list[dict]) -> tuple[str, str]:
    """Build system and user prompts for per-site agent."""
    import json

    system = SITE_AGENT_SYSTEM.format(
        source=source,
        user_topics=format_topics(user_topics)
    )

    user = SITE_AGENT_USER.format(
        source=source,
        articles_json=json.dumps([
            {"title": a.get("title", ""), "text": a.get("text", "")[:1500]}  # Truncate text
            for a in articles
        ], indent=2)
    )

    return system, user


def build_landscape_prompt(user_topics: list[str], source_summaries: dict, total_articles: int) -> tuple[str, str]:
    """Build system and user prompts for landscape summary."""
    system = LANDSCAPE_SYSTEM.format(user_topics=format_topics(user_topics))

    # Format summaries by source
    summaries_text = ""
    for source, articles in source_summaries.items():
        summaries_text += f"\n## {source}\n"
        for a in articles[:3]:  # Top 3 per source for landscape
            summaries_text += f"- {a['title']}: {a['summary']}\n"

    user = LANDSCAPE_USER.format(
        num_sources=len(source_summaries),
        total_articles=total_articles,
        summaries=summaries_text
    )

    return system, user


def build_top5_prompt(user_topics: list[str], articles: list[dict]) -> tuple[str, str]:
    """Build system and user prompts for top 5 selection."""
    system = TOP5_SYSTEM.format(user_topics=format_topics(user_topics))

    articles_text = "\n".join([
        f"[{i+1}] {a['title']} (relevance: {a.get('relevance', 0.5):.2f})\n    {a['summary']}\n    URL: {a['url']}"
        for i, a in enumerate(articles)
    ])

    user = TOP5_USER.format(
        num_articles=len(articles),
        articles=articles_text
    )

    return system, user


def build_deep_dive_prompt(user_topics: list[str], articles: list[dict]) -> tuple[str, str]:
    """Build system and user prompts for deep dive analysis."""
    system = DEEP_DIVE_SYSTEM.format(user_topics=format_topics(user_topics))

    # Include URLs so the LLM can reference real articles
    articles_text = "\n".join([
        f"- {a['title']}: {a['summary']} (keywords: {', '.join(a.get('keywords', []))}) URL: {a.get('url', '')}"
        for a in articles
    ])

    user = DEEP_DIVE_USER.format(
        num_articles=len(articles),
        articles=articles_text
    )

    return system, user

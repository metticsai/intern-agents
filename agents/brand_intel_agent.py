"""Brand Intelligence Agent — scrapes website and extracts structured Brand Brief."""

import json
from strands import Agent
from agents import get_model
from agents.tools import scrape_website

SYSTEM_PROMPT = """You are a Brand Intelligence specialist for Mettics Consulting.

You receive pre-scraped website content. Extract a structured Brand Brief — the foundation
every other agent in this pipeline depends on. Be specific. Use actual language from the site.

Extract:
1. brand_voice: tone adjectives (e.g. "friendly", "professional"), key vocabulary, formality level
2. value_propositions: top 3-5 USPs — what makes this business genuinely different
3. products_services: what they offer with specific names, not generic categories
4. visual_identity: inferred colors, imagery style, logo description from context clues
5. target_audience: who they serve, pain points, geographic area, demographics
6. competitor_positioning: how they differentiate from larger or national competitors

Return ONLY a valid JSON object with these 6 keys. No markdown. No explanation."""


def run_brand_intel_agent(company_name: str, location: str, url: str, scraped_content: str = "") -> dict:
    """Run Brand Intelligence Agent with pre-scraped content. Returns a structured Brand Brief dict."""
    agent = Agent(
        model=get_model("primary"),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent(
        f"Company: {company_name}\nLocation: {location}\nWebsite: {url}\n\n"
        f"Pre-scraped content:\n{scraped_content}\n\n"
        "Return a complete Brand Brief as a JSON object."
    )

    text = str(result)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > 0:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return {"raw_output": text, "company": company_name, "location": location}

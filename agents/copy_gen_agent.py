"""Creative Copy Generation Agent — generates 3 platform-optimized ad variants from Brand Brief."""

import json
from strands import Agent
from agents import get_model

SYSTEM_PROMPT = """You are an expert social media ad copywriter for Mettics Consulting.

Given a Brand Brief, generate 3 distinct ad copy variants per platform.

Techniques you must use:
- Chain-of-thought: For each variant, first decide the angle (urgency / trust / story / humor /
  social proof), then write headline → body → CTA in that frame
- Genuine variation: Each variant must target a different emotional trigger or audience pain point.
  Not synonym swaps — fundamentally different approaches.
- Temperature in creativity: Variant 1 = safe and proven, Variant 2 = emotional/bold,
  Variant 3 = unexpected/pattern interrupt

Platform requirements:
  Meta:     hook ≤125 chars | body 2-3 sentences | cta | hashtags (5-8) | image_prompt
  TikTok:   overlay ≤34 chars | caption ≤150 chars | cta | hashtags (5-8) | image_prompt
  LinkedIn: hook ≤150 chars | body ≤1300 chars, 3-4 sentences | cta | hashtags (5-8) | image_prompt

Style rules:
- Write like a real person, not a brand. First or second person only.
- Hyperlocal: use actual location names, real services, real differentiators from the brand brief.
- Emojis: 2-4 per variant, natural placement only.
- Hashtags: mix local, niche, and broad. Never generic.

Return ONLY a valid JSON object. No markdown. No fences. No explanation."""

PLATFORM_TEMPLATES = {
    "meta": (
        '"meta": {\n'
        '      "variant_1": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_2": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_3": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."}\n'
        '    }'
    ),
    "tiktok": (
        '"tiktok": {\n'
        '      "variant_1": {"overlay": "...", "caption": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_2": {"overlay": "...", "caption": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_3": {"overlay": "...", "caption": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."}\n'
        '    }'
    ),
    "linkedin": (
        '"linkedin": {\n'
        '      "variant_1": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_2": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."},\n'
        '      "variant_3": {"hook": "...", "body": "...", "cta": "...", "hashtags": "...", "image_prompt": "..."}\n'
        '    }'
    ),
}


def _build_structure(company_name: str, location: str, platforms: list) -> str:
    platform_blocks = ",\n    ".join(
        PLATFORM_TEMPLATES[p] for p in platforms if p in PLATFORM_TEMPLATES
    )
    return (
        f'{{\n'
        f'  "client": "{company_name}",\n'
        f'  "location": "{location}",\n'
        f'  "generated_by": "Community Trust Creative Agent",\n'
        f'  "platforms": {{\n    {platform_blocks}\n  }}\n'
        f'}}'
    )


def run_copy_gen_agent(brand_brief: dict, company_name: str, location: str, platforms: list) -> dict:
    """Run the Copy Generation Agent. Returns a campaign dict with 3 variants per platform."""
    agent = Agent(
        model=get_model("primary"),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )

    structure = _build_structure(company_name, location, platforms)

    result = agent(
        f"Company: {company_name}\n"
        f"Location: {location}\n"
        f"Platforms to generate (ONLY these): {', '.join(platforms)}\n\n"
        f"Brand Brief:\n{json.dumps(brand_brief, indent=2)}\n\n"
        f"Generate 3 variants for ONLY the platforms listed above. Return this exact JSON structure:\n"
        f"{structure}"
    )

    text = str(result)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > 0:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError as e:
            raise ValueError(f"Copy Gen returned invalid JSON: {e}\nRaw (last 300): {text[-300:]}")

    raise ValueError(f"Copy Gen returned no JSON. Raw: {text[:500]}")

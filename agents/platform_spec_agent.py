"""Platform Spec Agent — validates character limits and enriches copy with platform-specific hooks."""

import json
from strands import Agent
from agents import get_model
from agents.tools import check_character_limit

SYSTEM_PROMPT = """You are a platform specification validator for Mettics Consulting.

You receive a campaign JSON and must validate every text field against hard character limits.
You also enrich copy with platform-specific best practices.

Hard character limits:
  Meta:     hook ≤125 | body ≤500 | cta ≤25
  TikTok:   overlay ≤34 | caption ≤150 | cta ≤25
  LinkedIn: hook ≤150 | body ≤1300 | cta ≤50

Use the check_character_limit tool for any field you are unsure about.

For each variant, add a "spec_report" field:
{
  "spec_report": {
    "status": "PASS" or "FAIL",
    "violations": ["list of violated fields with counts"],
    "platform_hooks": ["suggestions to improve platform fit"]
  }
}

Platform hook guidance:
- Meta:     emotional triggers, social proof, urgency, local community feel
- TikTok:   trend-native language, UGC style, hook in first 2 seconds, sound-on design
- LinkedIn: professional credibility, specific results/numbers, thought leadership tone

Return the full campaign JSON with spec_report added to each variant. ONLY valid JSON."""


def run_platform_spec_agent(campaign_data: dict) -> dict:
    """Run the Platform Spec Agent. Returns campaign with spec_report on each variant."""
    agent = Agent(
        model=get_model("fast"),
        tools=[check_character_limit],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent(
        f"Validate this campaign against all platform specs. "
        f"Add spec_report to every variant.\n\n"
        f"{json.dumps(campaign_data, indent=2)}"
    )

    text = str(result)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > 0:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # If parsing fails, return original — don't block the pipeline
    return campaign_data

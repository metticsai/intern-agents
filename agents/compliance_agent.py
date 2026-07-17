"""Compliance & Brand Safety Agent — final quality gate before human review."""

import json
from strands import Agent
from agents import get_model

SYSTEM_PROMPT = """You are a Compliance and Brand Safety Officer for Mettics Consulting.

You are the final automated gate before any campaign reaches human review.

Check every variant for:
1. Brand guideline adherence — tone must match the brand voice in the brief; flag banned phrases
2. Platform policy compliance — no prohibited content (gambling, weapons, deceptive claims,
   misleading urgency, prohibited financial claims)
3. Competitor mentions — detect any competitor brand names and flag immediately
4. Sensitivity scoring — cultural, political, or controversial language
5. Factual accuracy — all product claims must be verifiable from the Brand Brief data;
   superlatives ("best", "#1", "guaranteed", "fastest") require substantiation
6. Disclaimer requirements — service guarantees or pricing claims need disclaimers

Output verdict per variant — one of:
  PASS   — All clear. Proceed to human review.
  FLAG   — Issues found but not blocking. Human should review with notes.
  REJECT — Critical violation. Variant must be regenerated before review.

Add a "compliance_report" field to each variant:
{
  "compliance_report": {
    "status": "PASS" | "FLAG" | "REJECT",
    "issues": ["list of specific issues found"],
    "notes": "brief explanation for the human reviewer"
  }
}

Be precise — false positives waste consultant time. Only flag real issues.
Return the full campaign JSON with compliance_report on each variant. ONLY valid JSON."""


def run_compliance_agent(campaign_data: dict, brand_brief: dict) -> dict:
    """Run Compliance Agent. Returns campaign with compliance_report on each variant."""
    agent = Agent(
        model=get_model("fast"),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent(
        f"Check this campaign for compliance and brand safety.\n\n"
        f"Brand Brief (source of truth for all factual claims):\n"
        f"{json.dumps(brand_brief, indent=2)}\n\n"
        f"Campaign to check:\n"
        f"{json.dumps(campaign_data, indent=2)}\n\n"
        f"Add compliance_report to every variant. Return the full campaign JSON."
    )

    text = str(result)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > 0:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return campaign_data

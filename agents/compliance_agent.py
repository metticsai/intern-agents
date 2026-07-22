"""Compliance & Brand Safety Agent — final quality gate before human review."""

import json
import copy
from strands import Agent
from agents import get_model

SYSTEM_PROMPT = """You are a Compliance and Brand Safety Officer for Mettics Consulting.

You receive all ad variants for a campaign and a Brand Brief. Check every variant for:
1. Brand guideline adherence — tone must match the brand voice; flag banned phrases
2. Platform policy compliance — no prohibited content (gambling, weapons, deceptive claims,
   misleading urgency, prohibited financial claims)
3. Competitor mentions — detect any competitor brand names and flag immediately
4. Factual accuracy — all claims must be verifiable from the Brand Brief;
   superlatives ("best", "#1", "guaranteed") require substantiation
5. Disclaimer requirements — service guarantees or pricing claims need disclaimers

Output verdict per variant — one of:
  PASS   — All clear. Proceed to human review.
  FLAG   — Issues found but not blocking. Human should review with notes.
  REJECT — Critical violation. Variant must be regenerated.

Return ONLY this JSON object — nothing else:
{
  "meta": {
    "variant_1": {"status": "PASS", "issues": [], "notes": "brief explanation"},
    "variant_2": {"status": "PASS", "issues": [], "notes": "..."},
    "variant_3": {"status": "FLAG", "issues": ["specific issue"], "notes": "..."}
  },
  "tiktok": { ... },
  "linkedin": { ... }
}

Only include platforms that exist in the campaign. Return ONLY valid JSON. No markdown."""


def run_compliance_agent(campaign_data: dict, brand_brief: dict) -> dict:
    """Run one Haiku compliance check across all variants. Merges results in Python."""
    result = copy.deepcopy(campaign_data)

    agent = Agent(
        model=get_model("fast"),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )

    response = agent(
        f"Check this entire campaign for compliance and brand safety.\n\n"
        f"Brand Brief (source of truth for all factual claims):\n"
        f"{json.dumps(brand_brief, indent=2)}\n\n"
        f"Campaign variants to check:\n"
        f"{json.dumps(campaign_data.get('platforms', {}), indent=2)}\n\n"
        f"Return ONLY the compliance_reports JSON object keyed by platform → variant."
    )

    text = str(response)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        print("  ⚠️  Compliance agent returned no JSON — skipping compliance check")
        return result

    try:
        reports = json.loads(text[start:end])
    except json.JSONDecodeError:
        print("  ⚠️  Compliance report JSON invalid — skipping compliance check")
        return result

    for platform_key, variants in reports.items():
        if platform_key not in result.get("platforms", {}):
            continue
        if not isinstance(variants, dict):
            continue
        for variant_key, report in variants.items():
            if variant_key not in result["platforms"][platform_key]:
                continue
            result["platforms"][platform_key][variant_key]["compliance_report"] = report
            status = report.get("status", "?")
            icon = "✅" if status == "PASS" else ("⚠️ " if status == "FLAG" else "❌")
            print(f"  {icon} {platform_key}/{variant_key}: {status}")

    return result

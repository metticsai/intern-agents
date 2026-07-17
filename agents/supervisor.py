"""Supervisor Agent — orchestrates the full campaign pipeline via Strands SDK."""

import json
import requests
from bs4 import BeautifulSoup
from strands import Agent, tool
from agents import get_model
from agents.brand_intel_agent import run_brand_intel_agent
from agents.copy_gen_agent import run_copy_gen_agent
from agents.platform_spec_agent import run_platform_spec_agent
from agents.compliance_agent import run_compliance_agent

# Shared campaign state across the session
campaign_state: dict = {}

PLATFORM_SPECS = {
    "meta":     {"name": "Meta / Instagram", "limits": {"hook": 125}},
    "tiktok":   {"name": "TikTok",           "limits": {"overlay": 34, "caption": 150}},
    "linkedin": {"name": "LinkedIn",          "limits": {"body": 1300}},
}


# ── HITL helpers ─────────────────────────────────────────────────────────────

def _print_variant(platform_key: str, variant_num: int, variant_data: dict) -> None:
    spec = PLATFORM_SPECS[platform_key]
    print(f"\n  VARIANT {variant_num}")
    print("  " + "─" * 56)

    compliance = variant_data.get("compliance_report", {})
    if compliance:
        status = compliance.get("status", "UNKNOWN")
        colour = "✅" if status == "PASS" else ("⚠️ " if status == "FLAG" else "❌")
        print(f"  COMPLIANCE: {colour} {status}")
        for issue in compliance.get("issues", []):
            print(f"    • {issue}")

    spec_rep = variant_data.get("spec_report", {})
    if spec_rep and spec_rep.get("violations"):
        print(f"  SPEC VIOLATIONS: {', '.join(spec_rep['violations'])}")

    for field, value in variant_data.items():
        if field in ("image_prompt", "compliance_report", "spec_report"):
            continue
        if not isinstance(value, str):
            continue
        limit = spec["limits"].get(field)
        if limit:
            flag = " ⚠️  OVER" if len(value) > limit else " ✅"
            print(f"  {field.upper()} ({len(value)}/{limit}{flag}): {value}")
        else:
            print(f"  {field.upper()}: {value}")


# ── Supervisor tools (each wraps one agent or HITL gate) ─────────────────────

@tool
def search_and_confirm_url(company_name: str, location: str) -> str:
    """Search DuckDuckGo for the business website and present results to the user for confirmation.

    This is HITL Gate 1 — Pre-Scrape Confirmation. Returns the confirmed URL string.
    """
    print(f"\n🔍 Searching for {company_name} in {location}...")
    query = f"{company_name} {location} official website"
    url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    results = [link.get_text().strip() for link in soup.select(".result__url")[:3]]

    if not results:
        return "ERROR: No search results found."

    print("\n  Top results:")
    for i, r in enumerate(results):
        print(f"  {i + 1}. {r}")

    choice = input("\n  Which URL to scrape? (1/2/3): ").strip()
    try:
        confirmed_url = f"https://{results[int(choice) - 1]}"
    except (ValueError, IndexError):
        confirmed_url = f"https://{results[0]}"

    print(f"  ✅ Confirmed: {confirmed_url}")
    campaign_state["url"] = confirmed_url
    return confirmed_url


@tool
def extract_brand_intelligence(company_name: str, location: str, url: str) -> str:
    """Run the Brand Intelligence Agent to scrape the website and extract a structured Brand Brief.

    This is HITL Gate 2 — Brand Identity Approval. Returns the approved Brand Brief as JSON string.
    """
    print(f"\n🧠 Brand Intelligence Agent running...")
    brief = run_brand_intel_agent(company_name, location, url)
    campaign_state["brand_brief"] = brief

    print("\n" + "=" * 62)
    print("  BRAND BRIEF — REVIEW AND APPROVE BEFORE GENERATION")
    print("=" * 62)
    print(json.dumps(brief, indent=2))

    confirm = input("\n  Approve this brand brief? [Y to approve / N to add corrections]: ").strip().upper()
    if confirm != "Y":
        correction = input("  Enter corrections: ").strip()
        if correction:
            brief["human_corrections"] = correction
            print("  ✅ Corrections noted — proceeding with updated brief")
    else:
        print("  ✅ Brand brief approved")

    campaign_state["brand_brief"] = brief
    return json.dumps(brief)


@tool
def generate_campaign_copy(company_name: str, location: str, brand_brief_json: str, platforms: str) -> str:
    """Run the Creative Copy Generation Agent to produce 3 variants per platform.

    Inputs: company_name, location, brand_brief as JSON string, comma-separated platform list.
    Returns campaign JSON string.
    """
    print(f"\n✍️  Copy Generation Agent running...")
    brief = json.loads(brand_brief_json)
    platform_list = [p.strip() for p in platforms.split(",")]
    campaign = run_copy_gen_agent(brief, company_name, location, platform_list)
    campaign_state["campaign"] = campaign
    print(f"  ✅ Generated {len(platform_list)} platforms × 3 variants")
    return json.dumps(campaign)


@tool
def validate_platform_specs(campaign_json: str) -> str:
    """Run the Platform Spec Agent to validate character limits and add platform-specific hooks.

    Returns validated campaign JSON string with spec_report on each variant.
    """
    print(f"\n📋 Platform Spec Agent running...")
    campaign = json.loads(campaign_json)
    validated = run_platform_spec_agent(campaign)
    campaign_state["campaign"] = validated
    print(f"  ✅ Platform specs validated")
    return json.dumps(validated)


@tool
def run_compliance_check(campaign_json: str, brand_brief_json: str) -> str:
    """Run the Compliance & Brand Safety Agent to check all variants before human review.

    Returns campaign JSON string with compliance_report on each variant (PASS/FLAG/REJECT).
    """
    print(f"\n🛡️  Compliance Agent running...")
    campaign = json.loads(campaign_json)
    brief = json.loads(brand_brief_json)
    checked = run_compliance_agent(campaign, brief)
    campaign_state["campaign"] = checked

    # Print a quick summary of compliance results
    for platform_key, platform_data in checked.get("platforms", {}).items():
        for vkey, vdata in platform_data.items():
            if not vkey.startswith("variant_"):
                continue
            report = vdata.get("compliance_report", {})
            status = report.get("status", "UNKNOWN")
            icon = "✅" if status == "PASS" else ("⚠️ " if status == "FLAG" else "❌")
            print(f"  {icon} {platform_key}/{vkey}: {status}")

    return json.dumps(checked)


@tool
def present_for_human_review(campaign_json: str) -> str:
    """Present all campaign variants to the user for approval.

    This is HITL Gate 3 — Creative Review Gate. User picks one variant per platform
    or rejects the entire campaign. Returns flattened approved campaign JSON string.
    """
    campaign = json.loads(campaign_json)
    selected: dict = {}

    for platform_key, spec in PLATFORM_SPECS.items():
        if platform_key not in campaign.get("platforms", {}):
            continue

        platform_data = campaign["platforms"][platform_key]
        variants = {k: v for k, v in platform_data.items() if k.startswith("variant_")}

        print("\n" + "=" * 62)
        print(f"  {spec['name'].upper()} — PICK A VARIANT")
        print("=" * 62)

        for i, (vkey, vdata) in enumerate(variants.items(), 1):
            _print_variant(platform_key, i, vdata)

        while True:
            raw = input(
                f"\n  Which variant for {spec['name']}? (1-{len(variants)}) or [R] to reject all: "
            ).strip().upper()

            if raw == "R":
                print("❌ Campaign rejected — no files saved")
                campaign_state["rejected"] = True
                return json.dumps({"rejected": True})

            try:
                idx = int(raw) - 1
                vkey = list(variants.keys())[idx]
                chosen = variants[vkey]

                # Warn if any field is over limit
                over = [
                    f"{field} ({len(chosen.get(field, ''))}/{limit})"
                    for field, limit in spec["limits"].items()
                    if isinstance(chosen.get(field), str) and len(chosen[field]) > limit
                ]
                if over:
                    print(f"  ⚠️  Over limit: {', '.join(over)}")
                    confirm = input("  Use anyway? [Y/N]: ").strip().upper()
                    if confirm != "Y":
                        print("  Pick a different variant.")
                        continue

                selected[platform_key] = chosen
                print(f"  ✅ Selected variant {raw} for {spec['name']}")
                break
            except (ValueError, IndexError):
                print("  Invalid — try again")

    # Flatten selected variants back into campaign
    for platform_key, variant_data in selected.items():
        campaign["platforms"][platform_key] = variant_data

    campaign_state["campaign"] = campaign
    print("\n✅ All platforms approved — ready for image generation and save")
    return json.dumps(campaign)


# ── Supervisor Agent definition ───────────────────────────────────────────────

SUPERVISOR_PROMPT = """You are the Campaign Orchestration Supervisor for Mettics Consulting.

You orchestrate a full ad campaign pipeline using specialist agents.
Follow these steps IN ORDER — never skip or reorder them:

1. search_and_confirm_url(company_name, location)
   → Finds the business website, user confirms (HITL Gate 1)

2. extract_brand_intelligence(company_name, location, url)
   → Brand Intel Agent scrapes site and extracts Brand Brief, user approves (HITL Gate 2)

3. generate_campaign_copy(company_name, location, brand_brief_json, platforms)
   → Copy Gen Agent produces 3 variants per platform from the brand brief

4. validate_platform_specs(campaign_json)
   → Platform Spec Agent checks character limits and adds platform hooks

5. run_compliance_check(campaign_json, brand_brief_json)
   → Compliance Agent checks brand safety — any REJECT means that variant is flagged for human

6. present_for_human_review(campaign_json)
   → User reviews all variants and picks one per platform (HITL Gate 3)

After step 6, report what was approved and that files are ready to save.

RULES:
- Never skip the compliance check or human review gate
- Never auto-publish any creative without human approval
- If any step returns an error, report clearly what failed and stop"""


def create_supervisor() -> Agent:
    """Create and return the configured Supervisor Agent."""
    return Agent(
        model=get_model("fast"),
        tools=[
            search_and_confirm_url,
            extract_brand_intelligence,
            generate_campaign_copy,
            validate_platform_specs,
            run_compliance_check,
            present_for_human_review,
        ],
        system_prompt=SUPERVISOR_PROMPT,
    )

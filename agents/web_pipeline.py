"""Web Supervisor — orchestrates the Strands specialist agents for the web app.

The CLI supervisor (agents/supervisor.py) drives the pipeline with an LLM and blocking
input() HITL gates. In the web app the human-in-the-loop gates live in the browser
(URL confirmation, variant review), so orchestration here is a deterministic, code-based
supervisor. Each *creative* step is still a real Strands LLM agent:

    Brand Intelligence Agent (Sonnet)  → structured Brand Brief
    Copy Generation Agent    (Sonnet)  → 3 strategic variants (tuned prompt preserved)
    Platform Spec Agent      (Python)  → character-limit + CTA validation report
    Compliance Agent         (Haiku)   → PASS / FLAG / REJECT per variant

Returns (campaign_dict, brand_brief). Raises on hard failure so the caller can fall
back to the hybrid single-call pipeline — the web app must never break mid-demo.
"""

import json

from agents.brand_intel_agent import run_brand_intel_agent
from agents.copy_gen_agent import run_copy_gen_rich
from agents.platform_spec_agent import run_platform_spec_agent
from agents.compliance_agent import run_compliance_agent


def _scraped_to_text(scraped: dict) -> str:
    """Flatten the scraped site dict into the text blob the Brand Intel Agent reads."""
    parts = [f"URL: {scraped.get('url', '')}"]
    if scraped.get("h1"):
        parts.append("H1: " + " | ".join(scraped["h1"]))
    if scraped.get("h2"):
        parts.append("H2: " + " | ".join(scraped["h2"][:8]))
    signals = scraped.get("brand_signals", {})
    if signals:
        parts.append("BRAND SIGNALS: " + json.dumps(signals))
    parts.append("CONTENT:\n" + "\n".join(scraped.get("paragraphs", [])[:15]))
    for name, page in scraped.get("subpages", {}).items():
        combined = page.get("h1", []) + page.get("h2", []) + page.get("paragraphs", [])
        if combined:
            parts.append(f"[{name.upper()}]\n" + "\n".join(combined[:6]))
    return "\n\n".join(parts)


def run_agent_pipeline(scraped, company_name, location, config, feedback=""):
    """Code-based supervisor: run the four specialist agents in sequence.

    Returns (campaign_dict, brand_brief_dict). Raises on unrecoverable failure.
    """
    # Import here to avoid any import-order coupling with main.py
    from main import _build_campaign_prompt, validate_output

    platforms = config.get("platforms", ["meta"])

    # ── Agent 1 — Brand Intelligence (Strands, Sonnet) ─────────────────────────
    print("\n🧠 [1/4] Brand Intelligence Agent...")
    scraped_text = _scraped_to_text(scraped)
    brand_brief = run_brand_intel_agent(company_name, location, scraped.get("url", ""), scraped_text)
    print("  ✅ Brand brief extracted")

    # ── Agent 2 — Copy Generation (Strands, Sonnet, tuned prompt + brief) ──────
    print("✍️  [2/4] Copy Generation Agent...")
    system_prompt, user_message, industry = _build_campaign_prompt(
        scraped, company_name, location, config, feedback, brand_brief=brand_brief)
    raw = run_copy_gen_rich(system_prompt, user_message)
    is_valid, campaign, err = validate_output(raw)
    if not is_valid or not campaign:
        raise ValueError(f"Copy Generation Agent produced unusable output: {err}")
    # Keep only configured platforms
    campaign["platforms"] = {k: v for k, v in campaign["platforms"].items() if k in platforms}
    print(f"  ✅ {len(campaign['platforms'])} platform(s) × 3 variants")

    # ── Agent 3 — Platform Spec validation (Python) ────────────────────────────
    print("📋 [3/4] Platform Spec Agent...")
    campaign = run_platform_spec_agent(campaign)

    # ── Agent 4 — Compliance & Brand Safety (Strands, Haiku) ───────────────────
    print("🛡️  [4/4] Compliance Agent...")
    try:
        campaign = run_compliance_agent(campaign, brand_brief)
    except Exception as e:
        print(f"  ⚠️  Compliance check skipped: {e}")

    # Expose each variant's compliance verdict in the shape the frontend reads
    # (variant.compliance.status), defaulting to PASS when the agent didn't flag it.
    for pdata in campaign.get("platforms", {}).values():
        for vkey, vdata in pdata.items():
            if vkey.startswith("variant_") and isinstance(vdata, dict):
                report = vdata.get("compliance_report") or {"status": "PASS", "issues": [], "notes": ""}
                vdata["compliance"] = {
                    "status": str(report.get("status", "PASS")).lower(),
                    "issues": report.get("issues", []),
                    "notes": report.get("notes", ""),
                }

    return campaign, brand_brief

"""Platform Spec Agent — validates character limits. Pure Python, no API calls needed."""

import copy

LIMITS = {
    "meta":     {"hook": 125, "body": 500},
    "tiktok":   {"overlay": 34, "caption": 150, "cta": 30},
    "linkedin": {"hook": 150, "body": 1300, "cta": 50},
}

META_CTA_OPTIONS = {
    "Book Now", "Call Now", "Get Quote", "Learn More",
    "Contact Us", "Sign Up", "Shop Now", "Send Message",
}

PLATFORM_HOOKS = {
    "meta":     "Use emotional triggers, social proof, and local community feel. Hook must stop the scroll in under 2 seconds.",
    "tiktok":   "Write like a real person, not a brand. Overlay must work without sound. Hook in first frame.",
    "linkedin": "Lead with professional credibility. Use specific numbers and results. Thought leadership tone.",
}


def run_platform_spec_agent(campaign_data: dict) -> dict:
    """Validate character limits in pure Python. No API calls."""
    result = copy.deepcopy(campaign_data)

    for platform_key, platform_data in campaign_data.get("platforms", {}).items():
        limits = LIMITS.get(platform_key, {})
        hook = PLATFORM_HOOKS.get(platform_key, "")

        for variant_key, variant_data in platform_data.items():
            if not variant_key.startswith("variant_"):
                continue

            violations = []
            for field, limit in limits.items():
                value = variant_data.get(field, "")
                if isinstance(value, str) and len(value) > limit:
                    violations.append(f"{field}: {len(value)}/{limit} chars")

            if platform_key == "meta":
                cta = variant_data.get("cta", "")
                if cta not in META_CTA_OPTIONS:
                    violations.append(f"cta: '{cta}' not a valid Meta button — must be one of: {', '.join(sorted(META_CTA_OPTIONS))}")

            status = "FAIL" if violations else "PASS"
            result["platforms"][platform_key][variant_key]["spec_report"] = {
                "status": status,
                "violations": violations,
                "platform_hooks": [hook] if hook else [],
            }
            icon = "✅" if status == "PASS" else "⚠️ "
            print(f"  {icon} {platform_key}/{variant_key}: {status}" + (f" — {', '.join(violations)}" if violations else ""))

    return result

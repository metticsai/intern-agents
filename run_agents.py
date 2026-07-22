#!/usr/bin/env python3.11
"""
run_agents.py — Strands multi-agent entry point.

Architecture:
  User → Supervisor (Strands/Haiku) → Brand Intel Agent (Sonnet)
                                     → Copy Gen Agent (Sonnet)
                                     → Platform Spec Agent (Haiku)
                                     → Compliance Agent (Haiku)
                                     → HITL Review Gates × 3
                                     → Save Output
"""

import os
import json
import time
import warnings
warnings.filterwarnings("ignore")
from dotenv import load_dotenv
load_dotenv()

from agents.supervisor import create_supervisor, campaign_state
from main import save_output, get_output_dir


def main():
    print("\n" + "=" * 62)
    print("  COMMUNITY TRUST CREATIVE AGENT")
    print("  Mettics Consulting — Multi-Agent Pipeline (Strands SDK)")
    print("=" * 62)
    print("  Supervisor   → Claude Haiku 4.5  (orchestration)")
    print("  Brand Intel  → Claude Sonnet 4.6 (extraction)")
    print("  Copy Gen     → Claude Sonnet 4.6 (generation)")
    print("  Platform Spec→ Claude Haiku 4.5  (validation)")
    print("  Compliance   → Claude Haiku 4.5  (safety check)")
    print("=" * 62 + "\n")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not found in .env — add credits to activate")
        print("   Switch to Gemini provider in config.json for text-only mode.")
        return

    config = json.load(open("config.json"))
    platforms = ", ".join(config["platforms"])

    company_name = input("Enter company name: ").strip()
    location = input("Enter location (e.g. Brambleton VA): ").strip()

    start_time = time.time()

    supervisor = create_supervisor()

    supervisor(
        f"Run a complete ad campaign for:\n"
        f"Company: {company_name}\n"
        f"Location: {location}\n"
        f"Target Platforms: {platforms}\n\n"
        f"Follow all 6 pipeline steps in order."
    )

    # Save output if campaign was approved
    campaign = campaign_state.get("campaign", {})
    if not isinstance(campaign.get("platforms"), dict) or not campaign["platforms"]:
        print("\n❌ Campaign data malformed — 'platforms' key missing or empty.")
        print(f"   Keys found: {list(campaign.keys())}")
        print("   The agents ran but the output structure couldn't be parsed correctly.")
        print("   Try running again — this is usually a one-off JSON formatting issue.")
        return

    if campaign_state.get("campaign") and not campaign_state.get("rejected"):
        output_dir = get_output_dir(company_name)

        if config["image_generation"].get("enabled", False):
            import requests as req
            import fal_client
            images_dir = f"{output_dir}/images"
            os.makedirs(images_dir, exist_ok=True)
            print(f"\n🎨 Generating images with {config['image_generation']['provider']}...")
            for platform in ["meta", "tiktok", "linkedin"]:
                prompt = campaign_state["campaign"]["platforms"][platform].get("image_prompt", "")
                image_path = f"{images_dir}/{platform}.jpg"
                try:
                    result = fal_client.run(
                        f"fal-ai/{config['image_generation']['model']}",
                        arguments={"prompt": prompt, "image_size": "square_hd", "num_images": 1},
                    )
                    image_url = result["images"][0]["url"]
                    r = req.get(image_url, timeout=60)
                    r.raise_for_status()
                    with open(image_path, "wb") as f:
                        f.write(r.content)
                    campaign_state["campaign"]["platforms"][platform]["image_url"] = image_url
                    campaign_state["campaign"]["platforms"][platform]["image_path"] = image_path
                    print(f"  ✅ {platform}: {image_path}")
                except Exception as e:
                    print(f"  ⚠️  {platform} image failed: {e}")
        else:
            print("\n🎨 Image generation disabled (set enabled: true in config.json to activate)")

        save_output(campaign_state["campaign"], output_dir)
        elapsed = time.time() - start_time
        images_generated = sum(
            1 for p in ["meta", "tiktok", "linkedin"]
            if campaign_state["campaign"]["platforms"].get(p, {}).get("image_path")
        )
        cost = images_generated * config["image_generation"]["cost_per_image"]

        print(f"\n" + "=" * 62)
        print(f"  CAMPAIGN COMPLETE — {company_name.upper()}")
        print("=" * 62)
        print(f"  Time:   {elapsed:.0f} seconds")
        print(f"  Images: {images_generated}/3 generated")
        print(f"  Cost:   ~${cost:.3f} (image generation only)")
        print(f"  Output: {output_dir}/")
        print("=" * 62 + "\n")


if __name__ == "__main__":
    main()

import os
import json
import time
import warnings
import requests
warnings.filterwarnings("ignore")
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

def get_output_dir(company_name):
    clean_name = company_name.lower().strip().replace(" ", "_")
    version = 1
    while os.path.exists(f"output/{clean_name}_v{version}"):
        version += 1
    return f"output/{clean_name}_v{version}"

def search_business(company_name, location):
    print(f"\n🔍 Searching for {company_name} in {location}...")
    query = f"{company_name} {location} official website"
    url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for link in soup.select(".result__url")[:3]:
        results.append(link.get_text().strip())
    print(f"✅ Found {len(results)} results")
    return results

def _scrape_page(url, headers):
    """Scrape a single page and return its text content."""
    try:
        response = requests.get(url, headers=headers, timeout=4)
        soup = BeautifulSoup(response.text, "html.parser")
        h1s = [t.get_text().strip() for t in soup.find_all("h1") if t.get_text().strip()]
        h2s = [t.get_text().strip() for t in soup.find_all("h2") if t.get_text().strip()]
        paragraphs = [t.get_text().strip() for t in soup.find_all("p") if len(t.get_text().strip()) > 30]
        return {"url": url, "h1": h1s, "h2": h2s, "paragraphs": paragraphs[:15], "soup": soup}
    except Exception:
        return None

def _find_subpages(base_url, soup):
    """Find About, Services, and Reviews subpage links from the homepage."""
    from urllib.parse import urljoin, urlparse
    base_domain = urlparse(base_url).netloc
    keywords = ["about", "service", "review", "testimonial", "team", "contact"]
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if any(k in href or k in text for k in keywords):
            full = urljoin(base_url, a["href"])
            if urlparse(full).netloc == base_domain and full not in found and full != base_url:
                found.append(full)
    return found[:4]

def _detect_industry(scraped_data):
    """Classify business type from scraped content. Returns (industry_key, image_style_hint)."""
    all_text = " ".join(
        scraped_data.get("paragraphs", []) +
        scraped_data.get("h1", []) +
        scraped_data.get("h2", [])
    ).lower()

    if any(k in all_text for k in ["plumb", "hvac", "heat", "cool", "electric", "roof", "landscap", "pest", "handyman", "drain", "sewer", "gutter"]):
        return "home_services", "Technician actively working on-site, natural daylight, tool belt visible, real house setting. NOT posed stock."
    if any(k in all_text for k in ["coffee", "cafe", "café", "restaurant", "food", "bar", "bakery", "pizza", "sushi", "taco", "brew", "bistro", "diner", "eatery"]):
        return "food_beverage", "Hands cupping a steaming drink or holding signature item. Warm golden-hour window light. Overhead flat lay with natural props. Moody or bright to match brand."
    if any(k in all_text for k in ["salon", "spa", "hair", "nail", "massage", "beauty", "barber", "skin", "facial", "wellness", "wax"]):
        return "health_beauty", "Client mid-service or just-finished, soft natural window light, serene and relaxed, clean minimalist salon background."
    if any(k in all_text for k in ["gym", "fitness", "yoga", "personal train", "crossfit", "sport", "workout", "pilates"]):
        return "health_fitness", "Person mid-exercise with visible effort and determination, dramatic gym lighting or bright outdoor setting, dynamic motion."
    if any(k in all_text for k in ["law", "attorney", "legal", "accounting", "finance", "consult", "insurance", "real estate", "mortgage", "advisor"]):
        return "professional_services", "Two people in genuine conversation or reviewing results on a laptop, bright clean office, confident and credible."
    if any(k in all_text for k in ["shop", "store", "retail", "boutique", "clothing", "jewel", "gift", "apparel"]):
        return "retail", "Person using or wearing the product in a natural lifestyle context, clean daylight, aspirational but candid."
    return "general_business", "Real people in the actual business setting, natural light, authentic candid moment — not staged or stock."


def _extract_brand_signals(all_text):
    """Pull specific brand signals from combined page text using pattern matching."""
    import re
    signals = {}

    # Review count — "196 reviews", "4.9 stars", "200+ reviews"
    review_match = re.search(r'(\d[\d,]*\+?)\s*(five[- ]star|5[- ]star|★+)?\s*reviews?', all_text, re.I)
    if review_match:
        signals["review_count"] = review_match.group(0).strip()

    # Star rating — "4.9 out of 5", "4.8/5"
    rating_match = re.search(r'(\d\.\d)\s*(out of 5|\/5|stars?)', all_text, re.I)
    if rating_match:
        signals["rating"] = rating_match.group(0).strip()

    # Years in business — "since 2008", "15 years", "family owned since"
    years_match = re.search(r'(since \d{4}|\d{1,2}\+?\s*years?\s*(in business|of (experience|service)))', all_text, re.I)
    if years_match:
        signals["years_in_business"] = years_match.group(0).strip()

    # Certifications — licensed, insured, bonded, certified
    certs = re.findall(r'\b(licensed|insured|bonded|certified|accredited|BBB|background.checked)\b', all_text, re.I)
    if certs:
        signals["certifications"] = list(dict.fromkeys([c.lower() for c in certs]))

    # Team/people names — "Our team", mentions of names
    names = re.findall(r'\b(Max|Ryan|John|Mike|Chris|David|Sarah|Alex|Maria)\b', all_text)
    if names:
        signals["team_names"] = list(dict.fromkeys(names))[:3]

    # Service area — "serving X, Y, and Z"
    area_match = re.search(r'serv(?:ing|e[sd]?)\s+([\w\s,]+(?:VA|MD|DC|Virginia|Maryland))', all_text, re.I)
    if area_match:
        signals["service_area"] = area_match.group(0).strip()

    # Guarantee / same-day
    if re.search(r'same.day', all_text, re.I):
        signals["same_day_service"] = True
    if re.search(r'guarantee|satisfaction guaranteed', all_text, re.I):
        signals["guarantee"] = True
    if re.search(r'24.7|24 hours|emergency', all_text, re.I):
        signals["emergency_service"] = True

    return signals

def scrape_website(url):
    print(f"\n🌐 Scraping {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}

    # Scrape homepage
    home = _scrape_page(url, headers)
    if not home:
        return {"url": url, "h1": [], "h2": [], "paragraphs": [], "images": [], "brand_signals": {}, "subpages": {}}

    # Find and scrape subpages (About, Services, Reviews) in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    subpage_urls = _find_subpages(url, home["soup"])
    subpages = {}

    def _fetch_subpage(sub_url):
        label = sub_url.rstrip("/").split("/")[-1] or "page"
        result = _scrape_page(sub_url, headers)
        return label, result

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_fetch_subpage, u): u for u in subpage_urls}
        for future in as_completed(futures):
            label, result = future.result()
            if result:
                subpages[label] = result
                print(f"  + Scraped subpage: {label}")

    # Combine all text for signal extraction
    all_paragraphs = home["paragraphs"][:]
    for page_data in subpages.values():
        all_paragraphs += page_data["paragraphs"]
    all_text = " ".join(all_paragraphs)

    brand_signals = _extract_brand_signals(all_text)

    # Collect hero/product images from homepage
    images = []
    for tag in home["soup"].find_all("img"):
        src = tag.get("src", "")
        if src and not src.endswith(".svg") and ("hero" in src.lower() or "logo" in src.lower()):
            images.append(src)

    scraped = {
        "url": url,
        "h1": home["h1"],
        "h2": home["h2"],
        "paragraphs": all_paragraphs[:20],
        "images": images[:5],
        "brand_signals": brand_signals,
        "subpages": {k: {"h1": v["h1"], "h2": v["h2"], "paragraphs": v["paragraphs"]} for k, v in subpages.items()}
    }

    total_paragraphs = len(all_paragraphs)
    print(f"✅ Scraped {total_paragraphs} paragraphs across {1 + len(subpages)} pages")
    if brand_signals:
        print(f"  Brand signals found: {', '.join(brand_signals.keys())}")
    return scraped

def validate_scrape(scraped_data, company_name, location):
    print(f"\n✔️  Validating scrape...")
    total_content = len(scraped_data["h1"]) + len(scraped_data["paragraphs"])

    # Detect JS-rendered sites — lots of script tags, almost no readable text
    is_js_rendered = total_content < 3

    if is_js_rendered:
        print(f"⚠️  Very little content found — site may be JavaScript-rendered (React, Squarespace, Wix)")
        print(f"   This happens when the site builds its content in the browser, not the HTML.")
        print(f"\n  Options:")
        print(f"  1. Try a different URL (About page, Services page, Google Business listing)")
        print(f"  2. Paste the business description manually and continue")
        print(f"  3. Exit and check the URL manually")
        choice = input("\n  Choose (1/2/3): ").strip()

        if choice == "1":
            new_url = input("  Enter new URL: ").strip()
            if not new_url.startswith("http"):
                new_url = f"https://{new_url}"
            new_data = scrape_website(new_url)
            scraped_data.update(new_data)
            return validate_scrape(scraped_data, company_name, location)

        elif choice == "2":
            print(f"\n  Paste a description of {company_name} — services, location, what makes them different.")
            print(f"  Press Enter twice when done.\n")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            manual_text = " ".join(lines).strip()
            if manual_text:
                scraped_data["paragraphs"] = [manual_text]
                scraped_data["h1"] = [company_name]
                scraped_data["manual_input"] = True
                print(f"  ✅ Manual content accepted — continuing with generation")
                return True
            else:
                print("  ❌ No content entered. Exiting.")
                return False

        else:
            print("  ❌ Exiting — please check the URL manually.")
            return False

    print(f"✅ Scrape validated — content looks good")
    return True

def generate_campaign(scraped_data, company_name, location, config, feedback=""):
    provider = config["ai_generation"]["provider"]
    model = config["ai_generation"]["model"]
    print(f"\n🤖 Sending to {provider} ({model}) for campaign generation...")
    signals = scraped_data.get("brand_signals", {})
    signals_text = "\n".join(f"  - {k}: {v}" for k, v in signals.items()) if signals else "  None extracted"

    subpages_text = ""
    for page_name, page_data in scraped_data.get("subpages", {}).items():
        combined = page_data.get("h1", []) + page_data.get("h2", []) + page_data.get("paragraphs", [])
        if combined:
            subpages_text += f"\n[{page_name.upper()} PAGE]\n" + "\n".join(combined[:8]) + "\n"

    industry, image_style = _detect_industry(scraped_data)
    platforms_to_generate = config.get("platforms", ["meta"])
    print(f"  Industry detected: {industry} | Platforms: {', '.join(platforms_to_generate)}")

    context = f"""
Company: {company_name}
Location: {location}
Website: {scraped_data['url']}
Platforms to generate: {', '.join(platforms_to_generate)}
Business type: {industry}
Image style guidance: {image_style}

BRAND SIGNALS (use these as hard facts in the copy):
{signals_text}

HOMEPAGE HEADINGS:
{chr(10).join(scraped_data['h1'] + scraped_data['h2'])}

HOMEPAGE CONTENT:
{chr(10).join(scraped_data['paragraphs'][:12])}
{subpages_text}
"""
    system_prompt = open("system_prompt.txt").read()
    feedback_line = f"\n\nIMPORTANT FEEDBACK FROM REVIEWER — apply this to all 3 variants: {feedback}" if feedback else ""
    full_prompt = f"{system_prompt}\n\nGenerate a complete campaign for {company_name} in {location}. Here is all the data scraped from their website:\n\n{context}{feedback_line}\n\nReturn ONLY a valid JSON object. No markdown, no explanation, just the JSON."

    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(max_output_tokens=8192)
        )
        print(f"✅ Gemini generated campaign ({len(response.text)} chars)")
        return response.text

    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": full_prompt}]
        )
        print(f"✅ Claude generated campaign")
        return message.content[0].text

    else:
        raise ValueError(f"Unknown AI provider: {provider}")

def validate_output(campaign_json):
    print(f"\n✔️  Validating campaign output...")
    errors = []
    try:
        # Extract the JSON object regardless of what surrounds it
        start = campaign_json.find("{")
        end = campaign_json.rfind("}") + 1
        if start == -1 or end == 0:
            raise json.JSONDecodeError("No JSON object found", campaign_json, 0)
        clean = campaign_json[start:end]
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"❌ Output is not valid JSON: {e}")
        print(f"   Response length: {len(campaign_json)} chars")
        print(f"   Last 300 chars of response:")
        print(campaign_json[-300:])
        return False, None
    required_platforms = list(data.get("platforms", {}).keys())
    if not required_platforms:
        errors.append("No platforms found in output")
        for error in errors:
            print(f"❌ {error}")
        return False, None
    required_fields = {
        "meta": ["headline", "hook", "body", "cta", "hashtags", "image_prompt"],
        "tiktok": ["overlay", "caption", "cta", "hashtags", "image_prompt"],
        "linkedin": ["hook", "body", "cta", "hashtags", "image_prompt"],
    }
    for platform in required_platforms:
        if platform not in data.get("platforms", {}):
            continue
        platform_data = data["platforms"][platform]
        variants = [v for v in ["variant_1", "variant_2", "variant_3"] if v in platform_data]
        if not variants:
            errors.append(f"No variants found in {platform}")
            continue
        for variant in variants:
            for field in required_fields[platform]:
                if field not in platform_data[variant]:
                    errors.append(f"Missing field '{field}' in {platform}/{variant}")
    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False, None
    print(f"✅ Campaign output validated — all fields present")
    return True, data

def human_review_gate(data):
    ALL_PLATFORM_SPECS = {
        "meta":     {"name": "Meta / Instagram", "limits": {"headline": 40, "hook": 125}},
        "tiktok":   {"name": "TikTok",           "limits": {"overlay": 34, "caption": 150}},
        "linkedin": {"name": "LinkedIn",          "limits": {"body": 1300}},
    }
    PLATFORM_SPECS = {k: v for k, v in ALL_PLATFORM_SPECS.items() if k in data.get("platforms", {})}

    def print_variant(platform_key, variant_num, variant_data):
        spec = PLATFORM_SPECS[platform_key]
        print(f"\n  VARIANT {variant_num}")
        print("  " + "─" * 56)
        for field, value in variant_data.items():
            if field == "image_prompt":
                continue
            limit = spec["limits"].get(field)
            if limit:
                flag = " ⚠️  OVER" if len(value) > limit else " ✅"
                print(f"  {field.upper()} ({len(value)}/{limit}{flag}): {value}")
            else:
                print(f"  {field.upper()}: {value}")

    selected = {}

    for platform_key, spec in PLATFORM_SPECS.items():
        platform_data = data["platforms"][platform_key]
        variants = {k: v for k, v in platform_data.items() if k.startswith("variant_")}

        print("\n" + "=" * 62)
        print(f"  {spec['name'].upper()} — PICK A VARIANT")
        print("=" * 62)

        for i, (vkey, vdata) in enumerate(variants.items(), 1):
            print_variant(platform_key, i, vdata)

        while True:
            raw = input(f"\n  Which variant? (1-{len(variants)}) / [R] reject all / [F] feedback + regenerate: ").strip().upper()
            if raw == "R":
                print("❌ Rejected — no files saved")
                return None
            if raw == "F":
                feedback = input("  What should be different? (e.g. 'more urgent', 'mention the reviews', 'less corporate'): ").strip()
                return {"regenerate": True, "feedback": feedback, "platform": platform_key}
            try:
                idx = int(raw) - 1
                vkey = list(variants.keys())[idx]
                chosen = variants[vkey]
                over_limit = []
                for field, limit in spec["limits"].items():
                    val = chosen.get(field, "")
                    if len(val) > limit:
                        over_limit.append(f"{field} ({len(val)}/{limit})")
                if over_limit:
                    print(f"  ⚠️  Over limit: {', '.join(over_limit)}")
                    confirm = input(f"  Use anyway? [Y/N]: ").strip().upper()
                    if confirm != "Y":
                        print("  Pick a different variant.")
                        continue
                selected[platform_key] = chosen
                print(f"  ✅ Selected variant {raw} for {spec['name']}")
                break
            except (ValueError, IndexError):
                print("  Invalid — try again")

    # Flatten selections back into data["platforms"]
    for platform_key, variant_data in selected.items():
        data["platforms"][platform_key] = variant_data

    print("\n✅ All platforms selected — proceeding to image generation")
    return data

def generate_images(data, output_dir, config, industry="general_business"):
    provider = config["image_generation"]["provider"]
    model = config["image_generation"]["model"]
    print(f"\n🎨 Generating images with {provider} ({model})...")
    images_dir = f"{output_dir}/images"
    os.makedirs(images_dir, exist_ok=True)
    active_platforms = list(data["platforms"].keys())

    image_sizes = {
        "meta": "portrait_4_3",      # 4:5 for Instagram feed
        "tiktok": "portrait_16_9",   # 9:16 vertical for TikTok
        "linkedin": "landscape_4_3", # 16:9 horizontal for LinkedIn
    }

    # Check for reference image to use as style anchor (image-to-image)
    ref_dir = f"client_assets/references/{industry}"
    ref_images = []
    if os.path.exists(ref_dir):
        ref_images = [f for f in os.listdir(ref_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    use_reference = bool(ref_images)
    if use_reference:
        print(f"  📎 Using reference image for style: {ref_dir}/{ref_images[0]}")

    for platform in active_platforms:
        image_prompt = data["platforms"][platform].get("image_prompt", "")
        image_path = f"{images_dir}/{platform}.jpg"

        try:
            import fal_client

            if use_reference:
                # Image-to-image: reference guides composition + style, prompt customizes content
                ref_path = f"{ref_dir}/{ref_images[0]}"
                with open(ref_path, "rb") as rf:
                    ref_url = fal_client.upload(rf.read(), content_type="image/jpeg")
                result = fal_client.run(
                    f"fal-ai/{model}",
                    arguments={
                        "prompt": image_prompt,
                        "image_url": ref_url,
                        "image_size": image_sizes.get(platform, "square_hd"),
                        "strength": 0.75,
                        "num_images": 1,
                    },
                )
            else:
                # Text-to-image with detailed prompt
                result = fal_client.run(
                    f"fal-ai/{model}",
                    arguments={
                        "prompt": image_prompt,
                        "image_size": image_sizes.get(platform, "square_hd"),
                        "num_images": 1,
                    },
                )

            image_url = result["images"][0]["url"]
            response = requests.get(image_url, timeout=60)
            response.raise_for_status()
            with open(image_path, "wb") as f:
                f.write(response.content)
            data["platforms"][platform]["image_url"] = image_url
            data["platforms"][platform]["image_path"] = image_path
            print(f"  ✅ {platform}: saved to {image_path}")

        except Exception as e:
            print(f"  ⚠️  {platform} image failed: {e}")

    return data

def _save_html_preview(data, output_dir):
    client = data.get("client", "")
    location = data.get("location", "")
    platforms_html = ""

    PLATFORM_LABELS = {
        "meta": "Instagram / Meta",
        "tiktok": "TikTok",
        "linkedin": "LinkedIn",
    }

    for platform_key, platform_data in data["platforms"].items():
        label = PLATFORM_LABELS.get(platform_key, platform_key.title())
        image_path = platform_data.get("image_path", "")
        image_tag = f'<img src="../{image_path}" alt="{label} ad image">' if image_path else '<div class="no-image">Image generation disabled</div>'

        if platform_key == "meta":
            hook = platform_data.get("hook", "")
            headline = platform_data.get("headline", "")
            body = platform_data.get("body", "")
            cta = platform_data.get("cta", "")
            hashtags = platform_data.get("hashtags", "")
            copy_html = f"""
                <p class="hook">{hook}</p>
                <p class="body">{body}</p>
                <div class="cta-bar">
                    <span class="headline">{headline}</span>
                    <button class="cta-btn">{cta}</button>
                </div>
                <p class="hashtags">{hashtags}</p>"""
        elif platform_key == "tiktok":
            overlay = platform_data.get("overlay", "")
            caption = platform_data.get("caption", "")
            cta = platform_data.get("cta", "")
            hashtags = platform_data.get("hashtags", "")
            copy_html = f"""
                <p class="overlay-label">[ IMAGE OVERLAY ] <strong>{overlay}</strong></p>
                <p class="body">{caption}</p>
                <p class="hook">{cta}</p>
                <p class="hashtags">{hashtags}</p>"""
        else:
            hook = platform_data.get("hook", "")
            body = platform_data.get("body", "")
            cta = platform_data.get("cta", "")
            hashtags = platform_data.get("hashtags", "")
            copy_html = f"""
                <p class="hook">{hook}</p>
                <p class="body">{body}</p>
                <p class="hook">{cta}</p>
                <p class="hashtags">{hashtags}</p>"""

        platforms_html += f"""
        <div class="ad-card">
            <div class="platform-label">{label}</div>
            <div class="ad-inner">
                <div class="ad-image">{image_tag}</div>
                <div class="ad-copy">{copy_html}</div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{client} — Ad Campaign Preview</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #1c1e21; }}
  header {{ background: #1877f2; color: white; padding: 24px 32px; }}
  header h1 {{ font-size: 22px; font-weight: 700; }}
  header p {{ font-size: 14px; opacity: 0.85; margin-top: 4px; }}
  .badge {{ display: inline-block; background: rgba(255,255,255,0.2); border-radius: 12px; padding: 2px 10px; font-size: 12px; margin-top: 8px; }}
  main {{ max-width: 960px; margin: 32px auto; padding: 0 16px; }}
  .ad-card {{ background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.12); margin-bottom: 28px; overflow: hidden; }}
  .platform-label {{ background: #1877f2; color: white; font-size: 12px; font-weight: 600; padding: 6px 16px; letter-spacing: 0.05em; text-transform: uppercase; }}
  .ad-inner {{ display: flex; gap: 0; }}
  .ad-image {{ width: 280px; min-width: 280px; background: #e4e6ea; display: flex; align-items: center; justify-content: center; }}
  .ad-image img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .no-image {{ color: #65676b; font-size: 13px; padding: 40px 20px; text-align: center; }}
  .ad-copy {{ flex: 1; padding: 20px 24px; display: flex; flex-direction: column; gap: 10px; }}
  .hook {{ font-size: 15px; color: #1c1e21; line-height: 1.5; }}
  .body {{ font-size: 14px; color: #444; line-height: 1.6; }}
  .hashtags {{ font-size: 13px; color: #1877f2; line-height: 1.6; }}
  .overlay-label {{ font-size: 13px; color: #666; }}
  .cta-bar {{ display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #e4e6ea; padding-top: 12px; margin-top: 4px; }}
  .headline {{ font-size: 16px; font-weight: 700; color: #1c1e21; }}
  .cta-btn {{ background: #1877f2; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-size: 14px; font-weight: 600; cursor: pointer; }}
  footer {{ text-align: center; color: #65676b; font-size: 12px; padding: 24px; }}
  @media (max-width: 600px) {{ .ad-inner {{ flex-direction: column; }} .ad-image {{ width: 100%; min-width: unset; height: 240px; }} }}
</style>
</head>
<body>
<header>
  <h1>{client}</h1>
  <p>{location}</p>
  <span class="badge">Generated by Community Trust Creative Agent · Mettics Consulting</span>
</header>
<main>
{platforms_html}
</main>
<footer>Generated by Mettics Community Trust Creative Agent</footer>
</body>
</html>"""

    with open(f"{output_dir}/preview.html", "w") as f:
        f.write(html)

META_CTA_MAP = {
    "Book Now": "BOOK_TRAVEL",
    "Call Today": "CALL_NOW",
    "Get a Free Quote": "GET_QUOTE",
    "DM Us": "MESSAGE_PAGE",
    "Learn More": "LEARN_MORE",
    "Contact Us": "CONTACT_US",
}

def _save_meta_export(data, output_dir):
    """Save meta_export.json formatted for Meta Ads Manager upload."""
    meta = data["platforms"]["meta"]
    primary_text = f"{meta.get('hook', '')}\n\n{meta.get('body', '')}"
    cta_text = meta.get("cta", "Learn More")
    export = {
        "meta_ads_manager": {
            "campaign_name": f"{data['client']} — Instagram Campaign",
            "ad_format": "Single Image",
            "placement": "Instagram Feed",
            "aspect_ratio": "4:5",
            "recommended_resolution": "1080x1350px",
            "primary_text": primary_text,
            "headline": meta.get("headline", ""),
            "call_to_action_type": META_CTA_MAP.get(cta_text, "LEARN_MORE"),
            "call_to_action_label": cta_text,
            "hashtags": meta.get("hashtags", ""),
            "image_prompt": meta.get("image_prompt", ""),
            "image_path": meta.get("image_path", "— not generated yet —"),
            "upload_instructions": [
                "1. Go to Meta Ads Manager → Create Ad",
                "2. Choose Instagram Feed placement",
                "3. Upload image at 1080x1350px (4:5 ratio)",
                "4. Paste primary_text into Primary Text field",
                "5. Paste headline into Headline field",
                "6. Set call_to_action_type from this file",
                "7. Set budget and audience, then publish"
            ]
        }
    }
    with open(f"{output_dir}/meta_export.json", "w") as f:
        json.dump(export, f, indent=2)


def save_output(data, output_dir):
    print(f"\n💾 Saving output to {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)

    with open(f"{output_dir}/campaign.json", "w") as f:
        json.dump(data, f, indent=2)

    saved_files = []

    if "meta" in data["platforms"]:
        meta = data["platforms"]["meta"]
        with open(f"{output_dir}/meta.md", "w") as f:
            f.write(f"# Meta / Instagram — {data['client']}\n\n")
            f.write(f"## AD PREVIEW\n\n")
            f.write(f"---\n\n")
            f.write(f"{meta.get('hook', '')}\n\n")
            f.write(f"{meta.get('body', '')}\n\n")
            f.write(f"**{meta.get('headline', '')}**\n\n")
            f.write(f"👉 {meta.get('cta', '')}\n\n")
            f.write(f"{meta.get('hashtags', '')}\n\n")
            f.write(f"---\n\n")
            f.write(f"## SPECS\n\n")
            f.write(f"- **Headline** ({len(meta.get('headline', ''))} chars / 40 max): {meta.get('headline', '')}\n")
            f.write(f"- **Primary Text** ({len(meta.get('hook', ''))} chars / 125 max): {meta.get('hook', '')}\n")
            f.write(f"- **CTA:** {meta.get('cta', '')}\n")
            f.write(f"- **Image Prompt:** {meta.get('image_prompt', '')}\n")
            f.write(f"- **Image Ratio:** 4:5 portrait (Instagram feed)\n")
            if meta.get('image_path'):
                f.write(f"- **Image:** {meta['image_path']}\n")
        saved_files.append("meta.md")

    if "tiktok" in data["platforms"]:
        tiktok = data["platforms"]["tiktok"]
        with open(f"{output_dir}/tiktok.md", "w") as f:
            f.write(f"# TikTok — {data['client']}\n\n")
            f.write(f"## AD PREVIEW\n\n")
            f.write(f"---\n\n")
            f.write(f"**[ IMAGE OVERLAY ]** {tiktok.get('overlay', '')}\n\n")
            f.write(f"{tiktok.get('caption', '')}\n\n")
            f.write(f"👉 {tiktok.get('cta', '')}\n\n")
            f.write(f"{tiktok.get('hashtags', '')}\n\n")
            f.write(f"---\n\n")
            f.write(f"## SPECS\n\n")
            f.write(f"- **Overlay** ({len(tiktok.get('overlay', ''))} chars / 34 max)\n")
            f.write(f"- **Caption** ({len(tiktok.get('caption', ''))} chars / 150 max)\n")
            f.write(f"- **CTA:** {tiktok.get('cta', '')}\n")
            f.write(f"- **Image Prompt:** {tiktok.get('image_prompt', '')}\n")
            if tiktok.get('image_path'):
                f.write(f"- **Image:** {tiktok['image_path']}\n")
        saved_files.append("tiktok.md")

    if "linkedin" in data["platforms"]:
        linkedin = data["platforms"]["linkedin"]
        with open(f"{output_dir}/linkedin.md", "w") as f:
            f.write(f"# LinkedIn — {data['client']}\n\n")
            f.write(f"## POST PREVIEW\n\n")
            f.write(f"---\n\n")
            f.write(f"{linkedin.get('hook', '')}\n\n")
            f.write(f"{linkedin.get('body', '')}\n\n")
            f.write(f"{linkedin.get('cta', '')}\n\n")
            f.write(f"{linkedin.get('hashtags', '')}\n\n")
            f.write(f"---\n\n")
            f.write(f"## SPECS\n\n")
            f.write(f"- **Hook** ({len(linkedin.get('hook', ''))} chars)\n")
            f.write(f"- **Body** ({len(linkedin.get('body', ''))} chars / 1300 max)\n")
            f.write(f"- **CTA:** {linkedin.get('cta', '')}\n")
            f.write(f"- **Image Prompt:** {linkedin.get('image_prompt', '')}\n")
            if linkedin.get('image_path'):
                f.write(f"- **Image:** {linkedin['image_path']}\n")
        saved_files.append("linkedin.md")

    saved_files.append("campaign.json")
    _save_html_preview(data, output_dir)
    saved_files.append("preview.html")

    if "meta" in data["platforms"]:
        _save_meta_export(data, output_dir)
        saved_files.append("meta_export.json")

    print(f"✅ Saved: {', '.join(saved_files)}")

if __name__ == "__main__":
    config = json.load(open("config.json"))

    print("\n" + "=" * 62)
    print("  COMMUNITY TRUST CREATIVE AGENT")
    print("  Mettics Consulting — AI Ad Campaign Generator")
    print("=" * 62)
    print(f"  Platforms: {', '.join(config['platforms'])}")
    print("  Output:    3 variants + AI image (4:5 portrait)")
    print("=" * 62 + "\n")
    start_time = time.time()

    company_name = input("Enter company name: ")
    location = input("Enter location (e.g. Brambleton VA): ")
    output_dir = get_output_dir(company_name)
    config["output_dir"] = output_dir
    print(f"\n📁 Output will be saved to: {output_dir}")

    # Stage 1 — Search
    results = search_business(company_name, location)
    print("\nTop results found:")
    for i, r in enumerate(results):
        print(f"  {i+1}. {r}")

    if results:
        print("\nWhich result do you want to use? (enter 1, 2, or 3)")
        choice = input("Choice: ").strip()
        try:
            index = int(choice) - 1
            website_url = f"https://{results[index]}"
            print(f"✅ Using: {website_url}")
        except:
            print("Invalid choice, using first result")
            website_url = f"https://{results[0]}"
    else:
        website_url = None

    if not website_url:
        print("❌ No results found. Exiting.")
        exit()

    # Stage 2 — Scrape and Validate
    scraped = scrape_website(website_url)
    is_valid = validate_scrape(scraped, company_name, location)
    if not is_valid:
        print("❌ Validation failed. Please check the URL manually.")
        exit()

    # Stage 3 — AI Generation
    provider = config["ai_generation"]["provider"]
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        print("\n❌ No Gemini API key found in .env")
        exit()
    elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("\n❌ No Anthropic API key found in .env")
        exit()

    # Stage 3–5 loop — supports regeneration with feedback
    regenerate_prompt = ""
    while True:
        try:
            campaign_json = generate_campaign(scraped, company_name, location, config, regenerate_prompt)
        except Exception as e:
            print(f"\n❌ AI generation failed: {e}")
            exit()

        # Stage 4 — Validate Output
        is_valid_output, data = validate_output(campaign_json)
        if not is_valid_output:
            print("❌ Output validation failed. Campaign not saved.")
            exit()

        # Keep only configured platforms (AI may generate extras)
        configured = config.get("platforms", ["meta"])
        data["platforms"] = {k: v for k, v in data["platforms"].items() if k in configured}

        # Stage 5 — Human Review Gate
        result = human_review_gate(data)
        if result is None:
            exit()
        if isinstance(result, dict) and result.get("regenerate"):
            regenerate_prompt = result["feedback"]
            print(f"\n🔄 Regenerating with feedback: \"{regenerate_prompt}\"...")
            continue
        data = result
        break

    # Stage 6 — Image Generation
    industry, _ = _detect_industry(scraped)
    if config["image_generation"].get("enabled", True):
        try:
            data = generate_images(data, output_dir, config, industry)
        except Exception as e:
            print(f"\n⚠️  Image generation failed: {e}")
            print("   Continuing — text output will still be saved.")
    else:
        print(f"\n🎨 Image generation disabled — skipping (set enabled: true in config.json to activate)")

    # Stage 7 — Save Output
    save_output(data, output_dir)

    elapsed = time.time() - start_time
    active_platforms = list(data["platforms"].keys())
    images_generated = sum(1 for p in active_platforms if data["platforms"][p].get("image_path"))
    cost = images_generated * config["image_generation"]["cost_per_image"]

    md_files = [f"{p}.md" for p in active_platforms]
    file_lines = [f"           ├── {f}" for f in md_files]
    file_lines += ["           ├── campaign.json", "           ├── preview.html"]
    if images_generated:
        img_names = ", ".join(f"{p}.jpg" for p in active_platforms)
        file_lines.append(f"           └── images/  ({img_names})")

    print(f"\n" + "=" * 62)
    print(f"  CAMPAIGN COMPLETE — {company_name.upper()}")
    print("=" * 62)
    print(f"  Time:      {elapsed:.0f} seconds")
    print(f"  Platforms: {', '.join(active_platforms)}")
    print(f"  Images:    {images_generated}/{len(active_platforms)} generated")
    print(f"  Cost:      ~${cost:.3f} (image generation only)")
    print(f"  Output:    {output_dir}/")
    for line in file_lines:
        print(line)
    print("=" * 62 + "\n")
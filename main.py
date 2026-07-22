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

INDUSTRY_KEYWORDS = {
    # Scored with word boundaries — the industry with the most keyword hits wins.
    # This prevents e.g. "Southern Thai heat" matching home_services' "heat".
    "food_beverage": [
        "restaurant", "menu", "chef", "cuisine", "dish", "dishes", "dining", "dine",
        "coffee", "cafe", "café", "bakery", "pizza", "sushi", "thai", "taco", "tacos",
        "brunch", "brewery", "brewing", "bistro", "diner", "eatery", "catering",
        "takeout", "cocktails", "appetizers", "entrees", "dessert", "flavors", "foodie",
    ],
    "home_services": [
        "plumbing", "plumber", "plumbers", "hvac", "heating", "cooling", "furnace",
        "electrician", "electrical", "roofing", "roofer", "landscaping", "lawn",
        "pest", "handyman", "drain", "drains", "sewer", "gutter", "gutters",
        "water heater", "air conditioning", "remodeling", "renovation", "contractor",
    ],
    "health_beauty": [
        "salon", "spa", "stylist", "haircut", "hairstyle", "manicure", "pedicure",
        "massage", "barber", "barbershop", "facial", "facials", "skincare", "lashes",
        "waxing", "botox", "esthetician", "blowout", "balayage", "nails",
    ],
    "health_fitness": [
        "gym", "fitness", "yoga", "pilates", "crossfit", "workout", "workouts",
        "training", "trainer", "trainers", "athletes", "cardio", "strength",
        "membership", "classes", "coaching", "bootcamp",
    ],
    "professional_services": [
        "attorney", "attorneys", "law", "legal", "accounting", "accountant", "cpa",
        "tax", "taxes", "consulting", "consultant", "insurance", "realtor",
        "real estate", "mortgage", "advisor", "advisors", "financial", "bookkeeping",
    ],
    "retail": [
        "boutique", "shop", "store", "retail", "clothing", "apparel", "jewelry",
        "gifts", "accessories", "collection", "collections", "merchandise",
        # e-commerce / consumer-tech gear
        "charger", "chargers", "charging", "cable", "cables", "adapter", "adapters",
        "powerbank", "power bank", "wireless", "usb", "gadget", "gadgets", "device",
        "devices", "electronics", "portable", "watt", "watts", "product", "products",
        "cart", "checkout", "shipping", "bundle", "warranty", "add to cart", "buy now",
    ],
}

INDUSTRY_STYLE_HINTS = {
    "home_services": "Technician actively working on-site, natural daylight, tool belt visible, real house setting. NOT posed stock.",
    "food_beverage": "Signature dish or drink as the hero, bright natural daylight, vibrant appetizing colors, fresh ingredients visible. Bright and inviting, not dark.",
    "health_beauty": "Client mid-service or just-finished, soft natural window light, serene and relaxed, clean minimalist salon background.",
    "health_fitness": "Person mid-exercise with visible effort and determination, bright energetic gym or outdoor setting, dynamic motion.",
    "professional_services": "Two people in genuine conversation or reviewing results on a laptop, bright clean office, confident and credible.",
    "retail": "Person using or wearing the product in a natural lifestyle context, clean daylight, aspirational but candid.",
    "general_business": "Real people in the actual business setting, natural light, authentic candid moment — not staged or stock.",
}


def _detect_industry(scraped_data):
    """Classify business type from scraped content. Returns (industry_key, image_style_hint).
    Scores every industry by whole-word keyword hits and picks the highest — a single
    stray substring can no longer misclassify (e.g. a Thai restaurant as home services)."""
    import re
    all_text = " ".join(
        scraped_data.get("paragraphs", []) +
        scraped_data.get("h1", []) +
        scraped_data.get("h2", [])
    ).lower()

    scores = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            score += len(re.findall(rf"\b{re.escape(kw)}\b", all_text))
        scores[industry] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "general_business"
    return best, INDUSTRY_STYLE_HINTS[best]


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

def _collect_site_images(base_url, soup, headers):
    """Find real product/hero photos on the site: og:image plus every large <img>.
    Candidates are downloaded in parallel and only genuinely large photos survive
    (min 500x400, sane aspect ratio), ranked by pixel area. Returns up to 6 URLs."""
    from urllib.parse import urljoin
    from io import BytesIO
    from PIL import Image as PILImage

    candidates = []
    for meta in soup.find_all("meta", attrs={"property": ["og:image", "og:image:secure_url"]}):
        if meta.get("content"):
            candidates.append(urljoin(base_url, meta["content"]))
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or ""
        if not src and tag.get("srcset"):
            src = tag["srcset"].split(",")[-1].strip().split(" ")[0]
        if not src:
            continue
        low = src.lower()
        if low.startswith("data:") or any(x in low for x in (
                ".svg", ".gif", "logo", "icon", "sprite", "favicon",
                "placeholder", "avatar", "badge", "payment")):
            continue
        candidates.append(urljoin(base_url, src))

    seen, unique = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    def _check(img_url):
        try:
            r = requests.get(img_url, headers=headers, timeout=6)
            r.raise_for_status()
            im = PILImage.open(BytesIO(r.content))
            w, h = im.size
            if w >= 500 and h >= 400 and 0.4 <= w / h <= 2.6:
                return (w * h, img_url)
        except Exception:
            pass
        return None

    from concurrent.futures import ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(_check, unique[:12]):
            if res:
                results.append(res)
    results.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in results[:6]]


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

    # Collect real product/hero photos from the homepage (validated by download)
    images = _collect_site_images(url, home["soup"], headers)
    if images:
        print(f"  📷 Found {len(images)} usable photos on the site")

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

def _build_campaign_prompt(scraped_data, company_name, location, config, feedback="", brand_brief=None):
    """Assemble the rich generation prompt (tuned system prompt + scraped context +
    per-industry few-shot examples + brand signals + optional Brand Brief + feedback).
    Returns (system_prompt, user_message, industry). Shared by the hybrid single-call
    path and the Copy Generation Agent so both produce identically high-quality copy
    and image prompts."""
    signals = scraped_data.get("brand_signals", {})
    signals_text = "\n".join(f"  - {k}: {v}" for k, v in signals.items()) if signals else "  None extracted"

    subpages_text = ""
    for page_name, page_data in scraped_data.get("subpages", {}).items():
        combined = page_data.get("h1", []) + page_data.get("h2", []) + page_data.get("paragraphs", [])
        if combined:
            subpages_text += f"\n[{page_name.upper()} PAGE]\n" + "\n".join(combined[:8]) + "\n"

    industry, image_style = _detect_industry(scraped_data)
    platforms_to_generate = config.get("platforms", ["meta"])

    examples_text = ""
    examples_path = f"client_assets/examples/{industry}.json"
    if os.path.exists(examples_path):
        try:
            ex_data = json.load(open(examples_path))
            examples = ex_data.get("examples", [])[:2]
            if examples:
                examples_text = "\n\nHIGH-PERFORMING AD EXAMPLES — study these and match the quality, specificity, and tone:\n"
                for i, ex in enumerate(examples, 1):
                    examples_text += f"\nExample {i} ({ex.get('angle', '')}):\n"
                    examples_text += f"  headline: {ex['headline']}\n"
                    examples_text += f"  hook: {ex['hook']}\n"
                    examples_text += f"  body: {ex['body']}\n"
                    examples_text += f"  cta: {ex['cta']}\n"
                    if ex.get('image_prompt'):
                        examples_text += f"  image_prompt: {ex['image_prompt']}\n"
        except Exception:
            pass

    # The Brand Intelligence Agent's structured brief, when available, gives the
    # copywriter richer voice/USP/positioning signal than regex-scraped facts alone.
    brief_block = ""
    if brand_brief:
        brief_block = ("\n\nBRAND BRIEF (from the Brand Intelligence Agent — use its voice, "
                       "USPs, audience and positioning to make every line specific):\n"
                       + json.dumps(brand_brief, indent=2))

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
    user_message = (f"Generate a complete campaign for {company_name} in {location}. "
                    f"Here is all the data scraped from their website:\n\n"
                    f"{context}{examples_text}{brief_block}{feedback_line}\n\n"
                    f"Return ONLY a valid JSON object. No markdown, no explanation, just the JSON.")
    return system_prompt, user_message, industry


def generate_campaign(scraped_data, company_name, location, config, feedback="", brand_brief=None):
    provider = config["ai_generation"]["provider"]
    model = config["ai_generation"]["model"]
    print(f"\n🤖 Sending to {provider} ({model}) for campaign generation...")

    system_prompt, user_message, industry = _build_campaign_prompt(
        scraped_data, company_name, location, config, feedback, brand_brief)
    platforms_to_generate = config.get("platforms", ["meta"])
    print(f"  Industry detected: {industry} | Platforms: {', '.join(platforms_to_generate)}")
    full_prompt = f"{system_prompt}\n\n{user_message}"

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
            max_tokens=8192,
            messages=[{"role": "user", "content": full_prompt}]
        )
        print(f"✅ Claude generated campaign")
        return message.content[0].text

    else:
        raise ValueError(f"Unknown AI provider: {provider}")

def _repair_json(text):
    """Best-effort cleanup of the small JSON mistakes LLMs make, so one stray
    character doesn't waste a whole generation. Handles: markdown fences, trailing
    commas before } or ], smart quotes, and stray control chars inside the object."""
    import re
    # Strip code fences if the model wrapped the object despite instructions
    text = re.sub(r"^```(?:json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    # Isolate the outermost object
    start, end = text.find("{"), text.rfind("}") + 1
    if start != -1 and end > 0:
        text = text[start:end]
    # Normalize smart quotes the model may have used around keys/values
    text = text.replace("“", '"').replace("”", '"')
    # Remove trailing commas: ,}  ,]  (the single most common LLM JSON error)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    # Drop raw control characters that break strict JSON
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


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
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            # Recover from malformed LLM JSON (unescaped quotes, trailing commas,
            # missing commas, ...). json_repair is the robust path; the regex
            # cleanup is a dependency-free fallback if it isn't installed.
            try:
                import json_repair
                data = json_repair.loads(campaign_json)
                if not isinstance(data, dict) or not data:
                    raise ValueError("json_repair produced no object")
            except ImportError:
                data = json.loads(_repair_json(campaign_json))
            print("  🔧 Recovered from malformed JSON in AI response")
    except json.JSONDecodeError as e:
        msg = f"Not valid JSON: {e} (response length: {len(campaign_json)} chars, last 200: ...{campaign_json[-200:]})"
        print(f"❌ {msg}")
        return False, None, msg
    required_platforms = list(data.get("platforms", {}).keys())
    if not required_platforms:
        msg = "No platforms found in AI output"
        print(f"❌ {msg}")
        return False, None, msg
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
        return False, None, "; ".join(errors)
    print(f"✅ Campaign output validated — all fields present")
    return True, data, None

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

import re as _re_emoji
# Emoji / pictographic ranges. The AI puts emojis in copy (great for the caption, which
# the browser renders), but the fonts used to draw text ONTO the ad image have no emoji
# glyphs, so they'd show as □ tofu boxes. We strip them from baked-in overlay text only.
_EMOJI_RE = _re_emoji.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticons, symbols, transport, supplemental
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U00002300-\U000023FF"   # misc technical (⌚⏳ etc.)
    "\U00002B00-\U00002BFF"   # misc symbols and arrows
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U0000200D"              # zero-width joiner
    "\U000020E3"              # combining enclosing keycap
    "]+"
)


def _strip_emoji(text):
    """Remove emoji/pictographs and tidy the spacing they leave behind."""
    if not text:
        return text
    text = _EMOJI_RE.sub("", text)
    text = _re_emoji.sub(r"\s{2,}", " ", text)          # collapse double spaces
    text = _re_emoji.sub(r"\s+([.,!?;:])", r"\1", text)  # no space before punctuation
    return text.strip()


INDUSTRY_PALETTE = {
    "food_beverage":         {"accent": (210, 120, 30),  "btn": (210, 120, 30),  "btn_txt": (255, 255, 255)},
    "home_services":         {"accent": (30, 80, 180),   "btn": (30, 80, 180),   "btn_txt": (255, 255, 255)},
    "health_beauty":         {"accent": (200, 80, 110),  "btn": (200, 80, 110),  "btn_txt": (255, 255, 255)},
    "health_fitness":        {"accent": (255, 80, 10),   "btn": (255, 80, 10),   "btn_txt": (255, 255, 255)},
    "retail":                {"accent": (100, 60, 160),  "btn": (100, 60, 160),  "btn_txt": (255, 255, 255)},
    "professional_services": {"accent": (10, 40, 120),   "btn": (10, 40, 120),   "btn_txt": (255, 255, 255)},
    "general_business":      {"accent": (99, 102, 241),  "btn": (99, 102, 241),  "btn_txt": (255, 255, 255)},
}

def _create_ad_creative(image_path, headline, hook, cta="Learn More", industry="general_business",
                        eyebrow="", layout="classic", signals=None):
    """Full-bleed photo with a designed brand overlay. Three layout archetypes so the
    variants read as distinct ads, not one template with swapped text:
      - social_proof: gold star row + real rating/review numbers above the headline
      - bold:         oversized headline with a brand-color marker behind the key word
      - editorial:    centered serif composition with an outlined CTA (story ads)
      - classic:      the original left-aligned stack (CLI fallback)"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
        import math

        # Strip emojis from anything drawn onto the image — the overlay fonts have no
        # emoji glyphs, so they'd render as □ boxes. (Emojis stay in the caption/body,
        # which the browser renders fine.)
        headline = _strip_emoji(headline)
        hook = _strip_emoji(hook)
        cta = _strip_emoji(cta) or "Learn More"
        eyebrow = _strip_emoji(eyebrow)

        c = INDUSTRY_PALETTE.get(industry, INDUSTRY_PALETTE["general_business"])
        accent = c["accent"]

        # Brighten the accent so it stays visible on the dark gradient
        def _bright(rgb, floor=155):
            r, g, b = rgb
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum < floor:
                k = floor / max(lum, 1)
                return tuple(min(255, int(ch * k)) for ch in rgb)
            return rgb
        accent_bright = _bright(accent)
        dark_brand = tuple(int(ch * 0.20) for ch in accent)  # brand-tinted shadow

        img = Image.open(image_path).convert("RGB")

        # ── Subtle vibrance pass: brighter, punchier, more "ad-ready" ──
        img = ImageEnhance.Brightness(img).enhance(1.06)
        img = ImageEnhance.Color(img).enhance(1.14)
        img = ImageEnhance.Contrast(img).enhance(1.04)
        img = img.convert("RGBA")
        w, h = img.size

        # ── Brand-tinted gradient over the lower frame ─────────────────
        # Fades from clear (top) to a dark brand-tinted black (bottom), so the
        # photo reads as on-brand rather than sitting under a generic black bar.
        # Starts lower + ramps gentler than before so more of the photo shows.
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_start = int(h * 0.30)
        for y in range(grad_start, h):
            t = (y - grad_start) / (h - grad_start)
            # Ramp to near-opaque so headline + body always read cleanly, but keep
            # the top of the ramp gentle so the product photo stays visible.
            alpha = int(248 * min(t ** 0.55, 1.0))
            fill_rgb = tuple(int(dark_brand[i] * t) for i in range(3))
            ov_draw.line([(0, y), (w, y)], fill=(*fill_rgb, alpha))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # ── Fonts ──────────────────────────────────────────────────────
        fs_eye = max(int(w * 0.028), 14)
        fs_sub = max(int(w * 0.041), 17)
        fs_btn = max(int(w * 0.040), 16)

        # Named type roles → prioritized (path, collection-index) stacks. Avenir Next
        # (Heavy display, Demi labels, Medium body) and Didot (editorial serif) give a
        # premium agency look; Helvetica Neue / Helvetica are graceful fallbacks.
        FONT_STACKS = {
            "display": [("/System/Library/Fonts/Avenir Next.ttc", 8),      # Heavy
                        ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
                        ("/System/Library/Fonts/Helvetica.ttc", 1)],
            "serif":   [("/System/Library/Fonts/Supplemental/Didot.ttc", 2),  # Bold
                        ("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", None),
                        ("/System/Library/Fonts/Helvetica.ttc", 1)],
            "label":   [("/System/Library/Fonts/Avenir Next.ttc", 2),      # Demi Bold
                        ("/System/Library/Fonts/HelveticaNeue.ttc", 10),
                        ("/System/Library/Fonts/Helvetica.ttc", 1)],
            "body":    [("/System/Library/Fonts/Avenir Next.ttc", 5),      # Medium
                        ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
                        ("/System/Library/Fonts/Helvetica.ttc", 0)],
            "cta":     [("/System/Library/Fonts/Avenir Next.ttc", 0),      # Bold
                        ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
                        ("/System/Library/Fonts/Helvetica.ttc", 1)],
        }

        def _tf(role, size):
            for path, idx in FONT_STACKS.get(role, FONT_STACKS["body"]):
                if os.path.exists(path):
                    try:
                        return ImageFont.truetype(path, size, index=idx) if idx is not None \
                               else ImageFont.truetype(path, size)
                    except Exception:
                        continue
            return ImageFont.load_default()

        pad = int(w * 0.075)
        avail_w = w - 2 * pad

        # Draw text with manual letter-spacing (PIL has no native tracking)
        def _draw_tracked(pos, text, font, fill, tracking):
            x, y = pos
            for ch in text:
                draw.text((x, y), ch, font=font, fill=fill)
                x += draw.textlength(ch, font=font) + tracking

        # 5-point star, drawn as a polygon so it renders in every font environment
        def _star(cx, cy, r, fill):
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                rad = r if i % 2 == 0 else r * 0.42
                pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
            draw.polygon(pts, fill=fill)

        # ── Auto-fit headline: shrink font until the WHOLE headline fits ──
        # in at most 2 lines. Never truncate — a cut-off headline looks broken.
        def _wrap_to_width(text, font, max_w):
            words, lines, cur = text.split(), [], ""
            for word in words:
                trial = (cur + " " + word).strip()
                if draw.textlength(trial, font=font) <= max_w or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = word
            if cur:
                lines.append(cur)
            return lines

        def _fit_headline(text, start, min_size, max_lines=2, mk=None):
            mk = mk or (lambda s: _tf("display", s))
            size = start
            while size >= min_size:
                font = mk(size)
                lines = _wrap_to_width(text, font, avail_w)
                fits_width = all(draw.textlength(ln, font=font) <= avail_w for ln in lines)
                if len(lines) <= max_lines and fits_width:
                    return font, lines, size
                size -= 3
            font = mk(min_size)
            return font, _wrap_to_width(text, font, avail_w)[:max_lines], min_size

        # Headline treatment per layout: bold goes bigger (urgency shouts),
        # editorial goes serif and slightly smaller (story whispers)
        if layout == "bold":
            hfont, hl_lines, fs_hl = _fit_headline(
                headline.strip(), start=max(int(w * 0.115), 44),
                min_size=max(int(w * 0.052), 24), max_lines=3)
        elif layout == "editorial":
            hfont, hl_lines, fs_hl = _fit_headline(
                headline.strip(), start=max(int(w * 0.088), 34),
                min_size=max(int(w * 0.048), 22), mk=lambda s: _tf("serif", s))
        else:
            hfont, hl_lines, fs_hl = _fit_headline(
                headline.strip(), start=max(int(w * 0.098), 38),
                min_size=max(int(w * 0.052), 24))
        efont = _tf("label", fs_eye)   # Demi Bold (eyebrow / rating)
        bfont = _tf("cta", fs_btn)     # Bold (CTA)

        # ── Auto-fit hook: shrink slightly so the WHOLE hook fits in up to 3 lines. ──
        # This keeps the primary text from being cut off; ellipsis is a last resort only
        # if an unusually long hook still won't fit even at the smallest size.
        def _fit_hook(text, start, min_size, max_lines=3):
            size = start
            while size >= min_size:
                f = _tf("body", size)
                lines = _wrap_to_width(text, f, avail_w)
                if len(lines) <= max_lines:
                    return f, lines, size
                size -= 2
            f = _tf("body", min_size)
            lines = _wrap_to_width(text, f, avail_w)[:max_lines]
            lines[-1] = lines[-1].rstrip(" ,;—-") + "…"
            return f, lines, min_size

        sfont, hook_lines, fs_sub = _fit_hook(
            hook.strip(), fs_sub, max(int(fs_sub * 0.80), 14), max_lines=3)

        lh_hl  = int(fs_hl  * 1.14)
        lh_sub = int(fs_sub * 1.46)

        # ── CTA pill: sized to label + vector arrow, not a full-width bar ──
        cta_label = cta[:20]
        btn_pad_x = int(w * 0.055)
        btn_h_px  = max(int(h * 0.070), 50)
        label_w   = int(draw.textlength(cta_label, font=bfont))
        arrow_len = int(fs_btn * 0.95)
        arrow_gap = int(fs_btn * 0.60)
        content_w = label_w + arrow_gap + arrow_len
        btn_w_px  = max(content_w + 2 * btn_pad_x, int(w * 0.42))

        # ── Real numbers for the social-proof star row ─────────────────
        import re as _re
        rating_txt = ""
        if signals:
            m = _re.search(r"\d\.\d", str(signals.get("rating", "")))
            r_num = m.group(0) if m else ""
            m2 = _re.search(r"[\d,]+\+?", str(signals.get("review_count", "")))
            c_num = m2.group(0) if m2 else ""
            if r_num and c_num:
                rating_txt = f"{r_num}  ·  {c_num} reviews"
            elif r_num:
                rating_txt = f"Rated {r_num} by customers"
            elif c_num:
                rating_txt = f"{c_num} customer reviews"
        use_stars = layout == "social_proof" and bool(rating_txt)
        centered = layout == "editorial"

        def _line_x(line, font):
            return (w - int(draw.textlength(line, font=font))) // 2 if centered else pad

        # ── Build layout from bottom up ────────────────────────────────
        bot_margin = int(h * 0.062)

        btn_y   = h - bot_margin - btn_h_px
        hook_y  = btn_y - int(h * 0.030) - len(hook_lines) * lh_sub
        hl_y    = hook_y - int(h * 0.030) - len(hl_lines) * lh_hl

        # ── Element above the headline: differs per layout ─────────────
        star_r = int(fs_eye * 0.64)
        if use_stars:
            row_h = star_r * 2
            row_y = hl_y - int(h * 0.040) - row_h
            cx = pad + star_r
            cy = row_y + star_r
            for _ in range(5):
                _star(cx, cy, star_r, (255, 196, 54, 255))
                cx += int(star_r * 2.4)
            rt_bbox = draw.textbbox((0, 0), rating_txt, font=efont)
            draw.text((cx + int(star_r * 0.9), cy - (rt_bbox[3] - rt_bbox[1]) // 2 - rt_bbox[1]),
                      rating_txt, font=efont, fill=(255, 255, 255, 245))
        elif layout == "bold" and eyebrow:
            # Badge chip: eyebrow inside a solid brand-color tag
            chip_txt = eyebrow.upper()[:28]
            tr = max(2, int(fs_eye * 0.10))
            chip_w = int(draw.textlength(chip_txt, font=efont) + len(chip_txt) * tr) + int(fs_eye * 1.6)
            chip_h = int(fs_eye * 2.0)
            chip_y = hl_y - int(h * 0.026) - chip_h
            draw.rounded_rectangle([pad, chip_y, pad + chip_w, chip_y + chip_h],
                                   radius=int(chip_h * 0.24), fill=(*c["btn"], 255))
            _draw_tracked((pad + int(fs_eye * 0.8), chip_y + (chip_h - fs_eye) // 2 - int(fs_eye * 0.10)),
                          chip_txt, efont, (*c["btn_txt"], 255), tracking=tr)
        else:
            # Classic / editorial: tracked eyebrow + accent rule (centered if editorial)
            line_y = hl_y - int(h * 0.026)
            eye_y  = line_y - int(h * 0.014) - fs_eye
            rule_w = int(w * 0.13)
            rule_x = (w - rule_w) // 2 if centered else pad
            if eyebrow:
                etxt = eyebrow.upper()[:32]
                tr = max(2, int(fs_eye * 0.14))
                etxt_w = int(draw.textlength(etxt, font=efont) + len(etxt) * tr)
                ex = (w - etxt_w) // 2 if centered else pad
                _draw_tracked((ex, eye_y), etxt, efont, (*accent_bright, 255), tracking=tr)
            draw.rectangle([rule_x, line_y, rule_x + rule_w, line_y + max(4, int(h * 0.004))],
                           fill=(*accent_bright, 255))

        # ── Headline ───────────────────────────────────────────────────
        # Bold layout: brand-color marker box behind the PUNCHLINE — the trailing
        # word(s) of the last line, where the emotional payoff lands. Anchoring it
        # to the end (not a random middle word) reads as a deliberate design choice.
        hi_phrase = ""
        if layout == "bold" and hl_lines:
            last_words = hl_lines[-1].split()
            if last_words:
                hi_phrase = last_words[-1]
                # pull in the previous word if the last one is tiny ("It", "Now")
                if len(_re.sub(r"\W", "", hi_phrase)) <= 3 and len(last_words) > 1:
                    hi_phrase = " ".join(last_words[-2:])
        y = hl_y
        for idx, line in enumerate(hl_lines):
            lx = _line_x(line, hfont)
            is_last = idx == len(hl_lines) - 1
            if hi_phrase and is_last and line.endswith(hi_phrase):
                pre = line[:len(line) - len(hi_phrase)]
                x0 = lx + int(draw.textlength(pre, font=hfont))
                ww_px = int(draw.textlength(hi_phrase, font=hfont))
                px_pad = int(fs_hl * 0.16)
                draw.rounded_rectangle(
                    [x0 - px_pad, y + int(fs_hl * 0.04), x0 + ww_px + px_pad, y + int(fs_hl * 1.14)],
                    radius=int(fs_hl * 0.12), fill=(*c["btn"], 255))
            draw.text((lx + 2, y + 2), line, font=hfont, fill=(0, 0, 0, 140))
            draw.text((lx, y),     line, font=hfont, fill=(255, 255, 255, 255))
            y += lh_hl

        # ── Hook text ──────────────────────────────────────────────────
        y = hook_y
        for line in hook_lines:
            draw.text((_line_x(line, sfont), y), line, font=sfont, fill=(224, 224, 224, 235))
            y += lh_sub

        # ── CTA pill: filled (classic/social/bold) or outlined + centered (editorial)
        btn_x = (w - btn_w_px) // 2 if centered else pad
        if centered:
            ow = max(3, int(h * 0.0035))
            draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w_px, btn_y + btn_h_px],
                                   radius=int(btn_h_px / 2), outline=(255, 255, 255, 255), width=ow)
            btn_txt_col = (255, 255, 255, 255)
        else:
            draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w_px, btn_y + btn_h_px],
                                   radius=int(btn_h_px / 2), fill=(*c["btn"], 255))
            btn_txt_col = (*c["btn_txt"], 255)
        content_x = btn_x + (btn_w_px - content_w) // 2
        # Label (vertically centered)
        lbbox = draw.textbbox((0, 0), cta_label, font=bfont)
        ty = btn_y + (btn_h_px - (lbbox[3] - lbbox[1])) // 2 - lbbox[1]
        draw.text((content_x, ty), cta_label, font=bfont, fill=btn_txt_col)
        # Vector arrow → (drawn, not a font glyph, so it always renders)
        ax = content_x + label_w + arrow_gap
        ay = btn_y + btn_h_px // 2
        aw = max(2, int(fs_btn * 0.11))
        draw.line([(ax, ay), (ax + arrow_len, ay)], fill=btn_txt_col, width=aw)
        hs = int(fs_btn * 0.30)
        draw.polygon(
            [(ax + arrow_len, ay), (ax + arrow_len - hs, ay - hs), (ax + arrow_len - hs, ay + hs)],
            fill=btn_txt_col,
        )

        img.convert("RGB").save(image_path, "JPEG", quality=93)
        print(f"  ✏️  Ad creative applied ({industry}, {layout})")

    except Exception as e:
        print(f"  ⚠️  Ad creative skipped: {e}")


NEGATIVE_PROMPT = (
    "blurry, out of focus, low quality, pixelated, noisy, grainy, "
    "generic stock photo, cheesy smile, forced pose, watermark, logo, "
    "text, caption, oversaturated, overexposed, underexposed, "
    "cartoon, illustration, painting, drawing, ugly, deformed, "
    "amateur photography, bad lighting, harsh shadows, "
    "dark, dim, gloomy, dimly lit, low-key lighting, heavy vignette, "
    "candlelit darkness, murky, dull colors, desaturated, flat lighting"
)

IMAGE_SIZES = {
    "meta": "portrait_4_3",      # 4:5 for Instagram feed
    "tiktok": "portrait_16_9",   # 9:16 vertical for TikTok
    "linkedin": "landscape_4_3", # 16:9 horizontal for LinkedIn
}


def _generate_base_image(image_prompt, image_path, platform, industry, config, upscale=True):
    """Generate ONE raw photo via Fal.ai (optional reference img2img) + AuraSR upscale.
    Saves to image_path. Does NOT apply the text overlay. Returns the source CDN url."""
    import fal_client
    model = config["image_generation"]["model"]

    # Reference image as a style anchor (image-to-image) if one exists for this industry
    ref_dir = f"client_assets/references/{industry}"
    ref_images = []
    if os.path.exists(ref_dir):
        ref_images = [f for f in os.listdir(ref_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]

    if ref_images:
        with open(f"{ref_dir}/{ref_images[0]}", "rb") as rf:
            ref_url = fal_client.upload(rf.read(), content_type="image/jpeg")
        result = fal_client.run(f"fal-ai/{model}", arguments={
            "prompt": image_prompt,
            "image_url": ref_url,
            "image_size": IMAGE_SIZES.get(platform, "square_hd"),
            "strength": 0.75,
            "num_images": 1,
        })
    else:
        result = fal_client.run(f"fal-ai/{model}", arguments={
            "prompt": image_prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "image_size": IMAGE_SIZES.get(platform, "square_hd"),
            "num_images": 1,
        })

    image_url = result["images"][0]["url"]
    response = requests.get(image_url, timeout=60)
    response.raise_for_status()
    with open(image_path, "wb") as f:
        f.write(response.content)

    if upscale:
        _upscale_inplace(image_path)

    return image_url


def _upscale_inplace(image_path):
    """4x AuraSR upscale of a saved image, in place. Silently skipped on failure."""
    import fal_client
    try:
        with open(image_path, "rb") as f:
            up_url = fal_client.upload(f.read(), content_type="image/jpeg")
        up_result = fal_client.run("fal-ai/aura-sr", arguments={
            "image_url": up_url, "upscaling_factor": 4, "overlapping_tiles": True})
        up_img = requests.get(up_result["image"]["url"], timeout=60)
        up_img.raise_for_status()
        with open(image_path, "wb") as f:
            f.write(up_img.content)
    except Exception as up_err:
        print(f"  ⚠️  Upscale skipped: {up_err}")


KONTEXT_ASPECTS = {"meta": "3:4", "tiktok": "9:16", "linkedin": "16:9"}

EDIT_PROMPT = (
    "Turn this photo into a premium Instagram advertisement photograph. Keep the exact "
    "same subject, products, people and setting — clearly recognizable, nothing replaced. "
    "Apply professional commercial retouching: bright natural daylight, vibrant saturated "
    "colors, crisp sharp focus on the main subject, clean uncluttered composition with the "
    "subject in the upper two thirds of the frame. Make the bottom third of the frame "
    "simple and softly blurred so ad copy can be placed over it. "
    "No text, no logos, no watermarks in the image."
)


def _edit_scraped_image(source_url, image_path, platform, config):
    """Re-shoot a real photo from the client's website with Fal's Kontext editing model:
    the actual product/venue stays recognizable, but lighting, color and composition are
    upgraded to ad quality. Saves to image_path."""
    import fal_client
    r = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    up_url = fal_client.upload(r.content, content_type="image/jpeg")
    result = fal_client.run("fal-ai/flux-pro/kontext", arguments={
        "prompt": EDIT_PROMPT,
        "image_url": up_url,
        "aspect_ratio": KONTEXT_ASPECTS.get(platform, "3:4"),
        "guidance_scale": 3.5,
        "output_format": "jpeg",
    })
    img_url = result["images"][0]["url"]
    resp = requests.get(img_url, timeout=60)
    resp.raise_for_status()
    with open(image_path, "wb") as f:
        f.write(resp.content)
    _upscale_inplace(image_path)


VARIANT_LAYOUTS = {
    # variant strategy → visual archetype, so the three ads read as three
    # different creatives instead of one template with swapped text
    0: "social_proof",  # variant_1: star row + real review numbers
    1: "bold",          # variant_2: oversized urgency headline + marker highlight
    2: "editorial",     # variant_3: centered serif story composition
}


def generate_variant_images(data, output_dir, config, industry="general_business",
                            scraped_images=None, brand_signals=None):
    """Generate a real, finished ad image for EVERY variant of every platform — in
    parallel — so the reviewer can pick based on the actual creative, not a mockup.
    When the client's website has real photos, each variant remixes a DIFFERENT site
    photo via Kontext (actual product/venue in the ad); fresh generation is the
    fallback. Each variant gets image_path = output/.../images/{platform}_{variant}.jpg."""
    provider = config["image_generation"]["provider"]
    model = config["image_generation"]["model"]
    scraped_images = scraped_images or []
    if scraped_images:
        print(f"\n🎨 Remixing {len(scraped_images)} real site photos with Kontext (+ {provider} {model} fallback)...")
    else:
        print(f"\n🎨 Generating variant preview images with {provider} ({model})...")
    images_dir = f"{output_dir}/images"
    os.makedirs(images_dir, exist_ok=True)
    eyebrow = data.get("location", "")

    jobs = []
    for platform, pdata in data["platforms"].items():
        for vkey, vdata in pdata.items():
            if vkey.startswith("variant_"):
                jobs.append((platform, vkey, vdata))

    def _one(job):
        platform, vkey, vdata = job
        image_path = f"{images_dir}/{platform}_{vkey}.jpg"
        try:
            # variant_1 → site photo 1, variant_2 → site photo 2, ... so the three
            # ads don't all look like the same template with different text
            vnum = int(vkey.split("_")[-1]) - 1
            source = scraped_images[vnum] if vnum < len(scraped_images) else None
            made_from = "generated"
            if source:
                try:
                    _edit_scraped_image(source, image_path, platform, config)
                    made_from = "site photo"
                except Exception as edit_err:
                    print(f"  ⚠️  {platform}/{vkey} photo edit failed ({edit_err}) — generating fresh")
                    _generate_base_image(vdata.get("image_prompt", ""), image_path, platform, industry, config)
            else:
                _generate_base_image(vdata.get("image_prompt", ""), image_path, platform, industry, config)
            headline = vdata.get("headline", "")
            hook = vdata.get("hook", "") or vdata.get("overlay", "")
            cta = vdata.get("cta", "Learn More")
            layout = VARIANT_LAYOUTS.get(vnum, "classic")
            _create_ad_creative(image_path, headline, hook, cta, industry, eyebrow,
                                layout=layout, signals=brand_signals)
            vdata["image_path"] = image_path
            return f"  ✅ {platform}/{vkey} ({made_from}, {layout}): {image_path}"
        except Exception as e:
            return f"  ⚠️  {platform}/{vkey} failed: {e}"

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as ex:
        for line in ex.map(_one, jobs):
            print(line)

    return data


def generate_images(data, output_dir, config, industry="general_business"):
    """Generate the final image for the SELECTED (flattened) variant of each platform.
    Used by the CLI path. The web path pre-generates per-variant images instead."""
    provider = config["image_generation"]["provider"]
    model = config["image_generation"]["model"]
    print(f"\n🎨 Generating images with {provider} ({model})...")
    images_dir = f"{output_dir}/images"
    os.makedirs(images_dir, exist_ok=True)
    eyebrow = data.get("location", "")

    for platform in list(data["platforms"].keys()):
        image_path = f"{images_dir}/{platform}.jpg"
        try:
            image_url = _generate_base_image(
                data["platforms"][platform].get("image_prompt", ""),
                image_path, platform, industry, config,
            )
            headline = data["platforms"][platform].get("headline", "")
            hook = data["platforms"][platform].get("hook", "") or data["platforms"][platform].get("overlay", "")
            cta = data["platforms"][platform].get("cta", "Learn More")
            _create_ad_creative(image_path, headline, hook, cta, industry, eyebrow)
            data["platforms"][platform]["image_url"] = image_url
            data["platforms"][platform]["image_path"] = image_path
            print(f"  ✅ {platform}: saved to {image_path}")
        except Exception as e:
            print(f"  ⚠️  {platform} image failed: {e}")

    return data

def _save_html_preview(data, output_dir):
    client = data.get("client", "")
    location = data.get("location", "")
    cards_html = ""

    for platform_key, platform_data in data["platforms"].items():
        # Embed image as base64 so preview.html is self-contained (works when downloaded)
        image_abs = f"{output_dir}/images/{platform_key}.jpg"
        if os.path.exists(image_abs):
            import base64
            with open(image_abs, "rb") as _f:
                _b64 = base64.b64encode(_f.read()).decode()
            image_block = f'<img class="post-img" src="data:image/jpeg;base64,{_b64}" alt="Ad image">'
        else:
            image_block = '<div class="img-placeholder">📷</div>'

        if platform_key == "meta":
            hook     = platform_data.get("hook", "")
            headline = platform_data.get("headline", "")
            body     = platform_data.get("body", "")
            cta      = platform_data.get("cta", "Learn More")
            tags     = platform_data.get("hashtags", "")
            if isinstance(tags, list):
                tags = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)

            # image_block already set above via base64 embed

            cards_html += f"""
  <div class="ig-card">
    <div class="ig-header">
      <div class="ig-avatar"></div>
      <div class="ig-meta">
        <div class="ig-handle">{client}</div>
        <div class="ig-sponsored">Sponsored</div>
      </div>
      <div class="ig-dots">&#8942;</div>
    </div>
    <p class="ig-caption"><strong>{hook}</strong></p>
    {image_block}
    <div class="ig-actions">
      <span class="ig-icon">♡</span>
      <span class="ig-icon">&#128172;</span>
      <span class="ig-icon">&#10148;</span>
    </div>
    <div class="ig-footer-copy">
      <div class="ig-likes">&#128077; 47 others</div>
      <p class="ig-body-text"><strong>{client}</strong> {body}</p>
      <p class="ig-tags">{tags}</p>
    </div>
    <div class="ig-cta-row">
      <div class="ig-cta-info">
        <div class="ig-domain">{location}</div>
        <div class="ig-headline">{headline}</div>
      </div>
      <button class="ig-cta-btn">{cta}</button>
    </div>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{client} — Ad Preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', -apple-system, sans-serif;
  background: #0a0a0a;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 16px 60px;
  color: #fff;
}}
.page-header {{
  text-align: center;
  margin-bottom: 36px;
}}
.page-eyebrow {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #6366f1;
  margin-bottom: 10px;
}}
.page-title {{
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 6px;
}}
.page-sub {{
  font-size: 14px;
  color: #6b7280;
}}
/* Instagram card */
.ig-card {{
  width: 375px;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  color: #111;
  box-shadow: 0 24px 60px rgba(0,0,0,0.6);
}}
.ig-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
}}
.ig-avatar {{
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
  flex-shrink: 0;
}}
.ig-meta {{ flex: 1; }}
.ig-handle {{ font-size: 13px; font-weight: 700; color: #111; }}
.ig-sponsored {{ font-size: 11px; color: #8e8e8e; }}
.ig-dots {{ font-size: 20px; color: #8e8e8e; cursor: pointer; }}
.ig-caption {{
  font-size: 13px;
  color: #111;
  line-height: 1.5;
  padding: 0 14px 10px;
}}
.post-img {{
  width: 100%;
  aspect-ratio: 4/5;
  object-fit: cover;
  display: block;
}}
.img-placeholder {{
  width: 100%;
  aspect-ratio: 4/5;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
}}
.ig-actions {{
  display: flex;
  gap: 14px;
  padding: 10px 14px 6px;
}}
.ig-icon {{ font-size: 22px; cursor: pointer; }}
.ig-footer-copy {{ padding: 0 14px 10px; }}
.ig-likes {{ font-size: 13px; font-weight: 600; color: #111; margin-bottom: 4px; }}
.ig-body-text {{
  font-size: 13px;
  color: #333;
  line-height: 1.5;
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.ig-tags {{ font-size: 13px; color: #00376b; line-height: 1.5; }}
.ig-cta-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px 14px;
  border-top: 1px solid #efefef;
  background: #fafafa;
}}
.ig-domain {{ font-size: 10px; color: #8e8e8e; text-transform: uppercase; letter-spacing: 0.05em; }}
.ig-headline {{ font-size: 14px; font-weight: 700; color: #111; margin-top: 2px; }}
.ig-cta-btn {{
  background: #0095f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}}
.footer {{
  margin-top: 36px;
  font-size: 11px;
  color: #374151;
  letter-spacing: 0.05em;
}}
</style>
</head>
<body>
<div class="page-header">
  <p class="page-eyebrow">Mettics Creative Agent</p>
  <h1 class="page-title">{client}</h1>
  <p class="page-sub">{location} &nbsp;·&nbsp; Instagram / Meta</p>
</div>
{cards_html}
<p class="footer">GENERATED BY METTICS COMMUNITY TRUST CREATIVE AGENT</p>
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
        is_valid_output, data, val_error = validate_output(campaign_json)
        if not is_valid_output:
            print(f"❌ Output validation failed: {val_error}")
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
import os
import json
import requests
import anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

def get_output_dir(company_name):
    """Generate output folder name from company name."""
    clean_name = company_name.lower().strip()
    clean_name = clean_name.replace(" ", "_")
    return f"output/{clean_name}_v1"

def search_business(company_name, location):
    """Search DuckDuckGo for the business and return top URLs."""
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

def scrape_website(url):
    """Scrape a website and return clean text and image URLs."""
    print(f"\n🌐 Scraping {url}...")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    
    h1s = [tag.get_text().strip() for tag in soup.find_all("h1")]
    h2s = [tag.get_text().strip() for tag in soup.find_all("h2")]
    paragraphs = [tag.get_text().strip() for tag in soup.find_all("p")]
    
    images = []
    for tag in soup.find_all("img"):
        src = tag.get("src", "")
        if src and not src.endswith(".svg") and "logo" in src.lower() or "hero" in src.lower():
            images.append(src)
    
    scraped = {
        "url": url,
        "h1": h1s,
        "h2": h2s,
        "paragraphs": paragraphs[:10],
        "images": images[:5]
    }
    
    print(f"✅ Scraped {len(paragraphs)} paragraphs and {len(images)} images")
    return scraped

def validate_scrape(scraped_data, company_name, location):
    """Validate that we scraped the right business."""
    print(f"\n✔️  Validating scrape...")
    
    errors = []
    
    if not scraped_data["h1"] and not scraped_data["paragraphs"]:
        errors.append("No content found on page")
    
    if len(scraped_data["paragraphs"]) < 2:
        errors.append("Too little content scraped — may be wrong page")
    
    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False
    
    print(f"✅ Scrape validated — content looks good")
    return True

def generate_campaign(scraped_data, company_name, location, config):
    """Send scraped data to Claude for campaign generation."""
    print(f"\n🤖 Sending to Claude for campaign generation...")
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    context = f"""
Company: {company_name}
Location: {location}
Website: {scraped_data['url']}

HEADINGS FOUND ON SITE:
{chr(10).join(scraped_data['h1'] + scraped_data['h2'])}

CONTENT FOUND ON SITE:
{chr(10).join(scraped_data['paragraphs'])}

IMAGE URLS FOUND:
{chr(10).join(scraped_data['images'])}

PLATFORMS TO GENERATE FOR: {', '.join(config['platforms'])}
IMAGE PROVIDER: {config['image_generation']['provider']} 
IMAGE MODEL: {config['image_generation']['model']}
COST PER IMAGE: ${config['image_generation']['cost_per_image']}
"""

    system_prompt = open("PROMPTS.md").read()
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Generate a complete campaign for {company_name} in {location}. Here is all the data scraped from their website:\n\n{context}\n\nReturn ONLY a valid JSON object matching the campaign.json structure. No markdown, no explanation, just the JSON."
            }
        ]
    )
    
    print(f"✅ Claude generated campaign")
    return message.content[0].text

def validate_output(campaign_json):
    """Validate the AI generated campaign JSON."""
    print(f"\n✔️  Validating campaign output...")
    
    errors = []
    
    try:
        data = json.loads(campaign_json)
    except json.JSONDecodeError:
        errors.append("Output is not valid JSON")
        for error in errors:
            print(f"❌ {error}")
        return False, None
    
    required_platforms = ["meta", "tiktok", "linkedin"]
    for platform in required_platforms:
        if platform not in data.get("platforms", {}):
            errors.append(f"Missing platform: {platform}")
    
    required_fields = ["hook", "cta", "image_prompt"]
    for platform in required_platforms:
        if platform in data.get("platforms", {}):
            for field in required_fields:
                if field not in data["platforms"][platform]:
                    errors.append(f"Missing field '{field}' in {platform}")
    
    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False, None
    
    print(f"✅ Campaign output validated — all fields present")
    return True, data

def save_output(data, output_dir):
    """Save campaign to markdown and JSON files."""
    print(f"\n💾 Saving output to {output_dir}...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Save JSON
    with open(f"{output_dir}/campaign.json", "w") as f:
        json.dump(data, f, indent=2)
    
    # Save Meta
    with open(f"{output_dir}/meta.md", "w") as f:
        meta = data["platforms"]["meta"]
        f.write(f"# Meta Campaign — {data['client']}\n")
        f.write(f"## Location: {data['location']}\n\n")
        f.write(f"**Hook:** {meta['hook']}\n\n")
        f.write(f"**Body:** {meta.get('body', '')}\n\n")
        f.write(f"**CTA:** {meta['cta']}\n\n")
        f.write(f"**Image Prompt:** {meta['image_prompt']}\n")
    
    # Save TikTok
    with open(f"{output_dir}/tiktok.md", "w") as f:
        tiktok = data["platforms"]["tiktok"]
        f.write(f"# TikTok Campaign — {data['client']}\n")
        f.write(f"## Location: {data['location']}\n\n")
        f.write(f"**Hook:** {tiktok['hook']}\n\n")
        f.write(f"**Script:** {tiktok.get('script', '')}\n\n")
        f.write(f"**CTA:** {tiktok['cta']}\n\n")
        f.write(f"**Image Prompt:** {tiktok['image_prompt']}\n")
    
    # Save LinkedIn
    with open(f"{output_dir}/linkedin.md", "w") as f:
        linkedin = data["platforms"]["linkedin"]
        f.write(f"# LinkedIn Campaign — {data['client']}\n")
        f.write(f"## Location: {data['location']}\n\n")
        f.write(f"**Hook:** {linkedin['hook']}\n\n")
        f.write(f"**Body:** {linkedin.get('body', '')}\n\n")
        f.write(f"**CTA:** {linkedin['cta']}\n\n")
        f.write(f"**Image Prompt:** {linkedin['image_prompt']}\n")
    
    print(f"✅ Saved: meta.md, tiktok.md, linkedin.md, campaign.json")

if __name__ == "__main__":
    config = json.load(open("config.json"))
    
    company_name = input("Enter company name: ")
    location = input("Enter location (e.g. Brambleton VA): ")
    
    # Generate dynamic output directory
    output_dir = get_output_dir(company_name)
    config["output_dir"] = output_dir
    print(f"\n📁 Output will be saved to: {output_dir}")
    
    # Stage 1 — Search
    results = search_business(company_name, location)
    print("\nTop results found:")
    for i, r in enumerate(results):
        print(f"{i+1}. {r}")
    
    website_url = f"https://{results[0]}" if results else None
    
    if not website_url:
        print("❌ No results found. Exiting.")
        exit()
    
    # Stage 2 — Scrape and Validate
    scraped = scrape_website(website_url)
    is_valid = validate_scrape(scraped, company_name, location)
    
    if not is_valid:
        print("❌ Validation failed. Please check the URL manually.")
        exit()
    
    # Stage 3 — AI Generation (requires API key with credits)
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n❌ No Anthropic API key found in .env — skipping AI generation")
        print("✅ Stages 1 and 2 completed successfully")
        exit()
    
    try:
        campaign_json = generate_campaign(scraped, company_name, location, config)
    except Exception as e:
        if "credit balance" in str(e):
            print("\n❌ Anthropic API has no credits — skipping AI generation")
            print("✅ Stages 1 and 2 completed successfully")
            print("➡️  Add credits at: https://console.anthropic.com/settings/billing")
        else:
            print(f"\n❌ AI generation failed: {e}")
        exit()
    
    campaign_json = generate_campaign(scraped, company_name, location, config)
    
    # Stage 4 — Validate and Save Output
    is_valid_output, data = validate_output(campaign_json)
    
    if not is_valid_output:
        print("❌ Output validation failed. Campaign not saved.")
        exit()
    
    save_output(data, output_dir)
    
    print(f"\n🎉 Campaign complete! Files saved to {output_dir}")